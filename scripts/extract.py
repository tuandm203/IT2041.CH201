"""
extract.py - Parse raw CTDT HTML files into structured program JSON.

Input:  data/raw/html/{cohort}/{major}.html  (from crawl.py)
Output: data/programs/{cohort}/{major}/{program_type}.json

Handles 3 layout variants:
  fieldset      - K2012–K2022: fieldset.collapsible top-level elements
  acc_multi     - K2023–K2025 (multi-program files): dl.ckeditor-accordion, DTs labeled A./B./C.
  acc_single    - K2025 (single-program files): dl.ckeditor-accordion, DTs labeled 1./2./3.

Usage:
  python scripts/extract.py                          # all files
  python scripts/extract.py --cohorts K2023 K2024    # filter cohorts
  python scripts/extract.py --majors CNTT KTPM       # filter majors
  python scripts/extract.py --force                  # re-extract even if output exists
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from datetime import datetime

from bs4 import BeautifulSoup, Tag


def nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)

ROOT     = Path(__file__).parent.parent
HTML_DIR = ROOT / "data" / "raw" / "html"
OUT_DIR  = ROOT / "data" / "programs"
MANIFEST = HTML_DIR / "manifest.json"

# ── regex helpers ─────────────────────────────────────────────────────────────
COURSE_ID_RE  = re.compile(r'^[A-Z]{1,5}\d{2,6}[A-Z0-9]?$')
INT_RE        = re.compile(r'\d+')
CREDITS_RE    = re.compile(
    r'[Tt]ổng\s+(?:cộng|số\s+tín\s+chỉ[^:]*?)\s*(\d+)\s*tín\s*chỉ',
)
# Matches total credit requirements; captures the number
TOTAL_MIN_RE  = re.compile(
    r'tối\s*thiểu\s+(?:là\s+)?(\d+)\s*tín\s*chỉ'
    r'|tích\s*lũy\s*(?:tối\s*thiểu\s*(?:là\s*)?)?(\d+)\s*tín\s*chỉ'
    r'|≥\s*(\d+)\s*tín\s*chỉ'
    r'|(\d+)\s*tín\s*chỉ[^.]{0,30}tối\s*thiểu',
    re.IGNORECASE,
)
SEMESTER_RE   = re.compile(
    r'[Hh]ọc\s+[Kk]ỳ\s+(\d+)'
    r'|HK\s*(\d+)'
    r'|\bHK\s*([IVX]+)\b'
    r'|[Kk]ỳ\s+(\d+)'
    r'|[Ss]emester\s+(\d+)',
)
ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
         'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10}


def is_course_id(s: str) -> bool:
    return bool(s) and bool(COURSE_ID_RE.match(s.strip()))


def parse_roman(s: str) -> int | None:
    s = s.upper().strip()
    return ROMAN.get(s)


def semester_from_text(txt: str) -> int | None:
    m = SEMESTER_RE.search(txt)
    if not m:
        return None
    for i, g in enumerate(m.groups()):
        if g:
            if i < 2:  # digit groups
                return int(g)
            elif i == 2:  # roman
                return parse_roman(g)
            else:
                return int(g)
    return None


def cell_text(td) -> str:
    return td.get_text(' ', strip=True)


# ── program type detection ─────────────────────────────────────────────────────
def infer_program_type(label: str) -> str:
    u = nfc(label.upper())
    if 'TÀI NĂNG' in u:
        return 'talent'
    if 'QUỐC TẾ' in u or 'CTTT' in u or 'TIÊN TIẾN' in u:
        return 'international'
    if 'LIÊN THÔNG' in u and 'TỪ XA' in u:
        return 'transfer_distance'
    if 'LIÊN THÔNG' in u:
        return 'transfer'
    if 'VĂN BẰNG' in u and 'TỪ XA' in u:
        return 'second_degree_distance'
    if 'VĂN BẰNG' in u or 'VB2' in u:
        return 'second_degree'
    if 'TỪ XA' in u:
        return 'distance'
    if 'CHẤT LƯỢNG CAO' in u or 'CLC' in u or 'VIỆT NHẬT' in u or 'NHẬT BẢN' in u:
        return 'high_quality'
    return 'standard'


# ── layout detection ──────────────────────────────────────────────────────────
def detect_layout(soup: BeautifulSoup) -> str:
    if soup.find('dl', class_='ckeditor-accordion'):
        dts = soup.find('dl', class_='ckeditor-accordion').find_all('dt', recursive=False)
        if dts:
            first = dts[0].get_text(strip=True)
            # A. / B. style → multi-program
            if re.match(r'^[A-Z][\.\s]', first):
                return 'acc_multi'
        return 'acc_single'
    if soup.find('fieldset', class_='collapsible'):
        return 'fieldset'
    return 'unknown'


# ── get top-level program blocks ───────────────────────────────────────────────
def get_program_blocks(soup: BeautifulSoup, layout: str) -> list[tuple[str, Tag]]:
    """
    Returns list of (label, content_tag) for each program variant in the page.
    content_tag is the element containing headings + tables for that program.
    """
    blocks = []

    if layout == 'fieldset':
        for fs in soup.select('fieldset.collapsible'):
            # Only top-level fieldsets (not nested inside another fieldset)
            if fs.find_parent('fieldset'):
                continue
            legend = fs.find('legend')
            if not legend:
                continue
            label = legend.get_text(' ', strip=True)
            label_upper = nfc(label.upper())
            # Skip non-curriculum sections
            if any(kw in label_upper for kw in (
                'KẾ HOẠCH', 'MÔ TẢ', 'CHUẨN ĐẦU RA', 'GIỚI THIỆU',
            )):
                if 'KẾ HOẠCH' in label_upper:
                    wrapper = fs.find(class_='fieldset-wrapper')
                    if wrapper:
                        blocks.append(('__schedule__', wrapper))
                continue
            wrapper = fs.find(class_='fieldset-wrapper')
            if wrapper:
                blocks.append((label, wrapper))

    elif layout == 'acc_multi':
        accordion = soup.find('dl', class_='ckeditor-accordion')
        dts = accordion.find_all('dt', recursive=False)
        dds = accordion.find_all('dd', recursive=False)
        for dt, dd in zip(dts, dds):
            label = dt.get_text(' ', strip=True)
            label_upper = nfc(label.upper())
            if 'KẾ HOẠCH' in label_upper:
                blocks.append(('__schedule__', dd))
            else:
                blocks.append((label, dd))

    elif layout == 'acc_single':
        # Single program: look for the CHƯƠNG TRÌNH section
        accordion = soup.find('dl', class_='ckeditor-accordion')
        dts = accordion.find_all('dt', recursive=False)
        dds = accordion.find_all('dd', recursive=False)
        # Use page <title> or first DT as program label
        title_tag = soup.find('title') or soup.find('h1')
        page_label = title_tag.get_text(' ', strip=True) if title_tag else 'Chương trình đào tạo'
        # NFC-normalize before string search (HTML may use NFD)
        for dt, dd in zip(dts, dds):
            dt_text = nfc(dt.get_text(' ', strip=True))
            dt_upper = dt_text.upper()
            if 'KẾ HOẠCH' in dt_upper:
                blocks.append(('__schedule__', dd))
            elif 'CHƯƠNG TRÌNH' in dt_upper and 'CHUẨN ĐẦU RA' not in dt_upper and 'MA TRẬN' not in dt_upper:
                # Use the DT text as label so we can infer program type
                blocks.append((dt_text, dd))

    return blocks


# ── table parsing ──────────────────────────────────────────────────────────────
def detect_col_map(header_row) -> dict[str, int]:
    """Map column names to indices from a header row."""
    col_map = {}
    cells = header_row.find_all(['th', 'td'])
    for i, td in enumerate(cells):
        t = cell_text(td).lower().strip()
        if t in ('stt', 'tt', '#'):
            col_map.setdefault('stt', i)
        elif 'mã' in t and ('môn' in t or 'hp' in t):
            col_map.setdefault('course_id', i)
        elif 'tên môn' in t or 'tên hp' in t or 'tên học phần' in t:
            col_map.setdefault('name', i)
        elif t == 'tc' or t == 'số tc' or 'tín chỉ' in t and len(t) < 10:
            col_map.setdefault('tc', i)
        elif t == 'lt' or t == 'lý thuyết':
            col_map.setdefault('lt', i)
        elif t == 'th' or t == 'thực hành' or t == 'thực tế':
            col_map.setdefault('th', i)
        elif 'ghi chú' in t or 'ghi chu' in t:
            col_map.setdefault('note', i)
        elif 'bắt buộc' in t or 'chọn' in t:
            col_map.setdefault('required_flag', i)
    return col_map


def is_header_row(row) -> bool:
    cells = row.find_all(['th', 'td'])
    texts = [cell_text(c).lower() for c in cells]
    return any('mã môn' in t or 'mã hp' in t or 'mã học phần' in t for t in texts)


def is_group_header_row(row, col_map: dict) -> bool:
    """Sub-group label rows spanning multiple columns (e.g., 'Lý luận chính trị  10')."""
    cells = row.find_all(['td', 'th'])
    if not cells:
        return False
    # Check colspan
    first_colspan = int(cells[0].get('colspan', 1))
    if first_colspan >= 3:
        return True
    # Few non-empty cells, no course ID
    non_empty = [c for c in cells if cell_text(c)]
    if len(non_empty) <= 2:
        cid_col = col_map.get('course_id')
        if cid_col is not None and cid_col < len(cells):
            cid_text = cell_text(cells[cid_col]).strip()
            if not is_course_id(cid_text):
                return True
    return False


def parse_course_table(table) -> list[dict]:
    """
    Parse a course table and return a flat list of course dicts.
    Each dict has: course_id, name, credits, lt, th, group_name, note, is_mandatory, semester
    """
    rows = table.find_all('tr')
    if not rows:
        return []

    col_map = {}
    courses = []
    current_group = ''
    current_semester = None

    # Try to find semester context from table caption or surrounding text
    caption = table.find('caption')
    if caption:
        current_semester = semester_from_text(cell_text(caption))

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue

        # Header row
        if is_header_row(row):
            col_map = detect_col_map(row)
            continue

        if not col_map:
            # Fallback: detect from first row with a course ID
            texts = [cell_text(c) for c in cells]
            for i, t in enumerate(texts):
                if is_course_id(t):
                    col_map = {'course_id': i, 'name': i + 1, 'tc': i + 2, 'lt': i + 3, 'th': i + 4}
                    break

        # Check for semester header inside table (e.g., 'Học kỳ 1' spanning a column)
        row_text = row.get_text(' ', strip=True)
        sem = semester_from_text(row_text)
        # Only treat as semester header if it doesn't look like a course row
        if sem and not any(is_course_id(cell_text(c)) for c in cells):
            current_semester = sem
            # May also be a group header
            if is_group_header_row(row, col_map):
                current_group = cells[0].get_text(' ', strip=True)
            continue

        # Group header row
        if is_group_header_row(row, col_map):
            # Use empty separator to avoid splitting words across inline tags
            current_group = cells[0].get_text('', strip=True)
            # Strip credit counts from end: "Lý luận chính trị10"
            current_group = re.sub(r'\d+\s*$', '', current_group).strip()
            # Re-normalize Vietnamese characters (may be NFD from HTML)
            current_group = nfc(current_group)
            continue

        # Course row
        cid_col = col_map.get('course_id')
        if cid_col is None or cid_col >= len(cells):
            continue
        cid = cell_text(cells[cid_col]).strip()
        if not is_course_id(cid):
            continue

        def safe_int(col_key: str) -> int | None:
            col = col_map.get(col_key)
            if col is None or col >= len(cells):
                return None
            m = INT_RE.search(cell_text(cells[col]))
            return int(m.group()) if m else None

        def safe_str(col_key: str) -> str:
            col = col_map.get(col_key)
            if col is None or col >= len(cells):
                return ''
            return cell_text(cells[col])

        # is_mandatory from Bắt buộc/Chọn column or group name
        req_flag = safe_str('required_flag').lower()
        if req_flag:
            is_mandatory = 'b' in req_flag or 'bắt buộc' in req_flag
        else:
            gname_lower = current_group.lower()
            is_mandatory = not ('tự chọn' in gname_lower)

        courses.append({
            'course_id':   cid,
            'course_name': safe_str('name'),
            'credits':     safe_int('tc'),
            'credits_lt':  safe_int('lt'),
            'credits_th':  safe_int('th'),
            'group_name':  current_group,
            'note':        safe_str('note') or None,
            'is_mandatory': is_mandatory,
            'semester':    current_semester,
        })

    return courses


def is_course_table(table) -> bool:
    """Returns True if this table contains curriculum course rows."""
    rows = table.find_all('tr')
    for row in rows:
        cells = row.find_all(['td', 'th'])
        for c in cells:
            if is_course_id(cell_text(c).strip()):
                return True
    return False


# ── Kế hoạch giảng dạy extraction ─────────────────────────────────────────────
def extract_semester_schedule(content_elem) -> dict[str, int]:
    """
    Extract semester assignments from Kế hoạch giảng dạy tables.
    Returns {course_id: semester_number}.
    """
    schedule = {}
    current_semester = None

    for table in content_elem.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            row_text = row.get_text(' ', strip=True)

            # Detect semester header rows
            sem = semester_from_text(row_text)
            if sem and not any(is_course_id(cell_text(c).strip()) for c in cells):
                current_semester = sem
                continue

            # Course row: first cell (or second) is course ID
            for c in cells:
                t = cell_text(c).strip()
                if is_course_id(t) and current_semester:
                    schedule[t] = current_semester
                    break

    return schedule


# ── main content walker ────────────────────────────────────────────────────────
def find_total_credits(elem) -> int | None:
    """Scan an HTML element for the program's minimum total credit requirement."""
    full_text = nfc(elem.get_text(' '))
    best = None
    for line in full_text.splitlines():
        line = line.strip()
        m = TOTAL_MIN_RE.search(line)
        if m:
            val = int(next(g for g in m.groups() if g))
            if 60 <= val <= 300:
                if best is None or val > best:
                    best = val
    return best


