"""
Append preseason card rows to data/historical/preseason_results.csv.
Run after each preseason engine cycle. Outcome columns are left blank
for manual entry after games are played.

Usage:
    python3 scripts/log_preseason_results.py
"""
import csv
import json
import os
from pathlib import Path

FEED_PATH = "data/historical/matrix_engine_feed.json"
LOG_PATH = "data/historical/preseason_results.csv"

FIELDNAMES = [
    "season", "week", "matchup_key", "away_tla", "home_tla",
    "action", "pick_label", "selector_score", "confidence",
    "required_line", "current_line", "referee",
    "ats_pct", "ou_pct", "ref_sample",
    # outcome columns — fill in after game
    "ats_result",   # cover / no_cover / push
    "ou_result",    # over / under / push
    "notes",
]

with open(FEED_PATH) as f:
    feed = json.load(f)

ctx = feed.get("current_context", {})
if ctx.get("season_type") != "PRE":
    print("Not a preseason context — nothing to log.")
    exit(0)

cards = feed.get("weekly_betting_card", {}).get("cards", [])
actionable = [c for c in cards if c.get("action") in ("play", "watch", "lean")]

if not actionable:
    print("No actionable cards to log.")
    exit(0)

# Load existing rows to avoid duplicates
existing_keys = set()
log_exists = os.path.exists(LOG_PATH)
if log_exists:
    with open(LOG_PATH, newline="") as f:
        for row in csv.DictReader(f):
            existing_keys.add((row["season"], row["week"], row["matchup_key"]))

new_rows = []
for c in actionable:
    key = (str(c.get("season", "")), str(c.get("week", "")), c.get("matchup_key", ""))
    if key in existing_keys:
        continue
    ref_stats = c.get("referee_stats") or {}
    new_rows.append({
        "season":         c.get("season", ""),
        "week":           c.get("week", ""),
        "matchup_key":    c.get("matchup_key", ""),
        "away_tla":       c.get("away_tla", ""),
        "home_tla":       c.get("home_tla", ""),
        "action":         c.get("action", ""),
        "pick_label":     c.get("pick_label", ""),
        "selector_score": c.get("selector_score", ""),
        "confidence":     c.get("confidence", ""),
        "required_line":  c.get("required_line", ""),
        "current_line":   c.get("current_line", ""),
        "referee":        c.get("referee", ""),
        "ats_pct":        ref_stats.get("ats_pct", ""),
        "ou_pct":         ref_stats.get("ou_pct", ""),
        "ref_sample":     ref_stats.get("sample_size", ""),
        "ats_result":     "",
        "ou_result":      "",
        "notes":          "",
    })

if not new_rows:
    print("All current cards already logged.")
    exit(0)

with open(LOG_PATH, "a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    if not log_exists:
        writer.writeheader()
    writer.writerows(new_rows)

print(f"Logged {len(new_rows)} new row(s) to {LOG_PATH}")
for r in new_rows:
    print(f"  {r['season']} {r['week']} {r['matchup_key']} {r['action']} {r['pick_label']}")
