#!/usr/bin/env python3

import pandas as pd
import requests
import re
from datetime import datetime
import argparse

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


# -----------------------------
# SCORE FETCH
# -----------------------------
def fetch_scores(season, week):
    params = {"seasontype": 2, "week": week}
    r = requests.get(ESPN_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    scores = {}
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])

        away = home = None
        for c in competitors:
            if c.get("homeAway") == "away":
                away = c
            elif c.get("homeAway") == "home":
                home = c

        if not away or not home:
            continue

        key = away["team"]["abbreviation"] + "@" + home["team"]["abbreviation"]
        a = int(away.get("score", 0))
        h = int(home.get("score", 0))

        scores[key] = {
            "away_score": a,
            "home_score": h,
            "margin": a - h,
            "total": a + h
        }

    return scores


# -----------------------------
# RECOMMENDATION PARSER
# -----------------------------
def parse_recommendation(text):
    if not isinstance(text, str):
        return None

    # Spread: TEAM -3.5
    spread = re.search(r'([A-Za-z ]+)\s([+-]\d+\.?\d*)', text)
    if spread:
        return {
            "type": "spread",
            "team": spread.group(1).strip(),
            "line": float(spread.group(2))
        }

    # Totals: OVER 47.5 / UNDER 41
    total = re.search(r'(OVER|UNDER|O|U)\s?(\d+\.?\d*)', text, re.I)
    if total:
        return {
            "type": "total",
            "side": total.group(1).upper()[0],  # O / U
            "line": float(total.group(2))
        }

    return None


# -----------------------------
# EVALUATION
# -----------------------------
def evaluate(row, score):
    rec = parse_recommendation(row.get("final_recommendation"))
    if not rec:
        return "NO BET", None

    if rec["type"] == "spread":
        line = rec["line"]
        margin = score["margin"]

        # away team is listed first in matchup_key
        away = row["away_tla"]
        picked_team = rec["team"].split()[-1]

        picked_is_away = picked_team in away
        effective_margin = margin if picked_is_away else -margin

        cover = effective_margin + line

        if cover > 0:
            return "WIN", cover
        if cover < 0:
            return "LOSS", cover
        return "PUSH", 0

    if rec["type"] == "total":
        total = score["total"]
        line = rec["line"]

        if rec["side"] == "O":
            return ("WIN" if total > line else "LOSS" if total < line else "PUSH"), total - line
        else:
            return ("WIN" if total < line else "LOSS" if total > line else "PUSH"), line - total

    return "NO BET", None


# -----------------------------
# MAIN
# -----------------------------
def grade_week(season, week):
    path = f"data/historical/week{week}_master.csv"
    df = pd.read_csv(path)

    scores = fetch_scores(season, week)

    df["graded"] = df.get("graded", False)
    df["result"] = df.get("result")
    df["cover_margin"] = df.get("cover_margin")
    df["graded_at"] = df.get("graded_at")

    for idx, row in df.iterrows():
        if row["graded"]:
            continue

        key = row["matchup_key"]
        if key not in scores:
            continue

        result, margin = evaluate(row, scores[key])

        df.at[idx, "result"] = result
        df.at[idx, "cover_margin"] = margin
        df.at[idx, "graded"] = True
        df.at[idx, "graded_at"] = datetime.utcnow().isoformat()

    df.to_csv(path, index=False)
    print(f"✅ Week {week} graded successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    grade_week(args.season, args.week)
