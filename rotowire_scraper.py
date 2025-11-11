#!/usr/bin/env python3
"""
RotoWire NFL Injury Report Scraper
Gets current injury status for all NFL players
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import pandas as pd
import time
from datetime import datetime
import os
import sys

def scrape_injuries():
    """Scrape NFL injury reports from RotoWire"""
    
    # === Set up Chrome ===
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # For local Mac testing
    if not os.path.exists("/usr/bin/chromium-browser"):
        # Mac
        driver = webdriver.Chrome(options=options)
    else:
        # Ubuntu (GitHub Actions)
        options.binary_location = "/usr/bin/chromium-browser"
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
    
    print("🏈 Scraping RotoWire NFL injuries...")
    
    try:
        # Navigate to injury page
        driver.get("https://www.rotowire.com/football/injury-report.php")
        time.sleep(5)
        
        injuries = []
        
        # Find all injury rows
        rows = driver.find_elements(By.CSS_SELECTOR, "div.injuries tbody tr")
        
        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 5:
                    injuries.append({
                        "Player": cols[0].text.strip(),
                        "Position": cols[1].text.strip(),
                        "Team": cols[2].text.strip(),
                        "Injury": cols[3].text.strip(),
                        "Status": cols[4].text.strip(),
                        "Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            except Exception as e:
                continue
        
        driver.quit()
        
        # Save to CSV
        df = pd.DataFrame(injuries)
        output = f"rotowire_injuries_{datetime.now().strftime('%Y-%m-%d')}.csv"
        df.to_csv(output, index=False)
        
        print(f"✅ Scraped {len(df)} injury reports")
        print(f"📁 Saved to {output}")
        
        # Show critical injuries (Out/Doubtful)
        critical = df[df['Status'].isin(['Out', 'Doubtful'])]
        if len(critical) > 0:
            print(f"\n🚨 {len(critical)} players OUT or DOUBTFUL:")
            for _, injury in critical.head(10).iterrows():
                print(f"   • {injury['Player']} ({injury['Team']}) - {injury['Status']}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error scraping injuries: {e}")
        driver.quit()
        return None

if __name__ == "__main__":
    scrape_injuries()
