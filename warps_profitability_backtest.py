#!/usr/bin/env python3
"""
warps_profitability_backtest.py
───────────────────────────────
Simulates betting WARPS model edges against historical Vegas preseason win totals.

Data sources
  - WARPS backtest predictions: warps_backtest_team_results_v1_*.csv
  - Vegas lines: nflverse/nfldata preseason win totals (2003-2020)

Output
  - Console summary tables
  - warps_profitability_summary.csv  — P&L by model/threshold
  - warps_profitability_by_year.csv  — year-by-year P&L for v1.8 / 3-model
"""

import urllib.request
from io import StringIO
import pandas as pd
import numpy as np

# ── 1. Load Vegas win totals ─────────────────────────────────────────────────────
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/win_totals.csv"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    win_totals = pd.read_csv(StringIO(r.read().decode()))

ALIASES = {
    "OAK": "LV", "STL": "LAR", "SD": "LAC", "ARZ": "ARI",
    "BLT": "BAL", "CLV": "CLE", "HST": "HOU", "SL": "LAR",
}
win_totals["team"] = win_totals["team"].replace(ALIASES)
print(f"Vegas win totals: {len(win_totals)} rows, seasons {win_totals['season'].min()}–{win_totals['season'].max()}")

# ── 2. Load WARPS backtest files ─────────────────────────────────────────────────
def load_backtest(version):
    path = f"warps_backtest_team_results_v{version}.csv"
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df["team"] = df["team"].replace(ALIASES)
    # Rename wins → actual_wins; handle both column naming conventions
    if "wins" in df.columns:
        df = df.rename(columns={"wins": "actual_wins"})
    # Normalise pyth_fc column name
    if "pyth_forecast_prior" in df.columns:
        df = df.rename(columns={"pyth_forecast_prior": "pyth_fc"})
    if "prior_wins_forecast" in df.columns:
        df = df.rename(columns={"prior_wins_forecast": "pw_fc"})
    return df

v18  = load_backtest("1_8") [["season", "team", "warps_wins", "actual_wins", "pyth_fc", "pw_fc"]]
v15d = load_backtest("1_5d")[["season", "team", "warps_wins"]].rename(columns={"warps_wins": "w_v15d"})
v16  = load_backtest("1_6") [["season", "team", "warps_wins"]].rename(columns={"warps_wins": "w_v16"})

print(f"v1.8 backtest: {len(v18)} rows ({v18['season'].min()}–{v18['season'].max()})")
print(f"v1.5d backtest: {len(v15d)} rows")
print(f"v1.6  backtest: {len(v16)} rows")

# ── 3. Merge ─────────────────────────────────────────────────────────────────────
df = (v18
      .merge(win_totals[["season", "team", "line", "over_odds", "under_odds"]],
             on=["season", "team"], how="inner")
      .merge(v15d, on=["season", "team"], how="left")
      .merge(v16,  on=["season", "team"], how="left")
)
print(f"\nMerged: {len(df)} team-seasons ({df['season'].min()}–{df['season'].max()})")
print(f"Seasons: {sorted(df['season'].unique())}")

# ── 4. Compute edges ──────────────────────────────────────────────────────────────
df["edge_v18"]   = df["warps_wins"] - df["line"]
df["edge_pyth"]  = df["pyth_fc"]    - df["line"]
df["edge_pw"]    = df["pw_fc"]      - df["line"]
df["edge_v15d"]  = df["w_v15d"]     - df["line"]
df["edge_v16"]   = df["w_v16"]      - df["line"]

# 3-model consensus: all 3 agree on direction and min avg |edge|
has_all = df[["w_v15d", "w_v16"]].notna().all(axis=1)
same_dir = (
    (np.sign(df["edge_v18"]) == np.sign(df["edge_v15d"])) &
    (np.sign(df["edge_v18"]) == np.sign(df["edge_v16"]))
)
df["consensus_dir"] = np.where(has_all & same_dir, np.sign(df["edge_v18"]), 0)
df["avg_edge_3m"]   = np.where(
    has_all,
    (df["edge_v18"] + df["edge_v15d"].fillna(0) + df["edge_v16"].fillna(0)) / 3,
    np.nan
)

# ── 5. P&L simulation ─────────────────────────────────────────────────────────────
def american_to_profit(odds):
    """Convert American odds to profit per $1 wagered."""
    if pd.isna(odds):
        return 100 / 110  # default -110
    odds = float(odds)
    if odds < 0:
        return 100 / abs(odds)
    return odds / 100

