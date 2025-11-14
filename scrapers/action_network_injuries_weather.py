#!/usr/bin/env python3
"""
Action Network – Unified Scraper
Scrapes BOTH:
  • NFL Injuries
  • NFL Weather
Produces two CSV outputs:
  • action_injuries_YYYY-MM-DD_.csv
  • action_weather_YYYY-MM-DD_.csv
"""

import time
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


# ------------------------------------------------------------
# DRIVER SETUP (FIXED - uses system ChromeDriver)
# ------------------------------------------------------------
def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(
        service=Service('/usr/bin/chromedriver'),
        options=options
    )


# ------------------------------------------------------------
# SCRAPE ACTION NETWORK INJURIES
# ------------------------------------------------------------
def scrape_action_injuries(driver):
    print("🩹 Scraping Action Network NFL Injuries...")

    driver.get("https://www.actionnetwork.com/nfl/injuries")
    time.sleep(5)

    injuries = []
    current_team = None

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")

        for row in rows:
            # Detect team header row
            team_cells = row.find_elements(By.CSS_SELECTOR, "td.injuries-table-layout__team-header-cell")
            if team_cells:
                current_team = team_cells[0].text.strip()
                continue

            # Player rows
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) == 6 and current_team:
                injuries.append({
                    "team": current_team,
                    "player": cells[0].text.strip(),
                    "pos": cells[1].text.strip(),
                    "status": cells[2].text.strip(),
                    "injury": cells[3].text.strip(),
                    "description": cells[4].text.strip(),
                    "date": cells[5].text.strip()
                })

    except Exception as e:
        print("❌ Error scraping injuries:", e)

    df = pd.DataFrame(injuries)
    output = f"data/action_injuries_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(output, index=False)

    print(f"✅ Scraped {len(df)} injuries")
    print(f"📁 Saved injuries → {output}")

    return df, output


# ------------------------------------------------------------
# SCRAPE ACTION NETWORK WEATHER
# ------------------------------------------------------------
def scrape_action_weather(driver):
    print("🌤️ Scraping Action Network NFL Weather...")

    driver.get("https://www.actionnetwork.com/nfl/weather")
    time.sleep(5)

    games = []

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "li.forecasts__row")

        for row in rows:

            # -----------------------------
            # Extract teams
            # -----------------------------
            team_containers = row.find_elements(By.CSS_SELECTOR, ".forecast-row__team-container")
            if len(team_containers) < 2:
                continue

            away = team_containers[0].text.split("\n")[-1].strip()
            home = team_containers[1].text.split("\n")[-1].strip()

            # -----------------------------
            # Extract date/time
            # -----------------------------
            date = time_txt = ""
            dt_block = row.find_elements(By.CSS_SELECTOR, "div > div")
            if len(dt_block) >= 2:
                date = dt_block[0].text.strip()
                time_txt = dt_block[1].text.strip()

            # -----------------------------
            # Forecast
            # -----------------------------
            forecast_el = row.find_elements(By.CSS_SELECTOR, ".forecast-row__forecast-description")
            forecast = forecast_el[0].text.strip() if forecast_el else ""

            # -----------------------------
            # Precipitation
            # -----------------------------
            precip_el = row.find_elements(By.CSS_SELECTOR, ".forecast-row__summarized-field")
            precip = precip_el[0].text.strip() if precip_el else "--"

            # -----------------------------
            # Wind
            # -----------------------------
            wind_el = row.find_elements(By.CSS_SELECTOR, "span.css-13s1q9n")
            wind = wind_el[0].text.strip() if wind_el else ""

            # Dome logic
            if forecast == "" and precip == "--":
                forecast = "Dome"
                wind = ""

            games.append({
                "away": away,
                "home": home,
                "date": date,
                "time": time_txt,
                "forecast": forecast,
                "precip": precip,
                "wind": wind
            })

    except Exception as e:
        print("❌ Error scraping weather:", e)

    df = pd.DataFrame(games)
    output = f"data/action_weather_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(output, index=False)

    print(f"✅ Scraped {len(df)} weather rows")
    print(f"📁 Saved weather → {output}")

    return df, output


# ------------------------------------------------------------
# RUN BOTH
# ------------------------------------------------------------
if __name__ == "__main__":
    driver = setup_driver()

    try:
        injuries_df, inj_file = scrape_action_injuries(driver)
        weather_df, weather_file = scrape_action_weather(driver)
    finally:
        driver.quit()

    print("\n🎉 ALL DONE!")
    print(f"📁 Injuries File: {inj_file}")
    print(f"📁 Weather File:  {weather_file}")
