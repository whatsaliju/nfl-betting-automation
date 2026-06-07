"""
WARPS-NFL v1.5d — NFL win-total model.

Patches applied after v1.5 review:

1) SOS double-count removed.
   - apply_sos_to_projection now defaults to False.
   - Game-level projection already embeds opponent quality via head-to-head spread.
   - Applying schedule_context_map on top was penalizing hard schedules twice.
   - SOS columns are retained as diagnostic output only.

2) Composite weights normalized to sum to 1.0.
   - v1.5 weights summed to ~0.875, suppressing rating amplitude.
   - WEIGHT_SUM constant added; warps_z divided by WEIGHT_SUM before scaling.
   - Grid search can now recalibrate the 3.0 * warps_z scale cleanly.

3) QB/market overrides separated into external CSV config.
   - warps_2026_overrides.csv: market_total, qb_override, override_reason, source, confidence
   - Model reads CSV at runtime; constants in code are kept as fallback defaults only.
   - Enables clean version control and audit trail for assumptions.

Install:
    pip install pandas numpy nfl_data_py

Run:
    python warps_nfl_model_v1_5d.py [--no-grid] [--overrides warps_2026_overrides.csv]

Outputs:
    warps_parameter_grid_v1_5d.csv
    warps_validation_metrics_v1_5d.csv
    warps_validation_team_results_v1_5d.csv
    warps_backtest_team_results_v1_5d.csv
    warps_backtest_by_year_v1_5d.csv
    warps_backtest_overall_v1_5d.csv
    warps_calibration_buckets_v1_5d.csv
    warps_2026_screen_v1_5d.csv
    warps_2026_game_probs_v1_5d.csv
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
    raise SystemExit(
        "Missing package. Install with: pip install nfl_data_py pandas numpy"
    ) from exc


PYTH_EXPONENT = 2.37
HOME_FIELD = 1.5

DEFAULT_REGRESSION_FACTOR = 0.65
DEFAULT_SOS_WEIGHT = 0.20
DEFAULT_LOGIT_SPREAD_SCALE = 6.5

REGRESSION_GRID = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
SOS_GRID = [0.00, 0.10, 0.15, 0.20, 0.25, 0.30]
LOGIT_SCALE_GRID = [5.5, 6.0, 6.5, 7.0, 7.5]

TRAIN_YEARS = list(range(2015, 2022))
VALIDATION_YEARS = list(range(2022, 2026))
FULL_BACKTEST_YEARS = list(range(2015, 2026))

# ---------------------------------------------------------------------------
# OVERRIDE CONFIG LOADER
# Reads warps_2026_overrides.csv if present; falls back to hard-coded dicts.
# CSV schema: team, market_total, qb_override, override_reason, source, confidence
# ---------------------------------------------------------------------------

def load_overrides_csv(path="warps_2026_overrides.csv"):
    """Load market lines and QB overrides from CSV config. Returns (market_dict, qb_dict)."""
    try:
        df = pd.read_csv(path)
        market = dict(zip(df["team"], pd.to_numeric(df["market_total"], errors="coerce")))
        qb = dict(zip(df["team"], pd.to_numeric(df["qb_override"], errors="coerce").fillna(0.0)))
        print(f"[INFO] Loaded overrides from {path} ({len(df)} teams)")
        return market, qb
    except FileNotFoundError:
        print(f"[WARN] {path} not found — using hard-coded fallback dicts.")
        return None, None


# ---------------------------------------------------------------------------
# QB / ROSTER OVERRIDES 2026
# Units: spread-points added to team rating.
# Positive = team better than prior-year EPA suggests.
# Negative = team worse than prior-year EPA suggests.
# ---------------------------------------------------------------------------
QB_OVERRIDES_2026 = {
    "BUF": +0.5,
    "MIA": -2.0,
    "NE":  +1.5,
    "NYJ": -1.5,
    "BAL": +1.0,
    "CIN": +1.0,
    "CLE": -1.5,
    "PIT":  0.0,
    "HOU":  0.0,
    "IND":  0.0,
    "JAX": +0.5,
    "TEN": +0.5,
    "DEN": -0.5,
    "KC":  +1.0,
    "LAC":  0.0,
    "LV":   0.0,
    "DAL": +0.5,
    "NYG":  0.0,
    "PHI":  0.0,
    "WAS": +1.5,
    "CHI": -0.5,
    "DET": +0.5,
    "GB":   0.0,
    "MIN":  0.0,
    "ATL": -0.5,
    "CAR":  0.0,
    "NO":  +0.5,
    "TB":   0.0,
    "ARI": -1.0,
    "LAR": +0.5,
    "SF":   0.0,
    "SEA": -0.5,
}

# ---------------------------------------------------------------------------
# MARKET WIN TOTALS 2026
# Source: DraftKings Sportsbook, June 2026 consensus
# ---------------------------------------------------------------------------
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

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}


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


SCHEDULES_URL = "https://raw.githubusercontent.com/leesharpe/nfldata/master/data/games.csv"


def load_data(start=2014, end=2026):
    seasons = list(range(start, end + 1))
    # habitatring.com is the same data — use the GitHub raw mirror when that URL is blocked
    try:
        schedules = nfl.import_schedules(seasons)
    except Exception:
        print(f"[INFO] Falling back to GitHub raw schedule source: {SCHEDULES_URL}")
        schedules = pd.read_csv(SCHEDULES_URL)
        schedules = schedules[schedules["season"].isin(seasons)]
    schedules["home_team"] = schedules["home_team"].map(norm_team)
    schedules["away_team"] = schedules["away_team"].map(norm_team)

    pbp = nfl.import_pbp_data(seasons, downcast=True)
    pbp = pbp[pbp["season_type"].eq("REG")].copy()

    for col in ["posteam", "defteam"]:
        pbp[col] = pbp[col].map(norm_team)

    pbp = pbp.dropna(subset=["posteam", "defteam", "epa"])

    pass_plays = pbp[pbp["play_type"].isin(["pass"])].copy()
    rush_plays = pbp[pbp["play_type"].isin(["run"])].copy()

    turnover_col = "turnover" if "turnover" in pbp.columns else "interception"
    print(f"[INFO] Using turnover column: {turnover_col}")

    off_base = (
        pbp.groupby(["season", "posteam"], as_index=False)
           .agg(
               off_epa_per_play=("epa", "mean"),
               off_success=("success", "mean"),
               off_explosive=("yards_gained", lambda x: np.mean(
                   pd.to_numeric(x, errors="coerce").fillna(0) >= 20)),
               off_turnovers=(turnover_col, "mean"),
               plays=("play_id", "count"),
           )
           .rename(columns={"posteam": "team"})
    )

    off_pass = (
        pass_plays.groupby(["season", "posteam"], as_index=False)
                  .agg(off_pass_epa=("epa", "mean"))
                  .rename(columns={"posteam": "team"})
    )

    off_rush = (
        rush_plays.groupby(["season", "posteam"], as_index=False)
                  .agg(off_rush_epa=("epa", "mean"))
                  .rename(columns={"posteam": "team"})
    )

    offense = off_base.merge(off_pass, on=["season", "team"], how="left") \
                      .merge(off_rush, on=["season", "team"], how="left")

    def_base = (
        pbp.groupby(["season", "defteam"], as_index=False)
           .agg(
               def_epa_allowed_per_play=("epa", "mean"),
               def_success_allowed=("success", "mean"),
               def_explosive_allowed=("yards_gained", lambda x: np.mean(
                   pd.to_numeric(x, errors="coerce").fillna(0) >= 20)),
               def_turnovers_forced=(turnover_col, "mean"),
           )
           .rename(columns={"defteam": "team"})
    )

    def_pass = (
        pass_plays.groupby(["season", "defteam"], as_index=False)
                  .agg(def_pass_epa_allowed=("epa", "mean"))
                  .rename(columns={"defteam": "team"})
    )

    def_rush = (
        rush_plays.groupby(["season", "defteam"], as_index=False)
                  .agg(def_rush_epa_allowed=("epa", "mean"))
                  .rename(columns={"defteam": "team"})
    )

    defense = def_base.merge(def_pass, on=["season", "team"], how="left") \
                      .merge(def_rush, on=["season", "team"], how="left")

    team_stats = offense.merge(defense, on=["season", "team"], how="inner")

    reg = schedules[schedules["game_type"].eq("REG")].copy()
    reg = reg.dropna(subset=["home_score", "away_score"])

    rows = []
    for _, g in reg.iterrows():
        season = int(g["season"])
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        if hs == as_:
            hw = aw = 0.5
        else:
            hw = 1.0 if hs > as_ else 0.0
            aw = 1.0 - hw
        rows.append([season, home, hw, hs, as_])
        rows.append([season, away, aw, as_, hs])

    records = pd.DataFrame(rows, columns=["season", "team", "wins", "pf", "pa"])
    records = records.groupby(["season", "team"], as_index=False).agg(
        wins=("wins", "sum"),
        games=("wins", "count"),
        pf=("pf", "sum"),
        pa=("pa", "sum"),
    )
    records["pyth_wins_same_year"] = records.apply(
        lambda r: pyth_win_pct(r["pf"], r["pa"]) * r["games"], axis=1
    )

    team_stats = team_stats.merge(records, on=["season", "team"], how="inner")

    counts = team_stats.groupby("season")["team"].nunique()
    bad = counts[counts < 32]
    if not bad.empty:
        warnings.warn(f"Some seasons have fewer than 32 teams: {bad.to_dict()}")

    return schedules, team_stats


def build_prior_ratings(team_stats, regression_factor):
    df = team_stats.copy()

    df["pass_epa_diff"] = df["off_pass_epa"] - df["def_pass_epa_allowed"]
    df["rush_epa_diff"] = df["off_rush_epa"] - df["def_rush_epa_allowed"]
    df["epa_diff"] = df["off_epa_per_play"] - df["def_epa_allowed_per_play"]
    df["success_diff"] = df["off_success"] - df["def_success_allowed"]
    df["explosive_diff"] = df["off_explosive"] - df["def_explosive_allowed"]
    df["point_diff_per_game"] = (df["pf"] - df["pa"]) / df["games"]
    df["pyth_edge"] = df["pyth_wins_same_year"] - (df["games"] / 2)
    df["turnover_margin_rate"] = df["def_turnovers_forced"] - df["off_turnovers"]

    ratings = []
    for season, g in df.groupby("season"):
        g = g.copy()

        # Weights: pass EPA diff 30%, rush EPA diff 10%, success diff 15%,
        # explosive diff 8%, point diff 12%, pythagorean 8%, turnover 7% * 0.5 noise discount.
        # Sum = 0.875; divide by WEIGHT_SUM to normalize amplitude to 1.0.
        WEIGHT_SUM = 0.30 + 0.10 + 0.15 + 0.08 + 0.12 + 0.08 + (0.07 * 0.5)

        turnover_component = 0.5 * zscore(g["turnover_margin_rate"])

        pass_diff_z = zscore(g["pass_epa_diff"]) if g["pass_epa_diff"].notna().sum() > 10 \
                      else zscore(g["epa_diff"])
        rush_diff_z = zscore(g["rush_epa_diff"]) if g["rush_epa_diff"].notna().sum() > 10 \
                      else zscore(g["epa_diff"]) * 0.0

        g["warps_z"] = (
            0.30 * pass_diff_z
            + 0.10 * rush_diff_z
            + 0.15 * zscore(g["success_diff"])
            + 0.08 * zscore(g["explosive_diff"])
            + 0.12 * zscore(g["point_diff_per_game"])
            + 0.08 * zscore(g["pyth_edge"])
            + 0.07 * turnover_component
        ) / WEIGHT_SUM

        raw_rating_pts = 3.0 * g["warps_z"]
        g["rating_pts"] = raw_rating_pts * regression_factor
        g["raw_rating_pts"] = raw_rating_pts

        ratings.append(g[["season", "team", "rating_pts", "raw_rating_pts",
                           "pyth_wins_same_year", "games"]])

    return pd.concat(ratings, ignore_index=True)


def compute_prior_year_sos(target_season, schedules, raw_rating_map):
    """SOS computed from pre-regression (raw) team ratings to avoid double-shrinkage."""
    reg = schedules[(schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))].copy()
    rows = []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        rows.append([home, raw_rating_map.get(away, 0.0)])
        rows.append([away, raw_rating_map.get(home, 0.0)])

    sos = pd.DataFrame(rows, columns=["team", "opp_rating"])
    return sos.groupby("team")["opp_rating"].mean().to_dict()


def project_season(
    target_season,
    schedules,
    prior_ratings,
    qb_overrides=None,
    sos_weight=DEFAULT_SOS_WEIGHT,
    logit_scale=DEFAULT_LOGIT_SPREAD_SCALE,
    apply_sos_to_projection=False,
):
    prior_year = target_season - 1
    ratings = prior_ratings[prior_ratings["season"].eq(prior_year)][
        ["team", "rating_pts", "raw_rating_pts"]
    ]

    if ratings.empty:
        raise ValueError(f"No prior ratings found for {prior_year}")

    pure_quality_map = dict(zip(ratings["team"], ratings["rating_pts"]))
    raw_quality_map = dict(zip(ratings["team"], ratings["raw_rating_pts"]))

    sos_map = compute_prior_year_sos(target_season, schedules, raw_quality_map)

    schedule_context_map = {
        team: -sos_weight * sos_map.get(team, 0.0)
        for team in pure_quality_map
    }

    qb_adjusted_quality_map = dict(pure_quality_map)
    if qb_overrides:
        for team, adj in qb_overrides.items():
            if team in qb_adjusted_quality_map:
                qb_adjusted_quality_map[team] += float(adj)

    if apply_sos_to_projection:
        projection_quality_map = {
            team: qb_adjusted_quality_map[team] + schedule_context_map.get(team, 0.0)
            for team in qb_adjusted_quality_map
        }
    else:
        projection_quality_map = dict(qb_adjusted_quality_map)

    reg = schedules[(schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))].copy()
    if reg.empty:
        raise ValueError(f"No schedule rows for {target_season}")

    rows = []
    game_rows = []

    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])

        home_pure = pure_quality_map.get(home, 0.0)
        away_pure = pure_quality_map.get(away, 0.0)
        home_proj = projection_quality_map.get(home, 0.0)
        away_proj = projection_quality_map.get(away, 0.0)

        home_spread = home_proj - away_proj + HOME_FIELD
        home_wp = win_prob_from_spread(home_spread, logit_scale)

        rows.append([target_season, home, home_wp])
        rows.append([target_season, away, 1 - home_wp])

        game_rows.append([
            target_season, home, away, home_spread, home_wp,
            home_pure, away_pure, home_proj, away_proj,
            schedule_context_map.get(home, 0.0), schedule_context_map.get(away, 0.0),
        ])

    proj = pd.DataFrame(rows, columns=["season", "team", "game_wp"])
    proj = proj.groupby(["season", "team"], as_index=False).agg(warps_wins=("game_wp", "sum"))
    proj["pure_quality_pts"] = proj["team"].map(pure_quality_map)
    proj["schedule_context_pts"] = proj["team"].map(schedule_context_map)
    proj["projection_quality_pts"] = proj["team"].map(projection_quality_map)

    games = pd.DataFrame(
        game_rows,
        columns=[
            "season", "home_team", "away_team", "home_expected_spread", "home_win_prob",
            "home_pure_quality_pts", "away_pure_quality_pts",
            "home_projection_quality_pts", "away_projection_quality_pts",
            "home_schedule_context_pts", "away_schedule_context_pts",
        ],
    )

    return proj, games


def evaluate_model(
    schedules,
    team_stats,
    regression_factor,
    sos_weight,
    logit_scale,
    target_years=FULL_BACKTEST_YEARS,
):
    prior_ratings = build_prior_ratings(team_stats, regression_factor)

    all_proj = []
    for target in target_years:
        try:
            proj, _ = project_season(
                target, schedules, prior_ratings,
                qb_overrides=None,
                sos_weight=sos_weight,
                logit_scale=logit_scale,
                apply_sos_to_projection=False,
            )
            all_proj.append(proj)
        except Exception as e:
            warnings.warn(str(e))

    proj = pd.concat(all_proj, ignore_index=True)
    actual = team_stats[["season", "team", "wins", "games", "pyth_wins_same_year"]].copy()

    prior_pyth = actual[["season", "team", "pyth_wins_same_year", "games"]].copy()
    prior_pyth["season"] += 1
    prior_pyth = prior_pyth.rename(
        columns={"pyth_wins_same_year": "pyth_forecast_prior", "games": "prior_games"}
    )

    out = actual.merge(proj, on=["season", "team"], how="inner").merge(
        prior_pyth, on=["season", "team"], how="left"
    )
    out["pyth_forecast_prior"] = out["pyth_forecast_prior"] * (out["games"] / out["prior_games"])
    out["warps_error"] = out["warps_wins"] - out["wins"]
    out["pyth_error"] = out["pyth_forecast_prior"] - out["wins"]

    metrics = {
        "regression_factor": regression_factor,
        "sos_weight": sos_weight,
        "logit_scale": logit_scale,
        "warps_mae": np.mean(np.abs(out["warps_error"])),
        "pyth_mae": np.mean(np.abs(out["pyth_error"])),
        "warps_rmse": math.sqrt(np.mean(out["warps_error"] ** 2)),
        "pyth_rmse": math.sqrt(np.mean(out["pyth_error"] ** 2)),
        "n": len(out),
        "years": f"{min(target_years)}-{max(target_years)}",
    }

    return out, metrics


def grid_search(schedules, team_stats, target_years=TRAIN_YEARS):
    results = []
    for reg_factor, sos_weight, logit_scale in product(REGRESSION_GRID, SOS_GRID, LOGIT_SCALE_GRID):
        _, metrics = evaluate_model(
            schedules, team_stats,
            regression_factor=reg_factor,
            sos_weight=sos_weight,
            logit_scale=logit_scale,
            target_years=target_years,
        )
        results.append(metrics)

    grid = pd.DataFrame(results).sort_values(["warps_mae", "warps_rmse"]).reset_index(drop=True)
    return grid


def calibration_buckets(team_results, n_buckets=6):
    df = team_results.copy()
    df["pred_bucket"] = pd.qcut(df["warps_wins"], q=n_buckets, duplicates="drop")
    cal = df.groupby("pred_bucket", observed=True).agg(
        teams=("team", "count"),
        avg_projected_wins=("warps_wins", "mean"),
        avg_actual_wins=("wins", "mean"),
        avg_error=("warps_error", "mean"),
        mae=("warps_error", lambda x: np.mean(np.abs(x))),
    ).reset_index()
    return cal


def add_market_signals(screen_2026, market_dict=None, strict_market=False):
    screen_2026 = screen_2026.copy()
    if market_dict is None:
        market_dict = MARKET_2026
    screen_2026["market_total"] = screen_2026["team"].map(market_dict)

    missing = screen_2026.loc[screen_2026["market_total"].isna(), "team"].sort_values().tolist()
    if missing:
        msg = f"Missing 2026 market win totals for: {missing}"
        if strict_market:
            raise ValueError(msg)
        warnings.warn(msg)

    screen_2026["edge"] = screen_2026["warps_wins"] - screen_2026["market_total"]
    screen_2026["signal"] = np.select(
        [
            screen_2026["edge"] >= 1.5,
            screen_2026["edge"] >= 1.0,
            screen_2026["edge"] <= -1.5,
            screen_2026["edge"] <= -1.0,
        ],
        ["Strong Over", "Playable Over", "Strong Under", "Playable Under"],
        default="No bet / lean only",
    )
    return screen_2026


def backtest(run_grid_search=True, use_train_validation=True, strict_market=True,
             overrides_csv="warps_2026_overrides.csv"):
    schedules, team_stats = load_data(2014, 2026)

    csv_market, csv_qb = load_overrides_csv(overrides_csv)
    active_market = csv_market if csv_market is not None else MARKET_2026
    active_qb = csv_qb if csv_qb is not None else QB_OVERRIDES_2026

    if run_grid_search:
        train_years = TRAIN_YEARS if use_train_validation else FULL_BACKTEST_YEARS
        grid = grid_search(schedules, team_stats, target_years=train_years)
        grid.to_csv("warps_parameter_grid_v1_5d.csv", index=False)

        best = grid.iloc[0]
        reg_factor = float(best["regression_factor"])
        sos_weight = float(best["sos_weight"])
        logit_scale = float(best["logit_scale"])

        if use_train_validation:
            validation_results, validation_metrics = evaluate_model(
                schedules, team_stats,
                regression_factor=reg_factor,
                sos_weight=sos_weight,
                logit_scale=logit_scale,
                target_years=VALIDATION_YEARS,
            )
            pd.DataFrame([validation_metrics]).to_csv("warps_validation_metrics_v1_5d.csv", index=False)
            validation_results.to_csv("warps_validation_team_results_v1_5d.csv", index=False)
    else:
        grid = None
        reg_factor = DEFAULT_REGRESSION_FACTOR
        sos_weight = DEFAULT_SOS_WEIGHT
        logit_scale = DEFAULT_LOGIT_SPREAD_SCALE

    team_results, metrics = evaluate_model(
        schedules, team_stats,
        regression_factor=reg_factor,
        sos_weight=sos_weight,
        logit_scale=logit_scale,
        target_years=FULL_BACKTEST_YEARS,
    )

    summary = team_results.groupby("season").agg(
        teams=("team", "count"),
        warps_mae=("warps_error", lambda x: np.mean(np.abs(x))),
        pyth_mae=("pyth_error", lambda x: np.mean(np.abs(x))),
        warps_rmse=("warps_error", lambda x: math.sqrt(np.mean(x*x))),
        pyth_rmse=("pyth_error", lambda x: math.sqrt(np.mean(x*x))),
    ).reset_index()

    overall = pd.DataFrame([metrics])
    cal = calibration_buckets(team_results)

    prior_ratings = build_prior_ratings(team_stats, reg_factor)
    screen_2026, games_2026 = project_season(
        2026, schedules, prior_ratings,
        qb_overrides=active_qb,
        sos_weight=sos_weight,
        logit_scale=logit_scale,
        apply_sos_to_projection=False,
    )
    # Apply market signals once using the active (CSV-loaded) market dict
    screen_2026 = add_market_signals(screen_2026, market_dict=active_market,
                                     strict_market=strict_market)

    team_results.to_csv("warps_backtest_team_results_v1_5d.csv", index=False)
    summary.to_csv("warps_backtest_by_year_v1_5d.csv", index=False)
    overall.to_csv("warps_backtest_overall_v1_5d.csv", index=False)
    cal.to_csv("warps_calibration_buckets_v1_5d.csv", index=False)
    screen_2026.sort_values("edge", ascending=False).to_csv("warps_2026_screen_v1_5d.csv", index=False)
    games_2026.to_csv("warps_2026_game_probs_v1_5d.csv", index=False)

    print("\nBEST PARAMETERS")
    print(pd.DataFrame([{
        "regression_factor": reg_factor,
        "sos_weight": sos_weight,
        "logit_scale": logit_scale,
    }]).to_string(index=False))

    if run_grid_search and use_train_validation:
        print("\nVALIDATION METRICS")
        print(pd.DataFrame([validation_metrics]).round(3).to_string(index=False))

    print("\nOVERALL BACKTEST")
    print(overall.round(3).to_string(index=False))

    print("\nBACKTEST BY YEAR")
    print(summary.round(3).to_string(index=False))

    print("\nCALIBRATION BUCKETS")
    print(cal.round(3).to_string(index=False))

    print("\n2026 SCREEN")
    print(screen_2026.sort_values("edge", ascending=False).round(2).to_string(index=False))

    if grid is not None:
        print("\nTOP 10 GRID SEARCH RESULTS")
        print(grid.head(10).round(3).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WARPS-NFL v1.5d win-total model")
    parser.add_argument("--no-grid", action="store_true",
                        help="Skip grid search; use default parameters")
    parser.add_argument("--overrides", default="warps_2026_overrides.csv",
                        help="Path to overrides CSV (default: warps_2026_overrides.csv)")
    args = parser.parse_args()

    backtest(
        run_grid_search=not args.no_grid,
        use_train_validation=not args.no_grid,
        strict_market=True,
        overrides_csv=args.overrides,
    )
