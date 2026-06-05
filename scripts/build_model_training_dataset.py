#!/usr/bin/env python3
"""Export model-ready training rows and a factor leaderboard.

The training dataset keeps one row per analyzed game/pick candidate with clean
targets. The leaderboard is deliberately simple and transparent: it compares
feature buckets against the graded replay baseline so promising factors can be
promoted to simulations before becoming selector logic.
"""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_DATASET_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "model_training_dataset.csv"
DEFAULT_DATASET_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "model_training_dataset.json"
DEFAULT_LEADERBOARD_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_leaderboard.csv"
DEFAULT_LEADERBOARD_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_leaderboard.json"
DEFAULT_LEADERBOARD_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_leaderboard.md"

CATEGORICAL_FEATURES = [
    "best_edge_market",
    "best_edge_side",
    "best_edge_status",
    "spread_status",
    "total_status",
    "moneyline_status",
    "division_game",
    "conference_game",
    "pythagorean_side",
    "market_expectation_side",
    "value_gap_side",
    "overperformance_side",
    "pythagorean_pick_alignment",
    "market_expectation_pick_alignment",
    "value_gap_pick_alignment",
    "overperformance_pick_alignment",
    "expectation_sample_warning",
    "source_health_status",
    "data_quality_status",
]

NUMERIC_FEATURES = [
    "best_edge_score",
    "spread_score",
    "total_score",
    "pythagorean_wins_delta",
    "vegas_win_total_delta",
    "pythagorean_vs_vegas_delta",
    "actual_vs_pythagorean_delta",
    "expectation_games_tracked_min",
    "moneyline_selected_ev",
    "moneyline_selected_edge",
]


def load_rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def float_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bool_target(row):
    result = row.get("bet_result")
    if result == "win":
        return 1
    if result == "loss":
        return 0
    return ""


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


def training_row(row):
    output = {
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "week": row.get("week"),
        "matchup_key": row.get("matchup_key"),
        "away_tla": row.get("away_tla"),
        "home_tla": row.get("home_tla"),
        "market": row.get("best_edge_market"),
        "side": row.get("best_edge_side"),
        "bet_result": row.get("bet_result"),
        "target_bet_win": bool_target(row),
        "target_margin_to_line": row.get("bet_margin_to_line"),
        "straight_up_winner_side": row.get("straight_up_winner_side"),
        "final_margin_away_minus_home": row.get("final_margin_away_minus_home"),
        "final_total": row.get("final_total"),
    }
    for feature in CATEGORICAL_FEATURES + NUMERIC_FEATURES:
        output[feature] = row.get(feature, "")
    for feature in NUMERIC_FEATURES:
        output[f"{feature}_bin"] = numeric_bin(feature, float_or_none(row.get(feature)))
    return output


def is_graded_pick(row):
    return row.get("best_edge_market") and row.get("bet_result") in {"win", "loss"}


def summarize_bucket(feature, value, rows, baseline_win_rate):
    wins = sum(1 for row in rows if row.get("bet_result") == "win")
    losses = sum(1 for row in rows if row.get("bet_result") == "loss")
    plays = wins + losses
    win_rate = round(wins / plays, 4) if plays else None
    if plays >= 8:
        sample_flag = "monitor"
    elif plays >= 4:
        sample_flag = "thin"
    else:
        sample_flag = "micro"
    return {
        "feature": feature,
        "value": value or "NONE",
        "actionability": actionability(feature),
        "plays": plays,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "baseline_win_rate": baseline_win_rate,
        "win_rate_lift": (
            round(win_rate - baseline_win_rate, 4)
            if win_rate is not None and baseline_win_rate is not None
            else None
        ),
        "sample_flag": sample_flag,
    }


