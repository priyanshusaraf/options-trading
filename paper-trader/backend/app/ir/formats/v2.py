"""Closed Component IR v2 schema and identity contract.

This module intentionally stops before resolution and evaluation.  A validated
document is descriptive input, never an executable or an admission authority.
"""
from __future__ import annotations

import copy
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from app.ir.hashing import content_address
from app.ir.schema import (
    V2_ASSEMBLIES, V2_CARDINALITIES, V2_COMPONENT_REF_KEYS,
    V2_CONNECTION_KEYS, V2_DOCUMENT_KEYS, V2_EDGE_KEYS, V2_ENDPOINT_KEYS,
    V2_FLOWS, V2_INPUT_PORT_KEYS, V2_METADATA_KEYS, V2_NODE_KEYS,
    V2_PORT_KEYS, V2_SCOPES, V2_SHAPES, V2_TYPE_REF_KEYS,
)

FORMAT_VERSION = 2
IDENTITY_SCHEME_VERSION = 1


@dataclass(frozen=True)
class V2Violation:
    code: str
    path: str
    message: str


def _error(errors: list[V2Violation], code: str, path: str, message: str) -> None:
    errors.append(V2Violation(code, path, message))


def _closed(value: Any, keys: frozenset[str], path: str, errors: list[V2Violation], *, required: frozenset[str] | None = None) -> bool:
    if not isinstance(value, Mapping):
        _error(errors, "V2_OBJECT", path, "must be an object")
        return False
    for key in sorted(set(value) - keys):
        _error(errors, "V2_UNKNOWN_KEY", f"{path}.{key}", "not in the v2 grammar")
    for key in sorted((keys if required is None else required) - set(value)):
        _error(errors, "V2_REQUIRED", f"{path}.{key}", "missing")
    return True


def _integer(value: Any, path: str, errors: list[V2Violation], *, minimum: int = 0) -> bool:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _error(errors, "V2_INTEGER", path, f"must be an integer >= {minimum}")
        return False
    return True


def _text(value: Any, path: str, errors: list[V2Violation], *, nonempty: bool = False) -> bool:
    if not isinstance(value, str) or (nonempty and not value):
        _error(errors, "V2_STRING", path, "must be a non-empty string" if nonempty else "must be a string")
        return False
    if unicodedata.normalize("NFC", value) != value:
        _error(errors, "V2_NFC", path, "must be NFC-normalized")
        return False
    return True


def _type_ref(value: Any, path: str, errors: list[V2Violation]) -> tuple[str, int] | None:
    if not _closed(value, V2_TYPE_REF_KEYS, path, errors):
        return None
    if not _text(value.get("type_id"), f"{path}.type_id", errors, nonempty=True):
        return None
    if not _integer(value.get("type_version"), f"{path}.type_version", errors, minimum=1):
        return None
    return value["type_id"], value["type_version"]


def _port(value: Any, path: str, errors: list[V2Violation], *, boundary: bool = False) -> None:
    keys = V2_INPUT_PORT_KEYS if isinstance(value, Mapping) and value.get("direction") == "input" else V2_PORT_KEYS
    required = V2_PORT_KEYS | (frozenset({"connections"}) if isinstance(value, Mapping) and value.get("direction") == "input" else frozenset())
    if not _closed(value, keys, path, errors, required=required):
        return
    if not _text(value.get("port_id"), f"{path}.port_id", errors, nonempty=True):
        return
    direction = value.get("direction")
    if direction not in {"input", "output"}:
        _error(errors, "V2_DIRECTION", f"{path}.direction", "must be input or output")
    if value.get("semantic_flow") not in V2_FLOWS:
        _error(errors, "V2_FLOW", f"{path}.semantic_flow", "is not a closed semantic flow")
    _text(value.get("semantic_role"), f"{path}.semantic_role", errors, nonempty=True)
    _type_ref(value.get("type_ref"), f"{path}.type_ref", errors)
    if value.get("shape") not in V2_SHAPES:
        _error(errors, "V2_SHAPE", f"{path}.shape", "is not a closed shape")
    if direction != "input":
        return
    connections = value.get("connections")
    if not _closed(connections, V2_CONNECTION_KEYS, f"{path}.connections", errors):
        return
    cardinality, assembly = connections.get("cardinality"), connections.get("assembly")
    minimum, maximum = connections.get("min"), connections.get("max")
    if cardinality not in V2_CARDINALITIES:
        _error(errors, "V2_CARDINALITY", f"{path}.connections.cardinality", "is not closed")
        return
    if assembly not in V2_ASSEMBLIES:
        _error(errors, "V2_ASSEMBLY", f"{path}.connections.assembly", "is not closed")
    if not _integer(minimum, f"{path}.connections.min", errors):
        return
    if cardinality == "single" and (minimum != 1 or maximum != 1 or assembly != "single"):
        _error(errors, "V2_CARDINALITY", f"{path}.connections", "single requires min=1, max=1, assembly=single")
    elif cardinality == "optional" and (minimum != 0 or maximum != 1 or assembly != "single"):
        _error(errors, "V2_CARDINALITY", f"{path}.connections", "optional requires min=0, max=1, assembly=single")
    elif cardinality == "bounded_many":
        if not _integer(maximum, f"{path}.connections.max", errors, minimum=2) or maximum < minimum:
            _error(errors, "V2_CARDINALITY", f"{path}.connections", "bounded_many max must be finite and >= min")
        if assembly not in {"ordered", "keyed", "unordered"}:
            _error(errors, "V2_ASSEMBLY", f"{path}.connections.assembly", "many inputs require ordered, keyed, or unordered")
    elif cardinality == "variadic":
        if maximum is not None:
            _error(errors, "V2_CARDINALITY", f"{path}.connections.max", "variadic max must be null")
        if assembly not in {"ordered", "keyed", "unordered"}:
            _error(errors, "V2_ASSEMBLY", f"{path}.connections.assembly", "variadic inputs require ordered, keyed, or unordered")
    if "default" in value and minimum != 0:
        _error(errors, "V2_DEFAULT", f"{path}.default", "is allowed only when min is zero")


