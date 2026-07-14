#!/usr/bin/env python3
"""Backtest WARPS matchup priors against historical spread and ML markets.

This tests whether preseason WARPS win projections, translated into game-level
fair spreads and win probabilities, had signal versus historical closing lines.
It is intentionally separate from the weekly engine: no injuries, refs, sharp
splits, or weather confirmations are included here.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET_SPINE = ROOT / "data" / "historical" / "nfl_market_spine.csv"
DEFAULT_WARPS = ROOT / "warps_backtest_team_results_v2_3.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "backtests" / "warps_game_edges"

HOME_FIELD_WINS = 1.6
WIN_GAP_LOGIT_SCALE = 0.15
NFL_MARGIN_SD = 13.45
TEAM_ALIASES = {
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "WSH": "WAS",
}


def canonical_team(team: str | None) -> str:
    value = str(team or "").strip()
    return TEAM_ALIASES.get(value, value)


def parse_float(value) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def parse_int(value) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def logistic(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def probability_to_american(probability: float) -> int:
    probability = min(max(probability, 0.001), 0.999)
    if probability >= 0.5:
        return round(-100 * probability / (1 - probability))
    return round(100 * (1 - probability) / probability)


def american_profit_per_unit(odds: float | None) -> float | None:
    if odds is None:
        return None
    return odds / 100 if odds > 0 else 100 / abs(odds)


def bet_roi(odds: float | None, result: str) -> float | None:
    profit = american_profit_per_unit(odds)
    if profit is None or result == "missing":
        return None
    if result == "push":
        return 0.0
    return profit if result == "win" else -1.0


def moneyline_ev(probability: float | None, odds: float | None) -> float | None:
    profit = american_profit_per_unit(odds)
    if probability is None or profit is None:
        return None
    return (probability * profit) - (1 - probability)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_warps(path: Path) -> dict[tuple[int, str], float]:
    rows = read_csv(path)
    projections: dict[tuple[int, str], float] = {}
    for row in rows:
        season = parse_int(row.get("season"))
        team = canonical_team(row.get("team"))
        proj = parse_float(row.get("proj"))
        if season is not None and team and proj is not None:
            projections[(season, team)] = proj
    return projections


def game_prior(home_warps: float, away_warps: float) -> dict:
    home_strength_gap = home_warps - away_warps
    home_win_prob = logistic((home_strength_gap + HOME_FIELD_WINS) * WIN_GAP_LOGIT_SCALE)
    away_win_prob = 1 - home_win_prob
    expected_home_margin = NormalDist().inv_cdf(home_win_prob) * NFL_MARGIN_SD
    fair_home_spread = -expected_home_margin
    fair_away_spread = expected_home_margin
    return {
        "home_strength_gap_wins": home_strength_gap,
        "home_win_prob": home_win_prob,
        "away_win_prob": away_win_prob,
        "fair_home_spread": fair_home_spread,
        "fair_away_spread": fair_away_spread,
        "home_fair_moneyline": probability_to_american(home_win_prob),
        "away_fair_moneyline": probability_to_american(away_win_prob),
    }


def build_game_edges(market_rows: list[dict], warps: dict[tuple[int, str], float]) -> list[dict]:
    output = []
    for row in market_rows:
        season = parse_int(row.get("season"))
        away = canonical_team(row.get("away_team"))
        home = canonical_team(row.get("home_team"))
        if season is None:
            continue
        away_warps = warps.get((season, away))
        home_warps = warps.get((season, home))
        if away_warps is None or home_warps is None:
            continue

        prior = game_prior(home_warps, away_warps)
        home_spread_line = parse_float(row.get("home_spread_line"))
        away_spread_line = parse_float(row.get("away_spread_line"))
        home_spread_edge = None if home_spread_line is None else home_spread_line - prior["fair_home_spread"]
        away_spread_edge = None if away_spread_line is None else away_spread_line - prior["fair_away_spread"]

        home_market_ml = parse_float(row.get("home_ml_no_vig_prob"))
        away_market_ml = parse_float(row.get("away_ml_no_vig_prob"))
        home_ml_edge = None if home_market_ml is None else prior["home_win_prob"] - home_market_ml
        away_ml_edge = None if away_market_ml is None else prior["away_win_prob"] - away_market_ml

        spread_side = ""
        spread_edge = None
        spread_result = ""
        spread_odds = None
        if home_spread_edge is not None and away_spread_edge is not None:
            if home_spread_edge >= away_spread_edge:
                spread_side = "HOME"
                spread_edge = home_spread_edge
                spread_result = row.get("home_cover_result") or ""
                spread_odds = parse_float(row.get("home_spread_odds"))
            else:
                spread_side = "AWAY"
                spread_edge = away_spread_edge
                spread_result = row.get("away_cover_result") or ""
                spread_odds = parse_float(row.get("away_spread_odds"))

        ml_side = ""
        ml_edge = None
        ml_result = ""
        ml_odds = None
        ml_model_prob = None
        ml_market_prob = None
        if home_ml_edge is not None and away_ml_edge is not None:
            if home_ml_edge >= away_ml_edge:
                ml_side = "HOME"
                ml_edge = home_ml_edge
                ml_result = row.get("home_ml_result") or ""
                ml_odds = parse_float(row.get("home_moneyline"))
                ml_model_prob = prior["home_win_prob"]
                ml_market_prob = home_market_ml
            else:
                ml_side = "AWAY"
                ml_edge = away_ml_edge
                ml_result = row.get("away_ml_result") or ""
                ml_odds = parse_float(row.get("away_moneyline"))
                ml_model_prob = prior["away_win_prob"]
                ml_market_prob = away_market_ml

        row_out = {
            "season": season,
            "game_type": row.get("game_type") or "",
            "week": parse_int(row.get("week")),
            "game_id": row.get("game_id") or "",
            "gameday": row.get("gameday") or "",
            "matchup_key": row.get("matchup_key") or f"{away}@{home}",
            "away_team": away,
            "home_team": home,
            "away_score": parse_int(row.get("away_score")),
            "home_score": parse_int(row.get("home_score")),
            "away_warps_wins": round(away_warps, 3),
            "home_warps_wins": round(home_warps, 3),
            "home_strength_gap_wins": round(prior["home_strength_gap_wins"], 3),
            "home_win_prob": round(prior["home_win_prob"], 4),
            "away_win_prob": round(prior["away_win_prob"], 4),
            "home_fair_moneyline": prior["home_fair_moneyline"],
            "away_fair_moneyline": prior["away_fair_moneyline"],
            "fair_home_spread": round(prior["fair_home_spread"], 2),
            "fair_away_spread": round(prior["fair_away_spread"], 2),
            "market_home_spread": home_spread_line,
            "market_away_spread": away_spread_line,
            "home_spread_edge": round(home_spread_edge, 3) if home_spread_edge is not None else "",
            "away_spread_edge": round(away_spread_edge, 3) if away_spread_edge is not None else "",
            "spread_pick_side": spread_side,
            "spread_pick_team": home if spread_side == "HOME" else away if spread_side == "AWAY" else "",
            "spread_edge_points": round(spread_edge, 3) if spread_edge is not None else "",
            "spread_odds": spread_odds,
            "spread_result": spread_result,
            "spread_roi": round(bet_roi(spread_odds, spread_result), 4) if bet_roi(spread_odds, spread_result) is not None else "",
            "market_home_ml_no_vig_prob": home_market_ml,
            "market_away_ml_no_vig_prob": away_market_ml,
            "home_ml_edge": round(home_ml_edge, 4) if home_ml_edge is not None else "",
            "away_ml_edge": round(away_ml_edge, 4) if away_ml_edge is not None else "",
            "ml_pick_side": ml_side,
            "ml_pick_team": home if ml_side == "HOME" else away if ml_side == "AWAY" else "",
            "ml_model_prob": round(ml_model_prob, 4) if ml_model_prob is not None else "",
            "ml_market_prob": round(ml_market_prob, 4) if ml_market_prob is not None else "",
            "ml_edge_prob": round(ml_edge, 4) if ml_edge is not None else "",
            "ml_odds": ml_odds,
            "ml_ev": round(moneyline_ev(ml_model_prob, ml_odds), 4) if moneyline_ev(ml_model_prob, ml_odds) is not None else "",
            "ml_result": ml_result,
            "ml_roi": round(bet_roi(ml_odds, ml_result), 4) if bet_roi(ml_odds, ml_result) is not None else "",
            "model": "WARPS v2.3 historical game prior",
            "method": "preseason WARPS projected wins -> logistic win probability -> normal-margin fair spread",
        }
        output.append(row_out)
    return output


def summarize_picks(rows: list[dict]) -> dict:
    graded = [row for row in rows if row["result"] in {"win", "loss", "push"}]
    decisions = [row for row in graded if row["result"] in {"win", "loss"}]
    wins = sum(1 for row in decisions if row["result"] == "win")
    losses = len(decisions) - wins
    pushes = sum(1 for row in graded if row["result"] == "push")
    roi_values = [row["roi"] for row in graded if row["roi"] is not None]
    units = sum(roi_values) if roi_values else None
    by_season = defaultdict(list)
    for row in graded:
        by_season[row["season"]].append(row)
    profitable_seasons = 0
    season_count = 0
    for season_rows in by_season.values():
        season_roi = sum(row["roi"] for row in season_rows if row["roi"] is not None)
        season_count += 1
        if season_roi > 0:
            profitable_seasons += 1
    return {
        "plays": len(rows),
        "graded": len(graded),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / (wins + losses), 4) if wins + losses else None,
        "units": round(units, 4) if units is not None else None,
        "roi_per_play": round(units / len(roi_values), 4) if roi_values else None,
        "profitable_season_pct": round(profitable_seasons / season_count, 4) if season_count else None,
    }


def threshold_rows(game_edges: list[dict]) -> tuple[list[dict], list[dict]]:
    pick_rows = []
    summary_rows = []

    spread_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    for threshold in spread_thresholds:
        rows = []
        for row in game_edges:
            edge = parse_float(row.get("spread_edge_points"))
            if edge is None or edge < threshold:
                continue
            pick = {
                "market": "spread",
                "threshold": threshold,
                "season": row["season"],
                "game_type": row["game_type"],
                "week": row["week"],
                "game_id": row["game_id"],
                "matchup_key": row["matchup_key"],
                "side": row["spread_pick_side"],
                "pick_team": row["spread_pick_team"],
                "edge": edge,
                "odds": parse_float(row.get("spread_odds")),
                "result": row["spread_result"],
                "roi": parse_float(row.get("spread_roi")),
            }
            rows.append(pick)
            pick_rows.append(pick)
        summary = summarize_picks(rows)
        summary_rows.append({"market": "spread", "threshold_type": "edge_points", "threshold": threshold, **summary})

    ml_edge_thresholds = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]
    for threshold in ml_edge_thresholds:
        rows = []
        for row in game_edges:
            edge = parse_float(row.get("ml_edge_prob"))
            if edge is None or edge < threshold:
                continue
            pick = {
                "market": "moneyline",
                "threshold": threshold,
                "season": row["season"],
                "game_type": row["game_type"],
                "week": row["week"],
                "game_id": row["game_id"],
                "matchup_key": row["matchup_key"],
                "side": row["ml_pick_side"],
                "pick_team": row["ml_pick_team"],
                "edge": edge,
                "odds": parse_float(row.get("ml_odds")),
                "result": row["ml_result"],
                "roi": parse_float(row.get("ml_roi")),
            }
            rows.append(pick)
            pick_rows.append(pick)
        summary = summarize_picks(rows)
        summary_rows.append({"market": "moneyline", "threshold_type": "edge_prob", "threshold": threshold, **summary})

    ml_ev_thresholds = [0.02, 0.05, 0.08, 0.10, 0.15, 0.20]
    for threshold in ml_ev_thresholds:
        rows = []
        for row in game_edges:
            ev = parse_float(row.get("ml_ev"))
            if ev is None or ev < threshold:
                continue
            pick = {
                "market": "moneyline",
                "threshold": threshold,
                "season": row["season"],
                "game_type": row["game_type"],
                "week": row["week"],
                "game_id": row["game_id"],
                "matchup_key": row["matchup_key"],
                "side": row["ml_pick_side"],
                "pick_team": row["ml_pick_team"],
                "edge": ev,
                "odds": parse_float(row.get("ml_odds")),
                "result": row["ml_result"],
                "roi": parse_float(row.get("ml_roi")),
            }
            rows.append(pick)
            pick_rows.append(pick)
        summary = summarize_picks(rows)
        summary_rows.append({"market": "moneyline", "threshold_type": "ev", "threshold": threshold, **summary})

    return pick_rows, summary_rows


def best_rows(summary_rows: list[dict]) -> list[dict]:
    candidates = [
        row for row in summary_rows
        if row["plays"] >= 100 and row["roi_per_play"] is not None
    ]
    return sorted(candidates, key=lambda row: (row["roi_per_play"], row["plays"]), reverse=True)[:10]


def markdown_report(summary: dict, summary_rows: list[dict]) -> str:
    lines = [
        "# WARPS Game Edge Backtest",
        "",
        "This audit tests preseason WARPS team-strength priors against historical game markets.",
        "It does not include the weekly engine's injury, referee, weather, sharp-split, or line-movement layers.",
        "",
        "## Headline",
        "",
        "WARPS game priors are useful as a baseline, but they should not be treated as standalone spread or moneyline picks.",
        "The strongest spread thresholds get close to break-even before vig, while moneyline edges are materially negative in this broad historical sweep.",
        "",
        "## Model Setup",
        "",
        f"- Rows joined: {summary['rows_joined']}",
        f"- Home-field value: {summary['home_field_wins']} projected wins",
        f"- Win-gap logit scale: {summary['win_gap_logit_scale']}",
        f"- Margin standard deviation: {summary['nfl_margin_sd']}",
        "- Fair spread method: WARPS projected win gap -> win probability -> normal-margin spread",
        "- Market edge method: model spread/probability compared to historical no-vig market line/probability",
        "- Realized units: listed American odds from the market spine",
        "",
        "## Threshold Summary",
        "",
        "| Market | Threshold Type | Threshold | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        wl = f"{row['wins']}-{row['losses']}-{row['pushes']}"
        win_rate = "" if row["win_rate"] is None else f"{row['win_rate']:.1%}"
        units = "" if row["units"] is None else f"{row['units']:+.2f}"
        roi = "" if row["roi_per_play"] is None else f"{row['roi_per_play']:+.2%}"
        prof = "" if row["profitable_season_pct"] is None else f"{row['profitable_season_pct']:.1%}"
        lines.append(
            f"| {row['market']} | {row['threshold_type']} | {row['threshold']} | "
            f"{row['plays']} | {wl} | {win_rate} | {units} | {roi} | {prof} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Spread: the best broad threshold was around 3.5-4.0 points of model-vs-market edge, but it still finished slightly negative after vig.",
        "- Moneyline: broad WARPS probability edges did not clear market pricing. Treat moneyline as a weekly-engine research overlay until confirmed by richer signals.",
        "- Practical use: show WARPS spread/ML as a fair-line prior on the site, then require weekly confirmations before promoting anything to an actionable edge.",
        "",
        "## Next Gate",
        "",
        "Join this prior to the weekly engine factors and test whether spreads/ML improve when WARPS agrees with injuries, market movement, referee context, and source-health gates.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest WARPS game-prior spread and ML edges")
    parser.add_argument("--market-spine", type=Path, default=DEFAULT_MARKET_SPINE)
    parser.add_argument("--warps", type=Path, default=DEFAULT_WARPS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    market_rows = read_csv(args.market_spine)
    warps = load_warps(args.warps)
    game_edges = build_game_edges(market_rows, warps)
    pick_rows, summary_rows = threshold_rows(game_edges)
    best = best_rows(summary_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "warps_game_edges.csv", game_edges)
    write_csv(args.output_dir / "warps_game_edge_threshold_picks.csv", pick_rows)
    write_csv(args.output_dir / "warps_game_edge_threshold_summary.csv", summary_rows)
    summary = {
        "market_spine": str(args.market_spine),
        "warps_projection_source": str(args.warps),
        "model": "WARPS v2.3 historical game prior",
        "rows_joined": len(game_edges),
        "home_field_wins": HOME_FIELD_WINS,
        "win_gap_logit_scale": WIN_GAP_LOGIT_SCALE,
        "nfl_margin_sd": NFL_MARGIN_SD,
        "limitations": [
            "Uses preseason WARPS team-strength priors only.",
            "Does not include weekly injuries, refs, weather, line movement, or market-split data.",
            "Postseason rows are included if present in the market spine, but the prior is still preseason team strength.",
            "No-vig probabilities are used to measure market edge; listed American odds are used for realized units.",
        ],
        "best_thresholds_min_100_plays": best,
    }
    (args.output_dir / "warps_game_edge_summary.json").write_text(json.dumps(summary, indent=2))
    (args.output_dir / "warps_game_edge_report.md").write_text(markdown_report(summary, summary_rows))

    print(json.dumps({
        "rows_joined": len(game_edges),
        "summary": str(args.output_dir / "warps_game_edge_summary.json"),
        "top_thresholds": best[:5],
    }, indent=2))


if __name__ == "__main__":
    main()
