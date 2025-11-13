#!/usr/bin/env python3
"""
NFL Weekly Betting Automation
Run Wednesday evening after referee assignments are posted

Usage:
    python3 nfl_weekly_analyzer.py          # Auto-detect current week
    python3 nfl_weekly_analyzer.py --week 11  # Specific week
    python3 nfl_weekly_analyzer.py --week 12  # Next week
"""

import subprocess
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import argparse

# Configuration
# GimmeTheDog / SDQL Credentials (from environment or fallback to local)
GIMMETHEDOG_EMAIL = os.getenv('GIMMETHEDOG_EMAIL')
GIMMETHEDOG_PASSWORD = os.getenv('GIMMETHEDOG_PASSWORD')

# Odds API (you might want to add this as a secret too)
ODDS_API_KEY = os.getenv('ODDS_API_KEY')

def get_current_nfl_week():
    """Auto-detect NEXT NFL week (upcoming games)"""
    season_start = datetime(2025, 9, 4)
    today = datetime.now()
    
    if today < season_start:
        return 1
    
    days_since_start = (today - season_start).days
    current_week = (days_since_start // 7) + 1
    
    # If it's Tuesday or later, analyze NEXT week
    if today.weekday() >= 1:  # Tuesday = 1
        current_week += 1
    
    return min(current_week, 18)

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def generate_final_report(week):
    """Combine all data sources into final betting report"""
    print_header("GENERATING FINAL REPORT")
    
    try:
        referees = pd.read_csv(f'week{week}_referees.csv')
        queries = pd.read_csv(f'week{week}_queries.csv')
        sdql = pd.read_csv('sdql_results.csv')
        
        # Merge
        final = queries.merge(sdql, left_on='query', right_on='query', how='left')
        
        # Generate text report
        report_file = f'week{week}_betting_report.txt'
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"NFL WEEK {week} BETTING ANALYSIS\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            for _, row in final.iterrows():
                f.write(f"\n{row['matchup']}\n")
                f.write(f"Referee: {row['referee']}\n")
                f.write(f"Spread: {row['home']} {row['spread']:+.1f}\n")
                f.write(f"Query Type: {row['favorite']} + {row['game_type']}\n")
                
                if pd.notna(row.get('ats_record')):
                    f.write(f"ATS: {row['ats_record']} ({row['ats_pct']})\n")
                    f.write(f"SU: {row['su_record']} ({row['su_pct']})\n")
                    f.write(f"OU: {row['ou_record']} ({row['ou_pct']})\n")
                    
                    # Simple recommendation logic
                    ats_pct = float(row['ats_pct'].replace('%', ''))
                    if ats_pct >= 60:
                        f.write(f"✅ STRONG PLAY - {ats_pct}% ATS\n")
                    elif ats_pct >= 55:
                        f.write(f"⭐ SOLID PLAY - {ats_pct}% ATS\n")
                    elif ats_pct <= 40:
                        f.write(f"❌ FADE - Only {ats_pct}% ATS\n")
                    else:
                        f.write(f"⚠️ NEUTRAL - {ats_pct}% ATS\n")
                else:
                    f.write("⚠️ No SDQL data found\n")
                
                f.write("-"*80 + "\n")
        
        print(f"✅ Final report saved: {report_file}")
        
        # Save CSV
        final.to_csv(f'week{week}_complete_data.csv', index=False)
        print(f"✅ Complete data saved: week{week}_complete_data.csv")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run complete weekly automation pipeline"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='NFL Weekly Betting Analyzer')
    parser.add_argument('--week', type=int, help='NFL week number (1-18)')
    args = parser.parse_args()
    
    # Determine week
    if args.week:
        week = args.week
        print(f"Using specified week: {week}")
    else:
        week = get_current_nfl_week()
        print(f"Auto-detected current NFL week: {week}")
    
    if week < 1 or week > 18:
        print(f"❌ Invalid week: {week} (must be 1-18)")
        return False
    
    print_header(f"NFL WEEK {week} AUTOMATION PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Scrape Football Zebras
    print_header(f"STEP 1/7: Scrape Week {week} Referee Assignments")
    from football_zebras_scraper import save_referees
    try:
        df = save_referees(week)
        if df is None or len(df) == 0:
            print(f"❌ Could not get Week {week} referee assignments")
            print("⚠️ They may not be posted yet. Check: https://www.footballzebras.com/category/assignments/")
            print("   (Usually posted Wednesday afternoon/evening)")
            return False
        print(f"✅ Got {len(df)} games")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Step 2: Generate queries
    print_header(f"STEP 2/7: Generate SDQL Queries for Week {week}")
    from query_generator import generate_queries
    try:
        queries_df = generate_queries(
            referees_csv=f'week{week}_referees.csv',
            api_key=ODDS_API_KEY,
            output_file=f'week{week}_queries.txt'
        )
        if len(queries_df) == 0:
            print("❌ No queries generated")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Run SDQL scraper
    print_header(f"STEP 3/7: Run SDQL Queries")
    from sdql_test import run_sdql_queries
    
    with open(f'week{week}_queries.txt', 'r') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    try:
        run_sdql_queries(
            email=GIMMETHEDOG_EMAIL,
            password=GIMMETHEDOG_PASSWORD,
            queries=queries,
            headless=True
        )
        
        if not os.path.exists('sdql_results.csv'):
            print("❌ SDQL results not found")
            return False
            
    except Exception as e:
        print(f"❌ Error running SDQL queries: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    # Step 4: Run Action Network scraper (after SDQL)
    print_header("STEP 4/7: Scrape Action Network Sharp Money")
    try:
        result = subprocess.run(['python3', 'action_network_scraper_cookies.py'], 
                              capture_output=True, 
                              text=True,
                              timeout=120)
        print(result.stdout)
        if result.returncode == 0:
            print("✅ Action Network data scraped")
        else:
            print("⚠️ Action Network scraper had issues, continuing...")
    except Exception as e:
        print(f"⚠️ Action Network failed: {e}")
        print("Continuing without sharp money data...")

    # Step 5: Scrape RotoWire Injuries
    print_header("STEP 5/7: Scrape RotoWire Lineup & Injuries")
    try:
        from rotowire_scraper import scrape_lineups
        injuries_df = scrape_lineups()
        if injuries_df is not None and len(injuries_df) > 0:
            print(f"✅ Got injury data for {len(injuries_df)} games")
        else:
            print("⚠️ No injury data scraped")
    except Exception as e:
        print(f"⚠️ RotoWire failed: {e}")
        print("Continuing without injury data...")
        
    # Step 6: Generate enhanced report
    print_header(f"STEP 6/7: Generate Enhanced Report")
    from enhanced_report_generator import generate_enhanced_report
    if not generate_enhanced_report(week):
        print("❌ Failed to generate enhanced report")
        return False
        
    # Step 7: Generate referee-only digest
    print_header(f"STEP 7/7: Generate Referee Trend Digest")
    from referee_trend_generator import generate_referee_digest
    if not generate_referee_digest(week):
        print("⚠️ Failed to generate referee digest")

    # Success!
    print_header(f"✅ WEEK {week} AUTOMATION COMPLETE!")
    print(f"\nGenerated files:")
    print(f"  📄 week{week}_referees.csv - Referee assignments")
    print(f"  📄 week{week}_queries.csv - SDQL queries with spreads")
    print(f"  📄 sdql_results.csv - Historical trends")
    print(f"  📄 week{week}_betting_report.txt - Final analysis ⭐")
    print(f"  📄 week{week}_complete_data.csv - All data combined")
    print(f"\n👉 Open week{week}_betting_report.txt for betting recommendations")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
