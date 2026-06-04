# NFL Matrix Site

Static Vite React app for the public NFL schedule matrix. The betting engine remains in the Python/GitHub Actions side of this repository and publishes `data/historical/matrix_engine_feed.json`.

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

Upload the contents of `site/dist/` to the public site path, for example `/nfl-matrix/`.

GitHub Actions also builds the site through `8 Matrix Site Build` whenever `site/` or
`data/historical/matrix_engine_feed.json` changes. Download the
`nfl-matrix-site-dist` artifact and upload those files to `/nfl-matrix/`.

## Embed Snippet

```html
<iframe
  src="/nfl-matrix/index.html"
  title="NFL Matrix"
  style="width:100%;height:900px;border:0;"
  loading="lazy"
></iframe>
```

## Data

The app fetches engine overlays from:

`https://raw.githubusercontent.com/whatsaliju/nfl-betting-automation/main/data/historical/matrix_engine_feed.json`

Set `VITE_ENGINE_FEED_URL` at build time to point to a different feed.
