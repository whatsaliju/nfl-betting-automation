#!/usr/bin/env python3
"""History layer: walk-forward side and total models on 2003-2025, scored on 2026.

One logistic model per market, trained only on information known before kickoff
and available for every past season (nflverse schedules + WARPS preseason priors):

  Sides  (target: home team covers the closing spread)
    WARPS edge vs the close plus a version that fades by week, spread size, home
    dog, rest difference, divisional, neutral site, each team's ATS form this
    season, the referee's home-cover history.
  Totals (target: game goes over the closing total)
    total line, wind, temperature, dome, divisional, each team's over/under form
    this season, under-start teams (<=1 over in Weeks 1-5) after Week 5, the
    referee's over history, Weeks 10-14, Sunday/Monday night.

Walk-forward: season S is predicted by a model trained only on 2003..S-1, so the
2008-2025 record is out of sample. 2026 uses the model trained on 2003-2025.
Records are graded at the closing line, so a pick has to clear 52.4% to beat -110.

Two versions per market: all inputs, and a lean model.

Writes data/backtests/history_model/{summary.json,report.md,predictions_2026.csv}.
Research output only: nothing here feeds the betting card.
"""

import argparse
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "backtests" / "history_model"
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
WARPS_HISTORY = ROOT / "warps_backtest_team_results_v2_3.csv"
WARPS_2026 = ROOT / "warps_2026_game_priors.csv"
TLA = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}

FIRST_SEASON = 2000          # 2000-2002 only build referee history
TRAIN_START = 2003
TEST_SEASONS = range(2008, 2026)
LIVE_SEASON = 2026
EARLY_WEEKS = 5
# WARPS is a preseason rating; its weight fades as the market learns from real games.
# warps_edge_decay = edge x (18 - week) / 17, so the model fits weight(week) = a + b x (18 - week) / 17.
REG_WEEKS = 17
L2 = 1.0
THRESHOLDS = (0.53, 0.55, 0.57)
BREAKEVEN = 110 / 210

# WARPS game prior, same constants as scripts/backtest_warps_game_edges.py
HOME_FIELD_WINS = 1.6
WIN_GAP_LOGIT_SCALE = 0.15
NFL_MARGIN_SD = 13.45

SIDE_FEATURES = [
    "warps_edge", "warps_edge_decay", "home_spread", "home_dog", "rest_diff",
    "div_game", "neutral", "home_ats_form", "away_ats_form", "ref_home_cover",
]
TOTAL_FEATURES = [
    "total_line", "wind", "temp_dev", "dome", "div_game",
    "home_ou_form", "away_ou_form", "under_start", "ref_over", "late_season", "primetime",
]
# Lean models keep the inputs with a consistent sign in the full model and regularise
# harder. WARPS enters as edge + edge x (18 - week) / 17 so its weight fades by week
# instead of switching off after Week 5. Week 10-14 and Sunday/Monday night games lean
# under. The lean inputs were picked after looking at the data, so their walk-forward
# record flatters them a little; the current season is the clean test.
LEAN_SIDE_FEATURES = ["warps_edge", "warps_edge_decay", "home_dog", "home_ats_form", "away_ats_form"]
LEAN_TOTAL_FEATURES = ["wind", "under_start", "home_ou_form", "away_ou_form", "late_season", "primetime"]
LEAN_L2 = 50.0
MODELS = [
    # key, label, features, target, l2
    ("sides", "Sides, all inputs (home cover)", SIDE_FEATURES, "home_cover", L2),
    ("totals", "Totals, all inputs (over)", TOTAL_FEATURES, "over", L2),
    ("sides_lean", "Sides, lean (home cover)", LEAN_SIDE_FEATURES, "home_cover", LEAN_L2),
    ("totals_lean", "Totals, lean (over)", LEAN_TOTAL_FEATURES, "over", LEAN_L2),
]


def tla(team):
    return TLA.get(team, team)


def shrunk(hits, n, prior=10):
    """Rate pulled toward 50% by `prior` pseudo-games, centered at 0."""
    return (hits + prior / 2) / (n + prior) - 0.5


def fair_home_spread(home_wins, away_wins, neutral):
    hfa = 0.0 if neutral else HOME_FIELD_WINS
    p = 1 / (1 + math.exp(-(home_wins - away_wins + hfa) * WIN_GAP_LOGIT_SCALE))
    return -NormalDist().inv_cdf(p) * NFL_MARGIN_SD


