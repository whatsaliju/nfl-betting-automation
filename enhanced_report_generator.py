#!/usr/bin/env python3
"""
Enhanced NFL Betting Report Generator
Combines all data sources into one intelligent report with flagging system
"""

import pandas as pd
from datetime import datetime
import os

def calculate_sharp_edge(row):
    """Calculate sharp money edge from Action Network data"""
    try:
        money_pct = float(row.get('money_pct', 0))
        bets_pct = float(row.get('bets_pct', 0))
        return money_pct - bets_pct
    except:
        return 0

def get_recommendation(ats_pct, sharp_edge, ref_ats, injuries, weather):
    """Generate betting recommendation based on all factors"""
    
    score = 0
    reasons = []
    risks = []
    
    # Referee trend
    if ref_ats >= 60:
        score += 3
        reasons.append(f"Strong referee trend ({ref_ats}% ATS)")
    elif ref_ats >= 55:
        score += 2
        reasons.append(f"Solid referee trend ({ref_ats}% ATS)")
    elif ref_ats <= 40:
        score -= 2
        risks.append(f"Poor referee trend ({ref_ats}% ATS)")
    
    # Sharp money edge
    if abs(sharp_edge) >= 5:
        if sharp_edge > 0:
            score += 3
            reasons.append(f"Large sharp money edge (+{sharp_edge:.1f}%)")
        else:
            score -= 3
            risks.append(f"Sharp money against ({sharp_edge:.1f}%)")
    elif abs(sharp_edge) >= 3:
        if sharp_edge > 0:
            score += 2
            reasons.append(f"Moderate sharp edge (+{sharp_edge:.1f}%)")
    
    # Injuries (basic check)
    if "None" not in str(injuries) and len(str(injuries)) > 20:
        score -= 1
        risks.append("Key injuries present")
    
    # Weather
    weather_str = str(weather).lower()
    if "rain" in weather_str or "snow" in weather_str:
        if "%" in weather_str:
            try:
                precip_pct = int(weather_str.split("%")[0].split()[-1])
                if precip_pct > 50:
                    score -= 1
                    risks.append(f"Bad weather ({precip_pct}% precipitation)")
            except:
                pass
    
    # Generate recommendation
    if score >= 4:
        rec = "✅ STRONG PLAY"
        units = 2.0
        confidence = min(9, 6 + score - 4)
    elif score >= 2:
        rec = "⭐ SOLID PLAY"
        units = 1.5
        confidence = min(8, 5 + score - 2)
    elif score >= 0:
        rec = "⚠️ LEAN"
        units = 1.0
        confidence = 5
    else:
        rec = "❌ FADE"
        units = 0
        confidence = max(3, 5 + score)
    
    return {
        'recommendation': rec,
        'units': units,
        'confidence': confidence,
        'reasons': reasons,
        'risks': risks,
        'score': score
    }

def should_flag_game(game_data, analysis):
    """Determine if game should be flagged for re-analysis"""
    flags = []
    
    # Sharp edge flag
    if abs(game_data.get('sharp_edge', 0)) >= 5:
        flags.append("🔥 SHARP_EDGE")
    
    # Weather flag
    weather = str(game_data.get('weather', '')).lower()
    if 'rain' in weather or 'snow' in weather:
        try:
            precip = int([w for w in weather.split() if '%' in w][0].replace('%', ''))
            if precip > 40:
                flags.append("🌧️ WEATHER")
        except:
            pass
    
    # Injury flag
    injuries = str(game_data.get('injuries', ''))
    if 'D' in injuries or 'O' in injuries:  # Doubtful or Out
        flags.append("🚑 KEY_INJURY")
    
    # Line movement flag (if available)
    # TODO: Add when we track opening lines
    
    # High confidence flag
    if analysis['confidence'] >= 8:
        flags.append("💎 HIGH_CONFIDENCE")
    
    return flags

