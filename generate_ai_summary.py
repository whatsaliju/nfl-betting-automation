#!/usr/bin/env python3
"""
Generate AI-Ready Summary for Manual Claude Analysis
Crash-proof, production-grade version with:
- Safe merges
- Safe optional data loading
- Full Data Health Check section
- Sharp money, injuries, weather (when available)
- No KeyErrors or crashes in GitHub Actions
"""

import pandas as pd
import os
from datetime import datetime

# ------------------------------------------------------
# SAFE CSV LOADING HELPERS
# ------------------------------------------------------

def safe_load_csv(path, required=True):
    """Load CSV safely; if missing or invalid, return empty DataFrame."""
    try:
        if os.path.exists(path):
            print(f"📄 Loading {path}")
            return pd.read_csv(path)
        if required:
            print(f"❌ Required file NOT found: {path}")
        else:
            print(f"⚠️ Optional file not found: {path}")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error loading {path}: {e}")
        return pd.DataFrame()

def find_latest(prefix):
    """Find latest file matching a prefix such as 'action_all_markets'."""
    files = [f for f in os.listdir('.') if f.startswith(prefix)]
    return sorted(files)[-1] if files else None

# ------------------------------------------------------
# MAIN SUMMARY GENERATOR
# ------------------------------------------------------

