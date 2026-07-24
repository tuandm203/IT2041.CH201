"""
Crawl course descriptions from daa.uit.edu.vn using Selenium
"""
import json
import re
import sys
import time
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent

def crawl_with_selenium():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("[ERROR] Selenium not installed. Run: pip install selenium webdriver-manager")
        return []
    
    url = 'https://daa.uit.edu.vn/content/bang-tom-tat-mon-hoc'
    
    # Setup Chrome headless
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    print(f"[INFO] Starting Chrome driver...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print(f"[INFO] Loading {url}...")
        driver.get(url)
        
        # Wait for table to load
        print("[INFO] Waiting for table to load...")
        time.sleep(3)
        
        # Try to find table
        tables = driver.find_elements(By.TAG_NAME, 'table')
        print(f"[INFO] Found {len(tables)} tables")
        
        courses = []
        
        if tables:
            # Get the first table with many rows
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, 'tr')
                if len(rows) > 10:
                    print(f"[INFO] Processing table with {len(rows)} rows")
                    
                    for i, row in enumerate(rows):
                        cells = row.find_elements(By.TAG_NAME, 'td')
                        if len(cells) >= 3:
                            # STT | Mã MH | Tên MH | Tóm tắt
                            stt = cells[0].text.strip()
                            ma_mh = cells[1].text.strip()
                            ten_mh = cells[2].text.strip()
                            tom_tat = cells[3].text.strip() if len(cells) > 3 else ''
                            
                            if ma_mh and ten_mh:
                                courses.append({
                                    'course_id': ma_mh,
                                    'name_vi': ten_mh,
                                    'description': tom_tat
                                })
                    break
        
        if not courses:
            # Fallback: try to get from page source
            print("[INFO] No table found, trying page source...")
            page_source = driver.page_source
            
            # Try to find iframe
            iframes = driver.find_elements(By.TAG_NAME, 'iframe')
            print(f"[INFO] Found {len(iframes)} iframes")
            
            for iframe in iframes:
                src = iframe.get_attribute('src')
                print(f"[INFO] Iframe src: {src}")
                if src:
                    try:
                        driver.switch_to.frame(iframe)
                        time.sleep(2)
                        tables = driver.find_elements(By.TAG_NAME, 'table')
                        print(f"[INFO] Found {len(tables)} tables in iframe")
                        
                        for table in tables:
                            rows = table.find_elements(By.TAG_NAME, 'tr')
                            if len(rows) > 10:
                                print(f"[INFO] Processing iframe table with {len(rows)} rows")
                                
                                for i, row in enumerate(rows):
                                    cells = row.find_elements(By.TAG_NAME, 'td')
                                    if len(cells) >= 3:
                                        ma_mh = cells[1].text.strip()
                                        ten_mh = cells[2].text.strip()
                                        tom_tat = cells[3].text.strip() if len(cells) > 3 else ''
                                        
                                        if ma_mh and ten_mh:
                                            courses.append({
                                                'course_id': ma_mh,
                                                'name_vi': ten_mh,
                                                'description': tom_tat
                                            })
                                break
                        
                        driver.switch_to.default_content()
                    except Exception as e:
                        print(f"[WARN] Error switching to iframe: {e}")
                        driver.switch_to.default_content()
        
        # Remove duplicates
        seen = set()
        unique_courses = []
        for c in courses:
            if c['course_id'] not in seen:
                seen.add(c['course_id'])
                unique_courses.append(c)
        
        print(f"\n[OK] Parsed {len(unique_courses)} unique courses")
        
        # Print samples
        for c in unique_courses[:15]:
            desc_preview = c['description'][:80] if c['description'] else '(no description)'
            print(f"  {c['course_id']:8s} | {c['name_vi'][:40]:40s} | {desc_preview}")
        
        # Save to JSON
        output_file = ROOT / 'data' / 'raw' / 'course_descriptions.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_courses, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] Saved {len(unique_courses)} courses to {output_file}")
        
        return unique_courses
        
    finally:
        driver.quit()

if __name__ == '__main__':
    crawl_with_selenium()