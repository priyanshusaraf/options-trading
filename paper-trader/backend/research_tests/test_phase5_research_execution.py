from __future__ import annotations

import ast
import copy
import datetime as dt
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

import pandas as pd
import pytest

from app.backtest.dataset_store import (
    DatasetManifest,
    DatasetSegment,
    dataset_byte_digest,
)
from app.ir.hashing import content_address
from app.ir.incremental_runtime import (
    CancellationToken,
    accept_research_resource_plan,
)
from app.ir.first_party.logic_state import STATEFUL_TYPE_5_NAMES
from app.ir.first_party.derivatives import (
    CAPABILITY_GATED_NAMES as TYPE_3_CAPABILITY_GATED_NAMES,
    TYPE_3_NAMES,
)
from app.ir.registry import (
    DependencyBoundary,
    PlatformRegistry,
    registered_v2_implementation,
)
from app.ir.resolve import resolve_v2
from app.ir.resource_plan import ResourcePlan
from app.ir.state_snapshots import (
    ResearchSnapshotAuthority,
    ResearchSnapshotRefusal,
    create_research_checkpoint,
    restore_research_checkpoint,
)
from app.ir import validity as validity_module
from app.ir.validity import ValidityState, invalid, valid
from app.market_data.requirements import compile_data_requirement_plan
from research.evaluation.phase5_runtime import (
    NODE_CONTEXT_RESOLVER_ADDRESS,
    ResearchExecutionRefusal,
    accept_research_snapshot_context,
    canonical_research_input_bytes,
    execute_research,
    evaluate_stateful_restart,
    registered_research_universe,
    require_complete_research_case_universe,
    research_evaluation_policy,
    verify_research_dataset,
)


UTC = dt.UTC


def _address(name: str) -> str:
    return content_address({"fixture": name})


def _node_contract(component_id: str):
    return {
        "stable_node_id": component_id,
        "semantic_version": 1,
        "visible_family": "TYPE_2",
        "input_types": {"input": "number/series"},
        "output_types": {"value": "number/series"},
        "required_market_fields": ["close"],
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 0,
        "execution_form": "STATELESS",
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/1", "reasons": []},
        "bar_policy": "COMPLETED_ONLY",
        "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "FINITE_ONLY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"],
        "streaming_support": True,
        "batch_support": True,
        "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [],
        "resource_profile": {
            "compute_microseconds_per_event": 10,
            "memory_bytes_upper_bound": 1024,
            "history_bytes_upper_bound": 1024,
            "state_bytes_upper_bound": 0,
            "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": 0,
            "fanout_upper_bound": 4,
        },
        "reference_provenance": [_address(f"reference-{component_id}")],
    }


def _cumulative(_parameters, inputs):
    return {"value": inputs["input"].cumsum()}


def _lookahead(_parameters, inputs):
    value = inputs["input"]
    return {"value": value.shift(-1).fillna(value.iloc[-1])}


def _scale(parameters, inputs):
    return {"value": inputs["input"] * parameters["factor"]}


def _passthrough(_parameters, inputs):
    value = inputs["input"]
    return {"value": value if isinstance(value, validity_module.NumericValue)
            else validity_module.valid(value)}


def _component(component_id, *, factor=False):
    parameters = {}
    if factor:
        parameters["factor"] = {
            "type": "float", "required": False, "default": 1.0,
            "enum": None, "domain": None, "units": "value",
            "serialization": "canonical-json",
        }
    return {
        "component_id": component_id, "component_version": 1,
        "domain_family": "transform", "structural_role": "transform",
        "ports": [
            {
                "port_id": "input", "direction": "input",
                "semantic_flow": "value", "semantic_role": "research_input",
                "type_ref": {"type_id": "number", "type_version": 1},
                "shape": "series",
                "connections": {"cardinality": "single", "min": 1, "max": 1,
                                "assembly": "single"},
            },
            {
                "port_id": "value", "direction": "output",
                "semantic_flow": "value", "semantic_role": "research_output",
                "type_ref": {"type_id": "number", "type_version": 1},
                "shape": "series",
            },
        ],
        "parameters": parameters,
    }


def _boundary_port(port_id, direction, *, shape="series", template=None):
    if template is None:
        value = {
            "port_id": port_id, "direction": direction,
            "semantic_flow": "value", "semantic_role": "research_value",
            "type_ref": {"type_id": "number", "type_version": 1},
            "shape": shape,
        }
        if direction == "input":
            value["connections"] = {
                "cardinality": "single", "min": 1, "max": 1,
                "assembly": "single",
            }
        return value
    value = _plain_policy(template)
    value["port_id"] = port_id
    value["direction"] = direction
    return value


def _registry(*, lookahead=False):
    components = (("research.cumsum", 1), ("research.scale", 1))
    contracts = {key: _node_contract(key[0]) for key in components}
    implementations = {
        ("research.cumsum", 1): _lookahead if lookahead else _cumulative,
        ("research.scale", 1): _scale,
    }
    descriptors = {
        ("research.cumsum", 1): _component("research.cumsum"),
        ("research.scale", 1): _component("research.scale", factor=True),
    }
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={("number", 1): {
            "type_id": "number", "type_version": 1,
            "shapes": ["series"], "runtime_representation": "float64",
        }},
        v2_components=descriptors,
        v2_implementations={
            key: registered_v2_implementation(
                component=key, implementation=implementation,
                dependency_boundary=DependencyBoundary("defining_module"),
            ) for key, implementation in implementations.items()
        },
        node_contracts=contracts,
        data_requirement_declarations={
            key: {
                "schema": "data-requirement-declaration/1",
                "classification": "NO_DATA", "requirements": [],
            }
            for key in components
        },
    )


def _graph(registry):
    return resolve_v2({
        "format_version": 2, "strategy_id": "phase5-research",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Research fixture",
                     "description": None, "tags": ["phase5"]},
        "graph_inputs": [_boundary_port("price", "input")],
        "graph_outputs": [_boundary_port("signal", "output")],
        "nodes": [
            {"node_id": "sum", "component": {
                "component_id": "research.cumsum", "component_version": 1,
            }, "parameters": {}},
            {"node_id": "scale", "component": {
                "component_id": "research.scale", "component_version": 1,
            }, "parameters": {"factor": 2.0}},
        ],
        "edges": [
            {"edge_id": "price-to-sum", "source": {
                "scope": "graph_input", "port_id": "price",
            }, "target": {"scope": "node", "node_id": "sum", "port_id": "input"},
             "binding": {"kind": "single"}},
            {"edge_id": "sum-to-scale", "source": {
                "scope": "node", "node_id": "sum", "port_id": "value",
            }, "target": {"scope": "node", "node_id": "scale", "port_id": "input"},
             "binding": {"kind": "single"}},
            {"edge_id": "scale-to-signal", "source": {
                "scope": "node", "node_id": "scale", "port_id": "value",
            }, "target": {"scope": "graph_output", "port_id": "signal"},
             "binding": {"kind": "single"}},
        ],
    }, registry)


