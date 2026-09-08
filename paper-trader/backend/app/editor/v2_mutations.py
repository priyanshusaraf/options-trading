"""Closed, deterministic command layer for the canonical Component IR v2.

This module owns no semantic authority.  It builds candidates exclusively from
the accepted registry descriptors, then delegates validation, resolution and
identity to the existing v2 authorities.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import math
import threading
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from app.ir.hashing import canonical_json, content_address


MAX_COMMANDS = 32
MAX_BATCH_BYTES = 1_048_576
MAX_RECEIPT_BYTES = 1_048_576
MAX_PRESENTATION_ITEMS = 10_000
MAX_IDENTIFIER_BYTES = 128


class EditorRefusal(ValueError):
    """Stable, non-leaking editor refusal."""

    def __init__(self, code: str, message: str, *, path: str = "$", current_revision: int | None = None):
        super().__init__(message)
        self.code = code
        self.path = path
        self.current_revision = current_revision

    def payload(self) -> dict[str, Any]:
        value: dict[str, Any] = {"code": self.code, "path": self.path, "message": str(self)}
        if self.current_revision is not None:
            value["current_revision"] = self.current_revision
        return value


@dataclass(frozen=True)
class SemanticMutation:
    document: dict[str, Any]
    forward_commands: tuple[dict[str, Any], ...]
    inverse_commands: tuple[dict[str, Any], ...]
    content_address: str
    graph_address: str
    resolved_address: str


@dataclass(frozen=True)
class PresentationMutation:
    document: dict[str, Any]
    forward_commands: tuple[dict[str, Any], ...]
    inverse_commands: tuple[dict[str, Any], ...]
    presentation_address: str


_RECEIPT_KEY_DOMAIN = b"strategy-os/v2-editor-semantic-receipt/v1"
_RECEIPT_MAC_DOMAIN = b"strategy-os/v2-editor-semantic-receipt/mac/v1\x00"


class _ReceiptRestoreInvocation:
    """One exact self-authenticating, process-local restore invocation."""

    __slots__ = (
        "__lock", "__consumed", "__receipt", "__document", "__commands",
        "__opposite_commands", "__registry", "__catalogue_identities",
        "__owner_id", "__project_id", "__graph_identifier", "__current_version",
        "__base_revision", "__requested_intent", "__target_content",
        "__target_graph", "__document_bytes", "__commands_bytes",
        "__opposite_commands_bytes", "__receipt_bytes",
    )

    def __init__(
        self, receipt: Mapping[str, Any], document: Mapping[str, Any],
        commands: Sequence[Mapping[str, Any]], *,
        opposite_commands: Sequence[Mapping[str, Any]], registry: Any,
        catalogue_identities: frozenset[tuple[str, int]] | None,
        owner_id: str, project_id: str, graph_identifier: str,
        current_version: int | None, base_revision: int, requested_intent: str,
        target_content: str, target_graph: str,
    ) -> None:
        self.__lock = threading.Lock()
        self.__consumed = False
        self.__receipt = copy.deepcopy(_plain(receipt))
        self.__document = copy.deepcopy(_plain(document))
        self.__commands = tuple(copy.deepcopy(_plain(command)) for command in commands)
        self.__opposite_commands = tuple(
            copy.deepcopy(_plain(command)) for command in opposite_commands)
        self.__registry = registry
        self.__catalogue_identities = catalogue_identities
        self.__owner_id = owner_id
        self.__project_id = project_id
        self.__graph_identifier = graph_identifier
        self.__current_version = current_version
        self.__base_revision = base_revision
        self.__requested_intent = requested_intent
        self.__target_content = target_content
        self.__target_graph = target_graph
        self.__receipt_bytes = canonical_json(self.__receipt).encode("utf-8")
        self.__document_bytes = canonical_json(self.__document).encode("utf-8")
        self.__commands_bytes = canonical_json(self.__commands).encode("utf-8")
        self.__opposite_commands_bytes = canonical_json(
            self.__opposite_commands).encode("utf-8")
        # Construction rejects incomplete or altered material, but grants no
        # authority. invoke() repeats this full authentication after consuming.
        self.__verified_context()

    def __verified_context(self) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
        try:
            if (canonical_json(self.__receipt).encode("utf-8") != self.__receipt_bytes
                    or canonical_json(self.__document).encode("utf-8") != self.__document_bytes
                    or canonical_json(self.__commands).encode("utf-8") != self.__commands_bytes
                    or canonical_json(self.__opposite_commands).encode("utf-8")
                    != self.__opposite_commands_bytes):
                raise EditorRefusal(
                    "RECEIPT_CAPABILITY_INVALID", "receipt invocation material changed")
            return _verify_receipt_restore_context(
                self.__receipt,
                self.__document,
                self.__commands,
                opposite_commands=self.__opposite_commands,
                registry=self.__registry,
                owner_id=self.__owner_id,
                project_id=self.__project_id,
                graph_identifier=self.__graph_identifier,
                current_version=self.__current_version,
                base_revision=self.__base_revision,
                requested_intent=self.__requested_intent,
                target_content=self.__target_content,
                target_graph=self.__target_graph,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            if isinstance(exc, EditorRefusal):
                raise
            raise EditorRefusal(
                "RECEIPT_CAPABILITY_INVALID",
                "receipt restore invocation is absent, consumed, or foreign",
            ) from exc

    def invoke(self) -> SemanticMutation:
        try:
            lock = self.__lock
        except AttributeError as exc:
            raise EditorRefusal(
                "RECEIPT_CAPABILITY_INVALID",
                "receipt restore invocation is absent, consumed, or foreign",
            ) from exc
        with lock:
            if self.__consumed:
                raise EditorRefusal(
                    "RECEIPT_CAPABILITY_INVALID",
                    "receipt restore invocation is absent, consumed, or foreign",
                )
            self.__consumed = True
        # Consumption precedes authentication, canonical work and validation.
        canonical, forward, opposite = self.__verified_context()
        working = copy.deepcopy(canonical)
        allowed = (_catalogue_identities() if self.__catalogue_identities is None
                   else self.__catalogue_identities)
        inverse: list[dict[str, Any]] = []
        for index, command in enumerate(forward):
            kind = command.get("command")
            path = f"$.commands[{index}]"
            if kind != "restore_edge_from_receipt":
                local_inverse = _apply_public_semantic_command(
                    working, command, index=index, registry=self.__registry,
                    catalogue_identities=allowed)
                inverse = local_inverse + inverse
                continue
            _closed(command, kind, {"mode", "edge", "graph_output_descriptor"}, index)
            if command["mode"] != "insert_or_replace_graph_output":
                raise EditorRefusal(
                    "REQUEST_SCHEMA_INVALID", "private edge restoration mode is invalid", path=path)
            edge = command["edge"]
            if not isinstance(edge, Mapping) or set(edge) != {
                    "edge_id", "source", "target", "binding"}:
                raise EditorRefusal(
                    "REQUEST_SCHEMA_INVALID", "restored edge is open or incomplete", path=path)
            edge = copy.deepcopy(_plain(edge))
            if not isinstance(edge["edge_id"], str) or not edge["edge_id"]:
                raise EditorRefusal(
                    "REQUEST_SCHEMA_INVALID", "restored edge identity is absent", path=path)
            if not isinstance(edge["source"], Mapping) or not isinstance(edge["target"], Mapping):
                raise EditorRefusal(
                    "REQUEST_SCHEMA_INVALID", "restored endpoints are invalid", path=path)
            if (edge["source"].get("scope") not in {"node", "graph_input"}
                    or edge["target"].get("scope") not in {"node", "graph_output"}):
                raise EditorRefusal(
                    "REQUEST_SCHEMA_INVALID", "restored endpoint scope is invalid", path=path)
            _binding(edge["binding"], path + ".edge.binding")
            descriptor = command["graph_output_descriptor"]
            if edge["target"]["scope"] == "node":
                if descriptor is not None:
                    raise EditorRefusal(
                        "REQUEST_SCHEMA_INVALID", "node edge cannot restore an output", path=path)
                retained_edges = working["edges"]
            else:
                if (not isinstance(descriptor, Mapping)
                        or descriptor.get("port_id") != edge["target"].get("port_id")):
                    raise EditorRefusal(
                        "REQUEST_SCHEMA_INVALID", "graph output descriptor does not match", path=path)
                descriptor = copy.deepcopy(_plain(descriptor))
                output_id = descriptor["port_id"]
                working["graph_outputs"] = [
                    row for row in working["graph_outputs"] if row["port_id"] != output_id]
                retained_edges = [
                    row for row in working["edges"]
                    if row["target"] != {"scope": "graph_output", "port_id": output_id}]
                working["edges"] = retained_edges
                working["graph_outputs"].append(descriptor)
            if any(row["edge_id"] == edge["edge_id"] for row in retained_edges):
                raise EditorRefusal(
                    "EDGE_ALREADY_EXISTS", "restored edge identity already exists", path=path)
            if any((row["source"], row["target"], row["binding"])
                   == (edge["source"], edge["target"], edge["binding"])
                   for row in retained_edges):
                raise EditorRefusal(
                    "EDGE_ALREADY_EXISTS", "restored semantic edge already exists", path=path)
            working["edges"].append(edge)

        result = _finalize_semantic_mutation(
            working, forward=forward, inverse=opposite, registry=self.__registry)
        if (result.content_address != self.__target_content
                or result.graph_address != self.__target_graph):
            raise EditorRefusal(
                "REPLAY_DIVERGED", "receipt invocation did not reproduce its bound target")
        return result

    def __copy__(self):
        raise TypeError("receipt restore invocations cannot be copied")

    def __deepcopy__(self, _memo):
        raise TypeError("receipt restore invocations cannot be copied")

    def __reduce_ex__(self, _protocol):
        raise TypeError("receipt restore invocations cannot be serialized")

    def __repr__(self) -> str:
        return "<one-shot receipt restore invocation>"


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(child) for child in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise EditorRefusal("REQUEST_SCHEMA_INVALID", "request must contain closed JSON")


def _closed(command: Mapping[str, Any], kind: str, keys: set[str], index: int) -> None:
    if command.get("command") != kind or set(command) != keys | {"command"}:
        raise EditorRefusal(
            "REQUEST_SCHEMA_INVALID", f"{kind} has missing or unknown fields",
            path=f"$.commands[{index}]",
        )


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_IDENTIFIER_BYTES:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "identifier is absent or exceeds its bound", path=path)
    return value


def _catalogue_identities() -> frozenset[tuple[str, int]]:
    from app.editor.v2_catalogue import CATALOGUE_DOCUMENT

    return frozenset(
        (row["component_id"], row["component_version"])
        for group in CATALOGUE_DOCUMENT["groups"] for row in group["components"]
    )


def _catalogue_exclusions() -> dict[tuple[str, int], str]:
    from app.editor.v2_catalogue import CATALOGUE_DOCUMENT

    return {
        (row["component_id"], row["component_version"]): row["reason_code"]
        for row in CATALOGUE_DOCUMENT["exclusions"]
    }


def _validate_batch(commands: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if not isinstance(commands, (list, tuple)) or not 1 <= len(commands) <= MAX_COMMANDS:
        raise EditorRefusal("EDITOR_RESOURCE_LIMIT", f"semantic batch requires 1..{MAX_COMMANDS} commands")
    try:
        plain = tuple(_plain(command) for command in commands)
        encoded = canonical_json(plain).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "semantic batch is not canonical JSON") from exc
    if len(encoded) > MAX_BATCH_BYTES:
        raise EditorRefusal("EDITOR_RESOURCE_LIMIT", "semantic batch byte limit exceeded")
    if not all(isinstance(command, dict) for command in plain):
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "every command must be an object")
    return plain


def _node(document: Mapping[str, Any], node_id: str, path: str) -> dict[str, Any]:
    for row in document.get("nodes", ()):  # the base document is validated below
        if row.get("node_id") == node_id:
            return row
    raise EditorRefusal("NODE_NOT_FOUND", "node not found", path=path)


def _component(registry: Any, node: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = node["component"]
    return registry.v2_components[(ref["component_id"], ref["component_version"])]


def _port(registry: Any, document: Mapping[str, Any], endpoint: Mapping[str, Any], direction: str, path: str) -> Mapping[str, Any]:
    if not isinstance(endpoint, Mapping) or set(endpoint) != {"node_id", "port_id"}:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "endpoint must contain node_id and port_id", path=path)
    node = _node(document, _identifier(endpoint.get("node_id"), path + ".node_id"), path + ".node_id")
    port_id = _identifier(endpoint.get("port_id"), path + ".port_id")
    matches = [row for row in _component(registry, node).get("ports", ()) if row.get("port_id") == port_id]
    if not matches:
        raise EditorRefusal("PORT_NOT_FOUND", "port not found", path=path + ".port_id")
    if matches[0].get("direction") != direction:
        raise EditorRefusal("PORT_DIRECTION_INVALID", f"port must be {direction}", path=path + ".port_id")
    return matches[0]


def _edge_id(source: Mapping[str, Any], target: Mapping[str, Any], binding: Mapping[str, Any]) -> str:
    digest = content_address({"source": source, "target": target, "binding": binding}).split(":", 1)[1]
    return "edge." + digest


def _restore_edge_command(
    edge: Mapping[str, Any], graph_output_descriptor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "command": "restore_edge_from_receipt",
        "mode": "insert_or_replace_graph_output",
        "edge": copy.deepcopy(_plain(edge)),
        "graph_output_descriptor": (
            None if graph_output_descriptor is None
            else copy.deepcopy(_plain(graph_output_descriptor))
        ),
    }


def _verify_receipt_restore_context(
    receipt: Mapping[str, Any], document: Mapping[str, Any],
    commands: Sequence[Mapping[str, Any]], *,
    opposite_commands: Sequence[Mapping[str, Any]], registry: Any,
    owner_id: str, project_id: str, graph_identifier: str,
    current_version: int | None, base_revision: int, requested_intent: str,
    target_content: str, target_graph: str,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Authenticate one exact restore context without applying any command."""
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for

    verified = validate_semantic_receipt(receipt)
    plain_commands = _validate_batch(commands)
    plain_opposite = _validate_batch(opposite_commands)
    if list(plain_commands) == verified["inverse_commands"]:
        valid_pair = list(plain_opposite) == verified["forward_commands"]
    elif list(plain_commands) == verified["forward_commands"]:
        valid_pair = list(plain_opposite) == verified["inverse_commands"]
    else:
        valid_pair = False
    expected_candidate = 1 if current_version is None else current_version + 1
    if (not valid_pair
            or verified["owner_id"] != owner_id
            or verified["project_id"] != project_id
            or verified["graph_identifier"] != graph_identifier
            or verified["registry_snapshot_address"] != registry.registry_snapshot_address
            or verified["current_version"] != current_version
            or verified["next_candidate_version"] != expected_candidate):
        raise EditorRefusal(
            "RECEIPT_CAPABILITY_INVALID",
            "receipt restore invocation is absent, consumed, or foreign",
        )
    if requested_intent == "UNDO":
        valid_state = (verified["intent"] in {"EDIT", "REDO"}
                       and verified["commit_state"] == "DRAFT_COMMITTED")
        expected_revision = verified["result_semantic_revision"]
        expected_content = verified["result_content_address"]
        expected_graph = verified["result_graph_address"]
        sealed_target_content = verified["base_content_address"]
        sealed_target_graph = verified["base_graph_address"]
    elif requested_intent == "REDO":
        valid_state = (verified["intent"] == "UNDO"
                       and verified["commit_state"] == "DRAFT_COMMITTED")
        expected_revision = verified["result_semantic_revision"]
        expected_content = verified["result_content_address"]
        expected_graph = verified["result_graph_address"]
        sealed_target_content = verified["base_content_address"]
        sealed_target_graph = verified["base_graph_address"]
    elif requested_intent == "REPLAY":
        valid_state = True
        expected_revision = base_revision
        expected_content = verified["base_content_address"]
        expected_graph = verified["base_graph_address"]
        sealed_target_content = verified["result_content_address"]
        sealed_target_graph = verified["result_graph_address"]
    else:
        valid_state = False
        expected_revision = -1
        expected_content = expected_graph = ""
        sealed_target_content = sealed_target_graph = ""
    canonical = _plain(canonical_document(document, registry))
    base_content = content_address_for(canonical, registry)
    base_graph = graph_address_for(canonical, registry)
    if (not valid_state
            or base_revision != expected_revision
            or base_content != expected_content
            or base_graph != expected_graph
            or target_content != sealed_target_content
            or target_graph != sealed_target_graph):
        raise EditorRefusal(
            "RECEIPT_CAPABILITY_INVALID",
            "receipt restore invocation is absent, consumed, or foreign",
        )
    return canonical, plain_commands, plain_opposite


