#!/usr/bin/env python3
"""
Query Generator V2 - Uses Action Network CSV instead of Odds API
Reads spreads from action_all_markets_*.csv (already scraped)
No external API calls needed!
"""

import pandas as pd
import warnings
import os
import re
warnings.filterwarnings('ignore')

# Team abbreviations mapping
TEAM_MAP = {
    'Raiders': 'LV', 'Broncos': 'DEN', 'Falcons': 'ATL', 'Colts': 'IND',
    'Saints': 'NO', 'Panthers': 'CAR', 'Giants': 'NYG', 'Bears': 'CHI',
    'Jaguars': 'JAX', 'Texans': 'HOU', 'Bills': 'BUF', 'Dolphins': 'MIA',
    'Ravens': 'BAL', 'Vikings': 'MIN', 'Browns': 'CLE', 'Jets': 'NYJ',
    'Patriots': 'NE', 'Buccaneers': 'TB', 'Cardinals': 'ARI', 'Seahawks': 'SEA',
    'Rams': 'LAR', '49ers': 'SF', 'Lions': 'DET', 'Commanders': 'WAS',
    'Steelers': 'PIT', 'Chargers': 'LAC', 'Eagles': 'PHI', 'Packers': 'GB',
    'Chiefs': 'KC', 'Bengals': 'CIN', 'Titans': 'TEN', 'Cowboys': 'DAL'
}

# Reverse mapping: Full name -> Abbreviation
TEAM_FULL_TO_ABBR = {
    'Patriots': 'NE', 'Jets': 'NYJ', 'Commanders': 'WAS', 'Dolphins': 'MIA',
    'Panthers': 'CAR', 'Falcons': 'ATL', 'Buccaneers': 'TB', 'Bills': 'BUF',
    'Chargers': 'LAC', 'Jaguars': 'JAX', 'Bears': 'CHI', 'Vikings': 'MIN',
    'Packers': 'GB', 'Giants': 'NYG', 'Bengals': 'CIN', 'Steelers': 'PIT',
    'Texans': 'HOU', 'Titans': 'TEN', '49ers': 'SF', 'Cardinals': 'ARI',
    'Seahawks': 'SEA', 'Rams': 'LAR', 'Ravens': 'BAL', 'Browns': 'CLE',
    'Chiefs': 'KC', 'Broncos': 'DEN', 'Lions': 'DET', 'Eagles': 'PHI',
    'Cowboys': 'DAL', 'Raiders': 'LV'
}

# Division mappings
DIVISIONS = {
    'AFC East': ['BUF', 'MIA', 'NE', 'NYJ'],
    'AFC North': ['BAL', 'CIN', 'CLE', 'PIT'],
    'AFC South': ['HOU', 'IND', 'JAX', 'TEN'],
    'AFC West': ['DEN', 'KC', 'LAC', 'LV'],
    'NFC East': ['DAL', 'NYG', 'PHI', 'WAS'],
    'NFC North': ['CHI', 'DET', 'GB', 'MIN'],
    'NFC South': ['ATL', 'CAR', 'NO', 'TB'],
    'NFC West': ['ARI', 'LAR', 'SEA', 'SF']
}

def find_latest_action_network_file():
    """Find the most recent action_all_markets_*.csv file"""
    files = [f for f in os.listdir('.') if f.startswith('action_all_markets_') and f.endswith('.csv')]
    if not files:
        raise FileNotFoundError("No action_all_markets_*.csv file found!")
    latest = sorted(files)[-1]
    print(f"📁 Using Action Network file: {latest}")
    return latest

def parse_spread_line(line_str):
    """
    Parse spread line like '-7 (-110) | +7 (-104)'
    Returns the away team spread (first number)
    """
    try:
        # Extract first spread value (away team)
        match = re.search(r'([+-]?\d+\.?\d*)', line_str)
        if match:
            return float(match.group(1))
    except:
        pass
    return 0.0