def _numeric_runtime(value):
    key = ("research.numeric", 1)
    contract = _node_contract(key[0])
    contract["input_types"] = {"input": "number/scalar"}
    contract["output_types"] = {"value": "number/scalar"}
    component = _component(key[0])
    for port in component["ports"]:
        port["shape"] = "scalar"
    component["numeric_validity"] = {
        "input_policy": "propagate", "output_policy": "numeric_envelope",
    }
    registry = PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={("number", 1): {
            "type_id": "number", "type_version": 1,
            "shapes": ["scalar"], "runtime_representation": "numeric-envelope",
        }},
        v2_components={key: component},
        v2_implementations={key: registered_v2_implementation(
            component=key, implementation=_passthrough,
            dependency_boundary=DependencyBoundary(
                "declared_objects", (validity_module,),
            ),
        )},
        node_contracts={key: contract},
        data_requirement_declarations={key: {
            "schema": "data-requirement-declaration/1",
            "classification": "NO_DATA", "requirements": [],
        }},
    )
    graph = resolve_v2({
        "format_version": 2, "strategy_id": "phase5-numeric",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Numeric fixture",
                     "description": None, "tags": ["phase5"]},
        "graph_inputs": [_boundary_port("price", "input", shape="scalar")],
        "graph_outputs": [_boundary_port("signal", "output", shape="scalar")],
        "nodes": [{"node_id": "numeric", "component": {
            "component_id": key[0], "component_version": 1,
        }, "parameters": {}}],
        "edges": [
            {"edge_id": "price-to-numeric", "source": {
                "scope": "graph_input", "port_id": "price",
            }, "target": {"scope": "node", "node_id": "numeric", "port_id": "input"},
             "binding": {"kind": "single"}},
            {"edge_id": "numeric-to-signal", "source": {
                "scope": "node", "node_id": "numeric", "port_id": "value",
            }, "target": {"scope": "graph_output", "port_id": "signal"},
             "binding": {"kind": "single"}},
        ],
    }, registry)
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), registry,
        queue_concurrency_upper_bound=1,
    )
    dataset = _dataset_inputs(length=1, inputs={"price": value})
    policy = _policy(graph, registry, plan, dataset, maximum_events=1)
    return graph, registry, plan, dataset, policy


def _plan(graph, registry):
    return accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), registry,
        cache_bytes_upper_bound=4096, artifact_bytes_upper_bound=4096,
        queue_concurrency_upper_bound=1,
    )


def _dataset_inputs(length=5, *, inputs=None):
    if inputs is None:
        index = pd.date_range("2026-01-01T00:00:00Z", periods=length, freq="min")
        inputs = {"price": pd.Series(range(1, length+1), index=index, dtype=float)}
    payload = canonical_research_input_bytes(inputs)
    instrument = _address("instrument")
    truth = _address("truth")
    segment = DatasetSegment(
        owner_id="owner-a",
        object_address=_address("object"),
        byte_digest=dataset_byte_digest(payload),
        byte_length=len(payload),
        media_type="application/x-phase5-test",
        raw_schema_address=_address("raw-schema"),
        row_start=0, row_end=length,
        instrument_addresses=(instrument,), fields=("close",),
        event_start="2026-01-01T00:00:00+00:00",
        event_end="2026-01-01T00:06:00+00:00",
        availability_start="2026-01-01T00:00:00+00:00",
        availability_end="2026-01-01T00:06:00+00:00",
        provider_product_addresses=(_address("product"),),
        provider_contract_addresses=(_address("contract"),),
        provider_observation_addresses=(_address("provider-observation"),),
        normalized_observation_addresses=(_address("normalized-observation"),),
        normalization_transform_addresses=(_address("transform"),),
        algorithm_addresses=(_address("algorithm"),), correction_addresses=(),
        creation_evidence_address=_address("creation"),
    )
    manifest = DatasetManifest(
        owner_id="owner-a", purpose="PHASE5_RESEARCH", mode="RESEARCH",
        segment_addresses=(segment.segment_address,),
        aggregate_byte_digest=dataset_byte_digest(payload),
        aggregate_byte_length=len(payload),
        instrument_addresses=(instrument,), fields=("close",),
        event_start="2026-01-01T00:00:00+00:00",
        event_end="2026-01-01T00:06:00+00:00",
        availability_start="2026-01-01T00:00:00+00:00",
        availability_end="2026-01-01T00:06:00+00:00",
        gaps=(), correction_addresses=(),
        provider_entity_addresses=(_address("entity"),),
        provider_product_addresses=segment.provider_product_addresses,
        provider_contract_addresses=segment.provider_contract_addresses,
        provider_observation_addresses=segment.provider_observation_addresses,
        normalized_observation_addresses=segment.normalized_observation_addresses,
        raw_schema_addresses=(segment.raw_schema_address,),
        normalization_transform_addresses=segment.normalization_transform_addresses,
        truth_snapshot_addresses=(truth,),
        creation_evidence_addresses=(segment.creation_evidence_address,),
        capability_profile_address=_address("capability"),
        alignment_policy_address=_address("alignment"),
        missing_data_policy_address=_address("missing"),
        adjustment_policy_address=_address("adjustment"),
        roll_policy_address=_address("roll"),
        algorithm_addresses=segment.algorithm_addresses,
        created_at="2026-01-01T00:06:00+00:00",
        recorded_at="2026-01-01T00:06:00+00:00",
    )
    return verify_research_dataset(
        manifest, {segment.segment_address: (segment, payload)}, inputs,
    )


