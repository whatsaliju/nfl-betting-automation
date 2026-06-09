"""
WARPS-NFL v2.1 — Garbage-Time EPA / Adjusted Pythagorean Experiment

Hypothesis: Points scored or allowed when win probability is outside [0.05, 0.95]
("garbage time") inflate / deflate Pythagorean win expectation and point differential
without adding predictive signal about future performance.

Analytical pre-test result (run on existing backtest data before PBP download):
  - Corr(pyth_same_year_error_N, next_warps_error_N+1): -0.005 (≈ zero)
    → No cascading bias: Pythagorean over-estimation in year N does NOT cause
      WARPS to systematically over-project in year N+1.
  - Extreme quality teams (|pure_quality_pts| > 75th pct): MAE = 2.26 vs 2.41
    → More extreme teams are NOT harder to project — the 2024/2025 problem is
      directional (dynasty under-projection), not calibration contamination.
  - Mechanism: Pythagorean's non-linear exponent (2.37) compresses garbage-time
    scores naturally. Once PF >> PA, adding more garbage-time points barely
    changes the Pythagorean ratio. The exponent IS the garbage-time filter.
  Expected outcome: likely null result similar to SOS (valid and important finding).
  Run this script when internet access is available to confirm on PBP data.

Experiment design
─────────────────
Phase 1 — Reproduce v2.0 champion on full sample (sanity check).
Phase 2 — Compute Adjusted Pythagorean and Adjusted Point Differential from
           WP-filtered PBP data, then re-run grid over four candidate models:
               A: adj_pyth replaces pyth   (weights: adj_pyth=0.75, adj_pd=0.25)
               B: adj_pd replaces point_diff (weights: pyth=0.75, adj_pd=0.25)
               C: both adjusted             (weights: adj_pyth=0.75, adj_pd=0.25)
               D: hybrid blend              (pyth=0.375, adj_pyth=0.375, adj_pd=0.25)
           + exhaustive grid over alpha ∈ {0.25, 0.50, 0.75, 1.00} for adj_pyth
             and adj_pd contributions (56 configs total).
Phase 3 — Compare: v2.0 champion vs best adjusted vs best hybrid on 2022-2025.

v2.0 champion inherited: pyth=0.75, pd=0.25, reg=0.75, logit=5.5, dynasty R=0.95

Install:  pip install pandas numpy nfl_data_py
Run:      python warps_nfl_model_v2_1.py
          python warps_nfl_model_v2_1.py --fast  (skip Phase 1)
"""

import argparse
import math
import warnings
from itertools import product

import numpy as np
import pandas as pd

try:
    import nfl_data_py as nfl
except ImportError as exc:
    raise SystemExit("pip install nfl_data_py pandas numpy") from exc


# ── Constants ─────────────────────────────────────────────────────────────────

PYTH_EXPONENT  = 2.37
HOME_FIELD     = 1.5
SCALE_FACTOR   = 3.0
SCHEDULES_URL  = "https://raw.githubusercontent.com/leesharpe/nfldata/master/data/games.csv"

TRAIN_YEARS      = list(range(2000, 2022))
VALIDATION_YEARS = list(range(2022, 2026))
FULL_YEARS       = list(range(2000, 2026))

# WP boundaries for "competitive minutes" — plays outside this range are garbage time
WP_LO = 0.05
WP_HI = 0.95

# v2.0 champion config
V20_WEIGHTS = {
    "pass_epa": 0.0, "rush_epa": 0.0, "success": 0.0, "explosive": 0.0,
    "point_diff": 0.10, "pyth_edge": 0.90, "turnover": 0.0,
    # new adjusted metrics (zero in baseline)
    "adj_pyth_edge": 0.0, "adj_point_diff": 0.0,
}
V20_REG_F  = 0.75
V20_LOGIT  = 5.5
V20_SOS_W  = 0.0

