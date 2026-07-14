#!/usr/bin/env python3
"""Fetch current NFL spreads and moneylines from The Odds API.

This writes the raw API response only. Normalize it with:

    python scripts/normalize_current_market_odds.py data/current_odds_api.json --input-format odds-api-json
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "current_odds_api.json"
API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"


def fetch_odds(api_key: str, regions: str, markets: str, odds_format: str) -> list[dict]:
    query = urllib.parse.urlencode({
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    })
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch current NFL odds from The Odds API")
    parser.add_argument("--api-key", default=os.environ.get("ODDS_API_KEY"))
    parser.add_argument("--regions", default="us")
    parser.add_argument("--markets", default="spreads,h2h")
    parser.add_argument("--odds-format", default="american")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("ODDS_API_KEY is required, either as env var or --api-key")

    data = fetch_odds(args.api_key, args.regions, args.markets, args.odds_format)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2))
    print(json.dumps({
        "output": str(args.output),
        "games": len(data),
        "markets": args.markets,
        "regions": args.regions,
    }, indent=2))


if __name__ == "__main__":
    main()