def _policy(graph, registry, plan, dataset, *, maximum_events=5):
    document = {
        "schema": "research-evaluation-policy/1",
        "owner_id": "owner-a", "mode": "RESEARCH",
        "dataset_manifest_address": dataset.manifest.manifest_address,
        "dataset_input_digest": dataset.input_digest,
        "input_derivation_address": dataset.derivation_address,
        "node_context_resolver_address": NODE_CONTEXT_RESOLVER_ADDRESS,
        "resolved_graph_address": graph.resolved_graph_address,
        "registry_snapshot_address": registry.registry_snapshot_address,
        "implementation_closure_address": graph.implementation_closure_address,
        "resource_plan_address": plan.plan_address,
        "truth_snapshot_addresses": list(dataset.manifest.truth_snapshot_addresses),
        "adjustment_policy_address": dataset.manifest.adjustment_policy_address,
        "session_policy_address": _address("session"),
        "resampling_policy_address": _address("resampling"),
        "missing_data_policy_address": dataset.manifest.missing_data_policy_address,
        "alignment_policy_address": dataset.manifest.alignment_policy_address,
        "run_authority_address": _address("run-authority"),
        "input_bindings": {
            name: {
                "instrument_address": dataset.manifest.instrument_addresses[0],
                "field": "close",
            }
            for name in sorted(dataset.inputs)
        },
        "event_kind": "completed_bar",
        "event_start": "2026-01-01T00:00:00+00:00",
        "event_end": "2026-01-01T00:06:00+00:00",
        "maximum_events": maximum_events,
        "cancellation_check_interval": 1,
    }
    document["evaluation_policy_address"] = content_address(document)
    return research_evaluation_policy(document)


def _runtime(*, lookahead=False, length=5, maximum_events=5):
    registry = _registry(lookahead=lookahead)
    graph = _graph(registry)
    plan = _plan(graph, registry)
    dataset = _dataset_inputs(length)
    policy = _policy(graph, registry, plan, dataset, maximum_events=maximum_events)
    return graph, registry, plan, dataset, policy


def _state_input(name):
    value = {
        "left": valid(2.0), "right": valid(1.0),
        "lower": valid(0.5), "upper": valid(1.5),
        "series": tuple(valid(item) for item in (0.0, 1.0, 1.0, 0.0)),
        "a_series": tuple(valid(item) for item in (True, False, False, True)),
        "b_series": tuple(valid(item) for item in (False, True, False, True)),
        "event_times": tuple(
            f"2026-01-01T00:0{index}:00+00:00" for index in range(4)
        ),
        "reset_series": tuple(valid(item) for item in (False, False, True, False)),
        "transition": {
            "False:False": False, "False:True": True,
            "True:False": False, "True:True": True,
        },
        "reset_reasons": [],
    }
    if name in {"ANY", "ALL", "LATCH", "RESETTABLE_LATCH", "TOGGLE",
                "STATE_MACHINE", "N_CONSECUTIVE", "N_OF_LAST_M"}:
        value["series"] = tuple(valid(item) for item in (False, True, True, False))
    if name == "HYSTERESIS":
        value["series"] = tuple(valid(item) for item in (0.0, 2.0, 1.0, 0.0))
    return value


def _state_initial(name):
    if name in {"A_THEN_B", "LATCH", "RESETTABLE_LATCH", "TOGGLE",
                "STATE_MACHINE", "HYSTERESIS"}: return False
    if name in {"A_WITHIN_N_BARS_OF_B", "LAG_N", "PREVIOUS_VALUE", "N_OF_LAST_M"}: return ()
    if name in {"RISING_N", "FALLING_N"}: return (None, 0)
    if name == "TIME_SINCE": return None
    if name == "BARS_SINCE": return -1
    if name == "COUNTER": return 0.0
    if name in {"DEBOUNCE", "COOLDOWN", "N_CONSECUTIVE"}: return 0
    raise AssertionError(name)


@lru_cache(maxsize=None)
def _state_runtime(name):
    from app.ir.library import REGISTRY as registry
    key = (f"logic.{name.lower()}", 1)
    component = registry.v2_components[key]
    contract = registry.node_contracts[key]
    input_port = next(port for port in component["ports"] if port["direction"] == "input")
    output_port = next(port for port in component["ports"] if port["direction"] == "output")
    graph = resolve_v2({
        "format_version": 2,
        "strategy_id": f"phase5-state-{name.lower().replace('_', '-')}",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": f"State {name}",
                     "description": None, "tags": ["phase5", "state"]},
        "graph_inputs": [
            _boundary_port("state_input", "input", template=input_port),
        ],
        "graph_outputs": [
            _boundary_port("state_output", "output", template=output_port),
        ],
        "nodes": [{"node_id": "state", "component": {
            "component_id": key[0], "component_version": key[1],
        }, "parameters": {}}],
        "edges": [
            {"edge_id": "input-to-state", "source": {
                "scope": "graph_input", "port_id": "state_input",
            }, "target": {"scope": "node", "node_id": "state",
                          "port_id": input_port["port_id"]},
             "binding": {"kind": "single"}},
            {"edge_id": "state-to-output", "source": {
                "scope": "node", "node_id": "state", "port_id": output_port["port_id"],
            }, "target": {"scope": "graph_output", "port_id": "state_output"},
             "binding": {"kind": "single"}},
        ],
    }, registry)
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), registry,
        queue_concurrency_upper_bound=1,
    )
    accepted_input = _state_input(name)
    accepted_input["reset_reasons"] = ()
    dataset = _dataset_inputs(
        length=1, inputs={"state_input": accepted_input},
    )
    policy = _policy(graph, registry, plan, dataset, maximum_events=4)
    context = accept_research_snapshot_context(
        key, "state", graph, registry, plan, dataset, policy,
        initial_state_payload=_state_initial(name),
    )
    assert contract["execution_form"] == "RECURSIVE"
    return (
        key, dict(graph.nodes[0].parameters), graph, plan, dataset, policy, context,
    )


def _restart(runtime, full_input, registry, *, split_index,
             pending_reset_reasons=(), context=None, node_id="state", parameters=None):
    key, accepted_parameters, graph, plan, dataset, policy, accepted_context = runtime
    return evaluate_stateful_restart(
        key,
        accepted_parameters if parameters is None else parameters,
        full_input,
        graph,
        registry,
        plan,
        dataset,
        policy,
        accepted_context if context is None else context,
        node_id=node_id,
        split_index=split_index,
        pending_reset_reasons=pending_reset_reasons,
    )


def _immutable_fixture(value):
    if isinstance(value, dict):
        return {key: _immutable_fixture(item) for key, item in value.items()}
    if isinstance(value, list): return tuple(_immutable_fixture(item) for item in value)
    if isinstance(value, tuple): return tuple(_immutable_fixture(item) for item in value)
    return value


