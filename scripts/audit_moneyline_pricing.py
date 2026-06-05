#!/usr/bin/env python3
"""Audit research moneyline pricing from canonical game features."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "moneyline_pricing_audit.csv"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "moneyline_pricing_audit.json"


def float_value(row, key):
    value = row.get(key)
    return float(value) if value not in (None, "") else None


def pct(wins, losses):
    return round(wins / (wins + losses), 4) if wins + losses else None


def load_rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def grade_row(row):
    side = row.get("moneyline_side")
    winner = row.get("straight_up_winner_side")
    if side not in {"AWAY", "HOME"} or winner not in {"AWAY", "HOME"}:
        return None
    return "win" if side == winner else "loss"


def summarize(rows, label, predicate):
    selected = [row for row in rows if predicate(row)]
    graded = [(row, grade_row(row)) for row in selected]
    graded = [(row, result) for row, result in graded if result]
    wins = sum(1 for _, result in graded if result == "win")
    losses = sum(1 for _, result in graded if result == "loss")
    avg_ev = None
    evs = [float_value(row, "moneyline_selected_ev") for row, _ in graded]
    evs = [value for value in evs if value is not None]
    if evs:
        avg_ev = round(sum(evs) / len(evs), 4)
    return {
        "bucket": label,
        "candidates": len(selected),
        "graded": len(graded),
        "wins": wins,
        "losses": losses,
        "win_rate": pct(wins, losses),
        "avg_selected_ev": avg_ev,
    }


def audit(rows):
    buckets = [
        summarize(rows, "all_priced", lambda row: row.get("moneyline_side") in {"AWAY", "HOME"}),
        summarize(rows, "research_thin_sample", lambda row: row.get("moneyline_status") == "research_thin_sample"),
        summarize(rows, "positive_ev_5pct", lambda row: (float_value(row, "moneyline_selected_ev") or -999) >= 0.05),
        summarize(rows, "positive_ev_10pct", lambda row: (float_value(row, "moneyline_selected_ev") or -999) >= 0.10),
        summarize(rows, "positive_ev_20pct", lambda row: (float_value(row, "moneyline_selected_ev") or -999) >= 0.20),
    ]

    by_side = defaultdict(list)
    for row in rows:
        by_side[row.get("moneyline_side") or "NONE"].append(row)
    for side, side_rows in sorted(by_side.items()):
        buckets.append(summarize(side_rows, f"side_{side}", lambda row: True))
    return buckets


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["bucket", "candidates", "graded", "wins", "losses", "win_rate", "avg_selected_ev"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    rows = load_rows(args.features)
    audit_rows = audit(rows)
    write_csv(args.csv_output, audit_rows)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps({
        "features": str(args.features),
        "rows": audit_rows,
        "policy": "research_only_until_full_result_sample",
    }, indent=2))
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.json_output}")
    for row in audit_rows[:5]:
        print(f"{row['bucket']}: {row['wins']}-{row['losses']} over {row['graded']} graded")


if __name__ == "__main__":
    main()
