# Claude Session Memory

## Project Identity
- **Repo**: `whatsaliju/nfl-betting-automation`
- **Owner**: Liju Varughese (lvarughese@gmail.com)
- **Dev branch**: `claude/warps-nfl-empirical-run-p2Nbd` — always reset from main after a merge with `git push --force-with-lease`

## Deployment Architecture (critical — do not confuse these)

### NFL Signal → Cloudflare Pages
- URL: **`https://nflsignal.com`** (custom domain; `nflsignal.pages.dev` is the underlying pages.dev address)
- Serves `site/dist/index.html` as the NFL Signal landing page
- Deployed automatically on push to `main` via Cloudflare Pages integration
- Deep links: `/matrix.html` (board app), `/warps.html` (WARPS model), `/matrix.html#command`, `#pickem`, `#edges`, `#survivor`, `#scout`

### lijuvarughese.com → Bluehost (SSH deploy)
- Workflow: `.github/workflows/10_bluehost_labs_deploy.yml`
- SSH target: `/home/lijuvaru/public_html/` (Bluehost shared hosting)
- **Key step**: before upload, workflow runs `cp dist/liju.html dist/index.html` so the personal hub is the root page
- Preserves `ytts/` subfolder on the server (financial dashboards live there)
- Secrets: `BLUEHOST_SSH_KEY`, `BLUEHOST_HOST`, `BLUEHOST_USER`, `BLUEHOST_PORT`

## Vite Build Entries (`site/vite.config.ts`)
```
main   → index.html    (NFL Signal landing — Cloudflare root)
matrix → matrix.html   (board app)
warps  → warps.html    (WARPS model/paper)
liju   → liju.html     (personal hub — Bluehost root after cp swap)
```

## Personal Hub (`lijuvarughese.com`)
- Entry: `site/liju.html` → `site/src/liju-main.tsx` → `site/src/PersonalApp.tsx`
- Styles: `site/src/personal.css` (Barlow Condensed + Barlow, dark/light themes, card left-border accents)
- Sections:
  - **Sports Analytics**: NFL Signal (navy, links to `nflsignal.com`), WARPS-NFL™ (red, links to `nflsignal.com/warps.html`)
  - **Financial Research**: Val Cap Quant (green, links to `ytts/research_dashboard_app.html`, `ytts/longhold_dashboard.html`)

## NFL Signal Landing (`nflsignal.com`)
- Entry: `site/index.html` → `site/src/main.tsx` → `site/src/LandingApp.tsx`
- Styles: `site/src/landing.css`
- Theme: NFL Shield palette — navy `#013369`, red `#D50A0A`, ground `#f6f8fc`, border `#dce5f0`
- Hero: "NFL analysis. 26 seasons deep." — Seven tool cards, no direct CTAs
- 7 tool cards mapping user goals to app features:
  1. Season Matrix (`matrix.html#matrix`) — "See the full 2026 season at a glance"
  2. Weekly Picks (`matrix.html#command`) — "What should I bet this week?"
  3. Pick'em (`matrix.html#pickem`) — "Who wins straight-up for my pool?"
  4. Survivor Pool (`matrix.html#survivor`) — "Which team do I pick for Survivor?"
  5. Edge Board (`matrix.html#edges`) — "Which games have real value on the spread?"
  6. Schedule & Scout (`matrix.html#scout`) — "What does my team's schedule look like?"
  7. Track Record & Model (`warps.html`) — "Can I trust this model?"

## Board App (`matrix.html`)
- Pick'em completed-game detection: `isCompleted = g.away_score != null && g.home_score != null`
- Completed games show Final badge + score; betting sections hidden for completed games
- Tiebreaker table excludes completed games
- CSS classes for completed games: `.pickem-final`, `.pk-final-badge`, `.pk-score`, `.pk-winner`, `.pk-loser`
- WSH/WAS normalization: `normalizeTla()` maps WSH→WAS
- UTC→ET: `utcToEt()` applies -4h EDT offset for game grouping

## TLA Canonical Form (critical — WSH/WAS is a recurring trap)
- **Canonical TLA for Washington is WAS everywhere** (NFL.com, Odds API, Action Network all use WAS)
- ESPN scoreboard API returns WSH — `canonical_team()` in `analyzers/nfl_common.py` normalizes WSH→WAS at line 73-74
- `normalize_matchup_key()` (also in `nfl_common.py`) uses `canonical_team()` — all matchup key construction goes through this
- `build_week_master_table.py` removed its `MATCHUP_KEY_ALIASES` (was converting WAS→WSH, the wrong direction); replaced with `normalize_matchup_key()`
- `graders/grade_week_results.py` wraps ESPN key in `normalize_matchup_key()` so score lookups match master CSV
- `analysis/join_model_and_actuals.py` maps "Washington Commanders"→"WAS"
- Other scripts (`backtest_historical_engine.py`, `build_historical_market_spine.py`, etc.) carry their own `WSH→WAS` alias dicts — now redundant but harmless
- `builders/build_matrix_engine_feed.py` has defensive WSH→WAS in `canonical_tla()` and `team_division()` — also harmless

## WARPS Data Pipeline

