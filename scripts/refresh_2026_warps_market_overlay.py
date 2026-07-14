#!/usr/bin/env python3
"""Refresh the 2026 WARPS market overlay end to end.

This wrapper is the workflow-friendly entrypoint:
- optionally fetch raw current Odds API prices
- normalize current prices into the shared odds shape
- rebuild the WARPS site overlay CSV and JSON

If no current odds source is provided, it can rebuild the fair-line-only overlay
with --fair-line-only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from build_2026_warps_market_overlay import DEFAULT_CSV, DEFAULT_JSON, DEFAULT_PRIORS, build_overlay, load_current_odds, read_csv, write_csv
from fetch_current_odds_api import DEFAULT_OUTPUT as DEFAULT_RAW_ODDS, fetch_odds
from normalize_current_market_odds import DEFAULT_OUTPUT as DEFAULT_NORMALIZED_ODDS, normalize_input, write_csv as write_odds_csv


ROOT = Path(__file__).resolve().parents[1]


def fetch_raw_odds(output: Path, api_key: str, regions: str, markets: str, odds_format: str) -> None:
    data = fetch_odds(api_key, regions, markets, odds_format)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2))
    print(json.dumps({"raw_odds": str(output), "games": len(data), "markets": markets}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh 2026 WARPS market overlay")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fetch-odds-api", action="store_true", help="Fetch raw odds from The Odds API before normalizing")
    source.add_argument("--current-odds-source", type=Path, default=None, help="Existing odds source file to normalize")
    source.add_argument("--fair-line-only", action="store_true", help="Rebuild overlay without current book prices")
    parser.add_argument("--input-format", choices=["auto", "odds-api-json", "action-csv", "normalized-csv"], default="auto")
    parser.add_argument("--preferred-book", default=None)
    parser.add_argument("--api-key", default=os.environ.get("ODDS_API_KEY"))
    parser.add_argument("--regions", default="us")
    parser.add_argument("--markets", default="spreads,h2h")
    parser.add_argument("--odds-format", default="american")
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_ODDS)
    parser.add_argument("--normalized-output", type=Path, default=DEFAULT_NORMALIZED_ODDS)
    parser.add_argument("--priors", type=Path, default=DEFAULT_PRIORS)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    current_odds_path: Path | None = None
    if args.fetch_odds_api:
        if not args.api_key:
            raise SystemExit("ODDS_API_KEY is required when --fetch-odds-api is used")
        fetch_raw_odds(args.raw_output, args.api_key, args.regions, args.markets, args.odds_format)
        rows = normalize_input(args.raw_output, "odds-api-json", args.preferred_book)
        write_odds_csv(args.normalized_output, rows)
        current_odds_path = args.normalized_output
    elif args.current_odds_source:
        rows = normalize_input(args.current_odds_source, args.input_format, args.preferred_book)
        write_odds_csv(args.normalized_output, rows)
        current_odds_path = args.normalized_output
    elif not args.fair_line_only:
        raise SystemExit("Provide --fetch-odds-api, --current-odds-source, or --fair-line-only")

    priors = read_csv(args.priors)
    current_odds = load_current_odds(current_odds_path)
    overlay_rows = build_overlay(priors, current_odds)
    write_csv(args.csv_output, overlay_rows)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(overlay_rows, indent=2))
    print(json.dumps({
        "overlay_rows": len(overlay_rows),
        "priced_rows": sum(1 for row in overlay_rows if row["status"] == "priced"),
        "normalized_odds": str(current_odds_path) if current_odds_path else None,
        "csv": str(args.csv_output),
        "json": str(args.json_output),
    }, indent=2))


if __name__ == "__main__":
    main()