def _new_receipt_restore_invocation(
    receipt: Mapping[str, Any], document: Mapping[str, Any],
    commands: Sequence[Mapping[str, Any]], *,
    opposite_commands: Sequence[Mapping[str, Any]], registry: Any,
    catalogue_identities: frozenset[tuple[str, int]] | None,
    owner_id: str, project_id: str, graph_identifier: str,
    current_version: int | None, base_revision: int, requested_intent: str,
    target_content: str, target_graph: str,
) -> _ReceiptRestoreInvocation:
    return _ReceiptRestoreInvocation(
        receipt, document, commands,
        opposite_commands=opposite_commands,
        registry=registry,
        catalogue_identities=catalogue_identities,
        owner_id=owner_id,
        project_id=project_id,
        graph_identifier=graph_identifier,
        current_version=current_version,
        base_revision=base_revision,
        requested_intent=requested_intent,
        target_content=target_content,
        target_graph=target_graph,
    )


def _semantic_error(violation: Any) -> EditorRefusal:
    code = getattr(violation, "code", "V2")
    mapped = {
        "V2_CARDINALITY": "CARDINALITY_INVALID", "V2_ASSEMBLY": "BINDING_INVALID",
        "V2_BINDING": "BINDING_INVALID", "V2_CYCLE": "CYCLE_INVALID",
        "V2_TYPE": "PORT_CONTRACT_MISMATCH", "V2_SHAPE": "PORT_CONTRACT_MISMATCH",
        "V2_FLOW": "PORT_CONTRACT_MISMATCH", "V2_DIRECTION": "PORT_DIRECTION_INVALID",
        "V2_ENDPOINT": "PORT_NOT_FOUND", "V2_BOUNDARY": "OUTPUT_BINDING_INVALID",
    }.get(code, "SEMANTIC_INVALID")
    return EditorRefusal(mapped, getattr(violation, "message", "v2 document refused"),
                         path=getattr(violation, "path", "$"))


