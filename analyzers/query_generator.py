import pandas as pd
import requests
import warnings
import os
import sys

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
        'Denver Broncos': 'DEN', 'Atlanta Falcons': 'ATL',
        'Indianapolis Colts': 'IND', 'New Orleans Saints': 'NO',
        'Carolina Panthers': 'CAR', 'New York Giants': 'NYG',
        'Chicago Bears': 'CHI', 'Jacksonville Jaguars': 'JAX',
        'Houston Texans': 'HOU', 'Buffalo Bills': 'BUF',
        'Miami Dolphins': 'MIA', 'Baltimore Ravens': 'BAL',
        'Minnesota Vikings': 'MIN', 'Cleveland Browns': 'CLE',
        'New York Jets': 'NYJ', 'New England Patriots': 'NE',
        'Tampa Bay Buccaneers': 'TB', 'Arizona Cardinals': 'ARI',
        'Seattle Seahawks': 'SEA', 'Los Angeles Rams': 'LAR',
        'San Francisco 49ers': 'SF', 'Detroit Lions': 'DET',
        'Washington Commanders': 'WAS', 'Pittsburgh Steelers': 'PIT',
        'Los Angeles Chargers': 'LAC', 'Philadelphia Eagles': 'PHI',
        'Green Bay Packers': 'GB', 'Kansas City Chiefs': 'KC',
        'Cincinnati Bengals': 'CIN', 'Tennessee Titans': 'TEN',
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
            print(f"❌ API error: {response.status_code}. Response: {response.text[:100]}...")
            return {}
        
        data = response.json()
        print(f"✅ Found {len(data)} games from API\n")
        
        spreads = {}
        for game in data:
            home = normalize_team_name(game['home_team'])
            away = normalize_team_name(game['away_team'])
            
            if game.get('bookmakers'):
                # Assuming the first bookmaker is sufficient for the spread
                first_bookmaker = game['bookmakers'][0]
                market_found = False
                
                for market in first_bookmaker.get('markets', []):
                    if market['key'] == 'spreads':
                        for outcome in market['outcomes']:
                            if normalize_team_name(outcome['name']) == home:
                                home_spread = outcome['point']
                                
                                # Determine who the favorite is
                                if home_spread < 0:
                                    # Home team is favorite (has negative spread)
                                    favorite = 'HF'
                                    spread_value = home_spread
                                elif home_spread > 0:
                                    # Away team is favorite (home has positive spread = underdog)
                                    favorite = 'AF'
                                    spread_value = -outcome['point'] # Spread is always stored as negative for favorite
                                else:
                                    # Pick 'em (defaulting to Home Favorite for 0 spread)
                                    favorite = 'HF'
                                    spread_value = 0
                                
                                spreads[f"{away}@{home}"] = {
                                    'spread': spread_value,
                                    'favorite': favorite
                                }
                                print(f"  {away} @ {home}: {spread_value:+.1f} ({favorite})")
                                market_found = True
                                break
                    if market_found:
                        break # Break from market loop
        
        return spreads
    except requests.exceptions.Timeout:
        print("❌ Error fetching spreads: Request timed out.")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching spreads (Network/HTTP): {e}")
        return {}
    except Exception as e:
        print(f"❌ Unexpected error fetching spreads: {e}")
        return {}

def determine_game_type(away_code, home_code):
    """Determine if game is divisional, conference, or non-division"""
    if is_same_division(away_code, home_code):
        return 'DIV'
    elif is_same_conference(away_code, home_code):
        return 'C'
    else:
        return 'NDIV'

def generate_queries(referees_csv, api_key, output_file):
    print(f"Reading {referees_csv}...")
    
    # Check if the input CSV exists before attempting to read
    if not os.path.exists(referees_csv):
        print(f"❌ ERROR: Input CSV file not found: {referees_csv}")
        # Return an empty DataFrame, the calling script should handle the exit
        return pd.DataFrame() 

    try:
        df = pd.read_csv(referees_csv)
    except pd.errors.EmptyDataError:
        print(f"⚠️ Warning: Input CSV file is empty: {referees_csv}")
        return pd.DataFrame()
        
    print(f"✅ Loaded {len(df)} games\n")
    
    if df.empty:
        print("⚠️ No games found in referee CSV. Skipping query generation.")
        return pd.DataFrame()
        
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
        # Default spread logic if Odds API data is missing/incomplete
        spread_data = spreads.get(spread_key, {'spread': 0, 'favorite': 'HF'})
        
        spread_value = spread_data['spread']
        favorite = spread_data['favorite']
        game_type = determine_game_type(away_code, home_code)
        
        # SDQL Query format
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
    csv_file = os.path.join('data', f'week{week_num}', output_file.replace('.txt', '.csv'))
    txt_file = os.path.join('data', f'week{week_num}', output_file)
    
    queries_df.to_csv(csv_file, index=False)
    with open(txt_file, 'w') as f:
        for q in queries:
            f.write(q['query'] + '\n')
    
    print(f"\n✅ Saved {len(queries)} queries to:")
    print(f"   - {txt_file}")
    print(f"   - {csv_file}")
    
    return queries_df

if __name__ == "__main__":
    # ODDS_API_KEY should be read from the environment set in the GitHub Actions workflow
    ODDS_API_KEY = os.getenv('ODDS_API_KEY')
    
    # CRITICAL FIX: The script was previously expecting 3 arguments 
    # but the workflow only passed 1 argument (WEEK_NUM).

    if len(sys.argv) < 2:
        print("Usage: python query_generator.py <week_number>")
        sys.exit(1)
        
    try:
        # Get the week number passed from the GitHub Actions run
        week = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid week number provided: {sys.argv[1]}. Must be an integer.")
        sys.exit(1)

    # 1. Construct the input file path based on the correct week number
    referees_csv = f'data/week{week}/week{week}_referees.csv'
    
    # 2. Construct the output base name
    output_file = f'week{week}_queries.txt' 
    
    # 3. Check for API key presence
    if not ODDS_API_KEY:
        print("❌ Error: ODDS_API_KEY not found in environment variables. Cannot fetch spreads.")
        sys.exit(1)

    # 4. Check for input file presence (it should have been created by the previous step)
    if not os.path.exists(referees_csv):
        print(f"❌ Critical Error: Input referee CSV not found: {referees_csv}. Ensure the scraping step succeeded.")
        sys.exit(1)

    # Now run the generation logic with the correct week-specific paths and API key
    generate_queries(
        referees_csv=referees_csv,
        api_key=ODDS_API_KEY, 
        output_file=output_file
    )

