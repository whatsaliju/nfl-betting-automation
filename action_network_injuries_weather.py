#!/usr/bin/env python3
"""
Action Network – NFL Injury Scraper (Normalized Output)
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
from datetime import datetime

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

def scrape_action_injuries():
    driver = setup_driver()

    print("🩹 Scraping Action Network NFL Injuries...")

    driver.get("https://www.actionnetwork.com/nfl/injuries")
    time.sleep(5)

    injuries = []
    current_team = None

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")

        for row in rows:
            # Team header row
            team_cells = row.find_elements(By.CSS_SELECTOR, "td.injuries-table-layout__team-header-cell")
            if team_cells:
                current_team = team_cells[0].text.strip()
                continue

            # Player injury row
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) == 6 and current_team:
                player = cells[0].text.strip()
                pos = cells[1].text.strip()
                status = cells[2].text.strip()
                injury = cells[3].text.strip()
                description = cells[4].text.strip()
                date = cells[5].text.strip()

                injuries.append({
                    "team": current_team,
                    "player": player,
                    "pos": pos,
                    "status": status,
                    "injury": injury,
                    "description": description,
                    "date": date
                })

    except Exception as e:
        print("❌ Error parsing injury table:", e)

    driver.quit()
    
    df = pd.DataFrame(injuries)
    output = f"action_injuries_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(output, index=False)

    print(f"✅ Scraped {len(df)} injuries")
    print(f"📁 Saved to {output}")

    return df

if __name__ == "__main__":
    scrape_action_injuries()
