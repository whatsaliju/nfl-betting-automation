#!/usr/bin/env python3
"""Rest-of-season forecast: learned team strength -> simulated standings, playoffs and futures.

Three views of each team's strength at the cutoff week, all in points per game:
  prior    WARPS preseason projected wins, centred (wins - 8.5; the stacker learns the scale)
  margin   ridge (MAP) rating from this season's scoring margins:
           margin = hfa + r_home - r_away, ratings pulled toward 0 by lambda
  market   ridge rating from this season's closing spreads (what the books think now)

A logistic model on the three rating differences (+ home field) is trained on every
game after the cutoff week in seasons 2003..S-1, using only information available at
the cutoff, and its ridge strength is chosen by leave-one-season-out log loss. Baselines
(prior only, market only, the old K=8 Pythagorean blend) are scored the same way.

The 2026 rest of season is then simulated N times (division winners, seeds, a 7-team
playoff per conference, Super Bowl, best regular-season record).

Usage: season_forecast.py [--games games.csv] [--week 8] [--season 2026] [--sims 20000]
Writes data/backtests/season_forecast_{season}.json
"""

import argparse
import csv
import io
import json
import math
import random
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
WARPS_HISTORY = ROOT / "warps_backtest_team_results_v2_3.csv"
WARPS_2026 = ROOT / "warps_2026_game_priors.csv"
ADJUST = ROOT / "data" / "historical" / "warps_{season}_inseason_adjustments.csv"
TLA = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
DIVS = {"AFC East": "BUF MIA NE NYJ", "AFC North": "BAL CIN CLE PIT", "AFC South": "HOU IND JAX TEN",
        "AFC West": "DEN KC LV LAC", "NFC East": "DAL NYG PHI WAS", "NFC North": "CHI DET GB MIN",
        "NFC South": "ATL CAR NO TB", "NFC West": "ARI LAR SF SEA"}
DIV = {t: d for d, s in DIVS.items() for t in s.split()}
TEAMS = sorted(DIV)
IDX = {t: i for i, t in enumerate(TEAMS)}


def tla(x):
    return TLA.get(x, x)


def load_games(path):
    text = Path(path).read_text() if path else urllib.request.urlopen(GAMES_URL, timeout=60).read().decode()
    return [g for g in csv.DictReader(io.StringIO(text)) if g["game_type"] == "REG"]


def load_priors():
    pri = {}
    for r in csv.DictReader(open(WARPS_HISTORY)):
        pri[(int(r["season"]), tla(r["team"]))] = float(r["proj"])
    if WARPS_2026.exists():
        for r in csv.DictReader(open(WARPS_2026)):
            pri.setdefault((int(r["season"]), r["away_tla"]), float(r["away_warps_wins"]))
            pri.setdefault((int(r["season"]), r["home_tla"]), float(r["home_warps_wins"]))
    return pri


def ridge_ratings(rows, target, lam):
    """MAP ratings: target = hfa*home + r_home - r_away, Gaussian prior on r (strength lam)."""
    if not rows:
        return np.zeros(len(TEAMS)), 0.0
    X = np.zeros((len(rows), len(TEAMS) + 1))
    y = np.zeros(len(rows))
    for i, g in enumerate(rows):
        X[i, IDX[g["h"]]] += 1
        X[i, IDX[g["a"]]] -= 1
        X[i, -1] = 0 if g["neutral"] else 1
        y[i] = target(g)
    P = lam * np.eye(X.shape[1])
    P[-1, -1] = 1e-6
    beta = np.linalg.solve(X.T @ X + P, X.T @ y)
    return beta[:-1], beta[-1]


def season_rows(games, season):
    out = []
    for g in games:
        if int(g["season"]) != season:
            continue
        h, a = tla(g["home_team"]), tla(g["away_team"])
        if h not in IDX or a not in IDX:
            continue
        out.append({"week": int(g["week"]), "h": h, "a": a, "neutral": g["location"] == "Neutral",
                    "hs": int(g["home_score"]) if g["home_score"] else None,
                    "as": int(g["away_score"]) if g["away_score"] else None,
                    "spread": float(g["spread_line"]) if g["spread_line"] else None})
    return out


