#!/usr/bin/env python3
"""
Scrape survivor pool consensus data from survivorgrid.com/picks
Outputs site/src/data/survivorConsensus2026.json

Data fields per team per week:
  w  - win probability (W%)
  p  - pick percentage (P%)
  ev - expected value (EV)
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PICKS_URL = "https://www.survivorgrid.com/picks"
GRID_URL = "https://www.survivorgrid.com/"
OUT_PATH = Path(__file__).parent.parent / "site" / "src" / "data" / "survivorConsensus2026.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; nflsignal-bot/1.0; +https://nflsignal.com)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# Map SurvivorGrid team names/abbreviations to our 3-letter TLAs
TEAM_MAP = {
    "Arizona Cardinals": "ARI", "Arizona": "ARI", "ARI": "ARI",
    "Atlanta Falcons": "ATL", "Atlanta": "ATL", "ATL": "ATL",
    "Baltimore Ravens": "BAL", "Baltimore": "BAL", "BAL": "BAL",
    "Buffalo Bills": "BUF", "Buffalo": "BUF", "BUF": "BUF",
    "Carolina Panthers": "CAR", "Carolina": "CAR", "CAR": "CAR",
    "Chicago Bears": "CHI", "Chicago": "CHI", "CHI": "CHI",
    "Cincinnati Bengals": "CIN", "Cincinnati": "CIN", "CIN": "CIN",
    "Cleveland Browns": "CLE", "Cleveland": "CLE", "CLE": "CLE",
    "Dallas Cowboys": "DAL", "Dallas": "DAL", "DAL": "DAL",
    "Denver Broncos": "DEN", "Denver": "DEN", "DEN": "DEN",
    "Detroit Lions": "DET", "Detroit": "DET", "DET": "DET",
    "Green Bay Packers": "GB", "Green Bay": "GB", "GB": "GB",
    "Houston Texans": "HOU", "Houston": "HOU", "HOU": "HOU",
    "Indianapolis Colts": "IND", "Indianapolis": "IND", "IND": "IND",
    "Jacksonville Jaguars": "JAX", "Jacksonville": "JAX", "JAX": "JAX",
    "Kansas City Chiefs": "KC", "Kansas City": "KC", "KC": "KC",
    "Las Vegas Raiders": "LV", "Las Vegas": "LV", "LV": "LV", "OAK": "LV", "Raiders": "LV",
    "Los Angeles Chargers": "LAC", "LA Chargers": "LAC", "LAC": "LAC",
    "Los Angeles Rams": "LAR", "LA Rams": "LAR", "LAR": "LAR", "Rams": "LAR",
    "Miami Dolphins": "MIA", "Miami": "MIA", "MIA": "MIA",
    "Minnesota Vikings": "MIN", "Minnesota": "MIN", "MIN": "MIN",
    "New England Patriots": "NE", "New England": "NE", "NE": "NE",
    "New Orleans Saints": "NO", "New Orleans": "NO", "NO": "NO",
    "New York Giants": "NYG", "NY Giants": "NYG", "NYG": "NYG",
    "New York Jets": "NYJ", "NY Jets": "NYJ", "NYJ": "NYJ",
    "Philadelphia Eagles": "PHI", "Philadelphia": "PHI", "PHI": "PHI",
    "Pittsburgh Steelers": "PIT", "Pittsburgh": "PIT", "PIT": "PIT",
    "San Francisco 49ers": "SF", "San Francisco": "SF", "SF": "SF",
    "Seattle Seahawks": "SEA", "Seattle": "SEA", "SEA": "SEA",
    "Tampa Bay Buccaneers": "TB", "Tampa Bay": "TB", "TB": "TB",
    "Tennessee Titans": "TEN", "Tennessee": "TEN", "TEN": "TEN",
    "Washington Commanders": "WAS", "Washington": "WAS", "WAS": "WAS",
}


def pct_to_float(val: str) -> float | None:
    """'72%' -> 0.72, '0.72' -> 0.72, '' -> None"""
    if not val:
        return None
    val = val.strip().replace("%", "").replace(",", "")
    try:
        f = float(val)
        return round(f / 100, 4) if f > 1 else round(f, 4)
    except ValueError:
        return None


def try_json_in_scripts(soup: BeautifulSoup) -> dict | None:
    """Look for embedded JSON data in <script> tags."""
    for script in soup.find_all("script"):
        text = script.string or ""
        # Look for patterns like window.__DATA__ = {...} or var data = {...}
        for pattern in [
            r"window\.__(?:DATA|INITIAL_STATE|APP_STATE|NEXT_DATA|NUXT)\s*=\s*(\{.+?\});",
            r"var\s+(?:data|picks|grid|teams)\s*=\s*(\[.+?\]);",
            r'"weeks"\s*:\s*(\{.+?\})',
        ]:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
    return None


def normalize_team(raw: str) -> str | None:
    raw = raw.strip()
    return TEAM_MAP.get(raw) or TEAM_MAP.get(raw.upper()) or None


def parse_picks_page(html: str) -> dict:
    """
    Parse survivorgrid.com/picks — expects a table with columns like
    Team | W% | P% | EV (for the current week).
    Returns {week: {team: {w, p, ev}}}
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try embedded JSON first
    json_data = try_json_in_scripts(soup)
    if json_data:
        print("[scraper] Found embedded JSON in script tag", file=sys.stderr)
        return _extract_from_json(json_data)

    # Debug: print all table headers found
    tables = soup.find_all("table")
    print(f"[scraper] Found {len(tables)} tables on /picks", file=sys.stderr)
    for i, t in enumerate(tables):
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        print(f"  Table {i}: headers={headers[:8]}", file=sys.stderr)

    weeks: dict = {}

    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(h in headers for h in ["team", "w%", "p%", "ev", "win", "pick"]):
            continue

        # Detect column positions
        col = {}
        for h_list in [headers]:
            for idx, h in enumerate(h_list):
                if "team" in h:
                    col.setdefault("team", idx)
                elif "w" in h and "%" in h:
                    col.setdefault("w", idx)
                elif "p" in h and "%" in h:
                    col.setdefault("p", idx)
                elif "ev" in h:
                    col.setdefault("ev", idx)

        print(f"[scraper] Column map: {col}", file=sys.stderr)

        # Try to detect which week this table covers
        week_num = 1
        heading = table.find_previous(["h1", "h2", "h3"])
        if heading:
            m = re.search(r"week\s*(\d+)", heading.get_text(), re.I)
            if m:
                week_num = int(m.group(1))

        week_data: dict = {}
        for row in table.find_all("tr")[1:]:  # skip header
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if not cells:
                continue
            team_raw = cells[col.get("team", 0)] if col.get("team", 0) < len(cells) else ""
            team = normalize_team(team_raw)
            if not team:
                print(f"[scraper] Unrecognized team: {team_raw!r}", file=sys.stderr)
                continue
            week_data[team] = {
                "w": pct_to_float(cells[col["w"]]) if "w" in col and col["w"] < len(cells) else None,
                "p": pct_to_float(cells[col["p"]]) if "p" in col and col["p"] < len(cells) else None,
                "ev": pct_to_float(cells[col["ev"]]) if "ev" in col and col["ev"] < len(cells) else None,
            }
        if week_data:
            weeks[str(week_num)] = week_data

    if not weeks:
        # Dump a snippet of the raw HTML so we can debug the structure
        print("[scraper] WARNING: No data parsed. First 3000 chars of HTML:", file=sys.stderr)
        print(html[:3000], file=sys.stderr)

    return weeks


def _extract_from_json(data: dict) -> dict:
    """Best-effort extraction from an unknown JSON shape."""
    weeks = {}
    # Try common shapes
    if isinstance(data, dict):
        for key in ["weeks", "picks", "grid", "data"]:
            if key in data and isinstance(data[key], dict):
                return data[key]
    return weeks


def main() -> None:
    print(f"[scraper] Fetching {PICKS_URL}", file=sys.stderr)
    try:
        resp = requests.get(PICKS_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[scraper] ERROR fetching /picks: {e}", file=sys.stderr)
        sys.exit(1)

    weeks = parse_picks_page(resp.text)

    # Load existing data to merge (preserves previous weeks)
    existing: dict = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text())
        except Exception:
            pass
    existing_weeks: dict = existing.get("weeks", {})

    # Merge new weeks in
    for wk, wk_data in weeks.items():
        existing_weeks[wk] = wk_data

    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "survivorgrid.com",
        "weeks": existing_weeks,
    }

    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"[scraper] Wrote {OUT_PATH} — {len(existing_weeks)} week(s)", file=sys.stderr)
    print(json.dumps(output, indent=2)[:500])


if __name__ == "__main__":
    main()
