"""
WARPS-NFL Walk-Forward Validation — EXP-2 & EXP-3

Runs 16 expanding-window retrains (predicting each year 2010-2025) for:
  EXP-2: Offensive/defensive pf_pg / pa_pg split
  EXP-3: SOS-adjusted Pythagorean

For each window:
  - Optimize feature weights on training years
  - Test on single held-out year
  - Compare OOS MAE to fixed champion (w_pyth=0.75, w_pd=0.25, R=0.75)

EXP-4 (turnover-adjusted pd) is included as a separate section but requires
PBP access. Run locally with: python warps_walkforward_v2_2.py --exp4

Output:
  warps_wf_exp2_results.csv  — per-year EXP-2 OOS results
  warps_wf_exp3_results.csv  — per-year EXP-3 OOS results
  warps_wf_exp4_results.csv  — per-year EXP-4 OOS results (local only)

Run: python warps_walkforward_v2_2.py
"""

import argparse
import math
import warnings

import numpy as np
import pandas as pd

try:
    import nfl_data_py as nfl
    HAS_NFL = True
except ImportError:
    HAS_NFL = False

SCHEDULES_URL = "https://raw.githubusercontent.com/leesharpe/nfldata/master/data/games.csv"

PYTH_EXPONENT = 2.37
HOME_FIELD    = 1.5
SCALE_FACTOR  = 3.0
CHAMPION_R    = 0.75
CHAMPION_LOGIT = 5.5
CHAMPION_WEIGHTS_PYTH = {"z_pyth": 0.75, "z_pd": 0.25}

FIRST_PRED = 2010
LAST_PRED  = 2025
ALL_YEARS  = list(range(2000, 2026))

TURNOVER_POINT_VALUE = 4.5

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

def win_prob(spread, logit_scale=CHAMPION_LOGIT):
    return 1 / (1 + np.exp(-spread / logit_scale))

def mae(errors):
    return float(np.mean(np.abs(errors)))


# ── Data loading ───────────────────────────────────────────────────────────────

def load_schedules():
    print("[INFO] Loading schedules...")
    try:
        sched = pd.read_csv(SCHEDULES_URL)
    except Exception as e:
        raise SystemExit(f"Could not load schedules: {e}")
    sched["home_team"] = sched["home_team"].map(norm_team)
    sched["away_team"] = sched["away_team"].map(norm_team)
    return sched


def build_team_stats(schedules):
    game_type_col = "game_type" if "game_type" in schedules.columns else "season_type"
    reg = schedules[schedules[game_type_col].eq("REG")].dropna(subset=["home_score", "away_score"])
    rows = []
    for _, g in reg.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        hw = 0.5 if hs == as_ else (1.0 if hs > as_ else 0.0)
        rows += [[int(g["season"]), h, hw, hs, as_], [int(g["season"]), a, 1-hw, as_, hs]]
    df = pd.DataFrame(rows, columns=["season", "team", "wins", "pf", "pa"])
    df = df.groupby(["season", "team"], as_index=False).agg(
        wins=("wins","sum"), games=("wins","count"), pf=("pf","sum"), pa=("pa","sum")
    )
    df["pyth_wins"]     = df.apply(lambda r: pyth_win_pct(r["pf"], r["pa"]) * r["games"], axis=1)
    df["point_diff_pg"] = (df["pf"] - df["pa"]) / df["games"]
    df["pf_pg"]         = df["pf"] / df["games"]
    df["pa_pg"]         = df["pa"] / df["games"]
    return df


def load_pbp_turnovers():
    """PBP turnover margins — requires local nflverse access."""
    if not HAS_NFL:
        return None
    seasons = list(range(1999, 2026))
    print("[INFO] Loading PBP turnover data...")
    try:
        pbp = nfl.import_pbp_data(seasons, downcast=True)
        if "season_type" not in pbp.columns:
            print("[WARN] season_type missing in PBP")
            return None
        pbp = pbp[pbp["season_type"].eq("REG")].copy()
        for c in ["posteam", "defteam"]:
            pbp[c] = pbp[c].map(norm_team)
        pbp.dropna(subset=["posteam", "defteam"], inplace=True)
        tc = "turnover" if "turnover" in pbp.columns else "interception"
        off = pbp.groupby(["season","posteam"], as_index=False).agg(off_to=(tc,"mean")).rename(columns={"posteam":"team"})
        def_ = pbp.groupby(["season","defteam"], as_index=False).agg(def_to=(tc,"mean")).rename(columns={"defteam":"team"})
        to = off.merge(def_, on=["season","team"])
        to["turnover_margin"] = to["def_to"] - to["off_to"]
        print(f"[INFO] Turnover data: {len(to)} team-seasons")
        return to[["season","team","turnover_margin"]]
    except Exception as e:
        print(f"[WARN] PBP load failed: {e}")
        return None


