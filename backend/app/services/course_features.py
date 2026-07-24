"""Feature engineering shared by the GP2 training and inference paths."""

from __future__ import annotations

import unicodedata
from typing import Any

from app.services.prereq_graph import (
    build_prereq_graph,
    graph_depth,
    unlock_count,
)


FEATURE_COLUMNS = [
    "graph_depth",
    "unlock_count",
    "credits",
    "is_mandatory",
    "block_category",
]


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(
        character for character in text if unicodedata.category(character) != "Mn"
    )
    return text.replace("đ", "d")


def _block_category(course: dict[str, Any]) -> int:
    raw_heading = course.get("heading_path", "")
    if isinstance(raw_heading, list):
        raw_heading = " ".join(str(part) for part in raw_heading)
    text = _normalize_text(f"{course.get('block_name', '')} {raw_heading}")

    if "dai cuong" in text:
        return 0
    if "co so" in text:
        return 1
    if "chuyen nganh" in text or "huong" in text:
        return 2
    return 3


def _find_course(course_id: str, program_json: dict[str, Any]) -> dict[str, Any]:
    normalized_course = course_id.strip().upper()
    for course in program_json.get("courses", []):
        if str(course.get("course_id", "")).strip().upper() == normalized_course:
            return course
    return {}


def build_feature_row(
    course_id: str,
    major: str,
    program_json: dict[str, Any],
) -> dict[str, float]:
    """Build the canonical numeric row used by the GP2 Ridge model."""
    del major  # Major defines the curriculum lookup, not a fitted input feature.
    course = _find_course(course_id, program_json)
    graph = build_prereq_graph()

    return {
        "graph_depth": float(graph_depth(graph, course_id)),
        "unlock_count": float(unlock_count(graph, course_id)),
        "credits": float(course.get("credits") or 0),
        "is_mandatory": float(bool(course.get("is_mandatory", False))),
        "block_category": float(_block_category(course)),
    }
