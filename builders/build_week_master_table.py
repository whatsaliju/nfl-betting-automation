#!/usr/bin/env python3

import json
import os
import sys
import requests
import pandas as pd
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analyzers.nfl_common import espn_season_type, espn_week, normalize_matchup_key, normalize_season_type


# -----------------------------
# CONFIG
# -----------------------------
DATA_DIR = "data"
OUTPUT_BASE = os.path.join("data", "historical")
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# -----------------------------
# PLAYOFF WEEK HANDLING
# -----------------------------
PLAYOFF_LABEL_TO_ESPN_WEEK = {
    "WC": 1,
    "DIV": 2,
    "CONF": 3,
    "CON": 3,
    "SB": 4,
}

# PRESEASON WEEK HANDLING (PRE1/PRE2/PRE3 → ESPN seasontype=1)
PRESEASON_LABEL_TO_ESPN_WEEK = {
    "PRE1": 1,
    "PRE2": 2,
    "PRE3": 3,
    "PRE4": 4,
}


def week_key(week) -> str:
    return str(week).strip().upper()


def week_slug(week, season_type: str = None) -> str:
    key = week_key(week)
    normalized_type = builder_season_type(season_type, week)
    if normalized_type == "PRE" and not key.startswith("PRE"):
        return f"PRE{key}"
    return key


def builder_season_type(season_type, week) -> str:
    key = week_key(week)
    if key in PLAYOFF_LABEL_TO_ESPN_WEEK:
        return "POST"
    if key in PRESEASON_LABEL_TO_ESPN_WEEK:
        return "PRE"
    return normalize_season_type(season_type, key)


def espn_params_for(season: int, week, season_type: str = None):
    key = week_key(week)
    if key in PLAYOFF_LABEL_TO_ESPN_WEEK:
        return {
            "dates": season,
            "seasontype": 3,
            "week": PLAYOFF_LABEL_TO_ESPN_WEEK[key],
        }
    if key in PRESEASON_LABEL_TO_ESPN_WEEK:
        return {
            "dates": season,
            "seasontype": 1,
            "week": PRESEASON_LABEL_TO_ESPN_WEEK[key],
        }

    try:
        week_num = int(key)
    except (ValueError, TypeError):
        week_num = 1
    normalized_type = normalize_season_type(season_type, week_num)
    return {
        "dates": season,
        "seasontype": espn_season_type(normalized_type, week_num),
        "week": espn_week(normalized_type, week_num),
    }


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
STAGES = ["initial", "update", "lock", "final"]

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
def fetch_week_schedule(season: int, week, season_type: str = None):
    season_type = builder_season_type(season_type, week)
    params = espn_params_for(season, week, season_type)

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
            "season_type": season_type,
            "week": week_key(week),
            "matchup_key": normalize_matchup_key(away["team"]["abbreviation"] + "@" + home["team"]["abbreviation"]),
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


