#!/usr/bin/env python3
"""Build a canonical one-row-per-game feature table for modeling.

This table is the bridge between the weekly analyzer outputs, matrix/site
overlays, and future learning/backtest scripts. It intentionally keeps every
feature flat and columnar so it can be loaded by pandas, spreadsheet tools, or
simple audit scripts without understanding the nested website feed schema.
"""

import argparse
import csv
import json
import re
import sys
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nfl_common import canonical_team, split_matchup
from builders.build_matrix_engine_feed import (
    build_team_expectations,
    candidate_payload,
    expectation_matchup_payload,
    market_status,
    number_or_none,
    team_conference,
    team_division,
)

DEFAULT_FEED = ROOT / "data" / "historical" / "matrix_engine_feed.json"
DEFAULT_JSON = ROOT / "data" / "historical" / "game_features.json"
DEFAULT_CSV = ROOT / "data" / "historical" / "game_features.csv"


def number_or_blank(value):
    return "" if value is None else value


def clamp(value, low, high):
    return max(low, min(high, value))


def parse_moneyline_line(line):
    values = re.findall(r"([+-]\d+)", str(line or ""))
    if len(values) < 2:
        return None, None
    return int(values[0]), int(values[1])


def american_implied_probability(odds):
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def american_profit_per_unit(odds):
    if odds is None:
        return None
    if odds > 0:
        return odds / 100
    return 100 / abs(odds)


def devig_moneyline(away_odds, home_odds):
    away_raw = american_implied_probability(away_odds)
    home_raw = american_implied_probability(home_odds)
    if away_raw is None or home_raw is None:
        return None, None, None
    total = away_raw + home_raw
    if total <= 0:
        return None, None, None
    return away_raw / total, home_raw / total, total - 1


def moneyline_model_probability(expectation, sharp_moneyline=None):
    """Return conservative away/home win probabilities for research.

    This is intentionally small-c conservative: expectation deltas nudge a
    neutral 50/50 baseline, while sharp ML direction gets a modest bump. It is
    not yet a production moneyline selector.
    """
    away_prob = 0.5
    pythag_delta = number_or_none(expectation.get("pythagorean_wins_delta"))
    value_delta = number_or_none(expectation.get("pythagorean_vs_vegas_delta"))
    vegas_delta = number_or_none(expectation.get("vegas_win_total_delta"))
    over_delta = number_or_none(expectation.get("actual_vs_pythagorean_delta"))

    if pythag_delta is not None:
        away_prob += clamp(pythag_delta * 0.018, -0.16, 0.16)
    if value_delta is not None:
        away_prob += clamp(value_delta * 0.012, -0.10, 0.10)
    if vegas_delta is not None:
        away_prob += clamp(vegas_delta * 0.008, -0.06, 0.06)
    if over_delta is not None:
        away_prob += clamp(over_delta * 0.025, -0.05, 0.05)

    sharp_moneyline = sharp_moneyline or {}
    sharp_direction = sharp_moneyline.get("direction")
    sharp_score = abs(number_or_none(sharp_moneyline.get("score")) or 0)
    sharp_bump = min(0.025 * sharp_score, 0.06)
    if sharp_direction == "AWAY":
        away_prob += sharp_bump
    elif sharp_direction == "HOME":
        away_prob -= sharp_bump

    away_prob = clamp(away_prob, 0.05, 0.95)
    return away_prob, 1 - away_prob


def moneyline_ev(probability, odds):
    profit = american_profit_per_unit(odds)
    if probability is None or profit is None:
        return None
    return probability * profit - (1 - probability)


