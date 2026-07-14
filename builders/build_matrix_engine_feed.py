#!/usr/bin/env python3
"""Build website-friendly matrix overlays from weekly master files.

The external NFL matrix already owns schedule layout and interaction. This
package gives it a compact feed of engine outputs keyed by matchup and team-week
cell so the site can overlay picks, source status, scores, and postseason rows.
"""

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_DIR = ROOT / "data" / "historical"
OUTPUT_JSON = HISTORICAL_DIR / "matrix_engine_feed.json"
OUTPUT_CSV = HISTORICAL_DIR / "matrix_engine_feed.csv"
READINESS_REPORT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "model_readiness_report.json"
FEATURE_RESEARCH_REPORT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_research_report.json"
FEATURE_POLICY_SIMULATION = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "feature_policy_simulation.json"
FACTOR_LEADERBOARD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_leaderboard.json"
FACTOR_PROMOTION_REPORT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "factor_promotion_report.json"
PROMOTION_OVERLAY_SIMULATION = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "promotion_overlay_simulation.json"
SOURCE_RELIABILITY_REPORT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "source_reliability_report.json"
WARPS_SELECTOR_ALIGNMENT_AUDIT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "warps_selector_alignment_audit.json"
MARKET_ROUTER_AUDIT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "market_router_audit.json"
CLV_AUDIT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "clv_audit.json"
BACKTEST_COVERAGE_REPORT = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "backtest_coverage_report.json"
PICK_EXPLANATIONS = HISTORICAL_DIR / "pick_explanations.json"
WEEKLY_BETTING_CARD = HISTORICAL_DIR / "weekly_betting_card.json"
WARPS_MARKET_OVERLAY = HISTORICAL_DIR / "warps_2026_market_overlay.csv"
STAGES = ("initial", "update", "lock", "final")
PYTHAGOREAN_EXPONENT = 2.37
VEGAS_WIN_TOTALS_2025 = {
    "ARI": 8.5,
    "ATL": 7.5,
    "BAL": 11.5,
    "BUF": 11.5,
    "CAR": 6.5,
    "CHI": 8.5,
    "CIN": 9.5,
    "CLE": 5.5,
    "DAL": 7.5,
    "DEN": 9.5,
    "DET": 10.5,
    "GB": 9.5,
    "HOU": 9.5,
    "IND": 7.5,
    "JAX": 7.5,
    "KC": 11.5,
    "LAC": 9.5,
    "LAR": 9.5,
    "LV": 6.5,
    "MIA": 8.5,
    "MIN": 8.5,
    "NE": 7.5,
    "NO": 6.5,
    "NYG": 5.5,
    "NYJ": 5.5,
    "PHI": 11.5,
    "PIT": 8.5,
    "SEA": 7.5,
    "SF": 10.5,
    "TB": 9.5,
    "TEN": 5.5,
    "WAS": 9.5,
}
DIVISIONS = {
    "AFC East": {"BUF", "MIA", "NE", "NYJ"},
    "AFC North": {"BAL", "CIN", "CLE", "PIT"},
    "AFC South": {"HOU", "IND", "JAX", "TEN"},
    "AFC West": {"DEN", "KC", "LAC", "LV"},
    "NFC East": {"DAL", "NYG", "PHI", "WAS", "WSH"},
    "NFC North": {"CHI", "DET", "GB", "MIN"},
    "NFC South": {"ATL", "CAR", "NO", "TB"},
    "NFC West": {"ARI", "LAR", "SEA", "SF"},
}


def team_division(team):
    team = "WAS" if team == "WSH" else team
    for division, teams in DIVISIONS.items():
        if team in teams:
            return division
    return "Unknown"


def team_conference(team):
    division = team_division(team)
    if division.startswith("AFC"):
        return "AFC"
    if division.startswith("NFC"):
        return "NFC"
    return "Unknown"


def canonical_tla(team):
    return "WAS" if team == "WSH" else team


def sort_master_path(path):
    match = re.search(r"week(?:(PRE)(\d+)|(\d+)|([A-Z]+))_master\.json$", path.name)
    if not match:
        return (9, 999, path.name)
    if match.group(1) == "PRE":
        return (0, int(match.group(2)), path.name)
    if match.group(3):
        return (1, int(match.group(3)), path.name)
    postseason_order = {"WC": 19, "DIV": 20, "CONF": 21, "CON": 21, "SB": 22}
    return (2, postseason_order.get(match.group(4), 999), path.name)