def load_source_health(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def attach_snapshot(df, snapshot, prefix):
    df["has_" + prefix] = False

    fields = [
        "classification",
        "classification_label",
        "recommendation",
        "tier_score",
        "total_score",
        "confidence",
        "model_version",
        "signal_classification",
    ]

    for field in fields:
        df[prefix + "_" + field] = None
    for field in [
        "pick_market",
        "pick_side",
        "selector_score",
        "pick_reasons",
        "recommendation_trace",
        "data_quality_status",
        "unsafe_sources",
        "degraded_sources",
        "sharp_spread_line",
        "sharp_total_line",
        "sharp_moneyline_line",
    ]:
        df[prefix + "_" + field] = None

    for idx, row in df.iterrows():
        key = row["matchup_key"]
        if key not in snapshot:
            continue

        g = snapshot[key]
        df.at[idx, "has_" + prefix] = True

        for field in fields:
            df.at[idx, prefix + "_" + field] = g.get(field)
        pick = g.get("pick_metadata") or {}
        df.at[idx, prefix + "_pick_market"] = pick.get("market")
        df.at[idx, prefix + "_pick_side"] = pick.get("side")
        score = pick.get("score")
        if score is None and pick.get("market") == "none":
            # PASS games record per-market scores as spread_score/total_score; use the best one
            cands = [pick.get("spread_score"), pick.get("total_score")]
            score = max((s for s in cands if s is not None), default=None)
        df.at[idx, prefix + "_selector_score"] = score
        df.at[idx, prefix + "_pick_reasons"] = "; ".join(pick.get("reasons", []))
        trace = g.get("recommendation_trace") or pick.get("trace") or {}
        df.at[idx, prefix + "_recommendation_trace"] = json.dumps(trace, sort_keys=True)
        data_quality = g.get("data_quality") or {}
        df.at[idx, prefix + "_data_quality_status"] = data_quality.get("status")
        df.at[idx, prefix + "_unsafe_sources"] = ", ".join(data_quality.get("unsafe_sources", []))
        df.at[idx, prefix + "_degraded_sources"] = ", ".join(data_quality.get("degraded_sources", []))
        sharp = g.get("sharp_analysis") or {}
        df.at[idx, prefix + "_sharp_spread_line"] = (sharp.get("spread") or {}).get("line") or ""
        df.at[idx, prefix + "_sharp_total_line"] = (sharp.get("total") or {}).get("line") or ""
        df.at[idx, prefix + "_sharp_moneyline_line"] = (sharp.get("moneyline") or {}).get("line") or ""

    return df


def attach_source_health(df, source_health, prefix):
    df[prefix + "_source_health_status"] = source_health.get("status")
    df[prefix + "_source_health_warnings"] = "; ".join(
        source_health.get("critical_warnings", []) + source_health.get("warnings", [])
    )
    df[prefix + "_source_health_degraded_sources"] = ", ".join(source_health.get("degraded_sources", []))
    df[prefix + "_source_health_unsafe_sources"] = ", ".join(source_health.get("unsafe_sources", []))
    df[prefix + "_source_health_reference_time"] = source_health.get("analysis_reference_time")
    return df


# -----------------------------
# RESULTS ATTACHMENT
# -----------------------------
def attach_results(df, season, week, season_type: str = None):
    season_type = builder_season_type(season_type, week)
    params = espn_params_for(season, week, season_type)

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

        key = normalize_matchup_key(away["team"]["abbreviation"] + "@" + home["team"]["abbreviation"])

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
def augment_from_snapshots(df, week_dir, season, season_type, week_key_str):
    """Add games found in analytics snapshots that ESPN's scoreboard didn't return."""
    known_keys = set(df["matchup_key"].values)
    new_rows = []
    for stage in STAGES:
        snap = normalize_snapshot_keys(load_snapshot(os.path.join(week_dir, f"{stage}.json")))
        for mk, game_data in snap.items():
            if mk in known_keys:
                continue
            parts = mk.split("@") if "@" in mk else [mk, mk]
            new_rows.append({
                "season": season,
                "season_type": season_type,
                "week": week_key_str,
                "matchup_key": mk,
                "away_team": game_data.get("away") or parts[0],
                "home_team": game_data.get("home") or (parts[1] if len(parts) > 1 else ""),
                "away_tla": parts[0],
                "home_tla": parts[1] if len(parts) > 1 else "",
                "game": game_data.get("matchup") or mk,
            })
            known_keys.add(mk)
    if new_rows:
        print(f"  ℹ️  Augmenting schedule with {len(new_rows)} games found in analytics (not in ESPN).")
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    return df


def build_week_master(season: int, week, season_type: str = None):
    season_type = builder_season_type(season_type, week)
    key = week_key(week)
    slug = week_slug(week, season_type)
    print(f"📅 Fetching authoritative schedule for {season} Week {key}...")
    df = fetch_week_schedule(season, week, season_type)

    week_dir = os.path.join(DATA_DIR, "week" + slug)

    # Augment ESPN schedule with any games present in analytics but missing from ESPN
    df = augment_from_snapshots(df, week_dir, season, season_type, key)

    print("📥 Loading snapshots...")
    print("🧩 Attaching snapshots...")
    for stage in STAGES:
        snapshot = normalize_snapshot_keys(load_snapshot(os.path.join(week_dir, f"{stage}.json")))
        source_health = load_source_health(os.path.join(week_dir, f"{stage}_source_health.json"))
        df = attach_snapshot(df, snapshot, stage)
        df = attach_source_health(df, source_health, stage)

    print("🏈 Attaching results...")
    df = attach_results(df, season, week, season_type)

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    out_path = os.path.join(OUTPUT_BASE, f"week{slug}_master.csv")
    out_json_path = os.path.join(OUTPUT_BASE, f"week{slug}_master.json")

    if os.path.exists(out_path):
        existing = pd.read_csv(out_path)
        # Prevent dtype coercion during combine_first: pandas upcasts an all-NaN
        # column to float64 which silently converts any string values to NaN.
        # Force JSON-string and other object columns to stay as object dtype.
        for col in existing.columns:
            if col.endswith("_recommendation_trace") or col.endswith("_pick_reasons"):
                existing[col] = existing[col].astype(object)
        df = (
            df.set_index("matchup_key")
              .combine_first(
                  existing.set_index("matchup_key")
              )
              .reset_index()
        )
    df = df.sort_values("matchup_key").reset_index(drop=True)
    df.to_csv(out_path, index=False)
    df.to_json(out_json_path, orient="records", indent=2)

    print("✅ Master table written to:", out_path)
    print("✅ Master JSON written to:", out_json_path)


# -----------------------------
# CLI
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build master table for NFL week (supports regular season 1-18 and playoffs WC/DIV/CONF/SB)"
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", required=True, help="Week number (1-18/19-22) or playoff round (WC/DIV/CONF/SB)")
    parser.add_argument("--season-type", default=None, help="REG or POST. Defaults to POST for weeks above 18.")
    args = parser.parse_args()

    build_week_master(args.season, args.week, args.season_type)
