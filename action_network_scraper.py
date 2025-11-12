# action_network_scraper.py
# -------------------------------------------
# Scrapes Action Network NFL public betting ("All Markets")
# Outputs CSV: action_all_markets_YYYY-MM-DD.csv
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

# === Read credentials from environment variables ===
EMAIL = os.environ.get('ACTION_NETWORK_EMAIL')
PASSWORD = os.environ.get('ACTION_NETWORK_PASSWORD')

if not EMAIL or not PASSWORD:
    print("❌ Action Network credentials not found")
    sys.exit(1)

print(f"✅ Using Action Network credentials for: {EMAIL[:3]}***@{EMAIL.split('@')[1]}")

# === Set up Chrome options ===
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.binary_location = "/usr/bin/chromium-browser"

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# === LOGIN ===
driver.get("https://www.actionnetwork.com/login")
time.sleep(3)
driver.find_element(By.NAME, "email").send_keys(EMAIL)
driver.find_element(By.NAME, "password").send_keys(PASSWORD)
driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
time.sleep(6)

# === NAVIGATE TO PUBLIC BETTING PAGE ===
driver.get("https://www.actionnetwork.com/nfl/public-betting")
time.sleep(5)

# Scroll once to trigger lazy load
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(3)
driver.execute_script("window.scrollTo(0, 0);")

# === SELECT "ALL MARKETS" FROM DROPDOWN ===
try:
    container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='odds-tools-sub-nav__odds-type']")
    dropdown_el = container.find_element(By.TAG_NAME, "select")
    Select(dropdown_el).select_by_value("combined")
    print("✅ Selected 'All Markets' via dropdown")
    time.sleep(5)
except Exception as e:
    print("⚠️ Could not select All Markets:", e)

# === WAIT FOR BETTING DATA TO LOAD ===
try:
    print("⏳ Waiting for betting data to refresh...")
    # first wait for any old content to disappear
    WebDriverWait(driver, 10).until_not(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".mobile-public-betting__percent .highlight-text__children")
        )
    )
except TimeoutException:
    pass

try:
    WebDriverWait(driver, 25).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".mobile-public-betting__percent .highlight-text__children")
        )
    )
    print("✅ Betting percentages visible")
except TimeoutException:
    print("⚠️ Still no visible % spans after 25s, continuing anyway")
    time.sleep(5)

# === SCRAPE FUNCTION ===
def scrape_table():
    data = []

    # find all matchup links
    game_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/nfl-game/']")
    matchups = []
    for link in game_links:
        href = link.get_attribute("href")
        text = " ".join(link.text.split())
        if "/nfl-game/" in href and text:
            date_part = href.split("odds-")[-1].split("/")[0].replace("-", " ").title()
            matchups.append(f"{date_part} {text}")

    print(f"🧾 Found {len(matchups)} matchup headers")

    # find all betting rows (mobile containers)
    blocks = driver.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__row--last")
    print(f"📊 Found {len(blocks)} betting blocks")

    # align matchups with betting blocks
    for idx, g in enumerate(blocks[:len(matchups)]):
        matchup = matchups[idx] if idx < len(matchups) else "Unknown"
        percents = g.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__percent .highlight-text__children")

        for i in range(0, len(percents), 2):
            try:
                bets_pct = driver.execute_script("return arguments[0].innerText;", percents[i]).strip()
                money_pct = driver.execute_script("return arguments[0].innerText;", percents[i + 1]).strip()
                if not bets_pct or not money_pct:
                    continue
            except Exception:
                continue

            diff = ""
            try:
                diff = str(abs(int(money_pct.strip('%')) - int(bets_pct.strip('%')))) + "%"
            except Exception:
                pass

            data.append({
                "Matchup": matchup,
                "Bets %": bets_pct,
                "Money %": money_pct,
                "Diff": diff,
                "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M")
            })

    return data

# === RUN SCRAPE ===
rows = scrape_table()

driver.quit()

# === SAVE TO CSV ===
df = pd.DataFrame(rows)
output = f"action_all_markets_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)
print(f"✅ Rows scraped: {len(df)}")
print(f"📁 Saved to {output}")
print("✅ Script completed")
