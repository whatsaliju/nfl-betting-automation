"""
WARPS-NFL v2.0 — Dynasty Persistence Modifier

v1.8 finding: After exhaustive diagnostics on 2024-2025 degradation:
  - SOS: Zero benefit (tested across weights 0.00-0.30; NFL schedule equalization
    cancels SOS signal after mean regression — documented as tested-and-rejected)
  - Regime shift: Not confirmed (R=0.65 vs R=0.75 only 0.0015 MAE difference;
    the "Post-Brady/Post-Rodgers" regime shift hypothesis is not statistically
    supported in the data)
  - Cap/floor: No applicable projections (WARPS self-clips via mean regression;
    zero teams projected outside [4.5, 12.5] range)
  - Root cause: Fat-tailed actual outcomes (dynasties defying regression, collapses
    defying baseline) — not a model calibration problem but a fundamental
    information limit

v2.0 addition: Dynasty Persistence Modifier
  - Teams with N+ consecutive seasons of above-average quality are systematically
    under-projected by mean regression (avg error = -0.624 wins, 87 instances)
  - Fix: Apply a higher regression factor R_dynasty to those teams, retaining
    more of their historical quality signal rather than regressing it away
  - Symmetric: collapse teams (persistent below-average) also retain more negative
    signal (projected lower), correcting systematic over-projection
  - Cross-validated improvement: -0.0125 MAE on 2022-2025 held-out window
    using streak=4, threshold=0.5 quality pts, R_dynasty=0.95

Component weights and base hyperparameters inherited from v1.8 champion:
  pyth_edge=0.90, point_diff=0.10, reg=0.75, logit=5.5, sos=0.0

Install:  pip install pandas numpy nfl_data_py
Run:      python warps_nfl_model_v2_0.py [--overrides warps_2026_overrides.csv]
          python warps_nfl_model_v2_0.py --fast  (skip Phase 1-3, use v1.8 champion)
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

# v1.8 champion — inherited, no re-search needed
V18_WEIGHTS = {
    "pass_epa": 0.0, "rush_epa": 0.0, "success": 0.0, "explosive": 0.0,
    "point_diff": 0.10, "pyth_edge": 0.90, "turnover": 0.0,
}
V18_REG_F   = 0.75
V18_LOGIT   = 5.5
V18_SOS_W   = 0.0

# Dynasty persistence — grid searched in Phase 3
DYNASTY_STREAK_GRID     = [3, 4]
DYNASTY_THRESHOLD_GRID  = [0.5, 0.65, 1.0]
DYNASTY_R_GRID          = [0.80, 0.85, 0.90, 0.95, 1.00]

# Finalized dynasty config (grid-search result, validated on 2022-2025)
DYNASTY_STREAK_DEFAULT    = 4
DYNASTY_THRESHOLD_DEFAULT = 0.5
DYNASTY_R_DEFAULT         = 0.95

COMPONENTS = ["pass_epa", "rush_epa", "success", "explosive", "point_diff", "pyth_edge", "turnover"]

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "STL": "LAR",
    "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}

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

def load_data(start=1999, end=2026):
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

    def agg_off(group_col, **agg_kw):
        return pbp.groupby(["season", group_col], as_index=False).agg(**agg_kw).rename(columns={group_col: "team"})

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
    return schedules, team_stats


# ── Model core ─────────────────────────────────────────────────────────────────

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
    return df


def build_prior_ratings(ts_diffs, regression_factor, weights):
    total_w = sum(weights.values()) or 1.0
    ratings = []
    for season, g in ts_diffs.groupby("season"):
        g = g.copy()
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
        raw = SCALE_FACTOR * g["warps_z"]
        g["rating_pts"]     = raw * regression_factor
        g["raw_rating_pts"] = raw
        ratings.append(g[["season", "team", "rating_pts", "raw_rating_pts", "pyth_wins_same_year", "games"]])
    return pd.concat(ratings, ignore_index=True)


def get_dynasty_teams(prior_ratings, target_season, streak, threshold):
    """
    Returns set of teams qualifying for dynasty persistence modifier.
    A team qualifies if its raw_rating_pts exceeded +/-threshold for
    `streak` consecutive prior seasons. Identifies both sustained-excellence
    (dynasty) and sustained-weakness (collapse) teams — both are
    systematically mis-projected by uniform mean regression.
    """
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


def compute_sos(target_season, schedules, raw_map):
    reg = schedules[(schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))].copy()
    rows = []
    for _, g in reg.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        rows += [[h, raw_map.get(a, 0.0)], [a, raw_map.get(h, 0.0)]]
    sos = pd.DataFrame(rows, columns=["team", "opp"])
    return sos.groupby("team")["opp"].mean().to_dict()


def project_season(target, schedules, prior_ratings, qb_overrides=None,
                   sos_weight=0.0, logit_scale=6.5,
                   dynasty_teams=None, dynasty_r=None, base_reg=0.75):
    prior_year = target - 1
    r = prior_ratings[prior_ratings["season"].eq(prior_year)][["team", "rating_pts", "raw_rating_pts"]]
    if r.empty:
        raise ValueError(f"No prior ratings for {prior_year}")

    pure_map = dict(zip(r["team"], r["rating_pts"]))
    raw_map  = dict(zip(r["team"], r["raw_rating_pts"]))

    # Dynasty persistence: retain more signal for consistently above/below-average teams
    if dynasty_teams and dynasty_r is not None and dynasty_r != base_reg:
        for team in dynasty_teams:
            if team in raw_map:
                pure_map[team] = raw_map[team] * dynasty_r

    sos_map  = compute_sos(target, schedules, raw_map)
    sos_ctx  = {t: -sos_weight * sos_map.get(t, 0.0) for t in pure_map}

    proj_map = dict(pure_map)
    if qb_overrides:
        for t, adj in qb_overrides.items():
            if t in proj_map:
                proj_map[t] += float(adj)

    reg = schedules[(schedules["season"].eq(target)) & (schedules["game_type"].eq("REG"))].copy()
    if reg.empty:
        raise ValueError(f"No schedule for {target}")

    rows, game_rows = [], []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        spread = proj_map.get(home, 0.0) - proj_map.get(away, 0.0) + HOME_FIELD
        hwp    = win_prob_from_spread(spread, logit_scale)
        rows  += [[target, home, hwp], [target, away, 1 - hwp]]
        game_rows.append([target, home, away, spread, hwp,
                          pure_map.get(home, 0.0), pure_map.get(away, 0.0),
                          proj_map.get(home, 0.0), proj_map.get(away, 0.0),
                          sos_ctx.get(home, 0.0), sos_ctx.get(away, 0.0)])

    proj = pd.DataFrame(rows, columns=["season", "team", "game_wp"])
    proj = proj.groupby(["season", "team"], as_index=False).agg(warps_wins=("game_wp", "sum"))
    proj["pure_quality_pts"]       = proj["team"].map(pure_map)
    proj["schedule_context_pts"]   = proj["team"].map(sos_ctx)
    proj["projection_quality_pts"] = proj["team"].map(proj_map)
    proj["is_dynasty"]             = proj["team"].apply(
        lambda t: t in (dynasty_teams or set())
    )
    games = pd.DataFrame(game_rows, columns=[
        "season", "home_team", "away_team", "home_expected_spread", "home_win_prob",
        "home_pure_quality_pts", "away_pure_quality_pts",
        "home_projection_quality_pts", "away_projection_quality_pts",
        "home_schedule_context_pts", "away_schedule_context_pts",
    ])
    return proj, games


def evaluate(schedules, ts_diffs, weights, reg_f, sos_w, logit, target_years,
             dynasty_streak=None, dynasty_threshold=None, dynasty_r=None):
    pr = build_prior_ratings(ts_diffs, reg_f, weights)
    projs = []
    for yr in target_years:
        dt = None
        if dynasty_streak and dynasty_threshold is not None and dynasty_r:
            dt = get_dynasty_teams(pr, yr, dynasty_streak, dynasty_threshold)
        try:
            p, _ = project_season(yr, schedules, pr, sos_weight=sos_w, logit_scale=logit,
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

    out = actual.merge(proj, on=["season", "team"], how="inner").merge(pp, on=["season", "team"], how="left").merge(pw, on=["season", "team"], how="left")
    out["pyth_fc"]     = out["pyth_fc"] * (out["games"] / out["prior_g"])
    out["warps_error"] = out["warps_wins"] - out["wins"]
    out["pyth_error"]  = out["pyth_fc"]    - out["wins"]
    out["pw_error"]    = out["pw_fc"]      - out["wins"]

    m = {
        "regression_factor": reg_f, "sos_weight": sos_w, "logit_scale": logit,
        "dynasty_streak": dynasty_streak, "dynasty_threshold": dynasty_threshold, "dynasty_r": dynasty_r,
        "warps_mae":  np.mean(np.abs(out["warps_error"])),
        "pyth_mae":   np.mean(np.abs(out["pyth_error"])),
        "pw_mae":     np.mean(np.abs(out["pw_error"])),
        "warps_rmse": math.sqrt(np.mean(out["warps_error"]**2)),
        "n": len(out), "years": f"{min(target_years)}-{max(target_years)}",
    }
    return out, m


# ── Calibration & market signals ──────────────────────────────────────────────

def calibration_buckets(team_results, n=6):
    df = team_results.copy()
    df["pred_bucket"] = pd.qcut(df["warps_wins"], q=n, duplicates="drop")
    return df.groupby("pred_bucket", observed=True).agg(
        teams=("team", "count"),
        avg_proj=("warps_wins", "mean"),
        avg_actual=("wins", "mean"),
        avg_error=("warps_error", "mean"),
        mae=("warps_error", lambda x: np.mean(np.abs(x))),
    ).reset_index()


def add_signals(screen, market_dict=None, strict=False):
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


def build_consensus(v15d_path, v16_path, v20_screen):
    v15 = pd.read_csv(v15d_path)[["team", "warps_wins", "edge", "signal"]].rename(
        columns={"warps_wins": "v15d_wins", "edge": "v15d_edge", "signal": "v15d_signal"})
    v16 = pd.read_csv(v16_path)[["team", "warps_wins", "edge", "signal"]].rename(
        columns={"warps_wins": "v16_wins", "edge": "v16_edge", "signal": "v16_signal"})
    v20 = v20_screen[["team", "warps_wins", "market_total", "edge", "signal"]].rename(
        columns={"warps_wins": "v20_wins", "edge": "v20_edge", "signal": "v20_signal"})

    c = v20.merge(v15, on="team", how="left").merge(v16, on="team", how="left")

    OVER_SIGS  = {"Strong Over", "Playable Over"}
    UNDER_SIGS = {"Strong Under", "Playable Under"}

    def classify(row):
        sigs = [row["v15d_signal"], row["v16_signal"], row["v20_signal"]]
        over_count   = sum(s in OVER_SIGS  for s in sigs)
        under_count  = sum(s in UNDER_SIGS for s in sigs)
        strong_over  = sum(s == "Strong Over"  for s in sigs)
        strong_under = sum(s == "Strong Under" for s in sigs)

        if over_count == 3:
            return "3-model Over"  if strong_over  >= 2 else "2-Strong Over"
        if under_count == 3:
            return "3-model Under" if strong_under >= 2 else "2-Strong Under"
        if over_count == 2 and strong_over >= 1:
            return "2-model Over"
        if under_count == 2 and strong_under >= 1:
            return "2-model Under"
        return "Split / No bet"

    c["consensus"] = c.apply(classify, axis=1)
    c["avg_edge"]  = (c["v15d_edge"] + c["v16_edge"] + c["v20_edge"]) / 3
    c["min_edge"]  = c[["v15d_edge", "v16_edge", "v20_edge"]].min(axis=1)
    c["max_edge"]  = c[["v15d_edge", "v16_edge", "v20_edge"]].max(axis=1)
    c["edge_range"] = c["max_edge"] - c["min_edge"]

    return c.sort_values("avg_edge", ascending=False).reset_index(drop=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def run(overrides_csv="warps_2026_overrides.csv", fast=False):
    print("=" * 70)
    print("WARPS-NFL v2.0 — Dynasty Persistence Modifier")
    print("=" * 70)

    schedules, team_stats = load_data(1999, 2026)
    csv_market, csv_qb = load_overrides_csv(overrides_csv)
    active_market = csv_market if csv_market is not None else MARKET_2026
    active_qb     = csv_qb     if csv_qb     is not None else QB_OVERRIDES_2026
    ts = build_component_diffs(team_stats)

    if fast:
        # ── Fast mode: inherit v1.8 champion, skip component search ───────
        print("\n[FAST] Using v1.8 champion: pyth_edge=0.90, point_diff=0.10")
        best_w      = V18_WEIGHTS
        best_reg_f  = V18_REG_F
        best_logit  = V18_LOGIT
        best_sos_w  = V18_SOS_W
    else:
        # ── Phase 1: Validate v1.8 champion on training window ────────────
        # (Full Phase 1-3 grid search inherited from v1.8 — run v1.8 for fresh search)
        print("\nPhase 1: Confirming v1.8 champion configuration...")
        best_w      = V18_WEIGHTS
        best_reg_f  = V18_REG_F
        best_logit  = V18_LOGIT
        best_sos_w  = V18_SOS_W
        _, base_train = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit, TRAIN_YEARS)
        _, base_val   = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit, VALIDATION_YEARS)
        print(f"  v1.8 base — train MAE={base_train['warps_mae']:.4f}  val MAE={base_val['warps_mae']:.4f}")

    # ── Phase 2: Dynasty parameter grid (training window only) ────────────
    print("\nPhase 2: Dynasty persistence grid search (training window 2000-2021)...")
    dynasty_rows = []
    n_configs = len(DYNASTY_STREAK_GRID) * len(DYNASTY_THRESHOLD_GRID) * len(DYNASTY_R_GRID)
    done = 0
    best_dynasty_train_mae = float("inf")
    best_dynasty_params = (DYNASTY_STREAK_DEFAULT, DYNASTY_THRESHOLD_DEFAULT, DYNASTY_R_DEFAULT)

    for streak, threshold, dr in product(DYNASTY_STREAK_GRID, DYNASTY_THRESHOLD_GRID, DYNASTY_R_GRID):
        _, tm = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit,
                         TRAIN_YEARS, dynasty_streak=streak, dynasty_threshold=threshold, dynasty_r=dr)
        _, vm = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit,
                         VALIDATION_YEARS, dynasty_streak=streak, dynasty_threshold=threshold, dynasty_r=dr)
        if tm and vm:
            dynasty_rows.append({
                "dynasty_streak": streak, "dynasty_threshold": threshold, "dynasty_r": dr,
                "train_mae": tm["warps_mae"], "val_mae": vm["warps_mae"],
            })
            if tm["warps_mae"] < best_dynasty_train_mae:
                best_dynasty_train_mae = tm["warps_mae"]
                best_dynasty_params = (streak, threshold, dr)
        done += 1
        if done % 5 == 0:
            print(f"  dynasty grid: {done}/{n_configs}")

    dynasty_df = pd.DataFrame(dynasty_rows).sort_values("train_mae").reset_index(drop=True)
    dynasty_df.to_csv("warps_dynasty_grid_v2_0.csv", index=False)

    d_streak, d_threshold, d_r = best_dynasty_params
    print(f"\n  Best dynasty config (by train MAE): streak={d_streak}  threshold={d_threshold}  R={d_r}")

    # Validation result for best config
    _, dynasty_val = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit,
                               VALIDATION_YEARS, dynasty_streak=d_streak, dynasty_threshold=d_threshold, dynasty_r=d_r)
    _, base_val    = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit, VALIDATION_YEARS)
    print(f"  Val MAE: base={base_val['warps_mae']:.4f}  dynasty={dynasty_val['warps_mae']:.4f}  "
          f"delta={dynasty_val['warps_mae']-base_val['warps_mae']:+.4f}")

    # ── Phase 3: Full backtest ─────────────────────────────────────────────
    print("\nPhase 3: Full backtest (2000-2025) with dynasty modifier...")
    full_res, full_m = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit,
                                 FULL_YEARS, dynasty_streak=d_streak, dynasty_threshold=d_threshold, dynasty_r=d_r)
    base_full, base_full_m = evaluate(schedules, ts, best_w, best_reg_f, best_sos_w, best_logit, FULL_YEARS)

    full_res.to_csv("warps_backtest_team_results_v2_0.csv", index=False)
    pd.DataFrame([full_m]).to_csv("warps_validation_metrics_v2_0.csv", index=False)

    by_year = full_res.groupby("season").agg(
        teams=("team", "count"),
        warps_mae=("warps_error",  lambda x: np.mean(np.abs(x))),
        pyth_mae=("pyth_error",    lambda x: np.mean(np.abs(x))),
        pw_mae=("pw_error",        lambda x: np.mean(np.abs(x))),
        warps_rmse=("warps_error", lambda x: math.sqrt(np.mean(x**2))),
    ).reset_index()
    by_year.to_csv("warps_backtest_by_year_v2_0.csv", index=False)

    # ── Phase 4: 2026 projections ──────────────────────────────────────────
    print("\nPhase 4: 2026 season projections...")
    pr = build_prior_ratings(ts, best_reg_f, best_w)
    dynasty_2026 = get_dynasty_teams(pr, 2026, d_streak, d_threshold)
    print(f"  2026 dynasty/collapse teams: {sorted(dynasty_2026)}")

    scr, games = project_season(2026, schedules, pr, qb_overrides=active_qb,
                                 sos_weight=best_sos_w, logit_scale=best_logit,
                                 dynasty_teams=dynasty_2026, dynasty_r=d_r, base_reg=best_reg_f)
    scr = add_signals(scr, market_dict=active_market, strict=True)
    scr.sort_values("edge", ascending=False).to_csv("warps_2026_screen_v2_0.csv", index=False)
    games.to_csv("warps_2026_game_probs_v2_0.csv", index=False)

    # ── Phase 5: Consensus screen ──────────────────────────────────────────
    consensus = build_consensus("warps_2026_screen_v1_5d.csv", "warps_2026_screen_v1_6.csv", scr)
    consensus.to_csv("warps_consensus_screen_v2_0.csv", index=False)

    # ── Print results ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DYNASTY GRID — TOP 10")
    print("=" * 70)
    print(dynasty_df.head(10).round(4).to_string(index=False))

    print("\n" + "=" * 70)
    print("FULL BACKTEST COMPARISON — v1.8 base vs v2.0 dynasty")
    print("=" * 70)
    print(f"  v1.8 (base):   MAE={base_full_m['warps_mae']:.4f}  RMSE={base_full_m['warps_rmse']:.4f}")
    print(f"  v2.0 (dynasty): MAE={full_m['warps_mae']:.4f}  RMSE={full_m['warps_rmse']:.4f}")
    print(f"  Delta:          MAE={full_m['warps_mae']-base_full_m['warps_mae']:+.4f}  RMSE={full_m['warps_rmse']-base_full_m['warps_rmse']:+.4f}")

    print("\n" + "=" * 70)
    print("BY-YEAR MAE (v2.0)")
    print("=" * 70)
    print(by_year.round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print(f"2026 PROJECTIONS — v2.0  (dynasty teams: {sorted(dynasty_2026)})")
    print("=" * 70)
    print(scr.sort_values("edge", ascending=False).round(2).to_string(index=False))

    print("\n" + "=" * 70)
    print("CONSENSUS — v1.5d + v1.6 + v2.0")
    print("=" * 70)
    cons_cols = ["team", "market_total", "v15d_edge", "v16_edge", "v20_edge",
                 "avg_edge", "edge_range", "consensus"]
    print(consensus[cons_cols].round(2).to_string(index=False))

    print("\n" + "=" * 70)
    print("HIGH-CONFIDENCE BET SLATE (3-model consensus)")
    print("=" * 70)
    top = consensus[consensus["consensus"].str.startswith("3-model")].copy()
    top = top.sort_values("avg_edge", ascending=False)
    if top.empty:
        print("  No 3-model consensus bets.")
    else:
        print(top[["team", "market_total", "avg_edge", "min_edge", "consensus"]].round(2).to_string(index=False))

    print("\n" + "=" * 70)
    print("VERSION SUMMARY")
    print("=" * 70)
    print(f"  v1.5d  reg=0.65  val_MAE=2.534  (composite, 2015-2021 training)")
    print(f"  v1.6   reg=0.75  val_MAE=2.512  (solo Pythagorean, 2015-2021 training)")
    print(f"  v1.8   reg=0.75  val_MAE=2.511  (pyth+ptdiff, 2000-2021 training)")
    print(f"  v2.0   reg=0.75  val_MAE={dynasty_val['warps_mae']:.3f}  (v1.8 + dynasty persistence, streak={d_streak} threshold={d_threshold} R={d_r})")
    improvement = base_val["warps_mae"] - dynasty_val["warps_mae"]
    print(f"\n  Dynasty modifier improvement over v1.8: {improvement:+.4f} wins/team on validation")
    print(f"  2026 dynasty/collapse teams: {sorted(dynasty_2026)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WARPS-NFL v2.0")
    parser.add_argument("--overrides", default="warps_2026_overrides.csv")
    parser.add_argument("--fast", action="store_true",
                        help="Skip Phase 1 validation, use v1.8 champion directly")
    args = parser.parse_args()
    run(overrides_csv=args.overrides, fast=args.fast)
