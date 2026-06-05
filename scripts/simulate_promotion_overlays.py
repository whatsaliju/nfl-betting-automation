#!/usr/bin/env python3
"""Simulate soft overlays for promoted candidate factors."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_PROMOTION = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_promotion_report.json"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "promotion_overlay_simulation.json"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "promotion_overlay_simulation.csv"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "promotion_overlay_simulation.md"


def load_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def load_json(path):
    return json.loads(Path(path).read_text())


def float_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def numeric_bin(name, value):
    if value is None:
        return "missing"
    absolute = abs(value)
    if name == "best_edge_score":
        if value >= 5:
            return ">=5"
        if value >= 4:
            return "4_to_5"
        if value > 0:
            return "0_to_4"
        return "<=0"
    if name in {"spread_score", "total_score"}:
        if value >= 4.5:
            return ">=4.5"
        if value >= 3.5:
            return "3.5_to_4.5"
        if value > 0:
            return "0_to_3.5"
        return "<=0"
    if name == "expectation_games_tracked_min":
        if value >= 8:
            return ">=8_games"
        if value >= 4:
            return "4_to_7_games"
        return "<4_games"
    if name in {"moneyline_selected_ev", "moneyline_selected_edge"}:
        if value >= 0.2:
            return ">=0.20"
        if value >= 0.1:
            return "0.10_to_0.20"
        if value > 0:
            return "0_to_0.10"
        return "<=0"
    if absolute >= 4:
        return "abs>=4"
    if absolute >= 2:
        return "abs2_to_4"
    if absolute >= 0.5:
        return "abs0.5_to_2"
    return "neutral"


def graded_picks(rows):
    return [
        row for row in rows
        if row.get("best_edge_market") and row.get("bet_result") in {"win", "loss", "push"}
    ]


def is_side_pick(row):
    return row.get("best_edge_market") == "spread" and row.get("best_edge_side") in {"AWAY", "HOME"}


def summarize(rows):
    wins = sum(1 for row in rows if row.get("bet_result") == "win")
    losses = sum(1 for row in rows if row.get("bet_result") == "loss")
    pushes = sum(1 for row in rows if row.get("bet_result") == "push")
    decisions = wins + losses
    return {
        "plays": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
    }


def factor_value(row, feature):
    if feature.endswith("_bin"):
        base = feature[:-4]
        return numeric_bin(base, float_or_none(row.get(base)))
    return row.get(feature) or "NONE"


def row_matches(row, factor):
    return factor_value(row, factor["feature"]) == factor["value"]


def candidate_factors(promotion_rows):
    return [
        row for row in promotion_rows
        if row.get("promotion_status") == "candidate" and row.get("selector_influence_allowed")
    ]


def simulation_rows(features, promotions):
    graded = graded_picks(features)
    baseline = summarize(graded)
    output = [{
        "overlay": "baseline",
        "factor": "",
        "description": "Keep every graded engine pick.",
        **baseline,
        "removed_plays": 0,
        "removed_wins": 0,
        "removed_losses": 0,
        "win_rate_delta": 0.0,
        "recommendation": "Current selector baseline.",
    }]

    for factor in candidate_factors(promotions):
        direct = [row for row in graded if row_matches(row, factor)]
        output.append(simulation_payload(
            f"{factor['factor']}:only",
            factor,
            direct,
            graded,
            baseline,
            "Keep only picks matching this promoted factor.",
            "Too restrictive for production; useful as a confidence tag.",
        ))

        feature = factor.get("feature") or ""
        if feature.endswith("_pick_alignment") and factor.get("value") == "aligned":
            no_conflict = [
                row for row in graded
                if not is_side_pick(row) or row.get(feature) != "conflict"
            ]
            output.append(simulation_payload(
                f"{factor['factor']}:no_conflict",
                factor,
                no_conflict,
                graded,
                baseline,
                "Keep totals; remove spread picks when this alignment factor conflicts.",
                "Best candidate for a soft veto simulation, not production gating.",
            ))
            aligned_or_total = [
                row for row in graded
                if not is_side_pick(row) or row.get(feature) == "aligned"
            ]
            output.append(simulation_payload(
                f"{factor['factor']}:aligned_or_total",
                factor,
                aligned_or_total,
                graded,
                baseline,
                "Keep totals; require side picks to align with this factor.",
                "Candidate threshold-bump policy; keep monitoring play starvation.",
            ))

    return sorted(
        output,
        key=lambda row: (
            row["overlay"] == "baseline",
            -(row["win_rate_delta"] if row["win_rate_delta"] is not None else -999),
            -row["plays"],
            row["overlay"],
        ),
    )


def simulation_payload(name, factor, kept, baseline_rows, baseline, description, recommendation):
    removed = [row for row in baseline_rows if row not in kept]
    summary = summarize(kept)
    removed_summary = summarize(removed)
    return {
        "overlay": name,
        "factor": factor["factor"],
        "description": description,
        **summary,
        "removed_plays": removed_summary["plays"],
        "removed_wins": removed_summary["wins"],
        "removed_losses": removed_summary["losses"],
        "win_rate_delta": (
            round(summary["win_rate"] - baseline["win_rate"], 4)
            if summary["win_rate"] is not None and baseline["win_rate"] is not None
            else None
        ),
        "recommendation": recommendation,
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "overlay",
        "factor",
        "description",
        "plays",
        "wins",
        "losses",
        "pushes",
        "win_rate",
        "removed_plays",
        "removed_wins",
        "removed_losses",
        "win_rate_delta",
        "recommendation",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_markdown(path, rows):
    lines = [
        "# Promotion Overlay Simulation",
        "",
        "Soft-rule tests generated from promoted candidate factors.",
        "",
        "| Overlay | Plays | W-L | Win Rate | Removed W-L | Delta | Recommendation |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        removed = f"{row['removed_wins']}-{row['removed_losses']}" if row["removed_plays"] else "-"
        delta = row["win_rate_delta"] if row["win_rate_delta"] is not None else ""
        lines.append(
            f"| {row['overlay']} | {row['plays']} | {row['wins']}-{row['losses']} | "
            f"{row['win_rate']} | {removed} | {delta} | {row['recommendation']} |"
        )
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--promotion", type=Path, default=DEFAULT_PROMOTION)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    rows = simulation_rows(load_csv(args.features), load_json(args.promotion))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(rows, indent=2))
    write_csv(args.csv_output, rows)
    write_markdown(args.md_output, rows)
    print(json.dumps({
        "overlay_rows": len(rows),
        "top_overlay": rows[0] if rows else None,
    }, indent=2))


if __name__ == "__main__":
    main()
