from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

# Add binary location for Ubuntu
options.binary_location = "/usr/bin/chromium-browser"

# Use system chromedriver
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)
# --- LOGIN ---
driver.get("https://www.actionnetwork.com/login")
time.sleep(3)

driver.find_element(By.NAME, "email").send_keys(EMAIL)
driver.find_element(By.NAME, "password").send_keys(PASSWORD)
driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
time.sleep(6)  # allow login to complete

# --- NAVIGATE TO PUBLIC BETTING PAGE ---
driver.get("https://www.actionnetwork.com/nfl/public-betting")
time.sleep(10)   # wait for table to fully render

# --- SCRAPE FUNCTION ---
def scrape_table(market_name):
    """Scrape whichever table is currently visible."""
    rows = []
    for tr in driver.find_elements(By.CSS_SELECTOR, "table tbody tr"):
        tds = tr.find_elements(By.TAG_NAME, "td")
        if len(tds) >= 4:
            rows.append({
                "Market": market_name,
                "Matchup": tds[0].text.strip(),
                "Line": tds[1].text.strip(),
                "Bets %": tds[2].text.strip(),
                "Money %": tds[3].text.strip(),
                "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    return rows

# --- SCRAPE SPREAD ---
spread_data = scrape_table("Spread")

# --- CLICK MONEYLINE TAB ---
try:
    driver.find_element(By.XPATH, "//button[contains(., 'Moneyline')]").click()
    time.sleep(5)
    moneyline_data = scrape_table("Moneyline")
except Exception as e:
    print("⚠️ Moneyline scrape failed:", e)
    moneyline_data = []

# --- CLICK OVER/UNDER TAB ---
try:
    driver.find_element(By.XPATH, "//button[contains(., 'Over/Under')]").click()
    time.sleep(5)
    ou_data = scrape_table("Over/Under")
except Exception as e:
    print("⚠️ Over/Under scrape failed:", e)
    ou_data = []

driver.quit()

# --- MERGE ALL MARKETS ---
all_rows = spread_data + moneyline_data + ou_data
df = pd.DataFrame(all_rows)

# --- CLEANUP ---
def clean_text(x):
    if isinstance(x, str):
        x = x.replace("\n", " ").replace("\r", " ")
        x = " ".join(x.split())
        return x
    return x

df = df.applymap(clean_text)

output = f"action_public_bets_all_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)

print("✅ Rows scraped:", len(df))
print(df.groupby("Market")["Matchup"].count())
print(f"📁 Saved to {output}")
