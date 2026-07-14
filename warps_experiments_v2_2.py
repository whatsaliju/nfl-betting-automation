"""
WARPS-NFL v2.2 Experiments — Feature Expansion Tests

Tests four hypotheses against the v1.8 champion (w_pyth=0.75, w_pd=0.25, R=0.75, MAE=2.376):

  EXP-1: Multi-year rolling Pythagorean (2yr and 3yr weighted averages of prior seasons)
  EXP-2: Offensive / defensive Pythagorean decomposition (pf_z vs pa_z weighted separately)
  EXP-3: SOS-adjusted Pythagorean (adjust raw scores by opponent quality before computing pyth)
  EXP-4: Turnover-adjusted point differential (strip estimated turnover points from pd)

All experiments use the same train/validation split as v1.8:
  Training:   2000-2021 (22 seasons)
  Validation: 2022-2025 (4 held-out seasons)

Run:  python warps_experiments_v2_2.py
"""

import math
import warnings

import numpy as np
import pandas as pd

try:
    import nfl_data_py as nfl
except ImportError as exc:
    raise SystemExit("pip install nfl_data_py pandas numpy") from exc


# ── Constants (same as v1.8) ───────────────────────────────────────────────────

PYTH_EXPONENT  = 2.37
HOME_FIELD     = 1.5
SCALE_FACTOR   = 3.0
LEAGUE_MEAN    = 8.5    # approximate — model is logit-spread based, not additive

TRAIN_YEARS      = list(range(2000, 2022))
VALIDATION_YEARS = list(range(2022, 2026))
ALL_YEARS        = list(range(2000, 2026))

CHAMPION_W_PYTH = 0.75
CHAMPION_W_PD   = 0.25
CHAMPION_R      = 0.75
CHAMPION_LOGIT  = 5.5

# Estimated win value of each turnover margin unit (from NFL historical EPA analysis)
TURNOVER_POINT_VALUE = 4.5  # points per net turnover above average → ~0.3w per game

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "STL": "LAR",
    "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def norm_team(t):
    if pd.isna(t):
        return t
    return TEAM_ALIASES.get(str(t), str(t))

def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    std = s.std(ddof=0)
    return s * 0 if (std == 0 or pd.isna(std)) else (s - s.mean()) / std

def pyth_win_pct(pf, pa):
    pf, pa = max(float(pf), 1.0), max(float(pa), 1.0)
    return (pf ** PYTH_EXPONENT) / ((pf ** PYTH_EXPONENT) + (pa ** PYTH_EXPONENT))

def win_prob_from_spread(spread, logit_scale):
    return 1 / (1 + np.exp(-spread / logit_scale))

def mae(errors):
    return np.mean(np.abs(errors))


# ── Data loading ──────────────────────────────────────────────────────────────
#
# Schedules-only path: computes pf, pa, wins, games, pyth_wins from game scores.
# No PBP download required — avoids 403 errors on recent seasons.
# EXP-4 (turnover-adj) uses a PBP-optional path; skipped gracefully if unavailable.

SCHEDULES_URL = "https://raw.githubusercontent.com/leesharpe/nfldata/master/data/games.csv"

def load_schedules(start=1999, end=2025):
    seasons = list(range(start, end + 1))
    print(f"[INFO] Loading schedules for {seasons[0]}-{seasons[-1]}...")
    try:
        schedules = nfl.import_schedules(seasons)
        if "game_type" not in schedules.columns and "season_type" in schedules.columns:
            schedules = schedules.rename(columns={"season_type": "game_type"})
    except Exception as e:
        print(f"[WARN] nfl.import_schedules failed ({e}), using fallback CSV...")
        schedules = pd.read_csv(SCHEDULES_URL)
        schedules = schedules[schedules["season"].isin(seasons)]

    schedules["home_team"] = schedules["home_team"].map(norm_team)
    schedules["away_team"] = schedules["away_team"].map(norm_team)
    return schedules


