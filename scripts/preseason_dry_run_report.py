#!/usr/bin/env python3
"""Offline preseason workflow readiness report.

This does not scrape live data. It verifies that PRE season-type wiring,
artifact naming, site prerequisites, and workflow hooks are in place before
we run real preseason games through the weekly engine.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nfl_common import espn_season_type, espn_week, nflverse_game_types, normalize_season_type
from builders.build_week_master_table import builder_season_type, espn_params_for, week_slug
from builders.build_matrix_engine_feed import sort_master_path


DEFAULT_JSON = ROOT / "data" / "historical" / "preseason_dry_run_report.json"
DEFAULT_MD = ROOT / "data" / "historical" / "preseason_dry_run_report.md"


def check(condition, name, detail, rows):
    rows.append({
        "name": name,
        "status": "PASS" if condition else "FAIL",
        "detail": detail,
    })


def file_contains(path, *needles):
    if not path.exists():
        return False
    text = path.read_text()
    return all(needle in text for needle in needles)


def build_report(season, week):
    rows = []
    season_type = "PRE"
    slug = week_slug(week, season_type)
    params = espn_params_for(season, week, season_type)

    check(normalize_season_type("PRE", week) == "PRE", "season type normalization", "PRE resolves to PRE", rows)
    check(nflverse_game_types("PRE") == ["PRE"], "nflverse game type", "PRE maps to nflverse PRE games", rows)
    check(espn_season_type("PRE", week) == 1, "ESPN season type", "PRE maps to ESPN seasontype=1", rows)
    check(espn_week("PRE", week) == int(week), "ESPN week", f"PRE Week {week} maps to ESPN week {week}", rows)
    check(params["seasontype"] == 1 and params["week"] == int(week), "builder ESPN params", json.dumps(params), rows)
    check(builder_season_type("PRE", week) == "PRE", "master builder season type", "builder uses PRE", rows)
    check(slug == f"PRE{week}", "preseason artifact slug", f"week {week} writes as week{slug}_master", rows)
    check(
        sort_master_path(Path(f"weekPRE{week}_master.json")) < sort_master_path(Path(f"week{week}_master.json")),
        "feed sort isolation",
        "preseason master files sort before regular-season master files",
        rows,
    )

    enhanced = ROOT / ".github" / "workflows" / "4.5_enhanced_pro_workflow.yml"
    dry_run = ROOT / ".github" / "workflows" / "12_preseason_dry_run.yml"
    contracts = ROOT / ".github" / "workflows" / "0_engine_contracts.yml"
    command = ROOT / "site" / "src" / "components" / "CommandCenterView.tsx"
    survivor = ROOT / "site" / "src" / "data" / "survivorRecommendations2026.json"
    card = ROOT / "data" / "historical" / "weekly_betting_card.json"

    check(file_contains(enhanced, "season_type", "NFL_SEASON_TYPE"), "enhanced workflow PRE env", str(enhanced), rows)
    check(file_contains(dry_run, "Preseason Engine Dry Run", "--season-type PRE"), "preseason dry-run workflow", str(dry_run), rows)
    check(file_contains(contracts, "preseason_dry_run_report.py"), "contract compile hook", str(contracts), rows)
    check(file_contains(command, "Weekly Command Center", "Live 2026 weekly feeds not active yet"), "command center readiness copy", str(command), rows)
    check(survivor.exists(), "survivor planning artifact", str(survivor), rows)
    check(card.exists(), "weekly betting card artifact", str(card), rows)

    failures = [row for row in rows if row["status"] != "PASS"]
    return {
        "season": season,
        "season_type": season_type,
        "week": int(week),
        "artifact_slug": slug,
        "status": "PASS" if not failures else "FAIL",
        "checks": rows,
        "next_live_command": (
            "python3 builders/build_week_master_table.py "
            f"--season {season} --week {week} --season-type PRE"
        ),
    }


def markdown(payload):
    lines = [
        "# Preseason Dry Run Readiness",
        "",
        f"- Season: {payload['season']}",
        f"- Season type: {payload['season_type']}",
        f"- Week: {payload['week']}",
        f"- Artifact slug: `{payload['artifact_slug']}`",
        f"- Status: **{payload['status']}**",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for row in payload["checks"]:
        lines.append(f"| {row['name']} | {row['status']} | {row['detail']} |")
    lines.extend([
        "",
        "## Next Live Command",
        "",
        f"`{payload['next_live_command']}`",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build_report(args.season, args.week)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2) + "\n")
    args.md_output.write_text(markdown(payload))
    print(json.dumps({"status": payload["status"], "checks": len(payload["checks"])}, indent=2))
    if payload["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
