"""
Generate COURSE_PREREQUISITE and COURSE_PRIOR global rules from course_catalog.csv.

The CTDT pages do not include prerequisite columns in their tables.
The master catalog (danh-muc-mon-hoc-dai-hoc) is the authoritative source.

Output: data/rules/global/course_prerequisites_catalog.json
"""

import csv, json, re
from pathlib import Path

ROOT      = Path(__file__).parent.parent
CATALOG   = ROOT / "data" / "raw" / "course_catalog.csv"
OUT_FILE  = ROOT / "data" / "rules" / "global" / "course_prerequisites_catalog.json"

COURSE_ID_RE = re.compile(r'^[A-Z]{1,5}\d{2,6}[A-Z0-9]?$')

def looks_course_id(s: str) -> bool:
    s = s.strip()
    return bool(s) and len(s) <= 12 and bool(COURSE_ID_RE.match(s))

def split_ids(raw: str) -> list[str]:
    """Split 'IT001IT002' or 'IT001, IT002' into list of valid course IDs."""
    # Try comma/space split first
    parts = [p.strip() for p in re.split(r'[,;\s]+', raw) if p.strip()]
    # If no valid IDs found, try splitting by capital letter patterns
    if not any(looks_course_id(p) for p in parts):
        parts = re.findall(r'[A-Z]{1,5}\d{2,6}[A-Z0-9]?', raw)
    return [p for p in parts if looks_course_id(p)]


def main():
    rules = []
    rule_counter = 1

    with open(CATALOG, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cid   = row["course_id"].strip()
            cname = row["name_vi"].strip()
            prereq_raw  = row.get("prerequisite_ids", "").strip()
            prior_raw   = row.get("prior_ids", "").strip()

            if not cid:
                continue

            course_ref = {"course_id": cid, "course_name": cname}

            if prereq_raw:
                prereq_ids = split_ids(prereq_raw)
                if prereq_ids:
                    rules.append({
                        "rule_id":       f"CAT-PRE-{rule_counter:04d}",
                        "rule_tier":     "global",
                        "rule_type":     "COURSE_PREREQUISITE",
                        "source":        {
                            "document": "danh-muc-mon-hoc-dai-hoc",
                            "article":  "course_catalog",
                            "section":  None,
                            "url":      "https://student.uit.edu.vn/danh-muc-mon-hoc-dai-hoc"
                        },
                        "applies_to":    {"cohorts": None, "majors": None, "program_types": None},
                        "overrides_rule": None,
                        "severity":      "hard",
                        "note":          None,
                        "payload": {
                            "course":        course_ref,
                            "requires_all":  [{"course_id": c} for c in prereq_ids],
                            "requires_any":  [],
                            "min_grade":     5.0,
                        }
                    })
                    rule_counter += 1

            if prior_raw:
                prior_ids = split_ids(prior_raw)
                if prior_ids:
                    rules.append({
                        "rule_id":       f"CAT-PRI-{rule_counter:04d}",
                        "rule_tier":     "global",
                        "rule_type":     "COURSE_PRIOR",
                        "source":        {
                            "document": "danh-muc-mon-hoc-dai-hoc",
                            "article":  "course_catalog",
                            "section":  None,
                            "url":      "https://student.uit.edu.vn/danh-muc-mon-hoc-dai-hoc"
                        },
                        "applies_to":    {"cohorts": None, "majors": None, "program_types": None},
                        "overrides_rule": None,
                        "severity":      "soft",
                        "note":          None,
                        "payload": {
                            "course":        course_ref,
                            "prior_courses": [{"course_id": c} for c in prior_ids],
                        }
                    })
                    rule_counter += 1

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "description": "COURSE_PREREQUISITE và COURSE_PRIOR rules tổng hợp từ danh mục môn học UIT. "
                       "Source: https://student.uit.edu.vn/danh-muc-mon-hoc-dai-hoc",
        "source_document": "danh-muc-mon-hoc-dai-hoc",
        "note": "Áp dụng toàn trường, không phân biệt khóa/ngành. "
                "Prerequisite từ CTĐT cụ thể (nếu có) sẽ override rule này.",
        "rules": rules,
    }
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    prereq_count = sum(1 for r in rules if r["rule_type"] == "COURSE_PREREQUISITE")
    prior_count  = sum(1 for r in rules if r["rule_type"] == "COURSE_PRIOR")
    print(f"Generated {len(rules)} rules → {OUT_FILE}")
    print(f"  COURSE_PREREQUISITE: {prereq_count}")
    print(f"  COURSE_PRIOR:        {prior_count}")


if __name__ == "__main__":
    main()
