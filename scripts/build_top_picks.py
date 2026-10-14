#!/usr/bin/env python3
"""Rank this week's spread and over/under picks by how well each kind of pick has done.

Every candidate comes from a signal with a graded history:
  - engine spread play / engine total play: 2025 replay + this season's live ledger
  - WARPS spread lean (edge >= 1 pt, Weeks 1-5 only): preseason WARPS vs close, 2015-2025
  - Over on an under-start team (Week 6+): 2015-2025, from teamTrends.json

Each signal's hit rate is shrunk toward 50% with a Beta(25, 25) prior, so small or
tuned-on samples cannot look stronger than they are, and gets a 90% interval.
Picks qualify only if the shrunk rate beats the 52.4% needed at -110, and are
ranked by the interval's lower bound. Writes site/src/data/topPicks.json.
"""

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "historical"
SITE_DATA = ROOT / "site" / "src" / "data"
OUT = SITE_DATA / "topPicks.json"
PRIOR = 25            # Beta(25, 25): worth 50 games at 50%
BREAKEVEN = 0.524
TOP_N = 10
EARLY_WEEKS = 5


def shrunk(wins, losses):
    a, b = wins + PRIOR, losses + PRIOR
    mean = a / (a + b)
    # Normal approximation to the Beta's 90% interval; accurate since a, b >= 25.
    sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    return {
        "expected": round(mean, 4),
        "low": round(mean - 1.645 * sd, 4),
        "high": round(mean + 1.645 * sd, 4),
        "history": f"{wins}-{losses}",
    }


def warps_early_history():
    w = l = 0
    path = ROOT / "data" / "backtests" / "warps_game_edges" / "warps_game_edges.csv"
    for r in csv.DictReader(open(path)):
        if r["game_type"] != "REG" or int(r["week"]) > EARLY_WEEKS or not r["market_home_spread"] or not r["home_score"]:
            continue
        mk, fair = float(r["market_home_spread"]), float(r["fair_home_spread"])
        edge = mk - fair
        if abs(edge) < 1:
            continue
        margin = float(r["home_score"]) - float(r["away_score"])
        m = (margin + mk) if edge > 0 else (-margin - mk)
        if m:
            w += m > 0
            l += m < 0
    return w, l


def engine_history(season):
    rec = {"spread": [0, 0], "total": [0, 0]}
    replay = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "pick_results.csv"
    ledger = HIST / f"live_pick_ledger_{season}.csv"
    for path in (replay, ledger):
        if not path.exists():
            continue
        for r in csv.DictReader(open(path)):
            m = r.get("market")
            if m in rec and r.get("result") in ("win", "loss"):
                rec[m][0 if r["result"] == "win" else 1] += 1
    return rec


def spread_text(team, line):
    return f"{team} {line:+g}" if line is not None else team


def build(season, week):
    feed = json.load(open(HIST / "matrix_engine_feed.json"))
    overlay = [r for r in json.load(open(SITE_DATA / "warpsMarketOverlay.json"))
               if int(float(r["week"])) == week and int(float(r.get("season", season))) == season]
    trends = json.load(open(SITE_DATA / "teamTrends.json"))
    under_start = set(trends["under_start"]["teams"]) if trends.get("season") == season else set()
    us_hist = trends["under_start"]["history"]["under_start_later_over"]

    eng = engine_history(season)
    signals = {
        "engine_spread": ("Betting engine spread play", shrunk(*eng["spread"])),
        "engine_total": ("Betting engine total play", shrunk(*eng["total"])),
        "warps_early": ("WARPS spread lean, Weeks 1–5", shrunk(*warps_early_history())),
        "under_start_over": ("Over on a team that started under", shrunk(us_hist["w"], us_hist["l"])),
    }

    candidates = {}  # (matchup, market) -> {side: [signal keys]}, plus display text

    def add(mk, market, side, text, signal):
        slot = candidates.setdefault((mk, market), {})
        entry = slot.setdefault(side, {"text": text, "signals": []})
        entry["signals"].append(signal)

    for e in feed.get("edge_board", []):
        if e.get("season") != season or str(e.get("week")) != str(week):
            continue
        best = e.get("best_edge") or {}
        if best.get("status") != "play" or best.get("market") not in ("spread", "total"):
            continue
        mk, side = e["matchup_key"], (best.get("side") or "").upper()
        line = (e.get("markets", {}).get(best["market"], {}) or {}).get("line") or ""
        parts = [p.strip() for p in line.split("|")]
        half = parts[1 if side in ("HOME", "UNDER") else 0] if len(parts) == 2 else ""
        num = half.split(" ")[0].lstrip("ou") if half else ""
        if best["market"] == "spread":
            team = e["home_tla"] if side == "HOME" else e["away_tla"]
            add(mk, "spread", side, f"{team} {num}".strip(), "engine_spread")
        else:
            add(mk, "total", side, f"{side.title()} {num}".strip(), "engine_total")

    for r in overlay:
        mk = r["matchup_key"]
        away, home = mk.split("@")
        total = r.get("market_total")
        if week > EARLY_WEEKS and total not in (None, "") and ({away, home} & under_start):
            add(mk, "total", "OVER", f"Over {float(total):g}", "under_start_over")
        edge = r.get("spread_overlay_edge_points")
        side = (r.get("spread_overlay_side") or "").upper()
        if week <= EARLY_WEEKS and edge not in (None, "") and float(edge) >= 1 and side in ("HOME", "AWAY"):
            line = r.get("market_home_spread") if side == "HOME" else r.get("market_away_spread")
            line = float(line) if line not in (None, "") else None
            add(mk, "spread", side, spread_text(r.get("spread_overlay_team") or (home if side == "HOME" else away), line), "warps_early")

    picks, conflicts = [], []
    for (mk, market), sides in candidates.items():
        if len(sides) > 1:
            conflicts.append({"matchup": mk, "market": market})
            continue
        side, entry = next(iter(sides.items()))
        # Several signals on the same side: use the strongest; list the rest as agreeing.
        ranked = sorted(entry["signals"], key=lambda s: signals[s][1]["low"], reverse=True)
        name, stats = signals[ranked[0]]
        picks.append({
            "matchup": mk,
            "market": market,
            "pick": entry["text"],
            "signal": name,
            "also": [signals[s][0] for s in ranked[1:]],
            **stats,
        })

    qualified = sorted((p for p in picks if p["expected"] > BREAKEVEN), key=lambda p: p["low"], reverse=True)
    return {
        "season": season,
        "week": week,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "breakeven": BREAKEVEN,
        "picks": qualified[:TOP_N],
        "below_breakeven": len(picks) - len(qualified),
        "conflicts": conflicts,
        "signals": [{"name": n, **s} for n, s in signals.values()],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    a = ap.parse_args()
    cw = json.load(open(ROOT / "data" / "current_week.json"))
    season = a.season or int(cw["season"])
    week = a.week or int(cw["week"])
    data = build(season, week)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Top picks week {week}: {len(data['picks'])} qualify, {data['below_breakeven']} below breakeven, {len(data['conflicts'])} conflicts")
    for p in data["picks"]:
        print(f"  {p['matchup']:8} {p['pick']:14} {p['expected']:.1%} ({p['low']:.0%}-{p['high']:.0%}) {p['signal']}")


if __name__ == "__main__":
    main()
