#!/usr/bin/env python3
"""Generate a consolidated NFL selector readiness report.

This report is intentionally offline. It reads replay grading, trace audit,
calibration, and walk-forward artifacts that were already generated, then writes
one JSON and one Markdown model-readiness summary.
"""

import argparse
import csv
import json
from pathlib import Path


DEFAULT_REPLAY_ROOT = Path("data/backtests/engine_2026_1_configured")


def load_json(path, default=None):
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


def pct(value):
    if value is None or value == "":
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def num(value):
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def top_rows(rows, dimension, limit=8):
    filtered = [row for row in rows if row.get("dimension") == dimension]
    return sorted(
        filtered,
        key=lambda row: (
            -int(row.get("plays") or row.get("passes") or 0),
            -float(row.get("win_rate") or 0),
        ),
    )[:limit]


def readiness_verdict(replay_summary, walk_forward_summary):
    missing = (replay_summary or {}).get("missing_results", 0) + (replay_summary or {}).get("missing_lines", 0)
    replay_wr = (replay_summary or {}).get("win_rate") or 0
    active = (walk_forward_summary or {}).get("active_policy_walk_forward") or {}
    active_wr = active.get("win_rate") or 0
    active_plays = active.get("plays") or 0

    if missing:
        return {
            "status": "BLOCKED",
            "reason": "Replay grading has missing results or market lines.",
        }
    if replay_wr >= 0.6 and active_wr >= 0.6 and active_plays >= 5:
        return {
            "status": "READY_FOR_MONITORING",
            "reason": "Replay and active-policy walk-forward both clear baseline stability checks.",
        }
    return {
        "status": "NEEDS_MORE_VALIDATION",
        "reason": "One or more stability checks did not clear the baseline.",
    }


def markdown_table(headers, rows):
    if not rows:
        return "_No rows available._"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def build_report(replay_root):
    replay_root = Path(replay_root)
    replay_summary = load_json(replay_root / "pick_results_summary.json", {})
    trace_summary = load_json(replay_root / "trace_outcome_audit.json", {})
    calibration_summary = load_json(replay_root / "selector_calibration_summary.json", {})
    walk_forward_summary = load_json(replay_root / "selector_walk_forward_summary.json", {})
    outcome_rows = load_csv(replay_root / "trace_outcome_by_reason.csv")
    pass_rows = load_csv(replay_root / "trace_pass_audit.csv")

    verdict = readiness_verdict(replay_summary, walk_forward_summary)
    active_wf = walk_forward_summary.get("active_policy_walk_forward") or {}
    optimized_wf = walk_forward_summary.get("walk_forward") or {}
    top_policies = calibration_summary.get("top_policies", [])[:5]

    report = {
        "replay_root": str(replay_root),
        "verdict": verdict,
        "replay": replay_summary,
        "walk_forward": {
            "optimized_policy": optimized_wf,
            "active_policy": walk_forward_summary.get("active_policy", {}),
            "active_policy_results": active_wf,
        },
        "calibration_top_policies": top_policies,
        "trace": {
            "plays": trace_summary.get("plays"),
            "passes": trace_summary.get("passes"),
            "markets": top_rows(outcome_rows, "market"),
            "aligned_signatures": top_rows(outcome_rows, "trace_aligned_signature"),
            "pass_reasons": top_rows(pass_rows, "final_reason"),
            "spread_pass_status": top_rows(pass_rows, "spread_threshold_status"),
            "total_pass_status": top_rows(pass_rows, "total_threshold_status"),
        },
    }
    return report


def render_markdown(report):
    replay = report["replay"]
    active = report["walk_forward"]["active_policy_results"]
    optimized = report["walk_forward"]["optimized_policy"]
    verdict = report["verdict"]

    lines = [
        "# NFL Selector Model Readiness",
        "",
        f"Status: **{verdict['status']}**",
        "",
        verdict["reason"],
        "",
        "## Replay Summary",
        "",
        markdown_table(
            ["Plays", "Wins", "Losses", "Win Rate", "Spread", "Total"],
            [[
                replay.get("plays", "n/a"),
                replay.get("wins", "n/a"),
                replay.get("losses", "n/a"),
                pct(replay.get("win_rate")),
                f"{replay.get('by_market', {}).get('spread', {}).get('wins', 'n/a')}-"
                f"{replay.get('by_market', {}).get('spread', {}).get('losses', 'n/a')}",
                f"{replay.get('by_market', {}).get('total', {}).get('wins', 'n/a')}-"
                f"{replay.get('by_market', {}).get('total', {}).get('losses', 'n/a')}",
            ]],
        ),
        "",
        "## Walk-Forward",
        "",
        markdown_table(
            ["Policy", "Plays", "Wins", "Losses", "Win Rate", "Avg Margin"],
            [
                [
                    "Active",
                    active.get("plays", "n/a"),
                    active.get("wins", "n/a"),
                    active.get("losses", "n/a"),
                    pct(active.get("win_rate")),
                    num(active.get("avg_margin_to_line")),
                ],
                [
                    "Auto-Optimized",
                    optimized.get("plays", "n/a"),
                    optimized.get("wins", "n/a"),
                    optimized.get("losses", "n/a"),
                    pct(optimized.get("win_rate")),
                    num(optimized.get("avg_margin_to_line")),
                ],
            ],
        ),
        "",
        "## Trace Outcomes",
        "",
        markdown_table(
            ["Signal Signature", "Plays", "Wins", "Losses", "Win Rate", "Avg Margin"],
            [
                [
                    row.get("value"),
                    row.get("plays"),
                    row.get("wins"),
                    row.get("losses"),
                    pct(row.get("win_rate")),
                    num(row.get("avg_margin_to_line")),
                ]
                for row in report["trace"]["aligned_signatures"]
            ],
        ),
        "",
        "## Pass Profile",
        "",
        markdown_table(
            ["Reason", "Passes"],
            [[row.get("value"), row.get("passes")] for row in report["trace"]["pass_reasons"]],
        ),
        "",
        "## Calibration Notes",
        "",
        markdown_table(
            ["Plays", "Wins", "Losses", "Win Rate", "Spread T", "Total T", "Injury Policy", "Total Policy"],
            [
                [
                    row.get("plays"),
                    row.get("wins"),
                    row.get("losses"),
                    pct(row.get("win_rate")),
                    row.get("spread_threshold"),
                    row.get("total_threshold"),
                    row.get("injury_policy"),
                    row.get("total_policy"),
                ]
                for row in report["calibration_top_policies"]
            ],
        ),
        "",
        "Interpretation: use the active policy as the current production candidate; treat auto-optimized policies as research evidence only until more weeks are available.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate consolidated selector readiness report")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY_ROOT))
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    replay_root = Path(args.replay_root)
    output_dir = Path(args.output_dir) if args.output_dir else replay_root
    output_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(replay_root)
    json_path = output_dir / "model_readiness_report.json"
    markdown_path = output_dir / "model_readiness_report.md"
    json_path.write_text(json.dumps(report, indent=2))
    markdown_path.write_text(render_markdown(report))

    print(json.dumps({
        "status": report["verdict"]["status"],
        "reason": report["verdict"]["reason"],
        "json": str(json_path),
        "markdown": str(markdown_path),
    }, indent=2))


if __name__ == "__main__":
    main()
