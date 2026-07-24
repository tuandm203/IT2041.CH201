"""
Crawl course descriptions from daa.uit.edu.vn using Playwright
"""
import json
import re
import sys
import asyncio
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent

async def crawl_with_playwright():
    from playwright.async_api import async_playwright
    
    url = 'https://daa.uit.edu.vn/content/bang-tom-tat-mon-hoc'
    
    async with async_playwright() as p:
        print("[INFO] Launching Chromium...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            print(f"[INFO] Loading {url}...")
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Try to find table
            tables = await page.query_selector_all('table')
            print(f"[INFO] Found {len(tables)} tables")
            
            courses = []
            
            if tables:
                for table in tables:
                    rows = await table.query_selector_all('tr')
                    if len(rows) > 10:
                        print(f"[INFO] Processing table with {len(rows)} rows")
                        
                        for row in rows:
                            cells = await row.query_selector_all('td')
                            if len(cells) >= 3:
                                ma_mh = (await cells[1].text_content()).strip()
                                ten_mh = (await cells[2].text_content()).strip()
                                tom_tat = (await cells[3].text_content()).strip() if len(cells) > 3 else ''
                                
                                if ma_mh and ten_mh:
                                    courses.append({
                                        'course_id': ma_mh,
                                        'name_vi': ten_mh,
                                        'description': tom_tat
                                    })
                        break
            
            if not courses:
                # Try iframe
                print("[INFO] No table found, trying iframe...")
                iframes = await page.query_selector_all('iframe')
                print(f"[INFO] Found {len(iframes)} iframes")
                
                for iframe in iframes:
                    try:
                        frame = await iframe.content_frame()
                        if frame:
                            tables = await frame.query_selector_all('table')
                            print(f"[INFO] Found {len(tables)} tables in iframe")
                            
                            for table in tables:
                                rows = await table.query_selector_all('tr')
                                if len(rows) > 10:
                                    print(f"[INFO] Processing iframe table with {len(rows)} rows")
                                    
                                    for row in rows:
                                        cells = await row.query_selector_all('td')
                                        if len(cells) >= 3:
                                            ma_mh = (await cells[1].text_content()).strip()
                                            ten_mh = (await cells[2].text_content()).strip()
                                            tom_tat = (await cells[3].text_content()).strip() if len(cells) > 3 else ''
                                            
                                            if ma_mh and ten_mh:
                                                courses.append({
                                                    'course_id': ma_mh,
                                                    'name_vi': ten_mh,
                                                    'description': tom_tat
                                                })
                                    break
                    except Exception as e:
                        print(f"[WARN] Error in iframe: {e}")
            
            # Remove header row and duplicates
            seen = set()
            unique_courses = []
            for c in courses:
                # Skip header row
                if c['course_id'] == 'Mã MH' and c['name_vi'] == 'Tên MH':
                    continue
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
            await browser.close()

if __name__ == '__main__':
    asyncio.run(crawl_with_playwright())