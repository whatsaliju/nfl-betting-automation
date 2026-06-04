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
STAGES = ("initial", "update", "lock", "final")


def sort_master_path(path):
    match = re.search(r"week(\d+)_master\.json$", path.name)
    return int(match.group(1)) if match else 999


def first_present(row, names):
    for name in names:
        value = row.get(name)
        if value not in (None, "", []):
            return value
    return None


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
    trace = row.get(f"{stage}_recommendation_trace")
    if isinstance(trace, str) and trace.strip():
        try:
            trace = json.loads(trace)
        except json.JSONDecodeError:
            pass
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
    return {
        "key": f"{team}:W{game.get('week')}",
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

    feed = {
        "feed_version": "2026.1",
        "source": "nfl-betting-automation weekly master files",
        "game_count": len(games),
        "team_cell_count": len(team_cells),
        "model_readiness": model_readiness_payload(),
        "games": games,
        "team_cells": team_cells,
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
        writer = csv.DictWriter(f, fieldnames=fields)
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
