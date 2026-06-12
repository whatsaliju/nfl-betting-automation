"""
WARPS-NFL EPA Null Result — Mechanism Analysis

The champion model assigns zero weight to all EPA-based metrics. This script
investigates WHY through three complementary analyses:

  1. Predictive correlation: correlation of each feature in year T with
     actual wins in year T+1 (how much raw signal does each metric carry?)

  2. Year-over-year stability: autocorrelation of each feature (feature_T
     vs feature_{T+1}); a high-correlation but low-stability signal is noise.

  3. Incremental R²: how much does each feature add to a Pythagorean-only
     OLS baseline? Quantifies redundancy.

Outputs:
  warps_epa_mechanism_correlations.csv  — feature-level predictive stats
  warps_epa_mechanism_incremental.csv   — incremental R² table
  warps_fig4_epa_mechanism.pdf/.png     — Figure 4 (two-panel chart)

Run:
    python warps_epa_mechanism.py

Requires: pip install nfl_data_py pandas numpy matplotlib scipy
Runtime:  ~30-60 min first run (data download); fast on subsequent runs.
"""

import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

from warps_stability_analysis import load_raw_data, norm_team

warnings.filterwarnings("ignore")

# Features to analyse
EPA_FEATURES  = ["epa_diff", "pass_epa_diff", "rush_epa_diff",
                  "success_diff", "explosive_diff", "turnover_margin"]
BASE_FEATURES = ["pyth_edge", "point_diff_per_game"]
ALL_FEATURES  = BASE_FEATURES + EPA_FEATURES

FEATURE_LABELS = {
    "pyth_edge":           "Pythagorean edge",
    "point_diff_per_game": "Point diff/game",
    "epa_diff":            "Net EPA/play",
    "pass_epa_diff":       "Pass EPA diff",
    "rush_epa_diff":       "Rush EPA diff",
    "success_diff":        "Success rate diff",
    "explosive_diff":      "Explosive play diff",
    "turnover_margin":     "Turnover margin",
}

BLUE   = "#2563eb"
ORANGE = "#ea580c"
GRAY   = "#94a3b8"
GREEN  = "#16a34a"


def build_lagged(ts):
    """Return df with year-T features paired with year-T+1 wins."""
    ts = ts.copy()
    next_wins = (ts[["season", "team", "wins"]]
                 .rename(columns={"season": "next_season", "wins": "next_wins"}))
    ts["next_season"] = ts["season"] + 1
    lagged = ts.merge(next_wins, on=["team", "next_season"], how="inner")
    return lagged


def build_autocorr(ts):
    """Return df with year-T feature paired with year-T+1 feature (for autocorr)."""
    ts = ts.copy()
    ts_next = ts[["season", "team"] + ALL_FEATURES].copy()
    ts_next["next_season"] = ts_next["season"]
    ts_next = ts_next.rename(columns={f: f"{f}_next" for f in ALL_FEATURES})
    ts["next_season"] = ts["season"] + 1
    ac = ts.merge(ts_next, on=["team", "next_season"], how="inner")
    return ac


def analysis_correlations(lagged):
    """Pearson r, partial r (controlling for pyth_edge), and p-value for each feature."""
    rows = []
    for feat in ALL_FEATURES:
        col_list = list(dict.fromkeys([feat, "next_wins", "pyth_edge"]))  # dedup when feat == "pyth_edge"
        sub = lagged[col_list].dropna()
        r, p = stats.pearsonr(sub[feat], sub["next_wins"])

        # Partial correlation: feat vs next_wins controlling for pyth_edge
        if feat != "pyth_edge":
            res_feat  = stats.linregress(sub["pyth_edge"], sub[feat])
            res_wins  = stats.linregress(sub["pyth_edge"], sub["next_wins"])
            e_feat    = sub[feat] - (res_feat.slope * sub["pyth_edge"] + res_feat.intercept)
            e_wins    = sub["next_wins"] - (res_wins.slope * sub["pyth_edge"] + res_wins.intercept)
            pr, pp    = stats.pearsonr(e_feat, e_wins)
        else:
            pr, pp    = r, p

        rows.append({
            "feature":       feat,
            "label":         FEATURE_LABELS[feat],
            "r_with_next_wins":   round(r, 4),
            "p_value":            round(p, 5),
            "partial_r_vs_pyth":  round(pr, 4),
            "partial_p":          round(pp, 5),
            "n":                  len(sub),
        })
    return pd.DataFrame(rows)


