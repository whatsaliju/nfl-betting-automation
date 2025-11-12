# action_network_scraper_split_v3_4.py
# -------------------------------------------
# Scrapes Action Network NFL Public Betting by Market Type
# Markets: Spread, Total, Moneyline
# Outputs: action_public_betting_YYYY-MM-DD.csv
# -------------------------------------------

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
import os
import sys

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

# --- Helper to scrape one market ---
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

    games = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📊 Found {len(games)} rows in {market_name}")

    for g in games:
        try:
            # Extract matchup teams
            teams = g.find_elements(By.CSS_SELECTOR, ".game-info__team--desktop span")
            if len(teams) >= 2:
                away_team = teams[0].text.strip()
                home_team = teams[1].text.strip()
                matchup = f"{away_team} @ {home_team}"
            else:
                matchup = "Unknown matchup"

            # Extract time
            try:
                game_time = g.find_element(By.CSS_SELECTOR, ".public-betting__game-status").text.strip()
            except:
                game_time = ""
        except Exception:
            matchup, game_time = "Unknown matchup", ""

        # Extract main numeric data
        tds = g.find_elements(By.TAG_NAME, "td")
        if len(tds) < 6:
            continue
        try:
            line = tds[2].text.strip()
            bets_pct = tds[3].text.strip()
            money_pct = tds[4].text.strip()
            diff = tds[5].text.strip()
        except Exception:
            continue

        rows.append({
            "Matchup": matchup,
            "Market": market_name,
            "Line": line,
            "Bets %": bets_pct,
            "Money %": money_pct,
            "Diff": diff,
            "Game Time": game_time,
            "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    return rows

# --- Dropdown container ---
container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='odds-tools-sub-nav__odds-type']")
dropdown_el = container.find_element(By.TAG_NAME, "select")
select = Select(dropdown_el)

# --- Scrape Spread / Total / Moneyline sequentially ---
all_data = []
for market_val, market_label in [("spread", "Spread"), ("total", "Total"), ("ml", "Moneyline")]:
    try:
        select.select_by_value(market_val)
        print(f"✅ Selected {market_label}")
        time.sleep(5)
        all_data.extend(scrape_current_market(market_label))
    except Exception as e:
        print(f"⚠️ Error scraping {market_label}: {e}")

driver.quit()

# --- Save combined CSV ---
df = pd.DataFrame(all_data)
output = f"action_public_betting_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)

print(f"✅ Rows scraped: {len(df)}")
print(f"📁 Saved to {output}")
print("✅ Script completed")
