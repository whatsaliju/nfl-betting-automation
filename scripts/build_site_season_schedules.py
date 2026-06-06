#!/usr/bin/env python3
"""Build static site schedule matrices from nflverse games.csv."""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path("/private/tmp/nflverse_games.csv")
OUTPUT = ROOT / "site" / "src" / "data" / "seasonSchedules.json"
SEASONS = range(2015, 2027)
TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]
NORMALIZE = {
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "WSH": "WAS",
}


def canonical(team):
    return NORMALIZE.get(team, team)


def short_day(weekday):
    return {
        "Monday": "Mon",
        "Tuesday": "Tue",
        "Wednesday": "Wed",
        "Thursday": "Thu",
        "Friday": "Fri",
        "Saturday": "Sat",
        "Sunday": "Sun",
    }.get(weekday, weekday[:3] if weekday else "Sun")


def number(value):
    if value in ("", None):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def safe_round(value, digits=1):
    return round(value, digits) if value is not None else None


def load_rows(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def season_win_totals(rows, season):
    wins = {team: 0 for team in TEAMS}
    games = {team: 0 for team in TEAMS}
    for row in rows:
        if row["season"] != str(season) or row["game_type"] != "REG":
            continue
        away = canonical(row["away_team"])
        home = canonical(row["home_team"])
        away_score = number(row["away_score"])
        home_score = number(row["home_score"])
        if away not in wins or home not in wins or away_score is None or home_score is None:
            continue
        games[away] += 1
        games[home] += 1
        if away_score > home_score:
            wins[away] += 1
        elif home_score > away_score:
            wins[home] += 1
    return {team: {"wins": wins[team], "games": games[team]} for team in TEAMS}


def sos_ranks(season_games, opponent_baseline):
    averages = {}
    for team in TEAMS:
        opp_values = []
        for game in season_games:
            away = canonical(game["away_team"])
            home = canonical(game["home_team"])
            if away == team:
                opp_values.append(opponent_baseline.get(home, {}).get("wins", 0))
            elif home == team:
                opp_values.append(opponent_baseline.get(away, {}).get("wins", 0))
        averages[team] = sum(opp_values) / len(opp_values) if opp_values else 0

    ranked = sorted(averages.items(), key=lambda item: item[1], reverse=True)
    return {team: rank + 1 for rank, (team, _) in enumerate(ranked)}


def build_season(rows, season):
    season_games = [
        row for row in rows
        if row["season"] == str(season) and row["game_type"] == "REG"
    ]
    max_week = max((int(row["week"]) for row in season_games), default=18)
    schedule_rows = {team: {"Team": team} for team in TEAMS}
    game_days = {str(week): {} for week in range(1, max_week + 1)}
    game_dates = {str(week): {} for week in range(1, max_week + 1)}
    results = []

    for team in TEAMS:
        for week in range(1, max_week + 1):
            schedule_rows[team][f"W{week}"] = "BYE"

    for row in season_games:
        week = int(row["week"])
        away = canonical(row["away_team"])
        home = canonical(row["home_team"])
        if away not in schedule_rows or home not in schedule_rows:
            continue
        day = short_day(row["weekday"])
        date = row["gameday"] or None
        schedule_rows[away][f"W{week}"] = f"@{home}"
        schedule_rows[home][f"W{week}"] = away
        game_days[str(week)][away] = day
        game_days[str(week)][home] = day
        game_dates[str(week)][away] = date
        game_dates[str(week)][home] = date

        away_score = number(row["away_score"])
        home_score = number(row["home_score"])
        if away_score is not None and home_score is not None:
            winner = None
            if away_score > home_score:
                winner = away
            elif home_score > away_score:
                winner = home
            results.append({
                "week": week,
                "homeTeam": home,
                "awayTeam": away,
                "homeScore": home_score,
                "awayScore": away_score,
                "status": "Final",
                "winner": winner,
                "date": date,
            })

    wins = season_win_totals(rows, season)
    baseline = season_win_totals(rows, season - 1) if season == 2026 else wins
    sos = sos_ranks(season_games, baseline)
    team_stats = {
        team: {
            "sos": sos.get(team, 0),
            "wins": safe_round(wins[team]["wins"], 1) if wins[team]["games"] else None,
        }
        for team in TEAMS
    }

    return {
        "season": season,
        "weeks": list(range(1, max_week + 1)),
        "hasResults": bool(results),
        "scheduleRows": [schedule_rows[team] for team in TEAMS],
        "gameDays": game_days,
        "gameDates": game_dates,
        "teamStats": team_stats,
        "results": sorted(results, key=lambda item: (item["week"], item["date"] or "", item["awayTeam"])),
    }


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not input_path.exists():
        raise SystemExit(f"Missing nflverse games CSV: {input_path}")
    rows = load_rows(input_path)
    payload = {
        str(season): build_season(rows, season)
        for season in SEASONS
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, separators=(",", ": ")) + "\n")
    print(f"Wrote {OUTPUT}")
    print(json.dumps({season: len(payload[str(season)]["results"]) for season in SEASONS}, sort_keys=True))


if __name__ == "__main__":
    main()
