#!/usr/bin/env python3
"""Audit canonical game features against available outcomes."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "historical" / "game_features.csv"
DEFAULT_OUTPUT_JSON = ROOT / "data" / "historical" / "game_feature_audit.json"
DEFAULT_OUTPUT_CSV = ROOT / "data" / "historical" / "game_feature_audit.csv"


def pct(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def add_bucket(buckets, dimension, value, row):
    key = (dimension, value or "NONE")
    bucket = buckets[key]
    bucket["games"] += 1
    winner = row.get("straight_up_winner_side")
    side_value = value in {"AWAY", "HOME"}
    if side_value and winner in {"AWAY", "HOME"}:
        bucket["decisions"] += 1
    if side_value and winner == value:
        bucket["straight_up_wins"] += 1

    best_side = row.get("best_edge_side")
    if best_side in {"AWAY", "HOME"} and side_value:
        bucket["engine_side_games"] += 1
        if best_side == value:
            bucket["engine_side_aligned"] += 1

    bet_result = row.get("bet_result")
    if bet_result in {"win", "loss", "push"}:
        bucket["graded_bets"] += 1
    if bet_result == "win":
        bucket["bet_wins"] += 1
    elif bet_result == "loss":
        bucket["bet_losses"] += 1
    elif bet_result == "push":
        bucket["bet_pushes"] += 1


def empty_bucket():
    return {
        "games": 0,
        "decisions": 0,
        "straight_up_wins": 0,
        "engine_side_games": 0,
        "engine_side_aligned": 0,
        "graded_bets": 0,
        "bet_wins": 0,
        "bet_losses": 0,
        "bet_pushes": 0,
    }


def finish_bucket(dimension, value, bucket):
    return {
        "dimension": dimension,
        "value": value,
        **bucket,
        "straight_up_hit_rate": pct(bucket["straight_up_wins"], bucket["decisions"]),
        "engine_side_alignment_rate": pct(bucket["engine_side_aligned"], bucket["engine_side_games"]),
        "bet_win_rate": pct(bucket["bet_wins"], bucket["bet_wins"] + bucket["bet_losses"]),
    }


def load_rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def audit(rows):
    buckets = defaultdict(empty_bucket)
    dimensions = [
        "pythagorean_side",
        "market_expectation_side",
        "value_gap_side",
        "overperformance_side",
        "pythagorean_pick_alignment",
        "market_expectation_pick_alignment",
        "value_gap_pick_alignment",
        "overperformance_pick_alignment",
        "best_edge_side",
        "best_edge_market",
        "spread_status",
        "total_status",
        "data_quality_status",
        "division_game",
        "expectation_sample_warning",
    ]
    for row in rows:
        if row.get("season_type") != "REG":
            continue
        for dimension in dimensions:
            add_bucket(buckets, dimension, row.get(dimension), row)

    output = [
        finish_bucket(dimension, value, bucket)
        for (dimension, value), bucket in sorted(buckets.items())
    ]
    return output


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_OUTPUT_CSV)
    args = parser.parse_args()

    rows = load_rows(args.features)
    audit_rows = audit(rows)
    summary = {
        "feature_rows": len(rows),
        "regular_rows": sum(1 for row in rows if row.get("season_type") == "REG"),
        "audit_groups": len(audit_rows),
        "top_groups": sorted(
            audit_rows,
            key=lambda row: (row["dimension"], -(row["games"] or 0), str(row["value"])),
        )[:80],
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(summary, indent=2))
    write_csv(args.csv_output, audit_rows)
    print(json.dumps({
        "feature_rows": summary["feature_rows"],
        "regular_rows": summary["regular_rows"],
        "audit_groups": summary["audit_groups"],
    }, indent=2))
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")


if __name__ == "__main__":
    main()
