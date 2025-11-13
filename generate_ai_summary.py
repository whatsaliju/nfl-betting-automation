New chat
Football Betting Project
/

enhanced_report_generator (1).py
425 lines

py


generate_ai_summary (1).py
234 lines

py


week11_ai_summary.txt
396 lines

txt


week11_enhanced_report.txt
439 lines

txt


action_all_markets_2025-11-13_.csv
47 lines

csv


rotowire_lineups_2025-11-13_.csv
32 lines

csv

why is something off in my summary reports?

Looking at your reports, I can see several issues:

Main Problems
1. Sharp Money Data Not Merging
All games show Sharp Edge: +0.0% in both reports, but your Action Network CSV clearly has spread betting data with actual percentages. The issue is in your matchup matching logic.

In action_all_markets_2025-11-13_.csv, the matchups are formatted as:

Packers @ Giants (full team names)
But your code is trying to match using abbreviated team codes from queries (e.g., GB, NYG).

2. Spread Values are Wrong
In your reports, you're showing:

Spread: NE -12.5 for Jets @ Patriots
But Action Network shows: +13 (-105) | -13 (-105)
You're using the spread from queries/SDQL, not from Action Network where your sharp money data lives.

3. Game Time Mismatch
Your Action Network CSV shows: Fri 11/14, 1:15 AM for Jets @ Patriots
But Rotowire shows: THU8:15 PM ET
Your reports show: Time: THU8:15 PM ET
This suggests the games in Action Network might be for a different week or the times are incorrectly formatted.

Quick Fixes
For the Sharp Money merge in both scripts:

The issue is in how you're comparing matchups. In generate_ai_summary.py (line 98-107), you have:

python
target1 = f"{away_full} @ {home_full}"
target2 = f"{home_full} @ {away_full}"
But Action Network uses format like "Packers @ Giants" where the away team is FIRST. Your target2 is backwards.

Solution: Change your matching logic to:

python
# In Action Network, away @ home
match = action[
    ((action["away_full"] == away_full) & (action["home_full"] == home_full))
]
Remove the reversed match since Action Network is consistent with away @ home format.

Would you like me to create corrected versions of both scripts?

yes

Fixed enhanced_report_generator.py
Code 
I've created fixed versions of both scripts. Here are the key changes:

Main Fixes
1. Sharp Money Matching
Filtered Action Network data to only "Spread" market (was pulling from all markets)
Fixed matchup comparison - Action Network uses away @ home format consistently
Removed the reversed match logic that was causing issues
Added detailed debug output to show which games matched
2. Data Parsing
Now properly parses the "60% | 40%" format from Action Network
Takes the first percentage (away team) for bets and money
Calculates sharp edge as money% - bets%
3. Spread Display
Now uses the spread from Action Network when available
Falls back to the spread from your queries/SDQL if Action Network data is missing
Stores it in a new action_spread column
4. Better Output
Added console debugging that shows:
Which games successfully matched
The sharp edge for each match
Total count of matched games
Enhanced summary file to show both public bets % and sharp money %
To Test
Run the fixed scripts and you should see output like:

🔍 Matching sharp money data...
  ✓ Jets @ Patriots: +7.0% edge
  ✓ Commanders @ Dolphins: +4.0% edge
  ...
✓ Matched 15/15 games
The sharp edge values should now be populated correctly in your reports!

i dont know if that edge is what i want? is that the differential? can we discuss

Yes, let's discuss! You're right to question this. The "edge" I calculated is the differential between where the sharp money is going vs. where the public bets are going.

Current Calculation
Sharp Edge = Money % - Bets %
What This Means
From your Action Network data, for Jets @ Patriots:

Bets %: 42% on Jets | 58% on Patriots
Money %: 49% on Jets | 51% on Patriots
Current edge = 49% - 42% = +7% (for the away team, Jets)

What This Tells You
A positive edge means sharps are putting MORE money on that team than the public is betting on them:

More money per bet = sharps/big bettors favor this side
+7% means 7% more money than expected based on bet count
A negative edge means sharps are fading that side relative to public.

Different Interpretations
What you might want instead:

Absolute Sharp Money Direction - Just show which team sharps favor?
Example: "Sharps on Jets (49% of money vs 42% of bets)"
Home Team Edge - Calculate based on home team instead of away?
Would flip the sign for some games
Favorite/Underdog Edge - Show edge relative to the spread favorite?
Both Sides - Show the differential for BOTH teams?
Jets: +7% edge
Patriots: -7% edge
Money vs Line Movement - Track if sharp money is moving the line?
Which interpretation makes most sense for your betting analysis? What are you trying to identify - fade the public spots, follow sharp money, or something else?

i dont have an intent yet but right now 7% edge not sure it's the right approach. i dont think both sides make sense since its basically the same, just flipped. neither does 2. i think we should have like #1 in a way and we have a lot of data why not look at spreads, o/u, moneyline info too how should we think about this

Great point! You have all three markets in your Action Network data. Let's think about this holistically.

What Each Market Tells You
Spread - Where is the value?
Shows which team sharps think will cover
Most important for ATS betting
Total (O/U) - Scoring environment expectation
Sharps on Over = expect shootout
Sharps on Under = expect defensive game, weather impact, etc.
Moneyline - True win probability divergence
Biggest sharp/public gaps often here
Shows when sharps think a dog will win outright
Proposed Approach
Instead of one "edge" number, let's capture sharp action across all three markets:

SHARP ANALYSIS:
Spread:
  • Sharps favor: Jets +13 (49% money vs 42% bets = +7% differential)
  • Line: Jets +13 (-105) | Patriots -13 (-105)

Total:  
  • Sharps favor: UNDER 43.5 (67% money vs 44% bets = +23% differential)
  • Line: o43.5 (-102) | u43.5 (-112)

Moneyline:
  • Sharps favor: Jets +640 (18% money vs 7% bets = +11% differential)
  • Public hammering: Patriots -800

Sharp Story: Sharps loading up on Jets side across all markets, 
            especially the total going UNDER. Classic fade-the-public setup.
Scoring System Idea
Rather than one "sharp edge" score, calculate separate signals:

Spread Sharp Score (-3 to +3)
Total Sharp Score (-3 to +3)
ML Sharp Score (-3 to +3)
Consensus Sharp Score - When all three align same direction
Thresholds:

Differential ≥15%: Strong sharp action (+3)
Differential ≥10%: Moderate (+2)
Differential ≥5%: Slight edge (+1)
Similar logic for negative (public trap)
The Question
Do you want:

All three markets analyzed separately?
A "consensus" when sharps align across markets?
Specific focus on one market (like just spread)?
Flag divergence (sharps on team to cover but UNDER the total)?
What feels most useful for your decision-making?


that's much better i think 1, 2, 4, would be good right or does 3 help too all that you shared is a good view lets think

Great! Let's think through how these work together:

The Four Elements
1. All Three Markets Analyzed Separately
Spread:    Sharps +7% on Jets +13
Total:     Sharps +23% on UNDER 43.5  
Moneyline: Sharps +11% on Jets +640
Value: Shows the complete picture. You see WHERE the value is.

2. Consensus When Sharps Align
🎯 SHARP CONSENSUS: All markets favor Jets side
   - Spread: +7% 
   - Total: +23% (UNDER)
   - ML: +11%
   
Classification: BLUE CHIP - Full sharp alignment
Value: When all three point the same direction = highest confidence plays

3. Specific Focus on One Market
This would mean only showing spread data in the main report, but having other markets available.

Value: Cleaner, simpler reports. Most bettors focus on spread anyway.

4. Flag Divergence
⚠️ SHARP DIVERGENCE DETECTED:
   - Sharps on Ravens -7.5 (spread)
   - But sharps on UNDER 39.5 (total)
   
Story: Sharps expect Ravens to win but in a low-scoring grind.
       Weather factor? Defensive matchup?