def _binding(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("kind") not in {"single", "ordered", "keyed", "unordered"}:
        raise EditorRefusal("BINDING_INVALID", "binding kind is invalid", path=path)
    permitted = {"kind"}
    if value["kind"] == "ordered":
        permitted.add("position")
        if isinstance(value.get("position"), bool) or not isinstance(value.get("position"), int) or value["position"] < 0:
            raise EditorRefusal("BINDING_INVALID", "ordered binding needs a nonnegative position", path=path)
    elif value["kind"] == "keyed":
        permitted.add("key")
        _identifier(value.get("key"), path + ".key")
    if set(value) != permitted:
        raise EditorRefusal("BINDING_INVALID", "binding has unknown or missing fields", path=path)
    return _plain(value)


def _apply_public_semantic_command(
    working: dict[str, Any], command: Mapping[str, Any], *, index: int,
    registry: Any, catalogue_identities: frozenset[tuple[str, int]],
) -> list[dict[str, Any]]:
    """Apply one public command to an isolated working document."""
    kind = command.get("command")
    path = f"$.commands[{index}]"
    if kind == "add_node":
            _closed(command, kind, {"node_id", "component_id", "component_version", "parameters"}, index)
            node_id = _identifier(command["node_id"], path + ".node_id")
            if any(row["node_id"] == node_id for row in working["nodes"]):
                raise EditorRefusal("NODE_ALREADY_EXISTS", "node already exists", path=path + ".node_id")
            if isinstance(command["component_version"], bool) or not isinstance(command["component_version"], int):
                raise EditorRefusal("REQUEST_SCHEMA_INVALID", "component_version must be an integer", path=path)
            ref = (_identifier(command["component_id"], path + ".component_id"), command["component_version"])
            if ref not in catalogue_identities or ref not in registry.v2_components:
                reason = _catalogue_exclusions().get(ref, "V0_COMPONENT_UNKNOWN") \
                    if catalogue_identities == _catalogue_identities() else "V0_COMPONENT_UNKNOWN"
                raise EditorRefusal(
                    "COMPONENT_NOT_IN_V0_CATALOGUE",
                    f"component is not in the accepted V0 catalogue: {reason}", path=path)
            if not isinstance(command["parameters"], Mapping):
                raise EditorRefusal("PARAMETER_INVALID", "parameters must be an object", path=path + ".parameters")
            declared = registry.v2_components[ref].get("parameters", {})
            if set(command["parameters"]) - set(declared):
                raise EditorRefusal("PARAMETER_INVALID", "parameter is not declared by the component", path=path + ".parameters")
            working["nodes"].append({
                "node_id": node_id,
                "component": {"component_id": ref[0], "component_version": ref[1]},
                "parameters": copy.deepcopy(command["parameters"]),
            })
            return [{"command": "remove_node", "node_id": node_id}]
    if kind == "remove_node":
            _closed(command, kind, {"node_id"}, index)
            node_id = _identifier(command["node_id"], path + ".node_id")
            removed = copy.deepcopy(_node(working, node_id, path + ".node_id"))
            incident = [copy.deepcopy(edge) for edge in working["edges"]
                        if edge["source"].get("node_id") == node_id or edge["target"].get("node_id") == node_id]
            output_by_id = {row["port_id"]: copy.deepcopy(row) for row in working["graph_outputs"]}
            working["nodes"] = [row for row in working["nodes"] if row["node_id"] != node_id]
            working["edges"] = [edge for edge in working["edges"] if edge not in incident]
            removed_outputs = [edge for edge in incident if edge["target"]["scope"] == "graph_output"]
            removed_output_ids = {edge["target"]["port_id"] for edge in removed_outputs}
            working["graph_outputs"] = [row for row in working["graph_outputs"] if row["port_id"] not in removed_output_ids]
            local_inverse = [{
                "command": "add_node", "node_id": removed["node_id"],
                "component_id": removed["component"]["component_id"],
                "component_version": removed["component"]["component_version"],
                "parameters": removed["parameters"],
            }]
            for edge in sorted((edge for edge in incident if edge["target"]["scope"] == "node"), key=lambda row: row["edge_id"]):
                local_inverse.append(_restore_edge_command(edge))
            for edge in sorted(removed_outputs, key=lambda row: row["target"]["port_id"]):
                descriptor = output_by_id[edge["target"]["port_id"]]
                local_inverse.append(_restore_edge_command(edge, descriptor))
            return local_inverse
    if kind in {"connect", "disconnect"}:
            _closed(command, kind, {"source", "target", "binding"}, index)
            _port(registry, working, command["source"], "output", path + ".source")
            _port(registry, working, command["target"], "input", path + ".target")
            binding = _binding(command["binding"], path + ".binding")
            source = {"scope": "node", **_plain(command["source"])}
            target = {"scope": "node", **_plain(command["target"])}
            identity = (source, target, binding)
            matches = [edge for edge in working["edges"]
                       if (edge["source"], edge["target"], edge["binding"]) == identity]
            inverse_kind = "disconnect" if kind == "connect" else "connect"
            if kind == "connect":
                if matches:
                    raise EditorRefusal("EDGE_ALREADY_EXISTS", "edge already exists", path=path)
                working["edges"].append({"edge_id": _edge_id(source, target, binding),
                                         "source": source, "target": target, "binding": binding})
            else:
                if len(matches) != 1:
                    raise EditorRefusal("EDGE_NOT_FOUND", "edge not found", path=path)
                working["edges"].remove(matches[0])
            return (
                [{"command": inverse_kind, "source": command["source"],
                  "target": command["target"], "binding": binding}]
                if kind == "connect" else [_restore_edge_command(matches[0])]
            )
    if kind in {"set_parameter", "clear_parameter"}:
            keys = {"node_id", "parameter_id", "value"} if kind == "set_parameter" else {"node_id", "parameter_id"}
            _closed(command, kind, keys, index)
            node = _node(working, _identifier(command["node_id"], path + ".node_id"), path)
            parameter_id = _identifier(command["parameter_id"], path + ".parameter_id")
            parameter_descriptors = _component(registry, node).get("parameters", {})
            if parameter_id not in parameter_descriptors:
                raise EditorRefusal("PARAMETER_INVALID", "parameter is not declared", path=path + ".parameter_id")
            if kind == "set_parameter" and isinstance(command.get("value"), Mapping) \
                    and set(command["value"]) & {"unit", "units"}:
                expected_unit = parameter_descriptors[parameter_id].get("units")
                raise EditorRefusal(
                    "UNIT_CONTRACT_REFUSED",
                    f"parameter uses registry-owned unit {expected_unit!r} and accepts its canonical value only",
                    path=path + ".value")
            existed = parameter_id in node["parameters"]
            prior = copy.deepcopy(node["parameters"].get(parameter_id))
            if kind == "set_parameter":
                node["parameters"][parameter_id] = copy.deepcopy(command["value"])
            elif not existed:
                raise EditorRefusal("PARAMETER_INVALID", "parameter has no explicit value to clear", path=path)
            else:
                del node["parameters"][parameter_id]
            return ([{"command": "set_parameter", "node_id": node["node_id"],
                      "parameter_id": parameter_id, "value": prior}]
                    if existed else [{"command": "clear_parameter", "node_id": node["node_id"],
                                      "parameter_id": parameter_id}])
    if kind in {"bind_output", "unbind_output"}:
            keys = {"output_id", "source", "semantic_role"} if kind == "bind_output" else {"output_id"}
            _closed(command, kind, keys, index)
            output_id = _identifier(command["output_id"], path + ".output_id")
            prior_descriptor = next((copy.deepcopy(row) for row in working["graph_outputs"] if row["port_id"] == output_id), None)
            prior_edge = next((copy.deepcopy(edge) for edge in working["edges"]
                              if edge["target"] == {"scope": "graph_output", "port_id": output_id}), None)
            working["graph_outputs"] = [row for row in working["graph_outputs"] if row["port_id"] != output_id]
            working["edges"] = [edge for edge in working["edges"]
                                if edge["target"] != {"scope": "graph_output", "port_id": output_id}]
            if kind == "bind_output":
                source_port = _port(registry, working, command["source"], "output", path + ".source")
                semantic_role = _identifier(command["semantic_role"], path + ".semantic_role")
                descriptor = {key: copy.deepcopy(source_port[key]) for key in
                              ("direction", "semantic_flow", "type_ref", "shape")}
                descriptor.update({"port_id": output_id, "semantic_role": semantic_role})
                source = {"scope": "node", **_plain(command["source"])}
                target = {"scope": "graph_output", "port_id": output_id}
                binding = {"kind": "single"}
                working["graph_outputs"].append(descriptor)
                working["edges"].append({"edge_id": _edge_id(source, target, binding),
                                         "source": source, "target": target, "binding": binding})
            elif prior_edge is None:
                raise EditorRefusal("OUTPUT_BINDING_INVALID", "output is not bound", path=path)
            if prior_edge is None:
                return [{"command": "unbind_output", "output_id": output_id}]
            return [_restore_edge_command(prior_edge, prior_descriptor)]
    if kind == "restore_edge_from_receipt":
        raise EditorRefusal(
            "REQUEST_SCHEMA_INVALID",
            "private edge restoration requires a verified semantic receipt",
            path=path,
        )
    raise EditorRefusal("REQUEST_SCHEMA_INVALID", "unknown semantic command", path=path + ".command")


def _finalize_semantic_mutation(
    working: Mapping[str, Any], *, forward: Sequence[Mapping[str, Any]],
    inverse: Sequence[Mapping[str, Any]], registry: Any,
) -> SemanticMutation:
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for, validate_document
    from app.ir.resolve import ResolutionError, resolve_v2

    if len(inverse) > MAX_COMMANDS:
        raise EditorRefusal(
            "EDITOR_RESOURCE_LIMIT",
            "canonical inverse exceeds the durable undo command limit",
            path="$.commands",
        )
    if inverse:
        _validate_batch(inverse)
    violations = validate_document(working, registry)
    if violations:
        raise _semantic_error(violations[0])
    try:
        canonical = _plain(canonical_document(working, registry))
        resolved = resolve_v2(canonical, registry)
        resolved_address = resolved.resolved_graph_address
    except ResolutionError as exc:
        code = "DATA_REQUIREMENT_REFUSED" if "requirement" in str(exc).lower() else (
            "EDITOR_RESOURCE_LIMIT" if getattr(exc, "clause", "") == "V2_LIMIT" else "SEMANTIC_INVALID")
        raise EditorRefusal(code, str(exc), path=getattr(exc, "path", "$")) from exc
    return SemanticMutation(
        document=canonical,
        forward_commands=tuple(_plain(command) for command in forward),
        inverse_commands=tuple(_plain(command) for command in inverse),
        content_address=content_address_for(canonical, registry),
        graph_address=graph_address_for(canonical, registry),
        resolved_address=resolved_address,
    )


def apply_semantic_commands(
    document: Mapping[str, Any], commands: Sequence[Mapping[str, Any]], *, registry: Any,
    catalogue_identities: frozenset[tuple[str, int]] | None = None,
) -> SemanticMutation:
    """Apply the closed public command grammar to one isolated v2 document."""
    from app.ir.formats.v2 import canonical_document, validate_document

    if not isinstance(document, Mapping) or document.get("format_version") != 2:
        raise EditorRefusal("V1_LEGACY_ONLY", "the v2 editor never maps legacy documents")
    violations = validate_document(document, registry)
    if violations:
        raise _semantic_error(violations[0])
    working = copy.deepcopy(_plain(canonical_document(document, registry)))
    forward = _validate_batch(commands)
    allowed = _catalogue_identities() if catalogue_identities is None else catalogue_identities
    inverse: list[dict[str, Any]] = []
    for index, command in enumerate(forward):
        local_inverse = _apply_public_semantic_command(
            working, command, index=index, registry=registry,
            catalogue_identities=allowed)
        inverse = local_inverse + inverse
    return _finalize_semantic_mutation(
        working, forward=forward, inverse=inverse, registry=registry)


def empty_presentation() -> dict[str, Any]:
    return {"schema": "strategy-os-v2-presentation/1", "positions": {}, "groups": {},
            "viewport": None, "selection": {"nodes": [], "edges": [], "outputs": []}}


def _finite(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "coordinate must be finite", path=path)
    result = float(value)
    if positive and result <= 0:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "value must be positive", path=path)
    return result


