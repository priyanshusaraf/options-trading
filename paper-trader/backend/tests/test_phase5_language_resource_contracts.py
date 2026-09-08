from __future__ import annotations

import dataclasses
from types import MappingProxyType, SimpleNamespace

import pytest

from app.ir.hashing import content_address
from app.ir.node_contracts import (
    NODE_CONTRACT_FIELDS,
    RESOURCE_PROFILE_FIELDS,
    NodeContractRefusal,
    canonical_node_contract,
    canonical_reset_schedule,
    canonical_state_snapshot,
    state_snapshot_document,
)
from app.ir.registry import PlatformRegistry
from app.ir.resource_plan import (
    DEFAULT_TIER_LIMITS,
    TIER_DIMENSIONS,
    ResourcePlan,
    ResourcePlanRefusal,
    binding_input_requirement,
    bounded_rate,
    compile_resource_plan,
    instrument_role_requirement,
    provider_requirement,
    resource_calibration,
    resource_tier_decision,
    resource_tier_policy,
)


def _address(value: str) -> str:
    return content_address({"fixture": value})


def _type() -> dict[str, object]:
    return {
        "type_id": "number",
        "type_version": 1,
        "shapes": ["series"],
        "runtime_representation": "float64",
    }


def _component(component_id: str) -> dict[str, object]:
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "utility",
        "structural_role": "transform",
        "ports": [
            {
                "port_id": "value",
                "direction": "out",
                "type_ref": {"type_id": "number", "type_version": 1},
                "shape": "series",
            }
        ],
        "parameters": {},
    }


def _contract(component_id: str, family: str = "TYPE_2") -> dict[str, object]:
    return {
        "stable_node_id": component_id,
        "semantic_version": 1,
        "visible_family": family,
        "input_types": {"value": "number/series"},
        "output_types": {"value": "number/series"},
        "required_market_fields": ["close"],
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 20,
        "execution_form": "ROLLING",
        "state_initialization": {
            "schema": "state-initialization/1",
            "initial_state_address": _address("initial"),
        },
        "state_reset_policy": {
            "schema": "state-reset-policy/1",
            "reasons": ["EXPLICIT", "SESSION"],
        },
        "bar_policy": "COMPLETED_ONLY",
        "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "FINITE_ONLY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"],
        "streaming_support": True,
        "batch_support": True,
        "mode_eligibility": {"research": True, "paper": True, "live": False},
        "provider_requirements": [_address("provider")],
        "resource_profile": {
            "compute_microseconds_per_event": 5,
            "memory_bytes_upper_bound": 32,
            "history_bytes_upper_bound": 160,
            "state_bytes_upper_bound": 16,
            "storage_bytes_per_day_upper_bound": 8,
            "subscription_count_upper_bound": 1,
            "fanout_upper_bound": 4,
        },
        "reference_provenance": [_address("reference")],
    }


def _provider():
    return provider_requirement({
        "capability_classes": ["candles"],
        "fields": ["close"],
        "timeframe_seconds": 60,
        "history_bars": 20,
        "freshness_seconds": 90,
        "depth_levels": 0,
        "session": "exchange",
        "alignment": "BAR_CLOSE",
        "product_classes": ["spot"],
        "contract_classes": [],
        "supply": "PROVIDER_REQUIRED",
    })


def _role(provider_address: str):
    return instrument_role_requirement({
        "role_id": "primary",
        "role_kind": "EXECUTION_TARGET",
        "instrument_type": "PHYSICAL",
        "cardinality": "EXACT_ONE",
        "maximum_members": 1,
        "source_requirement_addresses": [_address("data-requirement")],
        "provider_requirement_addresses": [provider_address],
        "binding_input_kind": "CANONICAL_PHYSICAL_ADDRESS",
        "execution_eligible": True,
        "research_only": False,
    })


def _registry() -> PlatformRegistry:
    components = {
        ("indicator.ema", 1): _component("indicator.ema"),
        ("signal.cross", 1): _component("signal.cross"),
    }
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={("number", 1): _type()},
        v2_components=components,
        node_contracts={
            ("indicator.ema", 1): _contract("indicator.ema", "TYPE_2"),
            ("signal.cross", 1): _contract("signal.cross", "TYPE_5"),
        },
    )


def _plan() -> ResourcePlan:
    registry = _registry()
    provider = _provider()
    role = _role(provider.address)
    nodes = (
        SimpleNamespace(
            node_id="bundle/ema", component=("indicator.ema", 1),
            authored_node_id="bundle", lowered_path=("bundle", "ema"),
        ),
        SimpleNamespace(
            node_id="cross", component=("signal.cross", 1),
            authored_node_id="cross", lowered_path=("cross",),
        ),
    )
    graph = SimpleNamespace(
        authored_ir_address=_address("authored"),
        resolved_graph_address=_address("resolved"),
        implementation_closure_address=_address("implementation"),
        registry_snapshot_address=registry.registry_snapshot_address,
        nodes=nodes,
        topology_document={
            "edges": [
                {"source": {"node_id": "bundle/ema", "port_id": "value"}},
                {"source": {"node_id": "bundle/ema", "port_id": "value"}},
            ]
        },
    )
    return compile_resource_plan(
        graph, SimpleNamespace(plan_address=_address("data-plan")), registry,
        instrument_roles=(role,), provider_requirements=(provider,),
        assumption_addresses=(_address("assumption"),),
        cache_bytes_upper_bound=1000, artifact_bytes_upper_bound=2000,
        queue_concurrency_upper_bound=2,
    )


