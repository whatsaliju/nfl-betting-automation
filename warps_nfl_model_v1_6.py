"""
WARPS-NFL v1.6 — Optimal Weight Search & Multi-Metric Comparison

Strategy:
  Phase 1 : 500-sample Dirichlet random weight search (train 2015-2021)
  Phase 2 : Predefined configs including every single-component NFL metric
  Phase 3 : Full hyper grid (regression × SOS × logit) for top-3 weight configs
  Phase 4 : Validate on 2022-2025 + full backtest 2015-2025
  Phase 5 : 2026 screen under optimal weights
  Output  : Ranked comparison — optimal WARPS vs every NFL metric baseline

Install:  pip install pandas numpy nfl_data_py
Run:      python warps_nfl_model_v1_6.py [--overrides warps_2026_overrides.csv]
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

TRAIN_YEARS      = list(range(2015, 2022))
VALIDATION_YEARS = list(range(2022, 2026))
FULL_YEARS       = list(range(2015, 2026))

REGRESSION_GRID  = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
SOS_GRID         = [0.00, 0.10, 0.15, 0.20, 0.25, 0.30]
LOGIT_SCALE_GRID = [5.5, 6.0, 6.5, 7.0, 7.5]

COMPONENTS = ["pass_epa", "rush_epa", "success", "explosive", "point_diff", "pyth_edge", "turnover"]

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}

# ── Predefined weight configurations ──────────────────────────────────────────

def _w(**kw):
    return {c: kw.get(c, 0.0) for c in COMPONENTS}

PREDEFINED_CONFIGS = {
    # composite candidates
    "v1_5d_default":    _w(pass_epa=0.30, rush_epa=0.10, success=0.15, explosive=0.08, point_diff=0.12, pyth_edge=0.08, turnover=0.07),
    "pass_heavy":       _w(pass_epa=0.50, rush_epa=0.05, success=0.15, explosive=0.05, point_diff=0.15, pyth_edge=0.05, turnover=0.05),
    "pass_success":     _w(pass_epa=0.35, rush_epa=0.05, success=0.30, explosive=0.05, point_diff=0.15, pyth_edge=0.05, turnover=0.05),
    "epa_dominant":     _w(pass_epa=0.40, rush_epa=0.20, success=0.10, explosive=0.10, point_diff=0.10, pyth_edge=0.05, turnover=0.05),
    "balanced":         _w(pass_epa=0.20, rush_epa=0.15, success=0.20, explosive=0.10, point_diff=0.15, pyth_edge=0.15, turnover=0.05),
    "pdiff_heavy":      _w(pass_epa=0.20, rush_epa=0.10, success=0.15, explosive=0.05, point_diff=0.35, pyth_edge=0.10, turnover=0.05),
    "pyth_heavy":       _w(pass_epa=0.20, rush_epa=0.10, success=0.15, explosive=0.05, point_diff=0.15, pyth_edge=0.30, turnover=0.05),
    "no_explosive_tov": _w(pass_epa=0.35, rush_epa=0.12, success=0.20, explosive=0.00, point_diff=0.18, pyth_edge=0.15, turnover=0.00),
    "pass_pyth":        _w(pass_epa=0.40, rush_epa=0.00, success=0.00, explosive=0.00, point_diff=0.00, pyth_edge=0.60, turnover=0.00),
    "efficiency_only":  _w(pass_epa=0.40, rush_epa=0.10, success=0.30, explosive=0.20, point_diff=0.00, pyth_edge=0.00, turnover=0.00),
    "pass_success_pdiff": _w(pass_epa=0.40, rush_epa=0.00, success=0.25, explosive=0.00, point_diff=0.25, pyth_edge=0.10, turnover=0.00),
    # individual NFL metric baselines (single-component)
    "solo_pass_epa":    _w(pass_epa=1.0),
    "solo_rush_epa":    _w(rush_epa=1.0),
    "solo_success":     _w(success=1.0),
    "solo_explosive":   _w(explosive=1.0),
    "solo_point_diff":  _w(point_diff=1.0),
    "solo_pyth_edge":   _w(pyth_edge=1.0),
    "solo_turnover":    _w(turnover=1.0),
}

# ── Fallback overrides ─────────────────────────────────────────────────────────

QB_OVERRIDES_2026 = {
    "BUF": +0.5, "MIA": -2.0, "NE":  +1.5, "NYJ": -1.5,
    "BAL": +1.0, "CIN": +1.0, "CLE": -1.5, "PIT":  0.0,
    "HOU":  0.0, "IND":  0.0, "JAX": +0.5, "TEN": +0.5,
    "DEN": -0.5, "KC":  +1.0, "LAC":  0.0, "LV":   0.0,
    "DAL": +0.5, "NYG":  0.0, "PHI":  0.0, "WAS": +1.5,
    "CHI": -0.5, "DET": +0.5, "GB":   0.0, "MIN":  0.0,
    "ATL": -0.5, "CAR":  0.0, "NO":  +0.5, "TB":   0.0,
    "ARI": -1.0, "LAR": +0.5, "SF":   0.0, "SEA": -0.5,
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

def norm_team(t):
    if pd.isna(t):
        return t
    return TEAM_ALIASES.get(str(t), str(t))

def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    std = s.std(ddof=0)
    if std == 0 or pd.isna(std):
        return s * 0
    return (s - s.mean()) / std

def win_prob_from_spread(spread, logit_scale):
    return 1 / (1 + np.exp(-spread / logit_scale))

def pyth_win_pct(pf, pa):
    pf = max(float(pf), 1.0)
    pa = max(float(pa), 1.0)
    return (pf ** PYTH_EXPONENT) / ((pf ** PYTH_EXPONENT) + (pa ** PYTH_EXPONENT))


# ── Data loading ───────────────────────────────────────────────────────────────

def load_overrides_csv(path="warps_2026_overrides.csv"):
    try:
        df = pd.read_csv(path)
        market = dict(zip(df["team"], pd.to_numeric(df["market_total"], errors="coerce")))
        qb = dict(zip(df["team"], pd.to_numeric(df["qb_override"], errors="coerce").fillna(0.0)))
        print(f"[INFO] Loaded overrides from {path} ({len(df)} teams)")
        return market, qb
    except FileNotFoundError:
        print(f"[WARN] {path} not found — using fallback dicts.")
        return None, None

def load_data(start=2014, end=2026):
    seasons = list(range(start, end + 1))
    try:
        schedules = nfl.import_schedules(seasons)
    except Exception:
        print(f"[INFO] Schedule URL fallback: {SCHEDULES_URL}")
        schedules = pd.read_csv(SCHEDULES_URL)
        schedules = schedules[schedules["season"].isin(seasons)]

    schedules["home_team"] = schedules["home_team"].map(norm_team)
    schedules["away_team"] = schedules["away_team"].map(norm_team)

    pbp = nfl.import_pbp_data(seasons, downcast=True)
    pbp = pbp[pbp["season_type"].eq("REG")].copy()
    for col in ["posteam", "defteam"]:
        pbp[col] = pbp[col].map(norm_team)
    pbp = pbp.dropna(subset=["posteam", "defteam", "epa"])

    pass_plays = pbp[pbp["play_type"].eq("pass")].copy()
    rush_plays = pbp[pbp["play_type"].eq("run")].copy()

    turnover_col = "turnover" if "turnover" in pbp.columns else "interception"
    print(f"[INFO] Turnover column: {turnover_col}")

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
    offense = off_base.merge(off_pass, on=["season", "team"], how="left").merge(off_rush, on=["season", "team"], how="left")

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
    defense = def_base.merge(def_pass, on=["season", "team"], how="left").merge(def_rush, on=["season", "team"], how="left")

    team_stats = offense.merge(defense, on=["season", "team"], how="inner")

    reg = schedules[schedules["game_type"].eq("REG")].copy()
    reg = reg.dropna(subset=["home_score", "away_score"])
    rows = []
    for _, g in reg.iterrows():
        season = int(g["season"])
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        hw = 0.5 if hs == as_ else (1.0 if hs > as_ else 0.0)
        rows += [[season, home, hw, hs, as_], [season, away, 1-hw, as_, hs]]

    records = pd.DataFrame(rows, columns=["season", "team", "wins", "pf", "pa"])
    records = records.groupby(["season", "team"], as_index=False).agg(
        wins=("wins", "sum"), games=("wins", "count"), pf=("pf", "sum"), pa=("pa", "sum")
    )
    records["pyth_wins_same_year"] = records.apply(
        lambda r: pyth_win_pct(r["pf"], r["pa"]) * r["games"], axis=1
    )
    team_stats = team_stats.merge(records, on=["season", "team"], how="inner")

    counts = team_stats.groupby("season")["team"].nunique()
    bad = counts[counts < 32]
    if not bad.empty:
        warnings.warn(f"Seasons with <32 teams: {bad.to_dict()}")

    return schedules, team_stats


# ── Core model ─────────────────────────────────────────────────────────────────

def build_component_diffs(team_stats):
    """Precompute all component diff columns on team_stats once."""
    df = team_stats.copy()
    df["pass_epa_diff"]    = df["off_pass_epa"]  - df["def_pass_epa_allowed"]
    df["rush_epa_diff"]    = df["off_rush_epa"]  - df["def_rush_epa_allowed"]
    df["epa_diff"]         = df["off_epa_per_play"] - df["def_epa_allowed_per_play"]
    df["success_diff"]     = df["off_success"]   - df["def_success_allowed"]
    df["explosive_diff"]   = df["off_explosive"] - df["def_explosive_allowed"]
    df["point_diff_per_game"] = (df["pf"] - df["pa"]) / df["games"]
    df["pyth_edge"]        = df["pyth_wins_same_year"] - (df["games"] / 2)
    df["turnover_margin"]  = df["def_turnovers_forced"] - df["off_turnovers"]
    return df


def build_prior_ratings_weighted(team_stats_with_diffs, regression_factor, weights):
    """Build per-season team ratings using parameterized component weights."""
    df = team_stats_with_diffs
    total_w = sum(weights.values())
    if total_w == 0:
        total_w = 1.0

    ratings = []
    for season, g in df.groupby("season"):
        g = g.copy()

        # Pass EPA: fall back to total EPA diff if pass split unavailable
        pass_z = zscore(g["pass_epa_diff"]) if g["pass_epa_diff"].notna().sum() > 10 else zscore(g["epa_diff"])
        rush_z = zscore(g["rush_epa_diff"]) if g["rush_epa_diff"].notna().sum() > 10 else pd.Series(0.0, index=g.index)

        g["warps_z"] = (
            weights["pass_epa"]   * pass_z
            + weights["rush_epa"]   * rush_z
            + weights["success"]    * zscore(g["success_diff"])
            + weights["explosive"]  * zscore(g["explosive_diff"])
            + weights["point_diff"] * zscore(g["point_diff_per_game"])
            + weights["pyth_edge"]  * zscore(g["pyth_edge"])
            + weights["turnover"]   * zscore(g["turnover_margin"])
        ) / total_w

        raw_rating = SCALE_FACTOR * g["warps_z"]
        g["rating_pts"]     = raw_rating * regression_factor
        g["raw_rating_pts"] = raw_rating

        ratings.append(g[["season", "team", "rating_pts", "raw_rating_pts", "pyth_wins_same_year", "games"]])

    return pd.concat(ratings, ignore_index=True)


def compute_prior_year_sos(target_season, schedules, raw_rating_map):
    reg = schedules[(schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))].copy()
    rows = []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        rows += [[home, raw_rating_map.get(away, 0.0)], [away, raw_rating_map.get(home, 0.0)]]
    sos = pd.DataFrame(rows, columns=["team", "opp_rating"])
    return sos.groupby("team")["opp_rating"].mean().to_dict()


def project_season(target_season, schedules, prior_ratings, qb_overrides=None,
                   sos_weight=0.0, logit_scale=6.5, apply_sos=False):
    prior_year = target_season - 1
    ratings = prior_ratings[prior_ratings["season"].eq(prior_year)][["team", "rating_pts", "raw_rating_pts"]]
    if ratings.empty:
        raise ValueError(f"No prior ratings for {prior_year}")

    pure_map = dict(zip(ratings["team"], ratings["rating_pts"]))
    raw_map  = dict(zip(ratings["team"], ratings["raw_rating_pts"]))
    sos_map  = compute_prior_year_sos(target_season, schedules, raw_map)
    sos_ctx  = {t: -sos_weight * sos_map.get(t, 0.0) for t in pure_map}

    proj_map = dict(pure_map)
    if qb_overrides:
        for t, adj in qb_overrides.items():
            if t in proj_map:
                proj_map[t] += float(adj)
    if apply_sos:
        proj_map = {t: proj_map[t] + sos_ctx.get(t, 0.0) for t in proj_map}

    reg = schedules[(schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))].copy()
    if reg.empty:
        raise ValueError(f"No schedule rows for {target_season}")

    rows, game_rows = [], []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        home_spread = proj_map.get(home, 0.0) - proj_map.get(away, 0.0) + HOME_FIELD
        home_wp = win_prob_from_spread(home_spread, logit_scale)
        rows += [[target_season, home, home_wp], [target_season, away, 1 - home_wp]]
        game_rows.append([target_season, home, away, home_spread, home_wp,
                          pure_map.get(home, 0.0), pure_map.get(away, 0.0),
                          proj_map.get(home, 0.0), proj_map.get(away, 0.0),
                          sos_ctx.get(home, 0.0), sos_ctx.get(away, 0.0)])

    proj = pd.DataFrame(rows, columns=["season", "team", "game_wp"])
    proj = proj.groupby(["season", "team"], as_index=False).agg(warps_wins=("game_wp", "sum"))
    proj["pure_quality_pts"]      = proj["team"].map(pure_map)
    proj["schedule_context_pts"]  = proj["team"].map(sos_ctx)
    proj["projection_quality_pts"] = proj["team"].map(proj_map)

    games = pd.DataFrame(game_rows, columns=[
        "season", "home_team", "away_team", "home_expected_spread", "home_win_prob",
        "home_pure_quality_pts", "away_pure_quality_pts",
        "home_projection_quality_pts", "away_projection_quality_pts",
        "home_schedule_context_pts", "away_schedule_context_pts",
    ])
    return proj, games


def evaluate_model_weighted(schedules, team_stats_diffs, weights, regression_factor,
                             sos_weight, logit_scale, target_years):
    prior_ratings = build_prior_ratings_weighted(team_stats_diffs, regression_factor, weights)

    all_proj = []
    for yr in target_years:
        try:
            proj, _ = project_season(yr, schedules, prior_ratings,
                                     sos_weight=sos_weight, logit_scale=logit_scale)
            all_proj.append(proj)
        except Exception as e:
            warnings.warn(str(e))
    if not all_proj:
        return None, None

    proj = pd.concat(all_proj, ignore_index=True)
    actual = team_stats_diffs[["season", "team", "wins", "games", "pyth_wins_same_year"]].copy()

    # Prior-year Pythagorean baseline
    prior_pyth = actual[["season", "team", "pyth_wins_same_year", "games"]].copy()
    prior_pyth["season"] += 1
    prior_pyth = prior_pyth.rename(columns={"pyth_wins_same_year": "pyth_forecast_prior", "games": "prior_games"})

    # Prior-year actual wins baseline
    prior_wins = actual[["season", "team", "wins"]].copy()
    prior_wins["season"] += 1
    prior_wins = prior_wins.rename(columns={"wins": "prior_wins_forecast"})

    out = (actual
           .merge(proj, on=["season", "team"], how="inner")
           .merge(prior_pyth, on=["season", "team"], how="left")
           .merge(prior_wins, on=["season", "team"], how="left"))

    out["pyth_forecast_prior"] = out["pyth_forecast_prior"] * (out["games"] / out["prior_games"])
    out["warps_error"]      = out["warps_wins"]          - out["wins"]
    out["pyth_error"]       = out["pyth_forecast_prior"] - out["wins"]
    out["prior_wins_error"] = out["prior_wins_forecast"] - out["wins"]

    metrics = {
        "regression_factor": regression_factor,
        "sos_weight":        sos_weight,
        "logit_scale":       logit_scale,
        "warps_mae":         np.mean(np.abs(out["warps_error"])),
        "pyth_mae":          np.mean(np.abs(out["pyth_error"])),
        "prior_wins_mae":    np.mean(np.abs(out["prior_wins_error"])),
        "warps_rmse":        math.sqrt(np.mean(out["warps_error"]**2)),
        "pyth_rmse":         math.sqrt(np.mean(out["pyth_error"]**2)),
        "prior_wins_rmse":   math.sqrt(np.mean(out["prior_wins_error"]**2)),
        "n":                 len(out),
        "years":             f"{min(target_years)}-{max(target_years)}",
    }
    return out, metrics


# ── Random weight search ───────────────────────────────────────────────────────

def random_weight_search(schedules, team_stats_diffs, n_samples=500,
                          regression_factor=0.65, sos_weight=0.0, logit_scale=6.5,
                          target_years=None):
    if target_years is None:
        target_years = TRAIN_YEARS

    np.random.seed(42)
    raw_samples = np.random.dirichlet(np.ones(len(COMPONENTS)), size=n_samples)

    results = []
    for i, raw in enumerate(raw_samples):
        weights = dict(zip(COMPONENTS, raw))
        try:
            _, metrics = evaluate_model_weighted(
                schedules, team_stats_diffs, weights,
                regression_factor, sos_weight, logit_scale, target_years
            )
            if metrics is not None:
                row = {f"w_{c}": weights[c] for c in COMPONENTS}
                row["config_name"] = f"random_{i:04d}"
                row.update(metrics)
                results.append(row)
        except Exception:
            pass
        if (i + 1) % 50 == 0:
            print(f"  random search: {i+1}/{n_samples} done")

    df = pd.DataFrame(results).sort_values("warps_mae").reset_index(drop=True)
    return df


# ── Predefined configs evaluation ─────────────────────────────────────────────

def evaluate_predefined_configs(schedules, team_stats_diffs,
                                  regression_factor=0.65, sos_weight=0.0, logit_scale=6.5,
                                  target_years=None):
    if target_years is None:
        target_years = TRAIN_YEARS

    results = []
    for name, weights in PREDEFINED_CONFIGS.items():
        try:
            _, metrics = evaluate_model_weighted(
                schedules, team_stats_diffs, weights,
                regression_factor, sos_weight, logit_scale, target_years
            )
            if metrics is not None:
                row = {"config_name": name}
                row.update({f"w_{c}": weights[c] for c in COMPONENTS})
                row.update(metrics)
                results.append(row)
        except Exception as e:
            warnings.warn(f"{name}: {e}")
    return pd.DataFrame(results).sort_values("warps_mae").reset_index(drop=True)


# ── Full hyper grid for given weights ─────────────────────────────────────────

def hyper_grid_search(schedules, team_stats_diffs, weights, target_years=None):
    if target_years is None:
        target_years = TRAIN_YEARS

    results = []
    combos = list(product(REGRESSION_GRID, SOS_GRID, LOGIT_SCALE_GRID))
    for i, (reg_factor, sos_w, logit) in enumerate(combos):
        try:
            _, metrics = evaluate_model_weighted(
                schedules, team_stats_diffs, weights,
                reg_factor, sos_w, logit, target_years
            )
            if metrics is not None:
                results.append(metrics)
        except Exception:
            pass
    return pd.DataFrame(results).sort_values(["warps_mae", "warps_rmse"]).reset_index(drop=True)


# ── Calibration & market signals ──────────────────────────────────────────────

def calibration_buckets(team_results, n_buckets=6):
    df = team_results.copy()
    df["pred_bucket"] = pd.qcut(df["warps_wins"], q=n_buckets, duplicates="drop")
    return df.groupby("pred_bucket", observed=True).agg(
        teams=("team", "count"),
        avg_projected_wins=("warps_wins", "mean"),
        avg_actual_wins=("wins", "mean"),
        avg_error=("warps_error", "mean"),
        mae=("warps_error", lambda x: np.mean(np.abs(x))),
    ).reset_index()


def add_market_signals(screen, market_dict=None, strict=False):
    screen = screen.copy()
    if market_dict is None:
        market_dict = MARKET_2026
    screen["market_total"] = screen["team"].map(market_dict)
    missing = screen.loc[screen["market_total"].isna(), "team"].tolist()
    if missing:
        msg = f"Missing market totals: {missing}"
        if strict:
            raise ValueError(msg)
        warnings.warn(msg)
    screen["edge"] = screen["warps_wins"] - screen["market_total"]
    screen["signal"] = np.select(
        [screen["edge"] >= 1.5, screen["edge"] >= 1.0,
         screen["edge"] <= -1.5, screen["edge"] <= -1.0],
        ["Strong Over", "Playable Over", "Strong Under", "Playable Under"],
        default="No bet / lean only",
    )
    return screen


# ── Main orchestration ────────────────────────────────────────────────────────

def run(overrides_csv="warps_2026_overrides.csv"):
    print("=" * 70)
    print("WARPS-NFL v1.6 — Optimal Weight Search & Multi-Metric Comparison")
    print("=" * 70)

    schedules, team_stats = load_data(2014, 2026)
    csv_market, csv_qb = load_overrides_csv(overrides_csv)
    active_market = csv_market if csv_market is not None else MARKET_2026
    active_qb     = csv_qb     if csv_qb     is not None else QB_OVERRIDES_2026

    team_stats_diffs = build_component_diffs(team_stats)

    # ── Phase 1: Random weight search (train years) ────────────────────────
    print(f"\nPhase 1: Random weight search (n=500, train {TRAIN_YEARS[0]}-{TRAIN_YEARS[-1]})...")
    random_results = random_weight_search(schedules, team_stats_diffs, n_samples=500,
                                           regression_factor=0.65, sos_weight=0.0, logit_scale=6.5,
                                           target_years=TRAIN_YEARS)
    random_results.to_csv("warps_random_weight_search_v1_6.csv", index=False)
    print(f"  Best random config  MAE={random_results.iloc[0]['warps_mae']:.4f}")
    print(f"  Worst random config MAE={random_results.iloc[-1]['warps_mae']:.4f}")

    # ── Phase 2: Predefined configs (train years) ──────────────────────────
    print(f"\nPhase 2: Predefined configs ({len(PREDEFINED_CONFIGS)} configs, train years)...")
    predefined_train = evaluate_predefined_configs(schedules, team_stats_diffs,
                                                    target_years=TRAIN_YEARS)
    print("\nPredefined configs ranked by train MAE:")
    print(predefined_train[["config_name", "warps_mae", "pyth_mae", "prior_wins_mae"]].round(3).to_string(index=False))

    # Combine top-3 from random with top-3 predefined → candidate pool
    top_random = random_results.head(3)
    top_predefined_names = predefined_train.head(3)["config_name"].tolist()
    best_random_weights = [
        dict(zip(COMPONENTS, [r[f"w_{c}"] for c in COMPONENTS]))
        for _, r in top_random.iterrows()
    ]
    candidate_configs = {
        **{n: PREDEFINED_CONFIGS[n] for n in top_predefined_names},
        **{f"random_best_{i}": w for i, w in enumerate(best_random_weights)},
    }

    # ── Phase 3: Full hyper grid for each candidate ────────────────────────
    print(f"\nPhase 3: Full hyper grid ({len(REGRESSION_GRID)*len(SOS_GRID)*len(LOGIT_SCALE_GRID)} combos) for {len(candidate_configs)} candidates...")
    best_val_mae   = float("inf")
    best_config    = None
    best_weights   = None
    best_grid      = None

    for cname, cweights in candidate_configs.items():
        grid = hyper_grid_search(schedules, team_stats_diffs, cweights, target_years=TRAIN_YEARS)
        best = grid.iloc[0]
        # quick validation check
        _, val_m = evaluate_model_weighted(
            schedules, team_stats_diffs, cweights,
            float(best["regression_factor"]), float(best["sos_weight"]),
            float(best["logit_scale"]), VALIDATION_YEARS
        )
        val_mae = val_m["warps_mae"] if val_m else float("inf")
        print(f"  {cname:30s} train_MAE={best['warps_mae']:.4f}  val_MAE={val_mae:.4f}")
        if val_mae < best_val_mae:
            best_val_mae   = val_mae
            best_config    = (cname, float(best["regression_factor"]),
                              float(best["sos_weight"]), float(best["logit_scale"]))
            best_weights   = cweights
            best_grid      = grid

    print(f"\n★ Champion config: {best_config[0]}")
    print(f"  regression_factor={best_config[1]}  sos_weight={best_config[2]}  logit_scale={best_config[3]}")
    print(f"  Validation MAE={best_val_mae:.4f}")

    # save best grid
    if best_grid is not None:
        best_grid.to_csv("warps_parameter_grid_v1_6.csv", index=False)

    # ── Phase 4: Full backtest + validation with champion ──────────────────
    reg_f, sos_w, logit_s = best_config[1], best_config[2], best_config[3]

    full_results, full_metrics = evaluate_model_weighted(
        schedules, team_stats_diffs, best_weights,
        reg_f, sos_w, logit_s, FULL_YEARS
    )
    val_results, val_metrics = evaluate_model_weighted(
        schedules, team_stats_diffs, best_weights,
        reg_f, sos_w, logit_s, VALIDATION_YEARS
    )

    full_results.to_csv("warps_backtest_team_results_v1_6.csv", index=False)
    pd.DataFrame([val_metrics]).to_csv("warps_validation_metrics_v1_6.csv", index=False)

    by_year = full_results.groupby("season").agg(
        teams=("team", "count"),
        warps_mae=("warps_error",      lambda x: np.mean(np.abs(x))),
        pyth_mae=("pyth_error",        lambda x: np.mean(np.abs(x))),
        prior_wins_mae=("prior_wins_error", lambda x: np.mean(np.abs(x))),
        warps_rmse=("warps_error",     lambda x: math.sqrt(np.mean(x**2))),
        pyth_rmse=("pyth_error",       lambda x: math.sqrt(np.mean(x**2))),
    ).reset_index()
    by_year.to_csv("warps_backtest_by_year_v1_6.csv", index=False)

    cal = calibration_buckets(full_results)
    cal.to_csv("warps_calibration_buckets_v1_6.csv", index=False)

    # ── Phase 5: Full metric comparison table ─────────────────────────────
    # Evaluate ALL predefined configs on FULL years to rank everything
    print(f"\nPhase 5: Full {FULL_YEARS[0]}-{FULL_YEARS[-1]} comparison of all configs...")
    full_comparison_rows = []

    # Champion WARPS
    full_comparison_rows.append({
        "model": f"WARPS_champion ({best_config[0]})",
        "type": "WARPS composite",
        **{f"w_{c}": best_weights[c] for c in COMPONENTS},
        **full_metrics,
    })

    # All predefined (full years, fixed hypers for fairness)
    for name, weights in PREDEFINED_CONFIGS.items():
        try:
            _, m = evaluate_model_weighted(
                schedules, team_stats_diffs, weights,
                reg_f, sos_w, logit_s, FULL_YEARS
            )
            if m:
                mtype = "single metric" if name.startswith("solo_") else "WARPS composite"
                full_comparison_rows.append({
                    "model": name,
                    "type": mtype,
                    **{f"w_{c}": weights[c] for c in COMPONENTS},
                    **m,
                })
        except Exception:
            pass

    comparison_df = pd.DataFrame(full_comparison_rows).sort_values("warps_mae").reset_index(drop=True)
    comparison_df["beats_pythagorean"]  = comparison_df["warps_mae"] < comparison_df["pyth_mae"]
    comparison_df["beats_prior_wins"]   = comparison_df["warps_mae"] < comparison_df["prior_wins_mae"]
    comparison_df["beats_all_baselines"] = comparison_df["beats_pythagorean"] & comparison_df["beats_prior_wins"]
    comparison_df.to_csv("warps_metric_ranking_v1_6.csv", index=False)

    # Also evaluate all predefined on VALIDATION years
    print("\nValidation (2022-2025) comparison of all predefined configs:")
    val_comparison_rows = []
    for name, weights in PREDEFINED_CONFIGS.items():
        try:
            _, m = evaluate_model_weighted(
                schedules, team_stats_diffs, weights,
                reg_f, sos_w, logit_s, VALIDATION_YEARS
            )
            if m:
                val_comparison_rows.append({"model": name, **m})
        except Exception:
            pass
    # add champion
    val_comparison_rows.append({"model": f"WARPS_champion ({best_config[0]})", **val_metrics})
    val_comparison_df = pd.DataFrame(val_comparison_rows).sort_values("warps_mae").reset_index(drop=True)
    val_comparison_df.to_csv("warps_val_metric_ranking_v1_6.csv", index=False)

    # ── Phase 6: 2026 screen ──────────────────────────────────────────────
    prior_ratings = build_prior_ratings_weighted(team_stats_diffs, reg_f, best_weights)
    screen_2026, games_2026 = project_season(
        2026, schedules, prior_ratings,
        qb_overrides=active_qb, sos_weight=sos_w, logit_scale=logit_s
    )
    screen_2026 = add_market_signals(screen_2026, market_dict=active_market, strict=True)
    screen_2026.sort_values("edge", ascending=False).to_csv("warps_2026_screen_v1_6.csv", index=False)
    games_2026.to_csv("warps_2026_game_probs_v1_6.csv", index=False)

    # ── Print summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("CHAMPION CONFIG")
    print("=" * 70)
    print(f"  Name:              {best_config[0]}")
    print(f"  regression_factor: {reg_f}")
    print(f"  sos_weight:        {sos_w}")
    print(f"  logit_scale:       {logit_s}")
    print(f"\n  Weights:")
    for c in COMPONENTS:
        print(f"    {c:15s}: {best_weights[c]:.4f}")

    print("\n" + "=" * 70)
    print("FULL BACKTEST METRICS (2015-2025)")
    print("=" * 70)
    print(pd.DataFrame([full_metrics]).round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("VALIDATION METRICS (2022-2025)")
    print("=" * 70)
    print(pd.DataFrame([val_metrics]).round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("BY-YEAR BACKTEST (WARPS vs Pythagorean vs Prior Wins)")
    print("=" * 70)
    print(by_year.round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("FULL METRIC RANKING — All Models vs All NFL Baselines (2015-2025)")
    print("=" * 70)
    rank_cols = ["model", "type", "warps_mae", "pyth_mae", "prior_wins_mae",
                 "warps_rmse", "beats_pythagorean", "beats_prior_wins", "beats_all_baselines"]
    print(comparison_df[rank_cols].round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("VALIDATION METRIC RANKING (2022-2025)")
    print("=" * 70)
    val_rank_cols = ["model", "warps_mae", "pyth_mae", "prior_wins_mae", "warps_rmse"]
    print(val_comparison_df[val_rank_cols].round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("CALIBRATION BUCKETS")
    print("=" * 70)
    print(cal.round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("2026 SCREEN — sorted by edge")
    print("=" * 70)
    print(screen_2026.sort_values("edge", ascending=False).round(2).to_string(index=False))

    # Final verdict
    champion_row = comparison_df[comparison_df["model"].str.startswith("WARPS_champion")].iloc[0]
    solo_maes = comparison_df[comparison_df["type"] == "single metric"]["warps_mae"]
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    print(f"  Champion WARPS MAE (full backtest): {champion_row['warps_mae']:.4f}")
    print(f"  Pythagorean MAE:                    {champion_row['pyth_mae']:.4f}")
    print(f"  Prior wins MAE:                     {champion_row['prior_wins_mae']:.4f}")
    print(f"  Best single-metric MAE:             {solo_maes.min():.4f} ({comparison_df.loc[solo_maes.idxmin(), 'model']})")
    if champion_row["beats_all_baselines"]:
        print(f"\n  ✓ WARPS champion beats ALL baselines on full 11-year backtest.")
    else:
        print(f"\n  ✗ WARPS champion does NOT beat all baselines — review config.")

    val_champ = val_comparison_df[val_comparison_df["model"].str.startswith("WARPS_champion")].iloc[0]
    solo_val = val_comparison_df[~val_comparison_df["model"].str.startswith("WARPS_champion")]
    best_solo_val = solo_val["warps_mae"].min()
    print(f"\n  Validation (2022-2025) WARPS MAE:        {val_champ['warps_mae']:.4f}")
    print(f"  Validation best single-metric MAE:       {best_solo_val:.4f}")
    if val_champ["warps_mae"] < best_solo_val:
        print(f"  ✓ WARPS champion beats all single metrics on held-out validation.")
    else:
        print(f"  ✗ Some single metric beats WARPS on validation — investigate.")

    print("\nOutputs written:")
    outputs = [
        "warps_random_weight_search_v1_6.csv",
        "warps_parameter_grid_v1_6.csv",
        "warps_validation_metrics_v1_6.csv",
        "warps_backtest_team_results_v1_6.csv",
        "warps_backtest_by_year_v1_6.csv",
        "warps_calibration_buckets_v1_6.csv",
        "warps_metric_ranking_v1_6.csv",
        "warps_val_metric_ranking_v1_6.csv",
        "warps_2026_screen_v1_6.csv",
        "warps_2026_game_probs_v1_6.csv",
    ]
    for f in outputs:
        print(f"  {f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WARPS-NFL v1.6 weight optimization")
    parser.add_argument("--overrides", default="warps_2026_overrides.csv")
    args = parser.parse_args()
    run(overrides_csv=args.overrides)
