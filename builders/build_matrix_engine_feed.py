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


def week_to_int(week):
    """Convert any week label (1-18, PRE1-PRE4, WC, DIV, CON, SB) to an int for sorting."""
    if week is None:
        return 0
    w = str(week).strip().upper()
    playoff_map = {"WC": 19, "DIV": 20, "CON": 21, "CONF": 21, "SB": 22}
    if w in playoff_map:
        return playoff_map[w]
    if w.startswith("PRE"):
        try:
            # PRE1=-4, PRE2=-3, PRE3=-2, PRE4=-1 so max() picks the latest preseason week
            return (int(w[3:]) if w[3:] else 1) - 5
        except ValueError:
            return -5
    try:
        return int(w)
    except (ValueError, TypeError):
        return 0


HISTORICAL_DIR = ROOT / "data" / "historical"
OUTPUT_JSON = HISTORICAL_DIR / "matrix_engine_feed.json"
OUTPUT_CSV = HISTORICAL_DIR / "matrix_engine_feed.csv"
WEEKLY_COMMAND_CENTER = HISTORICAL_DIR / "weekly_command_center.json"
WEEKLY_COMMAND_CENTER_MD = HISTORICAL_DIR / "weekly_command_center.md"
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
PRESEASON_DRY_RUN_REPORT = HISTORICAL_DIR / "preseason_dry_run_report.json"
SURVIVOR_BACKTEST_REPORT = HISTORICAL_DIR / "survivor_backtest_report.json"
SURVIVOR_POOL_EV_BACKTEST = HISTORICAL_DIR / "survivor_pool_ev_backtest.json"
SURVIVOR_RECOMMENDATIONS = HISTORICAL_DIR / "survivor_recommendations_2026.json"
WARPS_MARKET_OVERLAY = HISTORICAL_DIR / "warps_2026_market_overlay.csv"
STAGES = ("initial", "update", "lock", "final")
from analyzers.nfl_common import get_current_season as _get_current_season
ACTIVE_SEASON = _get_current_season()
PYTHAGOREAN_EXPONENT = 2.37
CURRENT_SEASON = _get_current_season()


def _load_vegas_win_totals(season):
    import json as _json
    try:
        with open("data/historical/vegas_win_totals.json") as _f:
            all_totals = _json.load(_f)
        return all_totals.get(str(season), {})
    except Exception:
        return {}


VEGAS_WIN_TOTALS = _load_vegas_win_totals(ACTIVE_SEASON)
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


def _ml_line_string(warps_overlay, sharp_moneyline_line):
    """Return the best available ML line string: sharp odds > WARPS market odds."""
    if sharp_moneyline_line:
        return sharp_moneyline_line
    if not (warps_overlay and warps_overlay.get("available")):
        return ""
    away_ml = warps_overlay.get("market_away_moneyline")
    home_ml = warps_overlay.get("market_home_moneyline")
    away_tla = warps_overlay.get("away_tla") or "Away"
    home_tla = warps_overlay.get("home_tla") or "Home"
    if away_ml is not None and home_ml is not None:
        away_str = f"{away_ml:+.0f}" if isinstance(away_ml, float) else str(away_ml)
        home_str = f"{home_ml:+.0f}" if isinstance(home_ml, float) else str(home_ml)
        return f"{away_tla} {away_str} | {home_tla} {home_str}"
    return ""


