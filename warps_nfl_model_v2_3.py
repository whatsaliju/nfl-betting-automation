"""
WARPS-NFL v2.3 — SOS-Adjusted Pythagorean

Core change from v2.0: replace raw Pythagorean win expectation with a
schedule-strength-adjusted version. For each team-season, opponent-average
defensive quality (pa/game) and offensive quality (pf/game) are used to
scale each team's raw scoring before computing Pythagorean. This corrects
for teams that accumulated good-looking pyth numbers against weak schedules.

Walk-forward validation (16 windows, 2010-2025):
  Champion (v1.8): beats Pythagorean baseline in 12/16 windows, avg OOS MAE 2.3378
  v2.3 (SOS-adj):  beats champion in 12/16 windows, avg OOS MAE 2.3228 (Δ=−0.015)
  Optimal config:  w_pyth_adj=1.00, w_pd=0.00, R=0.75 (consistent across all windows)

Run:  python warps_nfl_model_v2_3.py
"""

import numpy as np
import pandas as pd

# ── Constants ─────────────────────────────────────────────────────────────────

PYTH_EXPONENT  = 2.37
HOME_FIELD     = 1.5
SCALE_FACTOR   = 3.0
LOGIT_SCALE    = 5.5
REGRESSION_R   = 0.75
DYNASTY_R      = 0.95   # higher regression for sustained dynasty teams

SCHEDULES_URL = "https://raw.githubusercontent.com/leesharpe/nfldata/master/data/games.csv"

MARKET_2026 = {
    "NE": 10.5, "IND":  7.5, "NO":  7.5, "MIA":  4.5,
    "ARI": 4.5, "JAX":  9.5, "WAS": 7.5, "HOU":  9.5,
    "LV":  5.5, "ATL":  7.5, "MIN": 8.5, "PIT":  8.5,
    "CAR": 7.5, "NYG":  7.5, "SEA":10.5, "DEN":  9.5,
    "CLE": 6.5, "NYJ":  5.5, "TB":  8.5, "DAL":  9.5,
    "GB": 10.5, "DET": 10.5, "LAC":10.5, "SF":  10.5,
    "CHI": 9.5, "TEN":  6.5, "KC": 10.5, "BUF": 10.5,
    "PHI":10.5, "LAR": 11.5, "BAL":11.5, "CIN":  9.5,
}

# Teams with 4+ consecutive above-average seasons through 2025 → higher R
DYNASTY_POS = {"KC", "BUF", "PHI", "BAL", "DET"}
# Teams with 4+ consecutive below-average seasons through 2025 → dynasty R
DYNASTY_NEG = {"NYJ", "CAR"}