def build_team_stats_from_schedules(schedules):
    """Compute per-team per-season records (wins, pf, pa, games, pyth_wins) from game scores."""
    # Filter: REG games only, completed (both scores present)
    game_type_col = "game_type" if "game_type" in schedules.columns else "season_type"
    reg = schedules[schedules[game_type_col].eq("REG")].copy()
    reg = reg.dropna(subset=["home_score", "away_score"])

    rows = []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        hw = 0.5 if hs == as_ else (1.0 if hs > as_ else 0.0)
        rows += [
            [int(g["season"]), home, hw, hs, as_],
            [int(g["season"]), away, 1 - hw, as_, hs],
        ]

    records = pd.DataFrame(rows, columns=["season", "team", "wins", "pf", "pa"])
    records = records.groupby(["season", "team"], as_index=False).agg(
        wins=("wins", "sum"), games=("wins", "count"), pf=("pf", "sum"), pa=("pa", "sum")
    )
    records["pyth_wins"]     = records.apply(lambda r: pyth_win_pct(r["pf"], r["pa"]) * r["games"], axis=1)
    records["point_diff_pg"] = (records["pf"] - records["pa"]) / records["games"]
    return records


def load_turnover_margins(start=1999, end=2023):
    """
    Load per-team per-season turnover margins from PBP.
    Returns None if PBP data is unavailable (e.g. 403 in restricted environments).
    Only loads seasons up to end to avoid 403 on recent data.
    """
    seasons = list(range(start, end + 1))
    print(f"[INFO] Loading PBP turnover data for {seasons[0]}-{seasons[-1]} (optional)...")
    try:
        pbp = nfl.import_pbp_data(seasons, downcast=True)
        if "season_type" not in pbp.columns:
            print("[WARN] PBP missing season_type column — skipping turnover experiment")
            return None
        pbp = pbp[pbp["season_type"].eq("REG")].copy()
        for col in ["posteam", "defteam"]:
            pbp[col] = pbp[col].map(norm_team)
        pbp = pbp.dropna(subset=["posteam", "defteam"])

        turnover_col = "turnover" if "turnover" in pbp.columns else "interception"
        off = pbp.groupby(["season", "posteam"], as_index=False).agg(
            off_to=(turnover_col, "mean")
        ).rename(columns={"posteam": "team"})
        def_ = pbp.groupby(["season", "defteam"], as_index=False).agg(
            def_to_forced=(turnover_col, "mean")
        ).rename(columns={"defteam": "team"})
        to = off.merge(def_, on=["season", "team"], how="inner")
        to["turnover_margin"] = to["def_to_forced"] - to["off_to"]
        print(f"[INFO] Turnover data loaded: {len(to)} team-seasons")
        return to[["season", "team", "turnover_margin"]]
    except Exception as e:
        print(f"[WARN] PBP load failed ({e}) — EXP-4 will be skipped")
        return None


def load_data(start=1999, end=2025):
    schedules  = load_schedules(start, end)
    team_stats = build_team_stats_from_schedules(schedules)
    to_margins = load_turnover_margins(start, min(end, 2023))
    if to_margins is not None:
        team_stats = team_stats.merge(to_margins, on=["season", "team"], how="left")
    else:
        team_stats["turnover_margin"] = np.nan
    return schedules, team_stats


# ── Champion baseline (reproduces v1.8 projection logic) ──────────────────────

def project_wins(schedules, priors_map, target_season, logit_scale=CHAMPION_LOGIT):
    """
    Given a dict {team: rating_pts} for the prior season, project win totals
    for target_season using the game-by-game win probability approach.
    """
    reg = schedules[
        (schedules["season"].eq(target_season)) & (schedules["game_type"].eq("REG"))
    ].copy()
    if reg.empty:
        return {}

    rows = []
    for _, g in reg.iterrows():
        home, away = norm_team(g["home_team"]), norm_team(g["away_team"])
        spread = priors_map.get(home, 0.0) - priors_map.get(away, 0.0) + HOME_FIELD
        hwp = win_prob_from_spread(spread, logit_scale)
        rows += [[home, hwp], [away, 1 - hwp]]

    df = pd.DataFrame(rows, columns=["team", "wp"])
    return df.groupby("team")["wp"].sum().to_dict()


def build_rating_from_z(season_df, regression_factor, weights):
    """
    Given a season's team data with pre-computed z-scored columns,
    build regressed rating points using provided weights dict.
    weights: {col_name: weight, ...} — columns must exist in season_df.
    """
    total_w = sum(weights.values()) or 1.0
    z_sum = sum(season_df[col] * w for col, w in weights.items()) / total_w
    raw = SCALE_FACTOR * z_sum
    return raw * regression_factor


