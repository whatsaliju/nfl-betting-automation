"""Shared NFL team and betting-line helpers.

Keep these small and dependency-free so analyzer, replay, and grading scripts
use the same parsing rules.
"""

import re
from datetime import date, datetime, time, timedelta, timezone


PRESEASON_GAME_TYPES = {"PRE"}
REGULAR_SEASON_GAME_TYPES = {"REG"}
POSTSEASON_GAME_TYPES = {"WC", "DIV", "CON", "SB"}
ALL_GAME_TYPES = PRESEASON_GAME_TYPES | REGULAR_SEASON_GAME_TYPES | POSTSEASON_GAME_TYPES

TEAM_MAP = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders"
}
FULL_NAME_TO_TLA = {full.lower(): tla for tla, full in TEAM_MAP.items()}


def get_current_season(fallback=2026):
    """Return the active NFL season year from data/current_week.json.

    Falls back to `fallback` if the file is absent or unreadable.  Any script
    that previously hardcoded a season year should call this instead.
    """
    import json as _json
    for path in ("data/current_week.json", "../data/current_week.json"):
        try:
            with open(path) as _f:
                val = _json.load(_f).get("season")
            if val:
                return int(val)
        except Exception:
            pass
    return fallback


def canonical_team(team_raw):
    if not team_raw:
        return ""

    team = str(team_raw).strip().lower()
    team = re.sub(r"[*\d/]+$", "", team)

    if team.upper() in TEAM_MAP:
        return team.upper()
    if team in FULL_NAME_TO_TLA:
        return FULL_NAME_TO_TLA[team]

    for tla, full_name in TEAM_MAP.items():
        lowered = full_name.lower()
        if team == lowered or team in lowered or lowered in team:
            return tla

    return team.upper()


def normalize_matchup_key(matchup):
    if not matchup:
        return ""

    text = str(matchup).lower().replace(" vs. ", "@").replace(" vs ", "@").replace(" at ", "@")
    parts = text.split("@")
    if len(parts) != 2:
        return text.replace(" ", "")

    return f"{canonical_team(parts[0])}@{canonical_team(parts[1])}"


def split_matchup(matchup):
    text = str(matchup)
    for sep in (" @ ", " at ", " vs. ", " vs "):
        if sep in text:
            away, home = text.split(sep, 1)
            return away.strip(), home.strip()
    raise ValueError(f"Could not split matchup: {matchup}")


def first_number(text):
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(text))
    return float(match.group(0)) if match else None


def _line_parts(line_text):
    return [part.strip() for part in str(line_text or "").split("|") if part.strip()]


def spread_line_for_side(line_text, side):
    side = str(side or "").upper()
    parts = _line_parts(line_text)
    if len(parts) < 2:
        return first_number(line_text)
    return first_number(parts[0] if side == "AWAY" else parts[1])


def total_line_for_side(line_text, side):
    side = str(side or "").upper()
    parts = _line_parts(line_text)
    if len(parts) < 2:
        return first_number(line_text)
    return first_number(parts[0] if side == "OVER" else parts[1])


def home_spread_from_line(line_text):
    """Extract the home team's spread from an away|home market string."""
    if not line_text:
        return None

    text = str(line_text).strip()
    if "pick" in text.lower() or text.upper() == "PK":
        return 0.0

    numbers = []
    for part in _line_parts(text):
        match = re.search(r"([+-]\d+\.?\d*)", part)
        if match:
            numbers.append(float(match.group(1)))

    if len(numbers) >= 2:
        return numbers[1]
    if len(numbers) == 1:
        return -numbers[0]
    return None


