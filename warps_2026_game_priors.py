#!/usr/bin/env python3
"""Build WARPS-derived 2026 game priors for spreads and moneylines.

WARPS is a season win-total model. This script converts its team-strength
projections into matchup priors so the weekly engine can compare sportsbook
spread and moneyline prices against a stable preseason baseline.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import NormalDist

import pandas as pd


ROOT = Path(__file__).resolve().parent
SCHEDULES = ROOT / "site" / "src" / "data" / "seasonSchedules.json"
WARPS_SCREEN = ROOT / "warps_2026_screen_v2_3.csv"
CSV_OUTPUT = ROOT / "warps_2026_game_priors.csv"
JSON_OUTPUT = ROOT / "site" / "src" / "data" / "warpsGamePriors2026.json"

HOME_FIELD_WINS = 1.6
WIN_GAP_LOGIT_SCALE = 0.15
NFL_MARGIN_SD = 13.45


def logistic(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def probability_to_american(probability: float) -> int:
    probability = min(0.99, max(0.01, probability))
    if probability >= 0.5:
        return round(-(probability / (1 - probability)) * 100)
    return round(((1 - probability) / probability) * 100)


def format_moneyline(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def clean_opponent(value: str) -> str:
    return value.replace("@", "").strip()


def load_warps_wins() -> dict[str, float]:
    rows = pd.read_csv(WARPS_SCREEN)
    return {row.team: float(row.v23_wins) for row in rows.itertuples(index=False)}


def load_2026_games() -> list[dict]:
    payload = json.loads(SCHEDULES.read_text())
    season = payload["2026"]
    games = {}
    for team_row in season["scheduleRows"]:
        team = team_row["Team"]
        for week in season["weeks"]:
            opponent = team_row.get(f"W{week}", "")
            if not opponent or opponent == "BYE" or not opponent.startswith("@"):
                continue
            away = team
            home = clean_opponent(opponent)
            key = f"{int(week):02d}:{away}@{home}"
            games[key] = {
                "season": 2026,
                "week": int(week),
                "away_tla": away,
                "home_tla": home,
                "matchup_key": f"{away}@{home}",
                "game_date": season["gameDates"].get(str(week), {}).get(away),
                "game_day": season["gameDays"].get(str(week), {}).get(away),
            }
    return [games[key] for key in sorted(games)]


def build_priors() -> pd.DataFrame:
    wins = load_warps_wins()
    normal = NormalDist()
    rows = []
    for game in load_2026_games():
        away = game["away_tla"]
        home = game["home_tla"]
        away_wins = wins[away]
        home_wins = wins[home]
        home_strength_gap = home_wins - away_wins
        home_logit_edge = (home_strength_gap + HOME_FIELD_WINS) * WIN_GAP_LOGIT_SCALE
        home_win_prob = logistic(home_logit_edge)
        away_win_prob = 1 - home_win_prob
        expected_home_margin = normal.inv_cdf(home_win_prob) * NFL_MARGIN_SD
        fair_home_spread = -expected_home_margin
        fair_away_spread = expected_home_margin
        favorite = home if expected_home_margin > 0 else away
        favorite_spread = -abs(expected_home_margin)
        rows.append(
            {
                **game,
                "away_warps_wins": round(away_wins, 3),
                "home_warps_wins": round(home_wins, 3),
                "home_strength_gap_wins": round(home_strength_gap, 3),
                "home_field_wins": HOME_FIELD_WINS,
                "home_win_prob": round(home_win_prob, 4),
                "away_win_prob": round(away_win_prob, 4),
                "home_fair_moneyline": format_moneyline(probability_to_american(home_win_prob)),
                "away_fair_moneyline": format_moneyline(probability_to_american(away_win_prob)),
                "fair_home_spread": round(fair_home_spread, 1),
                "fair_away_spread": round(fair_away_spread, 1),
                "favorite": favorite,
                "favorite_fair_spread": round(favorite_spread, 1),
                "model": "WARPS v2.3 game prior",
                "method": "logistic((home_warps-away_warps+home_field_wins)*0.15), spread via NFL margin SD",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    priors = build_priors()
    CSV_OUTPUT.write_text(priors.to_csv(index=False, quoting=csv.QUOTE_MINIMAL))
    JSON_OUTPUT.write_text(json.dumps(priors.to_dict(orient="records"), indent=2) + "\n")
    print(f"Wrote {CSV_OUTPUT} ({len(priors)} games)")
    print(f"Wrote {JSON_OUTPUT}")
    print("\nLargest fair favorites:")
    print(
        priors.sort_values("favorite_fair_spread")
        [["week", "matchup_key", "favorite", "favorite_fair_spread", "home_win_prob", "home_fair_moneyline", "away_fair_moneyline"]]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
