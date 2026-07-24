"""
Crawl course descriptions from daa.uit.edu.vn
Parse meta description tag which contains all course data
"""
import requests
import json
import re
import html
import sys
import os
from pathlib import Path

# Force UTF-8 for Windows console
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent

def crawl_course_descriptions():
    url = 'https://daa.uit.edu.vn/content/bang-tom-tat-mon-hoc'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    r = requests.get(url, headers=headers, timeout=30)
    
    # Parse meta description
    meta_match = re.search(r'<meta name="description" content="(.*?)"', r.text, re.DOTALL)
    if not meta_match:
        print("[ERROR] No meta description found")
        return []
    
    content = meta_match.group(1)
    # Unescape HTML entities
    content = html.unescape(content)
    
    # Remove "STT Mã MH Tên MH Tóm tắt môn học" header
    content = re.sub(r'^STT\s+Mã MH\s+Tên MH\s+Tóm tắt môn học\s*', '', content)
    
    # Parse: so + ma (6-8 ky tu chu hoa/so) + phan con lai
    pattern = r'(\d+)\s+([A-Z0-9]{5,8})\s+(.*?)(?=\d+\s+[A-Z0-9]{5,8}\s|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    courses = []
    for stt, ma_mh, rest in matches:
        rest = rest.strip()
        if not rest or not ma_mh:
            continue
        
        desc_keywords = [
            'Trinh bay', 'Cung cap', 'Mon hoc nay', 'Mon hoc', 
            'Gioi thieu', 'Trang bi', 'Hoc phan', 'Sinh vien se',
            'Noi dung', 'Muc tieu', 'Cac kien thuc'
        ]
        
        name = rest
        description = ''
        
        min_idx = len(rest)
        found_kw = None
        for kw in desc_keywords:
            idx = rest.find(kw)
            if idx != -1 and idx < min_idx:
                min_idx = idx
                found_kw = kw
        
        if found_kw:
            name = rest[:min_idx].strip()
            description = rest[min_idx:].strip()
        else:
            parts = rest.split('. ', 1)
            if len(parts) > 1 and len(parts[0]) < 60:
                name = parts[0].strip()
                description = parts[1].strip()
            else:
                if len(rest) < 50:
                    name = rest
                    description = ''
                else:
                    for sep in [' - ', ': ']:
                        if sep in rest:
                            idx = rest.index(sep)
                            if idx < 50:
                                name = rest[:idx].strip()
                                description = rest[idx+len(sep):].strip()
                                break
        
        name = re.sub(r'\s+', ' ', name).strip()
        description = re.sub(r'\s+', ' ', description).strip()
        
        courses.append({
            'course_id': ma_mh,
            'name_vi': name,
            'description': description
        })
    
    # Remove duplicates by course_id
    seen = set()
    unique_courses = []
    for c in courses:
        if c['course_id'] not in seen:
            seen.add(c['course_id'])
            unique_courses.append(c)
    
    print(f"[OK] Parsed {len(unique_courses)} unique courses")
    
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

if __name__ == '__main__':
    crawl_course_descriptions()