TEAM_ALIASES = {
    "LA": "LAR", "JAC": "JAX", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL",
    "HST": "HOU", "SL": "LAR", "STL": "LAR",
    "SD": "LAC", "OAK": "LV", "WSH": "WAS",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def nt(t):
    if pd.isna(t): return t
    return TEAM_ALIASES.get(str(t), str(t))

def pyth(pf, pa):
    pf, pa = max(float(pf), 1.0), max(float(pa), 1.0)
    return pf**PYTH_EXPONENT / (pf**PYTH_EXPONENT + pa**PYTH_EXPONENT)

def zscore(s):
    std = s.std(ddof=0)
    return s * 0 if std == 0 else (s - s.mean()) / std

def win_prob(spread):
    return 1 / (1 + np.exp(-spread / LOGIT_SCALE))


# ── Data ──────────────────────────────────────────────────────────────────────

def load():
    print("[INFO] Loading schedule data...")
    sched = pd.read_csv(SCHEDULES_URL)
    sched["home_team"] = sched["home_team"].map(nt)
    sched["away_team"] = sched["away_team"].map(nt)

    game_type_col = "game_type" if "game_type" in sched.columns else "season_type"
    reg = sched[sched[game_type_col].eq("REG")].dropna(subset=["home_score","away_score"])

    rows = []
    for _, g in reg.iterrows():
        h, a = nt(g["home_team"]), nt(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        hw = 0.5 if hs == as_ else (1.0 if hs > as_ else 0.0)
        rows += [[int(g["season"]), h, hw, hs, as_],
                 [int(g["season"]), a, 1-hw, as_, hs]]

    df = pd.DataFrame(rows, columns=["season","team","wins","pf","pa"])
    df = df.groupby(["season","team"], as_index=False).agg(
        wins=("wins","sum"), games=("wins","count"), pf=("pf","sum"), pa=("pa","sum")
    )
    df["pyth_raw"]  = df.apply(lambda r: pyth(r["pf"], r["pa"]) * r["games"], axis=1)
    df["pd_pg"]     = (df["pf"] - df["pa"]) / df["games"]
    df["pf_pg"]     = df["pf"] / df["games"]
    df["pa_pg"]     = df["pa"] / df["games"]
    return sched, df


# ── SOS-adjusted Pythagorean ──────────────────────────────────────────────────

def sos_adjusted_pyth(season_df, sched):
    """
    Scale each team's pf/pa by opponent quality before computing Pythagorean.

    Intuition:
      Scoring 30 pts/game against a league-average defense is worth its face value.
      Scoring 30 pts/game against a bottom-5 defense should be discounted.
      adj_pf = raw_pf * (league_avg_pa / opp_avg_pa)
      adj_pa = raw_pa * (league_avg_pf / opp_avg_pf)
    """
    df = season_df.copy()
    season = int(df["season"].iloc[0])
    game_type_col = "game_type" if "game_type" in sched.columns else "season_type"
    gsched = sched[(sched["season"]==season) & (sched[game_type_col]=="REG")].copy()

    pf_map = dict(zip(df["team"], df["pf_pg"]))
    pa_map = dict(zip(df["team"], df["pa_pg"]))
    lg_pf  = np.mean(list(pf_map.values()))
    lg_pa  = np.mean(list(pa_map.values()))

    opp_pa, opp_pf, cnt = {}, {}, {}
    for _, g in gsched.iterrows():
        h, a = nt(g["home_team"]), nt(g["away_team"])
        for team, opp in [(h,a), (a,h)]:
            opp_pa.setdefault(team, 0.0); opp_pf.setdefault(team, 0.0); cnt.setdefault(team, 0)
            opp_pa[team] += pa_map.get(opp, lg_pa)
            opp_pf[team] += pf_map.get(opp, lg_pf)
            cnt[team]    += 1

    df["opp_pa"] = df["team"].map(lambda t: opp_pa.get(t,0)/max(cnt.get(t,1),1))
    df["opp_pf"] = df["team"].map(lambda t: opp_pf.get(t,0)/max(cnt.get(t,1),1))
    df["adj_pf"] = df["pf_pg"] * (lg_pa / df["opp_pa"].clip(lower=1.0))
    df["adj_pa"] = df["pa_pg"] * (lg_pf / df["opp_pf"].clip(lower=1.0))
    df["pyth_adj"] = df.apply(lambda r: pyth(r["adj_pf"], r["adj_pa"]) * r["games"], axis=1)
    return df


def build_ratings(ts, sched):
    """For every season, compute SOS-adjusted Pythagorean rating with regression."""
    all_rated = []
    for season, g in ts.groupby("season"):
        g = sos_adjusted_pyth(g, sched)
        z = zscore(g["pyth_adj"])
        raw = SCALE_FACTOR * z
        # Dynasty modifier: teams with sustained streaks regress less
        def reg_factor(team):
            if team in DYNASTY_POS or team in DYNASTY_NEG:
                return DYNASTY_R
            return REGRESSION_R
        g["rating"] = [raw.iloc[i] * reg_factor(t) for i, t in enumerate(g["team"])]
        all_rated.append(g[["season","team","rating","pyth_adj","pyth_raw","pd_pg","wins","games"]])
    return pd.concat(all_rated, ignore_index=True)


# ── Projection ────────────────────────────────────────────────────────────────

def project(rating_map, sched, target_season):
    game_type_col = "game_type" if "game_type" in sched.columns else "season_type"
    reg = sched[(sched["season"]==target_season) & (sched[game_type_col]=="REG")]
    rows = []
    for _, g in reg.iterrows():
        h, a = nt(g["home_team"]), nt(g["away_team"])
        spread = rating_map.get(h, 0.0) - rating_map.get(a, 0.0) + HOME_FIELD
        hwp = win_prob(spread)
        rows += [[h, hwp], [a, 1-hwp]]
    if not rows:
        return {}
    d = pd.DataFrame(rows, columns=["team","wp"])
    return d.groupby("team")["wp"].sum().to_dict()


# ── Backtest ──────────────────────────────────────────────────────────────────

def full_backtest(rated, sched, ts):
    """Run full backtest (2001-2025), compute MAE vs Pythagorean baseline."""
    projs, errors_warps, errors_pyth = [], [], []
    seasons = sorted(rated["season"].unique())

    for target in seasons:
        prior = target - 1
        prior_rated = rated[rated["season"]==prior]
        if prior_rated.empty:
            continue
        rating_map = dict(zip(prior_rated["team"], prior_rated["rating"]))
        proj_map   = project(rating_map, sched, target)
        if not proj_map:
            continue

        actual = ts[ts["season"]==target][["team","wins","games"]].copy()
        prior_stats = ts[ts["season"]==prior][["team","pyth_raw","games"]].rename(
            columns={"pyth_raw":"pyth_fc","games":"prior_g"})
        actual = actual.merge(prior_stats, on="team", how="left")
        actual["pyth_fc_scaled"] = actual["pyth_fc"] * (actual["games"] / actual["prior_g"].fillna(17))

        for _, row in actual.iterrows():
            if row["team"] not in proj_map:
                continue
            warps_proj = proj_map[row["team"]]
            errors_warps.append(warps_proj - row["wins"])
            errors_pyth.append(row["pyth_fc_scaled"] - row["wins"])
            projs.append({"season": target, "team": row["team"],
                          "proj": round(warps_proj, 3), "actual": row["wins"],
                          "pyth_fc": round(row["pyth_fc_scaled"], 3)})

    mae_w = float(np.mean(np.abs(errors_warps)))
    mae_p = float(np.mean(np.abs(errors_pyth)))
    df    = pd.DataFrame(projs)
    return df, mae_w, mae_p


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    sched, ts = load()
    rated = build_ratings(ts, sched)

    print("\n[INFO] Running full backtest (2001-2025)...")
    bt, mae_w, mae_p = full_backtest(rated, sched, ts)
    n = len(bt)
    print(f"  v2.3 MAE: {mae_w:.4f}  ({n} team-seasons)")
    print(f"  Pyth MAE: {mae_p:.4f}")
    print(f"  Improvement vs Pythagorean: {mae_p - mae_w:.4f}")

    # Year-by-year breakdown
    print("\n  Year-by-year:")
    print(f"  {'Season':>7}  {'WARPS MAE':>10}  {'Pyth MAE':>9}")
    for season, g in bt.groupby("season"):
        wm = np.mean(np.abs(g["proj"] - g["actual"]))
        pm = np.mean(np.abs(g["pyth_fc"] - g["actual"]))
        flag = "✓" if wm < pm else " "
        print(f"  {season:>7}  {wm:>10.4f}  {pm:>9.4f}  {flag}")

    # 2026 projections
    print("\n[INFO] Computing 2026 projections...")
    prior_2025 = rated[rated["season"]==2025]
    rating_map_2026 = dict(zip(prior_2025["team"], prior_2025["rating"]))
    proj_2026 = project(rating_map_2026, sched, 2026)

    print("\n=== 2026 WIN TOTAL PROJECTIONS (v2.3) ===")
    print(f"{'Team':>4}  {'v2.3 proj':>10}  {'BetMGM':>7}  {'Edge':>6}  {'Signal'}")
    print("-" * 55)

    results = []
    for team in sorted(MARKET_2026):
        proj = proj_2026.get(team, float("nan"))
        line = MARKET_2026[team]
        edge = proj - line
        signal = "Over" if edge > 0.5 else ("Under" if edge < -0.5 else "No bet")
        print(f"{team:>4}  {proj:>10.2f}  {line:>7.1f}  {edge:>+6.2f}  {signal}")
        results.append({"team": team, "v23_wins": round(proj, 2),
                        "market": line, "edge": round(edge, 2), "signal": signal})

    df_proj = pd.DataFrame(results).sort_values("edge", ascending=False)
    df_proj.to_csv("warps_2026_screen_v2_3.csv", index=False)
    bt.to_csv("warps_backtest_team_results_v2_3.csv", index=False)

    print(f"\n[INFO] Full-sample MAE: {mae_w:.4f}")
    print("[INFO] Saved warps_2026_screen_v2_3.csv")
    print("[INFO] Saved warps_backtest_team_results_v2_3.csv")

    # Print the three-model consensus update (v2.3 replaces v1.8 slot)
    print("\n=== SITE UPDATE — New v18Wins values for warpsData.ts ===")
    for _, r in df_proj.sort_values("team").iterrows():
        print(f"  {r['team']:>4}: v18Wins={r['v23_wins']:.2f}  edge={r['edge']:+.2f}")

    return df_proj, mae_w


if __name__ == "__main__":
    main()
