#!/usr/bin/env python3
"""
Advanced Enhanced NFL Betting Report Generator (FIXED VERSION)
===================================================================

Outputs:
- weekX_enhanced_report.txt
- weekX_enhanced_report.md
- weekX_enhanced_report.json
- weekX_enhanced_data.csv

FIXES:
✓ Sharp money matching corrected (away @ home format)
✓ Better debugging output to identify matching issues
✓ Spread now pulls from Action Network when available
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime


# ================================================================
# TEAM NORMALIZATION
# ================================================================

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


# ================================================================
# FILE HELPERS
# ================================================================

def safe_load_csv(path, required=False):
    """Safely load CSV, never throw hard errors."""
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
        if required:
            print(f"❌ Required file not found: {path}")
        else:
            print(f"⚠️ Optional file missing: {path}")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error loading {path}: {e}")
        return pd.DataFrame()


def find_latest(prefix):
    """Find the latest file with a given prefix."""
    matches = [f for f in os.listdir('.') if f.startswith(prefix)]
    return sorted(matches)[-1] if matches else None


# ================================================================
# ANALYTICS SCORING FUNCTIONS
# ================================================================

def score_referee_trend(ats):
    if ats >= 60: return 3
    if ats >= 55: return 2
    if ats <= 40: return -2
    return 0


def score_sharp_money(edge):
    if edge >= 8: return 4
    if edge >= 5: return 3
    if edge >= 3: return 2
    if edge <= -5: return -3
    return 0


def score_public_exposure(pct):
    if pct >= 70: return -2
    if pct >= 60: return -1
    return 0


def score_injuries(txt):
    """Detect importance of injuries."""
    s = str(txt).lower().strip()
    if s == "" or s == "none":
        return 0, []

    penalty = 0
    notes = []

    # Severity
    if any(x in s for x in ["doubtful", "questionable", "out", "ir", "d", "q", "o"]):
        penalty -= 1
        notes.append("Key injury present")

    # Position weighting
    if any(x in s for x in ["qb", "quarterback"]):
        penalty -= 2
        notes.append("QB injury")
    if any(x in s for x in ["wr", "wide", "receiver"]):
        penalty -= 1
        notes.append("WR injury")
    if any(x in s for x in ["rb", "running", "back"]):
        penalty -= 1
        notes.append("RB injury")
    if any(x in s for x in ["ol", "tackle", "guard", "center"]):
        penalty -= 1
        notes.append("OL injury")

    return penalty, notes


def score_weather(txt):
    """Parse weather string (°F, mph, precip)."""
    s = str(txt).lower().strip()
    if s == "" or s == "none":
        return 0, []

    score = 0
    notes = []

    # Dome
    if "dome" in s:
        return 0, ["Dome"]

    # Precip %
    for token in s.split():
        if token.endswith("%"):
            try:
                precip = int(token.replace("%", ""))
                if precip >= 50:
                    score -= 1
                    notes.append(f"High precipitation ({precip}%)")
            except:
                pass

    # Wind mph
    for token in s.replace(",", " ").split():
        try:
            mph = float(token)
            if mph >= 15:
                score -= 1
                notes.append(f"Windy ({mph} mph)")
            if mph >= 20:
                score -= 1
                notes.append(f"High wind ({mph} mph)")
        except:
            continue

    return score, notes


def classify_game(score, sharp_edge, public_pct):
    if score >= 6 and sharp_edge >= 5:
        return "BLUE CHIP"
    if score >= 4:
        return "TARGETED PLAY"
    if score >= 2:
        return "LEAN"
    if score <= -2:
        return "FADE"
    if score < 0 and public_pct >= 60 and sharp_edge < 0:
        return "TRAP GAME"
    return "LANDMINE"


# ================================================================
# MAIN REPORT GENERATOR
# ================================================================

def generate_enhanced_report(week):

    print("\n========== GENERATING ENHANCED REPORT ==========\n")

    # Required files
    referees = safe_load_csv(f"week{week}_referees.csv", required=True)
    queries = safe_load_csv(f"week{week}_queries.csv", required=True)
    sdql = safe_load_csv("sdql_results.csv", required=True)

    if queries.empty:
        print("❌ No queries found. Cannot proceed.")
        return

    # Optional files
    action_file = find_latest("action_all_markets_")
    action = safe_load_csv(action_file) if action_file else pd.DataFrame()

    rotowire_file = find_latest("rotowire_lineups_")
    rotowire = safe_load_csv(rotowire_file) if rotowire_file else pd.DataFrame()

    # ============================================================
    # MERGE BASE DATA
    # ============================================================

    final = queries.merge(sdql, on="query", how="left")

    # ============================================================
    # SHARP MONEY MERGE (FIXED)
    # ============================================================

    final["bets_pct"] = 0.0
    final["money_pct"] = 0.0
    final["sharp_edge"] = 0.0
    final["action_spread"] = ""

    if not action.empty and "Matchup" in action.columns:
        # Filter to just spread market
        spread_data = action[action["Market"] == "Spread"].copy()
        
        # Parse "Packers @ Giants" -> "Packers", "Giants"
        def parse_matchup(s):
            try:
                parts = s.split("@")
                return parts[0].strip(), parts[1].strip()
            except:
                return "", ""

        spread_data[["away_full", "home_full"]] = spread_data["Matchup"].apply(
            lambda x: pd.Series(parse_matchup(x))
        )

        print("\n🔍 DEBUG: Matching sharp money...")
        matched_count = 0
        
        for i, row in final.iterrows():
            away_full = TEAM_MAP.get(row["away"], row["away"])
            home_full = TEAM_MAP.get(row["home"], row["home"])

            # Action Network format is: away @ home
            match = spread_data[
                (spread_data["away_full"] == away_full) &
                (spread_data["home_full"] == home_full)
            ]

            if not match.empty:
                m = match.iloc[0]
                try:
                    # Parse "60% | 40%" format
                    bets_raw = str(m["Bets %"]).split("|")
                    money_raw = str(m["Money %"]).split("|")
                    
                    # First percentage is for away team
                    away_bets = float(bets_raw[0].strip().replace("%", ""))
                    away_money = float(money_raw[0].strip().replace("%", ""))
                    
                    final.at[i, "bets_pct"] = away_bets
                    final.at[i, "money_pct"] = away_money
                    final.at[i, "sharp_edge"] = away_money - away_bets
                    final.at[i, "action_spread"] = str(m.get("Line", ""))
                    
                    matched_count += 1
                    print(f"  ✓ {away_full} @ {home_full}: {away_money - away_bets:+.1f}% edge")
                except Exception as e:
                    print(f"  ⚠️ Error parsing {away_full} @ {home_full}: {e}")
            else:
                print(f"  ✗ No match for {away_full} @ {home_full}")
        
        print(f"\n✓ Matched {matched_count}/{len(final)} games with sharp money data\n")

    # ============================================================
    # ROTOWIRE MERGE (injuries + weather + game time)
    # ============================================================

    final["injuries"] = ""
    final["weather"] = ""
    final["game_time"] = ""

    if not rotowire.empty:
        rotowire["home_std"] = rotowire["home"].map(TEAM_MAP)
        rotowire["away_std"] = rotowire["away"].map(TEAM_MAP)

        for i, row in final.iterrows():
            home_full = TEAM_MAP.get(row["home"], row["home"])
            away_full = TEAM_MAP.get(row["away"], row["away"])

            match = rotowire[
                (rotowire["home_std"] == home_full) &
                (rotowire["away_std"] == away_full)
            ]

            if not match.empty:
                m = match.iloc[0]
                final.at[i, "injuries"] = m.get("injuries", "")
                final.at[i, "weather"] = m.get("weather", "")
                final.at[i, "game_time"] = m.get("game_time", "")

    # ============================================================
    # ANALYTICS PROCESSING
    # ============================================================

    results = []

    for _, row in final.iterrows():
        ats = float(str(row.get("ats_pct", "0")).replace("%", "") or 0)
        sharp_edge = float(row["sharp_edge"])
        public_pct = float(row["bets_pct"])

        ref_score = score_referee_trend(ats)
        sharp_score = score_sharp_money(sharp_edge)
        public_score = score_public_exposure(public_pct)
        inj_score, inj_notes = score_injuries(row["injuries"])
        weather_score, weather_notes = score_weather(row["weather"])

        total = ref_score + sharp_score + public_score + inj_score + weather_score
        category = classify_game(total, sharp_edge, public_pct)

        # Use Action Network spread if available, otherwise fallback
        spread_display = row.get("action_spread", "") or row.get("spread", "")

        results.append({
            "matchup": row["matchup"],
            "game_time": row["game_time"],
            "home": row["home"],
            "away": row["away"],
            "ref_ats_pct": ats,
            "spread": spread_display,
            "sharp_edge": sharp_edge,
            "public_pct": public_pct,
            "injuries": row["injuries"],
            "weather": row["weather"],
            "score": total,
            "classification": category,
            "ref_score": ref_score,
            "sharp_score": sharp_score,
            "public_score": public_score,
            "injury_score": inj_score,
            "weather_score": weather_score,
            "injury_notes": inj_notes,
            "weather_notes": weather_notes
        })

    out_df = pd.DataFrame(results)

    # ============================================================
    # OUTPUT FILES
    # ============================================================

    txt = f"week{week}_enhanced_report.txt"
    md = f"week{week}_enhanced_report.md"
    jsonf = f"week{week}_enhanced_report.json"
    csv = f"week{week}_enhanced_data.csv"

    # JSON
    with open(jsonf, "w") as f:
        json.dump(results, f, indent=4)

    # CSV
    out_df.to_csv(csv, index=False)

    # TXT + MD writers
    def write_report(path, md=False):
        with open(path, "w") as f:

            if md:
                f.write(f"# NFL WEEK {week} ADVANCED BETTING ANALYSIS\n")
            else:
                f.write(f"NFL WEEK {week} ADVANCED BETTING ANALYSIS\n")

            f.write(
                f"Generated: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p ET')}\n\n"
            )

            f.write("DATA HEALTH CHECK\n" + "-"*60 + "\n")
            f.write(f"Referees: {'✔' if not referees.empty else '✖'}\n")
            f.write(f"Queries:  {'✔' if not queries.empty else '✖'}\n")
            f.write(f"SDQL:     {'✔' if not sdql.empty else '✖'}\n")
            f.write(f"Sharp:    {'✔ ' + action_file if not action.empty else '✖'}\n")
            f.write(f"Rotowire: {'✔ ' + rotowire_file if not rotowire.empty else '✖'}\n\n")

            for g in results:
                f.write(f"{'### ' if md else ''}{g['matchup']}\n")
                f.write(f"Time: {g['game_time']}\n")
                f.write(f"Classification: {g['classification']}\n")
                if g['spread']:
                    f.write(f"Spread: {g['spread']}\n")
                f.write("\n")

                f.write("Referee:\n")
                f.write(f"• ATS: {g['ref_ats_pct']}%\n\n")

                f.write("Sharp Money:\n")
                f.write(f"• Edge: {g['sharp_edge']:+.1f}%\n")
                f.write(f"• Public Bets: {g['public_pct']:.1f}%\n\n")

                f.write("Injuries:\n")
                if g["injury_notes"]:
                    for n in g["injury_notes"]:
                        f.write(f"• {n}\n")
                else:
                    f.write("• None\n")
                f.write("\n")

                f.write("Weather:\n")
                if g["weather_notes"]:
                    for n in g["weather_notes"]:
                        f.write(f"• {n}\n")
                else:
                    f.write("• None\n")
                f.write("\n")

                f.write("Scores:\n")
                f.write(f"• Total Score: {g['score']}\n")
                f.write(f"• Ref Score: {g['ref_score']}\n")
                f.write(f"• Sharp Score: {g['sharp_score']}\n")
                f.write(f"• Public Score: {g['public_score']}\n")
                f.write(f"• Injury Score: {g['injury_score']}\n")
                f.write(f"• Weather Score: {g['weather_score']}\n")

                f.write("\n" + "-"*60 + "\n\n")

    write_report(txt)
    write_report(md, md=True)

    print(f"✓ TXT saved:   {txt}")
    print(f"✓ MD saved:    {md}")
    print(f"✓ JSON saved:  {jsonf}")
    print(f"✓ CSV saved:   {csv}")

    return True


# ================================================================
# CLI ENTRYPOINT
# ================================================================

if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_enhanced_report(week)