def views(rows, season, cutoff, priors, lam_margin, lam_market, adjust=None):
    """Team strength (points) per view, using games through the cutoff week only."""
    played = [g for g in rows if g["week"] <= cutoff and g["hs"] is not None]
    margin, _ = ridge_ratings(played, lambda g: g["hs"] - g["as"], lam_margin)
    priced = [g for g in rows if g["week"] <= cutoff and g["spread"] is not None]
    market, _ = ridge_ratings(priced, lambda g: g["spread"], lam_market)
    prior = np.array([priors.get((season, t), 8.5) - 8.5 for t in TEAMS])
    if adjust:
        for t, d in adjust.items():
            prior[IDX[t]] += d
    rec = defaultdict(lambda: [0.0, 0, 0, 0])  # wins, games, pf, pa
    for g in played:
        for t, pf, pa in ((g["h"], g["hs"], g["as"]), (g["a"], g["as"], g["hs"])):
            r = rec[t]
            r[0] += 1 if pf > pa else 0.5 if pf == pa else 0
            r[1] += 1; r[2] += pf; r[3] += pa
    return {"prior": prior, "margin": margin, "market": market, "record": dict(rec)}


def features(v, g):
    h, a = IDX[g["h"]], IDX[g["a"]]
    return [0.0 if g["neutral"] else 1.0,
            v["prior"][h] - v["prior"][a],
            v["margin"][h] - v["margin"][a],
            v["market"][h] - v["market"][a]]


class Logit:
    def __init__(self, l2):
        self.l2 = l2

    def fit(self, X, y):
        X = np.c_[np.ones(len(X)), X]
        w = np.zeros(X.shape[1])
        for _ in range(60):
            p = 1 / (1 + np.exp(-X @ w))
            reg = self.l2 * np.r_[0, w[1:]]
            H = (X * (p * (1 - p))[:, None]).T @ X + self.l2 * np.diag(np.r_[0, np.ones(len(w) - 1)])
            step = np.linalg.solve(H, X.T @ (p - y) + reg)
            w -= step
            if np.abs(step).max() < 1e-9:
                break
        self.w = w
        return self

    def predict(self, X):
        return 1 / (1 + np.exp(-(np.c_[np.ones(len(X)), X] @ self.w)))


def logloss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def pyth_blend_prob(v, g, k=8.0):
    """The old hand-set model: preseason wins blended with Pythagorean pace at weight k games."""
    def strength(t):
        prior_w = v["prior"][IDX[t]] + 8.5
        w, n, pf, pa = v["record"].get(t, [0, 0, 0, 0])
        if not n:
            return prior_w
        pyth = pf ** 2.37 / (pf ** 2.37 + pa ** 2.37) if pf + pa else 0.5
        return (prior_w * k + pyth * 17 * n) / (k + n)
    d = strength(g["h"]) - strength(g["a"]) + (0 if g["neutral"] else 1.6)
    return 1 / (1 + math.exp(-d * 0.15))


def build_dataset(games, priors, seasons, cutoff, lam_margin, lam_market):
    X, y, s, base = [], [], [], []
    for season in seasons:
        rows = season_rows(games, season)
        v = views(rows, season, cutoff, priors, lam_margin, lam_market)
        for g in rows:
            if g["week"] <= cutoff or g["hs"] is None or g["hs"] == g["as"]:
                continue
            X.append(features(v, g)); y.append(1.0 if g["hs"] > g["as"] else 0.0); s.append(season)
            base.append(pyth_blend_prob(v, g))
    return np.array(X), np.array(y), np.array(s), np.array(base)


def loso(X, y, s, cols, l2):
    """Leave-one-season-out predictions using the given feature columns."""
    p = np.zeros(len(y))
    for season in np.unique(s):
        tr, te = s != season, s == season
        p[te] = Logit(l2).fit(X[tr][:, cols], y[tr]).predict(X[te][:, cols])
    return p


