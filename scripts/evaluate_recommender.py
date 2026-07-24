#!/usr/bin/env python3
"""Leave-future-out evaluation of GP1 graph ranking versus GP2 Ridge ranking."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.prereq_graph import (  # noqa: E402
    build_prereq_graph,
    is_eligible,
    unlock_count,
)
from app.services.ranker import ranker_available, score_course  # noqa: E402


COHORTS = ("K2012", "K2013", "K2014", "K2015")
PROGRAMS_DIR = REPO_ROOT / "data" / "programs"
TOP_N = 5


def _metrics(recommendations: list[str], expected: set[str]) -> tuple[float, float]:
    hits = len(set(recommendations) & expected)
    precision = hits / len(recommendations) if recommendations else 0.0
    recall = hits / len(expected) if expected else 0.0
    return precision, recall


def main() -> None:
    if not ranker_available():
        raise SystemExit(
            "GP2 artifact is missing. Run `python scripts/train_ranker.py` first."
        )

    graph = build_prereq_graph()
    results: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(
        lambda: {"gp1": [], "gp2": []}
    )
    labeled_rows = 0

    for cohort in COHORTS:
        for program_path in sorted((PROGRAMS_DIR / cohort).glob("*/standard.json")):
            with program_path.open(encoding="utf-8") as program_file:
                program = json.load(program_file)

            major = str(program.get("major") or program_path.parent.name)
            labeled_entries = [
                course
                for course in program.get("courses", [])
                if course.get("course_id") and course.get("semester") is not None
            ]
            labeled_courses = {
                str(course["course_id"]).strip().upper(): course
                for course in labeled_entries
            }
            labeled_rows += len(labeled_entries)
            semesters = sorted(
                {int(course["semester"]) for course in labeled_courses.values()}
            )

            for semester in semesters:
                completed = {
                    course_id
                    for course_id, course in labeled_courses.items()
                    if int(course["semester"]) < semester
                }
                expected = {
                    course_id
                    for course_id, course in labeled_courses.items()
                    if int(course["semester"]) == semester
                }
                candidates = [
                    course_id
                    for course_id in labeled_courses
                    if course_id not in completed
                    and is_eligible(graph, course_id, completed)[0]
                ]

                gp1 = sorted(
                    candidates,
                    key=lambda course_id: (
                        -unlock_count(graph, course_id),
                        course_id,
                    ),
                )[:TOP_N]
                gp2 = sorted(
                    candidates,
                    key=lambda course_id: (
                        -score_course(course_id, major, program, graph),
                        course_id,
                    ),
                )[:TOP_N]

                results[major]["gp1"].append(_metrics(gp1, expected))
                results[major]["gp2"].append(_metrics(gp2, expected))

    print(
        f"Leave-future-out evaluation on {labeled_rows} real semester labels "
        f"(Top-N={TOP_N})"
    )
    print(
        f"{'Major':<12} {'Scenarios':>9} "
        f"{'GP1 P@5':>10} {'GP1 R@5':>10} "
        f"{'GP2 P@5':>10} {'GP2 R@5':>10}"
    )
    print("-" * 65)

    all_gp1: list[tuple[float, float]] = []
    all_gp2: list[tuple[float, float]] = []
    for major in sorted(results):
        gp1_metrics = results[major]["gp1"]
        gp2_metrics = results[major]["gp2"]
        all_gp1.extend(gp1_metrics)
        all_gp2.extend(gp2_metrics)
        gp1_precision, gp1_recall = np.mean(gp1_metrics, axis=0)
        gp2_precision, gp2_recall = np.mean(gp2_metrics, axis=0)
        print(
            f"{major:<12} {len(gp1_metrics):>9} "
            f"{gp1_precision:>10.4f} {gp1_recall:>10.4f} "
            f"{gp2_precision:>10.4f} {gp2_recall:>10.4f}"
        )

    gp1_precision, gp1_recall = np.mean(all_gp1, axis=0)
    gp2_precision, gp2_recall = np.mean(all_gp2, axis=0)
    print("-" * 65)
    print(
        f"{'MACRO AVG':<12} {len(all_gp1):>9} "
        f"{gp1_precision:>10.4f} {gp1_recall:>10.4f} "
        f"{gp2_precision:>10.4f} {gp2_recall:>10.4f}"
    )


if __name__ == "__main__":
    main()