def first_present(row, names):
    for name in names:
        value = row.get(name)
        if value not in (None, "", []):
            return value
    return None


def number_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def text_or_none(value):
    if value in (None, ""):
        return None
    return str(value)


def normalize_trace(trace):
    if isinstance(trace, str) and trace.strip():
        try:
            return json.loads(trace)
        except json.JSONDecodeError:
            return {}
    return trace if isinstance(trace, dict) else {}


def candidate_payload(trace, market):
    candidates = trace.get("market_candidates") or {}
    candidate = candidates.get(market) or {}
    if not candidate:
        return {
            "market": market,
            "side": None,
            "score": None,
            "threshold": None,
            "cleared_threshold": False,
            "blocked": True,
            "blockers": ["candidate unavailable"],
            "signals": [],
            "conflicts": [],
            "reasons": [],
        }
    return {
        "market": market,
        "side": candidate.get("side"),
        "score": number_or_none(candidate.get("score")),
        "threshold": number_or_none(candidate.get("threshold")),
        "cleared_threshold": bool(candidate.get("cleared_threshold")),
        "blocked": bool(candidate.get("blocked")),
        "blockers": candidate.get("blockers") or [],
        "signals": candidate.get("signals") or [],
        "conflicts": candidate.get("conflicts") or [],
        "reasons": candidate.get("reasons") or [],
    }


def market_status(candidate):
    if candidate.get("cleared_threshold"):
        return "playable"
    if candidate.get("blocked"):
        return "blocked"
    if candidate.get("score") is not None:
        return "lean"
    return "unavailable"


def pythagorean_win_pct(points_for, points_against):
    if points_for is None or points_against is None:
        return None
    if points_for <= 0 and points_against <= 0:
        return None
    pf = max(points_for, 0) ** PYTHAGOREAN_EXPONENT
    pa = max(points_against, 0) ** PYTHAGOREAN_EXPONENT
    denominator = pf + pa
    return pf / denominator if denominator else None


def expectation_band(actual_vs_pythag):
    if actual_vs_pythag is None:
        return "unknown"
    if actual_vs_pythag >= 1.0:
        return "overperforming"
    if actual_vs_pythag <= -1.0:
        return "underperforming"
    return "in_line"


def build_team_expectations(games):
    teams = {}
    for team in VEGAS_WIN_TOTALS_2025:
        teams[team] = {
            "team": team,
            "conference": team_conference(team),
            "division": team_division(team),
            "games_tracked": 0,
            "actual_wins": 0,
            "actual_losses": 0,
            "points_for": 0,
            "points_against": 0,
            "vegas_win_total": VEGAS_WIN_TOTALS_2025.get(team),
        }

    for game in games:
        if game.get("season_type") != "REG":
            continue
        away = canonical_tla(game.get("away_tla"))
        home = canonical_tla(game.get("home_tla"))
        away_score = number_or_none(game.get("away_score"))
        home_score = number_or_none(game.get("home_score"))
        if not away or not home or away_score is None or home_score is None:
            continue

        for team in (away, home):
            if team not in teams:
                teams[team] = {
                    "team": team,
                    "conference": team_conference(team),
                    "division": team_division(team),
                    "games_tracked": 0,
                    "actual_wins": 0,
                    "actual_losses": 0,
                    "points_for": 0,
                    "points_against": 0,
                    "vegas_win_total": VEGAS_WIN_TOTALS_2025.get(team),
                }

        away_won = away_score > home_score
        home_won = home_score > away_score
        teams[away]["games_tracked"] += 1
        teams[away]["actual_wins"] += 1 if away_won else 0
        teams[away]["actual_losses"] += 1 if home_won else 0
        teams[away]["points_for"] += away_score
        teams[away]["points_against"] += home_score
        teams[home]["games_tracked"] += 1
        teams[home]["actual_wins"] += 1 if home_won else 0
        teams[home]["actual_losses"] += 1 if away_won else 0
        teams[home]["points_for"] += home_score
        teams[home]["points_against"] += away_score

    payload = {}
    for team, row in teams.items():
        games_tracked = row["games_tracked"]
        win_pct = row["actual_wins"] / games_tracked if games_tracked else None
        pythag_pct = pythagorean_win_pct(row["points_for"], row["points_against"])
        pythag_wins_tracked = pythag_pct * games_tracked if pythag_pct is not None else None
        pythag_wins_17 = pythag_pct * 17 if pythag_pct is not None else None
        actual_vs_pythag = (
            row["actual_wins"] - pythag_wins_tracked
            if pythag_wins_tracked is not None
            else None
        )
        vegas_total = row["vegas_win_total"]
        payload[team] = {
            **row,
            "actual_win_pct": round(win_pct, 4) if win_pct is not None else None,
            "pythagorean_exponent": PYTHAGOREAN_EXPONENT,
            "pythagorean_win_pct": round(pythag_pct, 4) if pythag_pct is not None else None,
            "pythagorean_wins_tracked": round(pythag_wins_tracked, 2) if pythag_wins_tracked is not None else None,
            "pythagorean_wins_17_game_pace": round(pythag_wins_17, 2) if pythag_wins_17 is not None else None,
            "actual_vs_pythagorean": round(actual_vs_pythag, 2) if actual_vs_pythag is not None else None,
            "pythagorean_pace_vs_vegas": (
                round(pythag_wins_17 - vegas_total, 2)
                if pythag_wins_17 is not None and vegas_total is not None
                else None
            ),
            "actual_pace_vs_vegas": (
                round((win_pct * 17) - vegas_total, 2)
                if win_pct is not None and vegas_total is not None
                else None
            ),
            "expectation_band": expectation_band(actual_vs_pythag),
        }

    return payload


