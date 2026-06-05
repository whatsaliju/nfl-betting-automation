#!/usr/bin/env python3
"""Simulate simple feature-based policy overlays on graded picks.

These are research overlays, not production selector rules. The goal is to
measure whether expectation features should remain annotations, become threshold
bumps, or eventually become veto/gating logic.
"""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_policy_simulation.json"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_policy_simulation.csv"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_policy_simulation.md"


def load_rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def graded_picks(rows):
    return [
        row for row in rows
        if row.get("best_edge_market") and row.get("bet_result") in {"win", "loss", "push"}
    ]


def is_side_pick(row):
    return row.get("best_edge_market") == "spread" and row.get("best_edge_side") in {"AWAY", "HOME"}


def policy_baseline(row):
    return True


def policy_value_gap_no_conflict(row):
    if not is_side_pick(row):
        return True
    return row.get("value_gap_pick_alignment") != "conflict"


def policy_pythagorean_no_conflict(row):
    if not is_side_pick(row):
        return True
    return row.get("pythagorean_pick_alignment") != "conflict"


def policy_expectation_no_conflict(row):
    if not is_side_pick(row):
        return True
    return (
        row.get("value_gap_pick_alignment") != "conflict"
        and row.get("pythagorean_pick_alignment") != "conflict"
    )


def policy_value_gap_aligned(row):
    if not is_side_pick(row):
        return True
    return row.get("value_gap_pick_alignment") == "aligned"


def policy_pythagorean_aligned(row):
    if not is_side_pick(row):
        return True
    return row.get("pythagorean_pick_alignment") == "aligned"


POLICIES = {
    "baseline": {
        "description": "Keep every graded engine pick.",
        "fn": policy_baseline,
    },
    "value_gap_no_conflict": {
        "description": "Keep totals; remove spread picks when value-gap side conflicts with the pick.",
        "fn": policy_value_gap_no_conflict,
    },
    "pythagorean_no_conflict": {
        "description": "Keep totals; remove spread picks when Pythagorean side conflicts with the pick.",
        "fn": policy_pythagorean_no_conflict,
    },
    "expectation_no_conflict": {
        "description": "Keep totals; remove spread picks when either value-gap or Pythagorean side conflicts.",
        "fn": policy_expectation_no_conflict,
    },
    "value_gap_aligned": {
        "description": "Keep totals; require spread picks to align with value-gap side.",
        "fn": policy_value_gap_aligned,
    },
    "pythagorean_aligned": {
        "description": "Keep totals; require spread picks to align with Pythagorean side.",
        "fn": policy_pythagorean_aligned,
    },
}


def summarize_rows(rows):
    wins = sum(1 for row in rows if row.get("bet_result") == "win")
    losses = sum(1 for row in rows if row.get("bet_result") == "loss")
    pushes = sum(1 for row in rows if row.get("bet_result") == "push")
    decisions = wins + losses
    by_market = {}
    for market in sorted({row.get("best_edge_market") for row in rows if row.get("best_edge_market")}):
        market_rows = [row for row in rows if row.get("best_edge_market") == market]
        market_wins = sum(1 for row in market_rows if row.get("bet_result") == "win")
        market_losses = sum(1 for row in market_rows if row.get("bet_result") == "loss")
        by_market[market] = {
            "plays": len(market_rows),
            "wins": market_wins,
            "losses": market_losses,
            "win_rate": round(market_wins / (market_wins + market_losses), 4)
            if market_wins + market_losses else None,
        }
    return {
        "plays": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
        "by_market": by_market,
    }


def simulate(rows):
    graded = graded_picks(rows)
    baseline = summarize_rows(graded)
    output = []
    for name, policy in POLICIES.items():
        kept = [row for row in graded if policy["fn"](row)]
        removed = [row for row in graded if not policy["fn"](row)]
        summary = summarize_rows(kept)
        removed_summary = summarize_rows(removed)
        output.append({
            "policy": name,
            "description": policy["description"],
            **summary,
            "removed_plays": removed_summary["plays"],
            "removed_wins": removed_summary["wins"],
            "removed_losses": removed_summary["losses"],
            "removed_win_rate": removed_summary["win_rate"],
            "plays_delta": summary["plays"] - baseline["plays"],
            "wins_delta": summary["wins"] - baseline["wins"],
            "losses_delta": summary["losses"] - baseline["losses"],
            "win_rate_delta": (
                round(summary["win_rate"] - baseline["win_rate"], 4)
                if summary["win_rate"] is not None and baseline["win_rate"] is not None
                else None
            ),
        })
    return output


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "policy",
        "description",
        "plays",
        "wins",
        "losses",
        "pushes",
        "win_rate",
        "removed_plays",
        "removed_wins",
        "removed_losses",
        "removed_win_rate",
        "plays_delta",
        "wins_delta",
        "losses_delta",
        "win_rate_delta",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_markdown(path, rows):
    lines = [
        "# Feature Policy Simulation",
        "",
        "These simulations are research-only overlays on already graded engine picks.",
        "",
        "| Policy | Plays | W-L | Win Rate | Removed W-L | Delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        removed = f"{row['removed_wins']}-{row['removed_losses']}" if row["removed_plays"] else "-"
        delta = row["win_rate_delta"] if row["win_rate_delta"] is not None else ""
        lines.append(
            f"| {row['policy']} | {row['plays']} | {row['wins']}-{row['losses']} | "
            f"{row['win_rate']} | {removed} | {delta} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- Prefer policies that remove more losses than wins without starving play count.")
    lines.append("- Small-sample results should be treated as monitor-only until more full-season data exists.")
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    rows = load_rows(args.features)
    simulations = simulate(rows)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(simulations, indent=2))
    write_csv(args.csv_output, simulations)
    write_markdown(args.md_output, simulations)
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.md_output}")
    for row in simulations:
        print(f"{row['policy']}: {row['wins']}-{row['losses']} over {row['plays']} plays")


if __name__ == "__main__":
    main()
