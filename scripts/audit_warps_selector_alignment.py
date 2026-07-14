#!/usr/bin/env python3
"""Audit whether WARPS game priors improve weekly selector decisions.

This is a quality-gate study, not a betting ROI model. It joins graded engine
replay picks to historical WARPS game edges and asks whether selector spread
picks perform differently when WARPS agrees, conflicts, or is missing.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_WARPS = ROOT / "data" / "backtests" / "warps_game_edges" / "warps_game_edges.csv"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "warps_selector_alignment_audit.json"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "warps_selector_alignment_buckets.csv"
DEFAULT_ROWS = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "warps_selector_alignment_rows.csv"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "warps_selector_alignment_audit.md"


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


def warps_index(rows):
    return {join_key(row): row for row in rows if row.get("matchup_key")}


def is_graded_pick(row):
    return row.get("best_edge_market") and row.get("bet_result") in {"win", "loss", "push"}


def is_spread_side_pick(row):
    return row.get("best_edge_market") == "spread" and row.get("best_edge_side") in {"AWAY", "HOME"}


def alignment(selector_side, warps_side):
    if selector_side not in {"AWAY", "HOME"}:
        return "non_side_pick" if selector_side else "no_pick"
    if warps_side not in {"AWAY", "HOME"}:
        return "missing"
    return "aligned" if selector_side == warps_side else "conflict"


def edge_bucket(edge_points):
    value = number_or_none(edge_points)
    if value is None:
        return "missing"
    value = abs(value)
    if value >= 3:
        return "abs>=3"
    if value >= 2:
        return "abs2_to_3"
    if value >= 1:
        return "abs1_to_2"
    return "abs<1"


def enrich_row(row, warps):
    joined = warps.get(join_key(row))
    spread_side = (joined or {}).get("spread_pick_side") or ""
    spread_alignment = (
        alignment(row.get("best_edge_side"), spread_side)
        if is_spread_side_pick(row)
        else "non_spread_pick"
    )
    spread_edge = number_or_none((joined or {}).get("spread_edge_points"))
    ml_side = (joined or {}).get("ml_pick_side") or ""
    return {
        **row,
        "warps_joined": "true" if joined else "false",
        "warps_spread_side": spread_side,
        "warps_spread_team": (joined or {}).get("spread_pick_team") or "",
        "warps_spread_edge_points": spread_edge if spread_edge is not None else "",
        "warps_spread_edge_bucket": edge_bucket(spread_edge),
        "warps_spread_pick_alignment": spread_alignment,
        "warps_fair_home_spread": (joined or {}).get("fair_home_spread") or "",
        "warps_fair_away_spread": (joined or {}).get("fair_away_spread") or "",
        "warps_home_win_prob": (joined or {}).get("home_win_prob") or "",
        "warps_away_win_prob": (joined or {}).get("away_win_prob") or "",
        "warps_ml_side": ml_side,
        "warps_ml_team": (joined or {}).get("ml_pick_team") or "",
        "warps_ml_edge_prob": (joined or {}).get("ml_edge_prob") or "",
        "warps_ml_ev": (joined or {}).get("ml_ev") or "",
    }


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


def bucket_rows(rows, dimension):
    buckets = defaultdict(list)
    for row in rows:
        buckets[row.get(dimension) or "NONE"].append(row)
    return [
        {
            "dimension": dimension,
            "value": value,
            **summarize(bucket),
        }
        for value, bucket in sorted(buckets.items())
    ]


def policy_baseline(row):
    return True


def policy_warps_no_conflict(row):
    if not is_spread_side_pick(row):
        return True
    return row.get("warps_spread_pick_alignment") != "conflict"


def policy_warps_aligned_only(row):
    if not is_spread_side_pick(row):
        return True
    return row.get("warps_spread_pick_alignment") == "aligned"


def policy_warps_min_1pt_no_conflict(row):
    if not is_spread_side_pick(row):
        return True
    edge = number_or_none(row.get("warps_spread_edge_points"))
    return row.get("warps_spread_pick_alignment") != "conflict" and edge is not None and abs(edge) >= 1


def policy_warps_min_2pt_aligned(row):
    if not is_spread_side_pick(row):
        return True
    edge = number_or_none(row.get("warps_spread_edge_points"))
    return row.get("warps_spread_pick_alignment") == "aligned" and edge is not None and abs(edge) >= 2


POLICIES = {
    "baseline": {
        "description": "Keep every graded engine pick.",
        "fn": policy_baseline,
    },
    "warps_no_conflict": {
        "description": "Keep totals; remove spread picks when WARPS conflicts with the selector side.",
        "fn": policy_warps_no_conflict,
    },
    "warps_aligned_only": {
        "description": "Keep totals; require spread picks to agree with WARPS.",
        "fn": policy_warps_aligned_only,
    },
    "warps_min_1pt_no_conflict": {
        "description": "Keep totals; require spread picks to have at least 1 WARPS point and no conflict.",
        "fn": policy_warps_min_1pt_no_conflict,
    },
    "warps_min_2pt_aligned": {
        "description": "Keep totals; require spread picks to agree with WARPS by at least 2 points.",
        "fn": policy_warps_min_2pt_aligned,
    },
}


def simulate_policies(rows):
    baseline = summarize(rows)
    output = []
    for name, policy in POLICIES.items():
        kept = [row for row in rows if policy["fn"](row)]
        removed = [row for row in rows if not policy["fn"](row)]
        kept_summary = summarize(kept)
        removed_summary = summarize(removed)
        output.append({
            "policy": name,
            "description": policy["description"],
            **kept_summary,
            "removed_plays": removed_summary["plays"],
            "removed_wins": removed_summary["wins"],
            "removed_losses": removed_summary["losses"],
            "removed_pushes": removed_summary["pushes"],
            "removed_win_rate": removed_summary["win_rate"],
            "plays_delta": kept_summary["plays"] - baseline["plays"],
            "wins_delta": kept_summary["wins"] - baseline["wins"],
            "losses_delta": kept_summary["losses"] - baseline["losses"],
            "win_rate_delta": (
                round(kept_summary["win_rate"] - baseline["win_rate"], 4)
                if kept_summary["win_rate"] is not None and baseline["win_rate"] is not None
                else None
            ),
        })
    return output


def verdict(policy_rows, spread_buckets):
    baseline = next((row for row in policy_rows if row["policy"] == "baseline"), {})
    no_conflict = next((row for row in policy_rows if row["policy"] == "warps_no_conflict"), {})
    aligned = next(
        (row for row in spread_buckets if row["dimension"] == "warps_spread_pick_alignment" and row["value"] == "aligned"),
        {},
    )
    conflict = next(
        (row for row in spread_buckets if row["dimension"] == "warps_spread_pick_alignment" and row["value"] == "conflict"),
        {},
    )
    sample = baseline.get("plays") or 0
    if sample < 40:
        status = "MONITOR_ONLY"
        recommendation = "Sample is still thin; keep WARPS as an explanation and conflict tag."
    elif no_conflict.get("win_rate_delta") and no_conflict["win_rate_delta"] >= 0.03:
        status = "CANDIDATE_SOFT_VETO"
        recommendation = "Simulate WARPS conflicts as a spread downgrade before promoting to production."
    elif conflict.get("plays", 0) >= 8 and (conflict.get("win_rate") or 0) < (baseline.get("win_rate") or 0):
        status = "WATCH_CONFLICTS"
        recommendation = "WARPS conflicts look weaker than baseline; keep monitoring as a spread warning."
    else:
        status = "CONTEXT_ONLY"
        recommendation = "WARPS has not cleared a gating threshold; keep it as fair-line context."
    return {
        "status": status,
        "recommendation": recommendation,
        "baseline_win_rate": baseline.get("win_rate"),
        "aligned_win_rate": aligned.get("win_rate"),
        "conflict_win_rate": conflict.get("win_rate"),
        "no_conflict_policy_delta": no_conflict.get("win_rate_delta"),
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
        "# WARPS Selector Alignment Audit",
        "",
        "This audit joins graded weekly engine picks to historical WARPS fair-line game priors.",
        "It is a quality-gate study, not an ROI calculation.",
        "",
        "## Verdict",
        "",
        f"- Status: {payload['verdict']['status']}",
        f"- Recommendation: {payload['verdict']['recommendation']}",
        f"- Baseline win rate: {payload['baseline'].get('win_rate')}",
        f"- Aligned win rate: {payload['verdict'].get('aligned_win_rate')}",
        f"- Conflict win rate: {payload['verdict'].get('conflict_win_rate')}",
        "",
        "## Alignment Buckets",
        "",
        "| Bucket | Plays | W-L-P | Win Rate |",
        "|---|---:|---:|---:|",
    ]
    for row in payload["alignment_buckets"]:
        if row["dimension"] != "warps_spread_pick_alignment":
            continue
        lines.append(
            f"| {row['value']} | {row['plays']} | {row['wins']}-{row['losses']}-{row['pushes']} | {row['win_rate']} |"
        )
    lines.extend([
        "",
        "## Policy Simulations",
        "",
        "| Policy | Plays | W-L-P | Win Rate | Removed W-L-P | Delta |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in payload["policy_simulations"]:
        lines.append(
            f"| {row['policy']} | {row['plays']} | {row['wins']}-{row['losses']}-{row['pushes']} | "
            f"{row['win_rate']} | {row['removed_wins']}-{row['removed_losses']}-{row['removed_pushes']} | "
            f"{row['win_rate_delta']} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Totals are kept in WARPS policy simulations because this audit is focused on spread-side agreement.",
        "- Use this as a downgrade/upgrade candidate only after enough graded rows accumulate.",
    ])
    return "\n".join(lines)


def build(features, warps_rows):
    indexed_warps = warps_index(warps_rows)
    enriched = [enrich_row(row, indexed_warps) for row in features]
    graded = [row for row in enriched if is_graded_pick(row)]
    spread_graded = [row for row in graded if is_spread_side_pick(row)]
    alignment_buckets = (
        bucket_rows(spread_graded, "warps_spread_pick_alignment")
        + bucket_rows(spread_graded, "warps_spread_edge_bucket")
        + bucket_rows(graded, "best_edge_market")
    )
    policy_rows = simulate_policies(graded)
    payload = {
        "features": len(features),
        "graded_picks": len(graded),
        "graded_spread_picks": len(spread_graded),
        "warps_joined": sum(1 for row in graded if row.get("warps_joined") == "true"),
        "baseline": summarize(graded),
        "alignment_buckets": alignment_buckets,
        "policy_simulations": policy_rows,
        "verdict": verdict(policy_rows, alignment_buckets),
        "enriched_rows": enriched,
    }
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--warps", type=Path, default=DEFAULT_WARPS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--rows-output", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build(load_csv(args.features), load_csv(args.warps))
    public_payload = {key: value for key, value in payload.items() if key != "enriched_rows"}
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(public_payload, indent=2))
    write_csv(args.csv_output, payload["alignment_buckets"] + payload["policy_simulations"])
    write_csv(args.rows_output, payload["enriched_rows"])
    args.md_output.write_text(markdown_report(public_payload))
    print(json.dumps({
        "graded_picks": public_payload["graded_picks"],
        "graded_spread_picks": public_payload["graded_spread_picks"],
        "warps_joined": public_payload["warps_joined"],
        "verdict": public_payload["verdict"],
    }, indent=2))
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.rows_output}")
    print(f"Wrote {args.md_output}")


if __name__ == "__main__":
    main()
