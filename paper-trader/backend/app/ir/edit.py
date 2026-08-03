"""
The editor plane, writing half: graph mutation that cannot return an invalid
artefact.

Every edit validates its result before returning, returns a new artefact rather
than mutating its input (C2), and addresses nodes by instance identifier, never
display name (F2).
"""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from app.ir.validate import Violation, validate


class EditRejected(Exception):
    """An edit whose result would not be a conforming artefact."""

    def __init__(self, action: str, violations: Sequence[Violation]) -> None:
        detail = "; ".join(str(v) for v in violations) or "no reason recorded"
        super().__init__(f"{action} rejected: {detail}")
        self.action = action
        self.violations = tuple(violations)


def _result(action: str, graph: dict[str, Any]) -> dict[str, Any]:
    violations = validate(graph)
    if violations:
        raise EditRejected(action, violations)
    return graph


def _copy(graph: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(graph))


def _node(graph: Mapping[str, Any], instance_id: str) -> Mapping[str, Any] | None:
    return next((n for n in graph.get("nodes", ())
                 if n.get("instance_id") == instance_id), None)


# ── nodes ─────────────────────────────────────────────────────────────────

def add_node(graph: Mapping[str, Any], instance_id: str, identifier: str,
             version: int, overrides: Mapping[str, Any] | None = None,
             domain: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Place a node. The instance id is the author's; resolution derives the
    rest of the path from it (C7)."""
    if _node(graph, instance_id) is not None:
        raise EditRejected(
            f"add_node({instance_id!r})",
            [Violation("F9", f"$.nodes.{instance_id}",
                       "an instance identifier is unique within a graph")])

    out = _copy(graph)
    node: dict[str, Any] = {
        "instance_id": instance_id,
        "component": {"identifier": identifier, "version": version},
        "overrides": dict(overrides or {}),
    }
    if domain:
        node["domain"] = dict(domain)
    out.setdefault("nodes", []).append(node)
    return _result(f"add_node({instance_id!r})", out)


def remove_node(graph: Mapping[str, Any], instance_id: str) -> dict[str, Any]:
    """Remove a node, and every edge that touched it.

    One operation: leaving the edges would reference a node that is gone (F9).
    """
    if _node(graph, instance_id) is None:
        raise EditRejected(
            f"remove_node({instance_id!r})",
            [Violation("F9", f"$.nodes.{instance_id}", "is not a node in this graph")])

    out = _copy(graph)
    out["nodes"] = [n for n in out["nodes"] if n["instance_id"] != instance_id]
    out["edges"] = [e for e in out.get("edges", [])
                    if instance_id not in (e.get("source", {}).get("instance"),
                                           e.get("target", {}).get("instance"))]
    for group in out.get("groups", []):
        group["members"] = [m for m in group.get("members", []) if m != instance_id]
    return _result(f"remove_node({instance_id!r})", out)


def set_override(graph: Mapping[str, Any], instance_id: str, parameter: str,
                 value: Any) -> dict[str, Any]:
    """Set one override. F10: a value only — the validator enforces the rest."""
    if _node(graph, instance_id) is None:
        raise EditRejected(
            f"set_override({instance_id!r}, {parameter!r})",
            [Violation("F9", f"$.nodes.{instance_id}", "is not a node in this graph")])

    out = _copy(graph)
    _node(out, instance_id)["overrides"][parameter] = value  # type: ignore[index]
    return _result(f"set_override({instance_id!r}, {parameter!r})", out)


def clear_override(graph: Mapping[str, Any], instance_id: str,
                   parameter: str) -> dict[str, Any]:
    """Drop an override so the component's declared default applies again."""
    out = _copy(graph)
    node = _node(out, instance_id)
    if node is None or parameter not in node.get("overrides", {}):
        raise EditRejected(
            f"clear_override({instance_id!r}, {parameter!r})",
            [Violation("F10", f"$.nodes.{instance_id}.overrides.{parameter}",
                       "is not overridden")])
    del node["overrides"][parameter]  # type: ignore[index]
    return _result(f"clear_override({instance_id!r}, {parameter!r})", out)


# ── edges ─────────────────────────────────────────────────────────────────

def connect(graph: Mapping[str, Any], source: tuple[str, str],
            target: tuple[str, str]) -> dict[str, Any]:
    """Wire one socket to another. Both ends must be nodes in this graph."""
    action = f"connect({source} → {target})"
    edge = {"source": {"instance": source[0], "socket": source[1]},
            "target": {"instance": target[0], "socket": target[1]}}

    out = _copy(graph)
    if edge in out.get("edges", []):
        raise EditRejected(action, [Violation("F9", "$.edges",
                                              "this edge is already present")])
    out.setdefault("edges", []).append(edge)
    return _result(action, out)


def disconnect(graph: Mapping[str, Any], source: tuple[str, str],
               target: tuple[str, str]) -> dict[str, Any]:
    action = f"disconnect({source} → {target})"
    edge = {"source": {"instance": source[0], "socket": source[1]},
            "target": {"instance": target[0], "socket": target[1]}}

    out = _copy(graph)
    remaining = [e for e in out.get("edges", []) if e != edge]
    if len(remaining) == len(out.get("edges", [])):
        raise EditRejected(action, [Violation("F9", "$.edges", "no such edge")])
    out["edges"] = remaining
    return _result(action, out)


# ── grouping and naming ───────────────────────────────────────────────────

def group(graph: Mapping[str, Any], identifier: str, display_name: str,
          members: Sequence[str]) -> dict[str, Any]:
    """Reject the retired executable-group primitive.

    The import remains for one compatibility window so an old caller receives
    the F12 refusal instead of silently persisting presentation state.
    """
    raise EditRejected(
        f"group({identifier!r})",
        [Violation(
            "F12",
            "$.groups",
            "visual groups are revisioned presentation state and cannot be "
            "executable graph content",
        )],
    )


def rename(graph: Mapping[str, Any], display_name: str) -> dict[str, Any]:
    """Change the graph's display name.

    Nothing references a display name (F2), but it is part of the artefact, so a
    rename does change the content address. `test_ir_edit.py` pins that.
    """
    out = _copy(graph)
    out["display_name"] = display_name
    return _result("rename", out)
