from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo
import importlib.util
from pathlib import Path
import sys
import threading

import pytest

import app.ir.evaluation_schedule as evaluation_schedule_module
from app.ir.evaluation_schedule import (
    AcquisitionSupport,
    AuthoredGateOutcome,
    ConditionalAcquisitionAuthority,
    ScheduleRefusal,
    ScheduleRefusalCode,
    ScheduleResourceCeiling,
    admit_evaluation_event,
    canonical_conditional_requirement_selector,
    admit_authored_acquisition_gate,
    compile_conditional_acquisition_authority,
    compile_evaluation_schedule,
    compile_schedule_resource_ceiling,
    verify_conditional_acquisition_authority,
    verify_authored_acquisition_gate,
    verify_evaluation_event,
    verify_evaluation_schedule,
    verify_schedule_resource_ceiling,
)
from app.ir.formats.v2 import canonical_document
from app.ir.hashing import canonical_json, content_address
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.resource_plan import compile_resource_plan
from app.ir.v2_graph_versions import V2GraphFacts
from app.market_data.capability import assess_capability
from app.market_data.eligibility import compile_graph_data_eligibility
from app.market_data.requirements import compile_data_requirement_plan
from tests.test_v0_graph_data_eligibility import _case as _eligibility_case


UTC = timezone.utc


class _ChameleonTuple(tuple):
    def __contains__(self, item):
        return item == "tick" or super().__contains__(item)


class _ChameleonInt(int):
    def __lt__(self, other):
        return False

    def __ge__(self, other):
        return True


class _ChameleonStr(str):
    pass


class _ChameleonDict(dict):
    pass


class _ChameleonDateTime(datetime):
    pass


class _MutableUtcTz(tzinfo):
    def __init__(self) -> None:
        self.offset = timedelta(0)

    def utcoffset(self, _value):
        return self.offset

    def dst(self, _value):
        return timedelta(0)

    def tzname(self, _value):
        return "mutable-utc"


def _address(label: str) -> str:
    return content_address({"evaluation_schedule_fixture": label})


def _type(type_id: str, runtime: str) -> dict[str, object]:
    return {
        "type_id": type_id,
        "type_version": 1,
        "shapes": ["scalar"],
        "runtime_representation": runtime,
    }


def _port(port_id: str, direction: str, type_id: str) -> dict[str, object]:
    result = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "input" if direction == "input" else "result",
        "type_ref": {"type_id": type_id, "type_version": 1},
        "shape": "scalar",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": "optional", "min": 0, "max": 1, "assembly": "single",
        }
    return result


def _ports(name: str) -> list[dict[str, object]]:
    input_type = "boolean" if name == "dependent" else "number"
    output_type = "boolean" if name == "gate" else "number"
    return [
        _port("in", "input", input_type),
        _port("out", "output", output_type),
    ]


def _component(name: str, component_id: str) -> dict[str, object]:
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "state" if name == "gate" else "transform",
        "structural_role": "transform",
        "ports": _ports(name),
        "parameters": {},
    }


def _contract(component_id: str, *, name: str, stateful: bool = False) -> dict[str, object]:
    input_contract = "boolean-value/1" if name == "dependent" else "numeric-value/1"
    output_contract = "boolean-value/1" if name == "gate" else "numeric-value/1"
    return {
        "stable_node_id": component_id,
        "semantic_version": 1,
        "visible_family": "TYPE_5" if name == "gate" else "TYPE_2",
        "input_types": {"in": input_contract},
        "output_types": {"out": output_contract},
        "required_market_fields": ["close"],
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 2,
        "execution_form": "ROLLING" if stateful else "STATELESS",
        "state_initialization": {
            "schema": "state-initialization/1",
            "initial_state_address": _address(f"initial-{component_id}"),
        },
        "state_reset_policy": {
            "schema": "state-reset-policy/1",
            "reasons": ["EXPLICIT", "SESSION"] if stateful else ["EXPLICIT"],
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
            "history_bytes_upper_bound": 64,
            "state_bytes_upper_bound": 16 if stateful else 0,
            "storage_bytes_per_day_upper_bound": 8,
            "subscription_count_upper_bound": 1,
            "fanout_upper_bound": 4,
        },
        "reference_provenance": [_address("reference")],
    }


def _no_data() -> dict[str, object]:
    return {
        "schema": "data-requirement-declaration/1",
        "classification": "NO_DATA",
        "requirements": [],
    }


def _conditional_data() -> dict[str, object]:
    literal = lambda value: {"literal": value}
    return {
        "schema": "data-requirement-declaration/1",
        "classification": "REQUIRES_DATA",
        "requirements": [
            {
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
            }
        ],
    }


def _registry(*, gate_family: str = "TYPE_5", gate_domain: str = "state",
              boolean_runtime: str = "bool", gate_output_contract: str = "boolean-value/1",
              dependent_input_contract: str = "boolean-value/1") -> PlatformRegistry:
    keys = {
        name: (f"schedule.{name}", 1)
        for name in ("source", "gate", "dependent", "independent")
    }
    components = {key: _component(name, key[0]) for name, key in keys.items()}
    components[keys["gate"]]["domain_family"] = gate_domain
    contracts = {
        key: _contract(key[0], name=name, stateful=name == "dependent")
        for name, key in keys.items()
    }
    contracts[keys["gate"]]["visible_family"] = gate_family
    contracts[keys["gate"]]["output_types"]["out"] = gate_output_contract
    contracts[keys["dependent"]]["input_types"]["in"] = dependent_input_contract
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types={
            ("number", 1): _type("number", "float64"),
            ("boolean", 1): _type("boolean", boolean_runtime),
        },
        v2_components=components,
        data_requirement_declarations={
            keys["source"]: _no_data(),
            keys["gate"]: _no_data(),
            keys["dependent"]: _conditional_data(),
            keys["independent"]: _no_data(),
        },
        node_contracts=contracts,
    )


def _document(*, reverse: bool = False) -> dict[str, object]:
    names = ["source", "gate", "dependent", "independent"]
    nodes = [
        {
            "node_id": name,
            "component": {"component_id": f"schedule.{name}", "component_version": 1},
            "parameters": {},
        }
        for name in names
    ]
    edges = [
        {
            "edge_id": "source-gate",
            "source": {"scope": "node", "node_id": "source", "port_id": "out"},
            "target": {"scope": "node", "node_id": "gate", "port_id": "in"},
            "binding": {"kind": "single"},
        },
        {
            "edge_id": "gate-dependent",
            "source": {"scope": "node", "node_id": "gate", "port_id": "out"},
            "target": {"scope": "node", "node_id": "dependent", "port_id": "in"},
            "binding": {"kind": "single"},
        },
    ]
    return {
        "format_version": 2,
        "strategy_id": "evaluation-schedule",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": "Evaluation schedule fixture",
            "description": None,
            "tags": [],
        },
        "graph_inputs": [],
        "graph_outputs": [],
        "nodes": list(reversed(nodes)) if reverse else nodes,
        "edges": list(reversed(edges)) if reverse else edges,
    }


def _selector(record) -> str:
    return canonical_conditional_requirement_selector(record)


def _plain(value):
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _facts(*, reverse: bool = False, ceiling_changes=None,
           owner_id: str = "owner-a", assignment_id: str = "assignment-a"):
    registry = _registry()
    graph = resolve_v2(_document(reverse=reverse), registry)
    data = compile_data_requirement_plan(graph)
    resource = compile_resource_plan(
        graph,
        data,
        registry,
        cache_bytes_upper_bound=128,
        artifact_bytes_upper_bound=0,
        queue_concurrency_upper_bound=2,
    )
    ceiling_values = {
        "history_bytes_upper_bound": 256,
        "memory_bytes_upper_bound": 400,
        "cache_bytes_upper_bound": 128,
        "queue_concurrency_upper_bound": 2,
        "event_rate_events": 1,
        "event_rate_per_seconds": 1,
        "policy_address": _address("resource-ceiling"),
    }
    ceiling_values.update(ceiling_changes or {})
    ceiling = compile_schedule_resource_ceiling(**ceiling_values)
    conditional = next(record for record in data.requirements if record["authored_node_id"] == "dependent")
    schedule = compile_evaluation_schedule(
        owner_id=owner_id,
        assignment_id=assignment_id,
        resolved_graph=graph,
        data_requirement_plan=data,
        resource_plan=resource,
        registry=registry,
        gate_node_id="gate",
        conditional_requirement_selector=_selector(conditional),
        unit_contract_addresses={node.node_id: _address(f"unit-{node.node_id}") for node in graph.nodes},
        event_unit_address=_address("event-unit-seconds"),
        mode="paper",
        trigger_rates={"completed_bar": {"events": 1, "per_seconds": 1}},
        resource_ceiling=ceiling,
    )
    return registry, graph, data, resource, schedule, conditional


