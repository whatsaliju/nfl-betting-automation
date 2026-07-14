#!/usr/bin/env python3
"""Summarize selector replay coverage and expansion blockers."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIGURED = ROOT / "data" / "backtests" / "engine_2026_1_configured"
DEFAULT_ATTEMPT = ROOT / "data" / "backtests" / "engine_2026_1_full2025_attempt"
DEFAULT_JSON = DEFAULT_CONFIGURED / "backtest_coverage_report.json"
DEFAULT_MD = DEFAULT_CONFIGURED / "backtest_coverage_report.md"


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def load_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def configured_summary(root):
    rows = load_json(Path(root) / "summary.json", [])
    pick_results = load_csv(Path(root) / "pick_results.csv")
    graded = [row for row in pick_results if row.get("result") in {"win", "loss", "push"}]
    wins = sum(1 for row in graded if row.get("result") == "win")
    losses = sum(1 for row in graded if row.get("result") == "loss")
    pushes = sum(1 for row in graded if row.get("result") == "push")
    decisions = wins + losses
    return {
        "root": str(root),
        "weeks": [row.get("week") for row in rows],
        "week_count": len(rows),
        "games": sum(int(row.get("games") or 0) for row in rows),
        "plays": sum(int(row.get("plays") or 0) for row in rows),
        "graded": len(graded),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
        "warnings": [
            {"week": row.get("week"), "warnings": row.get("quality_warnings") or []}
            for row in rows
            if row.get("quality_warnings")
        ],
    }


def attempt_summary(root):
    rows = load_json(Path(root) / "summary.json", [])
    pick_summary = load_json(Path(root) / "pick_results_summary.json", {})
    skipped = []
    failed = []
    completed = []
    for row in rows:
        if row.get("returncode") is None:
            skipped.append(row)
        elif row.get("returncode") == 0:
            completed.append(row)
        else:
            failed.append(row)
    return {
        "root": str(root),
        "weeks_requested": [row.get("week") for row in rows],
        "completed_weeks": [row.get("week") for row in completed],
        "skipped_weeks": [
            {
                "week": row.get("week"),
                "reason": row.get("error") or "; ".join(row.get("quality_warnings") or []),
            }
            for row in skipped
        ],
        "failed_weeks": [
            {
                "week": row.get("week"),
                "reason": row.get("error"),
                "source_status": row.get("source_status"),
            }
            for row in failed
        ],
        "graded": pick_summary.get("graded"),
        "wins": pick_summary.get("wins"),
        "losses": pick_summary.get("losses"),
        "pushes": pick_summary.get("pushes"),
        "win_rate": pick_summary.get("win_rate"),
        "by_market": pick_summary.get("by_market") or {},
    }


def readiness_verdict(configured, attempt):
    blockers = []
    if attempt.get("skipped_weeks"):
        blockers.append("Weeks 1-9 are missing weekly query/referee input files.")
    if attempt.get("failed_weeks"):
        blockers.append("Fresh full-season replay still has failed weeks; inspect attempt summary for week-level errors.")
    if configured["week_count"] >= 8 and configured["graded"] >= 18:
        status = "WEEKLY_PIPELINE_READY_MONITOR"
        recommendation = (
            "Current weekly workflows are close to operational for 2026, but full-season historical selector "
            "validation remains blocked until earlier weekly query/referee files are restored or regenerated."
        )
    else:
        status = "NOT_READY"
        recommendation = "Replay sample is too small; expand validated weekly artifacts before relying on automated weekly outputs."
    return {
        "status": status,
        "recommendation": recommendation,
        "blockers": blockers,
    }


def build(configured_root, attempt_root):
    configured = configured_summary(configured_root)
    attempt = attempt_summary(attempt_root)
    return {
        "configured_replay": configured,
        "full_2025_attempt": attempt,
        "verdict": readiness_verdict(configured, attempt),
        "next_steps": [
            "Restore or regenerate week1-week9 query/referee files before rerunning full 2025 selector replay.",
            "Run one 2026 preseason dry run after current 2026 data sources are available.",
            "Keep WARPS, market router, and CLV gates in monitor mode until the graded selected-bet sample grows.",
        ],
    }


def markdown(payload):
    configured = payload["configured_replay"]
    attempt = payload["full_2025_attempt"]
    verdict = payload["verdict"]
    lines = [
        "# Backtest Coverage Report",
        "",
        "## Current Valid Replay",
        "",
        f"- Weeks: {configured['weeks']}",
        f"- Games: {configured['games']}",
        f"- Engine plays: {configured['plays']}",
        f"- Graded selected bets: {configured['graded']}",
        f"- Record: {configured['wins']}-{configured['losses']}-{configured['pushes']}",
        f"- Win rate: {configured['win_rate']}",
        "",
        "## Full 2025 Replay Attempt",
        "",
        f"- Requested weeks: {attempt['weeks_requested']}",
        f"- Completed weeks: {attempt['completed_weeks']}",
        f"- Skipped weeks: {[row['week'] for row in attempt['skipped_weeks']]}",
        f"- Failed weeks: {[row['week'] for row in attempt['failed_weeks']]}",
        f"- Graded selected bets: {attempt.get('graded')}",
        f"- Record: {attempt.get('wins')}-{attempt.get('losses')}-{attempt.get('pushes')}",
        f"- Win rate: {attempt.get('win_rate')}",
        "",
        "## Verdict",
        "",
        f"- Status: {verdict['status']}",
        f"- Recommendation: {verdict['recommendation']}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in verdict["blockers"])
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {item}" for item in payload["next_steps"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configured-root", type=Path, default=DEFAULT_CONFIGURED)
    parser.add_argument("--attempt-root", type=Path, default=DEFAULT_ATTEMPT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build(args.configured_root, args.attempt_root)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2))
    args.md_output.write_text(markdown(payload))
    print(json.dumps({
        "status": payload["verdict"]["status"],
        "configured_weeks": payload["configured_replay"]["weeks"],
        "graded": payload["configured_replay"]["graded"],
        "blockers": payload["verdict"]["blockers"],
    }, indent=2))
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.md_output}")


if __name__ == "__main__":
    main()
