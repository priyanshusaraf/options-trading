from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

import pytest

from app.ir import validity
from app.ir.evaluation_schedule import (
    admit_evaluation_event,
    canonical_conditional_requirement_selector,
    compile_evaluation_schedule,
    compile_schedule_resource_ceiling,
)
from app.ir.first_party import monitoring_intent_v2
from app.ir.hashing import content_address
from app.ir.registry import (
    DependencyBoundary,
    PlatformRegistry,
    registered_v2_implementation,
)
from app.ir.resolve import resolve_v2
from app.ir.resource_plan import compile_resource_plan
from app.market_data.requirements import compile_data_requirement_plan
from app.monitoring import evaluation as subject
from app.monitoring.contracts import (
    AlertDerived,
    EntryReference,
    EntryReferenceKind,
    FactValidity,
    Freshness,
    NoAlert,
    NoAlertCode,
    ProtectionBasis,
    ProtectionEvidence,
    ProtectionKind,
    ProtectionUnits,
    SignalAction,
    StrategyState,
)
from app.monitoring.state_contracts import (
    MonitoringAssignment,
    MonitoringAssignmentSpec,
    MonitoringStateSnapshot,
)


UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "paper-trader/backend/app/monitoring/evaluation.py"


def address(label: str) -> str:
    return content_address({"monitoring-evaluation-fixture": label})


def moment(second: int) -> datetime:
    return datetime(2026, 8, 31, 9, 15, 0, tzinfo=UTC) + timedelta(seconds=second)


def _port(port_id: str, direction: str, type_id: str) -> dict[str, object]:
    result = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "condition" if type_id == "monitoring.condition" else "value",
        "semantic_role": "condition" if direction == "input" else "result",
        "type_ref": {"type_id": type_id, "type_version": 1},
        "shape": "scalar",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": "single", "min": 1, "max": 1, "assembly": "single",
        }
    return result


def _component(
    component_id: str, family: str, *,
    input_type: str = "boolean", output_type: str = "boolean",
) -> dict[str, object]:
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "state" if family == "TYPE_5" else "transform",
        "structural_role": "transform",
        "ports": [
            _port("in", "input", input_type),
            _port("out", "output", output_type),
        ],
        "parameters": {},
    }


def _contract(
    component_id: str, family: str, *,
    input_contract: str = "boolean-value/1",
    output_contract: str = "boolean-value/1", fanout: int = 8,
) -> dict[str, object]:
    return {
        "stable_node_id": component_id,
        "semantic_version": 1,
        "visible_family": family,
        "input_types": {"in": input_contract},
        "output_types": {"out": output_contract},
        "required_market_fields": [],
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 0,
        "execution_form": "STATELESS",
        "state_initialization": {
            "schema": "state-initialization/1", "initial_state_address": None,
        },
        "state_reset_policy": {"schema": "state-reset-policy/1", "reasons": []},
        "bar_policy": "COMPLETED_ONLY",
        "missing_data_policy": "REFUSE",
        "numeric_validity_policy": "EXPLICIT_VALIDITY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"],
        "streaming_support": True,
        "batch_support": True,
        "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [],
        "resource_profile": {
            "compute_microseconds_per_event": 10,
            "memory_bytes_upper_bound": 64,
            "history_bytes_upper_bound": 0,
            "state_bytes_upper_bound": 0,
            "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": 0,
            "fanout_upper_bound": fanout,
        },
        "reference_provenance": [address("fixture-contract")],
    }


