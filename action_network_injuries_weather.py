#!/usr/bin/env python3

"""
Action Network NFL Injury + Weather Scraper
Fully rewritten, stable, production-ready.

Outputs:
- action_injuries_YYYY-MM-DD_.csv
- action_weather_YYYY-MM-DD_.csv
- injury_page_debug.html
- weather_page_debug.html

Author: ChatGPT
"""

import time
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# =====================================================================
# 🔧 DRIVER SETUP
# =====================================================================

def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


# =====================================================================
# 🩹 INJURY SCRAPER
# =====================================================================

def scrape_action_injuries(driver):
    print("\n🩹 Loading Action Network injuries page…")
    driver.get("https://www.actionnetwork.com/nfl/injuries")
    time.sleep(5)

    # ALWAYS SAVE DEBUG
    with open("injury_page_debug.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    rows = driver.find_elements(By.CSS_SELECTOR, ".injuries-table-layout__row")
    print(f"Found {len(rows)} injury rows (including team headers).")

    injury_data = []

    current_team = None

    for r in rows:
        try:
            # Team header row
            try:
                header = r.find_element(By.CSS_SELECTOR, ".injuries-table-layout__team-header-cell")
                current_team = header.text.strip()
                continue
            except:
                pass  # Not a header row → player row

            # Player row
            cols = r.find_elements(By.TAG_NAME, "td")
            if len(cols) < 5:
                continue

            player = cols[0].text.strip()
            position = cols[1].text.strip()
            status = cols[2].text.strip()
            injury_type = cols[3].text.strip()
            notes = cols[4].text.strip() if len(cols) > 4 else ""

            injury_data.append({
                "team": current_team,
                "player": player,
                "position": position,
                "status": status,
                "injury": injury_type,
                "notes": notes
            })

        except Exception:
            continue

    df = pd.DataFrame(injury_data)
    out_csv = f"action_injuries_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(out_csv, index=False)

    print(f"✅ Saved {len(df)} injuries → {out_csv}")
    return df


# =====================================================================
# 🌤️ WEATHER SCRAPER
# =====================================================================

def scrape_action_weather(driver):
    print("\n🌤️ Loading Action Network weather page…")
    driver.get("https://www.actionnetwork.com/nfl/weather")
    time.sleep(5)

    # ALWAYS SAVE DEBUG
    with open("weather_page_debug.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    rows = driver.find_elements(By.CSS_SELECTOR, ".forecasts__row")
    print(f"Found {len(rows)} weather rows.")

    weather_data = []

    for r in rows:
        try:
            # Team names
            teams = r.find_elements(By.CSS_SELECTOR, ".forecast-row__team-display--desktop")
            if len(teams) < 2:
                continue

            away = teams[0].text.strip()
            home = teams[1].text.strip()

            # Date/time info
            time_block = r.find_elements(By.CSS_SELECTOR, ".forecast-row__summarized-fields-container > div:nth-child(2) div")
            game_date = time_block[0].text if len(time_block) > 0 else ""
            game_time = time_block[1].text if len(time_block) > 1 else ""

            # Forecast description: "46°F Partly Cloudy"
            try:
                desc = r.find_element(By.CSS_SELECTOR, ".forecast-row__forecast-description").text.strip()
            except:
                desc = ""

            # Precip %
            try:
                precip = r.find_element(By.CSS_SELECTOR, ".forecast-row__summarized-field").text.strip()
            except:
                precip = ""

            # Wind (mph + direction)
            try:
                wind = r.find_element(By.CSS_SELECTOR, "span.css-13s1q9n").text.strip()
            except:
                wind = ""

            weather_data.append({
                "away": away,
                "home": home,
                "date": game_date,
                "time": game_time,
                "forecast": desc,
                "precip": precip,
                "wind": wind
            })

        except Exception:
            continue

    df = pd.DataFrame(weather_data)
    out_csv = f"action_weather_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(out_csv, index=False)

    print(f"✅ Saved {len(df)} weather rows → {out_csv}")
    return df


# =====================================================================
# 🚀 MASTER RUNNER — CALL THIS IN GITHUB ACTIONS
# =====================================================================

def run_full_action_network_scrape():
    driver = setup_driver()

    try:
        injuries = scrape_action_injuries(driver)
        weather = scrape_action_weather(driver)

        print("\n🎉 COMPLETE!")
        print(f"Injuries: {len(injuries)} rows")
        print(f"Weather : {len(weather)} rows")

        return injuries, weather

    finally:
        driver.quit()


if __name__ == "__main__":
    run_full_action_network_scrape()