def _endpoint(value: Any, path: str, errors: list[V2Violation]) -> None:
    required = frozenset({"scope", "port_id"})
    if isinstance(value, Mapping) and value.get("scope") == "node":
        required = required | frozenset({"node_id"})
    if not _closed(value, V2_ENDPOINT_KEYS, path, errors, required=required):
        return
    scope = value.get("scope")
    if scope not in V2_SCOPES:
        _error(errors, "V2_SCOPE", f"{path}.scope", "is not closed")
    node_id = value.get("node_id")
    if scope == "node":
        _text(node_id, f"{path}.node_id", errors, nonempty=True)
    elif node_id is not None:
        _error(errors, "V2_ENDPOINT", f"{path}.node_id", "is permitted only for node scope")
    _text(value.get("port_id"), f"{path}.port_id", errors, nonempty=True)


def _binding(value: Any, path: str, errors: list[V2Violation]) -> None:
    if not isinstance(value, Mapping):
        _error(errors, "V2_OBJECT", path, "must be an object")
        return
    kind = value.get("kind")
    permitted = {"kind"} | ({"position"} if kind == "ordered" else {"key"} if kind == "keyed" else set())
    for key in sorted(set(value) - permitted):
        _error(errors, "V2_UNKNOWN_KEY", f"{path}.{key}", "not allowed by binding kind")
    if kind not in {"single", "ordered", "keyed", "unordered"}:
        _error(errors, "V2_BINDING", f"{path}.kind", "is not closed")
    elif kind == "ordered":
        _integer(value.get("position"), f"{path}.position", errors)
    elif kind == "keyed":
        _text(value.get("key"), f"{path}.key", errors, nonempty=True)


def validate_document(document: Any, registry: Any) -> list[V2Violation]:
    """Pure closed validation. The returned order is deterministic."""
    errors: list[V2Violation] = []
    types = getattr(registry, "v2_types", {})
    if not _closed(document, V2_DOCUMENT_KEYS, "$", errors):
        return errors
    if document.get("format_version") != 2 or isinstance(document.get("format_version"), bool):
        _error(errors, "V2_FORMAT", "$.format_version", "must be integer 2")
    _text(document.get("strategy_id"), "$.strategy_id", errors, nonempty=True)
    _integer(document.get("strategy_version"), "$.strategy_version", errors, minimum=1)
    metadata = document.get("metadata")
    if _closed(metadata, V2_METADATA_KEYS, "$.metadata", errors):
        if metadata.get("metadata_version") != 1 or isinstance(metadata.get("metadata_version"), bool):
            _error(errors, "V2_METADATA_VERSION", "$.metadata.metadata_version", "must be integer 1")
        for name in ("name", "description"):
            if metadata.get(name) is not None:
                _text(metadata.get(name), f"$.metadata.{name}", errors)
        tags = metadata.get("tags")
        if not isinstance(tags, list):
            _error(errors, "V2_TAGS", "$.metadata.tags", "must be an array")
        else:
            seen: set[str] = set()
            for index, tag in enumerate(tags):
                if _text(tag, f"$.metadata.tags[{index}]", errors, nonempty=True):
                    if tag in seen:
                        _error(errors, "V2_TAGS", f"$.metadata.tags[{index}]", "must not contain duplicates")
                    seen.add(tag)
    _validate_graph_body(document, registry, errors, "$", require_collections=False)
    return errors