def apply_presentation_commands(
    document: Mapping[str, Any], commands: Sequence[Mapping[str, Any]], *, semantic_ids: Mapping[str, frozenset[str]],
) -> PresentationMutation:
    working = copy.deepcopy(_plain(document))
    if set(working) != {"schema", "positions", "groups", "viewport", "selection"} \
            or working.get("schema") != "strategy-os-v2-presentation/1":
        raise EditorRefusal("PRESENTATION_INVALID", "presentation document is not canonical")
    forward = _validate_batch(commands)
    inverse: list[dict[str, Any]] = []
    for index, command in enumerate(forward):
        kind = command.get("command")
        path = f"$.commands[{index}]"
        if kind in {"set_position", "clear_position"}:
            _closed(command, kind, {"node_id", "x", "y"} if kind == "set_position" else {"node_id"}, index)
            node_id = _identifier(command["node_id"], path + ".node_id")
            if kind == "set_position" and node_id not in semantic_ids["nodes"]:
                raise EditorRefusal("PRESENTATION_REFERENCE_INVALID", "semantic node not found", path=path)
            prior = copy.deepcopy(working["positions"].get(node_id))
            if kind == "set_position":
                working["positions"][node_id] = {"x": _finite(command["x"], path + ".x"),
                                                  "y": _finite(command["y"], path + ".y")}
            elif prior is None:
                raise EditorRefusal("PRESENTATION_REFERENCE_INVALID", "position not found", path=path)
            else:
                del working["positions"][node_id]
            local = ([{"command": "set_position", "node_id": node_id, **prior}]
                     if prior is not None else [{"command": "clear_position", "node_id": node_id}])
        elif kind in {"put_group", "remove_group"}:
            keys = {"group_id", "x", "y", "width", "height", "members"} if kind == "put_group" else {"group_id"}
            _closed(command, kind, keys, index)
            group_id = _identifier(command["group_id"], path + ".group_id")
            prior = copy.deepcopy(working["groups"].get(group_id))
            if kind == "put_group":
                members = command["members"]
                if not isinstance(members, list) or len(members) > MAX_PRESENTATION_ITEMS \
                        or not all(isinstance(value, str) for value in members) \
                        or len(set(members)) != len(members) or not set(members) <= semantic_ids["nodes"]:
                    raise EditorRefusal("PRESENTATION_REFERENCE_INVALID", "group members are invalid", path=path)
                working["groups"][group_id] = {
                    "x": _finite(command["x"], path + ".x"), "y": _finite(command["y"], path + ".y"),
                    "width": _finite(command["width"], path + ".width", positive=True),
                    "height": _finite(command["height"], path + ".height", positive=True),
                    "members": sorted(members),
                }
            elif prior is None:
                raise EditorRefusal("PRESENTATION_REFERENCE_INVALID", "group not found", path=path)
            else:
                del working["groups"][group_id]
            local = ([{"command": "put_group", "group_id": group_id, **prior}]
                     if prior is not None else [{"command": "remove_group", "group_id": group_id}])
        elif kind == "set_viewport":
            _closed(command, kind, {"x", "y", "zoom"}, index)
            prior = copy.deepcopy(working["viewport"])
            working["viewport"] = {"x": _finite(command["x"], path + ".x"),
                                   "y": _finite(command["y"], path + ".y"),
                                   "zoom": _finite(command["zoom"], path + ".zoom", positive=True)}
            local = ([{"command": "set_viewport", **prior}] if prior is not None
                     else [{"command": "clear_viewport"}])
        elif kind == "clear_viewport":
            _closed(command, kind, set(), index)
            prior = copy.deepcopy(working["viewport"])
            if prior is None:
                raise EditorRefusal("PRESENTATION_INVALID", "viewport is already empty", path=path)
            working["viewport"] = None
            local = [{"command": "set_viewport", **prior}]
        elif kind in {"set_selection", "clear_selection"}:
            _closed(command, kind, {"nodes", "edges", "outputs"} if kind == "set_selection" else set(), index)
            prior = copy.deepcopy(working["selection"])
            if kind == "set_selection":
                selected: dict[str, list[str]] = {}
                for key in ("nodes", "edges", "outputs"):
                    values = command[key]
                    if not isinstance(values, list) or len(values) > MAX_PRESENTATION_ITEMS \
                            or not all(isinstance(value, str) for value in values) \
                            or len(set(values)) != len(values) or not set(values) <= semantic_ids[key]:
                        raise EditorRefusal("PRESENTATION_REFERENCE_INVALID", "selection is invalid", path=path + "." + key)
                    selected[key] = sorted(values)
                working["selection"] = selected
            else:
                working["selection"] = {"nodes": [], "edges": [], "outputs": []}
            local = [{"command": "set_selection", **prior}]
        else:
            raise EditorRefusal("REQUEST_SCHEMA_INVALID", "unknown presentation command", path=path)
        inverse = local + inverse
    if sum(map(len, (working["positions"], working["groups"]))) > MAX_PRESENTATION_ITEMS:
        raise EditorRefusal("EDITOR_RESOURCE_LIMIT", "presentation item limit exceeded")
    canonical = json.loads(canonical_json(working))
    return PresentationMutation(canonical, forward, tuple(inverse), content_address(canonical))