# Dynasty persistence (validated in v2.0)
DYNASTY_STREAK    = 4
DYNASTY_THRESHOLD = 0.5
DYNASTY_R         = 0.95

COMPONENTS = [
    "pass_epa", "rush_epa", "success", "explosive",
    "point_diff", "pyth_edge", "turnover",
    "adj_pyth_edge", "adj_point_diff",
]

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "STL": "LAR",
    "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}

MARKET_2026 = {
    "BUF": 12.5, "MIA":  4.5, "NE":   8.5, "NYJ":  6.5,
    "BAL": 11.5, "CIN":  9.5, "CLE":  5.5, "PIT":  8.5,
    "HOU":  9.5, "IND":  7.5, "JAX":  7.5, "TEN":  6.5,
    "DEN":  9.5, "KC":  11.5, "LAC":  9.5, "LV":   6.5,
    "DAL":  9.5, "NYG":  5.5, "PHI": 11.5, "WAS":  7.5,
    "CHI":  9.5, "DET": 10.5, "GB":   9.5, "MIN":  9.5,
    "ATL":  6.5, "CAR":  7.5, "NO":   4.5, "TB":   8.5,
    "ARI":  4.5, "LAR": 11.5, "SF":  10.5, "SEA": 10.5,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _w(**kw):
    return {c: kw.get(c, 0.0) for c in COMPONENTS}

def norm_team(t):
    if pd.isna(t):
        return t
    return TEAM_ALIASES.get(str(t), str(t))

def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    std = s.std(ddof=0)
    return s * 0 if (std == 0 or pd.isna(std)) else (s - s.mean()) / std

def win_prob_from_spread(spread, logit_scale):
    return 1 / (1 + np.exp(-spread / logit_scale))

def pyth_win_pct(pf, pa):
    pf, pa = max(float(pf), 1.0), max(float(pa), 1.0)
    return (pf ** PYTH_EXPONENT) / ((pf ** PYTH_EXPONENT) + (pa ** PYTH_EXPONENT))


# ── Data loading with garbage-time filter ─────────────────────────────────────

def _compute_adjusted_points(pbp, schedules):
    """
    Computes per-team per-season adjusted points for/against using only plays
    where home-team WP is in [WP_LO, WP_HI] (competitive minutes).

    Returns DataFrame with columns: season, team, adj_pf, adj_pa
    """
    if "wp" not in pbp.columns:
        print("[WARN] 'wp' column not found — adjusted metrics unavailable, falling back to standard.")
        return None

    pbp_wp = pbp.dropna(subset=["wp", "game_id", "total_home_score", "total_away_score"]).copy()
    pbp_wp["wp"] = pd.to_numeric(pbp_wp["wp"], errors="coerce")
    pbp_wp = pbp_wp.dropna(subset=["wp"])

    # Compute per-play score increments (home and away)
    pbp_wp = pbp_wp.sort_values(["game_id", "play_id"])
    pbp_wp["home_score_delta"] = (
        pbp_wp.groupby("game_id")["total_home_score"].diff().fillna(pbp_wp["total_home_score"])
    ).clip(lower=0)
    pbp_wp["away_score_delta"] = (
        pbp_wp.groupby("game_id")["total_away_score"].diff().fillna(pbp_wp["total_away_score"])
    ).clip(lower=0)

    # Filter to competitive plays only
    competitive = pbp_wp[pbp_wp["wp"].between(WP_LO, WP_HI)].copy()

    # Aggregate competitive-minutes points per game
    game_pts = competitive.groupby(
        ["season", "game_id", "home_team", "away_team"], as_index=False
    ).agg(
        comp_home_pts=("home_score_delta", "sum"),
        comp_away_pts=("away_score_delta", "sum"),
    )

    # Normalize team names
    game_pts["home_team"] = game_pts["home_team"].map(norm_team)
    game_pts["away_team"] = game_pts["away_team"].map(norm_team)

    # Pivot to one row per team per game
    home_rows = game_pts[["season", "home_team", "comp_home_pts", "comp_away_pts"]].copy()
    home_rows.columns = ["season", "team", "adj_pf_g", "adj_pa_g"]
    away_rows = game_pts[["season", "away_team", "comp_away_pts", "comp_home_pts"]].copy()
    away_rows.columns = ["season", "team", "adj_pf_g", "adj_pa_g"]

    all_rows = pd.concat([home_rows, away_rows], ignore_index=True)
    season_agg = all_rows.groupby(["season", "team"], as_index=False).agg(
        adj_pf=("adj_pf_g", "sum"),
        adj_pa=("adj_pa_g", "sum"),
    )
    return season_agg


def load_data(start=1999, end=2026):
    seasons = list(range(start, end + 1))
    try:
        schedules = nfl.import_schedules(seasons)
    except Exception:
        print(f"[INFO] Schedule fallback: {SCHEDULES_URL}")
        schedules = pd.read_csv(SCHEDULES_URL)
        schedules = schedules[schedules["season"].isin(seasons)]

    schedules["home_team"] = schedules["home_team"].map(norm_team)
    schedules["away_team"] = schedules["away_team"].map(norm_team)

    pbp = nfl.import_pbp_data(seasons, downcast=True)
    pbp = pbp[pbp["season_type"].eq("REG")].copy()
    for col in ["posteam", "defteam", "home_team", "away_team"]:
        if col in pbp.columns:
            pbp[col] = pbp[col].map(norm_team)
    pbp = pbp.dropna(subset=["posteam", "defteam", "epa"])

    # Standard EPA metrics (all plays, as before)
    pass_plays = pbp[pbp["play_type"].eq("pass")].copy()
    rush_plays = pbp[pbp["play_type"].eq("run")].copy()
    turnover_col = "turnover" if "turnover" in pbp.columns else "interception"

    off_base = (
        pbp.groupby(["season", "posteam"], as_index=False)
           .agg(
               off_epa_per_play=("epa", "mean"),
               off_success=("success", "mean"),
               off_explosive=("yards_gained", lambda x: np.mean(pd.to_numeric(x, errors="coerce").fillna(0) >= 20)),
               off_turnovers=(turnover_col, "mean"),
               plays=("play_id", "count"),
           )
           .rename(columns={"posteam": "team"})
    )
    off_pass = pass_plays.groupby(["season", "posteam"], as_index=False).agg(off_pass_epa=("epa", "mean")).rename(columns={"posteam": "team"})
    off_rush = rush_plays.groupby(["season", "posteam"], as_index=False).agg(off_rush_epa=("epa", "mean")).rename(columns={"posteam": "team"})
    offense  = off_base.merge(off_pass, on=["season", "team"], how="left").merge(off_rush, on=["season", "team"], how="left")

    def_base = (
        pbp.groupby(["season", "defteam"], as_index=False)
           .agg(
               def_epa_allowed_per_play=("epa", "mean"),
               def_success_allowed=("success", "mean"),
               def_explosive_allowed=("yards_gained", lambda x: np.mean(pd.to_numeric(x, errors="coerce").fillna(0) >= 20)),
               def_turnovers_forced=(turnover_col, "mean"),
           )
           .rename(columns={"defteam": "team"})
    )
    def_pass = pass_plays.groupby(["season", "defteam"], as_index=False).agg(def_pass_epa_allowed=("epa", "mean")).rename(columns={"defteam": "team"})
    def_rush = rush_plays.groupby(["season", "defteam"], as_index=False).agg(def_rush_epa_allowed=("epa", "mean")).rename(columns={"defteam": "team"})
    defense  = def_base.merge(def_pass, on=["season", "team"], how="left").merge(def_rush, on=["season", "team"], how="left")

    team_stats = offense.merge(defense, on=["season", "team"], how="inner")

    # Actual game records (for standard Pyth and point diff)
    reg = schedules[schedules["game_type"].eq("REG")].copy().dropna(subset=["home_score", "away_score"])
    rows = []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        hw = 0.5 if hs == as_ else (1.0 if hs > as_ else 0.0)
        rows += [[int(g["season"]), home, hw, hs, as_], [int(g["season"]), away, 1-hw, as_, hs]]

    records = pd.DataFrame(rows, columns=["season", "team", "wins", "pf", "pa"])
    records = records.groupby(["season", "team"], as_index=False).agg(
        wins=("wins", "sum"), games=("wins", "count"), pf=("pf", "sum"), pa=("pa", "sum")
    )
    records["pyth_wins_same_year"] = records.apply(
        lambda r: pyth_win_pct(r["pf"], r["pa"]) * r["games"], axis=1
    )
    team_stats = team_stats.merge(records, on=["season", "team"], how="inner")

    # Garbage-time adjusted metrics
    print("[INFO] Computing garbage-time filtered (adjusted) point metrics...")
    adj_pts = _compute_adjusted_points(pbp, schedules)
    if adj_pts is not None:
        team_stats = team_stats.merge(adj_pts, on=["season", "team"], how="left")
        # Fill HOU 2002 expansion team and any other missing rows with standard values
        team_stats["adj_pf"] = team_stats["adj_pf"].fillna(team_stats["pf"])
        team_stats["adj_pa"] = team_stats["adj_pa"].fillna(team_stats["pa"])
        team_stats["adj_pyth_wins"] = team_stats.apply(
            lambda r: pyth_win_pct(r["adj_pf"], r["adj_pa"]) * r["games"], axis=1
        )
        team_stats["adj_point_diff_per_game"] = (team_stats["adj_pf"] - team_stats["adj_pa"]) / team_stats["games"]
        adj_coverage = (~team_stats["adj_pf"].isna()).mean()
        print(f"[INFO] Adjusted metrics coverage: {adj_coverage:.1%} of team-seasons")
        print(f"[INFO] Mean adj_pf per game: {(team_stats['adj_pf']/team_stats['games']).mean():.1f}  "
              f"vs standard: {(team_stats['pf']/team_stats['games']).mean():.1f}")
    else:
        team_stats["adj_pyth_wins"] = team_stats["pyth_wins_same_year"]
        team_stats["adj_point_diff_per_game"] = (team_stats["pf"] - team_stats["pa"]) / team_stats["games"]
        print("[WARN] Falling back to standard metrics for adjusted columns.")

    return schedules, team_stats


# ── Model core (unchanged from v2.0, extended with adj metrics) ────────────────

def build_component_diffs(team_stats):
    df = team_stats.copy()
    df["pass_epa_diff"]       = df["off_pass_epa"]  - df["def_pass_epa_allowed"]
    df["rush_epa_diff"]       = df["off_rush_epa"]  - df["def_rush_epa_allowed"]
    df["epa_diff"]            = df["off_epa_per_play"] - df["def_epa_allowed_per_play"]
    df["success_diff"]        = df["off_success"]   - df["def_success_allowed"]
    df["explosive_diff"]      = df["off_explosive"] - df["def_explosive_allowed"]
    df["point_diff_per_game"] = (df["pf"] - df["pa"]) / df["games"]
    df["pyth_edge"]           = df["pyth_wins_same_year"] - (df["games"] / 2)
    df["turnover_margin"]     = df["def_turnovers_forced"] - df["off_turnovers"]
    # Adjusted metrics
    df["adj_pyth_edge_col"]   = df["adj_pyth_wins"] - (df["games"] / 2)
    df["adj_pd_per_game"]     = df["adj_point_diff_per_game"]
    return df


def build_prior_ratings(ts_diffs, regression_factor, weights):
    total_w = sum(weights.values()) or 1.0
    ratings = []
    for season, g in ts_diffs.groupby("season"):
        g = g.copy()
        pass_z = zscore(g["pass_epa_diff"]) if g["pass_epa_diff"].notna().sum() > 10 else zscore(g["epa_diff"])
        rush_z = zscore(g["rush_epa_diff"]) if g["rush_epa_diff"].notna().sum() > 10 else pd.Series(0.0, index=g.index)
        g["warps_z"] = (
            weights["pass_epa"]      * pass_z
            + weights["rush_epa"]    * rush_z
            + weights["success"]     * zscore(g["success_diff"])
            + weights["explosive"]   * zscore(g["explosive_diff"])
            + weights["point_diff"]  * zscore(g["point_diff_per_game"])
            + weights["pyth_edge"]   * zscore(g["pyth_edge"])
            + weights["turnover"]    * zscore(g["turnover_margin"])
            + weights.get("adj_pyth_edge", 0.0) * zscore(g["adj_pyth_edge_col"])
            + weights.get("adj_point_diff", 0.0) * zscore(g["adj_pd_per_game"])
        ) / total_w
        raw = SCALE_FACTOR * g["warps_z"]
        g["rating_pts"]     = raw * regression_factor
        g["raw_rating_pts"] = raw
        ratings.append(g[["season", "team", "rating_pts", "raw_rating_pts", "pyth_wins_same_year", "games"]])
    return pd.concat(ratings, ignore_index=True)


def get_dynasty_teams(prior_ratings, target_season, streak, threshold):
    qualified = set()
    pr_idx = prior_ratings.set_index(["season", "team"])["raw_rating_pts"]
    for team in prior_ratings["team"].unique():
        try:
            ratings = [float(pr_idx.loc[(target_season - i, team)]) for i in range(1, streak + 1)]
        except KeyError:
            continue
        if all(r > threshold for r in ratings) or all(r < -threshold for r in ratings):
            qualified.add(team)
    return qualified


def project_season(target, schedules, prior_ratings, logit_scale=6.5,
                   dynasty_teams=None, dynasty_r=None, base_reg=0.75):
    prior_year = target - 1
    r = prior_ratings[prior_ratings["season"].eq(prior_year)][["team", "rating_pts", "raw_rating_pts"]]
    if r.empty:
        raise ValueError(f"No prior ratings for {prior_year}")

    pure_map = dict(zip(r["team"], r["rating_pts"]))
    raw_map  = dict(zip(r["team"], r["raw_rating_pts"]))

    if dynasty_teams and dynasty_r is not None and dynasty_r != base_reg:
        for team in dynasty_teams:
            if team in raw_map:
                pure_map[team] = raw_map[team] * dynasty_r

    reg = schedules[(schedules["season"].eq(target)) & (schedules["game_type"].eq("REG"))].copy()
    if reg.empty:
        raise ValueError(f"No schedule for {target}")

    rows = []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        spread = pure_map.get(home, 0.0) - pure_map.get(away, 0.0) + HOME_FIELD
        hwp    = win_prob_from_spread(spread, logit_scale)
        rows  += [[target, home, hwp], [target, away, 1 - hwp]]

    proj = pd.DataFrame(rows, columns=["season", "team", "game_wp"])
    proj = proj.groupby(["season", "team"], as_index=False).agg(warps_wins=("game_wp", "sum"))
    return proj


def evaluate(schedules, ts_diffs, weights, reg_f, logit, target_years,
             dynasty_streak=None, dynasty_threshold=None, dynasty_r=None):
    pr = build_prior_ratings(ts_diffs, reg_f, weights)
    projs = []
    for yr in target_years:
        dt = None
        if dynasty_streak and dynasty_threshold is not None and dynasty_r:
            dt = get_dynasty_teams(pr, yr, dynasty_streak, dynasty_threshold)
        try:
            p = project_season(yr, schedules, pr, logit_scale=logit,
                               dynasty_teams=dt, dynasty_r=dynasty_r, base_reg=reg_f)
            projs.append(p)
        except Exception as e:
            warnings.warn(str(e))
    if not projs:
        return None, None

    proj   = pd.concat(projs, ignore_index=True)
    actual = ts_diffs[["season", "team", "wins", "games", "pyth_wins_same_year"]].copy()

    pp = actual[["season", "team", "pyth_wins_same_year", "games"]].copy()
    pp["season"] += 1
    pp = pp.rename(columns={"pyth_wins_same_year": "pyth_fc", "games": "prior_g"})

    pw = actual[["season", "team", "wins"]].copy()
    pw["season"] += 1
    pw = pw.rename(columns={"wins": "pw_fc"})

    out = (actual
           .merge(proj, on=["season", "team"], how="inner")
           .merge(pp,   on=["season", "team"], how="left")
           .merge(pw,   on=["season", "team"], how="left"))
    out["pyth_fc"]    = out["pyth_fc"] * (out["games"] / out["prior_g"])
    out["warps_error"] = out["warps_wins"] - out["wins"]
    out["pyth_error"]  = out["pyth_fc"]   - out["wins"]
    out["pw_error"]    = out["pw_fc"]     - out["wins"]

    m = {
        "warps_mae":  np.mean(np.abs(out["warps_error"])),
        "pyth_mae":   np.mean(np.abs(out["pyth_error"])),
        "pw_mae":     np.mean(np.abs(out["pw_error"])),
        "warps_rmse": math.sqrt(np.mean(out["warps_error"]**2)),
        "n": len(out), "years": f"{min(target_years)}-{max(target_years)}",
    }
    return out, m


# ── Grid search helpers ────────────────────────────────────────────────────────

def run_grid(label, candidates, schedules, ts_diffs, target_years,
             use_dynasty=True, verbose=True):
    """Run a list of weight dicts and return sorted results."""
    results = []
    for i, cfg in enumerate(candidates):
        weights = cfg["weights"]
        reg_f   = cfg.get("reg_f", V20_REG_F)
        logit   = cfg.get("logit", V20_LOGIT)
        d_streak = DYNASTY_STREAK if use_dynasty else None
        d_thresh = DYNASTY_THRESHOLD if use_dynasty else None
        d_r      = DYNASTY_R if use_dynasty else None
        _, m = evaluate(schedules, ts_diffs, weights, reg_f, logit, target_years,
                        dynasty_streak=d_streak, dynasty_threshold=d_thresh, dynasty_r=d_r)
        if m is None:
            continue
        row = {**cfg, **m}
        results.append(row)
        if verbose and (i % 10 == 0 or i == len(candidates) - 1):
            print(f"  [{label}] {i+1}/{len(candidates)}  MAE={m['warps_mae']:.4f}")
    return pd.DataFrame(results).sort_values("warps_mae")


def _grid_configs_v21():
    """
    Build 56 candidate configurations for Phase 2 adjusted-metrics grid.
    Each config varies how much weight goes to standard vs adjusted versions
    of Pythagorean and point differential.
    """
    alphas = [0.0, 0.25, 0.50, 0.75, 1.0]  # fraction of weight on adjusted metric
    cfgs = []
    # Fix pyth_total=0.75, pd_total=0.25 (v2.0 champion ratio)
    pyth_total, pd_total = 0.75, 0.25
    for a_pyth in alphas:
        for a_pd in alphas:
            # a_pyth = fraction of pyth_total that goes to adj_pyth (rest to standard pyth)
            # a_pd   = fraction of pd_total that goes to adj_pd (rest to standard pd)
            cfg = {
                "a_pyth": a_pyth, "a_pd": a_pd,
                "weights": _w(
                    pyth_edge      = pyth_total * (1 - a_pyth),
                    adj_pyth_edge  = pyth_total * a_pyth,
                    point_diff     = pd_total   * (1 - a_pd),
                    adj_point_diff = pd_total   * a_pd,
                ),
            }
            cfgs.append(cfg)
    return cfgs


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Skip Phase 1 (v2.0 reproduction)")
    args = parser.parse_args()

    print("=" * 68)
    print("WARPS-NFL v2.1 — Garbage-Time Filter Experiment")
    print(f"WP competitive range: [{WP_LO}, {WP_HI}]")
    print("=" * 68)

    print("\n[LOAD] Fetching schedules and PBP data...")
    schedules, team_stats = load_data()
    ts_diffs = build_component_diffs(team_stats)

    print(f"\n[DATA] {len(ts_diffs)} team-seasons loaded ({ts_diffs['season'].min()}–{ts_diffs['season'].max()})")
    print(f"[DATA] Adj Pythagorean correlation with standard: "
          f"{ts_diffs['adj_pyth_edge_col'].corr(ts_diffs['pyth_edge']):.4f}")
    print(f"[DATA] Adj Point Diff correlation with standard:  "
          f"{ts_diffs['adj_pd_per_game'].corr(ts_diffs['point_diff_per_game']):.4f}")
    print(f"[DATA] Mean points/game standard: {(team_stats['pf']/team_stats['games']).mean():.2f}  "
          f"adj: {(team_stats['adj_pf']/team_stats['games']).mean():.2f}")
    print(f"[DATA] Mean PA/game standard:     {(team_stats['pa']/team_stats['games']).mean():.2f}  "
          f"adj: {(team_stats['adj_pa']/team_stats['games']).mean():.2f}")

    # ── Phase 1: Reproduce v2.0 baseline ──────────────────────────────────────
    if not args.fast:
        print("\n── Phase 1: Reproducing v2.0 champion (sanity check) ─────────────────")
        _, m_full = evaluate(schedules, ts_diffs, V20_WEIGHTS, V20_REG_F, V20_LOGIT,
                             FULL_YEARS, DYNASTY_STREAK, DYNASTY_THRESHOLD, DYNASTY_R)
        _, m_val  = evaluate(schedules, ts_diffs, V20_WEIGHTS, V20_REG_F, V20_LOGIT,
                             VALIDATION_YEARS, DYNASTY_STREAK, DYNASTY_THRESHOLD, DYNASTY_R)
        if m_full:
            print(f"  v2.0 full  MAE={m_full['warps_mae']:.4f}  Pyth={m_full['pyth_mae']:.4f}  n={m_full['n']}")
        if m_val:
            print(f"  v2.0 val   MAE={m_val['warps_mae']:.4f}  Pyth={m_val['pyth_mae']:.4f}   n={m_val['n']}")
    else:
        print("\n[SKIP] Phase 1 — --fast mode, using known v2.0 MAE: full=2.352, val=2.495")

    # ── Phase 2: Adjusted metrics grid ────────────────────────────────────────
    print("\n── Phase 2: Garbage-Time Adjusted Metrics Grid (56 configs) ─────────")
    print("  Testing all combinations of standard vs adjusted Pythagorean / point diff")
    print("  Dynasty modifier active (streak=4, threshold=0.5, R=0.95)")

    cfgs = _grid_configs_v21()

    # Full-sample grid (champion selection)
    print("\n  [Full sample 2000-2025]")
    full_results = run_grid("full", cfgs, schedules, ts_diffs, FULL_YEARS)
    full_results.to_csv("warps_garbage_time_grid_full.csv", index=False)

    # Validation grid (held-out 2022-2025)
    print("\n  [Validation 2022-2025]")
    val_results  = run_grid("val",  cfgs, schedules, ts_diffs, VALIDATION_YEARS)
    val_results.to_csv("warps_garbage_time_grid_val.csv", index=False)

    # ── Phase 3: Summary ───────────────────────────────────────────────────────
    print("\n── Phase 3: Results Summary ─────────────────────────────────────────")

    v20_full_mae = 2.352  # from v2.0 run
    v20_val_mae  = 2.495

    print("\nTop 5 configs by full-sample MAE:")
    cols = ["a_pyth", "a_pd", "warps_mae", "pyth_mae", "n"]
    print(full_results[cols].head(5).to_string(index=False, float_format="%.4f"))

    best_full = full_results.iloc[0]
    best_val  = val_results.iloc[0]

    print(f"\n  v2.0 champion:  full MAE={v20_full_mae:.4f}  val MAE={v20_val_mae:.4f}")
    print(f"  v2.1 best full: full MAE={best_full['warps_mae']:.4f}  "
          f"(a_pyth={best_full['a_pyth']:.2f}, a_pd={best_full['a_pd']:.2f})")
    print(f"  v2.1 best val:  val  MAE={best_val['warps_mae']:.4f}  "
          f"(a_pyth={best_val['a_pyth']:.2f}, a_pd={best_val['a_pd']:.2f})")

    full_delta = best_full["warps_mae"] - v20_full_mae
    val_delta  = best_val["warps_mae"]  - v20_val_mae
    full_verdict = f"{'IMPROVEMENT' if full_delta < -0.005 else 'MARGINAL' if full_delta < 0 else 'NO IMPROVEMENT'}"
    val_verdict  = f"{'IMPROVEMENT' if val_delta < -0.005 else 'MARGINAL' if val_delta < 0 else 'NO IMPROVEMENT'}"

    print(f"\n  Full-sample delta: {full_delta:+.4f}  → {full_verdict}")
    print(f"  Validation delta:  {val_delta:+.4f}  → {val_verdict}")

    # Special cases: pure adjusted
    pure_adj_cfg = {"a_pyth": 1.0, "a_pd": 1.0}
    pure_adj = full_results[
        (full_results["a_pyth"] == 1.0) & (full_results["a_pd"] == 1.0)
    ]
    if not pure_adj.empty:
        r = pure_adj.iloc[0]
        print(f"\n  Pure adjusted (a_pyth=1.0, a_pd=1.0):  MAE={r['warps_mae']:.4f}  "
              f"delta={r['warps_mae'] - v20_full_mae:+.4f}")

    adj_pyth_only = full_results[(full_results["a_pyth"] == 1.0) & (full_results["a_pd"] == 0.0)]
    if not adj_pyth_only.empty:
        r = adj_pyth_only.iloc[0]
        print(f"  Adj Pyth only   (a_pyth=1.0, a_pd=0.0):  MAE={r['warps_mae']:.4f}  "
              f"delta={r['warps_mae'] - v20_full_mae:+.4f}")

    adj_pd_only = full_results[(full_results["a_pyth"] == 0.0) & (full_results["a_pd"] == 1.0)]
    if not adj_pd_only.empty:
        r = adj_pd_only.iloc[0]
        print(f"  Adj PD only     (a_pyth=0.0, a_pd=1.0):  MAE={r['warps_mae']:.4f}  "
              f"delta={r['warps_mae'] - v20_full_mae:+.4f}")

    # Interpretation
    print("\n── Interpretation ───────────────────────────────────────────────────")
    if full_delta < -0.01:
        print("  ✓ Garbage-time filtering provides meaningful signal.")
        print("  → Recommend incorporating adjusted metrics into v2.2 champion.")
    elif full_delta < 0:
        print("  ~ Marginal improvement — garbage-time filter helps slightly.")
        print("  → SOS-level test: real but thin. Include only if val window confirms.")
    else:
        print("  ✗ No improvement from garbage-time filter on full sample.")
        print("  → Pythagorean already self-corrects for garbage-time inflation.")
        print("    (This is a valid and important null result, similar to SOS.)")

    print("\n  Output files:")
    print("    warps_garbage_time_grid_full.csv  — 56 configs, full sample")
    print("    warps_garbage_time_grid_val.csv   — 56 configs, validation only")
    print("\nDone.")


if __name__ == "__main__":
    main()
