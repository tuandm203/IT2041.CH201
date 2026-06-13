"""
UIT Data Crawler — Phase 1 only: download raw HTML/PDF to disk.

Saves raw HTML of each CTDT page so extraction can be done offline and re-run
without hitting the network again.

Output layout:
  data/raw/html/K{year}/{major}.html      — raw CTDT page HTML
  data/raw/html/manifest.json             — URL + cohort + major metadata
  data/raw/regulations_pdf/...            — regulation PDFs (unchanged)
  data/raw/course_catalog.csv             — master course catalog

Usage:
  python scripts/crawl.py                                  # all phases
  python scripts/crawl.py --pdf-only
  python scripts/crawl.py --catalog-only
  python scripts/crawl.py --html-only
  python scripts/crawl.py --cohorts 2022 2023 --majors CNTT KHMT
  python scripts/crawl.py --force   # re-download even if file exists
"""

import csv, json, time, re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

BASE       = "https://student.uit.edu.vn"
ROOT       = Path(__file__).parent.parent
DATA_RAW   = ROOT / "data" / "raw"
PDF_DIR    = DATA_RAW / "regulations_pdf"
HTML_DIR   = DATA_RAW / "html"
DELAY      = 1.2

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "UIT-Research-Crawler/3.0 (academic)"})

COHORTS = list(range(2012, 2027))

MAJOR_SLUGS = {
    "CNTT":     ["cu-nhan-nganh-cong-nghe-thong-tin",  "ky-su-nganh-cong-nghe-thong-tin"],
    "HTTT":     ["cu-nhan-nganh-he-thong-thong-tin",   "ky-su-nganh-he-thong-thong-tin"],
    "KHMT":     ["cu-nhan-nganh-khoa-hoc-may-tinh"],
    "KTPM":     ["cu-nhan-nganh-ky-thuat-phan-mem",    "ky-su-nganh-ky-thuat-phan-mem"],
    "KTMT":     ["cu-nhan-nganh-ky-thuat-may-tinh",    "ky-su-va-cu-nhan-nganh-ky-thuat-may-tinh",
                 "ky-su-nganh-ky-thuat-may-tinh"],
    "MMT&TTDL": ["cu-nhan-nganh-mang-may-tinh-va-truyen-thong-du-lieu",
                 "ky-su-nganh-mang-may-tinh-va-truyen-thong-du-lieu",
                 "ky-su-nganh-truyen-thong-va-mang-may-tinh",
                 "cu-nhan-nganh-truyen-thong-va-mang-may-tinh"],
    "ATTT":     ["cu-nhan-nganh-an-toan-thong-tin",    "cu-nhan-nganh-toan-thong-tin",
                 "ky-su-nganh-toan-thong-tin",          "ky-su-nganh-an-toan-thong-tin"],
    "TMDT":     ["cu-nhan-nganh-thuong-mai-dien-tu"],
    "KHdl":     ["cu-nhan-khoa-hoc-nganh-khoa-hoc-du-lieu", "cu-nhan-nganh-khoa-hoc-du-lieu"],
    "TTNT":     ["cu-nhan-nganh-tri-tue-nhan-tao"],
    "TKVM":     ["cu-nhan-nganh-thiet-ke-vi-mach"],
    "TTDM":     ["cu-nhan-nganh-truyen-thong-da-phuong-tien"],
}

REGULATION_LIST_PAGES = [
    f"{BASE}/qui-che-qui-dinh-qui-trinh",
    f"{BASE}/qui-che-qui-dinh-qui-trinh?page=1",
    f"{BASE}/quy-che-quy-dinh-dao-tao-dai-hoc-cua-dhqg-hcm",
    f"{BASE}/quy-che-quy-dinh-dao-tao-dai-hoc-cua-bo-gddt",
    f"{BASE}/mot-so-quy-trinh-danh-cho-sinh-vien",
]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def fetch_text(url: str, retries: int = 3) -> Optional[str]:
    """Fetch URL and return raw HTML text, or None on failure."""
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except Exception as e:
            print(f"    Retry {attempt+1}: {e}")
        time.sleep(DELAY * (attempt + 1))
    return None

def fetch_binary(url: str) -> Optional[bytes]:
    try:
        r = SESSION.get(url, timeout=60)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None

def safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)[:80].strip()

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — PDF regulations (unchanged logic, save to data/raw/regulations_pdf/)
# ──────────────────────────────────────────────────────────────────────────────

