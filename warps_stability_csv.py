"""
WARPS Walk-Forward Stability Analysis — CSV-only version
=========================================================
Answers Q1 and Q3 from existing backtest CSVs without downloading raw data.

Math
----
Given champion parameters (w_pyth=0.75, w_pd=0.25, R=0.75) we stored:
  pyth_fc   = R * pyth_raw   + (1-R) * 8.5
  warps_wins = R * warps_raw + (1-R) * 8.5

So we can recover:
  pyth_raw  = (pyth_fc    - (1-R)*8.5) / R
  warps_raw = (warps_wins - (1-R)*8.5) / R

And since warps_raw = 0.75*pyth_raw + 0.25*pd_raw:
  pd_raw = 4*warps_raw - 3*pyth_raw

For any new (w_p, w_d, R_new) with w_p + w_d = 1:
  new_pred = R_new * (w_p*pyth_raw + w_d*pd_raw) + (1-R_new)*8.5

This is exact — verified to floating-point precision against the stored forecasts.
"""

import numpy as np
import pandas as pd

CHAMP_R = 0.75
CHAMP_W_PYTH = 0.75
CHAMP_W_PD = 0.25
LEAGUE_MEAN = 8.5

PYTH_WEIGHTS = np.round(np.arange(0.0, 1.01, 0.05), 2)   # 0.00 to 1.00 in 0.05 steps
REG_FACTORS  = np.round(np.arange(0.50, 0.96, 0.05), 2)   # 0.50 to 0.95 in 0.05 steps

FIRST_PRED = 2010   # first year used as test; trains on 2000..(Y-1)
LAST_PRED  = 2025


# ──────────────────────────────────────────────
# Load and enrich
# ──────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_csv("warps_backtest_team_results_v1_8.csv")
    R = CHAMP_R
    df["pyth_raw"]  = (df["pyth_fc"]    - (1 - R) * LEAGUE_MEAN) / R
    df["warps_raw"] = (df["warps_wins"] - (1 - R) * LEAGUE_MEAN) / R
    df["pd_raw"]    = (df["warps_raw"] - CHAMP_W_PYTH * df["pyth_raw"]) / CHAMP_W_PD
    return df


def predict(df: pd.DataFrame, w_p: float, R: float) -> pd.Series:
    w_d = 1.0 - w_p
    composite = w_p * df["pyth_raw"] + w_d * df["pd_raw"]
    return R * composite + (1 - R) * LEAGUE_MEAN


def mae(actual: pd.Series, pred: pd.Series) -> float:
    return (actual - pred).abs().mean()


# ──────────────────────────────────────────────
# Q1 — Walk-forward stability
# ──────────────────────────────────────────────

def run_q1(df: pd.DataFrame):
    print("=" * 70)
    print("Q1: COEFFICIENT STABILITY — WALK-FORWARD 2010–2025")
    print("=" * 70)
    print("For each year Y: train 2000..(Y-1), find (w_pyth, R) minimising MAE,")
    print("record OOS MAE for champion vs optimal.")
    print()

    records = []

    for year in range(FIRST_PRED, LAST_PRED + 1):
        train = df[df["season"] < year]
        test  = df[df["season"] == year]
        if train.empty or test.empty:
            continue

        best_mae_train = np.inf
        best_w, best_r = CHAMP_W_PYTH, CHAMP_R

        for w_p in PYTH_WEIGHTS:
            for R in REG_FACTORS:
                pred_train = predict(train, w_p, R)
                m = mae(train["wins"], pred_train)
                if m < best_mae_train:
                    best_mae_train = m
                    best_w, best_r  = w_p, R

        # OOS MAE for champion vs optimal
        champ_pred = predict(test, CHAMP_W_PYTH, CHAMP_R)
        opt_pred   = predict(test, best_w, best_r)
        champ_oos  = mae(test["wins"], champ_pred)
        opt_oos    = mae(test["wins"], opt_pred)

        records.append({
            "year": year,
            "train_n": len(train),
            "opt_w_pyth": best_w,
            "opt_R": best_r,
            "train_mae_opt": round(best_mae_train, 4),
            "oos_mae_champ": round(champ_oos, 4),
            "oos_mae_opt": round(opt_oos, 4),
            "oos_delta": round(champ_oos - opt_oos, 4),
        })

    results = pd.DataFrame(records)

    # Print table
    header = f"{'Year':>5}  {'w_pyth':>7}  {'R':>5}  {'TrainMAE':>9}  {'OOS_Champ':>10}  {'OOS_Opt':>8}  {'Delta':>7}"
    print(header)
    print("-" * len(header))
    for _, row in results.iterrows():
        star = " ✓" if abs(row.opt_w_pyth - CHAMP_W_PYTH) < 0.06 and abs(row.opt_R - CHAMP_R) < 0.06 else "  "
        print(f"{int(row.year):>5}  {row.opt_w_pyth:>7.2f}  {row.opt_R:>5.2f}  "
              f"{row.train_mae_opt:>9.4f}  {row.oos_mae_champ:>10.4f}  "
              f"{row.oos_mae_opt:>8.4f}  {row.oos_delta:>7.4f}{star}")

    print()
    print("Summary — optimal w_pyth across walk-forward windows")
    print(f"  Median w_pyth : {results.opt_w_pyth.median():.2f}  (champion = {CHAMP_W_PYTH})")
    print(f"  IQR           : [{results.opt_w_pyth.quantile(0.25):.2f}, {results.opt_w_pyth.quantile(0.75):.2f}]")
    print(f"  Min / Max     : {results.opt_w_pyth.min():.2f} / {results.opt_w_pyth.max():.2f}")
    print()
    print("Summary — optimal R (regression factor)")
    print(f"  Median R      : {results.opt_R.median():.2f}  (champion = {CHAMP_R})")
    print(f"  IQR           : [{results.opt_R.quantile(0.25):.2f}, {results.opt_R.quantile(0.75):.2f}]")
    print(f"  Min / Max     : {results.opt_R.min():.2f} / {results.opt_R.max():.2f}")
    print()

    # Count how often champion parameters are within one grid step of optimal
    near_champ = ((results.opt_w_pyth - CHAMP_W_PYTH).abs() < 0.06) & \
                 ((results.opt_R - CHAMP_R).abs() < 0.06)
    print(f"  Windows where optimal ≈ champion (±1 grid step): {near_champ.sum()}/{len(results)}")
    print()
    avg_oos_gap = results.oos_delta.mean()
    print(f"  Average OOS cost of using champion vs optimal: {avg_oos_gap:+.4f}w MAE")
    print(f"  (negative = champion beats the walk-forward optimal on OOS)")
    print()

    results.to_csv("warps_q1_walk_forward.csv", index=False)
    print("[OUT] warps_q1_walk_forward.csv")
    print()
    return results


