"""
gen_rules.py - Generate local curriculum rules from structured program data.

Input:  data/programs/{cohort}/{major}/{program_type}.json  (from extract.py)
Output: data/rules/local/{cohort}/{major}.json

Generates:
  PROGRAM_STRUCTURE       - overall program layout (blocks + total_credits + course list)
  COURSE_GROUP_REQUIREMENT - per-block course groups (required and elective)

Usage:
  python scripts/gen_rules.py                          # all files
  python scripts/gen_rules.py --cohorts K2023 K2024
  python scripts/gen_rules.py --majors CNTT KTPM
  python scripts/gen_rules.py --force                  # overwrite existing
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT        = Path(__file__).parent.parent
PROGRAM_DIR = ROOT / "data" / "programs"
OUT_DIR     = ROOT / "data" / "rules" / "local"


# ── helpers ────────────────────────────────────────────────────────────────────

def load_programs(cohort: str, major: str) -> list[dict]:
    """Load all program JSON files for a given cohort/major."""
    folder = PROGRAM_DIR / cohort / major
    if not folder.exists():
        return []
    programs = []
    for p in sorted(folder.glob("*.json")):
        try:
            programs.append(json.loads(p.read_text()))
        except Exception:
            pass
    return programs


def courses_for_block(program: dict, block_id: str) -> list[str]:
    """Return ordered unique course_ids belonging to a block."""
    seen = set()
    ids = []
    for c in program.get("courses", []):
        if c.get("block_id") == block_id and c["course_id"] not in seen:
            seen.add(c["course_id"])
            ids.append(c["course_id"])
    return ids


def selection_type(block: dict, program: dict) -> str:
    """Infer selection_type from block metadata."""
    name_lower = block.get("block_name", "").lower()
    if block.get("is_elective"):
        rc = block.get("required_credits")
        if rc:
            return "min_credits"
        return "choose_any"
    return "all"


# ── rule generators ────────────────────────────────────────────────────────────

def gen_program_structure(program: dict) -> dict:
    """PROGRAM_STRUCTURE rule for one program."""
    knowledge_blocks = []
    for kb in program.get("knowledge_blocks", []):
        block_id = kb["block_id"]
        course_ids = courses_for_block(program, block_id)
        knowledge_blocks.append({
            "block_id":        block_id,
            "block_name":      kb["block_name"],
            "heading_path":    kb.get("heading_path"),
            "required_credits": kb.get("required_credits"),
            "is_elective":     kb.get("is_elective", False),
            "courses":         course_ids,
        })

    return {
        "rule_type":         "PROGRAM_STRUCTURE",
        "program_type":      program["program_type"],
        "total_credits":     program.get("total_credits"),
        "designed_semesters": program.get("designed_semesters"),
        "knowledge_blocks":  knowledge_blocks,
    }


def gen_course_group_requirements(program: dict) -> list[dict]:
    """COURSE_GROUP_REQUIREMENT rules — one per knowledge block that has courses."""
    rules = []
    for kb in program.get("knowledge_blocks", []):
        block_id = kb["block_id"]
        course_ids = courses_for_block(program, block_id)
        if not course_ids:
            continue

        stype = selection_type(kb, program)

        rules.append({
            "rule_type":          "COURSE_GROUP_REQUIREMENT",
            "program_type":       program["program_type"],
            "block_id":           block_id,
            "group_name":         kb["block_name"],
            "required_credits":   kb.get("required_credits"),
            "is_elective":        kb.get("is_elective", False),
            "selection_type":     stype,
            "courses":            course_ids,
        })

    return rules


# ── per cohort/major ────────────────────────────────────────────────────────────

def build_rules_for(cohort: str, major: str) -> dict | None:
    programs = load_programs(cohort, major)
    if not programs:
        return None

    # Use source_url from any program (prefer standard)
    source_url = ""
    for p in programs:
        if p.get("source_url"):
            source_url = p["source_url"]
            if p.get("program_type") == "standard":
                break

    all_rules = []
    for prog in programs:
        # One PROGRAM_STRUCTURE per program type
        all_rules.append(gen_program_structure(prog))
        # COURSE_GROUP_REQUIREMENT for each block
        all_rules.extend(gen_course_group_requirements(prog))

    return {
        "major":        major,
        "cohort":       cohort,
        "source_url":   source_url,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "rules":        all_rules,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate local curriculum rules from program data")
    parser.add_argument("--cohorts", nargs="+", help="Filter cohorts")
    parser.add_argument("--majors",  nargs="+", help="Filter majors")
    parser.add_argument("--force",   action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()

    # Discover all cohort/major pairs that have program data
    pairs: list[tuple[str, str]] = []
    for cohort_dir in sorted(PROGRAM_DIR.iterdir()):
        if not cohort_dir.is_dir():
            continue
        cohort = cohort_dir.name
        if args.cohorts and cohort not in args.cohorts:
            continue
        for major_dir in sorted(cohort_dir.iterdir()):
            if not major_dir.is_dir():
                continue
            major = major_dir.name
            if args.majors and major not in args.majors:
                continue
            pairs.append((cohort, major))

    total_rules = 0
    written = 0

    for cohort, major in pairs:
        out_path = OUT_DIR / cohort / f"{major}.json"

        if out_path.exists() and not args.force:
            continue

        result = build_rules_for(cohort, major)
        if not result:
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

        n = len(result["rules"])
        ps_count = sum(1 for r in result["rules"] if r["rule_type"] == "PROGRAM_STRUCTURE")
        cg_count = n - ps_count
        print(f"  [{cohort}/{major}] {ps_count} PROGRAM_STRUCTURE  {cg_count:3d} COURSE_GROUP → {out_path.relative_to(ROOT)}")
        total_rules += n
        written += 1

    print()
    print(f"Done: {written} files, {total_rules} total rules")


if __name__ == "__main__":
    main()
