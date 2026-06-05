#!/usr/bin/env python3
"""Build per-game pick explanations and quality-gated actions."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "historical" / "game_features.csv"
DEFAULT_PROMOTION = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_promotion_report.json"
DEFAULT_JSON = ROOT / "data" / "historical" / "pick_explanations.json"
DEFAULT_CSV = ROOT / "data" / "historical" / "pick_explanations.csv"
DEFAULT_MD = ROOT / "data" / "historical" / "pick_explanations.md"

CRITICAL_BAD_STATUSES = {"UNSAFE", "MISSING", "CRITICAL", "FAILED"}


def load_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def load_promotion(path):
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text())


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


def feature_value(row, feature):
    if feature.endswith("_bin"):
        return numeric_bin(feature[:-4], float_or_none(row.get(feature[:-4])))
    return row.get(feature) or "NONE"


def playable_market(row):
    market = row.get("best_edge_market") or ""
    side = row.get("best_edge_side") or ""
    if market:
        return market, side
    return "", ""


def raw_action(row):
    market, _ = playable_market(row)
    if market:
        return "play"
    if row.get("spread_status") == "lean" or row.get("total_status") == "lean":
        return "lean"
    return "pass"


def source_gate(row):
    statuses = {
        "source_health_status": row.get("source_health_status") or "UNKNOWN",
        "data_quality_status": row.get("data_quality_status") or "UNKNOWN",
    }
    blockers = []
    warnings = []
    for label, status in statuses.items():
        if status in CRITICAL_BAD_STATUSES:
            blockers.append(f"{label}={status}")
        elif status not in {"OK", "", "UNKNOWN"}:
            warnings.append(f"{label}={status}")
    if blockers:
        return "blocked", blockers, warnings
    if warnings:
        return "warn", blockers, warnings
    return "clear", blockers, warnings


def promoted_matches(row, promotion_rows):
    matches = []
    for factor in promotion_rows:
        if factor.get("promotion_status") not in {"candidate", "production_ready", "monitor"}:
            continue
        feature = factor.get("feature")
        if not feature:
            continue
        if feature_value(row, feature) == factor.get("value"):
            matches.append({
                "factor": factor.get("factor"),
                "status": factor.get("promotion_status"),
                "allowed": bool(factor.get("selector_influence_allowed")),
                "plays": factor.get("plays"),
                "wins": factor.get("wins"),
                "losses": factor.get("losses"),
                "lift": factor.get("win_rate_lift"),
            })
    return matches


def explain_signal_sources(row, market):
    sources = row.get(f"{market}_signal_sources") or ""
    conflicts = row.get(f"{market}_conflict_sources") or ""
    blockers = row.get(f"{market}_blockers") or ""
    return {
        "signals": [item for item in sources.split(";") if item],
        "conflicts": [item for item in conflicts.split(";") if item],
        "blockers": [item for item in blockers.split(";") if item],
    }


def quality_action(row, matches):
    action = raw_action(row)
    gate, blockers, warnings = source_gate(row)
    if gate == "blocked" and action in {"play", "lean"}:
        return "watch", gate, blockers, warnings
    if action == "play":
        return "play", gate, blockers, warnings
    if action == "lean":
        return "watch", gate, blockers, warnings
    return "pass", gate, blockers, warnings


def confidence(row, action, gate, matches):
    if gate == "blocked":
        return "blocked"
    candidate_matches = [match for match in matches if match["status"] == "candidate"]
    if action == "play" and candidate_matches and gate == "clear":
        return "high"
    if action == "play":
        return "standard"
    if action == "watch":
        return "watch"
    return "none"


def explanation_row(row, promotion_rows):
    market, side = playable_market(row)
    matches = promoted_matches(row, promotion_rows)
    action, gate, source_blockers, source_warnings = quality_action(row, matches)
    market_for_context = market if market in {"spread", "total"} else "spread"
    source_context = explain_signal_sources(row, market_for_context)
    reasons = []
    if market:
        reasons.append(f"Selector isolated {market} {side}".strip())
    if source_context["signals"]:
        reasons.append(f"Signals: {', '.join(source_context['signals'])}")
    if row.get("value_gap_pick_alignment") == "aligned":
        reasons.append("Value-gap alignment supports the side")
    elif row.get("value_gap_pick_alignment") == "conflict":
        reasons.append("Value-gap alignment conflicts with the side")
    if matches:
        reasons.append(f"Promoted factors matched: {len(matches)}")
    if source_warnings:
        reasons.append(f"Source warning: {', '.join(source_warnings)}")
    if source_blockers:
        reasons.append(f"Source blocker: {', '.join(source_blockers)}")
    if not reasons:
        reasons.append("No isolated selector edge")

    return {
        "key": f"{row.get('matchup_key')}:{row.get('stage') or 'final'}",
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "week": row.get("week"),
        "matchup_key": row.get("matchup_key"),
        "away_tla": row.get("away_tla"),
        "home_tla": row.get("home_tla"),
        "stage": row.get("stage"),
        "raw_action": raw_action(row),
        "quality_action": action,
        "quality_gate": gate,
        "confidence": confidence(row, action, gate, matches),
        "market": market,
        "side": side,
        "selector_score": row.get("best_edge_score"),
        "label": row.get("best_edge_label"),
        "recommendation": row.get("engine_recommendation"),
        "source_health_status": row.get("source_health_status"),
        "data_quality_status": row.get("data_quality_status"),
        "promoted_matches": matches,
        "source_blockers": source_blockers,
        "source_warnings": source_warnings,
        "market_signals": source_context["signals"],
        "market_conflicts": source_context["conflicts"],
        "market_blockers": source_context["blockers"],
        "alignment": {
            "pythagorean": row.get("pythagorean_pick_alignment"),
            "market_expectation": row.get("market_expectation_pick_alignment"),
            "value_gap": row.get("value_gap_pick_alignment"),
            "overperformance": row.get("overperformance_pick_alignment"),
        },
        "reasons": reasons[:8],
        "result": row.get("bet_result"),
        "margin_to_line": row.get("bet_margin_to_line"),
    }


def build(rows, promotion_rows):
    return [explanation_row(row, promotion_rows) for row in rows]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "key",
        "season",
        "season_type",
        "week",
        "matchup_key",
        "away_tla",
        "home_tla",
        "stage",
        "raw_action",
        "quality_action",
        "quality_gate",
        "confidence",
        "market",
        "side",
        "selector_score",
        "label",
        "recommendation",
        "source_health_status",
        "data_quality_status",
        "result",
        "margin_to_line",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_markdown(path, rows):
    lines = [
        "# Pick Explanations",
        "",
        "| Game | Raw | Gated | Market | Side | Confidence | Reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows[:80]:
        lines.append(
            f"| W{row['week']} {row['matchup_key']} | {row['raw_action']} | "
            f"{row['quality_action']} | {row['market']} | {row['side']} | "
            f"{row['confidence']} | {'; '.join(row['reasons'])} |"
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

    rows = build(load_csv(args.features), load_promotion(args.promotion))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(rows, indent=2))
    write_csv(args.csv_output, rows)
    write_markdown(args.md_output, rows)
    counts = {}
    for row in rows:
        counts[row["quality_action"]] = counts.get(row["quality_action"], 0) + 1
    print(json.dumps({
        "explanations": len(rows),
        "quality_actions": counts,
    }, indent=2))


if __name__ == "__main__":
    main()
