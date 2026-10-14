#!/usr/bin/env python3
"""Team over/under and against-the-spread trends, plus the under-start over angle.

Uses nflverse schedules (final scores and closing spread/total). Writes
site/src/data/teamTrends.json for the Track Record tab.

Under-start angle: a team that went over in at most 1 of its 4-5 graded games
in Weeks 1-5. From 2015-2025 those teams went over ~54% the rest of the season
(10 of 11 seasons above the rest), because the market cuts their totals more
than for other teams. It is tracked here, graded at the closing total, and is
not a recommendation.
"""

import argparse
import csv
import io
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "src" / "data" / "teamTrends.json"
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
TLA = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
EARLY_WEEKS = 5
HISTORY = range(2015, 2026)


def load_games():
    """Returns (graded games, unplayed games)."""
    with urllib.request.urlopen(SCHEDULES_URL, timeout=60) as resp:
        text = resp.read().decode()
    games, unplayed = [], []
    for r in csv.DictReader(io.StringIO(text)):
        if r["game_type"] != "REG":
            continue
        if not r["home_score"]:
            unplayed.append({
                "season": int(r["season"]),
                "week": int(r["week"]),
                "away": TLA.get(r["away_team"], r["away_team"]),
                "home": TLA.get(r["home_team"], r["home_team"]),
                "total_line": float(r["total_line"]) if r["total_line"] else None,
            })
            continue
        if not r["total_line"] or not r["spread_line"]:
            continue
        hs, aws = int(r["home_score"]), int(r["away_score"])
        total_margin = hs + aws - float(r["total_line"])
        # nflverse spread_line is the expected home margin.
        home_ats_margin = hs - aws - float(r["spread_line"])
        games.append({
            "season": int(r["season"]),
            "week": int(r["week"]),
            "away": TLA.get(r["away_team"], r["away_team"]),
            "home": TLA.get(r["home_team"], r["home_team"]),
            "total_line": float(r["total_line"]),
            "over": None if total_margin == 0 else total_margin > 0,
            "home_cover": None if home_ats_margin == 0 else home_ats_margin > 0,
            "home_fav": float(r["spread_line"]) > 0,
            # Straight-up result for the spread favorite (None for pick'em lines and ties).
            "fav_won": None if float(r["spread_line"]) == 0 or hs == aws else (hs > aws) == (float(r["spread_line"]) > 0),
        })
    return games, unplayed


def record(values):
    hits = sum(1 for v in values if v is True)
    misses = sum(1 for v in values if v is False)
    return {"w": hits, "l": misses, "pct": round(hits / (hits + misses), 4) if hits + misses else None}


def under_start_teams(season_games):
    early = defaultdict(list)
    for g in season_games:
        if g["week"] <= EARLY_WEEKS and g["over"] is not None:
            early[g["away"]].append(g["over"])
            early[g["home"]].append(g["over"])
    return {t for t, xs in early.items() if len(xs) >= 4 and sum(xs) <= 1}


def history_context(games):
    flagged, others = [], []
    seasons_ahead = 0
    for season in HISTORY:
        sg = [g for g in games if g["season"] == season]
        teams = under_start_teams(sg)
        f, o = [], []
        for g in sg:
            if g["week"] <= EARLY_WEEKS or g["over"] is None:
                continue
            for t in (g["away"], g["home"]):
                (f if t in teams else o).append(g["over"])
        flagged += f
        others += o
        if f and o and sum(f) / len(f) > sum(o) / len(o):
            seasons_ahead += 1
    return {
        "seasons": f"{HISTORY.start}-{HISTORY.stop - 1}",
        "under_start_later_over": record(flagged),
        "others_later_over": record(others),
        "seasons_ahead": seasons_ahead,
        "season_count": len(HISTORY),
    }


def build(season):
    games, unplayed = load_games()
    cur = [g for g in games if g["season"] == season]
    teams = sorted({g["away"] for g in cur} | {g["home"] for g in cur})

    per_team = []
    for t in teams:
        tg = [g for g in cur if t in (g["away"], g["home"])]
        covers = [None if g["home_cover"] is None else (g["home_cover"] if g["home"] == t else not g["home_cover"]) for g in tg]
        per_team.append({"team": t, "ou": record([g["over"] for g in tg]), "ats": record(covers)})

    flagged = under_start_teams(cur) if max((g["week"] for g in cur), default=0) >= EARLY_WEEKS else set()
    angle_games = []
    for g in sorted(cur, key=lambda g: (g["week"], g["away"])):
        if g["week"] <= EARLY_WEEKS or not ({g["away"], g["home"]} & flagged):
            continue
        angle_games.append({
            "week": g["week"],
            "matchup": f"{g['away']}@{g['home']}",
            "teams": sorted({g["away"], g["home"]} & flagged),
            "total": g["total_line"],
            "result": "push" if g["over"] is None else ("win" if g["over"] else "loss"),
        })

    upcoming_pool = [g for g in unplayed if g["season"] == season]
    next_week = min((g["week"] for g in upcoming_pool), default=None)
    upcoming = [
        {"week": g["week"], "matchup": f"{g['away']}@{g['home']}", "teams": sorted({g["away"], g["home"]} & flagged), "total": g["total_line"]}
        for g in sorted(upcoming_pool, key=lambda g: g["away"])
        if g["week"] == next_week and {g["away"], g["home"]} & flagged
    ]

    favs = [g["home_cover"] == g["home_fav"] for g in cur if g["home_cover"] is not None]
    return {
        "season": season,
        "through_week": max((g["week"] for g in cur), default=0),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "league": {
            "ou": record([g["over"] for g in cur]),
            "home_ats": record([g["home_cover"] for g in cur]),
            "fav_ats": record(favs),
            "fav_su": record([g["fav_won"] for g in cur]),
        },
        "teams": per_team,
        "under_start": {
            "teams": sorted(flagged),
            "record": record([True if a["result"] == "win" else False if a["result"] == "loss" else None for a in angle_games]),
            "games": angle_games,
            "upcoming": upcoming,
            "history": history_context(games),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    a = ap.parse_args()
    try:
        data = build(a.season)
    except Exception as e:  # network or format failure: keep last week's file
        print(f"Team trends not rebuilt: {e}", file=sys.stderr)
        return
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    u = data["under_start"]
    print(f"Team trends through week {data['through_week']}: under-start teams {u['teams']}, angle {u['record']}")


if __name__ == "__main__":
    main()