def load_schedule(path):
    if path:
        text = Path(path).read_text()
    else:
        with urllib.request.urlopen(SCHEDULES_URL, timeout=60) as resp:
            text = resp.read().decode()
    rows = [r for r in csv.DictReader(io.StringIO(text))
            if r["game_type"] == "REG" and int(r["season"]) >= FIRST_SEASON and r["spread_line"] and r["total_line"]]
    rows.sort(key=lambda r: (r["gameday"], r.get("gametime") or "", r["game_id"]))
    return rows


def load_warps():
    wins = {}
    with open(WARPS_HISTORY) as f:
        for r in csv.DictReader(f):
            wins[(int(r["season"]), tla(r["team"]))] = float(r["proj"])
    if WARPS_2026.exists():
        with open(WARPS_2026) as f:
            for r in csv.DictReader(f):
                wins.setdefault((int(r["season"]), r["away_tla"]), float(r["away_warps_wins"]))
                wins.setdefault((int(r["season"]), r["home_tla"]), float(r["home_warps_wins"]))
    return wins


def build_rows(schedule, warps):
    """Features use only games that kicked off earlier (state is updated after each row)."""
    ats = defaultdict(lambda: [0, 0])      # (season, team) -> [covers, graded]
    ou = defaultdict(lambda: [0, 0])       # (season, team) -> [overs, graded]
    early_ou = defaultdict(lambda: [0, 0])  # Weeks 1-5 only
    ref_cover = defaultdict(lambda: [0, 0])
    ref_over = defaultdict(lambda: [0, 0])
    rows = []
    for g in schedule:
        season, week = int(g["season"]), int(g["week"])
        away, home = tla(g["away_team"]), tla(g["home_team"])
        home_spread = -float(g["spread_line"])     # nflverse spread_line = expected home margin
        total = float(g["total_line"])
        neutral = g.get("location") == "Neutral"
        dome = g.get("roof") in ("dome", "closed")
        wind = 0.0 if dome or not g.get("wind") else float(g["wind"])
        temp = 70.0 if dome or not g.get("temp") else float(g["temp"])
        ref = g.get("referee") or ""
        played = g["home_score"] != ""

        hw, aw = warps.get((season, home)), warps.get((season, away))
        warps_edge = None
        if hw is not None and aw is not None:
            # Positive = WARPS rates the home side better than the market does.
            warps_edge = max(-10.0, min(10.0, home_spread - fair_home_spread(hw, aw, neutral)))

        def under_start(team):
            o, n = early_ou[(season, team)]
            return week > EARLY_WEEKS and n >= 4 and o <= 1

        row = {
            "season": season, "week": week, "game_id": g["game_id"],
            "matchup": f"{away}@{home}", "away": away, "home": home,
            "home_spread_line": home_spread, "total_line_raw": total, "played": played,
            "warps_edge": warps_edge if warps_edge is not None else 0.0,
            "warps_edge_early": (warps_edge or 0.0) if week <= EARLY_WEEKS else 0.0,
            "warps_edge_decay": (warps_edge or 0.0) * max(0.0, (REG_WEEKS + 1 - week) / REG_WEEKS),
            "has_warps": warps_edge is not None,
            "home_spread": home_spread,
            "home_dog": 1.0 if home_spread > 0 else 0.0,
            "rest_diff": (float(g["home_rest"] or 7) - float(g["away_rest"] or 7)) / 7,
            "div_game": float(g.get("div_game") or 0),
            "neutral": 1.0 if neutral else 0.0,
            "home_ats_form": shrunk(*ats[(season, home)]),
            "away_ats_form": shrunk(*ats[(season, away)]),
            "ref_home_cover": shrunk(*ref_cover[ref], prior=40) if ref else 0.0,
            "total_line": total,
            "wind": wind,
            "temp_dev": abs(temp - 65) / 10,
            "dome": 1.0 if dome else 0.0,
            "home_ou_form": shrunk(*ou[(season, home)]),
            "away_ou_form": shrunk(*ou[(season, away)]),
            "under_start": 1.0 if under_start(home) or under_start(away) else 0.0,
            "ref_over": shrunk(*ref_over[ref], prior=40) if ref else 0.0,
            # Sunday/Monday night (not Thursday, not international) and the Week 10-14 stretch.
            "primetime": 1.0 if not neutral and (g.get("weekday") == "Monday" or (
                g.get("weekday") == "Sunday" and (g.get("gametime") or "13:00") >= "19:00")) else 0.0,
            "late_season": 1.0 if 10 <= week <= 14 else 0.0,
            "home_cover": None, "over": None,
        }
        if played:
            hs, as_ = int(g["home_score"]), int(g["away_score"])
            cover_margin = hs - as_ + home_spread
            total_margin = hs + as_ - total
            row["home_cover"] = None if cover_margin == 0 else float(cover_margin > 0)
            row["over"] = None if total_margin == 0 else float(total_margin > 0)
            if row["home_cover"] is not None:
                c = int(row["home_cover"])
                ats[(season, home)][0] += c; ats[(season, home)][1] += 1
                ats[(season, away)][0] += 1 - c; ats[(season, away)][1] += 1
                if ref:
                    ref_cover[ref][0] += c; ref_cover[ref][1] += 1
            if row["over"] is not None:
                o = int(row["over"])
                for t in (home, away):
                    ou[(season, t)][0] += o; ou[(season, t)][1] += 1
                    if week <= EARLY_WEEKS:
                        early_ou[(season, t)][0] += o; early_ou[(season, t)][1] += 1
                if ref:
                    ref_over[ref][0] += o; ref_over[ref][1] += 1
        rows.append(row)
    return rows