def _single_production_runtime(key, input_value, *, parameters=None, maximum_events=1):
    from app.ir.library import REGISTRY
    component = REGISTRY.v2_components[key]
    input_port = next(port for port in component["ports"] if port["direction"] == "input")
    output_port = next(port for port in component["ports"] if port["direction"] == "output")
    graph = resolve_v2({
        "format_version": 2,
        "strategy_id": f"phase5-{key[0].replace('.', '-')}",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": f"Research {key[0]}",
                     "description": None, "tags": ["phase5", "complete-universe"]},
        "graph_inputs": [_boundary_port("input", "input", template=input_port)],
        "graph_outputs": [_boundary_port("value", "output", template=output_port)],
        "nodes": [{"node_id": "node", "component": {
            "component_id": key[0], "component_version": key[1],
        }, "parameters": {} if parameters is None else parameters}],
        "edges": [
            {"edge_id": "input-to-node", "source": {
                "scope": "graph_input", "port_id": "input",
            }, "target": {"scope": "node", "node_id": "node",
                          "port_id": input_port["port_id"]},
             "binding": {"kind": "single"}},
            {"edge_id": "node-to-output", "source": {
                "scope": "node", "node_id": "node", "port_id": output_port["port_id"],
            }, "target": {"scope": "graph_output", "port_id": "value"},
             "binding": {"kind": "single"}},
        ],
    }, REGISTRY)
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), REGISTRY,
        queue_concurrency_upper_bound=1,
    )
    dataset = _dataset_inputs(
        length=maximum_events,
        inputs={"input": _immutable_fixture(input_value)},
    )
    policy = _policy(
        graph, REGISTRY, plan, dataset, maximum_events=maximum_events,
    )
    return graph, REGISTRY, plan, dataset, policy


def _accepted_type3_fact(name):
    from app.market_truth.identity import canonical_fact_address
    from app.market_data.capability import CAPABILITY_ASSESSMENT_SCHEMA
    from tests.test_phase5_state_execution_derivatives_catalogue import (
        _derivative_fact,
        _rehash_fact,
    )
    fact = _derivative_fact(
        name, capability=name in TYPE_3_CAPABILITY_GATED_NAMES,
    )
    fact["event_time"] = "2026-01-01T00:01:00+00:00"
    fact["knowledge_time"] = "2026-01-01T00:02:00+00:00"
    fact["evaluation_cutoff"] = "2026-01-01T00:03:00+00:00"
    envelope = fact.get("capability_assessment_envelope")
    if envelope is not None:
        envelope["fact"]["assessed_at"] = int(dt.datetime(
            2026, 1, 1, 0, 2, 30, tzinfo=dt.UTC,
        ).timestamp())
        fact["capability_evidence_address"] = canonical_fact_address(
            CAPABILITY_ASSESSMENT_SCHEMA, envelope["fact"],
        )
    return _rehash_fact(fact)


def test_verified_vector_incremental_execution_and_complete_provenance():
    graph, registry, plan, dataset, policy = _runtime()
    result = execute_research(graph, registry, plan, dataset, policy)
    expected = pd.Series((2.0, 6.0, 12.0, 20.0, 30.0),
                         index=dataset.inputs["price"].index)
    pd.testing.assert_series_equal(result.batch_outputs["signal"], expected)
    pd.testing.assert_series_equal(result.incremental_outputs["signal"], expected)
    assert result.document["status"] == "COMPLETED"
    assert result.document["dataset_manifest_address"] == dataset.manifest.manifest_address
    assert result.document["evaluation_policy_address"] == policy.policy_address
    assert result.document["resource_plan_address"] == plan.plan_address
    assert result.document["node_components"] == (
        "research.cumsum@1", "research.scale@1",
    )
    assert tuple(result.document["node_contract_addresses"]) \
        == tuple(plan.document["node_contract_addresses"])
    assert result.document["dataset_input_digest"] == dataset.input_digest
    assert result.document["input_derivation_address"] == dataset.derivation_address


@pytest.mark.parametrize("mutation", ("values", "index", "field"))
def test_verified_segment_bytes_are_the_only_research_input_authority(mutation):
    dataset = _dataset_inputs()
    substituted = {
        "price": dataset.inputs["price"].copy(deep=True),
    }
    if mutation == "values":
        substituted["price"].iloc[0] = 999.0
    elif mutation == "index":
        substituted["price"].index = (
            substituted["price"].index + pd.Timedelta(seconds=1)
        )
    else:
        substituted = {"volume": substituted.pop("price")}
    with pytest.raises(ResearchExecutionRefusal, match="do not derive"):
        verify_research_dataset(
            dataset.manifest, dataset.segment_objects, substituted,
        )


def test_resolved_topology_and_used_callable_cannot_change_under_retained_identities():
    graph, registry, plan, dataset, policy = _runtime()
    changed_outputs = dict(graph.outputs)
    changed_outputs["signal"] = graph.outputs["signal"].__class__(
        edge_id=graph.outputs["signal"].edge_id,
        source={"scope": "node", "node_id": "sum", "port_id": "value"},
        binding=graph.outputs["signal"].binding,
        type_ref=graph.outputs["signal"].type_ref,
        provenance=graph.outputs["signal"].provenance,
    )
    object.__setattr__(graph, "outputs", MappingProxyType(changed_outputs))
    with pytest.raises(ResearchExecutionRefusal, match="graph"):
        execute_research(graph, registry, plan, dataset, policy)

    graph, registry, plan, dataset, policy = _runtime()
    implementations = dict(registry.v2_implementations)
    implementations[("research.cumsum", 1)] = _lookahead
    object.__setattr__(
        registry, "_v2_implementations", MappingProxyType(implementations),
    )
    with pytest.raises(ResearchExecutionRefusal, match="callable"):
        execute_research(graph, registry, plan, dataset, policy)


@pytest.mark.parametrize("mutation", ("memory", "research-mode"))
def test_resource_plan_readdressing_cannot_underreport_compiler_demand(mutation):
    graph, registry, plan, dataset, policy = _runtime()
    document = _plain_policy(plan.document)
    assert document["memory_bytes_upper_bound"] > 0
    if mutation == "memory":
        document["memory_bytes_upper_bound"] = 0
    else:
        document["mode_support"]["research"] = False
    document.pop("plan_address")
    document["plan_address"] = content_address(document)
    object.__setattr__(
        plan, "plan", ResourcePlan(document, document["plan_address"]),
    )
    policy_document = _plain_policy(policy.document)
    policy_document["resource_plan_address"] = document["plan_address"]
    policy_document.pop("evaluation_policy_address")
    policy_document["evaluation_policy_address"] = content_address(policy_document)
    policy = research_evaluation_policy(policy_document)
    with pytest.raises(ResearchExecutionRefusal, match="ResourcePlan authority"):
        execute_research(graph, registry, plan, dataset, policy)