def _moneyline_market(warps_overlay, sharp_moneyline_line=""):
    """Build the moneyline market block from WARPS ML edge when available.

    Only favorites qualify: backtest (3,028 games, 2015-2025) showed underdog
    ML picks win at 32% regardless of edge level (-4.6% ROI/play). Favorite
    picks with >=5% probability edge win at 61% (+7.2% ROI/play, 7/11 seasons
    positive). Threshold is 5% edge_prob for playable, 2% for lean.
    """
    ml_ev = None
    ml_side = None
    ml_edge_prob = None
    ml_odds = None
    if warps_overlay and warps_overlay.get("available"):
        ml_ev = warps_overlay.get("ml_ev")
        ml_side = warps_overlay.get("ml_side")
        ml_edge_prob = warps_overlay.get("ml_edge_prob")
        if ml_side == "HOME":
            ml_odds = warps_overlay.get("market_home_moneyline")
        elif ml_side == "AWAY":
            ml_odds = warps_overlay.get("market_away_moneyline")

    # Use edge_prob (%) as the display score so it reads against a 5.0 threshold
    edge_pct = ml_edge_prob if ml_edge_prob is not None else None
    ml_score = round(edge_pct * 100, 1) if edge_pct is not None else None
    is_favorite = isinstance(ml_odds, (int, float)) and ml_odds < 0

    if ml_score is None:
        ml_status = "research_only"
        blockers = ["WARPS ML unavailable for this week"]
    elif not is_favorite:
        ml_status = "blocked"
        blockers = ["underdog ML not predictive (32% win rate historically, all edge levels)"]
    elif edge_pct >= 0.05:
        ml_status = "playable"
        blockers = []
    elif edge_pct >= 0.02:
        ml_status = "lean"
        blockers = []
    else:
        ml_status = "not_priced"
        blockers = ["ML edge below lean threshold (need >=2% on a favorite)"]

    line = _ml_line_string(warps_overlay, sharp_moneyline_line)
    return {
        "market": "moneyline",
        "side": ml_side,
        "score": ml_score,
        "threshold": 5.0,
        "cleared_threshold": ml_status == "playable",
        "status": ml_status,
        "promotion_status": "playable" if ml_status == "playable" else "not_promoted",
        "blockers": blockers,
        "line": line,
        "reason": (
            "WARPS ML: fav >=5% edge playable" if ml_status == "playable"
            else "WARPS ML: fav >=2% edge lean" if ml_status == "lean"
            else "WARPS ML EV" if ml_score is not None
            else "moneyline selector not promoted; WARPS provides context only"
        ),
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
    for team in VEGAS_WIN_TOTALS:
        teams[team] = {
            "team": team,
            "conference": team_conference(team),
            "division": team_division(team),
            "games_tracked": 0,
            "actual_wins": 0,
            "actual_losses": 0,
            "points_for": 0,
            "points_against": 0,
            "vegas_win_total": VEGAS_WIN_TOTALS.get(team),
        }

    for game in games:
        if game.get("season_type") != "REG":
            continue
        try:
            game_season = int(game.get("season") or 0)
        except (ValueError, TypeError):
            game_season = 0
        if game_season and game_season != CURRENT_SEASON:
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
                    "vegas_win_total": VEGAS_WIN_TOTALS.get(team),
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


def stage_has_pick(row, stage):
    """Return True if this stage produced an actionable market pick (not 'none')."""
    pick_market = str(row.get(f"{stage}_pick_market") or "").strip().lower()
    return pick_market in ("spread", "total", "moneyline")


def latest_stage(row):
    season_type = str(row.get("season_type") or "").upper()
    for stage in reversed(STAGES):
        if not stage_available(row, stage):
            continue
        # For preseason: if the final stage produced no market pick, fall back to the
        # most recent earlier stage that does have a pick (typically initial).
        if season_type == "PRE" and stage == "final" and not stage_has_pick(row, stage):
            continue
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
        "sharp_spread_line": row.get(f"{stage}_sharp_spread_line") or "",
        "sharp_total_line": row.get(f"{stage}_sharp_total_line") or "",
        "sharp_moneyline_line": row.get(f"{stage}_sharp_moneyline_line") or "",
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


def week_label_from_path(queries_path):
    """Extract week label from a path like data/weekPRE1/weekPRE1_queries.csv → 'PRE1'."""
    match = re.search(r"week(PRE\d+|\d+|[A-Z]+)_queries\.csv$", queries_path.name)
    return match.group(1) if match else None


def game_week_dir_label(game):
    """Map game fields to the week directory label used in queries CSVs."""
    season_type = str(game.get("season_type") or "").upper()
    week = game.get("week")
    if season_type == "PRE":
        w = str(week or "1").strip().upper()
        num = w[3:] if w.startswith("PRE") else w
        return f"PRE{num or '1'}"
    w = str(week or "").strip().upper()
    if w in ("WC", "DIV", "CONF", "CON", "SB"):
        return "CONF" if w == "CON" else w
    return str(week) if week else None


def load_referee_index():
    """Build a lookup of (week_label, away_tla, home_tla) → referee name."""
    index = {}
    data_dir = ROOT / "data"
    for queries_path in sorted(data_dir.glob("week*/week*_queries.csv")):
        week_label = week_label_from_path(queries_path)
        if not week_label:
            continue
        try:
            with queries_path.open() as f:
                for row in csv.DictReader(f):
                    away = (row.get("away") or "").strip().upper()
                    home = (row.get("home") or "").strip().upper()
                    referee = (row.get("referee") or "").strip()
                    if away and home and referee:
                        index[(week_label, away, home)] = referee
        except Exception:
            pass
    return index


def load_referee_stats():
    """Load SDQL referee trend data keyed by (referee, game_type)."""
    sdql_path = HISTORICAL_DIR / "sdql_results.csv"
    if not sdql_path.exists():
        return {}
    index = {}
    try:
        with sdql_path.open() as f:
            for row in csv.DictReader(f):
                referee = (row.get("referee") or "").strip()
                game_type = (row.get("game_type") or "").strip().upper()
                if not referee:
                    continue
                def _parse_pct(s):
                    try:
                        return float((s or "").strip().rstrip("%"))
                    except Exception:
                        return None
                stats = {
                    "su_record": row.get("su_record", ""),
                    "su_pct": _parse_pct(row.get("su_pct")),
                    "ats_record": row.get("ats_record", ""),
                    "ats_pct": _parse_pct(row.get("ats_pct")),
                    "ou_record": row.get("ou_record", ""),
                    "ou_pct": _parse_pct(row.get("ou_pct")),
                    "sample_size": int(row.get("sample_size") or 0),
                    "game_type": game_type,
                    "favorite": (row.get("favorite") or "").strip(),
                }
                index[(referee, game_type)] = stats
    except Exception:
        pass
    return index


def referee_stats_for_game(referee, is_division, referee_stats_index):
    """Return the best-matching SDQL stats for a referee given game context."""
    if not referee or not referee_stats_index:
        return None
    preferred = "C" if is_division else "NDIV"
    fallback = "NDIV" if is_division else "C"
    result = (
        referee_stats_index.get((referee, preferred))
        or referee_stats_index.get((referee, fallback))
    )
    if result:
        return result
    # Queries CSV may produce composite names like "Alan Eck/David Oliver"; try first name only
    primary = referee.split("/")[0].strip()
    if primary != referee:
        return (
            referee_stats_index.get((primary, preferred))
            or referee_stats_index.get((primary, fallback))
        )
    return None


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


def edge_board_payload(game, expectations, warps_index, referee_index=None, referee_stats_index=None):
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
    # For WATCH/PASS games with no committed market, still surface the best candidate score
    if selector_score is None:
        candidate_scores = [s for s in [spread.get("score"), total.get("score")] if s is not None]
        if candidate_scores:
            selector_score = number_or_none(max(candidate_scores))

    # Back-fill candidate market score from selector_score when trace lacks market_candidates
    # (common in preseason where the stage row has selector_score but no candidate detail)
    if pick_market == "spread" and spread.get("score") is None and selector_score is not None:
        spread["score"] = selector_score
    if pick_market == "total" and total.get("score") is None and selector_score is not None:
        total["score"] = selector_score

    away = canonical_tla(game.get("away_tla"))
    home = canonical_tla(game.get("home_tla"))
    week_label = game_week_dir_label(game)
    referee = (referee_index or {}).get((week_label, away, home)) if week_label else None
    is_division = team_division(away) == team_division(home)
    schedule_context = {
        "division_game": is_division,
        "conference_game": team_conference(away) == team_conference(home),
        "away_division": team_division(away),
        "home_division": team_division(home),
    }
    ref_stats = referee_stats_for_game(referee, is_division, referee_stats_index)

    best_market = pick_market if pick_market in ("spread", "total") else None
    classification_label = (latest.get("classification_label") or "").lower()
    if best_market:
        edge_status = "play"
    elif classification_label in ("lean", "watch", "lean_play"):
        edge_status = "watch"
    else:
        edge_status = "pass"
    best_edge = {
        "market": best_market,
        "side": pick_side if best_market else None,
        "score": selector_score,
        "label": latest.get("classification"),
        "recommendation": latest.get("recommendation"),
        "status": edge_status,
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
            "spread": {**spread, "status": market_status(spread),
                       "line": latest.get("sharp_spread_line") or ""},
            "total": {**total, "status": market_status(total),
                      "line": latest.get("sharp_total_line") or ""},
            "moneyline": _moneyline_market(warps_overlay, latest.get("sharp_moneyline_line") or ""),
        },
        "referee": referee,
        "referee_stats": ref_stats,
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


def weekly_betting_card_payload(referee_index=None, referee_stats_index=None):
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
    if referee_index:
        for card in payload.get("cards") or []:
            week_label = game_week_dir_label(card)
            away = (card.get("away_tla") or "").strip().upper()
            home = (card.get("home_tla") or "").strip().upper()
            referee = referee_index.get((week_label, away, home)) if week_label else None
            card["referee"] = referee
            is_division = team_division(away) == team_division(home)
            card["referee_stats"] = referee_stats_for_game(referee, is_division, referee_stats_index)
    return payload


def season_type_rank(season_type):
    return {"PRE": 0, "REG": 1, "POST": 2}.get(str(season_type or "").upper(), -1)


def make_week_label(season_type, week):
    w = str(week).strip().upper()
    if season_type == "PRE":
        num = w[3:] if w.startswith("PRE") else w
        return f"PRE W{num or '1'}"
    if w in ("WC", "DIV", "CONF", "CON", "SB"):
        return w
    return f"W{week}"


def current_context_payload(games, card_payload, preseason_payload):
    # M-1 fix: prefer data/current_week.json as the authoritative week/season context.
    # Without this, max() over card rows can pick a prior-season row with a higher week
    # number, overriding the correct current week.
    _cw_season = None
    _cw_week = None
    _cw_season_type = None
    _cw_path = ROOT / "data" / "current_week.json"
    if _cw_path.exists():
        try:
            _cw = json.loads(_cw_path.read_text())
            _s = _cw.get("season")
            _w = str(_cw.get("week", "")).strip()
            _st = str(_cw.get("season_type", "")).strip().upper()
            if _s and _w:
                _cw_season = int(_s)
                _cw_week = _w
                _cw_season_type = _st or "REG"
        except Exception:
            pass  # Fall through to card-scanning fallback

    cards = card_payload.get("cards") or []
    active_cards = [
        row for row in cards
        if row.get("season") == ACTIVE_SEASON and row.get("season_type") in ("PRE", "REG", "POST")
    ]
    active_games = [
        row for row in games
        if row.get("season") == ACTIVE_SEASON and row.get("season_type") in ("PRE", "REG", "POST")
    ]

    if _cw_season and _cw_week and _cw_season_type:
        # current_week.json is authoritative — skip card-row scanning for week/season_type.
        season_type = _cw_season_type
        week = _cw_week
        # Still derive stage from any card rows that match this specific week, if available.
        week_cards = [
            row for row in active_cards
            if str(row.get("week") or "") == str(week) and row.get("season_type") == season_type
        ]
        if week_cards:
            _best = max(
                week_cards,
                key=lambda row: (
                    row.get("latest", {}).get("stage") in ("lock", "final")
                    if isinstance(row.get("latest"), dict) else False,
                ),
            )
            stage = (
                (_best.get("latest") or {}).get("stage")
                if isinstance(_best.get("latest"), dict)
                else _best.get("stage")
            )
        else:
            stage = None
        return {
            "season": _cw_season,
            "season_type": season_type,
            "week": week,
            "week_label": make_week_label(season_type, week),
            "stage": stage,
            "status": "LIVE_CARD" if active_cards else "LIVE_GAMES_NO_CARD",
            "mode": "live",
            "has_betting_card": bool(active_cards),
            "message": "Current active engine context from current_week.json.",
        }

    candidates = active_cards or active_games
    if candidates:
        selected = max(
            candidates,
            key=lambda row: (
                season_type_rank(row.get("season_type")),
                week_to_int(row.get("week")),
                row.get("latest", {}).get("stage") in ("lock", "final") if isinstance(row.get("latest"), dict) else False,
            ),
        )
        season_type = selected.get("season_type") or "REG"
        week = selected.get("week") or 1
        return {
            "season": ACTIVE_SEASON,
            "season_type": season_type,
            "week": week,
            "week_label": make_week_label(season_type, week),
            "stage": (selected.get("latest") or {}).get("stage") if isinstance(selected.get("latest"), dict) else selected.get("stage"),
            "status": "LIVE_CARD" if active_cards else "LIVE_GAMES_NO_CARD",
            "mode": "live",
            "has_betting_card": bool(active_cards),
            "message": f"Current active engine context from {ACTIVE_SEASON} artifacts.",
        }

    if preseason_payload.get("available"):
        season_type = preseason_payload.get("season_type") or "PRE"
        week = preseason_payload.get("week") or 1
        pre_cards = [
            row for row in (card_payload.get("cards") or [])
            if row.get("season_type") == "PRE"
        ]
        has_card = bool(pre_cards)
        return {
            "season": preseason_payload.get("season") or ACTIVE_SEASON,
            "season_type": season_type,
            "week": week,
            "week_label": make_week_label(season_type, week),
            "stage": "final" if has_card else "dry_run",
            "status": "PRESEASON_CARD_LIVE" if has_card else "PRESEASON_DRY_RUN_READY",
            "mode": "live" if has_card else "dry_run",
            "has_betting_card": has_card,
            "message": (
                "Preseason picks available (research only — no bets recommended)."
                if has_card else
                "Preseason plumbing dry-run is available; live betting card has not published yet."
            ),
        }

    historical_cards = bool(cards)
    return {
        "season": ACTIVE_SEASON,
        "season_type": "REG",
        "week": 1,
        "week_label": "W1",
        "stage": "planning",
        "status": "PLANNING_NO_LIVE_CARD",
        "mode": "planning",
        "has_betting_card": False,
        "historical_card_available": historical_cards,
        "message": f"No {ACTIVE_SEASON} live card is published yet. Historical cards are retained for audit only.",
    }


def preseason_dry_run_payload():
    if not PRESEASON_DRY_RUN_REPORT.exists():
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "checks_total": 0,
            "checks_passed": 0,
        }
    report = json.loads(PRESEASON_DRY_RUN_REPORT.read_text())
    checks = report.get("checks") or []
    return {
        "available": True,
        "season": report.get("season"),
        "season_type": report.get("season_type"),
        "week": report.get("week"),
        "artifact_slug": report.get("artifact_slug"),
        "status": report.get("status") or "UNKNOWN",
        "checks_total": len(checks),
        "checks_passed": sum(1 for row in checks if row.get("status") == "PASS"),
        "next_live_command": report.get("next_live_command"),
    }


