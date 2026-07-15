#!/usr/bin/env python3
"""Run the historical market research stack.

By default this uses the checked-in market spine and produces:
- market-only spread/total/moneyline baselines
- WARPS game-prior spread/moneyline edge backtest

Use --rebuild-spine when a local nflverse schedules CSV is available or when
network access is intentionally allowed for the public nflverse source.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET_SPINE = ROOT / "data" / "historical" / "nfl_market_spine.csv"
DEFAULT_MARKET_SUMMARY = ROOT / "data" / "historical" / "nfl_market_spine_summary.json"
DEFAULT_BASELINE_DIR = ROOT / "data" / "backtests" / "historical_market_baselines"
DEFAULT_WARPS_DIR = ROOT / "data" / "backtests" / "warps_game_edges"


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run historical spread/total/ML research")
    parser.add_argument("--rebuild-spine", action="store_true")
    parser.add_argument("--source", default=None, help="Optional local nflverse schedules CSV or URL for spine rebuild")
    parser.add_argument("--seasons", default="2015-2025")
    parser.add_argument("--include-postseason", action="store_true", default=True)
    parser.add_argument("--market-spine", type=Path, default=DEFAULT_MARKET_SPINE)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--warps-dir", type=Path, default=DEFAULT_WARPS_DIR)
    args = parser.parse_args()

    if args.rebuild_spine:
        cmd = [
            sys.executable,
            "scripts/build_historical_market_spine.py",
            "--seasons",
            args.seasons,
            "--output",
            str(args.market_spine),
            "--summary-output",
            str(DEFAULT_MARKET_SUMMARY),
        ]
        if args.source:
            cmd.extend(["--source", args.source])
        if args.include_postseason:
            cmd.append("--include-postseason")
        run(cmd)

    run([
        sys.executable,
        "scripts/backtest_market_baselines.py",
        "--market-spine",
        str(args.market_spine),
        "--output-dir",
        str(args.baseline_dir),
    ])
    run([
        sys.executable,
        "scripts/backtest_warps_game_edges.py",
        "--market-spine",
        str(args.market_spine),
        "--output-dir",
        str(args.warps_dir),
    ])

    print(json.dumps({
        "market_spine": str(args.market_spine),
        "baseline_summary": str(args.baseline_dir / "market_baseline_summary.json"),
        "warps_summary": str(args.warps_dir / "warps_game_edge_summary.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
