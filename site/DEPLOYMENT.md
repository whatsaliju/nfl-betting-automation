# Bluehost Deployment

Recommended public structure:

- `https://lijuvarughese.com/labs/` for the experimental lab area
- `https://lijuvarughese.com/labs/nfl-edge/` for this app
- Existing Val Cap Quant dashboards remain linked from:
  - `https://lijuvarughese.com/ytts/research_dashboard_app.html`
  - `https://lijuvarughese.com/ytts/longhold_dashboard.html`

## 1. Create Target Folder

In Bluehost/cPanel File Manager or SSH:

```bash
mkdir -p ~/public_html/labs/nfl-edge
```

## 2. Create Deploy SSH Key

Preferred: create a dedicated SSH key for this repository, not your primary cPanel password.

Add the public key to Bluehost/cPanel SSH authorized keys.

Add the private key to GitHub repository secrets as:

`BLUEHOST_SSH_KEY`

## 3. Add GitHub Secrets

Repository settings -> Secrets and variables -> Actions -> New repository secret:

- `BLUEHOST_HOST`: your Bluehost SSH host
- `BLUEHOST_PORT`: `22`
- `BLUEHOST_USER`: your deploy user
- `BLUEHOST_SSH_KEY`: private key contents
- `BLUEHOST_TARGET_DIR`: `/home/YOURUSER/public_html/labs/nfl-edge`

## 4. Deploy

Run GitHub Actions workflow:

`10 Deploy NFL Edge Hub to Bluehost`

Optional inputs:

- `engine_feed_url`: override public GitHub raw feed
- `target_dir`: override the target deploy folder

## 5. Verify

Open:

`https://lijuvarughese.com/labs/nfl-edge/`

Expected first screen:

- Home tab with NFL Edge Hub cards
- Links to Val Cap Quant screener and longhold dashboard
- Matrix/Edges/Expect/Research/Week/Compare/Results tabs

## Notes

The app is static. No backend is deployed to Bluehost.

The engine continues to publish JSON artifacts through this repository. The static app fetches the public engine feed from GitHub raw unless `VITE_ENGINE_FEED_URL` is overridden at build time.