def generate_ai_summary(week):
    print(f"\n🤖 Generating AI analysis summary for Week {week}...\n")

    try:
        # =====================================================
        # LOAD REQUIRED DATA
        # =====================================================
        referees = safe_load_csv(f'week{week}_referees.csv')
        queries   = safe_load_csv(f'week{week}_queries.csv')
        sdql      = safe_load_csv('sdql_results.csv')

        if queries.empty:
            print("❌ No queries found. Cannot generate summary.")
            return None

        # =====================================================
        # OPTIONAL: ACTION NETWORK SHARP MONEY
        # =====================================================
        action_file = find_latest("action_all_markets")
        if action_file:
            action = safe_load_csv(action_file, required=False)
            has_action = not action.empty
            print(f"📊 Action Network file used: {action_file}")
        else:
            action = pd.DataFrame()
            has_action = False
            print("⚠️ No Action Network file detected.")

        # =====================================================
        # OPTIONAL: ROTOWIRE INJURIES + WEATHER
        # =====================================================
        injury_file = find_latest("rotowire_lineups")
        if injury_file:
            injuries = safe_load_csv(injury_file, required=False)
            has_injuries = not injuries.empty
            print(f"🩹 RotoWire injuries file used: {injury_file}")
        else:
            injuries = pd.DataFrame()
            has_injuries = False
            print("⚠️ No RotoWire injury file detected.")

        # =====================================================
        # MERGE SDQL INTO QUERIES
        # =====================================================
        final = queries.merge(sdql, on="query", how="left")

        # =====================================================
        # ADD SHARP MONEY (SAFE)
        # =====================================================
        if has_action and "Matchup" in action.columns:
            final['bets_pct'] = 0.0
            final['money_pct'] = 0.0
            final['sharp_edge'] = 0.0

            for idx, row in final.iterrows():
                home, away = row.get('home', ''), row.get('away', '')
                if not home or not away:
                    continue

                matches = action[
                    action['Matchup'].str.contains(home, na=False) |
                    action['Matchup'].str.contains(away, na=False)
                ]

                if len(matches) > 0:
                    m = matches.iloc[0]
                    try:
                        bets = float(str(m.get('Bets %', '0')).replace('%', '') or 0)
                        money = float(str(m.get('Money %', '0')).replace('%', '') or 0)
                        final.loc[idx, 'bets_pct'] = bets
                        final.loc[idx, 'money_pct'] = money
                        final.loc[idx, 'sharp_edge'] = money - bets
                    except:
                        pass

        # =====================================================
        # ADD INJURY + WEATHER DATA (SAFE)
        # =====================================================
        if has_injuries and {'home','away'}.issubset(injuries.columns):
            final['injuries'] = ""
            final['weather'] = ""
            final['game_time'] = ""

            for idx, row in final.iterrows():
                home, away = row.get('home'), row.get('away')
                match = injuries[(injuries['home'] == home) & (injuries['away'] == away)]
                if not match.empty:
                    m = match.iloc[0]
                    final.loc[idx, 'injuries'] = m.get('injuries', '')
                    final.loc[idx, 'weather'] = m.get('weather', '')
                    final.loc[idx, 'game_time'] = m.get('game_time', '')

        # =====================================================
        # START OUTPUT FILE
        # =====================================================
        summary_file = f"week{week}_ai_summary.txt"

        with open(summary_file, 'w') as f:

            # -------------------------------------------------
            # HEADER
            # -------------------------------------------------
            f.write("="*80 + "\n")
            f.write(f"NFL WEEK {week} - AI ANALYSIS REQUEST\n")
            f.write(f"Generated: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p ET')}\n")
            f.write("="*80 + "\n\n")

            f.write("INSTRUCTIONS FOR AI:\n")
            f.write("Provide:\n"
                    "1. Individual game recommendations & confidence\n"
                    "2. Unit sizing (0.5–3.0 units)\n"
                    "3. Sharp/public analysis\n"
                    "4. Injury/weather adjustments\n"
                    "5. Trap games & contrarian plays\n"
                    "6. Weekly betting portfolio\n")
            f.write("\n" + "="*80 + "\n\n")

            # -------------------------------------------------
            # DATA HEALTH CHECK
            # -------------------------------------------------
            f.write("DATA HEALTH CHECK\n")
            f.write("-"*80 + "\n")

            f.write(f"SDQL Results:           {'✔ (' + str(len(sdql)) + ' rows)' if not sdql.empty else '✖ Missing'}\n")
            f.write(f"Referee Assignments:    {'✔ (' + str(len(referees)) + ' games)' if not referees.empty else '✖ Missing'}\n")
            f.write(f"Query File:             {'✔ (' + str(len(queries)) + ' queries)' if not queries.empty else '✖ Missing'}\n")

            if has_action:
                f.write(f"Action Network Sharp:   ✔ Loaded ({action_file})\n")
                f.write(f"  - Bets % column:      {'✔' if 'Bets %' in action.columns else '✖'}\n")
                f.write(f"  - Money % column:     {'✔' if 'Money %' in action.columns else '✖'}\n")
            else:
                f.write("Action Network Sharp:   ✖ Missing (sharp_edge unavailable)\n")

            if has_injuries:
                matched = 0
                for _, r in queries.iterrows():
                    if not injuries[
                        (injuries['home'] == r.get('home')) &
                        (injuries['away'] == r.get('away'))
                    ].empty:
                        matched += 1

                f.write(f"RotoWire Injuries:      ✔ Loaded ({injury_file})\n")
                f.write(f"  - Games matched:      {matched} of {len(queries)}\n")
                f.write(f"Weather Data:           {'✔' if 'weather' in injuries.columns else '✖'}\n")
            else:
                f.write("RotoWire Injuries:      ✖ Missing\n")
                f.write("Weather Data:           ✖ Missing\n")

            # Missing critical columns
            critical = ['query','matchup','home','away','spread','referee']
            missing_cols = [c for c in critical if c not in final.columns]

            if missing_cols:
                f.write(f"Missing Critical Columns: {', '.join(missing_cols)}\n")
            else:
                f.write("Missing Critical Columns: None\n")

            f.write("\n" + "="*80 + "\n\n")

            # -------------------------------------------------
            # GAME-BY-GAME BREAKDOWN
            # -------------------------------------------------
            for idx, row in final.iterrows():
                f.write(f"GAME #{idx + 1}: {row.get('matchup', '')}\n")
                f.write("-"*80 + "\n")

                if row.get('game_time'):
                    f.write(f"Time: {row['game_time']}\n")

                # Referee block
                f.write(f"\nREFEREE: {row.get('referee','Unknown')}\n")
                if pd.notna(row.get('ats_record')):
                    f.write(f"  ATS: {row.get('ats_record')} ({row.get('ats_pct','')})\n")
                    f.write(f"  SU:  {row.get('su_record')} ({row.get('su_pct','')})\n")
                    f.write(f"  O/U: {row.get('ou_record')} ({row.get('ou_pct','')})\n")
                else:
                    f.write("  No historical referee data available\n")

                # Betting lines
                f.write("\nBETTING LINES:\n")
                try:
                    f.write(f"  Spread: {row['home']} {float(row['spread']):+.1f}\n")
                except:
                    f.write("  Spread: N/A\n")

                if pd.notna(row.get('total')):
                    f.write(f"  Total: {row['total']}\n")

                # Sharp money
                if has_action and 'sharp_edge' in final.columns:
                    edge = row.get('sharp_edge', 0)
                    f.write(f"\nSHARP MONEY:\n  Sharp Edge: {edge:+.1f}%\n")
                    if abs(edge) >= 5:
                        f.write("  🔥 High sharp discrepancy\n")
                else:
                    f.write("\nSHARP MONEY: Not available\n")

                # Injuries
                f.write("\nINJURIES:\n")
                inj = str(row.get('injuries',''))
                f.write("  None\n" if not inj else f"  {inj}\n")

                # Weather
                f.write("\nWEATHER:\n")
                w = str(row.get('weather',''))
                f.write("  None\n" if not w else f"  {w}\n")

                # Context
                f.write("\nCONTEXT:\n")
                f.write(f"  Type: {row.get('game_type','Unknown')}\n")
                f.write(f"  Favorite: {row.get('favorite','Unknown')}\n")

                f.write("\n" + "="*80 + "\n\n")

            # -------------------------------------------------
            # QUICK STATS SUMMARY
            # -------------------------------------------------
            f.write("\nQUICK STATS:\n")

            # Sharp edges
            if has_action and 'sharp_edge' in final.columns:
                sharp = final['sharp_edge'].fillna(0)
                high_edge = final.loc[abs(sharp) >= 5]
                f.write(f"Games with 5+% sharp edge: {len(high_edge)}\n")
            else:
                f.write("Games with 5+% sharp edge: 0\n")

            # Weather concerns
            weather_count = 0
            if has_injuries:
                for w in final.get('weather', pd.Series([])).fillna(''):
                    if any(k in w.lower() for k in ['rain','snow']):
                        weather_count += 1
            f.write(f"Games with weather concerns: {weather_count}\n")

            # Prime time
            prime = 0
            for t in final.get('game_time', pd.Series([])).fillna(''):
                if any(x in t.upper() for x in ['THU','MON','8:']):
                    prime += 1
            f.write(f"Prime time games: {prime}\n")

        print(f"✅ AI summary successfully created: {summary_file}")
        return summary_file

    except Exception as e:
        print(f"❌ Unexpected failure in generate_ai_summary: {e}")
        return None


if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_ai_summary(week)