def analysis_autocorr(ac):
    """Year-over-year autocorrelation of each feature."""
    rows = []
    for feat in ALL_FEATURES:
        sub = ac[[feat, f"{feat}_next"]].dropna()
        r, p = stats.pearsonr(sub[feat], sub[f"{feat}_next"])
        rows.append({
            "feature":     feat,
            "label":       FEATURE_LABELS[feat],
            "autocorr":    round(r, 4),
            "p_value":     round(p, 5),
            "n":           len(sub),
        })
    return pd.DataFrame(rows)


def analysis_incremental_r2(lagged):
    """Incremental R² when adding each feature to a Pythagorean-only OLS baseline."""
    from numpy.linalg import lstsq

    def ols_r2(X, y):
        X_ = np.column_stack([np.ones(len(X)), X])
        beta, _, _, _ = lstsq(X_, y, rcond=None)
        y_hat = X_ @ beta
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        return 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    sub_base = lagged[["pyth_edge", "next_wins"]].dropna()
    r2_pyth  = ols_r2(sub_base[["pyth_edge"]].values, sub_base["next_wins"].values)

    # Pythagorean + point differential
    sub_pd = lagged[["pyth_edge", "point_diff_per_game", "next_wins"]].dropna()
    r2_pd  = ols_r2(sub_pd[["pyth_edge", "point_diff_per_game"]].values,
                    sub_pd["next_wins"].values)

    rows = [
        {"feature": "pyth_edge",           "label": "Pythagorean only",
         "r2": round(r2_pyth, 4), "delta_r2": 0.0},
        {"feature": "point_diff_per_game", "label": "+ Point diff/game",
         "r2": round(r2_pd, 4),  "delta_r2": round(r2_pd - r2_pyth, 4)},
    ]

    for feat in EPA_FEATURES:
        sub = lagged[["pyth_edge", feat, "next_wins"]].dropna()
        r2_epa = ols_r2(sub[["pyth_edge", feat]].values, sub["next_wins"].values)
        rows.append({
            "feature":   feat,
            "label":     f"+ {FEATURE_LABELS[feat]}",
            "r2":        round(r2_epa, 4),
            "delta_r2":  round(r2_epa - r2_pyth, 4),
        })

    return pd.DataFrame(rows)