def test_research_result_outputs_are_defensive_materializations():
    graph, registry, plan, dataset, policy = _runtime()
    result = execute_research(graph, registry, plan, dataset, policy)
    expected = result.batch_outputs["signal"].copy(deep=True)
    address = result.result_address
    document = _plain_policy(result.document)
    batch = result.batch_outputs["signal"]
    incremental = result.incremental_outputs["signal"]
    batch.iloc[0] = -1.0
    batch.index = batch.index + pd.Timedelta(days=1)
    incremental.iloc[-1] = -2.0
    pd.testing.assert_series_equal(result.batch_outputs["signal"], expected)
    pd.testing.assert_series_equal(result.incremental_outputs["signal"], expected)
    assert result.result_address == address
    assert _plain_policy(result.document) == document


def test_complete_registered_research_universe_is_source_derived_and_omission_sensitive():
    registry = _registry()
    expected = (("research.cumsum", 1), ("research.scale", 1))
    assert registered_research_universe(registry) == expected
    assert require_complete_research_case_universe(registry, expected) == expected
    with pytest.raises(ResearchExecutionRefusal, match="incomplete"):
        require_complete_research_case_universe(registry, expected[:-1])
    with pytest.raises(ResearchExecutionRefusal, match="noncanonical"):
        require_complete_research_case_universe(registry, tuple(reversed(expected)))


def test_production_registered_research_universe_is_complete_and_omission_sensitive():
    from app.ir.library import REGISTRY
    expected = tuple(sorted(REGISTRY.v2_components))
    # The former literal 309 predated the accepted analytical /2 catalogue.
    # Completeness is the exact active registry closure, never a stale count.
    assert expected and len(expected) == len(set(expected))
    assert registered_research_universe(REGISTRY) == expected
    assert require_complete_research_case_universe(REGISTRY, expected) == expected
    with pytest.raises(ResearchExecutionRefusal, match="incomplete"):
        require_complete_research_case_universe(REGISTRY, expected[:-1])


@pytest.mark.parametrize("name", TYPE_3_NAMES)
def test_every_type3_node_executes_with_accepted_point_in_time_context(name):
    from tests.test_phase5_state_execution_derivatives_catalogue import (
        _assert_semantic_equal,
        _type3_expected,
    )
    fact = _accepted_type3_fact(name)
    runtime = _single_production_runtime(
        (f"derivative.{name.lower()}", 1), fact,
        parameters={"maximum_members": 3},
    )
    result = execute_research(*runtime)
    actual = result.batch_outputs["value"]
    assert actual == result.incremental_outputs["value"]
    _assert_semantic_equal(actual["value"], _type3_expected(fact)[name])
    assert result.document["event_count"] == 1
    assert result.document["node_context_resolver_address"] \
        == NODE_CONTEXT_RESOLVER_ADDRESS


@pytest.mark.parametrize("name", tuple(sorted(STATEFUL_TYPE_5_NAMES)))
def test_every_recursive_type5_node_executes_over_actual_nested_events(name):
    from tests.test_phase5_state_execution_derivatives_catalogue import (
        _assert_type5_semantic,
        _type5_expected,
        _type5_input,
    )
    value = _type5_input(name)
    value["event_times"] = tuple(
        f"2026-01-01T00:0{index}:00+00:00" for index in range(4)
    )
    component = (f"logic.{name.lower()}", 1)
    parameters = {"window": 2}
    if name == "N_OF_LAST_M": parameters["required_count"] = 1
    runtime = _single_production_runtime(
        component, value, parameters=parameters, maximum_events=4,
    )
    result = execute_research(*runtime)
    actual = result.batch_outputs["value"]
    expected = _type5_expected()[name]
    expected = type(expected)(
        expected.values,
        actual.state_payload if name == "TIME_SINCE" else expected.state_payload,
        actual.last_event_time,
    )
    _assert_type5_semantic(actual, expected)
    assert actual == result.incremental_outputs["value"]
    assert result.document["event_count"] == 4
    assert result.document["last_event_time"] == "2026-01-01T00:03:00+00:00"


@pytest.mark.parametrize("mutation", (
    "owner", "mode", "event-before-window", "knowledge-after-cutoff",
    "cutoff-after-window", "graph-authored-context", "resolver-address",
))
def test_type3_context_is_derived_only_from_accepted_fact_and_policy(mutation):
    from tests.test_phase5_state_execution_derivatives_catalogue import _rehash_fact
    fact = _accepted_type3_fact("BASIS")
    if mutation == "owner": fact["owner_id"] = "owner-b"
    elif mutation == "mode": fact["mode"] = "PAPER"
    elif mutation == "event-before-window":
        fact["event_time"] = "2025-12-31T23:59:00+00:00"
    elif mutation == "knowledge-after-cutoff":
        fact["knowledge_time"] = "2026-01-01T00:04:00+00:00"
    elif mutation == "cutoff-after-window":
        fact["evaluation_cutoff"] = "2026-01-01T00:06:00+00:00"
    elif mutation == "graph-authored-context":
        fact["evaluation_context"] = {"forged": True}
    if mutation != "resolver-address": _rehash_fact(fact)
    graph, registry, plan, dataset, policy = _single_production_runtime(
        ("derivative.basis", 1), fact, parameters={"maximum_members": 3},
    )
    if mutation == "resolver-address":
        document = _plain_policy(policy.document)
        document["node_context_resolver_address"] = _address("wrong-resolver")
        document.pop("evaluation_policy_address")
        document["evaluation_policy_address"] = content_address(document)
        policy = research_evaluation_policy(document)
    with pytest.raises(ResearchExecutionRefusal):
        execute_research(graph, registry, plan, dataset, policy)


