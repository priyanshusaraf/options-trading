"""
The editor plane, writing half: graph mutation that cannot return an invalid
artefact.

Every public edit returns a new artefact rather than mutating its input (C2)
and addresses nodes by instance identifier, never display name (F2). Individual
helpers validate their result. A bounded semantic batch validates its one final
result so incomplete intermediate values cannot escape the call.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence, TypeAlias

from app.ir.validate import Violation, validate


class EditRejected(Exception):
    """An edit whose result would not be a conforming artefact."""

    def __init__(
        self,
        action: str,
        violations: Sequence[Violation],
        *,
        operation_index: int | None = None,
    ) -> None:
        detail = "; ".join(str(v) for v in violations) or "no reason recorded"
        super().__init__(f"{action} rejected: {detail}")
        self.action = action
        self.violations = tuple(violations)
        self.operation_index = operation_index


@dataclass(frozen=True)
class SocketRef:
    instance_id: str
    socket: str


@dataclass(frozen=True)
class AddNode:
    instance_id: str
    identifier: str
    version: int
    overrides: Mapping[str, Any]
    domain: Mapping[str, str] | None
    secret_params: tuple[str, ...]
    node_index: int | None = None
    operation: Literal["add_node"] = field(init=False, default="add_node")


@dataclass(frozen=True)
class RemoveNode:
    instance_id: str
    operation: Literal["remove_node"] = field(init=False, default="remove_node")


@dataclass(frozen=True)
class Connect:
    source: SocketRef
    target: SocketRef
    edge_index: int | None = None
    operation: Literal["connect"] = field(init=False, default="connect")


@dataclass(frozen=True)
class Disconnect:
    source: SocketRef
    target: SocketRef
    operation: Literal["disconnect"] = field(init=False, default="disconnect")


@dataclass(frozen=True)
class SetDisplayName:
    display_name: str
    operation: Literal["set_display_name"] = field(
        init=False, default="set_display_name"
    )


@dataclass(frozen=True)
class SetOverride:
    instance_id: str
    parameter: str
    value: Any
    operation: Literal["set_override"] = field(init=False, default="set_override")


@dataclass(frozen=True)
class ClearOverride:
    instance_id: str
    parameter: str
    operation: Literal["clear_override"] = field(init=False, default="clear_override")


SemanticOperation: TypeAlias = (
    AddNode | RemoveNode | Connect | Disconnect
    | SetDisplayName | SetOverride | ClearOverride
)


@dataclass(frozen=True)
class EditBatchResult:
    graph: dict[str, Any]
    applied_operations: tuple[SemanticOperation, ...]
    inverse_operations: tuple[SemanticOperation, ...]


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

def _add_node(graph: Mapping[str, Any], operation: AddNode) -> dict[str, Any]:
    if _node(graph, operation.instance_id) is not None:
        raise EditRejected(
            f"add_node({operation.instance_id!r})",
            [Violation(
                "F9",
                f"$.nodes.{operation.instance_id}",
                "an instance identifier is unique within a graph",
            )],
        )
    out = _copy(graph)
    node: dict[str, Any] = {
        "instance_id": operation.instance_id,
        "component": {
            "identifier": operation.identifier,
            "version": operation.version,
        },
        "overrides": copy.deepcopy(dict(operation.overrides)),
    }
    if operation.domain:
        node["domain"] = dict(operation.domain)
    if operation.secret_params:
        node["secret_params"] = list(operation.secret_params)
    nodes = out.setdefault("nodes", [])
    index = len(nodes) if operation.node_index is None else operation.node_index
    if index < 0 or index > len(nodes):
        raise EditRejected(
            f"add_node({operation.instance_id!r})",
            [Violation("F9", "$.nodes", "node insertion index is out of bounds")],
        )
    nodes.insert(index, node)
    return out


def _remove_node(graph: Mapping[str, Any], operation: RemoveNode) -> dict[str, Any]:
    if _node(graph, operation.instance_id) is None:
        raise EditRejected(
            f"remove_node({operation.instance_id!r})",
            [Violation(
                "F9",
                f"$.nodes.{operation.instance_id}",
                "is not a node in this graph",
            )],
        )
    out = _copy(graph)
    out["nodes"] = [
        node for node in out["nodes"]
        if node["instance_id"] != operation.instance_id
    ]
    out["edges"] = [
        edge for edge in out.get("edges", [])
        if operation.instance_id not in (
            edge.get("source", {}).get("instance"),
            edge.get("target", {}).get("instance"),
        )
    ]
    return out


def _set_override(
    graph: Mapping[str, Any], operation: SetOverride
) -> dict[str, Any]:
    if _node(graph, operation.instance_id) is None:
        raise EditRejected(
            f"set_override({operation.instance_id!r}, {operation.parameter!r})",
            [Violation(
                "F9", f"$.nodes.{operation.instance_id}",
                "is not a node in this graph",
            )],
        )
    out = _copy(graph)
    node = _node(out, operation.instance_id)
    node["overrides"][operation.parameter] = copy.deepcopy(operation.value)  # type: ignore[index]
    return out


def _clear_override(
    graph: Mapping[str, Any], operation: ClearOverride
) -> dict[str, Any]:
    out = _copy(graph)
    node = _node(out, operation.instance_id)
    if node is None or operation.parameter not in node.get("overrides", {}):
        raise EditRejected(
            f"clear_override({operation.instance_id!r}, {operation.parameter!r})",
            [Violation(
                "F10",
                f"$.nodes.{operation.instance_id}.overrides.{operation.parameter}",
                "is not overridden",
            )],
        )
    del node["overrides"][operation.parameter]  # type: ignore[index]
    return out

def add_node(graph: Mapping[str, Any], instance_id: str, identifier: str,
             version: int, overrides: Mapping[str, Any] | None = None,
             domain: Mapping[str, str] | None = None,
             secret_params: Sequence[str] | None = None) -> dict[str, Any]:
    """Place a node. The instance id is the author's; resolution derives the
    rest of the path from it (C7)."""
    operation = AddNode(
        instance_id, identifier, version, dict(overrides or {}), domain,
        tuple(secret_params or ()),
    )
    return _result(f"add_node({instance_id!r})", _add_node(graph, operation))


def remove_node(graph: Mapping[str, Any], instance_id: str) -> dict[str, Any]:
    """Remove a node, and every edge that touched it.

    One operation: leaving the edges would reference a node that is gone (F9).
    """
    operation = RemoveNode(instance_id)
    return _result(f"remove_node({instance_id!r})", _remove_node(graph, operation))


def set_override(graph: Mapping[str, Any], instance_id: str, parameter: str,
                 value: Any) -> dict[str, Any]:
    """Set one override. F10: a value only — the validator enforces the rest."""
    operation = SetOverride(instance_id, parameter, value)
    return _result(
        f"set_override({instance_id!r}, {parameter!r})",
        _set_override(graph, operation),
    )


def clear_override(graph: Mapping[str, Any], instance_id: str,
                   parameter: str) -> dict[str, Any]:
    """Drop an override so the component's declared default applies again."""
    operation = ClearOverride(instance_id, parameter)
    return _result(
        f"clear_override({instance_id!r}, {parameter!r})",
        _clear_override(graph, operation),
    )


