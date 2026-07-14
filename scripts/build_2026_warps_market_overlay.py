#!/usr/bin/env python3
"""Build the 2026 WARPS spread/ML market overlay for the site.

By default this publishes the WARPS fair spread and moneyline prior for every
2026 game. If a current-odds CSV is supplied, it also computes book-vs-model
spread and moneyline edges in the same shape.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIORS = ROOT / "warps_2026_game_priors.csv"
DEFAULT_CSV = ROOT / "data" / "historical" / "warps_2026_market_overlay.csv"
DEFAULT_JSON = ROOT / "site" / "src" / "data" / "warpsMarketOverlay2026.json"


def parse_float(value) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        parsed = float(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def parse_int(value) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def american_implied_prob(odds: float | None) -> float | None:
    if odds is None:
        return None
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def american_profit_per_unit(odds: float | None) -> float | None:
    if odds is None:
        return None
    return odds / 100 if odds > 0 else 100 / abs(odds)


def devig_pair(left_odds: float | None, right_odds: float | None) -> tuple[float | None, float | None, float | None]:
    left = american_implied_prob(left_odds)
    right = american_implied_prob(right_odds)
    if left is None or right is None or left + right <= 0:
        return None, None, None
    return left / (left + right), right / (left + right), left + right - 1


def moneyline_ev(probability: float | None, odds: float | None) -> float | None:
    profit = american_profit_per_unit(odds)
    if probability is None or profit is None:
        return None
    return (probability * profit) - (1 - probability)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_current_odds(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    rows = read_csv(path)
    return {row.get("matchup_key", ""): row for row in rows if row.get("matchup_key")}


def value(value, digits: int = 4):
    return round(value, digits) if value is not None else ""


def build_overlay(priors: list[dict], current_odds: dict[str, dict]) -> list[dict]:
    rows = []
    for row in priors:
        key = row["matchup_key"]
        odds = current_odds.get(key, {})

        home_spread = parse_float(odds.get("home_spread_line"))
        away_spread = parse_float(odds.get("away_spread_line"))
        home_ml = parse_float(odds.get("home_moneyline"))
        away_ml = parse_float(odds.get("away_moneyline"))

        fair_home_spread = parse_float(row.get("fair_home_spread"))
        fair_away_spread = parse_float(row.get("fair_away_spread"))
        home_win_prob = parse_float(row.get("home_win_prob"))
        away_win_prob = parse_float(row.get("away_win_prob"))

        home_spread_edge = home_spread - fair_home_spread if home_spread is not None and fair_home_spread is not None else None
        away_spread_edge = away_spread - fair_away_spread if away_spread is not None and fair_away_spread is not None else None

        home_market_prob, away_market_prob, ml_hold = devig_pair(home_ml, away_ml)
        home_ml_edge = home_win_prob - home_market_prob if home_win_prob is not None and home_market_prob is not None else None
        away_ml_edge = away_win_prob - away_market_prob if away_win_prob is not None and away_market_prob is not None else None

        spread_side = ""
        spread_team = ""
        spread_edge = None
        if home_spread_edge is not None and away_spread_edge is not None:
            if home_spread_edge >= away_spread_edge:
                spread_side = "HOME"
                spread_team = row["home_tla"]
                spread_edge = home_spread_edge
            else:
                spread_side = "AWAY"
                spread_team = row["away_tla"]
                spread_edge = away_spread_edge

        ml_side = ""
        ml_team = ""
        ml_edge = None
        ml_ev = None
        if home_ml_edge is not None and away_ml_edge is not None:
            if home_ml_edge >= away_ml_edge:
                ml_side = "HOME"
                ml_team = row["home_tla"]
                ml_edge = home_ml_edge
                ml_ev = moneyline_ev(home_win_prob, home_ml)
            else:
                ml_side = "AWAY"
                ml_team = row["away_tla"]
                ml_edge = away_ml_edge
                ml_ev = moneyline_ev(away_win_prob, away_ml)

        has_market = bool(odds)
        rows.append({
            "season": parse_int(row.get("season")),
            "week": parse_int(row.get("week")),
            "matchup_key": key,
            "game_date": row.get("game_date") or "",
            "game_day": row.get("game_day") or "",
            "away_tla": row.get("away_tla") or "",
            "home_tla": row.get("home_tla") or "",
            "away_warps_wins": parse_float(row.get("away_warps_wins")),
            "home_warps_wins": parse_float(row.get("home_warps_wins")),
            "fair_home_spread": fair_home_spread,
            "fair_away_spread": fair_away_spread,
            "home_win_prob": home_win_prob,
            "away_win_prob": away_win_prob,
            "home_fair_moneyline": row.get("home_fair_moneyline") or "",
            "away_fair_moneyline": row.get("away_fair_moneyline") or "",
            "market_home_spread": value(home_spread, 2),
            "market_away_spread": value(away_spread, 2),
            "market_home_moneyline": value(home_ml, 0),
            "market_away_moneyline": value(away_ml, 0),
            "home_spread_edge": value(home_spread_edge, 3),
            "away_spread_edge": value(away_spread_edge, 3),
            "spread_overlay_side": spread_side,
            "spread_overlay_team": spread_team,
            "spread_overlay_edge_points": value(spread_edge, 3),
            "home_ml_no_vig_prob": value(home_market_prob, 4),
            "away_ml_no_vig_prob": value(away_market_prob, 4),
            "moneyline_hold": value(ml_hold, 4),
            "home_ml_edge": value(home_ml_edge, 4),
            "away_ml_edge": value(away_ml_edge, 4),
            "ml_overlay_side": ml_side,
            "ml_overlay_team": ml_team,
            "ml_overlay_edge_prob": value(ml_edge, 4),
            "ml_overlay_ev": value(ml_ev, 4),
            "status": "priced" if has_market else "fair_line_only",
            "recommendation_policy": "overlay_only_until_weekly_engine_confirmation",
            "source": "WARPS v2.3 game prior" + (" + supplied current odds" if has_market else ""),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2026 WARPS market overlay")
    parser.add_argument("--priors", type=Path, default=DEFAULT_PRIORS)
    parser.add_argument("--current-odds", type=Path, default=None, help="Optional CSV keyed by matchup_key")
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    priors = read_csv(args.priors)
    current_odds = load_current_odds(args.current_odds)
    rows = build_overlay(priors, current_odds)

    write_csv(args.csv_output, rows)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(rows, indent=2))
    print(json.dumps({
        "rows": len(rows),
        "priced_rows": sum(1 for row in rows if row["status"] == "priced"),
        "csv": str(args.csv_output),
        "json": str(args.json_output),
    }, indent=2))


if __name__ == "__main__":
    main()