def simulate(subset, edge_col, min_edge, direction_col=None):
    """
    Bet whenever abs(edge) >= min_edge.
    direction_col: if provided, only bet when that column != 0 (used for consensus).
    """
    mask = np.abs(subset[edge_col]) >= min_edge
    if direction_col:
        mask = mask & (subset[direction_col] != 0)
    bets = subset[mask].copy()
    if len(bets) == 0:
        return {"n": 0, "n_win": 0, "n_push": 0, "n_lose": 0,
                "win_pct": 0.0, "units": 0.0, "roi_pct": 0.0}

    bets["bet_dir"]    = np.sign(bets[edge_col])
    bets["actual_dir"] = np.sign(bets["actual_wins"] - bets["line"])
    bets["push"]       = bets["actual_dir"] == 0
    bets["win"]        = (bets["bet_dir"] == bets["actual_dir"]) & ~bets["push"]
    bets["lose"]       = (bets["bet_dir"] != bets["actual_dir"]) & ~bets["push"]

    def row_payout(row):
        if row["bet_dir"] > 0:
            return american_to_profit(row["over_odds"])
        return american_to_profit(row["under_odds"])

    bets["payout"] = bets.apply(row_payout, axis=1)
    bets["pnl"]    = np.where(bets["win"], bets["payout"],
                     np.where(bets["push"], 0.0, -1.0))

    n      = len(bets)
    n_win  = int(bets["win"].sum())
    n_push = int(bets["push"].sum())
    n_lose = int(bets["lose"].sum())
    denom  = n - n_push
    units  = round(bets["pnl"].sum(), 3)
    roi    = round(units / denom * 100, 2) if denom > 0 else 0.0
    win_p  = round(n_win / denom * 100, 1) if denom > 0 else 0.0
    return {"n": n, "n_win": n_win, "n_push": n_push, "n_lose": n_lose,
            "win_pct": win_p, "units": units, "roi_pct": roi}

# ── 6. Results tables ─────────────────────────────────────────────────────────────
thresholds = [0.5, 1.0, 1.5, 2.0, 2.5]

print("\n" + "=" * 78)
print("WARPS PROFITABILITY BACKTEST — 2003-2020 (18 seasons, Vegas preseason win totals)")
print("=" * 78)

models = [
    ("WARPS v1.8",              "edge_v18",   df,                   None),
    ("Pythagorean (baseline)",  "edge_pyth",  df,                   None),
    ("Prior-year wins (baseline)","edge_pw",  df,                   None),
    ("3-model consensus",       "avg_edge_3m",df[df["consensus_dir"] != 0], "consensus_dir"),
]

summary_rows = []
for model_name, ecol, mdf, dcol in models:
    print(f"\n{model_name}:")
    print(f"  {'Thresh':>7} {'N':>5} {'W-P-L':>12} {'Win%':>7} {'Units':>8} {'ROI%':>7}")
    for t in thresholds:
        r = simulate(mdf, ecol, t, dcol)
        wpl = f"{r['n_win']}-{r['n_push']}-{r['n_lose']}"
        print(f"  {t:>7.1f} {r['n']:>5} {wpl:>12} {r['win_pct']:>6.1f}% {r['units']:>+8.3f} {r['roi_pct']:>+6.1f}%")
        summary_rows.append({"model": model_name, "threshold": t, **r})

# ── 7. Over vs Under split for v1.8 at 1.0 ───────────────────────────────────────
print("\n\nWARPS v1.8 breakdown at edge ≥ 1.0 win:")
print(f"  {'Direction':>10} {'N':>5} {'W-P-L':>10} {'Win%':>7} {'Units':>8} {'ROI%':>7}")
for label, subset in [("Overs", df[df["edge_v18"] >= 1.0]),
                      ("Unders", df[df["edge_v18"] <= -1.0])]:
    r = simulate(subset, "edge_v18", 1.0)
    wpl = f"{r['n_win']}-{r['n_push']}-{r['n_lose']}"
    print(f"  {label:>10} {r['n']:>5} {wpl:>10} {r['win_pct']:>6.1f}% {r['units']:>+8.3f} {r['roi_pct']:>+6.1f}%")

# ── 8. Year-by-year P&L for v1.8 and 3-model (edge ≥ 1.0) ───────────────────────
print("\n\nWARPS v1.8 year-by-year (edge ≥ 1.0 win):")
print(f"  {'Season':>8} {'N':>5} {'W-L':>8} {'Win%':>7} {'Units':>8}")
yearly_rows = []
for season in sorted(df["season"].unique()):
    r = simulate(df[df["season"] == season], "edge_v18", 1.0)
    if r["n"] > 0:
        wl = f"{r['n_win']}-{r['n_lose']}"
        print(f"  {season:>8} {r['n']:>5} {wl:>8} {r['win_pct']:>6.1f}% {r['units']:>+8.3f}")
        yearly_rows.append({"season": season, "model": "WARPS v1.8", **r})

