# action_network_scraper_fixed.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
from datetime import datetime
import os, sys

EMAIL = os.environ.get("ACTION_NETWORK_EMAIL")
PASSWORD = os.environ.get("ACTION_NETWORK_PASSWORD")

if not EMAIL or not PASSWORD:
    print("❌ Missing Action Network credentials")
    sys.exit(1)

print(f"✅ Using credentials for: {EMAIL[:3]}***@{EMAIL.split('@')[1]}")

# --- Browser setup ---
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.binary_location = "/usr/bin/chromium-browser"
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# --- Login ---
driver.get("https://www.actionnetwork.com/login")
time.sleep(3)
driver.find_element(By.NAME, "email").send_keys(EMAIL)
driver.find_element(By.NAME, "password").send_keys(PASSWORD)
driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
time.sleep(6)

# --- Navigate ---
driver.get("https://www.actionnetwork.com/nfl/public-betting")
time.sleep(5)

def extract_percentage_pairs(container):
    """Extract both percentages from a container (away | home)"""
    try:
        pct_elements = container.find_elements(By.CSS_SELECTOR, ".highlight-text__children")
        if len(pct_elements) >= 2:
            return f"{pct_elements[0].text.strip()} | {pct_elements[1].text.strip()}"
        elif len(pct_elements) == 1:
            return pct_elements[0].text.strip()
    except:
        pass
    return ""