@pytest.mark.parametrize("mutation", (
    "length", "naive-time", "duplicate-time", "event-limit",
))
def test_recursive_nested_event_clock_is_closed_and_bounded(mutation):
    from tests.test_phase5_state_execution_derivatives_catalogue import _type5_input
    value = _type5_input("COUNTER")
    value["event_times"] = tuple(
        f"2026-01-01T00:0{index}:00+00:00" for index in range(4)
    )
    if mutation == "length": value["series"] = value["series"][:-1]
    elif mutation == "naive-time":
        value["event_times"] = tuple(item.replace("+00:00", "") for item in value["event_times"])
    elif mutation == "duplicate-time":
        value["event_times"] = value["event_times"][:-1] + (value["event_times"][-2],)
    graph, registry, plan, dataset, policy = _single_production_runtime(
        ("logic.counter", 1), value, parameters={"window": 2}, maximum_events=4,
    )
    if mutation == "event-limit":
        document = _plain_policy(policy.document)
        document["maximum_events"] = 3
        document.pop("evaluation_policy_address")
        document["evaluation_policy_address"] = content_address(document)
        policy = research_evaluation_policy(document)
    with pytest.raises(ResearchExecutionRefusal):
        execute_research(graph, registry, plan, dataset, policy)


def test_recursive_nested_cancellation_prefix_and_result_immutability():
    from tests.test_phase5_state_execution_derivatives_catalogue import _type5_input
    name = "A_WITHIN_N_BARS_OF_B"
    value = _type5_input(name)
    value["event_times"] = tuple(
        f"2026-01-01T00:0{index}:00+00:00" for index in range(4)
    )
    runtime = _single_production_runtime(
        (f"logic.{name.lower()}", 1), value,
        parameters={"window": 2}, maximum_events=4,
    )
    cancelled = execute_research(
        *runtime, cancellation=CancellationToken(cancel_after_events=2),
    )
    assert cancelled.document["status"] == "CANCELLED"
    assert cancelled.document["event_count"] == 2
    completed = execute_research(*runtime)
    exposed = completed.batch_outputs["value"]
    expected_payload = exposed.state_payload
    object.__setattr__(exposed, "state_payload", ("forged",))
    assert completed.batch_outputs["value"].state_payload == expected_payload

    prefix_value = copy.deepcopy(value)
    for field in ("series", "a_series", "b_series", "event_times", "reset_series"):
        if field in prefix_value: prefix_value[field] = prefix_value[field][:3]
    prefix_runtime = _single_production_runtime(
        (f"logic.{name.lower()}", 1), prefix_value,
        parameters={"window": 2}, maximum_events=3,
    )
    prefix = execute_research(*prefix_runtime)
    assert completed.batch_outputs["value"].values[:3] \
        == prefix.batch_outputs["value"].values


@pytest.mark.parametrize("name", tuple(sorted(STATEFUL_TYPE_5_NAMES)))
def test_production_stateful_nodes_match_batch_and_checkpoint_restart(name):
    from app.ir.library import REGISTRY
    runtime = _state_runtime(name)
    key = runtime[0]
    result = _restart(runtime, _state_input(name), REGISTRY, split_index=2)
    assert result.component == key
    assert len(result.values) == 4


@pytest.mark.parametrize("reason", (
    "ELAPSED_WINDOW", "EXPIRY_ROLL", "EXPLICIT", "POSITION_CLOSE", "SESSION",
))
def test_research_restart_applies_every_canonical_reset_reason(reason):
    from app.ir.library import REGISTRY
    runtime = _state_runtime("COUNTER")
    result = _restart(
        runtime, _state_input("COUNTER"), REGISTRY, split_index=2,
        pending_reset_reasons=(reason,),
    )
    assert result.applied_reset_reasons == (reason,)


def test_state_restart_requires_accepted_full_graph_data_policy_context():
    from app.ir.library import REGISTRY
    from app.ir.incremental_runtime import _create_accepted_research_snapshot_context
    name = "COUNTER"
    runtime = _state_runtime(name)
    key, parameters, _graph_value, plan, _dataset, _policy_value, context = runtime
    assert context.authority.implementation_closure_address \
        != REGISTRY.v2_implementation_identities[key]

    with pytest.raises(ResearchSnapshotRefusal, match="accepted execution boundary"):
        ResearchSnapshotAuthority(
            strategy_address=context.authority.strategy_address,
            resolved_graph_address=context.authority.resolved_graph_address,
            node_contract_address=context.authority.node_contract_address,
            implementation_closure_address=context.authority.implementation_closure_address,
            dataset_context_address=context.authority.dataset_context_address,
            evaluation_context_address=context.authority.evaluation_context_address,
            reset_policy_address=context.authority.reset_policy_address,
            creation_evidence_address=context.authority.creation_evidence_address,
            initial_state_payload=context.authority.initial_state_payload,
        )
    with pytest.raises(ResearchExecutionRefusal, match="accepted snapshot context"):
        _restart(runtime, _state_input(name), REGISTRY, context=object(), split_index=2)

    forged = _create_accepted_research_snapshot_context(
        component=key,
        node_id="state",
        node_parameters=parameters,
        registry_snapshot_address=REGISTRY.registry_snapshot_address,
        resource_plan_address=_address("invented-resource-plan"),
        run_authority_address=_address("invented-run-authority"),
        strategy_address=_address("invented-strategy"),
        resolved_graph_address=_address("invented-graph"),
        node_contract_address=REGISTRY.node_contract_addresses[key],
        implementation_closure_address=context.authority.implementation_closure_address,
        dataset_context_address=_address("invented-dataset"),
        evaluation_context_address=_address("invented-policy"),
        reset_policy_address=context.authority.reset_policy_address,
        initial_state_payload=context.authority.initial_state_payload,
    )
    assert forged.resource_plan_address != plan.plan_address
    with pytest.raises(ResearchExecutionRefusal, match="does not derive"):
        _restart(runtime, _state_input(name), REGISTRY, context=forged, split_index=2)
    object_forged = object.__new__(type(context))
    for field in (
        "component", "node_id", "node_parameters", "registry_snapshot_address",
        "resource_plan_address", "run_authority_address", "authority",
        "context_address",
    ):
        object.__setattr__(object_forged, field, getattr(forged, field))
    with pytest.raises(ResearchExecutionRefusal, match="does not derive"):
        _restart(
            runtime, _state_input(name), REGISTRY,
            context=object_forged, split_index=2,
        )

    for field in (
        "resolved_graph_address", "implementation_closure_address",
        "dataset_context_address", "evaluation_context_address",
    ):
        wrong = copy.copy(context)
        wrong_authority = copy.copy(context.authority)
        object.__setattr__(wrong_authority, field, _address(f"wrong-{field}"))
        object.__setattr__(wrong, "authority", wrong_authority)
        with pytest.raises(ResearchExecutionRefusal, match="does not derive"):
            _restart(runtime, _state_input(name), REGISTRY, context=wrong, split_index=2)
    wrong_wrapper = copy.copy(context)
    object.__setattr__(wrong_wrapper, "context_address", _address("wrong-context"))
    with pytest.raises(ResearchExecutionRefusal, match="does not derive"):
        _restart(
            runtime, _state_input(name), REGISTRY, context=wrong_wrapper, split_index=2,
        )
    with pytest.raises(ResearchExecutionRefusal, match="restart evaluation refused"):
        _restart(
            runtime, _state_input(name), REGISTRY, split_index=2,
            parameters={**parameters, "window": parameters.get("window", 1) + 1},
        )
    with pytest.raises(ResearchExecutionRefusal, match="recursive graph node"):
        _restart(runtime, _state_input(name), REGISTRY, node_id="other", split_index=2)
    ordered = _restart(
        runtime, _state_input(name), REGISTRY, split_index=2,
        pending_reset_reasons=("EXPLICIT", "SESSION"),
    )
    reversed_order = _restart(
        runtime, _state_input(name), REGISTRY, split_index=2,
        pending_reset_reasons=("SESSION", "EXPLICIT"),
    )
    assert ordered == reversed_order


