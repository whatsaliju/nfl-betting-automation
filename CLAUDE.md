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

- `data/historical/warps_{season}_inseason_adjustments.csv` — manual rating changes the scores can't see yet (team, wins_delta in 17-game wins, from_week, to_week blank = open, reason). Applied by `update_warps_inseason.py` (Wf 11) to games in that week range. 2026: PHI −1.5 from Week 7 (Hurts out, blood clot; McKee starting) — set to_week when Hurts returns.
- Blend check (2015–2025, through Week 6): preseason weighted as 4–8 games is the best rest-of-season win predictor (RMSE 0.194 vs 0.208 preseason-only, 0.246 record-only), but no blend beats the closing spread after Week 6 (48.8–50.2%). WARPS spread edges after Week 5 went 50% on 2000–2025. Edge Board and the WARPS badge label spread edges "info only" after Week 5.

### Overlay Schema
Key columns: `season`, `week`, `matchup_key`, `fair_home_spread`, `fair_away_spread`, `home_win_prob`, `away_win_prob`, `market_home_spread`, `market_away_spread`, `market_home_moneyline`, `market_away_moneyline`, `market_total` (added PR#189), edge columns, `status` (priced/fair_line_only), `source`

### WARPS Model Limitations
- **Total predictions**: R²=0.002 across 3,028 games (2015–2025). WARPS does not generate meaningful fair totals. `market_total` is shown but no total edge is computed.
- **Win probability**: Pythagorean expectation — beats statistical baseline in 25 of 26 seasons.

## Workflow Chain (trigger order)
1. **Wf 1** `1_referee_collection.yml` — polls Tue 10a/2p/6p and Wed 9a/noon/3p ET for Football Zebras' own page for the week (strict, no date-matched fallback) → once found, commits referee/SDQL data → fires `referee-data-ready`; later runs stand down once `week{N}_referees.csv` has ≥10 rows; the Wed 3pm run allows fallbacks and starts the pipeline regardless. Refs posted by Tue evening in Weeks 1 and 4 of 2026.
2. **Wf 2** `2_initial_market_data.yml` — `referee-data-ready` → scrapes Action Network → fires `initial-market-data`
3. **Wf 3** `3_market_update.yml` — dispatched on time by Claude Code scheduled tasks "NFL market update — <day> <time> ET (<stage>)" (Tue 3:52p update, Wed 8:52a opening, Thu 4:22p pre_tnf (right after the contest posts lines, by 2pm MT / 4pm ET), Thu 6:52p pre_tnf, Fri 5:22p update, Sat 8:52p update, Sun 8:22a lock, Sun 11:42a final, Sun 3:07p update, Sun 6:57p update, Mon 6:52p pre_mnf; runs after inactives (90 min before kickoff) and Friday's final injury report; Aug–Feb; a full run takes ~5 min), which fire into the dev session and call workflow_dispatch; GitHub crons remain as a backup and skip if a dispatched run started in the last 3h (GitHub crons ran 2–8h late in 2026) → scrapes lines + lineups → fires `market-data-ready`
4. **Wf 4.5** `4.5_enhanced_pro_workflow.yml` — `initial-market-data` or `market-data-ready` → runs engine → builds master JSON → **patches overlay CSV** → **rebuilds warpsMarketOverlay.json** → builds matrix feed → commits `data/` + `site/src/data/` → fires `analysis-complete`
5. **Wf 5** `5_conversational_email.yml` — `analysis-complete` → sends betting card email (no commit) only at decision points (`_decision_point()` in `send_betting_card_email.py`): the week's first initial run (first look, once per week via an Actions cache marker `first-look-{season}-wk{week}`); always Thu noon–5pm ET (contest lines), Fri after 4pm ET (final injury report), Sun before 1pm ET when a game kicks off within 2.5h (after inactives for 9:30 / 1pm); and Thu evening / Sun afternoon-evening / Mon only when there's a play on a game kicking off within 3h (TNF, 4pm window, SNF, MNF). Other runs refresh the site silently; a manual Wf 5 run always sends. Each email has an "Injury & lineup changes" section: latest `data/action_injuries_*.csv` vs the previous day's file, and starting-QB changes from the week's first vs latest `rotowire_lineups_week{N}_*.csv`, limited to teams whose games haven't kicked off. Wf 4.5's nfl_reporter Wednesday email is manual-only. Tuesday sends only the Wf 6 Grade results email (Wf 6 Perf emails only on manual runs).
6. **Wf 6 Perf** `6_update-performance.yml` — Tue schedule → updates performance report → fires `performance-complete`
7. **Wf 6 Grade** `6. Grade Week Results.yml` — `performance-complete` → grades results → logs edge performance → rebuilds matrix feed → commits → fires `grades-complete`
8. **Wf 9** `9. analysis-model-vs-actuals.yml` — `grades-complete` → model vs actuals analysis
9. **Wf 11** `11_refresh_warps_market_overlay.yml` — daily 9:15am ET → full overlay rebuild from Odds API → **patches with master sharp lines** → rebuilds JSON → commits
10. **Wf 8** `8_matrix_site_build.yml` — push to main (path filter: `site/**`, engine feed, overlay CSV) → builds static site
11. **Wf 10** `10_bluehost_labs_deploy.yml` — push to main (same path filter) → deploys to Bluehost

12. **Wf 13** `13_pipeline_watchdog.yml` — emails Liju (`scripts/pipeline_watchdog.py`) right away when a watched pipeline workflow fails (`workflow_run`), and twice daily (10:37am / 6:37pm ET, Aug–Feb) checks: failed runs in the last 26h, week pointer not advanced 30h after the week's last game is final, feed week ≠ `current_week.json`, newest scrape > 3 days old, no `week{N}_referees.csv` from Wed 4pm ET on, site games for the week that aren't on the nflverse schedule. Added Nov 12 2026 after Wf 6 failed on Python 3.9 (Ubuntu 26.04 runners dropped it) and the site sat on Week 9 for three days; all workflows now pin Python 3.11+.

### Seasonal Maintenance (start of each season)
- **Run `14 New Season Rollover`** (workflow_dispatch: season = new year, reset_week on) before the preseason: `scripts/archive_season.py` moves last season's `data/week*/` folders and `data/historical/week*_master.*` to `data/archive/before_{season}/` (weekPRE* untouched) and resets `current_week.json` to Week 1. The watchdog emails a reminder in August if `current_week.json` is still on last season.
- Update `warps_2026_market_overlay.csv` path filters in `8_matrix_site_build.yml` and `10_bluehost_labs_deploy.yml` to the new season year
- Build new `warps_{season}_game_priors.csv` for the new season
- `validate_engine_contracts.py` has hardcoded schedule dates for known seasons — add new season's Week 1 date

### Engine (`analyzers/nfl_pro_analyzer.py`, config `config/model_config.json`, version 2026.9)
- Hand-tuned rules, not fitted. Spread score = sharp (0-3) + team rating (0-2), max 5; threshold 3-4 plus calendar/injury/WARPS adjustments, **capped at 5** (`max_spread_score`). Total score = |sharp total| + weather context; threshold 3. `config/model_config.json` overrides the code defaults — change both.
- Oct 21 2026 review fixes: week 7 +2 penalty removed (made spreads unpickable); injury side corrected (score = home - away, positive → AWAY); referee ATS <=35 branch reachable; referee O/U weight 0 (also gated out of totals).
- Known, left as is: SituationalAnalyzer never receives game_time (primetime/travel rules dormant); week 15+ -1 applies to every game; calendar/WARPS hard blocks were mined on WARPS-edge picks, not sharp picks; the only full-engine replay (2025 Wk 11-18, 14-4) predates most rules and leaks referee data.

### History Model (research only, not on the betting card)
- `scripts/build_history_model.py [--games games.csv]` — numpy-only L2 logistic models, walk-forward 2008–2025 (train 2003..S-1; 2000–2002 only seed referee history), 2026 scored by the 2003–2025 model; graded at the closing line (break-even 52.4%). Writes `data/backtests/history_model/{summary.json,report.md,predictions_2026.csv}`.
- WARPS enters as `warps_edge` + `warps_edge_decay` (edge × (18 − week)/17), so its weight fades by week; no hard Week 5 cut. On 2000–2025, WARPS edges ≥1.5 went 52.6% Wk 1–3, 52.4% Wk 4–5, 51.9% Wk 6–8, 50.5% Wk 9–12, 48.8% Wk 13+ (the 2015–2025 "Weeks 1–5 = 54%" did not replicate on 2000–2014).
- Oct 25 2026 results, 2008–2025 at 53%+: sides lean 444-426 (51.0%, 9/18 seasons) — about break-even; totals lean (`wind`, `under_start`, O/U form, `late_season` Wk 10–14, `primetime` SNF/MNF) 930-800 (53.8%, 11/18), 55%+ 399-311 (56.2%). Full models don't beat a coin flip. Lean inputs were chosen after seeing the data, so 2026 is the clean test.

### Learning Model (Model view — second opinion, not on the betting card)
- `scripts/build_learning_model.py [games.csv]` — 2026 layer on top of the history lean models: logistic with the history logit as offset, new inputs `sharp_home`/`sharp_over` (Action Network money% − bets%, last pregame read from `data/action_all_markets_{season}-*.csv`) and `move_home`/`move_total` (now vs first line in `engine_line_snapshots_{season}.csv`). Weights start at 0 with L2 = 150 pseudo-games, so a few weeks only nudge them; needs 2 graded weeks. Walk-forward within the season.
- Writes `data/backtests/history_model/learning_{season}.json` and `site/src/data/modelView.json` (upcoming week's side/total picks + confidence). Shown as "Model view" on the Edge Board (`ModelViewPanel.tsx`, leans ≥53%) and in the email (`build_model_view_section`).
- Runs: Wf 4.5 after the feed build (fresh splits each run); Wf 6 Grade on Tuesday refits `build_history_model.py` then the learning layer.
- Oct 21 2026 walk-forward (2026 Wk 1–6, 53%+): sides history-only 22-13 → with layer 23-12; totals 15-12 → 21-11. Tiny samples.

### Season Forecast (futures / win totals, research only)
- `scripts/season_forecast.py [--week N]` — three team-strength views at the cutoff week (WARPS preseason wins, ridge/MAP rating from this season's margins, ridge rating from this season's closing spreads) stacked by a logistic model trained on 2003..S-1 games after the cutoff (leave-one-season-out); then 20k simulations of standings, seeds, playoffs, Super Bowl, best record. Writes `data/backtests/season_forecast_{season}.json`.
- Nov 3 2026 (cutoff Week 8) held-out log loss: all three 0.634 (64.8% winners) vs margin-only 0.639, market-only 0.643, old K=8 Pythagorean blend 0.645, preseason only 0.672. With margin + market in, the preseason prior gets ~0 weight.
- `scripts/season_factor_test.py` (Nov 3 2026, 3,230 held-out games 2003–2025, cutoff Week 8): adding Pythagorean −0.0003 log loss, plain record +0.0005, rest −0.0001, QB-change flag −0.0006 (15/23 seasons), remaining SOS +0.0001, margins capped at ±10/14/17/21 (garbage-time proxy) +0.0018/+0.0006/+0.0001/−0.0002; all together −0.001. None kept: the ridge ratings already adjust for opponents and PF/PA, the simulation plays the real remaining schedule, and blowout margins carry information. QB flag misfires (SEA marked for Darnold returning) — injuries go through `warps_{season}_inseason_adjustments.csv` instead. Referee home-win / home-cover rates don't persist year to year (r = 0.02 / 0.02 over 349 crew-seasons) → noise.
- `scripts/pbp_edge_test.py PBP_DIR` (Nov 3 2026): play-level ratings from nflverse play-by-play (offense/defense EPA per pass and run, garbage time removed at 10–90% win prob, starting-QB EPA per dropback shrunk 100 dropbacks, pace), built only from earlier weeks, walk-forward 2012–2026 from Week 4, graded at the closing line: sides 50.0% (top 10% 49.2%), without QB 49.9%, totals 49.5% (top 10% 52.3%), 4/15 seasons above 52.4%. No edge at the close — public play-level data is already in the closing number. pbp files: `play_by_play_{season}.csv.gz` from the nflverse `pbp` release (~19 MB/season; pyarrow isn't installable here, use the csv.gz).
- Liju's bets: win totals BAL U11.5 $200/$129, NE O9.5 $250/$156, LAC U10.5 $450/$300, DAL U9.5 $500/$416, JAX O9.5 $500/$550, CIN U9.5 $650/$975, ARI O4.5 $700/$875, MIA O4.5 $750/$1,012; futures MIN NFC North −105 $150, MIN NFC +825 $60, MIN SB +2000 $25, JAX AFC +600 $40, JAX SB +1250 $25; MVP Mahomes +850 $20, Murray (MIN) +11000 $10.
- Contests after Week 8: KillerSports ATS 24-7-1, 24.5 pts, 32 of 100 picks used (#1: 45 pts, 73 used); Yahoo straight-up 70-50, 33rd (#1 81-39).

### Pick'em Contest (`scripts/build_top_picks.py` → `site/src/data/topPicks.json`, Contest tab)
- 100 picks/season, ≤10/week, ATS sides + O/U; lines posted Thursday by 2pm MT (4pm ET), picks lock at kickoff; win 1, push 0.5.
- Contest line = `data/contest/contest_lines_{season}_wk{week}.csv` (matchup_key, home_spread, total — entered from what Liju's contest shows; line_source "contest"), else the last snapshot before Thu 4:30pm ET. The contest's numbers can differ from ours (Wk 7 2026: contest CIN −1 vs our snapshot CIN +1.5), so ask for the posted lines each Thursday.

### Straight-up pool (Liju: ~56 players, weekly winner + season winner; was 59-47 vs leader 70-36 after Week 7)
- Vegas favorite SU 2026 Wk 1–7: 68-38; site recommendation (WARPS Wk 1–5, favorite Wk 6+) ≈ 67-39.
- `UpsetPicksPanel.tsx` (Pick'em Games tab): up to 6 closest open games (favorite ≤ 3.5) with the underdog, Model view agreement (≥52%), and the last game's total as tiebreaker. Simulated weekly-win odds for 56 players: all favorites 0.2%, 5–6 upsets ~4.5% (even share 1.8%).

### Line sanity (Action Network halves can carry an alternate line, e.g. NE@MIA '+16.5 | +6.5' when NE was −7)
- `nfl_common.home_spread_from_line(line, moneyline)` resolves halves that disagree by >1 pt (moneyline favorite, else the smaller number); `spread_line_for_side` keeps halves within a point as quoted (contract check). Site `lineForSide` mirrors this.
- **Scrape corrections, layered so the Odds API is the last resort** (`scripts/verify_scraped_lines.py WEEK`, Wf 2 and Wf 3 right after the Action Network scrape; rewrites the scrape CSV in place so engine/feed/contest/site/email all use the fixed number):
  1. the scrape itself: a bad spread is one real half + an alternate, so the real half is usually there;
  2. free references pick the half / confirm the line: nflverse consensus + Wf 11's morning `data/current_odds_api.json` (≤30h);
  3. our cached paid call `data/odds_api_cache.json` (≤3h, committed);
  4. a live Odds API call only for unsettled games, only the markets needed (1 credit each), not within 30 min of the last call or when quota < 60 (read from the `x-requests-remaining` header);
  5. else the free reference value. Moneylines have no free source, so a bad one needs 2–4.
  Checks: spread halves within 1 pt and ≤2.5 off reference; over/under match and ≤3 off; moneyline implied sum 0.97–1.15 with the same favorite as the spread. Log `data/line_corrections_{season}.csv`; latest `data/line_verify_latest.json`. Nov 1 2026: 5 of 13 spreads had a bad half, all fixed from the scrape with 0 credits.
- `canonical_team('LA')` returns LAR (nflverse writes the Rams as LA; the substring match used to read it as ATL).
- `scripts/check_lines.py` (Wf 4.5 after the feed build) compares each unplayed game's spread/total with nflverse's consensus; gaps > 2.5 (spread) / 3 (total) go to `site/src/data/lineCheck.json` along with the scrape corrections and data warnings (stale scrape > 8h, scheduled game missing or duplicated, total outside 30–65) → Edge Board `LineCheckBanner` + email "Line check" box. `detect_line_moves.py` drops moves nflverse doesn't confirm and skips started games.

### Stale week folders (data/week{N}/ is not split by season)
- `data/week{N}/` and `data/historical/week{N}_master.*` are reused every season, so they can hold last season's files or an old dry run (Week 10 2026: an Aug 12 dry-run `final.json` with another schedule's 14 games, plus a stray `WSH@NYG` row — 29 rows on the site; weeks 16–18 still hold 2025 masters).
- `build_week_master_table.py` (Nov 12 2026): ignores a stage whose `metadata.json` timestamp is > 10 days older than the newest stage or that `metadata.json` doesn't list, starts fresh when the existing master is from another season, and drops existing rows not on this week's ESPN schedule.
- Nov 12 2026 cleanup: `archive_season.py --season 2026 --apply` moved 2025's Weeks 11–18 and playoff folders/masters and the Aug 12 Week 10 dry-run `final*` files to `data/archive/before_2026/` (209 files).

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
