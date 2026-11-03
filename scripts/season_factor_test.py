#!/usr/bin/env python3
"""Which factors add anything to the season forecast? Held-out test, 2003..S-1.

Base model (season_forecast.py): home field + WARPS preseason (the Season Matrix's prior)
+ ridge margin rating + ridge market rating, all as of the cutoff week. Each candidate is
added on its own and scored on every game after the cutoff, leave-one-season-out:

  pythag        Pythagorean win% difference (points for vs against, exponent 2.37)
  record        plain win% difference (no strength-of-schedule adjustment)
  capped_N      margin rating refit with each game's margin capped at +/-N points
                (garbage-time proxy: blowout scores stop counting past N)
  rest          home rest days minus away rest days (bye weeks, short weeks)
  qb_change     team's latest starter is not the QB who started most of its games
                (injury / benching signal), home flag minus away flag
  sos_remaining average market rating of the opponents left on the schedule

Separately, referees: does a crew's home-cover or home-win rate in earlier seasons
predict the next season's? (Year-to-year correlation across crews with 30+ games.)

Usage: season_factor_test.py [--games games.csv] [--week 8]
Writes data/backtests/season_factor_test.json
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import season_forecast as sf

ROOT = Path(__file__).resolve().parents[1]


def extra_rows(games, season):
    """season_rows plus rest days and starting QBs."""
    rows = []
    for g in games:
        if int(g["season"]) != season:
            continue
        h, a = sf.tla(g["home_team"]), sf.tla(g["away_team"])
        if h not in sf.IDX or a not in sf.IDX:
            continue
        rows.append({"week": int(g["week"]), "h": h, "a": a, "neutral": g["location"] == "Neutral",
                     "hs": int(g["home_score"]) if g["home_score"] else None,
                     "as": int(g["away_score"]) if g["away_score"] else None,
                     "spread": float(g["spread_line"]) if g["spread_line"] else None,
                     "rest": (float(g["home_rest"] or 7) - float(g["away_rest"] or 7)),
                     "hqb": g.get("home_qb_name"), "aqb": g.get("away_qb_name")})
    return rows


def pythag(rec, t):
    w, n, pf, pa = rec.get(t, [0, 0, 0, 0])
    return pf ** 2.37 / (pf ** 2.37 + pa ** 2.37) if pf + pa else 0.5


def qb_flags(rows, cutoff):
    starts = defaultdict(Counter)
    last = {}
    for g in sorted((g for g in rows if g["week"] <= cutoff and g["hs"] is not None), key=lambda g: g["week"]):
        for t, q in ((g["h"], g["hqb"]), (g["a"], g["aqb"])):
            if q:
                starts[t][q] += 1
                last[t] = q
    return {t: float(last.get(t) is not None and starts[t] and last[t] != starts[t].most_common(1)[0][0])
            for t in sf.TEAMS}


def season_features(games, priors, season, cutoff, lam_m, lam_k, caps):
    rows = extra_rows(games, season)
    v = sf.views(rows, season, cutoff, priors, lam_m, lam_k)
    played = [g for g in rows if g["week"] <= cutoff and g["hs"] is not None]
    capped = {c: sf.ridge_ratings(played, lambda g, c=c: max(-c, min(c, g["hs"] - g["as"])), lam_m)[0] for c in caps}
    qb = qb_flags(rows, cutoff)
    future = defaultdict(list)
    for g in rows:
        if g["week"] > cutoff:
            future[g["h"]].append(g["a"]); future[g["a"]].append(g["h"])
    sos = {t: float(np.mean([v["market"][sf.IDX[o]] for o in opp])) if opp else 0.0 for t, opp in future.items()}
    out = []
    for g in rows:
        if g["week"] <= cutoff or g["hs"] is None or g["hs"] == g["as"]:
            continue
        h, a = sf.IDX[g["h"]], sf.IDX[g["a"]]
        rh, ra = v["record"].get(g["h"], [0, 1]), v["record"].get(g["a"], [0, 1])
        f = {"base": sf.features(v, g),
             "pythag": pythag(v["record"], g["h"]) - pythag(v["record"], g["a"]),
             "record": rh[0] / max(rh[1], 1) - ra[0] / max(ra[1], 1),
             "rest": g["rest"],
             "qb_change": qb[g["h"]] - qb[g["a"]],
             "sos_remaining": sos.get(g["h"], 0) - sos.get(g["a"], 0)}
        for c in caps:
            f[f"capped_{c}"] = capped[c][h] - capped[c][a]
        out.append((f, 1.0 if g["hs"] > g["as"] else 0.0, season))
    return out


def score(X, y, s):
    p = np.zeros(len(y))
    per = {}
    for season in np.unique(s):
        tr, te = s != season, s == season
        p[te] = sf.Logit(1.0).fit(X[tr], y[tr]).predict(X[te])
        per[int(season)] = sf.logloss(p[te], y[te])
    return sf.logloss(p, y), float(np.mean((p > 0.5) == (y == 1))), per


def referee_persistence(games):
    by = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))  # ref -> season -> [home wins, home covers, n]
    for g in games:
        if not g["home_score"] or not g.get("referee") or not g["spread_line"]:
            continue
        margin = int(g["home_score"]) - int(g["away_score"])
        if margin == float(g["spread_line"]):
            continue
        r = by[g["referee"]][int(g["season"])]
        r[0] += margin > 0; r[1] += margin > float(g["spread_line"]); r[2] += 1
    pairs_w, pairs_c = [], []
    for ref, seasons in by.items():
        ss = sorted(seasons)
        for s in ss:
            prev = [seasons[x] for x in ss if x < s]
            pw, pc, pn = (sum(x[i] for x in prev) for i in range(3))
            cw, cc, cn = seasons[s]
            if pn >= 30 and cn >= 10:
                pairs_w.append((pw / pn, cw / cn)); pairs_c.append((pc / pn, cc / cn))
    corr = lambda ps: float(np.corrcoef(np.array(ps).T)[0, 1]) if len(ps) > 3 else None
    return {"crew_seasons": len(pairs_w), "home_win_rate_corr": round(corr(pairs_w), 3),
            "home_cover_rate_corr": round(corr(pairs_c), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games")
    ap.add_argument("--week", type=int, default=8)
    ap.add_argument("--season", type=int, default=2026)
    args = ap.parse_args()
    games = sf.load_games(args.games)
    priors = sf.load_priors()
    caps = (10, 14, 17, 21)
    data = []
    for season in range(2003, args.season):
        data += season_features(games, priors, season, args.week, 4, 2, caps)
    y = np.array([d[1] for d in data]); s = np.array([d[2] for d in data])
    base = np.array([d[0]["base"] for d in data])
    b_ll, b_acc, b_per = score(base, y, s)
    results = {"base": {"log_loss": round(b_ll, 4), "accuracy": round(b_acc, 4)}}
    print(f"games {len(y)}  base log loss {b_ll:.4f} acc {b_acc:.3f}")
    names = ["pythag", "record", "rest", "qb_change", "sos_remaining"] + [f"capped_{c}" for c in caps]
    for n in names:
        col = np.array([[d[0][n]] for d in data])
        X = np.c_[base, col]
        if n.startswith("capped_"):
            X = np.c_[base[:, [0, 1, 3]], col]          # replaces the raw margin rating
        ll, acc, per = score(X, y, s)
        better = sum(per[k] < b_per[k] for k in per)
        results[n] = {"log_loss": round(ll, 4), "delta": round(ll - b_ll, 4), "accuracy": round(acc, 4),
                      "seasons_better": f"{better}/{len(per)}"}
        print(f"  {n:14} log loss {ll:.4f} ({ll - b_ll:+.4f})  acc {acc:.3f}  better in {better}/{len(per)} seasons")
    results["referees"] = referee_persistence([g for g in games if int(g["season"]) < args.season])
    print("referees", results["referees"])
    dest = ROOT / "data" / "backtests" / "season_factor_test.json"
    dest.write_text(json.dumps(results, indent=1) + "\n")


if __name__ == "__main__":
    main()
