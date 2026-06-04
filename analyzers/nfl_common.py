"""Shared NFL team and betting-line helpers.

Keep these small and dependency-free so analyzer, replay, and grading scripts
use the same parsing rules.
"""

import re
from datetime import date, datetime, time, timedelta, timezone


REGULAR_SEASON_GAME_TYPES = {"REG"}
POSTSEASON_GAME_TYPES = {"WC", "DIV", "CON", "SB"}
ALL_GAME_TYPES = REGULAR_SEASON_GAME_TYPES | POSTSEASON_GAME_TYPES

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
    """Return REG or POST, inferring playoffs from nflverse week numbers."""
    value = str(season_type or "").strip().upper()
    aliases = {
        "REGULAR": "REG",
        "REGULAR_SEASON": "REG",
        "POSTSEASON": "POST",
        "PLAYOFF": "POST",
        "PLAYOFFS": "POST",
    }
    if value in aliases:
        return aliases[value]
    if value in {"REG", "POST"}:
        return value
    if value in POSTSEASON_GAME_TYPES:
        return "POST"
    if week is not None and int(week) > 18:
        return "POST"
    return "REG"


def nflverse_game_types(season_type=None, week=None):
    normalized = normalize_season_type(season_type, week)
    return sorted(POSTSEASON_GAME_TYPES) if normalized == "POST" else ["REG"]


def espn_season_type(season_type=None, week=None):
    return 3 if normalize_season_type(season_type, week) == "POST" else 2


def espn_week(season_type=None, week=None):
    """Translate nflverse season week into ESPN scoreboard week."""
    if week is None:
        return None
    week = int(week)
    if normalize_season_type(season_type, week) == "REG":
        return week
    if week == 22:
        return 5
    return max(1, week - 18)


def regular_season_sunday(season, week):
    # 2025 season opened Friday 2025-09-05. Sunday of Week 1 is two days later.
    if season != 2025:
        raise ValueError("This helper currently knows the 2025 calendar only.")
    return date(2025, 9, 7) + timedelta(days=(week - 1) * 7)


def week_anchor_date(season, week, season_type=None):
    season_type = normalize_season_type(season_type, week)
    if season == 2025 and season_type == "POST":
        anchors = {
            19: date(2026, 1, 11),
            20: date(2026, 1, 18),
            21: date(2026, 1, 25),
            22: date(2026, 2, 8),
        }
        if int(week) in anchors:
            return anchors[int(week)]
    return regular_season_sunday(season, week)


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
