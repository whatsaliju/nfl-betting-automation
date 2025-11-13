from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import re
import os

def run_sdql_queries(email, password, queries, headless=True):
    print("Starting browser...")
    
    if not email or not password:
        print("❌ ERROR: Missing credentials!")
        return
    
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-insecure-localhost')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    all_results = []
    
    try:
        print(f"Logging in with email: {email[:3]}***")
        driver.get("https://www.gimmethedog.com/login")
        time.sleep(5)

        # Try dismiss alert
        try:
            driver.switch_to.alert.dismiss()
            time.sleep(1)
        except:
            pass
        
        # login
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        email_field.send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)

        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        time.sleep(5)

        if "login" in driver.current_url.lower():
            print("❌ Login failed")
            return

        print("✅ Login successful!")
        driver.get("https://www.gimmethedog.com/NFL")
        time.sleep(4)

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Running query: {query[:50]}...")

            try:
                if i > 1:
                    driver.get("https://www.gimmethedog.com/NFL")
                    time.sleep(4)

                query_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "standard-textarea"))
                )

                query_box.click()
                query_box.clear()
                time.sleep(1)
                query_box.send_keys(query)
                time.sleep(1)

                driver.find_element(By.XPATH, "//button[text()='SDQL']").click()
                time.sleep(15)

                table_rows = driver.find_elements(By.XPATH, "//tbody/tr")

                su_text = table_rows[0].text if len(table_rows) > 0 else ""
                ats_text = table_rows[1].text if len(table_rows) > 1 else ""
                ou_text = table_rows[2].text if len(table_rows) > 2 else ""

                # -----------------------------
                # CLEAN EXTRACTION BLOCKS
                # -----------------------------

                # SU extraction
                su_match = re.search(r'SU:\s*([\d-]+)\s*\(([^)]+)\)', su_text)
                if su_match:
                    su_record = su_match.group(1)
                    raw = su_match.group(2)
                    pct_match = re.search(r'(\d+\.\d+%)', raw)
                    su_pct = pct_match.group(1) if pct_match else ""
                else:
                    su_record = ""
                    su_pct = ""

                # ATS extraction
                ats_match = re.search(r'ATS:\s*([\d-]+)\s*\(([^)]+)\)', ats_text)
                if ats_match:
                    ats_record = ats_match.group(1)
                    raw = ats_match.group(2)
                    pct_match = re.search(r'(\d+\.\d+%)', raw)
                    ats_pct = pct_match.group(1) if pct_match else ""
                else:
                    ats_record = ""
                    ats_pct = ""

                # OU extraction
                ou_match = re.search(r'OU:\s*([\d-]+)\s*\(([^)]+)\)', ou_text)
                if ou_match:
                    ou_record = ou_match.group(1)
                    raw = ou_match.group(2)
                    pct_match = re.search(r'(\d+\.\d+%)', raw)
                    ou_pct = pct_match.group(1) if pct_match else ""
                else:
                    ou_record = ""
                    ou_pct = ""

                # Add result
                result = {
                    'query': query,
                    'su_record': su_record,
                    'su_pct': su_pct,
                    'ats_record': ats_record,
                    'ats_pct': ats_pct,
                    'ou_record': ou_record,
                    'ou_pct': ou_pct
                }

                all_results.append(result)
                print(f"  ✓ ATS: {ats_record} ({ats_pct})")

            except Exception as e:
                print(f"  ✗ Error on query {i}: {e}")
                all_results.append({'query': query, 'error': str(e)})

        df = pd.DataFrame(all_results)
        df.to_csv('sdql_results.csv', index=False)
        print("\n✓ Saved results to sdql_results.csv")

    finally:
        driver.quit()



if __name__ == "__main__":
    GIMMETHEDOG_EMAIL = os.getenv('GIMMETHEDOG_EMAIL')
    GIMMETHEDOG_PASSWORD = os.getenv('GIMMETHEDOG_PASSWORD')

    if not GIMMETHEDOG_EMAIL or not GIMMETHEDOG_PASSWORD:
        print("❌ ERROR: Missing environment variables")
        exit(1)

    queries = [
        "'Bill Vinovich' in officials and HF and DIV and REG and season>=2018",
        "'Clete Blakeman' in officials and AF and NDIV and REG and season>=2018"
    ]

    run_sdql_queries(GIMMETHEDOG_EMAIL, GIMMETHEDOG_PASSWORD, queries, headless=True)
