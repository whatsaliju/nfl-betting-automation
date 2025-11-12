#!/usr/bin/env python3
"""
Generate AI-Ready Summary for Manual Claude Analysis
Creates a clean, comprehensive summary to paste into Claude chat
"""

import pandas as pd
import os
from datetime import datetime

def generate_ai_summary(week):
    """Create formatted summary for AI analysis"""
    
    print(f"\n🤖 Generating AI analysis summary for Week {week}...")
    
    try:
        # Load all data
        referees = pd.read_csv(f'week{week}_referees.csv')
        queries = pd.read_csv(f'week{week}_queries.csv')
        sdql = pd.read_csv('sdql_results.csv')
        
        # Optional data
        try:
            # Get the most recent action network file (the one with timestamp)
            action_files = [f for f in os.listdir('.') if f.startswith('action_all_markets') and '_' in f and not f.endswith('_2058.csv')]
            if action_files:
                action = pd.read_csv(sorted(action_files)[-1])
                has_action = True
            else:
                action = None
                has_action = False
        except:
            action = None
            has_action = False
        
        try:
            injuries = pd.read_csv([f for f in os.listdir('.') if f.startswith('rotowire_lineups')][0])
            has_injuries = True
        except:
            injuries = None
            has_injuries = False
        
        # Merge data
        final = queries.merge(sdql, left_on='query', right_on='query', how='left')
        
        # Add Action Network data
        if has_action:
            for idx, row in final.iterrows():
                home = row['home']
                away = row['away']
                # Try to match by looking for team codes in Matchup column
                match = action[action['Matchup'].str.contains(home, na=False) | action['Matchup'].str.contains(away, na=False)]
                if len(match) > 0:
                    # Parse the percentage columns (they might have % or be strings)
                    try:
                        bets_pct = str(match.iloc[0].get('Bets %', '0')).replace('%', '').strip()
                        money_pct = str(match.iloc[0].get('Money %', '0')).replace('%', '').strip()
                        final.loc[idx, 'bets_pct'] = float(bets_pct) if bets_pct else 0
                        final.loc[idx, 'money_pct'] = float(money_pct) if money_pct else 0
                        final.loc[idx, 'sharp_edge'] = final.loc[idx, 'money_pct'] - final.loc[idx, 'bets_pct']
                    except:
                        pass
        
        # Add injury/weather data
        if has_injuries:
            for idx, row in final.iterrows():
                home = row['home']
                away = row['away']
                match = injuries[(injuries['home'] == home) & (injuries['away'] == away)]
                if len(match) > 0:
                    final.loc[idx, 'injuries'] = match.iloc[0].get('injuries', 'None')
                    final.loc[idx, 'weather'] = match.iloc[0].get('weather', '')
                    final.loc[idx, 'game_time'] = match.iloc[0].get('game_time', '')
        
        # Generate summary file
        summary_file = f'week{week}_ai_summary.txt'
        
        with open(summary_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"NFL WEEK {week} - AI ANALYSIS REQUEST\n")
            f.write(f"Generated: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p ET')}\n")
            f.write("="*80 + "\n\n")
            
            f.write("INSTRUCTIONS FOR AI:\n")
            f.write("Analyze these NFL games and provide:\n")
            f.write("1. Individual game recommendations (STRONG PLAY/SOLID PLAY/LEAN/PASS/FADE)\n")
            f.write("2. Unit sizing (0.5-3.0 units per play)\n")
            f.write("3. Confidence scores (1-10)\n")
            f.write("4. Portfolio strategy for the week\n")
            f.write("5. Top 3 plays with detailed reasoning\n")
            f.write("6. Trap game warnings\n")
            f.write("7. Contrarian opportunities\n")
            f.write("8. Games to monitor for line movement/injuries\n")
            f.write("\n" + "="*80 + "\n\n")
            
            # Write each game
            for idx, row in final.iterrows():
                f.write(f"GAME #{idx + 1}: {row['matchup']}\n")
                f.write("-" * 80 + "\n")
                
                # Game time
                if pd.notna(row.get('game_time')):
                    f.write(f"Time: {row['game_time']}\n")
                
                # Referee data
                f.write(f"\nREFEREE: {row['referee']}\n")
                if pd.notna(row.get('ats_record')):
                    f.write(f"  ATS: {row['ats_record']} ({row['ats_pct']})\n")
                    f.write(f"  SU: {row['su_record']} ({row['su_pct']})\n")
                    f.write(f"  O/U: {row['ou_record']} ({row['ou_pct']})\n")
                else:
                    f.write(f"  No historical data available\n")
                
                # Betting lines
                f.write(f"\nBETTING LINES:\n")
                f.write(f"  Spread: {row['home']} {row['spread']:+.1f}\n")
                if pd.notna(row.get('total')):
                    f.write(f"  Total: {row['total']}\n")
                
                # Sharp money
                if has_action and pd.notna(row.get('sharp_edge')):
                    edge = row['sharp_edge']
                    f.write(f"\nSHARP MONEY:\n")
                    f.write(f"  Sharp Edge: {edge:+.1f}% ")
                    if abs(edge) >= 5:
                        f.write("🔥 SIGNIFICANT\n")
                    elif abs(edge) >= 3:
                        f.write("⚠️ MODERATE\n")
                    else:
                        f.write("\n")
                    f.write(f"  Public Bets: {row.get('bets_pct', 'N/A')}% on favorite\n")
                    f.write(f"  Money: {row.get('money_pct', 'N/A')}% on favorite\n")
                else:
                    f.write(f"\nSHARP MONEY: Not available\n")
                
                # Injuries
                if has_injuries:
                    injuries_str = str(row.get('injuries', 'None'))
                    f.write(f"\nINJURIES:\n")
                    if injuries_str == 'None':
                        f.write(f"  No key injuries reported\n")
                    else:
                        for inj in injuries_str.split(', '):
                            f.write(f"  • {inj}\n")
                
                # Weather
                if has_injuries and pd.notna(row.get('weather')):
                    weather = row['weather']
                    f.write(f"\nWEATHER: {weather}\n")
                    # Flag bad weather
                    if 'rain' in weather.lower() or 'snow' in weather.lower():
                        try:
                            precip = int([w for w in weather.split() if '%' in w][0].replace('%', ''))
                            if precip > 50:
                                f.write(f"  ⚠️ HIGH PRECIPITATION RISK\n")
                        except:
                            pass
                
                # Game context
                f.write(f"\nCONTEXT:\n")
                f.write(f"  Type: {row.get('game_type', 'Unknown')}\n")
                f.write(f"  Favorite: {row.get('favorite', 'Unknown')}\n")
                
                f.write("\n" + "="*80 + "\n\n")
            
            # Summary stats
            f.write("\nQUICK STATS:\n")
            f.write(f"Total games: {len(final)}\n")
            
            if has_action:
                high_edge = final[abs(final.get('sharp_edge', 0)) >= 5]
                f.write(f"Games with 5+% sharp edge: {len(high_edge)}\n")
            
            # Games with bad weather
            if has_injuries:
                bad_weather = 0
                for _, row in final.iterrows():
                    weather = str(row.get('weather', '')).lower()
                    if 'rain' in weather or 'snow' in weather:
                        try:
                            precip = int([w for w in weather.split() if '%' in w][0].replace('%', ''))
                            if precip > 40:
                                bad_weather += 1
                        except:
                            pass
                f.write(f"Games with weather concerns: {bad_weather}\n")
            
            # TNF/SNF/MNF games
            prime_time = 0
            for _, row in final.iterrows():
                game_time = str(row.get('game_time', '')).upper()
                if 'THU' in game_time or 'MON' in game_time or '8:' in game_time:
                    prime_time += 1
            f.write(f"Prime time games: {prime_time}\n")
        
        print(f"\n✅ AI summary created: {summary_file}")
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Open {summary_file}")
        print(f"   2. Copy the entire contents")
        print(f"   3. Paste into Claude chat")
        print(f"   4. Ask: 'Analyze these NFL games and provide detailed betting recommendations'")
        print(f"\n💡 TIP: You can also ask follow-up questions like:")
        print(f"   - 'Which game is the best value?'")
        print(f"   - 'Should I bet the Thursday night game?'")
        print(f"   - 'What's the contrarian play this week?'")
        print(f"   - 'How many units should I bet total?'")
        
        return summary_file
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_ai_summary(week)
