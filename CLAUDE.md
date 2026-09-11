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
- Hero: "Stop guessing. Start picking."
- 6 tool cards mapping user goals to app features:
  1. Weekly Picks (`matrix.html#command`) — "What should I bet this week?"
  2. Pick'em (`matrix.html#pickem`) — "Who wins straight-up for my pool?"
  3. Survivor Pool (`matrix.html#survivor`) — "Which team do I pick for Survivor?"
  4. Edge Board (`matrix.html#edges`) — "Which games have real value on the spread?"
  5. Schedule & Scout (`matrix.html#scout`) — "What does my team's schedule look like?"
  6. Track Record & Model (`warps.html`) — "Can I trust this model?"

## Board App (`matrix.html`)
- Pick'em completed-game detection: `isCompleted = g.away_score != null && g.home_score != null`
- Completed games show Final badge + score; betting sections hidden for completed games
- Tiebreaker table excludes completed games
- CSS classes for completed games: `.pickem-final`, `.pk-final-badge`, `.pk-score`, `.pk-winner`, `.pk-loser`
- WSH/WAS normalization: `normalizeTla()` maps WSH→WAS
- UTC→ET: `utcToEt()` applies -4h EDT offset for game grouping

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

## Active PRs (as of 2026-09-11)
- **PR #157**: Personal hub page (`liju.html`) for `lijuvarughese.com` — CI green, awaiting user merge approval
