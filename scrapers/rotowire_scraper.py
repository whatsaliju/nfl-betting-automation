#!/usr/bin/env python3
"""
RotoWire NFL Lineup & Injury Scraper
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import pandas as pd
import time
from datetime import datetime

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    return webdriver.Chrome(
        service=Service('/usr/bin/chromedriver'),
        options=options
    )

def scrape_lineups():
    driver = setup_driver()
    
    print("🏈 Scraping RotoWire NFL lineups...")
    
    try:
        # CORRECT URL
        driver.get("https://www.rotowire.com/football/lineups.php")
        
        # --- NEW ROBUST WAIT ---
        print("⏳ Waiting up to 30 seconds for RotoWire game cards to load...")
        try:
            # Wait 30 seconds for the main game card container to be present
            wait = WebDriverWait(driver, 30) 
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.lineup.is-nfl"))
            )
            print("✅ RotoWire page loaded dynamically.")
            
        except TimeoutException:
            print("❌ Timeout waiting for RotoWire elements. The page took too long to load.")
            driver.quit()
            return [] # Exit gracefully on failure
            
        # This line now executes only after the element is confirmed present
        game_cards = driver.find_elements(By.CSS_SELECTOR, "div.lineup.is-nfl")
        
        print(f"✅ Found {len(game_cards)} games")
        
        games = []
        
        for card in game_cards:
            try:
                game_data = {}
                
                # Game time
                try:
                    game_time = card.find_element(By.CSS_SELECTOR, "div.lineup__time").text.strip()
                    game_data["game_time"] = game_time
                except:
                    game_data["game_time"] = ""
                
                # Teams
                teams = card.find_elements(By.CSS_SELECTOR, "div.lineup__abbr")
                if len(teams) >= 2:
                    away = teams[0].text.strip()
                    home = teams[1].text.strip()
                    game_data["away"] = away
                    game_data["home"] = home
                    game_data["matchup"] = f"{away} @ {home}"
                else:
                    continue
                
                # QBs (first player in each lineup list)
                qb_elements = card.find_elements(By.CSS_SELECTOR, "li.lineup__player")
                qbs = [el for el in qb_elements if "QB" in el.text]
                
                if len(qbs) >= 2:
                    game_data["away_qb"] = qbs[0].find_element(By.TAG_NAME, "a").text.strip()
                    game_data["home_qb"] = qbs[1].find_element(By.TAG_NAME, "a").text.strip()
                else:
                    game_data["away_qb"] = ""
                    game_data["home_qb"] = ""
                
                # Injuries
                injuries = []
                player_elements = card.find_elements(By.CSS_SELECTOR, "li.lineup__player")
                
                for player in player_elements:
                    try:
                        injury_span = player.find_element(By.TAG_NAME, "span")
                        injury_marker = injury_span.text.strip()
                        if injury_marker in ['Q', 'D', 'O']:
                            player_name = player.find_element(By.TAG_NAME, "a").text.strip()
                            position = player.find_element(By.CSS_SELECTOR, "div.lineup__pos").text.strip()
                            injuries.append(f"{player_name} ({position})-{injury_marker}")
                    except:
                        pass
                
                game_data["injuries"] = ", ".join(injuries) if injuries else "None"
                
                # Weather
                try:
                    weather = card.find_element(By.CSS_SELECTOR, "div.lineup__weather-text").text.strip()
                    game_data["weather"] = weather
                except:
                    game_data["weather"] = ""
                
                # Spread and Total
                try:
                    odds_items = card.find_elements(By.CSS_SELECTOR, "div.lineup__odds-item")
                    for item in odds_items:
                        text = item.text.strip()
                        if "SPREAD" in text:
                            game_data["spread"] = text.replace("SPREAD", "").strip()
                        elif "O/U" in text:
                            game_data["total"] = text.replace("O/U", "").strip()
                except:
                    game_data["spread"] = ""
                    game_data["total"] = ""
                
                game_data["fetched"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                games.append(game_data)
                
            except Exception as e:
                print(f"⚠️ Error parsing game: {e}")
                continue
        
        driver.quit()
        
        # Save to CSV
        df = pd.DataFrame(games)
        output = f"data/rotowire_lineups_{datetime.now().strftime('%Y-%m-%d_')}.csv"
        df.to_csv(output, index=False)
        
        print(f"\n✅ Scraped {len(df)} games")
        print(f"📁 Saved to {output}")
        
        # Display summary
        print("\n📋 GAME SUMMARY:")
        for _, game in df.iterrows():
            print(f"\n{game['matchup']} ({game['game_time']})")
            print(f"  QBs: {game['away_qb']} vs {game['home_qb']}")
            if game['injuries'] != "None":
                print(f"  🚨 Injuries: {game['injuries']}")
            if game['weather']:
                print(f"  🌤️  Weather: {game['weather']}")
            if game['spread']:
                print(f"  📊 {game['spread']} | {game['total']}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return None

if __name__ == "__main__":
    scrape_lineups()