def actionability(feature):
    if feature.startswith("moneyline_") or feature == "moneyline_status":
        return "moneyline_research"
    if "pick_alignment" in feature:
        return "candidate_overlay"
    if feature in {
        "pythagorean_side",
        "market_expectation_side",
        "value_gap_side",
        "overperformance_side",
    } or feature in {
        "pythagorean_wins_delta_bin",
        "vegas_win_total_delta_bin",
        "pythagorean_vs_vegas_delta_bin",
        "actual_vs_pythagorean_delta_bin",
        "expectation_games_tracked_min_bin",
    }:
        return "research_feature"
    if feature.startswith("best_edge_") or feature.startswith("spread_") or feature.startswith("total_"):
        return "selector_diagnostic"
    return "context"


def factor_leaderboard(rows):
    graded = [row for row in rows if is_graded_pick(row)]
    wins = sum(1 for row in graded if row.get("bet_result") == "win")
    losses = sum(1 for row in graded if row.get("bet_result") == "loss")
    baseline = round(wins / (wins + losses), 4) if wins + losses else None
    buckets = []

    for feature in CATEGORICAL_FEATURES:
        values = sorted({row.get(feature) or "NONE" for row in graded})
        for value in values:
            feature_rows = [row for row in graded if (row.get(feature) or "NONE") == value]
            buckets.append(summarize_bucket(feature, value, feature_rows, baseline))

    for feature in NUMERIC_FEATURES:
        keyed_rows = [
            {**row, "_bin": numeric_bin(feature, float_or_none(row.get(feature)))}
            for row in graded
        ]
        for value in sorted({row["_bin"] for row in keyed_rows}):
            feature_rows = [row for row in keyed_rows if row["_bin"] == value]
            buckets.append(summarize_bucket(f"{feature}_bin", value, feature_rows, baseline))

    return sorted(
        buckets,
        key=lambda row: (
            {"monitor": 0, "thin": 1, "micro": 2}.get(row["sample_flag"], 3),
            {
                "candidate_overlay": 0,
                "research_feature": 1,
                "selector_diagnostic": 2,
                "moneyline_research": 3,
                "context": 4,
            }.get(row["actionability"], 5),
            -(row["win_rate_lift"] if row["win_rate_lift"] is not None else -999),
            -row["plays"],
            row["feature"],
            row["value"],
        ),
    )


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


def write_markdown(path, rows):
    lines = [
        "# Factor Leaderboard",
        "",
        "Research-only ranking of feature buckets against graded replay picks.",
        "",
        "| Feature | Value | Type | Plays | W-L | Win Rate | Lift | Sample |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows[:30]:
        win_rate = row["win_rate"] if row["win_rate"] is not None else ""
        lift = row["win_rate_lift"] if row["win_rate_lift"] is not None else ""
        lines.append(
            f"| {row['feature']} | {row['value']} | {row['actionability']} | "
            f"{row['plays']} | {row['wins']}-{row['losses']} | "
            f"{win_rate} | {lift} | {row['sample_flag']} |"
        )
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--dataset-csv", type=Path, default=DEFAULT_DATASET_CSV)
    parser.add_argument("--dataset-json", type=Path, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--leaderboard-csv", type=Path, default=DEFAULT_LEADERBOARD_CSV)
    parser.add_argument("--leaderboard-json", type=Path, default=DEFAULT_LEADERBOARD_JSON)
    parser.add_argument("--leaderboard-md", type=Path, default=DEFAULT_LEADERBOARD_MD)
    args = parser.parse_args()

    rows = load_rows(args.features)
    dataset = [training_row(row) for row in rows]
    leaderboard = factor_leaderboard(rows)

    args.dataset_json.parent.mkdir(parents=True, exist_ok=True)
    args.dataset_json.write_text(json.dumps(dataset, indent=2))
    args.leaderboard_json.write_text(json.dumps(leaderboard, indent=2))
    write_csv(args.dataset_csv, dataset)
    write_csv(args.leaderboard_csv, leaderboard)
    write_markdown(args.leaderboard_md, leaderboard)

    graded = [row for row in rows if is_graded_pick(row)]
    print(json.dumps({
        "training_rows": len(dataset),
        "graded_pick_rows": len(graded),
        "leaderboard_rows": len(leaderboard),
        "top_factor": leaderboard[0] if leaderboard else None,
    }, indent=2))


if __name__ == "__main__":
    main()
