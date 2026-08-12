"""
Football Zebras referee scraper.

Supports two page formats Football Zebras uses:

1. Multi-game assignment list (regular season + full preseason weeks):
   URL: /YYYY/MM/week-N-referee-assignments-YYYY/
   Parser: div.assignment_list > div.b_post blocks

2. Single-game crew article (HOF game, individual preseason games):
   URL: /YYYY/MM/{referee-name}-to-head-{game}-crew/  (unpredictable)
   Parser: HTML table row where position = "R", matchup from article text

For preseason, both formats may appear in the same week. The scraper tries
the predictable multi-game URL first, then falls back to archive discovery
for individual crew articles. nflverse schedules CSV is a final fallback.
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os

# ── Season-specific URL shapes ────────────────────────────────────────────────

# Playoff round → candidate URL slugs (tried in order)
PLAYOFF_SLUGS = {
    "WC":   ["wild-card", "wild-card-round", "wildcard"],
    "DIV":  ["divisional-playoff", "divisional-round", "divisional-playoffs"],
    "CONF": ["conference-championship", "championship", "afc-nfc-championship"],
    "SB":   ["super-bowl"],
}

# Month search order by phase
PRESEASON_MONTHS  = ["08", "07"]
REGULAR_MONTHS    = ["09", "10", "11", "12", "01"]
POSTSEASON_MONTHS = ["01", "02"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NFLEdge/1.0)"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_year(year=None):
    return year if year is not None else datetime.now().year


def _week_str(week) -> str:
    return str(week).upper()


def _is_preseason(week) -> bool:
    return _week_str(week).startswith("PRE")


def _preseason_num(week) -> int:
    return int(_week_str(week)[3:])


def _is_playoff(week) -> bool:
    return _week_str(week) in PLAYOFF_SLUGS


# ── Multi-game assignment-list parser (standard format) ───────────────────────

def _parse_assignment_list(html) -> list[dict]:
    """Parse a Football Zebras multi-game assignment page."""
    soup = BeautifulSoup(html, "html.parser")
    assignment_div = soup.find("div", class_="assignment_list")
    if not assignment_div:
        return []

    games = []
    for block in assignment_div.find_all("div", class_="b_post"):
        game_div = block.find("div", class_="b_post-game")
        ref_div  = block.find("div", class_="b_post-referee")
        time_div = block.find("div", class_="b_post-time")

        game    = game_div.text.strip() if game_div else None
        referee = ref_div.text.strip()  if ref_div  else None
        gametime = time_div.text.strip() if time_div else None

        if game and referee:
            games.append({"matchup": game, "referee": referee, "time": gametime})

    return games


# ── Single-game crew article parser ───────────────────────────────────────────

# Maps full team names to last word (city nickname) for matching
_TEAM_NICKNAMES = {
    "Cardinals", "Falcons", "Ravens", "Bills", "Panthers", "Bears",
    "Bengals", "Browns", "Cowboys", "Broncos", "Lions", "Packers",
    "Texans", "Colts", "Jaguars", "Chiefs", "Chargers", "Rams",
    "Raiders", "Dolphins", "Vikings", "Patriots", "Saints", "Giants",
    "Jets", "Eagles", "Steelers", "Seahawks", "49ers", "Buccaneers",
    "Titans", "Commanders",
}

# Full name → abbreviation for crew-article matchup normalization
_FULL_NAME_MAP = {
    "arizona cardinals": "ARI", "atlanta falcons": "ATL", "baltimore ravens": "BAL",
    "buffalo bills": "BUF", "carolina panthers": "CAR", "chicago bears": "CHI",
    "cincinnati bengals": "CIN", "cleveland browns": "CLE", "dallas cowboys": "DAL",
    "denver broncos": "DEN", "detroit lions": "DET", "green bay packers": "GB",
    "houston texans": "HOU", "indianapolis colts": "IND", "jacksonville jaguars": "JAX",
    "kansas city chiefs": "KC", "los angeles chargers": "LAC", "los angeles rams": "LAR",
    "las vegas raiders": "LV", "miami dolphins": "MIA", "minnesota vikings": "MIN",
    "new england patriots": "NE", "new orleans saints": "NO", "new york giants": "NYG",
    "new york jets": "NYJ", "philadelphia eagles": "PHI", "pittsburgh steelers": "PIT",
    "seattle seahawks": "SEA", "san francisco 49ers": "SF", "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN", "washington commanders": "WAS",
}


def _find_referee_in_table(soup) -> str | None:
    """Find referee (R position) from a crew-article HTML table."""
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if cells and cells[0] == "R" and len(cells) >= 3:
                return cells[2]
    return None


def _extract_matchup_from_text(text: str) -> str | None:
    """
    Pull team matchup from article body text.
    Handles: "between the X and Y", "X vs. Y", "X at Y"
    Returns "Away at Home" string or None.
    """
    # "between the Arizona Cardinals and (the) Carolina Panthers"
    m = re.search(
        r"between (?:the )?([A-Z][a-zA-Z\s]+?) and (?:the )?([A-Z][a-zA-Z\s]+?)(?:\.|,|\s+in\s|\s+at\s|\s+on\s)",
        text,
    )
    if m:
        return f"{m.group(1).strip()} at {m.group(2).strip()}"

    # "X vs. Y" or "X at Y" with known team nicknames
    for pattern in [r"([A-Z][a-zA-Z\s]+?) vs\.? ([A-Z][a-zA-Z\s]+?)\b",
                    r"([A-Z][a-zA-Z\s]+?) at the ([A-Z][a-zA-Z\s]+?)\b"]:
        m = re.search(pattern, text)
        if m:
            g1 = m.group(1).strip().split()[-1]  # last word = nickname
            g2 = m.group(2).strip().split()[-1]
            if g1 in _TEAM_NICKNAMES and g2 in _TEAM_NICKNAMES:
                return f"{m.group(1).strip()} at {m.group(2).strip()}"

    return None


def _parse_crew_article(html: bytes, url: str = "") -> list[dict]:
    """
    Parse a single-game Football Zebras crew article.
    Returns a list with one game dict, or empty list if not parseable.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try standard assignment list first (sometimes used even for single articles)
    games = _parse_assignment_list(html)
    if games:
        return games

    referee = _find_referee_in_table(soup)
    if not referee:
        return []

    text = soup.get_text(" ", strip=True)
    matchup = _extract_matchup_from_text(text)
    if not matchup:
        print(f"  ⚠️  Could not extract matchup from: {url}")
        matchup = "Unknown at Unknown"

    return [{"matchup": matchup, "referee": referee, "time": "", "source_url": url}]


