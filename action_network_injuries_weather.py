#!/usr/bin/env python3
"""
Action Network – NFL Weather Scraper (Clean Normalized Output)
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
from datetime import datetime
import re


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

def scrape_injuries(driver):
    """Scrape NFL injury data from Action Network."""
    print("🩹 Scraping Action Network Injuries...")

    driver.get("https://www.actionnetwork.com/nfl/injuries")
    time.sleep(5)

    injuries = []
    current_team = None

    try:
        # Each team header cell identifies a new team section
        rows = driver.find_elements(By.CSS_SELECTOR,
            "td.injuries-table-layout__team-header-cell, tr"
        )

        for row in rows:
            tag = row.tag_name.lower()

            # 1️⃣ TEAM HEADER ROW
            if tag == "td" and "team-header-cell" in row.get_attribute("class"):
                # Extract clean team name
                team_text = row.text.strip()
                if team_text:
                    current_team = team_text
                continue

            # 2️⃣ PLAYER ROW
            if tag == "tr":
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 5:
                    continue

                player = cells[0].text.strip()
                position = cells[1].text.strip()
                status = cells[2].text.strip()
                injury = cells[3].text.strip()
                notes = cells[4].text.strip()
                date = cells[5].text.strip() if len(cells) > 5 else ""

                if current_team:  # Only attach if inside a team block
                    injuries.append({
                        "team": current_team,
                        "player": player,
                        "position": position,
                        "status": status,
                        "injury": injury,
                        "notes": notes,
                        "date": date,
                    })

        # Save output
        df = pd.DataFrame(injuries)
        output = f"action_injuries_{datetime.now().strftime('%Y-%m-%d_')}.csv"
        df.to_csv(output, index=False)

        print(f"✅ Injuries scraped: {len(df)} rows")
        print(f"📁 Saved to {output}")

        return df

    except Exception as e:
        print(f"❌ Injury scraper error: {e}")
        return pd.DataFrame()

def scrape_weather(driver):
    """Scrape NFL weather from Action Network (expanded rows)."""

    print("🌤️  Scraping Action Network Weather...")

    driver.get("https://www.actionnetwork.com/nfl/weather")
    time.sleep(5)

    # Scroll to bottom to load all games
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    weather_rows = driver.find_elements(By.CSS_SELECTOR, "li.forecasts__row")
    print(f"  Found {len(weather_rows)} weather rows")

    results = []

    for row in weather_rows:
        try:
            # 1️⃣ Teams
            teams = row.find_elements(By.CLASS_NAME, "forecast-row__team-display--desktop")
            if len(teams) < 2:
                continue
            away = teams[0].text.strip()
            home = teams[1].text.strip()

            # 2️⃣ Date & Time
            datetime_block = row.find_elements(
                By.CSS_SELECTOR,
                ".forecast-row__summarized-fields-container > div"
            )[1].find_elements(By.TAG_NAME, "div")

            date = datetime_block[0].text.strip()
            time_str = datetime_block[1].text.strip()

            # 3️⃣ Temperature + Conditions
            try:
                forecast_desc = row.find_element(
                    By.CLASS_NAME, "forecast-row__forecast-description"
                ).text.strip()
            except:
                forecast_desc = ""

            # 4️⃣ Precipitation %
            try:
                precip = row.find_element(
                    By.CLASS_NAME, "forecast-row__summarized-field"
                ).text.strip()
            except:
                precip = ""

            # 5️⃣ Wind Speed + Direction
            try:
                wind = row.find_element(
                    By.CSS_SELECTOR, "span.css-13s1q9n"
                ).text.strip()
            except:
                wind = ""

            results.append({
                "matchup": f"{away} @ {home}",
                "away": away,
                "home": home,
                "date": date,
                "time": time_str,
                "forecast": forecast_desc,
                "precip": precip,
                "wind": wind,
            })

        except Exception as e:
            print(f"⚠️ Error parsing row: {e}")
            continue

    # Save file
    df = pd.DataFrame(results)
    output = f"action_weather_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(output, index=False)

    print(f"✅ Weather scraped: {len(df)} games")
    print(f"📁 Saved to {output}")

    return df



if __name__ == "__main__":
    driver = setup_driver_with_cookies()

    try:
        inj = scrape_injuries(driver)
        weather = scrape_weather(driver)
    finally:
        driver.quit()
