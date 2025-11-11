from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select  # ← ADD THIS
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
    # Find the container div first (more reliable)
    container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='odds-tools-sub-nav__odds-type']")
    
    # Find the select within it
    dropdown = container.find_element(By.TAG_NAME, "select")
    
    # Use JavaScript to set value and trigger change
    driver.execute_script("""
        arguments[0].value = 'combined';
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, dropdown)
    
    time.sleep(5)
    print("✅ Selected 'All Markets'")
    
except Exception as e:
    print(f"⚠️ Could not select All Markets: {e}")
    print("Proceeding with default view...")

# --- SCRAPE THE TABLE ---
rows = []
for tr in driver.find_elements(By.CSS_SELECTOR, "table tbody tr"):
    tds = tr.find_elements(By.TAG_NAME, "td")
    if len(tds) >= 6:
        rows.append({
            "Matchup": tds[0].text.strip(),
            "Line": tds[2].text.strip(),
            "Bets %": tds[3].text.strip(),
            "Money %": tds[4].text.strip(),
            "Diff": tds[5].text.strip() if len(tds) > 5 else "",
            "Fetched": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

driver.quit()

# --- CLEANUP TEXT ---
def clean_text(x):
    if isinstance(x, str):
        x = x.replace("\n", " ").replace("\r", " ")
        x = " ".join(x.split())
    return x

# --- SAVE ---
df = pd.DataFrame(rows)
df = df.map(clean_text)  # Changed from applymap (deprecated)

output = f"action_all_markets_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(output, index=False)

print(f"✅ Rows scraped: {len(df)}")
print(f"📁 Saved to {output}")
