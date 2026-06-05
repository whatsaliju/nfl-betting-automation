#!/usr/bin/env python3
"""Audit Pythagorean/Vegas expectation context in the matrix engine feed."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEED = ROOT / "data" / "historical" / "matrix_engine_feed.json"
DEFAULT_OUTPUT = ROOT / "data" / "historical" / "expectation_edge_audit.csv"


def signed_gap(row, key):
    value = row.get("expectation_context", {}).get(key)
    return value if value is not None else ""


def build_rows(feed):
    rows = []
    for game in feed.get("edge_board", []):
        context = game.get("expectation_context") or {}
        if game.get("season_type") != "REG":
            continue
        rows.append({
            "season": game.get("season"),
            "week": game.get("week"),
            "matchup_key": game.get("matchup_key"),
            "away_tla": game.get("away_tla"),
            "home_tla": game.get("home_tla"),
            "best_market": (game.get("best_edge") or {}).get("market"),
            "best_side": (game.get("best_edge") or {}).get("side"),
            "best_score": (game.get("best_edge") or {}).get("score"),
            "pythagorean_side": context.get("pythagorean_side"),
            "pythagorean_wins_delta": signed_gap(game, "pythagorean_wins_delta"),
            "market_expectation_side": context.get("market_expectation_side"),
            "vegas_win_total_delta": signed_gap(game, "vegas_win_total_delta"),
            "value_gap_side": context.get("value_gap_side"),
            "pythagorean_vs_vegas_delta": signed_gap(game, "pythagorean_vs_vegas_delta"),
            "overperformance_side": context.get("overperformance_side"),
            "actual_vs_pythagorean_delta": signed_gap(game, "actual_vs_pythagorean_delta"),
            "games_tracked_min": context.get("games_tracked_min"),
            "sample_warning": context.get("sample_warning"),
        })
    return rows


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "season",
        "week",
        "matchup_key",
        "away_tla",
        "home_tla",
        "best_market",
        "best_side",
        "best_score",
        "pythagorean_side",
        "pythagorean_wins_delta",
        "market_expectation_side",
        "vegas_win_total_delta",
        "value_gap_side",
        "pythagorean_vs_vegas_delta",
        "overperformance_side",
        "actual_vs_pythagorean_delta",
        "games_tracked_min",
        "sample_warning",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, default=DEFAULT_FEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    feed = json.loads(args.feed.read_text())
    rows = build_rows(feed)
    write_csv(rows, args.output)
    playable = sum(1 for row in rows if row["best_market"])
    thin = sum(1 for row in rows if row["sample_warning"])
    print(f"Wrote {args.output}")
    print(f"Rows: {len(rows)} | Playable: {playable} | Thin samples: {thin}")


if __name__ == "__main__":
    main()