# ── edges ─────────────────────────────────────────────────────────────────

def _edge(source: SocketRef, target: SocketRef) -> dict[str, dict[str, str]]:
    return {
        "source": {"instance": source.instance_id, "socket": source.socket},
        "target": {"instance": target.instance_id, "socket": target.socket},
    }


def _connect(graph: Mapping[str, Any], operation: Connect) -> dict[str, Any]:
    action = f"connect({operation.source} → {operation.target})"
    edge = _edge(operation.source, operation.target)
    out = _copy(graph)
    edges = out.setdefault("edges", [])
    if edge in edges:
        raise EditRejected(
            action, [Violation("F9", "$.edges", "this edge is already present")]
        )
    index = len(edges) if operation.edge_index is None else operation.edge_index
    if index < 0 or index > len(edges):
        raise EditRejected(
            action, [Violation("F9", "$.edges", "edge insertion index is out of bounds")]
        )
    edges.insert(index, edge)
    return out


def _disconnect(graph: Mapping[str, Any], operation: Disconnect) -> dict[str, Any]:
    action = f"disconnect({operation.source} → {operation.target})"
    edge = _edge(operation.source, operation.target)
    out = _copy(graph)
    remaining = [item for item in out.get("edges", []) if item != edge]
    if len(remaining) == len(out.get("edges", [])):
        raise EditRejected(action, [Violation("F9", "$.edges", "no such edge")])
    out["edges"] = remaining
    return out

