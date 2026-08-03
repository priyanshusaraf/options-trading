"""Pure deterministic comparison of two immutable authored Component IR graphs."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ir.hashing import content_address
from app.ir.validate import validate


_MISSING = object()


class GraphComparisonRejected(Exception):
    pass


def _reported(value: Any) -> Any:
    return {"state": "missing"} if value is _MISSING else value


def _difference(dimension: str, path: list[str | int], left: Any, right: Any) -> dict:
    return {
        "dimension": dimension,
        "path": path,
        "left": _reported(left),
        "right": _reported(right),
    }


def _diff(dimension: str, path: list[str | int], left: Any, right: Any) -> list[dict]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        differences = []
        for key in sorted(set(left) | set(right), key=str):
            differences.extend(_diff(
                dimension,
                [*path, key],
                left.get(key, _MISSING),
                right.get(key, _MISSING),
            ))
        return differences
    if isinstance(left, list) and isinstance(right, list):
        differences = []
        for index in range(max(len(left), len(right))):
            differences.extend(_diff(
                dimension,
                [*path, index],
                left[index] if index < len(left) else _MISSING,
                right[index] if index < len(right) else _MISSING,
            ))
        return differences
    if left == right:
        return []
    return [_difference(dimension, path, left, right)]


def _edge_key(edge: Mapping[str, Any]) -> tuple[str, str, str, str]:
    try:
        return (
            str(edge["source"]["instance"]), str(edge["source"]["socket"]),
            str(edge["target"]["instance"]), str(edge["target"]["socket"]),
        )
    except (KeyError, TypeError) as exc:
        raise GraphComparisonRejected("immutable graph has an invalid edge") from exc


def _verified(selection: Mapping[str, Any]) -> tuple[dict, str]:
    if not isinstance(selection, Mapping) or set(selection) != {"graph", "content_address"}:
        raise GraphComparisonRejected("immutable graph comparison selection is invalid")
    graph = selection["graph"]
    declared = selection["content_address"]
    if not isinstance(graph, dict) or not isinstance(declared, str):
        raise GraphComparisonRejected("immutable graph comparison selection is invalid")
    if graph.get("groups"):
        raise GraphComparisonRejected(
            "presentation groups cannot contaminate immutable graph comparison"
        )
    violations = validate(graph)
    if violations:
        first = violations[0]
        raise GraphComparisonRejected(
            f"immutable graph is invalid at {first.path}: {first.message}"
        )
    if content_address(graph) != declared:
        raise GraphComparisonRejected("immutable graph content address does not match")
    return graph, declared


def _nodes(graph: Mapping[str, Any]) -> tuple[list[str], dict[str, dict]]:
    values = graph.get("nodes")
    if not isinstance(values, list):
        raise GraphComparisonRejected("immutable graph nodes are invalid")
    ordered: list[str] = []
    indexed: dict[str, dict] = {}
    for node in values:
        if not isinstance(node, dict) or not isinstance(node.get("instance_id"), str):
            raise GraphComparisonRejected("immutable graph node is invalid")
        instance_id = node["instance_id"]
        if instance_id in indexed:
            raise GraphComparisonRejected("immutable graph node identity is duplicated")
        ordered.append(instance_id)
        indexed[instance_id] = node
    return ordered, indexed


def _edges(graph: Mapping[str, Any]) -> tuple[list[tuple], dict[tuple, dict]]:
    values = graph.get("edges")
    if not isinstance(values, list):
        raise GraphComparisonRejected("immutable graph edges are invalid")
    ordered: list[tuple] = []
    indexed: dict[tuple, dict] = {}
    for edge in values:
        if not isinstance(edge, dict):
            raise GraphComparisonRejected("immutable graph edge is invalid")
        key = _edge_key(edge)
        if key in indexed:
            raise GraphComparisonRejected("immutable graph edge is duplicated")
        ordered.append(key)
        indexed[key] = edge
    return ordered, indexed


def compare_graph_versions(
    left_selection: Mapping[str, Any], right_selection: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare exact stored graph documents without resolving or loading presentation."""
    left, left_address = _verified(left_selection)
    right, right_address = _verified(right_selection)
    left_order, left_nodes = _nodes(left)
    right_order, right_nodes = _nodes(right)
    left_edge_order, left_edges = _edges(left)
    right_edge_order, right_edges = _edges(right)
    differences: list[dict] = []

    for instance_id in sorted(set(left_nodes) | set(right_nodes)):
        lnode = left_nodes.get(instance_id, _MISSING)
        rnode = right_nodes.get(instance_id, _MISSING)
        if lnode is _MISSING or rnode is _MISSING:
            differences.append(_difference(
                "structure", ["nodes", instance_id], lnode, rnode
            ))
            continue
        differences.extend(_diff(
            "components", ["nodes", instance_id, "component"],
            lnode.get("component", _MISSING), rnode.get("component", _MISSING),
        ))
        differences.extend(_diff(
            "parameters", ["nodes", instance_id, "overrides"],
            lnode.get("overrides", _MISSING), rnode.get("overrides", _MISSING),
        ))
        differences.extend(_diff(
            "parameters", ["nodes", instance_id, "secret_params"],
            lnode.get("secret_params", _MISSING), rnode.get("secret_params", _MISSING),
        ))
        differences.extend(_diff(
            "metadata", ["nodes", instance_id, "domain"],
            lnode.get("domain", _MISSING), rnode.get("domain", _MISSING),
        ))

    for key in sorted(set(left_edges) | set(right_edges)):
        if key not in left_edges or key not in right_edges:
            differences.append(_difference(
                "structure", ["edges", *key],
                left_edges.get(key, _MISSING), right_edges.get(key, _MISSING),
            ))

    differences.extend(_diff(
        "interface", ["interface"],
        left.get("interface", _MISSING), right.get("interface", _MISSING),
    ))
    differences.extend(_diff(
        "metadata", ["display_name"],
        left.get("display_name", _MISSING), right.get("display_name", _MISSING),
    ))
    for key in ("format_version", "kind", "identifier", "version", "parent_version"):
        differences.extend(_diff(
            "identity", [key], left.get(key, _MISSING), right.get(key, _MISSING)
        ))
    if set(left_nodes) == set(right_nodes) and left_order != right_order:
        differences.append(_difference(
            "identity", ["nodes", "order"], left_order, right_order
        ))
    if set(left_edges) == set(right_edges) and left_edge_order != right_edge_order:
        differences.append(_difference(
            "identity", ["edges", "order"],
            [list(key) for key in left_edge_order],
            [list(key) for key in right_edge_order],
        ))
    if left_address != right_address:
        differences.append(_difference(
            "identity", ["content_address"], left_address, right_address
        ))

    differences.sort(key=lambda item: (item["dimension"], repr(item["path"])))
    return {
        "equivalent": not differences,
        "incomparable": [],
        "differences": differences,
    }


__all__ = ["GraphComparisonRejected", "compare_graph_versions"]
