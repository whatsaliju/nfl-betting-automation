"""
WARPS-NFL Stability Analysis
============================

Answers three questions from the walk-forward research agenda:

  Q1. Is the coefficient stable?
      Walk-forward optimizer: for each prediction year Y (2010–2025),
      optimize weights on all data up to Y-1, record optimal parameters,
      then compute out-of-sample MAE for year Y.
      Output: stability table (median, IQR, min, max) + per-year weights CSV.

  Q2. Does WARPS win consistently?
      Uses existing warps_backtest_by_year_v1_8.csv (no data download needed).
      Output: year-by-year WARPS vs Pythagorean table + win-rate summary.

  Q3. Is the basin broad?
      Full-sample 2D grid search over Pythagorean weight × regression factor.
      Output: heatmap CSV + console table showing the MAE surface.

Usage:
    # Q2 only (no data download, runs immediately from existing CSVs):
    python warps_stability_analysis.py --q2-only

    # Full analysis (downloads PBP data ~1-2 GB, takes 20-40 minutes):
    python warps_stability_analysis.py

    # Skip walk-forward but run heatmap:
    python warps_stability_analysis.py --skip-q1

Install: pip install pandas numpy nfl_data_py
"""

import argparse
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# ── Q2: Year-by-year win consistency (from existing CSV) ──────────────────────

def run_q2(path="warps_backtest_by_year_v1_8.csv"):
    print("\n" + "=" * 70)
    print("Q2: DOES WARPS WIN CONSISTENTLY?")
    print("=" * 70)

    if not Path(path).exists():
        print(f"[ERROR] {path} not found. Run warps_nfl_model_v1_8.py first.")
        return None

    df = pd.read_csv(path)
    df = df.sort_values("season").copy()
    df["delta"] = df["pyth_mae"] - df["warps_mae"]   # positive = WARPS better
    df["warps_wins"] = df["delta"] > 0

    # Year-by-year table
    print(f"\n{'Year':<6} {'WARPS MAE':>10} {'Pyth MAE':>10} {'Delta':>8} {'Winner':>8}")
    print("-" * 46)
    for _, r in df.iterrows():
        winner = "WARPS" if r["delta"] > 0 else "Pyth "
        print(f"{int(r['season']):<6} {r['warps_mae']:>10.3f} {r['pyth_mae']:>10.3f} "
              f"{r['delta']:>+8.3f} {winner:>8}")

    # Summary
    n = len(df)
    w = df["warps_wins"].sum()
    avg_delta = df["delta"].mean()
    med_delta = df["delta"].median()
    win_deltas = df.loc[df["warps_wins"], "delta"]
    lose_deltas = df.loc[~df["warps_wins"], "delta"]

    print(f"\n{'Summary':}")
    print(f"  Seasons:          {n}")
    print(f"  WARPS wins:       {w}/{n} ({w/n*100:.0f}%)")
    print(f"  Pyth wins:        {n-w}/{n} ({(n-w)/n*100:.0f}%)")
    print(f"  Average delta:    {avg_delta:+.3f}w  (positive = WARPS better)")
    print(f"  Median delta:     {med_delta:+.3f}w")
    if len(win_deltas) > 0:
        print(f"  Avg margin (WARPS wins):  +{win_deltas.mean():.3f}w")
    if len(lose_deltas) > 0:
        print(f"  Avg margin (Pyth wins):   -{abs(lose_deltas.mean()):.3f}w")

    # Validation window
    val = df[df["season"].isin([2022, 2023, 2024, 2025])]
    if len(val) > 0:
        val_w = val["warps_wins"].sum()
        print(f"\n  Validation (2022–2025): WARPS wins {val_w}/{len(val)} "
              f"({val_w/len(val)*100:.0f}%)")
        print(f"  Avg delta validation: {val['delta'].mean():+.3f}w")

    df.to_csv("warps_q2_year_by_year.csv", index=False)
    print(f"\n[OUT] warps_q2_year_by_year.csv")
    return df


