#!/usr/bin/env python3
"""
Extract kickoff times from current_odds_api.json and write
site/src/data/gameTimes2026.json for use in the Week View.

Output shape:
  { "1": { "SF@LAR": "2026-09-11T00:35:00Z", ... }, "2": { ... } }

Run after fetch_current_odds_api.py or whenever current_odds_api.json changes.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
IN_PATH = ROOT / "data" / "current_odds_api.json"
OUT_PATH = ROOT / "site" / "src" / "data" / "gameTimes2026.json"

TEAM_MAP = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

SEASON_START = datetime(2026, 9, 8, tzinfo=timezone.utc)


def week_number(commence_utc: str) -> int:
    dt = datetime.fromisoformat(commence_utc.replace("Z", "+00:00"))
    days = (dt - SEASON_START).days
    return max(1, min(18, days // 7 + 1))


def main() -> None:
    if not IN_PATH.exists():
        print(f"[game-times] {IN_PATH} not found — skipping", file=sys.stderr)
        sys.exit(0)

    with open(IN_PATH) as f:
        games = json.load(f)

    by_week: dict[str, dict[str, str]] = {}
    skipped = 0
    for game in games:
        if game.get("sport_key") != "americanfootball_nfl":
            continue
        away = TEAM_MAP.get(game.get("away_team", ""))
        home = TEAM_MAP.get(game.get("home_team", ""))
        commence = game.get("commence_time", "")
        if not away or not home or not commence:
            skipped += 1
            continue
        wk = str(week_number(commence))
        key = f"{away}@{home}"
        by_week.setdefault(wk, {})[key] = commence

    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "the-odds-api",
        "weeks": by_week,
    }

    OUT_PATH.write_text(json.dumps(output, indent=2))
    weeks_found = len(by_week)
    games_found = sum(len(v) for v in by_week.values())
    print(f"[game-times] Wrote {OUT_PATH} — {weeks_found} weeks, {games_found} games, {skipped} skipped", file=sys.stderr)


if __name__ == "__main__":
    main()