def moneyline_research_payload(line, expectation, sharp_moneyline=None):
    away_odds, home_odds = parse_moneyline_line(line)
    away_fair, home_fair, hold = devig_moneyline(away_odds, home_odds)
    if away_odds is None or away_fair is None:
        return {
            "market": "moneyline",
            "status": "not_priced",
            "side": None,
            "reason": "moneyline odds unavailable",
        }

    away_model, home_model = moneyline_model_probability(expectation, sharp_moneyline)
    away_edge = away_model - away_fair
    home_edge = home_model - home_fair
    away_ev = moneyline_ev(away_model, away_odds)
    home_ev = moneyline_ev(home_model, home_odds)

    side = "AWAY" if away_ev >= home_ev else "HOME"
    selected_ev = away_ev if side == "AWAY" else home_ev
    selected_edge = away_edge if side == "AWAY" else home_edge
    if expectation.get("sample_warning"):
        status = "research_thin_sample"
    elif selected_ev >= 0.03 and selected_edge >= 0.025:
        status = "playable"
    elif selected_ev > 0 and selected_edge > 0:
        status = "lean"
    else:
        status = "no_edge"

    return {
        "market": "moneyline",
        "status": status,
        "side": side if status in {"playable", "lean", "research_thin_sample"} else None,
        "line": line,
        "away_odds": away_odds,
        "home_odds": home_odds,
        "away_fair_prob": round(away_fair, 4),
        "home_fair_prob": round(home_fair, 4),
        "market_hold": round(hold, 4),
        "away_model_prob": round(away_model, 4),
        "home_model_prob": round(home_model, 4),
        "away_edge": round(away_edge, 4),
        "home_edge": round(home_edge, 4),
        "away_ev": round(away_ev, 4),
        "home_ev": round(home_ev, 4),
        "selected_ev": round(selected_ev, 4),
        "selected_edge": round(selected_edge, 4),
    }


def side_winner(away_score, home_score):
    if away_score is None or home_score is None:
        return ""
    if away_score > home_score:
        return "AWAY"
    if home_score > away_score:
        return "HOME"
    return "PUSH"


def bool_text(value):
    if value is None:
        return ""
    return "true" if bool(value) else "false"


def side_alignment(feature_side, pick_side):
    if pick_side not in {"AWAY", "HOME"}:
        return "non_side_pick" if pick_side else "no_pick"
    if feature_side in ("", None, "NONE"):
        return "missing"
    if feature_side == "NEUTRAL":
        return "neutral"
    return "aligned" if feature_side == pick_side else "conflict"


def get_market(game, market):
    return (game.get("markets") or {}).get(market) or {}


def get_context(game):
    return game.get("expectation_context") or {}


def market_signal_sources(market):
    return ";".join(
        str(signal.get("source", ""))
        for signal in market.get("signals", [])
        if signal.get("source")
    )


def market_conflict_sources(market):
    return ";".join(
        str(conflict.get("source", ""))
        for conflict in market.get("conflicts", [])
        if conflict.get("source")
    )