def make_figure(corr_df, autocorr_df):
    plt.rcParams.update({
        "font.family": "serif",
        "font.size":   11,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "figure.dpi":        300,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.subplots_adjust(wspace=0.40)

    order    = ALL_FEATURES
    labels   = [FEATURE_LABELS[f] for f in order]
    x        = np.arange(len(order))
    colors   = [BLUE if f in BASE_FEATURES else ORANGE for f in order]

    # — Panel A: predictive correlation with next-year wins —
    r_vals   = corr_df.set_index("feature").loc[order, "r_with_next_wins"].values
    pr_vals  = corr_df.set_index("feature").loc[order, "partial_r_vs_pyth"].values

    bars = ax1.bar(x, r_vals, color=colors, alpha=0.80, width=0.45, label="Raw r")
    ax1.bar(x + 0.45, pr_vals, color=colors, alpha=0.35, width=0.45,
            label="Partial r (| Pythagorean)")
    ax1.axhline(0, color=GRAY, lw=0.8)
    ax1.set_xticks(x + 0.225)
    ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=8.5)
    ax1.set_ylabel("Pearson r with next-year wins", fontsize=9.5)
    ax1.legend(fontsize=8, frameon=False)
    ax1.text(0.02, 0.97, "A", transform=ax1.transAxes, fontweight="bold",
             fontsize=12, va="top")
    ax1.set_title("Predictive correlation with next-year wins\n"
                  "(partial r controls for Pythagorean)", fontsize=9.5)

    # — Panel B: year-over-year stability —
    ac_vals = autocorr_df.set_index("feature").loc[order, "autocorr"].values
    ax2.bar(x, ac_vals, color=colors, alpha=0.80, width=0.55)
    ax2.axhline(0, color=GRAY, lw=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=35, ha="right", fontsize=8.5)
    ax2.set_ylabel("Year-over-year autocorrelation", fontsize=9.5)
    ax2.text(0.02, 0.97, "B", transform=ax2.transAxes, fontweight="bold",
             fontsize=12, va="top")
    ax2.set_title("Year-over-year stability of each metric", fontsize=9.5)

    blue_patch  = plt.Rectangle((0,0),1,1, fc=BLUE,   alpha=0.8, label="Points-based")
    orange_patch = plt.Rectangle((0,0),1,1, fc=ORANGE, alpha=0.8, label="EPA-based")
    ax2.legend(handles=[blue_patch, orange_patch], fontsize=8, frameon=False)

    fig.suptitle(
        "Figure 4. Why EPA receives zero weight: predictive correlation and year-over-year stability\n"
        "Blue = points-based metrics (Pythagorean, point diff).  "
        "Orange = EPA-based metrics.",
        fontsize=10, y=1.01,
    )

    plt.savefig("warps_fig4_epa_mechanism.pdf", bbox_inches="tight")
    plt.savefig("warps_fig4_epa_mechanism.png", bbox_inches="tight")
    plt.close()
    print("[OUT] warps_fig4_epa_mechanism.pdf / .png")


def print_summary(corr_df, autocorr_df, incr_df):
    print("\n" + "=" * 70)
    print("PREDICTIVE CORRELATION (feature_T → wins_{T+1})")
    print("=" * 70)
    print(f"  {'Feature':<25}  {'Raw r':>7}  {'Partial r|Pyth':>15}  {'p(partial)':>12}")
    print("  " + "-" * 64)
    for _, r in corr_df.iterrows():
        tag = " *" if r["partial_p"] < 0.05 else "  "
        print(f"  {r['label']:<25}  {r['r_with_next_wins']:>+7.3f}  "
              f"{r['partial_r_vs_pyth']:>+15.3f}  {r['partial_p']:>10.4f}{tag}")

    print("\n" + "=" * 70)
    print("YEAR-OVER-YEAR STABILITY (autocorrelation)")
    print("=" * 70)
    print(f"  {'Feature':<25}  {'Autocorr':>9}  {'p':>8}")
    print("  " + "-" * 48)
    for _, r in autocorr_df.iterrows():
        print(f"  {r['label']:<25}  {r['autocorr']:>+9.3f}  {r['p_value']:>8.4f}")

    print("\n" + "=" * 70)
    print("INCREMENTAL R² BEYOND PYTHAGOREAN BASELINE")
    print("=" * 70)
    print(f"  {'Model':<30}  {'R²':>7}  {'ΔR²':>8}")
    print("  " + "-" * 50)
    for _, r in incr_df.iterrows():
        print(f"  {r['label']:<30}  {r['r2']:>7.4f}  {r['delta_r2']:>+8.4f}")


def main():
    print("Loading raw NFL data (may take 20–40 min first run)...")
    schedules, ts = load_raw_data()

    # Drop any duplicate columns that can arise from the merge chain in load_raw_data
    ts = ts.loc[:, ~ts.columns.duplicated()].copy()

    lagged   = build_lagged(ts)
    ac_data  = build_autocorr(ts)

    print(f"Lagged pairs: {len(lagged)}  |  Autocorr pairs: {len(ac_data)}")

    corr_df  = analysis_correlations(lagged)
    ac_df    = analysis_autocorr(ac_data)
    incr_df  = analysis_incremental_r2(lagged)

    corr_df.to_csv("warps_epa_mechanism_correlations.csv", index=False)
    incr_df.to_csv("warps_epa_mechanism_incremental.csv",  index=False)

    print_summary(corr_df, ac_df, incr_df)
    make_figure(corr_df, ac_df)

    print("\n[OUT] warps_epa_mechanism_correlations.csv")
    print("[OUT] warps_epa_mechanism_incremental.csv")


if __name__ == "__main__":
    main()
