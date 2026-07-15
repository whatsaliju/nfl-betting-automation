# Codebase Guide

Complete map of every file in this repo and what it does.

---

## Documentation

| File | Purpose |
|---|---|
| `README.md` | Project overview, WARPS model summary, how to run scripts, key output files |
| `WARPS_NFL_paper.md` | **Canonical research paper v2.2** — full methods, results, walk-forward stability analysis, MAE heatmap, EPA null result, glossary, references. Single source of truth for the model. |
| `CODEBASE_GUIDE.md` | This file — complete file inventory |
| `CITATION.cff` | Machine-readable citation metadata for academic use |
| `LICENSE` | MIT License (code) |
| `README_weekly_tracker.md` | Documentation for the weekly in-season betting tracker system |
| `WORKFLOW_PATH_UPDATE_GUIDE.md` | Instructions for updating GitHub Actions workflow paths if repo structure changes |
| `site/DEPLOYMENT.md` | How to deploy the site to Bluehost |
| `site/README.md` | Site-specific build and development instructions |

---

## WARPS Model — Python Scripts

Current champion model is **v2.3**. v1.x files remain useful historical baselines and consensus references.

| File | Purpose |
|---|---|
| `warps_nfl_model_v2_3.py` | **Main model** — SOS-adjusted Pythagorean champion, full backtest (2000–2025) + 2026 projections. |
| `warps_monte_carlo.py` | Empirical residual Monte Carlo layer for 2026 win distributions and market-side probabilities. |
| `warps_betting_value_backtest.py` | Walk-forward betting-value lab — joins historical win totals/odds, model probabilities, no-vig market probabilities, and realized units. |
| `warps_2026_betting_card.py` | Applies historically tested gates to current 2026 projections/prices and writes the current betting card. |
| `warps_betting_stability_audit.py` | Stress-tests betting gates with era splits, leave-one-season-out, season concentration, and current-card fragility labels. |
| `warps_2026_game_priors.py` | Converts WARPS season-strength projections into 2026 game-level fair spread and moneyline priors. |
| `scripts/build_historical_market_spine.py` | Builds the normalized historical spread, moneyline, and totals spine from nflverse schedules for edge backtests. |
| `scripts/backtest_market_baselines.py` | Builds market-only spread, total, and moneyline control-group baselines from the historical market spine. |
| `scripts/backtest_warps_game_edges.py` | Backtests WARPS-derived fair spreads and moneyline probabilities against the historical market spine. |
| `scripts/run_historical_market_research.py` | Runs the historical market research stack: optional spine rebuild, market baselines, and WARPS game-edge backtest. |
| `scripts/fetch_current_odds_api.py` | Fetches raw current NFL spreads and moneylines from The Odds API for later normalization. |
| `scripts/normalize_current_market_odds.py` | Normalizes live/current spread and moneyline odds from Odds API JSON, Action CSV, or an already-normalized CSV. |
| `scripts/build_2026_warps_market_overlay.py` | Builds the site-ready 2026 WARPS fair spread/ML overlay, optionally joined to supplied current odds. |
| `scripts/refresh_2026_warps_market_overlay.py` | End-to-end wrapper for fetching/normalizing current odds and rebuilding the 2026 WARPS site overlay. |
| `warps_nfl_model_v1_8.py` | Prior champion baseline — full backtest (2000–2025) + 2026 projections. |
| `warps_nfl_model_v1_5d.py` | Earlier version — shorter training window, used as one of three consensus models |
| `warps_nfl_model_v1_6.py` | Intermediate version with additional EPA components — used as second consensus model |
| `warps_nfl_model_v1_7.py` | Pre-champion version (pure Pythagorean on short window) — reference only |
| `warps_nfl_model_v2_0.py` | Experimental — dynasty persistence modifier development |
| `warps_nfl_model_v2_1.py` | Experimental — further dynasty modifier tuning |
| `warps_bootstrap_v1_8.py` | Bootstrap confidence intervals (10,000 resamplings) for all DM test results |
| `warps_bootstrap_v1_7.py` | Same for v1.7 — reference |
| `warps_profitability_backtest.py` | Simulates betting WARPS edges vs historical Vegas opening lines (2003–2020) |
| `warps_stability_csv.py` | **Q1/Q3 stability analysis from existing CSVs** — walk-forward parameter stability (Q1) and MAE basin heatmap (Q3). No data download needed. Run: `python warps_stability_csv.py` |
| `warps_stability_analysis.py` | Full stability analysis requiring `nfl_data_py` download (~1 GB). Q2 runs from existing CSV with `--q2-only`. Q1/Q3 need raw PBP data. |

