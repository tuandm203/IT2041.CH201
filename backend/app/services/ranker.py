"""GP2 model loading and course-priority inference."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import networkx as nx
import pandas as pd

from app.core.config import settings
from app.services.course_features import FEATURE_COLUMNS, build_feature_row
from app.services.prereq_graph import unlock_count


logger = logging.getLogger(__name__)

_ranker: Any | None = None
_feature_columns: list[str] = FEATURE_COLUMNS
_load_attempted = False


def _model_path() -> Path:
    return settings.data_dir / "models" / "course_priority_ranker.joblib"


def _feature_columns_path() -> Path:
    return settings.data_dir / "models" / "feature_columns.json"


def load_ranker() -> Any | None:
    """Load the trained Ridge artifact once, falling back cleanly to GP1."""
    global _ranker, _feature_columns, _load_attempted
    if _load_attempted:
        return _ranker

    _load_attempted = True
    model_path = _model_path()
    columns_path = _feature_columns_path()
    if not model_path.exists() or not columns_path.exists():
        logger.warning(
            "GP2 model artifact is unavailable under %s; falling back to GP1.",
            model_path.parent,
        )
        return None

    try:
        with columns_path.open(encoding="utf-8") as columns_file:
            loaded_columns = json.load(columns_file)
        if loaded_columns != FEATURE_COLUMNS:
            raise ValueError(
                f"Feature order mismatch: expected {FEATURE_COLUMNS}, "
                f"artifact contains {loaded_columns}"
            )
        _feature_columns = loaded_columns
        _ranker = joblib.load(model_path)
        logger.info("Loaded GP2 course ranker from %s", model_path)
    except Exception:
        logger.exception(
            "Could not load GP2 ranker from %s; falling back to GP1.",
            model_path,
        )
        _ranker = None
    return _ranker


def ranker_available() -> bool:
    return load_ranker() is not None


@lru_cache(maxsize=64)
def load_program_json(major: str, cohort: str | None = None) -> dict[str, Any]:
    """Load a curriculum by code, using the newest matching cohort if omitted."""
    programs_dir = settings.data_dir / "programs"
    normalized_major = major.strip().casefold()
    normalized_cohort = cohort.strip().upper() if cohort else None
    if normalized_cohort and normalized_cohort.isdigit():
        normalized_cohort = f"K{normalized_cohort}"

    cohort_dirs = [
        directory
        for directory in programs_dir.iterdir()
        if directory.is_dir() and directory.name.upper().startswith("K")
    ] if programs_dir.exists() else []
    cohort_dirs.sort(key=lambda directory: directory.name, reverse=True)

    if normalized_cohort:
        cohort_dirs = [
            directory
            for directory in cohort_dirs
            if directory.name.upper() == normalized_cohort
        ]

    for cohort_dir in cohort_dirs:
        for major_dir in cohort_dir.iterdir():
            if not major_dir.is_dir() or major_dir.name.casefold() != normalized_major:
                continue
            program_path = major_dir / "standard.json"
            if program_path.exists():
                with program_path.open(encoding="utf-8") as program_file:
                    return json.load(program_file)

    logger.warning(
        "No curriculum found for major=%s cohort=%s; GP2 will use zero-valued "
        "curriculum features for unavailable courses.",
        major,
        cohort,
    )
    return {"major": major, "cohort": cohort, "courses": []}


def score_course(
    course_id: str,
    major: str,
    program_json: dict[str, Any],
    graph: nx.DiGraph,
) -> float:
    """Return GP2 priority: earlier predicted semester first, unlocks as tie-break."""
    model = load_ranker()
    if model is None:
        return float(unlock_count(graph, course_id))

    feature_row = build_feature_row(course_id, major, program_json)
    features = pd.DataFrame([feature_row], columns=_feature_columns)
    predicted_semester = float(model.predict(features)[0])
    return -predicted_semester + (unlock_count(graph, course_id) * 1e-6)