def semantic_ids(document: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    return {
        "nodes": frozenset(row["node_id"] for row in document["nodes"]),
        "edges": frozenset(row["edge_id"] for row in document["edges"]),
        "outputs": frozenset(row["port_id"] for row in document["graph_outputs"]),
    }


def receipt_address(receipt: Mapping[str, Any]) -> str:
    body = dict(_plain(receipt))
    supplied = body.pop("receipt_address", None)
    derived = content_address(body)
    if supplied is None or supplied != derived:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt address does not match its bytes")
    return derived


def seal_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(_plain(receipt))
    body.pop("receipt_address", None)
    result = {**body, "receipt_address": content_address(body)}
    if len(canonical_json(result).encode("utf-8")) > MAX_RECEIPT_BYTES:
        raise EditorRefusal("EDITOR_RESOURCE_LIMIT", "receipt byte limit exceeded")
    return result


def _semantic_receipt_key() -> bytes:
    from app.core.config import get_settings

    secret = get_settings().event_cursor_secret
    if not isinstance(secret, str) or len(secret.strip().encode("utf-8")) < 32:
        raise EditorRefusal(
            "RECEIPT_SEAL_UNAVAILABLE",
            "semantic receipt sealing requires the deployment event cursor secret",
        )
    return hmac.new(secret.encode("utf-8"), _RECEIPT_KEY_DOMAIN, hashlib.sha256).digest()


def _semantic_server_seal(unsigned_body: Mapping[str, Any]) -> str:
    payload = _RECEIPT_MAC_DOMAIN + canonical_json(_plain(unsigned_body)).encode("utf-8")
    return hmac.new(_semantic_receipt_key(), payload, hashlib.sha256).hexdigest()


def seal_semantic_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(_plain(receipt))
    unsigned.pop("receipt_address", None)
    unsigned.pop("server_seal", None)
    if unsigned.get("schema") != "strategy-os-v2-semantic-receipt/2" \
            or unsigned.get("receipt_class") != "SEALED_EDITOR_INVERSE":
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "semantic receipt class is invalid")
    body = {
        **unsigned,
        "server_seal": {
            "schema": "strategy-os-v2-semantic-receipt-server-seal/1",
            "algorithm": "hmac-sha256",
            "value": _semantic_server_seal(unsigned),
        },
    }
    result = {**body, "receipt_address": content_address(body)}
    if len(canonical_json(result).encode("utf-8")) > MAX_RECEIPT_BYTES:
        raise EditorRefusal("EDITOR_RESOURCE_LIMIT", "receipt byte limit exceeded")
    return result


