#!/usr/bin/env python3
"""Summarize recommendation trace outcomes from a replay run.

This turns the selector trace into tuning evidence: which final reasons,
aligned sources, conflicts, and pass blockers are associated with wins, losses,
and passes.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_REPLAY_ROOT = Path("data/backtests/engine_2026_1_configured")


def pct(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def add_result(summary, row):
    result = row.get("result")
    summary["plays"] += 1
    if result in {"win", "loss", "push"}:
        summary["graded"] += 1
    if result == "win":
        summary["wins"] += 1
    elif result == "loss":
        summary["losses"] += 1
    elif result == "push":
        summary["pushes"] += 1
    summary["margin_sum"] += float(row.get("margin_to_line") or 0)


def finish_summary(summary):
    decisions = summary["wins"] + summary["losses"]
    summary["win_rate"] = pct(summary["wins"], decisions)
    summary["avg_margin_to_line"] = round(summary["margin_sum"] / summary["graded"], 3) if summary["graded"] else None
    del summary["margin_sum"]
    return summary


def summary_bucket():
    return {
        "plays": 0,
        "graded": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "margin_sum": 0.0,
    }


def split_values(value):
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def threshold_status(candidate):
    if not candidate:
        return "missing candidate"
    if candidate.get("blocked"):
        blockers = candidate.get("blockers") or []
        return ";".join(str(blocker) for blocker in blockers) or "blocked"
    if candidate.get("cleared_threshold"):
        return "cleared threshold"
    return "missed threshold"


def load_pick_results(replay_root):
    path = Path(replay_root) / "pick_results.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing pick result rows: {path}")
    with path.open() as f:
        return list(csv.DictReader(f))


def iter_pass_traces(replay_root, stage):
    pattern = f"week*/{stage}/week*_analytics.json"
    for path in sorted(Path(replay_root).glob(pattern)):
        week_match = re.search(r"week(\d+)", path.name)
        week = int(week_match.group(1)) if week_match else None
        for game in json.loads(path.read_text()):
            meta = game.get("pick_metadata") or {}
            if meta.get("market") not in (None, "none"):
                continue
            trace = game.get("recommendation_trace") or meta.get("trace") or {}
            final = trace.get("final_decision") or {}
            candidates = trace.get("market_candidates") or {}
            spread = candidates.get("spread") or {}
            total = candidates.get("total") or {}
            yield {
                "week": week,
                "matchup": game.get("matchup", ""),
                "classification": game.get("classification", ""),
                "data_quality_status": (game.get("data_quality") or {}).get("status", ""),
                "final_reason": final.get("reason", ""),
                "spread_side": spread.get("side", ""),
                "spread_score": spread.get("score", ""),
                "spread_threshold": spread.get("threshold", ""),
                "spread_blockers": ";".join(str(item) for item in spread.get("blockers", [])),
                "spread_threshold_status": threshold_status(spread),
                "spread_conflicts": ";".join(str(item.get("source", "")) for item in spread.get("conflicts", [])),
                "total_side": total.get("side", ""),
                "total_score": total.get("score", ""),
                "total_threshold": total.get("threshold", ""),
                "total_blockers": ";".join(str(item) for item in total.get("blockers", [])),
                "total_threshold_status": threshold_status(total),
                "total_conflicts": ";".join(str(item.get("source", "")) for item in total.get("conflicts", [])),
            }


def grouped_rows(rows, dimensions):
    buckets = defaultdict(summary_bucket)
    for row in rows:
        for dimension in dimensions:
            values = split_values(row.get(dimension)) if dimension.endswith("_sources") else [row.get(dimension, "")]
            if not values:
                values = [""]
            for value in values:
                key = (dimension, value or "NONE")
                add_result(buckets[key], row)

    output = []
    for (dimension, value), summary in sorted(buckets.items()):
        item = {"dimension": dimension, "value": value}
        item.update(finish_summary(summary))
        output.append(item)
    return output


def pass_group_rows(pass_rows):
    buckets = defaultdict(lambda: {"passes": 0})
    dimensions = [
        "final_reason",
        "spread_blockers",
        "spread_threshold_status",
        "spread_conflicts",
        "total_blockers",
        "total_threshold_status",
        "total_conflicts",
        "data_quality_status",
    ]
    for row in pass_rows:
        for dimension in dimensions:
            values = split_values(row.get(dimension)) or [row.get(dimension, "") or "NONE"]
            for value in values:
                buckets[(dimension, value)]["passes"] += 1

    output = []
    for (dimension, value), summary in sorted(buckets.items()):
        output.append({"dimension": dimension, "value": value, **summary})
    return output


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Audit replay recommendation traces")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY_ROOT))
    parser.add_argument("--stage", default="final")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    replay_root = Path(args.replay_root)
    output_dir = Path(args.output_dir) if args.output_dir else replay_root
    output_dir.mkdir(parents=True, exist_ok=True)

    pick_rows = load_pick_results(replay_root)
    pass_rows = list(iter_pass_traces(replay_root, args.stage))

    outcome_dimensions = [
        "market",
        "side",
        "trace_final_reason",
        "trace_aligned_signature",
        "trace_aligned_sources",
        "trace_conflict_sources",
        "trace_blockers",
        "data_quality_status",
    ]
    for row in pick_rows:
        aligned = split_values(row.get("trace_aligned_sources"))
        row["trace_aligned_signature"] = "+".join(sorted(aligned)) if aligned else "NONE"

    outcome_rows = grouped_rows(pick_rows, outcome_dimensions)
    pass_audit_rows = pass_group_rows(pass_rows)

    summary = {
        "replay_root": str(replay_root),
        "stage": args.stage,
        "plays": len(pick_rows),
        "passes": len(pass_rows),
        "top_outcome_groups": sorted(
            outcome_rows,
            key=lambda row: (row["dimension"], -(row.get("plays") or 0), -(row.get("wins") or 0)),
        )[:50],
        "top_pass_groups": sorted(pass_audit_rows, key=lambda row: (row["dimension"], -(row["passes"])))[:50],
    }

    write_csv(output_dir / "trace_outcome_by_reason.csv", outcome_rows)
    write_csv(output_dir / "trace_pass_audit.csv", pass_audit_rows)
    (output_dir / "trace_outcome_audit.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps({
        "plays": summary["plays"],
        "passes": summary["passes"],
        "outcome_groups": len(outcome_rows),
        "pass_groups": len(pass_audit_rows),
    }, indent=2))
    print(f"Wrote {output_dir / 'trace_outcome_by_reason.csv'}")
    print(f"Wrote {output_dir / 'trace_pass_audit.csv'}")
    print(f"Wrote {output_dir / 'trace_outcome_audit.json'}")


if __name__ == "__main__":
    main()
