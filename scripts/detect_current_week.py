#!/usr/bin/env python3
"""Detect the current NFL week from ESPN's live scoreboard API.

Prints a week label to stdout (PRE1-4, 1-18, WC, DIV, CONF, SB).
Exits with code 0 on success, 1 if ESPN is unreachable.
"""
import json
import sys
import urllib.request

POST_MAP = {1: "WC", 2: "DIV", 3: "CONF", 4: "SB"}

try:
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.load(r)
    season_type = data.get("season", {}).get("type")
    week_number = data.get("week", {}).get("number")
    if season_type and week_number:
        if season_type == 1:
            print("PRE" + str(week_number))
        elif season_type == 2:
            print(str(week_number))
        elif season_type == 3:
            print(POST_MAP.get(week_number, "POST" + str(week_number)))
        else:
            sys.exit(1)
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
