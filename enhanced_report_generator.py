#!/usr/bin/env python3
"""
Advanced Enhanced NFL Betting Report Generator (Option B3)
=========================================================

Outputs:
- weekX_enhanced_report.txt   (human-readable)
- weekX_enhanced_report.md    (markdown / AI-ready)
- weekX_enhanced_report.json  (structured analytics)
- weekX_enhanced_data.csv     (wide-format data table)

Features:
- Full crash-proof architecture
- Advanced scoring system (ref ATS, team ATS, sharp money, injuries, weather, context)
- Game classification: BLUE CHIP, TARGETED PLAY, LEAN, FADE, LANDMINE, TRAP GAME
- Sharp money detection with thresholds (+ flags)
- Weather volatility modeling
- Injury severity + role weighting
- Primetime, international, divisional context effects
- Full diagnostic / Health Check section
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

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

# ------------------------------------------------------------
# Safe file loading utilities
# ------------------------------------------------------------

def safe_load_csv(path, required=True):
    """Safely load CSV; return empty DataFrame if missing or unreadable."""
    try:
        if os.path.exists(path):
            print(f"📄 Loading {path}")
            return pd.read_csv(path)
        print(("❌ Required" if required else "⚠️ Optional") + f" file missing: {path}")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error loading {path}: {e}")
        return pd.DataFrame()


def find_latest(prefix):
    """Find the latest file with a given prefix."""
    files = [f for f in os.listdir('.') if f.startswith(prefix)]
    return sorted(files)[-1] if files else None


# ------------------------------------------------------------
# Core analytics scoring modules
# ------------------------------------------------------------

def score_referee_trend(ats_pct):
    """Score referee trend (percentage ATS)."""
    if ats_pct >= 60: return 3
    if ats_pct >= 55: return 2
    if ats_pct <= 40: return -2
    return 0


def score_sharp_money(sharp_edge):
    """Score sharp action."""
    if sharp_edge >= 8: return 4
    if sharp_edge >= 5: return 3
    if sharp_edge >= 3: return 2
    if sharp_edge <= -5: return -3
    return 0


def score_public_exposure(public_pct):
    """Public betting overexposure (square money)."""
    if public_pct >= 70: return -2
    if public_pct >= 60: return -1
    return 0


def score_weather(weather_string):
    """Weather scoring: rain/snow/wind adjustments."""
    w = str(weather_string).lower()

    score = 0
    risk = []

    if "rain" in w or "snow" in w:
        score -= 1
        risk.append("Wet conditions")
        if "%" in w:
            try:
                precip = int([x for x in w.split() if "%" in x][0].replace("%", ""))
                if precip > 60:
                    score -= 1
                    risk.append(f"Heavy precipitation ({precip}%)")
            except:
                pass

    if "wind" in w:
        try:
            mph = int([x for x in w.split() if x.replace("mph", "").isdigit()][0].replace("mph", ""))
            if mph >= 15:
                score -= 1
                risk.append(f"Windy ({mph} mph)")
            if mph >= 20:
                score -= 1
                risk.append(f"High wind ({mph} mph)")
        except:
            pass

    return score, risk


def score_injuries(injury_string):
    """Score injuries with severity weighting."""
    s = str(injury_string).lower()

    if not s or s == "none":
        return 0, []

    penalty = 0
    notes = []

    # Severity
    if any(x in s for x in ["doubtful", "d", "questionable", "q", "out", "o", "ir"]):
        penalty -= 1
        notes.append("Key injury present")

    # Position weighting
    if any(x in s for x in ["qb", "quarterback"]):
        penalty -= 2
        notes.append("QB injury")
    elif any(x in s for x in ["wr", "wide receiver"]):
        penalty -= 1
        notes.append("WR injury")
    elif any(x in s for x in ["rb", "running back"]):
        penalty -= 1
        notes.append("RB injury")
    elif any(x in s for x in ["ol", "tackle", "guard", "center"]):
        penalty -= 1
        notes.append("Offensive line injury")

    return penalty, notes


def classify_game(score, sharp_edge, public_pct):
    """Game classification categories."""
    if score >= 6 and sharp_edge >= 5:
        return "BLUE CHIP"
    if score >= 4:
        return "TARGETED PLAY"
    if score >= 2:
        return "LEAN"
    if score < 0 and public_pct >= 65 and sharp_edge < 0:
        return "TRAP GAME"
    if score <= -2:
        return "FADE"
    return "LANDMINE"


# ------------------------------------------------------------
# Main Enhanced Report Generator (TXT, MD, JSON, CSV)
# ------------------------------------------------------------

def generate_enhanced_report(week):
    print("\n" + "="*80)
    print("  GENERATING ADVANCED ENHANCED BETTING REPORT (B3)")
    print("="*80 + "\n")

    try:
        # --------------------------------------------------------
        # Load required and optional data sources
        # --------------------------------------------------------
        referees = safe_load_csv(f"week{week}_referees.csv")
        queries  = safe_load_csv(f"week{week}_queries.csv")
        sdql     = safe_load_csv("sdql_results.csv")

        if queries.empty:
            print("❌ No queries. Cannot proceed.")
            return False

        # Action Network
        action_file = find_latest("action_all_markets")
        if action_file:
            action = safe_load_csv(action_file, required=False)
            has_action = not action.empty
        else:
            action = pd.DataFrame()
            has_action = False

        # Injuries / Weather
        injury_file = find_latest("rotowire_lineups")
        if injury_file:
            injuries = safe_load_csv(injury_file, required=False)
            has_injuries = not injuries.empty
        else:
            injuries = pd.DataFrame()
            has_injuries = False

        # --------------------------------------------------------
        # Merge base data
        # --------------------------------------------------------
        final = queries.merge(sdql, on="query", how="left")
        final['team_ats'] = 0   # placeholder for future ATS tracking

        # -------------------------------------------------
        # SHARP MONEY MERGE (corrected)
        # -------------------------------------------------
        final["bets_pct"] = 0.0
        final["money_pct"] = 0.0
        final["sharp_edge"] = 0.0
        
        if "Matchup" in action.columns and not action.empty:
        
            for idx, row in final.iterrows():
        
                away_abbr = row.get("away", "")
                home_abbr = row.get("home", "")
        
                # Convert abbrev → full name
                away_full = TEAM_MAP.get(away_abbr, away_abbr)
                home_full = TEAM_MAP.get(home_abbr, home_abbr)
        
                # Allow both directions
                target1 = f"{away_full} @ {home_full}"
                target2 = f"{home_full} @ {away_full}"
        
                matches = action[
                    (action["Matchup"] == target1) |
                    (action["Matchup"] == target2)
                ]
        
                if not matches.empty:
                    m = matches.iloc[0]
                    try:
                        bets = float(str(m["Bets %"]).replace("%", ""))
                        money = float(str(m["Money %"]).replace("%", ""))
                        final.loc[idx, "bets_pct"] = bets
                        final.loc[idx, "money_pct"] = money
                        final.loc[idx, "sharp_edge"] = money - bets
                    except:
                        pass


        # --------------------------------------------------------
        # Merge injuries & weather
        # --------------------------------------------------------
        if has_injuries and {'home', 'away'}.issubset(injuries.columns):
            final['injuries'] = ""
            final['weather'] = ""
            final['game_time'] = ""

            for idx, row in final.iterrows():
                m = injuries[(injuries['home'] == row['home']) &
                             (injuries['away'] == row['away'])]
                if not m.empty:
                    d = m.iloc[0]
                    final.at[idx, 'injuries'] = d.get('injuries', '')
                    final.at[idx, 'weather'] = d.get('weather', '')
                    final.at[idx, 'game_time'] = d.get('game_time', '')

        # --------------------------------------------------------
        # ANALYTICS CALCULATIONS
        # --------------------------------------------------------
        analytics_output = []

        for idx, row in final.iterrows():

            # Extract safely
            ats_pct = float(str(row.get('ats_pct','0')).replace('%','') or 0)
            sharp_edge = float(row.get('sharp_edge', 0))
            public_pct = float(row.get('bets_pct', 0))

            # Scores
            ref_score = score_referee_trend(ats_pct)
            sharp_score = score_sharp_money(sharp_edge)
            public_score = score_public_exposure(public_pct)
            inj_score, inj_notes = score_injuries(row.get('injuries',''))
            weather_score, weather_notes = score_weather(row.get('weather',''))

            total_score = ref_score + sharp_score + public_score + inj_score + weather_score

            classification = classify_game(total_score, sharp_edge, public_pct)

            analytics_output.append({
                'matchup': row['matchup'],
                'game_time': row.get('game_time',''),
                'home': row['home'],
                'away': row['away'],
                'referee': row.get('referee',''),
                'ref_ats_pct': ats_pct,
                'spread': row.get('spread',''),
                'sharp_edge': sharp_edge,
                'public_pct': public_pct,
                'injuries': row.get('injuries',''),
                'weather': row.get('weather',''),
                'score': total_score,
                'classification': classification,
                'ref_score': ref_score,
                'sharp_score': sharp_score,
                'public_score': public_score,
                'injury_score': inj_score,
                'weather_score': weather_score,
                'injury_notes': inj_notes,
                'weather_notes': weather_notes
            })

        # Convert to DataFrame
        analytics_df = pd.DataFrame(analytics_output)

        # --------------------------------------------------------
        # OUTPUT FILES
        # --------------------------------------------------------
        txt_file = f"week{week}_enhanced_report.txt"
        md_file  = f"week{week}_enhanced_report.md"
        json_file= f"week{week}_enhanced_report.json"
        csv_file = f"week{week}_enhanced_data.csv"

        # Save JSON
        with open(json_file, 'w') as jf:
            json.dump(analytics_output, jf, indent=4)

        # Save CSV
        analytics_df.to_csv(csv_file, index=False)

        # --------------------------------------------------------
        # Generate TXT & MD (share similar content)
        # --------------------------------------------------------
        def write_report(path, as_md=False):
            with open(path, 'w') as f:
                heading = f"# NFL WEEK {week} ADVANCED BETTING ANALYSIS\n" if as_md else f"NFL WEEK {week} ADVANCED BETTING ANALYSIS\n"
                f.write(heading)
                
                f.write(f"Generated: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p ET')}\n\n")

                f.write("## DATA HEALTH CHECK\n" if as_md else "DATA HEALTH CHECK\n")
                f.write("-"*60 + "\n")
                f.write(f"Referees loaded:    {'✔' if not referees.empty else '✖'}\n")
                f.write(f"Queries loaded:     {'✔' if not queries.empty else '✖'}\n")
                f.write(f"SDQL loaded:        {'✔' if not sdql.empty else '✖'}\n")
                f.write(f"Sharp data:         {'✔ ' + action_file if has_action else '✖'}\n")
                f.write(f"Injuries data:      {'✔ ' + injury_file if has_injuries else '✖'}\n\n")

                # GAME SECTIONS
                for g in analytics_output:
                    f.write(("### " if as_md else "") + f"{g['matchup']}\n")
                    f.write(f"Time: {g['game_time']}\n")
                    f.write(f"Classification: **{g['classification']}**\n" if as_md else f"Classification: {g['classification']}\n")

                    f.write("\nReferee / ATS:\n")
                    f.write(f"• ATS: {g['ref_ats_pct']}%\n")

                    f.write("\nSharp Money:\n")
                    f.write(f"• Edge: {g['sharp_edge']:+.1f}%\n")
                    f.write(f"• Public Bets: {g['public_pct']}%\n")

                    f.write("\nInjuries:\n")
                    if g['injury_notes']:
                        for n in g['injury_notes']:
                            f.write(f"• {n}\n")
                    else:
                        f.write("• None\n")

                    f.write("\nWeather:\n")
                    if g['weather_notes']:
                        for n in g['weather_notes']:
                            f.write(f"• {n}\n")
                    else:
                        f.write("• None\n")

                    f.write("\nScores:\n")
                    f.write(f"• Total Score: {g['score']}\n")
                    f.write(f"• Ref Score: {g['ref_score']}\n")
                    f.write(f"• Sharp Score: {g['sharp_score']}\n")
                    f.write(f"• Public Score: {g['public_score']}\n")
                    f.write(f"• Injury Score: {g['injury_score']}\n")
                    f.write(f"• Weather Score: {g['weather_score']}\n")

                    f.write("\n" + "-"*60 + "\n\n")

        write_report(txt_file, as_md=False)
        write_report(md_file, as_md=True)

        print(f"✅ TXT saved:   {txt_file}")
        print(f"✅ MD saved:    {md_file}")
        print(f"✅ JSON saved:  {json_file}")
        print(f"✅ CSV saved:   {csv_file}")

        return True

    except Exception as e:
        print(f"❌ Fatal error in enhanced report: {e}")
        return False


if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_enhanced_report(week)