class Logistic:
    """L2-regularised logistic regression fit by Newton's method on standardised features."""

    def __init__(self, l2=L2):
        self.l2 = l2

    def fit(self, X, y):
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1
        Z = np.column_stack([np.ones(len(X)), (X - self.mu) / self.sd])
        w = np.zeros(Z.shape[1])
        reg = np.full(Z.shape[1], self.l2); reg[0] = 0
        for _ in range(50):
            p = 1 / (1 + np.exp(-Z @ w))
            grad = Z.T @ (p - y) + reg * w
            H = (Z * (p * (1 - p))[:, None]).T @ Z + np.diag(reg)
            step = np.linalg.solve(H, grad)
            w -= step
            if np.abs(step).max() < 1e-8:
                break
        self.w = w
        return self

    def predict(self, X):
        Z = np.column_stack([np.ones(len(X)), (X - self.mu) / self.sd])
        return 1 / (1 + np.exp(-Z @ self.w))


def matrix(rows, features):
    return np.array([[r[f] for f in features] for r in rows], dtype=float)


def grade(probs, ys):
    """Bet the side the model favours when its probability clears each threshold."""
    out = {}
    for t in THRESHOLDS:
        w = l = 0
        for p, y in zip(probs, ys):
            if p >= t:
                w += y == 1; l += y == 0
            elif p <= 1 - t:
                w += y == 0; l += y == 1
        out[str(t)] = {"w": int(w), "l": int(l), "pct": round(w / (w + l), 4) if w + l else None}
    eps = 1e-9
    ll = -np.mean([y * math.log(p + eps) + (1 - y) * math.log(1 - p + eps) for p, y in zip(probs, ys)])
    return {"games": len(ys), "log_loss": round(float(ll), 4), "picks": out}


def run_market(rows, features, target, l2=L2):
    labelled = [r for r in rows if r[target] is not None and (target != "home_cover" or r["has_warps"])]
    by_season = defaultdict(list)
    for r in labelled:
        by_season[r["season"]].append(r)

    seasons = {}
    pooled_p, pooled_y = [], []
    for s in TEST_SEASONS:
        train = [r for r in labelled if TRAIN_START <= r["season"] < s]
        test = by_season.get(s, [])
        if not train or not test:
            continue
        model = Logistic(l2).fit(matrix(train, features), np.array([r[target] for r in train]))
        p = model.predict(matrix(test, features))
        y = [int(r[target]) for r in test]
        seasons[s] = grade(p, y)
        pooled_p += list(p); pooled_y += y

    final_train = [r for r in labelled if TRAIN_START <= r["season"] < LIVE_SEASON]
    final = Logistic(l2).fit(matrix(final_train, features), np.array([r[target] for r in final_train]))
    live = [r for r in labelled if r["season"] == LIVE_SEASON]
    live_grade = grade(final.predict(matrix(live, features)), [int(r[target]) for r in live]) if live else None

    beat = {str(t): sum(1 for g in seasons.values()
                        if g["picks"][str(t)]["pct"] is not None and g["picks"][str(t)]["pct"] > BREAKEVEN)
            for t in THRESHOLDS}
    coefs = {f: round(float(c), 4) for f, c in zip(features, final.w[1:])}
    return {
        "walk_forward": {"seasons": {str(k): v for k, v in seasons.items()},
                         "pooled": grade(pooled_p, pooled_y),
                         "seasons_beating_breakeven": beat},
        "live_2026": live_grade,
        "coefficients_per_sd": coefs,
        "intercept": round(float(final.w[0]), 4),
    }, final


