"""Semantic specialization-track matching with cached GTE embeddings."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings


logger = logging.getLogger(__name__)

MODEL_NAME = "thenlper/gte-small"
TRACK_SCORE_WEIGHT = 2.0

# Anchor profiles use faculty labels while curricula use major directory codes.
MAJOR_PROFILE_ALIASES = {
    "KTPM": "CNPM",
    "MMT&TTDL": "MMT&TT",
}


@dataclass
class _EmbeddingIndex:
    course_embeddings: dict[str, np.ndarray]
    anchor_embeddings: dict[tuple[str, str], np.ndarray]


def _anchor_profiles_path() -> Path:
    return settings.data_dir.parent / "notebooks" / "anchor_profiles.json"


def _descriptions_path() -> Path:
    return settings.data_dir / "raw" / "course_descriptions.json"


def _catalog_path() -> Path:
    return settings.data_dir / "raw" / "course_catalog.csv"


def _profile_major(major: str) -> str:
    normalized = major.strip().upper()
    return MAJOR_PROFILE_ALIASES.get(normalized, normalized)


@lru_cache(maxsize=1)
def load_anchor_profiles() -> dict[str, Any]:
    """Load the hand-authored specialization taxonomy without loading GTE."""
    path = _anchor_profiles_path()
    try:
        with path.open(encoding="utf-8") as profile_file:
            profiles = json.load(profile_file)
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not load specialization anchors from %s.", path)
        return {}
    return {
        str(major).strip().upper(): profile
        for major, profile in profiles.items()
    }


def get_track_options(major: str) -> list[dict[str, str]]:
    """Return UI-safe anchor metadata for a curriculum/faculty major code."""
    profile = load_anchor_profiles().get(_profile_major(major), {})
    anchors = profile.get("anchors", {})
    return [
        {
            "key": str(anchor_key),
            "name": str(anchor.get("name") or anchor_key),
            "description": str(anchor.get("description") or ""),
        }
        for anchor_key, anchor in anchors.items()
    ]


def has_track_coverage(major: str, anchor_key: str | None = None) -> bool:
    """Check coverage before attempting the relatively expensive model load."""
    profile = load_anchor_profiles().get(_profile_major(major))
    if not profile:
        return False
    if anchor_key is None:
        return bool(profile.get("anchors"))
    return anchor_key.strip() in profile.get("anchors", {})


@lru_cache(maxsize=1)
def list_available_majors() -> list[str]:
    """List all curriculum major codes available to the frontend."""
    programs_dir = settings.data_dir / "programs"
    if not programs_dir.exists():
        return []
    return sorted({
        major_dir.name
        for cohort_dir in programs_dir.iterdir()
        if cohort_dir.is_dir()
        for major_dir in cohort_dir.iterdir()
        if major_dir.is_dir() and (major_dir / "standard.json").exists()
    })


def get_frontend_track_profiles() -> dict[str, list[dict[str, str]]]:
    """Return anchors keyed by the major codes users select in curricula."""
    return {
        major: options
        for major in list_available_majors()
        if (options := get_track_options(major))
    }


@lru_cache(maxsize=1)
def _load_course_records() -> dict[str, dict[str, str]]:
    """Merge crawled descriptions with canonical catalog metadata by course ID."""
    descriptions_path = _descriptions_path()
    catalog_path = _catalog_path()
    try:
        with descriptions_path.open(encoding="utf-8") as descriptions_file:
            descriptions = json.load(descriptions_file)
        with catalog_path.open(encoding="utf-8-sig", newline="") as catalog_file:
            catalog_rows = {
                str(row.get("course_id", "")).strip().upper(): row
                for row in csv.DictReader(catalog_file)
                if row.get("course_id")
            }
    except (OSError, json.JSONDecodeError):
        logger.exception(
            "Could not load course text data from %s and %s.",
            descriptions_path,
            catalog_path,
        )
        return {}

    records: dict[str, dict[str, str]] = {}
    for description_row in descriptions:
        course_id = str(description_row.get("course_id", "")).strip().upper()
        if not course_id:
            continue
        catalog_row = catalog_rows.get(course_id, {})
        records[course_id] = {
            "description": str(description_row.get("description") or "").strip(),
            "name_vi": str(
                catalog_row.get("name_vi")
                or description_row.get("name_vi")
                or ""
            ).strip(),
            "name_en": str(catalog_row.get("name_en") or "").strip(),
            "managed_by": str(catalog_row.get("managed_by") or "").strip(),
        }
    return records


def _course_text(record: dict[str, str]) -> str:
    return "\n".join(
        value
        for value in (
            record.get("description", ""),
            record.get("name_vi", ""),
            record.get("name_en", ""),
        )
        if value
    )


def _anchor_text(anchor: dict[str, Any]) -> str:
    keywords = " ".join(str(keyword) for keyword in anchor.get("keywords", []))
    return "\n".join(
        value
        for value in (str(anchor.get("description") or ""), keywords)
        if value
    )


@lru_cache(maxsize=1)
def load_embedding_model() -> Any | None:
    """Load GTE once; missing package/model/network yields a neutral fallback."""
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(MODEL_NAME)
        logger.info("Loaded track embedding model %s.", MODEL_NAME)
        return model
    except Exception:
        logger.exception(
            "Could not load track embedding model %s; track relevance will "
            "fall back to neutral scores.",
            MODEL_NAME,
        )
        return None


@lru_cache(maxsize=1)
def _build_embedding_index() -> _EmbeddingIndex | None:
    """Encode all 401 described courses and all anchors exactly once."""
    model = load_embedding_model()
    course_records = _load_course_records()
    profiles = load_anchor_profiles()
    if model is None or not course_records or not profiles:
        return None

    try:
        course_ids = sorted(course_records)
        course_vectors = model.encode(
            [_course_text(course_records[course_id]) for course_id in course_ids],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        course_embeddings = {
            course_id: vector
            for course_id, vector in zip(course_ids, course_vectors)
        }

        anchor_keys: list[tuple[str, str]] = []
        anchor_texts: list[str] = []
        for major, profile in profiles.items():
            for anchor_key, anchor in profile.get("anchors", {}).items():
                anchor_keys.append((major, str(anchor_key)))
                anchor_texts.append(_anchor_text(anchor))
        anchor_vectors = model.encode(
            anchor_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        anchor_embeddings = {
            key: vector
            for key, vector in zip(anchor_keys, anchor_vectors)
        }
    except Exception:
        logger.exception(
            "Could not build track embedding index; track relevance will "
            "fall back to neutral scores."
        )
        return None

    logger.info(
        "Built cached track index with %d courses and %d anchors.",
        len(course_embeddings),
        len(anchor_embeddings),
    )
    return _EmbeddingIndex(course_embeddings, anchor_embeddings)


def track_matcher_available() -> bool:
    return _build_embedding_index() is not None


@lru_cache(maxsize=4096)
def score_track_relevance(
    course_id: str,
    major: str,
    anchor_key: str,
) -> float:
    """Return cosine similarity for a course and selected specialization."""
    profile_major = _profile_major(major)
    normalized_anchor = anchor_key.strip()
    if not has_track_coverage(profile_major, normalized_anchor):
        return 0.0

    normalized_course = course_id.strip().upper()
    if normalized_course not in _load_course_records():
        return 0.0

    index = _build_embedding_index()
    if index is None:
        return 0.0

    course_embedding = index.course_embeddings.get(normalized_course)
    anchor_embedding = index.anchor_embeddings.get(
        (profile_major, normalized_anchor)
    )
    if course_embedding is None or anchor_embedding is None:
        return 0.0
    return float(np.dot(course_embedding, anchor_embedding))
