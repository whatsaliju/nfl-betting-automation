#!/usr/bin/env python3
"""Build a market-level edge ledger and router audit.

The ledger normalizes each analyzed game into spread, total, and moneyline
candidate rows. It deliberately separates selected bet outcomes from research
candidate outcomes so downstream reports do not overstate what was actually
graded.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "warps_selector_alignment_rows.csv"
FALLBACK_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_LEDGER_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_edge_ledger.csv"
DEFAULT_LEDGER_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_edge_ledger.json"
DEFAULT_AUDIT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_router_audit.json"
DEFAULT_AUDIT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_router_audit.csv"
DEFAULT_AUDIT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_router_audit.md"


def load_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def feature_path(path):
    if path.exists():
        return path
    return FALLBACK_FEATURES


def number_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def result_for_market(row, market, side):
    if row.get("best_edge_market") == market and row.get("best_edge_side") == side:
        return row.get("bet_result") or "", "selected_bet"
    if market == "moneyline" and side in {"AWAY", "HOME"}:
        winner = row.get("straight_up_winner_side")
        if winner in {"AWAY", "HOME"}:
            return ("win" if winner == side else "loss"), "straight_up_research"
    return "", "ungraded_candidate"


def candidate_status(row, market):
    if market == "spread":
        return row.get("spread_status") or ""
    if market == "total":
        return row.get("total_status") or ""
    return row.get("moneyline_status") or ""


def candidate_side(row, market):
    if market == "spread":
        return row.get("spread_side") or ""
    if market == "total":
        return row.get("total_side") or ""
    return row.get("moneyline_side") or ""


def candidate_score(row, market):
    if market == "spread":
        return row.get("spread_score") or ""
    if market == "total":
        return row.get("total_score") or ""
    return row.get("moneyline_selected_ev") or ""


def candidate_threshold(row, market):
    if market == "spread":
        return row.get("spread_threshold") or ""
    if market == "total":
        return row.get("total_threshold") or ""
    return ""


def candidate_sources(row, market):
    if market == "spread":
        return row.get("spread_signal_sources") or ""
    if market == "total":
        return row.get("total_signal_sources") or ""
    return "research_model" if row.get("moneyline_side") else ""


def candidate_conflicts(row, market):
    if market == "spread":
        return row.get("spread_conflict_sources") or ""
    if market == "total":
        return row.get("total_conflict_sources") or ""
    return ""


def selected_rank(row, market, side):
    return "selected" if row.get("best_edge_market") == market and row.get("best_edge_side") == side else "candidate"


def market_line(row, market, side):
    if row.get("best_edge_market") == market and row.get("best_edge_side") == side:
        return row.get("bet_line") or ""
    if market == "moneyline":
        return row.get("moneyline_away_odds" if side == "AWAY" else "moneyline_home_odds") or ""
    return ""


def market_fair(row, market, side):
    if market == "spread":
        if side == "HOME":
            return row.get("warps_fair_home_spread") or ""
        if side == "AWAY":
            return row.get("warps_fair_away_spread") or ""
    if market == "moneyline":
        if side == "HOME":
            return row.get("moneyline_home_model_prob") or row.get("warps_home_win_prob") or ""
        if side == "AWAY":
            return row.get("moneyline_away_model_prob") or row.get("warps_away_win_prob") or ""
    return ""


def market_edge_value(row, market, side):
    if market == "spread":
        return row.get("warps_spread_edge_points") or ""
    if market == "moneyline":
        return row.get("moneyline_selected_ev") or row.get("warps_ml_ev") or ""
    return ""


def ledger_row(row, market):
    side = candidate_side(row, market)
    result, result_scope = result_for_market(row, market, side)
    return {
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "week": row.get("week"),
        "matchup_key": row.get("matchup_key"),
        "away_tla": row.get("away_tla"),
        "home_tla": row.get("home_tla"),
        "market": market,
        "side": side,
        "candidate_status": candidate_status(row, market),
        "candidate_score": candidate_score(row, market),
        "candidate_threshold": candidate_threshold(row, market),
        "selection_rank": selected_rank(row, market, side),
        "selected_by_engine": "true" if selected_rank(row, market, side) == "selected" else "false",
        "line_or_price": market_line(row, market, side),
        "fair_estimate": market_fair(row, market, side),
        "edge_value": market_edge_value(row, market, side),
        "result": result,
        "result_scope": result_scope,
        "margin_to_line": row.get("bet_margin_to_line") if result_scope == "selected_bet" else "",
        "signal_sources": candidate_sources(row, market),
        "conflict_sources": candidate_conflicts(row, market),
        "source_health_status": row.get("source_health_status") or "",
        "data_quality_status": row.get("data_quality_status") or "",
        "warps_spread_pick_alignment": row.get("warps_spread_pick_alignment") or "",
        "warps_spread_side": row.get("warps_spread_side") or "",
        "warps_spread_edge_points": row.get("warps_spread_edge_points") or "",
        "warps_ml_side": row.get("warps_ml_side") or "",
        "warps_ml_ev": row.get("warps_ml_ev") or "",
        "pythagorean_pick_alignment": row.get("pythagorean_pick_alignment") or "",
        "value_gap_pick_alignment": row.get("value_gap_pick_alignment") or "",
        "market_expectation_pick_alignment": row.get("market_expectation_pick_alignment") or "",
        "overperformance_pick_alignment": row.get("overperformance_pick_alignment") or "",
    }


def build_ledger(rows):
    ledger = []
    for row in rows:
        for market in ("spread", "total", "moneyline"):
            ledger.append(ledger_row(row, market))
    return ledger


def summarize(rows):
    wins = sum(1 for row in rows if row.get("result") == "win")
    losses = sum(1 for row in rows if row.get("result") == "loss")
    pushes = sum(1 for row in rows if row.get("result") == "push")
    decisions = wins + losses
    return {
        "plays": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
    }


def bucket_summary(ledger, dimension, predicate):
    buckets = defaultdict(list)
    for row in ledger:
        if predicate(row):
            buckets[row.get(dimension) or "NONE"].append(row)
    return [
        {
            "section": dimension,
            "bucket": bucket,
            **summarize(rows),
        }
        for bucket, rows in sorted(buckets.items())
    ]


def router_audit(ledger):
    selected = [row for row in ledger if row.get("result_scope") == "selected_bet" and row.get("result") in {"win", "loss", "push"}]
    ml_research = [row for row in ledger if row.get("market") == "moneyline" and row.get("result_scope") == "straight_up_research"]
    rows = []
    rows.append({"section": "overall", "bucket": "selected_engine_bets", **summarize(selected)})
    rows.extend(bucket_summary(ledger, "market", lambda row: row in selected))
    rows.extend(bucket_summary(ledger, "warps_spread_pick_alignment", lambda row: row in selected and row.get("market") == "spread"))
    rows.extend(bucket_summary(ledger, "candidate_status", lambda row: row in selected))
    rows.append({"section": "moneyline_research", "bucket": "all_research_sides", **summarize(ml_research)})
    rows.extend(bucket_summary(ledger, "side", lambda row: row in ml_research))
    verdict = market_router_verdict(rows)
    return {
        "ledger_rows": len(ledger),
        "selected_bets": len(selected),
        "moneyline_research_rows": len(ml_research),
        "summary_rows": rows,
        "verdict": verdict,
    }


def market_router_verdict(rows):
    overall = next((row for row in rows if row["section"] == "overall"), {})
    market_rows = [row for row in rows if row["section"] == "market"]
    best_market = None
    if market_rows:
        best_market = max(
            market_rows,
            key=lambda row: (
                row.get("plays", 0) >= 5,
                row.get("win_rate") if row.get("win_rate") is not None else -1,
                row.get("plays", 0),
            ),
        )
    status = "BUILDING_SAMPLE"
    recommendation = "Keep routing descriptive until spread, total, and ML all have larger graded samples."
    if overall.get("plays", 0) >= 40 and best_market and best_market.get("win_rate", 0) >= (overall.get("win_rate") or 0) + 0.03:
        status = "CANDIDATE_MARKET_TILT"
        recommendation = f"{best_market['bucket']} is outperforming baseline enough to monitor as a routing tilt."
    elif best_market:
        recommendation = f"{best_market['bucket']} is the current best selected market, but sample is still monitor-only."
    return {
        "status": status,
        "recommendation": recommendation,
        "baseline_win_rate": overall.get("win_rate"),
        "best_market": best_market,
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = []
    for row in rows:
        for field in row.keys():
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(audit):
    lines = [
        "# Market Router Audit",
        "",
        "This report summarizes the market edge ledger by selected engine market and research moneyline direction.",
        "",
        "## Verdict",
        "",
        f"- Status: {audit['verdict']['status']}",
        f"- Recommendation: {audit['verdict']['recommendation']}",
        f"- Selected bets: {audit['selected_bets']}",
        f"- Ledger rows: {audit['ledger_rows']}",
        "",
        "## Buckets",
        "",
        "| Section | Bucket | Plays | W-L-P | Win Rate |",
        "|---|---|---:|---:|---:|",
    ]
    for row in audit["summary_rows"]:
        lines.append(
            f"| {row['section']} | {row['bucket']} | {row['plays']} | "
            f"{row['wins']}-{row['losses']}-{row['pushes']} | {row['win_rate']} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Spread and total outcomes are only treated as graded when that market was the selected engine bet.",
        "- Moneyline rows are straight-up research grades unless the engine later promotes ML to selected bets.",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--ledger-csv", type=Path, default=DEFAULT_LEDGER_CSV)
    parser.add_argument("--ledger-json", type=Path, default=DEFAULT_LEDGER_JSON)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--audit-md", type=Path, default=DEFAULT_AUDIT_MD)
    args = parser.parse_args()

    rows = load_csv(feature_path(args.features))
    ledger = build_ledger(rows)
    audit = router_audit(ledger)
    write_csv(args.ledger_csv, ledger)
    args.ledger_json.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_json.write_text(json.dumps(ledger, indent=2))
    args.audit_json.write_text(json.dumps(audit, indent=2))
    write_csv(args.audit_csv, audit["summary_rows"])
    args.audit_md.write_text(markdown_report(audit))
    print(json.dumps({
        "ledger_rows": audit["ledger_rows"],
        "selected_bets": audit["selected_bets"],
        "moneyline_research_rows": audit["moneyline_research_rows"],
        "verdict": audit["verdict"],
    }, indent=2))
    print(f"Wrote {args.ledger_csv}")
    print(f"Wrote {args.ledger_json}")
    print(f"Wrote {args.audit_json}")
    print(f"Wrote {args.audit_csv}")
    print(f"Wrote {args.audit_md}")


if __name__ == "__main__":
    main()