def survivor_backtest_payload():
    if not SURVIVOR_BACKTEST_REPORT.exists():
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "summary": [],
        }
    report = json.loads(SURVIVOR_BACKTEST_REPORT.read_text())
    summary = report.get("summary") or []
    best = summary[0] if summary else None
    return {
        "available": True,
        "status": "BACKTESTED",
        "model": (report.get("metadata") or {}).get("model"),
        "seasons": (report.get("metadata") or {}).get("seasons") or [],
        "candidate_count": (report.get("metadata") or {}).get("candidate_count"),
        "method": (report.get("metadata") or {}).get("method"),
        "best_strategy": best,
        "summary": summary,
    }


def survivor_pool_ev_payload():
    if not SURVIVOR_POOL_EV_BACKTEST.exists():
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "summary": [],
        }
    report = json.loads(SURVIVOR_POOL_EV_BACKTEST.read_text())
    summary = report.get("summary") or []
    best = summary[0] if summary else None
    return {
        "available": True,
        "status": "BACKTESTED",
        "model": (report.get("metadata") or {}).get("model"),
        "seasons": (report.get("metadata") or {}).get("seasons") or [],
        "trials_per_scenario": (report.get("metadata") or {}).get("trials_per_scenario"),
        "max_public_entries": (report.get("metadata") or {}).get("max_public_entries"),
        "method": (report.get("metadata") or {}).get("method"),
        "best_strategy": best,
        "summary": summary[:12],
    }


