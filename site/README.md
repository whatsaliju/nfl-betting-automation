# NFL Edge Hub

Static Vite React app for the experimental NFL lab:

- Home: lab links and orientation
- Matrix: schedule/team context
- Edges: weekly play/watch/pass explanations
- Expect: Pythagorean and Vegas win-total expectations
- Research: factor leaderboard, promotion rules, overlay tests, source reliability
- Week/Compare/Results: supporting views

The betting engine remains in the Python/GitHub Actions side of this repository and publishes `data/historical/matrix_engine_feed.json`.

## Local Development

```bash
cd site
npm install
npm run dev
```

## Build

```bash
cd site
npm run build
```

Recommended public path:

`https://lijuvarughese.com/labs/nfl-edge/`

Upload the contents of `site/dist/` to:

`public_html/labs/nfl-edge/`

## Labs Links

The Home tab links to the current Val Cap Quant dashboards:

- `https://lijuvarughese.com/ytts/research_dashboard_app.html`
- `https://lijuvarughese.com/ytts/longhold_dashboard.html`

## GitHub Actions

`8 NFL Edge Hub Site Build` builds the static app and uploads the `nfl-edge-hub-dist` artifact.

`10 Deploy NFL Edge Hub to Bluehost` builds and deploys to Bluehost through SSH. It expects these repository secrets:

- `BLUEHOST_HOST`
- `BLUEHOST_PORT`, usually `22`
- `BLUEHOST_USER`
- `BLUEHOST_SSH_KEY`
- `BLUEHOST_TARGET_DIR`, recommended `/home/YOURUSER/public_html/labs/nfl-edge`

Do not store the cPanel master password in GitHub. Use a limited SSH key or deploy user.

## Data

The app fetches engine overlays from:

`https://raw.githubusercontent.com/whatsaliju/nfl-betting-automation/main/data/historical/matrix_engine_feed.json`

Set `VITE_ENGINE_FEED_URL` at build time to point to a different feed.

## Embed Snippet

```html
<iframe
  src="/labs/nfl-edge/index.html"
  title="NFL Edge Hub"
  style="width:100%;height:900px;border:0;"
  loading="lazy"
></iframe>
```