def scrape_current_market(market_name):
    print(f"🔍 Scraping {market_name} market...")
    rows = []

    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
        )
    except TimeoutException:
        print(f"⚠️ Timeout waiting for {market_name} rows")
        return rows

    # Wait a bit more for dynamic content
    time.sleep(2)
    
    games = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📊 Found {len(games)} total rows in {market_name}")

    for idx, g in enumerate(games):
        try:
            # Skip header/promo rows
            html = g.get_attribute("innerHTML")
            if not html or "public-betting-upsell-header" in html or "FREE" in g.text:
                continue
            
            # Must have game info to be a valid game row
            game_info_elements = g.find_elements(By.CSS_SELECTOR, ".public-betting__game-info")
            if not game_info_elements:
                continue
                
            info = game_info_elements[0]
            
            # Extract game time
            try:
                game_time = info.find_element(By.CSS_SELECTOR, ".public-betting__game-status").text.strip()
            except:
                game_time = ""
            
            # Extract teams - get ALL team name elements
            teams = []
            try:
                # Try desktop view first
                team_elements = info.find_elements(By.CSS_SELECTOR, ".game-info__team--desktop span")
                teams = [t.text.strip() for t in team_elements if t.text.strip()]
                
                # If no desktop, try mobile
                if not teams:
                    team_elements = info.find_elements(By.CSS_SELECTOR, ".game-info__team--mobile span")
                    teams = [t.text.strip() for t in team_elements if t.text.strip()]
            except Exception as e:
                print(f"  ⚠️ Row {idx}: Error extracting teams: {e}")
            
            if len(teams) >= 2:
                matchup = f"{teams[0]} @ {teams[1]}"
            elif len(teams) == 1:
                matchup = teams[0]
            else:
                matchup = "Unknown"
                print(f"  ⚠️ Row {idx}: Could not extract teams")
            
            # Get all table cells
            tds = g.find_elements(By.TAG_NAME, "td")
            if len(tds) < 6:
                print(f"  ⚠️ Row {idx}: Only {len(tds)} columns found")
                continue
            
            # Extract current odds/line (column 2)
            line_text = ""
            try:
                odds_divs = tds[2].find_elements(By.CSS_SELECTOR, ".book-cell__odds")
                line_parts = []
                for odds_div in odds_divs:
                    primary = odds_div.find_elements(By.CSS_SELECTOR, ".css-1jlt5rt")
                    secondary = odds_div.find_elements(By.CSS_SELECTOR, ".book-cell__secondary")
                    if primary:
                        line_str = primary[0].text.strip()
                        if secondary:
                            line_str += f" ({secondary[0].text.strip()})"
                        line_parts.append(line_str)
                line_text = " | ".join(line_parts) if line_parts else tds[2].text.strip()
            except Exception as e:
                line_text = tds[2].text.strip()
            
            # Extract Bets % (column 3)
            bets_text = ""
            try:
                bets_container = tds[3].find_element(By.CSS_SELECTOR, ".public-betting__percents-container")
                bets_text = extract_percentage_pairs(bets_container)
            except Exception as e:
                print(f"  ⚠️ Row {idx}: Error extracting bets %: {e}")
            
            # Extract Money % (column 4)
            money_text = ""
            try:
                money_container = tds[4].find_element(By.CSS_SELECTOR, ".public-betting__percents-container")
                money_text = extract_percentage_pairs(money_container)
            except Exception as e:
                print(f"  ⚠️ Row {idx}: Error extracting money %: {e}")
            
            # Extract Diff (column 5)
            diff_text = ""
            try:
                diff_text = tds[5].text.strip()
            except:
                pass
            
            # Extract number of bets (column 6 if exists)
            num_bets = ""
            if len(tds) > 6:
                try:
                    num_bets = tds[6].text.strip()
                except:
                    pass
            
            # Only add if we have actual data
            if matchup != "Unknown" or bets_text or money_text:
                rows.append({
                    "Matchup": matchup,
                    "Market": market_name,
                    "Game Time": game_time,
                    "Line": line_text,
                    "Bets %": bets_text,
                    "Money %": money_text,
                    "Diff": diff_text,
                    "Num Bets": num_bets,
                    "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                print(f"  ✅ Row {idx}: {matchup} - Bets: {bets_text}, Money: {money_text}")
            
        except Exception as e:
            print(f"  ⚠️ Row {idx}: Unexpected error: {e}")
            continue

    print(f"✅ Extracted {len(rows)} valid games from {market_name}")
    return rows

# --- Find ALL THREE dropdowns ---
print("🔍 Looking for dropdowns...")
try:
    # Find all select elements on the page
    all_selects = driver.find_elements(By.TAG_NAME, "select")
    print(f"📋 Found {len(all_selects)} select elements")
    
    market_select = None
    sport_select = None
    week_select = None
    
    # Identify which is which by their options
    for idx, sel in enumerate(all_selects):
        options = [opt.get_attribute("value") for opt in sel.find_elements(By.TAG_NAME, "option")]
        print(f"  Select #{idx+1} with options: {options[:3]}...")  # Show first 3
        
        if "spread" in options and "total" in options:
            market_select = Select(sel)
            print("  ✅ Found MARKET dropdown (spread/total/ml)")
        elif "nfl" in options and "nba" in options:
            sport_select = Select(sel)
            print("  ✅ Found SPORT dropdown (nfl/ncaaf/etc)")
        elif "Week 1" in options or "Week 11" in options:
            week_select = Select(sel)
            print("  ✅ Found WEEK dropdown (Week 1/Week 2/etc)")
    
    if not market_select:
        print("❌ Could not find market dropdown!")
        driver.quit()
        sys.exit(1)
    
    # Set sport to NFL if sport dropdown exists
    if sport_select:
        sport_select.select_by_value("nfl")
        print("✅ Set sport to NFL")
        time.sleep(3)
    
    # Set week to current week (Week 11) if week dropdown exists
    if week_select:
        try:
            week_select.select_by_value("Week 11")
            print("✅ Set week to Week 11")
            time.sleep(3)
        except:
            # If Week 11 doesn't exist, just use whatever is selected
            current_week = week_select.first_selected_option.text
            print(f"ℹ️ Using current selection: {current_week}")
            time.sleep(3)
    
except Exception as e:
    print(f"❌ Error finding dropdowns: {e}")
    import traceback
    traceback.print_exc()
    driver.quit()
    sys.exit(1)

# --- Scrape all markets ---
all_data = []
markets = [
    ("spread", "Spread"),
    ("total", "Total"),
    ("ml", "Moneyline")
]

for val, label in markets:
    print(f"\n{'='*60}")
    print(f"🎯 Switching to {label} market")
    print(f"{'='*60}")
    try:
        market_select.select_by_value(val)
        print(f"✅ Dropdown set to: {label}")
        time.sleep(7)  # Longer wait for table to reload
        
        market_data = scrape_current_market(label)
        all_data.extend(market_data)
        
    except Exception as e:
        print(f"❌ Error scraping {label}: {e}")
        import traceback
        traceback.print_exc()

driver.quit()

# --- Save results ---
df = pd.DataFrame(all_data)
out = f"action_public_betting_{datetime.now().strftime('%Y-%m-%d_%H%M')}.csv"
df.to_csv(out, index=False)

print(f"\n{'='*60}")
print(f"📊 FINAL RESULTS")
print(f"{'='*60}")
print(f"✅ Total rows scraped: {len(df)}")
print(f"📁 Saved to: {out}")

if len(df) > 0:
    print(f"\n📋 Sample data (first 3 rows):")
    print(df.head(3).to_string())
    print(f"\n📈 Breakdown by market:")
    print(df['Market'].value_counts().to_string())
else:
    print("⚠️ No data scraped!")

print("\n✅ Script completed")