def _conditional_requirement() -> dict[str, object]:
    literal = lambda value: {"literal": value}
    return {
        "schema": "data-requirement-declaration/1",
        "classification": "REQUIRES_DATA",
        "requirements": [{
            "requirement_id": "conditional_depth",
            "instrument": literal({"role": "option_window", "type": "ECONOMIC_SELECTOR"}),
            "field": literal("BID"),
            "timeframe": literal(60),
            "history": literal({"minimum_bars": 1, "warmup_bars": 0}),
            "freshness": literal({"maximum_age_seconds": 60}),
            "depth": literal({"kind": "BOOK", "levels": 5}),
            "session": literal("INSTRUMENT_CALENDAR"),
            "alignment": literal({"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 1}),
            "derived_local": literal(False),
        }],
    }


def _no_data() -> dict[str, object]:
    return {"schema": "data-requirement-declaration/1", "classification": "NO_DATA", "requirements": []}


def _registry() -> PlatformRegistry:
    gate = ("fixture.monitoring_gate", 1)
    dependent = ("fixture.conditional_bool", 1)
    converter = ("fixture.valid_condition", 1)

    def passthrough(_parameters, inputs):
        return {"out": inputs["in"]}

    def convert(_parameters, inputs):
        return {"out": validity.valid(inputs["in"])}

    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={
            ("boolean", 1): {
                "type_id": "boolean", "type_version": 1,
                "shapes": ["scalar"], "runtime_representation": "bool",
            },
            **monitoring_intent_v2.V2_TYPES,
        },
        v2_components={
            gate: _component(gate[0], "TYPE_5"),
            dependent: _component(dependent[0], "TYPE_2"),
            converter: _component(
                converter[0], "TYPE_2",
                input_type="boolean", output_type="monitoring.condition",
            ),
            **monitoring_intent_v2.V2_COMPONENTS,
        },
        v2_implementations={
            gate: registered_v2_implementation(
                component=gate, implementation=passthrough,
                dependency_boundary=DependencyBoundary("defining_module"),
            ),
            dependent: registered_v2_implementation(
                component=dependent, implementation=passthrough,
                dependency_boundary=DependencyBoundary("defining_module"),
            ),
            converter: registered_v2_implementation(
                component=converter, implementation=convert,
                dependency_boundary=DependencyBoundary("defining_module", (validity,)),
            ),
            **monitoring_intent_v2.V2_IMPLEMENTATIONS,
        },
        data_requirement_declarations={
            gate: _no_data(), dependent: _conditional_requirement(), converter: _no_data(),
            **monitoring_intent_v2.DATA_REQUIREMENTS,
        },
        node_contracts={
            gate: _contract(gate[0], "TYPE_5"),
            dependent: _contract(dependent[0], "TYPE_2"),
            converter: _contract(
                converter[0], "TYPE_2",
                input_contract="boolean-value/1",
                output_contract="numeric-validity-bool/1",
                fanout=128,
            ),
            **monitoring_intent_v2.NODE_CONTRACTS,
        },
    )


def _output_port(name: str, component: dict[str, object]) -> dict[str, object]:
    port = monitoring_intent_v2.node_contracts._plain(
        next(value for value in component["ports"] if value["direction"] == "output")
    )
    port["port_id"] = name
    return port


def _document(
    target: str = "BUY", *, second_target: str | None = None,
    omit_take: bool = False, target_count: int = 1,
    stop_name: str = "FIXED_STOP_PERCENT", stop_parameters=None,
    take_name: str = "TAKE_PROFIT_PERCENT", take_parameters=None,
    duplicate_stop: bool = False,
):
    target_names = [target] * target_count + ([second_target] if second_target else [])
    nodes = [
        {"node_id": "gate", "component": {"component_id": "fixture.monitoring_gate", "component_version": 1}, "parameters": {}},
        {"node_id": "dependent", "component": {"component_id": "fixture.conditional_bool", "component_version": 1}, "parameters": {}},
        {"node_id": "condition", "component": {"component_id": "fixture.valid_condition", "component_version": 1}, "parameters": {}},
    ]
    outputs = []
    edges = [
        {"edge_id": "condition-gate", "source": {"scope": "graph_input", "port_id": "condition"}, "target": {"scope": "node", "node_id": "gate", "port_id": "in"}, "binding": {"kind": "single"}},
        {"edge_id": "gate-dependent", "source": {"scope": "node", "node_id": "gate", "port_id": "out"}, "target": {"scope": "node", "node_id": "dependent", "port_id": "in"}, "binding": {"kind": "single"}},
        {"edge_id": "dependent-condition", "source": {"scope": "node", "node_id": "dependent", "port_id": "out"}, "target": {"scope": "node", "node_id": "condition", "port_id": "in"}, "binding": {"kind": "single"}},
    ]
    for index, name in enumerate(target_names):
        key = monitoring_intent_v2.component_key(name)
        node_id = f"target-{index}"
        output_id = f"target-{index}"
        nodes.append({"node_id": node_id, "component": {"component_id": key[0], "component_version": key[1]}, "parameters": {}})
        outputs.append(_output_port(output_id, monitoring_intent_v2.V2_COMPONENTS[key]))
        edges.extend([
            {"edge_id": f"condition-{node_id}", "source": {"scope": "node", "node_id": "condition", "port_id": "out"}, "target": {"scope": "node", "node_id": node_id, "port_id": "condition"}, "binding": {"kind": "single"}},
            {"edge_id": f"{node_id}-output", "source": {"scope": "node", "node_id": node_id, "port_id": "intent"}, "target": {"scope": "graph_output", "port_id": output_id}, "binding": {"kind": "single"}},
        ])
    stop_parameters = {"rate": "0.05"} if stop_parameters is None else stop_parameters
    take_parameters = {"rate": "0.15"} if take_parameters is None else take_parameters
    protection_nodes = [("stop", stop_name, stop_parameters), ("take", take_name, take_parameters)]
    if omit_take:
        protection_nodes.pop()
    if duplicate_stop:
        protection_nodes.append(("stop-duplicate", stop_name, stop_parameters))
    needs_distance = any(
        monitoring_intent_v2.PROTECTION_SPECS[name]["input"] == "distance"
        for _node_id, name, _parameters in protection_nodes
    )
    for node_id, name, parameters in protection_nodes:
        key = monitoring_intent_v2.component_key(name)
        nodes.append({"node_id": node_id, "component": {"component_id": key[0], "component_version": key[1]}, "parameters": parameters})
        outputs.append(_output_port(node_id, monitoring_intent_v2.V2_COMPONENTS[key]))
        input_id = monitoring_intent_v2.PROTECTION_SPECS[name]["input"]
        input_source = (
            {"scope": "graph_input", "port_id": "distance"}
            if input_id == "distance"
            else {"scope": "node", "node_id": "condition", "port_id": "out"}
        )
        edges.extend([
            {"edge_id": f"input-{node_id}", "source": input_source, "target": {"scope": "node", "node_id": node_id, "port_id": input_id}, "binding": {"kind": "single"}},
            {"edge_id": f"{node_id}-output", "source": {"scope": "node", "node_id": node_id, "port_id": "protection"}, "target": {"scope": "graph_output", "port_id": node_id}, "binding": {"kind": "single"}},
        ])
    graph_inputs = [_port("condition", "input", "boolean")]
    if needs_distance:
        graph_inputs.append(_port("distance", "input", "monitoring.distance"))
    return {
        "format_version": 2,
        "strategy_id": "monitoring-transition-fixture",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Monitoring transition", "description": None, "tags": []},
        "graph_inputs": graph_inputs,
        "graph_outputs": outputs,
        "nodes": nodes,
        "edges": edges,
    }


def _baseline_protection(kind: ProtectionKind, value: str) -> ProtectionEvidence:
    return ProtectionEvidence(
        kind=kind, basis=ProtectionBasis.ABSOLUTE_PRICE,
        authored_component_id="fixture.initial", authored_component_version=1,
        authored_component_address=address("initial-component"),
        authored_contract_address=address("initial-contract"),
        authored_parameters_address=address("initial-parameters"),
        authored_value=value, units=ProtectionUnits.PRICE,
        resolved_value=value, resolution_address=address(f"initial-{kind.value}"),
        validity=FactValidity.VALID,
    )


def _facts(target: str = "BUY", *, previous_state=StrategyState.FLAT,
           second_target: str | None = None, omit_take: bool = False,
           event_second: int = 0, target_count: int = 1,
           stop_name: str = "FIXED_STOP_PERCENT", stop_parameters=None,
           take_name: str = "TAKE_PROFIT_PERCENT", take_parameters=None,
           duplicate_stop: bool = False):
    registry = _registry()
    graph = resolve_v2(_document(
        target, second_target=second_target, omit_take=omit_take,
        target_count=target_count, stop_name=stop_name,
        stop_parameters=stop_parameters, take_name=take_name,
        take_parameters=take_parameters, duplicate_stop=duplicate_stop,
    ), registry)
    data = compile_data_requirement_plan(graph, registry=registry)
    resource = compile_resource_plan(
        graph, data, registry, cache_bytes_upper_bound=1024,
        artifact_bytes_upper_bound=0, queue_concurrency_upper_bound=2,
    )
    conditional = next(value for value in data.requirements if value["authored_node_id"] == "dependent")
    ceiling = compile_schedule_resource_ceiling(
        history_bytes_upper_bound=1_000_000,
        memory_bytes_upper_bound=100_000_000,
        cache_bytes_upper_bound=10_000_000,
        queue_concurrency_upper_bound=8,
        event_rate_events=10,
        event_rate_per_seconds=1,
        policy_address=address("resource-ceiling"),
    )
    schedule = compile_evaluation_schedule(
        owner_id="owner-a", assignment_id="assignment-a",
        resolved_graph=graph, data_requirement_plan=data, resource_plan=resource,
        registry=registry, gate_node_id="gate",
        conditional_requirement_selector=canonical_conditional_requirement_selector(conditional),
        unit_contract_addresses={node.node_id: address(f"unit-{node.node_id}") for node in graph.nodes},
        event_unit_address=address("event-unit"), mode="research",
        trigger_rates={"completed_bar": {"events": 1, "per_seconds": 60}},
        resource_ceiling=ceiling,
    )
    event = admit_evaluation_event(
        schedule, trigger="completed_bar", observation_address=address(f"observation-{event_second}"),
        event_at=moment(event_second), completed_at=moment(event_second + 1),
        available_at=moment(event_second + 1), recorded_at=moment(event_second + 2),
        cutoff_at=moment(event_second + 2), unit_contract_address=address("event-unit"),
    )
    entry = EntryReference(
        kind=EntryReferenceKind.COMPLETED_EVENT_CLOSE,
        canonical_instrument_address=address("instrument"), value="100",
        currency="INR", observed_at=event.event_at,
        source_truth_address=address("market-truth"), validity=FactValidity.VALID,
    )
    previous = MonitoringStateSnapshot(
        owner_id="owner-a", assignment_id="assignment-a",
        canonical_instrument_address=entry.canonical_instrument_address,
        snapshot_sequence=0, predecessor_snapshot_address=None,
        strategy_state=previous_state, entry_reference=entry,
        stop_loss=_baseline_protection(ProtectionKind.STOP_LOSS, "90"),
        take_profit=_baseline_protection(ProtectionKind.TAKE_PROFIT, "120"),
        evaluation_event_address=address("initial-event"), effective_at=moment(-60),
    )
    spec = MonitoringAssignmentSpec(
        assignment_id="assignment-a", project_id="project-a",
        strategy_id="strategy-a", graph_version_address=graph.authored_ir_address,
        resolved_graph_address=graph.resolved_graph_address,
        registry_address=graph.registry_snapshot_address,
        implementation_closure_address=graph.implementation_closure_address,
        research_admission_address=address("admission"),
        static_scope_revision_address=address("static-scope"),
        role_binding_address=address("role"), data_connection_id=1,
        capability_profile_address=address("capability"),
        resource_plan_address=resource.plan_address,
        evaluation_trigger_address=schedule.schedule_address,
        state_reset_policy_address=address("reset-policy"),
    )
    assignment = MonitoringAssignment(
        owner_id="owner-a", spec=spec, optimistic_revision=2,
        lifecycle_state="ACTIVE", current_state_snapshot_address=previous.address,
        created_at=moment(-120), updated_at=moment(-60), withdrawn_at=None,
    )
    return registry, graph, schedule, event, entry, previous, assignment


def _distance_input(state="VALID"):
    return monitoring_intent_v2.verified_distance(
        value="5" if state == "VALID" else None,
        units="PRICE_POINTS", source_component_id="analytical.atr",
        source_component_version=2,
        source_component_address=address("atr-component"),
        source_contract_address=address("atr-contract"),
        validity_state=state,
    )


def _compile(*, requested=True, distance_state="VALID", **fact_changes):
    registry, graph, schedule, event, entry, previous, assignment = _facts(**fact_changes)
    inputs = {"condition": requested}
    if "distance" in graph.graph_inputs:
        inputs["distance"] = _distance_input(distance_state)
    return subject.compile_monitoring_transition(
        assignment=assignment, previous_snapshot=previous,
        schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
        inputs=inputs, entry_reference=entry,
        display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
        dataset_address=address("dataset"),
    )


def test_buy_alert_resolves_exact_user_authored_sl_and_tp():
    result = _compile(target="BUY")
    assert result.signal_event.action is SignalAction.BUY
    assert result.next_snapshot.strategy_state is StrategyState.LONG
    assert result.signal_event.entry_reference.value == "100"
    assert result.signal_event.stop_loss.authored_value == "0.05"
    assert result.signal_event.stop_loss.resolved_value == "95"
    assert result.signal_event.take_profit.authored_value == "0.15"
    assert result.signal_event.take_profit.resolved_value == "115"
    assert isinstance(result.alert_result, AlertDerived)
    assert result.alert_result.alert.monitoring_event_address == result.signal_event.address


def test_sell_alert_keeps_short_stop_above_and_target_below_entry():
    result = _compile(target="SELL")
    assert result.signal_event.action is SignalAction.SELL
    assert result.next_snapshot.strategy_state is StrategyState.SHORT
    assert result.signal_event.stop_loss.resolved_value == "105"
    assert result.signal_event.take_profit.resolved_value == "85"
    assert isinstance(result.alert_result, AlertDerived)


def test_exit_alert_returns_flat_from_long_with_direction_aware_geometry():
    result = _compile(target="CLOSE_POSITION", previous_state=StrategyState.LONG)
    assert result.signal_event.action is SignalAction.EXIT
    assert result.next_snapshot.strategy_state is StrategyState.FLAT
    assert result.signal_event.stop_loss.resolved_value == "95"
    assert result.signal_event.take_profit.resolved_value == "115"
    assert isinstance(result.alert_result, AlertDerived)


def test_false_target_is_explicit_hold_and_retains_previous_protection():
    result = _compile(target="BUY", requested=False)
    assert result.signal_event.action is SignalAction.HOLD
    assert result.next_snapshot.strategy_state is StrategyState.FLAT
    assert result.next_snapshot.stop_loss.resolved_value == "90"
    assert result.next_snapshot.take_profit.resolved_value == "120"
    assert result.alert_result == NoAlert(result.signal_event.address, NoAlertCode.HOLD)


def test_multiple_requested_targets_refuse_instead_of_picking_one():
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        _compile(target="BUY", second_target="SELL")
    assert caught.value.code is subject.MonitoringEvaluationCode.TARGET_AMBIGUOUS


def test_transition_requires_paired_active_stop_and_take_profit():
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        _compile(target="BUY", omit_take=True)
    assert caught.value.code is subject.MonitoringEvaluationCode.PROTECTION_MISSING


def test_repeated_target_is_explicit_hold_with_updated_protection_evidence():
    result = _compile(target="BUY", previous_state=StrategyState.LONG)
    assert result.signal_event.action is SignalAction.HOLD
    assert result.signal_event.repeated_target_state is True
    assert result.signal_event.reason_code == "REPEATED_TARGET_STATE"
    assert result.next_snapshot.strategy_state is StrategyState.LONG
    assert result.next_snapshot.stop_loss.resolved_value == "95"
    assert result.next_snapshot.take_profit.resolved_value == "115"
    assert result.alert_result == NoAlert(result.signal_event.address, NoAlertCode.HOLD)


def test_invalid_short_target_geometry_refuses_before_event_authorship():
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        _compile(target="SELL", take_parameters={"rate": "1.5"})
    assert caught.value.code is subject.MonitoringEvaluationCode.PROTECTION_INVALID


def test_paused_assignment_cannot_author_a_transition():
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    paused = replace(assignment, lifecycle_state="PAUSED")
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=paused, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": True}, entry_reference=entry,
            display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.ASSIGNMENT_INACTIVE


def test_resolved_graph_address_tamper_refuses_before_evaluation():
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    object.__setattr__(graph, "resolved_graph_address", address("forged-graph"))
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=assignment, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": True}, entry_reference=entry,
            display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.GRAPH_INVALID


def test_poisoned_registry_proxy_refuses_before_any_callable_runs(monkeypatch):
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    calls = []
    real_evaluate = subject.evaluate_v2

    class RegistryProxy:
        registry_snapshot_address = registry.registry_snapshot_address
        v2_components = registry.v2_components
        v2_implementations = MappingProxyType({
            **registry.v2_implementations,
            ("fixture.valid_condition", 1): lambda _parameters, _inputs: {
                "out": validity.valid(True)
            },
        })

        def __getattr__(self, name):
            return getattr(registry, name)

    def counted(*args, **kwargs):
        calls.append(True)
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(subject, "evaluate_v2", counted)
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=assignment, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph,
            registry=RegistryProxy(), inputs={"condition": False},
            entry_reference=entry, display_symbol="ABC",
            provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.AUTHORITY_MISMATCH
    assert calls == []


def test_mutated_exact_registry_callable_map_refuses_before_evaluation():
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    poisoned = {
        **registry.v2_implementations,
        ("fixture.valid_condition", 1): lambda _parameters, _inputs: {
            "out": validity.valid(True)
        },
    }
    object.__setattr__(registry, "_v2_implementations", MappingProxyType(poisoned))
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=assignment, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": False}, entry_reference=entry,
            display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.AUTHORITY_MISMATCH


def test_forged_evaluator_output_authorship_refuses(monkeypatch):
    real_evaluate = subject.evaluate_v2

    def forged(*args, **kwargs):
        values = dict(real_evaluate(*args, **kwargs))
        target = dict(values["target-0"])
        target["authored"] = {
            **target["authored"],
            "component_address": address("forged-component"),
        }
        values["target-0"] = target
        return MappingProxyType(values)

    monkeypatch.setattr(subject, "evaluate_v2", forged)
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        _compile(target="BUY")
    assert caught.value.code is subject.MonitoringEvaluationCode.OUTPUT_INVALID


def test_invalid_input_refuses_as_evaluation_not_hold():
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=assignment, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": validity.invalid(validity.ValidityState.STALE)},
            entry_reference=entry, display_symbol="ABC",
            provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.EVALUATION_REFUSED


def test_unsafe_display_symbol_refuses_before_fact_creation():
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=assignment, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": True}, entry_reference=entry,
            display_symbol="ABC\nleak", provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.OUTPUT_INVALID


def test_graph_output_resource_bound_below_at_and_first_above():
    for target_count in (61, 62):
        result = _compile(target="BUY", target_count=target_count, requested=False)
        assert result.signal_event.action is SignalAction.HOLD
    calls = []
    real_evaluate = subject.evaluate_v2

    def counted(*args, **kwargs):
        calls.append(True)
        return real_evaluate(*args, **kwargs)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(subject, "evaluate_v2", counted)
        with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
            _compile(target="BUY", target_count=63, requested=False)
    assert caught.value.code is subject.MonitoringEvaluationCode.OUTPUT_INVALID
    assert calls == []


@pytest.mark.parametrize(
    "target,stop_name,stop_parameters,take_name,take_parameters,expected_stop,expected_take",
    [
        ("BUY", "POINT_STOP", {"distance": "5"}, "RISK_REWARD_TARGET", {"ratio": "3"}, "95", "115"),
        ("SELL", "ATR_STOP", {"multiplier": "1"}, "RISK_REWARD_TARGET", {"ratio": "3"}, "105", "85"),
    ],
)
def test_actual_v2_point_and_verified_distance_geometry(
    target, stop_name, stop_parameters, take_name, take_parameters,
    expected_stop, expected_take,
):
    result = _compile(
        target=target, stop_name=stop_name, stop_parameters=stop_parameters,
        take_name=take_name, take_parameters=take_parameters,
    )
    assert result.signal_event.stop_loss.resolved_value == expected_stop
    assert result.signal_event.take_profit.resolved_value == expected_take
    assert isinstance(result.alert_result, AlertDerived)


def test_invalid_verified_distance_refuses_as_evaluation_not_hold():
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        _compile(
            target="BUY", stop_name="ATR_STOP", stop_parameters={"multiplier": "1"},
            take_name="RISK_REWARD_TARGET", take_parameters={"ratio": "3"},
            distance_state="STALE",
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.EVALUATION_REFUSED


def test_duplicate_active_protection_refuses():
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        _compile(target="BUY", duplicate_stop=True)
    assert caught.value.code is subject.MonitoringEvaluationCode.PROTECTION_AMBIGUOUS


def test_assignment_schedule_and_current_state_are_exact_authority_inputs():
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    foreign = replace(assignment, owner_id="owner-b")
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=foreign, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": True}, entry_reference=entry,
            display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.STATE_INVALID


@pytest.mark.parametrize(
    "field",
    [
        "graph_version_address", "resolved_graph_address", "registry_address",
        "implementation_closure_address", "resource_plan_address",
        "evaluation_trigger_address",
    ],
)
def test_every_assignment_schedule_binding_mismatch_refuses(field):
    registry, graph, schedule, event, entry, previous, assignment = _facts()
    forged_spec = replace(assignment.spec, **{field: address(f"forged-{field}")})
    forged = replace(assignment, spec=forged_spec)
    with pytest.raises(subject.MonitoringEvaluationRefusal) as caught:
        subject.compile_monitoring_transition(
            assignment=forged, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={"condition": True}, entry_reference=entry,
            display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
            dataset_address=address("dataset"),
        )
    assert caught.value.code is subject.MonitoringEvaluationCode.AUTHORITY_MISMATCH


def test_canonical_v2_evaluator_is_called_exactly_once(monkeypatch):
    real_evaluate = subject.evaluate_v2
    calls = []

    def counted(*args, **kwargs):
        calls.append((args, kwargs))
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(subject, "evaluate_v2", counted)
    result = _compile(target="BUY")
    assert isinstance(result.alert_result, AlertDerived)
    assert len(calls) == 1


def test_replay_is_exact_and_appending_later_event_cannot_rewrite_prefix():
    first = _compile(target="BUY", event_second=0)
    replay = _compile(target="BUY", event_second=0)
    later = _compile(target="BUY", requested=False, event_second=10)
    assert first == replay
    assert first.signal_event.address == replay.signal_event.address
    assert first.next_snapshot.address == replay.next_snapshot.address
    assert first.signal_event.address != later.signal_event.address
    assert first.signal_event.to_dict() == replay.signal_event.to_dict()


def test_second_event_chains_from_first_successor_without_rewriting_prefix():
    registry, graph, schedule, event, entry, previous, assignment = _facts(target="BUY")
    first = subject.compile_monitoring_transition(
        assignment=assignment, previous_snapshot=previous,
        schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
        inputs={"condition": True}, entry_reference=entry,
        display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
        dataset_address=address("dataset"),
    )
    first_event_bytes = first.signal_event.canonical_bytes
    later_event = admit_evaluation_event(
        schedule, trigger="completed_bar", observation_address=address("observation-later"),
        event_at=moment(10), completed_at=moment(11), available_at=moment(11),
        recorded_at=moment(12), cutoff_at=moment(12),
        unit_contract_address=address("event-unit"),
    )
    later_entry = replace(entry, value="137", observed_at=later_event.event_at)
    advanced_assignment = replace(
        assignment,
        optimistic_revision=assignment.optimistic_revision + 1,
        current_state_snapshot_address=first.next_snapshot.address,
        updated_at=later_event.event_at,
    )
    second = subject.compile_monitoring_transition(
        assignment=advanced_assignment, previous_snapshot=first.next_snapshot,
        schedule=schedule, evaluation_event=later_event, graph=graph, registry=registry,
        inputs={"condition": False}, entry_reference=later_entry,
        display_symbol="ABC", provider_evidence_address=address("provider-evidence"),
        dataset_address=address("dataset"),
    )
    assert second.next_snapshot.predecessor_snapshot_address == first.next_snapshot.address
    assert second.signal_event.state_before_address == first.next_snapshot.address
    assert second.next_snapshot.entry_reference == first.next_snapshot.entry_reference
    assert second.signal_event.entry_reference == first.signal_event.entry_reference
    assert first.signal_event.canonical_bytes == first_event_bytes
    assert second.signal_event.address != first.signal_event.address


@pytest.mark.parametrize('previous_state,target,requested', [
    (StrategyState.LONG, 'BUY', False), (StrategyState.LONG, 'BUY', True),
    (StrategyState.SHORT, 'SELL', False), (StrategyState.SHORT, 'SELL', True),
    (StrategyState.LONG, 'CLOSE_POSITION', True),
    (StrategyState.SHORT, 'CLOSE_POSITION', True),
])
def test_entry_reference_is_retained_while_holding_or_exiting(previous_state, target, requested):
    registry, graph, schedule, event, entry, previous, assignment = _facts(
        target=target, previous_state=previous_state)
    held_entry = replace(entry, observed_at=moment(-60), source_truth_address=address('entry-source'))
    previous = replace(previous, entry_reference=held_entry)
    assignment = replace(assignment, current_state_snapshot_address=previous.address)
    current_close = replace(entry, value='137', source_truth_address=address('later-price-source'))
    result = subject.compile_monitoring_transition(assignment=assignment, previous_snapshot=previous,
        schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
        inputs={'condition':requested}, entry_reference=current_close, display_symbol='ABC',
        provider_evidence_address=address('provider'), dataset_address=address('dataset'))
    assert result.next_snapshot.entry_reference == held_entry
    assert result.signal_event.entry_reference == held_entry
    if requested:
        expected = ('95', '115') if previous_state is StrategyState.LONG else ('105', '85')
        assert (result.next_snapshot.stop_loss.resolved_value, result.next_snapshot.take_profit.resolved_value) == expected
    else:
        assert result.next_snapshot.stop_loss == previous.stop_loss
        assert result.next_snapshot.take_profit == previous.take_profit
    assert result.signal_event.action is (SignalAction.EXIT if target == 'CLOSE_POSITION' else SignalAction.HOLD)


@pytest.mark.parametrize('previous_state,target', [
    (StrategyState.FLAT, 'BUY'), (StrategyState.FLAT, 'SELL'),
    (StrategyState.SHORT, 'BUY'), (StrategyState.LONG, 'SELL'),
])
def test_entry_reference_is_replaced_for_new_entries_and_reversals(previous_state, target):
    registry, graph, schedule, event, entry, previous, assignment = _facts(
        target=target, previous_state=previous_state)
    current_entry = replace(entry, value='137', source_truth_address=address('new-entry-source'))
    result = subject.compile_monitoring_transition(assignment=assignment, previous_snapshot=previous,
        schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
        inputs={'condition':True}, entry_reference=current_entry, display_symbol='ABC',
        provider_evidence_address=address('provider'), dataset_address=address('dataset'))
    assert result.next_snapshot.entry_reference == current_entry
    assert result.signal_event.entry_reference == current_entry
    expected = ('130.15', '157.55') if target == 'BUY' else ('143.85', '116.45')
    assert (result.next_snapshot.stop_loss.resolved_value, result.next_snapshot.take_profit.resolved_value) == expected
    assert isinstance(result.alert_result, AlertDerived)


def test_entry_reference_cannot_replace_missing_held_entry_with_a_later_price():
    registry, graph, schedule, event, entry, previous, assignment = _facts(previous_state=StrategyState.LONG)
    missing = replace(entry, value=None, validity=FactValidity.MISSING)
    previous = replace(previous, entry_reference=missing)
    assignment = replace(assignment, current_state_snapshot_address=previous.address)
    with pytest.raises(subject.MonitoringEvaluationRefusal) as failure:
        subject.compile_monitoring_transition(assignment=assignment, previous_snapshot=previous,
            schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
            inputs={'condition':True}, entry_reference=entry, display_symbol='ABC',
            provider_evidence_address=address('provider'), dataset_address=address('dataset'))
    assert failure.value.code is subject.MonitoringEvaluationCode.STATE_INVALID


def test_source_has_no_provider_execution_database_network_or_money_import():
    tree = ast.parse(SOURCE.read_text())
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    }
    forbidden = (
        "app.providers", "app.engine", "app.execution", "app.ledger",
        "app.api", "app.db", "app.monitoring.repository", "sqlalchemy",
        "requests", "httpx", "socket", "websocket",
    )
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    source = SOURCE.read_text()
    for token in ("order", "position", "capital", "pnl", "credential", "broker"):
        assert f"app.{token}" not in source.lower()


def test_fresh_import_closure_excludes_repository_database_and_sqlalchemy():
    code = f"""
import sys
sys.path.insert(0, {str(ROOT / 'paper-trader' / 'backend')!r})
import app.monitoring.evaluation
blocked = [name for name in sys.modules if (
    name == 'app.monitoring.repository' or name == 'app.db' or
    name.startswith('app.db.') or name == 'sqlalchemy' or name.startswith('sqlalchemy.')
)]
assert blocked == [], blocked
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=False, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def _price_prefix(values=(100.0, 101.0)):
    import pandas as pd
    return pd.Series(values, index=pd.date_range('2026-08-31T09:15:00Z', periods=len(values), freq='min'))


def _prefix_boundary(inputs, cutoff=None, terminal=None):
    from types import SimpleNamespace
    return subject._frozen_inputs(SimpleNamespace(graph_inputs={'frame': {}}), inputs,
        cutoff_at=cutoff or moment(600), terminal_at=terminal or moment(60))


def test_completed_price_inputs_are_detached_without_relaxing_alert_outputs():
    source = _price_prefix()
    expected_index = source.index.copy(deep=True)
    copied = _prefix_boundary({'frame': {'close': source, 'configuration': (True, validity.valid(2))}})
    assert copied['frame']['close'].equals(source)
    assert copied['frame']['configuration'] == (True, validity.valid(2))
    source.iloc[0] = 999
    raw_index = source.index.asi8
    raw_index.setflags(write=True)
    raw_index[0] += 1
    assert copied['frame']['close'].iloc[0] == 100
    assert copied['frame']['close'].index.equals(expected_index)
    with pytest.raises(TypeError):
        copied['frame']['close'] = source
    with pytest.raises(subject.MonitoringEvaluationRefusal):
        subject._plain(copied)
    with pytest.raises(subject.MonitoringEvaluationRefusal):
        subject._frozen_inputs(type('LegacyBoundary', (), {'graph_inputs': {'frame': {}}})(),
            {'frame': {'close': source}})


def test_completed_price_prefix_validates_the_detached_clock():
    import pandas as pd
    source = _price_prefix()
    original_values = source.tolist()

    def mutate_during_copy():
        source.index = pd.DatetimeIndex([moment(601), moment(60)])
        return original_values

    source.tolist = mutate_during_copy
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='clock is invalid'):
        _prefix_boundary({'frame': {'close': source}})


@pytest.mark.parametrize('change', ['empty', 'naive', 'duplicate', 'reverse', 'future', 'nat', 'nan', 'text'])
def test_completed_price_prefix_refuses_invalid_clocks_and_cells(change):
    import pandas as pd
    source = _price_prefix()
    if change == 'empty':
        source = source.iloc[:0]
    elif change == 'naive':
        source.index = source.index.tz_localize(None)
    elif change == 'duplicate':
        source.index = pd.DatetimeIndex([source.index[0], source.index[0]])
    elif change == 'reverse':
        source = source.iloc[::-1]
    elif change == 'future':
        source.index = source.index + timedelta(days=1)
    elif change == 'nat':
        source.index = pd.DatetimeIndex([source.index[0], pd.NaT])
    elif change == 'nan':
        source.iloc[0] = float('nan')
    else:
        source = pd.Series(['100', '101'], index=source.index)
    with pytest.raises(subject.MonitoringEvaluationRefusal):
        _prefix_boundary({'frame': {'close': source}})


def test_completed_price_prefix_rejects_misaligned_columns_and_excessive_size():
    import pandas as pd
    close = _price_prefix()
    high = _price_prefix()
    high.index = high.index + timedelta(seconds=1)
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='not aligned'):
        _prefix_boundary({'frame': {'close': close, 'high': high}})
    oversized = pd.Series(100.0, index=pd.date_range('2026-01-01T00:00:00Z',
        periods=monitoring_intent_v2.MAX_PREFIX_EVENTS + 1, freq='s'))

    def unbounded_copy():
        raise AssertionError('An oversized prefix must be rejected before materialization')

    oversized.tolist = unbounded_copy
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='prefix bound'):
        _prefix_boundary({'frame': {'close': oversized}})
    growing = _price_prefix()
    growing.tolist = lambda: [100.0] * (monitoring_intent_v2.MAX_PREFIX_EVENTS + 1)
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='prefix bound'):
        _prefix_boundary({'frame': {'close': growing}})


def test_completed_price_prefix_requires_series_and_closed_input_boundaries():
    for inputs in ({'frame': {'close': (100, 101)}}, {'other': {}},
                   {'frame': {1: _price_prefix()}}, {'frame': {'': _price_prefix()}},
                   {'frame': {'close': object()}}):
        with pytest.raises(subject.MonitoringEvaluationRefusal):
            _prefix_boundary(inputs)
    value = _price_prefix()
    for _ in range(subject.MAX_INPUT_DEPTH + 1):
        value = (value,)
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='depth'):
        _prefix_boundary({'frame': {'close': value}})


@pytest.mark.parametrize('values', [(100.0,), (100.0, 101.0, 102.0)])
def test_completed_prefix_cannot_substitute_an_older_or_newer_known_bar(values):
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='admitted observation'):
        _prefix_boundary({'frame': {'close': _price_prefix(values)}})


def test_completed_prefix_preserves_subsecond_availability_and_cutoff():
    source = _price_prefix()
    source.index = source.index + timedelta(microseconds=123456)
    available = moment(60) + timedelta(microseconds=123456)
    copied = _prefix_boundary({'frame': {'close': source}}, cutoff=available, terminal=available)
    assert copied['frame']['close'].index[-1].to_pydatetime() == available
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='cutoff'):
        _prefix_boundary({'frame': {'close': source}},
            cutoff=available - timedelta(microseconds=1), terminal=available)
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='admitted observation'):
        _prefix_boundary({'frame': {'close': source}}, cutoff=available,
            terminal=available + timedelta(microseconds=1))


def test_completed_prefix_preserves_invalid_final_condition_without_fallback():
    source = _price_prefix((validity.valid(True), validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY)))
    copied = _prefix_boundary({'frame': {'condition': source}})['frame']['condition']
    assert copied.iloc[-1].state is validity.ValidityState.INSUFFICIENT_HISTORY
    with pytest.raises(monitoring_intent_v2.MonitoringIntentRefusal):
        monitoring_intent_v2.final_prefix_condition({}, {'series': copied})


@pytest.fixture(scope='module')
def registered_completed_input_cases():
    from app.ir.library import REGISTRY
    from tests.test_v0_evaluation_schedule import _completed_bar_authority_cases
    return _completed_bar_authority_cases(REGISTRY)


@pytest.mark.parametrize('preset', ['trend_impulse_v3', 'expanding_z_v4'])
def test_real_registered_saved_presets_accept_completed_price_history(preset, registered_completed_input_cases):
    import pandas as pd
    from types import SimpleNamespace
    from tests.test_v0_evaluation_schedule import _completed_schedule
    facts = registered_completed_input_cases[preset]
    registry, graph, _, _ = facts
    schedule = _completed_schedule(facts)
    index = pd.date_range('2026-08-31T09:15:00Z', periods=300, freq='min')
    close = pd.Series([100.0 + position / 4 for position in range(300)], index=index)
    frame = {'close': close}
    if preset == 'expanding_z_v4':
        frame.update(high=close + 1, low=close - 1)
    inputs = {'frame': frame}
    outputs = subject._evaluate_monitoring_inputs(graph, schedule,
        SimpleNamespace(cutoff_at=index[-1].to_pydatetime() + timedelta(microseconds=1),
            completed_at=index[-1].to_pydatetime(),
            available_at=index[-1].to_pydatetime() + timedelta(microseconds=1)),
        inputs, registry)
    assert len(outputs) == 4
    assert all(type(value) is pd.Series and value.index.equals(index) for value in outputs.values())
    # Raw strategy series still need explicitly authored monitoring intent;
    # accepting real price inputs must not admit arbitrary alert outputs.
    with pytest.raises(subject.MonitoringEvaluationRefusal):
        subject._closed_outputs(outputs)


def test_delayed_evaluation_cannot_extend_the_source_freshness_deadline():
    registry, graph, schedule, _, entry, previous, assignment = _facts()
    event = admit_evaluation_event(schedule, trigger='completed_bar', observation_address=address('late-arrival'),
        event_at=moment(0), completed_at=moment(1), available_at=moment(50),
        recorded_at=moment(51), cutoff_at=moment(52), unit_contract_address=schedule.event_unit_address)
    result = subject.compile_monitoring_transition(assignment=assignment, previous_snapshot=previous,
        schedule=schedule, evaluation_event=event, graph=graph, registry=registry,
        inputs={'condition': True}, entry_reference=entry, display_symbol='ABC',
        provider_evidence_address=address('provider-evidence'), dataset_address=address('dataset'))
    assert result.signal_event.valid_until == moment(61)
    assert result.alert_result.alert.valid_until == moment(61)
    assert (result.signal_event.valid_until - result.signal_event.knowledge_cutoff_at).total_seconds() == 9


def _initial_state_arguments(**changes):
    from app.market_truth.identity import CanonicalPhysicalInstrument
    registry, graph, schedule, event, entry, _, assignment = _facts(**changes)
    instrument = CanonicalPhysicalInstrument('synthetic', 'initial-state', 'XNSE', 'EQUITY', 'SPOT', 'INR', None)
    return dict(assignment=replace(assignment, current_state_snapshot_address=None), graph=graph,
        registry=registry, schedule=schedule, evaluation_event=event, instrument=instrument,
        source_truth_address=entry.source_truth_address)


def test_initial_monitoring_state_retains_authored_protection_without_fabricated_prices():
    from app.monitoring.initial_state import compile_initial_monitoring_state
    arguments = _initial_state_arguments(stop_parameters={'rate':'0.03'}, take_parameters={'rate':'0.07'})
    initial = compile_initial_monitoring_state(**arguments)
    assert initial.strategy_state is StrategyState.FLAT
    assert initial.snapshot_sequence == 0 and initial.predecessor_snapshot_address is None
    assert initial.entry_reference.validity is FactValidity.MISSING and initial.entry_reference.value is None
    for evidence, name, rate in ((initial.stop_loss,'FIXED_STOP_PERCENT','0.03'),
                                (initial.take_profit,'TAKE_PROFIT_PERCENT','0.07')):
        assert evidence.validity is FactValidity.MISSING and evidence.resolved_value is None
        assert evidence.authored_value == rate
        authored = subject._expected_authored(name, {'rate':rate})
        assert evidence.authored_component_address == authored['component_address']
        assert evidence.authored_parameters_address == authored['parameters_address']
    assert compile_initial_monitoring_state(**arguments) == initial
    assert initial.evaluation_event_address == arguments['evaluation_event'].event_address
    assert initial.entry_reference.source_truth_address == arguments['source_truth_address']


@pytest.mark.parametrize('change', ['existing_state','paused','withdrawn','foreign_owner','foreign_graph','forged_event'])
def test_initial_monitoring_state_refuses_changed_assignment_and_event_authority(change):
    from app.monitoring.initial_state import compile_initial_monitoring_state
    arguments = _initial_state_arguments()
    assignment = arguments['assignment']
    if change == 'existing_state':
        arguments['assignment'] = replace(assignment,current_state_snapshot_address=address('existing'))
    if change == 'paused':
        arguments['assignment'] = replace(assignment,lifecycle_state='PAUSED')
    if change == 'withdrawn':
        arguments['assignment'] = replace(assignment,withdrawn_at=moment(0))
    if change == 'foreign_owner':
        arguments['assignment'] = replace(assignment,owner_id='foreign-owner')
    if change == 'foreign_graph':
        arguments['assignment'] = replace(assignment,spec=replace(assignment.spec,graph_version_address=address('foreign')))
    if change == 'forged_event':
        from copy import copy
        arguments['evaluation_event'] = copy(arguments['evaluation_event'])
        object.__setattr__(arguments['evaluation_event'], 'observation_address', address('forged'))
    with pytest.raises(subject.MonitoringEvaluationRefusal):
        compile_initial_monitoring_state(**arguments)


@pytest.mark.parametrize('changes', [{'omit_take':True},{'duplicate_stop':True},{'target_count':0}])
def test_initial_monitoring_state_requires_unambiguous_authored_protection(changes):
    from app.monitoring.initial_state import compile_initial_monitoring_state
    with pytest.raises(subject.MonitoringEvaluationRefusal):
        compile_initial_monitoring_state(**_initial_state_arguments(**changes))


def test_initial_monitoring_state_can_hold_then_enter_using_actual_authored_protection():
    from app.monitoring.initial_state import compile_initial_monitoring_state
    arguments = _initial_state_arguments(stop_parameters={'rate':'0.03'}, take_parameters={'rate':'0.07'})
    initial = compile_initial_monitoring_state(**arguments)
    assignment = replace(arguments['assignment'], current_state_snapshot_address=initial.address)
    common = dict(schedule=arguments['schedule'], graph=arguments['graph'], registry=arguments['registry'],
        display_symbol='SYNTHETIC', provider_evidence_address=address('retained-provider'), dataset_address=address('dataset'))
    observed = replace(initial.entry_reference, value='100', validity=FactValidity.VALID)
    hold = subject.compile_monitoring_transition(**common, assignment=assignment, previous_snapshot=initial,
        evaluation_event=arguments['evaluation_event'], inputs={'condition':False}, entry_reference=observed)
    assert hold.signal_event.action is SignalAction.HOLD
    assert hold.next_snapshot.stop_loss.validity is FactValidity.MISSING
    assert hold.alert_result == NoAlert(hold.signal_event.address, NoAlertCode.HOLD)
    event = admit_evaluation_event(arguments['schedule'], trigger='completed_bar', observation_address=address('next-bar'),
        event_at=moment(60), completed_at=moment(61), available_at=moment(61), recorded_at=moment(62),
        cutoff_at=moment(62), unit_contract_address=arguments['schedule'].event_unit_address)
    entry = replace(initial.entry_reference, observed_at=moment(60), value='100', validity=FactValidity.VALID)
    transition = subject.compile_monitoring_transition(**common,
        assignment=replace(assignment,current_state_snapshot_address=hold.next_snapshot.address),
        previous_snapshot=hold.next_snapshot, evaluation_event=event, inputs={'condition':True}, entry_reference=entry)
    assert transition.signal_event.action is SignalAction.BUY
    assert transition.next_snapshot.stop_loss.resolved_value == '97'
    assert transition.next_snapshot.take_profit.resolved_value == '107'
    assert isinstance(transition.alert_result, AlertDerived)


def _authored_preset_monitoring_document(preset):
    """Explicit test revision: retain preset math and author one long-entry alert."""
    from app.ir.original_strategy_presets import instantiate_preset
    document = instantiate_preset(preset, 'authored-monitoring-' + preset)
    source = next(edge['source'] for edge in document['edges']
                  if edge['target'] == {'scope': 'graph_output', 'port_id': 'longEntry'})
    document['edges'] = [edge for edge in document['edges']
                         if edge['target']['scope'] != 'graph_output']
    document['graph_outputs'] = []
    document['nodes'].append({'node_id': 'alert_condition', 'component': {
        'component_id': 'monitoring.final_prefix_condition', 'component_version': 1}, 'parameters': {}})
    document['edges'].append({'edge_id': 'alert_projection', 'source': source,
        'target': {'scope': 'node', 'node_id': 'alert_condition', 'port_id': 'series'},
        'binding': {'kind': 'single'}})
    for name, operation, parameters, port in (
        ('alert_buy', 'BUY', {}, 'intent'),
        ('alert_stop', 'FIXED_STOP_PERCENT', {'rate': '0.01'}, 'protection'),
        ('alert_take', 'TAKE_PROFIT_PERCENT', {'rate': '0.02'}, 'protection'),
    ):
        component_id, version = monitoring_intent_v2.component_key(operation)
        document['nodes'].append({'node_id': name, 'component': {
            'component_id': component_id, 'component_version': version}, 'parameters': parameters})
        output = next(monitoring_intent_v2.node_contracts._plain(value)
                      for value in monitoring_intent_v2.descriptor(operation)['ports']
                      if value['direction'] == 'output')
        document['graph_outputs'].append({**output, 'port_id': name})
        document['edges'].extend([
            {'edge_id': name + '_condition', 'source': {'scope': 'node',
                'node_id': 'alert_condition', 'port_id': 'condition'},
             'target': {'scope': 'node', 'node_id': name, 'port_id': 'condition'},
             'binding': {'kind': 'single'}},
            {'edge_id': name + '_output', 'source': {'scope': 'node', 'node_id': name, 'port_id': port},
             'target': {'scope': 'graph_output', 'port_id': name}, 'binding': {'kind': 'single'}},
        ])
    return document


def _authored_completed_case(preset, registered_completed_input_cases):
    import math
    import pandas as pd
    from tests.test_v0_evaluation_schedule import _completed_bar_graph_authorities, _completed_schedule
    registry, original, _, _ = registered_completed_input_cases[preset]
    index = pd.date_range('2026-08-31T09:15:00Z', periods=300, freq='min')
    close = pd.Series([100 + 2 * math.sin(position / 7) + position / 50
                       for position in range(300)], index=index)
    frame = {'close': close}
    fields = ['CLOSE']
    if preset == 'expanding_z_v4':
        frame.update(high=close + 1, low=close - 1)
        fields.extend(['HIGH', 'LOW'])
    original_outputs = subject.evaluate_v2(original, {'frame': frame}, registry)
    candidates = [offset for offset, value in enumerate(original_outputs['longEntry'])
                  if value.state is validity.ValidityState.VALID and value.value is True]
    assert candidates, 'Synthetic price path must exercise the real preset long-entry rule'
    end = candidates[-1]
    prefix = {'frame': {key: value.iloc[:end + 1] for key, value in frame.items()}}
    facts = _completed_bar_graph_authorities(registry, _authored_preset_monitoring_document(preset), fields)
    _, graph, _, resource = facts
    schedule = _completed_schedule(facts, owner_id='owner-a', assignment_id='assignment-a')
    available = index[end].to_pydatetime()
    event = admit_evaluation_event(schedule, trigger='completed_bar', observation_address=address('preset-tail'),
        event_at=available - timedelta(minutes=1), completed_at=available,
        available_at=available + timedelta(microseconds=1),
        recorded_at=available + timedelta(microseconds=2), cutoff_at=available + timedelta(microseconds=3),
        unit_contract_address=schedule.event_unit_address)
    _, _, _, _, entry, previous, assignment = _facts(previous_state=StrategyState.FLAT)
    entry = replace(entry, value=str(float(close.iloc[end])), observed_at=event.completed_at)
    previous = replace(previous, effective_at=event.completed_at)
    spec = replace(assignment.spec, graph_version_address=graph.authored_ir_address,
        resolved_graph_address=graph.resolved_graph_address, registry_address=graph.registry_snapshot_address,
        implementation_closure_address=graph.implementation_closure_address,
        resource_plan_address=resource.plan_address, evaluation_trigger_address=schedule.schedule_address)
    assignment = replace(assignment, spec=spec, current_state_snapshot_address=previous.address)
    return dict(assignment=assignment, previous_snapshot=previous,
        schedule=schedule, evaluation_event=event, graph=graph, registry=registry, inputs=prefix,
        entry_reference=entry, display_symbol='ABC', provider_evidence_address=address('preset-tail'),
        dataset_address=address('preset-prefix')), facts


@pytest.fixture(scope='module')
def authored_completed_cases(registered_completed_input_cases):
    return {preset: _authored_completed_case(preset, registered_completed_input_cases)
            for preset in ('trend_impulse_v3', 'expanding_z_v4')}


@pytest.mark.parametrize('preset', ['trend_impulse_v3', 'expanding_z_v4'])
def test_real_preset_authored_intent_compiles_attributable_alert(preset, authored_completed_cases):
    """Pure integration only; fixture addresses do not establish provider admission."""
    arguments, _ = authored_completed_cases[preset]
    event, graph, registry = (arguments[key] for key in ('evaluation_event', 'graph', 'registry'))
    previous, assignment = arguments['previous_snapshot'], arguments['assignment']
    schedule = arguments['schedule']
    result = subject.compile_monitoring_transition(**arguments)
    assert result.signal_event.action is SignalAction.BUY
    assert result.next_snapshot.strategy_state is StrategyState.LONG
    assert isinstance(result.alert_result, AlertDerived)
    assert result.signal_event.graph_version_address == graph.authored_ir_address
    assert result.signal_event.evaluation_event_address == event.event_address
    assert result.alert_result.alert.monitoring_event_address == result.signal_event.address
    assert result.signal_event.event_at == result.signal_event.latest_data_at == event.completed_at
    assert result.next_snapshot.effective_at == event.completed_at
    assert result.signal_event.knowledge_cutoff_at == event.cutoff_at
    future = replace(previous, effective_at=event.completed_at + timedelta(microseconds=1))
    future_assignment = replace(assignment, current_state_snapshot_address=future.address)
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='predecessor state is from the future'):
        subject._verified_context(future_assignment, future, schedule, event, graph, registry)


def _completed_policy(facts, **changes):
    from app.monitoring.evaluation_policy import compile_monitoring_evaluation_policy
    resource = facts[3]
    values = dict(owner_id='owner-a', assignment_id='assignment-a',
        initial_resource_plan_address=resource.plan_address, maximum_age_seconds=30,
        history_bytes_upper_bound=sum(row['bytes_upper_bound'] for row in resource.document['history_requirements']),
        memory_bytes_upper_bound=resource.document['memory_bytes_upper_bound'],
        cache_bytes_upper_bound=resource.document['cache_bytes_upper_bound'],
        queue_concurrency_upper_bound=resource.document['queue_concurrency_upper_bound'],
        event_rate_events=1, event_rate_per_seconds=60)
    return compile_monitoring_evaluation_policy(**{**values, **changes})


def _policy_transition_arguments(arguments, facts, policy, **schedule_changes):
    from app.monitoring.evaluation_policy import monitoring_resource_ceiling
    from tests.test_v0_evaluation_schedule import _completed_schedule
    options = dict(owner_id='owner-a', assignment_id='assignment-a',
        resource_ceiling=monitoring_resource_ceiling(policy),
        freshness_ceiling_seconds=policy.document['maximum_age_seconds'])
    schedule = _completed_schedule(facts, **{**options, **schedule_changes})
    original = arguments['evaluation_event']
    clocks = {key: getattr(original, key) for key in
        ('event_at', 'completed_at', 'available_at', 'recorded_at', 'cutoff_at')}
    event = admit_evaluation_event(schedule, trigger='completed_bar',
        observation_address=original.observation_address,
        unit_contract_address=schedule.event_unit_address, **clocks)
    assignment = arguments['assignment']
    assignment = replace(assignment,
        spec=replace(assignment.spec, evaluation_trigger_address=policy.address))
    return {**arguments, 'assignment': assignment, 'schedule': schedule,
        'evaluation_event': event, 'evaluation_policy': policy}


def test_monitoring_policy_roundtrip_and_fresh_schedule_compile(authored_completed_cases):
    from app.monitoring.evaluation_policy import (
        load_monitoring_evaluation_policy, monitoring_policy_payload, monitoring_resource_ceiling,
    )
    arguments, facts = authored_completed_cases['trend_impulse_v3']
    policy = _completed_policy(facts)
    payload = monitoring_policy_payload(policy)
    assert load_monitoring_evaluation_policy(payload) == policy
    assert monitoring_resource_ceiling(policy).policy_address == policy.address
    assert 'resource_ceiling_address' not in payload
    bound = _policy_transition_arguments(arguments, facts, policy)
    result = subject.compile_monitoring_transition(**bound)
    assert result.signal_event.action is SignalAction.BUY
    assert result.signal_event.valid_until == bound['evaluation_event'].completed_at + timedelta(seconds=30)
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='assignment schedule binding differs'):
        subject._verified_context(bound['assignment'], bound['previous_snapshot'], bound['schedule'],
            bound['evaluation_event'], bound['graph'], bound['registry'])


def test_monitoring_policy_keeps_assignment_while_exact_dataset_plans_change(authored_completed_cases):
    """Binding fixtures prove per-manifest compilation, not provider acquisition."""
    from app.ir.incremental_runtime import accept_research_resource_plan
    from tests.test_indicator_accuracy_contract_assurance import context, input_facts
    arguments, facts = authored_completed_cases['trend_impulse_v3']
    registry, graph, old_data, old_resource = facts
    source = input_facts()['price_feed']
    source.update(fields=['CLOSE'], timeframe=60, derived_local=False,
        freshness={'maximum_age_seconds': 60}, dataset_manifest_address=address('next-manifest'),
        dataset_context_address=address('next-dataset-context'))
    bindings = context({'frame': source}, dataset=source['dataset_context_address'])
    data = compile_data_requirement_plan(graph, registry=registry, input_bindings=bindings)
    resource = accept_research_resource_plan(graph, data, registry, input_bindings=bindings).plan
    assert data.plan_address != old_data.plan_address
    assert resource.plan_address != old_resource.plan_address
    policy = _completed_policy(facts)
    first = _policy_transition_arguments(arguments, facts, policy)
    second = _policy_transition_arguments(arguments, (registry, graph, data, resource), policy)
    assert first['assignment'] == second['assignment']
    assert first['schedule'].schedule_address != second['schedule'].schedule_address
    second['dataset_address'] = source['dataset_manifest_address']
    result = subject.compile_monitoring_transition(**second)
    assert result.signal_event.dataset_address == source['dataset_manifest_address']
    assert result.signal_event.evaluation_event_address == second['evaluation_event'].event_address


@pytest.mark.parametrize('change', ['owner', 'assignment', 'initial_plan', 'policy_address'])
def test_monitoring_policy_rejects_foreign_assignment_bindings(change, authored_completed_cases):
    from app.monitoring.evaluation_policy import verify_monitoring_policy_schedule
    arguments, facts = authored_completed_cases['trend_impulse_v3']
    policy = _completed_policy(facts)
    bound = _policy_transition_arguments(arguments, facts, policy)
    assignment = bound['assignment']
    if change == 'owner':
        assignment = replace(assignment, owner_id='owner-b')
    else:
        field = {'assignment': 'assignment_id', 'initial_plan': 'resource_plan_address',
            'policy_address': 'evaluation_trigger_address'}[change]
        value = 'foreign-assignment' if change == 'assignment' else address('foreign-' + change)
        assignment = replace(assignment, spec=replace(assignment.spec, **{field: value}))
    with pytest.raises(ValueError, match='assignment policy binding differs'):
        verify_monitoring_policy_schedule(policy, assignment, bound['schedule'])


@pytest.mark.parametrize('change', ['freshness', 'rate', 'ceiling'])
def test_monitoring_policy_rejects_issued_schedule_outside_its_bounds(change, authored_completed_cases):
    from app.monitoring.evaluation_policy import verify_monitoring_policy_schedule, monitoring_resource_ceiling
    arguments, facts = authored_completed_cases['trend_impulse_v3']
    policy = _completed_policy(facts)
    changes = {}
    if change == 'freshness':
        changes['freshness_ceiling_seconds'] = None
    elif change == 'rate':
        changes['trigger_rates'] = {'completed_bar': {'events': 2, 'per_seconds': 120}}
    else:
        other = _completed_policy(facts, memory_bytes_upper_bound=policy.document['memory_bytes_upper_bound'] + 1)
        changes['resource_ceiling'] = monitoring_resource_ceiling(other)
    bound = _policy_transition_arguments(arguments, facts, policy, **changes)
    with pytest.raises(ValueError):
        verify_monitoring_policy_schedule(policy, bound['assignment'], bound['schedule'])
    with pytest.raises(subject.MonitoringEvaluationRefusal, match='assignment monitoring policy differs'):
        subject._verified_context(bound['assignment'], bound['previous_snapshot'], bound['schedule'],
            bound['evaluation_event'], bound['graph'], bound['registry'], policy)


@pytest.mark.parametrize('change', ['unknown', 'schema', 'address', 'negative', 'boolean', 'zero_rate'])
def test_monitoring_policy_retained_payload_is_closed(change, authored_completed_cases):
    from app.monitoring.evaluation_policy import load_monitoring_evaluation_policy, monitoring_policy_payload
    _, facts = authored_completed_cases['trend_impulse_v3']
    payload = monitoring_policy_payload(_completed_policy(facts))
    field, value = {
        'unknown': ('unrelated', True), 'schema': ('schema', 'monitoring-evaluation-policy/2'),
        'address': ('address', address('forged-policy')), 'negative': ('maximum_age_seconds', -1),
        'boolean': ('memory_bytes_upper_bound', True), 'zero_rate': ('event_rate_events', 0),
    }[change]
    payload[field] = value
    with pytest.raises(ValueError):
        load_monitoring_evaluation_policy(payload)


def _research_replay_inputs(risk_policy="none", *, stop=0.0, target=0.0, capital=10000.0):
    """Pure simulation inputs, deliberately not an admission or worker receipt."""
    from types import SimpleNamespace
    from app.ir.resource_plan import _canonical
    from app.monitoring.research_consumer import SCHEMA, _replay_policy
    from app.monitoring.research_replay_state import ResearchReplayState
    from research.data.canonical_dataset import instrument_key
    from research.orchestrator.v2_preparation import execution_policy
    address = "sha256:" + "a" * 64
    policy = execution_policy(capital, risk_policy, stop_loss_pct=stop, take_profit_pct=target)
    consumer = _canonical(SCHEMA, {"owner_id": "replay.owner", "assignment_id": "replay.assignment",
        **_replay_policy({"execution_policy": policy, "settings_snapshot": {"schema": "research-settings-snapshot/3"}})})
    state = ResearchReplayState("replay.owner", "replay.assignment", address, consumer.address, 0)
    instrument = SimpleNamespace(key=instrument_key(address), name=address, segment="NSE",
                                 lot_size=1, source="canonical_dataset")
    return state, consumer, instrument, policy


def _research_replay_bars(state):
    from app.monitoring.research_replay import ResearchReplayBar
    start = datetime(2026, 9, 7, 3, 45, tzinfo=timezone.utc)
    opens = [100.0, 101.0, 105.0, 99.0, 100.0, 99.0, 95.0, 101.0, 100.0]
    closes = [100.0, 102.0, 104.0, 99.0, 100.0, 98.0, 96.0, 101.0, 100.0]
    return [ResearchReplayBar(state.owner_id, state.canonical_instrument_address, 900,
        start + timedelta(minutes=15 * index), start + timedelta(minutes=15 * (index + 1)),
        opened, 130.0 if index == 1 else max(opened, close) + 1.0,
        60.0 if index == 5 else min(opened, close) - 1.0, close,
        long_entry=index in {0, 6}, short_entry=index in {2, 4},
        long_exit=index in {2, 7}, short_exit=index in {6, 7}, atr=2.0)
        for index, (opened, close) in enumerate(zip(opens, closes, strict=True))]


@pytest.mark.parametrize("risk_policy", ["none", "pine-v4-ratchet/1", "pine-v4-reversal/1"])
@pytest.mark.parametrize("stop,target", [(0.0, 0.0), (.01, 0.0), (0.0, .02), (.01, .02)])
@pytest.mark.parametrize("flip", [False, True])
def test_research_replay_restart_matches_original_replay_fills_charges_sizing_and_management(risk_policy, stop, target, flip):
    from dataclasses import asdict
    import pandas as pd
    from app.backtest import engine
    from app.monitoring.research_replay import advance_research_replay
    from app.monitoring.research_replay_state import ResearchReplayState
    from app.ir.hashing import canonical_json
    state, consumer, instrument, policy = _research_replay_inputs(risk_policy, stop=stop, target=target)
    bars = _research_replay_bars(state)
    if flip:
        bars = [replace(bar, long_entry=bar.short_entry, short_entry=bar.long_entry,
                        long_exit=bar.short_exit, short_exit=bar.long_exit) for bar in bars]
    expected = engine.run_trades(pd.DataFrame([bar.to_row() for bar in bars]), instrument,
        "NSE_EQ", policy["risk"]["capital"], policy["risk"]["overlay"]["risk_model"],
        slippage_pct=.0005, replay_policy=policy["risk"]["overlay"].get("replay_policy"),
        stop_loss_pct=stop, take_profit_pct=target)
    closed = []
    for bar in bars:
        step = advance_research_replay(state, bar, consumer=consumer, instrument=instrument)
        assert step.before_address == state.address
        assert step.next_state.predecessor_snapshot_address == state.address
        assert step.next_state.snapshot_sequence == state.snapshot_sequence + 1
        reopened = ResearchReplayState.from_json(canonical_json(step.next_state.to_dict()))
        assert reopened == step.next_state
        state = reopened
        closed.extend(step.closed_trades)
    expected = [trade for trade in expected if trade.reason != "OPEN_AT_END"]
    assert expected, "fixture must exercise actual closed fills"
    assert [asdict(trade) for trade in closed] == [asdict(trade) for trade in expected]


def test_research_replay_fill_waits_for_next_observed_bar_and_fill_bar_does_not_credit_ratchet_mfe():
    from app.monitoring.research_replay import advance_research_replay
    state, consumer, instrument, _ = _research_replay_inputs("pine-v4-ratchet/1")
    bars = _research_replay_bars(state)
    decision = advance_research_replay(state, bars[0], consumer=consumer, instrument=instrument)
    assert decision.next_state.position is None and decision.opened_position is None and not decision.closed_trades
    assert (decision.next_state.pending.kind, decision.next_state.pending.argument) == ("ENTER", "LONG")
    fill = advance_research_replay(decision.next_state, bars[1], consumer=consumer, instrument=instrument)
    position = fill.next_state.position
    assert position.entry_price == 101.0 * 1.00025
    assert position.entry_open_at == bars[1].opened_at
    assert position.ratchet_high_water == position.entry_price
    assert position.entry_atr == bars[1].atr
    assert fill.opened_position.entry_price == position.entry_price
    assert position.mae_pct > 0


def test_research_replay_original_cash_budget_can_decline_a_pending_entry():
    from app.monitoring.research_replay import advance_research_replay
    state, consumer, instrument, _ = _research_replay_inputs(capital=1.0)
    bars = _research_replay_bars(state)
    state = advance_research_replay(state, bars[0], consumer=consumer, instrument=instrument).next_state
    step = advance_research_replay(state, bars[1], consumer=consumer, instrument=instrument)
    assert step.next_state.position is None and step.next_state.pending is None
    assert step.opened_position is None and not step.closed_trades


@pytest.mark.parametrize("changes", [{"owner_id": "foreign.owner"},
    {"canonical_instrument_address": "sha256:" + "b" * 64},
    {"opened_at": datetime(2026, 9, 7, 3, 44, tzinfo=timezone.utc),
     "completed_at": datetime(2026, 9, 7, 3, 59, tzinfo=timezone.utc)}])
def test_research_replay_rejects_foreign_and_preceding_bars(changes):
    from app.monitoring.contracts import MonitoringContractError
    from app.monitoring.research_replay import advance_research_replay
    state, consumer, instrument, _ = _research_replay_inputs()
    bars = _research_replay_bars(state)
    state = advance_research_replay(state, bars[0], consumer=consumer, instrument=instrument).next_state
    with pytest.raises(MonitoringContractError):
        advance_research_replay(state, replace(bars[1], **changes), consumer=consumer, instrument=instrument)
    with pytest.raises(MonitoringContractError, match="already consumed"):
        advance_research_replay(state, bars[0], consumer=consumer, instrument=instrument)


@pytest.mark.parametrize("changes", [{"high": 50.0}, {"open": float("nan")}, {"close": 0.0},
    {"atr": 0.0}, {"long_entry": 1}, {"short_exit": None}, {"timeframe_seconds": True},
    {"timeframe_seconds": 60}, {"open": 100},
    {"opened_at": datetime(2026, 9, 7, 3, 45)},
    {"completed_at": datetime(2026, 9, 7, 4, 30, tzinfo=timezone.utc)}])
def test_research_replay_bar_requires_closed_ohlc_signals_and_clocks(changes):
    from app.monitoring.contracts import MonitoringContractError
    state, *_ = _research_replay_inputs()
    with pytest.raises(MonitoringContractError):
        replace(_research_replay_bars(state)[0], **changes)


def test_research_replay_refuses_missing_risk_atr_foreign_consumer_and_instrument():
    from app.monitoring.contracts import MonitoringContractError
    from app.monitoring.research_replay import advance_research_replay
    from types import SimpleNamespace
    state, consumer, instrument, _ = _research_replay_inputs("pine-v4-ratchet/1")
    bar = _research_replay_bars(state)[0]
    with pytest.raises(MonitoringContractError, match="ATR"):
        advance_research_replay(state, replace(bar, atr=None), consumer=consumer, instrument=instrument)
    other = _research_replay_inputs("none")[1]
    with pytest.raises(MonitoringContractError, match="scope"):
        advance_research_replay(state, bar, consumer=other, instrument=instrument)
    for changes in ({"key": "NIFTY"}, {"name": "foreign"}, {"segment": "NFO"},
                    {"lot_size": True}, {"source": "seed"}):
        with pytest.raises(MonitoringContractError, match="instrument"):
            advance_research_replay(state, bar, consumer=consumer,
                instrument=SimpleNamespace(**{**vars(instrument), **changes}))


@pytest.mark.parametrize("module_name", ["app.monitoring.research_replay", "app.monitoring.research_replay_state",
    "app.monitoring.research_prefix", "app.monitoring.input_producer", "research.evaluation.phase5_runtime",
    "research.data.historical_capture", "app.monitoring.research_protection", "app.monitoring.research_state_contracts",
    "app.monitoring.research_event_contracts", "app.monitoring.research_evaluation", "app.monitoring.research_runtime",
    "app.monitoring.repository", "app.monitoring.runtime", "app.monitoring.evaluation", "app.monitoring.evaluation_policy",
    "app.monitoring.research_worker", "app.monitoring.research_schedule", "app.monitoring.watchlist_config", "app.monitoring.watchlist_store",
    "app.backtest.engine", "app.engine.charges", "app.engine.event_risk", "app.core.market_hours",
    "research.orchestrator.v2_preparation"])
def test_research_replay_consumer_identity_binds_fill_state_sizing_cost_and_policy_code(module_name, monkeypatch):
    import importlib
    from app.backtest import identity
    from app.monitoring.research_consumer import research_consumer_implementation_address
    original = research_consumer_implementation_address()
    target = importlib.import_module(module_name)
    read = identity._module_bytes
    monkeypatch.setattr(identity, "_module_bytes", lambda module:
        read(module) + b"\n# changed replay rule\n" if module is target else read(module))
    assert research_consumer_implementation_address() != original


@pytest.mark.parametrize("risk_policy", ["none", "pine-v4-ratchet/1", "pine-v4-reversal/1"])
@pytest.mark.parametrize("stop,target", [(0.0, 0.0), (.01, 0.0), (0.0, .02), (.01, .02)])
@pytest.mark.parametrize("flip", [False, True])
def test_research_protection_retains_optional_rules_and_original_simulated_entry(risk_policy, stop, target, flip):
    from app.monitoring.research_protection import (
        PERCENT, RATCHET, ResearchProtectionEvidence, compile_research_protections,
    )
    from app.monitoring.research_replay import advance_research_replay
    state, consumer, instrument, _ = _research_replay_inputs(risk_policy, stop=stop, target=target)
    bars = _research_replay_bars(state)
    if flip:
        bars = [replace(bar, long_entry=bar.short_entry, short_entry=bar.long_entry,
            long_exit=bar.short_exit, short_exit=bar.long_exit) for bar in bars]
    expected_bases = ([PERCENT] if stop else []) + ([RATCHET] if risk_policy != "none" else [])
    initial = compile_research_protections(state, consumer=consumer, instrument=instrument)
    for evidence in initial:
        assert evidence.status == ("UNRESOLVED" if evidence.rules else "DISABLED")
        assert ResearchProtectionEvidence.from_dict(evidence.to_dict()) == evidence
    state = advance_research_replay(state, bars[0], consumer=consumer, instrument=instrument).next_state
    pending = compile_research_protections(state, consumer=consumer, instrument=instrument)
    assert pending == initial
    state = advance_research_replay(state, bars[1], consumer=consumer, instrument=instrument).next_state
    filled = compile_research_protections(state, consumer=consumer, instrument=instrument)
    assert [rule.basis for rule in filled[0].rules] == expected_bases
    assert [rule.basis for rule in filled[1].rules] == ([PERCENT] if target else [])
    direction = -1 if flip else 1
    entry = state.position.entry_price
    if stop:
        assert filled[0].rules[0].resolved_value.hex() == (entry * (1 - direction * stop)).hex()
    if target:
        assert filled[1].rules[0].resolved_value.hex() == (entry * (1 + direction * target)).hex()
    if risk_policy != "none":
        assert filled[0].rules[-1].resolved_value.hex() == state.position.ratchet_stop.hex()
    for before, after in zip(pending, filled, strict=True):
        assert [rule.definition_address for rule in before.rules] == [rule.definition_address for rule in after.rules]
        assert after.status == ("RESOLVED" if after.rules else "DISABLED")
        assert ResearchProtectionEvidence.from_dict(after.to_dict()) == after


@pytest.mark.parametrize("risk_policy,kind", [("none", "EXIT"), ("pine-v4-reversal/1", "REVERSE")])
def test_research_protection_exit_keeps_held_levels_but_reversal_waits_for_new_fill(risk_policy, kind):
    from app.monitoring.research_protection import compile_research_protections
    from app.monitoring.research_replay import advance_research_replay
    state, consumer, instrument, _ = _research_replay_inputs(risk_policy, stop=.05, target=.2)
    bars = _research_replay_bars(state)
    for bar in bars[:3]:
        state = advance_research_replay(state, bar, consumer=consumer, instrument=instrument).next_state
    assert state.pending.kind == kind and state.position is not None
    stop, target = compile_research_protections(state, consumer=consumer, instrument=instrument)
    expected = "RESOLVED" if kind == "EXIT" else "UNRESOLVED"
    assert stop.status == target.status == expected
    if kind == "REVERSE":
        assert all(rule.resolved_value is None for evidence in (stop, target) for rule in evidence.rules)
        state = advance_research_replay(state, bars[3], consumer=consumer, instrument=instrument).next_state
        stop, target = compile_research_protections(state, consumer=consumer, instrument=instrument)
        assert stop.status == target.status == "RESOLVED" and state.position.direction == "SHORT"
        assert target.rules[0].resolved_value == state.position.entry_price * .8


@pytest.mark.parametrize("change", ["consumer", "policy", "kind", "basis", "fraction_bool", "fraction_zero",
    "fraction_one", "infinite", "ratchet_fraction", "ratchet_target", "extra", "definition", "status",
    "duplicate", "order", "foreign_rule", "mixed_policy", "mixed_resolution", "rule_list"])
def test_research_protection_closed_facts_refuse_invalid_or_mixed_evidence(change):
    from app.monitoring.contracts import MonitoringContractError, ProtectionKind
    from app.monitoring.research_protection import PERCENT, RATCHET, ResearchProtectionRule, ResearchProtectionEvidence
    address = "sha256:" + "a" * 64
    rule = ResearchProtectionRule(address, address, ProtectionKind.STOP_LOSS, PERCENT, .01, 99.0)
    ratchet = ResearchProtectionRule(address, address, ProtectionKind.STOP_LOSS, RATCHET, None, 98.0)
    evidence = ResearchProtectionEvidence(address, ProtectionKind.STOP_LOSS, (rule, ratchet))
    edits = {
        "consumer": {"consumer_address": "invalid"}, "policy": {"risk_policy_address": "invalid"},
        "kind": {"kind": "STOP_LOSS"}, "basis": {"basis": "DEFAULT_STOP"},
        "fraction_bool": {"fraction": True}, "fraction_zero": {"fraction": 0.0},
        "fraction_one": {"fraction": 1.0}, "infinite": {"resolved_value": float("inf")},
        "ratchet_fraction": {"basis": RATCHET}, "ratchet_target": {
            "basis": RATCHET, "fraction": None, "kind": ProtectionKind.TAKE_PROFIT},
    }
    with pytest.raises(MonitoringContractError):
        if change in edits:
            replace(rule, **edits[change])
        elif change == "extra":
            ResearchProtectionRule.from_dict({**rule.to_dict(), "extra": True})
        elif change == "definition":
            ResearchProtectionRule.from_dict({**rule.to_dict(), "definition_address": "sha256:"+"b"*64})
        elif change == "status":
            ResearchProtectionEvidence.from_dict({**evidence.to_dict(), "status": "DISABLED"})
        else:
            cases = {"duplicate": (rule, rule), "order": (ratchet, rule),
                "foreign_rule": (replace(rule, consumer_address="sha256:"+"b"*64),),
                "mixed_policy": (rule, replace(ratchet, risk_policy_address="sha256:"+"b"*64)),
                "mixed_resolution": (rule, replace(ratchet, resolved_value=None)), "rule_list": [rule]}
            replace(evidence, rules=cases[change])


@pytest.mark.parametrize("change", ["state_type", "consumer_type", "owner", "instrument", "state_policy",
    "state_owner", "state_assignment", "policy_contents"])
def test_research_protection_compiler_refuses_changed_consumer_scope(change):
    from app.ir.resource_plan import _canonical, _plain
    from app.monitoring.contracts import MonitoringContractError
    from app.monitoring.research_protection import compile_research_protections
    state, consumer, instrument, _ = _research_replay_inputs()
    if change == "state_type":
        state = None
    elif change == "consumer_type":
        consumer = None
    elif change == "owner":
        consumer = _canonical(consumer.schema, {**_plain(consumer.document), "owner_id": "other-owner"})
    elif change == "instrument":
        instrument.name = "foreign"
    elif change == "state_owner":
        state = replace(state, owner_id="other-owner")
    elif change == "state_assignment":
        state = replace(state, assignment_id="other-assignment")
    elif change == "policy_contents":
        changed = _plain(consumer.document)
        changed["execution_policy"]["risk"]["fill"] = "same-bar-close"
        consumer = _canonical(consumer.schema, changed)
        state = replace(state, consumer_address=consumer.address)
    else:
        state = replace(state, consumer_address="sha256:"+"b"*64)
    with pytest.raises(MonitoringContractError):
        compile_research_protections(state, consumer=consumer, instrument=instrument)
# Research prefix events use the original replay decisions and protection policy.
def _research_signal_event_case(risk_policy="none", index=1):
    from dataclasses import fields
    from app.monitoring.contracts import MonitoringSignalEvent
    from app.monitoring.research_event_contracts import ResearchMonitoringSignalEvent
    from tests.test_v0_monitoring_persistence import _research_monitoring_snapshot_case
    from tests.test_v0_signal_alert_attention_contract import event
    snapshots, _, _ = _research_monitoring_snapshot_case(risk_policy)
    before, after = snapshots[index-1:index+1]
    state = after.checkpoint.state
    pending = state.pending
    template = event()
    arguments = {field.name: getattr(template, field.name) for field in fields(MonitoringSignalEvent)}
    action = SignalAction.HOLD if pending is None else (SignalAction.EXIT if pending.kind == "EXIT"
        else SignalAction.BUY if pending.argument == "LONG" else SignalAction.SELL)
    arguments.update(owner_id=after.owner_id, assignment_id=after.assignment_id,
        canonical_instrument_address=after.canonical_instrument_address,
        previous_state=before.strategy_state, target_state=after.strategy_state, action=action,
        evaluation_event_address=after.evaluation_event_address, event_at=after.effective_at,
        latest_data_at=after.effective_at, knowledge_cutoff_at=after.effective_at+timedelta(seconds=3),
        valid_until=after.effective_at+timedelta(seconds=60), evaluation_validity=FactValidity.VALID,
        freshness=Freshness.FRESH, repeated_target_state=before.strategy_state is after.strategy_state,
        entry_reference=after.entry_reference, stop_loss=after.stop_loss, take_profit=after.take_profit,
        state_before_address=before.address, state_after_address=after.address,
        reason_code="RESEARCH_DECISION", consumer_address=state.consumer_address,
        completed_bar_identity=state.last_bar_identity, prefix_completed_at=after.effective_at,
        prefix_available_at=after.effective_at+timedelta(seconds=1),
        prefix_recorded_at=after.effective_at+timedelta(seconds=2), replay_scope="CURRENT",
        decision_kind="NONE" if pending is None else pending.kind,
        simulated_position_state=StrategyState.FLAT if state.position is None else StrategyState(state.position.direction))
    return ResearchMonitoringSignalEvent(**arguments)


@pytest.mark.parametrize("risk_policy", ["none", "pine-v4-ratchet/1", "pine-v4-reversal/1"])
@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_research_signal_event_and_alert_roundtrip_original_pending_decisions(risk_policy, index):
    from app.ir.hashing import canonical_json
    from app.monitoring.research_event_contracts import ResearchMonitoringSignalEvent, ResearchSignalAlert, derive_research_signal_alert
    source = _research_signal_event_case(risk_policy, index)
    assert ResearchMonitoringSignalEvent.from_json(canonical_json(source.to_dict())) == source
    result = derive_research_signal_alert(source)
    if source.action is SignalAction.HOLD:
        assert isinstance(result, NoAlert) and result.code is NoAlertCode.HOLD
        return
    assert isinstance(result, AlertDerived)
    alert = result.alert
    assert alert.monitoring_event_address == source.address and alert.completed_bar_identity == source.completed_bar_identity
    assert alert.stop_loss == source.stop_loss and alert.take_profit == source.take_profit
    assert ResearchSignalAlert.from_json(canonical_json(alert.to_dict()).encode()) == alert
    assert alert.to_dict()["authority"] == "NONE"
    if source.decision_kind in ("ENTER", "REVERSE"):
        assert alert.stop_loss.status == "UNRESOLVED"


@pytest.mark.parametrize("change", ["catch_up", "stale", "hold", "repeated_new_entry"])
def test_research_signal_event_alert_eligibility_uses_current_decision_not_intent_difference(change):
    from app.monitoring.research_event_contracts import derive_research_signal_alert
    source = _research_signal_event_case()
    if change == "catch_up":
        completed = source.event_at+timedelta(minutes=15)
        source = replace(source, prefix_completed_at=completed, prefix_available_at=completed+timedelta(seconds=1),
            prefix_recorded_at=completed+timedelta(seconds=2), knowledge_cutoff_at=completed+timedelta(seconds=3),
            valid_until=completed+timedelta(seconds=60), replay_scope="CATCH_UP")
        expected = NoAlertCode.REPLAY_CATCH_UP
    elif change == "stale":
        source = replace(source, knowledge_cutoff_at=source.valid_until+timedelta(microseconds=1), freshness=Freshness.STALE)
        expected = NoAlertCode.STALE_DATA
    elif change == "hold":
        # A failed previous entry may reset the desired state without a real exit.
        source = replace(source, previous_state=StrategyState.LONG, target_state=StrategyState.FLAT,
            action=SignalAction.HOLD, decision_kind="NONE")
        expected = NoAlertCode.HOLD
    else:
        source = replace(source, previous_state=StrategyState.LONG, repeated_target_state=True)
        assert isinstance(derive_research_signal_alert(source), AlertDerived)
        return
    result = derive_research_signal_alert(source)
    assert isinstance(result, NoAlert) and result.code is expected


@pytest.mark.parametrize("changes", [
    {"decision_kind": "ORDER"}, {"replay_scope": "CATCH_UP"}, {"evaluation_validity": FactValidity.REFUSED},
    {"freshness": Freshness.STALE}, {"action": SignalAction.SELL}, {"simulated_position_state": StrategyState.LONG},
    {"target_state": StrategyState.FLAT}, {"decision_kind": "EXIT", "action": SignalAction.EXIT,
        "previous_state": StrategyState.LONG, "target_state": StrategyState.FLAT},
    {"repeated_target_state": 0}, {"repeated_target_state": True}, {"display_symbol": "bad\ntext"},
    {"consumer_address": "invalid"}, {"reason_code": "invalid code"}, {"entry_reference": {}}, {"stop_loss": {}},
])
def test_research_signal_event_refuses_invalid_decision_evidence_and_closed_values(changes):
    source = _research_signal_event_case()
    with pytest.raises(ValueError):
        replace(source, **changes)


@pytest.mark.parametrize("field,delta", [("event_at", 1), ("latest_data_at", -1),
    ("prefix_available_at", -2), ("prefix_recorded_at", -2), ("knowledge_cutoff_at", -2),
    ("valid_until", -60), ("valid_until", 86400)])
def test_research_signal_event_refuses_invalid_completed_prefix_clocks(field, delta):
    source = _research_signal_event_case()
    with pytest.raises(ValueError):
        replace(source, **{field: getattr(source, field)+timedelta(seconds=delta)})


@pytest.mark.parametrize("kind", ["event", "alert"])
@pytest.mark.parametrize("field,value", [("authority", "LIVE"), ("evaluation_scope", "SINGLE_BAR"),
    ("extra", None), ("schema", "unrecognized"), ("address", "sha256:"+"0"*64), ("decision_kind", "EXIT")])
def test_research_signal_event_and_alert_parser_refuses_rehashed_schema_and_decision(kind, field, value):
    from app.ir.hashing import content_address
    from app.monitoring.research_event_contracts import derive_research_signal_alert
    source = _research_signal_event_case()
    source = source if kind == "event" else derive_research_signal_alert(source).alert
    payload = {**source.canonical_payload(), field: value}
    if field != "address":
        payload["address"] = content_address(payload)
    with pytest.raises(ValueError):
        type(source).from_dict(payload)


@pytest.mark.parametrize("disabled", [("stop_loss",), ("take_profit",), ("stop_loss", "take_profit")])
def test_research_signal_event_allows_declared_disabled_protection_without_inventing_levels(disabled):
    from app.monitoring.research_event_contracts import derive_research_signal_alert
    source = _research_signal_event_case()
    source = replace(source, **{name: replace(getattr(source, name), rules=()) for name in disabled})
    alert = derive_research_signal_alert(source).alert
    assert all(getattr(alert, name).status == "DISABLED" for name in disabled)


def test_research_signal_event_refuses_protection_for_a_future_unfilled_entry():
    source = _research_signal_event_case()
    stop = replace(source.stop_loss, rules=tuple(replace(rule, resolved_value=95.0) for rule in source.stop_loss.rules))
    with pytest.raises(ValueError, match="entry availability"):
        replace(source, stop_loss=stop)


@pytest.mark.parametrize("kind", ["event", "alert"])
def test_research_signal_event_and_alert_json_refuses_duplicate_keys_and_oversized_documents(kind):
    from app.ir.hashing import canonical_json
    from app.monitoring.research_event_contracts import derive_research_signal_alert
    source = _research_signal_event_case()
    source = source if kind == "event" else derive_research_signal_alert(source).alert
    payload = canonical_json(source.to_dict()).encode()
    duplicate = payload.replace(b'"authority":', b'"authority":"LIVE","authority":', 1)
    for invalid in (duplicate, b"[]", b"NaN", b"\xff", b" "*(16*1024+1)):
        with pytest.raises(ValueError):
            type(source).from_json(invalid)