def validate_graph_body(body: Any, registry: Any) -> list[V2Violation]:
    """Validate the ordinary graph contract reused by a compound body.

    A body deliberately has no document envelope, but its ports, nodes, edges,
    cardinality, and topology are exactly the ordinary v2 graph contract.
    """
    errors: list[V2Violation] = []
    _validate_graph_body(body, registry, errors, "$", require_collections=True)
    return errors


def _validate_graph_body(
    document: Any, registry: Any, errors: list[V2Violation], path: str, *, require_collections: bool,
) -> None:
    if not isinstance(document, Mapping):
        _error(errors, "V2_OBJECT", path, "must be an object")
        return
    components = getattr(registry, "v2_components", {})
    types = getattr(registry, "v2_types", {})
    if require_collections:
        required = {"graph_inputs", "graph_outputs", "nodes", "edges"}
        if set(document) != required:
            for key in sorted(required - set(document)):
                _error(errors, "V2_REQUIRED", f"{path}.{key}", "missing")
            for key in sorted(set(document) - required):
                _error(errors, "V2_UNKNOWN_KEY", f"{path}.{key}", "not in the ordinary v2 graph grammar")
    for name, ports, direction in (
        ("graph_inputs", document.get("graph_inputs"), "input"),
        ("graph_outputs", document.get("graph_outputs"), "output"),
    ):
        if not isinstance(ports, (list, tuple)):
            _error(errors, "V2_ARRAY", f"$.{name}", "must be an array")
            continue
        ids: set[str] = set()
        for index, port in enumerate(ports):
            _port(port, f"$.{name}[{index}]", errors, boundary=True)
            if isinstance(port, Mapping):
                if port.get("direction") != direction:
                    _error(errors, "V2_BOUNDARY", f"$.{name}[{index}].direction", f"must be {direction}")
                if isinstance(port.get("port_id"), str):
                    if port["port_id"] in ids: _error(errors, "V2_DUPLICATE", f"$.{name}[{index}].port_id", "must be unique")
                    ids.add(port["port_id"])
                ref = _type_ref(port.get("type_ref"), f"$.{name}[{index}].type_ref", errors)
                if ref is not None:
                    descriptor = types.get(ref)
                    if descriptor is None:
                        _error(errors, "V2_TYPE", f"$.{name}[{index}].type_ref", "is not registered")
                    elif port.get("shape") not in descriptor.get("shapes", ()):
                        _error(errors, "V2_SHAPE", f"$.{name}[{index}].shape", "conflicts with registered type")
    nodes = document.get("nodes")
    node_ids: set[str] = set()
    if not isinstance(nodes, (list, tuple)): _error(errors, "V2_ARRAY", "$.nodes", "must be an array")
    else:
        for index, node in enumerate(nodes):
            path = f"$.nodes[{index}]"
            if not _closed(node, V2_NODE_KEYS, path, errors): continue
            if _text(node.get("node_id"), f"{path}.node_id", errors, nonempty=True):
                if node["node_id"] in node_ids: _error(errors, "V2_DUPLICATE", f"{path}.node_id", "must be unique")
                node_ids.add(node["node_id"])
            if _closed(node.get("component"), V2_COMPONENT_REF_KEYS, f"{path}.component", errors):
                ref = (node["component"].get("component_id"), node["component"].get("component_version"))
                if not _text(ref[0], f"{path}.component.component_id", errors, nonempty=True) or not _integer(ref[1], f"{path}.component.component_version", errors, minimum=1): pass
                elif ref not in components: _error(errors, "V2_COMPONENT", f"{path}.component", "is not registered")
            if not isinstance(node.get("parameters"), Mapping): _error(errors, "V2_PARAMETERS", f"{path}.parameters", "must be an object")
    _validate_edges(document, registry, errors, node_ids, types)
    return None