---

## WARPS Model — Output CSVs

### Current season (2026) projections

| File | Contents |
|---|---|
| `warps_2026_screen_v2_3.csv` | **Primary 2026 output** — all 32 teams, WARPS projection, Vegas O/U, edge, consensus tier |
| `warps_2026_monte_carlo.csv` | 2026 empirical residual Monte Carlo distribution — median/P10/P90, O/U probability, risk tier |
| `warps_2026_betting_card.csv` | Gate-applied 2026 betting card — bet/pass/watch, side, odds, model probability, no-vig price edge, and stake tier |
| `warps_2026_game_priors.csv` | WARPS-derived game priors for spreads and moneylines: fair spread, fair ML, and home/away win probability |
| `data/historical/nfl_market_spine.csv` | Historical per-game market spine with spread/ML/total odds, no-vig probabilities, and graded outcomes. |
| `data/backtests/historical_market_baselines/` | Market-only spread/total/ML control-group reports used as baselines before promoting model factors. |
| `data/backtests/warps_game_edges/` | WARPS game-prior edge audit outputs: row-level edges, threshold picks, summary CSV/JSON, and markdown report. |
| `data/historical/current_market_odds.csv` | Normalized current market input for WARPS fair-line overlay joins. |
| `data/historical/warps_2026_market_overlay.csv` | 2026 game-level WARPS fair-line overlay for spread/ML comparison against supplied book prices. |
| `site/src/data/warpsMarketOverlay2026.json` | Static frontend copy of the 2026 WARPS fair-line spread/ML overlay. |
| `data/current_odds_api.json` | Raw current NFL odds response from The Odds API, generated by the overlay refresh workflow. |
| `warps_2026_screen_v1_8.csv` | Prior champion 2026 output — all 32 teams, WARPS projection, Vegas O/U, edge, consensus tier |
| `warps_2026_screen_v1_5d.csv` | 2026 projections from v1.5d model (used in consensus) |
| `warps_2026_screen_v1_6.csv` | 2026 projections from v1.6 model (used in consensus) |
| `warps_2026_screen_v1_7.csv` | 2026 projections from v1.7 model (reference) |
| `warps_2026_game_probs_v1_8.csv` | Per-game win probabilities for all 2026 games (v1.8) |
| `warps_2026_game_probs_v1_5d.csv` | Per-game win probabilities (v1.5d) |
| `warps_2026_game_probs_v1_6.csv` | Per-game win probabilities (v1.6) |
| `warps_2026_game_probs_v1_7.csv` | Per-game win probabilities (v1.7) |
| `warps_2026_overrides.csv` | Manual QB adjustment overrides applied on top of statistical projections |

### Backtest results (2000–2025)

| File | Contents |
|---|---|
| `warps_backtest_team_results_v2_3.csv` | **Primary backtest** — v2.3 per-team predictions vs actuals for all 26 seasons |
| `warps_backtest_team_results_v1_8.csv` | Prior champion backtest — per-team predictions vs actuals for all 26 seasons, all 3 models' errors |
| `warps_backtest_by_year_v1_8.csv` | Year-level MAE summary: WARPS vs Pythagorean vs prior wins |
| `warps_backtest_team_results_v1_5d.csv` | Same for v1.5d |
| `warps_backtest_team_results_v1_6.csv` | Same for v1.6 |
| `warps_backtest_team_results_v1_7.csv` | Same for v1.7 |
| `warps_backtest_by_year_v1_5d.csv` | Year-level MAE for v1.5d |
| `warps_backtest_by_year_v1_6.csv` | Year-level MAE for v1.6 |
| `warps_backtest_by_year_v1_7.csv` | Year-level MAE for v1.7 |
| `warps_backtest_overall_v1_5d.csv` | Single-row overall MAE summary for v1.5d |

### Model selection & parameter search

