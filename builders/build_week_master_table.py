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
OUTPUT_DIR = "data/historical"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


# -----------------------------
# ESPN SCHEDULE (SOURCE OF TRUTH)
# -----------------------------
def fetch_week_schedule(season: int, week: int):
    params = {
        "seasontype": 2,  # regular season
        "week": week
    }

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
            "week": week,
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
def attach_results(df, season, week):
    params = {
        "seasontype": 2,
        "week": week
    }

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
def build_week_master(season: int, week: int):
    print("📅 Fetching authoritative schedule...")
    df = fetch_week_schedule(season, week)

    week_dir = os.path.join(DATA_DIR, "week" + str(week))

    print("📥 Loading snapshots...")
    initial = load_snapshot(os.path.join(week_dir, "initial.json"))
    update = load_snapshot(os.path.join(week_dir, "update.json"))
    final = load_snapshot(os.path.join(week_dir, "final.json"))

    print("🧩 Attaching snapshots...")
    df = attach_snapshot(df, initial, "initial")
    df = attach_snapshot(df, update, "update")
    df = attach_snapshot(df, final, "final")

    print("🏈 Attaching results...")
    df = attach_results(df, season, week)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "week" + str(week) + "_master.csv")
    df.to_csv(out_path, index=False)

    print("✅ Master table written to:", out_path)


# -----------------------------
# CLI
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    build_week_master(args.season, args.week)