# ── Shared model core (adapted from warps_nfl_model_v1_8.py) ─────────────────

PYTH_EXPONENT = 2.37
HOME_FIELD    = 1.5
SCALE_FACTOR  = 3.0
COMPONENTS    = ["pass_epa", "rush_epa", "success", "explosive", "point_diff", "pyth_edge", "turnover"]

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "STL": "LAR",
    "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}

def norm_team(t):
    if pd.isna(t): return t
    return TEAM_ALIASES.get(str(t), str(t))

def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    std = s.std(ddof=0)
    return s * 0 if (std == 0 or pd.isna(std)) else (s - s.mean()) / std

def win_prob(spread, logit_scale=6.5):
    return 1 / (1 + np.exp(-spread / logit_scale))

def pyth_win_pct(pf, pa):
    pf, pa = max(float(pf), 1.0), max(float(pa), 1.0)
    return pf**PYTH_EXPONENT / (pf**PYTH_EXPONENT + pa**PYTH_EXPONENT)

def _w(**kw):
    return {c: kw.get(c, 0.0) for c in COMPONENTS}


def build_features(ts_diffs, regression_factor, pyth_w, pd_w):
    """Compute per-team ratings for a given Pythagorean/PD weight pair."""
    weights = _w(pyth_edge=pyth_w, point_diff=pd_w)
    total_w = pyth_w + pd_w or 1.0
    ratings = []
    for season, g in ts_diffs.groupby("season"):
        g = g.copy()
        g["warps_z"] = (
            weights["pyth_edge"]  * zscore(g["pyth_edge"])
            + weights["point_diff"] * zscore(g["point_diff_per_game"])
        ) / total_w
        raw = SCALE_FACTOR * g["warps_z"]
        g["rating_pts"] = raw * regression_factor
        g["raw_rating_pts"] = raw
        ratings.append(g[["season", "team", "rating_pts", "raw_rating_pts",
                           "pyth_wins_same_year", "games"]])
    return pd.concat(ratings, ignore_index=True)


def project_year(target, schedules, prior_ratings, logit_scale=6.5):
    prior = prior_ratings[prior_ratings["season"].eq(target - 1)]
    if prior.empty:
        return None
    proj_map = dict(zip(prior["team"], prior["rating_pts"]))
    reg = schedules[(schedules["season"].eq(target)) &
                    (schedules["game_type"].eq("REG"))].copy()
    if reg.empty:
        return None
    rows = []
    for _, g in reg.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        spread = proj_map.get(h, 0.0) - proj_map.get(a, 0.0) + HOME_FIELD
        wp = win_prob(spread, logit_scale)
        rows += [[target, h, wp], [target, a, 1 - wp]]
    proj = pd.DataFrame(rows, columns=["season", "team", "game_wp"])
    return proj.groupby(["season", "team"], as_index=False).agg(warps_wins=("game_wp", "sum"))


def evaluate_config(ts_diffs, schedules, target_years, pyth_w, pd_w, reg_f, logit=6.5):
    """MAE for a specific (pyth_w, pd_w, reg_f) config on target_years."""
    pr = build_features(ts_diffs, reg_f, pyth_w, pd_w)
    projs = [project_year(y, schedules, pr, logit) for y in target_years]
    projs = [p for p in projs if p is not None]
    if not projs:
        return np.nan
    proj = pd.concat(projs)
    actual = ts_diffs[["season", "team", "wins"]].copy()
    out = actual.merge(proj, on=["season", "team"])
    return np.mean(np.abs(out["warps_wins"] - out["wins"]))


