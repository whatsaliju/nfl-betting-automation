#!/usr/bin/env python3
"""
Generate data/schedule_rest_{season}.py from nflverse public schedule data.

Usage:
    python scripts/generate_schedule_rest.py 2027

Fetches the nflverse games.csv, computes rest days (calendar days since each
team's previous game), and writes the keyed dict in the same format as
data/schedule_rest_2026.py.
"""

import sys
import os
import requests
import pandas as pd
from datetime import datetime

NFLVERSE_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
TEAMS = ['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB',
         'HOU','IND','JAX','KC','LAC','LAR','LV','MIA','MIN','NE','NO','NYG','NYJ',
         'PHI','PIT','SEA','SF','TB','TEN','WAS']

WEEK_ORDER = ['W1','W2','W3','W4','W5','W6','W7','W8','W9','W10','W11','W12',
              'W13','W14','W15','W16','W17','W18','WC','DIV','CONF','SB']

WEEK_LABEL_MAP = {
    'REG': lambda n: f'W{n}',
    'WC':  lambda _: 'WC',
    'DIV': lambda _: 'DIV',
    'CON': lambda _: 'CONF',
    'SB':  lambda _: 'SB',
}


def fetch_games(season: int) -> pd.DataFrame:
    print(f"📥 Fetching nflverse games.csv …")
    r = requests.get(NFLVERSE_URL, timeout=30)
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(r.text), low_memory=False)
    df = df[df['season'] == season].copy()
    df['gameday'] = pd.to_datetime(df['gameday'])
    return df


def week_label(game_type: str, week: int) -> str | None:
    gt = str(game_type).upper()[:3]
    fn = WEEK_LABEL_MAP.get(gt)
    return fn(week) if fn else None


def compute_rest(df: pd.DataFrame) -> dict:
    last_game: dict[str, datetime] = {}
    result: dict[str, dict[str, int]] = {}

    # Sort chronologically so we process weeks in order
    df = df.sort_values('gameday')

    for _, row in df.iterrows():
        label = week_label(row['game_type'], int(row['week']))
        if label is None:
            continue
        if label not in result:
            result[label] = {}

        game_date = row['gameday']
        for side in ('away', 'home'):
            team = row[f'{side}_team']
            if pd.isna(team):
                continue
            team = str(team).upper()
            if team not in TEAMS:
                continue
            prev = last_game.get(team)
            rest = (game_date - prev).days if prev else 7
            result[label][team] = rest
            last_game[team] = game_date

    # Fill any missing teams with 7 (shouldn't happen for complete schedules)
    for label in result:
        for t in TEAMS:
            result[label].setdefault(t, 7)

    return result


def write_module(season: int, data: dict, out_path: str) -> None:
    lines = [
        f"# schedule_rest_{season}.py",
        f"# Rest-day matrix for {season} season — generated from nflverse games.csv",
        "# days = calendar days since team's previous game (7=standard, 4=short-rest TNF, 6=MNF, 14=bye)",
        "",
        f"SCHEDULE_REST_DATA_{season} = {{",
    ]
    for label in WEEK_ORDER:
        if label not in data:
            continue
        row = data[label]
        entries = ", ".join(f"'{t}': {row.get(t, 7)}" for t in TEAMS)
        lines.append(f"    '{label}': {{{entries}}},")
    lines += ["}", ""]
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"✅ Written to {out_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_schedule_rest.py <season>")
        sys.exit(1)
    season = int(sys.argv[1])
    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', f'schedule_rest_{season}.py')
    out_path = os.path.normpath(out_path)

    df = fetch_games(season)
    if df.empty:
        print(f"❌ No games found for season {season} in nflverse data.")
        sys.exit(1)
    print(f"✅ Loaded {len(df)} games for {season}")

    rest_data = compute_rest(df)
    write_module(season, rest_data, out_path)


if __name__ == '__main__':
    main()
