"""
WARPS-NFL v1.7 — Bootstrap CI + Diebold-Mariano Statistical Validation

Runs on top of warps_backtest_team_results_v1_7.csv (already generated).
No re-running the model — pure statistical analysis of forecast errors.

Install:  pandas numpy (already installed)
Run:      python warps_bootstrap_v1_7.py

Output:
  warps_bootstrap_results_v1_7.csv   — per-bootstrap MAE samples
  warps_statistical_summary_v1_7.txt — publication-ready summary table
"""

import math
import sys
import numpy as np
import pandas as pd


N_BOOTSTRAP = 10_000
SEED        = 2026
CI_LEVEL    = 0.95


# ── Bootstrap helpers ─────────────────────────────────────────────────────────

def bootstrap_mae(errors: np.ndarray, n: int = N_BOOTSTRAP, seed: int = SEED) -> np.ndarray:
    """Return n bootstrap samples of MAE."""
    rng = np.random.default_rng(seed)
    k = len(errors)
    samples = rng.integers(0, k, size=(n, k))
    return np.mean(np.abs(errors[samples]), axis=1)


def bootstrap_mae_diff(errors_a: np.ndarray, errors_b: np.ndarray,
                        n: int = N_BOOTSTRAP, seed: int = SEED) -> np.ndarray:
    """Return n bootstrap samples of MAE(a) - MAE(b).
    Negative value means a is better than b."""
    rng = np.random.default_rng(seed)
    k = len(errors_a)
    idx = rng.integers(0, k, size=(n, k))
    diff = np.mean(np.abs(errors_a[idx]), axis=1) - np.mean(np.abs(errors_b[idx]), axis=1)
    return diff


def ci(samples: np.ndarray, level: float = CI_LEVEL):
    lo = (1 - level) / 2 * 100
    hi = (1 + level) / 2 * 100
    return np.percentile(samples, [lo, hi])


# ── Diebold-Mariano test ───────────────────────────────────────────────────────

def diebold_mariano(errors_a: np.ndarray, errors_b: np.ndarray) -> tuple[float, float]:
    """DM test: H0 equal accuracy, H1 model a is better (one-sided).
    Returns (DM statistic, p-value).
    d_t = |e_b| - |e_a|; positive mean → a is better.
    """
    d = np.abs(errors_b) - np.abs(errors_a)
    n = len(d)
    dm = np.mean(d) / (np.std(d, ddof=1) / math.sqrt(n))
    # one-sided p-value from standard normal (large n justified)
    p = 0.5 * math.erfc(dm / math.sqrt(2))
    return float(dm), float(p)


