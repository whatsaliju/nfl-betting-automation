# utils/team_codes.py

TEAM_TLA_CANONICAL = {
    # Washington (critical fix)
    "WAS": "WSH",
    "WSH": "WSH",

    # Vegas
    "OAK": "LV",
    "LV": "LV",

    # Jacksonville (historical safety)
    "JAC": "JAX",
    "JAX": "JAX",

    # LA teams (paranoia-safe)
    "SD": "LAC",
    "LAC": "LAC",
    "STL": "LAR",
    "LAR": "LAR",
}

def normalize_tla(tla: str) -> str:
    if not tla:
        return tla
    return TEAM_TLA_CANONICAL.get(tla.upper(), tla.upper())


def normalize_matchup_key(away_tla: str, home_tla: str) -> str:
    away = normalize_tla(away_tla)
    home = normalize_tla(home_tla)
    return f"{away}@{home}"