def evaluate_config(schedules, team_stats, feature_fn, weights, regression_factor,
                    train_years=TRAIN_YEARS, val_years=VALIDATION_YEARS,
                    logit_scale=CHAMPION_LOGIT):
    """
    Core evaluation loop. feature_fn(season_df) → season_df with z-scored feature columns.
    weights: {col: w} applied to z-scored columns output by feature_fn.
    Returns (train_mae, val_mae, all_mae) tuples.
    """
    all_years = sorted(set(train_years) | set(val_years))
    all_projections = []

    for target in all_years:
        prior_year = target - 1
        prior_df = team_stats[team_stats["season"].eq(prior_year)].copy()
        if prior_df.empty:
            continue

        prior_df = feature_fn(prior_df, team_stats)  # feature_fn may need full history
        prior_df["_rating"] = build_rating_from_z(prior_df, regression_factor, weights)
        rating_map = dict(zip(prior_df["team"], prior_df["_rating"]))

        proj_map = project_wins(schedules, rating_map, target, logit_scale)
        if not proj_map:
            continue

        actual = team_stats[team_stats["season"].eq(target)][["team", "wins", "games"]].copy()
        for _, row in actual.iterrows():
            if row["team"] in proj_map:
                all_projections.append({
                    "season": target,
                    "team": row["team"],
                    "proj": proj_map[row["team"]],
                    "actual": row["wins"],
                    "split": "train" if target in train_years else "val",
                })

    df = pd.DataFrame(all_projections)
    if df.empty:
        return None, None, None

    df["error"] = df["proj"] - df["actual"]
    train_mae = mae(df[df["split"] == "train"]["error"])
    val_mae   = mae(df[df["split"] == "val"]["error"]) if (df["split"] == "val").any() else None
    all_mae   = mae(df["error"])
    return train_mae, val_mae, all_mae


# ── Champion feature function ──────────────────────────────────────────────────

def features_champion(season_df, all_stats):
    df = season_df.copy()
    df["z_pyth"]  = zscore(df["pyth_wins"])
    df["z_pd"]    = zscore(df["point_diff_pg"])
    return df

CHAMPION_WEIGHTS = {"z_pyth": CHAMPION_W_PYTH, "z_pd": CHAMPION_W_PD}


# ── EXP-1: Multi-year rolling Pythagorean ─────────────────────────────────────

def features_rolling_2yr(season_df, all_stats, w1=0.7, w2=0.3):
    """Blend t-1 and t-2 Pythagorean wins."""
    df = season_df.copy()
    season = df["season"].iloc[0]
    prior2 = all_stats[all_stats["season"].eq(season - 1)][["team", "pyth_wins"]].rename(
        columns={"pyth_wins": "pyth_t2"}
    )
    df = df.merge(prior2, on="team", how="left")
    df["pyth_rolled"] = df["pyth_wins"] * w1 + df["pyth_t2"].fillna(df["pyth_wins"]) * w2
    df["z_pyth"] = zscore(df["pyth_rolled"])
    df["z_pd"]   = zscore(df["point_diff_pg"])
    return df

def features_rolling_3yr(season_df, all_stats, w1=0.6, w2=0.3, w3=0.1):
    """Blend t-1, t-2, and t-3 Pythagorean wins."""
    df = season_df.copy()
    season = df["season"].iloc[0]
    prior2 = all_stats[all_stats["season"].eq(season - 1)][["team", "pyth_wins"]].rename(
        columns={"pyth_wins": "pyth_t2"}
    )
    prior3 = all_stats[all_stats["season"].eq(season - 2)][["team", "pyth_wins"]].rename(
        columns={"pyth_wins": "pyth_t3"}
    )
    df = df.merge(prior2, on="team", how="left").merge(prior3, on="team", how="left")
    df["pyth_rolled"] = (
        df["pyth_wins"] * w1
        + df["pyth_t2"].fillna(df["pyth_wins"]) * w2
        + df["pyth_t3"].fillna(df["pyth_wins"]) * w3
    )
    df["z_pyth"] = zscore(df["pyth_rolled"])
    df["z_pd"]   = zscore(df["point_diff_pg"])
    return df


# ── EXP-2: Offensive / defensive Pythagorean split ────────────────────────────