def normalize_season_type(season_type=None, week=None):
    """Return PRE, REG, or POST, inferring playoffs from nflverse week numbers."""
    value = str(season_type or "").strip().upper()
    aliases = {
        "PRESEASON": "PRE",
        "PRE_SEASON": "PRE",
        "REGULAR": "REG",
        "REGULAR_SEASON": "REG",
        "POSTSEASON": "POST",
        "PLAYOFF": "POST",
        "PLAYOFFS": "POST",
    }
    if value in aliases:
        return aliases[value]
    if value in {"PRE", "REG", "POST"}:
        return value
    if value in POSTSEASON_GAME_TYPES:
        return "POST"
    if week is not None:
        try:
            if int(week) > 18:
                return "POST"
        except (ValueError, TypeError):
            pass
    return "REG"


def nflverse_game_types(season_type=None, week=None):
    normalized = normalize_season_type(season_type, week)
    if normalized == "PRE":
        return ["PRE"]
    return sorted(POSTSEASON_GAME_TYPES) if normalized == "POST" else ["REG"]


def espn_season_type(season_type=None, week=None):
    normalized = normalize_season_type(season_type, week)
    if normalized == "PRE":
        return 1
    return 3 if normalized == "POST" else 2


def espn_week(season_type=None, week=None):
    """Translate nflverse season week into ESPN scoreboard week."""
    if week is None:
        return None
    try:
        week = int(week)
    except (ValueError, TypeError):
        return None
    if normalize_season_type(season_type, week) in {"PRE", "REG"}:
        return week
    if week == 22:
        return 5
    return max(1, week - 18)


_WEEK1_SUNDAY = {
    2025: date(2025, 9, 7),   # Season opened Fri 2025-09-05; Week 1 Sunday two days later
    2026: date(2026, 9, 6),   # Season opens Thu 2026-09-03; Week 1 Sunday three days later
}

def regular_season_sunday(season, week):
    anchor = _WEEK1_SUNDAY.get(season)
    if anchor is None:
        raise ValueError(f"regular_season_sunday: no Week 1 anchor for season {season}. Add it to _WEEK1_SUNDAY.")
    return anchor + timedelta(days=(week - 1) * 7)


def _week_num(week) -> int:
    """Coerce any week label to a sortable integer for calendar math."""
    playoff_map = {"WC": 19, "DIV": 20, "CON": 21, "CONF": 21, "SB": 22}
    w = str(week).strip().upper()
    if w in playoff_map:
        return playoff_map[w]
    if w.startswith("PRE"):
        try:
            return int(w[3:]) if w[3:] else 1
        except ValueError:
            return 1
    try:
        return int(w)
    except (ValueError, TypeError):
        return 0


def week_anchor_date(season, week, season_type=None):
    season_type = normalize_season_type(season_type, week)
    week_num = _week_num(week)
    if season_type == "PRE":
        # Approximate first preseason Sunday. Exact dry-run dates should come
        # from schedule data once preseason markets are available.
        return date(season, 8, 3) + timedelta(days=(week_num - 1) * 7)
    _POST_ANCHORS = {
        2025: {19: date(2026, 1, 11), 20: date(2026, 1, 18), 21: date(2026, 1, 25), 22: date(2026, 2, 8)},
        2026: {19: date(2027, 1, 10), 20: date(2027, 1, 17), 21: date(2027, 1, 24), 22: date(2027, 2, 7)},
    }
    if season_type == "POST" and season in _POST_ANCHORS:
        anchors = _POST_ANCHORS[season]
        if week_num in anchors:
            return anchors[week_num]
    return regular_season_sunday(season, week_num)


def target_date_for_stage(season, week, stage, season_type=None):
    sunday = week_anchor_date(season, week, season_type)
    if stage == "initial":
        return sunday - timedelta(days=3)
    if stage in ("update", "lock"):
        return sunday - timedelta(days=1)
    return sunday


def reference_time_for_stage(season, week, stage, season_type=None):
    """UTC cutoff used to simulate whether games have started yet."""
    target = target_date_for_stage(season, week, stage, season_type)
    cutoffs = {
        "initial": time(12, 0),
        "update": time(12, 0),
        "lock": time(16, 0),
        "final": time(0, 0),
    }
    return datetime.combine(target, cutoffs.get(stage, time(0, 0)), tzinfo=timezone.utc)