def get_regulation_page_links(list_url: str) -> list[tuple[str, str]]:
    html = fetch_text(list_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if re.search(r'/\d{2}[-_]', href) or "/thongbao/" in href:
            if len(text) > 5 and any(k in text.lower() for k in ["quy","hướng","quyết"]):
                full = href if href.startswith("http") else BASE + href
                links.append((text[:80], full))
    seen = set()
    return [(t,u) for t,u in links if u not in seen and not seen.add(u)]

def crawl_pdfs(force: bool = False):
    print("\n[Phase 1] Downloading regulation PDFs...")
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = 0
    manifest = []
    visited_pages, visited_pdfs = set(), set()

    def download_pdf(label, url, subfolder=""):
        nonlocal downloaded, skipped
        if url in visited_pdfs:
            return
        visited_pdfs.add(url)
        fname = safe_filename(Path(urlparse(url).path).name)
        if not fname.endswith(".pdf"):
            fname += ".pdf"
        dest = (PDF_DIR / subfolder / fname) if subfolder else (PDF_DIR / fname)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            skipped += 1
            manifest.append({"file": str(dest.relative_to(ROOT)), "label": label, "url": url, "status": "skipped"})
            return
        data = fetch_binary(url)
        if data:
            dest.write_bytes(data)
            downloaded += 1
            manifest.append({"file": str(dest.relative_to(ROOT)), "label": label, "url": url, "status": "downloaded"})
            print(f"      [dl] {fname}")
        time.sleep(DELAY)

    all_reg_pages = []
    for lu in REGULATION_LIST_PAGES:
        all_reg_pages.extend(get_regulation_page_links(lu))
        time.sleep(DELAY)
    seen = set()
    all_reg_pages = [(t,u) for t,u in all_reg_pages if u not in seen and not seen.add(u)]
    print(f"  Found {len(all_reg_pages)} regulation pages")

    for title, page_url in all_reg_pages:
        if page_url in visited_pages:
            continue
        visited_pages.add(page_url)
        html = fetch_text(page_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        pdf_links = [(a.get_text(strip=True), urljoin(page_url, a["href"]))
                     for a in soup.find_all("a", href=True) if ".pdf" in a["href"].lower()]
        if not pdf_links:
            continue
        slug = re.sub(r'\W+', '_', title[:40]).strip('_').lower()
        print(f"  [{title[:55]}] ({len(pdf_links)} PDFs)")
        for label, url in pdf_links:
            download_pdf(label, url, slug)
        time.sleep(DELAY)

    if manifest:
        write_csv(PDF_DIR / "manifest.csv", manifest, ["file","label","url","status"])
    print(f"\n  Downloaded: {downloaded}, Skipped: {skipped}")

# ──────────────────────────────────────────────────────────────────────────────
# Phase 2a — Master course catalog
# ──────────────────────────────────────────────────────────────────────────────

def crawl_course_catalog(force: bool = False):
    print("\n[Phase 2a] Crawling master course catalog...")
    out = DATA_RAW / "course_catalog.csv"
    if out.exists() and not force:
        print(f"  Already exists ({out}), skipping. Use --force to re-download.")
        return

    html = fetch_text(f"{BASE}/danh-muc-mon-hoc-dai-hoc")
    if not html:
        print("  FAILED")
        return
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    courses, SKIP = [], {"mã","số tt","tên"}
    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
        if not cells or len(cells) < 10:
            continue
        if cells[0].lower() in SKIP or cells[1].lower() in SKIP or not cells[1]:
            continue
        courses.append({
            "stt": cells[0], "course_id": cells[1],
            "name_vi": cells[2], "name_en": cells[3],
            "is_open": cells[4], "managed_by": cells[5], "course_type": cells[6],
            "old_code":         cells[7]  if len(cells) > 7  else "",
            "equivalent_ids":   cells[8]  if len(cells) > 8  else "",
            "prerequisite_ids": cells[9]  if len(cells) > 9  else "",
            "prior_ids":        cells[10] if len(cells) > 10 else "",
            "credits_lt":       cells[11] if len(cells) > 11 else "",
            "credits_th":       cells[12] if len(cells) > 12 else "",
        })
    write_csv(out, courses, list(courses[0].keys()) if courses else [])
    print(f"  Saved {len(courses)} courses → {out}")

# ──────────────────────────────────────────────────────────────────────────────
# Phase 2b — CTDT page HTML (raw save only, NO parsing here)
# ──────────────────────────────────────────────────────────────────────────────

def get_major_urls(year: int) -> dict[str, str]:
    found = {}
    for cohort_url in [
        f"{BASE}/chuong-trinh-dao-tao/ctdt-khoa-{year}",
        f"{BASE}/cqui/ctdt-khoa-{year}",
    ]:
        html = fetch_text(cohort_url)
        if html:
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "ap-dung-tu-khoa" not in href:
                    continue
                full = href if href.startswith("http") else BASE + href
                for major, slugs in MAJOR_SLUGS.items():
                    if major in found:
                        continue
                    for slug in slugs:
                        if slug in href:
                            found[major] = full
                            break
            if found:
                break
    return found

def crawl_ctdt_html(target_cohorts=None, target_majors=None, force: bool = False,
                    from_manifest: bool = False):
    """
    Download raw HTML for each CTDT page → data/raw/html/K{year}/{major}.html.
    Does NOT parse. Extraction is handled by extract.py.

    from_manifest=True: use URLs already in manifest.json (faster, no URL discovery).
    """
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = HTML_DIR / "manifest.json"
    manifest: dict = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    stats = {"downloaded": 0, "skipped": 0, "missing": 0, "error": 0}

    if from_manifest and manifest:
        # Use pre-known URLs — filter by cohort/major if requested
        entries = list(manifest.items())
        if target_cohorts:
            cohort_set = {f"K{y}" for y in target_cohorts}
            entries = [(k, v) for k, v in entries if v["cohort"] in cohort_set]
        if target_majors:
            major_set = set(target_majors)
            entries = [(k, v) for k, v in entries if v["major"] in major_set]
        print(f"\n[Phase 2b] Downloading CTDT HTML from manifest — {len(entries)} pages")
        for key, meta in sorted(entries):
            _download_one(key, meta["cohort"], meta["major"], meta["url"],
                          manifest, stats, force)
    else:
        # Discover URLs by crawling cohort index pages
        tc = target_cohorts or COHORTS
        tm = set(target_majors or MAJOR_SLUGS.keys())
        print(f"\n[Phase 2b] Discovering + downloading CTDT HTML — {len(tc)} cohorts × {len(tm)} majors")
        for year in tc:
            cohort = f"K{year}"
            print(f"\n  {cohort}:")
            major_urls = get_major_urls(year)
            for major in tm:
                url = major_urls.get(major)
                if not url:
                    print(f"    [{major}] not found")
                    stats["missing"] += 1
                    continue
                key = f"{cohort}/{major}"
                manifest[key] = {"cohort": cohort, "major": major, "url": url}
                _download_one(key, cohort, major, url, manifest, stats, force)

    write_json(manifest_path, manifest)
    print(f"\n  Downloaded:{stats['downloaded']} Skipped:{stats['skipped']} "
          f"Missing:{stats['missing']} Error:{stats['error']}")
    print(f"  Manifest → {manifest_path}")


def _download_one(key: str, cohort: str, major: str, url: str,
                  manifest: dict, stats: dict, force: bool):
    dest = HTML_DIR / cohort / f"{major}.html"
    if dest.exists() and not force:
        print(f"    [{key}] already saved — skip")
        stats["skipped"] += 1
        return
    print(f"    [{key}] {url}")
    html = fetch_text(url)
    if not html:
        print(f"      → FAILED")
        stats["error"] += 1
        time.sleep(DELAY)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    stats["downloaded"] += 1
    print(f"      → saved ({len(html)//1024} KB)")
    time.sleep(DELAY)

# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="UIT crawler — download raw data only")
    p.add_argument("--pdf-only",      action="store_true", help="Phase 1 only: PDFs")
    p.add_argument("--catalog-only",  action="store_true", help="Phase 2a only: course catalog")
    p.add_argument("--html-only",     action="store_true", help="Phase 2b only: CTDT HTML pages")
    p.add_argument("--cohorts",  nargs="+", type=int,   help="Limit to specific cohort years")
    p.add_argument("--majors",   nargs="+",              help="Limit to specific majors")
    p.add_argument("--force",           action="store_true", help="Re-download even if file exists")
    p.add_argument("--from-manifest",   action="store_true", help="Use URLs from manifest.json (skip URL discovery)")
    args = p.parse_args()

    run_all = not (args.pdf_only or args.catalog_only or args.html_only)

    if run_all or args.pdf_only:
        crawl_pdfs(force=args.force)

    if run_all or args.catalog_only:
        crawl_course_catalog(force=args.force)
        time.sleep(DELAY)

    if run_all or args.html_only:
        crawl_ctdt_html(
            target_cohorts=args.cohorts,
            target_majors=args.majors,
            force=args.force,
            from_manifest=args.from_manifest,
        )