def _plan_at(plan: ResourcePlan, dimension: str, value: int) -> ResourcePlan:
    document = {key: (dict(item) if isinstance(item, MappingProxyType) else item)
                for key, item in plan.document.items()}
    document["family_counts"] = dict(plan.document["family_counts"])
    if dimension in document["family_counts"]:
        document["family_counts"][dimension] = value
    else:
        document[dimension] = value
    payload = {key: _plain(item) for key, item in document.items() if key != "plan_address"}
    document["plan_address"] = content_address(payload)
    return ResourcePlan(MappingProxyType(document), document["plan_address"])


def _plain(value):
    if isinstance(value, dict) or isinstance(value, MappingProxyType):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def test_node_contract_is_closed_frozen_and_registry_bound():
    raw = _contract("indicator.ema")
    contract = canonical_node_contract(("indicator.ema", 1), raw)
    assert tuple(raw) == NODE_CONTRACT_FIELDS
    assert tuple(raw["resource_profile"]) == RESOURCE_PROFILE_FIELDS
    with pytest.raises(TypeError):
        contract.document["visible_family"] = "TYPE_1"
    registry = _registry()
    assert registry.node_contract_addresses[("indicator.ema", 1)] == contract.contract_address
    assert registry.registry_snapshot_payload["node_contracts"][0]["contract_address"]


@pytest.mark.parametrize("mutation", ["missing", "extra", "family", "bool-int", "unsorted"])
def test_node_contract_complete_universe_refuses(mutation):
    raw = _contract("indicator.ema")
    if mutation == "missing":
        raw.pop("reference_provenance")
    elif mutation == "extra":
        raw["other"] = 1
    elif mutation == "family":
        raw["visible_family"] = "TYPE_6"
    elif mutation == "bool-int":
        raw["resource_profile"]["memory_bytes_upper_bound"] = True
    else:
        raw["evaluation_triggers"] = ["z", "a"]
    with pytest.raises(NodeContractRefusal):
        canonical_node_contract(("indicator.ema", 1), raw)


def test_resource_plan_counts_lowered_origin_and_separates_identities():
    plan = _plan()
    assert plan.document["family_counts"] == {
        "TYPE_1": 0, "TYPE_2": 1, "TYPE_3": 0, "TYPE_4": 0, "TYPE_5": 1,
    }
    assert plan.document["authored_node_count"] == 2
    assert plan.document["lowered_node_count"] == 2
    assert plan.document["maximum_compound_depth"] == 1
    assert plan.document["maximum_single_output_fanout"] == 2
    assert plan.document["instrument_role_requirements"][0]["role_id"] == "primary"
    assert binding_input_requirement(_role(_provider().address)).document == {
        "role_requirement_address": _role(_provider().address).address,
        "binding_input_kind": "CANONICAL_PHYSICAL_ADDRESS",
        "maximum_members": 1,
    }
    assert bounded_rate(10, 20) == {"events": 1, "per_seconds": 2}


def test_tier_limits_are_conjunctive_at_limit_and_first_over():
    plan = _plan()
    calibration = resource_calibration({
        "workload_address": _address("workload"),
        "measurement_evidence_addresses": [_address("measurement")],
        "measured_at": "2026-08-26T00:00:00Z",
    })
    policy = resource_tier_policy(
        "Standard", evidence_addresses=(_address("tier-evidence"),),
    )
    for dimension in TIER_DIMENSIONS:
        at_limit = _plan_at(plan, dimension, DEFAULT_TIER_LIMITS["Standard"][dimension])
        assert resource_tier_decision(
            at_limit, policy, calibration, owner_id="owner-a"
        ).document["accepted"]
        over = _plan_at(plan, dimension, DEFAULT_TIER_LIMITS["Standard"][dimension] + 1)
        decision = resource_tier_decision(over, policy, calibration, owner_id="owner-a")
        assert not decision.document["accepted"]
        assert dimension in decision.document["binding_dimensions"]