def load_raw_data():
    """Load schedules + team stats from nfl_data_py. Slow (downloads ~1GB)."""
    try:
        import nfl_data_py as nfl
    except ImportError:
        raise SystemExit("pip install nfl_data_py")

    seasons = list(range(1999, 2026))
    print(f"[INFO] Loading schedules and PBP data for {seasons[0]}–{seasons[-1]} ...")
    schedules = nfl.import_schedules(seasons)
    schedules["home_team"] = schedules["home_team"].map(norm_team)
    schedules["away_team"] = schedules["away_team"].map(norm_team)

    pbp = nfl.import_pbp_data(seasons, downcast=True)
    pbp = pbp[pbp["season_type"].eq("REG")].copy()
    for col in ["posteam", "defteam"]:
        pbp[col] = pbp[col].map(norm_team)
    pbp = pbp.dropna(subset=["posteam", "defteam", "epa"])

    pass_plays = pbp[pbp["play_type"].eq("pass")]
    rush_plays = pbp[pbp["play_type"].eq("run")]
    turnover_col = "turnover" if "turnover" in pbp.columns else "interception"

    off_base = (pbp.groupby(["season", "posteam"], as_index=False)
                   .agg(off_epa_per_play=("epa", "mean"),
                        off_success=("success", "mean"),
                        off_explosive=("yards_gained", lambda x: np.mean(pd.to_numeric(x, errors="coerce").fillna(0) >= 20)),
                        off_turnovers=(turnover_col, "mean"))
                   .rename(columns={"posteam": "team"}))
    off_pass = (pass_plays.groupby(["season", "posteam"], as_index=False)
                          .agg(off_pass_epa=("epa", "mean")).rename(columns={"posteam": "team"}))
    off_rush = (rush_plays.groupby(["season", "posteam"], as_index=False)
                          .agg(off_rush_epa=("epa", "mean")).rename(columns={"posteam": "team"}))
    offense = off_base.merge(off_pass, on=["season", "team"], how="left").merge(off_rush, on=["season", "team"], how="left")

    def_base = (pbp.groupby(["season", "defteam"], as_index=False)
                   .agg(def_epa_allowed_per_play=("epa", "mean"),
                        def_success_allowed=("success", "mean"),
                        def_explosive_allowed=("yards_gained", lambda x: np.mean(pd.to_numeric(x, errors="coerce").fillna(0) >= 20)),
                        def_turnovers_forced=(turnover_col, "mean"))
                   .rename(columns={"defteam": "team"}))
    defense = def_base

    team_stats = offense.merge(defense, on=["season", "team"], how="inner")

    reg = schedules[schedules["game_type"].eq("REG")].copy().dropna(subset=["home_score", "away_score"])
    rows = []
    for _, g in reg.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        hw = 0.5 if hs == as_ else (1.0 if hs > as_ else 0.0)
        rows += [[int(g["season"]), h, hw, hs, as_], [int(g["season"]), a, 1-hw, as_, hs]]

    records = pd.DataFrame(rows, columns=["season", "team", "wins", "pf", "pa"])
    records = records.groupby(["season", "team"], as_index=False).agg(
        wins=("wins", "sum"), games=("wins", "count"), pf=("pf", "sum"), pa=("pa", "sum"))
    records["pyth_wins_same_year"] = records.apply(
        lambda r: pyth_win_pct(r["pf"], r["pa"]) * r["games"], axis=1)

    team_stats = team_stats.merge(records, on=["season", "team"], how="inner")

    # Derived features
    ts = team_stats.copy()
    ts["pass_epa_diff"]       = ts["off_pass_epa"] - ts.get("def_pass_epa_allowed", 0)
    ts["rush_epa_diff"]       = ts["off_rush_epa"] - ts.get("def_rush_epa_allowed", 0)
    ts["epa_diff"]            = ts["off_epa_per_play"] - ts.get("def_epa_allowed_per_play", 0)
    ts["success_diff"]        = ts["off_success"] - ts.get("def_success_allowed", 0)
    ts["explosive_diff"]      = ts["off_explosive"] - ts.get("def_explosive_allowed", 0)
    ts["point_diff_per_game"] = (ts["pf"] - ts["pa"]) / ts["games"]
    ts["pyth_edge"]           = ts["pyth_wins_same_year"] - (ts["games"] / 2)
    ts["turnover_margin"]     = ts.get("def_turnovers_forced", 0) - ts["off_turnovers"]

    print(f"[INFO] Loaded {len(ts)} team-season rows.")
    return schedules, ts