def report_md(summary):
    lines = [
        "# History layer: walk-forward side and total models",
        "",
        f"Generated {summary['generated_at']}. Trained on {TRAIN_START}-{LIVE_SEASON - 1}; each test season "
        f"uses only earlier seasons. Graded at the closing line; break-even at -110 is {BREAKEVEN:.1%}.",
        "",
    ]
    for market, label, _, target, _ in MODELS:
        m = summary[market]
        pooled = m["walk_forward"]["pooled"]
        lines += [f"## {label}", "",
                  f"Pooled {TEST_SEASONS.start}-{TEST_SEASONS.stop - 1}: {pooled['games']} games, "
                  f"log loss {pooled['log_loss']} (coin flip = 0.6931).", "",
                  "| Confidence | Picks | W-L | Win % | Seasons above 52.4% |", "|---|---:|---:|---:|---:|"]
        for t in THRESHOLDS:
            p = pooled["picks"][str(t)]
            pct = f"{p['pct']:.1%}" if p["pct"] is not None else "-"
            lines.append(f"| {round(t * 100)}%+ | {p['w'] + p['l']} | {p['w']}-{p['l']} | {pct} | "
                         f"{m['walk_forward']['seasons_beating_breakeven'][str(t)]} of {len(m['walk_forward']['seasons'])} |")
        lines += ["", "| Season | Games | Log loss | 53%+ W-L | Win % |", "|---|---:|---:|---:|---:|"]
        for s, g in m["walk_forward"]["seasons"].items():
            p = g["picks"]["0.53"]
            pct = f"{p['pct']:.1%}" if p["pct"] is not None else "-"
            lines.append(f"| {s} | {g['games']} | {g['log_loss']} | {p['w']}-{p['l']} | {pct} |")
        live = m["live_2026"]
        if live:
            p = live["picks"]["0.53"]
            pct = f"{p['pct']:.1%}" if p["pct"] is not None else "-"
            lines.append(f"| **2026 to date** | {live['games']} | {live['log_loss']} | {p['w']}-{p['l']} | {pct} |")
        lines += ["", "Final-model weights (per standard deviation; positive pushes toward "
                  f"{'home cover' if target == 'home_cover' else 'over'}):", ""]
        for f, c in sorted(m["coefficients_per_sd"].items(), key=lambda kv: -abs(kv[1])):
            lines.append(f"- `{f}`: {c:+.3f}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", help="local nflverse games.csv (default: download)")
    a = ap.parse_args()

    rows = build_rows(load_schedule(a.games), load_warps())
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "train_seasons": f"{TRAIN_START}-{LIVE_SEASON - 1}",
        "test_seasons": f"{TEST_SEASONS.start}-{TEST_SEASONS.stop - 1}",
        "breakeven": round(BREAKEVEN, 4),
    }
    models = {}
    for key, _, features, target, l2 in MODELS:
        summary[key], models[key] = run_market(rows, features, target, l2)
        summary[key]["features"] = features

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT_DIR / "report.md").write_text(report_md(summary))

    live = [r for r in rows if r["season"] == LIVE_SEASON]
    if live:
        probs = {key: models[key].predict(matrix(live, feats)) for key, _, feats, _, _ in MODELS}
        with open(OUT_DIR / "predictions_2026.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["season", "week", "matchup", "home_spread", "total_line"]
                       + [f"{key}_prob" for key, *_ in MODELS] + ["home_cover", "over"])
            for i, r in enumerate(live):
                w.writerow([r["season"], r["week"], r["matchup"], r["home_spread_line"], r["total_line_raw"]]
                           + [round(float(probs[key][i]), 4) for key, *_ in MODELS]
                           + ["" if r["home_cover"] is None else int(r["home_cover"]),
                              "" if r["over"] is None else int(r["over"])])

    for key, *_ in MODELS:
        p = summary[key]["walk_forward"]["pooled"]
        print(key, p["log_loss"], {t: (v["w"], v["l"], v["pct"]) for t, v in p["picks"].items()})


if __name__ == "__main__":
    main()