def test_policy_and_calibration_never_change_resource_plan_identity():
    plan = _plan()
    first_policy = resource_tier_policy("Standard", evidence_addresses=(_address("e1"),))
    second_policy = resource_tier_policy("Pro", evidence_addresses=(_address("e2"),))
    first_calibration = resource_calibration({
        "workload_address": _address("w1"),
        "measurement_evidence_addresses": [_address("m1")],
        "measured_at": "2026-08-26T00:00:00Z",
    })
    second_calibration = resource_calibration({
        "workload_address": _address("w2"),
        "measurement_evidence_addresses": [_address("m2")],
        "measured_at": "2026-08-26T00:01:00Z",
    })
    first = resource_tier_decision(plan, first_policy, first_calibration, owner_id="owner-a")
    second = resource_tier_decision(plan, second_policy, second_calibration, owner_id="owner-a")
    assert first.address != second.address
    assert plan.plan_address == _plan().plan_address


def test_state_snapshot_identity_and_reset_schedule_are_order_independent():
    facts = {
        "strategy_address": _address("strategy"),
        "resolved_graph_address": _address("resolved"),
        "node_contract_address": _address("node-contract"),
        "implementation_closure_address": _address("implementation"),
        "dataset_context_address": _address("dataset"),
        "evaluation_context_address": _address("evaluation"),
        "last_event_address": _address("event"),
        "last_event_time": "2026-08-26T00:00:00Z",
        "state_bytes_digest": _address("state-bytes"),
        "validity_state": "VALID",
        "reset_policy_address": _address("reset-policy"),
        "reset_reasons": ["EXPLICIT", "SESSION"],
        "creation_evidence_address": _address("creation"),
    }
    snapshot = canonical_state_snapshot(state_snapshot_document(**facts))
    assert snapshot.snapshot_address == snapshot.document["snapshot_address"]
    assert canonical_reset_schedule(["SESSION", "EXPLICIT", "SESSION"]) == (
        "EXPLICIT", "SESSION",
    )
    with pytest.raises(NodeContractRefusal):
        canonical_state_snapshot({**dict(snapshot.document), "last_event_time": "future"})


@pytest.mark.parametrize("mutation", ["role-authority", "dynamic-unbounded", "provider-open", "rate-bool"])
def test_role_provider_and_rate_refusals_are_closed(mutation):
    if mutation == "role-authority":
        raw = dict(_role(_provider().address).document)
        raw.update(role_kind="OBSERVATION", execution_eligible=True)
        with pytest.raises(ResourcePlanRefusal):
            instrument_role_requirement(raw)
    elif mutation == "dynamic-unbounded":
        raw = dict(_role(_provider().address).document)
        raw.update(cardinality="DYNAMIC_WINDOW", maximum_members=0)
        with pytest.raises(ResourcePlanRefusal):
            instrument_role_requirement(raw)
    elif mutation == "provider-open":
        raw = dict(_provider().document)
        raw["provider_id"] = "kite"
        with pytest.raises(ResourcePlanRefusal):
            provider_requirement(raw)
    else:
        with pytest.raises(ResourcePlanRefusal):
            bounded_rate(True, 1)


def test_assurance_findings_refuse_through_public_wrappers_and_compiler():
    plan = _plan()
    malformed = dict(plan.document)
    malformed["node_contract_addresses"] = None
    malformed["plan_address"] = content_address({
        key: _plain(value) for key, value in malformed.items()
        if key != "plan_address"
    })
    with pytest.raises(ResourcePlanRefusal):
        dataclasses.replace(plan, document=MappingProxyType(malformed),
                            plan_address=malformed["plan_address"])

    policy = resource_tier_policy("Standard", evidence_addresses=(_address("e1"),))
    forged_policy = dict(policy.document)
    forged_policy["limits"] = {**dict(policy.document["limits"]), "TYPE_1": 999}
    with pytest.raises(ResourcePlanRefusal):
        dataclasses.replace(policy, document=MappingProxyType(forged_policy))

    role = _role(_provider().address)
    forged_role = dict(role.document)
    forged_role["binding_input_kind"] = "SELECTOR_POLICY_ADDRESS"
    with pytest.raises(ResourcePlanRefusal):
        dataclasses.replace(role, document=MappingProxyType(forged_role))

    registry = _registry()
    node = SimpleNamespace(
        node_id="ema", component=("indicator.ema", 1),
        authored_node_id="ema", lowered_path=("ema",),
    )
    graph = SimpleNamespace(
        authored_ir_address=_address("fanout-authored"),
        resolved_graph_address=_address("fanout-resolved"),
        implementation_closure_address=_address("fanout-implementation"),
        registry_snapshot_address=registry.registry_snapshot_address,
        nodes=(node,),
        topology_document={"edges": [
            {"source": {"node_id": "ema", "port_id": "value"}},
            {"source": {"node_id": "ema", "port_id": "value"}},
            {"source": {"node_id": "ema", "port_id": "value"}},
            {"source": {"node_id": "ema", "port_id": "value"}},
            {"source": {"node_id": "ema", "port_id": "value"}},
        ]},
    )
    with pytest.raises(ResourcePlanRefusal, match="fanout"):
        compile_resource_plan(
            graph, SimpleNamespace(plan_address=_address("fanout-data")), registry,
        )