def walk_content(
    content_elem,
    schedule: dict[str, int] | None = None,
    total_credits: int | None = None,
) -> tuple[list[dict], list[dict], int | None]:
    """
    Walk the content element and collect knowledge blocks and courses.

    Returns:
        knowledge_blocks: list of block metadata dicts
        courses:          flat list of course dicts
        total_credits:    minimum program credits (or None)
    """
    knowledge_blocks = []
    all_courses = []

    # Heading stack: {level: text}
    heading_stack: dict[int, str] = {}
    current_block_credits: int | None = None
    block_counter = 0

    # Skip headings that don't introduce course content
    SKIP_SECTIONS = {
        'giới thiệu', 'mục tiêu', 'vị trí', 'quan điểm', 'hình thức',
        'chuẩn đầu ra', 'tỷ lệ', 'phân bố', 'quy định', 'điều kiện',
        'kế hoạch giảng dạy', 'ghi chú', 'chú thích',
    }

    def current_heading_path() -> str:
        return ' > '.join(heading_stack[l] for l in sorted(heading_stack))

    def current_block_name() -> str:
        if not heading_stack:
            return ''
        return heading_stack[max(heading_stack)]

    def iter_elements(parent):
        """Yield h1-h4, p, table in document order, recursing into div/span wrappers."""
        for child in parent.children:
            if not isinstance(child, Tag):
                continue
            if child.name in ('h1', 'h2', 'h3', 'h4', 'p', 'table'):
                yield child
            elif child.name in ('div', 'section', 'article', 'span'):
                # Recurse through generic container elements
                yield from iter_elements(child)
            # Ignore fieldset/dl/ul/ol (handled at higher level)

    for child in iter_elements(content_elem):
        # ── headings ──────────────────────────────────────────────────────────
        if child.name in ('h1', 'h2', 'h3', 'h4'):
            level = int(child.name[1])
            text = child.get_text(' ', strip=True)
            # Prune deeper levels
            for l in list(heading_stack.keys()):
                if l >= level:
                    del heading_stack[l]
            heading_stack[level] = text
            current_block_credits = None  # reset on new heading

        # ── paragraphs: look for block-level required credits ─────────────────
        elif child.name == 'p':
            txt = child.get_text(' ', strip=True)
            m2 = CREDITS_RE.search(nfc(txt))
            if m2:
                val = int(m2.group(1))
                if 5 < val < 200:
                    current_block_credits = val

        # ── tables ────────────────────────────────────────────────────────────
        elif child.name == 'table':

            if not is_course_table(child):
                continue

            block_name = current_block_name()
            # Skip non-curriculum headings
            block_lower = block_name.lower()
            if any(kw in block_lower for kw in SKIP_SECTIONS):
                continue

            block_counter += 1
            block_id = f'B{block_counter:02d}'

            is_elective = 'tự chọn' in block_lower

            kb = {
                'block_id':       block_id,
                'block_name':     block_name,
                'heading_path':   current_heading_path(),
                'required_credits': current_block_credits,
                'is_elective':    is_elective,
            }
            knowledge_blocks.append(kb)

            courses = parse_course_table(child)
            for c in courses:
                # Apply semester from schedule if not already set
                if c['semester'] is None and schedule:
                    c['semester'] = schedule.get(c['course_id'])
                c['block_id']   = block_id
                c['block_name'] = block_name
                all_courses.append(c)

    return knowledge_blocks, all_courses, total_credits