def generate_enhanced_report(week):
    """Generate comprehensive betting report with all data sources"""
    
    print("\n" + "="*80)
    print("  GENERATING ENHANCED BETTING REPORT")
    print("="*80 + "\n")
    
    try:
        # Load all data sources
        referees = pd.read_csv(f'week{week}_referees.csv')
        queries = pd.read_csv(f'week{week}_queries.csv')
        sdql = pd.read_csv('sdql_results.csv')
        
        # Try to load optional data sources
        try:
            action = pd.read_csv([f for f in os.listdir('.') if f.startswith('action_all_markets')][0])
            has_action = False
        except:
            has_action = False
            print("⚠️ No Action Network data found")
        
        try:
            injuries = pd.read_csv([f for f in os.listdir('.') if f.startswith('rotowire_lineups')][0])
            has_injuries = True
        except:
            has_injuries = False
            print("⚠️ No RotoWire data found")
        
        # Merge referee + SDQL data
        final = queries.merge(sdql, left_on='query', right_on='query', how='left')
        
        # Add Action Network data if available
        if has_action:
            # Match by team names (approximate matching)
            for idx, row in final.iterrows():
                home = row['home']
                # Find matching Action Network row
                match = action[action['game'].str.contains(home, na=False)]
                if len(match) > 0:
                    final.loc[idx, 'sharp_edge'] = calculate_sharp_edge(match.iloc[0])
                    final.loc[idx, 'money_pct'] = match.iloc[0].get('money_pct', 0)
                    final.loc[idx, 'bets_pct'] = match.iloc[0].get('bets_pct', 0)
        
        # Add injury data if available
        if has_injuries:
            for idx, row in final.iterrows():
                home = row['home']
                away = row['away']
                match = injuries[(injuries['home'] == home) & (injuries['away'] == away)]
                if len(match) > 0:
                    final.loc[idx, 'injuries'] = match.iloc[0].get('injuries', 'None')
                    final.loc[idx, 'weather'] = match.iloc[0].get('weather', '')
                    final.loc[idx, 'game_time'] = match.iloc[0].get('game_time', '')
        
        # Generate enhanced report
        report_file = f'week{week}_enhanced_report.txt'
        flagged_games = []
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"NFL WEEK {week} COMPLETE BETTING ANALYSIS\n")
            f.write(f"Generated: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p ET')}\n")
            f.write("="*80 + "\n\n")
            
            # Process each game
            for _, row in final.iterrows():
                # Parse ATS percentage
                try:
                    ats_pct = float(str(row.get('ats_pct', '0')).replace('%', ''))
                except:
                    ats_pct = 0
                
                # Get recommendation
                analysis = get_recommendation(
                    ats_pct=ats_pct,
                    sharp_edge=row.get('sharp_edge', 0),
                    ref_ats=ats_pct,
                    injuries=row.get('injuries', 'None'),
                    weather=row.get('weather', '')
                )
                
                # Check if should be flagged
                flags = should_flag_game(row.to_dict(), analysis)
                
                # Write game section
                game_time = row.get('game_time', '')
                f.write(f"🏈 {row['matchup'].upper()}")
                if game_time:
                    f.write(f" ({game_time})")
                f.write("\n\n")
                
                f.write(f"REFEREE: {row['referee']}\n")
                if pd.notna(row.get('ats_record')):
                    f.write(f"├─ ATS Record: {row['ats_record']} ({row['ats_pct']})\n")
                    f.write(f"├─ SU Record: {row['su_record']} ({row['su_pct']})\n")
                    f.write(f"└─ O/U Record: {row['ou_record']} ({row['ou_pct']})\n")
                else:
                    f.write("└─ No historical data available\n")
                
                f.write(f"\nBETTING LINES:\n")
                f.write(f"├─ Spread: {row['home']} {row['spread']:+.1f}\n")
                
                if has_action and pd.notna(row.get('sharp_edge')):
                    edge = row['sharp_edge']
                    symbol = "✅" if abs(edge) >= 3 else "⚠️"
                    f.write(f"└─ Sharp Money: {edge:+.1f}% edge {symbol}\n")
                else:
                    f.write(f"└─ Sharp Money: Not available\n")
                
                if has_injuries:
                    f.write(f"\nINJURIES:\n")
                    injuries_str = str(row.get('injuries', 'None'))
                    if injuries_str == 'None':
                        f.write(f"└─ No key injuries reported\n")
                    else:
                        for inj in injuries_str.split(', ')[:5]:  # Limit to top 5
                            f.write(f"├─ {inj}\n")
                
                if has_injuries and pd.notna(row.get('weather')):
                    f.write(f"\nWEATHER: {row['weather']}\n")
                
                # Recommendation
                f.write(f"\n🎯 RECOMMENDATION: {analysis['recommendation']}\n")
                if analysis['units'] > 0:
                    f.write(f"   Unit Size: {analysis['units']:.1f} units\n")
                
                if analysis['reasons']:
                    f.write(f"   Reasoning:\n")
                    for reason in analysis['reasons']:
                        f.write(f"   • {reason}\n")
                
                if analysis['risks']:
                    f.write(f"\n⚠️ RISK FACTORS:\n")
                    for risk in analysis['risks']:
                        f.write(f"   • {risk}\n")
                
                f.write(f"\n📊 CONFIDENCE: {analysis['confidence']}/10\n")
                
                # Flags
                if flags:
                    f.write(f"\n🚩 FLAGS: {' '.join(flags)}\n")
                    flagged_games.append({
                        'game': row['matchup'],
                        'flags': flags,
                        'time': game_time
                    })
                
                f.write("\n" + "-"*80 + "\n\n")
            
            # Summary section
            f.write("\n" + "="*80 + "\n")
            f.write("SUMMARY\n")
            f.write("="*80 + "\n\n")
            
            strong_plays = final[final.apply(lambda r: get_recommendation(
                float(str(r.get('ats_pct', '0')).replace('%', '')),
                r.get('sharp_edge', 0),
                float(str(r.get('ats_pct', '0')).replace('%', '')),
                r.get('injuries', 'None'),
                r.get('weather', '')
            )['recommendation'] == '✅ STRONG PLAY', axis=1)]
            
            f.write(f"✅ STRONG PLAYS: {len(strong_plays)}\n")
            for _, play in strong_plays.iterrows():
                f.write(f"   • {play['matchup']}\n")
            
            if flagged_games:
                f.write(f"\n🔥 FLAGGED FOR RE-ANALYSIS: {len(flagged_games)}\n")
                for game in flagged_games:
                    f.write(f"   • {game['game']} ({game['time']}) - {', '.join(game['flags'])}\n")
                f.write(f"\n💡 TIP: Re-run analysis closer to game time for flagged games\n")
        
        print(f"✅ Enhanced report saved: {report_file}")
        
        # Also save CSV with all data
        final.to_csv(f'week{week}_complete_data.csv', index=False)
        print(f"✅ Complete data saved: week{week}_complete_data.csv")
        
        # Print summary to console
        print(f"\n📊 ANALYSIS SUMMARY:")
        print(f"   Total games: {len(final)}")
        print(f"   Strong plays: {len(strong_plays)}")
        print(f"   Flagged games: {len(flagged_games)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating enhanced report: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_enhanced_report(week)
