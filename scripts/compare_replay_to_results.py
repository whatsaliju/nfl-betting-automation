#!/usr/bin/env python3
"""
Score replayed analyzer picks against final NFL results.

The replay outputs contain model recommendations and the exact market lines used
at analysis time. This script joins those picks to nflverse final scores, grades
spread and total plays, and writes summary CSV/JSON files next to the replay.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nfl_common import (
    TEAM_MAP,
    nflverse_game_types,
    normalize_season_type,
    split_matchup,
    spread_line_for_side,
    total_line_for_side,
)


DEFAULT_REPLAY_ROOT = ROOT / "data" / "backtests" / "engine_2026_1"
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

# nflverse can lag or omit scores for a few late-season rows depending on the
# release snapshot. Keep verified overrides explicit so backtest grades remain
# traceable instead of silently mixing result sources.
RESULT_OVERRIDES = {
    (14, "Los Angeles Rams", "Arizona Cardinals"): {
        "away_score": 45,
        "home_score": 17,
        "result_source": "manual_override",
        "result_source_name": "ESPN game page",
        "result_source_url": "https://www.espn.com/nfl/game?gameId=401772901",
    },
    (15, "Detroit Lions", "Los Angeles Rams"): {
        "away_score": 34,
        "home_score": 41,
        "result_source": "manual_override",
        "result_source_name": "ESPN game page",
        "result_source_url": "https://www.espn.com/nfl/game?gameId=401772909",
    },
    (18, "Arizona Cardinals", "Los Angeles Rams"): {
        "away_score": 20,
        "home_score": 37,
        "result_source": "manual_override",
        "result_source_name": "ESPN game page",
        "result_source_url": "https://www.espn.com/nfl/game?gameId=401772955",
    },
}


def infer_replay_season_type(replay_root):
    for path in Path(replay_root).glob("week*"):
        match = re.search(r"week(\d+)", path.name)
        if match and int(match.group(1)) > 18:
            return "POST"
    return "REG"


def load_results(season, season_type="REG"):
    season_type = normalize_season_type(season_type)
    wanted = {"season", "week", "season_type", "game_type", "away_team", "home_team", "away_score", "home_score"}
    usecols = lambda col: col in wanted
    games = pd.read_csv(SCHEDULES_URL, usecols=usecols)
    mask = (games["season"] == season) & games["away_score"].notna() & games["home_score"].notna()
    if "season_type" in games.columns:
        mask &= games["season_type"] == season_type
    elif "game_type" in games.columns:
        mask &= games["game_type"].isin(nflverse_game_types(season_type))
    games = games[mask].copy()

    results = {}
    for row in games.itertuples(index=False):
        away_full = TEAM_MAP.get(row.away_team, row.away_team)
        home_full = TEAM_MAP.get(row.home_team, row.home_team)
        results[(int(row.week), away_full, home_full)] = {
            "away_score": int(row.away_score),
            "home_score": int(row.home_score),
            "away_abbr": row.away_team,
            "home_abbr": row.home_team,
            "result_source": "nflverse",
            "result_source_name": "nflverse schedules",
            "result_source_url": SCHEDULES_URL,
        }
    if season_type == "REG":
        results.update(RESULT_OVERRIDES)
    return results


def grade_spread(side, line, away_score, home_score):
    if line is None:
        return "missing_line", None
    margin = away_score - home_score if side == "AWAY" else home_score - away_score
    cover_margin = margin + line
    if cover_margin > 0:
        return "win", cover_margin
    if cover_margin < 0:
        return "loss", cover_margin
    return "push", cover_margin


def grade_total(side, line, away_score, home_score):
    if line is None:
        return "missing_line", None
    total = away_score + home_score
    margin = total - line if side == "OVER" else line - total
    if margin > 0:
        return "win", margin
    if margin < 0:
        return "loss", margin
    return "push", margin


def iter_pick_rows(replay_root, season, stage):
    pattern = f"week*/{stage}/week*_analytics.json"
    for path in sorted(Path(replay_root).glob(pattern)):
        week_match = re.search(r"week(\d+)_analytics", path.name)
        week = int(week_match.group(1)) if week_match else int(path.parts[-3].replace("week", ""))
        games = json.loads(path.read_text())
        for game in games:
            meta = game.get("pick_metadata") or {}
            market = meta.get("market")
            if market in (None, "none"):
                continue

            away, home = split_matchup(game["matchup"])
            sharp = game.get("sharp_analysis") or {}
            line = None
            if market == "spread":
                side = meta.get("side")
                line = spread_line_for_side((sharp.get("spread") or {}).get("line"), side)
                pick = away if side == "AWAY" else home
            elif market == "total":
                side = meta.get("side")
                line = total_line_for_side((sharp.get("total") or {}).get("line"), side)
                pick = side
            else:
                continue

            trace = meta.get("trace") or game.get("recommendation_trace") or {}
            final_trace = trace.get("final_decision") or {}
            candidates = trace.get("market_candidates") or {}
            market_trace = candidates.get(market) or {}
            signals = market_trace.get("signals") or []
            conflicts = market_trace.get("conflicts") or []

            yield {
                "season": season,
                "week": week,
                "matchup": game["matchup"],
                "away_team": away,
                "home_team": home,
                "market": market,
                "side": meta.get("side"),
                "pick": pick,
                "line": line,
                "selector_score": meta.get("score"),
                "reasons": "; ".join(meta.get("reasons", [])),
                "recommendation": game.get("recommendation"),
                "classification": game.get("classification"),
                "data_quality_status": (game.get("data_quality") or {}).get("status", ""),
                "unsafe_sources": ",".join((game.get("data_quality") or {}).get("unsafe_sources", [])),
                "degraded_sources": ",".join((game.get("data_quality") or {}).get("degraded_sources", [])),
                "trace_final_market": final_trace.get("market", ""),
                "trace_final_side": final_trace.get("side", ""),
                "trace_final_reason": final_trace.get("reason", ""),
                "trace_market_score": market_trace.get("score", ""),
                "trace_market_threshold": market_trace.get("threshold", ""),
                "trace_market_cleared": market_trace.get("cleared_threshold", ""),
                "trace_aligned_sources": ";".join(
                    str(signal.get("source", "")) for signal in signals if signal.get("status") == "aligned"
                ),
                "trace_conflict_sources": ";".join(str(conflict.get("source", "")) for conflict in conflicts),
                "trace_blockers": ";".join(str(blocker) for blocker in market_trace.get("blockers", [])),
            }


def summarize(rows):
    graded = [row for row in rows if row.get("result") in {"win", "loss", "push"}]
    missing_results = [row for row in rows if row.get("result") == "missing_result"]
    missing_lines = [row for row in rows if row.get("result") == "missing_line"]
    decisions = [row for row in graded if row["result"] != "push"]
    wins = sum(1 for row in decisions if row["result"] == "win")
    losses = sum(1 for row in decisions if row["result"] == "loss")
    pushes = sum(1 for row in graded if row["result"] == "push")

    by_market = {}
    for market in sorted({row["market"] for row in rows}):
        market_rows = [row for row in graded if row["market"] == market]
        market_decisions = [row for row in market_rows if row["result"] != "push"]
        market_wins = sum(1 for row in market_decisions if row["result"] == "win")
        market_losses = sum(1 for row in market_decisions if row["result"] == "loss")
        by_market[market] = {
            "graded": len(market_rows),
            "wins": market_wins,
            "losses": market_losses,
            "pushes": sum(1 for row in market_rows if row["result"] == "push"),
            "win_rate": round(market_wins / len(market_decisions), 4) if market_decisions else None,
        }

    by_result_source = {}
    for row in graded:
        source = row.get("result_source") or "unknown"
        by_result_source[source] = by_result_source.get(source, 0) + 1

    return {
        "plays": len(rows),
        "graded": len(graded),
        "missing_results": len(missing_results),
        "missing_lines": len(missing_lines),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / len(decisions), 4) if decisions else None,
        "by_market": by_market,
        "by_result_source": by_result_source,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare replay picks to final NFL results")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--stage", default="final")
    parser.add_argument("--season-type", default=None, help="REG or POST. Defaults to POST when replay root has week19+.")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY_ROOT))
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    replay_root = Path(args.replay_root)
    output_dir = Path(args.output_dir) if args.output_dir else replay_root
    output_dir.mkdir(parents=True, exist_ok=True)

    season_type = normalize_season_type(args.season_type or infer_replay_season_type(replay_root))
    results = load_results(args.season, season_type)
    rows = []
    for row in iter_pick_rows(replay_root, args.season, args.stage):
        actual = results.get((row["week"], row["away_team"], row["home_team"]))
        if not actual:
            row.update({"result": "missing_result"})
            rows.append(row)
            continue

        away_score = actual["away_score"]
        home_score = actual["home_score"]
        if row["market"] == "spread":
            result, margin = grade_spread(row["side"], row["line"], away_score, home_score)
        else:
            result, margin = grade_total(row["side"], row["line"], away_score, home_score)

        row.update({
            "away_score": away_score,
            "home_score": home_score,
            "final_total": away_score + home_score,
            "result_source": actual.get("result_source", ""),
            "result_source_name": actual.get("result_source_name", ""),
            "result_source_url": actual.get("result_source_url", ""),
            "result": result,
            "margin_to_line": margin,
        })
        rows.append(row)

    summary = summarize(rows)
    summary["season_type"] = season_type
    rows_path = output_dir / "pick_results.csv"
    summary_path = output_dir / "pick_results_summary.json"

    if rows:
        fieldnames = sorted({key for row in rows for key in row.keys()})
        with open(rows_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    summary_path.write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"Wrote {rows_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
