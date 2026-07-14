#!/usr/bin/env python3
"""Normalize Action Network market CSVs for the analyzer.

Older scraper exports are already close to analyzer-ready, but lack the stable
`normalized_matchup` key. This script keeps raw market fields intact and adds
canonical join columns so historical replay and live workflows use the same
matching contract.
"""

import argparse
import csv
import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nfl_common import canonical_team, normalize_matchup_key, split_matchup


REQUIRED_RAW_COLUMNS = ["Matchup", "Market", "Line", "Bets %", "Money %"]


def load_rows(path):
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def split_safe(matchup):
    try:
        return split_matchup(matchup)
    except ValueError:
        return "", ""


def normalize_row(row):
    matchup = row.get("Matchup") or row.get("matchup") or ""
    away, home = split_safe(matchup)
    normalized = row.get("normalized_matchup") or normalize_matchup_key(matchup)
    output = dict(row)
    output["Matchup"] = matchup
    output["Market"] = row.get("Market") or row.get("market") or ""
    output["Line"] = row.get("Line") or row.get("line") or ""
    output["Bets %"] = row.get("Bets %") or row.get("bets_pct") or ""
    output["Money %"] = row.get("Money %") or row.get("money_pct") or ""
    output["Game Time"] = row.get("Game Time") or row.get("game_time") or ""
    output["normalized_matchup"] = normalized
    output["away_tla"] = canonical_team(away)
    output["home_tla"] = canonical_team(home)
    return output


def normalize(rows):
    return [normalize_row(row) for row in rows]


def missing_required_columns(rows):
    if not rows:
        return REQUIRED_RAW_COLUMNS
    fields = set(rows[0].keys())
    return [field for field in REQUIRED_RAW_COLUMNS if field not in fields]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = []
    preferred = [
        "Matchup",
        "Market",
        "Game Time",
        "Line",
        "Bets %",
        "Money %",
        "Diff",
        "Num Bets",
        "Fetched",
        "normalized_matchup",
        "away_tla",
        "home_tla",
    ]
    for field in preferred:
        if any(field in row for row in rows):
            fields.append(field)
    for row in rows:
        for field in row.keys():
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(input_path, output_path):
    rows = load_rows(input_path)
    normalized = normalize(rows)
    missing = missing_required_columns(rows)
    unique_games = sorted({row.get("normalized_matchup") for row in normalized if row.get("normalized_matchup")})
    market_counts = {}
    for row in normalized:
        market = row.get("Market") or "UNKNOWN"
        market_counts[market] = market_counts.get(market, 0) + 1
    write_csv(output_path, normalized)
    return {
        "input": str(input_path),
        "output": str(output_path),
        "rows": len(normalized),
        "games": len(unique_games),
        "market_counts": market_counts,
        "missing_raw_columns": missing,
        "status": "OK" if not missing and normalized else "WARN",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, default=None)
    args = parser.parse_args()

    summary = build(args.input, args.output)
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