# ── per-file extraction ────────────────────────────────────────────────────────
def extract_file(
    html_path: Path,
    cohort: str,
    major: str,
    source_url: str,
) -> list[dict]:
    """Parse one HTML file and return list of program dicts (one per program type)."""
    soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='replace'), 'lxml')
    layout = detect_layout(soup)
    if layout == 'unknown':
        print(f'  [WARN] unknown layout for {html_path}', file=sys.stderr)
        return []

    program_blocks = get_program_blocks(soup, layout)
    if not program_blocks:
        print(f'  [WARN] no program blocks for {html_path}', file=sys.stderr)
        return []

    # Collect schedule blocks (acc_single puts __schedule__ as a separate entry)
    schedule_elem = None
    filtered_blocks = []
    for label, elem in program_blocks:
        if label == '__schedule__':
            schedule_elem = elem
        else:
            filtered_blocks.append((label, elem))

    # Build global schedule map (course_id → semester)
    schedule: dict[str, int] = {}
    if schedule_elem:
        schedule.update(extract_semester_schedule(schedule_elem))

    # For acc_single, scan the full page for total_credits (may be in a separate DT)
    # For acc_multi/fieldset, scan per-block to avoid mixing programs
    page_total_credits = find_total_credits(soup) if layout == 'acc_single' else None

    programs = []
    seen_types: dict[str, int] = {}

    for label, content_elem in filtered_blocks:
        program_type = infer_program_type(label)

        # Also look for schedule section inside fieldset variant
        local_schedule = dict(schedule)
        if layout == 'fieldset':
            for t in content_elem.find_all('table'):
                rows = t.find_all('tr')
                for row in rows:
                    if semester_from_text(row.get_text()):
                        local_schedule.update(extract_semester_schedule(t))
                        break

        # For acc_single: use full-page scan (credits may be in a different section)
        # For acc_multi: use block-level scan (each DD is a separate program)
        # For fieldset: try block-level first, fall back to page-level
        if layout == 'acc_single':
            block_total_credits = page_total_credits
        elif layout == 'acc_multi':
            block_total_credits = find_total_credits(content_elem)
        else:  # fieldset
            block_total_credits = find_total_credits(content_elem)
            if block_total_credits is None:
                block_total_credits = find_total_credits(soup)

        knowledge_blocks, courses, total_credits = walk_content(
            content_elem, local_schedule, total_credits=block_total_credits
        )

        if not courses and not knowledge_blocks:
            continue

        # Deduplicate program types with a suffix (only count emitted programs)
        count = seen_types.get(program_type, 0)
        seen_types[program_type] = count + 1
        slug = program_type if count == 0 else f'{program_type}_{count + 1}'

        program_id = f'{cohort}-{major}-{slug}'

        programs.append({
            'program_id':        program_id,
            'cohort':            cohort,
            'major':             major,
            'program_type':      program_type,
            'program_label':     label,
            'source_url':        source_url,
            'extracted_at':      datetime.utcnow().isoformat() + 'Z',
            'total_credits':     total_credits,
            'designed_semesters': None,
            'knowledge_blocks':  knowledge_blocks,
            'courses':           courses,
        })

    return programs


