#!/usr/bin/env python3
"""Do play-level ratings beat the closing line? Walk-forward test on nflverse play-by-play.

For every regular-season game from Week 4 on, ratings come only from plays in earlier
weeks of the same season (plus last season, down-weighted early on):

  off_pass / off_rush   offense EPA per dropback / per designed run
  def_pass / def_rush   EPA per play allowed
  qb                    the starting QB's EPA per dropback (his own plays, this season and
                        last, shrunk toward league average) minus the team's pass offense,
                        so a backup moves the number before the scores do
  pace                  offensive plays per game
  Garbage time is removed: only plays with win probability between 10% and 90%.

Sides: ridge regression of (home margin - closing expected margin) on home-minus-away
features; pick the side whose residual the model predicts. Totals: regression of (total
points - closing total) on summed features; pick over/under. Trained on seasons before
the test season (first test season 2012). Graded at the closing line (break-even 52.4%),
overall and for the most confident 25% / 10% of games.

Usage: pbp_edge_test.py PBP_DIR [--games games.csv]
PBP_DIR holds play_by_play_{season}.csv.gz files (nflverse releases).
Writes data/backtests/pbp_edge_test.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TLA = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
COLS = ["game_id", "season", "week", "season_type", "posteam", "defteam", "play_type", "epa", "wp",
        "passer_player_name", "qb_dropback"]
FIRST_TEST = 2012
SIDE_FEATS = ["off_pass", "off_rush", "def_pass", "def_rush", "qb"]
TOTAL_FEATS = ["off_pass", "off_rush", "def_pass", "def_rush", "pace"]


def t(x):
    return TLA.get(x, x)


def load_plays(pbp_dir, seasons):
    frames = []
    for s in seasons:
        f = Path(pbp_dir) / f"pbp_{s}.csv.gz"
        if not f.exists():
            f = Path(pbp_dir) / f"play_by_play_{s}.csv.gz"
        if not f.exists():
            continue
        d = pd.read_csv(f, usecols=COLS, low_memory=False)
        d = d[(d.season_type == "REG") & d.play_type.isin(["pass", "run"]) & d.epa.notna()]
        frames.append(d)
    p = pd.concat(frames, ignore_index=True)
    p["posteam"] = p.posteam.map(t)
    p["defteam"] = p.defteam.map(t)
    p["garbage"] = (p.wp < 0.1) | (p.wp > 0.9)
    p["is_pass"] = p.qb_dropback.fillna(0) == 1
    return p


def team_game_table(p):
    """Per team-game offense and defense numbers (garbage time excluded)."""
    q = p[~p.garbage]
    off = q.groupby(["season", "week", "posteam", "is_pass"]).epa.agg(["sum", "count"]).unstack("is_pass")
    off.columns = [f"off_{'pass' if b else 'rush'}_{a}" for a, b in off.columns]
    de = q.groupby(["season", "week", "defteam", "is_pass"]).epa.agg(["sum", "count"]).unstack("is_pass")
    de.columns = [f"def_{'pass' if b else 'rush'}_{a}" for a, b in de.columns]
    plays = p.groupby(["season", "week", "posteam"]).size().rename("plays")
    off.index.names = de.index.names = ["season", "week", "team"]
    plays.index.names = ["season", "week", "team"]
    return off.join(de, how="outer").join(plays, how="outer").fillna(0).reset_index()


def qb_table(p):
    q = p[~p.garbage & p.is_pass & p.passer_player_name.notna()]
    return q.groupby(["season", "week", "posteam", "passer_player_name"]).epa.agg(["sum", "count"]).reset_index()


def ratings_before(tg, qb, season, week):
    """Team ratings from earlier weeks this season, plus last season weighted by how early it is."""
    w_last = max(0.0, (6 - week) / 6) * 0.5
    cur = tg[(tg.season == season) & (tg.week < week)]
    last = tg[tg.season == season - 1]
    agg = {}
    for part, wt in ((cur, 1.0), (last, w_last)):
        if part.empty or wt == 0:
            continue
        g = part.groupby("team").sum(numeric_only=True)
        for team, row in g.iterrows():
            a = agg.setdefault(team, defaultdict_float())
            for c in row.index:
                if c not in ("season", "week"):
                    a[c] += row[c] * wt
            a["games"] += (part.team == team).sum() * wt
    out = {}
    for team, a in agg.items():
        def rate(k, prior=15):  # shrink to 0 (league average EPA ~ 0) with `prior` pseudo-plays
            return a[f"{k}_sum"] / (a[f"{k}_count"] + prior)
        out[team] = {"off_pass": rate("off_pass"), "off_rush": rate("off_rush"),
                     "def_pass": rate("def_pass"), "def_rush": rate("def_rush"),
                     "pace": a["plays"] / a["games"] if a["games"] else 62.0}
    qcur = qb[((qb.season == season) & (qb.week < week)) | (qb.season == season - 1)]
    qg = qcur.groupby("passer_player_name")[["sum", "count"]].sum()
    qbr = (qg["sum"] / (qg["count"] + 100)).to_dict()   # 100 pseudo-dropbacks of league average
    return out, qbr


class defaultdict_float(dict):
    def __missing__(self, k):
        return 0.0


def build(games, tg, qb):
    rows = []
    for (season, week), wk in games.groupby(["season", "week"]):
        if week < 4:
            continue
        r, qbr = ratings_before(tg, qb, season, week)
        for g in wk.itertuples():
            h, a = g.home, g.away
            if h not in r or a not in r:
                continue
            def qb_delta(team, name):
                if not isinstance(name, str):
                    return 0.0
                return qbr.get(name, -0.05) - r[team]["off_pass"]   # unknown QB: below average
            hq, aq = qb_delta(h, g.home_qb_name), qb_delta(a, g.away_qb_name)
            side = {k: r[h][k] - r[a][k] for k in ("off_pass", "off_rush", "def_pass", "def_rush")}
            side["qb"] = hq - aq
            tot = {k: r[h][k] + r[a][k] for k in ("off_pass", "off_rush", "def_pass", "def_rush", "pace")}
            rows.append({"season": season, "week": week, "game": f"{a}@{h}",
                         "margin_resid": g.margin - g.spread_line,
                         "total_resid": g.total - g.total_line,
                         **{f"s_{k}": v for k, v in side.items()}, **{f"t_{k}": v for k, v in tot.items()}})
    return pd.DataFrame(rows)


def ridge(X, y, lam=5.0):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    w = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return lambda Xn: y.mean() + ((Xn - mu) / sd) @ w


def grade(df, feats, target):
    preds, outs = [], []
    for s in sorted(df.season.unique()):
        if s < FIRST_TEST:
            continue
        tr, te = df[df.season < s], df[df.season == s]
        if tr.empty or te.empty:
            continue
        f = ridge(tr[feats].to_numpy(), tr[target].to_numpy())
        preds.append(pd.Series(f(te[feats].to_numpy()), index=te.index))
    pr = pd.concat(preds)
    d = df.loc[pr.index].assign(pred=pr)
    d = d[d[target] != 0]   # pushes
    d["win"] = np.sign(d.pred) == np.sign(d[target])
    res = {}
    for name, q in (("all", 0.0), ("top25", 0.75), ("top10", 0.90)):
        cut = d.pred.abs().quantile(q)
        sub = d[d.pred.abs() >= cut]
        res[name] = {"n": int(len(sub)), "win_pct": round(float(sub.win.mean()), 4)}
    by = d.groupby("season").win.mean()
    res["seasons_above_524"] = f"{int((by > 0.524).sum())}/{len(by)}"
    res["by_season"] = {int(k): round(float(v), 3) for k, v in by.items()}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbp_dir")
    ap.add_argument("--games")
    args = ap.parse_args()
    import season_forecast as sf
    raw = sf.load_games(args.games)
    g = pd.DataFrame(raw)
    g = g[g.home_score != ""].copy()
    for c in ("season", "week", "home_score", "away_score"):
        g[c] = g[c].astype(int)
    for c in ("spread_line", "total_line"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g.dropna(subset=["spread_line", "total_line"])
    g["home"], g["away"] = g.home_team.map(t), g.away_team.map(t)
    g["margin"] = g.home_score - g.away_score
    g["total"] = g.home_score + g.away_score
    seasons = sorted(s for s in g.season.unique() if s >= 2009)
    g = g[g.season.isin(seasons)]

    plays = load_plays(args.pbp_dir, seasons)
    tg = team_game_table(plays)
    qb = qb_table(plays)
    df = build(g, tg, qb)
    sides = grade(df, [f"s_{k}" for k in SIDE_FEATS], "margin_resid")
    sides_no_qb = grade(df, [f"s_{k}" for k in SIDE_FEATS if k != "qb"], "margin_resid")
    totals = grade(df, [f"t_{k}" for k in TOTAL_FEATS], "total_resid")
    out = {"games": int(len(df)), "test_seasons": f"{FIRST_TEST}-{max(seasons)}",
           "sides": sides, "sides_without_qb": sides_no_qb, "totals": totals}
    dest = ROOT / "data" / "backtests" / "pbp_edge_test.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    for k in ("sides", "sides_without_qb", "totals"):
        v = out[k]
        print(f"{k:17} all {v['all']['win_pct']:.3f} (n={v['all']['n']})  top25 {v['top25']['win_pct']:.3f}"
              f"  top10 {v['top10']['win_pct']:.3f} (n={v['top10']['n']})  seasons>52.4% {v['seasons_above_524']}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
