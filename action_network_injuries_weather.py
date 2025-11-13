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


def scrape_action_weather():
    driver = setup_driver()

    print("🌤️ Scraping Action Network NFL Weather...")

    driver.get("https://www.actionnetwork.com/nfl/weather")
    time.sleep(6)  # allow React to load

    weather_rows = []
    severe_alerts = {}

    # --------------------------------------------------------
    # 1. SCRAPE SEVERE WEATHER CATEGORY SECTIONS
    # --------------------------------------------------------
    try:
        severe_sections = driver.find_elements(By.CLASS_NAME, "severe-weather-category__title")
        print(f"Found {len(severe_sections)} severe weather categories")

        for title in severe_sections:
            category = title.text.strip()

            container = title.find_element(By.XPATH, "./ancestor::section")
            teams = container.find_elements(By.CLASS_NAME, "severe-weather-category__team-name--desktop")
            metrics = container.find_elements(By.CLASS_NAME, "severe-weather-category__metric")

            for i, t in enumerate(teams):
                team = t.text.strip()
                wind = metrics[i].text if i < len(metrics) else ""

                severe_alerts[team] = {
                    "severe": category,
                    "severe_wind": wind
                }

    except Exception as e:
        print("⚠️ Severe weather scrape error:", e)

    # --------------------------------------------------------
    # 2. SCRAPE GAME-BY-GAME FORECAST WEATHER
    # --------------------------------------------------------
    try:
        forecast_blocks = driver.find_elements(By.CLASS_NAME, "forecast-row__forecast-description")
        print(f"Found {len(forecast_blocks)} forecast description rows")

        all_blocks = driver.find_elements(By.CSS_SELECTOR, ".forecast-row")

        for block in all_blocks:
            try:
                # Forecast (e.g. "45°F Partly Cloudy")
                desc = block.find_element(By.CLASS_NAME, "forecast-row__forecast-description").text.strip()

                temp = ""
                cond = ""
                m = re.match(r"(\d+°F)\s*(.*)", desc)
                if m:
                    temp = m.group(1)
                    cond = m.group(2)

                # Precip %
                try:
                    precip = block.find_element(By.CLASS_NAME, "forecast-row__summarized-field").text.strip()
                except:
                    precip = ""

                # Wind — directional arrow + text (e.g. "14.19 ESE")
                try:
                    wind_el = block.find_element(By.CSS_SELECTOR, ".css-13s1q9n.e1mp5wme0")
                    wind = wind_el.text.strip()
                except:
                    wind = ""

                # Team name (in same parent container)
                parent = block.find_element(By.XPATH, "./ancestor::div[contains(@class,'forecast')]")
                team_el = parent.find_element(By.CSS_SELECTOR, ".forecast__team-name")
                team = team_el.text.strip()

                severe = severe_alerts.get(team, {}).get("severe", "")
                severe_wind = severe_alerts.get(team, {}).get("severe_wind", "")

                weather_rows.append({
                    "team": team,
                    "temp": temp,
                    "conditions": cond,
                    "precip": precip,
                    "wind": wind,
                    "severe": severe,
                    "severe_wind": severe_wind
                })

            except Exception:
                continue

    except Exception as e:
        print("❌ Error in main forecast loop:", e)

    driver.quit()

    df = pd.DataFrame(weather_rows)
    output = f"action_weather_{datetime.now().strftime('%Y-%m-%d_')}.csv"
    df.to_csv(output, index=False)

    print(f"\n🌤️ Saved weather file: {output}")
    print(f"Rows: {len(df)}")

    return df


if __name__ == "__main__":
    scrape_action_weather()
