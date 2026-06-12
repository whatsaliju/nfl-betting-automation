"""
WARPS-NFL Prediction Intervals

Derives team-level forecast uncertainty bands from historical residuals.
For each projection P, the interval is P + [q_lo, q_hi] of the residual
distribution, where residuals come from leave-year-out validation to avoid
circularity.

Outputs:
  warps_pi_summary.csv       — coverage calibration by confidence level
  warps_pi_by_bin.csv        — conditional interval widths by projection range
  warps_pi_team_results.csv  — per-team interval + hit/miss for validation years

Run:
    python warps_prediction_intervals.py

Requires: warps_backtest_team_results_v1_8.csv (from warps_nfl_model_v1_8.py)
"""

import numpy as np
import pandas as pd

RESULTS_PATH  = "warps_backtest_team_results_v1_8.csv"
VAL_YEARS     = [2022, 2023, 2024, 2025]
CONFIDENCE_LEVELS = [0.50, 0.60, 0.70, 0.80, 0.90]

# Projection bins (wins) for conditional intervals
BINS  = [0, 5, 7, 9, 11, 18]
LABELS = ["≤5", "5–7", "7–9", "9–11", "11+"]


def load_data():
    df = pd.read_csv(RESULTS_PATH)
    df = df.dropna(subset=["warps_error", "warps_wins", "wins"]).copy()
    df["residual"] = df["wins"] - df["warps_wins"]  # actual − predicted (signed)
    df["proj_bin"] = pd.cut(df["warps_wins"], bins=BINS, labels=LABELS, right=False)
    return df


def leave_year_out_residuals(df):
    """For each team-season, collect residuals from all other years (no data leakage)."""
    records = []
    seasons = sorted(df["season"].unique())
    for s in seasons:
        loo_resid = df.loc[df["season"] != s, "residual"].values
        records.append({"season": s, "loo_residuals": loo_resid})
    return records


def compute_interval(pred_wins, residuals, level):
    lo = (1 - level) / 2
    hi = 1 - lo
    q_lo = float(np.quantile(residuals, lo))
    q_hi = float(np.quantile(residuals, hi))
    return pred_wins + q_lo, pred_wins + q_hi


def run_calibration(df, loo_map):
    """Check actual coverage on each season using leave-year-out residuals."""
    rows = []
    for _, r in df.iterrows():
        s = int(r["season"])
        residuals = loo_map[s]
        pred = float(r["warps_wins"])
        actual = float(r["wins"])
        hit_by_level = {}
        for lvl in CONFIDENCE_LEVELS:
            lo, hi = compute_interval(pred, residuals, lvl)
            hit_by_level[f"hit_{int(lvl*100)}"] = int(lo <= actual <= hi)
            hit_by_level[f"lo_{int(lvl*100)}"]  = round(lo, 2)
            hit_by_level[f"hi_{int(lvl*100)}"]  = round(hi, 2)
        rows.append({
            "season":      s,
            "team":        r["team"],
            "warps_wins":  round(pred, 2),
            "actual_wins": actual,
            "proj_bin":    r["proj_bin"],
            **hit_by_level,
        })
    return pd.DataFrame(rows)


def coverage_summary(results_df, label, mask=None):
    sub = results_df if mask is None else results_df[mask]
    rows = []
    for lvl in CONFIDENCE_LEVELS:
        col = f"hit_{int(lvl*100)}"
        coverage = sub[col].mean()
        lo_col = f"lo_{int(lvl*100)}"
        hi_col = f"hi_{int(lvl*100)}"
        avg_width = (sub[hi_col] - sub[lo_col]).mean()
        rows.append({
            "sample":    label,
            "stated_pct": int(lvl * 100),
            "actual_pct": round(coverage * 100, 1),
            "avg_width":  round(avg_width, 2),
            "n":          len(sub),
        })
    return pd.DataFrame(rows)


