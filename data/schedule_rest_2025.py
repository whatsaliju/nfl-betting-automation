"""
schedule_rest_2025.py

Builds an *effective rest days* map for the 2025 NFL season using the
FixtureDownload JSON schedule.

Model:
- Week 1: first game for every team is treated as 7 days rest.
- Rest between games = (next_game_date - prev_game_date).days
- Thursday games (TNF / short week) are treated as **3 days** rest
  whenever the raw gap is very short (<= 4 days).
- Monday games (MNF / weird weeks) are treated as **at least 6 days**
  rest if the raw gap comes out < 6.

Output:
- SCHEDULE_REST_DATA_2025 = {
      "W1": {"ARI": 7, "ATL": 7, ...},
      "W2": {"ARI": 7, "ATL": 3, ...},
      ...
  }
"""

import requests
from datetime import datetime
from collections import defaultdict

SCHEDULE_URL = "https://fixturedownload.com/feed/json/nfl-2025"

# Map full team names from the feed -> your TLAs
FULL_TO_TLA = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


def _effective_rest(prev_date, cur_date):
    """
    Convert calendar-day gap into your betting-model rest:

    - First game of season: handled separately (7 days).
    - TNF: treat as 3 days rest when it's a true short week (<= 4 days).
    - MNF: enforce a minimum of 6 days rest (if gap somehow < 6).
    """
    raw_days = (cur_date.date() - prev_date.date()).days
    cur_wd = cur_date.weekday()  # Monday=0, Sunday=6

    # --- TNF logic (Model B: 3 days rest on short weeks) ---
    # If the game is on Thursday (3) and the gap is very short, cap at 3.
    if cur_wd == 3 and raw_days <= 4:
        return 3

    # --- MNF logic (Model B: minimum 6 days rest) ---
    # If the game is on Monday (0) and somehow has < 6 calendar days gap,
    # bump it up to 6 for your model.
    if cur_wd == 0 and raw_days < 6:
        return 6

    # Otherwise just use the actual day difference.
    return raw_days


def build_schedule_rest_data():
    # 1. Get schedule from FixtureDownload
    resp = requests.get(SCHEDULE_URL, timeout=30)
    resp.raise_for_status()
    games = resp.json()

    # 2. Build per-team chronological game lists
    team_games = defaultdict(list)

    for g in games:
        dt = datetime.strptime(g["DateUtc"], "%Y-%m-%d %H:%M:%SZ")
        week = g["RoundNumber"]
        home_full = g["HomeTeam"]
        away_full = g["AwayTeam"]

        # Map to TLAs (defensive: skip if something weird)
        if home_full not in FULL_TO_TLA or away_full not in FULL_TO_TLA:
            continue

        home = FULL_TO_TLA[home_full]
        away = FULL_TO_TLA[away_full]

        team_games[home].append({"week": week, "date": dt})
        team_games[away].append({"week": week, "date": dt})

    # Sort each team schedule by date
    for tla in team_games:
        team_games[tla].sort(key=lambda x: x["date"])

    # 3. Compute effective rest days per team per week
    rest_by_week = defaultdict(dict)

    for tla, games_for_team in team_games.items():
        prev_date = None
        for g in games_for_team:
            week = g["week"]
            date = g["date"]

            if prev_date is None:
                # First game of season → treat as 7 days rest for everyone
                rest_days = 7
            else:
                rest_days = _effective_rest(prev_date, date)

            wk_label = f"W{week}"
            rest_by_week[wk_label][tla] = rest_days
            prev_date = date

    # 4. Ensure every week has all known teams with a default of 7
    all_tlas = sorted(team_games.keys())
    for w in range(1, 19):  # Weeks 1–18
        wk_label = f"W{w}"
        for tla in all_tlas:
            rest_by_week[wk_label].setdefault(tla, 7)

    # 5. Convert into a plain dict-of-dicts so it’s import-safe
    schedule_rest = {}
    for w in range(1, 19):
        wk_label = f"W{w}"
        # Make sure the week exists, else default everyone to 7
        week_map = rest_by_week.get(wk_label, {})
        schedule_rest[wk_label] = {tla: week_map.get(tla, 7) for tla in all_tlas}

    return schedule_rest


# This is what nfl_pro_analyzer imports
SCHEDULE_REST_DATA_2025 = build_schedule_rest_data()

if __name__ == "__main__":
    # Quick debug print if you ever run this file directly
    import pprint
    pprint.pp(SCHEDULE_REST_DATA_2025)
