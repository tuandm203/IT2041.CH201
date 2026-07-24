"""Prerequisite graph shared by training, evaluation, and API inference."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import networkx as nx

from app.core.config import settings


def _catalog_path() -> Path:
    return settings.data_dir / "rules" / "global" / "course_prerequisites_catalog.json"


def _course_id(item: object) -> str | None:
    if isinstance(item, str):
        value = item
    elif isinstance(item, dict):
        value = item.get("course_id")
    else:
        return None
    if not value:
        return None
    return str(value).strip().upper()


def _add_edge(
    graph: nx.DiGraph,
    prerequisite: str,
    course_id: str,
    *,
    kind: str,
    min_grade: float | None = None,
) -> None:
    """Add an edge without allowing a soft duplicate to replace a hard rule."""
    existing = graph.get_edge_data(prerequisite, course_id, default={})
    if existing.get("kind") == "hard" and kind == "soft":
        return

    attributes: dict[str, object] = {"kind": kind}
    if kind == "hard":
        attributes["min_grade"] = min_grade
    graph.add_edge(prerequisite, course_id, **attributes)


@lru_cache(maxsize=1)
def build_prereq_graph() -> nx.DiGraph:
    """Load the global UIT prerequisite catalog into a cached directed graph."""
    path = _catalog_path()
    with path.open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)

    graph = nx.DiGraph()
    for rule in catalog.get("rules", []):
        rule_type = rule.get("rule_type") or rule.get("type")
        payload = rule.get("payload", {})
        course = _course_id(payload.get("course"))
        if not course:
            continue

        graph.add_node(course)
        if rule_type == "COURSE_PREREQUISITE":
            min_grade = payload.get("min_grade")
            for requirement in (
                payload.get("requires_all", []) + payload.get("requires_any", [])
            ):
                prerequisite = _course_id(requirement)
                if prerequisite:
                    _add_edge(
                        graph,
                        prerequisite,
                        course,
                        kind="hard",
                        min_grade=min_grade,
                    )
        elif rule_type == "COURSE_PRIOR":
            for requirement in payload.get("prior_courses", []):
                prerequisite = _course_id(requirement)
                if prerequisite:
                    _add_edge(graph, prerequisite, course, kind="soft")

    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError(f"Prerequisite catalog at {path} contains a directed cycle")
    return graph


def is_eligible(
    graph: nx.DiGraph,
    course_id: str,
    completed_ids: set[str],
) -> tuple[bool, list[str]]:
    """Return whether every hard incoming prerequisite has been completed."""
    normalized_course = course_id.strip().upper()
    normalized_completed = {item.strip().upper() for item in completed_ids}
    if normalized_course not in graph:
        return True, []

    missing = sorted(
        prerequisite
        for prerequisite, _, data in graph.in_edges(normalized_course, data=True)
        if data.get("kind") == "hard"
        and prerequisite not in normalized_completed
    )
    return not missing, missing


def graph_depth(graph: nx.DiGraph, course_id: str) -> int:
    """Return the longest prerequisite/prior path ending at ``course_id``."""
    normalized_course = course_id.strip().upper()
    if normalized_course not in graph:
        return 0

    relevant_nodes = nx.ancestors(graph, normalized_course) | {normalized_course}
    return int(nx.dag_longest_path_length(graph.subgraph(relevant_nodes)))


def unlock_count(graph: nx.DiGraph, course_id: str) -> int:
    """Count all direct and indirect courses unlocked by ``course_id``."""
    normalized_course = course_id.strip().upper()
    if normalized_course not in graph:
        return 0
    return len(nx.descendants(graph, normalized_course))