def stage_available(row, stage):
    value = row.get(f"has_{stage}")
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def latest_stage(row):
    for stage in reversed(STAGES):
        if stage_available(row, stage):
            return stage
    return None


def stage_payload(row, stage):
    trace = normalize_trace(row.get(f"{stage}_recommendation_trace"))
    return {
        "available": stage_available(row, stage),
        "classification": row.get(f"{stage}_classification"),
        "signal_classification": row.get(f"{stage}_signal_classification"),
        "recommendation": row.get(f"{stage}_recommendation"),
        "pick_market": row.get(f"{stage}_pick_market"),
        "pick_side": row.get(f"{stage}_pick_side"),
        "selector_score": row.get(f"{stage}_selector_score"),
        "pick_reasons": row.get(f"{stage}_pick_reasons"),
        "recommendation_trace": trace,
        "data_quality_status": row.get(f"{stage}_data_quality_status"),
        "source_health_status": row.get(f"{stage}_source_health_status"),
        "source_health_warnings": row.get(f"{stage}_source_health_warnings"),
        "source_health_reference_time": row.get(f"{stage}_source_health_reference_time"),
    }


def latest_payload(row):
    stage = latest_stage(row)
    if not stage:
        return {"stage": None, "available": False}
    payload = stage_payload(row, stage)
    payload["stage"] = stage
    return payload


def game_payload(row):
    latest = latest_payload(row)
    return {
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "week": row.get("week"),
        "matchup_key": row.get("matchup_key"),
        "game": row.get("game"),
        "away_team": row.get("away_team"),
        "home_team": row.get("home_team"),
        "away_tla": row.get("away_tla"),
        "home_tla": row.get("home_tla"),
        "away_score": row.get("away_score"),
        "home_score": row.get("home_score"),
        "final_margin": row.get("final_margin"),
        "final_total": row.get("final_total"),
        "latest": latest,
        "stages": {stage: stage_payload(row, stage) for stage in STAGES},
    }


def delta(left, right, key):
    left_value = (left or {}).get(key)
    right_value = (right or {}).get(key)
    if left_value is None or right_value is None:
        return None
    return round(left_value - right_value, 2)


def side_from_delta(value, threshold=0.5):
    if value is None:
        return None
    if value >= threshold:
        return "AWAY"
    if value <= -threshold:
        return "HOME"
    return "NEUTRAL"


def side_alignment(feature_side, pick_side):
    if pick_side not in {"AWAY", "HOME"}:
        return "no_pick" if not pick_side else "non_side_pick"
    if feature_side in (None, "", "NONE"):
        return "missing"
    if feature_side == "NEUTRAL":
        return "neutral"
    return "aligned" if feature_side == pick_side else "conflict"


def fair_spread_side(overlay):
    home_spread = number_or_none(overlay.get("fair_home_spread"))
    away_spread = number_or_none(overlay.get("fair_away_spread"))
    if home_spread is None or away_spread is None:
        return None
    if home_spread <= -0.5:
        return "HOME"
    if away_spread <= -0.5:
        return "AWAY"
    return "NEUTRAL"