# ── Archive discovery for preseason crew articles ──────────────────────────────

def _article_date_from_url(url: str) -> datetime | None:
    """Parse YYYY/MM from Football Zebras URL."""
    m = re.search(r"/(\d{4})/(\d{2})/", url)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    return None


def _discover_crew_articles(year: int, months: list[str], target_date: datetime,
                             window_days: int = 10) -> list[str]:
    """
    Scrape Football Zebras monthly archive pages and return URLs of crew articles
    published within `window_days` of `target_date`.
    """
    found = []
    cutoff_early = target_date - timedelta(days=window_days)
    cutoff_late  = target_date + timedelta(days=window_days)

    for month in months:
        archive_url = f"https://www.footballzebras.com/{year}/{month}/"
        try:
            r = requests.get(archive_url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Archive fetch error: {e}")
            continue

        soup = BeautifulSoup(r.content, "html.parser")

        # Collect article links — Football Zebras archive lists articles
        # Each article <h2> or <article> contains the permalink
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not (f"footballzebras.com/{year}" in href):
                continue

            # Only articles about game crews / referee assignments
            slug = href.rstrip("/").split("/")[-1].lower()
            if not any(kw in slug for kw in ["crew", "assignment", "official"]):
                continue

            # Date filter via URL
            pub_date = _article_date_from_url(href)
            if pub_date:
                # Use month-level precision: if month is within range, include
                if not (cutoff_early <= pub_date <= cutoff_late + timedelta(days=31)):
                    continue

            if href not in found:
                found.append(href)

    return found


def _scrape_preseason_via_archive(week, year: int) -> pd.DataFrame:
    """
    Discover and parse individual crew articles from the Football Zebras archive.
    Used when the predictable multi-game assignment URL doesn't exist.
    """
    pre_num = _preseason_num(week)
    # Estimate game dates: PRE1=Aug 13, PRE2=Aug 20, PRE3=Aug 27 (approximate)
    # Use Aug 7 as base + (pre_num - 1) * 7 days
    base = datetime(year, 8, 7)
    target_date = base + timedelta(weeks=pre_num - 1)

    print(f"  Discovering crew articles around {target_date.strftime('%b %d')}...")
    urls = _discover_crew_articles(year, PRESEASON_MONTHS, target_date, window_days=8)

    if not urls:
        print("  ⚠️  No crew articles found in archive")
        return pd.DataFrame()

    print(f"  Found {len(urls)} candidate article(s): {urls}")

    all_games = []
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            games = _parse_crew_article(r.content, url)
            all_games.extend(games)
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Article fetch error ({url}): {e}")

    if not all_games:
        return pd.DataFrame()

    df = pd.DataFrame(all_games)
    df["week"] = week
    print(f"  ✅ Archive discovery: {len(df)} game(s) found")
    return df


# ── Primary Football Zebras scraper ───────────────────────────────────────────

def _build_url_candidates(week, year: int) -> list[str]:
    """Build ordered list of candidate Football Zebras URLs (predictable format)."""
    wk = _week_str(week)

    if _is_preseason(week):
        n = _preseason_num(week)
        return [
            f"https://www.footballzebras.com/{year}/{m}/preseason-week-{n}-referee-assignments-{year}/"
            for m in PRESEASON_MONTHS
        ]

    if _is_playoff(week):
        candidates = []
        for slug in PLAYOFF_SLUGS[wk]:
            for m in POSTSEASON_MONTHS:
                candidates.append(
                    f"https://www.footballzebras.com/{year}/{m}/{slug}-referee-assignments-{year}/"
                )
        return candidates

    # Regular season
    return [
        f"https://www.footballzebras.com/{year}/{m}/week-{week}-referee-assignments-{year}/"
        for m in REGULAR_MONTHS
    ]


def scrape_week_referees(week, year=None) -> pd.DataFrame:
    """
    Scrape referee assignments from Football Zebras.
    week: int (1-18) or label (PRE1/PRE2/PRE3/WC/DIV/CONF/SB)
    year: NFL season year; defaults to current calendar year.
    """
    year = _get_year(year)
    print(f"Fetching week {week} ({year}) referee assignments from Football Zebras...")

    # ── Step 1: Try predictable multi-game assignment URLs ────────────────────
    for url in _build_url_candidates(week, year):
        print(f"  Trying: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            games = _parse_assignment_list(r.content)
            if games:
                print(f"  ✅ Multi-game page: {len(games)} game(s) at {url}")
                df = pd.DataFrame(games)
                df["week"] = week
                return df
            print("  ⚠️  Page found but no assignment_list — continuing")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ {e}")

    # ── Step 2: For preseason, try archive discovery (individual crew articles) ─
    if _is_preseason(week):
        print("  Falling back to archive discovery for individual crew articles...")
        df = _scrape_preseason_via_archive(week, year)
        if not df.empty:
            return df

    print(f"⚠️  No Football Zebras data found for week {week} {year}")
    return pd.DataFrame()


# ── nflverse fallback ─────────────────────────────────────────────────────────

_NFLVERSE_SCHEDULES = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

_POST_WEEK_MAP = {"WC": 1, "DIV": 2, "CONF": 3, "SB": 5}


def scrape_nflverse_referees(week, year=None) -> pd.DataFrame:
    """
    Fallback: pull referee column from nflverse schedules CSV.
    Populated by NFL a few days before game week (not guaranteed for future games).
    """
    year = _get_year(year)
    wk = _week_str(week)
    print(f"Trying nflverse schedules fallback for week {week} {year}...")

    try:
        df = pd.read_csv(_NFLVERSE_SCHEDULES)
    except Exception as e:
        print(f"  ❌ Could not fetch nflverse schedules: {e}")
        return pd.DataFrame()

    if _is_preseason(week):
        mask = (df["season"] == year) & (df["game_type"] == "PRE") & (df["week"] == _preseason_num(week))
    elif _is_playoff(week):
        pw = _POST_WEEK_MAP.get(wk, 0)
        mask = (df["season"] == year) & (df["game_type"] == "POST") & (df["week"] == pw)
    else:
        mask = (df["season"] == year) & (df["game_type"] == "REG") & (df["week"] == int(week))

    subset = df[mask].copy()
    if subset.empty:
        print(f"  ⚠️  No nflverse rows for week {week} {year}")
        return pd.DataFrame()

    ref_col = "referee" if "referee" in subset.columns else None
    if not ref_col or subset[ref_col].isna().all():
        print(f"  ⚠️  nflverse schedules have no referee data for week {week} {year}")
        return pd.DataFrame()

    games = []
    for _, row in subset.iterrows():
        ref = row.get(ref_col)
        if pd.isna(ref) or not str(ref).strip():
            continue
        matchup = f"{row.get('away_team', '?')} at {row.get('home_team', '?')}"
        games.append({"matchup": matchup, "referee": str(ref).strip(),
                      "time": str(row.get("gametime", "")), "week": week})

    if not games:
        print("  ⚠️  nflverse rows exist but no referee names filled in yet")
        return pd.DataFrame()

    print(f"  ✅ nflverse fallback: {len(games)} game(s) with referee data")
    return pd.DataFrame(games)


# ── Matchup parser ────────────────────────────────────────────────────────────

def parse_matchup(matchup: str):
    """Parse 'Away at Home' / 'Away @ Home' / 'Away vs. Home' → (away, home)."""
    for sep in [" at ", " @ "]:
        if sep in matchup:
            parts = matchup.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    for sep in [" vs. ", " vs "]:
        if sep in matchup:
            parts = matchup.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return None, None


# ── Public API ────────────────────────────────────────────────────────────────

def save_referees(week, year=None, output_file=None) -> pd.DataFrame | None:
    """
    Scrape and save referee assignments to CSV.
    Tries Football Zebras (multi-game → archive discovery), then nflverse.
    """
    year = _get_year(year)

    df = scrape_week_referees(week, year)
    if df.empty:
        df = scrape_nflverse_referees(week, year)

    if df.empty:
        print("❌ No referee data found from any source")
        return None

    df[["away_team", "home_team"]] = df["matchup"].apply(
        lambda x: pd.Series(parse_matchup(x))
    )

    if output_file is None:
        os.makedirs(f"data/week{week}", exist_ok=True)
        output_file = f"data/week{week}/week{week}_referees.csv"

    df.to_csv(output_file, index=False)
    print(f"\n📁 Saved {len(df)} game(s) to {output_file}")
    print("\n" + "=" * 60)
    print(f"WEEK {week} REFEREE ASSIGNMENTS")
    print("=" * 60)
    for _, row in df.iterrows():
        print(f"  {row['matchup']:<40} → {row['referee']}")
    print("=" * 60)

    return df


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    week_arg = sys.argv[1] if len(sys.argv) > 1 else "PRE1"
    year_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None
    week = int(week_arg) if week_arg.isdigit() else week_arg
    df = save_referees(week, year=year_arg)
    if df is not None:
        print(f"\n✅ SUCCESS — {len(df)} game(s) saved")
    else:
        print("\n⚠️  No data saved (assignments not posted yet)")
