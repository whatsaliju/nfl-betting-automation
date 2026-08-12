# action_network_scraper_cookies.py
# Cookie-based authentication approach
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import pandas as pd
import time
import json
import random
from datetime import datetime
import os, sys
from selenium.webdriver.common.action_chains import ActionChains

# --- Dynamic Week Number Extraction ---
if len(sys.argv) < 2:
    print("❌ Error: Week number argument missing.")
    sys.exit(1)

WEEK_NUMBER = sys.argv[1]
print(f"✅ Target Week set to: {WEEK_NUMBER}")

COOKIES_FILE = os.environ.get("ACTION_NETWORK_COOKIES", "config/action_network_cookies.json")
AN_EMAIL = os.environ.get("ACTION_NETWORK_EMAIL", "")
AN_PASSWORD = os.environ.get("ACTION_NETWORK_PASSWORD", "")

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

CHROMIUM_PATH = os.environ.get("CHROME_PATH")
CHROMEDRIVER_PATH = os.environ.get("CHROMEDRIVER_PATH")

if CHROMIUM_PATH:
    options.binary_location = CHROMIUM_PATH

if CHROMEDRIVER_PATH:
    service = Service(CHROMEDRIVER_PATH)
else:
    service = Service("/usr/bin/chromedriver") 

driver = webdriver.Chrome(service=service, options=options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

def _load_cookies():
    """Try to inject stored cookies. Returns True if file existed and loaded."""
    if not os.path.exists(COOKIES_FILE):
        return False
    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
        driver.get("https://www.actionnetwork.com")
        time.sleep(2)
        for cookie in cookies:
            if 'expiry' in cookie:
                try:
                    cookie['expiry'] = int(cookie['expiry'])
                except (ValueError, TypeError):
                    cookie.pop('expiry', None)
            cookie.setdefault('domain', '.actionnetwork.com')
            cookie.setdefault('path', '/')
            cookie.pop('sameSite', None)
            cookie.pop('httpOnly', None)
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"  ⚠️ Cookie {cookie.get('name')}: {e}")
        print(f"✅ Loaded {len(cookies)} cookies")
        return True
    except Exception as e:
        print(f"⚠️ Could not load cookies: {e}")
        return False


def _human_type(element, text, min_delay=0.05, max_delay=0.18):
    """Type text character by character with random delays to mimic human input."""
    actions = ActionChains(driver)
    actions.move_to_element(element).click().perform()
    time.sleep(random.uniform(0.3, 0.7))
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))


def _login_with_credentials(email, password):
    """Log in via the Action Network login form with human-like behaviour."""
    print(f"🔑 Attempting credential login for {email}...")
    try:
        driver.get("https://www.actionnetwork.com/login")
        # Pause as a real user would while the page loads
        time.sleep(random.uniform(2.5, 4.5))

        wait = WebDriverWait(driver, 25)
        email_input = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[placeholder*='email' i]")
        ))

        # Scroll the element into view before interacting
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", email_input)
        time.sleep(random.uniform(0.4, 0.9))

        _human_type(email_input, email)
        time.sleep(random.uniform(0.5, 1.2))

        password_input = driver.find_element(
            By.CSS_SELECTOR, "input[type='password'], input[name='password']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", password_input)
        time.sleep(random.uniform(0.3, 0.7))

        _human_type(password_input, password)
        time.sleep(random.uniform(0.8, 1.5))

        # Move mouse to submit button then click
        submit = driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
        )
        ActionChains(driver).move_to_element(submit).pause(random.uniform(0.3, 0.6)).click().perform()

        # Wait for navigation away from login page
        time.sleep(random.uniform(4.0, 6.0))

        if "login" not in driver.current_url.lower():
            print("✅ Credential login succeeded")
            return True
        print("❌ Credential login failed — still on login page")
        return False
    except Exception as e:
        print(f"❌ Credential login error: {e}")
        return False


def _is_authenticated():
    """Return True if we appear to be logged in."""
    login_xpaths = [
        "//*[contains(text(), 'Log In')]",
        "//*[contains(text(), 'Sign Up')]",
        "//button[contains(@class, 'login')]",
    ]
    for xpath in login_xpaths:
        if driver.find_elements(By.XPATH, xpath):
            return False
    return True


# ── Authentication ──────────────────────────────────────────────────────────
print("🔐 Authenticating with Action Network...")

authenticated = False

# 1) Try stored cookies first
if _load_cookies():
    driver.get("https://www.actionnetwork.com/nfl/public-betting")
    time.sleep(5)
    if _is_authenticated():
        print("✅ Cookie auth succeeded")
        authenticated = True
    else:
        print("⚠️ Cookies are expired or invalid")

# 2) Fall back to email/password credentials
if not authenticated:
    if AN_EMAIL and AN_PASSWORD:
        if _login_with_credentials(AN_EMAIL, AN_PASSWORD):
            driver.get("https://www.actionnetwork.com/nfl/public-betting")
            time.sleep(5)
            authenticated = _is_authenticated()
    else:
        print("⚠️ No ACTION_NETWORK_EMAIL/PASSWORD set — credential fallback unavailable")

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

    # The wait for rows is now handled in the main loop before calling this function
    # Small sleep to ensure all cells within the rows are populated   
    games = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📊 Found {len(games)} total rows in {market_name}")

    for idx, g in enumerate(games):
        try:
            html = g.get_attribute("innerHTML")
            # Added logging to see what's being filtered out
            if not html or "public-betting-upsell-header" in html:
                # print(f"  -> Skipping upsell/header row {idx}")
                continue
            if "FREE" in g.text:
                print(f"  -> Skipping row {idx} due to 'FREE' filter. Text: {g.text[:30]}...")
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
                # Added debug print for silent failures
                # print(f"  ⚠️ Could not extract Money % for {matchup}")
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
            
            if matchup != "Unknown":
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
            print(f"❌ Error parsing row {idx}: {e}")
            continue

    print(f"✅ Extracted {len(rows)} valid games from {market_name}")
    return rows