def _semantic_server_seal_shape(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    seal = receipt.get("server_seal")
    if not isinstance(seal, Mapping) or set(seal) != {"schema", "algorithm", "value"} \
            or seal.get("schema") != "strategy-os-v2-semantic-receipt-server-seal/1" \
            or seal.get("algorithm") != "hmac-sha256" \
            or not isinstance(seal.get("value"), str) \
            or len(seal["value"]) != 64 \
            or any(character not in "0123456789abcdef" for character in seal["value"]):
        raise EditorRefusal("RECEIPT_SEAL_INVALID", "semantic receipt server seal is invalid")
    return seal


def _verify_semantic_server_seal(receipt: Mapping[str, Any]) -> None:
    seal = _semantic_server_seal_shape(receipt)
    unsigned = dict(_plain(receipt))
    unsigned.pop("receipt_address", None)
    unsigned.pop("server_seal", None)
    expected = _semantic_server_seal(unsigned)
    if not hmac.compare_digest(seal["value"], expected):
        raise EditorRefusal("RECEIPT_SEAL_INVALID", "semantic receipt server seal is invalid")


NONAUTHORITY = {
    "research_admission": False, "deployment_authority": False,
    "execution_authority": False, "provider_capability": False, "money_authority": False,
}


SEMANTIC_RECEIPT_BODY_KEYS = frozenset({
    "schema", "owner_id", "project_id", "graph_identifier", "format_version", "intent",
    "source_receipt_address", "registry_snapshot_address", "base_semantic_revision",
    "result_semantic_revision", "base_content_address", "result_content_address",
    "base_graph_address", "result_graph_address", "current_version",
    "next_candidate_version", "forward_commands", "inverse_commands",
    "resolved_topology_address", "commit_state", "nonauthority", "receipt_class",
    "server_seal",
})
PRESENTATION_RECEIPT_BODY_KEYS = frozenset({
    "schema", "owner_id", "project_id", "graph_identifier", "format_version", "intent",
    "source_receipt_address", "semantic_revision", "semantic_content_address",
    "base_presentation_revision", "result_presentation_revision",
    "base_presentation_address", "result_presentation_address", "forward_commands",
    "inverse_commands", "commit_state", "identity_class", "nonauthority",
})


def _require_closed_receipt(
    value: Mapping[str, Any], *, schema: str, body_keys: frozenset[str], intents: frozenset[str],
) -> dict[str, Any]:
    try:
        receipt = _plain(value)
    except EditorRefusal as exc:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt is not closed JSON") from exc
    try:
        if len(canonical_json(receipt).encode("utf-8")) > MAX_RECEIPT_BYTES:
            raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt byte limit exceeded")
    except (TypeError, ValueError, OverflowError) as exc:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt is not canonical JSON") from exc
    if not isinstance(receipt, dict) or set(receipt) != set(body_keys) | {"receipt_address"} \
            or receipt.get("schema") != schema or receipt.get("format_version") != 2 \
            or receipt.get("intent") not in intents:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt schema is open or incomplete")
    if schema == "strategy-os-v2-semantic-receipt/2":
        if receipt.get("receipt_class") != "SEALED_EDITOR_INVERSE":
            raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "semantic receipt class is invalid")
        _semantic_server_seal_shape(receipt)
    for name in ("owner_id", "project_id", "graph_identifier"):
        value = receipt.get(name)
        if not isinstance(value, str) or not value \
                or len(value.encode("utf-8")) > MAX_IDENTIFIER_BYTES:
            raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt lineage identifier is invalid")
    for name in ("base_semantic_revision", "result_semantic_revision") \
            if schema == "strategy-os-v2-semantic-receipt/2" \
            else ("semantic_revision", "base_presentation_revision", "result_presentation_revision"):
        value = receipt.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt revision is invalid", path=f"$.{name}")
    revision_prefix = "semantic" if schema == "strategy-os-v2-semantic-receipt/2" else "presentation"
    if receipt[f"result_{revision_prefix}_revision"] != receipt[f"base_{revision_prefix}_revision"] + 1:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt revision transition is invalid")
    if schema == "strategy-os-v2-semantic-receipt/2":
        current = receipt.get("current_version")
        candidate = receipt.get("next_candidate_version")
        if ((current is not None and (isinstance(current, bool) or not isinstance(current, int)
                                      or current < 1))
                or isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 1
                or candidate != (1 if current is None else current + 1)):
            raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt version lineage is invalid")
    address_names = (
        ("registry_snapshot_address", "base_content_address", "result_content_address",
         "base_graph_address", "result_graph_address", "resolved_topology_address")
        if schema == "strategy-os-v2-semantic-receipt/2"
        else ("semantic_content_address", "base_presentation_address", "result_presentation_address")
    )
    from app.ir.schema import is_content_address
    if any(not is_content_address(receipt.get(name)) for name in address_names):
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt contains a malformed address")
    source = receipt.get("source_receipt_address")
    if (receipt["intent"] == "EDIT" and source is not None) or (
            receipt["intent"] != "EDIT" and not is_content_address(source)):
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt lineage is invalid")
    for name in ("forward_commands", "inverse_commands"):
        try:
            _validate_batch(receipt.get(name))
        except EditorRefusal as exc:
            raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt commands are invalid") from exc
    if receipt.get("nonauthority") != NONAUTHORITY:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "receipt nonauthority flags are invalid")
    receipt_address(receipt)
    if schema == "strategy-os-v2-semantic-receipt/2":
        _verify_semantic_server_seal(receipt)
    return receipt


def validate_semantic_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _require_closed_receipt(
        value, schema="strategy-os-v2-semantic-receipt/2",
        body_keys=SEMANTIC_RECEIPT_BODY_KEYS,
        intents=frozenset({"EDIT", "UNDO", "REDO", "REPLAY"}),
    )
    if receipt.get("commit_state") not in {"DRY_RUN_ROLLED_BACK", "DRAFT_COMMITTED"} \
            or receipt.get("receipt_class") != "SEALED_EDITOR_INVERSE":
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "semantic commit state is invalid")
    return receipt


def validate_presentation_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _require_closed_receipt(
        value, schema="strategy-os-v2-presentation-receipt/1",
        body_keys=PRESENTATION_RECEIPT_BODY_KEYS,
        intents=frozenset({"EDIT", "UNDO", "REDO", "REPLAY"}),
    )
    if receipt.get("commit_state") not in {"DRY_RUN_ROLLED_BACK", "PRESENTATION_COMMITTED"} \
            or receipt.get("identity_class") != "NOT_EXECUTABLE_IDENTITY":
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "presentation receipt state is invalid")
    return receipt
