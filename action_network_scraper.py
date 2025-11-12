# action_network_scraper_v3_1.py
# -------------------------------------------
# Scrapes Action Network NFL Public Betting ("All Markets")
# Outputs: action_all_markets_YYYY-MM-DD.csv
# -------------------------------------------

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
from datetime import datetime
import os
import sys

# === Credentials ===
EMAIL = os.environ.get("ACTION_NETWORK_EMAIL")
PASSWORD = os.environ.get("ACTION_NETWORK_PASSWORD")

if not EMAIL or not PASSWORD:
    print("❌ Missing Action Network credentials")
    sys.exit(1)

print(f"✅ Using credentials for: {EMAIL[:3]}***@{EMAIL.split('@')[1]}")

# === Chrome Setup ===
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.binary_location = "/usr/bin/chromium-browser"
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# === Login ===
driver.get("https://www.actionnetwork.com/login")
time.sleep(3)
driver.find_element(By.NAME, "email").send_keys(EMAIL)
driver.find_element(By.NAME, "password").send_keys(PASSWORD)
driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
time.sleep(6)

# === Navigate to Public Betting ===
driver.get("https://www.actionnetwork.com/nfl/public-betting")
time.sleep(5)

# Scroll to trigger lazy load
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)
driver.execute_script("window.scrollTo(0, 0);")

# === Select "All Markets" ===
try:
    container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='odds-tools-sub-nav__odds-type']")
    dropdown_el = container.find_element(By.TAG_NAME, "select")
    Select(dropdown_el).select_by_value("combined")
    print("✅ Selected 'All Markets'")
    time.sleep(6)
except Exception as e:
    print("⚠️ Could not change dropdown:", e)

# === Wait for Betting Data ===
try:
    WebDriverWait(driver, 25).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".mobile-public-betting__details"))
    )
    print("✅ Betting rows visible")
except TimeoutException:
    print("⚠️ Timeout waiting for betting rows")

# === SCRAPE ===
rows = []
blocks = driver.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__details")
print(f"📊 Found {len(blocks)} full game containers")

for block in blocks:
    # --- Matchup name ---
    try:
        matchup_el = block.find_element(By.CSS_SELECTOR, "a[href*='/nfl-game/']")
        matchup = " ".join(matchup_el.text.split())
    except:
        matchup = "Unknown matchup"

    # --- Game time ---
    try:
        time_str = block.find_element(By.CSS_SELECTOR, ".mobile-public-betting__game-status").text.strip()
    except:
        time_str = ""

    # --- Percent groups (Spread / Total / Moneyline) ---
    percent_groups = block.find_elements(By.XPATH, ".//div[span[contains(@class,'mobile-public-betting__percent')]]")

    # --- Odds container (lines) ---
    odds_container = block.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__odds-container div[data-testid='book-cell__odds']")
    odds_lines = []
    for o in odds_container:
        odds_lines.append(o.text.replace("\n", " ").strip())

    for i, group in enumerate(percent_groups):
        percents = group.find_elements(By.CSS_SELECTOR, ".highlight-text__children")
        if len(percents) < 2:
            continue

        bets_pct = driver.execute_script("return arguments[0].innerText;", percents[0]).strip()
        money_pct = driver.execute_script("return arguments[0].innerText;", percents[1]).strip()

        diff = ""
        try:
            diff = str(abs(int(money_pct.strip('%')) - int(bets_pct.strip('%')))) + "%"
        except:
            pass

        # Assign market type by order
        market = ["Spread", "Total", "Moneyline"][i] if i < 3 else f"Market_{i+1}"
        line = odds_lines[i] if i < len(odds_lines) else ""

        rows.append({
            "Matchup": matchup,
            "Market": market,
            "Line": line,
            "Bets %": bets_pct,
            "Money %": money_pct,
            "Diff": diff,
            "Game Time": time_str,
            "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

driver.quit()

# === SAVE TO CSV ===
df = pd.DataFrame(rows)
output = f"action_all_markets_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)
print(f"✅ Rows scraped: {len(df)}")
print(f"📁 Saved to {output}")
print("✅ Script completed")
