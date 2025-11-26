import json
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

def build_schedule_rest_data():
    # 1. Get schedule
    resp = requests.get(SCHEDULE_URL)
    resp.raise_for_status()
    games = resp.json()

    # 2. Build per-team game list (sorted by date)
    team_games = defaultdict(list)
    for g in games:
        dt = datetime.strptime(g["DateUtc"], "%Y-%m-%d %H:%M:%SZ")
        week = g["RoundNumber"]
        home = FULL_TO_TLA[g["HomeTeam"]]
        away = FULL_TO_TLA[g["AwayTeam"]]

        team_games[home].append({"week": week, "date": dt})
        team_games[away].append({"week": week, "date": dt})

    for tla in team_games:
        team_games[tla].sort(key=lambda x: x["date"])

    # 3. Compute rest days per team per week
    rest_by_week = defaultdict(dict)

    for tla, games in team_games.items():
        prev_date = None
        for g in games:
            week = g["week"]
            date = g["date"]
            if prev_date is None:
                # First game of the season: define as 7 days rest
                rest_days = 7
            else:
                rest_days = (date.date() - prev_date.date()).days

            wk_label = f"W{week}"
            rest_by_week[wk_label][tla] = rest_days
            prev_date = date

    # 4. Ensure every week has all 32 teams with default 7 if (for some reason) missing
    all_tlas = sorted(team_games.keys())
    for w in range(1, 19):
        wk_label = f"W{w}"
        for tla in all_tlas:
            rest_by_week[wk_label].setdefault(tla, 7)

    # 5. Build pretty Python constant string
    lines = []
    lines.append("SCHEDULE_REST_DATA_2025 = {")
    for w in range(1, 19):
        wk_label = f"W{w}"
        mp = {tla: rest_by_week[wk_label][tla] for tla in sorted(all_tlas)}

        lines.append(f"    '{wk_label}': {{")
        line = "        "
        for tla, val in mp.items():
            entry = f"'{tla}': {val}, "
            if len(line) + len(entry) > 100:
                lines.append(line)
                line = "        " + entry
            else:
                line += entry
        if line.strip():
            lines.append(line)
        lines.append("    },")
    lines.append("}")

    return "\n".join(lines)

if __name__ == "__main__":
    rest_map_str = build_schedule_rest_data()
    with open("data/schedule_rest_2025.py", "w") as f:
    f.write(rest_map_str)

