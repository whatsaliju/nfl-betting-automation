#!/usr/bin/env python3

import json
import os
import requests
import pandas as pd
from datetime import datetime


# -----------------------------
# CONFIG
# -----------------------------
DATA_DIR = "data"
OUTPUT_BASE = os.path.join("data", "historical")
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# -----------------------------
# PLAYOFF WEEK HANDLING
# -----------------------------
def get_espn_params(week_str):
    """Convert week to ESPN API parameters"""
    
    # Regular season weeks (1-18)
    try:
        week_num = int(week_str)
        return {"seasontype": 2, "week": week_num}  # Regular season
    except ValueError:
        pass
    
    # Playoff weeks
    playoff_mapping = {
        'WC': {"seasontype": 3, "week": 1},      # Wild Card
        'DIV': {"seasontype": 3, "week": 2},     # Divisional  
        'CONF': {"seasontype": 3, "week": 3},    # Conference
        'SB': {"seasontype": 3, "week": 4}       # Super Bowl
    }
    
    if week_str in playoff_mapping:
        return playoff_mapping[week_str]
    
    raise ValueError(f"Unknown week format: {week_str}")


# -----------------------------
# MATCHUP KEY NORMALIZATION (BUILDER-ONLY)
# -----------------------------
MATCHUP_KEY_ALIASES = {
    # Washington
    "PHI@WAS": "PHI@WSH",
    "DAL@WAS": "DAL@WSH",
    "NYG@WAS": "NYG@WSH",
    "WAS@PHI": "WSH@PHI",
    "WAS@DAL": "WSH@DAL",
    "WAS@NYG": "WSH@NYG",
}

def normalize_snapshot_keys(snapshot: dict) -> dict:
    normalized = {}

    for key, game in snapshot.items():
        canonical_key = MATCHUP_KEY_ALIASES.get(key, key)

        # Preserve original key for audit / ML
        game = dict(game)
        game["original_matchup_key"] = key

        normalized[canonical_key] = game

    return normalized


# -----------------------------
# ESPN SCHEDULE (SOURCE OF TRUTH)
# -----------------------------
def fetch_week_schedule(season: int, week: str):
    """Fetch schedule for given season and week (supports playoffs)"""
    params = get_espn_params(week)

    r = requests.get(ESPN_SCOREBOARD_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    games = []

    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        away = home = None
        for c in competitors:
            if c.get("homeAway") == "away":
                away = c
            elif c.get("homeAway") == "home":
                home = c

        if not away or not home:
            continue

        games.append({
            "season": season,
            "week": week,  # Keep as string (e.g., "WC", "18")
            "matchup_key": away["team"]["abbreviation"] + "@" + home["team"]["abbreviation"],
            "away_team": away["team"]["displayName"],
            "home_team": home["team"]["displayName"],
            "away_tla": away["team"]["abbreviation"],
            "home_tla": home["team"]["abbreviation"],
            "game": away["team"]["displayName"] + " @ " + home["team"]["displayName"]
        })

    return pd.DataFrame(games)


# -----------------------------
# SNAPSHOT LOADERS
# -----------------------------
def load_snapshot(path):
    if not os.path.exists(path):
        return {}

    with open(path, "r") as f:
        data = json.load(f)

    return {g["matchup_key"]: g for g in data}


def attach_snapshot(df, snapshot, prefix):
    df["has_" + prefix] = False

    fields = [
        "classification",
        "classification_label",
        "recommendation",
        "tier_score",
        "total_score",
        "confidence"
    ]

    for field in fields:
        df[prefix + "_" + field] = None

    for idx, row in df.iterrows():
        key = row["matchup_key"]
        if key not in snapshot:
            continue

        g = snapshot[key]
        df.at[idx, "has_" + prefix] = True

        for field in fields:
            df.at[idx, prefix + "_" + field] = g.get(field)

    return df


# -----------------------------
# RESULTS ATTACHMENT
# -----------------------------
def attach_results(df, season, week: str):
    """Attach final scores for given week (supports playoffs)"""
    params = get_espn_params(week)

    r = requests.get(ESPN_SCOREBOARD_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    score_map = {}

    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        away = home = None
        for c in competitors:
            if c.get("homeAway") == "away":
                away = c
            elif c.get("homeAway") == "home":
                home = c

        if not away or not home:
            continue

        key = away["team"]["abbreviation"] + "@" + home["team"]["abbreviation"]

        score_map[key] = {
            "away_score": int(away.get("score", 0)),
            "home_score": int(home.get("score", 0))
        }

    df["away_score"] = None
    df["home_score"] = None
    df["final_margin"] = None
    df["final_total"] = None

    for idx, row in df.iterrows():
        key = row["matchup_key"]
        if key not in score_map:
            continue

        a = score_map[key]["away_score"]
        h = score_map[key]["home_score"]

        df.at[idx, "away_score"] = a
        df.at[idx, "home_score"] = h
        df.at[idx, "final_margin"] = a - h
        df.at[idx, "final_total"] = a + h

    return df


# -----------------------------
# MAIN BUILDER
# -----------------------------
def build_week_master(season: int, week: str):
    print(f"📅 Fetching authoritative schedule for {season} Week {week}...")
    df = fetch_week_schedule(season, week)

    week_dir = os.path.join(DATA_DIR, "week" + week)  # e.g., "weekWC", "week18"

    print("📥 Loading snapshots...")
    initial = normalize_snapshot_keys(
        load_snapshot(os.path.join(week_dir, "initial.json"))
    )
    
    update = normalize_snapshot_keys(
        load_snapshot(os.path.join(week_dir, "update.json"))
    )
    
    lock = normalize_snapshot_keys(
        load_snapshot(os.path.join(week_dir, "lock.json"))
    )

    print("🧩 Attaching snapshots...")
    df = attach_snapshot(df, initial, "initial")
    df = attach_snapshot(df, update, "update")
    df = attach_snapshot(df, lock, "lock")

    print("🏈 Attaching results...")
    df = attach_results(df, season, week)

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    out_path = os.path.join(OUTPUT_BASE, f"week{week}_master.csv")

    if os.path.exists(out_path):
        existing = pd.read_csv(out_path)
    
        df = (
            df.set_index("matchup_key")
              .combine_first(
                  existing.set_index("matchup_key")
              )
              .reset_index()
        )
    df = df.sort_values("matchup_key").reset_index(drop=True)
    df.to_csv(out_path, index=False)

    print("✅ Master table written to:", out_path)


# -----------------------------
# CLI
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build master table for NFL week (supports regular season 1-18 and playoffs WC/DIV/CONF/SB)"
    )
    parser.add_argument("--season", type=int, required=True, help="NFL season year")
    parser.add_argument("--week", type=str, required=True, 
                       help="Week number (1-18) or playoff round (WC/DIV/CONF/SB)")
    args = parser.parse_args()

    build_week_master(args.season, args.week)
