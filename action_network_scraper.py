# action_network_scraper_v2.py
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

EMAIL = os.environ.get('ACTION_NETWORK_EMAIL')
PASSWORD = os.environ.get('ACTION_NETWORK_PASSWORD')

if not EMAIL or not PASSWORD:
    print("❌ Missing credentials")
    sys.exit(1)

print(f"✅ Using Action Network credentials for: {EMAIL[:3]}***@{EMAIL.split('@')[1]}")

# --- CHROME SETUP ---
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.binary_location = "/usr/bin/chromium-browser"
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# --- LOGIN ---
driver.get("https://www.actionnetwork.com/login")
time.sleep(3)
driver.find_element(By.NAME, "email").send_keys(EMAIL)
driver.find_element(By.NAME, "password").send_keys(PASSWORD)
driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
time.sleep(6)

# --- NAVIGATE ---
driver.get("https://www.actionnetwork.com/nfl/public-betting")
time.sleep(5)

# scroll to trigger lazy load
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)
driver.execute_script("window.scrollTo(0, 0);")

# --- SELECT 'ALL MARKETS' ---
try:
    container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='odds-tools-sub-nav__odds-type']")
    dropdown_el = container.find_element(By.TAG_NAME, "select")
    Select(dropdown_el).select_by_value("combined")
    print("✅ Selected 'All Markets' via dropdown")
    time.sleep(6)
except Exception as e:
    print("⚠️ Could not switch dropdown:", e)

# --- WAIT FOR RELOAD ---
try:
    WebDriverWait(driver, 25).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".mobile-public-betting__row--last"))
    )
    print("✅ Betting rows visible")
except TimeoutException:
    print("⚠️ Timeout waiting for rows")

# --- SCRAPE ---
rows = []
blocks = driver.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__row--last")

print(f"📊 Found {len(blocks)} game blocks")

for block in blocks:
    # matchup name
    try:
        matchup_link = block.find_element(By.CSS_SELECTOR, "a[href*='/nfl-game/']")
        matchup = " ".join(matchup_link.text.split())
        if not matchup:
            matchup = "Unknown matchup"
    except:
        matchup = "Unknown matchup"

    # market sections (Spread / Total / ML)
    markets = block.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__odds-container")

    for m in markets:
        try:
            line_text = m.text.strip()
        except:
            line_text = ""

        # find % spans within this market section
        percents = m.find_elements(By.XPATH, "../../following-sibling::div/span/span[@class='highlight-text__children']")
        if len(percents) >= 2:
            bets_pct = driver.execute_script("return arguments[0].innerText;", percents[0]).strip()
            money_pct = driver.execute_script("return arguments[0].innerText;", percents[1]).strip()
        else:
            bets_pct = money_pct = ""

        diff = ""
        try:
            diff = str(abs(int(money_pct.strip('%')) - int(bets_pct.strip('%')))) + "%"
        except:
            pass

        rows.append({
            "Matchup": matchup,
            "Line": line_text,
            "Bets %": bets_pct,
            "Money %": money_pct,
            "Diff": diff,
            "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

driver.quit()

# --- SAVE ---
df = pd.DataFrame(rows)
output = f"action_all_markets_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)

print(f"✅ Rows scraped: {len(df)}")
print(f"📁 Saved to {output}")
print("✅ Script completed")