def test_repeated_recursive_components_bind_exact_node_instance():
    from app.ir.library import REGISTRY
    key = ("logic.counter", 1)
    component = REGISTRY.v2_components[key]
    input_port = next(port for port in component["ports"] if port["direction"] == "input")
    output_port = next(port for port in component["ports"] if port["direction"] == "output")
    graph_inputs = [
        _boundary_port(f"input_{suffix}", "input", template=input_port)
        for suffix in ("a", "b")
    ]
    graph_outputs = [
        _boundary_port(f"output_{suffix}", "output", template=output_port)
        for suffix in ("a", "b")
    ]
    nodes = [{
        "node_id": f"state_{suffix}",
        "component": {"component_id": key[0], "component_version": key[1]},
        "parameters": {},
    } for suffix in ("a", "b")]
    edges = []
    for suffix in ("a", "b"):
        edges.extend((
            {"edge_id": f"input-{suffix}-to-state", "source": {
                "scope": "graph_input", "port_id": f"input_{suffix}",
            }, "target": {"scope": "node", "node_id": f"state_{suffix}",
                          "port_id": input_port["port_id"]},
             "binding": {"kind": "single"}},
            {"edge_id": f"state-{suffix}-to-output", "source": {
                "scope": "node", "node_id": f"state_{suffix}",
                "port_id": output_port["port_id"],
            }, "target": {"scope": "graph_output", "port_id": f"output_{suffix}"},
             "binding": {"kind": "single"}},
        ))
    graph = resolve_v2({
        "format_version": 2, "strategy_id": "phase5-repeated-state",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Repeated state",
                     "description": None, "tags": ["phase5", "state"]},
        "graph_inputs": graph_inputs, "graph_outputs": graph_outputs,
        "nodes": nodes, "edges": edges,
    }, REGISTRY)
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), REGISTRY,
        queue_concurrency_upper_bound=1,
    )
    accepted_input = _state_input("COUNTER")
    accepted_input["reset_reasons"] = ()
    dataset = _dataset_inputs(length=1, inputs={
        "input_a": accepted_input, "input_b": accepted_input,
    })
    policy = _policy(graph, REGISTRY, plan, dataset, maximum_events=4)
    contexts = {
        node_id: accept_research_snapshot_context(
            key, node_id, graph, REGISTRY, plan, dataset, policy,
            initial_state_payload=_state_initial("COUNTER"),
        )
        for node_id in ("state_a", "state_b")
    }
    assert contexts["state_a"].context_address != contexts["state_b"].context_address
    parameters = dict(next(node for node in graph.nodes
                           if node.node_id == "state_a").parameters)
    result = evaluate_stateful_restart(
        key, parameters, _state_input("COUNTER"), graph, REGISTRY, plan,
        dataset, policy, contexts["state_a"], node_id="state_a", split_index=2,
    )
    assert len(result.values) == 4
    with pytest.raises(ResearchExecutionRefusal, match="does not derive"):
        evaluate_stateful_restart(
            key, parameters, _state_input("COUNTER"), graph, REGISTRY, plan,
            dataset, policy, contexts["state_b"], node_id="state_a", split_index=2,
        )


@pytest.mark.parametrize("value", (
    valid(3.0),
    invalid(ValidityState.MISSING),
    invalid(ValidityState.STALE),
    invalid(ValidityState.INSUFFICIENT_HISTORY),
    invalid(ValidityState.MATHEMATICALLY_UNDEFINED),
    invalid(ValidityState.PROVIDER_UNAVAILABLE),
    invalid(ValidityState.NOT_IN_SESSION),
    invalid(ValidityState.NOT_LISTED),
))
def test_validity_states_match_vector_and_independent_incremental_paths(value):
    graph, registry, plan, dataset, policy = _numeric_runtime(value)
    result = execute_research(graph, registry, plan, dataset, policy)
    assert result.batch_outputs["signal"] == value
    assert result.incremental_outputs["signal"] == value


def test_future_append_does_not_change_completed_prefixes():
    graph, registry, plan, full_dataset, full_policy = _runtime()
    full = execute_research(graph, registry, plan, full_dataset, full_policy)
    prefix_dataset = _dataset_inputs(length=3)
    prefix_policy = _policy(graph, registry, plan, prefix_dataset, maximum_events=5)
    prefix = execute_research(graph, registry, plan, prefix_dataset, prefix_policy)
    pd.testing.assert_series_equal(
        full.batch_outputs["signal"].iloc[:3], prefix.batch_outputs["signal"],
    )


def test_independent_prefix_path_rejects_future_lookahead():
    graph, registry, plan, dataset, policy = _runtime(lookahead=True)
    with pytest.raises(ResearchExecutionRefusal, match="outputs differ"):
        execute_research(graph, registry, plan, dataset, policy)


def test_cancellation_is_bounded_and_provenance_complete():
    graph, registry, plan, dataset, policy = _runtime()
    result = execute_research(
        graph, registry, plan, dataset, policy,
        cancellation=CancellationToken(cancel_after_events=2),
    )
    assert result.document["status"] == "CANCELLED"
    assert result.document["event_count"] == 2
    assert result.document["cancellation_state"] == "CANCELLED"
    assert result.document["output_digest"] is None
    assert result.batch_outputs == result.incremental_outputs == {}


