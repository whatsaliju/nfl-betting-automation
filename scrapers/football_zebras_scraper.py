import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

def scrape_week_referees(week, year=2025):
    """
    Scrape referee assignments from Football Zebras
    Tries multiple URL formats
    """
    
    # Try different URL patterns (they're inconsistent)
    url_patterns = [
        f"https://www.footballzebras.com/{year}/11/week-{week}-referee-assignments-{year}/",
        f"https://www.footballzebras.com/{year}/10/week-{week}-referee-assignments-{year}/",
        f"https://www.footballzebras.com/{year}/09/week-{week}-referee-assignments-{year}/",
    ]
    
    print(f"Fetching Week {week} referee assignments...")
    
    for url in url_patterns:
        try:
            print(f"Trying: {url}")
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            if response.status_code == 200:
                print(f"✅ Found at: {url}")
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find the assignment list div
                assignment_div = soup.find('div', class_='assignment_list')
                
                if not assignment_div:
                    print("⚠️ Found page but no assignment_list div")
                    continue
                
                games = []
                
                # Find all game blocks
                game_blocks = assignment_div.find_all('div', class_='b_post')
                
                for block in game_blocks:
                    game_div = block.find('div', class_='b_post-game')
                    game = game_div.text.strip() if game_div else None
                    
                    ref_div = block.find('div', class_='b_post-referee')
                    referee = ref_div.text.strip() if ref_div else None
                    
                    time_div = block.find('div', class_='b_post-time')
                    game_time = time_div.text.strip() if time_div else None
                    
                    if game and referee:
                        games.append({
                            'matchup': game,
                            'referee': referee,
                            'time': game_time,
                            'week': week
                        })
                
                if len(games) > 0:
                    print(f"✅ Found {len(games)} games")
                    return pd.DataFrame(games)
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed: {e}")
            continue
    
    print(f"❌ Could not find Week {week} assignments at any URL")
    return pd.DataFrame()


def parse_matchup(matchup):
    """Parse matchup into away/home teams"""
    # Handle "at", "@", or "vs." (neutral site)
    if ' at ' in matchup:
        parts = matchup.split(' at ')
    elif ' @ ' in matchup:
        parts = matchup.split(' @ ')
    elif ' vs. ' in matchup or ' vs ' in matchup:
        # Neutral site - treat first team as "away"
        parts = matchup.replace(' vs. ', ' at ').replace(' vs ', ' at ').split(' at ')
    else:
        return None, None
    
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return None, None

def save_referees(week, output_file=None):
    """Scrape and save referee assignments to CSV"""
    df = scrape_week_referees(week)
    
    if len(df) == 0:
        print("❌ No data to save")
        return None
    
    # Parse matchups
    df[['away_team', 'home_team']] = df['matchup'].apply(
        lambda x: pd.Series(parse_matchup(x))
    )
    
    if output_file is None:
        os.makedirs(f'data/week{week}', exist_ok=True)
        output_file = f"data/week{week}/week{week}_referees.csv"  # Changed to week, added folder
    
    df.to_csv(output_file, index=False)
    print(f"📁 Saved to {output_file}")
    
    print("\n" + "="*60)
    print(f"WEEK {week} REFEREE ASSIGNMENTS")
    print("="*60)
    for _, row in df.iterrows():
        print(f"{row['matchup']:<35} → {row['referee']}")
    print("="*60)
    
    return df


if __name__ == "__main__":
    # Test with Week 10 (current week)
    week = 10
    df = save_referees(week)
    
    if df is not None:
        print(f"\n✅ SUCCESS! Week {week} data saved")
        print(f"Referees: {df['referee'].unique()}")
