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

def run_sdql_queries(email, password, queries, headless=True):
    print("Starting browser...")
    
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        print("Running in background mode...")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    all_results = []
    
    try:
        driver.get("https://www.gimmethedog.com/login")
        time.sleep(2)
        
        print("Logging in...")
        email_field = driver.find_element(By.ID, "email")
        password_field = driver.find_element(By.ID, "password")
        email_field.send_keys(email)
        password_field.send_keys(password)
        
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        time.sleep(3)
        
        driver.get("https://www.gimmethedog.com/NFL")
        time.sleep(4)
        
        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Running query...")
            
            try:
                # Clear and enter query
                query_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "standard-textarea"))
                )
                query_box.click()
                query_box.send_keys(Keys.COMMAND + "a")
                query_box.send_keys(Keys.DELETE)
                time.sleep(0.5)
                query_box.send_keys(query)
                time.sleep(0.5)
                
                # Submit
                submit_btn = driver.find_element(By.XPATH, "//button[text()='SDQL']")
                submit_btn.click()
                
                # Wait for table to appear
                time.sleep(8)
                
                # Extract results
                table_rows = driver.find_elements(By.XPATH, "//tbody/tr")
                
                if len(table_rows) < 3:
                    print(f"⚠️ Only found {len(table_rows)} rows, expected 3")
                
                su_text = table_rows[0].text if len(table_rows) > 0 else ""
                ats_text = table_rows[1].text if len(table_rows) > 1 else ""
                ou_text = table_rows[2].text if len(table_rows) > 2 else ""
                
                su_match = re.search(r'SU:\s*(\d+-\d+)\s*\([^,]+,([^)]+)\)', su_text)
                su_record = su_match.group(1) if su_match else ""
                su_pct = su_match.group(2) if su_match else ""
                
                ats_match = re.search(r'ATS:\s*(\d+-\d+)\s*\([^,]+,([^)]+)\)', ats_text)
                ats_record = ats_match.group(1) if ats_match else ""
                ats_pct = ats_match.group(2) if ats_match else ""
                
                ou_match = re.search(r'OU:\s*(\d+-\d+-\d+)\s*\([^,]+,([^)]+)\)', ou_text)
                ou_record = ou_match.group(1) if ou_match else ""
                ou_pct = ou_match.group(2) if ou_match else ""
                
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
                print(f"✓ ATS: {ats_record} ({ats_pct})")
                
            except Exception as e:
                print(f"✗ Error on query {i}: {e}")
                all_results.append({'query': query, 'error': str(e)})
        
        df = pd.DataFrame(all_results)
        df.to_csv('sdql_results.csv', index=False)
        print(f"\n✓ Saved to sdql_results.csv")
        
    finally:
        driver.quit()


# Only run this when script is executed directly (not imported)
if __name__ == "__main__":
    from config import GIMMETHEDOG_EMAIL, GIMMETHEDOG_PASSWORD
    
    # Test queries
    queries = [
        "'Bill Vinovich' in officials and HF and DIV and REG and season>=2018",
        "'Clete Blakeman' in officials and AF and NDIV and REG and season>=2018",
        "'Brad Allen' in officials and HF and DIV and REG and season>=2018",
        "'Adrian Hill' in officials and HF and NDIV and REG and season>=2018",
        "'Alex Moore' in officials and AF and DIV and REG and season>=2018",
        "'Ron Torbert' in officials and AF and DIV and REG and season>=2018",
        "'Shawn Hochuli' in officials and AF and NDIV and REG and season>=2018",
        "'Shawn Smith' in officials and AF and C and REG and season>=2018",
        "'Alex Kemp' in officials and HF and NDIV and REG and season>=2018",
        "'Alan Eck' in officials and HF and DIV and REG and season>=2018",
        "'Land Clark' in officials and AF and DIV and REG and season>=2018",
        "'Scott Novak' in officials and AF and C and REG and season>=2018",
        "'Brad Rogers' in officials and HF and NDIV and REG and season>=2018",
        "'Clay Martin' in officials and HF and C and REG and season>=2018"
    ]
    
    run_sdql_queries(GIMMETHEDOG_EMAIL, GIMMETHEDOG_PASSWORD, queries, headless=True)