| File | Contents |
|---|---|
| `warps_parameter_grid_v1_8.csv` | Grid search over regression factor × logit scale (v1.8 training) |
| `warps_fine_3comp_grid_v1_8.csv` | Fine grid over Pythagorean/EPA/point-diff weights (v1.8) |
| `warps_biased_dirichlet_v1_8.csv` | 300-draw randomized weight search results (v1.8) |
| `warps_consensus_screen_v1_8.csv` | Raw consensus screen output before site formatting |
| `warps_calibration_buckets_v1_8.csv` | Calibration by projected win bucket — 6 buckets (v1.8) |
| `warps_validation_metrics_v1_8.csv` | Held-out validation MAE summary (v1.8) |
| `warps_bootstrap_results_v1_8.csv` | Raw bootstrap output: 10,000 paired resamplings |
| `warps_metric_ranking_v1_6.csv` | Component metric importance ranking from v1.6 search |
| `warps_val_metric_ranking_v1_6.csv` | Validation-window metric ranking (v1.6) |
| `warps_random_weight_search_v1_6.csv` | Random search outputs for v1.6 |
| `warps_garbage_time_grid_full.csv` | Garbage-time filter test: full-sample MAE grid |
| `warps_garbage_time_grid_val.csv` | Garbage-time filter test: validation-window MAE grid |
| `warps_parameter_grid_v1_5d.csv` | Parameter grid for v1.5d |
| `warps_parameter_grid_v1_6.csv` | Parameter grid for v1.6 |
| `warps_parameter_grid_v1_7.csv` | Parameter grid for v1.7 |
| `warps_fine_3comp_grid_v1_7.csv` | Fine 3-component grid for v1.7 |
| `warps_biased_dirichlet_v1_7.csv` | Randomized search for v1.7 |
| `warps_consensus_screen_v1_7.csv` | Consensus screen for v1.7 |
| `warps_calibration_buckets_v1_5d.csv` | Calibration (v1.5d) |
| `warps_calibration_buckets_v1_6.csv` | Calibration (v1.6) |
| `warps_calibration_buckets_v1_7.csv` | Calibration (v1.7) |
| `warps_validation_metrics_v1_5d.csv` | Validation metrics (v1.5d) |
| `warps_validation_metrics_v1_6.csv` | Validation metrics (v1.6) |
| `warps_validation_metrics_v1_7.csv` | Validation metrics (v1.7) |
| `warps_bootstrap_results_v1_7.csv` | Bootstrap results (v1.7) |

### Profitability analysis

| File | Contents |
|---|---|
| `warps_profitability_summary.csv` | P&L by model and edge threshold (2003–2020) |
| `warps_profitability_by_year.csv` | Year-by-year betting P&L |
| `warps_betting_value_bets.csv` | Row-level model-vs-price backtest with edge, no-vig market probability, estimated model probability, and realized units |
| `warps_betting_value_summary.csv` | Threshold grid summary for win-edge and price-edge gates |
| `warps_betting_value_gate_summary.csv` | Richer betting gate grid with side splits, model-probability filters, model-agreement counts, and season stability |
| `warps_betting_value_by_year.csv` | Year-by-year betting-value P&L for the default gate |
| `warps_betting_stability_report.md` | Human-readable stability audit for the betting gates and current 2026 card |
| `warps_betting_gate_stability.csv` | Machine-readable gate stress tests: base, eras, and leave-one-season-out slices |
| `warps_2026_card_stability_audit.csv` | Current 2026 betting card annotated with historical gate fragility flags |

### Stability analysis outputs (Q1/Q2/Q3)

| File | Contents |
|---|---|
| `warps_q1_walk_forward.csv` | Walk-forward parameter stability: optimal w_pyth and R per year (2010–2025) |
| `warps_q2_year_by_year.csv` | Year-by-year WARPS vs Pythagorean MAE comparison (Q2, all 26 seasons) |
| `warps_q3_heatmap.csv` | Full 2D MAE landscape over w_pyth × R grid (Q3 basin analysis) |

### Miscellaneous model outputs

| File | Contents |
|---|---|
| `warps_statistical_summary_v1_7.txt` | Human-readable stats summary (v1.7) |
| `warps_statistical_summary_v1_8.txt` | Human-readable stats summary (v1.8) |

---

## Site (`site/`)

React + TypeScript dashboard. Built with Vite.

### Entry points

| File | Purpose |
|---|---|
| `site/index.html` | Main app entry point (NFL Edge Hub) |
| `site/warps.html` | Standalone WARPS paper/dashboard page |
| `site/matrix.html` | Standalone matrix page |
| `site/vite.config.ts` | Vite build configuration |
| `site/tsconfig.json` | TypeScript config |
| `site/package.json` | Dependencies and build scripts |

### Source (`site/src/`)

| File | Purpose |
|---|---|
| `App.tsx` | Root component — view routing (Matrix, Week, Compare, Results, Edges, Scout, Projections, Track), season selector, engine feed loading |
| `WARPSApp.tsx` | Standalone WARPS app wrapper used by `warps.html` |

### Components (`site/src/components/`)

