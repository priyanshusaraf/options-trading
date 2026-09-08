"""Integrated 125-name registry, identity, history, and real-consumer proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backtest.cache import phase4_cache_identity
from app.backtest.public_computation import is_eligible
from app.ir import node_contracts
from app.ir.first_party import analytical
from app.ir.first_party.analytical_v2 import session_data
from app.ir.first_party.analytical_v2.contracts import (
    ResolvedNodeContract,
    canonical_input_bindings,
)
from app.ir.hashing import content_address
from app.ir.library import (
    ANALYTICAL_V2_DISPOSITIONS,
    REGISTRY,
    LibraryConflict,
    compose_v2,
)
from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.resource_plan import compile_resource_plan
from app.ir.runtime import evaluate_v2
from app.market_data.requirements import (
    compile_data_requirement_plan,
    verify_data_requirement_plan,
)


ROOT = Path(__file__).resolve().parents[3]
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"


def _address(label):
    return content_address({"registry_lineage_test": label})


def _phase4(**changes):
    values = {
        "owner_id": "owner-a", "authored_ir_address": _address("authored"),
        "manifest_address": _address("manifest"),
        "registry_snapshot_address": REGISTRY.registry_snapshot_address,
        "resolved_graph_address": _address("graph"),
        "implementation_closure_address": _address("implementation"),
        "declaration_addresses": (_address("declaration"),),
        "plan_address": _address("plan"),
        "capability_assessment_address": _address("capability"),
        "market_truth_address": _address("truth"),
        "evaluation_policy_address": _address("evaluation"),
        "admission_address": _address("admission"),
    }
    values.update(changes)
    return phase4_cache_identity(**values)


def _sma_consumer():
    from tests import test_indicator_accuracy_core_math as fixture

    key = ("analytical.sma", 2)
    ports = node_contracts._plain(REGISTRY.v2_components[key]["ports"])
    inputs = [deepcopy(port) for port in ports if port["direction"] == "input"]
    outputs = [deepcopy(port) for port in ports if port["direction"] == "output"]
    document = {
        "format_version": 2, "strategy_id": "registry-lineage-sma", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Registry lineage SMA",
                     "description": None, "tags": []},
        "graph_inputs": inputs, "graph_outputs": outputs,
        "nodes": [{"node_id": "sma", "component": {
            "component_id": key[0], "component_version": 2},
            "parameters": {"window": 2}}],
        "edges": [{
            "edge_id": "input", "source": {"scope": "graph_input", "port_id": "frame"},
            "target": {"scope": "node", "node_id": "sma", "port_id": "frame"},
            "binding": {"kind": "single"},
        }, {
            "edge_id": "output", "source": {"scope": "node", "node_id": "sma", "port_id": "value"},
            "target": {"scope": "graph_output", "port_id": "value"},
            "binding": {"kind": "single"},
        }],
    }
    fact = fixture.fact("primary", ["CLOSE"])
    context = canonical_input_bindings(
        owner_id=fact["owner_id"],
        dataset_context_address=fact["dataset_context_address"],
        evaluation_context_address=fact["evaluation_context_address"],
        bindings={"frame": fact}, expected_source_addresses={"frame": content_address(fact)},
    )
    graph = resolve_v2(document, REGISTRY)
    data = compile_data_requirement_plan(graph, registry=REGISTRY, input_bindings=context)
    verify_data_requirement_plan(data, graph, registry=REGISTRY, input_bindings=context)
    resource = compile_resource_plan(graph, data, REGISTRY)
    receipt = node_contracts._plain(
        data.parameter_binding_provenance[0]["node_contract_binding"])
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    values = evaluate_v2(
        graph, fixture.bars("SMA"), REGISTRY,
        evaluation_context_resolver=lambda _node, _inputs: {"bound_contract": bound},
    )
    return document, graph, data, resource, receipt, values


def test_complete_universe_and_frozen_v1_identity_are_exact():
    frozen = json.loads(CATALOGUE.read_text())
    assert hashlib.sha256((ROOT / "paper-trader/backend/app/ir/first_party/analytical.py").read_bytes()).hexdigest() == frozen["source_sha256"]
    assert len(ANALYTICAL_V2_DISPOSITIONS) == len(frozen["records"]) == 125
    assert sum(row["status"] == "ACCEPTED_V2" for row in ANALYTICAL_V2_DISPOSITIONS.values()) == 108
    assert sum(row["status"] == "UNAVAILABLE" for row in ANALYTICAL_V2_DISPOSITIONS.values()) == 17
    for row in frozen["records"]:
        key = (row["component_id"], 1)
        assert node_contracts._plain(REGISTRY.v2_components[key]) == row["descriptor"]
        assert node_contracts._plain(REGISTRY.node_contracts[key]) == row["node_contract"]
        assert REGISTRY.node_contract_addresses[key] == row["node_contract_address"]
        assert REGISTRY.data_requirement_declaration_addresses[key] == row["data_requirement_address"]
        assert REGISTRY.v2_implementation_identities[key] == row["implementation_address"]


def test_only_accepted_v2_rows_are_executable_and_unavailable_rows_have_stable_reasons():
    for name, disposition in ANALYTICAL_V2_DISPOSITIONS.items():
        key = (analytical.component_id(name), 2)
        if disposition["status"] == "ACCEPTED_V2":
            assert key in REGISTRY.v2_components
            assert key in REGISTRY.v2_implementation_identities
            assert key in REGISTRY.node_contracts
            assert key in REGISTRY.contract_bindings
        else:
            assert disposition["reason_code"]
            assert key not in REGISTRY.v2_components
            with pytest.raises(ResolutionError):
                resolve_v2({"format_version": 2, "strategy_id": "refused", "strategy_version": 1,
                    "metadata": {"metadata_version": 1, "name": "Refused", "description": None, "tags": []},
                    "graph_inputs": [], "graph_outputs": [],
                    "nodes": [{"node_id": "x", "component": {"component_id": key[0], "component_version": 2}, "parameters": {}}],
                    "edges": []}, REGISTRY)


def test_shared_type_reconciliation_is_exact_and_detects_a_mutation():
    changed = dict(session_data.V2_TYPES)
    key = ("analytical.market_frame", 2)
    changed[key] = {**dict(changed[key]), "runtime_representation": "unknown mutable frame"}
    module = SimpleNamespace(
        V2_TYPES=changed, V2_COMPONENTS={}, V2_IMPLEMENTATIONS={},
        DATA_REQUIREMENTS={}, NODE_CONTRACTS={}, CONTRACT_BINDINGS={},
    )
    with pytest.raises(LibraryConflict):
        compose_v2(REGISTRY, (module,))


def test_real_resolution_data_resource_and_runtime_bind_complete_identity():
    document, graph, data, resource, receipt, values = _sma_consumer()
    assert values["value"].iloc[-1].value == 3.0
    assert graph.registry_snapshot_address == REGISTRY.registry_snapshot_address
    assert data.registry_snapshot_address == graph.registry_snapshot_address
    assert resource.document["registry_snapshot_address"] == graph.registry_snapshot_address
    assert resource.document["implementation_closure_address"] == graph.implementation_closure_address
    assert receipt["source_contract_address"] == REGISTRY.node_contract_addresses[("analytical.sma", 2)]
    assert receipt["binding_implementation_address"] == REGISTRY.contract_bindings[("analytical.sma", 2)].implementation_address
    assert receipt["parameters"] == {"window": 2}
    assert receipt["input_binding"]["ports"]["frame"]["binding"]["session"] == "INSTRUMENT_CALENDAR"
    assert graph.authored_ir_address == content_address(document)


@pytest.mark.parametrize("field,value", [
    ("registry_snapshot_address", _address("stale-registry")),
    ("implementation_closure_address", _address("stale-implementation")),
    ("declaration_addresses", (_address("stale-template"),)),
    ("plan_address", _address("stale-bound-contract-plan")),
    ("owner_id", "owner-b"),
])
def test_cache_identity_misses_for_every_integrated_lineage_dimension(field, value):
    assert _phase4() != _phase4(**{field: value})


def test_unknown_historical_environment_and_public_promotion_fail_closed():
    with pytest.raises(ValueError):
        _phase4(implementation_closure_address="UNKNOWN_HISTORICAL_ENVIRONMENT")
    assert not is_eligible(
        dataset_classification="MARKET_PUBLIC", strategy_key="ir.registry-lineage-sma",
        strategy_module="app.ir.runtime", execution_manifest={
            "dataset_address": "a" * 64, "dataset_verified": True,
        })