if not authenticated:
    print("❌ AUTHENTICATION FAILED — no valid cookies or credentials. Exiting.")
    driver.quit()
    sys.exit(1)

# Wait for the betting table to appear
print("⏳ Waiting for betting table to load...")
try:
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody"))
    )
    print("✅ Table data detected.")
except TimeoutException:
    print("❌ Timeout: authenticated but betting table didn't load.")
    driver.quit()
    sys.exit(1)

def get_action_network_week_value(week):
    """Map internal week codes to Action Network dropdown values"""
    week_upper = str(week).strip().upper()
    playoff_mapping = {
        'WC': 'Wild Card',
        'DIV': 'Divisional Round',
        'CONF': 'Conf Champ',
        'SB': 'Super Bowl',
    }
    preseason_mapping = {
        'PRE1': 'Preseason Week 1',
        'PRE2': 'Preseason Week 2',
        'PRE3': 'Preseason Week 3',
        'PRE4': 'Preseason Week 4',
    }
    if week_upper in playoff_mapping:
        return playoff_mapping[week_upper]
    if week_upper in preseason_mapping:
        return preseason_mapping[week_upper]
    return f"Week {week}"
# --- Find dropdowns ---
print("🔍 Looking for dropdowns...")
all_selects = driver.find_elements(By.TAG_NAME, "select")

market_select_element = None
sport_select = None
week_select = None

for sel in all_selects:
    options = [opt.get_attribute("value") for opt in sel.find_elements(By.TAG_NAME, "option")]
    if "spread" in options and "total" in options:
        market_select_element = sel # Store the element itself, not the Select object yet
        print("  ✅ Found MARKET dropdown element")
    elif "nfl" in options and "nba" in options:
        sport_select = Select(sel)
        print("  ✅ Found SPORT dropdown")
    elif any(x in options for x in ["Week 1", "Week 11", "Wild Card", "Divisional Round", "Conf Champ", "Super Bowl"]):
        week_select = Select(sel)
        print("  ✅ Found WEEK dropdown")

if not market_select_element:
    print("❌ Could not find market dropdown!")
    driver.quit()
    sys.exit(1)

# Set Sport and Week (your existing logic)
if sport_select:
    sport_select.select_by_value("nfl")
    time.sleep(2)
if week_select:
    try:
        week_value = get_action_network_week_value(WEEK_NUMBER)
        week_select.select_by_visible_text(week_value)
        print(f"✅ Set week to {week_value}")
        time.sleep(2)
    except:
        print(f"⚠️ Could not set week. Using default.")

# --- Scrape all markets with ROBUST WAITS ---
all_data = []
markets = [
    ("spread", "Spread"),
    ("total", "Total"),
    ("ml", "Moneyline")
]

wait = WebDriverWait(driver, 25)

for val, label in markets:
    print(f"\n{'='*60}\n🎯 Switching to {label} market\n{'='*60}")
    try:
        # 1. Get the current table body BEFORE changing the dropdown
        try:
            old_table_body = driver.find_element(By.CSS_SELECTOR, "table tbody")
        except:
            # If it's the first iteration or table is missing, just find the dropdown
            old_table_body = None

        # 2. Re-create the Select object to avoid StaleElementReferenceException
        market_select = Select(market_select_element)
        market_select.select_by_value(val)
        print(f"✅ Dropdown selection changed to: {val}")
        
        # NEW, ROBUST SYNCHRONIZATION CODE
        # We wait for an actual game element to be present, which signals data has arrived.
        print("⏳ Waiting for new table data to load...")
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr .public-betting__game-info"))
        )
        print("✅ Market data loaded dynamically.")
        
        # 5. Now it's safe to scrape
        market_data = scrape_current_market(label)
        all_data.extend(market_data)
        
    except TimeoutException:
        print(f"❌ Timeout waiting for {label} market data to load.")
    except Exception as e:
        # Important: if the market select element itself became stale, we need to find it again.
        print(f"❌ Error scraping {label}: {e}")
        if isinstance(e, StaleElementReferenceException):
            print("Re-finding dropdown element...")
            all_selects = driver.find_elements(By.TAG_NAME, "select")
            for sel in all_selects:
                opts = [opt.get_attribute("value") for opt in sel.find_elements(By.TAG_NAME, "option")]
                if "spread" in opts and "total" in opts:
                    market_select_element = sel
                    break

driver.quit()

# --- Save results (Your existing code) ---
df = pd.DataFrame(all_data)
# ... rest of your saving logic ...
out = f"data/action_all_markets_{datetime.now().strftime('%Y-%m-%d_')}.csv"
# Ensure data directory exists
os.makedirs("data", exist_ok=True)
df.to_csv(out, index=False)

print(f"\n{'='*60}\n📊 FINAL RESULTS\n{'='*60}")
print(f"✅ Total rows scraped: {len(df)}")
print(f"📁 Saved to: {out}")

if len(df) > 0:
    print(f"\n📋 Sample data (first 3 rows):")
    print(df.head(3).to_string())
    print(f"\n📈 Breakdown by market:")
    print(df['Market'].value_counts().to_string())
    money_pct_filled = df['Money %'].notna() & (df['Money %'] != '')
    print(f"\n💰 Games with Money % data: {money_pct_filled.sum()} / {len(df)}")
else:
    print("⚠️ No data scraped!")

print("\n✅ Script completed")