### Key Files
- `data/historical/warps_{season}_market_overlay.csv` — per-game WARPS fair values + market lines; season-named (e.g. `warps_2026_market_overlay.csv`)
- `site/src/data/warpsMarketOverlay.json` — same data as JSON for the React overlay panel
- `data/historical/warps_edge_log.csv` — weekly performance log: every priced game's edge, engine confirmation, and outcomes (cover/miss/push)
- `data/historical/week{N}_master.json` — master record per game with all stage data (initial/update/lock/final); contains `{stage}_sharp_spread_line`, `{stage}_sharp_total_line`, `{stage}_sharp_moneyline_line`

### Key Scripts
- `scripts/patch_overlay_from_master.py` — reads master JSON sharp lines and patches overlay CSV: updates market spreads/ML, adds `market_total` column, recomputes edges. Stage preference: lock→update→initial. Does NOT add fair_total (WARPS R²=0.002 vs totals = no signal).
- `scripts/log_warps_edge_performance.py` — appends one row per priced game after grading; idempotent (removes existing week rows before appending). Run by Workflow 6 (Grade Week Results).
- `scripts/refresh_warps_market_overlay.py` — full rebuild from WARPS priors + Odds API (or `--fair-line-only`). Writes both CSV and JSON.

### Overlay Schema
Key columns: `season`, `week`, `matchup_key`, `fair_home_spread`, `fair_away_spread`, `home_win_prob`, `away_win_prob`, `market_home_spread`, `market_away_spread`, `market_home_moneyline`, `market_away_moneyline`, `market_total` (added PR#189), edge columns, `status` (priced/fair_line_only), `source`

### WARPS Model Limitations
- **Total predictions**: R²=0.002 across 3,028 games (2015–2025). WARPS does not generate meaningful fair totals. `market_total` is shown but no total edge is computed.
- **Win probability**: Pythagorean expectation — beats statistical baseline in 25 of 26 seasons.

## Workflow Chain (trigger order)
1. **Wf 1** `1_referee_collection.yml` — Wed schedule → commits referee/SDQL data → fires `referee-data-ready`
2. **Wf 2** `2_initial_market_data.yml` — `referee-data-ready` → scrapes Action Network → fires `initial-market-data`
3. **Wf 3** `3_market_update.yml` — 5 schedule crons (Wed/Thu/Sat/Sun/Mon) → scrapes lines + lineups → fires `market-data-ready`
4. **Wf 4.5** `4.5_enhanced_pro_workflow.yml` — `initial-market-data` or `market-data-ready` → runs engine → builds master JSON → **patches overlay CSV** → **rebuilds warpsMarketOverlay.json** → builds matrix feed → commits `data/` + `site/src/data/` → fires `analysis-complete`
5. **Wf 5** `5_conversational_email.yml` — `analysis-complete` → sends betting card email (no commit)
6. **Wf 6 Perf** `6_update-performance.yml` — Tue schedule → updates performance report → fires `performance-complete`
7. **Wf 6 Grade** `6. Grade Week Results.yml` — `performance-complete` → grades results → logs edge performance → rebuilds matrix feed → commits → fires `grades-complete`
8. **Wf 9** `9. analysis-model-vs-actuals.yml` — `grades-complete` → model vs actuals analysis
9. **Wf 11** `11_refresh_warps_market_overlay.yml` — daily 9:15am ET → full overlay rebuild from Odds API → **patches with master sharp lines** → rebuilds JSON → commits
10. **Wf 8** `8_matrix_site_build.yml` — push to main (path filter: `site/**`, engine feed, overlay CSV) → builds static site
11. **Wf 10** `10_bluehost_labs_deploy.yml` — push to main (same path filter) → deploys to Bluehost

### Seasonal Maintenance (start of each season)
- Update `warps_2026_market_overlay.csv` path filters in `8_matrix_site_build.yml` and `10_bluehost_labs_deploy.yml` to the new season year
- Build new `warps_{season}_game_priors.csv` for the new season
- `validate_engine_contracts.py` has hardcoded schedule dates for known seasons — add new season's Week 1 date

### Known Deferred Gap
- **Wf 11 doesn't rebuild engine feed**: After Wf 11's daily Odds API refresh, `warpsMarketOverlay.json` has fresh prices but `matrix_engine_feed.json` is stale until Wf 4.5 next runs. Deferred — engine feed needs master JSON context that Wf 11 doesn't run. The window is at most one day since Wf 4.5 runs multiple times weekly.

## Git Workflow
- After each PR merges to main, reset the dev branch:
  ```
  git fetch origin main
  git checkout -B claude/warps-nfl-empirical-run-p2Nbd origin/main
  git push --force-with-lease
  ```
- Push: `git push -u origin claude/warps-nfl-empirical-run-p2Nbd`
- Always create a PR after pushing; check for `.github/pull_request_template.md` first
- PRs subscribed via `mcp__Claude_Code_Remote__subscribe_pr_activity`

## Supabase
- Publishable key `sb_publishable_Fh_OJIdc1gVT9BYjv8Ud9A_mWmQTbKx` — safe for client-side use (RLS enforced)
- Never log `GMAIL_USERNAME` or `GMAIL_APP_PASSWORD`

## Active PRs
_None as of 2026-09-18_
