# action_network_scraper_cookies.py
# Cookie-based authentication approach
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
import json
from datetime import datetime
import os, sys

# Set this to your cookies JSON file path
COOKIES_FILE = os.environ.get("ACTION_NETWORK_COOKIES", "config/action_network_cookies.json")

# --- Browser setup ---
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

# Load cookies if they exist
if os.path.exists(COOKIES_FILE):
    print(f"✅ Found cookies file: {COOKIES_FILE}")
    
    # First navigate to the domain
    driver.get("https://www.actionnetwork.com")
    time.sleep(2)
    
    # Load cookies
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
    print("📝 To create cookies:")
    print("   1. Login to actionnetwork.com in Chrome")
    print("   2. Open DevTools (F12) → Application → Cookies")
    print("   3. Copy all cookies")
    print("   4. Save as JSON in action_network_cookies.json")
    print("   Or use a browser extension like 'EditThisCookie' to export")
    driver.quit()
    sys.exit(1)

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

    time.sleep(5)
    
    games = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📊 Found {len(games)} total rows in {market_name}")

    for idx, g in enumerate(games):
        try:
            html = g.get_attribute("innerHTML")
            if not html or "public-betting-upsell-header" in html or "FREE" in g.text:
                continue
            
            game_info_elements = g.find_elements(By.CSS_SELECTOR, ".public-betting__game-info")
            if not game_info_elements:
                continue
                
            info = game_info_elements[0]
            
            try:
                game_time = info.find_element(By.CSS_SELECTOR, ".public-betting__game-status").text.strip()
            except:
                game_time = ""
            
            teams = []
            try:
                team_elements = info.find_elements(By.CSS_SELECTOR, ".game-info__team--desktop span")
                teams = [t.text.strip() for t in team_elements if t.text.strip()]
                
                if not teams:
                    team_elements = info.find_elements(By.CSS_SELECTOR, ".game-info__team--mobile span")
                    teams = [t.text.strip() for t in team_elements if t.text.strip()]
            except:
                pass
            
            if len(teams) >= 2:
                matchup = f"{teams[0]} @ {teams[1]}"
            else:
                matchup = "Unknown"
            
            tds = g.find_elements(By.TAG_NAME, "td")
            if len(tds) < 6:
                continue
            
            # Line
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
            except:
                line_text = tds[2].text.strip()
            
            # Bets %
            bets_text = ""
            try:
                bets_container = tds[3].find_element(By.CSS_SELECTOR, ".public-betting__percents-container")
                bets_text = extract_percentage_pairs(bets_container)
            except:
                bets_text = tds[3].text.strip()
            
            # Money %
            money_text = ""
            try:
                money_container = tds[4].find_element(By.CSS_SELECTOR, ".public-betting__percents-container")
                money_text = extract_percentage_pairs(money_container)
            except:
                pass
            
            # Diff
            diff_text = ""
            try:
                diff_text = tds[5].text.strip()
            except:
                pass
            
            # Num bets
            num_bets = ""
            if len(tds) > 6:
                try:
                    num_bets = tds[6].text.strip()
                except:
                    pass
            
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
            
        except Exception as e:
            continue

    print(f"✅ Extracted {len(rows)} valid games from {market_name}")
    return rows

# --- Navigate with cookies ---
driver.get("https://www.actionnetwork.com/nfl/public-betting")
print("⏳ Waiting for page to load with cookies...")
time.sleep(8)

# Check authentication
try:
    login_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Log In') or contains(text(), 'Sign Up')]")
    if login_buttons:
        print("❌ Still not authenticated - cookies may be expired")
        print("💡 Please generate fresh cookies by logging in manually")
        driver.save_screenshot("debug_cookie_auth_failed.png")
        driver.quit()
        sys.exit(1)
    else:
        print("✅ Successfully authenticated with cookies!")
except:
    pass

# --- Find dropdowns ---
print("🔍 Looking for dropdowns...")
all_selects = driver.find_elements(By.TAG_NAME, "select")
print(f"📋 Found {len(all_selects)} select elements")

market_select = None
sport_select = None
week_select = None

for idx, sel in enumerate(all_selects):
    options = [opt.get_attribute("value") for opt in sel.find_elements(By.TAG_NAME, "option")]
    
    if "spread" in options and "total" in options:
        market_select = Select(sel)
        print("  ✅ Found MARKET dropdown")
    elif "nfl" in options and "nba" in options:
        sport_select = Select(sel)
        print("  ✅ Found SPORT dropdown")
    elif "Week 1" in options or "Week 11" in options:
        week_select = Select(sel)
        print("  ✅ Found WEEK dropdown")

if not market_select:
    print("❌ Could not find market dropdown!")
    driver.quit()
    sys.exit(1)

if sport_select:
    sport_select.select_by_value("nfl")
    print("✅ Set sport to NFL")
    time.sleep(3)

if week_select:
    try:
        week_select.select_by_value("Week 11")
        print("✅ Set week to Week 11")
        time.sleep(3)
    except:
        current_week = week_select.first_selected_option.text
        print(f"ℹ️ Using current selection: {current_week}")
        time.sleep(3)

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
        time.sleep(10)
        
        market_data = scrape_current_market(label)
        all_data.extend(market_data)
        
    except Exception as e:
        print(f"❌ Error scraping {label}: {e}")

driver.quit()

# --- Save results ---
df = pd.DataFrame(all_data)
out = f"data/action_all_markets_{datetime.now().strftime('%Y-%m-%d_')}.csv"
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
    
    # Check how many games have Money %
    money_pct_filled = df['Money %'].notna() & (df['Money %'] != '')
    print(f"\n💰 Games with Money % data: {money_pct_filled.sum()} / {len(df)}")
else:
    print("⚠️ No data scraped!")

print("\n✅ Script completed")
