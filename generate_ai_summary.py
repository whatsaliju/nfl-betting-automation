#!/usr/bin/env python3
"""
Generate AI-Ready Summary for Manual Claude Analysis
Option A: SIMPLE + CORRECT
- Stable merges
- Correct injury / weather matches via team normalization
- Correct sharp money matches via team normalization
- No new features added
"""

import pandas as pd
import os
from datetime import datetime

# ------------------------------------------------------
# TEAM NORMALIZATION MAP (abbrev → full name)
# ------------------------------------------------------
TEAM_MAP = {
    "NE": "Patriots", "NYJ": "Jets",
    "WAS": "Commanders", "MIA": "Dolphins",
    "CAR": "Panthers", "ATL": "Falcons",
    "TB": "Buccaneers", "BUF": "Bills",
    "LAC": "Chargers", "JAX": "Jaguars",
    "CHI": "Bears", "MIN": "Vikings",
    "GB": "Packers", "NYG": "Giants",
    "CIN": "Bengals", "PIT": "Steelers",
    "HOU": "Texans", "TEN": "Titans",
    "SF": "49ers", "ARI": "Cardinals",
    "SEA": "Seahawks", "LAR": "Rams",
    "BAL": "Ravens", "CLE": "Browns",
    "KC": "Chiefs", "DEN": "Broncos",
    "DET": "Lions", "PHI": "Eagles",
    "DAL": "Cowboys", "LV": "Raiders"
}

# ------------------------------------------------------
# HELPERS
# ------------------------------------------------------

def safe_load_csv(path):
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def find_latest(prefix):
    files = [f for f in os.listdir('.') if f.startswith(prefix)]
    return sorted(files)[-1] if files else None


# ------------------------------------------------------
# MAIN SUMMARY
# ------------------------------------------------------

def generate_ai_summary(week):

    # ---------- Load core files ----------
    refs = safe_load_csv(f"week{week}_referees.csv")
    queries = safe_load_csv(f"week{week}_queries.csv")
    sdql = safe_load_csv("sdql_results.csv")

    if queries.empty:
        print("❌ No queries found.")
        return None

    # Merge ref trends + SDQL into queries
    final = queries.merge(sdql, on="query", how="left")

    # ---------- Load Action Network ----------
    action_file = find_latest("action_all_markets")
    if action_file:
        action = safe_load_csv(action_file)
    else:
        action = pd.DataFrame()

    # ---------- Load Rotowire ----------
    injury_file = find_latest("rotowire_lineups_")
    if injury_file:
        injuries = safe_load_csv(injury_file)
    else:
        injuries = pd.DataFrame()

    # Normalize rotowire names
    if not injuries.empty:
        injuries["home_std"] = injuries["home"].map(TEAM_MAP)
        injuries["away_std"] = injuries["away"].map(TEAM_MAP)

        # Clean weather newlines
        if "weather" in injuries.columns:
            injuries["weather"] = injuries["weather"].astype(str).str.replace("\n", " | ")

    # Normalize Action Network matchup names
    if not action.empty and "Matchup" in action.columns:
        # example: "Packers @ Giants" → "Packers", "Giants"
        def extract_teams(s):
            try:
                left, right = s.split("@")
                return left.strip(), right.strip()
            except:
                return "", ""
        action[["away_full", "home_full"]] = action["Matchup"].apply(
            lambda x: pd.Series(extract_teams(x))
        )

    # -------------------------------------------------
    # Merge Sharp Money (corrected)
    # -------------------------------------------------
    final["bets_pct"] = 0.0
    final["money_pct"] = 0.0
    final["sharp_edge"] = 0.0
    
    if not action.empty and "Matchup" in action.columns:
    
        for idx, row in final.iterrows():
    
            away_abbr = row.get("away", "")
            home_abbr = row.get("home", "")
    
            # Convert abbrev → full name
            away_full = TEAM_MAP.get(away_abbr, away_abbr)
            home_full = TEAM_MAP.get(home_abbr, home_abbr)
    
            # Two possible matchup formats
            target1 = f"{away_full} @ {home_full}"
            target2 = f"{home_full} @ {away_full}"
    
            matches = action[
                (action["Matchup"] == target1) |
                (action["Matchup"] == target2)
            ]
    
            if len(matches) > 0:
                m = matches.iloc[0]
                try:
                    bets = float(str(m["Bets %"]).replace("%", ""))
                    money = float(str(m["Money %"]).replace("%", ""))
                    final.loc[idx, "bets_pct"] = bets
                    final.loc[idx, "money_pct"] = money
                    final.loc[idx, "sharp_edge"] = money - bets
                except:
                    pass



    # -------------------------------------------------
    # Merge Injuries + Weather
    # -------------------------------------------------
    final["injuries"] = ""
    final["weather"] = ""
    final["game_time"] = ""

    if not injuries.empty:
        for idx, row in final.iterrows():
            home = row.get("home", "")
            away = row.get("away", "")

            match = injuries[
                (injuries["home_std"] == home) &
                (injuries["away_std"] == away)
            ]

            if not match.empty:
                m = match.iloc[0]
                final.loc[idx, "injuries"] = m.get("injuries", "")
                final.loc[idx, "weather"] = m.get("weather", "")
                final.loc[idx, "game_time"] = m.get("game_time", "")

    # -------------------------------------------------
    # WRITE SUMMARY FILE
    # -------------------------------------------------

    outfile = f"week{week}_ai_summary.txt"

    with open(outfile, "w") as f:

        f.write("="*80 + "\n")
        f.write(f"NFL WEEK {week} - AI ANALYSIS REQUEST\n")
        f.write(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
        f.write("="*80 + "\n\n")

        # ---------- GAME BY GAME ----------
        for idx, row in final.iterrows():
            f.write(f"GAME #{idx+1}: {row['matchup']}\n")
            f.write("-"*80 + "\n")

            # Time
            if row.get("game_time"):
                f.write(f"Time: {row['game_time']}\n")

            # Referee
            f.write(f"\nREFEREE: {row.get('referee','Unknown')}\n")
            f.write(f"  ATS: {row.get('ats_record','')} ({row.get('ats_pct','')})\n")
            f.write(f"  SU:  {row.get('su_record','')} ({row.get('su_pct','')})\n")
            f.write(f"  O/U: {row.get('ou_record','')} ({row.get('ou_pct','')})\n")

            # Betting
            f.write("\nBETTING LINES:\n")
            try:
                f.write(f"  Spread: {row['home']} {float(row['spread']):+.1f}\n")
            except:
                f.write("  Spread: N/A\n")

            # Sharp money
            f.write("\nSHARP MONEY:\n")
            edge = row.get("sharp_edge", 0)
            f.write(f"  Sharp Edge: {edge:+.1f}%\n")

            # Injuries
            f.write("\nINJURIES:\n")
            f.write(f"  {row['injuries'] or 'None'}\n")

            # Weather
            f.write("\nWEATHER:\n")
            f.write(f"  {row['weather'] or 'None'}\n")

            # Context
            f.write("\nCONTEXT:\n")
            f.write(f"  Type: {row.get('game_type')}\n")
            f.write(f"  Favorite: {row.get('favorite')}\n")

            f.write("\n" + "="*80 + "\n\n")

    print(f"✅ Summary generated: {outfile}")
    return outfile



if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_ai_summary(week)