def get_action_network_spreads():
    """Read spreads from Action Network CSV"""
    print("📊 Reading spreads from Action Network CSV...")
    
    action_file = find_latest_action_network_file()
    df = pd.read_csv(action_file)
    
    # Filter to just spread market
    spread_data = df[df['Market'] == 'Spread'].copy()
    
    spreads = {}
    
    for _, row in spread_data.iterrows():
        matchup = row['Matchup']
        
        # Parse "Packers @ Giants" -> away, home
        try:
            away_full, home_full = matchup.split('@')
            away_full = away_full.strip()
            home_full = home_full.strip()
            
            # Convert to abbreviations
            away_code = TEAM_FULL_TO_ABBR.get(away_full, away_full)
            home_code = TEAM_FULL_TO_ABBR.get(home_full, home_full)
            
            # Parse spread from Line column
            away_spread = parse_spread_line(row['Line'])
            
            # Determine favorite
            # Away spread negative = away favorite
            # Away spread positive = home favorite
            if away_spread < 0:
                favorite = 'AF'
                spread_value = away_spread
            elif away_spread > 0:
                favorite = 'HF'
                spread_value = -away_spread  # Convert to home team perspective
            else:
                favorite = 'HF'  # Pick'em defaults to home
                spread_value = 0
            
            spreads[f"{away_code}@{home_code}"] = {
                'spread': spread_value,
                'favorite': favorite
            }
            
            print(f"  {away_code} @ {home_code}: {spread_value:+.1f} ({favorite})")
            
        except Exception as e:
            print(f"  ⚠️ Could not parse: {matchup} - {e}")
            continue
    
    print(f"\n✅ Found spreads for {len(spreads)} games\n")
    return spreads

def get_team_code(team_name):
    return TEAM_MAP.get(team_name, team_name)

def get_team_division(team_code):
    for div, teams in DIVISIONS.items():
        if team_code in teams:
            return div
    return None

def is_same_division(team1, team2):
    div1 = get_team_division(team1)
    div2 = get_team_division(team2)
    return div1 == div2 if (div1 and div2) else False

def is_same_conference(team1, team2):
    div1 = get_team_division(team1)
    div2 = get_team_division(team2)
    if not (div1 and div2):
        return False
    conf1 = 'AFC' if 'AFC' in div1 else 'NFC'
    conf2 = 'AFC' if 'AFC' in div2 else 'NFC'
    return conf1 == conf2

def determine_game_type(away_code, home_code):
    """Determine if game is divisional, conference, or non-division"""
    if is_same_division(away_code, home_code):
        return 'DIV'
    elif is_same_conference(away_code, home_code):
        return 'C'
    else:
        return 'NDIV'

def generate_queries(referees_csv, output_file='week11_queries.txt'):
    print(f"📋 Reading {referees_csv}...")
    df = pd.read_csv(referees_csv)
    print(f"✅ Loaded {len(df)} games\n")
    
    spreads = get_action_network_spreads()
    
    queries = []
    print("\n" + "="*90)
    
    for _, row in df.iterrows():
        away_name = row['away_team']
        home_name = row['home_team']
        referee = row['referee']
        matchup = row['matchup']
        
        away_code = get_team_code(away_name)
        home_code = get_team_code(home_name)
        
        spread_key = f"{away_code}@{home_code}"
        spread_data = spreads.get(spread_key, {'spread': 0, 'favorite': 'HF'})
        
        spread_value = spread_data['spread']
        favorite = spread_data['favorite']
        game_type = determine_game_type(away_code, home_code)
        
        query = f"'{referee}' in officials and {favorite} and {game_type} and REG and season>=2018"
        
        queries.append({
            'matchup': matchup,
            'referee': referee,
            'away': away_code,
            'home': home_code,
            'spread': spread_value,
            'favorite': favorite,
            'game_type': game_type,
            'query': query
        })
        
        print(f"{matchup:<35} | {referee:<18} | {favorite} {game_type:4} | {spread_value:+5.1f}")
    
    print("="*90)
    
    queries_df = pd.DataFrame(queries)
        
    # Extract week number from output_file (e.g., "week11_queries.txt" -> "11")
    week_num = output_file.split('week')[1].split('_')[0] if 'week' in output_file else '11'
    os.makedirs(f'data/week{week_num}', exist_ok=True)
    
    # Update paths to include data/week{X}/
    csv_file = f'data/week{week_num}/' + output_file.replace('.txt', '.csv').split('/')[-1]
    txt_file = f'data/week{week_num}/' + output_file.split('/')[-1]
    
    queries_df.to_csv(csv_file, index=False)
    with open(txt_file, 'w') as f:
        for q in queries:
            f.write(q['query'] + '\n')
    
    print(f"\n✅ Saved {len(queries)} queries to:")
    print(f"   - {txt_file}")
    print(f"   - {csv_file}")
    
    return queries_df

if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    
    generate_queries(
        referees_csv=f'week{week}_referees.csv',
        output_file=f'week{week}_queries.txt'
    )