def build_row(game):
    best = game.get("best_edge") or {}
    spread = get_market(game, "spread")
    total = get_market(game, "total")
    moneyline = get_market(game, "moneyline")
    schedule = game.get("schedule_context") or {}
    expectation = get_context(game)
    result = game.get("result") or {}
    away_score = result.get("away_score")
    home_score = result.get("home_score")
    best_side = best.get("side") or ""
    pythagorean_side = expectation.get("pythagorean_side") or ""
    market_expectation_side = expectation.get("market_expectation_side") or ""
    value_gap_side = expectation.get("value_gap_side") or ""
    overperformance_side = expectation.get("overperformance_side") or ""

    return {
        "season": game.get("season"),
        "season_type": game.get("season_type"),
        "week": game.get("week"),
        "matchup_key": game.get("matchup_key"),
        "away_tla": game.get("away_tla"),
        "home_tla": game.get("home_tla"),
        "stage": game.get("stage"),
        "analysis_available": bool_text(game.get("analysis_available")),
        "best_edge_market": best.get("market") or "",
        "best_edge_side": best_side,
        "best_edge_score": number_or_blank(best.get("score")),
        "best_edge_status": best.get("status") or "",
        "best_edge_label": best.get("label") or "",
        "engine_recommendation": best.get("recommendation") or "",
        "spread_side": spread.get("side") or "",
        "spread_score": number_or_blank(spread.get("score")),
        "spread_threshold": number_or_blank(spread.get("threshold")),
        "spread_status": spread.get("status") or "",
        "spread_cleared_threshold": bool_text(spread.get("cleared_threshold")),
        "spread_blocked": bool_text(spread.get("blocked")),
        "spread_blockers": ";".join(str(item) for item in spread.get("blockers", [])),
        "spread_signal_sources": market_signal_sources(spread),
        "spread_conflict_sources": market_conflict_sources(spread),
        "total_side": total.get("side") or "",
        "total_score": number_or_blank(total.get("score")),
        "total_threshold": number_or_blank(total.get("threshold")),
        "total_status": total.get("status") or "",
        "total_cleared_threshold": bool_text(total.get("cleared_threshold")),
        "total_blocked": bool_text(total.get("blocked")),
        "total_blockers": ";".join(str(item) for item in total.get("blockers", [])),
        "total_signal_sources": market_signal_sources(total),
        "total_conflict_sources": market_conflict_sources(total),
        "moneyline_status": moneyline.get("status") or "",
        "moneyline_side": moneyline.get("side") or "",
        "moneyline_line": moneyline.get("line") or "",
        "moneyline_away_odds": number_or_blank(moneyline.get("away_odds")),
        "moneyline_home_odds": number_or_blank(moneyline.get("home_odds")),
        "moneyline_away_fair_prob": number_or_blank(moneyline.get("away_fair_prob")),
        "moneyline_home_fair_prob": number_or_blank(moneyline.get("home_fair_prob")),
        "moneyline_away_model_prob": number_or_blank(moneyline.get("away_model_prob")),
        "moneyline_home_model_prob": number_or_blank(moneyline.get("home_model_prob")),
        "moneyline_away_edge": number_or_blank(moneyline.get("away_edge")),
        "moneyline_home_edge": number_or_blank(moneyline.get("home_edge")),
        "moneyline_away_ev": number_or_blank(moneyline.get("away_ev")),
        "moneyline_home_ev": number_or_blank(moneyline.get("home_ev")),
        "moneyline_selected_ev": number_or_blank(moneyline.get("selected_ev")),
        "moneyline_selected_edge": number_or_blank(moneyline.get("selected_edge")),
        "moneyline_market_hold": number_or_blank(moneyline.get("market_hold")),
        "division_game": bool_text(schedule.get("division_game")),
        "conference_game": bool_text(schedule.get("conference_game")),
        "away_division": schedule.get("away_division") or "",
        "home_division": schedule.get("home_division") or "",
        "pythagorean_side": pythagorean_side,
        "market_expectation_side": market_expectation_side,
        "value_gap_side": value_gap_side,
        "overperformance_side": overperformance_side,
        "pythagorean_pick_alignment": side_alignment(pythagorean_side, best_side),
        "market_expectation_pick_alignment": side_alignment(market_expectation_side, best_side),
        "value_gap_pick_alignment": side_alignment(value_gap_side, best_side),
        "overperformance_pick_alignment": side_alignment(overperformance_side, best_side),
        "pythagorean_wins_delta": number_or_blank(expectation.get("pythagorean_wins_delta")),
        "vegas_win_total_delta": number_or_blank(expectation.get("vegas_win_total_delta")),
        "pythagorean_vs_vegas_delta": number_or_blank(expectation.get("pythagorean_vs_vegas_delta")),
        "actual_vs_pythagorean_delta": number_or_blank(expectation.get("actual_vs_pythagorean_delta")),
        "expectation_games_tracked_min": number_or_blank(expectation.get("games_tracked_min")),
        "expectation_sample_warning": bool_text(expectation.get("sample_warning")),
        "source_health_status": game.get("source_health_status") or "",
        "data_quality_status": game.get("data_quality_status") or "",
        "away_score": number_or_blank(away_score),
        "home_score": number_or_blank(home_score),
        "straight_up_winner_side": side_winner(away_score, home_score),
        "final_margin_away_minus_home": number_or_blank(result.get("final_margin")),
        "final_total": number_or_blank(result.get("final_total")),
        "bet_result": result.get("bet_result") or "",
        "bet_margin_to_line": number_or_blank(result.get("bet_margin_to_line")),
        "bet_line": number_or_blank(result.get("bet_line")),
        "result_source": result.get("result_source") or "",
    }


def build_rows(feed):
    return [build_row(game) for game in feed.get("edge_board", [])]


def replay_week_from_path(path):
    match = re.search(r"week(\d+)", str(path))
    return int(match.group(1)) if match else None


def load_pick_result_index(replay_root):
    path = Path(replay_root) / "pick_results.csv"
    if not path.exists():
        return {}
    with path.open() as f:
        rows = list(csv.DictReader(f))
    return {
        (int(row["week"]), row["matchup"]): row
        for row in rows
        if row.get("week") and row.get("matchup")
    }


def scored_games_from_pick_results(pick_index):
    games = []
    for (week, matchup), row in pick_index.items():
        away_tla = canonical_team(row.get("away_team"))
        home_tla = canonical_team(row.get("home_team"))
        games.append({
            "season_type": "REG",
            "week": week,
            "away_tla": away_tla,
            "home_tla": home_tla,
            "away_score": number_or_none(row.get("away_score")),
            "home_score": number_or_none(row.get("home_score")),
        })
    return games