print("\n3-model consensus year-by-year (avg edge ≥ 1.0 win, direction must agree):")
consensus_df = df[df["consensus_dir"] != 0]
for season in sorted(consensus_df["season"].unique()):
    r = simulate(consensus_df[consensus_df["season"] == season], "avg_edge_3m", 1.0, "consensus_dir")
    if r["n"] > 0:
        wl = f"{r['n_win']}-{r['n_lose']}"
        print(f"  {season:>8} {r['n']:>5} {wl:>8} {r['win_pct']:>6.1f}% {r['units']:>+8.3f}")
        yearly_rows.append({"season": season, "model": "3-model consensus", **r})

# ── 9. Cumulative P&L ────────────────────────────────────────────────────────────
print("\n\nCumulative P&L — WARPS v1.8 (edge ≥ 1.0 win):")
bets = df[np.abs(df["edge_v18"]) >= 1.0].copy()
bets["bet_dir"]    = np.sign(bets["edge_v18"])
bets["actual_dir"] = np.sign(bets["actual_wins"] - bets["line"])
bets["push"]       = bets["actual_dir"] == 0

def row_payout(row):
    if row["bet_dir"] > 0:
        return american_to_profit(row["over_odds"])
    return american_to_profit(row["under_odds"])

bets["payout"] = bets.apply(row_payout, axis=1)
bets["pnl"]    = np.where(bets["bet_dir"] == bets["actual_dir"], bets["payout"],
                 np.where(bets["push"], 0.0, -1.0))
bets_sorted = bets.sort_values("season")
bets_sorted["cumulative_units"] = bets_sorted["pnl"].cumsum()
for _, row in bets_sorted.groupby("season")[["pnl", "cumulative_units"]].last().iterrows():
    pass  # just for reference
cumulative_by_season = bets_sorted.groupby("season").agg(
    n=("pnl", "count"),
    units=("pnl", "sum"),
    cum_units=("cumulative_units", "last")
).reset_index()
print(f"  {'Season':>8} {'N':>5} {'Season units':>14} {'Cumulative':>12}")
for _, row in cumulative_by_season.iterrows():
    print(f"  {int(row['season']):>8} {int(row['n']):>5} {row['units']:>+14.3f} {row['cum_units']:>+12.3f}")

# ── 10. Key metrics summary ───────────────────────────────────────────────────────
r_total = simulate(df, "edge_v18", 1.0)
r_high  = simulate(df, "edge_v18", 2.0)
r_cons  = simulate(df[df["consensus_dir"] != 0], "avg_edge_3m", 1.0, "consensus_dir")

print("\n\n" + "=" * 78)
print("SUMMARY: KEY METRICS FOR PAPER")
print("=" * 78)
print(f"Dataset: {len(df)} team-seasons, 2003–2020 (18 seasons), actual opening odds")
print(f"\nWARPS v1.8 (edge ≥ 1.0 win):    {r_total['n']:3d} bets, "
      f"{r_total['win_pct']:.1f}% win, {r_total['units']:+.2f} units, {r_total['roi_pct']:+.1f}% ROI")
print(f"WARPS v1.8 (edge ≥ 2.0 wins):   {r_high['n']:3d} bets, "
      f"{r_high['win_pct']:.1f}% win, {r_high['units']:+.2f} units, {r_high['roi_pct']:+.1f}% ROI")
print(f"3-model consensus (avg ≥ 1.0):  {r_cons['n']:3d} bets, "
      f"{r_cons['win_pct']:.1f}% win, {r_cons['units']:+.2f} units, {r_cons['roi_pct']:+.1f}% ROI")
r_pyth = simulate(df, "edge_pyth", 1.0)
print(f"Pythagorean baseline (≥ 1.0):   {r_pyth['n']:3d} bets, "
      f"{r_pyth['win_pct']:.1f}% win, {r_pyth['units']:+.2f} units, {r_pyth['roi_pct']:+.1f}% ROI")
breakeven = 100 / 110 / (1 + 100/110) * 100
print(f"\nBreak-even win rate at -110 juice: {breakeven:.1f}%")

# ── 11. Save outputs ──────────────────────────────────────────────────────────────
pd.DataFrame(summary_rows).to_csv("warps_profitability_summary.csv", index=False)
pd.DataFrame(yearly_rows).to_csv("warps_profitability_by_year.csv", index=False)
print("\n\nOutputs saved: warps_profitability_summary.csv, warps_profitability_by_year.csv")