def features_off_def_split(season_df, all_stats):
    """Separate z-scores for points scored (offense) and points allowed (defense)."""
    df = season_df.copy()
    df["pf_pg"] = df["pf"] / df["games"]
    df["pa_pg"] = df["pa"] / df["games"]
    df["z_off"] = zscore(df["pf_pg"])         # higher = better offense
    df["z_def"] = zscore(-df["pa_pg"])        # higher = better defense (inverted)
    df["z_pd"]  = zscore(df["point_diff_pg"])
    return df


# ── EXP-3: SOS-adjusted Pythagorean ───────────────────────────────────────────

def build_sos_adjusted_pyth(season_df, schedules):
    """
    Adjust each team's points for and against by their opponents' average
    defensive and offensive quality, then recompute Pythagorean.

    Approach:
      1. Compute league-average pf_pg and pa_pg.
      2. For each team, find their opponents and compute avg opponent pf_pg and pa_pg.
      3. adj_pf = raw_pf * (league_avg_pa / opp_avg_pa)  — scored more vs good defenses → scale up
      4. adj_pa = raw_pa * (league_avg_pf / opp_avg_pf)  — allowed more vs good offenses → scale down
      5. Recompute Pythagorean from adjusted pf, pa.
    """
    season = int(season_df["season"].iloc[0])
    sched = schedules[(schedules["season"].eq(season)) & (schedules["game_type"].eq("REG"))].copy()

    pf_map = dict(zip(season_df["team"], season_df["pf"] / season_df["games"]))
    pa_map = dict(zip(season_df["team"], season_df["pa"] / season_df["games"]))
    league_pf = np.mean(list(pf_map.values()))
    league_pa = np.mean(list(pa_map.values()))

    opp_pa_sum, opp_pf_sum, opp_count = {}, {}, {}
    for _, g in sched.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        for team, opp in [(h, a), (a, h)]:
            if team not in opp_pa_sum:
                opp_pa_sum[team] = 0.0
                opp_pf_sum[team] = 0.0
                opp_count[team]  = 0
            opp_pa_sum[team] += pa_map.get(opp, league_pa)
            opp_pf_sum[team] += pf_map.get(opp, league_pf)
            opp_count[team]  += 1

    df = season_df.copy()
    df["opp_avg_pa"] = df["team"].map(lambda t: opp_pa_sum.get(t, 0) / max(opp_count.get(t, 1), 1))
    df["opp_avg_pf"] = df["team"].map(lambda t: opp_pf_sum.get(t, 0) / max(opp_count.get(t, 1), 1))

    df["adj_pf"] = (df["pf"] / df["games"]) * (league_pa / df["opp_avg_pa"].clip(lower=1.0))
    df["adj_pa"] = (df["pa"] / df["games"]) * (league_pf / df["opp_avg_pf"].clip(lower=1.0))
    df["pyth_adj"] = df.apply(lambda r: pyth_win_pct(r["adj_pf"], r["adj_pa"]) * r["games"], axis=1)

    df["z_pyth"] = zscore(df["pyth_adj"])
    df["z_pd"]   = zscore(df["point_diff_pg"])
    return df

def features_sos_adjusted(season_df, all_stats, schedules_ref=None):
    return build_sos_adjusted_pyth(season_df, schedules_ref)


# ── EXP-4: Turnover-adjusted point differential ───────────────────────────────

def features_turnover_adj_pd(season_df, all_stats):
    """
    Strip estimated turnover-caused points from point differential.
    Logic: each net turnover is worth ~4.5 points (opponent field position + scoring probability).
    adj_pd = raw_pd - TURNOVER_POINT_VALUE * turnover_margin
    This isolates 'earned' scoring margin from lucky takeaways/giveaways.
    """
    df = season_df.copy()
    df["adj_pd_pg"] = df["point_diff_pg"] - TURNOVER_POINT_VALUE * df["turnover_margin"]
    df["z_pyth"]    = zscore(df["pyth_wins"])
    df["z_pd"]      = zscore(df["adj_pd_pg"])
    return df


# ── Grid search helpers ────────────────────────────────────────────────────────