# ── Q1: Walk-forward coefficient stability ────────────────────────────────────

# Grid for the walk-forward optimizer (coarser than the main v1.8 grid to keep runtime manageable)
PYTH_WEIGHTS   = [0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00]
PD_WEIGHTS_MAP = {pw: round(1.0 - pw, 2) for pw in PYTH_WEIGHTS}  # pd = 1 - pyth
REGRESSION_GRID = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
LOGIT_SCALE    = 6.5

FIRST_PRED_YEAR = 2010   # minimum training window: 2000–2009 (10 seasons)
LAST_PRED_YEAR  = 2025


def run_q1(ts_diffs, schedules):
    print("\n" + "=" * 70)
    print("Q1: IS THE COEFFICIENT STABLE?  (walk-forward optimizer)")
    print("=" * 70)
    print(f"Predicting {FIRST_PRED_YEAR}–{LAST_PRED_YEAR}, one year at a time.")
    print(f"Grid: {len(PYTH_WEIGHTS)} pyth weights × {len(REGRESSION_GRID)} regression factors")
    print()

    all_years = list(range(2000, 2026))
    results = []

    for pred_year in range(FIRST_PRED_YEAR, LAST_PRED_YEAR + 1):
        train_years = [y for y in all_years if y < pred_year]
        train_data  = ts_diffs[ts_diffs["season"].isin(train_years)]

        best_mae, best_pyth, best_pd, best_r = np.inf, 0.75, 0.25, 0.75
        configs_run = 0

        for pyth_w in PYTH_WEIGHTS:
            pd_w = round(1.0 - pyth_w, 2)
            for reg_f in REGRESSION_GRID:
                mae_train = evaluate_config(train_data, schedules, train_years,
                                            pyth_w, pd_w, reg_f, LOGIT_SCALE)
                configs_run += 1
                if mae_train < best_mae:
                    best_mae  = mae_train
                    best_pyth = pyth_w
                    best_pd   = pd_w
                    best_r    = reg_f

        # Out-of-sample MAE for pred_year
        test_data = ts_diffs[ts_diffs["season"].isin(train_years + [pred_year])]
        oos_mae = evaluate_config(test_data, schedules, [pred_year],
                                  best_pyth, best_pd, best_r, LOGIT_SCALE)
        # Pythagorean baseline for pred_year
        pyth_baseline = evaluate_config(test_data, schedules, [pred_year],
                                        1.0, 0.0, best_r, LOGIT_SCALE)
        delta = (pyth_baseline or np.nan) - (oos_mae or np.nan)

        results.append({
            "pred_year":     pred_year,
            "train_seasons": len(train_years),
            "opt_pyth_w":    best_pyth,
            "opt_pd_w":      best_pd,
            "opt_r":         best_r,
            "train_mae":     round(best_mae, 4),
            "oos_mae":       round(oos_mae, 4) if not np.isnan(oos_mae) else None,
            "pyth_oos_mae":  round(pyth_baseline, 4) if not np.isnan(pyth_baseline) else None,
            "delta":         round(delta, 4),
        })
        print(f"  {pred_year}: pyth={best_pyth:.2f} pd={best_pd:.2f} R={best_r:.2f}  "
              f"train={best_mae:.3f}  OOS={oos_mae:.3f}  Δ={delta:+.3f}")

    df = pd.DataFrame(results)
    df.to_csv("warps_q1_walk_forward.csv", index=False)

    # Stability table
    print(f"\n{'─' * 60}")
    print("STABILITY TABLE  (optimal parameters across walk-forward windows)")
    print(f"{'─' * 60}")
    for col, label in [("opt_pyth_w", "Pythag Weight"), ("opt_pd_w", "PD Weight"), ("opt_r", "Regression R")]:
        s = df[col]
        q25, q75 = s.quantile(0.25), s.quantile(0.75)
        print(f"  {label:<18} median={s.median():.2f}  IQR=[{q25:.2f},{q75:.2f}]  "
              f"min={s.min():.2f}  max={s.max():.2f}")

    # Walk-forward win rate
    wins = (df["delta"] > 0).sum()
    print(f"\n  Walk-forward win rate: WARPS beats Pythagorean in {wins}/{len(df)} years "
          f"({wins/len(df)*100:.0f}%)")
    print(f"  Avg OOS delta: {df['delta'].mean():+.3f}w  "
          f"median: {df['delta'].median():+.3f}w")
    print(f"\n[OUT] warps_q1_walk_forward.csv")
    return df


