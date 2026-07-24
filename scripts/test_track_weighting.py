#!/usr/bin/env python3
"""Show the real optimizer ordering before/after KHMT track personalization."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastapi import UploadFile


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.optimizer import optimize_schedule  # noqa: E402
from app.models.schedule import (  # noqa: E402
    CourseGroup,
    OptimizeRequest,
    StudentProfile,
)
from app.services.excel_parser import parse_excel_file  # noqa: E402
from app.services.prereq_graph import build_prereq_graph, unlock_count  # noqa: E402
from app.services.track_matcher import (  # noqa: E402
    TRACK_SCORE_WEIGHT,
    score_track_relevance,
    track_matcher_available,
)


TIMETABLE_PATH = REPO_ROOT / "TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx"
ELECTIVE_IDS = {"CS105", "CS321", "CS331", "CS338", "CS410", "CS419"}
MAJOR = "KHMT"
TRACK = "computer_vision"


async def _load_real_electives() -> list[CourseGroup]:
    with TIMETABLE_PATH.open("rb") as timetable_file:
        upload = UploadFile(file=timetable_file, filename=TIMETABLE_PATH.name)
        groups, _ = await parse_excel_file(upload)

    # Keep real IDs, names, and credits from the timetable. Remove class slots so
    # this check isolates course ranking rather than the independent CSP layer.
    return [
        CourseGroup(
            course_id=group.course_id,
            course_name=group.course_name,
            total_credits=group.total_credits,
            department=group.department,
        )
        for group in groups
        if group.course_id.upper() in ELECTIVE_IDS
    ]


def _run(
    groups: list[CourseGroup],
    engine: str,
    track: str | None,
):
    request = OptimizeRequest(
        min_credits=1,
        max_credits=50,
        max_courses=5,
        course_groups=groups,
        student=StudentProfile(
            major=MAJOR,
            cohort="K2015",
            track=track,
            english_level="passed",
        ),
        engine=engine,
    )
    return optimize_schedule(request)


def _selected_order(result: object) -> list[str]:
    return [item.course_id for item in result.selected]


def main() -> None:
    groups = asyncio.run(_load_real_electives())
    actual_ids = {group.course_id for group in groups}
    if actual_ids != ELECTIVE_IDS:
        raise SystemExit(
            f"Timetable elective fixture changed: expected {sorted(ELECTIVE_IDS)}, "
            f"found {sorted(actual_ids)}"
        )

    available = track_matcher_available()
    graph = build_prereq_graph()
    print(f"GTE model available: {available}")
    print(f"Track: {MAJOR}/{TRACK}; additive weight: {TRACK_SCORE_WEIGHT}")
    print("Course scores (base GP1, cosine, blended):")
    for course_id in sorted(ELECTIVE_IDS - {"CS410"}):
        base = float(unlock_count(graph, course_id))
        cosine = score_track_relevance(course_id, MAJOR, TRACK)
        blended = base + (TRACK_SCORE_WEIGHT * cosine)
        print(
            f"  {course_id}: base={base:.6f}, cosine={cosine:.6f}, "
            f"blended={blended:.6f}"
        )

    ordering_changes: dict[str, bool] = {}
    for engine in ("gp1", "gp2"):
        baseline = _run(groups, engine, track=None)
        personalized = _run(groups, engine, track=TRACK)
        before = _selected_order(baseline)
        after = _selected_order(personalized)
        blocked = next(
            item for item in personalized.not_selected if item.course_id == "CS410"
        )
        print(f"{engine.upper()} without track: {before}")
        print(f"{engine.upper()} with track:    {after}")
        print(f"{engine.upper()} ordering changed: {before != after}")
        print(f"{engine.upper()} CS410 gate: {blocked.reason}")
        ordering_changes[engine] = before != after

    unsupported = score_track_relevance("CS331", "CNTT", TRACK)
    print(f"Unsupported-major neutral score (CNTT/CS331): {unsupported:.6f}")

    if not available:
        print(
            "TRACK PROOF UNAVAILABLE: thenlper/gte-small is not cached and "
            "Hugging Face cannot be reached; neutral fallback correctly leaves "
            "both orderings unchanged."
        )
    elif all(ordering_changes.values()):
        print("TRACK PROOF PASSED: GP1 and GP2 elective orderings both changed.")
    else:
        raise SystemExit(
            "Track embeddings loaded, but the controlled elective ordering did "
            "not change for both engines."
        )


if __name__ == "__main__":
    main()