def replay_result_payload(result_row):
    if not result_row:
        return {
            "away_score": None,
            "home_score": None,
            "final_margin": None,
            "final_total": None,
        }
    away_score = number_or_none(result_row.get("away_score"))
    home_score = number_or_none(result_row.get("home_score"))
    return {
        "away_score": away_score,
        "home_score": home_score,
        "final_margin": away_score - home_score if away_score is not None and home_score is not None else None,
        "final_total": number_or_none(result_row.get("final_total")),
        "bet_result": result_row.get("result"),
        "bet_margin_to_line": number_or_none(result_row.get("margin_to_line")),
        "bet_line": number_or_none(result_row.get("line")),
        "result_source": result_row.get("result_source"),
    }


def replay_game_payload(game, week, season, stage, expectations, result_row):
    pick = game.get("pick_metadata") or {}
    trace = game.get("recommendation_trace") or pick.get("trace") or {}
    final = trace.get("final_decision") or {}
    spread = candidate_payload(trace, "spread")
    total = candidate_payload(trace, "total")
    sharp_analysis = game.get("sharp_analysis") or {}
    sharp_moneyline = sharp_analysis.get("moneyline") or {}
    market = pick.get("market") or final.get("market")
    side = pick.get("side") or final.get("side")
    best_market = market if market in {"spread", "total"} else None
    away_tla = game.get("away_tla")
    home_tla = game.get("home_tla")
    if not away_tla or not home_tla:
        away, home = split_matchup(game.get("matchup", ""))
        away_tla = canonical_team(away)
        home_tla = canonical_team(home)

    return {
        "season": season,
        "season_type": "REG",
        "week": week,
        "matchup_key": game.get("matchup_key") or f"{away_tla}@{home_tla}",
        "game": game.get("matchup"),
        "away_tla": away_tla,
        "home_tla": home_tla,
        "stage": stage,
        "analysis_available": True,
        "best_edge": {
            "market": best_market,
            "side": side if best_market else None,
            "score": number_or_none(pick.get("score") or final.get("score")),
            "label": game.get("classification"),
            "recommendation": game.get("recommendation"),
            "status": "play" if best_market else "pass",
        },
        "markets": {
            "spread": {**spread, "status": market_status(spread)},
            "total": {**total, "status": market_status(total)},
            "moneyline": moneyline_research_payload(
                sharp_moneyline.get("line"),
                expectation_matchup_payload(away_tla, home_tla, expectations),
                sharp_moneyline,
            ),
        },
        "schedule_context": {
            "division_game": team_division(away_tla) == team_division(home_tla),
            "conference_game": team_conference(away_tla) == team_conference(home_tla),
            "away_division": team_division(away_tla),
            "home_division": team_division(home_tla),
        },
        "expectation_context": expectation_matchup_payload(away_tla, home_tla, expectations),
        "source_health_status": (game.get("data_quality") or {}).get("status"),
        "data_quality_status": (game.get("data_quality") or {}).get("status"),
        "result": replay_result_payload(result_row),
    }


def build_replay_rows(replay_root, season, stage):
    replay_root = Path(replay_root)
    pick_index = load_pick_result_index(replay_root)
    expectations = build_team_expectations(scored_games_from_pick_results(pick_index))
    rows = []
    for path in sorted(replay_root.glob(f"week*/{stage}/week*_analytics.json")):
        week = replay_week_from_path(path)
        for game in json.loads(path.read_text()):
            result_row = pick_index.get((week, game.get("matchup")))
            rows.append(build_row(replay_game_payload(game, week, season, stage, expectations, result_row)))
    return rows


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, default=DEFAULT_FEED)
    parser.add_argument("--replay-root", type=Path, default=None)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--stage", default="final")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    if args.replay_root:
        rows = build_replay_rows(args.replay_root, args.season, args.stage)
    else:
        feed = json.loads(args.feed.read_text())
        rows = build_rows(feed)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(rows, indent=2))
    write_csv(args.csv_output, rows)
    regular = sum(1 for row in rows if row.get("season_type") == "REG")
    playable = sum(1 for row in rows if row.get("best_edge_market"))
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Rows: {len(rows)} | Regular: {regular} | Playable: {playable}")


if __name__ == "__main__":
    main()