# ── write output ───────────────────────────────────────────────────────────────
def write_program(program: dict, force: bool = False) -> Path:
    cohort = program['cohort']
    major  = program['major']
    slug   = program['program_type']
    # If there are multiple of same type, use program_id slug
    pid = program['program_id']
    parts = pid.split('-', 2)
    slug_from_id = parts[2] if len(parts) == 3 else slug

    out_path = OUT_DIR / cohort / major / f'{slug_from_id}.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not force:
        return out_path

    out_path.write_text(json.dumps(program, ensure_ascii=False, indent=2))
    return out_path


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Extract CTDT data from raw HTML files')
    parser.add_argument('--cohorts', nargs='+', help='Filter cohorts (e.g. K2023 K2024)')
    parser.add_argument('--majors',  nargs='+', help='Filter majors (e.g. CNTT KTPM)')
    parser.add_argument('--force',   action='store_true', help='Overwrite existing outputs')
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

    html_files = sorted(HTML_DIR.glob('K*/*.html'))
    if args.cohorts:
        html_files = [f for f in html_files if f.parent.name in args.cohorts]
    if args.majors:
        html_files = [f for f in html_files if f.stem in args.majors]

    total_programs = 0
    total_courses  = 0
    skipped        = 0

    for html_path in html_files:
        cohort = html_path.parent.name
        major  = html_path.stem

        key = f'{cohort}/{major}'
        source_url = manifest.get(key, {}).get('url', '')

        programs = extract_file(html_path, cohort, major, source_url)

        if not programs:
            skipped += 1
            print(f'  [{cohort}/{major}] no programs extracted')
            continue

        for prog in programs:
            out = write_program(prog, force=args.force)
            nc = len(prog['courses'])
            nkb = len(prog['knowledge_blocks'])
            total_programs += 1
            total_courses  += nc
            print(f'  [{cohort}/{major}] {prog["program_type"]:30s} {nc:4d} courses  {nkb:3d} blocks → {out.relative_to(ROOT)}')

    print()
    print(f'Done: {total_programs} programs, {total_courses} total courses, {skipped} files skipped')


if __name__ == '__main__':
    main()
