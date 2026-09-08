"""Independent identity and stale-consumer oracle for session-context binding."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import hashlib

import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party import analytical
from app.ir.first_party.analytical_v2 import core_math, multi_output, recursive_state
from app.ir.first_party.analytical_v2.contracts import (
    ResolvedNodeContract,
    canonical_input_bindings,
)
from app.ir.library import REGISTRY as DEFAULT_REGISTRY
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.state_snapshots import (
    ResearchSnapshotRefusal,
    _create_research_snapshot_authority,
    create_research_checkpoint,
    restore_research_checkpoint,
)
from app.market_data.requirements import (
    DataRequirementPlan,
    DataRequirementRefusal,
    compile_data_requirement_plan,
    verify_data_requirement_plan,
)


ROOT = Path(__file__).resolve().parents[3]
CORRECTION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction"
PRE = json.loads((CORRECTION / "pre-mutation.json").read_text())
TRANSITION = json.loads((CORRECTION / "identity-transition.json").read_text())
MODULES = (core_math, recursive_state, multi_output)
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [plain(item) for item in value]
    return value


def closed(value):
    if isinstance(value, dict):
        return {key: closed(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(closed(item) for item in value)
    return value


def key_label(key) -> str:
    return f"{key[0]}@{key[1]}"


def accepted_registry() -> PlatformRegistry:
    types, components, implementations, contracts, bindings = {}, {}, {}, {}, {}
    for module in MODULES:
        for target, source in (
            (types, module.V2_TYPES),
            (components, module.V2_COMPONENTS),
            (implementations, module.V2_IMPLEMENTATIONS),
            (contracts, module.NODE_CONTRACTS),
            (bindings, module.CONTRACT_BINDINGS),
        ):
            for key, value in source.items():
                if key in target:
                    assert hashing.content_address(plain(target[key])) == hashing.content_address(plain(value))
                target[key] = value
    return PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=types, v2_components=components,
        v2_implementations=implementations, node_contracts=contracts, contract_bindings=bindings,
    )


def current_identity_records():
    records = {}
    for module in MODULES:
        for key in module.V2_COMPONENTS:
            registration = module.CONTRACT_BINDINGS[key]
            records[key_label(key)] = {
                "component_address": hashing.content_address(plain(module.V2_COMPONENTS[key])),
                "source_contract_address": hashing.content_address(plain(module.NODE_CONTRACTS[key])),
                "binding_source_contract_address": registration.source_contract_address,
                "binding_implementation_address": registration.implementation_address,
                "implementation_address": module.V2_IMPLEMENTATIONS[key].implementation_address,
            }
    return records


def test_all_84_source_binding_and_transitive_implementation_identities_are_exact():
    current = current_identity_records()
    assert [len(module.V2_COMPONENTS) for module in MODULES] == [58, 17, 9]
    assert len(current) == len(PRE["identities"]) == len(TRANSITION["records"]) == 84
    assert set(current) == set(PRE["identities"]) == set(TRANSITION["records"])

    for label, actual in current.items():
        sealed = TRANSITION["records"][label]
        assert actual == sealed["after"]
        assert sealed["before"] == PRE["identities"][label]
        for field in (
            "component_address", "source_contract_address",
            "binding_source_contract_address", "binding_implementation_address",
        ):
            assert sealed["before"][field] == sealed["after"][field]
        assert sealed["before"]["implementation_address"] != sealed["after"]["implementation_address"]
        assert sealed["component_exact"] is True
        assert sealed["source_contract_exact"] is True
        assert sealed["binding_contract_exact"] is True
        assert sealed["implementation_moved"] is True

    assert TRANSITION["component_descriptors_exact"] == 84
    assert TRANSITION["source_contracts_exact"] == 84
    assert TRANSITION["binding_contracts_exact"] == 84
    assert TRANSITION["transitive_implementations_moved"] == 84


def test_125_legacy_identities_and_default_registry_snapshot_are_unchanged():
    catalogue = json.loads(CATALOGUE.read_text())
    assert hashlib.sha256(CATALOGUE.read_bytes()).hexdigest() == PRE["legacy_catalogue_sha256"]
    assert len(catalogue["records"]) == PRE["legacy_count"] == 125
    assert DEFAULT_REGISTRY.registry_snapshot_address == PRE["default_registry_snapshot_address"]
    for row in catalogue["records"]:
        key = (row["component_id"], row["component_version"])
        assert plain(DEFAULT_REGISTRY.v2_components[key]) == row["descriptor"]
        assert plain(DEFAULT_REGISTRY.node_contracts[key]) == row["node_contract"]
        assert plain(DEFAULT_REGISTRY.data_requirement_declarations[key]) == row["data_requirement"]
        assert DEFAULT_REGISTRY.v2_implementation_registrations[key].implementation_address == row["implementation_address"]
        assert DEFAULT_REGISTRY.node_contract_addresses[key] == row["node_contract_address"]
        assert DEFAULT_REGISTRY.data_requirement_declaration_addresses[key] == row["data_requirement_address"]


def graph_document(registry: PlatformRegistry, component, parameters):
    descriptor = plain(registry.v2_components[component])
    graph_input = deepcopy(next(port for port in descriptor["ports"] if port["direction"] == "input"))
    graph_input["port_id"] = "frame"
    return {
        "format_version": 2,
        "strategy_id": "session-context-stale-oracle",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Stale context oracle", "description": None, "tags": []},
        "graph_inputs": [graph_input],
        "graph_outputs": [],
        "nodes": [{"node_id": "probe", "component": {
            "component_id": component[0], "component_version": component[1]},
            "parameters": parameters}],
        "edges": [{"edge_id": "frame-to-probe", "source": {"scope": "graph_input", "port_id": "frame"},
                   "target": {"scope": "node", "node_id": "probe", "port_id": "frame"},
                   "binding": {"kind": "single"}}],
    }


def context_from_old_receipt(receipt):
    node_input = receipt["input_binding"]
    entry = node_input["ports"]["frame"]
    return canonical_input_bindings(
        owner_id=node_input["owner_id"],
        dataset_context_address=node_input["dataset_context_address"],
        evaluation_context_address=node_input["evaluation_context_address"],
        bindings={"frame": entry["binding"]},
        expected_source_addresses={"frame": entry["binding_address"]},
    )


def component_registry(module, name) -> PlatformRegistry:
    key = module.component_key(name)
    return PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=module.V2_TYPES,
        v2_components={key: module.V2_COMPONENTS[key]},
        v2_implementations={key: module.V2_IMPLEMENTATIONS[key]},
        node_contracts={key: module.NODE_CONTRACTS[key]},
        contract_bindings={key: module.CONTRACT_BINDINGS[key]},
    )


@pytest.mark.parametrize("wave", ["core_math", "recursive_state", "multi_output"])
def test_old_receipts_plans_and_research_checkpoints_refuse_current_identity(wave):
    representative = PRE["representatives"][wave]
    name = representative["name"]
    module = {"core_math": core_math, "recursive_state": recursive_state, "multi_output": multi_output}[wave]
    key = module.component_key(name)
    registry = component_registry(module, name)
    context = context_from_old_receipt(representative["receipt"])
    resolved = resolve_v2(graph_document(registry, key, representative["parameters"]), registry)
    current = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)

    stale_receipt = ResolvedNodeContract(
        representative["receipt"], representative["receipt"]["bound_contract_address"]
    )
    current_receipt = current.parameter_binding_provenance[0]["node_contract_binding"]
    assert stale_receipt.bound_contract_address == current_receipt["bound_contract_address"]
    assert stale_receipt.document["binding_implementation_address"] == current_receipt["binding_implementation_address"]
    assert resolved.implementation_closure_address != representative["plan"]["implementation_closure_address"]

    with pytest.raises(DataRequirementRefusal):
        verify_data_requirement_plan(DataRequirementPlan(**representative["plan"]), resolved, registry=registry, input_bindings=context)

    state = representative.get("state")
    if state is not None:
        creation = hashing.content_address({"session_context_assurance": "checkpoint:" + name})
        reset = hashing.content_address(plain(current_receipt["resolved_contract"]["state_reset_policy"]))
        old_authority = _create_research_snapshot_authority(
            strategy_address=hashing.content_address({"strategy": name}),
            resolved_graph_address=representative["resolved_graph_address"],
            node_contract_address=representative["receipt"]["source_contract_address"],
            implementation_closure_address=representative["plan"]["implementation_closure_address"],
            dataset_context_address=representative["receipt"]["input_binding"]["dataset_context_address"],
            evaluation_context_address=representative["receipt"]["input_binding"]["evaluation_context_address"],
            reset_policy_address=reset,
            creation_evidence_address=creation,
            initial_state_payload={},
        )
        checkpoint = create_research_checkpoint(
            old_authority, closed(state),
            last_event_address=hashing.content_address({"old_event": name}),
            last_event_time="2025-01-02T10:00:00+00:00",
        )
        current_authority = _create_research_snapshot_authority(
            strategy_address=hashing.content_address({"strategy": name}),
            resolved_graph_address=resolved.resolved_graph_address,
            node_contract_address=current_receipt["source_contract_address"],
            implementation_closure_address=current.implementation_closure_address,
            dataset_context_address=current_receipt["input_binding"]["dataset_context_address"],
            evaluation_context_address=current_receipt["input_binding"]["evaluation_context_address"],
            reset_policy_address=reset,
            creation_evidence_address=creation,
            initial_state_payload={},
        )
        with pytest.raises(ResearchSnapshotRefusal):
            restore_research_checkpoint(
                checkpoint, current_authority,
                next_event_address=hashing.content_address({"next_event": name}),
                next_event_time="2025-01-02T10:15:00+00:00",
            )
