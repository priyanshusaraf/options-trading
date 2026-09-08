"""Pure comparison of two verified terminal research-evidence payloads."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.research_visualization_read import (
    SCHEMA as VISUALIZATION_SCHEMA,
    VisualizationRejected,
    page_projection,
)


_INCOMPARABLE = {
    "datasets": "DATASET_IDENTITY_CHANGED",
    "costs": "COST_ASSUMPTIONS_CHANGED",
    "gates": "GATE_CONTRACT_CHANGED",
}
_MISSING = object()


def _reported(value: Any) -> Any:
    return {"state": "missing"} if value is _MISSING else value


def _semantic_results(results: Mapping[str, Any]) -> dict[str, Any]:
    """Remove only run/spec envelope identity from the saved result comparison."""
    evidence = dict(results)
    if "visualization" not in evidence:
        return evidence
    visualization = evidence["visualization"]
    if not isinstance(visualization, Mapping):
        raise ValueError("comparison requires verified terminal evidence")
    state = visualization.get("state")
    if state == "UNAVAILABLE":
        if set(visualization) != {"schema", "state", "reason_code"} \
                or visualization.get("schema") != VISUALIZATION_SCHEMA \
                or not isinstance(visualization.get("reason_code"), str) \
                or not visualization["reason_code"]:
            raise ValueError("comparison requires verified terminal evidence")
        return evidence
    if state != "AVAILABLE":
        raise ValueError("comparison requires verified terminal evidence")
    try:
        page_projection(
            visualization,
            trade_after=0,
            trade_limit=1,
            terminal_evidence_address="sha256:" + "0" * 64,
        )
    except (VisualizationRejected, TypeError, ValueError, KeyError) as exc:
        raise ValueError("comparison requires verified terminal evidence") from exc
    normalized_visualization = dict(visualization)
    normalized_visualization.pop("visualization_address", None)
    identity = normalized_visualization.get("identity")
    if isinstance(identity, Mapping):
        normalized_identity = dict(identity)
        normalized_identity.pop("run_id", None)
        normalized_identity.pop("spec_id", None)
        normalized_visualization["identity"] = normalized_identity
    evidence["visualization"] = normalized_visualization
    return evidence


def _sections(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise ValueError("comparison requires verified terminal evidence")
    provenance = evidence.get("provenance")
    results = evidence.get("results")
    run = evidence.get("run")
    if not all(isinstance(value, Mapping) for value in (provenance, results, run)):
        raise ValueError("comparison requires verified terminal evidence")
    graph_provenance = provenance.get("graph_provenance")
    if not isinstance(graph_provenance, Mapping):
        raise ValueError("comparison requires verified terminal evidence")
    graph = graph_provenance.get("graph")
    resolution = graph_provenance.get("resolution")
    if not isinstance(graph, Mapping) or not isinstance(resolution, Mapping):
        raise ValueError("comparison requires verified terminal evidence")
    return {
        "graph": graph,
        "resolution": resolution,
        "parameters": provenance.get("params", {}),
        "datasets": {
            "identities": provenance.get("datasets", {}),
            "bindings": graph_provenance.get("dataset_bindings", {}),
        },
        "costs": provenance.get("cost_assumptions", {}),
        "gates": provenance.get("gates", {}),
        "build": {
            key: provenance.get(key)
            for key in (
                "program", "hypothesis", "git_commit", "strategy", "seed", "versions"
            )
        },
        "results": {
            "status": run.get("status"),
            "decision": run.get("decision"),
            "evidence": _semantic_results(results),
        },
    }


def _diff(dimension: str, left: Any, right: Any, path: tuple = ()) -> list[dict]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        out = []
        for key in sorted(set(left) | set(right), key=str):
            out.extend(_diff(
                dimension,
                left.get(key, _MISSING),
                right.get(key, _MISSING),
                (*path, key),
            ))
        return out
    if isinstance(left, list) and isinstance(right, list):
        out = []
        for index in range(max(len(left), len(right))):
            lv = left[index] if index < len(left) else _MISSING
            rv = right[index] if index < len(right) else _MISSING
            out.extend(_diff(dimension, lv, rv, (*path, index)))
        return out
    if left == right:
        return []
    return [{
        "dimension": dimension,
        "path": list(path),
        "left": _reported(left),
        "right": _reported(right),
    }]


def compare_experiment_evidence(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    """Report exact differences and dimensions that forbid like-for-like claims."""
    left_sections = _sections(left)
    right_sections = _sections(right)
    differences = []
    incomparable = []
    for dimension in (
        "graph", "resolution", "parameters", "datasets", "costs", "gates", "build",
        "results",
    ):
        changed = _diff(
            dimension, left_sections[dimension], right_sections[dimension]
        )
        differences.extend(changed)
        if changed and dimension in _INCOMPARABLE:
            incomparable.append(_INCOMPARABLE[dimension])
    return {
        "equivalent": not differences,
        "incomparable": incomparable,
        "differences": differences,
    }


__all__ = ["compare_experiment_evidence"]
