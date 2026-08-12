import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

# Slug patterns Football Zebras uses for each round type
# Each entry is a list of candidate slugs (tried in order)
PLAYOFF_SLUGS = {
    "WC":   ["wild-card", "wild-card-round", "wildcard"],
    "DIV":  ["divisional-playoff", "divisional-round", "divisional-playoffs"],
    "CONF": ["conference-championship", "championship", "afc-nfc-championship"],
    "SB":   ["super-bowl", "super-bowl-lviii", "super-bowl-lix", "super-bowl-lx"],
}

# Month search order per week type
PRESEASON_MONTHS  = ["08", "07"]
REGULAR_MONTHS    = ["09", "10", "11", "12", "01"]
POSTSEASON_MONTHS = ["01", "02"]


def _get_year(year=None):
    return year if year is not None else datetime.now().year


def _build_url_patterns(week, year):
    """Return ordered list of candidate Football Zebras URLs for the given week."""
    y = _get_year(year)

    week_str = str(week).upper()

    # ── Preseason ──────────────────────────────────────────────────────────────
    if week_str.startswith("PRE"):
        n = week_str[3:]  # "1", "2", "3", "4"
        return [
            f"https://www.footballzebras.com/{y}/{m}/preseason-week-{n}-referee-assignments-{y}/"
            for m in PRESEASON_MONTHS
        ]

    # ── Playoffs ────────────────────────────────────────────────────────────────
    if week_str in PLAYOFF_SLUGS:
        patterns = []
        for slug in PLAYOFF_SLUGS[week_str]:
            for m in POSTSEASON_MONTHS:
                patterns.append(
                    f"https://www.footballzebras.com/{y}/{m}/{slug}-referee-assignments-{y}/"
                )
        return patterns

    # ── Regular season ──────────────────────────────────────────────────────────
    return [
        f"https://www.footballzebras.com/{y}/{m}/week-{week}-referee-assignments-{y}/"
        for m in REGULAR_MONTHS
    ]


def _parse_page(html):
    """Extract games from a Football Zebras assignment page. Returns list of dicts."""
    soup = BeautifulSoup(html, "html.parser")
    assignment_div = soup.find("div", class_="assignment_list")
    if not assignment_div:
        return []

    games = []
    for block in assignment_div.find_all("div", class_="b_post"):
        game_div = block.find("div", class_="b_post-game")
        ref_div  = block.find("div", class_="b_post-referee")
        time_div = block.find("div", class_="b_post-time")

        game     = game_div.text.strip() if game_div else None
        referee  = ref_div.text.strip()  if ref_div  else None
        gametime = time_div.text.strip() if time_div else None

        if game and referee:
            games.append({"matchup": game, "referee": referee, "time": gametime})

    return games


def scrape_week_referees(week, year=None):
    """
    Scrape referee assignments from Football Zebras.
    week: int (1-18) or string label (PRE1/PRE2/PRE3/WC/DIV/CONF/SB)
    year: NFL season year; defaults to current calendar year.
    """
    year = _get_year(year)
    urls = _build_url_patterns(week, year)

    print(f"Fetching Week {week} ({year}) referee assignments from Football Zebras...")

    for url in urls:
        try:
            print(f"  Trying: {url}")
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200:
                continue
            games = _parse_page(r.content)
            if games:
                print(f"  ✅ Found {len(games)} games at {url}")
                df = pd.DataFrame(games)
                df["week"] = week
                return df
            else:
                print(f"  ⚠️  Page found but no assignment_list div — skipping")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Request error: {e}")
            continue

    print(f"⚠️  No Football Zebras data found for week {week} {year}")
    return pd.DataFrame()


def scrape_nflverse_referees(week, year=None):
    """
    Fallback: pull referee column from nflverse schedules CSV.
    Only populated after assignments are announced by NFL (typically Wed-Thu before game week).
    week: int or PRE/playoff string
    """
    year = _get_year(year)
    url = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
    print(f"Trying nflverse schedules fallback for week {week} {year}...")

    try:
        df = pd.read_csv(url)
    except Exception as e:
        print(f"  ❌ Could not fetch nflverse schedules: {e}")
        return pd.DataFrame()

    week_str = str(week).upper()

    # Map our week labels to nflverse game_type + week columns
    if week_str.startswith("PRE"):
        pre_num = int(week_str[3:])
        mask = (df["season"] == year) & (df["game_type"] == "PRE") & (df["week"] == pre_num)
    elif week_str in ("WC", "DIV", "CONF", "SB"):
        post_map = {"WC": 1, "DIV": 2, "CONF": 3, "SB": 5}
        mask = (df["season"] == year) & (df["game_type"] == "POST") & (df["week"] == post_map.get(week_str, 0))
    else:
        mask = (df["season"] == year) & (df["game_type"] == "REG") & (df["week"] == int(week))

    subset = df[mask].copy()
    if subset.empty:
        print(f"  ⚠️  No nflverse schedule rows for week {week} {year}")
        return pd.DataFrame()

    # nflverse uses home_team/away_team abbreviations
    ref_col = "referee" if "referee" in subset.columns else None
    if ref_col is None or subset[ref_col].isna().all():
        print(f"  ⚠️  nflverse schedules have no referee data for week {week} {year}")
        return pd.DataFrame()

    games = []
    for _, row in subset.iterrows():
        ref = row.get(ref_col)
        if pd.isna(ref) or not str(ref).strip():
            continue
        matchup = f"{row.get('away_team', '?')} at {row.get('home_team', '?')}"
        games.append({
            "matchup": matchup,
            "referee": str(ref).strip(),
            "time": str(row.get("gametime", "")),
            "week": week,
        })

    if not games:
        print(f"  ⚠️  nflverse had schedule rows but no referee names filled in yet")
        return pd.DataFrame()

    print(f"  ✅ nflverse fallback: {len(games)} games with referee data")
    return pd.DataFrame(games)


def parse_matchup(matchup):
    """Parse 'Away at Home' or 'Away @ Home' into (away, home)."""
    for sep in [" at ", " @ "]:
        if sep in matchup:
            parts = matchup.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    # Neutral site
    for sep in [" vs. ", " vs "]:
        if sep in matchup:
            parts = matchup.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return None, None


def save_referees(week, year=None, output_file=None):
    """
    Scrape and save referee assignments to CSV.
    Tries Football Zebras first, then nflverse schedules as fallback.
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
    print(f"📁 Saved to {output_file}")

    print("\n" + "=" * 60)
    print(f"WEEK {week} REFEREE ASSIGNMENTS")
    print("=" * 60)
    for _, row in df.iterrows():
        print(f"{row['matchup']:<35} → {row['referee']}")
    print("=" * 60)

    return df


if __name__ == "__main__":
    import sys
    week_arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    year_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None
    week = int(week_arg) if week_arg.isdigit() else week_arg
    df = save_referees(week, year=year_arg)
    if df is not None:
        print(f"\n✅ SUCCESS — {len(df)} games saved")
