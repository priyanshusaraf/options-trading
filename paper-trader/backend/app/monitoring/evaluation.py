"""Pure canonical-v2 monitoring transition compilation.

This module calls the existing v2 evaluator and translates its closed monitoring
intent outputs into the accepted monitoring state/event/alert contracts. It does
not acquire data, persist facts, run a worker, publish an API, or grant execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, DecimalException
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from app.ir import registry as registry_contract
from app.ir.evaluation_schedule import (
    EvaluationEventAddress,
    EvaluationScheduleAddress,
    ScheduleRefusal,
    verify_evaluation_event,
    verify_evaluation_schedule,
)
from app.ir.first_party import monitoring_intent_v2
from app.ir.hashing import content_address
from app.ir.implementation_identity import ImplementationUnidentified, implementation_address
from app.ir.registry import PlatformRegistry, V2ImplementationRegistration
from app.ir.resolve import (
    ResolvedV2Graph,
    ResolutionError,
    resolved_v2_graph_address,
)
from app.ir.runtime import EvaluationError, evaluate_v2
from app.ir.schema import is_content_address
from app.ir.validity import NumericValue
from app.monitoring.contracts import (
    AlertDerived,
    EntryReference,
    FactValidity,
    Freshness,
    MonitoringSignalEvent,
    NoAlert,
    ProtectionBasis,
    ProtectionEvidence,
    ProtectionKind,
    ProtectionUnits,
    SignalAction,
    StrategyState,
    derive_signal_alert,
)
from app.monitoring.state_contracts import (
    MonitoringAssignment,
    MonitoringStateSnapshot,
)
from app.monitoring.evaluation_policy import _policy_schedule_binding


MAX_GRAPH_OUTPUTS = 64
MAX_INPUT_DEPTH = 16


class MonitoringEvaluationCode(str, Enum):
    ASSIGNMENT_INVALID = "ASSIGNMENT_INVALID"
    ASSIGNMENT_INACTIVE = "ASSIGNMENT_INACTIVE"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    GRAPH_INVALID = "GRAPH_INVALID"
    INPUT_INVALID = "INPUT_INVALID"
    EVALUATION_REFUSED = "EVALUATION_REFUSED"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    TARGET_AMBIGUOUS = "TARGET_AMBIGUOUS"
    PROTECTION_MISSING = "PROTECTION_MISSING"
    PROTECTION_AMBIGUOUS = "PROTECTION_AMBIGUOUS"
    PROTECTION_INVALID = "PROTECTION_INVALID"
    STATE_INVALID = "STATE_INVALID"


class MonitoringEvaluationRefusal(ValueError):
    """A stable refusal at the pure monitoring evaluation boundary."""

    def __init__(self, code: MonitoringEvaluationCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")


@dataclass(frozen=True, slots=True)
class MonitoringEvaluationTransition:
    next_snapshot: MonitoringStateSnapshot
    signal_event: MonitoringSignalEvent
    alert_result: AlertDerived | NoAlert


def _refuse(code: MonitoringEvaluationCode, detail: str) -> None:
    raise MonitoringEvaluationRefusal(code, detail)


def _address(value: Any, label: str) -> str:
    if type(value) is not str or not is_content_address(value):
        _refuse(MonitoringEvaluationCode.AUTHORITY_MISMATCH, f"{label} is not addressed")
    return value


def _display_symbol(value: Any) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "display symbol is unsafe")
    return value


def _plain(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_INPUT_DEPTH:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "closed value exceeds depth bound")
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _refuse(MonitoringEvaluationCode.INPUT_INVALID, "non-finite input")
        return value
    if type(value) is tuple:
        return tuple(_plain(item, depth=depth + 1) for item in value)
    if type(value) in {dict, MappingProxyType}:
        result = {}
        for key in sorted(value):
            if type(key) is not str or not key:
                _refuse(MonitoringEvaluationCode.INPUT_INVALID, "mapping key is not closed")
            result[key] = _plain(value[key], depth=depth + 1)
        return result
    if type(value) is NumericValue:
        return NumericValue(value.state, value.value, value.causes)
    _refuse(MonitoringEvaluationCode.INPUT_INVALID, "input is not closed immutable data")


def _series_snapshot(value):
    if not 0 < len(value) <= monitoring_intent_v2.MAX_PREFIX_EVENTS:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "price history exceeds the prefix bound")
    values = value.tolist()
    return values, value.index.copy(deep=True), value.dtype


def _series_input(value: pd.Series, cutoff_at, indexes: list) -> pd.Series:
    """Copy a caller-selected prefix; its retained source is checked by the caller."""
    values, index, dtype = _series_snapshot(value)
    if not 0 < len(values) <= monitoring_intent_v2.MAX_PREFIX_EVENTS:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "price history exceeds the prefix bound")
    try:
        monitoring_intent_v2._prefix_clock(index)
    except ValueError as exc:
        raise MonitoringEvaluationRefusal(
            MonitoringEvaluationCode.INPUT_INVALID, "price history clock is invalid",
        ) from exc
    if index[-1] > cutoff_at:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "price history extends beyond the evaluation cutoff")
    if indexes and not index.equals(indexes[0]):
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "price history columns are not aligned")
    if any(type(item) not in {int, float, bool, NumericValue} for item in values):
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "price history cells are not numeric values")
    indexes.append(index)
    return pd.Series([_plain(item) for item in values], index=index, dtype=dtype)


def _input_mapping(value, cutoff_at, indexes, depth):
    if any(type(key) is not str or not key for key in value):
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "input mapping key is not closed")
    return MappingProxyType({key: _input_value(value[key], cutoff_at, indexes, depth=depth + 1)
                             for key in sorted(value)})


def _input_value(value: Any, cutoff_at, indexes: list, *, depth: int = 0) -> Any:
    if depth > MAX_INPUT_DEPTH:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "input exceeds depth bound")
    if type(value) is pd.Series:
        return _series_input(value, cutoff_at, indexes)
    if type(value) is tuple:
        return tuple(_input_value(item, cutoff_at, indexes, depth=depth + 1) for item in value)
    if type(value) in {dict, MappingProxyType}:
        return _input_mapping(value, cutoff_at, indexes, depth)
    return _plain(value, depth=depth)


def _frozen_inputs(graph: ResolvedV2Graph, inputs: Any, *, cutoff_at=None, terminal_at=None) -> Mapping[str, Any]:
    if type(inputs) not in {dict, MappingProxyType}:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "graph inputs must be an exact mapping")
    if set(inputs) != set(graph.graph_inputs):
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "graph input boundary is incomplete")
    if cutoff_at is None:
        return MappingProxyType({key: _plain(inputs[key]) for key in sorted(inputs)})
    indexes = []
    result = {key: _input_value(inputs[key], cutoff_at, indexes) for key in sorted(inputs)}
    if not indexes:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "completed-bar evaluation needs a price history prefix")
    if indexes[0][-1] != terminal_at:
        _refuse(MonitoringEvaluationCode.INPUT_INVALID, "price history does not end at the admitted observation")
    return MappingProxyType(result)


def _canonical_decimal(value: Any, label: str) -> tuple[Decimal, str]:
    if type(value) is not str:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, f"{label} is not decimal text")
    try:
        number = Decimal(value)
    except DecimalException:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, f"{label} is not decimal text")
    if not number.is_finite() or number <= 0:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, f"{label} is not positive finite")
    normalized = format(number.normalize(), "f")
    if normalized.startswith("-") or normalized == "0":
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, f"{label} is not canonical")
    return number, normalized


def _expected_authored(name: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    key = monitoring_intent_v2.component_key(name)
    return {
        "component_id": key[0],
        "semantic_version": key[1],
        "component_address": content_address(
            monitoring_intent_v2.node_contracts._plain(
                monitoring_intent_v2.descriptor(name)
            )
        ),
        "node_contract_address": monitoring_intent_v2.NODE_CONTRACT_ADDRESSES[key],
        "parameters_address": content_address(
            monitoring_intent_v2.node_contracts._plain(parameters)
        ),
    }


def _verify_target(value: Any) -> Mapping[str, Any]:
    payload = _plain(value)
    expected = {
        "schema", "operation", "target_state", "risk_reducing", "requested",
        "authored", "validity",
    }
    if type(payload) is not dict or set(payload) != expected \
            or payload["schema"] != "monitoring-target-intent/1" \
            or payload["validity"] != "VALID" \
            or type(payload["requested"]) is not bool \
            or type(payload["risk_reducing"]) is not bool:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "target intent is not closed")
    name = payload["operation"]
    if name not in monitoring_intent_v2.TARGET_SPECS:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "target operation is unavailable")
    spec = monitoring_intent_v2.TARGET_SPECS[name]
    if payload["target_state"] != spec["target_state"] \
            or payload["risk_reducing"] is not spec["risk_reducing"] \
            or payload["authored"] != _expected_authored(name, MappingProxyType({})):
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "target authorship differs")
    return MappingProxyType(payload)


def _protection_name(component_id: Any) -> str:
    matches = [
        name for name in monitoring_intent_v2.PROTECTION_SPECS
        if monitoring_intent_v2.component_key(name)[0] == component_id
    ]
    if len(matches) != 1:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "protection component is unavailable")
    return matches[0]


def _verify_protection(value: Any) -> Mapping[str, Any]:
    payload = _plain(value)
    expected = {
        "schema", "kind", "basis", "value", "units", "active",
        "authored_value", "authored", "input_identity", "validity", "authority",
    }
    if type(payload) is not dict or set(payload) != expected \
            or payload["schema"] != "monitoring-protection/1" \
            or payload["validity"] != "VALID" \
            or payload["authority"] != "MONITORING_ONLY" \
            or type(payload["active"]) is not bool:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "protection output is not closed")
    authored = payload["authored"]
    if type(authored) is not dict or set(authored) != {
        "component_id", "semantic_version", "component_address",
        "node_contract_address", "parameters_address",
    }:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "protection authorship is open")
    name = _protection_name(authored["component_id"])
    spec = monitoring_intent_v2.PROTECTION_SPECS[name]
    authored_number, authored_value = _canonical_decimal(
        payload["authored_value"], "authored protection"
    )
    parameter_name = spec["parameter"]
    parameters = monitoring_intent_v2.parameters_for(
        name, {parameter_name: authored_value}
    )
    if payload["kind"] != spec["kind"] or payload["basis"] != spec["basis"] \
            or payload["units"] != spec["units"] \
            or authored != _expected_authored(name, parameters):
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "protection authorship differs")
    input_identity = payload["input_identity"]
    if spec["input"] == "condition":
        if input_identity is not None:
            _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "condition protection carries input identity")
    elif type(input_identity) is not dict or set(input_identity) != {
        "source_component_id", "source_component_version",
        "source_component_address", "source_contract_address",
    } or type(input_identity["source_component_id"]) is not str \
            or not input_identity["source_component_id"] \
            or type(input_identity["source_component_version"]) is not int \
            or input_identity["source_component_version"] < 1 \
            or any(
                type(input_identity[name]) is not str
                or not is_content_address(input_identity[name])
                for name in ("source_component_address", "source_contract_address")
            ):
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "distance protection identity differs")
    resolved_number, resolved_value = _canonical_decimal(
        payload["value"], "protection value"
    )
    if authored_number <= 0 or resolved_number <= 0:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, "protection is not positive")
    return MappingProxyType({
        **payload,
        "_name": name,
        "_authored_value": authored_value,
        "_value": resolved_value,
    })


def _closed_outputs(values: Mapping[str, Any]) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    if type(values) is not MappingProxyType or not values or len(values) > MAX_GRAPH_OUTPUTS:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "graph output boundary is unbounded")
    targets, protections = [], []
    for name in sorted(values):
        value = values[name]
        if not isinstance(value, Mapping):
            _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "graph output is not a fact")
        schema = value.get("schema")
        if schema == "monitoring-target-intent/1":
            targets.append(_verify_target(value))
        elif schema == "monitoring-protection/1":
            protections.append(_verify_protection(value))
        else:
            _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "graph output schema is unavailable")
    if not targets:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "target intent output is absent")
    return tuple(targets), tuple(protections)


def _target_transition(
    previous: StrategyState, targets: tuple[Mapping[str, Any], ...],
) -> tuple[StrategyState, SignalAction, bool, str]:
    requested = [value for value in targets if value["requested"]]
    if len(requested) > 1:
        _refuse(MonitoringEvaluationCode.TARGET_AMBIGUOUS, "multiple targets are requested")
    if not requested:
        return previous, SignalAction.HOLD, True, "NO_TARGET_REQUESTED"
    target = StrategyState(requested[0]["target_state"])
    if target is previous:
        return target, SignalAction.HOLD, True, "REPEATED_TARGET_STATE"
    action = {
        StrategyState.LONG: SignalAction.BUY,
        StrategyState.SHORT: SignalAction.SELL,
        StrategyState.FLAT: SignalAction.EXIT,
    }[target]
    if action is SignalAction.EXIT and previous is StrategyState.FLAT:
        _refuse(MonitoringEvaluationCode.STATE_INVALID, "flat state cannot exit")
    return target, action, False, "TARGET_STATE_CHANGED"


def _active_protections(
    protections: tuple[Mapping[str, Any], ...], kind: str,
) -> Mapping[str, Any] | None:
    matches = [value for value in protections if value["kind"] == kind and value["active"]]
    if len(matches) > 1:
        _refuse(MonitoringEvaluationCode.PROTECTION_AMBIGUOUS, f"multiple {kind} outputs")
    return matches[0] if matches else None


def _resolved_protection(
    value: Mapping[str, Any], *, direction: StrategyState,
    entry_reference: EntryReference, evaluation_event_address: str,
) -> ProtectionEvidence:
    if direction not in {StrategyState.LONG, StrategyState.SHORT}:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, "protection direction is flat")
    entry, _entry_text = _canonical_decimal(entry_reference.value, "entry reference")
    amount, amount_text = _canonical_decimal(value["_value"], "protection amount")
    basis = ProtectionBasis(value["basis"])
    kind = ProtectionKind(value["kind"])
    if basis is ProtectionBasis.PERCENT_FROM_ENTRY_REFERENCE:
        offset = entry * amount
    elif basis in {
        ProtectionBasis.DISTANCE_FROM_ENTRY_REFERENCE,
        ProtectionBasis.VERIFIED_INDICATOR_DISTANCE,
    }:
        offset = amount
    else:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, "protection basis is unavailable")
    lower = (direction is StrategyState.LONG and kind is ProtectionKind.STOP_LOSS) \
        or (direction is StrategyState.SHORT and kind is ProtectionKind.TAKE_PROFIT)
    resolved = entry - offset if lower else entry + offset
    if not resolved.is_finite() or resolved <= 0:
        _refuse(MonitoringEvaluationCode.PROTECTION_INVALID, "resolved protection is not positive")
    resolved_text = format(resolved.normalize(), "f")
    resolution = content_address({
        "schema": "monitoring-protection-resolution/1",
        "evaluation_event_address": evaluation_event_address,
        "canonical_instrument_address": entry_reference.canonical_instrument_address,
        "direction": direction.value,
        "kind": kind.value,
        "basis": basis.value,
        "authored_component_address": value["authored"]["component_address"],
        "authored_parameters_address": value["authored"]["parameters_address"],
        "entry_reference": entry_reference.value,
        "amount": amount_text,
        "resolved_value": resolved_text,
    })
    return ProtectionEvidence(
        kind=kind,
        basis=basis,
        authored_component_id=value["authored"]["component_id"],
        authored_component_version=value["authored"]["semantic_version"],
        authored_component_address=value["authored"]["component_address"],
        authored_contract_address=value["authored"]["node_contract_address"],
        authored_parameters_address=value["authored"]["parameters_address"],
        authored_value=value["_authored_value"],
        units=ProtectionUnits(value["units"]),
        resolved_value=resolved_text,
        resolution_address=resolution,
        validity=FactValidity.VALID,
    )


def _monitoring_instant(schedule, evaluation_event):
    """Completed prefixes use market completion; legacy event semantics stay exact."""
    return evaluation_event.completed_at if schedule.gate_node_id is None else evaluation_event.event_at


def _assignment_state(assignment, previous_snapshot):
    if type(assignment) is not MonitoringAssignment or type(previous_snapshot) is not MonitoringStateSnapshot:
        _refuse(MonitoringEvaluationCode.ASSIGNMENT_INVALID, "closed assignment and state required")
    if assignment.lifecycle_state != "ACTIVE" or assignment.withdrawn_at is not None:
        _refuse(MonitoringEvaluationCode.ASSIGNMENT_INACTIVE, "assignment is not active")
    if assignment.owner_id != previous_snapshot.owner_id \
            or assignment.spec.assignment_id != previous_snapshot.assignment_id \
            or assignment.current_state_snapshot_address != previous_snapshot.address:
        _refuse(MonitoringEvaluationCode.STATE_INVALID, "assignment current state differs")


def _issued_event_schedule(schedule, evaluation_event):
    try:
        schedule = verify_evaluation_schedule(schedule)
        evaluation_event = verify_evaluation_event(evaluation_event)
    except (ScheduleRefusal, TypeError, ValueError) as exc:
        raise MonitoringEvaluationRefusal(
            MonitoringEvaluationCode.AUTHORITY_MISMATCH,
            "schedule or evaluation event is stale or forged",
        ) from exc
    return schedule, evaluation_event


def _registry_snapshot(registry):
    snapshot_payload = registry.registry_snapshot_payload
    if type(snapshot_payload) is not registry_contract._FrozenDict:
        raise TypeError("registry snapshot payload is not frozen")
    snapshot = registry_contract._plain(snapshot_payload)
    if content_address(snapshot) != registry.registry_snapshot_address:
        raise ValueError("registry snapshot address is stale")
    snapshot_components = {
        (row["component_id"], row["component_version"]): row["value"]
        for row in snapshot["v2_components"]
    }
    snapshot_implementations = {
        (row["component_id"], row["component_version"]): row["value"]
        for row in snapshot["v2_implementations"]
    }
    return snapshot_components, snapshot_implementations


def _component_authority(registry, component, snapshot_components, snapshot_implementations):
    registration = registry.v2_implementation_registrations.get(component)
    if type(registration) is not V2ImplementationRegistration:
        raise TypeError("graph implementation registration is absent")
    actual_address = implementation_address(
        registration.implementation,
        registration.dependency_boundary,
    )
    if (
        registry_contract._plain(registry.v2_components.get(component))
            != snapshot_components.get(component)
        or registry.v2_implementations.get(component)
            is not registration.implementation
        or registry.v2_implementation_identities.get(component)
            != actual_address
        or registration.implementation_address != actual_address
        or snapshot_implementations.get(component) != actual_address
    ):
        raise ValueError("graph implementation authority differs")


def _registry_authority(registry, graph):
    if type(registry) is not PlatformRegistry:
        _refuse(MonitoringEvaluationCode.AUTHORITY_MISMATCH, "registry type differs")
    try:
        components, implementations = _registry_snapshot(registry)
        for component in {node.component for node in graph.nodes}:
            _component_authority(registry, component, components, implementations)
    except (AttributeError, ImplementationUnidentified, KeyError, TypeError, ValueError) as exc:
        raise MonitoringEvaluationRefusal(MonitoringEvaluationCode.AUTHORITY_MISMATCH,
            "registry implementation authority cannot reconstruct") from exc
    return registry


def _plan_schedule_binding(assignment, schedule, evaluation_policy):
    if evaluation_policy is None:
        actual = (assignment.spec.resource_plan_address, assignment.spec.evaluation_trigger_address)
        expected = (schedule.resource_plan_address, schedule.schedule_address)
        if actual != expected:
            _refuse(MonitoringEvaluationCode.AUTHORITY_MISMATCH, "assignment schedule binding differs")
        return
    try:
        _policy_schedule_binding(evaluation_policy, assignment, schedule)
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        raise MonitoringEvaluationRefusal(MonitoringEvaluationCode.AUTHORITY_MISMATCH,
            "assignment monitoring policy differs") from exc


def _assignment_schedule_binding(assignment, schedule, evaluation_event, evaluation_policy):
    spec = assignment.spec
    binding = (
        assignment.owner_id,
        spec.assignment_id,
        spec.graph_version_address,
        spec.resolved_graph_address,
        spec.registry_address,
        spec.implementation_closure_address,
    )
    expected = (
        schedule.owner_id,
        schedule.assignment_id,
        schedule.authored_ir_address,
        schedule.resolved_graph_address,
        schedule.registry_snapshot_address,
        schedule.implementation_closure_address,
    )
    if binding != expected or evaluation_event.schedule_address != schedule.schedule_address:
        _refuse(MonitoringEvaluationCode.AUTHORITY_MISMATCH, "assignment schedule binding differs")
    if schedule.mode != "research":
        _refuse(MonitoringEvaluationCode.AUTHORITY_MISMATCH, "monitoring evaluation must be research-only")
    _plan_schedule_binding(assignment, schedule, evaluation_policy)


def _graph_schedule_binding(graph, schedule, registry):
    try:
        graph_address = resolved_v2_graph_address(
            graph.nodes,
            graph.registry_snapshot_address,
            graph.implementation_closure_address,
            graph.registry_snapshot_payload,
            graph.data_requirement_declaration_closure,
        )
    except (ResolutionError, TypeError, ValueError) as exc:
        raise MonitoringEvaluationRefusal(
            MonitoringEvaluationCode.GRAPH_INVALID,
            "resolved graph cannot reconstruct",
        ) from exc
    actual = (
        graph_address, graph.resolved_graph_address, graph.authored_ir_address,
        graph.implementation_closure_address, graph.registry_snapshot_address,
        registry.registry_snapshot_address, {node.node_id for node in graph.nodes},
    )
    expected = (
        graph.resolved_graph_address, schedule.resolved_graph_address, schedule.authored_ir_address,
        schedule.implementation_closure_address, schedule.registry_snapshot_address,
        schedule.registry_snapshot_address, {node_id for node_id, _ in schedule.unit_contract_addresses},
    )
    if actual != expected:
        _refuse(MonitoringEvaluationCode.GRAPH_INVALID, "graph or registry differs from schedule")


def _verified_context(
    assignment: Any,
    previous_snapshot: Any,
    schedule: Any,
    evaluation_event: Any,
    graph: Any,
    registry: Any,
    evaluation_policy: Any = None,
) -> tuple[
    MonitoringAssignment, MonitoringStateSnapshot, EvaluationScheduleAddress,
    EvaluationEventAddress, ResolvedV2Graph, PlatformRegistry,
]:
    _assignment_state(assignment, previous_snapshot)
    schedule, evaluation_event = _issued_event_schedule(schedule, evaluation_event)
    if type(graph) is not ResolvedV2Graph:
        _refuse(MonitoringEvaluationCode.GRAPH_INVALID, "resolved graph type differs")
    verified_registry = _registry_authority(registry, graph)
    _assignment_schedule_binding(assignment, schedule, evaluation_event, evaluation_policy)
    _graph_schedule_binding(graph, schedule, verified_registry)
    if previous_snapshot.effective_at > _monitoring_instant(schedule, evaluation_event):
        _refuse(MonitoringEvaluationCode.STATE_INVALID, "predecessor state is from the future")
    return assignment, previous_snapshot, schedule, evaluation_event, graph, verified_registry


def _entry_at_event(entry_reference, previous_snapshot, event_at):
    if type(entry_reference) is not EntryReference \
            or entry_reference.validity is not FactValidity.VALID \
            or entry_reference.canonical_instrument_address \
                != previous_snapshot.canonical_instrument_address \
            or entry_reference.observed_at > event_at:
        _refuse(MonitoringEvaluationCode.STATE_INVALID, "entry reference differs from event state")


def _transition_entry_reference(candidate, previous_snapshot, target, event_at):
    """A held or closing strategy keeps the entry that established its state."""
    previous = previous_snapshot.strategy_state
    if previous is not StrategyState.FLAT and target in {previous, StrategyState.FLAT}:
        retained = previous_snapshot.entry_reference
        _entry_at_event(retained, previous_snapshot, event_at)
        return retained
    return candidate


def _evaluate_monitoring_inputs(graph, schedule, evaluation_event, inputs, registry):
    if len(graph.outputs) > MAX_GRAPH_OUTPUTS:
        _refuse(MonitoringEvaluationCode.OUTPUT_INVALID, "graph output boundary is unbounded")
    try:
        cutoff = evaluation_event.cutoff_at if schedule.gate_node_id is None else None
        return evaluate_v2(graph, _frozen_inputs(graph, inputs, cutoff_at=cutoff,
            terminal_at=evaluation_event.completed_at), registry)
    except (EvaluationError, TypeError, ValueError) as exc:
        raise MonitoringEvaluationRefusal(
            MonitoringEvaluationCode.EVALUATION_REFUSED,
            "canonical v2 evaluation refused",
        ) from exc


def compile_monitoring_transition(
    *,
    assignment: MonitoringAssignment,
    previous_snapshot: MonitoringStateSnapshot,
    schedule: EvaluationScheduleAddress,
    evaluation_event: EvaluationEventAddress,
    graph: ResolvedV2Graph,
    registry: Any,
    inputs: Mapping[str, Any],
    entry_reference: EntryReference,
    display_symbol: str,
    provider_evidence_address: str,
    dataset_address: str,
    evaluation_policy: Any = None,
) -> MonitoringEvaluationTransition:
    """Evaluate one completed event and compile one monitoring transition."""
    assignment, previous_snapshot, schedule, evaluation_event, graph, registry = _verified_context(
        assignment, previous_snapshot, schedule, evaluation_event, graph, registry, evaluation_policy,
    )
    event_at = _monitoring_instant(schedule, evaluation_event)
    _entry_at_event(entry_reference, previous_snapshot, event_at)
    provider = _address(provider_evidence_address, "provider evidence")
    dataset = _address(dataset_address, "dataset")
    symbol = _display_symbol(display_symbol)
    evaluated = _evaluate_monitoring_inputs(graph, schedule, evaluation_event, inputs, registry)
    targets, protections = _closed_outputs(evaluated)
    target, action, repeated, reason = _target_transition(
        previous_snapshot.strategy_state, targets,
    )
    entry_reference = _transition_entry_reference(entry_reference, previous_snapshot, target, event_at)
    stop = _active_protections(protections, "STOP_LOSS")
    take = _active_protections(protections, "TAKE_PROFIT")
    if (stop is None) != (take is None):
        _refuse(MonitoringEvaluationCode.PROTECTION_MISSING, "stop and target must be paired")
    if stop is None:
        if action is not SignalAction.HOLD:
            _refuse(MonitoringEvaluationCode.PROTECTION_MISSING, "transition lacks stop and target")
        stop_evidence = previous_snapshot.stop_loss
        take_evidence = previous_snapshot.take_profit
    else:
        direction = target if target is not StrategyState.FLAT else previous_snapshot.strategy_state
        stop_evidence = _resolved_protection(
            stop, direction=direction, entry_reference=entry_reference,
            evaluation_event_address=evaluation_event.event_address,
        )
        take_evidence = _resolved_protection(
            take, direction=direction, entry_reference=entry_reference,
            evaluation_event_address=evaluation_event.event_address,
        )
    next_snapshot = MonitoringStateSnapshot(
        owner_id=assignment.owner_id,
        assignment_id=assignment.spec.assignment_id,
        canonical_instrument_address=entry_reference.canonical_instrument_address,
        snapshot_sequence=previous_snapshot.snapshot_sequence + 1,
        predecessor_snapshot_address=previous_snapshot.address,
        strategy_state=target,
        entry_reference=entry_reference,
        stop_loss=stop_evidence,
        take_profit=take_evidence,
        evaluation_event_address=evaluation_event.event_address,
        effective_at=event_at,
    )
    output_evidence = content_address({
        "schema": "monitoring-evaluation-reason/1",
        "evaluation_event_address": evaluation_event.event_address,
        "previous_snapshot_address": previous_snapshot.address,
        "target_state": target.value,
        "action": action.value,
        "reason": reason,
        "outputs": _plain(evaluated),
    })
    signal_event = MonitoringSignalEvent(
        owner_id=assignment.owner_id,
        assignment_id=assignment.spec.assignment_id,
        strategy_id=assignment.spec.strategy_id,
        graph_version_address=assignment.spec.graph_version_address,
        resolved_graph_address=assignment.spec.resolved_graph_address,
        implementation_closure_address=assignment.spec.implementation_closure_address,
        admission_address=assignment.spec.research_admission_address,
        canonical_instrument_address=entry_reference.canonical_instrument_address,
        display_symbol=symbol,
        previous_state=previous_snapshot.strategy_state,
        target_state=target,
        action=action,
        evaluation_event_address=evaluation_event.event_address,
        event_at=event_at,
        latest_data_at=event_at,
        knowledge_cutoff_at=evaluation_event.cutoff_at,
        valid_until=evaluation_event.completed_at + timedelta(
            seconds=schedule.maximum_age_seconds
        ),
        evaluation_validity=FactValidity.VALID,
        freshness=Freshness.FRESH,
        repeated_target_state=repeated,
        entry_reference=entry_reference,
        stop_loss=stop_evidence,
        take_profit=take_evidence,
        state_before_address=previous_snapshot.address,
        state_after_address=next_snapshot.address,
        provider_evidence_address=provider,
        dataset_address=dataset,
        reason_code=reason,
        reason_evidence_address=output_evidence,
    )
    return MonitoringEvaluationTransition(
        next_snapshot=next_snapshot,
        signal_event=signal_event,
        alert_result=derive_signal_alert(signal_event),
    )


__all__ = [
    "MAX_GRAPH_OUTPUTS",
    "MonitoringEvaluationCode",
    "MonitoringEvaluationRefusal",
    "MonitoringEvaluationTransition",
    "compile_monitoring_transition",
]