def _compile_for_gate(registry: PlatformRegistry, gate_node_id: str, document=None):
    graph = resolve_v2(document or _document(), registry)
    data = compile_data_requirement_plan(graph)
    resource = compile_resource_plan(
        graph, data, registry, cache_bytes_upper_bound=128,
        artifact_bytes_upper_bound=0, queue_concurrency_upper_bound=2,
    )
    conditional = next(record for record in data.requirements
                       if record["authored_node_id"] == "dependent")
    return compile_evaluation_schedule(
        owner_id="owner-a", assignment_id="assignment-a",
        resolved_graph=graph, data_requirement_plan=data, resource_plan=resource,
        registry=registry, gate_node_id=gate_node_id,
        conditional_requirement_selector=_selector(conditional),
        unit_contract_addresses={node.node_id: _address(f"unit-{node.node_id}")
                                 for node in graph.nodes},
        event_unit_address=_address("event-unit-seconds"), mode="paper",
        trigger_rates={"completed_bar": {"events": 1, "per_seconds": 1}},
        resource_ceiling=compile_schedule_resource_ceiling(
            history_bytes_upper_bound=sum(row["bytes_upper_bound"]
                                          for row in resource.document["history_requirements"]),
            memory_bytes_upper_bound=resource.document["memory_bytes_upper_bound"],
            cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
            event_rate_events=1, event_rate_per_seconds=1,
            policy_address=_address("resource-ceiling"),
        ),
    )


def _compile_with_ceiling(registry, graph, data, resource, conditional, ceiling, *, module=None):
    module = module or evaluation_schedule_module
    return module.compile_evaluation_schedule(
        owner_id="owner-a", assignment_id="assignment-a",
        resolved_graph=graph, data_requirement_plan=data, resource_plan=resource,
        registry=registry, gate_node_id="gate",
        conditional_requirement_selector=module.canonical_conditional_requirement_selector(
            conditional),
        unit_contract_addresses={node.node_id: _address(f"unit-{node.node_id}")
                                 for node in graph.nodes},
        event_unit_address=_address("event-unit-seconds"), mode="paper",
        trigger_rates={"completed_bar": {"events": 1, "per_seconds": 1}},
        resource_ceiling=ceiling,
    )


def _time(second: int) -> datetime:
    return datetime(2026, 8, 31, 9, 15, 0, tzinfo=UTC) + timedelta(seconds=second)


def test_schedule_reconstructs_exact_authorities_and_stable_topological_phases():
    registry, graph, data, resource, schedule, _conditional = _facts()
    assert schedule.authored_ir_address == graph.authored_ir_address
    assert schedule.resolved_graph_address == graph.resolved_graph_address
    assert schedule.data_requirement_plan_address == data.plan_address
    assert schedule.resource_plan_address == resource.plan_address
    assert schedule.registry_snapshot_address == registry.registry_snapshot_address
    assert schedule.implementation_closure_address == graph.implementation_closure_address
    assert schedule.unconditional_nodes == ("independent", "source")
    assert schedule.authored_gate_nodes == ("gate",)
    assert schedule.dependent_nodes == ("dependent",)
    assert schedule.reset_requirements[-1]["node_id"] == "source"
    assert _facts(reverse=True)[4] == schedule


def test_public_conditional_selector_is_canonical_and_closed():
    _registry_value, _graph, _data, _resource, schedule, conditional = _facts()
    assert canonical_conditional_requirement_selector(conditional) \
        == schedule.conditional_requirement_selector
    with pytest.raises(ScheduleRefusal) as caught:
        canonical_conditional_requirement_selector({**dict(conditional), "ui_gate": True})
    assert caught.value.code is ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID


def test_same_bytes_chameleon_tuple_refuses_verifier_event_and_cache_facing_boundary():
    schedule = _facts()[4]
    original_address = schedule.schedule_address
    object.__setattr__(
        schedule, "declared_triggers", _ChameleonTuple(("completed_bar",)))
    assert content_address(evaluation_schedule_module._schedule_payload(schedule)) \
        == original_address
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_schedule(schedule)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            schedule, trigger="tick", observation_address=_address("observation"),
            event_at=_time(0), completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(2),
            unit_contract_address=_address("event-unit-seconds"),
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_exact_string_and_mapping_subclasses_refuse_compiler_and_verifier_boundaries():
    with pytest.raises(ScheduleRefusal) as caught:
        _facts(owner_id=_ChameleonStr("owner-a"))
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    registry, graph, data, resource, _schedule, conditional = _facts()
    ceiling = compile_schedule_resource_ceiling(
        history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
        cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
        event_rate_events=1, event_rate_per_seconds=1,
        policy_address=_address("resource-ceiling"),
    )
    with pytest.raises(ScheduleRefusal) as caught:
        evaluation_schedule_module.compile_evaluation_schedule(
            owner_id="owner-a", assignment_id="assignment-a",
            resolved_graph=graph, data_requirement_plan=data, resource_plan=resource,
            registry=registry, gate_node_id="gate",
            conditional_requirement_selector=_selector(conditional),
            unit_contract_addresses={node.node_id: _address(f"unit-{node.node_id}")
                                     for node in graph.nodes},
            event_unit_address=_address("event-unit-seconds"), mode="paper",
            trigger_rates=_ChameleonDict({
                "completed_bar": {"events": 1, "per_seconds": 1}
            }),
            resource_ceiling=ceiling,
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    schedule = _facts()[4]
    object.__setattr__(schedule, "owner_id", _ChameleonStr("owner-a"))
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_schedule(schedule)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_int_and_datetime_subclasses_refuse_before_addressing_or_event_admission():
    with pytest.raises(ScheduleRefusal) as caught:
        compile_schedule_resource_ceiling(
            history_bytes_upper_bound=256,
            memory_bytes_upper_bound=_ChameleonInt(1),
            cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
            event_rate_events=1, event_rate_per_seconds=1,
            policy_address=_address("resource-ceiling"),
        )
    assert caught.value.code is ScheduleRefusalCode.UNIT_AMBIGUOUS
    schedule = _facts()[4]
    hostile_time = _ChameleonDateTime(
        2026, 8, 31, 9, 15, 0, tzinfo=UTC)
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            schedule, trigger="completed_bar", observation_address=_address("observation"),
            event_at=hostile_time, completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(2),
            unit_contract_address=_address("event-unit-seconds"),
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_TIME


def test_issued_nested_mapping_int_datetime_and_enum_runtime_subclasses_refuse():
    schedule = _facts()[4]
    row = schedule.trigger_rates[0]
    object.__setattr__(
        schedule, "trigger_rates", (_ChameleonDict(dict(row)),))
    assert content_address(evaluation_schedule_module._schedule_payload(schedule)) \
        == schedule.schedule_address
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_schedule(schedule)

    ceiling = compile_schedule_resource_ceiling(
        history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
        cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
        event_rate_events=1, event_rate_per_seconds=1,
        policy_address=_address("resource-ceiling"),
    )
    object.__setattr__(ceiling, "memory_bytes_upper_bound", _ChameleonInt(400))
    assert content_address(evaluation_schedule_module._ceiling_payload(ceiling)) \
        == ceiling.ceiling_address
    with pytest.raises(ScheduleRefusal):
        verify_schedule_resource_ceiling(ceiling)

    valid_schedule = _facts()[4]
    event = admit_evaluation_event(
        valid_schedule, trigger="completed_bar", observation_address=_address("observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1),
        recorded_at=_time(2), cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    )
    hostile_time = _ChameleonDateTime(
        event.event_at.year, event.event_at.month, event.event_at.day,
        event.event_at.hour, event.event_at.minute, event.event_at.second,
        tzinfo=UTC,
    )
    object.__setattr__(event, "event_at", hostile_time)
    assert content_address(evaluation_schedule_module._event_payload(event)) \
        == event.event_address
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_event(event)

    gate = admit_authored_acquisition_gate(
        valid_schedule, data_requirement_plan=_facts()[2],
        outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    object.__setattr__(gate, "outcome", _ChameleonStr("NOT_REQUIRED"))
    with pytest.raises(ScheduleRefusal):
        verify_authored_acquisition_gate(gate)


@pytest.mark.parametrize("registry,gate_node_id", [
    (_registry(), "source"),
    (_registry(gate_family="TYPE_2"), "gate"),
    (_registry(gate_domain="transform"), "gate"),
    (_registry(boolean_runtime="float64"), "gate"),
    (_registry(gate_output_contract="numeric-value/1"), "gate"),
    (_registry(dependent_input_contract="numeric-value/1"), "gate"),
    (_registry(), "presentation.canvas_gate"),
])
def test_numeric_arbitrary_or_presentation_gate_refuses(registry, gate_node_id):
    with pytest.raises(ScheduleRefusal) as caught:
        _compile_for_gate(registry, gate_node_id)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORED_GATE


def test_unrelated_boolean_node_cannot_open_the_conditional_closure():
    document = _document()
    document["nodes"].append({
        "node_id": "unrelated_boolean",
        "component": {"component_id": "schedule.gate", "component_version": 1},
        "parameters": {},
    })
    with pytest.raises(ScheduleRefusal) as caught:
        _compile_for_gate(_registry(), "unrelated_boolean", document)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORED_GATE


def test_owner_and_assignment_are_schedule_identity_dimensions():
    base = _facts()[4]
    assert _facts(owner_id="owner-b")[4].schedule_address != base.schedule_address
    assert _facts(assignment_id="assignment-b")[4].schedule_address != base.schedule_address


def test_completed_event_admission_is_causal_at_every_boundary_and_prefix_stable():
    schedule = _facts()[4]
    event = admit_evaluation_event(
        schedule,
        trigger="completed_bar",
        observation_address=_address("observation"),
        event_at=_time(0),
        completed_at=_time(1),
        available_at=_time(1),
        recorded_at=_time(2),
        cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    )
    assert event.event_at <= event.completed_at <= event.available_at <= event.recorded_at <= event.cutoff_at
    assert admit_evaluation_event(
        schedule,
        trigger="completed_bar",
        observation_address=_address("observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1),
        recorded_at=_time(2), cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    ) == event
    future_observations = [event, _address("future-observation")]
    assert len(future_observations) == 2
    assert _facts()[4].schedule_address == schedule.schedule_address


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"trigger": "tick"}, ScheduleRefusalCode.UNDECLARED_TRIGGER),
        ({"completed_at": _time(3)}, ScheduleRefusalCode.FORMING_OBSERVATION),
        ({"event_at": _time(3)}, ScheduleRefusalCode.FUTURE_EVENT),
        ({"available_at": _time(0)}, ScheduleRefusalCode.AVAILABILITY_BEFORE_COMPLETION),
        ({"recorded_at": _time(3)}, ScheduleRefusalCode.LATE_UNAVAILABLE),
        ({"available_at": _time(1), "cutoff_at": _time(62), "recorded_at": _time(2)}, ScheduleRefusalCode.STALE_OBSERVATION),
        ({"unit_contract_address": _address("other-unit")}, ScheduleRefusalCode.UNIT_AMBIGUOUS),
    ],
)
def test_event_refusals_are_typed(changes, code):
    values = {
        "trigger": "completed_bar",
        "observation_address": _address("observation"),
        "event_at": _time(0),
        "completed_at": _time(1),
        "available_at": _time(1),
        "recorded_at": _time(2),
        "cutoff_at": _time(2),
        "unit_contract_address": _address("event-unit-seconds"),
    }
    values.update(changes)
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(_facts()[4], **values)
    assert caught.value.code is code


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 8, 31, 9, 15, 0),
        datetime(2026, 8, 31, 9, 15, 0, 1, tzinfo=UTC),
        datetime(2026, 8, 31, 14, 45, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ],
)
def test_event_times_refuse_naive_fractional_and_non_utc_values(value):
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            _facts()[4], trigger="completed_bar", observation_address=_address("observation"),
            event_at=value, completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(2),
            unit_contract_address=_address("event-unit-seconds"),
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_TIME