def load_warps_market_overlay():
    if not WARPS_MARKET_OVERLAY.exists():
        return {}
    with WARPS_MARKET_OVERLAY.open() as f:
        rows = list(csv.DictReader(f))
    return {
        (
            str(row.get("season") or ""),
            str(row.get("week") or ""),
            row.get("matchup_key"),
        ): row
        for row in rows
        if row.get("season") and row.get("week") and row.get("matchup_key")
    }


def warps_overlay_payload(game, overlay_index, best_edge):
    overlay = overlay_index.get((
        str(game.get("season") or ""),
        str(game.get("week") or ""),
        game.get("matchup_key"),
    ))
    if not overlay:
        return {
            "available": False,
            "status": "unavailable",
            "recommendation_policy": "forecast_context_only",
            "reason": "WARPS market overlay not available for this matchup",
        }

    priced_side = text_or_none(overlay.get("spread_overlay_side"))
    fair_side = fair_spread_side(overlay)
    spread_side = priced_side or fair_side
    ml_side = text_or_none(overlay.get("ml_overlay_side"))
    pick_market = best_edge.get("market")
    pick_side = best_edge.get("side")
    spread_alignment = (
        side_alignment(spread_side, pick_side)
        if pick_market == "spread"
        else "no_spread_pick"
    )
    ml_alignment = (
        side_alignment(ml_side, pick_side)
        if pick_market == "moneyline"
        else "research_only"
    )

    return {
        "available": True,
        "status": overlay.get("status") or "fair_line_only",
        "source": overlay.get("source") or "WARPS game prior",
        "recommendation_policy": overlay.get("recommendation_policy") or "overlay_only_until_weekly_engine_confirmation",
        "historical_policy": "WARPS game priors are context/fair-line inputs; spread-only backtests were slightly negative after vig, and ML remains research-only.",
        "away_tla": overlay.get("away_tla"),
        "home_tla": overlay.get("home_tla"),
        "away_warps_wins": number_or_none(overlay.get("away_warps_wins")),
        "home_warps_wins": number_or_none(overlay.get("home_warps_wins")),
        "fair_home_spread": number_or_none(overlay.get("fair_home_spread")),
        "fair_away_spread": number_or_none(overlay.get("fair_away_spread")),
        "home_win_prob": number_or_none(overlay.get("home_win_prob")),
        "away_win_prob": number_or_none(overlay.get("away_win_prob")),
        "home_fair_moneyline": text_or_none(overlay.get("home_fair_moneyline")),
        "away_fair_moneyline": text_or_none(overlay.get("away_fair_moneyline")),
        "market_home_spread": number_or_none(overlay.get("market_home_spread")),
        "market_away_spread": number_or_none(overlay.get("market_away_spread")),
        "market_home_moneyline": number_or_none(overlay.get("market_home_moneyline")),
        "market_away_moneyline": number_or_none(overlay.get("market_away_moneyline")),
        "spread_side": spread_side,
        "spread_team": text_or_none(overlay.get("spread_overlay_team")),
        "spread_edge_points": number_or_none(overlay.get("spread_overlay_edge_points")),
        "spread_pick_alignment": spread_alignment,
        "fair_spread_side": fair_side,
        "ml_side": ml_side,
        "ml_team": text_or_none(overlay.get("ml_overlay_team")),
        "ml_edge_prob": number_or_none(overlay.get("ml_overlay_edge_prob")),
        "ml_ev": number_or_none(overlay.get("ml_overlay_ev")),
        "ml_pick_alignment": ml_alignment,
    }


def expectation_matchup_payload(away, home, expectations):
    away_key = canonical_tla(away)
    home_key = canonical_tla(home)
    away_expectation = expectations.get(away_key)
    home_expectation = expectations.get(home_key)
    pythag_delta = delta(away_expectation, home_expectation, "pythagorean_wins_17_game_pace")
    vegas_delta = delta(away_expectation, home_expectation, "vegas_win_total")
    pythag_vs_vegas_delta = delta(away_expectation, home_expectation, "pythagorean_pace_vs_vegas")
    actual_vs_pythag_delta = delta(away_expectation, home_expectation, "actual_vs_pythagorean")
    games_tracked = min(
        (away_expectation or {}).get("games_tracked", 0),
        (home_expectation or {}).get("games_tracked", 0),
    )

    return {
        "away_team": away_key,
        "home_team": home_key,
        "away": away_expectation,
        "home": home_expectation,
        "games_tracked_min": games_tracked,
        "pythagorean_wins_delta": pythag_delta,
        "vegas_win_total_delta": vegas_delta,
        "pythagorean_vs_vegas_delta": pythag_vs_vegas_delta,
        "actual_vs_pythagorean_delta": actual_vs_pythag_delta,
        "pythagorean_side": side_from_delta(pythag_delta),
        "market_expectation_side": side_from_delta(vegas_delta),
        "value_gap_side": side_from_delta(pythag_vs_vegas_delta),
        "overperformance_side": side_from_delta(actual_vs_pythag_delta),
        "sample_warning": games_tracked < 4,
    }