def sig_stars(p: float) -> str:
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    if p < 0.10:  return "."
    return "ns"


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    results_path = "warps_backtest_team_results_v1_7.csv"
    try:
        df = pd.read_csv(results_path)
    except FileNotFoundError:
        sys.exit(f"ERROR: {results_path} not found. Run warps_nfl_model_v1_7.py first.")

    # Drop rows with missing baselines (2015 has no prior-year Pythagorean for 2014)
    df = df.dropna(subset=["warps_error", "pyth_error", "pw_error"]).copy()
    df_val = df[df["season"].between(2022, 2025)].copy()

    we  = df["warps_error"].values
    pe  = df["pyth_error"].values
    pwe = df["pw_error"].values

    we_v  = df_val["warps_error"].values
    pe_v  = df_val["pyth_error"].values
    pwe_v = df_val["pw_error"].values

    print("=" * 70)
    print("WARPS-NFL v1.7 — Statistical Validation")
    print("=" * 70)
    print(f"Bootstrap iterations : {N_BOOTSTRAP:,}")
    print(f"Confidence level     : {CI_LEVEL*100:.0f}%")
    print(f"Full backtest obs    : {len(df)} team-seasons ({df['season'].min()}-{df['season'].max()})")
    print(f"Validation obs       : {len(df_val)} team-seasons (2022-2025)")

    # ── Full backtest: point estimates ────────────────────────────────────────
    print("\n" + "─" * 70)
    print("POINT ESTIMATES — Full Backtest (2015-2025)")
    print("─" * 70)

    warps_mae_full = float(np.mean(np.abs(we)))
    pyth_mae_full  = float(np.mean(np.abs(pe)))
    pw_mae_full    = float(np.mean(np.abs(pwe)))

    bs_warps = bootstrap_mae(we)
    bs_pyth  = bootstrap_mae(pe)
    bs_pw    = bootstrap_mae(pwe)
    ci_w = ci(bs_warps); ci_p = ci(bs_pyth); ci_pw = ci(bs_pw)

    print(f"  {'Model':<25}  {'MAE':>6}  {'95% CI':>20}")
    print(f"  {'─'*25}  {'─'*6}  {'─'*20}")
    print(f"  {'WARPS v1.7':<25}  {warps_mae_full:>6.3f}  [{ci_w[0]:.3f}, {ci_w[1]:.3f}]")
    print(f"  {'Pythagorean prior':<25}  {pyth_mae_full:>6.3f}  [{ci_p[0]:.3f}, {ci_p[1]:.3f}]")
    print(f"  {'Prior-year wins':<25}  {pw_mae_full:>6.3f}  [{ci_pw[0]:.3f}, {ci_pw[1]:.3f}]")

    # ── Full backtest: MAE differences ────────────────────────────────────────
    print("\n" + "─" * 70)
    print("MAE DIFFERENCES — Full Backtest (negative = WARPS better)")
    print("─" * 70)

    bs_wp = bootstrap_mae_diff(we, pe)
    bs_wpw = bootstrap_mae_diff(we, pwe)
    ci_wp = ci(bs_wp); ci_wpw = ci(bs_wpw)
    dm_wp,  p_wp  = diebold_mariano(we, pe)
    dm_wpw, p_wpw = diebold_mariano(we, pwe)

    print(f"  {'Comparison':<35}  {'Diff':>7}  {'95% CI':>20}  {'DM stat':>8}  {'p-val':>8}  sig")
    print(f"  {'─'*35}  {'─'*7}  {'─'*20}  {'─'*8}  {'─'*8}  {'─'*4}")
    d_wp  = warps_mae_full - pyth_mae_full
    d_wpw = warps_mae_full - pw_mae_full
    print(f"  {'WARPS vs Pythagorean':<35}  {d_wp:>+7.3f}  [{ci_wp[0]:+.3f}, {ci_wp[1]:+.3f}]  {dm_wp:>8.3f}  {p_wp:>8.4f}  {sig_stars(p_wp)}")
    print(f"  {'WARPS vs Prior Wins':<35}  {d_wpw:>+7.3f}  [{ci_wpw[0]:+.3f}, {ci_wpw[1]:+.3f}]  {dm_wpw:>8.3f}  {p_wpw:>8.4f}  {sig_stars(p_wpw)}")

    sig_note_wp  = "CI entirely negative → significant improvement" if ci_wp[1]  < 0 else "CI includes zero → not significant"
    sig_note_wpw = "CI entirely negative → significant improvement" if ci_wpw[1] < 0 else "CI includes zero → not significant"
    print(f"\n  vs Pythagorean : {sig_note_wp}")
    print(f"  vs Prior Wins  : {sig_note_wpw}")

    # ── Validation: point estimates ───────────────────────────────────────────
    print("\n" + "─" * 70)
    print("POINT ESTIMATES — Validation (2022-2025)")
    print("─" * 70)

    warps_mae_val = float(np.mean(np.abs(we_v)))
    pyth_mae_val  = float(np.mean(np.abs(pe_v)))
    pw_mae_val    = float(np.mean(np.abs(pwe_v)))

    bs_warps_v = bootstrap_mae(we_v)
    bs_pyth_v  = bootstrap_mae(pe_v)
    bs_pw_v    = bootstrap_mae(pwe_v)
    ci_wv = ci(bs_warps_v); ci_pv = ci(bs_pyth_v); ci_pwv = ci(bs_pw_v)

    print(f"  {'Model':<25}  {'MAE':>6}  {'95% CI':>20}")
    print(f"  {'─'*25}  {'─'*6}  {'─'*20}")
    print(f"  {'WARPS v1.7':<25}  {warps_mae_val:>6.3f}  [{ci_wv[0]:.3f}, {ci_wv[1]:.3f}]")
    print(f"  {'Pythagorean prior':<25}  {pyth_mae_val:>6.3f}  [{ci_pv[0]:.3f}, {ci_pv[1]:.3f}]")
    print(f"  {'Prior-year wins':<25}  {pw_mae_val:>6.3f}  [{ci_pwv[0]:.3f}, {ci_pwv[1]:.3f}]")

    # ── Validation: differences ───────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("MAE DIFFERENCES — Validation (negative = WARPS better)")
    print("─" * 70)

    bs_wp_v  = bootstrap_mae_diff(we_v, pe_v)
    bs_wpw_v = bootstrap_mae_diff(we_v, pwe_v)
    ci_wpv = ci(bs_wp_v); ci_wpwv = ci(bs_wpw_v)
    dm_wpv,  p_wpv  = diebold_mariano(we_v, pe_v)
    dm_wpwv, p_wpwv = diebold_mariano(we_v, pwe_v)

    d_wpv  = warps_mae_val - pyth_mae_val
    d_wpwv = warps_mae_val - pw_mae_val
    print(f"  {'Comparison':<35}  {'Diff':>7}  {'95% CI':>20}  {'DM stat':>8}  {'p-val':>8}  sig")
    print(f"  {'─'*35}  {'─'*7}  {'─'*20}  {'─'*8}  {'─'*8}  {'─'*4}")
    print(f"  {'WARPS vs Pythagorean':<35}  {d_wpv:>+7.3f}  [{ci_wpv[0]:+.3f}, {ci_wpv[1]:+.3f}]  {dm_wpv:>8.3f}  {p_wpv:>8.4f}  {sig_stars(p_wpv)}")
    print(f"  {'WARPS vs Prior Wins':<35}  {d_wpwv:>+7.3f}  [{ci_wpwv[0]:+.3f}, {ci_wpwv[1]:+.3f}]  {dm_wpwv:>8.3f}  {p_wpwv:>8.4f}  {sig_stars(p_wpwv)}")

    sig_note_wpv  = "CI entirely negative → significant improvement" if ci_wpv[1]  < 0 else "CI includes zero — improvement not significant at 5%"
    sig_note_wpwv = "CI entirely negative → significant improvement" if ci_wpwv[1] < 0 else "CI includes zero — improvement not significant at 5%"
    print(f"\n  vs Pythagorean : {sig_note_wpv}")
    print(f"  vs Prior Wins  : {sig_note_wpwv}")

    # ── Season-by-season win rate ──────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("SEASON-BY-SEASON: WARPS beats Pythagorean?")
    print("─" * 70)
    season_stats = df.groupby("season").agg(
        warps_mae=("warps_error", lambda x: np.mean(np.abs(x))),
        pyth_mae=("pyth_error",   lambda x: np.mean(np.abs(x))),
    ).reset_index()
    season_stats["warps_wins"] = season_stats["warps_mae"] < season_stats["pyth_mae"]
    win_count = season_stats["warps_wins"].sum()
    total = len(season_stats)
    print(f"  WARPS beats Pythagorean in {win_count}/{total} seasons")
    for _, r in season_stats.iterrows():
        marker = "✓" if r["warps_wins"] else "✗"
        print(f"    {int(r['season'])}  WARPS={r['warps_mae']:.3f}  Pyth={r['pyth_mae']:.3f}  {marker}")

    # ── Save CSV of bootstrap samples ─────────────────────────────────────────
    out = pd.DataFrame({
        "warps_mae_full_bs":   bs_warps,
        "pyth_mae_full_bs":    bs_pyth,
        "pw_mae_full_bs":      bs_pw,
        "diff_wp_full_bs":     bs_wp,
        "diff_wpw_full_bs":    bs_wpw,
        "warps_mae_val_bs":    bs_warps_v,
        "pyth_mae_val_bs":     bs_pyth_v,
        "diff_wp_val_bs":      bs_wp_v,
    })
    out.to_csv("warps_bootstrap_results_v1_7.csv", index=False)

    # ── Save text summary ────────────────────────────────────────────────────
    summary_lines = [
        "WARPS-NFL v1.7 Statistical Validation Summary",
        "=" * 55,
        "",
        "Model: pyth_edge=0.90, point_diff=0.10",
        "Hypers: regression_factor=0.75, logit_scale=5.5, sos_weight=0.0",
        f"Bootstrap iterations: {N_BOOTSTRAP:,} | CI level: {CI_LEVEL*100:.0f}%",
        "",
        "FULL BACKTEST (2015-2025, n=351)",
        f"  WARPS MAE:      {warps_mae_full:.3f}  95% CI [{ci_w[0]:.3f}, {ci_w[1]:.3f}]",
        f"  Pythagorean:    {pyth_mae_full:.3f}  95% CI [{ci_p[0]:.3f}, {ci_p[1]:.3f}]",
        f"  Prior wins:     {pw_mae_full:.3f}  95% CI [{ci_pw[0]:.3f}, {ci_pw[1]:.3f}]",
        f"  vs Pythagorean: {d_wp:+.3f}  95% CI [{ci_wp[0]:+.3f}, {ci_wp[1]:+.3f}]  DM={dm_wp:.3f} p={p_wp:.4f} {sig_stars(p_wp)}",
        f"  vs Prior Wins:  {d_wpw:+.3f}  95% CI [{ci_wpw[0]:+.3f}, {ci_wpw[1]:+.3f}]  DM={dm_wpw:.3f} p={p_wpw:.4f} {sig_stars(p_wpw)}",
        f"  Season win rate vs Pythagorean: {win_count}/{total}",
        "",
        "VALIDATION (2022-2025, n=128)",
        f"  WARPS MAE:      {warps_mae_val:.3f}  95% CI [{ci_wv[0]:.3f}, {ci_wv[1]:.3f}]",
        f"  Pythagorean:    {pyth_mae_val:.3f}  95% CI [{ci_pv[0]:.3f}, {ci_pv[1]:.3f}]",
        f"  Prior wins:     {pw_mae_val:.3f}  95% CI [{ci_pwv[0]:.3f}, {ci_pwv[1]:.3f}]",
        f"  vs Pythagorean: {d_wpv:+.3f}  95% CI [{ci_wpv[0]:+.3f}, {ci_wpv[1]:+.3f}]  DM={dm_wpv:.3f} p={p_wpv:.4f} {sig_stars(p_wpv)}",
        f"  vs Prior Wins:  {d_wpwv:+.3f}  95% CI [{ci_wpwv[0]:+.3f}, {ci_wpwv[1]:+.3f}]  DM={dm_wpwv:.3f} p={p_wpwv:.4f} {sig_stars(p_wpwv)}",
        "",
        "Significance: *** p<0.001  ** p<0.01  * p<0.05  . p<0.10  ns p>=0.10",
    ]
    summary_text = "\n".join(summary_lines)
    with open("warps_statistical_summary_v1_7.txt", "w") as f:
        f.write(summary_text)

    print("\n" + "─" * 70)
    print("Outputs written:")
    print("  warps_bootstrap_results_v1_7.csv")
    print("  warps_statistical_summary_v1_7.txt")


if __name__ == "__main__":
    run()
