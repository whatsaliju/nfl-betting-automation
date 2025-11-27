"""
schedule_rest_2025.py

Builds an effective rest map for the 2025 NFL season using FixtureDownload.

OUTPUT FORMAT (IMPORTANT):

SCHEDULE_REST_DATA_2025 = {
    1: {"BUF": 7, "KC": 7, ...},
    2: {"BUF": 8, "KC": 6, ...},
    ...
}
"""

import requests
from datetime import datetime
from collections import defaultdict

SCHEDULE_URL = "https://fixturedownload.com/feed/json/nfl-2025"

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


def _effective_rest(prev, cur):
    """TNF handling = 3 days, MNF floor = 6 days, else actual gap"""
    raw = (cur.date() - prev.date()).days
    wd = cur.weekday()

    # Thursday game short week
    if wd == 3 and raw <= 4:
        return 3

    # Monday with compressed gap
    if wd == 0 and raw < 6:
        return 6

    return raw


def build_schedule_rest_data():
    resp = requests.get(SCHEDULE_URL, timeout=30)
    resp.raise_for_status()
    games = resp.json()

    team_games = defaultdict(list)

    for g in games:
        dt = datetime.strptime(g["DateUtc"], "%Y-%m-%d %H:%M:%SZ")
        w = g["RoundNumber"]
        h = g["HomeTeam"]
        a = g["AwayTeam"]

        if h not in FULL_TO_TLA or a not in FULL_TO_TLA:
            continue

        team_games[FULL_TO_TLA[h]].append({"week": w, "date": dt})
        team_games[FULL_TO_TLA[a]].append({"week": w, "date": dt})

    # Sort each team chronologically
    for t in team_games:
        team_games[t].sort(key=lambda x: x["date"])

    rest = defaultdict(dict)

    for team, seq in team_games.items():
        prev = None
        for g in seq:
            w = g["week"]
            d = g["date"]

            if prev is None:
                days = 7
            else:
                days = _effective_rest(prev, d)

            rest[w][team] = days
            prev = d

    # Fill missing teams
    tla_all = sorted(team_games.keys())
    for w in range(1, 19):
        for team in tla_all:
            rest[w].setdefault(team, 7)

    return {int(w): dict(rest[w]) for w in rest}


SCHEDULE_REST_DATA_2025 = build_schedule_rest_data()