def bin_intervals(df, loo_map):
    """Unconditional and bin-conditional interval widths using full-sample residuals."""
    global_resid = df["residual"].values
    rows = []

    # Unconditional
    for lvl in CONFIDENCE_LEVELS:
        lo_q = np.quantile(global_resid, (1 - lvl) / 2)
        hi_q = np.quantile(global_resid, 1 - (1 - lvl) / 2)
        rows.append({
            "bin":         "All",
            "n":           len(df),
            "stated_pct":  int(lvl * 100),
            "lower_adj":   round(lo_q, 3),
            "upper_adj":   round(hi_q, 3),
            "width":       round(hi_q - lo_q, 3),
        })

    # Conditional by projection bin
    for bin_label in LABELS:
        sub = df[df["proj_bin"] == bin_label]
        if len(sub) < 20:
            continue
        resid = sub["residual"].values
        for lvl in CONFIDENCE_LEVELS:
            lo_q = np.quantile(resid, (1 - lvl) / 2)
            hi_q = np.quantile(resid, 1 - (1 - lvl) / 2)
            rows.append({
                "bin":        bin_label,
                "n":          len(sub),
                "stated_pct": int(lvl * 100),
                "lower_adj":  round(lo_q, 3),
                "upper_adj":  round(hi_q, 3),
                "width":      round(hi_q - lo_q, 3),
            })

    return pd.DataFrame(rows)


def print_summary(cal_full, cal_val):
    print("\n" + "=" * 70)
    print("CALIBRATION — Leave-Year-Out (Full Sample)")
    print("=" * 70)
    print(f"{'Stated':>8}  {'Actual':>8}  {'Width':>8}  {'Diff':>8}")
    print("-" * 40)
    for _, r in cal_full[cal_full["sample"] == "Full (2000-2025)"].iterrows():
        diff = r["actual_pct"] - r["stated_pct"]
        print(f"  {r['stated_pct']:>5}%  {r['actual_pct']:>6.1f}%  {r['avg_width']:>6.2f}w  {diff:>+6.1f}pp")

    print("\n" + "=" * 70)
    print("CALIBRATION — Validation Window (2022-2025)")
    print("=" * 70)
    print(f"{'Stated':>8}  {'Actual':>8}  {'Width':>8}  {'Diff':>8}")
    print("-" * 40)
    for _, r in cal_full[cal_full["sample"] == "Validation (2022-2025)"].iterrows():
        diff = r["actual_pct"] - r["stated_pct"]
        print(f"  {r['stated_pct']:>5}%  {r['actual_pct']:>6.1f}%  {r['avg_width']:>6.2f}w  {diff:>+6.1f}pp")

    # Key stat for paper
    row80 = cal_full[
        (cal_full["sample"] == "Validation (2022-2025)") &
        (cal_full["stated_pct"] == 80)
    ]
    if not row80.empty:
        r = row80.iloc[0]
        print(f"\nKey result: 80% PI → {r['actual_pct']:.1f}% actual coverage on holdout "
              f"(avg width ±{r['avg_width']/2:.1f}w)")


def main():
    df = load_data()
    print(f"Loaded {len(df)} team-seasons ({df.season.min()}–{df.season.max()})")
    print(f"Overall residual: mean={df.residual.mean():.3f}  std={df.residual.std():.3f}  "
          f"MAE={df.residual.abs().mean():.3f}")

    # Leave-year-out residual map
    loo_records = leave_year_out_residuals(df)
    loo_map = {r["season"]: r["loo_residuals"] for r in loo_records}

    # Team-level calibration
    results = run_calibration(df, loo_map)
    results.to_csv("warps_pi_team_results.csv", index=False)

    # Coverage summary
    cal_full = coverage_summary(results, "Full (2000-2025)")
    cal_val  = coverage_summary(results, "Validation (2022-2025)",
                                 mask=results["season"].isin(VAL_YEARS))
    combined = pd.concat([cal_full, cal_val], ignore_index=True)
    combined.to_csv("warps_pi_summary.csv", index=False)

    # Bin-conditional widths
    bins_df = bin_intervals(df, loo_map)
    bins_df.to_csv("warps_pi_by_bin.csv", index=False)

    print_summary(combined, cal_val)

    print("\n[OUT] warps_pi_summary.csv")
    print("[OUT] warps_pi_by_bin.csv")
    print("[OUT] warps_pi_team_results.csv")


if __name__ == "__main__":
    main()