def load_survivor_recommendations():
    if not SURVIVOR_RECOMMENDATIONS.exists():
        return {}
    return json.loads(SURVIVOR_RECOMMENDATIONS.read_text())


def current_card_rows(card_payload, context):
    rows = card_payload.get("cards") or []
    return [
        row for row in rows
        if row.get("season") == context.get("season")
        and row.get("season_type") == context.get("season_type")
        and row.get("week") == context.get("week")
    ]


def planning_week_for(context):
    """During preseason, survivor/WARPS look ahead to REG W1 for planning."""
    raw = context.get("week") or 1
    if context.get("season_type") == "PRE":
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return week_to_int(raw) or 1


def survivor_command_payload(context):
    payload = load_survivor_recommendations()
    week = planning_week_for(context)
    pool_cards = [
        row for row in payload.get("pool_cards", [])
        if row.get("week") == week and row.get("payout_style") == "top_heavy"
    ]
    pool_cards.sort(key=lambda row: row.get("pool_size") or 0)
    weekly = next((row for row in payload.get("weekly", []) if row.get("week") == week), {})
    return {
        "available": bool(payload),
        "week": week,
        "planning_context": "preseason" if context.get("season_type") == "PRE" else "current",
        "primary": weekly.get("primary"),
        "safest": weekly.get("safest"),
        "pool_cards": pool_cards,
        "path_pick": next(
            (row for row in (payload.get("optimal_path") or {}).get("picks", []) if row.get("week") == week),
            None,
        ),
    }


