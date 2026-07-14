#!/usr/bin/env python3
"""Build a clean historical NFL market spine from nflverse schedules.

The weekly engine, WARPS matchup priors, and future live odds adapters should
all join against this shape when evaluating spread, moneyline, and total edges.
One row represents one played NFL game with market lines, no-vig probabilities,
and outcome grading for both teams/sides.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
DEFAULT_CACHE = ROOT / "data" / "historical" / "nflverse_games.csv"
TMP_CACHE = Path("/private/tmp/nflverse_games.csv")
DEFAULT_OUTPUT = ROOT / "data" / "historical" / "nfl_market_spine.csv"
DEFAULT_SUMMARY = ROOT / "data" / "historical" / "nfl_market_spine_summary.json"

TEAM_ALIASES = {
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "WSH": "WAS",
}


def canonical_team(team: str | None) -> str:
    value = str(team or "").strip()
    return TEAM_ALIASES.get(value, value)


def parse_float(value) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def parse_int(value) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def american_implied_prob(odds: float | None) -> float | None:
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def american_profit_per_unit(odds: float | None) -> float | None:
    if odds is None:
        return None
    return odds / 100 if odds > 0 else 100 / abs(odds)


def devig_pair(left_odds: float | None, right_odds: float | None) -> tuple[float | None, float | None, float | None]:
    left_raw = american_implied_prob(left_odds)
    right_raw = american_implied_prob(right_odds)
    if left_raw is None or right_raw is None or left_raw + right_raw <= 0:
        return None, None, None
    hold = left_raw + right_raw - 1
    return left_raw / (left_raw + right_raw), right_raw / (left_raw + right_raw), hold


def result_label(margin: float | None) -> str:
    if margin is None:
        return "missing"
    if margin > 0:
        return "win"
    if margin < 0:
        return "loss"
    return "push"


def read_games(source: str | Path) -> list[dict]:
    source_text = str(source)
    if source_text.startswith(("http://", "https://")):
        with urlopen(source_text, timeout=45) as response:
            text = response.read().decode("utf-8")
        return list(csv.DictReader(text.splitlines()))
    with Path(source).open(newline="") as f:
        return list(csv.DictReader(f))


def resolve_source(source_arg: str | None) -> str | Path:
    if source_arg:
        return source_arg
    if DEFAULT_CACHE.exists():
        return DEFAULT_CACHE
    if TMP_CACHE.exists():
        return TMP_CACHE
    return SCHEDULES_URL


def parse_seasons(value: str) -> set[int]:
    seasons: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            seasons.update(range(int(start), int(end) + 1))
        else:
            seasons.add(int(part))
    return seasons


def wanted_row(row: dict, seasons: set[int], include_postseason: bool) -> bool:
    season = parse_int(row.get("season"))
    if season not in seasons:
        return False
    game_type = row.get("game_type")
    if game_type == "REG":
        return True
    return include_postseason and game_type in {"WC", "DIV", "CON", "SB"}


def build_row(row: dict) -> dict | None:
    away_score = parse_float(row.get("away_score"))
    home_score = parse_float(row.get("home_score"))
    if away_score is None or home_score is None:
        return None

    away = canonical_team(row.get("away_team"))
    home = canonical_team(row.get("home_team"))
    away_margin = away_score - home_score
    home_margin = -away_margin
    total_points = away_score + home_score

    # nflverse spread_line is from the away-team perspective:
    # DAL at PHI with DAL +8.5 is stored as spread_line=8.5.
    away_spread_line = parse_float(row.get("spread_line"))
    home_spread_line = -away_spread_line if away_spread_line is not None else None
    away_cover_margin = away_margin + away_spread_line if away_spread_line is not None else None
    home_cover_margin = home_margin + home_spread_line if home_spread_line is not None else None

    total_line = parse_float(row.get("total_line"))
    over_margin = total_points - total_line if total_line is not None else None
    under_margin = -over_margin if over_margin is not None else None

    away_ml_result = "win" if away_margin > 0 else "loss" if away_margin < 0 else "push"
    home_ml_result = "win" if home_margin > 0 else "loss" if home_margin < 0 else "push"

    away_ml = parse_float(row.get("away_moneyline"))
    home_ml = parse_float(row.get("home_moneyline"))
    away_ml_prob, home_ml_prob, ml_hold = devig_pair(away_ml, home_ml)

    away_spread_odds = parse_float(row.get("away_spread_odds"))
    home_spread_odds = parse_float(row.get("home_spread_odds"))
    away_spread_prob, home_spread_prob, spread_hold = devig_pair(away_spread_odds, home_spread_odds)

    over_odds = parse_float(row.get("over_odds"))
    under_odds = parse_float(row.get("under_odds"))
    over_prob, under_prob, total_hold = devig_pair(over_odds, under_odds)

    if away_spread_line is None:
        favorite_side = ""
        favorite_team = ""
        favorite_spread = ""
    elif away_spread_line < 0:
        favorite_side = "AWAY"
        favorite_team = away
        favorite_spread = away_spread_line
    elif away_spread_line > 0:
        favorite_side = "HOME"
        favorite_team = home
        favorite_spread = home_spread_line
    else:
        favorite_side = "PICK"
        favorite_team = "PICK"
        favorite_spread = 0.0

    away_cover_result = result_label(away_cover_margin)
    home_cover_result = result_label(home_cover_margin)
    favorite_cover_result = ""
    underdog_cover_result = ""
    if favorite_side == "AWAY":
        favorite_cover_result = away_cover_result
        underdog_cover_result = home_cover_result
    elif favorite_side == "HOME":
        favorite_cover_result = home_cover_result
        underdog_cover_result = away_cover_result
    elif favorite_side == "PICK":
        favorite_cover_result = "push" if away_cover_result == "push" else "pick"
        underdog_cover_result = favorite_cover_result

    return {
        "season": parse_int(row.get("season")),
        "game_type": row.get("game_type") or "",
        "week": parse_int(row.get("week")),
        "game_id": row.get("game_id") or "",
        "gameday": row.get("gameday") or "",
        "weekday": row.get("weekday") or "",
        "gametime": row.get("gametime") or "",
        "matchup_key": f"{away}@{home}",
        "away_team": away,
        "home_team": home,
        "away_score": int(away_score),
        "home_score": int(home_score),
        "away_margin": int(away_margin),
        "home_margin": int(home_margin),
        "total_points": int(total_points),
        "away_moneyline": away_ml,
        "home_moneyline": home_ml,
        "away_ml_no_vig_prob": round(away_ml_prob, 4) if away_ml_prob is not None else "",
        "home_ml_no_vig_prob": round(home_ml_prob, 4) if home_ml_prob is not None else "",
        "moneyline_hold": round(ml_hold, 4) if ml_hold is not None else "",
        "away_ml_profit_per_unit": round(american_profit_per_unit(away_ml), 4) if away_ml is not None else "",
        "home_ml_profit_per_unit": round(american_profit_per_unit(home_ml), 4) if home_ml is not None else "",
        "away_ml_result": away_ml_result,
        "home_ml_result": home_ml_result,
        "straight_up_winner_side": "AWAY" if away_margin > 0 else "HOME" if home_margin > 0 else "PUSH",
        "straight_up_winner_team": away if away_margin > 0 else home if home_margin > 0 else "PUSH",
        "away_spread_line": away_spread_line,
        "home_spread_line": home_spread_line,
        "away_spread_odds": away_spread_odds,
        "home_spread_odds": home_spread_odds,
        "away_spread_no_vig_prob": round(away_spread_prob, 4) if away_spread_prob is not None else "",
        "home_spread_no_vig_prob": round(home_spread_prob, 4) if home_spread_prob is not None else "",
        "spread_hold": round(spread_hold, 4) if spread_hold is not None else "",
        "away_cover_margin": round(away_cover_margin, 2) if away_cover_margin is not None else "",
        "home_cover_margin": round(home_cover_margin, 2) if home_cover_margin is not None else "",
        "away_cover_result": away_cover_result,
        "home_cover_result": home_cover_result,
        "favorite_side": favorite_side,
        "favorite_team": favorite_team,
        "favorite_spread": favorite_spread,
        "favorite_cover_result": favorite_cover_result,
        "underdog_cover_result": underdog_cover_result,
        "total_line": total_line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "over_no_vig_prob": round(over_prob, 4) if over_prob is not None else "",
        "under_no_vig_prob": round(under_prob, 4) if under_prob is not None else "",
        "total_hold": round(total_hold, 4) if total_hold is not None else "",
        "over_margin": round(over_margin, 2) if over_margin is not None else "",
        "under_margin": round(under_margin, 2) if under_margin is not None else "",
        "over_result": result_label(over_margin),
        "under_result": result_label(under_margin),
        "total_result": "OVER" if over_margin and over_margin > 0 else "UNDER" if over_margin and over_margin < 0 else "PUSH" if over_margin == 0 else "missing",
        "div_game": row.get("div_game") or "",
        "roof": row.get("roof") or "",
        "surface": row.get("surface") or "",
        "temp": parse_float(row.get("temp")) if parse_float(row.get("temp")) is not None else "",
        "wind": parse_float(row.get("wind")) if parse_float(row.get("wind")) is not None else "",
        "away_rest": parse_int(row.get("away_rest")) if parse_int(row.get("away_rest")) is not None else "",
        "home_rest": parse_int(row.get("home_rest")) if parse_int(row.get("home_rest")) is not None else "",
        "away_qb_name": row.get("away_qb_name") or "",
        "home_qb_name": row.get("home_qb_name") or "",
        "away_coach": row.get("away_coach") or "",
        "home_coach": row.get("home_coach") or "",
        "referee": row.get("referee") or "",
        "stadium": row.get("stadium") or "",
        "source": "nflverse schedules",
        "source_url": SCHEDULES_URL,
        "spread_line_convention": "away_team_perspective",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_summary(rows: list[dict], source: str | Path, seasons: set[int], include_postseason: bool) -> dict:
    by_game_type = Counter(row["game_type"] for row in rows)
    by_season = Counter(row["season"] for row in rows)
    return {
        "source": str(source),
        "source_url": SCHEDULES_URL,
        "seasons": sorted(seasons),
        "include_postseason": include_postseason,
        "rows": len(rows),
        "by_game_type": dict(sorted(by_game_type.items())),
        "by_season": dict(sorted(by_season.items())),
        "coverage": {
            "moneyline_rows": sum(1 for row in rows if row["away_moneyline"] not in (None, "")),
            "spread_rows": sum(1 for row in rows if row["away_spread_line"] not in (None, "")),
            "spread_odds_rows": sum(1 for row in rows if row["away_spread_odds"] not in (None, "")),
            "total_rows": sum(1 for row in rows if row["total_line"] not in (None, "")),
            "total_odds_rows": sum(1 for row in rows if row["over_odds"] not in (None, "")),
        },
        "field_notes": {
            "spread_line_convention": "nflverse spread_line is converted to away_spread_line/home_spread_line; original convention is away-team perspective.",
            "moneyline_probabilities": "No-vig probabilities are normalized from both listed American prices when available.",
            "grading": "Results are from the perspective of a one-unit bet on each side, before any model filtering.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build historical NFL spread/ML/total market spine")
    parser.add_argument("--source", default=None, help="Local CSV path or URL. Defaults to cached nflverse, then public URL.")
    parser.add_argument("--seasons", default="2015-2025")
    parser.add_argument("--include-postseason", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    seasons = parse_seasons(args.seasons)
    source = resolve_source(args.source)
    games = read_games(source)
    rows = [build_row(row) for row in games if wanted_row(row, seasons, args.include_postseason)]
    rows = [row for row in rows if row is not None]
    rows.sort(key=lambda row: (row["season"], row["game_type"] != "REG", row["week"], row["gameday"], row["game_id"]))

    write_csv(args.output, rows)
    summary = build_summary(rows, source, seasons, args.include_postseason)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, indent=2))

    print(json.dumps({
        "output": str(args.output),
        "summary": str(args.summary_output),
        "rows": summary["rows"],
        "coverage": summary["coverage"],
    }, indent=2))


if __name__ == "__main__":
    main()