| File | Purpose |
|---|---|
| `WARPSView.tsx` | **Full WARPS paper + interactive dashboard** — abstract through appendices, bet slate, performance charts, calibration, historical audit. Synced to `WARPS_NFL_paper.md` v2.2. |
| `MatrixTable.tsx` | Season schedule matrix — all 32 teams × all 18 weeks, engine overlays, heatmap, team modals |
| `WeekView.tsx` | Single-week game card view with engine overlays and edge badges |
| `CompareView.tsx` | Side-by-side team quality comparison |
| `ResultsView.tsx` | Season results table |
| `EdgeBoardView.tsx` | Live edge board — spread/total/ML recommendations (coming-soon state pre-season) |
| `ScoutView.tsx` | Team scouting view with Vegas O/U vs WARPS projection |
| `LiveAuditView.tsx` | Live win-total audit — WARPS vs Vegas vs current pace |
| `ExpectationsView.tsx` | Team expectations breakdown from engine feed |
| `TrackRecordView.tsx` | 11-season public track record — WARPS vs Vegas, KPI cards |
| `TeamModal.tsx` | Team detail modal — schedule, engine cell data, quality estimates |
| `PostseasonStrip.tsx` | Postseason game cells appended below the regular-season matrix |
| `EngineBadge.tsx` | Small badge component used in matrix cells for engine overlays |
| `ResearchView.tsx` | Research notes from engine feed (accessible via footer link) |

### Data (`site/src/data/`)

| File | Purpose |
|---|---|
| `warpsData.ts` | All WARPS model numbers hardcoded for the site — backtest results, bootstrap stats, calibration, profitability, consensus picks, trajectories |
| `nflData.ts` | Team colors, logos, historical Vegas win-total lines (2015–2025) |
| `qbData.ts` | QB tier definitions, 2026 QB changes, adjustment calculation |
| `seasonSchedules.json` | Complete NFL schedules 2015–2026 with game results |

### Library (`site/src/lib/`)

| File | Purpose |
|---|---|
| `schedule.ts` | Schedule parsing, team building, engine feed loading, matrix cell indexing |

---

## Weekly In-Season System

Automated pipeline for tracking weekly betting markets during the NFL season.

### Scrapers (`scrapers/`)

| File | Purpose |
|---|---|
| `action_network_scraper_cookies.py` | Scrapes Action Network for market data (lines, totals, sharp money %) |
| `action_network_injuries_weather.py` | Scrapes injury reports and weather data from Action Network |
| `rotowire_scraper.py` | Scrapes starting lineup data from RotoWire |
| `football_zebras_scraper.py` | Scrapes referee assignments from Football Zebras |
| `sdql_test.py` | Test script for SDQL (Sports Data Query Language) queries |

### Analyzers (`analyzers/`)

| File | Purpose |
|---|---|
| `nfl_weekly_analyzer.py` | Main weekly analysis — combines market, injury, weather, lineup data |
| `nfl_pro_analyzer.py` | Enhanced analysis with sharp money tracking and line movement |
| `nfl_reporter.py` | Report generation and formatting |
| `enhanced_report_generator.py` | Generates formatted analysis reports |
| `enhanced_email_reports.py` | Formats and sends analysis reports via email |
| `generate_ai_summary.py` | Generates AI-assisted narrative summaries of weekly picks |
| `referee_trend_generator.py` | Analyzes referee tendencies and generates trend reports |
| `nflverse_referee_trends.py` | Pulls referee data from nflverse public dataset |
| `injury_analyzer.py` | Parses and scores injury impact on game outcomes |
| `performance_tracker.py` | Tracks actual vs predicted outcomes week-over-week |
| `playoff_stats_enhancement.py` | Additional stats for playoff game analysis |
| `query_generator.py` | Generates SDQL queries for historical data lookups |
| `query_generator_v2.py` | Updated query generator |
| `nfl_common.py` | Shared utilities and constants across analyzers |

### Builders (`builders/`)

| File | Purpose |
|---|---|
| `build_matrix_engine_feed.py` | **Builds the live engine feed JSON** — combines WARPS projections, win expectations, edge picks into the format consumed by the site |
| `build_game_feature_table.py` | Builds per-game feature table for model input |
| `build_week_master_table.py` | Aggregates all weekly data into master table |

### Scripts (`scripts/`)

