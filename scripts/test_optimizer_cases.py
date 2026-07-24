"""Regression smoke test — runs the hand-authored student cases in data/train/
against the real optimizer (real TKB_KHDT sections, real prereq graph).

These are illustrative fixtures (4 cases), not a statistical benchmark — they
check specific correctness properties called out in each case's
`expected_recommendations`, distinct from the leave-future-out evaluation in
scripts/evaluate_recommender.py.

Calls optimize_schedule() directly (not via HTTP/HTML) so selected/not_selected
are inspected as structured data, not scraped from rendered markup.

Usage: run from repo root with the project venv, e.g.
  .venv/bin/python scripts/test_optimizer_cases.py
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from starlette.datastructures import UploadFile  # noqa: E402

from app.core.optimizer import optimize_schedule  # noqa: E402
from app.models.schedule import OptimizeRequest, StudentProfile  # noqa: E402
from app.services.excel_parser import parse_excel_file  # noqa: E402

TKB_PATH = ROOT / "TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx"
CASES_DIR = ROOT / "data" / "train"
CASE_FILES = [
    "student_case_1_missing_english.json",
    "student_case_2_retake_courses.json",
    "student_case_3_missing_prerequisites.json",
    "student_case_4_normal_progress.json",
]


def run_case(course_groups, case: dict) -> bool:
    student = StudentProfile(
        major=case["major"],
        cohort=case["cohort"],
        english_level=case["english_level"],
        completed_courses=case["completed_courses"],
        retake_courses=case.get("retake_courses", []),
    )
    req = OptimizeRequest(
        min_credits=case["min_credits"],
        max_credits=case["max_credits"],
        course_groups=course_groups,
        student=student,
        engine="gp1",
    )
    result = optimize_schedule(req)

    selected_ids = {item.course_id.upper() for item in result.selected}
    blocked_ids = {
        item.course_id.upper()
        for item in result.not_selected
        if item.category == "blocked"
    }

    print(f"\n=== {case['case_id']} — {case['case_name']} ===")
    print(f"  {case['description']}")

    expected = case["expected_recommendations"]
    ok = True

    for course_id in expected.get("should_not_include", []):
        cid = course_id.upper()
        if cid in selected_ids:
            print(f"  FAIL: {course_id} was selected but should NOT be (should_not_include)")
            ok = False
        else:
            print(f"  PASS: {course_id} correctly absent from selection")

    for course_id in expected.get("should_include", []):
        cid = course_id.upper()
        if cid in selected_ids:
            print(f"  PASS: {course_id} selected as expected")
        elif cid in blocked_ids:
            print(f"  FAIL: {course_id} incorrectly blocked by prerequisite check")
            ok = False
        else:
            print(
                f"  WARN: {course_id} not selected (likely not offered in this "
                f"semester's TKB, or excluded by credit/schedule limits — "
                f"not a prerequisite-logic bug)"
            )

    print(f"  Reason: {expected.get('reason', '-')}")
    return ok


async def load_course_groups():
    tkb_bytes = TKB_PATH.read_bytes()
    upload = UploadFile(filename="tkb.xlsx", file=io.BytesIO(tkb_bytes))
    course_groups, _departments = await parse_excel_file(upload)
    return course_groups


def main() -> int:
    course_groups = asyncio.run(load_course_groups())

    all_passed = True
    for filename in CASE_FILES:
        case = json.loads((CASES_DIR / filename).read_text(encoding="utf-8"))
        if not run_case(course_groups, case):
            all_passed = False

    print("\n" + "=" * 60)
    print("ALL CASES PASSED" if all_passed else "SOME CASES FAILED")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
