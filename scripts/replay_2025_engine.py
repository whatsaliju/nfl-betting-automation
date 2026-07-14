#!/usr/bin/env python3
"""
Replay the betting engine against stored 2025 weeks without live scraping.

The repository stores historical scraper outputs as dated root-level CSVs:
data/action_all_markets_YYYY-MM-DD_.csv, data/action_injuries_..., etc.
This script chooses the closest historical files for each week/stage, generates
week-specific nflverse referee trends into the backtest folder, and runs the
current analyzer with exact-file environment variables.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nflverse_referee_trends import build_referee_trends
from analyzers.nfl_common import normalize_season_type, reference_time_for_stage, target_date_for_stage

DATA = ROOT / "data"
BACKTEST_ROOT = DATA / "backtests"


def parse_date_from_name(path: Path):
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d").date()


def choose_dated_file(pattern: str, target: date):
    candidates = []
    for path in DATA.glob(pattern):
        found = parse_date_from_name(path)
        if found:
            candidates.append((found, path))
    if not candidates:
        return None

    before = [(found, path) for found, path in candidates if found <= target]
    if before:
        return str(max(before, key=lambda item: item[0])[1])
    return str(min(candidates, key=lambda item: item[0])[1])


def choose_rotowire_file(week: int, target: date, max_generic_age_days: int = 4):
    specific = []
    generic = []
    for path in DATA.glob(f"rotowire_lineups_week{week}_*.csv"):
        found = parse_date_from_name(path)
        if found:
            specific.append((found, path))
    for path in DATA.glob("rotowire_lineups_*.csv"):
        found = parse_date_from_name(path)
        if found:
            generic.append((found, path))

    candidates = specific
    if not candidates:
        generic = [
            (found, path)
            for found, path in generic
            if 0 <= (target - found).days <= max_generic_age_days
        ]
        candidates = generic
    if not candidates:
        return None
    before = [(found, path) for found, path in candidates if found <= target]
    if before:
        return str(max(before, key=lambda item: item[0])[1])
    return str(min(candidates, key=lambda item: item[0])[1])


def summarize_output(week: int, output_dir: Path):
    json_path = output_dir / f"week{week}_analytics.json"
    manifest_path = output_dir / f"week{week}_run_manifest.json"
    if not json_path.exists():
        return {"games": 0, "plays": 0, "passes": 0, "error": "missing analytics json"}

    with open(json_path) as f:
        games = json.load(f)
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    pick_counts = {}
    tier_counts = {}
    data_quality = games[0].get("data_quality", {}) if games else {}
    for game in games:
        market = game.get("pick_metadata", {}).get("market", "none")
        pick_counts[market] = pick_counts.get(market, 0) + 1
        tier = game.get("classification", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    return {
        "games": len(games),
        "plays": sum(v for k, v in pick_counts.items() if k != "none"),
        "passes": pick_counts.get("none", 0),
        "pick_counts": pick_counts,
        "tier_counts": tier_counts,
        "source_status": data_quality.get("status", ""),
        "unsafe_sources": ",".join(data_quality.get("unsafe_sources", [])),
        "degraded_sources": ",".join(data_quality.get("degraded_sources", [])),
        "source_warnings": "; ".join(data_quality.get("critical_warnings", []) + data_quality.get("warnings", [])),
        "manifest_path": str(manifest_path) if manifest_path.exists() else "",
        "manifest_model_version": manifest.get("model_version", ""),
        "manifest_reference_time": manifest.get("analysis_reference_time", ""),
        "manifest_play_count": manifest.get("play_count", ""),
    }


def replay_week(season: int, week: int, stage: str, output_root: Path, season_type: str = None):
    season_type = normalize_season_type(season_type, week)
    target = target_date_for_stage(season, week, stage, season_type)
    reference_time = reference_time_for_stage(season, week, stage, season_type)
    week_output = output_root / f"week{week}" / stage
    week_output.mkdir(parents=True, exist_ok=True)

    referee_trends = week_output / "referee_trends.csv"
    try:
        build_referee_trends(week, output=str(referee_trends), write_week_copy=False, season_type=season_type)
    except FileNotFoundError as exc:
        summary = {
            "week": week,
            "season_type": season_type,
            "stage": stage,
            "target_date": target.isoformat(),
            "reference_time": reference_time.isoformat(),
            "returncode": None,
            "games": 0,
            "plays": 0,
            "passes": 0,
            "source_status": "MISSING_INPUT",
            "quality_warnings": [str(exc)],
            "error": str(exc),
            "output_dir": str(week_output),
        }
        (week_output / "skip_reason.txt").write_text(str(exc))
        print(f"\n=== Skipping {season_type} Week {week} {stage} ({target}) ===")
        print(str(exc))
        return summary

    env = os.environ.copy()
    env.update({
        "NFL_SEASON": str(season),
        "NFL_SEASON_TYPE": season_type,
        "SKIP_PERFORMANCE_TRACKING": "1",
        "ANALYZER_OUTPUT_DIR": str(week_output),
        "ANALYZER_TARGET_DATE": target.isoformat(),
        "ANALYZER_REFERENCE_TIME": reference_time.isoformat(),
        "REFEREE_TRENDS_FILE": str(referee_trends),
    })

    exact_files = {
        "ACTION_MARKETS_FILE": choose_dated_file("action_all_markets_*.csv", target),
        "ACTION_INJURIES_FILE": choose_dated_file("action_injuries_*.csv", target),
        "ACTION_WEATHER_FILE": choose_dated_file("action_weather_*.csv", target),
        "ROTOWIRE_FILE": choose_rotowire_file(week, target),
    }
    quality_warnings = []
    if not exact_files["ROTOWIRE_FILE"]:
        quality_warnings.append(f"missing week-specific RotoWire file for week {week}")
    elif f"week{week}_" not in Path(exact_files["ROTOWIRE_FILE"]).name:
        quality_warnings.append(f"using generic dated RotoWire file for week {week}")
    for key, value in exact_files.items():
        env[key] = value or ""

    print(f"\n=== Replaying {season_type} Week {week} {stage} ({target}) ===")
    for key, value in exact_files.items():
        print(f"{key}: {value or 'MISSING'}")

    process = subprocess.run(
        ["python3", "-m", "analyzers.nfl_pro_analyzer", str(week)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    (week_output / "stdout.log").write_text(process.stdout)
    (week_output / "stderr.log").write_text(process.stderr)

    summary = summarize_output(week, week_output)
    summary.update({
        "week": week,
        "season_type": season_type,
        "stage": stage,
        "target_date": target.isoformat(),
        "reference_time": reference_time.isoformat(),
        "returncode": process.returncode,
        "quality_warnings": quality_warnings,
        **exact_files,
        "output_dir": str(week_output),
    })

    if process.returncode != 0:
        print(process.stdout[-2000:])
        print(process.stderr[-2000:])
        summary["error"] = f"analyzer exited {process.returncode}"
    else:
        print(f"Replay complete: {summary['games']} games, {summary['plays']} plays, {summary['passes']} passes")

    return summary


def write_summary(rows, output_root: Path):
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "summary.json"
    csv_path = output_root / "summary.csv"
    json_path.write_text(json.dumps(rows, indent=2, default=str))

    if rows:
        fieldnames = sorted({key for row in rows for key in row.keys()})
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"\nWrote {json_path}")
    print(f"Wrote {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Replay 2025 weeks with the current analyzer")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--weeks", default="11-18", help="Comma/range list, e.g. 11-18 or 16,17")
    parser.add_argument("--season-type", default=None, help="REG or POST. Defaults to POST for weeks above 18.")
    parser.add_argument("--stage", default="final", choices=["initial", "update", "lock", "final"])
    parser.add_argument("--output-root", default=str(BACKTEST_ROOT / "engine_2026_1"))
    args = parser.parse_args()

    weeks = []
    for part in args.weeks.split(","):
        part = part.strip()
        if "-" in part:
            start, end = [int(x) for x in part.split("-", 1)]
            weeks.extend(range(start, end + 1))
        elif part:
            weeks.append(int(part))

    output_root = Path(args.output_root)
    rows = [replay_week(args.season, week, args.stage, output_root, args.season_type) for week in weeks]
    write_summary(rows, output_root)


if __name__ == "__main__":
    main()