# ── Feature builders ───────────────────────────────────────────────────────────

def featurize_champion(season_df, _all, _sched):
    df = season_df.copy()
    df["z_pyth"] = zscore(df["pyth_wins"])
    df["z_pd"]   = zscore(df["point_diff_pg"])
    return df

def featurize_exp2(season_df, _all, _sched):
    df = season_df.copy()
    df["z_off"] = zscore(df["pf_pg"])
    df["z_def"] = zscore(-df["pa_pg"])
    df["z_pd"]  = zscore(df["point_diff_pg"])
    return df

def featurize_exp3(season_df, _all, sched):
    df = season_df.copy()
    season = int(df["season"].iloc[0])
    game_type_col = "game_type" if "game_type" in sched.columns else "season_type"
    gsched = sched[(sched["season"].eq(season)) & (sched[game_type_col].eq("REG"))].copy()

    pf_map = dict(zip(df["team"], df["pf_pg"]))
    pa_map = dict(zip(df["team"], df["pa_pg"]))
    lg_pf = np.mean(list(pf_map.values()))
    lg_pa = np.mean(list(pa_map.values()))

    opp_pa_sum, opp_pf_sum, cnt = {}, {}, {}
    for _, g in gsched.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        for team, opp in [(h, a), (a, h)]:
            opp_pa_sum.setdefault(team, 0.0)
            opp_pf_sum.setdefault(team, 0.0)
            cnt.setdefault(team, 0)
            opp_pa_sum[team] += pa_map.get(opp, lg_pa)
            opp_pf_sum[team] += pf_map.get(opp, lg_pf)
            cnt[team] += 1

    df["opp_pa"] = df["team"].map(lambda t: opp_pa_sum.get(t, 0) / max(cnt.get(t, 1), 1))
    df["opp_pf"] = df["team"].map(lambda t: opp_pf_sum.get(t, 0) / max(cnt.get(t, 1), 1))
    df["adj_pf"] = df["pf_pg"] * (lg_pa / df["opp_pa"].clip(lower=1.0))
    df["adj_pa"] = df["pa_pg"] * (lg_pf / df["opp_pf"].clip(lower=1.0))
    df["pyth_adj"] = df.apply(lambda r: pyth_win_pct(r["adj_pf"], r["adj_pa"]) * r["games"], axis=1)
    df["z_pyth"] = zscore(df["pyth_adj"])
    df["z_pd"]   = zscore(df["point_diff_pg"])
    return df

def featurize_exp4(season_df, all_stats, _sched):
    df = season_df.copy()
    if "turnover_margin" not in df.columns or df["turnover_margin"].isna().all():
        return None
    df["adj_pd_pg"] = df["point_diff_pg"] - TURNOVER_POINT_VALUE * df["turnover_margin"]
    df["z_pyth"]    = zscore(df["pyth_wins"])
    df["z_pd"]      = zscore(df["adj_pd_pg"])
    return df


# ── Projection engine ──────────────────────────────────────────────────────────

def project_wins_map(schedules, rating_map, target_season):
    game_type_col = "game_type" if "game_type" in schedules.columns else "season_type"
    reg = schedules[(schedules["season"].eq(target_season)) & (schedules[game_type_col].eq("REG"))]
    rows = []
    for _, g in reg.iterrows():
        h, a = norm_team(g["home_team"]), norm_team(g["away_team"])
        spread = rating_map.get(h, 0.0) - rating_map.get(a, 0.0) + HOME_FIELD
        hwp = win_prob(spread)
        rows += [[h, hwp], [a, 1 - hwp]]
    if not rows:
        return {}
    d = pd.DataFrame(rows, columns=["team", "wp"])
    return d.groupby("team")["wp"].sum().to_dict()


