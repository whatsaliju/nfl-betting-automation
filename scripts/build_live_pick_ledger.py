#!/usr/bin/env python3
"""Build the live pick ledger and track record from engine line snapshots.

A play is the engine's pick in the last snapshot before kickoff. Its pick line is
the picked side's line when that pick first appeared (and held through kickoff);
the close is nflverse's closing line, falling back to the last pre-kickoff
snapshot. CLV is in points from the picked side: positive means the pick beat
the close.
"""

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "historical"
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
STAGES = ["initial", "pre_tnf", "update", "lock", "pre_mnf", "final"]
NFLVERSE_TLA = {"LA": "LAR", "WSH": "WAS"}
ET = ZoneInfo("America/New_York")
LEDGER_FIELDS = [
    "season", "week", "matchup_key", "kickoff_utc", "model_version", "classification",
    "market", "side", "pick", "picked_at", "pick_line", "close_line", "close_source",
    "clv", "away_score", "home_score", "result", "reasons",
]


def fetch_schedule(season):
    try:
        with urllib.request.urlopen(SCHEDULES_URL, timeout=30) as resp:
            text = resp.read().decode()
    except Exception as e:
        print(f"nflverse schedule unavailable ({e}); using snapshot closes and master scores", file=sys.stderr)
        return {}
    games = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["season"] != str(season) or r["game_type"] != "REG":
            continue
        away = NFLVERSE_TLA.get(r["away_team"], r["away_team"])
        home = NFLVERSE_TLA.get(r["home_team"], r["home_team"])
        kickoff = None
        if r["gameday"] and r["gametime"]:
            kickoff = datetime.fromisoformat(f"{r['gameday']}T{r['gametime']}").replace(tzinfo=ET)
        games[(r["week"], f"{away}@{home}")] = {
            "kickoff": kickoff,
            "away_score": r["away_score"],
            "home_score": r["home_score"],
            # nflverse spread_line is the expected home margin, so the home team's spread is its negative.
            "home_spread_close": -float(r["spread_line"]) if r["spread_line"] else None,
            "total_close": float(r["total_line"]) if r["total_line"] else None,
        }
    return games


def site_kickoffs():
    path = ROOT / "site" / "src" / "data" / "gameTimes.json"
    if not path.exists():
        return {}
    weeks = json.load(open(path)).get("weeks", {})
    return {(wk, mk): datetime.fromisoformat(t.replace("Z", "+00:00"))
            for wk, games in weeks.items() for mk, t in games.items() if t}


def half(line, idx):
    parts = str(line or "").split("|")
    if len(parts) != 2:
        return None
    m = re.search(r"[+-]?\d+\.?\d*", parts[idx])
    return float(m.group(0)) if m else None


def pick_line(market, side, row):
    if market == "spread":
        return half(row["spread_line"], 0 if side == "AWAY" else 1)
    if market == "total":
        return half(row["total_line"], 0 if side == "OVER" else 1)
    if market == "moneyline":
        return half(row["moneyline_line"], 0 if side == "AWAY" else 1)
    return None


def grade(market, side, line, away, home):
    if away is None or home is None or line is None:
        return ""
    if market == "spread":
        margin = (away - home if side == "AWAY" else home - away) + line
    elif market == "total":
        margin = (away + home - line) * (1 if side == "OVER" else -1)
    elif market == "moneyline":
        margin = away - home if side == "AWAY" else home - away
    else:
        return ""
    return "win" if margin > 0 else ("loss" if margin < 0 else "push")


