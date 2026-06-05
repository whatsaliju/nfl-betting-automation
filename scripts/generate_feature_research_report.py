#!/usr/bin/env python3
"""Generate a concise research report from canonical game feature audits."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_AUDIT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_feature_audit.csv"
DEFAULT_POLICY_SIMULATION = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_policy_simulation.csv"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_research_report.json"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_research_report.md"


KEY_DIMENSIONS = [
    "best_edge_market",
    "pythagorean_pick_alignment",
    "value_gap_pick_alignment",
    "market_expectation_pick_alignment",
    "overperformance_pick_alignment",
    "division_game",
    "data_quality_status",
]


def load_records(path):
    path = Path(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("rows") or data.get("policy_simulations") or []
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def load_csv(path):
    return load_records(path)


def int_value(row, key):
    value = row.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(value) if value not in (None, "") else 0


def float_value(row, key):
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return float(value) if value not in (None, "") else None


def audit_slice(rows, dimension):
    return [
        {
            "value": row["value"],
            "games": int_value(row, "games"),
            "graded_bets": int_value(row, "graded_bets"),
            "wins": int_value(row, "bet_wins"),
            "losses": int_value(row, "bet_losses"),
            "pushes": int_value(row, "bet_pushes"),
            "bet_win_rate": float_value(row, "bet_win_rate"),
        }
        for row in rows
        if row.get("dimension") == dimension
    ]


def policy_slice(rows):
    output = []
    for row in rows:
        output.append({
            "policy": row.get("policy"),
            "description": row.get("description"),
            "plays": int_value(row, "plays"),
            "wins": int_value(row, "wins"),
            "losses": int_value(row, "losses"),
            "win_rate": float_value(row, "win_rate"),
            "removed_plays": int_value(row, "removed_plays"),
            "removed_wins": int_value(row, "removed_wins"),
            "removed_losses": int_value(row, "removed_losses"),
            "win_rate_delta": float_value(row, "win_rate_delta"),
        })
    return output


def report_payload(features, audit_rows, policy_rows=None):
    graded = [row for row in features if row.get("bet_result") in {"win", "loss", "push"}]
    decisions = [row for row in graded if row.get("bet_result") in {"win", "loss"}]
    wins = sum(1 for row in decisions if row.get("bet_result") == "win")
    losses = sum(1 for row in decisions if row.get("bet_result") == "loss")
    by_dimension = {dimension: audit_slice(audit_rows, dimension) for dimension in KEY_DIMENSIONS}

    value_aligned = next(
        (row for row in by_dimension["value_gap_pick_alignment"] if row["value"] == "aligned"),
        None,
    )
    value_conflict = next(
        (row for row in by_dimension["value_gap_pick_alignment"] if row["value"] == "conflict"),
        None,
    )
    pythag_aligned = next(
        (row for row in by_dimension["pythagorean_pick_alignment"] if row["value"] == "aligned"),
        None,
    )
    pythag_conflict = next(
        (row for row in by_dimension["pythagorean_pick_alignment"] if row["value"] == "conflict"),
        None,
    )

    observations = []
    if value_aligned and value_conflict:
        observations.append(
            "Value-gap alignment looks promising but is still a small sample: "
            f"aligned {value_aligned['wins']}-{value_aligned['losses']} vs "
            f"conflict {value_conflict['wins']}-{value_conflict['losses']}."
        )
    if pythag_aligned and pythag_conflict:
        observations.append(
            "Pythagorean side alignment is also promising: "
            f"aligned {pythag_aligned['wins']}-{pythag_aligned['losses']} vs "
            f"conflict {pythag_conflict['wins']}-{pythag_conflict['losses']}."
        )
    observations.append(
        "Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample."
    )
    policies = policy_slice(policy_rows or [])
    best_policy = None
    non_baseline = [row for row in policies if row["policy"] != "baseline" and row["plays"]]
    if non_baseline:
        best_policy = max(
            non_baseline,
            key=lambda row: (row["win_rate"] or 0, row["plays"]),
        )
        observations.append(
            f"Best simple overlay in this sample is {best_policy['policy']}: "
            f"{best_policy['wins']}-{best_policy['losses']} over {best_policy['plays']} plays."
        )

    return {
        "feature_rows": len(features),
        "graded_bets": len(graded),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / (wins + losses), 4) if wins + losses else None,
        "by_dimension": by_dimension,
        "policy_simulations": policies,
        "observations": observations,
        "candidate_policy": {
            "status": "monitor_only" if not best_policy else "monitor_candidate_overlay",
            "recommendation": (
                "Track expectation alignment as an annotation and candidate spread threshold bump. "
                "Do not hard-gate production picks until more full-season feature rows are available."
            ),
        },
    }


def write_markdown(path, report):
    lines = [
        "# Feature Research Report",
        "",
        f"- Feature rows: {report['feature_rows']}",
        f"- Graded bets: {report['graded_bets']}",
        f"- Result: {report['wins']}-{report['losses']} ({report['win_rate']})",
        "",
        "## Key Observations",
        "",
    ]
    lines.extend(f"- {item}" for item in report["observations"])
    lines.extend(["", "## Factor Groups", ""])
    for dimension in KEY_DIMENSIONS:
        lines.append(f"### {dimension}")
        for row in report["by_dimension"].get(dimension, []):
            if row["graded_bets"]:
                lines.append(
                    f"- {row['value']}: {row['wins']}-{row['losses']} "
                    f"({row['bet_win_rate']}) over {row['graded_bets']} graded bets"
                )
            else:
                lines.append(f"- {row['value']}: {row['games']} games")
        lines.append("")
    if report.get("policy_simulations"):
        lines.extend(["## Policy Simulations", ""])
        for row in report["policy_simulations"]:
            lines.append(
                f"- {row['policy']}: {row['wins']}-{row['losses']} "
                f"({row['win_rate']}) over {row['plays']} plays; "
                f"removed {row['removed_wins']}-{row['removed_losses']}"
            )
        lines.append("")
    lines.extend([
        "## Candidate Policy",
        "",
        f"- Status: {report['candidate_policy']['status']}",
        f"- Recommendation: {report['candidate_policy']['recommendation']}",
        "",
    ])
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--policy-simulation", type=Path, default=None)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    features = load_csv(args.features)
    audit_rows = load_csv(args.audit)
    policy_rows = load_csv(args.policy_simulation) if args.policy_simulation and args.policy_simulation.exists() else []
    report = report_payload(features, audit_rows, policy_rows)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2))
    write_markdown(args.md_output, report)
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.md_output}")
    print(json.dumps({
        "graded_bets": report["graded_bets"],
        "wins": report["wins"],
        "losses": report["losses"],
        "win_rate": report["win_rate"],
    }, indent=2))


if __name__ == "__main__":
    main()