def test_event_admission_refuses_caller_owned_mutable_utc_timezone():
    caller_timezone = _MutableUtcTz()
    caller_time = datetime(2026, 8, 31, 9, 15, 0, tzinfo=caller_timezone)
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            _facts()[4], trigger="completed_bar",
            observation_address=_address("observation"),
            event_at=caller_time, completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(2),
            unit_contract_address=_address("event-unit-seconds"),
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_TIME
    caller_timezone.offset = timedelta(hours=1)
    assert caller_time.utcoffset() == timedelta(hours=1)


def _typed_conditional_authority(registry, graph, data, schedule):
    case = _eligibility_case()
    document = canonical_document(_document(), registry)
    projection = {
        "identity_scheme_version": 1,
        "graph": {
            key: document[key]
            for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")
        },
    }
    facts = V2GraphFacts(
        schedule.owner_id,
        document["strategy_id"],
        document["strategy_version"],
        canonical_json(document),
        2,
        content_address(document),
        content_address(projection),
        data.registry_snapshot_address,
    )
    case = {**case, "graph": facts, "resolved_graph": graph, "plan": data}
    eligibility = compile_graph_data_eligibility(**case)
    assessment = assess_capability(
        plan=data,
        profile=case["profile"],
        owner_id=schedule.owner_id,
        mode="RESEARCH",
        dataset_manifest_address=content_address({
            "dataset_manifest_addresses": sorted(eligibility.dataset_manifest_addresses)
        }),
        market_truth_snapshot_address=content_address({
            "truth_snapshot_addresses": sorted(eligibility.truth_snapshot_addresses)
        }),
        evaluation_policy_address=content_address({
            "policy_addresses": sorted(eligibility.policy_addresses)
        }),
        assessment_evidence_address=case["conformance"].address,
        at_time=int(case["request"].as_of.timestamp()),
        conformance=case["conformance"],
        provider_contract=case["provider_contract"],
    )
    authority = compile_conditional_acquisition_authority(
        schedule,
        data_requirement_plan=data,
        capability_assessment=assessment,
        eligibility_result=eligibility,
    )
    return assessment, eligibility, authority


def test_not_required_authored_gate_exposes_no_conditional_requirement():
    _registry_value, _graph, data, _resource, schedule, conditional = _facts()
    not_required = admit_authored_acquisition_gate(
        schedule,
        data_requirement_plan=data,
        outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    assert not_required.conditional_requirement is None
    assert not_required.conditional_requirement_selector is None


@pytest.mark.parametrize(("outcome", "code"), [
    (AuthoredGateOutcome.UNKNOWN, ScheduleRefusalCode.ACQUISITION_GATE_UNKNOWN),
    (AuthoredGateOutcome.REQUIRED, ScheduleRefusalCode.CAPABILITY_UNKNOWN),
    (True, ScheduleRefusalCode.INVALID_GATE_OUTCOME),
])
def test_unknown_boolean_or_absent_authority_never_opens_acquisition(outcome, code):
    _registry_value, _graph, data, _resource, schedule, conditional = _facts()
    with pytest.raises(ScheduleRefusal) as caught:
        admit_authored_acquisition_gate(
            schedule,
            data_requirement_plan=data,
            outcome=outcome,
            decision_input_address=_address("gate-input"),
        )
    assert caught.value.code is code


def test_real_typed_current_authorities_keep_static_depth_required_closed():
    registry, graph, data, _resource, schedule, _conditional = _facts()
    assessment, eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    assert type(assessment).__name__ == "CapabilityAssessment"
    assert type(eligibility).__name__ == "EligibilityResult"
    assert eligibility.status == "REFUSED"
    assert authority.result is AcquisitionSupport.UNSUPPORTED
    with pytest.raises(ScheduleRefusal) as caught:
        admit_authored_acquisition_gate(
            schedule,
            data_requirement_plan=data,
            outcome=AuthoredGateOutcome.REQUIRED,
            decision_input_address=_address("gate-input"),
            authority=authority,
            capability_assessment=assessment,
            eligibility_result=eligibility,
        )
    assert caught.value.code is ScheduleRefusalCode.CAPABILITY_UNSUPPORTED


def _forged_eligibility(result, **changes):
    forged = object.__new__(type(result))
    for name in result.__dataclass_fields__:
        object.__setattr__(forged, name, changes.get(name, getattr(result, name)))
    return forged


def test_cross_owner_cross_plan_and_forged_status_cannot_compile_support():
    registry, graph, data, _resource, schedule, _conditional = _facts()
    assessment, eligibility, _authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    foreign_schedule = _facts(owner_id="owner-b")[4]
    other_eligibility = compile_graph_data_eligibility(**_eligibility_case())
    forged_status = _forged_eligibility(eligibility, status="SUPPORTED", refusals=())
    for target_schedule, candidate in (
        (foreign_schedule, eligibility),
        (schedule, other_eligibility),
        (schedule, forged_status),
    ):
        with pytest.raises(ScheduleRefusal) as caught:
            compile_conditional_acquisition_authority(
                target_schedule,
                data_requirement_plan=data,
                capability_assessment=assessment,
                eligibility_result=candidate,
            )
        assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"history_bytes_upper_bound": 255}, ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED),
        ({"memory_bytes_upper_bound": 399}, ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED),
        ({"cache_bytes_upper_bound": 127}, ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED),
        ({"queue_concurrency_upper_bound": 1}, ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED),
        ({"event_rate_events": 0}, ScheduleRefusalCode.UNIT_AMBIGUOUS),
    ],
)
def test_resource_and_unit_boundaries_refuse(changes, code):
    with pytest.raises(ScheduleRefusal) as caught:
        _facts(ceiling_changes=changes)
    assert caught.value.code is code


def test_at_resource_ceiling_is_accepted_and_missing_node_unit_refuses():
    _facts()
    registry = _registry()
    graph = resolve_v2(_document(), registry)
    data = compile_data_requirement_plan(graph)
    resource = compile_resource_plan(
        graph, data, registry, cache_bytes_upper_bound=128,
        artifact_bytes_upper_bound=0, queue_concurrency_upper_bound=2,
    )
    conditional = next(record for record in data.requirements if record["authored_node_id"] == "dependent")
    with pytest.raises(ScheduleRefusal) as caught:
        compile_evaluation_schedule(
            owner_id="owner-a", assignment_id="assignment-a",
            resolved_graph=graph, data_requirement_plan=data, resource_plan=resource,
            registry=registry, gate_node_id="gate",
            conditional_requirement_selector=_selector(conditional),
            unit_contract_addresses={"gate": _address("unit-gate")},
            event_unit_address=_address("event-unit-seconds"), mode="paper",
            trigger_rates={"completed_bar": {"events": 1, "per_seconds": 1}},
            resource_ceiling=compile_schedule_resource_ceiling(
                history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
                cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
                event_rate_events=1, event_rate_per_seconds=1,
                policy_address=_address("resource-ceiling"),
            ),
        )
    assert caught.value.code is ScheduleRefusalCode.UNIT_AMBIGUOUS