def score(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def build(season):
    snap_path = HIST / f"engine_line_snapshots_{season}.csv"
    if not snap_path.exists():
        sys.exit(f"No snapshots at {snap_path}")
    snaps = defaultdict(list)
    for r in csv.DictReader(open(snap_path)):
        snaps[(r["week"], r["matchup_key"])].append(r)

    schedule = fetch_schedule(season)
    fallback_kick = site_kickoffs()
    master_scores = {}
    for path in HIST.glob("week*_master.json"):
        wk = path.stem[4:].split("_")[0]
        for g in json.load(open(path)):
            if str(g.get("season")) == str(season):
                master_scores[(wk, g.get("matchup_key"))] = (g.get("away_score"), g.get("home_score"))

    ledger = []
    for (wk, mk), rows in sorted(snaps.items(), key=lambda x: (int(x[0][0]), x[0][1])):
        sched = schedule.get((wk, mk), {})
        kickoff = sched.get("kickoff") or fallback_kick.get((wk, mk))
        if kickoff is None:
            continue
        rows = [r for r in rows if datetime.fromisoformat(r["captured_at"]) < kickoff]
        rows.sort(key=lambda r: (r["captured_at"], STAGES.index(r["stage"]) if r["stage"] in STAGES else 0))
        if not rows:
            continue
        final = rows[-1]
        market, side = final["pick_market"], final["pick_side"].upper()
        if market in ("", "none") or not side:
            continue
        first = final
        for r in reversed(rows):
            if r["pick_market"] == market and r["pick_side"].upper() == side:
                first = r
            else:
                break

        line = pick_line(market, side, first)
        close, source = None, ""
        if market == "spread" and sched.get("home_spread_close") is not None:
            close = sched["home_spread_close"] if side == "HOME" else -sched["home_spread_close"]
            source = "nflverse"
        elif market == "total" and sched.get("total_close") is not None:
            close, source = sched["total_close"], "nflverse"
        if close is None:
            close = pick_line(market, side, final)
            source = "last_snapshot" if close is not None else ""

        clv = None
        if line is not None and close is not None and market in ("spread", "total"):
            if market == "spread":
                clv = line - close
            else:
                clv = (close - line) if side == "OVER" else (line - close)

        away, home = score(sched.get("away_score")), score(sched.get("home_score"))
        if away is None or home is None:
            ms = master_scores.get((wk, mk), (None, None))
            away, home = score(ms[0]), score(ms[1])
            if away == 0 and home == 0:
                away = home = None

        away_tla, home_tla = mk.split("@")
        team = away_tla if side == "AWAY" else home_tla
        if market == "total":
            pick = f"{side.title()} {line:g}" if line is not None else side.title()
        elif market == "spread":
            pick = f"{team} {line:+g}" if line is not None else team
        else:
            pick = f"{team} ML {line:+g}" if line is not None else f"{team} ML"

        ledger.append({
            "season": season, "week": wk, "matchup_key": mk,
            "kickoff_utc": kickoff.astimezone(ZoneInfo("UTC")).isoformat(timespec="minutes"),
            "model_version": final["model_version"], "classification": final["classification"],
            "market": market, "side": side, "pick": pick, "picked_at": first["captured_at"],
            "pick_line": "" if line is None else line, "close_line": "" if close is None else close,
            "close_source": source, "clv": "" if clv is None else round(clv, 2),
            "away_score": "" if away is None else away, "home_score": "" if home is None else home,
            "result": grade(market, side, line, away, home), "reasons": final["pick_reasons"],
        })
    return ledger


def summarize(rows):
    def block(rs):
        w = sum(r["result"] == "win" for r in rs)
        l = sum(r["result"] == "loss" for r in rs)
        p = sum(r["result"] == "push" for r in rs)
        clvs = [float(r["clv"]) for r in rs if r["clv"] != ""]
        return {
            "plays": len(rs), "wins": w, "losses": l, "pushes": p,
            "pending": sum(r["result"] == "" for r in rs),
            "win_rate": round(w / (w + l), 4) if w + l else None,
            "clv_plays": len(clvs),
            "avg_clv": round(sum(clvs) / len(clvs), 2) if clvs else None,
            "beat_close_rate": round(sum(c > 0 for c in clvs) / len(clvs), 4) if clvs else None,
        }

    def grouped(key_fn):
        groups = defaultdict(list)
        for r in rows:
            for k in key_fn(r):
                groups[k].append(r)
        return {k: block(v) for k, v in sorted(groups.items())}

    def reason_tags(r):
        return [t.strip() for t in r["reasons"].split(";") if t.strip()] or ["(none)"]

    return {
        "overall": block(rows),
        "by_market": grouped(lambda r: [r["market"]]),
        "by_model_version": grouped(lambda r: [r["model_version"] or "unknown"]),
        "by_week": grouped(lambda r: [str(r["week"])]),
        "by_reason": grouped(reason_tags),
        "plays": [{k: r[k] for k in ("week", "matchup_key", "pick", "classification", "clv", "result", "close_line")} for r in rows],
        "note": "Live engine plays only (pick in the last snapshot before kickoff). Small samples: treat as monitoring, not proof.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    a = ap.parse_args()
    rows = build(a.season)
    out_csv = HIST / f"live_pick_ledger_{a.season}.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary = {"season": a.season, "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"), **summarize(rows)}
    out_json = HIST / f"live_track_record_{a.season}.json"
    out_json.write_text(json.dumps(summary, indent=2))
    o = summary["overall"]
    print(f"{len(rows)} plays: {o['wins']}-{o['losses']}-{o['pushes']} ({o['pending']} pending), avg CLV {o['avg_clv']}")


if __name__ == "__main__":
    main()