def _validate_edges(document: Mapping[str, Any], registry: Any, errors: list[V2Violation], node_ids: set[str], types: Mapping[Any, Any]) -> None:
    edges = document.get("edges")
    if not isinstance(edges, (list, tuple)): _error(errors, "V2_ARRAY", "$.edges", "must be an array"); return
    ids: set[str] = set(); targets: dict[tuple[str, str, str | None], list[Mapping[str, Any]]] = {}
    semantic_tuples: set[tuple[str, str | None, str, str, str | None, str, tuple[tuple[str, Any], ...]]] = set()
    for index, edge in enumerate(edges):
        path = f"$.edges[{index}]"
        if not _closed(edge, V2_EDGE_KEYS, path, errors): continue
        if _text(edge.get("edge_id"), f"{path}.edge_id", errors, nonempty=True):
            if edge["edge_id"] in ids: _error(errors, "V2_DUPLICATE", f"{path}.edge_id", "must be unique")
            ids.add(edge["edge_id"])
        _endpoint(edge.get("source"), f"{path}.source", errors); _endpoint(edge.get("target"), f"{path}.target", errors); _binding(edge.get("binding"), f"{path}.binding", errors)
        if not isinstance(edge.get("source"), Mapping) or not isinstance(edge.get("target"), Mapping): continue
        source, target = edge["source"], edge["target"]
        binding = edge.get("binding")
        if isinstance(binding, Mapping):
            tuple_key = (
                str(source.get("scope")), source.get("node_id"), str(source.get("port_id")),
                str(target.get("scope")), target.get("node_id"), str(target.get("port_id")),
                tuple(sorted(binding.items())),
            )
            if tuple_key in semantic_tuples:
                _error(errors, "V2_DUPLICATE", path, "duplicates an existing source-target-binding tuple")
            semantic_tuples.add(tuple_key)
        if source.get("scope") == "graph_output": _error(errors, "V2_DIRECTION", f"{path}.source.scope", "graph_output cannot be an edge source")
        if target.get("scope") == "graph_input": _error(errors, "V2_DIRECTION", f"{path}.target.scope", "graph_input cannot be an edge target")
        for endpoint, endpoint_path in ((source, "source"), (target, "target")):
            if endpoint.get("scope") == "node" and endpoint.get("node_id") not in node_ids:
                _error(errors, "V2_ENDPOINT", f"{path}.{endpoint_path}.node_id", "does not name a node")
        key = (target.get("scope"), target.get("port_id"), target.get("node_id"))
        targets.setdefault(key, []).append(edge)
        source_port = _source_port(document, registry, source)
        target_port = _target_port(document, registry, key)
        if source_port is None:
            _error(errors, "V2_ENDPOINT", f"{path}.source.port_id", "does not name an output port")
        if target_port is None:
            _error(errors, "V2_ENDPOINT", f"{path}.target.port_id", "does not name an input port")
        if source_port is not None and target_port is not None:
            source_ref, target_ref = source_port.get("type_ref"), target_port.get("type_ref")
            if source_ref != target_ref or source_port.get("shape") != target_port.get("shape") or source_port.get("semantic_flow") != target_port.get("semantic_flow"):
                _error(errors, "V2_TYPE", path, "source and target contracts must match exactly")
    # Static cardinality/type checks use the registry's exact component contracts.
    for target, members in sorted(targets.items()):
        port = _target_port(document, registry, target)
        if port is None: continue
        _port(port, "$.registry", errors)
        # A graph output is a boundary sink, not a component input.  Its
        # contract is therefore exactly one ``single`` producer rather than
        # an undeclared component ``connections`` object.
        if target[0] == "graph_output":
            if len(members) != 1:
                _error(errors, "V2_BOUNDARY", "$.edges", "each graph output requires exactly one producer")
            elif members[0].get("binding", {}).get("kind") != "single":
                _error(errors, "V2_BINDING", "$.edges", "graph output binding must be single")
            continue
        contract = port.get("connections", {})
        count = len(members); minimum, maximum = contract.get("min"), contract.get("max")
        if isinstance(minimum, int) and count < minimum: _error(errors, "V2_CARDINALITY", "$.edges", "target has fewer edges than min")
        if isinstance(maximum, int) and count > maximum: _error(errors, "V2_CARDINALITY", "$.edges", "target has more edges than max")
        assembly = contract.get("assembly"); bindings = [member.get("binding", {}) for member in members]
        kinds = [binding.get("kind") for binding in bindings]
        expected = "single" if assembly == "single" else assembly
        if any(kind != expected for kind in kinds): _error(errors, "V2_BINDING", "$.edges", "binding kind disagrees with target assembly")
        if assembly == "ordered":
            positions = [binding.get("position") for binding in bindings]
            if (not all(isinstance(position, int) and not isinstance(position, bool) for position in positions)
                    or sorted(positions) != list(range(len(positions)))):
                _error(errors, "V2_BINDING", "$.edges", "ordered positions must be unique and contiguous from zero")
        if assembly == "keyed":
            keys = [binding.get("key") for binding in bindings]
            if len(set(keys)) != len(keys): _error(errors, "V2_BINDING", "$.edges", "keyed keys must be unique")
    # Inputs with no incoming edge still need min/default validation.
    for node in document.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        component = getattr(registry, "v2_components", {}).get((node.get("component", {}).get("component_id"), node.get("component", {}).get("component_version")), {})
        for port in component.get("ports", []):
            if port.get("direction") != "input": continue
            key = ("node", port.get("port_id"), node.get("node_id"))
            if key not in targets and port.get("connections", {}).get("min", 0) > 0:
                _error(errors, "V2_CARDINALITY", f"$.nodes[{node.get('node_id')}].{port.get('port_id')}", "required input has no edge")
    _reject_cycles(document, errors)