# ── Q3: Basin shape (full-sample MAE heatmap) ─────────────────────────────────

HEATMAP_PYTH  = [0.40, 0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00]
HEATMAP_R     = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]


def run_q3(ts_diffs, schedules, full_years=None):
    print("\n" + "=" * 70)
    print("Q3: IS THE BASIN BROAD?  (full-sample MAE heatmap)")
    print("=" * 70)

    if full_years is None:
        full_years = list(range(2000, 2026))

    rows = []
    print(f"\n{'Pyth_W':>8} {'R':>6} {'MAE':>8}")
    print("-" * 26)
    for pyth_w in HEATMAP_PYTH:
        pd_w = round(1.0 - pyth_w, 2)
        for reg_f in HEATMAP_R:
            mae = evaluate_config(ts_diffs, schedules, full_years, pyth_w, pd_w, reg_f)
            rows.append({"pyth_w": pyth_w, "pd_w": pd_w, "reg_f": reg_f, "mae": round(mae, 4)})
            marker = " ★" if pyth_w == 0.75 and reg_f == 0.75 else ""
            print(f"  {pyth_w:>5.2f}  {reg_f:>5.2f}  {mae:>8.4f}{marker}")

    df = pd.DataFrame(rows)
    df.to_csv("warps_q3_heatmap.csv", index=False)

    # Basin summary: how far can you deviate from 0.75/0.75 before losing 0.05 MAE?
    champion_mae = df[(df.pyth_w == 0.75) & (df.reg_f == 0.75)]["mae"].values
    if len(champion_mae) > 0:
        threshold = champion_mae[0] + 0.05
        robust = df[df["mae"] <= threshold]
        print(f"\n  Champion (0.75/0.75) MAE:  {champion_mae[0]:.4f}")
        print(f"  Configs within +0.05 MAE:  {len(robust)} of {len(df)}")
        print(f"  Pyth weight range within threshold: "
              f"{robust['pyth_w'].min():.2f} – {robust['pyth_w'].max():.2f}")
        print(f"  R range within threshold:  "
              f"{robust['reg_f'].min():.2f} – {robust['reg_f'].max():.2f}")

    print(f"\n[OUT] warps_q3_heatmap.csv")
    return df


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WARPS stability analysis")
    parser.add_argument("--q2-only",  action="store_true",
                        help="Only run Q2 (uses existing CSV, no data download)")
    parser.add_argument("--skip-q1",  action="store_true",
                        help="Skip walk-forward optimizer (Q1), run Q2+Q3 only")
    parser.add_argument("--skip-q3",  action="store_true",
                        help="Skip heatmap (Q3)")
    args = parser.parse_args()

    # Q2 always runs first — no data download needed
    run_q2()

    if args.q2_only:
        print("\n[INFO] --q2-only: skipping Q1 and Q3.")
        return

    # Q1 and Q3 need the raw data
    print("\n[INFO] Loading raw NFL data for Q1/Q3 (may take 20–40 min first run)...")
    try:
        schedules, ts_diffs = load_raw_data()
    except Exception as e:
        print(f"[ERROR] Could not load data: {e}")
        print("[INFO] Run with --q2-only to skip Q1/Q3, or install nfl_data_py.")
        return

    if not args.skip_q1:
        run_q1(ts_diffs, schedules)

    if not args.skip_q3:
        run_q3(ts_diffs, schedules)

    print("\n✓ All analyses complete.")


if __name__ == "__main__":
    main()