def edge_board_payload(game, expectations, warps_index):
    latest = game["latest"]
    trace = normalize_trace(latest.get("recommendation_trace"))
    final_decision = trace.get("final_decision") or {}
    spread = candidate_payload(trace, "spread")
    total = candidate_payload(trace, "total")
    pick_market = latest.get("pick_market") or final_decision.get("market")
    pick_side = latest.get("pick_side") or final_decision.get("side")
    selector_score = number_or_none(latest.get("selector_score") or final_decision.get("score"))

    if pick_market in ("spread", "total") and selector_score is None:
        selector_score = number_or_none(spread.get("score") if pick_market == "spread" else total.get("score"))

    away = canonical_tla(game.get("away_tla"))
    home = canonical_tla(game.get("home_tla"))
    schedule_context = {
        "division_game": team_division(away) == team_division(home),
        "conference_game": team_conference(away) == team_conference(home),
        "away_division": team_division(away),
        "home_division": team_division(home),
    }

    best_market = pick_market if pick_market in ("spread", "total") else None
    best_edge = {
        "market": best_market,
        "side": pick_side if best_market else None,
        "score": selector_score,
        "label": latest.get("classification"),
        "recommendation": latest.get("recommendation"),
        "status": "play" if best_market else "pass",
    }
    warps_overlay = warps_overlay_payload(game, warps_index, best_edge)

    factors = []
    for candidate in (spread, total):
        for signal in candidate.get("signals", []):
            source = signal.get("source")
            side = signal.get("side")
            impact = signal.get("impact", signal.get("score"))
            if source:
                factors.append({
                    "market": candidate["market"],
                    "source": source,
                    "side": side,
                    "impact": impact,
                    "status": signal.get("status", "aligned"),
                })
    if warps_overlay.get("available") and best_market == "spread":
        alignment = warps_overlay.get("spread_pick_alignment")
        if alignment in {"aligned", "conflict", "neutral"}:
            factors.append({
                "market": "spread",
                "source": "WARPS fair-line prior",
                "side": warps_overlay.get("spread_side"),
                "impact": warps_overlay.get("spread_edge_points"),
                "status": alignment,
            })

    return {
        "season": game.get("season"),
        "season_type": game.get("season_type"),
        "week": game.get("week"),
        "matchup_key": game.get("matchup_key"),
        "game": game.get("game"),
        "away_team": game.get("away_team"),
        "home_team": game.get("home_team"),
        "away_tla": away,
        "home_tla": home,
        "stage": latest.get("stage"),
        "analysis_available": bool(latest.get("available")),
        "best_edge": best_edge,
        "markets": {
            "spread": {**spread, "status": market_status(spread)},
            "total": {**total, "status": market_status(total)},
            "moneyline": {
                "market": "moneyline",
                "side": None,
                "score": None,
                "threshold": None,
                "status": "not_priced",
                "reason": "moneyline edge model is not implemented yet",
            },
        },
        "factor_summary": factors,
        "warps_market_overlay": warps_overlay,
        "schedule_context": schedule_context,
        "expectation_context": expectation_matchup_payload(away, home, expectations),
        "source_health_status": latest.get("source_health_status"),
        "data_quality_status": latest.get("data_quality_status"),
        "result": {
            "away_score": game.get("away_score"),
            "home_score": game.get("home_score"),
            "final_margin": game.get("final_margin"),
            "final_total": game.get("final_total"),
        },
    }


