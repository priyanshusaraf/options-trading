"""Immutable, registry-bound Phase 4 data-requirement plans.

This module deliberately consumes resolved facts only.  It does not inspect
component descriptors, choose a provider, or treat missing declarations as an
absence of data requirements.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import canonical_json, content_address
from app.ir.resolve import resolved_v2_graph_address
from app.ir.registry import _DATA_ID, _normalize_data_declaration, _validate_data_direct
from app.ir.schema import is_content_address


class DataRequirementRefusal(ValueError):
    """A closed Phase 4 declaration/binding refusal."""


@dataclass(frozen=True)
class DataRequirementPlan:
    authored_ir_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    registry_snapshot_address: str
    declaration_addresses: tuple[str, ...]
    requirements: tuple[Mapping[str, Any], ...]
    parameter_binding_provenance: tuple[Mapping[str, Any], ...]
    plan_address: str


def compile_data_requirement_plan(resolved_graph: Any, *, authored_ir_address: str | None = None,
                                  registry: Any = None, input_bindings: Any = None) -> DataRequirementPlan:
    """Compile the sole deterministic plan from a fully resolved v2 graph."""
    snapshot = getattr(resolved_graph, "registry_snapshot_address", None)
    graph_address = getattr(resolved_graph, "resolved_graph_address", None)
    closure = getattr(resolved_graph, "implementation_closure_address", None)
    if not all(isinstance(value, str) and is_content_address(value) for value in (snapshot, graph_address, closure)):
        raise DataRequirementRefusal("resolved graph lacks Phase 4 registry identity")
    snapshot_payload = getattr(resolved_graph, "registry_snapshot_payload", None)
    declaration_closure = getattr(resolved_graph, "data_requirement_declaration_closure", None)
    _verify_registry_closure(snapshot, snapshot_payload, declaration_closure)
    if resolved_v2_graph_address(
        resolved_graph.nodes, snapshot, closure, snapshot_payload, declaration_closure,
    ) != graph_address:
        raise DataRequirementRefusal("resolved graph identity does not match its registry-bound facts")
    declarations = _declarations_by_component(declaration_closure, snapshot_payload)
    dynamic = {node.component for node in resolved_graph.nodes
               if declarations.get(node.component, {}).get("schema") == "first-party-node-contract/2"}
    if dynamic:
        from app.ir.registry import PlatformRegistry
        from app.ir.first_party.analytical_v2.contracts import validate_input_bindings
        try:
            if (type(registry) is not PlatformRegistry
                    or registry.registry_snapshot_address != snapshot
                    or _plain(registry.registry_snapshot_payload) != _plain(snapshot_payload)):
                raise ValueError("binding compilation requires the exact source registry")
            registry.validate_contract_bindings()
            validate_input_bindings(input_bindings)
        except (TypeError, ValueError, AttributeError) as exc:
            raise DataRequirementRefusal("explicit valid contract binding context/registry is required") from exc
    elif input_bindings is not None:
        raise DataRequirementRefusal("input binding context is unused by this graph")
    records: list[dict[str, Any]] = []
    provenance: list[Mapping[str, Any]] = []
    declaration_addresses: list[str] = []
    node_paths: dict[str, tuple[str, ...]] = {}
    consumed_inputs: set[str] = set()
    for node in resolved_graph.nodes:
        if node.declaration_address is None or (node.bound_requirements is None and node.component not in dynamic) or node.registry_snapshot_address != snapshot:
            raise DataRequirementRefusal(f"node {node.node_id!r} has missing, stale, or unbound data declaration")
        declaration = declarations.get(node.component)
        if not isinstance(node.declaration_address, str) or not is_content_address(node.declaration_address) or declaration is None or content_address(_plain(declaration)) != node.declaration_address:
            raise DataRequirementRefusal(f"node {node.node_id!r} declaration does not belong to its exact leaf")
        declaration_addresses.append(node.declaration_address)
        if not isinstance(node.authored_node_id, str) or not node.authored_node_id or not isinstance(node.lowered_path, tuple) or not node.lowered_path or node.lowered_path[0] != node.authored_node_id:
            raise DataRequirementRefusal(f"node {node.node_id!r} lacks structured lowering attribution")
        existing_path = node_paths.setdefault(node.node_id, node.lowered_path)
        if existing_path != node.lowered_path:
            raise DataRequirementRefusal(f"node {node.node_id!r} collides across distinct lowered paths")
        provenance_row = {"authored_node_id": node.authored_node_id, "lowered_path": node.lowered_path, "parameters": node.parameter_provenance}
        bound_rows = node.bound_requirements
        if node.component in dynamic:
            from app.ir.first_party.analytical_v2.contracts import input_binding_for_node
            try:
                registration = registry.contract_bindings[node.component]
                if (node.bound_requirements is not None
                        or node.binding_implementation_address != registration.implementation_address
                        or node.declaration_address != registration.source_contract_address):
                    raise ValueError("stored binding recipe differs from its exact registry source")
                node_inputs = input_binding_for_node(resolved_graph, node, declaration, input_bindings)
                receipt = registry.bind_node_contract(node.component, node.parameters, node_inputs)
                bound_rows = receipt.document["bound_requirements"]
                provenance_row["node_contract_binding"] = receipt.document
                consumed_inputs.update(entry["source"]["port_id"] for entry in node_inputs["ports"].values())
            except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
                raise DataRequirementRefusal(f"node {node.node_id!r} contract binding refused: {exc}") from exc
        elif getattr(node, "binding_implementation_address", None) is not None:
            raise DataRequirementRefusal("legacy node cannot carry an unregistered binding recipe")
        provenance.append(_freeze(provenance_row))
        for row in bound_rows:
            _verify_bound_row(row)
            records.append({"authored_node_id": node.authored_node_id, "lowered_path": node.lowered_path, "leaf_component": node.component, "requirement": row})
    if dynamic and consumed_inputs != set(input_bindings.document["inputs"]):
        raise DataRequirementRefusal("canonical input binding set contains unused or missing sources")
    resolved_authored = getattr(resolved_graph, "authored_ir_address", None)
    if not isinstance(resolved_authored, str) or not is_content_address(resolved_authored):
        raise DataRequirementRefusal("resolved graph lacks authored IR identity")
    if authored_ir_address is not None and authored_ir_address != resolved_authored:
        raise DataRequirementRefusal("authored IR override conflicts with resolved graph identity")
    authored_ir_address = resolved_authored
    records.sort(key=lambda item: (item["authored_node_id"], item["lowered_path"], item["leaf_component"], item["requirement"]["requirement_id"], canonical_json(_plain(item["requirement"]))))
    canonical_records = [{"authored_node_id": item["authored_node_id"], "lowered_path": list(item["lowered_path"]), "leaf_component": {"component_id": item["leaf_component"][0], "component_version": item["leaf_component"][1]}, "requirement": _plain(item["requirement"])} for item in records]
    canonical_addresses = tuple(sorted(set(declaration_addresses)))
    provenance.sort(key=lambda item: (item["authored_node_id"], item["lowered_path"], canonical_json(_plain(item["parameters"]))))
    payload = {"authored_ir_address": authored_ir_address, "resolved_graph_address": graph_address, "implementation_closure_address": closure, "registry_snapshot_address": snapshot, "declaration_addresses": list(canonical_addresses), "requirements": canonical_records, "parameter_binding_provenance": _plain(provenance)}
    return DataRequirementPlan(authored_ir_address, graph_address, closure, snapshot, canonical_addresses, tuple(MappingProxyType(record) for record in records), tuple(provenance), content_address(payload))


def verify_data_requirement_plan(plan: DataRequirementPlan, resolved_graph: Any, *,
                                 registry: Any = None, input_bindings: Any = None) -> DataRequirementPlan:
    """Reconstruct through the same compiler; rehashed stored facts are insufficient.

    The later research/cache integration owns calling this at its actual load,
    claim and reclaim boundaries. No caller receives authority from a hash alone.
    """
    if type(plan) is not DataRequirementPlan:
        raise DataRequirementRefusal("stored plan is not a canonical DataRequirementPlan")
    expected = compile_data_requirement_plan(resolved_graph, registry=registry, input_bindings=input_bindings)
    if canonical_json(_plain(vars(plan))) != canonical_json(_plain(vars(expected))):
        raise DataRequirementRefusal("stored data plan differs from reconstructed contract binding")
    return expected


def _verify_registry_closure(snapshot: str, payload: Any, closure: Any) -> None:
    if not isinstance(payload, Mapping) or content_address(_plain(payload)) != snapshot:
        raise DataRequirementRefusal("registry snapshot payload is missing, malformed, or stale")
    if not isinstance(closure, tuple):
        raise DataRequirementRefusal("registry declaration closure is missing or mutable")
    addresses = payload.get("data_requirement_declarations")
    if not isinstance(addresses, (list, tuple)):
        raise DataRequirementRefusal("registry snapshot lacks declaration address map")
    expected: dict[tuple[str, int], str] = {}
    for row in addresses:
        if not isinstance(row, Mapping) or set(row) != {"component_id", "component_version", "declaration_address"}:
            raise DataRequirementRefusal("registry snapshot declaration address map is malformed")
        component = (row["component_id"], row["component_version"])
        if not isinstance(component[0], str) or isinstance(component[1], bool) or not isinstance(component[1], int) or not isinstance(row["declaration_address"], str) or component in expected:
            raise DataRequirementRefusal("registry snapshot declaration address map is malformed")
        expected[component] = row["declaration_address"]
    actual = _declarations_by_component(closure, payload)
    if set(actual) != set(expected) or any(content_address(_plain(actual[key])) != expected[key] for key in actual):
        raise DataRequirementRefusal("registry declaration closure disagrees with its snapshot")


def _declarations_by_component(closure: tuple[Mapping[str, Any], ...], snapshot_payload: Mapping[str, Any]) -> dict[tuple[str, int], Mapping[str, Any]]:
    component_entries = snapshot_payload.get("v2_components")
    if not isinstance(component_entries, (list, tuple)):
        raise DataRequirementRefusal("registry snapshot lacks v2 component closure")
    descriptors: dict[tuple[str, int], Mapping[str, Any]] = {}
    for entry in component_entries:
        if not isinstance(entry, Mapping) or set(entry) != {"component_id", "component_version", "value"} or not isinstance(entry["value"], Mapping):
            raise DataRequirementRefusal("registry snapshot v2 component closure is malformed")
        component = (entry["component_id"], entry["component_version"])
        if not isinstance(component[0], str) or isinstance(component[1], bool) or not isinstance(component[1], int) or component in descriptors:
            raise DataRequirementRefusal("registry snapshot v2 component closure is malformed")
        descriptors[component] = entry["value"]
    declarations: dict[tuple[str, int], Mapping[str, Any]] = {}
    for entry in closure:
        if not isinstance(entry, Mapping) or set(entry) != {"component_id", "component_version", "declaration"}:
            raise DataRequirementRefusal("registry declaration closure is malformed")
        component = (entry["component_id"], entry["component_version"])
        if not isinstance(component[0], str) or isinstance(component[1], bool) or not isinstance(component[1], int) or not isinstance(entry["declaration"], Mapping) or component in declarations:
            raise DataRequirementRefusal("registry declaration closure is malformed")
        descriptor = descriptors.get(component)
        if descriptor is None or descriptor.get("compound") is not None:
            raise DataRequirementRefusal("registry declaration closure does not belong to an exact leaf")
        try:
            normalized = _normalize_data_declaration(component, entry["declaration"], descriptor)
        except (KeyError, TypeError, ValueError) as exc:
            raise DataRequirementRefusal("registry declaration closure violates the registry grammar") from exc
        if _plain(entry["declaration"]) != _plain(normalized):
            raise DataRequirementRefusal("registry declaration closure is not canonical")
        declarations[component] = entry["declaration"]
    return declarations


def _verify_bound_row(row: Any) -> None:
    fields = ("instrument", "field", "timeframe", "history", "freshness", "depth", "session", "alignment", "derived_local")
    if not isinstance(row, Mapping) or set(row) != {"requirement_id", *fields} or not isinstance(row["requirement_id"], str) or not _DATA_ID.fullmatch(row["requirement_id"]):
        raise DataRequirementRefusal("bound data requirement row is malformed")
    for field in fields:
        value = row[field]
        if isinstance(value, Mapping) and set(value) in ({"literal"}, {"parameter"}):
            raise DataRequirementRefusal("bound data requirement retains an expression")
        try:
            _validate_data_direct(field, value)
        except ValueError as exc:
            raise DataRequirementRefusal("bound data requirement has invalid direct value") from exc


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value