def test_compiler_owned_fact_constructors_and_forged_copies_are_closed():
    registry, graph, data, _resource, schedule, _conditional = _facts()
    event = admit_evaluation_event(
        schedule, trigger="completed_bar", observation_address=_address("observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1),
        recorded_at=_time(2), cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    )
    gate = admit_authored_acquisition_gate(
        schedule, data_requirement_plan=data, outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    assessment, eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    for fact_type in (
        type(schedule), type(event), type(gate), ConditionalAcquisitionAuthority,
    ):
        with pytest.raises(TypeError):
            fact_type()
    for fact, changes in (
        (schedule, {"registry_snapshot_address": _address("other-registry")}),
        (event, {"trigger": "tick"}),
        (gate, {"decision_input_address": _address("other-gate-input")}),
        (authority, {"result": AcquisitionSupport.SUPPORTED}),
    ):
        with pytest.raises(TypeError):
            replace(fact, **changes)


def _self_consistent_fact_copy(fact, **changes):
    copied = object.__new__(type(fact))
    for name in fact.__dataclass_fields__:
        if hasattr(fact, name):
            object.__setattr__(copied, name, changes.get(name, getattr(fact, name)))
    if type(fact).__name__ == "EvaluationScheduleAddress":
        object.__setattr__(copied, "schedule_address", content_address(
            evaluation_schedule_module._schedule_payload(copied)))
    elif type(fact).__name__ == "EvaluationEventAddress":
        object.__setattr__(copied, "event_address", content_address(
            evaluation_schedule_module._event_payload(copied)))
    elif type(fact).__name__ == "AuthoredAcquisitionGate":
        object.__setattr__(copied, "gate_address", content_address(
            evaluation_schedule_module._gate_payload(copied)))
    elif type(fact).__name__ == "ConditionalAcquisitionAuthority":
        copied.__post_init__()
    return copied


def _mutate_issued_and_readdress(fact, **changes):
    for name, value in changes.items():
        object.__setattr__(fact, name, value)
    if type(fact).__name__ == "EvaluationScheduleAddress":
        object.__setattr__(fact, "schedule_address", content_address(
            evaluation_schedule_module._schedule_payload(fact)))
    elif type(fact).__name__ == "EvaluationEventAddress":
        object.__setattr__(fact, "event_address", content_address(
            evaluation_schedule_module._event_payload(fact)))
    elif type(fact).__name__ == "AuthoredAcquisitionGate":
        object.__setattr__(fact, "gate_address", content_address(
            evaluation_schedule_module._gate_payload(fact)))
    elif type(fact).__name__ == "ConditionalAcquisitionAuthority":
        fact.__post_init__()
    elif type(fact).__name__ == "ScheduleResourceCeiling":
        fact.__post_init__()
    return fact


@pytest.mark.parametrize("changes", [
    {"owner_id": "owner-mutated"},
    {"assignment_id": "assignment-mutated"},
    {"declared_triggers": ("tick",)},
    {"event_unit_address": _address("mutated-event-unit")},
    {"maximum_age_seconds": 86_400},
    {"resolved_graph_address": _address("mutated-resolved-graph")},
    {"data_requirement_plan_address": _address("mutated-data-plan")},
    {"resource_plan_address": _address("mutated-resource-plan")},
])
def test_issued_schedule_original_fingerprint_rejects_in_place_readdress(changes):
    schedule = _mutate_issued_and_readdress(_facts()[4], **changes)
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_schedule(schedule)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            schedule, trigger=schedule.declared_triggers[0],
            observation_address=_address("observation"),
            event_at=_time(0), completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(2),
            unit_contract_address=schedule.event_unit_address,
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_issued_schedule_address_only_mutation_refuses():
    schedule = _facts()[4]
    object.__setattr__(schedule, "schedule_address", _address("mutated-schedule-address"))
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_schedule(schedule)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_issued_event_gate_and_conditional_authority_original_fingerprints_refuse_mutation():
    registry, graph, data, _resource, schedule, conditional = _facts()
    event = admit_evaluation_event(
        schedule, trigger="completed_bar", observation_address=_address("observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1),
        recorded_at=_time(2), cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    )
    _mutate_issued_and_readdress(event, trigger="tick")
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_event(event)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY

    gate = admit_authored_acquisition_gate(
        schedule, data_requirement_plan=data, outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    _mutate_issued_and_readdress(
        gate,
        outcome=AuthoredGateOutcome.REQUIRED,
        authority_address=_address("fabricated-authority"),
        conditional_requirement_selector=_selector(conditional),
        conditional_requirement=conditional,
    )
    with pytest.raises(ScheduleRefusal) as caught:
        verify_authored_acquisition_gate(gate)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY

    assessment, eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    assert authority.result is AcquisitionSupport.UNSUPPORTED
    _mutate_issued_and_readdress(authority, result=AcquisitionSupport.SUPPORTED)
    with pytest.raises(ScheduleRefusal) as caught:
        verify_conditional_acquisition_authority(authority)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    with pytest.raises(ScheduleRefusal) as caught:
        admit_authored_acquisition_gate(
            schedule, data_requirement_plan=data, outcome=AuthoredGateOutcome.REQUIRED,
            decision_input_address=_address("gate-input"), authority=authority,
            capability_assessment=assessment, eligibility_result=eligibility,
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_resource_ceiling_is_factory_issued_and_original_state_sealed():
    values = {
        "history_bytes_upper_bound": 256,
        "memory_bytes_upper_bound": 400,
        "cache_bytes_upper_bound": 128,
        "queue_concurrency_upper_bound": 2,
        "event_rate_events": 1,
        "event_rate_per_seconds": 1,
        "policy_address": _address("resource-ceiling"),
    }
    with pytest.raises(TypeError):
        ScheduleResourceCeiling(**values)
    ceiling = compile_schedule_resource_ceiling(**values)
    ceiling_snapshot = verify_schedule_resource_ceiling(ceiling)
    assert ceiling_snapshot == ceiling and ceiling_snapshot is not ceiling
    copied = _self_consistent_fact_copy(ceiling)
    with pytest.raises(ScheduleRefusal):
        verify_schedule_resource_ceiling(copied)
    for changes in (
        {"memory_bytes_upper_bound": 4_000},
        {"policy_address": _address("other-resource-policy")},
    ):
        mutated = _mutate_issued_and_readdress(
            compile_schedule_resource_ceiling(**values), **changes)
        with pytest.raises(ScheduleRefusal) as caught:
            verify_schedule_resource_ceiling(mutated)
        assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_schedule_compiler_rejects_mutated_issued_resource_ceiling():
    registry, graph, data, resource, _schedule, conditional = _facts()
    ceiling = compile_schedule_resource_ceiling(
        history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
        cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
        event_rate_events=1, event_rate_per_seconds=1,
        policy_address=_address("resource-ceiling"),
    )
    _mutate_issued_and_readdress(ceiling, memory_bytes_upper_bound=4_000)
    with pytest.raises(ScheduleRefusal) as caught:
        _compile_with_ceiling(registry, graph, data, resource, conditional, ceiling)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_fresh_module_rejects_old_objects_and_exact_recompile_restores_equal_addresses():
    registry, graph, data, resource, schedule, conditional = _facts()
    source = Path(evaluation_schedule_module.__file__)
    module_name = "app.ir._evaluation_schedule_fresh_state_seal_test"
    spec = importlib.util.spec_from_file_location(module_name, source)
    assert spec is not None and spec.loader is not None
    fresh = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = fresh
    try:
        spec.loader.exec_module(fresh)
        with pytest.raises(fresh.ScheduleRefusal) as caught:
            fresh.verify_evaluation_schedule(schedule)
        assert caught.value.code is fresh.ScheduleRefusalCode.INVALID_AUTHORITY
        ceiling = fresh.compile_schedule_resource_ceiling(
            history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
            cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
            event_rate_events=1, event_rate_per_seconds=1,
            policy_address=_address("resource-ceiling"),
        )
        recompiled = _compile_with_ceiling(
            registry, graph, data, resource, conditional, ceiling, module=fresh)
        assert recompiled.schedule_address == schedule.schedule_address
        fresh_snapshot = fresh.verify_evaluation_schedule(recompiled)
        assert fresh_snapshot == recompiled and fresh_snapshot is not recompiled
        assert type(recompiled) is not type(schedule)
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize("changes", [
    {"owner_id": "owner-forged"},
    {"assignment_id": "assignment-forged"},
    {"declared_triggers": ("tick",)},
    {"event_unit_address": _address("forged-event-unit")},
    {"maximum_age_seconds": 86_400},
])
def test_event_admission_rejects_self_consistent_schedule_copies_before_fields(changes):
    forged = _self_consistent_fact_copy(_facts()[4], **changes)
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            forged,
            trigger=forged.declared_triggers[0],
            observation_address=_address("observation"),
            event_at=_time(0), completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(62),
            unit_contract_address=forged.event_unit_address,
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_public_verifiers_require_factory_identity_and_issuance_is_process_local():
    registry, graph, data, _resource, schedule, _conditional = _facts()
    event = admit_evaluation_event(
        schedule, trigger="completed_bar", observation_address=_address("observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1),
        recorded_at=_time(2), cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    )
    gate = admit_authored_acquisition_gate(
        schedule, data_requirement_plan=data, outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    _assessment, _eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    for fact, verifier in (
        (schedule, verify_evaluation_schedule),
        (event, verify_evaluation_event),
        (gate, verify_authored_acquisition_gate),
        (authority, verify_conditional_acquisition_authority),
    ):
        detached = verifier(fact)
        assert detached == fact and detached is not fact
    for fact, verifier in (
        (_self_consistent_fact_copy(schedule), verify_evaluation_schedule),
        (_self_consistent_fact_copy(event), verify_evaluation_event),
        (_self_consistent_fact_copy(gate), verify_authored_acquisition_gate),
        (_self_consistent_fact_copy(authority), verify_conditional_acquisition_authority),
    ):
        with pytest.raises(ScheduleRefusal) as caught:
            verifier(fact)
        assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    key = (type(schedule), id(schedule))
    with evaluation_schedule_module._ISSUED_LOCK:
        evaluation_schedule_module._ISSUED_FACTS.pop(key)
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_schedule(schedule)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_verifier_returns_detached_unissued_deep_original_snapshot():
    registry, graph, data, _resource, schedule, _conditional = _facts()
    snapshot = verify_evaluation_schedule(schedule)
    assert snapshot == schedule
    assert snapshot is not schedule
    assert snapshot.trigger_rates is not schedule.trigger_rates
    assert snapshot.trigger_rates[0] is not schedule.trigger_rates[0]
    with pytest.raises(ScheduleRefusal) as caught:
        verify_evaluation_schedule(snapshot)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    _assessment, _eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    authority_snapshot = verify_conditional_acquisition_authority(authority)
    assert authority_snapshot == authority and authority_snapshot is not authority
    with pytest.raises(ScheduleRefusal):
        verify_conditional_acquisition_authority(authority_snapshot)
    event = admit_evaluation_event(
        schedule, trigger="completed_bar", observation_address=_address("observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1),
        recorded_at=_time(2), cutoff_at=_time(2),
        unit_contract_address=_address("event-unit-seconds"),
    )
    event_snapshot = verify_evaluation_event(event)
    assert event_snapshot is not event
    assert event_snapshot.event_at is not event.event_at
    assert event_snapshot.event_at.tzinfo is UTC


def test_issued_seal_original_state_does_not_alias_live_fact_fields():
    schedule = _facts()[4]
    key = (type(schedule), id(schedule))
    with evaluation_schedule_module._ISSUED_LOCK:
        seal = evaluation_schedule_module._ISSUED_FACTS[key]
    assert seal.original_state is not schedule.__dict__
    assert seal.original_state["trigger_rates"] is not schedule.trigger_rates
    assert seal.original_state["trigger_rates"][0] is not schedule.trigger_rates[0]
    original_owner = seal.original_state["owner_id"]
    original_trigger = seal.original_state["declared_triggers"]
    _mutate_issued_and_readdress(
        schedule, owner_id="mutated-owner", declared_triggers=("tick",))
    assert seal.original_state["owner_id"] == original_owner
    assert seal.original_state["declared_triggers"] == original_trigger


def test_event_uses_detached_schedule_when_shared_fact_changes_after_verification(monkeypatch):
    _registry_value, _graph, _data, _resource, schedule, _conditional = _facts()
    original_address = schedule.schedule_address
    verified = threading.Barrier(2)
    resume = threading.Barrier(2)
    real_verify = evaluation_schedule_module.verify_evaluation_schedule

    def paused_verify(value):
        snapshot = real_verify(value)
        verified.wait()
        resume.wait()
        return snapshot

    monkeypatch.setattr(evaluation_schedule_module, "verify_evaluation_schedule", paused_verify)
    result = {}

    def run():
        try:
            result["event"] = admit_evaluation_event(
                schedule, trigger="completed_bar", observation_address=_address("observation"),
                event_at=_time(0), completed_at=_time(1), available_at=_time(1),
                recorded_at=_time(2), cutoff_at=_time(2),
                unit_contract_address=_address("event-unit-seconds"),
            )
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    verified.wait()
    _mutate_issued_and_readdress(
        schedule,
        owner_id="owner-mutated", assignment_id="assignment-mutated",
        declared_triggers=("tick",), event_unit_address=_address("mutated-event-unit"),
        maximum_age_seconds=0, resolved_graph_address=_address("mutated-graph"),
        data_requirement_plan_address=_address("mutated-data-plan"),
        resource_plan_address=_address("mutated-resource-plan"),
    )
    resume.wait()
    worker.join(5)
    assert not worker.is_alive()
    assert "error" not in result
    assert result["event"].schedule_address == original_address
    assert result["event"].trigger == "completed_bar"


def test_gate_and_conditional_verifiers_detach_before_shared_mutation(monkeypatch):
    registry, graph, data, _resource, schedule, conditional = _facts()
    gate = admit_authored_acquisition_gate(
        schedule, data_requirement_plan=data, outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    gate_verified = threading.Barrier(2)
    gate_resume = threading.Barrier(2)
    real_gate_verify = evaluation_schedule_module.verify_authored_acquisition_gate
    gate_result = {}

    def run_gate_verify():
        snapshot = real_gate_verify(gate)
        gate_verified.wait()
        gate_resume.wait()
        gate_result["snapshot"] = snapshot

    worker = threading.Thread(target=run_gate_verify)
    worker.start()
    gate_verified.wait()
    _mutate_issued_and_readdress(
        gate, outcome=AuthoredGateOutcome.REQUIRED,
        authority_address=_address("fabricated-authority"),
        conditional_requirement_selector=_selector(conditional),
        conditional_requirement=conditional,
    )
    gate_resume.wait()
    worker.join(5)
    assert gate_result["snapshot"].outcome is AuthoredGateOutcome.NOT_REQUIRED
    assert gate_result["snapshot"].authority_address is None

    assessment, eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    authority_verified = threading.Barrier(2)
    authority_resume = threading.Barrier(2)
    real_authority_verify = evaluation_schedule_module.verify_conditional_acquisition_authority

    def paused_authority(value):
        snapshot = real_authority_verify(value)
        authority_verified.wait()
        authority_resume.wait()
        return snapshot

    monkeypatch.setattr(
        evaluation_schedule_module, "verify_conditional_acquisition_authority",
        paused_authority,
    )
    result = {}

    def run_gate_admission():
        try:
            admit_authored_acquisition_gate(
                schedule, data_requirement_plan=data,
                outcome=AuthoredGateOutcome.REQUIRED,
                decision_input_address=_address("gate-input"), authority=authority,
                capability_assessment=assessment, eligibility_result=eligibility,
            )
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=run_gate_admission)
    worker.start()
    authority_verified.wait()
    _mutate_issued_and_readdress(authority, result=AcquisitionSupport.SUPPORTED)
    authority_resume.wait()
    worker.join(5)
    assert isinstance(result.get("error"), ScheduleRefusal)
    assert result["error"].code is ScheduleRefusalCode.CAPABILITY_UNSUPPORTED


def test_resource_preflight_uses_detached_original_ceiling_after_barrier(monkeypatch):
    registry, graph, data, resource, _schedule, conditional = _facts()
    ceiling = compile_schedule_resource_ceiling(
        history_bytes_upper_bound=256, memory_bytes_upper_bound=399,
        cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
        event_rate_events=1, event_rate_per_seconds=1,
        policy_address=_address("resource-ceiling"),
    )
    verified = threading.Barrier(2)
    resume = threading.Barrier(2)
    real_verify = evaluation_schedule_module.verify_schedule_resource_ceiling

    def paused_verify(value):
        snapshot = real_verify(value)
        verified.wait()
        resume.wait()
        return snapshot

    monkeypatch.setattr(evaluation_schedule_module, "verify_schedule_resource_ceiling", paused_verify)
    result = {}

    def run():
        try:
            result["schedule"] = _compile_with_ceiling(
                registry, graph, data, resource, conditional, ceiling)
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    verified.wait()
    _mutate_issued_and_readdress(
        ceiling, memory_bytes_upper_bound=4_000,
        policy_address=_address("mutated-resource-policy"),
    )
    resume.wait()
    worker.join(5)
    assert isinstance(result.get("error"), ScheduleRefusal)
    assert result["error"].code is ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED


def test_forged_supported_authority_and_gate_cannot_cross_issuance_boundary():
    registry, graph, data, _resource, schedule, conditional = _facts()
    assessment, eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule)
    forged_authority = _self_consistent_fact_copy(
        authority, result=AcquisitionSupport.SUPPORTED)
    with pytest.raises(ScheduleRefusal) as caught:
        admit_authored_acquisition_gate(
            schedule,
            data_requirement_plan=data,
            outcome=AuthoredGateOutcome.REQUIRED,
            decision_input_address=_address("gate-input"),
            authority=forged_authority,
            capability_assessment=assessment,
            eligibility_result=eligibility,
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    legitimate_gate = admit_authored_acquisition_gate(
        schedule, data_requirement_plan=data, outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    forged_gate = _self_consistent_fact_copy(
        legitimate_gate,
        outcome=AuthoredGateOutcome.REQUIRED,
        authority_address=forged_authority.authority_address,
        conditional_requirement_selector=_selector(conditional),
        conditional_requirement=conditional,
    )
    with pytest.raises(ScheduleRefusal) as caught:
        verify_authored_acquisition_gate(forged_gate)
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_stale_data_plan_and_invalid_observation_address_refuse():
    registry, graph, data, resource, schedule, conditional = _facts()
    with pytest.raises(ScheduleRefusal) as caught:
        compile_evaluation_schedule(
            owner_id="owner-a", assignment_id="assignment-a",
            resolved_graph=graph,
            data_requirement_plan=replace(data, plan_address=_address("stale-data-plan")),
            resource_plan=resource,
            registry=registry,
            gate_node_id="gate",
            conditional_requirement_selector=_selector(conditional),
            unit_contract_addresses={node.node_id: _address(f"unit-{node.node_id}") for node in graph.nodes},
            event_unit_address=_address("event-unit-seconds"),
            mode="paper",
            trigger_rates={"completed_bar": {"events": 1, "per_seconds": 1}},
            resource_ceiling=compile_schedule_resource_ceiling(
                history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
                cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
                event_rate_events=1, event_rate_per_seconds=1,
                policy_address=_address("resource-ceiling"),
            ),
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    with pytest.raises(ScheduleRefusal) as caught:
        admit_evaluation_event(
            schedule, trigger="completed_bar", observation_address="missing-address",
            event_at=_time(0), completed_at=_time(1), available_at=_time(1),
            recorded_at=_time(2), cutoff_at=_time(2),
            unit_contract_address=_address("event-unit-seconds"),
        )
    assert caught.value.code is ScheduleRefusalCode.INVALID_CONTENT_ADDRESS


def test_event_rate_above_ceiling_and_unsupported_live_mode_refuse():
    with pytest.raises(ScheduleRefusal) as caught:
        _facts(ceiling_changes={"event_rate_events": 1, "event_rate_per_seconds": 2})
    assert caught.value.code is ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED
    registry = _registry()
    graph = resolve_v2(_document(), registry)
    data = compile_data_requirement_plan(graph)
    resource = compile_resource_plan(
        graph, data, registry, cache_bytes_upper_bound=128,
        artifact_bytes_upper_bound=0, queue_concurrency_upper_bound=2,
    )
    conditional = next(record for record in data.requirements if record["authored_node_id"] == "dependent")
    with pytest.raises(ScheduleRefusal) as caught:
        compile_evaluation_schedule(
            owner_id="owner-a", assignment_id="assignment-a",
            resolved_graph=graph, data_requirement_plan=data, resource_plan=resource,
            registry=registry, gate_node_id="gate",
            conditional_requirement_selector=_selector(conditional),
            unit_contract_addresses={node.node_id: _address(f"unit-{node.node_id}") for node in graph.nodes},
            event_unit_address=_address("event-unit-seconds"), mode="live",
            trigger_rates={"completed_bar": {"events": 1, "per_seconds": 1}},
            resource_ceiling=compile_schedule_resource_ceiling(
                history_bytes_upper_bound=256, memory_bytes_upper_bound=400,
                cache_bytes_upper_bound=128, queue_concurrency_upper_bound=2,
                event_rate_events=1, event_rate_per_seconds=1,
                policy_address=_address("resource-ceiling"),
            ),
        )
    assert caught.value.code is ScheduleRefusalCode.UNSUPPORTED_MODE


def test_schedule_module_cannot_reach_runtime_provider_persistence_or_money_paths():
    source = Path(__file__).parents[1] / "app/ir/evaluation_schedule.py"
    text = source.read_text()
    forbidden = (
        "app.ir.runtime", "app.ir.incremental_runtime", "app.providers",
        "app.monitoring", "app.db", "app.api", "app.engine", "app.execution",
        "app.ledger", "app.backtest",
    )
    assert not [name for name in forbidden if name in text]


def _completed_bar_graph_authorities(registry, document, fields):
    """Bind a real authored graph to the shared bounded physical input fixture."""
    from app.ir.incremental_runtime import accept_research_resource_plan
    from tests.test_indicator_accuracy_contract_assurance import context, input_facts
    graph = resolve_v2(document, registry)
    fact = input_facts()["price_feed"]
    fact.update(fields=list(fields), timeframe=60, derived_local=False,
                freshness={"maximum_age_seconds": 60})
    bindings = context({"frame": fact})
    data = compile_data_requirement_plan(graph, registry=registry, input_bindings=bindings)
    resource = accept_research_resource_plan(graph, data, registry, input_bindings=bindings).plan
    return registry, graph, data, resource


def _completed_bar_authority_cases(registry):
    """Production preset components with bounded synthetic physical input facts."""
    from app.ir.original_strategy_presets import instantiate_preset
    return {preset: _completed_bar_graph_authorities(registry,
                instantiate_preset(preset, "completed-bar-" + preset), fields)
            for preset, fields in (("trend_impulse_v3", ["CLOSE"]),
                                   ("expanding_z_v4", ["CLOSE", "HIGH", "LOW"]))}


@pytest.fixture(scope="module")
def completed_bar_authorities():
    from tests.test_strategy_registry import _original_preset_registry
    return _completed_bar_authority_cases(_original_preset_registry())


@pytest.fixture(scope="module")
def platform_completed_bar_authorities():
    from app.ir.library import REGISTRY
    return _completed_bar_authority_cases(REGISTRY)


def _completed_bar_args(facts, **changes):
    registry, graph, data, resource = facts
    values = dict(owner_id="owner-assurance", assignment_id="completed-bar-assignment",
        resolved_graph=graph, data_requirement_plan=data, resource_plan=resource, registry=registry,
        unit_contract_addresses={node.node_id: _address("unit-" + node.node_id) for node in graph.nodes},
        event_unit_address=_address("event-unit-seconds"), mode="research",
        trigger_rates={"completed_bar": {"events": 1, "per_seconds": 60}},
        resource_ceiling=compile_schedule_resource_ceiling(
            history_bytes_upper_bound=sum(row["bytes_upper_bound"] for row in resource.document["history_requirements"]),
            memory_bytes_upper_bound=resource.document["memory_bytes_upper_bound"],
            cache_bytes_upper_bound=resource.document["cache_bytes_upper_bound"],
            queue_concurrency_upper_bound=resource.document["queue_concurrency_upper_bound"],
            event_rate_events=1, event_rate_per_seconds=60, policy_address=_address("completed-bar-ceiling")))
    values.update(changes)
    return values


def _completed_schedule(facts, **changes):
    return evaluation_schedule_module.compile_completed_bar_evaluation_schedule(**_completed_bar_args(facts, **changes))


def _completed_event(schedule, **changes):
    values = dict(trigger="completed_bar", observation_address=_address("completed-observation"),
        event_at=_time(0), completed_at=_time(1), available_at=_time(1), recorded_at=_time(2),
        cutoff_at=_time(2), unit_contract_address=_address("event-unit-seconds"))
    values.update(changes)
    return admit_evaluation_event(schedule, **values)


@pytest.mark.parametrize("preset", ["trend_impulse_v3", "expanding_z_v4"])
def test_completed_bar_schedule_accepts_real_registered_presets(platform_completed_bar_authorities, preset):
    facts = platform_completed_bar_authorities[preset]
    registry, graph, data, resource = facts
    schedule = _completed_schedule(facts)
    assert schedule == _completed_schedule(facts)
    assert verify_evaluation_schedule(schedule) == schedule
    assert schedule.registry_snapshot_address == registry.registry_snapshot_address
    assert all(node.component[0].startswith("strategy_math.") for node in graph.nodes)
    assert all(record["requirement"]["instrument"]["type"] == "PHYSICAL" for record in data.requirements)
    assert schedule.gate_node_id is schedule.conditional_requirement_selector is None
    assert schedule.authored_gate_nodes == schedule.dependent_nodes == ()
    assert set(schedule.unconditional_nodes) == {node.node_id for node in graph.nodes}
    positions = {node: index for index, node in enumerate(schedule.unconditional_nodes)}
    for edge in graph.topology_document["edges"]:
        source, target = edge["source"], edge["target"]
        if source["scope"] == target["scope"] == "node":
            assert positions[source["node_id"]] < positions[target["node_id"]]
    payload = evaluation_schedule_module._schedule_payload(schedule)
    assert payload["schema"] == "evaluation-schedule/2"
    assert payload["evaluation_kind"] == "COMPLETED_BAR"
    assert "gate_node_id" not in payload and "conditional_requirement_selector" not in payload
    assert payload["phases"] == {"unconditional": list(schedule.unconditional_nodes)}
    assert schedule.schedule_address == content_address(payload)
    event = _completed_event(schedule)
    assert event.schedule_address == schedule.schedule_address
    assert verify_evaluation_event(event) == event
    assert _completed_event(schedule) == event


def test_legacy_conditional_schedule_preserves_exact_v1_payload():
    _, graph, data, resource, schedule, conditional = _facts()
    expected = {
        "schema": "evaluation-schedule/1", "owner_id": "owner-a", "assignment_id": "assignment-a",
        "authored_ir_address": graph.authored_ir_address, "resolved_graph_address": graph.resolved_graph_address,
        "implementation_closure_address": graph.implementation_closure_address,
        "registry_snapshot_address": graph.registry_snapshot_address,
        "data_requirement_plan_address": data.plan_address, "resource_plan_address": resource.plan_address,
        "mode": "paper", "gate_node_id": "gate", "conditional_requirement_selector": _selector(conditional),
        "phases": {"unconditional": ["independent", "source"], "authored_gate": ["gate"], "dependent": ["dependent"]},
        "declared_triggers": ["completed_bar"],
        "trigger_rates": [{"trigger": "completed_bar", "events": 1, "per_seconds": 1}],
        "reset_requirements": _plain(resource.document["state_requirements"]),
        "unit_contract_addresses": [{"node_id": node, "unit_contract_address": _address("unit-" + node)}
                                    for node in ("dependent", "gate", "independent", "source")],
        "event_unit_address": _address("event-unit-seconds"), "maximum_age_seconds": 60,
        "resource_ceiling_address": schedule.resource_ceiling_address,
    }
    assert canonical_json(evaluation_schedule_module._schedule_payload(schedule)) == canonical_json(expected)
    assert schedule.schedule_address == content_address(expected)


@pytest.mark.parametrize("changes,code", [
    ({"completed_at": _time(3)}, ScheduleRefusalCode.FORMING_OBSERVATION),
    ({"event_at": _time(3)}, ScheduleRefusalCode.FUTURE_EVENT),
    ({"cutoff_at": _time(62)}, ScheduleRefusalCode.STALE_OBSERVATION),
    ({"available_at": _time(3)}, ScheduleRefusalCode.LATE_UNAVAILABLE),
    ({"unit_contract_address": _address("foreign-unit")}, ScheduleRefusalCode.UNIT_AMBIGUOUS),
    ({"trigger": "tick"}, ScheduleRefusalCode.UNDECLARED_TRIGGER),
])
def test_completed_bar_events_keep_causal_guards(completed_bar_authorities, changes, code):
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"])
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_event(schedule, **changes)
    assert caught.value.code is code


@pytest.mark.parametrize("changes,code", [
    ({"mode": "paper"}, ScheduleRefusalCode.UNSUPPORTED_MODE),
    ({"mode": "live"}, ScheduleRefusalCode.UNSUPPORTED_MODE),
    ({"owner_id": ""}, ScheduleRefusalCode.INVALID_AUTHORITY),
    ({"unit_contract_addresses": {}}, ScheduleRefusalCode.UNIT_AMBIGUOUS),
    ({"trigger_rates": {"completed_bar": {"events": 2, "per_seconds": 60}}}, ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED),
    ({"trigger_rates": {"tick": {"events": 1, "per_seconds": 60}}}, ScheduleRefusalCode.UNDECLARED_TRIGGER),
])
def test_completed_bar_schedule_keeps_mode_units_scope_and_rate_limits(completed_bar_authorities, changes, code):
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule(completed_bar_authorities["trend_impulse_v3"], **changes)
    assert caught.value.code is code


def test_completed_bar_schedule_rejects_conditional_data_plan():
    registry, graph, data, resource, _, _ = _facts()
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule((registry, graph, data, resource))
    assert caught.value.code is ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID


@pytest.mark.parametrize("changes", [
    {"conditional_requirement_selector": _address("conditional")},
    {"authored_gate_nodes": ("invented-gate",)}, {"dependent_nodes": ("invented-dependent",)},
    {"mode": "paper"}, {"declared_triggers": ("tick",)},
    {"gate_node_id": "invented-gate"},
])
def test_completed_bar_closed_shape_rejects_mixed_variants(completed_bar_authorities, changes):
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"])
    for name, value in changes.items():
        object.__setattr__(schedule, name, value)
    with pytest.raises(ScheduleRefusal):
        evaluation_schedule_module._require_schedule_runtime_shape(schedule)
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_schedule(schedule)


@pytest.mark.parametrize("changes", [
    {"owner_id": "another-owner"}, {"assignment_id": "another-assignment"},
    {"unconditional_nodes": ()}, {"maximum_age_seconds": 1000},
])
def test_completed_bar_seal_rejects_in_place_readdress_and_forged_copy(completed_bar_authorities, changes):
    import copy
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"])
    forged = copy.copy(schedule)
    with pytest.raises(ScheduleRefusal):
        _completed_event(forged)
    _mutate_issued_and_readdress(schedule, **changes)
    with pytest.raises(ScheduleRefusal):
        _completed_event(schedule)


def test_completed_bar_event_identity_stays_bound_to_owner_assignment(completed_bar_authorities):
    facts = completed_bar_authorities["trend_impulse_v3"]
    first = _completed_event(_completed_schedule(facts))
    second = _completed_event(_completed_schedule(facts, owner_id="another-owner"))
    assert first.schedule_address != second.schedule_address
    assert first.event_address != second.event_address
    _mutate_issued_and_readdress(first, schedule_address=second.schedule_address)
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_event(first)


def test_completed_bar_schedule_cannot_open_conditional_acquisition(completed_bar_authorities):
    facts = completed_bar_authorities["trend_impulse_v3"]
    schedule = _completed_schedule(facts)
    with pytest.raises(ScheduleRefusal, match="do not authorize conditional"):
        compile_conditional_acquisition_authority(schedule, data_requirement_plan=facts[2],
            capability_assessment=None, eligibility_result=None)
    for outcome in AuthoredGateOutcome:
        with pytest.raises(ScheduleRefusal, match="do not authorize conditional"):
            admit_authored_acquisition_gate(schedule, data_requirement_plan=facts[2], outcome=outcome,
                decision_input_address=_address("must-not-invent-gate"))


def _readdress_resource(resource, **changes):
    from app.ir.resource_plan import ResourcePlan
    document = _plain(resource.document)
    document.update(changes)
    document.pop("plan_address")
    document["plan_address"] = content_address(document)
    return ResourcePlan(evaluation_schedule_module._freeze(document), document["plan_address"])


@pytest.mark.parametrize("changes", [
    {"instrument": {"role": "primary", "type": "ECONOMIC_SELECTOR"}},
    {"instrument": {"role": "primary", "type": "CONTINUOUS_FUTURE"}},
    {"field": "BID"}, {"depth": {"kind": "BOOK", "levels": 5}},
    {"depth": {"kind": "NONE", "levels": 1}}, {"derived_local": True},
])
def test_completed_bar_schedule_rejects_readdressed_non_ohlcv_demand(completed_bar_authorities, changes):
    registry, graph, data, resource = completed_bar_authorities["trend_impulse_v3"]
    records = _plain(data.requirements)
    records[0]["requirement"].update(changes)
    changed = replace(data, requirements=evaluation_schedule_module._freeze(records))
    changed = replace(changed, plan_address=content_address(evaluation_schedule_module._data_plan_payload(changed)))
    rebound = _readdress_resource(resource, data_requirement_plan_address=changed.plan_address)
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule((registry, graph, changed, rebound))
    assert caught.value.code is ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID


def test_completed_bar_schedule_rejects_other_declared_triggers(completed_bar_authorities):
    registry, graph, data, resource = completed_bar_authorities["trend_impulse_v3"]
    triggers = [{**_plain(row), "trigger": "tick"} for row in resource.document["trigger_requirements"]]
    changed = _readdress_resource(resource, trigger_requirements=triggers)
    with pytest.raises(ScheduleRefusal, match="requires only completed_bar"):
        _completed_schedule((registry, graph, data, changed),
            trigger_rates={"tick": {"events": 1, "per_seconds": 60}})


def test_completed_bar_demand_requires_completed_node_contracts(completed_bar_authorities):
    from types import SimpleNamespace
    registry, graph, data, _ = completed_bar_authorities["trend_impulse_v3"]
    contracts = dict(registry.node_contracts)
    key = graph.nodes[0].component
    contracts[key] = {**_plain(contracts[key]), "bar_policy": "PARTIAL_ALLOWED"}
    with pytest.raises(ScheduleRefusal, match="node does not require completed bars"):
        evaluation_schedule_module._require_completed_bar_demand(data, graph, SimpleNamespace(node_contracts=contracts))


def test_completed_bar_schedule_keeps_memory_ceiling_and_authority_seals(completed_bar_authorities):
    facts = completed_bar_authorities["trend_impulse_v3"]
    args = _completed_bar_args(facts)
    ceiling = args["resource_ceiling"]
    smaller = compile_schedule_resource_ceiling(
        history_bytes_upper_bound=ceiling.history_bytes_upper_bound,
        memory_bytes_upper_bound=ceiling.memory_bytes_upper_bound-1,
        cache_bytes_upper_bound=ceiling.cache_bytes_upper_bound,
        queue_concurrency_upper_bound=ceiling.queue_concurrency_upper_bound,
        event_rate_events=ceiling.event_rate_events, event_rate_per_seconds=ceiling.event_rate_per_seconds,
        policy_address=ceiling.policy_address)
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule(facts, resource_ceiling=smaller)
    assert caught.value.code is ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule(facts, data_requirement_plan=replace(facts[2], plan_address=_address("forged-plan")))
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule(facts, registry=_registry())
    assert caught.value.code is ScheduleRefusalCode.INVALID_AUTHORITY


def test_completed_bar_mode_refusal_precedes_conditional_demand():
    registry, graph, data, resource, _, _ = _facts()
    # This legacy plan permits paper, so the new entry point must reject paper
    # itself before inspecting the plan's unrelated conditional demand.
    assert resource.document["mode_support"]["paper"] is True
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule((registry, graph, data, resource), mode="paper")
    assert caught.value.code is ScheduleRefusalCode.UNSUPPORTED_MODE


def _precise_event_values():
    return dict(event_at=_time(0)+timedelta(microseconds=1),
        completed_at=_time(1)+timedelta(microseconds=1),
        available_at=_time(1)+timedelta(microseconds=2),
        recorded_at=_time(1)+timedelta(microseconds=4),
        cutoff_at=_time(1)+timedelta(microseconds=4))


def test_completed_bar_event_preserves_microseconds_and_detached_original_state(completed_bar_authorities):
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"])
    clocks = _precise_event_values()
    first = _completed_event(schedule, **clocks)
    second = _completed_event(schedule, **{**clocks, "available_at": clocks["available_at"]+timedelta(microseconds=1)})
    assert first.event_address != second.event_address
    assert first.clock_precision == second.clock_precision == "MICROSECOND"
    payload = evaluation_schedule_module._event_payload(first)
    assert payload["schema"] == "evaluation-event/2"
    assert payload["clock_precision"] == "MICROSECOND"
    for name, expected in clocks.items():
        assert getattr(first, name) == expected
        assert payload[name] == expected.isoformat().replace("+00:00", "Z")
    detached = verify_evaluation_event(first)
    assert detached == first
    assert detached.available_at is not first.available_at
    assert detached.available_at.microsecond == 2
    _mutate_issued_and_readdress(first, available_at=second.available_at)
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_event(first)
    assert detached.available_at == clocks["available_at"]


@pytest.mark.parametrize("field,instant,code", [
    ("event_at", _time(1)+timedelta(microseconds=5), ScheduleRefusalCode.FUTURE_EVENT),
    ("completed_at", _time(1)+timedelta(microseconds=5), ScheduleRefusalCode.FORMING_OBSERVATION),
    ("available_at", _time(1)+timedelta(microseconds=5), ScheduleRefusalCode.LATE_UNAVAILABLE),
    ("recorded_at", _time(1)+timedelta(microseconds=5), ScheduleRefusalCode.LATE_UNAVAILABLE),
    ("available_at", _time(1), ScheduleRefusalCode.AVAILABILITY_BEFORE_COMPLETION),
    ("recorded_at", _time(1)+timedelta(microseconds=1), ScheduleRefusalCode.INVALID_TIME),
    ("cutoff_at", _time(61)+timedelta(microseconds=2), ScheduleRefusalCode.STALE_OBSERVATION),
])
def test_completed_bar_event_checks_exact_subsecond_boundaries(completed_bar_authorities, field, instant, code):
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"])
    clocks = _precise_event_values()
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_event(schedule, **{**clocks, field: instant})
    assert caught.value.code is code
    at_freshness_limit = _completed_event(schedule,
        **{**clocks, "cutoff_at": clocks["completed_at"]+timedelta(seconds=60)})
    assert at_freshness_limit.cutoff_at - at_freshness_limit.completed_at == timedelta(seconds=60)


@pytest.mark.parametrize("precision", ["NANOSECOND", True, None, _ChameleonStr("MICROSECOND")])
def test_completed_bar_event_precision_is_closed(completed_bar_authorities, precision):
    event = _completed_event(_completed_schedule(completed_bar_authorities["trend_impulse_v3"]))
    object.__setattr__(event, "clock_precision", precision)
    with pytest.raises(ScheduleRefusal, match="clock precision is not closed"):
        evaluation_schedule_module._require_event_runtime_shape(event)
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_event(event)


def test_completed_bar_event_seal_rejects_precision_relabelling(completed_bar_authorities):
    event = _completed_event(_completed_schedule(completed_bar_authorities["trend_impulse_v3"]))
    _mutate_issued_and_readdress(event, clock_precision="SECOND")
    with pytest.raises(ScheduleRefusal):
        verify_evaluation_event(event)


def test_legacy_event_retains_exact_v1_payload_and_whole_seconds():
    schedule = _facts()[4]
    event = _completed_event(schedule)
    expected = {
        "schema": "evaluation-event/1", "schedule_address": schedule.schedule_address,
        "trigger": "completed_bar", "observation_address": _address("completed-observation"),
        "event_at": "2026-08-31T09:15:00Z", "completed_at": "2026-08-31T09:15:01Z",
        "available_at": "2026-08-31T09:15:01Z", "recorded_at": "2026-08-31T09:15:02Z",
        "cutoff_at": "2026-08-31T09:15:02Z", "unit_contract_address": _address("event-unit-seconds"),
    }
    assert event.clock_precision == "SECOND"
    assert canonical_json(evaluation_schedule_module._event_payload(event)) == canonical_json(expected)
    assert event.event_address == content_address(expected)
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_event(schedule, **_precise_event_values())
    assert caught.value.code is ScheduleRefusalCode.INVALID_TIME


@pytest.mark.parametrize("value", [
    _ChameleonDateTime(2026, 8, 31, 9, 15, tzinfo=UTC),
    datetime(2026, 8, 31, 9, 15),
    datetime(2026, 8, 31, 9, 15, tzinfo=timezone(timedelta(hours=1))),
])
def test_completed_bar_event_keeps_exact_immutable_utc_clocks(completed_bar_authorities, value):
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"])
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_event(schedule, event_at=value)
    assert caught.value.code is ScheduleRefusalCode.INVALID_TIME


def test_conditional_acquisition_scope_retains_all_six_bindings():
    import copy
    registry, graph, data, _, schedule, _ = _facts()
    _, _, authority = _typed_conditional_authority(registry, graph, data, schedule)
    # Matching identity is independent of support: this real authority remains
    # UNSUPPORTED and this comparison does not admit an acquisition gate.
    assert authority.result is AcquisitionSupport.UNSUPPORTED
    evaluation_schedule_module._require_acquisition_scope(authority, schedule)
    for name in ("schedule_address", "owner_id", "assignment_id", "conditional_requirement_selector",
                 "data_requirement_plan_address", "resource_plan_address"):
        foreign = copy.copy(authority)
        object.__setattr__(foreign, name, "foreign-owner" if name == "owner_id" else _address("foreign-" + name))
        with pytest.raises(ScheduleRefusal, match="conditional authority differs from schedule"):
            evaluation_schedule_module._require_acquisition_scope(foreign, schedule)


def test_completed_bar_freshness_cap_preserves_default_and_source_provenance(completed_bar_authorities):
    facts = completed_bar_authorities["trend_impulse_v3"]
    data_before = canonical_json(evaluation_schedule_module._data_plan_payload(facts[2]))
    default = _completed_schedule(facts)
    assert default.maximum_age_seconds == 60
    for cap in (None, 60, 61, 1000000):
        bounded = _completed_schedule(facts, freshness_ceiling_seconds=cap)
        assert bounded == default
        assert canonical_json(evaluation_schedule_module._schedule_payload(bounded)) \
            == canonical_json(evaluation_schedule_module._schedule_payload(default))
    capped = _completed_schedule(facts, freshness_ceiling_seconds=5)
    assert capped.maximum_age_seconds == 5
    assert capped.schedule_address != default.schedule_address
    expected = {**evaluation_schedule_module._schedule_payload(default), "maximum_age_seconds": 5}
    assert evaluation_schedule_module._schedule_payload(capped) == expected
    assert capped.schedule_address == content_address(expected)
    assert capped.data_requirement_plan_address == default.data_requirement_plan_address == facts[2].plan_address
    assert capped.resource_plan_address == default.resource_plan_address == facts[3].plan_address
    assert canonical_json(evaluation_schedule_module._data_plan_payload(facts[2])) == data_before
    assert verify_evaluation_schedule(capped) == capped


@pytest.mark.parametrize("cap", [-1, True, False, 0.0, 5.0, 100.0, "5", _ChameleonInt(5), _ChameleonInt(100)])
def test_completed_bar_freshness_cap_requires_exact_nonnegative_integer(completed_bar_authorities, cap):
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_schedule(completed_bar_authorities["trend_impulse_v3"], freshness_ceiling_seconds=cap)
    assert caught.value.code is ScheduleRefusalCode.UNIT_AMBIGUOUS


@pytest.mark.parametrize("cap", [0, 5])
def test_completed_bar_freshness_cap_controls_exact_event_deadline(completed_bar_authorities, cap):
    schedule = _completed_schedule(completed_bar_authorities["trend_impulse_v3"], freshness_ceiling_seconds=cap)
    completed = _time(1) + timedelta(microseconds=123456)
    cutoff = completed + timedelta(seconds=cap)
    event = _completed_event(schedule, completed_at=completed, available_at=completed,
        recorded_at=completed, cutoff_at=cutoff)
    assert event.cutoff_at - event.completed_at == timedelta(seconds=cap)
    with pytest.raises(ScheduleRefusal) as caught:
        _completed_event(schedule, completed_at=completed, available_at=completed,
            recorded_at=completed, cutoff_at=cutoff + timedelta(microseconds=1))
    assert caught.value.code is ScheduleRefusalCode.STALE_OBSERVATION