def test_pre_cancel_reuse_and_completion_boundary_are_non_vacuous():
    graph, registry, plan, dataset, policy = _runtime()
    pre_cancelled = CancellationToken(cancelled=True)
    first = execute_research(
        graph, registry, plan, dataset, policy,
        cancellation=pre_cancelled,
    )
    assert first.document["status"] == "CANCELLED"
    assert first.document["event_count"] == 0
    assert pre_cancelled.observed_events == 0

    zero = execute_research(
        graph, registry, plan, dataset, policy,
        cancellation=CancellationToken(cancel_after_events=0),
    )
    assert zero.document["status"] == "CANCELLED"
    assert zero.document["event_count"] == 0

    token = CancellationToken(cancel_after_events=2)
    cancelled = execute_research(
        graph, registry, plan, dataset, policy, cancellation=token,
    )
    reused = execute_research(
        graph, registry, plan, dataset, policy, cancellation=token,
    )
    assert cancelled.document["event_count"] == 2
    assert reused.document["event_count"] == 2
    assert token.observed_events == 2

    completed = execute_research(
        graph, registry, plan, dataset, policy,
        cancellation=CancellationToken(cancel_after_events=5),
    )
    assert completed.document["status"] == "COMPLETED"
    assert completed.document["event_count"] == 5
    first_after = execute_research(
        graph, registry, plan, dataset, policy,
        cancellation=CancellationToken(cancel_after_events=4),
    )
    assert first_after.document["status"] == "CANCELLED"
    assert first_after.document["event_count"] == 4


def test_event_limit_at_limit_and_first_above_refuse():
    graph, registry, plan, dataset, policy = _runtime(maximum_events=5)
    assert execute_research(graph, registry, plan, dataset, policy).document["event_count"] == 5
    graph, registry, plan, dataset, policy = _runtime(maximum_events=4)
    with pytest.raises(ResearchExecutionRefusal, match="event count exceeds"):
        execute_research(graph, registry, plan, dataset, policy)


@pytest.mark.parametrize("mutation", (
    "dataset-bytes", "input-after-verify", "policy-dataset", "policy-binding",
    "policy-input-digest", "policy-derivation", "policy-window", "graph-closure",
    "resource-graph", "trigger",
))
def test_wrong_dataset_policy_graph_resource_and_trigger_bindings_refuse(mutation):
    graph, registry, plan, dataset, policy = _runtime()
    if mutation == "dataset-bytes":
        address = next(iter(dataset.segment_objects))
        segment, _payload = dataset.segment_objects[address]
        object.__setattr__(dataset, "segment_objects", {address: (segment, b"wrong")})
    elif mutation == "input-after-verify":
        dataset.inputs["price"].iloc[0] = 99.0
    elif mutation == "graph-closure":
        object.__setattr__(graph, "implementation_closure_address", _address("wrong-closure"))
    elif mutation == "resource-graph":
        document = _plain_policy(plan.document)
        document["resolved_graph_address"] = _address("wrong-graph")
        document["plan_address"] = content_address({
            key: value for key, value in document.items() if key != "plan_address"
        })
        plan = ResourcePlan(document, document["plan_address"])
    else:
        document = _plain_policy(policy.document)
        if mutation == "policy-dataset":
            document["dataset_manifest_address"] = _address("wrong-dataset")
        elif mutation == "policy-binding":
            document["input_bindings"]["price"]["field"] = "volume"
        elif mutation == "policy-input-digest":
            document["dataset_input_digest"] = _address("wrong-input-digest")
        elif mutation == "policy-derivation":
            document["input_derivation_address"] = _address("wrong-derivation")
        elif mutation == "policy-window":
            document["event_end"] = "2026-01-01T00:04:00+00:00"
        else:
            document["event_kind"] = "partial_bar"
        document.pop("evaluation_policy_address")
        document["evaluation_policy_address"] = content_address(document)
        policy = research_evaluation_policy(document)
    with pytest.raises((ResearchExecutionRefusal, AttributeError, TypeError)):
        execute_research(graph, registry, plan, dataset, policy)


def _plain_policy(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _plain_policy(item) for key, item in value.items()}
    if isinstance(value, tuple): return [_plain_policy(item) for item in value]
    return value


def test_checkpoint_restart_reset_and_stale_authority_refusals():
    *_unused, accepted = _state_runtime("COUNTER")
    authority = accepted.authority
    checkpoint = create_research_checkpoint(
        authority, 3.0, last_event_address=_address("event-1"),
        last_event_time="2026-01-01T00:01:00+00:00",
    )
    restored = restore_research_checkpoint(
        checkpoint, authority, next_event_address=_address("event-2"),
        next_event_time="2026-01-01T00:02:00+00:00",
    )
    assert restored.state_payload == 3.0
    reset = restore_research_checkpoint(
        checkpoint, authority, next_event_address=_address("event-2"),
        next_event_time="2026-01-01T00:02:00+00:00",
        pending_reset_reasons=("SESSION", "EXPLICIT"),
    )
    ordered = restore_research_checkpoint(
        checkpoint, authority, next_event_address=_address("event-2"),
        next_event_time="2026-01-01T00:02:00+00:00",
        pending_reset_reasons=("EXPLICIT", "SESSION"),
    )
    assert reset == ordered
    assert reset.state_payload == 0.0
    full = (1.0, 3.0, 6.0, 10.0)
    resumed = tuple((restored.state_payload + value) for value in (3.0, 7.0))
    assert resumed == full[2:]
    with pytest.raises(ResearchSnapshotRefusal, match="ordering"):
        restore_research_checkpoint(
            checkpoint, authority, next_event_address=_address("past"),
            next_event_time="2026-01-01T00:00:00+00:00",
        )
    wrong = copy.copy(authority)
    object.__setattr__(wrong, "dataset_context_address", _address("wrong-dataset"))
    with pytest.raises(ResearchSnapshotRefusal, match="authority"):
        restore_research_checkpoint(
            checkpoint, wrong, next_event_address=_address("event-2"),
            next_event_time="2026-01-01T00:02:00+00:00",
        )


def test_research_runtime_import_direction_excludes_broker_runner_and_session():
    from research.evaluation import phase5_runtime
    modules = (phase5_runtime,)
    forbidden = {"app.engine", "app.providers", "app.ledger", "app.db.session"}
    for module in modules:
        tree = ast.parse(Path(module.__file__).read_text())
        imports = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(any(name.startswith(prefix) for prefix in forbidden) for name in imports)
