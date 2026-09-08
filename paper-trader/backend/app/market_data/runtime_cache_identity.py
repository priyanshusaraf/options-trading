"""Pure, immutable runtime cache identities for the bounded V0 foundation.

These values describe answer-changing inputs.  They do not read, write, select,
or authorize a cache, provider, evaluator, monitoring process, or execution path.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.ir.evaluation_schedule import (
    AuthoredAcquisitionGate,
    AuthoredGateOutcome,
    EvaluationScheduleAddress,
    ScheduleRefusal,
    canonical_conditional_requirement_selector,
    verify_authored_acquisition_gate,
    verify_evaluation_schedule,
)
from app.ir.hashing import content_address


_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RESOURCE_DIMENSIONS = ("subscription_count", "depth_feed_count", "cache_bytes")


class RuntimeCacheRefusal(ValueError):
    """A closed refusal for incomplete, non-causal, or unbounded identity."""


@dataclass(frozen=True)
class ResourceBound:
    """One exact unit-bearing resource demand and its hard ceiling."""

    dimension: str
    unit_address: str
    demand: int | float
    ceiling: int | float

    def __post_init__(self) -> None:
        if self.dimension not in _RESOURCE_DIMENSIONS:
            raise RuntimeCacheRefusal("resource demand dimension is unknown")
        _address(self.unit_address, "resource unit")
        demand = _number(self.demand, "resource demand", nonnegative=True)
        ceiling = _number(self.ceiling, "resource ceiling", nonnegative=True)
        if demand > ceiling:
            raise RuntimeCacheRefusal(f"{self.dimension} demand exceeds its ceiling")

    def document(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "unit_address": self.unit_address,
            "demand": self.demand,
            "ceiling": self.ceiling,
        }


@dataclass(frozen=True, init=False)
class RuntimeCacheIdentity:
    """An immutable content address and its recursively immutable preimage."""

    cache_class: str
    document: Mapping[str, Any]
    address: str


def observation_cache_identity(
    *,
    owner_id: str,
    assignment_id: str,
    licence_scope_address: str,
    provider_entity_address: str,
    provider_product_address: str,
    provider_contract_address: str,
    provider_conformance_address: str,
    provider_capability_address: str,
    canonical_instrument_address: str,
    canonical_contract_address: str,
    fields: Sequence[str],
    depth_levels: int,
    rulebook_address: str,
    alias_addresses: Sequence[str],
    correction_addresses: Sequence[str],
    raw_segment_addresses: Sequence[str],
    event_at: dt.datetime,
    completed_at: dt.datetime,
    available_at: dt.datetime,
    recorded_at: dt.datetime,
    knowledge_cutoff: dt.datetime,
    timeframe_seconds: int,
    session_policy_address: str,
    unit_contract_address: str,
    missing_data_policy_address: str,
    alignment_policy_address: str,
    adjustment_policy_address: str,
) -> RuntimeCacheIdentity:
    """Address one owner/assignment-scoped immutable market observation."""
    owner, assignment = _scope(owner_id, assignment_id)
    addresses = _named_addresses(locals(), (
        "licence_scope_address", "provider_entity_address", "provider_product_address",
        "provider_contract_address", "provider_conformance_address",
        "provider_capability_address", "canonical_instrument_address",
        "canonical_contract_address", "rulebook_address", "session_policy_address",
        "unit_contract_address", "missing_data_policy_address",
        "alignment_policy_address", "adjustment_policy_address",
    ))
    canonical_fields = _strings(fields, "fields", require_nonempty=True)
    depth = _integer(depth_levels, "depth levels", nonnegative=True)
    timeframe = _integer(timeframe_seconds, "timeframe seconds", positive=True)
    aliases = _addresses(alias_addresses, "alias addresses", require_nonempty=True)
    corrections = _addresses(correction_addresses, "correction addresses")
    segments = _addresses(raw_segment_addresses, "raw segment addresses", require_nonempty=True)
    event, completed, available, recorded, cutoff = (
        _utc_time(event_at, "event time"),
        _utc_time(completed_at, "completion time"),
        _utc_time(available_at, "availability time"),
        _utc_time(recorded_at, "recording time"),
        _utc_time(knowledge_cutoff, "knowledge cutoff"),
    )
    if not event <= completed <= available <= recorded <= cutoff:
        raise RuntimeCacheRefusal(
            "observation time must satisfy event<=completed<=available<=recorded<=cutoff"
        )
    return _identity("observation", {
        "schema": "v0-runtime-observation-cache-identity/1",
        "owner_id": owner,
        "assignment_id": assignment,
        **addresses,
        "fields": list(canonical_fields),
        "depth_levels": depth,
        "alias_addresses": list(aliases),
        "correction_addresses": list(corrections),
        "raw_segment_addresses": list(segments),
        "event_at": event,
        "completed_at": completed,
        "available_at": available,
        "recorded_at": recorded,
        "knowledge_cutoff": cutoff,
        "timeframe_seconds": timeframe,
    })


def static_window_cache_identity(
    *,
    owner_id: str,
    assignment_id: str,
    static_scope_revision_address: str,
    evaluation_schedule: EvaluationScheduleAddress,
    authored_gate: AuthoredAcquisitionGate,
    selector_policy_address: str,
    underlying_instrument_address: str,
    contract_addresses: Sequence[str],
    expiry_lower_bound: dt.date,
    expiry_upper_bound: dt.date,
    strike_lower_bound: int | float,
    strike_upper_bound: int | float,
    strike_unit_address: str,
    buffer_policy_address: str,
    depth_levels: int,
    provider_entity_address: str,
    provider_product_address: str,
    provider_contract_address: str,
    provider_conformance_address: str,
    provider_capability_address: str,
    rulebook_address: str,
    alias_addresses: Sequence[str],
    as_of: dt.datetime,
    knowledge_cutoff: dt.datetime,
    freshness_seconds: int,
    resource_plan_address: str,
    resource_bounds: Sequence[ResourceBound],
) -> RuntimeCacheIdentity:
    """Address one bounded, already-authorized static option/depth window."""
    owner, assignment = _scope(owner_id, assignment_id)
    acquisition = _static_acquisition_facts(
        owner=owner,
        assignment=assignment,
        schedule=evaluation_schedule,
        gate=authored_gate,
        resource_plan_address=resource_plan_address,
    )
    addresses = _named_addresses(locals(), (
        "static_scope_revision_address", "selector_policy_address",
        "underlying_instrument_address", "strike_unit_address", "buffer_policy_address",
        "provider_entity_address", "provider_product_address", "provider_contract_address",
        "provider_conformance_address", "provider_capability_address", "rulebook_address",
        "resource_plan_address",
    ))
    contracts = _addresses(contract_addresses, "contract addresses", require_nonempty=True)
    aliases = _addresses(alias_addresses, "alias addresses", require_nonempty=True)
    lower_expiry = _date(expiry_lower_bound, "expiry lower bound")
    upper_expiry = _date(expiry_upper_bound, "expiry upper bound")
    if lower_expiry > upper_expiry:
        raise RuntimeCacheRefusal("expiry bounds are inverted")
    lower_strike = _number(strike_lower_bound, "strike lower bound", nonnegative=True)
    upper_strike = _number(strike_upper_bound, "strike upper bound", nonnegative=True)
    if lower_strike > upper_strike:
        raise RuntimeCacheRefusal("strike bounds are inverted")
    depth = _integer(depth_levels, "depth levels", positive=True)
    freshness = _integer(freshness_seconds, "freshness seconds", nonnegative=True)
    known_at = _utc_time(as_of, "as-of time")
    cutoff = _utc_time(knowledge_cutoff, "knowledge cutoff")
    if known_at > cutoff:
        raise RuntimeCacheRefusal("static window as-of time exceeds knowledge cutoff")
    bounds = _resource_bounds(resource_bounds)
    return _identity("static_window", {
        "schema": "v0-runtime-static-window-cache-identity/1",
        "owner_id": owner,
        "assignment_id": assignment,
        **addresses,
        **acquisition,
        "contract_addresses": list(contracts),
        "expiry_lower_bound": lower_expiry,
        "expiry_upper_bound": upper_expiry,
        "strike_lower_bound": lower_strike,
        "strike_upper_bound": upper_strike,
        "depth_levels": depth,
        "alias_addresses": list(aliases),
        "as_of": known_at,
        "knowledge_cutoff": cutoff,
        "freshness_seconds": freshness,
        "resource_bounds": [bound.document() for bound in bounds],
    })


def derived_node_cache_identity(
    *,
    owner_id: str,
    assignment_id: str,
    node_semantic_address: str,
    node_contract_address: str,
    node_implementation_address: str,
    parameters_address: str,
    input_bindings: Sequence[tuple[str, str]],
    resolved_graph_address: str,
    implementation_closure_address: str,
    registry_snapshot_address: str,
    input_unit_addresses: Sequence[str],
    output_unit_address: str,
    missing_data_policy_address: str,
    alignment_policy_address: str,
    adjustment_policy_address: str,
    session_policy_address: str,
    event_at: dt.datetime,
    knowledge_cutoff: dt.datetime,
    state_predecessor_address: str | None,
    state_reset_address: str | None,
    output_port: str,
    evaluation_schedule: EvaluationScheduleAddress,
) -> RuntimeCacheIdentity:
    """Address one derived output without evaluating the canonical graph."""
    owner, assignment = _scope(owner_id, assignment_id)
    schedule_address = _schedule_binding(
        owner=owner,
        assignment=assignment,
        schedule=evaluation_schedule,
        resolved_graph_address=resolved_graph_address,
        implementation_closure_address=implementation_closure_address,
        registry_snapshot_address=registry_snapshot_address,
    )
    addresses = _named_addresses(locals(), (
        "node_semantic_address", "node_contract_address", "node_implementation_address",
        "parameters_address", "resolved_graph_address", "implementation_closure_address",
        "registry_snapshot_address", "output_unit_address", "missing_data_policy_address",
        "alignment_policy_address", "adjustment_policy_address", "session_policy_address",
    ))
    predecessor, reset = _optional_state_pair(state_predecessor_address, state_reset_address)
    inputs = _input_bindings(input_bindings)
    units = _addresses(input_unit_addresses, "input unit addresses", require_nonempty=True,
                       preserve_order=True)
    if len(units) != len(inputs):
        raise RuntimeCacheRefusal("each exact input requires one unit contract")
    port = _text(output_port, "output port")
    event = _utc_time(event_at, "event time")
    cutoff = _utc_time(knowledge_cutoff, "knowledge cutoff")
    if event > cutoff:
        raise RuntimeCacheRefusal("derived event exceeds knowledge cutoff")
    return _identity("derived_node", {
        "schema": "v0-runtime-derived-node-cache-identity/1",
        "owner_id": owner,
        "assignment_id": assignment,
        **addresses,
        "input_bindings": [{"port": item[0], "address": item[1]} for item in inputs],
        "input_unit_addresses": list(units),
        "event_at": event,
        "knowledge_cutoff": cutoff,
        "output_port": port,
        "schedule_address": schedule_address,
        "state_predecessor_address": predecessor,
        "state_reset_address": reset,
    })


def evaluation_result_cache_identity(
    *,
    owner_id: str,
    assignment_id: str,
    resolved_graph_address: str,
    implementation_closure_address: str,
    registry_snapshot_address: str,
    admission_address: str,
    data_requirement_plan_address: str,
    resource_plan_address: str,
    dataset_or_stream_address: str,
    market_truth_address: str,
    evaluation_schedule: EvaluationScheduleAddress,
    input_addresses: Sequence[str],
    unit_policy_address: str,
    result_scope: str,
    fill_policy_address: str | None,
    charge_schedule_address: str | None,
    book_epoch_address: str | None,
    paper_policy_address: str | None,
    state_predecessor_address: str | None,
    state_reset_address: str | None,
    event_at: dt.datetime,
    knowledge_cutoff: dt.datetime,
) -> RuntimeCacheIdentity:
    """Address an exact V0 evaluation/result binding, never result authority."""
    owner, assignment = _scope(owner_id, assignment_id)
    schedule_address = _schedule_binding(
        owner=owner,
        assignment=assignment,
        schedule=evaluation_schedule,
        resolved_graph_address=resolved_graph_address,
        implementation_closure_address=implementation_closure_address,
        registry_snapshot_address=registry_snapshot_address,
        data_requirement_plan_address=data_requirement_plan_address,
        resource_plan_address=resource_plan_address,
    )
    addresses = _named_addresses(locals(), (
        "resolved_graph_address", "implementation_closure_address", "registry_snapshot_address",
        "admission_address", "data_requirement_plan_address", "resource_plan_address",
        "dataset_or_stream_address", "market_truth_address",
        "unit_policy_address",
    ))
    paper_addresses = _paper_result_addresses(
        result_scope, fill_policy_address, charge_schedule_address,
        book_epoch_address, paper_policy_address,
    )
    predecessor, reset = _optional_state_pair(state_predecessor_address, state_reset_address)
    inputs = _addresses(input_addresses, "evaluation input addresses", require_nonempty=True,
                        preserve_order=True)
    event = _utc_time(event_at, "event time")
    cutoff = _utc_time(knowledge_cutoff, "knowledge cutoff")
    if event > cutoff:
        raise RuntimeCacheRefusal("evaluation event exceeds knowledge cutoff")
    return _identity("evaluation_result", {
        "schema": "v0-runtime-evaluation-result-cache-identity/1",
        "owner_id": owner,
        "assignment_id": assignment,
        **addresses,
        "result_scope": result_scope,
        **paper_addresses,
        "state_predecessor_address": predecessor,
        "state_reset_address": reset,
        "schedule_address": schedule_address,
        "input_addresses": list(inputs),
        "event_at": event,
        "knowledge_cutoff": cutoff,
    })


def _identity(cache_class: str, payload: Mapping[str, Any]) -> RuntimeCacheIdentity:
    _reject_negative_zero(payload)
    address = content_address(payload)
    result = object.__new__(RuntimeCacheIdentity)
    object.__setattr__(result, "cache_class", cache_class)
    object.__setattr__(result, "document", _freeze(payload))
    object.__setattr__(result, "address", address)
    return result


def _scope(owner_id: object, assignment_id: object) -> tuple[str, str]:
    return _text(owner_id, "owner"), _text(assignment_id, "assignment")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise RuntimeCacheRefusal(f"{label} is absent or noncanonical")
    return value


def _address(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise RuntimeCacheRefusal(f"{label} must be an exact content address")
    return value


def _named_addresses(values: Mapping[str, Any], names: Sequence[str]) -> dict[str, str]:
    return {name: _address(values[name], name.replace("_", " ")) for name in names}


def _addresses(
    values: object,
    label: str,
    *,
    require_nonempty: bool = False,
    preserve_order: bool = False,
) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise RuntimeCacheRefusal(f"{label} must be a closed address sequence")
    result = tuple(_address(value, label) for value in values)
    if require_nonempty and not result:
        raise RuntimeCacheRefusal(f"{label} are absent")
    if len(set(result)) != len(result):
        raise RuntimeCacheRefusal(f"{label} are not canonical")
    if preserve_order:
        return result
    return tuple(sorted(result))


def _strings(values: object, label: str, *, require_nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise RuntimeCacheRefusal(f"{label} must be a closed string sequence")
    result = tuple(_text(value, label) for value in values)
    if require_nonempty and not result:
        raise RuntimeCacheRefusal(f"{label} are absent")
    if result != tuple(sorted(set(result))):
        raise RuntimeCacheRefusal(f"{label} are not canonical")
    return result


def _input_bindings(values: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, (tuple, list)) or not values:
        raise RuntimeCacheRefusal("exact input bindings are absent")
    result: list[tuple[str, str]] = []
    for value in values:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise RuntimeCacheRefusal("exact input binding is malformed")
        result.append((_text(value[0], "input port"), _address(value[1], "input address")))
    canonical = tuple(result)
    if canonical != tuple(sorted(canonical)) or len({item[0] for item in canonical}) != len(canonical):
        raise RuntimeCacheRefusal("exact input bindings are not canonical")
    return canonical


def _resource_bounds(values: object) -> tuple[ResourceBound, ...]:
    if not isinstance(values, (tuple, list)):
        raise RuntimeCacheRefusal("resource demand is unknown")
    if any(not isinstance(value, ResourceBound) for value in values):
        raise RuntimeCacheRefusal("resource demand is malformed")
    result = tuple(values)
    if tuple(value.dimension for value in result) != _RESOURCE_DIMENSIONS:
        raise RuntimeCacheRefusal("resource demand dimensions are incomplete or noncanonical")
    return result


def _static_acquisition_facts(
    *,
    owner: str,
    assignment: str,
    schedule: object,
    gate: object,
    resource_plan_address: object,
) -> dict[str, str]:
    try:
        schedule = verify_evaluation_schedule(schedule)
        gate = verify_authored_acquisition_gate(gate)
    except (ScheduleRefusal, TypeError, ValueError) as exc:
        raise RuntimeCacheRefusal("static acquisition fact is stale or forged") from exc
    resource = _address(resource_plan_address, "resource plan")
    if schedule.owner_id != owner or schedule.assignment_id != assignment:
        raise RuntimeCacheRefusal("static schedule owner or assignment differs from cache scope")
    if schedule.resource_plan_address != resource:
        raise RuntimeCacheRefusal("static schedule resource plan differs from cache resource plan")
    if gate.schedule_address != schedule.schedule_address \
            or gate.gate_node_id != schedule.gate_node_id:
        raise RuntimeCacheRefusal("authored gate differs from the static schedule")
    if gate.outcome is not AuthoredGateOutcome.REQUIRED:
        raise RuntimeCacheRefusal("static acquisition gate outcome is not REQUIRED")
    if gate.authority_address is None or gate.conditional_requirement_selector is None \
            or gate.conditional_requirement is None:
        raise RuntimeCacheRefusal("REQUIRED gate lacks compiler-derived acquisition facts")
    try:
        selector = canonical_conditional_requirement_selector(gate.conditional_requirement)
    except (ScheduleRefusal, TypeError, ValueError) as exc:
        raise RuntimeCacheRefusal("conditional requirement selector is invalid") from exc
    if selector != gate.conditional_requirement_selector \
            or selector != schedule.conditional_requirement_selector:
        raise RuntimeCacheRefusal("conditional requirement selector differs from the schedule")
    return {
        "schedule_address": schedule.schedule_address,
        "gate_address": gate.gate_address,
        "acquisition_authority_address": gate.authority_address,
        "conditional_requirement_selector": selector,
    }


def _schedule_binding(
    *,
    owner: str,
    assignment: str,
    schedule: object,
    resolved_graph_address: object,
    implementation_closure_address: object,
    registry_snapshot_address: object,
    data_requirement_plan_address: object | None = None,
    resource_plan_address: object | None = None,
) -> str:
    try:
        schedule = verify_evaluation_schedule(schedule)
    except (ScheduleRefusal, TypeError, ValueError) as exc:
        raise RuntimeCacheRefusal("evaluation schedule is stale or forged") from exc
    if schedule.owner_id != owner or schedule.assignment_id != assignment:
        raise RuntimeCacheRefusal("evaluation schedule owner or assignment differs from cache scope")
    exact = (
        schedule.resolved_graph_address == _address(resolved_graph_address, "resolved graph")
        and schedule.implementation_closure_address
            == _address(implementation_closure_address, "implementation closure")
        and schedule.registry_snapshot_address
            == _address(registry_snapshot_address, "registry snapshot")
    )
    if not exact:
        raise RuntimeCacheRefusal("evaluation schedule graph, implementation, or registry differs")
    if data_requirement_plan_address is not None and schedule.data_requirement_plan_address \
            != _address(data_requirement_plan_address, "data requirement plan"):
        raise RuntimeCacheRefusal("evaluation schedule DataRequirementPlan differs")
    if resource_plan_address is not None and schedule.resource_plan_address \
            != _address(resource_plan_address, "resource plan"):
        raise RuntimeCacheRefusal("evaluation schedule ResourcePlan differs")
    return schedule.schedule_address


def _optional_state_pair(predecessor: object, reset: object) -> tuple[str | None, str | None]:
    if predecessor is None and reset is None:
        return None, None
    if predecessor is None or reset is None:
        raise RuntimeCacheRefusal("state predecessor and reset facts must be both present or both absent")
    return _address(predecessor, "state predecessor"), _address(reset, "state reset")


def _paper_result_addresses(
    result_scope: object,
    fill: object,
    charge: object,
    book_epoch: object,
    paper_policy: object,
) -> dict[str, str | None]:
    names = ("fill_policy_address", "charge_schedule_address", "book_epoch_address",
             "paper_policy_address")
    values = (fill, charge, book_epoch, paper_policy)
    if result_scope == "EVALUATION_ONLY":
        if any(value is not None for value in values):
            raise RuntimeCacheRefusal("evaluation-only identity cannot carry paper result facts")
        return dict(zip(names, (None,) * len(names)))
    if result_scope != "PAPER_RESULT":
        raise RuntimeCacheRefusal("evaluation result scope is unknown")
    return {name: _address(value, name.replace("_", " "))
            for name, value in zip(names, values)}


def _utc_time(value: object, label: str) -> str:
    if value is None and label == "knowledge cutoff":
        raise RuntimeCacheRefusal("knowledge cutoff is unknown")
    if not isinstance(value, dt.datetime) or value.tzinfo is None \
            or value.utcoffset() != dt.timedelta(0):
        raise RuntimeCacheRefusal(f"{label} must be UTC-aware")
    if value.microsecond:
        raise RuntimeCacheRefusal(f"{label} must use whole seconds")
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: object, label: str) -> str:
    if not isinstance(value, dt.date) or isinstance(value, dt.datetime):
        raise RuntimeCacheRefusal(f"{label} must be an exact date")
    return value.isoformat()


def _integer(value: object, label: str, *, positive: bool = False,
             nonnegative: bool = False) -> int:
    if type(value) is not int:
        raise RuntimeCacheRefusal(f"{label} must be an exact integer")
    if positive and value <= 0 or nonnegative and value < 0:
        raise RuntimeCacheRefusal(f"{label} is outside its bound")
    return value


def _number(value: object, label: str, *, nonnegative: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeCacheRefusal(f"{label} is unknown or nonnumeric")
    if isinstance(value, float) and (not math.isfinite(value)):
        raise RuntimeCacheRefusal(f"{label} must be finite")
    if _is_negative_zero(value):
        raise RuntimeCacheRefusal(f"{label} contains negative zero")
    if nonnegative and value < 0:
        raise RuntimeCacheRefusal(f"{label} is outside its bound")
    return value


def _is_negative_zero(value: int | float) -> bool:
    return isinstance(value, float) and value == 0.0 and math.copysign(1.0, value) < 0


def _reject_negative_zero(value: Any) -> None:
    if _is_negative_zero(value):
        raise RuntimeCacheRefusal("identity contains negative zero")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_negative_zero(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _reject_negative_zero(item)


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


__all__ = [
    "ResourceBound",
    "RuntimeCacheIdentity",
    "RuntimeCacheRefusal",
    "derived_node_cache_identity",
    "evaluation_result_cache_identity",
    "observation_cache_identity",
    "static_window_cache_identity",
]