Value: This is GOLD. Divergence tells you HOW they expect the game to play out.

My Recommendation
Include #1, #2, and #4. Skip #3.

Here's why:

#1 gives you complete transparency - you see all the data
#2 identifies your highest-conviction plays automatically
#4 gives you narrative/context - it's predictive storytelling
#3 would just hide useful information
Proposed Report Structure
=== JETS @









Football Betting Project

#!/usr/bin/env python3
"""
Generate AI-Ready Summary for Manual Claude Analysis
FIXED VERSION
- Corrected sharp money matching (away @ home format)
- Better debugging output
- Spread from Action Network when available
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

    # -------------------------------------------------
    # Merge Sharp Money (FIXED)
    # -------------------------------------------------
    final["bets_pct"] = 0.0
    final["money_pct"] = 0.0
    final["sharp_edge"] = 0.0
    final["action_spread"] = ""
    
    if not action.empty and "Matchup" in action.columns:
        # Filter to just spread market
        spread_data = action[action["Market"] == "Spread"].copy()
        
        # Parse "Packers @ Giants" -> "Packers", "Giants"
        def extract_teams(s):
            try:
                parts = s.split("@")
                return parts[0].strip(), parts[1].strip()
            except:
                return "", ""
        
        spread_data[["away_full", "home_full"]] = spread_data["Matchup"].apply(
            lambda x: pd.Series(extract_teams(x))
        )
        
        print("\n🔍 Matching sharp money data...")
        matched = 0
        
        for idx, row in final.iterrows():
            away_abbr = row.get("away", "")
            home_abbr = row.get("home", "")
            
            # Convert abbrev → full name
            away_full = TEAM_MAP.get(away_abbr, away_abbr)
            home_full = TEAM_MAP.get(home_abbr, home_abbr)
            
            # Action Network format: away @ home
            matches = spread_data[
                (spread_data["away_full"] == away_full) &
                (spread_data["home_full"] == home_full)
            ]
            
            if len(matches) > 0:
                m = matches.iloc[0]
                try:
                    # Parse "60% | 40%" format
                    bets_raw = str(m["Bets %"]).split("|")
                    money_raw = str(m["Money %"]).split("|")
                    
                    # First percentage is for away team
                    away_bets = float(bets_raw[0].strip().replace("%", ""))
                    away_money = float(money_raw[0].strip().replace("%", ""))
                    
                    final.loc[idx, "bets_pct"] = away_bets
                    final.loc[idx, "money_pct"] = away_money
                    final.loc[idx, "sharp_edge"] = away_money - away_bets
                    final.loc[idx, "action_spread"] = str(m.get("Line", ""))
                    
                    matched += 1
                    print(f"  ✓ {away_full} @ {home_full}: {away_money - away_bets:+.1f}% edge")
                except Exception as e:
                    print(f"  ⚠️ Parse error for {away_full} @ {home_full}: {e}")
            else:
                print(f"  ✗ No match: {away_full} @ {home_full}")
        
        print(f"\n✓ Matched {matched}/{len(final)} games\n")

    # -------------------------------------------------
    # Merge Injuries + Weather
    # -------------------------------------------------
    final["injuries"] = ""
    final["weather"] = ""
    final["game_time"] = ""

    if not injuries.empty:
        for idx, row in final.iterrows():
            home = TEAM_MAP.get(row.get("home", ""), "")
            away = TEAM_MAP.get(row.get("away", ""), "")

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
            # Use Action Network spread if available
            spread = row.get("action_spread", "") or row.get("spread", "N/A")
            f.write(f"  Spread: {spread}\n")

            # Sharp money
            f.write("\nSHARP MONEY:\n")
            edge = row.get("sharp_edge", 0)
            bets = row.get("bets_pct", 0)
            money = row.get("money_pct", 0)
            f.write(f"  Sharp Edge: {edge:+.1f}%\n")
            f.write(f"  Public Bets: {bets:.1f}%\n")
            f.write(f"  Sharp Money: {money:.1f}%\n")

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