def warps_command_payload(context, warps_index):
    week = planning_week_for(context)
    rows = []
    for row in warps_index.values():
        if week_to_int(row.get("week")) != week_to_int(week):
            continue
        for side in ("home", "away"):
            team = row.get(f"{side}_tla")
            opponent = row.get("away_tla" if side == "home" else "home_tla")
            rows.append({
                "team": team,
                "opponent": opponent,
                "home_away": side,
                "matchup_key": row.get("matchup_key"),
                "win_probability": number_or_none(row.get(f"{side}_win_prob")),
                "fair_moneyline": row.get(f"{side}_fair_moneyline"),
                "fair_spread": number_or_none(row.get(f"fair_{side}_spread")),
                "status": row.get("status"),
            })
    rows.sort(key=lambda row: row.get("win_probability") or 0, reverse=True)
    return rows[:6]


def weekly_command_center_payload(context, weekly_card, edge_board, preseason, warps_index):
    cards = current_card_rows(weekly_card, context)
    plays = [row for row in cards if row.get("action") == "play"]
    watch = [row for row in cards if row.get("action") in {"watch", "lean"}]
    passes = [row for row in cards if row.get("action") == "pass"]
    current_edges = [
        row for row in edge_board
        if row.get("season") == context.get("season")
        and row.get("season_type") == context.get("season_type")
        and row.get("week") == context.get("week")
    ]
    best_edges = [
        row for row in current_edges
        if (row.get("best_edge") or {}).get("status") == "play"
    ]
    best_edges.sort(key=lambda row: (row.get("best_edge") or {}).get("score") or 0, reverse=True)
    warnings = []
    if not context.get("has_betting_card"):
        warnings.append("No live betting card is published for the current context.")
    if not plays and not watch:
        warnings.append("No actionable betting plays or watchlist spots are active.")
    if preseason.get("available") and preseason.get("status") != "PASS":
        warnings.append("Preseason dry-run checks are not fully passing.")
    source_gates = {
        "live_betting_card": "PASS" if context.get("has_betting_card") else "BLOCKED",
        "preseason_dry_run": "PASS" if preseason.get("status") == "PASS" else "WARN" if preseason.get("available") else "MISSING",
        "warps_priors": "PASS" if warps_index else "MISSING",
        "survivor_recommendations": "PASS" if load_survivor_recommendations() else "MISSING",
    }
    action = "NO BET - DATA INCOMPLETE" if source_gates["live_betting_card"] == "BLOCKED" else "PLAY" if plays else "WATCH" if watch else "PASS"
    confidence_tier = (
        "X" if action == "NO BET - DATA INCOMPLETE"
        else "A" if plays and all(value == "PASS" for value in source_gates.values())
        else "B" if plays
        else "C" if watch
        else "X"
    )
    action_reason = (
        "Live betting inputs are not published for this context."
        if action == "NO BET - DATA INCOMPLETE"
        else "At least one selector play cleared the current command gate."
        if action == "PLAY"
        else "No plays cleared, but watchlist spots exist."
        if action == "WATCH"
        else "No playable or watchlist edges are active."
    )
    return {
        "available": True,
        "generated_from": "matrix_engine_feed_builder",
        "current_context": context,
        "decision_mode": context.get("mode"),
        "recommended_action": action,
        "confidence_tier": confidence_tier,
        "action_reason": action_reason,
        "source_gates": source_gates,
        "do_nothing_warning": bool(warnings),
        "warnings": warnings,
        "betting_card": {
            "available": bool(context.get("has_betting_card")),
            "plays": len(plays),
            "watch": len(watch),
            "passes": len(passes),
            "top_cards": (plays + watch)[:6],
        },
        "best_edges": best_edges[:6],
        "survivor": survivor_command_payload(context),
        "warps_watch": warps_command_payload(context, warps_index),
        "source_health": {
            "preseason_dry_run": preseason,
            "card_available": bool(context.get("has_betting_card")),
        },
    }


