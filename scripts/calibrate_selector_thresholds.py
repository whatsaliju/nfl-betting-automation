#!/usr/bin/env python3
"""Offline calibration grid for recommendation selector traces.

The analyzer trace captures the spread and total candidates before the final
choice. This script reselects from those candidates under alternate thresholds
and context policies, then grades the simulated picks against final results.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nfl_common import split_matchup, spread_line_for_side, total_line_for_side
from scripts.compare_replay_to_results import grade_spread, grade_total, load_results


DEFAULT_REPLAY_ROOT = ROOT / "data" / "backtests" / "engine_2026_1_configured"


def parse_ints(value):
    return [int(part.strip()) for part in str(value).split(",") if part.strip()]


def source_present(candidate, source):
    for item in (candidate.get("signals") or []) + (candidate.get("conflicts") or []):
        if item.get("source") == source:
            return True
    return False


def source_aligned(candidate, source):
    return any(item.get("source") == source for item in candidate.get("signals") or [])


def source_conflicted(candidate, source):
    return any(item.get("source") == source for item in candidate.get("conflicts") or [])


def candidate_side(candidate):
    side = candidate.get("side")
    return str(side).upper() if side else ""


def candidate_score(candidate):
    try:
        return float(candidate.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def iter_games(replay_root, stage):
    pattern = f"week*/{stage}/week*_analytics.json"
    for path in sorted(Path(replay_root).glob(pattern)):
        week_match = re.search(r"week(\d+)", path.name)
        week = int(week_match.group(1)) if week_match else None
        for game in json.loads(path.read_text()):
            yield week, game


def spread_threshold_for(game, base_threshold, injury_policy):
    threshold = base_threshold
    classification = str(game.get("classification") or "")
    if "BLUE CHIP" in classification or "TARGETED" in classification:
        threshold = min(threshold, base_threshold)
    trace = game.get("recommendation_trace") or {}
    spread = (trace.get("market_candidates") or {}).get("spread") or {}
    if injury_policy == "raise_spread_threshold" and source_present(spread, "injury"):
        threshold += 1
    return threshold


def choose_pick(game, spread_threshold, total_threshold, injury_policy, total_policy):
    trace = game.get("recommendation_trace") or {}
    final = trace.get("final_decision") or {}
    if final.get("reason") in {"signal classification was FADE", "signal classification was LANDMINE"}:
        return None

    candidates = trace.get("market_candidates") or {}
    spread = candidates.get("spread") or {}
    total = candidates.get("total") or {}
    spread_side = candidate_side(spread)
    total_side = candidate_side(total)
    spread_score = candidate_score(spread)
    total_score = candidate_score(total)

    adjusted_spread_threshold = spread_threshold_for(game, spread_threshold, injury_policy)
    spread_viable = spread_side in {"AWAY", "HOME"} and spread_score >= adjusted_spread_threshold
    total_viable = total_side in {"OVER", "UNDER"} and total_score >= total_threshold

    if spread.get("blocked") or spread.get("blockers"):
        spread_viable = False
    if total.get("blocked") or total.get("blockers"):
        total_viable = False

    if injury_policy == "block_spread_if_injury_context" and source_present(spread, "injury"):
        spread_viable = False
    if injury_policy == "block_spread_if_injury_conflict" and source_conflicted(spread, "injury"):
        spread_viable = False

    if total_policy == "require_ref_weather" and not source_aligned(total, "ref_weather_context"):
        total_viable = False
    if total_policy == "require_sharp_and_ref_weather" and not (
        source_aligned(total, "sharp") and source_aligned(total, "ref_weather_context")
    ):
        total_viable = False

    if not spread_viable and not total_viable:
        return None
    if total_viable and (not spread_viable or total_score > spread_score):
        return {
            "market": "total",
            "side": total_side,
            "score": total_score,
            "threshold": total_threshold,
            "aligned_sources": sorted(item.get("source") for item in total.get("signals", []) if item.get("source")),
        }
    return {
        "market": "spread",
        "side": spread_side,
        "score": spread_score,
        "threshold": adjusted_spread_threshold,
        "aligned_sources": sorted(item.get("source") for item in spread.get("signals", []) if item.get("source")),
    }


def line_for_pick(game, pick):
    sharp = game.get("sharp_analysis") or {}
    if pick["market"] == "spread":
        return spread_line_for_side((sharp.get("spread") or {}).get("line"), pick["side"])
    return total_line_for_side((sharp.get("total") or {}).get("line"), pick["side"])


def grade_pick(game, week, pick, results):
    away, home = split_matchup(game["matchup"])
    actual = results.get((week, away, home))
    if not actual:
        return "missing_result", None, None
    line = line_for_pick(game, pick)
    if pick["market"] == "spread":
        result, margin = grade_spread(pick["side"], line, actual["away_score"], actual["home_score"])
    else:
        result, margin = grade_total(pick["side"], line, actual["away_score"], actual["home_score"])
    return result, margin, line


def summarize(rows):
    graded = [row for row in rows if row["result"] in {"win", "loss", "push"}]
    wins = sum(1 for row in graded if row["result"] == "win")
    losses = sum(1 for row in graded if row["result"] == "loss")
    pushes = sum(1 for row in graded if row["result"] == "push")
    decisions = wins + losses
    by_market = {}
    for market in ("spread", "total"):
        market_rows = [row for row in graded if row["market"] == market]
        market_wins = sum(1 for row in market_rows if row["result"] == "win")
        market_losses = sum(1 for row in market_rows if row["result"] == "loss")
        market_decisions = market_wins + market_losses
        by_market[market] = {
            "plays": len(market_rows),
            "wins": market_wins,
            "losses": market_losses,
            "win_rate": round(market_wins / market_decisions, 4) if market_decisions else None,
        }
    return {
        "plays": len(rows),
        "graded": len(graded),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
        "avg_margin_to_line": round(sum(float(row["margin_to_line"] or 0) for row in graded) / len(graded), 3)
        if graded else None,
        "by_market": by_market,
    }


def run_policy(games, results, spread_threshold, total_threshold, injury_policy, total_policy):
    rows = []
    for week, game in games:
        pick = choose_pick(game, spread_threshold, total_threshold, injury_policy, total_policy)
        if not pick:
            continue
        result, margin, line = grade_pick(game, week, pick, results)
        rows.append({
            "week": week,
            "matchup": game.get("matchup"),
            "market": pick["market"],
            "side": pick["side"],
            "score": pick["score"],
            "threshold": pick["threshold"],
            "line": line,
            "aligned_sources": "+".join(pick["aligned_sources"]),
            "result": result,
            "margin_to_line": margin,
        })
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Calibrate selector thresholds from replay traces")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--season-type", default="REG")
    parser.add_argument("--stage", default="final")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY_ROOT))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--spread-thresholds", default="3,4,5")
    parser.add_argument("--total-thresholds", default="3,4,5,6")
    parser.add_argument(
        "--injury-policies",
        default="allow,raise_spread_threshold,block_spread_if_injury_context,block_spread_if_injury_conflict",
    )
    parser.add_argument("--total-policies", default="allow,require_ref_weather,require_sharp_and_ref_weather")
    args = parser.parse_args()

    replay_root = Path(args.replay_root)
    output_dir = Path(args.output_dir) if args.output_dir else replay_root
    output_dir.mkdir(parents=True, exist_ok=True)

    games = list(iter_games(replay_root, args.stage))
    results = load_results(args.season, args.season_type)
    summaries = []
    best_rows = []
    best_key = None

    for spread_threshold in parse_ints(args.spread_thresholds):
        for total_threshold in parse_ints(args.total_thresholds):
            for injury_policy in [part.strip() for part in args.injury_policies.split(",") if part.strip()]:
                for total_policy in [part.strip() for part in args.total_policies.split(",") if part.strip()]:
                    rows = run_policy(games, results, spread_threshold, total_threshold, injury_policy, total_policy)
                    summary = summarize(rows)
                    summary.update({
                        "spread_threshold": spread_threshold,
                        "total_threshold": total_threshold,
                        "injury_policy": injury_policy,
                        "total_policy": total_policy,
                    })
                    summaries.append(summary)
                    key = (
                        summary["win_rate"] or 0,
                        summary["plays"],
                        summary["avg_margin_to_line"] or 0,
                    )
                    if best_key is None or key > best_key:
                        best_key = key
                        best_rows = rows

    flat_summaries = []
    for summary in summaries:
        row = {key: value for key, value in summary.items() if key != "by_market"}
        for market, market_summary in summary["by_market"].items():
            for key, value in market_summary.items():
                row[f"{market}_{key}"] = value
        flat_summaries.append(row)

    flat_summaries.sort(
        key=lambda row: (
            -(row.get("win_rate") or 0),
            -(row.get("plays") or 0),
            -(row.get("avg_margin_to_line") or 0),
        )
    )

    write_csv(output_dir / "selector_calibration_grid.csv", flat_summaries)
    write_csv(output_dir / "selector_calibration_best_picks.csv", best_rows)
    (output_dir / "selector_calibration_summary.json").write_text(json.dumps({
        "replay_root": str(replay_root),
        "stage": args.stage,
        "policy_count": len(flat_summaries),
        "top_policies": flat_summaries[:10],
    }, indent=2))

    print(json.dumps({
        "policy_count": len(flat_summaries),
        "top_policies": flat_summaries[:5],
    }, indent=2))
    print(f"Wrote {output_dir / 'selector_calibration_grid.csv'}")
    print(f"Wrote {output_dir / 'selector_calibration_best_picks.csv'}")
    print(f"Wrote {output_dir / 'selector_calibration_summary.json'}")


if __name__ == "__main__":
    main()
