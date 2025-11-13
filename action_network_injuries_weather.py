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
        
        injuries = []
        
        # Look for table rows
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            print(f"  Found {len(rows)} table rows")
            
            for row in rows:  # NO LIMIT - get all rows
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 4:
                        injuries.append({
                            'team': cells[0].text,
                            'player': cells[1].text,
                            'position': cells[2].text if len(cells) > 2 else '',
                            'status': cells[3].text if len(cells) > 3 else '',
                            'injury': cells[4].text if len(cells) > 4 else '',
                            'updated': cells[5].text if len(cells) > 5 else ''  # ADD THIS
                        })
                except Exception as e:
                    print(f"  ⚠️ Error parsing row: {e}")
                    continue
            
            print(f"  ✅ Parsed {len(injuries)} injury entries")
                    
        except Exception as e:
            print(f"  ❌ Table method failed: {e}")
        
        if len(injuries) > 0:
            df = pd.DataFrame(injuries)
            output = f"action_injuries_{datetime.now().strftime('%Y-%m-%d_')}.csv"
            df.to_csv(output, index=False)
            
            print(f"✅ Scraped {len(df)} total injury entries")
            print(f"📁 Saved to {output}")
            
            # Show sample
            print("\n📊 Sample data:")
            print(df.head(10))
            print(f"\n📊 Last entry: {df.iloc[-1]['team']} - {df.iloc[-1]['player']}")
            
            driver.quit()
            return df
        else:
            print("❌ No injury data found")
            driver.quit()
            return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return None

def scrape_weather():
    """Scrape NFL weather conditions from Action Network."""
    driver = setup_driver_with_cookies()

    print("\n🌤️  Scraping Action Network Weather Page...")
    driver.get("https://www.actionnetwork.com/nfl/weather")
    time.sleep(5)

    all_weather = []

    # -----------------------------------------------------------
    # 1. SEVERE WEATHER SECTIONS (e.g., Strong Winds)
    # -----------------------------------------------------------
    try:
        severe_sections = driver.find_elements(
            By.CSS_SELECTOR,
            "section[class*='severe-weather-category']"
        )

        print(f"  Found {len(severe_sections)} severe weather sections")

        for section in severe_sections:
            try:
                category_name = section.find_element(
                    By.CSS_SELECTOR,
                    ".severe-weather-category__title"
                ).text.strip()

                teams = section.find_elements(
                    By.CSS_SELECTOR,
                    ".severe-weather-category__team-name--desktop"
                )
                metrics = section.find_elements(
                    By.CSS_SELECTOR,
                    ".severe-weather-category__metric"
                )

                for i, team in enumerate(teams):
                    metric_text = metrics[i].text.strip() if i < len(metrics) else ""

                    all_weather.append({
                        "team": team.text.strip(),
                        "category": category_name,
                        "wind_mph": metric_text,
                        "temp": "",
                        "precip": "",
                        "conditions": "",
                        "wind_full": metric_text,
                        "is_severe": "YES"
                    })

            except:
                continue

    except Exception as e:
        print(f"  ⚠️ Severe weather block error: {e}")

    # -----------------------------------------------------------
    # 2. MAIN GAME FORECASTS
    # -----------------------------------------------------------
    try:
        forecast_rows = driver.find_elements(
            By.CSS_SELECTOR,
            ".forecast-row"
        )

        print(f"  Found {len(forecast_rows)} forecast-game rows")

        for row in forecast_rows:
            try:
                # TEAM name
                team = row.find_element(
                    By.CSS_SELECTOR,
                    ".forecast-row__team-name"
                ).text.strip()

                # Temperature + condition
                desc = row.find_element(
                    By.CSS_SELECTOR,
                    ".forecast-row__forecast-description"
                ).text.strip()  # e.g., "45°F Partly Cloudy"

                # Precipitation %
                try:
                    precip = row.find_element(
                        By.CSS_SELECTOR,
                        ".forecast-row__summarized-field"
                    ).text.strip().replace(" %", "%")
                except:
                    precip = ""

                # Wind direction + speed (e.g. "14.19 ESE")
                try:
                    wind_block = row.find_element(
                        By.CSS_SELECTOR,
                        ".css-13s1q9n"
                    ).text.strip()
                except:
                    wind_block = ""

                # Extract temp + conditions cleanly
                temp = ""
                conditions = ""

                temp_match = re.search(r"(\d+°F)", desc)
                if temp_match:
                    temp = temp_match.group(1)

                conditions = desc.replace(temp, "").strip()

                all_weather.append({
                    "team": team,
                    "category": "",
                    "wind_mph": wind_block,
                    "temp": temp,
                    "precip": precip,
                    "conditions": conditions,
                    "wind_full": wind_block,
                    "is_severe": "NO"
                })

            except Exception as e:
                print(f"  ⚠️ Error parsing row: {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Forecast block error: {e}")

    driver.quit()

    # -----------------------------------------------------------
    # SAVE TO CSV
    # -----------------------------------------------------------
    df = pd.DataFrame(all_weather)
    out = f"action_weather_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(out, index=False)

    print(f"\n✅ Weather scraped: {len(df)} entries")
    print(f"📁 Saved to {out}")

    return df


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
