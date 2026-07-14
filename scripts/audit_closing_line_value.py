#!/usr/bin/env python3
"""Audit closing-line value for selected engine bets.

The historical market spine is treated as the close/reference line. This script
only grades selected bets; candidate rows remain outside CLV so the report stays
about price discipline, not hypothetical alternatives.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_edge_ledger.csv"
DEFAULT_MARKET_SPINE = ROOT / "data" / "historical" / "nfl_market_spine.csv"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "clv_audit.json"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "clv_ledger.csv"
DEFAULT_BUCKETS = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "clv_audit_buckets.csv"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "clv_audit.md"


def load_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def number_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def join_key(row):
    return (
        str(row.get("season") or ""),
        str(row.get("week") or ""),
        row.get("matchup_key") or "",
    )


def market_index(rows):
    return {join_key(row): row for row in rows if row.get("matchup_key")}


def american_implied_probability(odds):
    odds = number_or_none(odds)
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def close_line_for(row, market):
    side = row.get("side")
    if market == "spread":
        return row.get("away_spread_line" if side == "AWAY" else "home_spread_line")
    if market == "total":
        return row.get("total_line")
    if market == "moneyline":
        return row.get("away_moneyline" if side == "AWAY" else "home_moneyline")
    return None


def close_result_for(row, market):
    side = row.get("side")
    if market == "spread":
        return row.get("away_cover_result" if side == "AWAY" else "home_cover_result")
    if market == "total":
        return row.get("over_result" if side == "OVER" else "under_result")
    if market == "moneyline":
        return row.get("away_ml_result" if side == "AWAY" else "home_ml_result")
    return ""


def clv_for(market, side, picked, close):
    picked_value = number_or_none(picked)
    close_value = number_or_none(close)
    if picked_value is None or close_value is None:
        return None, "missing"
    if market == "spread":
        # Side-perspective lines: +3 is better than +2.5; -2.5 is better than -3.
        value = picked_value - close_value
        return round(value, 4), direction(value)
    if market == "total":
        if side == "OVER":
            value = close_value - picked_value
        elif side == "UNDER":
            value = picked_value - close_value
        else:
            return None, "missing"
        return round(value, 4), direction(value)
    if market == "moneyline":
        picked_prob = american_implied_probability(picked_value)
        close_prob = american_implied_probability(close_value)
        if picked_prob is None or close_prob is None:
            return None, "missing"
        value = close_prob - picked_prob
        return round(value, 4), direction(value, neutral_band=0.0025)
    return None, "missing"


def direction(value, neutral_band=0.0001):
    if value is None:
        return "missing"
    if value > neutral_band:
        return "beat_close"
    if value < -neutral_band:
        return "lost_to_close"
    return "push_close"


def selected_rows(ledger):
    return [
        row for row in ledger
        if row.get("result_scope") == "selected_bet" and row.get("selected_by_engine") == "true"
    ]


def clv_row(row, market_row):
    market = row.get("market")
    side = row.get("side")
    close_line = close_line_for({**(market_row or {}), "side": side}, market) if market_row else None
    clv_value, clv_direction = clv_for(market, side, row.get("line_or_price"), close_line)
    close_result = close_result_for({**(market_row or {}), "side": side}, market) if market_row else ""
    return {
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "week": row.get("week"),
        "matchup_key": row.get("matchup_key"),
        "away_tla": row.get("away_tla"),
        "home_tla": row.get("home_tla"),
        "market": market,
        "side": side,
        "picked_line_or_price": row.get("line_or_price"),
        "close_line_or_price": close_line if close_line is not None else "",
        "clv_value": clv_value if clv_value is not None else "",
        "clv_direction": clv_direction,
        "result": row.get("result"),
        "close_result": close_result,
        "result_matches_close_result": (
            "true" if close_result and row.get("result") == close_result else
            "false" if close_result and row.get("result") else ""
        ),
        "candidate_score": row.get("candidate_score"),
        "signal_sources": row.get("signal_sources"),
        "conflict_sources": row.get("conflict_sources"),
        "warps_spread_pick_alignment": row.get("warps_spread_pick_alignment"),
        "value_gap_pick_alignment": row.get("value_gap_pick_alignment"),
        "source_health_status": row.get("source_health_status"),
        "data_quality_status": row.get("data_quality_status"),
        "market_reference_available": "true" if market_row else "false",
    }


def summarize(rows):
    wins = sum(1 for row in rows if row.get("result") == "win")
    losses = sum(1 for row in rows if row.get("result") == "loss")
    pushes = sum(1 for row in rows if row.get("result") == "push")
    decisions = wins + losses
    clv_values = [number_or_none(row.get("clv_value")) for row in rows]
    clv_values = [value for value in clv_values if value is not None]
    beat_close = sum(1 for row in rows if row.get("clv_direction") == "beat_close")
    lost_close = sum(1 for row in rows if row.get("clv_direction") == "lost_to_close")
    push_close = sum(1 for row in rows if row.get("clv_direction") == "push_close")
    clv_decisions = beat_close + lost_close
    return {
        "plays": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
        "avg_clv": round(sum(clv_values) / len(clv_values), 4) if clv_values else None,
        "beat_close": beat_close,
        "lost_to_close": lost_close,
        "push_close": push_close,
        "beat_close_rate": round(beat_close / clv_decisions, 4) if clv_decisions else None,
    }


def bucket_rows(rows, dimension):
    buckets = defaultdict(list)
    for row in rows:
        buckets[row.get(dimension) or "NONE"].append(row)
    return [
        {
            "section": dimension,
            "bucket": bucket,
            **summarize(bucket_rows),
        }
        for bucket, bucket_rows in sorted(buckets.items())
    ]


def verdict(overall, buckets):
    status = "BUILDING_SAMPLE"
    recommendation = "Track CLV, but do not promote price gates until the selected-bet sample is larger."
    if overall.get("plays", 0) >= 40:
        if (overall.get("beat_close_rate") or 0) >= 0.55 and (overall.get("avg_clv") or 0) > 0:
            status = "PRICE_DISCIPLINE_POSITIVE"
            recommendation = "Selected bets are beating close often enough to monitor price discipline as a production health metric."
        elif (overall.get("beat_close_rate") or 0) < 0.45:
            status = "PRICE_DISCIPLINE_WARNING"
            recommendation = "Selected bets are not beating close; require fresher line capture before increasing bet confidence."
    best_market = None
    market_buckets = [row for row in buckets if row["section"] == "market" and row.get("plays", 0) > 0]
    if market_buckets:
        best_market = max(
            market_buckets,
            key=lambda row: (
                row.get("beat_close_rate") if row.get("beat_close_rate") is not None else -1,
                row.get("avg_clv") if row.get("avg_clv") is not None else -999,
                row.get("plays", 0),
            ),
        )
    return {
        "status": status,
        "recommendation": recommendation,
        "best_market_by_clv": best_market,
    }


def build(ledger, market_rows):
    market_lookup = market_index(market_rows)
    clv_rows = [
        clv_row(row, market_lookup.get(join_key(row)))
        for row in selected_rows(ledger)
    ]
    buckets = (
        bucket_rows(clv_rows, "market")
        + bucket_rows(clv_rows, "clv_direction")
        + bucket_rows(clv_rows, "warps_spread_pick_alignment")
        + bucket_rows(clv_rows, "value_gap_pick_alignment")
    )
    overall = summarize(clv_rows)
    return {
        "selected_bets": len(clv_rows),
        "market_reference_rows": len(market_rows),
        "overall": overall,
        "buckets": buckets,
        "verdict": verdict(overall, buckets),
        "rows": clv_rows,
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


def markdown_report(payload):
    lines = [
        "# Closing Line Value Audit",
        "",
        "This report compares selected engine bets against the historical market spine close/reference line.",
        "",
        "## Verdict",
        "",
        f"- Status: {payload['verdict']['status']}",
        f"- Recommendation: {payload['verdict']['recommendation']}",
        f"- Selected bets: {payload['selected_bets']}",
        f"- Avg CLV: {payload['overall']['avg_clv']}",
        f"- Beat-close rate: {payload['overall']['beat_close_rate']}",
        "",
        "## Buckets",
        "",
        "| Section | Bucket | Plays | W-L-P | Avg CLV | Beat Close |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["buckets"]:
        lines.append(
            f"| {row['section']} | {row['bucket']} | {row['plays']} | "
            f"{row['wins']}-{row['losses']}-{row['pushes']} | {row['avg_clv']} | {row['beat_close_rate']} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Spread CLV is measured from the selected side perspective.",
        "- Total CLV is positive when an over has a lower picked line than close or an under has a higher picked line than close.",
        "- Moneyline CLV is measured as closing implied probability minus picked implied probability.",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--market-spine", type=Path, default=DEFAULT_MARKET_SPINE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--buckets-output", type=Path, default=DEFAULT_BUCKETS)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build(load_csv(args.ledger), load_csv(args.market_spine))
    public_payload = {key: value for key, value in payload.items() if key != "rows"}
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(public_payload, indent=2))
    write_csv(args.csv_output, payload["rows"])
    write_csv(args.buckets_output, payload["buckets"])
    args.md_output.write_text(markdown_report(public_payload))
    print(json.dumps({
        "selected_bets": public_payload["selected_bets"],
        "overall": public_payload["overall"],
        "verdict": public_payload["verdict"],
    }, indent=2))
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.buckets_output}")
    print(f"Wrote {args.md_output}")


if __name__ == "__main__":
    main()