def grid_two_features(schedules, team_stats, feature_fn, col_a, col_b,
                      regression_factor=CHAMPION_R, step=0.05, feature_fn_kwargs=None):
    """Grid search over w_a, w_b simplex at given step size."""
    if feature_fn_kwargs is None:
        feature_fn_kwargs = {}
    vals = np.round(np.arange(0.0, 1.0 + step, step), 10)
    results = []
    for w_a in vals:
        w_b = round(1.0 - w_a, 10)
        if w_b < -1e-9:
            continue
        w_b = max(w_b, 0.0)
        weights = {col_a: float(w_a), col_b: float(w_b)}

        def _feature_fn(sd, as_, _weights=weights, _fn=feature_fn, _kw=feature_fn_kwargs):
            return _fn(sd, as_, **_kw)

        train_mae, val_mae, _ = evaluate_config(
            schedules, team_stats, _feature_fn, weights, regression_factor
        )
        results.append({"w_a": w_a, "w_b": w_b, "train_mae": train_mae, "val_mae": val_mae})

    return pd.DataFrame(results).sort_values("val_mae").reset_index(drop=True)

def grid_three_features(schedules, team_stats, feature_fn, col_a, col_b, col_c,
                        regression_factor=CHAMPION_R, step=0.05, feature_fn_kwargs=None):
    """Grid search over w_a + w_b + w_c = 1 simplex."""
    if feature_fn_kwargs is None:
        feature_fn_kwargs = {}
    vals = np.round(np.arange(0.0, 1.0 + step, step), 10)
    results = []
    for w_a in vals:
        for w_b in vals:
            w_c = round(1.0 - w_a - w_b, 10)
            if w_c < -1e-9:
                continue
            w_c = max(w_c, 0.0)
            weights = {col_a: float(w_a), col_b: float(w_b), col_c: float(w_c)}

            def _feature_fn(sd, as_, _weights=weights, _fn=feature_fn, _kw=feature_fn_kwargs):
                return _fn(sd, as_, **_kw)

            train_mae, val_mae, _ = evaluate_config(
                schedules, team_stats, _feature_fn, weights, regression_factor
            )
            results.append({"w_a": w_a, "w_b": w_b, "w_c": w_c, "train_mae": train_mae, "val_mae": val_mae})

    return pd.DataFrame(results).sort_values("val_mae").reset_index(drop=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    schedules, team_stats = load_data(start=1999, end=2025)

    print("\n" + "=" * 70)
    print("CHAMPION BASELINE (v1.8: w_pyth=0.75, w_pd=0.25, R=0.75)")
    print("=" * 70)
    champ_train, champ_val, _ = evaluate_config(
        schedules, team_stats, features_champion, CHAMPION_WEIGHTS, CHAMPION_R
    )
    print(f"  Train MAE (2001-2022): {champ_train:.4f}")
    print(f"  Val MAE   (2022-2025): {champ_val:.4f}")

    summary = [{"experiment": "Champion v1.8", "best_val_mae": champ_val,
                "best_train_mae": champ_train, "delta_val": 0.0, "best_config": "w_pyth=0.75, w_pd=0.25"}]

    # ── EXP-1a: 2-year rolling Pythagorean ────────────────────────────────────
    print("\n" + "=" * 70)
    print("EXP-1a: 2-year rolling Pythagorean (various blend weights)")
    print("=" * 70)
    roll2_results = []
    for w1 in [0.5, 0.6, 0.7, 0.8, 0.9]:
        w2 = round(1.0 - w1, 2)
        def _fn(sd, as_, _w1=w1, _w2=w2):
            return features_rolling_2yr(sd, as_, w1=_w1, w2=_w2)
        t_mae, v_mae, _ = evaluate_config(schedules, team_stats, _fn, CHAMPION_WEIGHTS, CHAMPION_R)
        roll2_results.append({"w_t1": w1, "w_t2": w2, "train_mae": t_mae, "val_mae": v_mae})
        print(f"  w_t1={w1:.1f} w_t2={w2:.1f} → train={t_mae:.4f}  val={v_mae:.4f}")
    best2 = min(roll2_results, key=lambda r: r["val_mae"])
    delta2 = best2["val_mae"] - champ_val
    print(f"\n  Best: w_t1={best2['w_t1']:.1f} val={best2['val_mae']:.4f}  Δ vs champion: {delta2:+.4f}")
    summary.append({"experiment": "EXP-1a: 2yr rolling pyth", "best_val_mae": best2["val_mae"],
                    "best_train_mae": best2["train_mae"], "delta_val": delta2,
                    "best_config": f"w_t1={best2['w_t1']:.1f}, w_t2={best2['w_t2']:.1f}"})

    # ── EXP-1b: 3-year rolling Pythagorean ────────────────────────────────────
    print("\n" + "=" * 70)
    print("EXP-1b: 3-year rolling Pythagorean (fixed blend 0.6/0.3/0.1)")
    print("=" * 70)
    def fn_3yr(sd, as_):
        return features_rolling_3yr(sd, as_, w1=0.6, w2=0.3, w3=0.1)
    t3, v3, _ = evaluate_config(schedules, team_stats, fn_3yr, CHAMPION_WEIGHTS, CHAMPION_R)
    delta3 = v3 - champ_val
    print(f"  train={t3:.4f}  val={v3:.4f}  Δ vs champion: {delta3:+.4f}")
    summary.append({"experiment": "EXP-1b: 3yr rolling pyth (0.6/0.3/0.1)", "best_val_mae": v3,
                    "best_train_mae": t3, "delta_val": delta3, "best_config": "w_t1=0.6, w_t2=0.3, w_t3=0.1"})

    # ── EXP-2: Off/Def split ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("EXP-2: Offensive / defensive Pythagorean split")
    print("  (w_off=z_scored pf/game, w_def=z_scored -pa/game, w_pd=point diff)")
    print("=" * 70)
    od_results = []
    for w_off in np.arange(0.0, 1.05, 0.1):
        for w_def in np.arange(0.0, 1.0 - w_off + 0.05, 0.1):
            w_pd = round(1.0 - w_off - w_def, 10)
            if w_pd < -1e-9:
                continue
            w_pd = max(w_pd, 0.0)
            weights = {"z_off": round(w_off, 2), "z_def": round(w_def, 2), "z_pd": round(w_pd, 2)}

            def _fn(sd, as_, _w=weights):
                df = features_off_def_split(sd, as_)
                return df

            t_mae, v_mae, _ = evaluate_config(schedules, team_stats, _fn, weights, CHAMPION_R)
            od_results.append({**weights, "train_mae": t_mae, "val_mae": v_mae})

    od_df = pd.DataFrame(od_results).sort_values("val_mae").reset_index(drop=True)
    best_od = od_df.iloc[0]
    delta_od = best_od["val_mae"] - champ_val
    print(f"  Top 5 configs by val MAE:")
    for _, row in od_df.head(5).iterrows():
        print(f"    w_off={row['z_off']:.2f} w_def={row['z_def']:.2f} w_pd={row['z_pd']:.2f} "
              f"→ train={row['train_mae']:.4f}  val={row['val_mae']:.4f}")
    print(f"\n  Best val={best_od['val_mae']:.4f}  Δ vs champion: {delta_od:+.4f}")
    summary.append({
        "experiment": "EXP-2: Off/Def split",
        "best_val_mae": best_od["val_mae"],
        "best_train_mae": best_od["train_mae"],
        "delta_val": delta_od,
        "best_config": f"w_off={best_od['z_off']:.2f}, w_def={best_od['z_def']:.2f}, w_pd={best_od['z_pd']:.2f}",
    })

    # ── EXP-3: SOS-adjusted Pythagorean ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("EXP-3: SOS-adjusted Pythagorean (opponent-quality-scaled scores)")
    print("=" * 70)
    sos_results = []
    for w_pyth_adj in np.arange(0.0, 1.05, 0.1):
        w_pd = round(1.0 - w_pyth_adj, 10)
        w_pd = max(w_pd, 0.0)
        weights = {"z_pyth": round(w_pyth_adj, 2), "z_pd": round(w_pd, 2)}

        def _fn(sd, as_, _w=weights, _sched=schedules):
            return features_sos_adjusted(sd, as_, schedules_ref=_sched)

        t_mae, v_mae, _ = evaluate_config(schedules, team_stats, _fn, weights, CHAMPION_R)
        sos_results.append({"w_pyth_adj": round(w_pyth_adj, 2), "w_pd": round(w_pd, 2),
                            "train_mae": t_mae, "val_mae": v_mae})
        print(f"  w_pyth_adj={w_pyth_adj:.1f} w_pd={w_pd:.1f} → train={t_mae:.4f}  val={v_mae:.4f}")

    sos_df = pd.DataFrame(sos_results).sort_values("val_mae").reset_index(drop=True)
    best_sos = sos_df.iloc[0]
    delta_sos = best_sos["val_mae"] - champ_val
    print(f"\n  Best: w_pyth_adj={best_sos['w_pyth_adj']:.2f}  val={best_sos['val_mae']:.4f}  "
          f"Δ vs champion: {delta_sos:+.4f}")
    summary.append({
        "experiment": "EXP-3: SOS-adjusted pyth",
        "best_val_mae": best_sos["val_mae"],
        "best_train_mae": best_sos["train_mae"],
        "delta_val": delta_sos,
        "best_config": f"w_pyth_adj={best_sos['w_pyth_adj']:.2f}, w_pd={best_sos['w_pd']:.2f}",
    })

    # ── EXP-4: Turnover-adjusted point differential ───────────────────────────
    print("\n" + "=" * 70)
    print(f"EXP-4: Turnover-adjusted point differential (strip {TURNOVER_POINT_VALUE}pts/turnover)")
    print("=" * 70)
    has_to = team_stats["turnover_margin"].notna().any()
    if not has_to:
        print("  [SKIP] Turnover data unavailable in this environment (PBP 403). "
              "Re-run locally with full nflverse access.")
        summary.append({
            "experiment": "EXP-4: Turnover-adj pd",
            "best_val_mae": float("nan"), "best_train_mae": float("nan"),
            "delta_val": float("nan"), "best_config": "SKIPPED — PBP unavailable",
        })
    else:
        to_results = []
        for w_pyth in np.arange(0.0, 1.05, 0.1):
            w_pd = round(1.0 - w_pyth, 10)
            w_pd = max(w_pd, 0.0)
            weights = {"z_pyth": round(w_pyth, 2), "z_pd": round(w_pd, 2)}

            def _fn(sd, as_, _w=weights):
                return features_turnover_adj_pd(sd, as_)

            t_mae, v_mae, _ = evaluate_config(schedules, team_stats, _fn, weights, CHAMPION_R)
            to_results.append({"w_pyth": round(w_pyth, 2), "w_pd_adj": round(w_pd, 2),
                               "train_mae": t_mae, "val_mae": v_mae})
            print(f"  w_pyth={w_pyth:.1f} w_pd_adj={w_pd:.1f} → train={t_mae:.4f}  val={v_mae:.4f}")

        to_df = pd.DataFrame(to_results).sort_values("val_mae").reset_index(drop=True)
        best_to = to_df.iloc[0]
        delta_to = best_to["val_mae"] - champ_val
        print(f"\n  Best: w_pyth={best_to['w_pyth']:.2f}  val={best_to['val_mae']:.4f}  "
              f"Δ vs champion: {delta_to:+.4f}")
        summary.append({
            "experiment": "EXP-4: Turnover-adj pd",
            "best_val_mae": best_to["val_mae"],
            "best_train_mae": best_to["train_mae"],
            "delta_val": delta_to,
            "best_config": f"w_pyth={best_to['w_pyth']:.2f}, w_pd_adj={best_to['w_pd_adj']:.2f}",
        })

    # ── Summary table ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY — All experiments vs. Champion (lower MAE = better)")
    print("=" * 70)
    print(f"{'Experiment':<42} {'Val MAE':>8} {'Δ Val':>8}  Best config")
    print("-" * 70)
    for r in summary:
        flag = " ✓" if r["delta_val"] < -0.005 else ("  " if r["delta_val"] == 0.0 else "  ")
        print(f"{r['experiment']:<42} {r['best_val_mae']:>8.4f} {r['delta_val']:>+8.4f}{flag}  {r['best_config']}")

    out = pd.DataFrame(summary)
    out.to_csv("warps_experiments_v2_2_results.csv", index=False)
    print(f"\n[INFO] Results saved to warps_experiments_v2_2_results.csv")
    print("\nInterpretation:")
    print("  Δ < -0.01: meaningful improvement worth investigating further")
    print("  Δ  0 ± 0.01: flat basin — no signal (expected given paper findings)")
    print("  Δ > +0.01: feature hurts — adds noise")


if __name__ == "__main__":
    main()
