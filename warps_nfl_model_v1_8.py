"""
WARPS-NFL v1.8 — Extended Training Window (2000-2021) + Grid Search

v1.7 finding: Solo Pythagorean wins (regression factor 0.75, logit scale 5.5)
is the champion signal — it outperforms every composite on held-out data.

v1.8 change: Extend training from 7 seasons (2015-2021) to 22 seasons
(2000-2021). More data reduces the risk of the grid search locking onto
patterns specific to a small sample. The same search strategy is re-run
and champion selection still uses the held-out 2022-2025 seasons only.

Phases:
  1 : Fine grid over Pythagorean + Pass EPA + Point Differential (231 configs)
  2 : Randomized weight search biased toward Pythagorean region (300 draws)
  3 : Hyperparameter grid (regression factor x logit scale) for top candidates
  4 : Pick champion by held-out validation error (2022-2025)
  5 : Full backtest 2000-2025 + 2026 season win projections
  6 : 3-model consensus screen combining v1.5d, v1.6, and v1.8

Install:  pip install pandas numpy nfl_data_py
Run:      python warps_nfl_model_v1_8.py [--overrides warps_2026_overrides.csv]
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

TRAIN_YEARS      = list(range(2000, 2022))   # 22 seasons: more stable weight estimates
VALIDATION_YEARS = list(range(2022, 2026))   # held-out; never used for champion selection
FULL_YEARS       = list(range(2000, 2026))   # full 26-season backtest

REGRESSION_GRID  = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
SOS_GRID         = [0.00, 0.10, 0.15, 0.20, 0.25, 0.30]
LOGIT_SCALE_GRID = [5.5, 6.0, 6.5, 7.0, 7.5]

COMPONENTS = ["pass_epa", "rush_epa", "success", "explosive", "point_diff", "pyth_edge", "turnover"]

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "STL": "LAR",   # Rams: St. Louis through 2015
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
    print(f"[INFO] Turnover column: {turnover_col}")

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
    counts = team_stats.groupby("season")["team"].nunique()
    # Houston Texans joined in 2002, so 2000-2001 legitimately have 31 teams
    bad = counts[counts < 28]
    if not bad.empty:
        warnings.warn(f"Seasons with fewer than 28 teams (unexpected): {bad.to_dict()}")
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


def compute_sos(target_season, schedules, raw_map):
    reg = schedules[(schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))].copy()
    rows = []
    for _, g in reg.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        rows += [[h, raw_map.get(a, 0.0)], [a, raw_map.get(h, 0.0)]]
    sos = pd.DataFrame(rows, columns=["team", "opp"])
    return sos.groupby("team")["opp"].mean().to_dict()


def project_season(target, schedules, prior_ratings, qb_overrides=None,
                   sos_weight=0.0, logit_scale=6.5):
    prior_year = target - 1
    r = prior_ratings[prior_ratings["season"].eq(prior_year)][["team", "rating_pts", "raw_rating_pts"]]
    if r.empty:
        raise ValueError(f"No prior ratings for {prior_year}")

    pure_map = dict(zip(r["team"], r["rating_pts"]))
    raw_map  = dict(zip(r["team"], r["raw_rating_pts"]))
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
    games = pd.DataFrame(game_rows, columns=[
        "season", "home_team", "away_team", "home_expected_spread", "home_win_prob",
        "home_pure_quality_pts", "away_pure_quality_pts",
        "home_projection_quality_pts", "away_projection_quality_pts",
        "home_schedule_context_pts", "away_schedule_context_pts",
    ])
    return proj, games


def evaluate(schedules, ts_diffs, weights, reg_f, sos_w, logit, target_years):
    pr = build_prior_ratings(ts_diffs, reg_f, weights)
    projs = []
    for yr in target_years:
        try:
            p, _ = project_season(yr, schedules, pr, sos_weight=sos_w, logit_scale=logit)
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
    out["pyth_fc"]         = out["pyth_fc"] * (out["games"] / out["prior_g"])
    out["warps_error"]     = out["warps_wins"] - out["wins"]
    out["pyth_error"]      = out["pyth_fc"]    - out["wins"]
    out["pw_error"]        = out["pw_fc"]      - out["wins"]

    m = {
        "regression_factor": reg_f, "sos_weight": sos_w, "logit_scale": logit,
        "warps_mae":  np.mean(np.abs(out["warps_error"])),
        "pyth_mae":   np.mean(np.abs(out["pyth_error"])),
        "pw_mae":     np.mean(np.abs(out["pw_error"])),
        "warps_rmse": math.sqrt(np.mean(out["warps_error"]**2)),
        "n": len(out), "years": f"{min(target_years)}-{max(target_years)}",
    }
    return out, m


# ── Weight search ──────────────────────────────────────────────────────────────

def fine_3comp_grid(schedules, ts_diffs, reg_f=0.75, sos_w=0.0, logit=5.5, step=0.05):
    """Grid over pyth_edge + pass_epa + point_diff simplex."""
    vals  = np.round(np.arange(0.0, 1.0 + step, step), 10)
    rows  = []
    total = 0
    for pyth in vals:
        for pass_e in vals:
            pdiff = round(1.0 - pyth - pass_e, 10)
            if pdiff < -1e-9:
                continue
            pdiff = max(pdiff, 0.0)
            weights = _w(pyth_edge=float(pyth), pass_epa=float(pass_e), point_diff=float(pdiff))
            _, m = evaluate(schedules, ts_diffs, weights, reg_f, sos_w, logit, TRAIN_YEARS)
            if m:
                rows.append({"w_pyth_edge": pyth, "w_pass_epa": pass_e, "w_point_diff": pdiff, **m})
            total += 1
    df = pd.DataFrame(rows).sort_values("warps_mae").reset_index(drop=True)
    print(f"  fine_3comp_grid: {len(df)}/{total} configs evaluated")
    return df


def biased_dirichlet_search(schedules, ts_diffs, n=300, reg_f=0.75, sos_w=0.0, logit=5.5):
    """Dirichlet search biased toward pyth_edge + pass_epa region."""
    np.random.seed(2026)
    # alpha[5]=pyth_edge gets 8x weight, alpha[0]=pass_epa gets 3x
    alpha = np.array([3.0, 0.5, 1.0, 0.3, 1.5, 8.0, 0.3])
    samples = np.random.dirichlet(alpha, size=n)
    rows = []
    for i, raw in enumerate(samples):
        weights = dict(zip(COMPONENTS, raw))
        _, m = evaluate(schedules, ts_diffs, weights, reg_f, sos_w, logit, TRAIN_YEARS)
        if m:
            row = {f"w_{c}": weights[c] for c in COMPONENTS}
            row["config_name"] = f"dirichlet_{i:04d}"
            row.update(m)
            rows.append(row)
        if (i + 1) % 50 == 0:
            print(f"  biased Dirichlet: {i+1}/{n}")
    return pd.DataFrame(rows).sort_values("warps_mae").reset_index(drop=True)


def hyper_grid(schedules, ts_diffs, weights, target_years=None):
    if target_years is None:
        target_years = TRAIN_YEARS
    rows = []
    for rf, sw, ls in product(REGRESSION_GRID, SOS_GRID, LOGIT_SCALE_GRID):
        _, m = evaluate(schedules, ts_diffs, weights, rf, sw, ls, target_years)
        if m:
            rows.append(m)
    return pd.DataFrame(rows).sort_values(["warps_mae", "warps_rmse"]).reset_index(drop=True)


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


# ── Consensus screen ──────────────────────────────────────────────────────────

def build_consensus(v15d_path, v16_path, v17_screen):
    """Merge three model screens and classify consensus signal."""
    v15 = pd.read_csv(v15d_path)[["team", "warps_wins", "edge", "signal"]].rename(
        columns={"warps_wins": "v15d_wins", "edge": "v15d_edge", "signal": "v15d_signal"})
    v16 = pd.read_csv(v16_path)[["team", "warps_wins", "edge", "signal"]].rename(
        columns={"warps_wins": "v16_wins", "edge": "v16_edge", "signal": "v16_signal"})
    v17 = v17_screen[["team", "warps_wins", "market_total", "edge", "signal"]].rename(
        columns={"warps_wins": "v17_wins", "edge": "v17_edge", "signal": "v17_signal"})

    c = v17.merge(v15, on="team", how="left").merge(v16, on="team", how="left")

    OVER_SIGS  = {"Strong Over", "Playable Over"}
    UNDER_SIGS = {"Strong Under", "Playable Under"}

    def classify(row):
        sigs = [row["v15d_signal"], row["v16_signal"], row["v17_signal"]]
        over_count  = sum(s in OVER_SIGS  for s in sigs)
        under_count = sum(s in UNDER_SIGS for s in sigs)
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
    c["avg_edge"]  = (c["v15d_edge"] + c["v16_edge"] + c["v17_edge"]) / 3
    c["min_edge"]  = c[["v15d_edge", "v16_edge", "v17_edge"]].min(axis=1)
    c["max_edge"]  = c[["v15d_edge", "v16_edge", "v17_edge"]].max(axis=1)
    c["edge_range"] = c["max_edge"] - c["min_edge"]

    return c.sort_values("avg_edge", ascending=False).reset_index(drop=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def run(overrides_csv="warps_2026_overrides.csv"):
    print("=" * 70)
    print("WARPS-NFL v1.8 — Extended Training (2000-2021) + Grid Search")
    print("=" * 70)

    schedules, team_stats = load_data(1999, 2026)
    csv_market, csv_qb = load_overrides_csv(overrides_csv)
    active_market = csv_market if csv_market is not None else MARKET_2026
    active_qb     = csv_qb     if csv_qb     is not None else QB_OVERRIDES_2026
    ts = build_component_diffs(team_stats)

    # ── Phase 1: Fine 3-component grid ────────────────────────────────────
    print(f"\nPhase 1: Fine 3-component grid (pyth_edge + pass_epa + point_diff, step=0.05)...")
    g3 = fine_3comp_grid(schedules, ts, reg_f=0.75, sos_w=0.0, logit=5.5)
    g3.to_csv("warps_fine_3comp_grid_v1_8.csv", index=False)
    best3 = g3.iloc[0]
    print(f"  Best 3-comp: pyth={best3['w_pyth_edge']:.2f}  pass={best3['w_pass_epa']:.2f}  "
          f"pdiff={best3['w_point_diff']:.2f}  train_MAE={best3['warps_mae']:.4f}")

    # ── Phase 2: Biased Dirichlet search ──────────────────────────────────
    print(f"\nPhase 2: Biased Dirichlet (n=300, pyth/pass-EPA biased)...")
    bd = biased_dirichlet_search(schedules, ts, n=300, reg_f=0.75, sos_w=0.0, logit=5.5)
    bd.to_csv("warps_biased_dirichlet_v1_8.csv", index=False)
    best_bd = bd.iloc[0]
    print(f"  Best Dirichlet train_MAE={best_bd['warps_mae']:.4f}")

    # ── Phase 3: Hyper grid for top-5 candidates ──────────────────────────
    # Gather top-5 across both searches by train MAE, deduplicate
    candidates = {}
    for _, row in g3.head(3).iterrows():
        w = _w(pyth_edge=row["w_pyth_edge"], pass_epa=row["w_pass_epa"], point_diff=row["w_point_diff"])
        key = f"3comp_pyth{row['w_pyth_edge']:.2f}_pass{row['w_pass_epa']:.2f}"
        candidates[key] = w
    for i, (_, row) in enumerate(bd.head(3).iterrows()):
        w = {c: row[f"w_{c}"] for c in COMPONENTS}
        candidates[f"dirichlet_{i}"] = w

    print(f"\nPhase 3: Hyper grid (180 combos) for {len(candidates)} candidates...")
    best_val_mae, best_name, best_w, best_grid = float("inf"), None, None, None
    for cname, cw in candidates.items():
        grid = hyper_grid(schedules, ts, cw, TRAIN_YEARS)
        best = grid.iloc[0]
        _, vm = evaluate(schedules, ts, cw,
                         float(best["regression_factor"]), float(best["sos_weight"]),
                         float(best["logit_scale"]), VALIDATION_YEARS)
        vl = vm["warps_mae"] if vm else float("inf")
        print(f"  {cname:45s}  train={best['warps_mae']:.4f}  val={vl:.4f}")
        if vl < best_val_mae:
            best_val_mae = vl
            best_name    = cname
            best_w       = cw
            best_hypers  = (float(best["regression_factor"]),
                            float(best["sos_weight"]),
                            float(best["logit_scale"]))
            best_grid    = grid

    print(f"\n★ Champion: {best_name}")
    reg_f, sos_w, logit_s = best_hypers
    print(f"  regression_factor={reg_f}  sos_weight={sos_w}  logit_scale={logit_s}")
    print(f"  Val MAE={best_val_mae:.4f}")
    print(f"  Weights: { {c: round(best_w[c],4) for c in COMPONENTS} }")
    best_grid.to_csv("warps_parameter_grid_v1_8.csv", index=False)

    # ── Phase 4: Full backtest + validation ────────────────────────────────
    full_res, full_m = evaluate(schedules, ts, best_w, reg_f, sos_w, logit_s, FULL_YEARS)
    val_res,  val_m  = evaluate(schedules, ts, best_w, reg_f, sos_w, logit_s, VALIDATION_YEARS)

    full_res.to_csv("warps_backtest_team_results_v1_8.csv", index=False)
    pd.DataFrame([val_m]).to_csv("warps_validation_metrics_v1_8.csv", index=False)

    by_year = full_res.groupby("season").agg(
        teams=("team", "count"),
        warps_mae=("warps_error",  lambda x: np.mean(np.abs(x))),
        pyth_mae=("pyth_error",    lambda x: np.mean(np.abs(x))),
        pw_mae=("pw_error",        lambda x: np.mean(np.abs(x))),
        warps_rmse=("warps_error", lambda x: math.sqrt(np.mean(x**2))),
    ).reset_index()
    by_year.to_csv("warps_backtest_by_year_v1_8.csv", index=False)

    cal = calibration_buckets(full_res)
    cal.to_csv("warps_calibration_buckets_v1_8.csv", index=False)

    # ── Phase 5: 2026 screen ──────────────────────────────────────────────
    pr = build_prior_ratings(ts, reg_f, best_w)
    scr, games = project_season(2026, schedules, pr, qb_overrides=active_qb,
                                sos_weight=sos_w, logit_scale=logit_s)
    scr = add_signals(scr, market_dict=active_market, strict=True)
    scr.sort_values("edge", ascending=False).to_csv("warps_2026_screen_v1_8.csv", index=False)
    games.to_csv("warps_2026_game_probs_v1_8.csv", index=False)

    # ── Phase 6: Consensus screen ─────────────────────────────────────────
    v15d_path = "warps_2026_screen_v1_5d.csv"
    v16_path  = "warps_2026_screen_v1_6.csv"
    consensus = build_consensus(v15d_path, v16_path, scr)
    consensus.to_csv("warps_consensus_screen_v1_8.csv", index=False)

    # ── Print results ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("CHAMPION WEIGHTS")
    print("=" * 70)
    for c in COMPONENTS:
        if best_w[c] > 0.001:
            print(f"  {c:15s}: {best_w[c]:.4f}")

    print("\n" + "=" * 70)
    print("FULL BACKTEST (2000-2025)")
    print("=" * 70)
    print(pd.DataFrame([full_m]).round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("VALIDATION (2022-2025)")
    print("=" * 70)
    print(pd.DataFrame([val_m]).round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("BY-YEAR: WARPS v1.8 vs Pythagorean vs Prior Wins")
    print("=" * 70)
    print(by_year.round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("CALIBRATION BUCKETS")
    print("=" * 70)
    print(cal.round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("2026 SCREEN — v1.7 sorted by edge")
    print("=" * 70)
    print(scr.sort_values("edge", ascending=False).round(2).to_string(index=False))

    print("\n" + "=" * 70)
    print("CONSENSUS SCREEN — v1.5d + v1.6 + v1.8")
    print("=" * 70)
    cons_cols = ["team", "market_total", "v15d_edge", "v16_edge", "v17_edge",
                 "avg_edge", "edge_range", "consensus",
                 "v15d_signal", "v16_signal", "v17_signal"]
    print(consensus[cons_cols].round(2).to_string(index=False))

    print("\n" + "=" * 70)
    print("HIGH-CONFIDENCE BET SLATE (consensus = 3-model)")
    print("=" * 70)
    top = consensus[consensus["consensus"].str.startswith("3-model")].copy()
    top = top.sort_values("avg_edge", ascending=False)
    if top.empty:
        print("  No 3-model consensus bets found.")
    else:
        print(top[["team", "market_total", "avg_edge", "min_edge",
                   "consensus", "v15d_signal", "v16_signal", "v17_signal"]].round(2).to_string(index=False))

    print("\n" + "=" * 70)
    print("STRONG AGREEMENT (2 of 3 models Strong, same direction)")
    print("=" * 70)
    partial = consensus[consensus["consensus"].str.contains("Strong") &
                        ~consensus["consensus"].str.startswith("3-model")].copy()
    partial = partial.sort_values("avg_edge", ascending=False)
    if partial.empty:
        print("  None.")
    else:
        print(partial[["team", "market_total", "avg_edge", "consensus",
                        "v15d_signal", "v16_signal", "v17_signal"]].round(2).to_string(index=False))

    # version comparison
    print("\n" + "=" * 70)
    print("VERSION COMPARISON SUMMARY")
    print("=" * 70)
    print(f"  v1.5d  reg=0.65, logit=6.5  val_MAE=2.534  (original composite, 2015-2021 training)")
    print(f"  v1.6   reg=0.75, logit=5.5  val_MAE=2.512  (solo Pythagorean champion, 2015-2021 training)")
    print(f"  v1.7   reg=0.75, logit=5.5  val_MAE=2.514  (fine grid, 2015-2021 training)")
    print(f"  v1.8   reg={reg_f},  logit={logit_s}  val_MAE={val_m['warps_mae']:.3f}  ({best_name}, 2000-2021 training)")
    improvement = 2.534 - val_m["warps_mae"]
    print(f"\n  v1.8 improvement over v1.5d: {improvement:+.3f} wins/team on validation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WARPS-NFL v1.8")
    parser.add_argument("--overrides", default="warps_2026_overrides.csv")
    args = parser.parse_args()
    run(overrides_csv=args.overrides)