def build_ratings(season_df, weights, regression_factor):
    total_w = sum(weights.values()) or 1.0
    z_sum = sum(season_df[col] * w for col, w in weights.items() if col in season_df.columns) / total_w
    raw = SCALE_FACTOR * z_sum
    return raw * regression_factor


def oos_mae_for_config(schedules, team_stats, featurize_fn, weights,
                       regression_factor, train_years, pred_year):
    """Compute OOS MAE for one config on one held-out year."""
    prior_year = pred_year - 1
    prior_df = team_stats[team_stats["season"].eq(prior_year)].copy()
    if prior_df.empty:
        return np.nan
    featured = featurize_fn(prior_df, team_stats, schedules)
    if featured is None:
        return np.nan
    featured["_rating"] = build_ratings(featured, weights, regression_factor)
    rating_map = dict(zip(featured["team"], featured["_rating"]))
    proj_map = project_wins_map(schedules, rating_map, pred_year)
    actual = team_stats[team_stats["season"].eq(pred_year)][["team","wins"]].copy()
    errors = []
    for _, row in actual.iterrows():
        if row["team"] in proj_map:
            errors.append(proj_map[row["team"]] - row["wins"])
    return mae(errors) if errors else np.nan


def train_mae_for_config(schedules, team_stats, featurize_fn, weights,
                         regression_factor, train_years):
    """Compute average MAE across all train years (predicting each year from prior year)."""
    maes = []
    for yr in train_years:
        m = oos_mae_for_config(schedules, team_stats, featurize_fn, weights,
                               regression_factor, train_years, yr)
        if not math.isnan(m):
            maes.append(m)
    return np.mean(maes) if maes else np.nan


# ── Walk-forward ───────────────────────────────────────────────────────────────

def run_walkforward(schedules, team_stats, exp_name, featurize_fn, weight_grid,
                    desc=""):
    """
    16-window expanding walk-forward.
    weight_grid: list of weight dicts to search over for each window.
    """
    print(f"\n{'='*70}")
    print(f"{exp_name}: Walk-forward 2010–2025")
    if desc:
        print(f"  {desc}")
    print(f"{'='*70}")

    results = []
    for pred_year in range(FIRST_PRED, LAST_PRED + 1):
        train_years = [y for y in ALL_YEARS if y < pred_year]

        # Find optimal weights on training data
        best_train_mae = np.inf
        best_weights   = weight_grid[0]
        for w in weight_grid:
            m = train_mae_for_config(schedules, team_stats, featurize_fn, w,
                                     CHAMPION_R, train_years)
            if m < best_train_mae:
                best_train_mae = m
                best_weights   = w

        # OOS: optimal config
        oos_opt = oos_mae_for_config(schedules, team_stats, featurize_fn,
                                     best_weights, CHAMPION_R, train_years, pred_year)

        # OOS: champion config
        oos_champ = oos_mae_for_config(schedules, team_stats, featurize_champion,
                                       CHAMPION_WEIGHTS_PYTH, CHAMPION_R,
                                       train_years, pred_year)

        delta = oos_champ - oos_opt  # positive = exp beats champion

        result = {
            "year":        pred_year,
            "train_n":     len(train_years) * 32,
            "oos_champ":   round(oos_champ, 4),
            "oos_opt":     round(oos_opt, 4),
            "delta":       round(delta, 4),
            "exp_wins":    int(delta > 0),
            **{f"w_{k}": round(v, 2) for k, v in best_weights.items()},
        }
        results.append(result)

        champ_flag = "✓ exp" if delta > 0 else "✗ champ"
        print(f"  {pred_year}: champ={oos_champ:.4f}  {exp_name}={oos_opt:.4f}  "
              f"Δ={delta:+.4f}  [{champ_flag}]  best={best_weights}")

    df = pd.DataFrame(results)
    wins = int(df["exp_wins"].sum())
    avg_delta = df["delta"].mean()
    avg_oos   = df["oos_opt"].mean()
    avg_champ = df["oos_champ"].mean()
    print(f"\n  Summary: {exp_name} beats champion in {wins}/16 windows")
    print(f"  Avg OOS MAE — champion: {avg_champ:.4f}  {exp_name}: {avg_oos:.4f}  "
          f"avg Δ: {avg_delta:+.4f}")
    return df


# ── Weight grids ───────────────────────────────────────────────────────────────