def connect(graph: Mapping[str, Any], source: tuple[str, str],
            target: tuple[str, str]) -> dict[str, Any]:
    """Wire one socket to another. Both ends must be nodes in this graph."""
    operation = Connect(SocketRef(*source), SocketRef(*target))
    return _result(
        f"connect({source} → {target})", _connect(graph, operation)
    )


def disconnect(graph: Mapping[str, Any], source: tuple[str, str],
               target: tuple[str, str]) -> dict[str, Any]:
    operation = Disconnect(SocketRef(*source), SocketRef(*target))
    return _result(
        f"disconnect({source} → {target})", _disconnect(graph, operation)
    )


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
    return _result("rename", _rename(graph, SetDisplayName(display_name)))


def _rename(graph: Mapping[str, Any], operation: SetDisplayName) -> dict[str, Any]:
    out = _copy(graph)
    out["display_name"] = operation.display_name
    return out


def _socket_ref(value: Mapping[str, Any]) -> SocketRef:
    return SocketRef(str(value["instance"]), str(value["socket"]))


def _inverse_for(
    graph: Mapping[str, Any], operation: SemanticOperation
) -> tuple[SemanticOperation, ...]:
    if isinstance(operation, AddNode):
        return (RemoveNode(operation.instance_id),)
    if isinstance(operation, RemoveNode):
        nodes = list(graph.get("nodes", ()))
        node_index = next(
            index for index, node in enumerate(nodes)
            if node.get("instance_id") == operation.instance_id
        )
        node = nodes[node_index]
        component = node["component"]
        restore_node = AddNode(
            operation.instance_id,
            str(component["identifier"]),
            int(component["version"]),
            copy.deepcopy(node.get("overrides", {})),
            copy.deepcopy(node.get("domain")),
            tuple(node.get("secret_params", ())),
            node_index,
        )
        restore_edges = tuple(
            Connect(
                _socket_ref(edge["source"]),
                _socket_ref(edge["target"]),
                edge_index,
            )
            for edge_index, edge in enumerate(graph.get("edges", ()))
            if operation.instance_id in (
                edge.get("source", {}).get("instance"),
                edge.get("target", {}).get("instance"),
            )
        )
        return (restore_node, *restore_edges)
    if isinstance(operation, Connect):
        return (Disconnect(operation.source, operation.target),)
    if isinstance(operation, Disconnect):
        edge = _edge(operation.source, operation.target)
        edge_index = list(graph.get("edges", ())).index(edge)
        return (Connect(operation.source, operation.target, edge_index),)
    if isinstance(operation, SetDisplayName):
        return (SetDisplayName(str(graph["display_name"])),)
    node = _node(graph, operation.instance_id)
    if node is None:
        raise RuntimeError("accepted edit has no authored source node for its inverse")
    overrides = node.get("overrides", {})
    if isinstance(operation, ClearOverride) or operation.parameter in overrides:
        return (SetOverride(
            operation.instance_id,
            operation.parameter,
            copy.deepcopy(overrides[operation.parameter]),
        ),)
    return (ClearOverride(operation.instance_id, operation.parameter),)


def _apply_unchecked(
    graph: Mapping[str, Any], operation: SemanticOperation
) -> dict[str, Any]:
    if isinstance(operation, AddNode):
        return _add_node(graph, operation)
    if isinstance(operation, RemoveNode):
        return _remove_node(graph, operation)
    if isinstance(operation, Connect):
        return _connect(graph, operation)
    if isinstance(operation, Disconnect):
        return _disconnect(graph, operation)
    if isinstance(operation, SetDisplayName):
        return _rename(graph, operation)
    if isinstance(operation, SetOverride):
        return _set_override(graph, operation)
    return _clear_override(graph, operation)


def apply_batch(
    graph: Mapping[str, Any],
    operations: Sequence[SemanticOperation],
    components: Mapping[tuple[str, int], Mapping[str, Any]],
) -> EditBatchResult:
    """Apply a closed semantic batch and validate only its final graph."""
    edited = _copy(graph)
    inverse: list[SemanticOperation] = []
    for index, operation in enumerate(operations):
        before = _copy(edited)
        try:
            edited = _apply_unchecked(edited, operation)
            operation_inverse = _inverse_for(before, operation)
        except EditRejected as exc:
            raise EditRejected(
                exc.action, exc.violations, operation_index=index
            ) from exc
        inverse[0:0] = operation_inverse
    violations = validate(edited, components)
    if violations:
        raise EditRejected("semantic_batch", violations)
    return EditBatchResult(edited, tuple(operations), tuple(inverse))