| File | Purpose |
|---|---|
| `validate_engine_contracts.py` | **CI contract validation** — verifies engine feed JSON structure matches what the site expects |
| `build_site_season_schedules.py` | Generates `seasonSchedules.json` from raw NFL data |
| `audit_expectation_edges.py` | Audits WARPS edges against current win-total expectations |
| `audit_game_features.py` | Validates game feature table completeness |
| `audit_moneyline_pricing.py` | Checks moneyline pricing consistency |
| `audit_recommendation_traces.py` | Traces recommendation logic for audit trail |
| `audit_source_reliability.py` | Scores data source reliability |
| `backtest_historical_engine.py` | Backtests the full engine pipeline on historical data |
| `build_model_training_dataset.py` | Builds training dataset from raw PBP data |
| `build_pick_explanations.py` | Generates plain-language explanations for each pick |
| `calibrate_selector_thresholds.py` | Calibrates pick selection thresholds |
| `closing_line_archive.py` | Archives closing line data for CLV analysis |
| `compare_replay_to_results.py` | Compares replayed engine output to actual results |
| `evaluate_factor_promotion.py` | Tests whether a new factor should be promoted into the model |
| `generate_feature_research_report.py` | Generates research report on feature importance |
| `generate_model_readiness_report.py` | Assesses whether the model is ready for live monitoring |
| `replay_2025_engine.py` | Full replay of the 2025 season engine run |
| `simulate_feature_policies.py` | Simulates different feature selection policies |
| `simulate_promotion_overlays.py` | Simulates factor promotion overlays |
| `walk_forward_selector_validation.py` | Walk-forward validation of the feature selector |

### Graders (`graders/`)

| File | Purpose |
|---|---|
| `grade_week_results.py` | Grades weekly pick performance after game results come in |

### Analysis (`analysis/`)

| File | Purpose |
|---|---|
| `join_model_and_actuals.py` | Joins model predictions with actual game outcomes for evaluation |

### Config (`config/`)

| File | Purpose |
|---|---|
| `model_config.json` | Model configuration parameters |
| `injury_rules.json` | Rules for scoring injury impact by position and severity |
| `injury_whitelist.json` | Players/positions exempt from injury adjustments |

---

## Data (`data/`)

Large directory of collected in-season data. Not intended for manual editing.

| Path | Contents |
|---|---|
| `data/action_all_markets_*.csv` | Weekly Action Network market snapshots (lines, totals, sharp %) — one file per collection date |
| `data/action_injuries_*.csv` | Weekly injury report snapshots |
| `data/action_weather_*.csv` | Weekly weather data snapshots |
| `data/rotowire_lineups_*.csv` | Starter lineup snapshots by week |
| `data/week10/` – `data/week18/` | Per-week analysis output directories |
| `data/weekWC/` `weekDIV/` `weekCONF/` `weekSB/` | Playoff week analysis directories |
| `data/backtests/` | Historical engine backtest outputs |
| `data/historical/` | Historical reference data |
| `data/analysis/` | Ad-hoc analysis outputs |
| `data/schedule_raw_2025.json` | Raw 2025 schedule data |

---

## CI/CD (`.github/workflows/`)

| File | Purpose |
|---|---|
| `0_engine_contracts.yml` | **Runs on every PR** — validates engine feed JSON contracts and TypeScript build |
| `8_matrix_site_build.yml` | **Runs on every PR/push to main** — builds the React site |
| `10_bluehost_labs_deploy.yml` | Deploys built site to Bluehost via SFTP on push to main |
| `11_refresh_warps_market_overlay.yml` | Refreshes current spread/ML prices, rebuilds WARPS overlay JSON, and commits site data changes |
| `1_referee_collection.yml` | Wed 6 PM ET — collects referee assignments |
| `2_initial_market_data.yml` | Initial weekly market data collection |
| `3_market_update.yml` | Thu/Sat/Sun market data refresh |
| `4.5_enhanced_pro_workflow.yml` | Full analysis pipeline (replaces v4) |
| `5_conversational_email.yml` | Sends formatted analysis email |
| `6_update-performance.yml` | Updates performance tracking after games |
| `7_log_actual_bets.yml` | Logs actual bets placed for tracking |
| `9. analysis-model-vs-actuals.yml` | Post-week model vs actuals comparison |
| `6. Grade Week Results.yml` | Grades pick performance after results |

---

## Root-level miscellaneous

| File | Purpose |
|---|---|
| `requirements.txt` | Python dependencies for all scripts |
| `universal_weekly_tracker.py` | Entry point for the full weekly tracking pipeline |
| `migrate_repo_structure.py` | One-time migration script (already run) |
| `initial.json` | Initial configuration snapshot |
| `week11`–`week18_performance_report.txt` | Weekly performance report text files from the 2025 season |
