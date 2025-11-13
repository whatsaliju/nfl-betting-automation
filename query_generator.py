import pandas as pd
import requests
import warnings
import os
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

def normalize_team_name(name):
    """Convert API team names to our abbreviations"""
    name_map = {
        'Las Vegas Raiders': 'LV', 'Oakland Raiders': 'LV',
        'Denver Broncos': 'DEN',
        'Atlanta Falcons': 'ATL',
        'Indianapolis Colts': 'IND',
        'New Orleans Saints': 'NO',
        'Carolina Panthers': 'CAR',
        'New York Giants': 'NYG',
        'Chicago Bears': 'CHI',
        'Jacksonville Jaguars': 'JAX',
        'Houston Texans': 'HOU',
        'Buffalo Bills': 'BUF',
        'Miami Dolphins': 'MIA',
        'Baltimore Ravens': 'BAL',
        'Minnesota Vikings': 'MIN',
        'Cleveland Browns': 'CLE',
        'New York Jets': 'NYJ',
        'New England Patriots': 'NE',
        'Tampa Bay Buccaneers': 'TB',
        'Arizona Cardinals': 'ARI',
        'Seattle Seahawks': 'SEA',
        'Los Angeles Rams': 'LAR',
        'San Francisco 49ers': 'SF',
        'Detroit Lions': 'DET',
        'Washington Commanders': 'WAS',
        'Pittsburgh Steelers': 'PIT',
        'Los Angeles Chargers': 'LAC',
        'Philadelphia Eagles': 'PHI',
        'Green Bay Packers': 'GB',
        'Kansas City Chiefs': 'KC',
        'Cincinnati Bengals': 'CIN',
        'Tennessee Titans': 'TEN',
        'Dallas Cowboys': 'DAL'
    }
    return name_map.get(name, name)

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

def get_odds_api_spreads(api_key):
    print("Fetching spreads from Odds API...")
    url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'spreads',
        'oddsFormat': 'american'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"❌ API error: {response.status_code}")
            return {}
        
        data = response.json()
        print(f"✅ Found {len(data)} games from API\n")
        
        spreads = {}
        for game in data:
            home = normalize_team_name(game['home_team'])
            away = normalize_team_name(game['away_team'])
            
            if game.get('bookmakers'):
                for market in game['bookmakers'][0].get('markets', []):
                    if market['key'] == 'spreads':
                        for outcome in market['outcomes']:
                            if normalize_team_name(outcome['name']) == home:
                                spread = outcome['point']
                                # Invert the spread since API gives home team perspective
                                # But we want: negative = away favorite, positive = home favorite
                                spreads[f"{away}@{home}"] = -spread  # FLIP THE SIGN
                                print(f"  {away} @ {home}: {-spread:+.1f}")
                                break
        
        return spreads
    except Exception as e:
        print(f"❌ Error fetching spreads: {e}")
        return {}

def determine_query_type(away_code, home_code, spread):
    if spread < 0:
        position = 'AF'  # Negative = away favorite
    elif spread > 0:
        position = 'HF'  # Positive = home favorite
    else:
        position = 'HF'  # Pick 'em, default to HF
    
    if is_same_division(away_code, home_code):
        game_type = 'DIV'
    elif is_same_conference(away_code, home_code):
        game_type = 'C'
    else:
        game_type = 'NDIV'
    
    return position, game_type

def generate_queries(referees_csv, api_key, output_file='week11_queries.txt'):
    print(f"Reading {referees_csv}...")
    df = pd.read_csv(referees_csv)
    print(f"✅ Loaded {len(df)} games\n")
    
    spreads = get_odds_api_spreads(api_key)
    
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
        spread = spreads.get(spread_key, 0)
        
        position, game_type = determine_query_type(away_code, home_code, spread)
        
        query = f"'{referee}' in officials and {position} and {game_type} and REG and season>=2018"
        
        queries.append({
            'matchup': matchup,
            'referee': referee,
            'away': away_code,
            'home': home_code,
            'spread': spread,
            'favorite': position,
            'game_type': game_type,
            'query': query
        })
        
        print(f"{matchup:<35} | {referee:<18} | {position} {game_type:4} | {spread:+5.1f}")
    
    print("="*90)
    
    queries_df = pd.DataFrame(queries)
    csv_file = output_file.replace('.txt', '.csv')
    queries_df.to_csv(csv_file, index=False)
    
    with open(output_file, 'w') as f:
        for q in queries:
            f.write(q['query'] + '\n')
    
    print(f"\n✅ Saved {len(queries)} queries to:")
    print(f"   - {output_file}")
    print(f"   - {csv_file}")
    
    return queries_df

if __name__ == "__main__":
    ODDS_API_KEY = os.getenv('ODDS_API_KEY', '5f3c8ca6e631e6b59c3a05c291658e22')
    
    # Allow week to be passed as command line argument
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    
    generate_queries(
        referees_csv=f'week{week}_referees.csv',
        api_key=ODDS_API_KEY,
        output_file=f'week{week}_queries.txt'
    )
