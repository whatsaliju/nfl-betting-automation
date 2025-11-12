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
    
    # Validate credentials
    if not email or not password:
        print(f"❌ ERROR: Missing credentials!")
        print(f"   Email: {email}")
        print(f"   Password: {'***' if password else 'None'}")
        return
    
    options = webdriver.ChromeOptions()

    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--ignore-certificate-errors')  # Add this
        options.add_argument('--allow-insecure-localhost')   # Add this
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        print("Running in background mode...")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    all_results = []
    
    try:
        print(f"Logging in with email: {email[:3]}***")
        driver.get("https://www.gimmethedog.com/login")
        time.sleep(3)
        
        print("Entering credentials...")
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        email_field.clear()
        email_field.send_keys(email)
        time.sleep(0.5)
        
        password_field = driver.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(0.5)
        
        # Try pressing Enter instead of clicking button
        print("Submitting login form...")
        password_field.send_keys(Keys.RETURN)
        time.sleep(5)
        
        # Check if login was successful
        current_url = driver.current_url
        print(f"After login, URL: {current_url}")
        
        if "login" in current_url.lower():
            print("⚠️ WARNING: Still on login page - authentication failed!")
            print("Checking for error messages...")
            
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "invalid" in body_text.lower() or "incorrect" in body_text.lower():
                    print(f"❌ Login error found: {body_text[:200]}")
            except:
                pass
            
            driver.save_screenshot("login_failed.png")
            print("📸 Saved screenshot: login_failed.png")
            driver.quit()
            return
        
        print("✅ Login successful!")
        driver.get("https://www.gimmethedog.com/NFL")
        time.sleep(4)
        print(f"On NFL page, URL: {driver.current_url}")
        
        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Running query: {query[:50]}...")
            
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
                print("  Clicked SDQL button, waiting for results...")
                
                # Wait for table to appear
                time.sleep(10)
                
                # Try multiple ways to find results
                print("  Searching for results table...")
                
                # Method 1: Original way
                table_rows = driver.find_elements(By.XPATH, "//tbody/tr")
                print(f"  Method 1 (//tbody/tr): Found {len(table_rows)} rows")
                
                # Method 2: Look for any table
                all_tables = driver.find_elements(By.TAG_NAME, "table")
                print(f"  Found {len(all_tables)} table elements on page")
                
                # Method 3: Look for text containing "ATS:"
                page_source = driver.page_source
                if "ATS:" in page_source:
                    print("  ✓ Found 'ATS:' text in page")
                else:
                    print("  ✗ No 'ATS:' text found in page")
                
                # Method 4: Check for any tbody
                tbodies = driver.find_elements(By.TAG_NAME, "tbody")
                print(f"  Found {len(tbodies)} tbody elements")
                
                if len(table_rows) < 3:
                    print(f"  ⚠️ Only found {len(table_rows)} rows, expected 3")
                    # Save screenshot for first failed query
                    if i == 1:
                        driver.save_screenshot("debug_no_results.png")
                        print("  📸 Saved screenshot: debug_no_results.png")
                        # Print part of page to see what's there
                        body_text = driver.find_element(By.TAG_NAME, "body").text
                        print(f"  Page text preview: {body_text[:300]}")
                
                su_text = table_rows[0].text if len(table_rows) > 0 else ""
                ats_text = table_rows[1].text if len(table_rows) > 1 else ""
                ou_text = table_rows[2].text if len(table_rows) > 2 else ""
                
                print(f"  SU text: {su_text}")
                print(f"  ATS text: {ats_text}")
                print(f"  OU text: {ou_text}")
                
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
                print(f"  ✓ ATS: {ats_record} ({ats_pct})")
                
            except Exception as e:
                print(f"  ✗ Error on query {i}: {e}")
                import traceback
                traceback.print_exc()
                all_results.append({'query': query, 'error': str(e)})
        
        df = pd.DataFrame(all_results)
        df.to_csv('sdql_results.csv', index=False)
        print(f"\n✓ Saved {len(all_results)} results to sdql_results.csv")
        
    finally:
        driver.quit()


# Only run this when script is executed directly (not imported)
if __name__ == "__main__":
    GIMMETHEDOG_EMAIL = os.getenv('GIMMETHEDOG_EMAIL')
    GIMMETHEDOG_PASSWORD = os.getenv('GIMMETHEDOG_PASSWORD')
    
    print("Checking environment variables...")
    print(f"EMAIL present: {bool(GIMMETHEDOG_EMAIL)}")
    print(f"PASSWORD present: {bool(GIMMETHEDOG_PASSWORD)}")
    
    if not GIMMETHEDOG_EMAIL or not GIMMETHEDOG_PASSWORD:
        print("❌ ERROR: Environment variables not set!")
        exit(1)
    
    # Test queries
    queries = [
        "'Bill Vinovich' in officials and HF and DIV and REG and season>=2018",
        "'Clete Blakeman' in officials and AF and NDIV and REG and season>=2018"
    ]
    
    print(f"\nRunning {len(queries)} test queries...")
    run_sdql_queries(GIMMETHEDOG_EMAIL, GIMMETHEDOG_PASSWORD, queries, headless=True)
