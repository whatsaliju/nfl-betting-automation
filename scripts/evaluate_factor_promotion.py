#!/usr/bin/env python3
"""Evaluate whether researched factors are ready to influence recommendations.

This is intentionally conservative. A factor can look great in a small replay
and still be noise, so promotion stages are explicit and threshold based:
research -> monitor -> candidate -> production_ready.
"""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEADERBOARD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_leaderboard.json"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_promotion_report.json"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_promotion_report.csv"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_promotion_report.md"

PRODUCTION_PLAYS = 40
CANDIDATE_PLAYS = 8
MONITOR_PLAYS = 4
PRODUCTION_LIFT = 0.04
CANDIDATE_LIFT = 0.06
MONITOR_LIFT = 0.02
MAX_LOSS_RATE_FOR_PRODUCTION = 0.35

ALLOW_SELECTOR_INFLUENCE = {"candidate_overlay", "research_feature", "selector_diagnostic"}


def load_leaderboard(path):
    path = Path(path)
    if path.suffix == ".json":
        return json.loads(path.read_text())
    with path.open() as f:
        return list(csv.DictReader(f))


def int_value(row, key):
    value = row.get(key)
    if value in (None, ""):
        return 0
    return int(float(value))


def float_value(row, key):
    value = row.get(key)
    if value in (None, ""):
        return None
    return float(value)


def factor_key(row):
    return f"{row.get('feature')}={row.get('value')}"


def promotion_status(row):
    plays = int_value(row, "plays")
    losses = int_value(row, "losses")
    lift = float_value(row, "win_rate_lift")
    actionability = row.get("actionability") or "context"
    loss_rate = losses / plays if plays else 1.0

    blockers = []
    warnings = []

    if actionability == "moneyline_research":
        blockers.append("moneyline is research-only until the pricing model is separately validated")
    if actionability == "context":
        blockers.append("context factor should not directly alter picks")
    if lift is None:
        blockers.append("missing lift")
    elif lift <= 0:
        blockers.append("non-positive lift")
    if plays < MONITOR_PLAYS:
        blockers.append(f"needs at least {MONITOR_PLAYS} graded plays to monitor")
    elif plays < CANDIDATE_PLAYS:
        warnings.append(f"thin sample below candidate threshold {CANDIDATE_PLAYS}")
    elif plays < PRODUCTION_PLAYS:
        warnings.append(f"below production threshold {PRODUCTION_PLAYS}")
    if loss_rate > MAX_LOSS_RATE_FOR_PRODUCTION:
        warnings.append("loss rate too high for production")

    can_influence = actionability in ALLOW_SELECTOR_INFLUENCE and not blockers
    if (
        can_influence
        and plays >= PRODUCTION_PLAYS
        and lift is not None
        and lift >= PRODUCTION_LIFT
        and loss_rate <= MAX_LOSS_RATE_FOR_PRODUCTION
    ):
        status = "production_ready"
        recommendation = "Eligible for selector rule testing with guardrails."
    elif can_influence and plays >= CANDIDATE_PLAYS and lift is not None and lift >= CANDIDATE_LIFT:
        status = "candidate"
        recommendation = "Simulate as a soft overlay before changing production recommendations."
    elif can_influence and plays >= MONITOR_PLAYS and lift is not None and lift >= MONITOR_LIFT:
        status = "monitor"
        recommendation = "Keep visible in Research and re-evaluate after each graded week."
    else:
        status = "research"
        recommendation = "Retain as a descriptive feature only."

    return {
        "factor": factor_key(row),
        "feature": row.get("feature"),
        "value": row.get("value"),
        "actionability": actionability,
        "plays": plays,
        "wins": int_value(row, "wins"),
        "losses": losses,
        "win_rate": float_value(row, "win_rate"),
        "baseline_win_rate": float_value(row, "baseline_win_rate"),
        "win_rate_lift": lift,
        "sample_flag": row.get("sample_flag"),
        "promotion_status": status,
        "selector_influence_allowed": status in {"candidate", "production_ready"},
        "recommendation": recommendation,
        "blockers": blockers,
        "warnings": warnings,
    }


def evaluate(rows):
    reports = [promotion_status(row) for row in rows]
    return sorted(
        reports,
        key=lambda row: (
            {
                "production_ready": 0,
                "candidate": 1,
                "monitor": 2,
                "research": 3,
            }.get(row["promotion_status"], 4),
            -(row["win_rate_lift"] if row["win_rate_lift"] is not None else -999),
            -row["plays"],
            row["factor"],
        ),
    )


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "factor",
        "feature",
        "value",
        "actionability",
        "plays",
        "wins",
        "losses",
        "win_rate",
        "baseline_win_rate",
        "win_rate_lift",
        "sample_flag",
        "promotion_status",
        "selector_influence_allowed",
        "recommendation",
        "blockers",
        "warnings",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                **row,
                "blockers": ";".join(row["blockers"]),
                "warnings": ";".join(row["warnings"]),
            })


def write_markdown(path, rows):
    lines = [
        "# Factor Promotion Report",
        "",
        "Promotion rules are conservative. Candidate factors may be simulated as soft overlays; production-ready factors still need guardrail testing before changing picks.",
        "",
        "| Factor | Status | Plays | W-L | Lift | Allowed | Notes |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows[:30]:
        notes = "; ".join(row["blockers"] + row["warnings"]) or row["recommendation"]
        lift = row["win_rate_lift"] if row["win_rate_lift"] is not None else ""
        allowed = "yes" if row["selector_influence_allowed"] else "no"
        lines.append(
            f"| {row['factor']} | {row['promotion_status']} | {row['plays']} | "
            f"{row['wins']}-{row['losses']} | {lift} | {allowed} | {notes} |"
        )
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leaderboard", type=Path, default=DEFAULT_LEADERBOARD)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    rows = evaluate(load_leaderboard(args.leaderboard))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(rows, indent=2))
    write_csv(args.csv_output, rows)
    write_markdown(args.md_output, rows)
    counts = {}
    for row in rows:
        counts[row["promotion_status"]] = counts.get(row["promotion_status"], 0) + 1
    print(json.dumps({
        "promotion_rows": len(rows),
        "status_counts": counts,
        "top": rows[0] if rows else None,
    }, indent=2))


if __name__ == "__main__":
    main()
