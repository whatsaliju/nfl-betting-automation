from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

# === Set up Chrome options for Ubuntu ===
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

# --- NAVIGATE TO PUBLIC BETTING PAGE ---
driver.get("https://www.actionnetwork.com/nfl/public-betting")
time.sleep(5)

# --- SELECT "ALL MARKETS" FROM DROPDOWN ---
try:
    container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='odds-tools-sub-nav__odds-type']")
    dropdown = container.find_element(By.TAG_NAME, "select")
    driver.execute_script("""
        arguments[0].value = 'combined';
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, dropdown)
    time.sleep(5)
    print("✅ Selected 'All Markets'")
except Exception as e:
    print(f"⚠️ Could not select All Markets: {e}")
    print("Proceeding with default view...")

# --- ENSURE PAGE FULLY LOADED ---
wait = WebDriverWait(driver, 10)
wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".public-betting__percents-container")))

# --- SCROLL THROUGH PAGE (lazy load safeguard) ---
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)
driver.execute_script("window.scrollTo(0, 0);")
time.sleep(1)

# --- SCRAPE FUNCTION ---
def scrape_table():
    data = []
    for tr in driver.find_elements(By.CSS_SELECTOR, "table tbody tr"):
        tds = tr.find_elements(By.TAG_NAME, "td")
        if len(tds) >= 3:
            matchup = tds[0].text.strip()
            line = tds[2].text.strip()

            bets_pct = ""
            money_pct = ""

            try:
                pct_container = tds[3].find_element(By.CSS_SELECTOR, ".public-betting__percents-container")
                percents = pct_container.find_elements(By.CSS_SELECTOR, ".highlight-text__children")

                if len(percents) >= 2:
                    bets_pct = percents[0].text.strip()
                    money_pct = percents[1].text.strip()
                elif len(percents) == 1:
                    bets_pct = percents[0].text.strip()
            except Exception:
                bets_pct = tds[3].text.strip()
                try:
                    money_pct = tds[4].text.strip()
                except Exception:
                    pass

            diff = ""
            if bets_pct and money_pct and "%" in bets_pct and "%" in money_pct:
                try:
                    diff = abs(int(money_pct.strip('%')) - int(bets_pct.strip('%')))
                except ValueError:
                    diff = ""

            data.append({
                "Matchup": matchup,
                "Line": line,
                "Bets %": bets_pct,
                "Money %": money_pct,
                "Diff": diff,
                "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    return data

# --- INITIAL SCRAPE ---
rows = scrape_table()

# --- RETRY PASS FOR MISSING MONEY% ---
missing_rows = [r for r in rows if not r["Money %"]]
if missing_rows:
    print(f"🔁 Retrying {len(missing_rows)} rows missing Money % ...")
    time.sleep(4)
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".public-betting__percents-container")))
    time.sleep(3)
    retry_data = scrape_table()

    # merge retry results where matchup names match
    retry_map = {r["Matchup"]: r for r in retry_data}
    for row in rows:
        if not row["Money %"] and row["Matchup"] in retry_map:
            row.update(retry_map[row["Matchup"]])

driver.quit()

# --- CLEANUP TEXT ---
def clean_text(x):
    if isinstance(x, str):
        x = x.replace("\n", " ").replace("\r", " ")
        x = " ".join(x.split())
    return x

# --- SAVE ---
df = pd.DataFrame(rows)
df = df.map(clean_text)

output = f"action_all_markets_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)

print(f"✅ Rows scraped: {len(df)}")
print(f"📁 Saved to {output}")