def team_cell_payload(game, team_side):
    is_away = team_side == "away"
    team = game.get("away_tla" if is_away else "home_tla")
    opponent = game.get("home_tla" if is_away else "away_tla")
    latest = game["latest"]
    pick_side = str(latest.get("pick_side") or "").upper()
    pick_on_team = (
        latest.get("pick_market") == "spread"
        and ((is_away and pick_side == "AWAY") or ((not is_away) and pick_side == "HOME"))
    )
    season_prefix = "PRE" if game.get("season_type") == "PRE" else ""
    return {
        "key": f"{team}:{season_prefix}W{game.get('week')}",
        "team": team,
        "week": game.get("week"),
        "season": game.get("season"),
        "season_type": game.get("season_type"),
        "opponent": ("@" if is_away else "") + str(opponent or ""),
        "home_away": "away" if is_away else "home",
        "matchup_key": game.get("matchup_key"),
        "score_for": game.get("away_score" if is_away else "home_score"),
        "score_against": game.get("home_score" if is_away else "away_score"),
        "latest_stage": latest.get("stage"),
        "analysis_available": bool(latest.get("available")),
        "classification": latest.get("classification"),
        "pick_market": latest.get("pick_market"),
        "pick_side": latest.get("pick_side"),
        "pick_on_team": pick_on_team,
        "selector_score": latest.get("selector_score"),
        "data_quality_status": latest.get("data_quality_status"),
        "source_health_status": latest.get("source_health_status"),
    }


def load_pick_explanation_index():
    if not PICK_EXPLANATIONS.exists():
        return {}
    rows = json.loads(PICK_EXPLANATIONS.read_text())
    if not isinstance(rows, list):
        return {}
    index = {}
    for row in rows:
        matchup = row.get("matchup_key")
        stage = row.get("stage") or "final"
        if matchup:
            index[(matchup, stage)] = row
            index.setdefault((matchup, "latest"), row)
    return index


def weekly_betting_card_payload():
    if not WEEKLY_BETTING_CARD.exists():
        return {
            "available": False,
            "card_count": 0,
            "plays": 0,
            "watch": 0,
            "passes": 0,
            "cards": [],
        }
    payload = json.loads(WEEKLY_BETTING_CARD.read_text())
    payload["available"] = True
    return payload


def model_readiness_payload():
    if not READINESS_REPORT.exists():
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "reason": "model readiness report not generated",
        }

    report = json.loads(READINESS_REPORT.read_text())
    verdict = report.get("verdict") or {}
    replay = report.get("replay") or {}
    walk_forward = report.get("walk_forward") or {}
    active = walk_forward.get("active_policy_results") or {}
    optimized = walk_forward.get("optimized_policy") or {}
    return {
        "available": True,
        "status": verdict.get("status", "UNKNOWN"),
        "reason": verdict.get("reason", ""),
        "replay": {
            "plays": replay.get("plays"),
            "wins": replay.get("wins"),
            "losses": replay.get("losses"),
            "win_rate": replay.get("win_rate"),
        },
        "active_walk_forward": {
            "plays": active.get("plays"),
            "wins": active.get("wins"),
            "losses": active.get("losses"),
            "win_rate": active.get("win_rate"),
        },
        "optimized_walk_forward": {
            "plays": optimized.get("plays"),
            "wins": optimized.get("wins"),
            "losses": optimized.get("losses"),
            "win_rate": optimized.get("win_rate"),
        },
    }


