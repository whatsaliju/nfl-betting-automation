"""
WARPS-NFL True Walk-Forward Retraining

Replaces the algebraic reconstruction used in the paper with genuine
re-optimization from raw inputs for each of the 16 expanding training
windows (2010–2025).

Produces the same output files read by warps_generate_figures.py:
  warps_q1_walk_forward.csv  — per-year optimal params + OOS delta
  warps_q3_heatmap.csv       — full-sample MAE landscape (210 configs)

Usage:
    python warps_walk_forward_true.py            # both Q1 + Q3
    python warps_walk_forward_true.py --q1-only  # walk-forward only
    python warps_walk_forward_true.py --q3-only  # heatmap only

Requires: pip install nfl_data_py pandas numpy
Runtime:  ~30-60 min first run (data download); faster on subsequent runs.
"""

import argparse
import math
import numpy as np
import pandas as pd

from warps_stability_analysis import (
    load_raw_data,
    evaluate_config,
    LOGIT_SCALE,
)

# Champion configuration (optimised on 2000–2021 training data)
CHAMP_PYTH = 0.75
CHAMP_PD   = 0.25
CHAMP_R    = 0.75

FIRST_PRED_YEAR = 2010
LAST_PRED_YEAR  = 2025

# Walk-forward parameter grid
WF_PYTH_WEIGHTS = [round(v * 0.05, 2) for v in range(10, 21)]  # 0.50 – 1.00
WF_REGRESSION   = [round(v * 0.05, 2) for v in range(10, 20)]  # 0.50 – 0.95

# Heatmap grid: 21 × 10 = 210 configs, matching the paper's basin analysis
HM_PYTH_WEIGHTS = [round(v * 0.05, 2) for v in range(0, 21)]   # 0.00 – 1.00
HM_REGRESSION   = [round(v * 0.05, 2) for v in range(10, 20)]  # 0.50 – 0.95


def run_q1(ts_diffs, schedules):
    """True walk-forward: retrain from raw inputs for each expanding window."""
    print("\n" + "=" * 70)
    print("Q1: TRUE WALK-FORWARD RETRAINING (2010–2025)")
    print("=" * 70)
    n_configs = len(WF_PYTH_WEIGHTS) * len(WF_REGRESSION)
    print(f"Grid: {len(WF_PYTH_WEIGHTS)} pyth weights × {len(WF_REGRESSION)} "
          f"R values = {n_configs} configs per window\n")

    all_years = list(range(2000, LAST_PRED_YEAR + 1))
    results = []

    for pred_year in range(FIRST_PRED_YEAR, LAST_PRED_YEAR + 1):
        train_years = [y for y in all_years if y < pred_year]
        train_data  = ts_diffs[ts_diffs["season"].isin(train_years)]
        train_n     = len(train_data)

        best_mae  = np.inf
        best_pyth = CHAMP_PYTH
        best_r    = CHAMP_R

        for pyth_w in WF_PYTH_WEIGHTS:
            pd_w = round(1.0 - pyth_w, 2)
            for reg_f in WF_REGRESSION:
                mae = evaluate_config(train_data, schedules, train_years,
                                      pyth_w, pd_w, reg_f, LOGIT_SCALE)
                if mae < best_mae:
                    best_mae  = mae
                    best_pyth = pyth_w
                    best_r    = reg_f

        # OOS MAE: window-optimal config
        test_data = ts_diffs[ts_diffs["season"].isin(train_years + [pred_year])]
        oos_opt   = evaluate_config(
            test_data, schedules, [pred_year],
            best_pyth, round(1.0 - best_pyth, 2), best_r, LOGIT_SCALE)

        # OOS MAE: fixed champion config
        oos_champ = evaluate_config(
            test_data, schedules, [pred_year],
            CHAMP_PYTH, CHAMP_PD, CHAMP_R, LOGIT_SCALE)

        oos_delta = (
            (oos_champ if not math.isnan(oos_champ) else np.nan)
            - (oos_opt  if not math.isnan(oos_opt)  else np.nan)
        )

        results.append({
            "year":          pred_year,
            "train_n":       train_n,
            "opt_w_pyth":    best_pyth,
            "opt_R":         best_r,
            "train_mae_opt": round(best_mae, 4),
            "oos_mae_champ": round(oos_champ, 4),
            "oos_mae_opt":   round(oos_opt, 4),
            "oos_delta":     round(oos_delta, 4),
        })
        print(f"  {pred_year}: pyth={best_pyth:.2f}  R={best_r:.2f}  "
              f"train={best_mae:.3f}  OOS_opt={oos_opt:.3f}  "
              f"OOS_champ={oos_champ:.3f}  Δ={oos_delta:+.4f}")

    df = pd.DataFrame(results)
    df.to_csv("warps_q1_walk_forward.csv", index=False)

    w_wins = (df["oos_delta"] > 0).sum()
    avg_d  = df["oos_delta"].mean()
    med_wpy = df["opt_w_pyth"].median()
    iqr_wpy = (df["opt_w_pyth"].quantile(0.25), df["opt_w_pyth"].quantile(0.75))
    print(f"\nStability summary:")
    print(f"  opt_w_pyth  median={med_wpy:.2f}  IQR=[{iqr_wpy[0]:.2f}, {iqr_wpy[1]:.2f}]  "
          f"min={df.opt_w_pyth.min():.2f}  max={df.opt_w_pyth.max():.2f}")
    print(f"  opt_R       median={df.opt_R.median():.2f}  "
          f"IQR=[{df.opt_R.quantile(0.25):.2f}, {df.opt_R.quantile(0.75):.2f}]  "
          f"min={df.opt_R.min():.2f}  max={df.opt_R.max():.2f}")
    print(f"  Champion beats window-optimal OOS: {w_wins}/{len(df)} windows")
    print(f"  Avg OOS delta (champ − opt):       {avg_d:+.4f}w")
    print(f"\n[OUT] warps_q1_walk_forward.csv")
    return df