def _target_port(document: Mapping[str, Any], registry: Any, target: tuple[str, str, str | None]) -> Mapping[str, Any] | None:
    scope, port_id, node_id = target
    if scope == "graph_output": return next((p for p in document.get("graph_outputs", []) if p.get("port_id") == port_id), None)
    if scope != "node": return None
    node = next((n for n in document.get("nodes", []) if n.get("node_id") == node_id), None)
    if not node: return None
    component = getattr(registry, "v2_components", {}).get((node["component"].get("component_id"), node["component"].get("component_version")))
    return next((p for p in (component or {}).get("ports", []) if p.get("port_id") == port_id and p.get("direction") == "input"), None)


def _source_port(document: Mapping[str, Any], registry: Any, source: Mapping[str, Any]) -> Mapping[str, Any] | None:
    scope, port_id = source.get("scope"), source.get("port_id")
    if scope == "graph_input": return next((p for p in document.get("graph_inputs", []) if p.get("port_id") == port_id), None)
    if scope != "node": return None
    node = next((n for n in document.get("nodes", []) if n.get("node_id") == source.get("node_id")), None)
    if not node: return None
    component = getattr(registry, "v2_components", {}).get((node["component"].get("component_id"), node["component"].get("component_version")))
    return next((p for p in (component or {}).get("ports", []) if p.get("port_id") == port_id and p.get("direction") == "output"), None)


def _reject_cycles(document: Mapping[str, Any], errors: list[V2Violation]) -> None:
    nodes = {
        node_id
        for node in document.get("nodes", [])
        if isinstance(node, Mapping) and isinstance((node_id := node.get("node_id")), str)
    }
    outgoing = {node: set() for node in nodes}; incoming = {node: 0 for node in nodes}
    for edge in document.get("edges", []):
        # Structural validation has already recorded malformed edge objects.
        # Cycle traversal must not reinterpret or dereference those values:
        # only complete mapping endpoints can contribute topology.
        if not isinstance(edge, Mapping):
            continue
        source, target = edge.get("source"), edge.get("target")
        if not isinstance(source, Mapping) or not isinstance(target, Mapping):
            continue
        if source.get("scope") == target.get("scope") == "node" and source.get("node_id") in nodes and target.get("node_id") in nodes and target["node_id"] not in outgoing[source["node_id"]]:
            outgoing[source["node_id"]].add(target["node_id"]); incoming[target["node_id"]] += 1
    ready = sorted(node for node, count in incoming.items() if count == 0); seen = 0
    while ready:
        node = ready.pop(0); seen += 1
        for next_node in sorted(outgoing[node]):
            incoming[next_node] -= 1
            if incoming[next_node] == 0: ready.append(next_node)
    if seen != len(nodes): _error(errors, "V2_CYCLE", "$.edges", "v2 topology must be acyclic")


def canonical_document(document: Mapping[str, Any], registry: Any) -> Mapping[str, Any]:
    errors = validate_document(document, registry)
    if errors: raise ValueError("; ".join(f"{e.code}:{e.path}" for e in errors))
    result = copy.deepcopy(document)
    result["metadata"]["tags"] = sorted(result["metadata"]["tags"])
    result["nodes"] = sorted(result["nodes"], key=lambda node: node["node_id"])
    result["edges"] = sorted(result["edges"], key=lambda edge: edge["edge_id"])
    result["graph_inputs"] = sorted(result["graph_inputs"], key=lambda port: port["port_id"])
    result["graph_outputs"] = sorted(result["graph_outputs"], key=lambda port: port["port_id"])
    return result


def content_address_for(document: Mapping[str, Any], registry: Any) -> str:
    return content_address(canonical_document(document, registry))


def executable_projection(document: Mapping[str, Any], registry: Any) -> Mapping[str, Any]:
    value = canonical_document(document, registry)
    return {key: value[key] for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}


def graph_address_for(document: Mapping[str, Any], registry: Any) -> str:
    return content_address({"identity_scheme_version": IDENTITY_SCHEME_VERSION, "graph": executable_projection(document, registry)})