def simulate(rows, v, model, cutoff, n, seed=11):
    rem = [g for g in rows if g["week"] > cutoff or g["hs"] is None]
    base = {t: v["record"].get(t, [0, 0, 0, 0])[0] for t in TEAMS}
    probs = model.predict(np.array([features(v, g) for g in rem]))

    def p_home(h, a, neutral=False):
        return float(model.predict(np.array([features(v, {"h": h, "a": a, "neutral": neutral})]))[0])

    rng = random.Random(seed)
    counts = defaultdict(float)
    wins = {t: [] for t in TEAMS}
    for _ in range(n):
        tot = dict(base)
        for g, p in zip(rem, probs):
            tot[g["h"] if rng.random() < p else g["a"]] += 1
        for t in TEAMS:
            wins[t].append(tot[t])
        key = lambda t: (tot[t], rng.random())
        best = max(tot.values())
        top = [t for t in TEAMS if tot[t] == best]
        for t in top:
            counts[("best_record", t)] += 1 / len(top)
        champs = {}
        for conf in ("AFC", "NFC"):
            div_w = [max((t for t in TEAMS if DIV[t] == d), key=key) for d in DIVS if d.startswith(conf)]
            for t in div_w:
                counts[("division", t)] += 1
            wild = sorted([t for t in TEAMS if DIV[t].startswith(conf) and t not in div_w], key=key, reverse=True)[:3]
            seeds = sorted(div_w, key=key, reverse=True) + wild
            for t in seeds:
                counts[("playoffs", t)] += 1
            counts[("top_seed", seeds[0])] += 1
            play = lambda hi, lo: hi if rng.random() < p_home(hi, lo) else lo
            r1 = [seeds[0], play(seeds[1], seeds[6]), play(seeds[2], seeds[5]), play(seeds[3], seeds[4])]
            r1.sort(key=seeds.index)
            d1, d2 = play(r1[0], r1[3]), play(r1[1], r1[2])
            hi, lo = sorted([d1, d2], key=seeds.index)
            champ = play(hi, lo)
            champs[conf] = champ
            counts[("conference", champ)] += 1
        a, b = champs["AFC"], champs["NFC"]
        counts[("super_bowl", a if rng.random() < p_home(a, b, neutral=True) else b)] += 1
    return {f"{k[0]}|{k[1]}": c / n for k, c in counts.items()}, wins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games")
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--sims", type=int, default=20000)
    args = ap.parse_args()

    games = load_games(args.games)
    priors = load_priors()
    live = season_rows(games, args.season)
    cutoff = args.week or max((g["week"] for g in live if g["hs"] is not None), default=0)
    train_seasons = list(range(2003, args.season))

    # Choose ridge strengths for the rating fits, then the stacker's L2, by held-out log loss.
    best = None
    for lam_margin in (4, 8, 16, 32):
        for lam_market in (0.5, 2, 8):
            X, y, s, base = build_dataset(games, priors, train_seasons, cutoff, lam_margin, lam_market)
            p = loso(X, y, s, [0, 1, 2, 3], 1.0)
            ll = logloss(p, y)
            if best is None or ll < best[0]:
                best = (ll, lam_margin, lam_market, X, y, s, base)
    _, lam_margin, lam_market, X, y, s, base = best
    scores = {}
    for name, cols in {"prior_only": [0, 1], "margin_only": [0, 2], "market_only": [0, 3],
                       "prior+margin": [0, 1, 2], "all_three": [0, 1, 2, 3]}.items():
        p = loso(X, y, s, cols, 1.0)
        scores[name] = {"log_loss": round(logloss(p, y), 4),
                        "accuracy": round(float(np.mean((p > 0.5) == (y == 1))), 4)}
    scores["old_k8_blend"] = {"log_loss": round(logloss(base, y), 4),
                              "accuracy": round(float(np.mean((base > 0.5) == (y == 1))), 4)}
    model = Logit(1.0).fit(X, y)

    adjust = {}
    path = Path(str(ADJUST).format(season=args.season))
    if path.exists():
        for r in csv.DictReader(open(path)):
            to = int(r["to_week"]) if r.get("to_week") else 99
            if int(r["from_week"] or 1) <= cutoff + 1 <= to:
                adjust[r["team"]] = adjust.get(r["team"], 0) + float(r["wins_delta"])
    v = views(live, args.season, cutoff, priors, lam_margin, lam_market, adjust)
    probs, wins = simulate(live, v, model, cutoff, args.sims)

    out = {
        "season": args.season, "cutoff_week": cutoff, "sims": args.sims,
        "trained_on": f"{train_seasons[0]}-{train_seasons[-1]}, games after week {cutoff}, leave-one-season-out",
        "lambda_margin": lam_margin, "lambda_market": lam_market,
        "weights": dict(zip(["intercept", "home", "prior", "margin", "market"], [round(float(w), 4) for w in model.w])),
        "holdout": scores,
        "ratings": {t: {"prior": round(float(v["prior"][IDX[t]]), 2), "margin": round(float(v["margin"][IDX[t]]), 2),
                        "market": round(float(v["market"][IDX[t]]), 2),
                        "record": v["record"].get(t, [0, 0, 0, 0])[:2]} for t in TEAMS},
        "probabilities": probs,
        "wins": {t: {"mean": round(float(np.mean(w)), 2),
                     "dist": {str(k): round(float(np.mean(np.array(w) == k)), 4) for k in sorted(set(w))}}
                 for t, w in wins.items()},
    }
    dest = ROOT / "data" / "backtests" / f"season_forecast_{args.season}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(f"cutoff week {cutoff}; lambdas margin {lam_margin} market {lam_market}; weights {out['weights']}")
    for k, sc in scores.items():
        print(f"  {k:14} log loss {sc['log_loss']}  accuracy {sc['accuracy']}")
    print(f"wrote {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
