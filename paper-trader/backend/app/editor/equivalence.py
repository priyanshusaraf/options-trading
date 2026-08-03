"""Deterministic diagnostics for S3.3 executable-equivalence proofs."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from app.ir.hashing import canonical_json, content_address


@dataclass(frozen=True)
class EquivalenceMismatch:
    code: str
    path: str
    message: str


def _node_ids(graph: Mapping[str, Any]) -> list[str]:
    return [str(node.get("instance_id")) for node in graph.get("nodes", ())]


def _encoded_edges(graph: Mapping[str, Any]) -> list[str]:
    return [canonical_json(edge) for edge in graph.get("edges", ())]


def _semantic_projection(graph: Mapping[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(dict(graph))
    projected["groups"] = []
    projected["nodes"] = sorted(
        projected.get("nodes", ()), key=lambda node: str(node.get("instance_id"))
    )
    projected["edges"] = sorted(
        projected.get("edges", ()), key=canonical_json
    )
    return projected


def _first_difference(actual: Any, expected: Any, path: str = "$") -> str:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in sorted(set(actual) | set(expected)):
            child = f"{path}.{key}"
            if key not in actual or key not in expected:
                return child
            if canonical_json(actual[key]) != canonical_json(expected[key]):
                return _first_difference(actual[key], expected[key], child)
    elif isinstance(actual, list) and isinstance(expected, list):
        for index, (left, right) in enumerate(zip(actual, expected)):
            if canonical_json(left) != canonical_json(right):
                return _first_difference(left, right, f"{path}[{index}]")
        if len(actual) != len(expected):
            return f"{path}[{min(len(actual), len(expected))}]"
    return path


def executable_mismatches(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> tuple[EquivalenceMismatch, ...]:
    """Explain why two declared executable documents are not byte-identical."""
    mismatches: list[EquivalenceMismatch] = []
    if actual.get("groups") or expected.get("groups"):
        mismatches.append(EquivalenceMismatch(
            "PRESENTATION_CONTAMINATION",
            "$.groups",
            "visual groups are presentation state and cannot enter executable JSON",
        ))
    actual_nodes, expected_nodes = _node_ids(actual), _node_ids(expected)
    if actual_nodes != expected_nodes and sorted(actual_nodes) == sorted(expected_nodes):
        mismatches.append(EquivalenceMismatch(
            "NODE_ORDER_MISMATCH", "$.nodes",
            "authored node arrays contain the same instances in a different order",
        ))
    actual_edges, expected_edges = _encoded_edges(actual), _encoded_edges(expected)
    if actual_edges != expected_edges and sorted(actual_edges) == sorted(expected_edges):
        mismatches.append(EquivalenceMismatch(
            "EDGE_ORDER_MISMATCH", "$.edges",
            "authored edge arrays contain the same edges in a different order",
        ))
    actual_semantic = _semantic_projection(actual)
    expected_semantic = _semantic_projection(expected)
    if canonical_json(actual_semantic) != canonical_json(expected_semantic):
        path = _first_difference(actual_semantic, expected_semantic)
        mismatches.append(EquivalenceMismatch(
            "SEMANTIC_CONTENT_MISMATCH", path,
            "executable semantic content differs",
        ))
    if content_address(actual) != content_address(expected):
        mismatches.append(EquivalenceMismatch(
            "EXECUTABLE_IDENTITY_MISMATCH", "$",
            "canonical executable content addresses differ",
        ))
    return tuple(mismatches)
