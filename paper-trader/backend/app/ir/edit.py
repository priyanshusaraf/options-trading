"""
The editor plane, writing half: mutation that cannot store an invalid artefact.

`view.py` reads a graph. This writes one. It is the first thing in the platform
that *changes* an artefact, and the discipline it establishes is the one the
visual editor will inherit:

**Every edit validates before it is returned.** `validate()` has existed since
the format phase with nothing calling it on a write path, because there was no
write path. There is now, and an edit whose result violates §3 raises rather
than returning something storable. That is the difference between a validator
and a gate.

**Every edit returns a new artefact.** Nothing here mutates its input, for the
same reason resolution does not (C2): a caller that still holds the old graph
holds the old graph. Undo is then a matter of keeping references, not of
inverting operations, which is the design that does not accumulate bugs.

**Edits are expressed against instance identifiers, never display names.** F2:
a display name "MUST NOT be referenced by anything". An editing API is exactly
where that clause gets tested, because a UI knows a node by what the user sees.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from app.ir.validate import Violation, validate


class EditRejected(Exception):
    """An edit whose result would not be a conforming artefact.

    Carries the violations, so an editor can say which clause the user's action
    broke rather than "invalid".
    """

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

    Leaving the edges would produce a graph referencing a node that is not
    there — an F9 violation — so the two are one operation. A UI that offered
    them separately would have an invalid intermediate state to store.
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


# ── grouping and naming, which are not semantics ──────────────────────────

def group(graph: Mapping[str, Any], identifier: str, display_name: str,
          members: Sequence[str]) -> dict[str, Any]:
    """Box some nodes together. F12: a group is neither versionable nor
    publishable, which is what keeps cosmetic tidying out of version history."""
    out = _copy(graph)
    out.setdefault("groups", []).append(
        {"identifier": identifier, "display_name": display_name,
         "members": list(members)})
    return _result(f"group({identifier!r})", out)


def rename(graph: Mapping[str, Any], display_name: str) -> dict[str, Any]:
    """Change the graph's display name.

    F2 makes this free of *references*: nothing points at a display name, so no
    stored graph or experiment breaks. It is **not** free of the artefact's
    content address, because F2 also requires the display name to be in the
    artefact and F13 hashes the artefact's semantic content. Whether a rename
    should therefore mint a new body address is a real question this API
    surfaces and does not answer — `test_ir_edit.py` pins the current behaviour
    so the decision is visible rather than accidental. Changing it would be an
    amendment (§6), not an implementation detail.
    """
    out = _copy(graph)
    out["display_name"] = display_name
    return _result("rename", out)
