from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

# --- WAIT FOR PAGE RENDER ---
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

    # Wait until the page populates at least one betting block
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".mobile-public-betting__row--last"))
    )

    # 1️⃣ Get all matchup headers (global list)
    game_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/nfl-game/']")
    matchups = []
    for link in game_links:
        href = link.get_attribute("href")
        text = " ".join(link.text.split())
        if "/nfl-game/" in href and text:
            # derive readable date from slug
            date_part = href.split("odds-")[-1].split("/")[0].replace("-", " ").title()
            matchups.append(f"{date_part} {text}")

    print(f"Found {len(matchups)} matchup headers")

    # 2️⃣ Get all betting rows (one per matchup)
    blocks = driver.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__row--last")
    print(f"Found {len(blocks)} betting blocks")

    # Use min(len(matchups), len(blocks)) to avoid index overflow
    for idx, g in enumerate(blocks[:len(matchups)]):
        matchup = matchups[idx] if idx < len(matchups) else "Unknown"

        # Extract percentage pairs (bets %, money %)
        percents = g.find_elements(By.CSS_SELECTOR, ".mobile-public-betting__percent .highlight-text__children")
        for i in range(0, len(percents), 2):
            try:
                bets_pct = percents[i].text.strip() + "%"
                money_pct = percents[i + 1].text.strip() + "%"
            except IndexError:
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
    retry_map = {r["Matchup"] + r["Line"]: r for r in retry_data}
    for row in rows:
        key = row["Matchup"] + row["Line"]
        if not row["Money %"] and key in retry_map:
            row.update(retry_map[key])

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