def run_q3(ts_diffs, schedules):
    """Full-sample MAE heatmap: 21 × 10 = 210 configurations."""
    print("\n" + "=" * 70)
    print("Q3: MAE LANDSCAPE  (full sample 2000–2025, 210 configs)")
    print("=" * 70)

    full_years = list(range(2000, LAST_PRED_YEAR + 1))
    rows = []

    for pyth_w in HM_PYTH_WEIGHTS:
        pd_w = round(1.0 - pyth_w, 2)
        for reg_f in HM_REGRESSION:
            mae = evaluate_config(ts_diffs, schedules, full_years,
                                  pyth_w, pd_w, reg_f, LOGIT_SCALE)
            rows.append({"w_pyth": pyth_w, "R": reg_f, "mae": round(mae, 4)})

    df = pd.DataFrame(rows)

    champ_row = df[(df["w_pyth"] == CHAMP_PYTH) & (df["R"] == CHAMP_R)]
    champ_mae = champ_row["mae"].iloc[0]
    basin_thresh = champ_mae + 0.05
    df["in_basin"] = df["mae"] <= basin_thresh

    df.to_csv("warps_q3_heatmap.csv", index=False)

    n_basin = df["in_basin"].sum()
    min_row = df.loc[df["mae"].idxmin()]
    print(f"  Champion ({CHAMP_PYTH}/{CHAMP_R}) MAE:  {champ_mae:.4f}")
    print(f"  Full-sample min:              "
          f"w_pyth={min_row.w_pyth:.2f}  R={min_row.R:.2f}  MAE={min_row.mae:.4f}")
    print(f"  Basin (within +0.05w):        "
          f"{n_basin}/{len(df)} configs ({round(100 * n_basin / len(df))}%)")
    in_b = df[df["in_basin"]]
    print(f"  Basin w_pyth range:           {in_b.w_pyth.min():.2f} – {in_b.w_pyth.max():.2f}")
    print(f"  Basin R range:                {in_b.R.min():.2f} – {in_b.R.max():.2f}")
    print(f"\n[OUT] warps_q3_heatmap.csv")
    return df


def main():
    parser = argparse.ArgumentParser(
        description="WARPS true walk-forward retraining (replaces algebraic reconstruction)")
    parser.add_argument("--q1-only", action="store_true", help="Walk-forward only")
    parser.add_argument("--q3-only", action="store_true", help="Heatmap only")
    args = parser.parse_args()

    print("Loading raw NFL data (may take 20–40 min on first run)...")
    schedules, ts_diffs = load_raw_data()

    if not args.q3_only:
        run_q1(ts_diffs, schedules)
    if not args.q1_only:
        run_q3(ts_diffs, schedules)

    print("\nDone. Run warps_generate_figures.py to regenerate figures.")


if __name__ == "__main__":
    main()