def pick_label(pick):
    if not pick:
        return "n/a"
    team = pick.get("team") or "n/a"
    opponent = pick.get("opponent") or "n/a"
    prob = pick.get("win_probability")
    prob_text = f"{prob:.1%}" if isinstance(prob, (int, float)) else "n/a"
    return f"{team} vs {opponent} ({prob_text})"


def write_weekly_command_center_md(path, command):
    context = command.get("current_context") or {}
    survivor = command.get("survivor") or {}
    lines = [
        "# Weekly Command Center",
        "",
        f"- Context: {context.get('season')} {context.get('week_label')} · {context.get('mode')}",
        f"- Recommended action: **{command.get('recommended_action')}**",
        f"- Confidence tier: **{command.get('confidence_tier')}**",
        f"- Reason: {command.get('action_reason')}",
        "",
        "## Source Gates",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    for gate, status in (command.get("source_gates") or {}).items():
        lines.append(f"| {gate.replace('_', ' ')} | {status} |")
    lines.extend([
        "",
        "## Betting Card",
        "",
        f"- Plays: {command.get('betting_card', {}).get('plays', 0)}",
        f"- Watch: {command.get('betting_card', {}).get('watch', 0)}",
        f"- Passes: {command.get('betting_card', {}).get('passes', 0)}",
    ])
    top_cards = command.get("betting_card", {}).get("top_cards") or []
    if top_cards:
        lines.extend(["", "| Game | Action | Market | Side | Score |", "|---|---|---|---|---:|"])
        for row in top_cards:
            lines.append(
                f"| {row.get('away_tla')}@{row.get('home_tla')} | {row.get('action')} | "
                f"{row.get('market') or 'n/a'} | {row.get('side') or 'n/a'} | {row.get('selector_score') or 'n/a'} |"
            )
    lines.extend([
        "",
        "## Survivor",
        "",
        f"- Primary: {pick_label(survivor.get('primary'))}",
        f"- Safest: {pick_label(survivor.get('safest'))}",
        f"- Path pick: {pick_label(survivor.get('path_pick'))}",
        "",
        "| Pool | Safe | Balanced | Leverage |",
        "|---:|---|---|---|",
    ])
    for card in survivor.get("pool_cards") or []:
        lines.append(
            f"| {card.get('pool_size')} | {pick_label(card.get('safe'))} | "
            f"{pick_label(card.get('balanced'))} | {pick_label(card.get('leverage'))} |"
        )
    lines.extend(["", "## WARPS Watch", "", "| Team | Game | Win Prob | Fair ML |", "|---|---|---:|---|"])
    for row in command.get("warps_watch") or []:
        prob = row.get("win_probability")
        prob_text = f"{prob:.1%}" if isinstance(prob, (int, float)) else "n/a"
        prefix = "vs" if row.get("home_away") == "home" else "@"
        lines.append(f"| {row.get('team')} | {prefix} {row.get('opponent')} | {prob_text} | {row.get('fair_moneyline') or 'n/a'} |")
    if command.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in command.get("warnings"):
            lines.append(f"- {warning}")
    path.write_text("\n".join(lines) + "\n")


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


def line_move_alert_payload(week, season_type):
    """Return a compact line move alert dict if recent moves exist for the current week, else None."""
    if not week:
        return None
    summary_path = ROOT / "data" / f"week{week}" / "line_move_summary.json"
    if not summary_path.exists():
        return None
    try:
        summary = json.loads(summary_path.read_text())
    except Exception:
        return None
    total = summary.get("total_moves", 0)
    if not total:
        return None
    pick_affected = summary.get("pick_affected", 0)
    flips = summary.get("flips", 0)
    threshold = summary.get("threshold", 2.0)
    moves = summary.get("moves", [])
    compact = "; ".join(
        f"{m['matchup_key']} {m['old_away_spread']:+.1f}→{m['new_away_spread']:+.1f}"
        + (" [PICK]" if m.get("has_model_pick") else "")
        for m in moves[:5]
    )
    return {
        "total_moves": total,
        "pick_affected": pick_affected,
        "flips": flips,
        "threshold": threshold,
        "summary": compact,
        "week": week,
        "season_type": season_type,
    }


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
    referee_index = load_referee_index()
    referee_stats_index = load_referee_stats()
    analyzed_games = [g for g in games if (g.get("latest") or {}).get("available")]
    edge_board = [edge_board_payload(game, team_expectations, warps_index, referee_index, referee_stats_index) for game in analyzed_games]
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
            week_to_int(row.get("week")),
            row.get("matchup_key") or "",
        )
    )
    weekly_card = weekly_betting_card_payload(referee_index, referee_stats_index)
    preseason = preseason_dry_run_payload()
    current_context = current_context_payload(games, weekly_card, preseason)
    command_center = weekly_command_center_payload(current_context, weekly_card, edge_board, preseason, warps_index)
    line_move_alert = line_move_alert_payload(
        current_context.get("week"), current_context.get("season_type")
    )

    feed = {
        "feed_version": f"{ACTIVE_SEASON}.1",
        "source": "nfl-betting-automation weekly master files",
        "game_count": len(games),
        "team_cell_count": len(team_cells),
        "edge_board_count": len(edge_board),
        "current_context": current_context,
        "line_move_alert": line_move_alert,
        "weekly_command_center": command_center,
        "model_readiness": model_readiness_payload(),
        "research_summary": research_summary_payload(),
        "team_expectations": team_expectations,
        "weekly_betting_card": weekly_card,
        "preseason_dry_run": preseason,
        "survivor_backtest": survivor_backtest_payload(),
        "survivor_pool_ev": survivor_pool_ev_payload(),
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
    WEEKLY_COMMAND_CENTER.write_text(json.dumps(feed["weekly_command_center"], indent=2, default=str))
    write_weekly_command_center_md(WEEKLY_COMMAND_CENTER_MD, feed["weekly_command_center"])
    write_csv(feed["team_cells"])
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {WEEKLY_COMMAND_CENTER}")
    print(f"Wrote {WEEKLY_COMMAND_CENTER_MD}")
    print(f"Wrote {OUTPUT_CSV}")
    print(f"Games: {feed['game_count']} | Team cells: {feed['team_cell_count']}")


if __name__ == "__main__":
    main()
