#!/usr/bin/env python3
"""
Action Network Injury & Weather Scraper
Scrapes comprehensive injury reports and weather data
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import json
import time
from datetime import datetime
import os
import sys

def setup_driver_with_cookies():
    """Setup Chrome with Action Network cookies - same pattern as sharp money scraper"""
    
    COOKIES_FILE = os.environ.get("ACTION_NETWORK_COOKIES", "action_network_cookies.json")
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.binary_location = "/usr/bin/chromium-browser"
    
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    print("🍪 Cookie-based authentication approach")
    
    # Load cookies
    if os.path.exists(COOKIES_FILE):
        print(f"✅ Found cookies file: {COOKIES_FILE}")
        
        # First navigate to the domain
        driver.get("https://www.actionnetwork.com")
        time.sleep(2)
        
        try:
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            
            for cookie in cookies:
                # Remove fields that cause issues
                cookie.pop('sameSite', None)
                cookie.pop('httpOnly', None)
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"  ⚠️ Could not add cookie {cookie.get('name')}: {e}")
            
            print(f"✅ Loaded {len(cookies)} cookies")
        except Exception as e:
            print(f"❌ Error loading cookies: {e}")
            driver.quit()
            sys.exit(1)
    else:
        print(f"❌ Cookies file not found: {COOKIES_FILE}")
        driver.quit()
        sys.exit(1)
    
    return driver

def scrape_injuries():
    """Scrape NFL injury report"""
    driver = setup_driver_with_cookies()
    
    print("\n🏥 Scraping Action Network Injury Report...")
    
    try:
        driver.get("https://www.actionnetwork.com/nfl/injury-report")
        time.sleep(5)
        
        # Save page source for debugging
        with open('injury_page_debug.html', 'w') as f:
            f.write(driver.page_source)
        
        # Try multiple selectors to find injury data
        injuries = []
        
        # Method 1: Look for table rows
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            print(f"  Found {len(rows)} table rows")
            
            for row in rows[:50]:  # Limit to first 50 for testing
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 4:
                        injuries.append({
                            'team': cells[0].text,
                            'player': cells[1].text,
                            'position': cells[2].text if len(cells) > 2 else '',
                            'status': cells[3].text if len(cells) > 3 else '',
                            'injury': cells[4].text if len(cells) > 4 else ''
                        })
                except:
                    continue
        except:
            print("  ⚠️ Table method failed")
        
        # Method 2: Look for div-based layout
        if len(injuries) == 0:
            try:
                injury_cards = driver.find_elements(By.CSS_SELECTOR, "[class*='injury']")
                print(f"  Found {len(injury_cards)} injury cards")
                
                for card in injury_cards[:50]:
                    text = card.text
                    if text:
                        injuries.append({
                            'raw_data': text
                        })
            except:
                print("  ⚠️ Card method failed")
        
        if len(injuries) > 0:
            df = pd.DataFrame(injuries)
            output = f"action_injuries_{datetime.now().strftime('%Y-%m-%d_')}.csv"
            df.to_csv(output, index=False)
            
            print(f"✅ Scraped {len(df)} injury entries")
            print(f"📁 Saved to {output}")
            
            driver.quit()
            return df
        else:
            print("❌ No injury data found")
            print("📸 Saved page source to injury_page_debug.html")
            driver.quit()
            return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return None

def scrape_weather():
    """Scrape NFL weather conditions"""
    driver = setup_driver_with_cookies()
    
    print("\n🌤️  Scraping Action Network Weather...")
    
    try:
        driver.get("https://www.actionnetwork.com/nfl/weather")
        time.sleep(5)
        
        # Save page source for debugging
        with open('weather_page_debug.html', 'w') as f:
            f.write(driver.page_source)
        
        weather_data = []
        
        # Method 1: Look for table rows
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            print(f"  Found {len(rows)} table rows")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        weather_data.append({
                            'matchup': cells[0].text,
                            'game_time': cells[1].text if len(cells) > 1 else '',
                            'temp': cells[2].text if len(cells) > 2 else '',
                            'conditions': cells[3].text if len(cells) > 3 else '',
                            'wind': cells[4].text if len(cells) > 4 else '',
                            'forecast': cells[5].text if len(cells) > 5 else ''
                        })
                except:
                    continue
        except:
            print("  ⚠️ Table method failed")
        
        # Method 2: Look for card-based layout
        if len(weather_data) == 0:
            try:
                weather_cards = driver.find_elements(By.CSS_SELECTOR, "[class*='weather']")
                print(f"  Found {len(weather_cards)} weather cards")
                
                for card in weather_cards:
                    text = card.text
                    if text:
                        weather_data.append({
                            'raw_data': text
                        })
            except:
                print("  ⚠️ Card method failed")
        
        if len(weather_data) > 0:
            df = pd.DataFrame(weather_data)
            output = f"action_weather_{datetime.now().strftime('%Y-%m-%d_')}.csv"
            df.to_csv(output, index=False)
            
            print(f"✅ Scraped weather for {len(df)} games")
            print(f"📁 Saved to {output}")
            
            driver.quit()
            return df
        else:
            print("❌ No weather data found")
            print("📸 Saved page source to weather_page_debug.html")
            driver.quit()
            return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return None

if __name__ == "__main__":
    print("="*60)
    print("ACTION NETWORK INJURY & WEATHER SCRAPER")
    print("="*60)
    
    # Scrape injuries
    injuries_df = scrape_injuries()
    
    print()
    
    # Scrape weather
    weather_df = scrape_weather()
    
    print("\n" + "="*60)
    print("✅ Scraping complete!")
    print("="*60)