def research_summary_payload():
    summary = {
        "available": False,
        "status": "BUILDING_SAMPLE",
        "sample_warning": True,
        "feature_rows": 0,
        "graded_bets": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": None,
        "observations": [
            "Research layer is waiting on graded full-season feature rows."
        ],
        "candidate_policy": {
            "status": "monitor_only",
            "recommendation": "Use expectation and moneyline features as annotations until the sample is larger.",
        },
        "top_policy_simulations": [],
        "promotion_summary": {
            "production_ready": 0,
            "candidate": 0,
            "monitor": 0,
            "research": 0,
        },
        "promoted_factors": [],
        "promotion_overlay_simulations": [],
        "source_reliability": None,
        "warps_selector_alignment": None,
        "market_router": None,
        "clv_audit": None,
        "backtest_coverage": None,
    }

    if FEATURE_RESEARCH_REPORT.exists():
        report = json.loads(FEATURE_RESEARCH_REPORT.read_text())
        summary.update({
            "available": True,
            "feature_rows": report.get("feature_rows", 0),
            "graded_bets": report.get("graded_bets", 0),
            "wins": report.get("wins", 0),
            "losses": report.get("losses", 0),
            "win_rate": report.get("win_rate"),
            "observations": report.get("observations") or [],
            "candidate_policy": report.get("candidate_policy") or summary["candidate_policy"],
        })
        summary["sample_warning"] = (report.get("graded_bets") or 0) < 100
        summary["status"] = "MONITORING" if summary["sample_warning"] else "READY_FOR_MODELING"

    policies = []
    if FEATURE_POLICY_SIMULATION.exists():
        raw_policies = json.loads(FEATURE_POLICY_SIMULATION.read_text())
        if isinstance(raw_policies, list):
            for row in raw_policies:
                if not row.get("policy"):
                    continue
                policies.append({
                    "policy": row.get("policy"),
                    "description": row.get("description"),
                    "plays": row.get("plays"),
                    "wins": row.get("wins"),
                    "losses": row.get("losses"),
                    "win_rate": row.get("win_rate"),
                    "removed_plays": row.get("removed_plays"),
                    "removed_wins": row.get("removed_wins"),
                    "removed_losses": row.get("removed_losses"),
                    "win_rate_delta": row.get("win_rate_delta"),
                })
    summary["top_policy_simulations"] = sorted(
        policies,
        key=lambda row: (
            row.get("policy") == "baseline",
            -(row.get("win_rate_delta") or 0),
            -(row.get("plays") or 0),
        ),
    )[:6]
    leaderboard = []
    if FACTOR_LEADERBOARD.exists():
        raw_leaderboard = json.loads(FACTOR_LEADERBOARD.read_text())
        if isinstance(raw_leaderboard, list):
            leaderboard = [
                {
                    "feature": row.get("feature"),
                    "value": row.get("value"),
                    "actionability": row.get("actionability"),
                    "plays": row.get("plays"),
                    "wins": row.get("wins"),
                    "losses": row.get("losses"),
                    "win_rate": row.get("win_rate"),
                    "win_rate_lift": row.get("win_rate_lift"),
                    "sample_flag": row.get("sample_flag"),
                }
                for row in raw_leaderboard
                if row.get("feature")
            ]
    summary["top_factor_leaderboard"] = leaderboard[:10]
    promoted = []
    if FACTOR_PROMOTION_REPORT.exists():
        raw_promotion = json.loads(FACTOR_PROMOTION_REPORT.read_text())
        if isinstance(raw_promotion, list):
            counts = {
                "production_ready": 0,
                "candidate": 0,
                "monitor": 0,
                "research": 0,
            }
            for row in raw_promotion:
                status = row.get("promotion_status") or "research"
                counts[status] = counts.get(status, 0) + 1
                if status in {"production_ready", "candidate", "monitor"}:
                    promoted.append({
                        "factor": row.get("factor"),
                        "feature": row.get("feature"),
                        "value": row.get("value"),
                        "actionability": row.get("actionability"),
                        "plays": row.get("plays"),
                        "wins": row.get("wins"),
                        "losses": row.get("losses"),
                        "win_rate": row.get("win_rate"),
                        "win_rate_lift": row.get("win_rate_lift"),
                        "promotion_status": status,
                        "selector_influence_allowed": row.get("selector_influence_allowed"),
                        "recommendation": row.get("recommendation"),
                        "warnings": row.get("warnings") or [],
                        "blockers": row.get("blockers") or [],
                    })
            summary["promotion_summary"] = counts
    summary["promoted_factors"] = promoted[:12]
    overlays = []
    if PROMOTION_OVERLAY_SIMULATION.exists():
        raw_overlays = json.loads(PROMOTION_OVERLAY_SIMULATION.read_text())
        if isinstance(raw_overlays, list):
            overlays = [
                {
                    "overlay": row.get("overlay"),
                    "factor": row.get("factor"),
                    "description": row.get("description"),
                    "plays": row.get("plays"),
                    "wins": row.get("wins"),
                    "losses": row.get("losses"),
                    "win_rate": row.get("win_rate"),
                    "removed_plays": row.get("removed_plays"),
                    "removed_wins": row.get("removed_wins"),
                    "removed_losses": row.get("removed_losses"),
                    "win_rate_delta": row.get("win_rate_delta"),
                    "recommendation": row.get("recommendation"),
                }
                for row in raw_overlays
                if row.get("overlay")
            ]
    summary["promotion_overlay_simulations"] = overlays[:8]
    if SOURCE_RELIABILITY_REPORT.exists():
        source_report = json.loads(SOURCE_RELIABILITY_REPORT.read_text())
        summary["source_reliability"] = {
            "overall_status": source_report.get("overall_status"),
            "overall_score": source_report.get("overall_score"),
            "weeks_audited": len(source_report.get("weeks") or []),
            "recommendations": source_report.get("recommendations") or [],
            "by_source": (source_report.get("by_source") or [])[:8],
            "feature_status_buckets": source_report.get("feature_status_buckets") or [],
        }
    if WARPS_SELECTOR_ALIGNMENT_AUDIT.exists():
        warps_report = json.loads(WARPS_SELECTOR_ALIGNMENT_AUDIT.read_text())
        summary["warps_selector_alignment"] = {
            "graded_picks": warps_report.get("graded_picks"),
            "graded_spread_picks": warps_report.get("graded_spread_picks"),
            "warps_joined": warps_report.get("warps_joined"),
            "baseline": warps_report.get("baseline") or {},
            "verdict": warps_report.get("verdict") or {},
            "alignment_buckets": [
                row for row in warps_report.get("alignment_buckets", [])
                if row.get("dimension") == "warps_spread_pick_alignment"
            ],
            "policy_simulations": (warps_report.get("policy_simulations") or [])[:6],
        }
    if MARKET_ROUTER_AUDIT.exists():
        market_report = json.loads(MARKET_ROUTER_AUDIT.read_text())
        summary["market_router"] = {
            "ledger_rows": market_report.get("ledger_rows"),
            "selected_bets": market_report.get("selected_bets"),
            "moneyline_research_rows": market_report.get("moneyline_research_rows"),
            "verdict": market_report.get("verdict") or {},
            "summary_rows": (market_report.get("summary_rows") or [])[:12],
        }
    if CLV_AUDIT.exists():
        clv_report = json.loads(CLV_AUDIT.read_text())
        summary["clv_audit"] = {
            "selected_bets": clv_report.get("selected_bets"),
            "market_reference_rows": clv_report.get("market_reference_rows"),
            "overall": clv_report.get("overall") or {},
            "verdict": clv_report.get("verdict") or {},
            "buckets": (clv_report.get("buckets") or [])[:12],
        }
    if BACKTEST_COVERAGE_REPORT.exists():
        coverage = json.loads(BACKTEST_COVERAGE_REPORT.read_text())
        summary["backtest_coverage"] = coverage
    return summary