# ──────────────────────────────────────────────
# Q3 — Basin width (full-sample)
# ──────────────────────────────────────────────

def run_q3(df: pd.DataFrame):
    print("=" * 70)
    print("Q3: BASIN WIDTH — 2D MAE LANDSCAPE (full sample 2000–2025)")
    print("=" * 70)
    print(f"Grid: w_pyth ∈ [{PYTH_WEIGHTS[0]}, {PYTH_WEIGHTS[-1]}] × R ∈ [{REG_FACTORS[0]}, {REG_FACTORS[-1]}]")
    print()

    rows = []
    champ_mae = mae(df["wins"], predict(df, CHAMP_W_PYTH, CHAMP_R))
    threshold = champ_mae + 0.05

    for w_p in PYTH_WEIGHTS:
        for R in REG_FACTORS:
            pred = predict(df, w_p, R)
            m    = mae(df["wins"], pred)
            rows.append({"w_pyth": w_p, "R": R, "mae": round(m, 4), "in_basin": m <= threshold})

    grid = pd.DataFrame(rows)
    n_basin = grid.in_basin.sum()
    n_total = len(grid)

    print(f"Champion MAE (full sample): {champ_mae:.4f}w")
    print(f"Basin threshold (+0.05w)  : {threshold:.4f}w")
    print(f"Configs within basin      : {n_basin}/{n_total} ({100*n_basin/n_total:.0f}%)")
    print()

    # Print heatmap table (R as columns, w_pyth as rows)
    pivot = grid.pivot(index="w_pyth", columns="R", values="mae")
    pivot = pivot.sort_index(ascending=False)

    col_labels = [f"R={r:.2f}" for r in REG_FACTORS]
    header_row = f"{'w_pyth':>7} | " + "  ".join(f"{c:>7}" for c in col_labels)
    print(header_row)
    print("-" * len(header_row))
    for w_p, row in pivot.iterrows():
        vals = []
        for R in REG_FACTORS:
            v = row[R]
            tag = "**" if (abs(w_p - CHAMP_W_PYTH) < 0.01 and abs(R - CHAMP_R) < 0.01) else ("  " if v <= threshold else "  ")
            marker = "★" if (abs(w_p - CHAMP_W_PYTH) < 0.01 and abs(R - CHAMP_R) < 0.01) else (" " if v <= threshold else " ")
            vals.append(f"{v:>6.3f}{marker}")
        print(f"{w_p:>7.2f} | " + "  ".join(vals))

    print()
    print("★ = champion config")
    print(f"Basin = configs within 0.05w MAE of champion ({champ_mae:.4f}w)")
    print()

    # Basin extent
    basin = grid[grid.in_basin]
    print("Basin extent:")
    print(f"  w_pyth range : [{basin.w_pyth.min():.2f}, {basin.w_pyth.max():.2f}]  "
          f"(width = {basin.w_pyth.max() - basin.w_pyth.min():.2f})")
    print(f"  R range      : [{basin.R.min():.2f}, {basin.R.max():.2f}]  "
          f"(width = {basin.R.max() - basin.R.min():.2f})")
    print()

    grid.to_csv("warps_q3_heatmap.csv", index=False)
    print("[OUT] warps_q3_heatmap.csv")
    print()
    return grid


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    df = load_data()
    print(f"Loaded {len(df)} team-seasons ({df.season.min()}–{df.season.max()})\n")
    run_q1(df)
    run_q3(df)