def make_exp2_grid(step=0.1):
    """Grid over w_off + w_def + w_pd = 1."""
    grid = []
    vals = np.round(np.arange(0.0, 1.0 + step, step), 6)
    for w_off in vals:
        for w_def in vals:
            w_pd = round(1.0 - w_off - w_def, 6)
            if w_pd < -1e-9:
                continue
            grid.append({"z_off": round(float(w_off), 2),
                          "z_def": round(float(w_def), 2),
                          "z_pd":  round(max(w_pd, 0.0), 2)})
    return grid

def make_exp3_grid(step=0.1):
    """Grid over w_pyth_adj + w_pd = 1."""
    grid = []
    for w in np.round(np.arange(0.0, 1.0 + step, step), 6):
        grid.append({"z_pyth": round(float(w), 2),
                     "z_pd":   round(1.0 - float(w), 2)})
    return grid

def make_exp4_grid(step=0.1):
    """Grid over w_pyth + w_pd_adj = 1."""
    grid = []
    for w in np.round(np.arange(0.0, 1.0 + step, step), 6):
        grid.append({"z_pyth": round(float(w), 2),
                     "z_pd":   round(1.0 - float(w), 2)})
    return grid


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp4", action="store_true",
                        help="Also run EXP-4 (requires local PBP access via nfl_data_py)")
    args = parser.parse_args()

    schedules  = load_schedules()
    team_stats = build_team_stats(schedules)

    # ── EXP-2 walk-forward ────────────────────────────────────────────────────
    exp2_grid = make_exp2_grid(step=0.1)
    df2 = run_walkforward(
        schedules, team_stats,
        exp_name="EXP-2",
        featurize_fn=featurize_exp2,
        weight_grid=exp2_grid,
        desc="Offensive pf_pg (z_off) + defensive pa_pg (z_def) + point diff (z_pd)",
    )
    df2.to_csv("warps_wf_exp2_results.csv", index=False)
    print("[INFO] Saved warps_wf_exp2_results.csv")

    # ── EXP-3 walk-forward ────────────────────────────────────────────────────
    exp3_grid = make_exp3_grid(step=0.1)
    df3 = run_walkforward(
        schedules, team_stats,
        exp_name="EXP-3",
        featurize_fn=featurize_exp3,
        weight_grid=exp3_grid,
        desc="SOS-adjusted Pythagorean (scores adjusted by opponent quality)",
    )
    df3.to_csv("warps_wf_exp3_results.csv", index=False)
    print("[INFO] Saved warps_wf_exp3_results.csv")

    # ── EXP-4 walk-forward (local only) ───────────────────────────────────────
    if args.exp4:
        print(f"\n{'='*70}")
        print("EXP-4: Loading PBP turnover data...")
        print(f"{'='*70}")
        to_margins = load_pbp_turnovers()
        if to_margins is not None:
            team_stats_4 = team_stats.merge(to_margins, on=["season","team"], how="left")
            exp4_grid = make_exp4_grid(step=0.1)
            df4 = run_walkforward(
                schedules, team_stats_4,
                exp_name="EXP-4",
                featurize_fn=featurize_exp4,
                weight_grid=exp4_grid,
                desc=f"Turnover-adjusted pd (strip {TURNOVER_POINT_VALUE}pts/turnover from point diff)",
            )
            df4.to_csv("warps_wf_exp4_results.csv", index=False)
            print("[INFO] Saved warps_wf_exp4_results.csv")
        else:
            print("[SKIP] EXP-4 requires PBP data — not available in this environment.")
    else:
        print("\n[NOTE] EXP-4 skipped. Run locally with: python warps_walkforward_v2_2.py --exp4")

    # ── Combined summary ──────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    for exp_name, df, col_label in [("EXP-2 (off/def split)", df2, "oos_opt"),
                                     ("EXP-3 (SOS-adj pyth)",  df3, "oos_opt")]:
        wins  = int(df["exp_wins"].sum())
        avg_d = df["delta"].mean()
        avg_m = df[col_label].mean()
        champ = df["oos_champ"].mean()
        print(f"  {exp_name}: {wins}/16 windows, avg OOS={avg_m:.4f} vs champ={champ:.4f}, avg Δ={avg_d:+.4f}")


if __name__ == "__main__":
    main()