def build_feed():
    games = []
    for path in sorted(HISTORICAL_DIR.glob("week*_master.json"), key=sort_master_path):
        rows = json.loads(path.read_text())
        for row in rows:
            games.append(game_payload(row))

    team_cells = {}
    for game in games:
        if game.get("away_tla"):
            cell = team_cell_payload(game, "away")
            team_cells[cell["key"]] = cell
        if game.get("home_tla"):
            cell = team_cell_payload(game, "home")
            team_cells[cell["key"]] = cell

    team_expectations = build_team_expectations(games)
    explanation_index = load_pick_explanation_index()
    warps_index = load_warps_market_overlay()
    edge_board = [edge_board_payload(game, team_expectations, warps_index) for game in games]
    for row in edge_board:
        stage = row.get("stage") or "final"
        row["explanation"] = (
            explanation_index.get((row.get("matchup_key"), stage))
            or explanation_index.get((row.get("matchup_key"), "latest"))
        )
    edge_board.sort(
        key=lambda row: (
            row["best_edge"]["status"] != "play",
            -(row["best_edge"]["score"] or 0),
            int(row.get("week") or 0),
            row.get("matchup_key") or "",
        )
    )

    feed = {
        "feed_version": "2026.1",
        "source": "nfl-betting-automation weekly master files",
        "game_count": len(games),
        "team_cell_count": len(team_cells),
        "edge_board_count": len(edge_board),
        "model_readiness": model_readiness_payload(),
        "research_summary": research_summary_payload(),
        "team_expectations": team_expectations,
        "weekly_betting_card": weekly_betting_card_payload(),
        "games": games,
        "team_cells": team_cells,
        "edge_board": edge_board,
    }
    return feed


def write_csv(team_cells):
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "key",
        "season",
        "season_type",
        "week",
        "team",
        "opponent",
        "home_away",
        "matchup_key",
        "score_for",
        "score_against",
        "latest_stage",
        "analysis_available",
        "classification",
        "pick_market",
        "pick_side",
        "pick_on_team",
        "selector_score",
        "data_quality_status",
        "source_health_status",
    ]
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        rows = team_cells.values() if isinstance(team_cells, dict) else team_cells
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def main():
    feed = build_feed()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(feed, indent=2, default=str))
    write_csv(feed["team_cells"])
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_CSV}")
    print(f"Games: {feed['game_count']} | Team cells: {feed['team_cell_count']}")


if __name__ == "__main__":
    main()
