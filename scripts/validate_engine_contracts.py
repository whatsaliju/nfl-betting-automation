#!/usr/bin/env python3
"""Fast offline sanity checks for the NFL betting engine.

This intentionally avoids live scraping or network calls. It checks the shared
parsers, model config, and replay grading artifacts so refactors fail loudly
before a full workflow run.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.nfl_common import (
    canonical_team,
    espn_season_type,
    espn_week,
    home_spread_from_line,
    nflverse_game_types,
    normalize_matchup_key,
    normalize_season_type,
    reference_time_for_stage,
    split_matchup,
    spread_line_for_side,
    total_line_for_side,
)


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def validate_common_parsers(failures):
    cases = [
        (canonical_team("New York Jets"), "NYJ", "full team name canonicalization"),
        (canonical_team("jets"), "NYJ", "nickname canonicalization"),
        (canonical_team("panthers4/0"), "CAR", "seed suffix canonicalization"),
        (normalize_matchup_key("New England Patriots @ New York Jets"), "NE@NYJ", "full matchup key"),
        (normalize_matchup_key("NE at NYJ"), "NE@NYJ", "abbrev matchup key"),
        (home_spread_from_line("-13 (-110) | +12.5 (+100)"), 12.5, "home spread extraction"),
        (home_spread_from_line("+3.5 (-110) | -3.5 (-110)"), -3.5, "favorite home spread extraction"),
        (spread_line_for_side("-13 (-110) | +12.5 (+100)", "AWAY"), -13.0, "away spread line"),
        (spread_line_for_side("-13 (-110) | +12.5 (+100)", "HOME"), 12.5, "home spread line"),
        (total_line_for_side("O 44.5 (-110) | U 44.5 (-110)", "OVER"), 44.5, "over total line"),
        (total_line_for_side("O 44.5 (-110) | U 44.5 (-110)", "UNDER"), 44.5, "under total line"),
        (split_matchup("Detroit Lions @ Los Angeles Rams"), ("Detroit Lions", "Los Angeles Rams"), "matchup split"),
        (normalize_season_type("PRE", 1), "PRE", "preseason explicit season type"),
        (nflverse_game_types("PRE"), ["PRE"], "nflverse preseason game type"),
        (espn_season_type("PRE", 1), 1, "ESPN preseason season type"),
        (normalize_season_type(None, 19), "POST", "postseason week inference"),
        (espn_season_type("POST", 19), 3, "ESPN postseason season type"),
        (espn_week("POST", 19), 1, "ESPN wild-card week mapping"),
        (espn_week("POST", 22), 5, "ESPN Super Bowl week mapping"),
    ]
    for got, expected, label in cases:
        check(got == expected, f"{label}: expected {expected!r}, got {got!r}", failures)


def validate_model_config(path, failures):
    check(path.exists(), f"model config missing: {path}", failures)
    if not path.exists():
        return

    config = json.loads(path.read_text())
    weights = config.get("factor_weights", {})
    selector = config.get("selector", {})
    source_quality = config.get("source_quality", {})

    required_weights = {
        "sharp_consensus_score",
        "referee_ats_score",
        "referee_ou_score",
        "weather_score",
        "injury_score",
        "situational_score",
        "statistical_score",
        "game_theory_score",
        "schedule_score",
    }
    missing_weights = sorted(required_weights - set(weights))
    check(not missing_weights, f"model config missing weights: {missing_weights}", failures)
    check(weights.get("game_theory_score") == 0.0, "game_theory_score should remain 0.0", failures)
    check(selector.get("require_sharp_spread_edge") is True, "spread selector should require sharp edge", failures)
    check(selector.get("total_threshold", 0) >= 4, "total threshold should be at least 4", failures)
    check(
        selector.get("injury_context_threshold_bump", 0) >= 0,
        "injury context threshold bump should be configured as a non-negative number",
        failures,
    )
    check(
        source_quality.get("block_picks_on_unsafe") is True,
        "unsafe source quality should block picks",
        failures,
    )
    for source in ("queries", "action_markets", "referee_trends"):
        check(
            source in source_quality.get("critical_sources", []),
            f"{source} should be a critical source",
            failures,
        )


def validate_replay_stage_times(failures):
    expected = {
        "initial": "2025-11-13T12:00:00+00:00",
        "update": "2025-11-15T12:00:00+00:00",
        "lock": "2025-11-15T16:00:00+00:00",
        "final": "2025-11-16T00:00:00+00:00",
    }
    for stage, expected_value in expected.items():
        got = reference_time_for_stage(2025, 11, stage).isoformat()
        check(got == expected_value, f"{stage} reference time expected {expected_value}, got {got}", failures)
    got = reference_time_for_stage(2025, 22, "final", "POST").isoformat()
    expected_value = "2026-02-08T00:00:00+00:00"
    check(got == expected_value, f"Super Bowl reference time expected {expected_value}, got {got}", failures)


def validate_replay_outputs(replay_root, stage, failures, expected=None):
    summary_path = replay_root / "pick_results_summary.json"
    rows_path = replay_root / "pick_results.csv"
    if not summary_path.exists() and not rows_path.exists():
        return

    check(summary_path.exists(), f"missing replay grade summary: {summary_path}", failures)
    check(rows_path.exists(), f"missing replay grade rows: {rows_path}", failures)
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        check(summary.get("missing_results", 0) == 0, "replay has missing final results", failures)
        check(summary.get("missing_lines", 0) == 0, "replay has missing market lines", failures)
        check(summary.get("graded", 0) == summary.get("plays", 0), "not all replay plays were graded", failures)
        check(summary.get("by_result_source"), "replay summary missing result source counts", failures)
        for key, expected_value in (expected or {}).items():
            if expected_value is not None:
                check(
                    summary.get(key) == expected_value,
                    f"expected replay {key}={expected_value}, got {summary.get(key)}",
                    failures,
                )

    if rows_path.exists():
        with rows_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        required_columns = {
            "matchup",
            "market",
            "side",
            "line",
            "result",
            "result_source",
            "result_source_url",
            "data_quality_status",
            "trace_final_market",
            "trace_final_reason",
            "trace_aligned_sources",
            "trace_conflict_sources",
        }
        missing_columns = sorted(required_columns - set(reader.fieldnames or []))
        check(not missing_columns, f"pick_results missing columns: {missing_columns}", failures)
        check(all(row.get("result_source") for row in rows), "some graded rows lack result_source", failures)

    walk_forward_path = replay_root / "selector_walk_forward_summary.json"
    if walk_forward_path.exists():
        summary = json.loads(walk_forward_path.read_text())
        check(summary.get("folds", 0) > 0, "walk-forward summary has no folds", failures)
        check(summary.get("walk_forward"), "walk-forward summary missing optimized policy summary", failures)
        check(summary.get("active_policy_walk_forward"), "walk-forward summary missing active policy benchmark", failures)
        active = summary.get("active_policy_walk_forward") or {}
        check(active.get("graded", 0) == active.get("plays", 0), "active walk-forward has ungraded plays", failures)
        check(active.get("missing_results", 0) == 0, "active walk-forward has missing results", failures)

    readiness_path = replay_root / "model_readiness_report.json"
    readiness_markdown_path = replay_root / "model_readiness_report.md"
    if readiness_path.exists() or readiness_markdown_path.exists():
        check(readiness_path.exists(), f"missing readiness report JSON: {readiness_path}", failures)
        check(readiness_markdown_path.exists(), f"missing readiness report markdown: {readiness_markdown_path}", failures)
        if readiness_path.exists():
            readiness = json.loads(readiness_path.read_text())
            verdict = readiness.get("verdict") or {}
            check(verdict.get("status"), "readiness report missing verdict status", failures)
            check(readiness.get("replay"), "readiness report missing replay summary", failures)
            check(readiness.get("walk_forward"), "readiness report missing walk-forward summary", failures)

    for path in replay_root.glob(f"week*/{stage}/week*_selector_audit.csv"):
        with path.open() as f:
            reader = csv.DictReader(f)
            required = {
                "data_quality_status",
                "pick_market",
                "selector_score",
                "aggregate_score",
                "trace_final_market",
                "trace_final_reason",
                "trace_spread_side",
                "trace_total_side",
            }
            missing = sorted(required - set(reader.fieldnames or []))
            check(not missing, f"{path} missing selector audit columns: {missing}", failures)

    analytics_paths = sorted(replay_root.glob(f"week*/{stage}/week*_analytics.json"))
    for analytics_path in analytics_paths:
        week_match = analytics_path.name.replace("_analytics.json", "")
        manifest_path = analytics_path.with_name(f"{week_match}_run_manifest.json")
        source_health_path = analytics_path.with_name(f"{week_match}_source_health.json")
        source_health_text_path = analytics_path.with_name(f"{week_match}_source_health.txt")
        check(manifest_path.exists(), f"missing run manifest: {manifest_path}", failures)
        check(source_health_path.exists(), f"missing source health JSON: {source_health_path}", failures)
        check(source_health_text_path.exists(), f"missing source health text: {source_health_text_path}", failures)
        games = json.loads(analytics_path.read_text())
        for game in games:
            trace = game.get("recommendation_trace")
            check(isinstance(trace, dict), f"{analytics_path} game missing recommendation_trace object", failures)
            if isinstance(trace, dict):
                check("market_candidates" in trace, f"{analytics_path} trace missing market_candidates", failures)
                check("final_decision" in trace, f"{analytics_path} trace missing final_decision", failures)
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            check(manifest.get("model_version"), f"{manifest_path} missing model_version", failures)
            check(manifest.get("analysis_reference_time"), f"{manifest_path} missing analysis_reference_time", failures)
            check("data_quality" in manifest, f"{manifest_path} missing data_quality", failures)
            check(
                (manifest.get("data_quality") or {}).get("status") != "UNSAFE",
                f"{manifest_path} has UNSAFE data quality",
                failures,
            )
            input_files = manifest.get("input_files", {})
            check(input_files, f"{manifest_path} missing input file fingerprints", failures)
            for source, fingerprint in input_files.items():
                for field in ("path", "exists", "size_bytes", "modified_at", "sha256"):
                    check(field in fingerprint, f"{manifest_path} {source} fingerprint missing {field}", failures)
                if fingerprint.get("exists"):
                    check(
                        isinstance(fingerprint.get("size_bytes"), int) and fingerprint.get("size_bytes") >= 0,
                        f"{manifest_path} {source} has invalid size_bytes",
                        failures,
                    )
                    check(
                        len(fingerprint.get("sha256", "")) == 64,
                        f"{manifest_path} {source} has invalid sha256",
                        failures,
                    )
            check("config" in manifest, f"{manifest_path} missing config snapshot", failures)
            check("environment" in manifest, f"{manifest_path} missing environment snapshot", failures)
            if source_health_path.exists():
                source_health = json.loads(source_health_path.read_text())
                check(
                    source_health.get("status") == (manifest.get("data_quality") or {}).get("status"),
                    f"{source_health_path} status does not match manifest data quality",
                    failures,
                )
                check(source_health.get("sources"), f"{source_health_path} missing sources", failures)


def validate_run_directory(run_dir, failures):
    run_dir = Path(run_dir)
    check(run_dir.exists(), f"run directory missing: {run_dir}", failures)
    if not run_dir.exists():
        return

    analytics_paths = sorted(run_dir.glob("week*_analytics.json"))
    check(analytics_paths, f"{run_dir} missing week analytics JSON", failures)
    for analytics_path in analytics_paths:
        week_prefix = analytics_path.name.replace("_analytics.json", "")
        csv_path = analytics_path.with_name(f"{week_prefix}_analytics.csv")
        audit_path = analytics_path.with_name(f"{week_prefix}_selector_audit.csv")
        manifest_path = analytics_path.with_name(f"{week_prefix}_run_manifest.json")
        source_health_path = analytics_path.with_name(f"{week_prefix}_source_health.json")
        source_health_text_path = analytics_path.with_name(f"{week_prefix}_source_health.txt")

        check(csv_path.exists(), f"missing analytics CSV: {csv_path}", failures)
        check(audit_path.exists(), f"missing selector audit: {audit_path}", failures)
        check(manifest_path.exists(), f"missing run manifest: {manifest_path}", failures)
        check(source_health_path.exists(), f"missing source health JSON: {source_health_path}", failures)
        check(source_health_text_path.exists(), f"missing source health text: {source_health_text_path}", failures)

        games = json.loads(analytics_path.read_text())
        check(isinstance(games, list), f"{analytics_path} should contain a list", failures)
        check(len(games) > 0, f"{analytics_path} contains no games", failures)
        for game in games:
            check(game.get("model_version"), f"{analytics_path} game missing model_version", failures)
            check("pick_metadata" in game, f"{analytics_path} game missing pick_metadata", failures)
            check("data_quality" in game, f"{analytics_path} game missing data_quality", failures)
            trace = game.get("recommendation_trace")
            check(isinstance(trace, dict), f"{analytics_path} game missing recommendation_trace object", failures)
            if isinstance(trace, dict):
                check("market_candidates" in trace, f"{analytics_path} trace missing market_candidates", failures)
                check("final_decision" in trace, f"{analytics_path} trace missing final_decision", failures)

        if audit_path.exists():
            with audit_path.open() as f:
                reader = csv.DictReader(f)
                required = {
                    "data_quality_status",
                    "pick_market",
                    "selector_score",
                    "aggregate_score",
                    "trace_final_market",
                    "trace_final_reason",
                    "trace_spread_side",
                    "trace_total_side",
                }
                missing = sorted(required - set(reader.fieldnames or []))
                check(not missing, f"{audit_path} missing selector audit columns: {missing}", failures)

        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            check(manifest.get("model_version"), f"{manifest_path} missing model_version", failures)
            check(manifest.get("analysis_reference_time"), f"{manifest_path} missing analysis_reference_time", failures)
            check(manifest.get("game_count") == len(games), f"{manifest_path} game_count does not match analytics", failures)
            check(
                (manifest.get("data_quality") or {}).get("status") != "UNSAFE",
                f"{manifest_path} has UNSAFE data quality",
                failures,
            )
            input_files = manifest.get("input_files", {})
            check(input_files, f"{manifest_path} missing input file fingerprints", failures)
            for source, fingerprint in input_files.items():
                for field in ("path", "exists", "size_bytes", "modified_at", "sha256"):
                    check(field in fingerprint, f"{manifest_path} {source} fingerprint missing {field}", failures)
                if fingerprint.get("exists"):
                    check(
                        isinstance(fingerprint.get("size_bytes"), int) and fingerprint.get("size_bytes") >= 0,
                        f"{manifest_path} {source} has invalid size_bytes",
                        failures,
                    )
                    check(
                        len(fingerprint.get("sha256", "")) == 64,
                        f"{manifest_path} {source} has invalid sha256",
                        failures,
                    )
            if source_health_path.exists():
                source_health = json.loads(source_health_path.read_text())
                check(
                    source_health.get("status") == (manifest.get("data_quality") or {}).get("status"),
                    f"{source_health_path} status does not match manifest data quality",
                    failures,
                )
                check(source_health.get("sources"), f"{source_health_path} missing sources", failures)


def validate_matrix_engine_feed(path, failures):
    path = Path(path)
    if not path.exists():
        return

    feed = json.loads(path.read_text())
    check(feed.get("feed_version"), f"{path} missing feed_version", failures)
    games = feed.get("games") or []
    team_cells = feed.get("team_cells") or {}
    check(isinstance(games, list), f"{path} games should be a list", failures)
    check(isinstance(team_cells, dict), f"{path} team_cells should be keyed by TEAM:WEEK", failures)
    check(feed.get("game_count") == len(games), f"{path} game_count mismatch", failures)
    check(feed.get("team_cell_count") == len(team_cells), f"{path} team_cell_count mismatch", failures)

    for key, cell in list(team_cells.items())[:10]:
        check(key == cell.get("key"), f"{path} team cell key mismatch for {key}", failures)
        check(":" in key and "W" in key, f"{path} team cell key should look like TEAM:WEEK: {key}", failures)
        for field in ("team", "week", "season_type", "matchup_key", "analysis_available"):
            check(field in cell, f"{path} team cell {key} missing {field}", failures)

    readiness = feed.get("model_readiness") or {}
    check(readiness.get("status"), f"{path} missing model_readiness.status", failures)
    if readiness.get("available"):
        check(readiness.get("replay"), f"{path} readiness missing replay summary", failures)
        check(readiness.get("active_walk_forward"), f"{path} readiness missing active walk-forward summary", failures)


def main():
    parser = argparse.ArgumentParser(description="Validate core offline engine contracts")
    parser.add_argument("--config", default=str(ROOT / "config" / "model_config.json"))
    parser.add_argument("--replay-root", default=str(ROOT / "data" / "backtests" / "engine_2026_1_configured"))
    parser.add_argument("--run-dir", default=None, help="Validate one live analyzer output directory such as data/week18")
    parser.add_argument("--stage", default="final")
    parser.add_argument("--expected-plays", type=int)
    parser.add_argument("--expected-graded", type=int)
    parser.add_argument("--expected-wins", type=int)
    parser.add_argument("--expected-losses", type=int)
    parser.add_argument("--matrix-feed", default=str(ROOT / "data" / "historical" / "matrix_engine_feed.json"))
    args = parser.parse_args()

    failures = []
    validate_common_parsers(failures)
    validate_model_config(Path(args.config), failures)
    validate_replay_stage_times(failures)
    if args.run_dir:
        validate_run_directory(Path(args.run_dir), failures)
    else:
        validate_replay_outputs(
            Path(args.replay_root),
            args.stage,
            failures,
            expected={
                "plays": args.expected_plays,
                "graded": args.expected_graded,
                "wins": args.expected_wins,
                "losses": args.expected_losses,
            },
        )
    validate_matrix_engine_feed(Path(args.matrix_feed), failures)

    if failures:
        print("Engine contract validation failed:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print("Engine contract validation passed")


if __name__ == "__main__":
    main()
