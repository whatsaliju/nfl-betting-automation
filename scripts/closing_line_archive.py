"""
closing_line_archive.py — Vegas Closing Line Archiver

Freezes the Vegas O/U and spread for each NFL game at kickoff time.
Run as a cron job every 5 minutes during game days (Thu–Mon in season):

    */5 * * * 1,4,5,6,0 python3 scripts/closing_line_archive.py

Output: data/closing_lines_YYYY.jsonl — one JSON record per game, appended
on the minute the game enters "in_progress" state.

Records look like:
  {"game_id":"2026_01_KC_BAL","season":2026,"week":1,
   "home":"BAL","away":"KC","kickoff":"2026-09-06T13:00:00Z",
   "closing_ou":48.5,"closing_spread":-3.0,"archived_at":"2026-09-06T12:58:43Z"}

Why we need this:
  The Dynasty Modifier DM-test (Feb 2027 audit) requires the closing
  O/U line, not the opening line recorded in seasonSchedules.json.
  Line movement between open and close is the market's final signal;
  using the opening line would introduce bias into the validation.
"""

import json
import os
import sys
import time
import datetime
import urllib.request
import urllib.error

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ARCHIVE_FILE_TEMPLATE = os.path.join(DATA_DIR, "closing_lines_{season}.jsonl")

# ─── Data source ───────────────────────────────────────────────────────────────
# The Odds API (free tier: 500 req/mo).  Set env var ODDS_API_KEY.
# Docs: https://the-odds-api.com/lol-of-the-api/
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_URL = (
    "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
    "?apiKey={key}&regions=us&markets=totals,spreads&oddsFormat=american"
)


def fetch_current_lines(api_key: str) -> list[dict]:
    url = ODDS_API_URL.format(key=api_key)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[ODDS API] HTTP {e.code}: {e.reason}", file=sys.stderr)
        return []
    except urllib.error.URLError as e:
        print(f"[ODDS API] Network error: {e.reason}", file=sys.stderr)
        return []


def load_archived_ids(season: int) -> set[str]:
    path = ARCHIVE_FILE_TEMPLATE.format(season=season)
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path) as f:
        for line in f:
            try:
                ids.add(json.loads(line)["game_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return ids


def append_record(season: int, record: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = ARCHIVE_FILE_TEMPLATE.format(season=season)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[archived] {record['game_id']}  OU={record['closing_ou']}  "
          f"spread={record['closing_spread']}")


def parse_game(game: dict, now_utc: datetime.datetime) -> dict | None:
    """Extract closing line record from an odds-api game object."""
    commence = game.get("commence_time", "")
    if not commence:
        return None

    try:
        kickoff = datetime.datetime.fromisoformat(commence.replace("Z", "+00:00"))
    except ValueError:
        return None

    # Archive window: from 15 min before kickoff to 30 min after
    delta = (now_utc - kickoff).total_seconds()
    if not (-900 <= delta <= 1800):
        return None

    home = game.get("home_team", "")
    away = game.get("away_team", "")
    season = kickoff.year if kickoff.month >= 9 else kickoff.year - 1

    # Build a stable game ID from season + approximate week + teams
    week_num = max(1, min(18, int((kickoff - datetime.datetime(season, 9, 1, tzinfo=datetime.timezone.utc)).days / 7) + 1))
    h_code = home.split()[-1][:3].upper()
    a_code = away.split()[-1][:3].upper()
    game_id = f"{season}_{week_num:02d}_{a_code}_{h_code}"

    # Pull best-available O/U and spread from bookmakers
    closing_ou = None
    closing_spread = None
    for bookmaker in game.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] == "totals" and closing_ou is None:
                for outcome in market.get("outcomes", []):
                    if outcome["name"] == "Over":
                        closing_ou = outcome.get("point")
                        break
            if market["key"] == "spreads" and closing_spread is None:
                for outcome in market.get("outcomes", []):
                    if outcome["name"] == home:
                        closing_spread = outcome.get("point")
                        break

    if closing_ou is None and closing_spread is None:
        return None

    return {
        "game_id": game_id,
        "season": season,
        "week": week_num,
        "home": home,
        "away": away,
        "kickoff": commence,
        "closing_ou": closing_ou,
        "closing_spread": closing_spread,
        "archived_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def run() -> None:
    if not ODDS_API_KEY:
        print("ODDS_API_KEY not set — export it before running.", file=sys.stderr)
        sys.exit(1)

    now = datetime.datetime.now(datetime.timezone.utc)
    season = now.year if now.month >= 9 else now.year - 1
    archived_ids = load_archived_ids(season)

    games = fetch_current_lines(ODDS_API_KEY)
    new_count = 0

    for game in games:
        record = parse_game(game, now)
        if record is None:
            continue
        if record["game_id"] in archived_ids:
            continue  # already frozen
        append_record(season, record)
        archived_ids.add(record["game_id"])
        new_count += 1

    if new_count == 0:
        print(f"[{now:%Y-%m-%d %H:%M}Z] no new games in archive window")


if __name__ == "__main__":
    run()
