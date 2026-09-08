"""Pure addressed evaluation scheduling over the accepted IR authorities.

This module plans phases and admits facts.  It does not evaluate a node, acquire
data, persist a result, or grant paper/live execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from fractions import Fraction
import re
import threading
from types import MappingProxyType
from typing import Any, Mapping
import weakref

from app.ir.hashing import content_address
from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolvedV2Graph, ResolutionError, resolved_v2_graph_address
from app.ir.resource_plan import ResourcePlan, ResourcePlanRefusal
from app.ir.schema import is_content_address
from app.market_data.capability import (
    CapabilityAssessment,
    CapabilityRefusal,
    capability_assessment_authority_envelope,
)
from app.market_data.eligibility import EligibilityResult
from app.market_data.requirements import DataRequirementPlan


_SCOPE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_ISSUED_LOCK = threading.Lock()


@dataclass(frozen=True)
class _IssuedFactSeal:
    reference: weakref.ReferenceType[Any]
    original_fingerprint: str
    original_state: Mapping[str, Any]


_ISSUED_FACTS: dict[tuple[type, int], _IssuedFactSeal] = {}


class ScheduleRefusalCode(str, Enum):
    INVALID_AUTHORITY = "INVALID_AUTHORITY"
    INVALID_CONTENT_ADDRESS = "INVALID_CONTENT_ADDRESS"
    INVALID_TOPOLOGY = "INVALID_TOPOLOGY"
    UNDECLARED_TRIGGER = "UNDECLARED_TRIGGER"
    INVALID_TIME = "INVALID_TIME"
    FUTURE_EVENT = "FUTURE_EVENT"
    FORMING_OBSERVATION = "FORMING_OBSERVATION"
    AVAILABILITY_BEFORE_COMPLETION = "AVAILABILITY_BEFORE_COMPLETION"
    LATE_UNAVAILABLE = "LATE_UNAVAILABLE"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    UNIT_AMBIGUOUS = "UNIT_AMBIGUOUS"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    UNSUPPORTED_MODE = "UNSUPPORTED_MODE"
    INVALID_GATE_OUTCOME = "INVALID_GATE_OUTCOME"
    ACQUISITION_GATE_UNKNOWN = "ACQUISITION_GATE_UNKNOWN"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    CONDITIONAL_REQUIREMENT_INVALID = "CONDITIONAL_REQUIREMENT_INVALID"
    INVALID_AUTHORED_GATE = "INVALID_AUTHORED_GATE"


class ScheduleRefusal(ValueError):
    """Typed fail-closed schedule or event refusal."""

    def __init__(self, code: ScheduleRefusalCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")


class AuthoredGateOutcome(str, Enum):
    REQUIRED = "REQUIRED"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"


class AcquisitionSupport(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


def _refuse(code: ScheduleRefusalCode, detail: str) -> None:
    raise ScheduleRefusal(code, detail)


def _address(value: Any, label: str) -> str:
    if type(value) is not str or not is_content_address(value):
        _refuse(ScheduleRefusalCode.INVALID_CONTENT_ADDRESS, f"{label} is not a content address")
    return value


def _require_exact_integer(value: Any, label: str) -> int:
    if type(value) is not int:
        _refuse(ScheduleRefusalCode.UNIT_AMBIGUOUS, f"{label} is not an exact bounded integer")
    return value


def _exact_nonnegative_int(value: Any, label: str, *, positive: bool = False) -> int:
    _require_exact_integer(value, label)
    if value < (1 if positive else 0):
        _refuse(ScheduleRefusalCode.UNIT_AMBIGUOUS, f"{label} is not an exact bounded integer")
    return value


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


def _new_closed_fact(cls: type, values: Mapping[str, Any]) -> Any:
    result = object.__new__(cls)
    for name in cls.__dataclass_fields__:
        if name in values:
            object.__setattr__(result, name, values[name])
    result.__post_init__()
    _issue_fact(result)
    return result


def _issue_fact(value: Any) -> None:
    _require_fact_runtime_shape(value)
    key = (type(value), id(value))

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        with _ISSUED_LOCK:
            seal = _ISSUED_FACTS.get(key)
            if seal is not None and seal.reference is reference:
                _ISSUED_FACTS.pop(key, None)

    reference = weakref.ref(value, discard)
    fingerprint = _fact_state_fingerprint(value)
    original_state = _capture_original_state(value)
    with _ISSUED_LOCK:
        _ISSUED_FACTS[key] = _IssuedFactSeal(reference, fingerprint, original_state)


def _verify_issued_fact(value: Any, cls: type, label: str) -> Any:
    if type(value) is not cls:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} has the wrong authority type")
    key = (cls, id(value))
    with _ISSUED_LOCK:
        seal = _ISSUED_FACTS.get(key)
        issued = seal is not None and seal.reference() is value
    if not issued:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} was not issued by its compiler")
    try:
        _require_fact_runtime_shape(value)
        current_fingerprint = _fact_state_fingerprint(value)
        unchanged = current_fingerprint == seal.original_fingerprint
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ScheduleRefusal(
            ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} state cannot be reconstructed"
        ) from exc
    if not unchanged:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} differs from its issued state")
    value.__post_init__()
    detached = _detached_fact_from_state(cls, seal.original_state)
    if _fact_state_fingerprint(detached) != seal.original_fingerprint:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} original snapshot is stale")
    return detached


@dataclass(frozen=True, init=False)
class ScheduleResourceCeiling:
    history_bytes_upper_bound: int
    memory_bytes_upper_bound: int
    cache_bytes_upper_bound: int
    queue_concurrency_upper_bound: int
    event_rate_events: int
    event_rate_per_seconds: int
    policy_address: str
    ceiling_address: str = field(init=False)

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("schedule resource ceilings may only be constructed by the compiler")

    def __post_init__(self) -> None:
        _require_ceiling_runtime_shape(self, complete=False)
        for name in (
            "history_bytes_upper_bound",
            "memory_bytes_upper_bound",
            "cache_bytes_upper_bound",
        ):
            _exact_nonnegative_int(getattr(self, name), name)
        _exact_nonnegative_int(
            self.queue_concurrency_upper_bound, "queue_concurrency_upper_bound", positive=True
        )
        _exact_nonnegative_int(self.event_rate_events, "event_rate_events", positive=True)
        _exact_nonnegative_int(
            self.event_rate_per_seconds, "event_rate_per_seconds", positive=True
        )
        _address(self.policy_address, "resource ceiling policy")
        object.__setattr__(self, "ceiling_address", content_address(_ceiling_payload(self)))


def compile_schedule_resource_ceiling(
    *,
    history_bytes_upper_bound: int,
    memory_bytes_upper_bound: int,
    cache_bytes_upper_bound: int,
    queue_concurrency_upper_bound: int,
    event_rate_events: int,
    event_rate_per_seconds: int,
    policy_address: str,
) -> ScheduleResourceCeiling:
    """Compile one process-local immutable resource-ceiling authority."""
    values = {
        "history_bytes_upper_bound": history_bytes_upper_bound,
        "memory_bytes_upper_bound": memory_bytes_upper_bound,
        "cache_bytes_upper_bound": cache_bytes_upper_bound,
        "queue_concurrency_upper_bound": queue_concurrency_upper_bound,
        "event_rate_events": event_rate_events,
        "event_rate_per_seconds": event_rate_per_seconds,
        "policy_address": policy_address,
    }
    return _new_closed_fact(ScheduleResourceCeiling, values)


def verify_schedule_resource_ceiling(
    ceiling: ScheduleResourceCeiling,
) -> ScheduleResourceCeiling:
    """Require the exact unchanged ceiling issued by its compiler."""
    return _verify_issued_fact(ceiling, ScheduleResourceCeiling, "schedule resource ceiling")


@dataclass(frozen=True, init=False)
class ConditionalAcquisitionAuthority:
    schedule_address: str
    owner_id: str
    assignment_id: str
    conditional_requirement_selector: str
    data_requirement_plan_address: str
    resource_plan_address: str
    capability_assessment_address: str
    eligibility_address: str
    result: AcquisitionSupport
    authority_address: str = field(init=False)

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("conditional acquisition authority is compiler-owned")

    def __post_init__(self) -> None:
        _require_conditional_authority_runtime_shape(self)
        for name in (
            "schedule_address",
            "conditional_requirement_selector",
            "data_requirement_plan_address",
            "resource_plan_address",
            "capability_assessment_address",
            "eligibility_address",
        ):
            _address(getattr(self, name), name)
        if type(self.result) is not AcquisitionSupport:
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "acquisition support is not closed")
        if not isinstance(self.owner_id, str) or not _SCOPE_ID.fullmatch(self.owner_id) \
                or not isinstance(self.assignment_id, str) or not _SCOPE_ID.fullmatch(self.assignment_id):
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "acquisition scope is invalid")
        object.__setattr__(
            self, "authority_address", content_address(_conditional_authority_payload(self))
        )


@dataclass(frozen=True, init=False)
class EvaluationScheduleAddress:
    owner_id: str
    assignment_id: str
    authored_ir_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    registry_snapshot_address: str
    data_requirement_plan_address: str
    resource_plan_address: str
    mode: str
    gate_node_id: str | None
    conditional_requirement_selector: str | None
    unconditional_nodes: tuple[str, ...]
    authored_gate_nodes: tuple[str, ...]
    dependent_nodes: tuple[str, ...]
    declared_triggers: tuple[str, ...]
    trigger_rates: tuple[Mapping[str, Any], ...]
    reset_requirements: tuple[Mapping[str, Any], ...]
    unit_contract_addresses: tuple[tuple[str, str], ...]
    event_unit_address: str
    maximum_age_seconds: int
    resource_ceiling_address: str
    schedule_address: str

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("evaluation schedules may only be constructed by the compiler")

    def __post_init__(self) -> None:
        _require_schedule_runtime_shape(self)
        if self.schedule_address != content_address(_schedule_payload(self)):
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "schedule address is stale or forged")


@dataclass(frozen=True, init=False)
class EvaluationEventAddress:
    schedule_address: str
    trigger: str
    observation_address: str
    event_at: datetime
    completed_at: datetime
    available_at: datetime
    recorded_at: datetime
    cutoff_at: datetime
    unit_contract_address: str
    event_address: str
    clock_precision: str = field(default="SECOND", init=False)

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("evaluation events may only be constructed by event admission")

    def __post_init__(self) -> None:
        _require_event_runtime_shape(self)
        if self.event_address != content_address(_event_payload(self)):
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "event address is stale or forged")


@dataclass(frozen=True, init=False)
class AuthoredAcquisitionGate:
    schedule_address: str
    gate_node_id: str
    outcome: AuthoredGateOutcome
    decision_input_address: str
    authority_address: str | None
    conditional_requirement_selector: str | None
    conditional_requirement: Mapping[str, Any] | None
    gate_address: str

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("authored gate facts may only be constructed by gate admission")

    def __post_init__(self) -> None:
        _require_gate_runtime_shape(self)
        if type(self.outcome) is not AuthoredGateOutcome \
                or self.gate_address != content_address(_gate_payload(self)):
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "authored gate address is stale or forged")


def _require_exact_string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} is not an exact string")
    return value


def _require_exact_tuple(value: Any, label: str) -> tuple[Any, ...]:
    if type(value) is not tuple:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} is not an exact tuple")
    return value


def _require_closed_immutable(value: Any, label: str) -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is tuple:
        for index, item in enumerate(value):
            _require_closed_immutable(item, f"{label}[{index}]")
        return
    if type(value) is MappingProxyType:
        for key, item in value.items():
            _require_exact_string(key, f"{label} key")
            _require_closed_immutable(item, f"{label}.{key}")
        return
    _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, f"{label} is not closed immutable state")


def _require_ceiling_runtime_shape(
    ceiling: ScheduleResourceCeiling, *, complete: bool = True,
) -> None:
    for name in (
        "history_bytes_upper_bound", "memory_bytes_upper_bound",
        "cache_bytes_upper_bound", "queue_concurrency_upper_bound",
        "event_rate_events", "event_rate_per_seconds",
    ):
        _require_exact_integer(getattr(ceiling, name), name)
    _address(ceiling.policy_address, "resource ceiling policy")
    if complete:
        _address(ceiling.ceiling_address, "resource ceiling")


def _require_conditional_authority_runtime_shape(
    authority: ConditionalAcquisitionAuthority,
) -> None:
    for name in ("owner_id", "assignment_id"):
        _require_exact_string(getattr(authority, name), name)
    for name in (
        "schedule_address", "conditional_requirement_selector",
        "data_requirement_plan_address", "resource_plan_address",
        "capability_assessment_address", "eligibility_address",
    ):
        _address(getattr(authority, name), name)
    if type(authority.result) is not AcquisitionSupport:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "acquisition support is not an exact enum")
    if hasattr(authority, "authority_address"):
        _address(authority.authority_address, "conditional authority")


def _require_schedule_variant(schedule: EvaluationScheduleAddress) -> None:
    if schedule.gate_node_id is not None:
        _require_exact_string(schedule.gate_node_id, "gate node")
        _address(schedule.conditional_requirement_selector, "conditional requirement selector")
        return
    if (schedule.conditional_requirement_selector is not None
            or schedule.authored_gate_nodes != () or schedule.dependent_nodes != ()
            or schedule.mode != "research" or schedule.declared_triggers != ("completed_bar",)):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "completed-bar schedule carries conditional or non-research state")


def _require_conditional_schedule(schedule: EvaluationScheduleAddress) -> None:
    if schedule.gate_node_id is None:
        _refuse(ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID,
                "completed-bar schedules do not authorize conditional acquisition")


def _require_schedule_runtime_shape(schedule: EvaluationScheduleAddress) -> None:
    _require_schedule_variant(schedule)
    for name in ("owner_id", "assignment_id", "mode"):
        _require_exact_string(getattr(schedule, name), name)
    for name in (
        "authored_ir_address", "resolved_graph_address",
        "implementation_closure_address", "registry_snapshot_address",
        "data_requirement_plan_address", "resource_plan_address",
        "event_unit_address", "resource_ceiling_address", "schedule_address",
    ):
        _address(getattr(schedule, name), name)
    _require_schedule_sequences(schedule)
    _require_schedule_rates_and_resets(schedule)
    _require_schedule_units(schedule)
    _exact_nonnegative_int(schedule.maximum_age_seconds, "maximum age")


def _require_schedule_sequences(schedule):
    for name in (
        "unconditional_nodes", "authored_gate_nodes", "dependent_nodes",
        "declared_triggers", "trigger_rates", "reset_requirements",
        "unit_contract_addresses",
    ):
        _require_exact_tuple(getattr(schedule, name), name)
    for name in ("unconditional_nodes", "authored_gate_nodes", "dependent_nodes"):
        for item in getattr(schedule, name):
            _require_exact_string(item, f"{name} item")
    triggers = schedule.declared_triggers
    for trigger in triggers:
        _require_exact_string(trigger, "declared trigger")
    if triggers != tuple(sorted(set(triggers))):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "declared triggers are not canonical")


def _require_schedule_rates_and_resets(schedule):
    for row in schedule.trigger_rates:
        if type(row) is not MappingProxyType or set(row) != {"trigger", "events", "per_seconds"}:
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "trigger rate shape is not canonical")
        _require_exact_string(row["trigger"], "trigger rate trigger")
        _exact_nonnegative_int(row["events"], "trigger rate events", positive=True)
        _exact_nonnegative_int(row["per_seconds"], "trigger rate seconds", positive=True)
    for row in schedule.reset_requirements:
        if type(row) is not MappingProxyType:
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "reset requirement is not immutable")
        _require_closed_immutable(row, "reset requirement")


def _require_schedule_units(schedule):
    for pair in schedule.unit_contract_addresses:
        if type(pair) is not tuple or len(pair) != 2:
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "unit contract row is not canonical")
        _require_exact_string(pair[0], "unit node")
        _address(pair[1], "unit contract")


def _require_event_runtime_shape(event: EvaluationEventAddress) -> None:
    for name in ("schedule_address", "observation_address", "unit_contract_address", "event_address"):
        _address(getattr(event, name), name)
    _require_exact_string(event.trigger, "event trigger")
    read_clock = _event_clock_reader(event.clock_precision)
    for name in ("event_at", "completed_at", "available_at", "recorded_at", "cutoff_at"):
        read_clock(getattr(event, name), name)


def _require_gate_runtime_shape(gate: AuthoredAcquisitionGate) -> None:
    for name in ("schedule_address", "decision_input_address", "gate_address"):
        _address(getattr(gate, name), name)
    _require_exact_string(gate.gate_node_id, "gate node")
    if type(gate.outcome) is not AuthoredGateOutcome:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "gate outcome is not an exact enum")
    for name in ("authority_address", "conditional_requirement_selector"):
        value = getattr(gate, name)
        if value is not None:
            _address(value, name)
    if gate.conditional_requirement is not None:
        if type(gate.conditional_requirement) is not MappingProxyType:
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "conditional requirement is not immutable")
        _require_closed_immutable(gate.conditional_requirement, "conditional requirement")
    if gate.outcome is AuthoredGateOutcome.NOT_REQUIRED and any(
        value is not None for value in (
            gate.authority_address, gate.conditional_requirement_selector,
            gate.conditional_requirement,
        )
    ):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "NOT_REQUIRED gate carries authority")
    if gate.outcome is AuthoredGateOutcome.REQUIRED and any(
        value is None for value in (
            gate.authority_address, gate.conditional_requirement_selector,
            gate.conditional_requirement,
        )
    ):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "REQUIRED gate lacks authority")


def _require_fact_runtime_shape(value: Any) -> None:
    if type(value) is ScheduleResourceCeiling:
        _require_ceiling_runtime_shape(value)
    elif type(value) is ConditionalAcquisitionAuthority:
        _require_conditional_authority_runtime_shape(value)
    elif type(value) is EvaluationScheduleAddress:
        _require_schedule_runtime_shape(value)
    elif type(value) is EvaluationEventAddress:
        _require_event_runtime_shape(value)
    elif type(value) is AuthoredAcquisitionGate:
        _require_gate_runtime_shape(value)
    else:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "unknown issued fact type")


def _copy_exact_runtime_state(value: Any) -> Any:
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is datetime:
        return datetime(
            value.year, value.month, value.day, value.hour, value.minute,
            value.second, value.microsecond, tzinfo=timezone.utc, fold=value.fold,
        )
    if type(value) in {AuthoredGateOutcome, AcquisitionSupport}:
        return value
    if type(value) is tuple:
        return tuple(_copy_exact_runtime_state(item) for item in value)
    if type(value) is MappingProxyType:
        return MappingProxyType({
            key: _copy_exact_runtime_state(item) for key, item in value.items()
        })
    _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "issued state cannot be detached exactly")


def _capture_original_state(value: Any) -> Mapping[str, Any]:
    return MappingProxyType({
        name: _copy_exact_runtime_state(getattr(value, name))
        for name in type(value).__dataclass_fields__
        if hasattr(value, name)
    })


def _detached_fact_from_state(cls: type, state: Mapping[str, Any]) -> Any:
    if type(state) is not MappingProxyType:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "issued original state is not sealed")
    detached = object.__new__(cls)
    for name in cls.__dataclass_fields__:
        if name in state:
            object.__setattr__(detached, name, _copy_exact_runtime_state(state[name]))
    detached.__post_init__()
    _require_fact_runtime_shape(detached)
    return detached


def verify_evaluation_schedule(
    schedule: EvaluationScheduleAddress,
) -> EvaluationScheduleAddress:
    """Require one exact schedule object issued by this process's compiler."""
    return _verify_issued_fact(
        schedule, EvaluationScheduleAddress, "evaluation schedule"
    )


def verify_conditional_acquisition_authority(
    authority: ConditionalAcquisitionAuthority,
) -> ConditionalAcquisitionAuthority:
    """Require one exact conditional authority issued by its compiler."""
    return _verify_issued_fact(
        authority, ConditionalAcquisitionAuthority, "conditional acquisition authority"
    )


def verify_evaluation_event(event: EvaluationEventAddress) -> EvaluationEventAddress:
    """Require one exact event object issued by event admission."""
    return _verify_issued_fact(event, EvaluationEventAddress, "evaluation event")


def verify_authored_acquisition_gate(
    gate: AuthoredAcquisitionGate,
) -> AuthoredAcquisitionGate:
    """Require one exact gate object issued by gate admission."""
    return _verify_issued_fact(gate, AuthoredAcquisitionGate, "authored acquisition gate")


def _ceiling_payload(ceiling: ScheduleResourceCeiling) -> dict[str, Any]:
    return {
        "schema": "schedule-resource-ceiling/1",
        "history_bytes_upper_bound": ceiling.history_bytes_upper_bound,
        "memory_bytes_upper_bound": ceiling.memory_bytes_upper_bound,
        "cache_bytes_upper_bound": ceiling.cache_bytes_upper_bound,
        "queue_concurrency_upper_bound": ceiling.queue_concurrency_upper_bound,
        "event_rate": {
            "events": ceiling.event_rate_events,
            "per_seconds": ceiling.event_rate_per_seconds,
        },
        "policy_address": ceiling.policy_address,
    }


def _conditional_authority_payload(
    authority: ConditionalAcquisitionAuthority,
) -> dict[str, Any]:
    return {
        "schema": "conditional-acquisition-authority/1",
        "schedule_address": authority.schedule_address,
        "owner_id": authority.owner_id,
        "assignment_id": authority.assignment_id,
        "conditional_requirement_selector": authority.conditional_requirement_selector,
        "data_requirement_plan_address": authority.data_requirement_plan_address,
        "resource_plan_address": authority.resource_plan_address,
        "capability_assessment_address": authority.capability_assessment_address,
        "eligibility_address": authority.eligibility_address,
        "result": authority.result.value,
    }


def _schedule_payload_values(values: Mapping[str, Any]) -> dict[str, Any]:
    payload = {name: values[name] for name in (
        "owner_id", "assignment_id", "authored_ir_address", "resolved_graph_address",
        "implementation_closure_address", "registry_snapshot_address", "data_requirement_plan_address",
        "resource_plan_address", "mode", "event_unit_address", "maximum_age_seconds",
        "resource_ceiling_address",
    )}
    payload.update(
        phases={"unconditional": list(values["unconditional_nodes"])},
        declared_triggers=list(values["declared_triggers"]),
        trigger_rates=_plain(values["trigger_rates"]),
        reset_requirements=_plain(values["reset_requirements"]),
        unit_contract_addresses=[{"node_id": node, "unit_contract_address": address}
                                 for node, address in values["unit_contract_addresses"]],
    )
    if values["gate_node_id"] is None:
        payload.update(schema="evaluation-schedule/2", evaluation_kind="COMPLETED_BAR")
    else:
        payload.update(schema="evaluation-schedule/1", gate_node_id=values["gate_node_id"],
                       conditional_requirement_selector=values["conditional_requirement_selector"])
        payload["phases"].update(authored_gate=list(values["authored_gate_nodes"]),
                                 dependent=list(values["dependent_nodes"]))
    return payload


def _schedule_payload(schedule: EvaluationScheduleAddress) -> dict[str, Any]:
    return _schedule_payload_values(vars(schedule))


def _event_payload_values(values: Mapping[str, Any]) -> dict[str, Any]:
    payload = {name: values[name] for name in (
        "schedule_address", "trigger", "observation_address", "unit_contract_address")}
    payload.update({name: _iso(values[name]) for name in (
        "event_at", "completed_at", "available_at", "recorded_at", "cutoff_at")})
    payload["schema"] = "evaluation-event/1"
    if values.get("clock_precision", "SECOND") == "MICROSECOND":
        payload.update(schema="evaluation-event/2", clock_precision="MICROSECOND")
    return payload


def _event_payload(event: EvaluationEventAddress) -> dict[str, Any]:
    return _event_payload_values(vars(event))


def _gate_payload(gate: AuthoredAcquisitionGate) -> dict[str, Any]:
    return {
        "schema": "authored-acquisition-gate/1",
        "schedule_address": gate.schedule_address,
        "gate_node_id": gate.gate_node_id,
        "outcome": gate.outcome.value,
        "decision_input_address": gate.decision_input_address,
        "authority_address": gate.authority_address,
        "conditional_requirement_selector": gate.conditional_requirement_selector,
        "conditional_requirement": _plain(gate.conditional_requirement),
    }


def _fact_state_fingerprint(value: Any) -> str:
    if type(value) is ScheduleResourceCeiling:
        payload, address = _ceiling_payload(value), value.ceiling_address
    elif type(value) is ConditionalAcquisitionAuthority:
        payload, address = _conditional_authority_payload(value), value.authority_address
    elif type(value) is EvaluationScheduleAddress:
        payload, address = _schedule_payload(value), value.schedule_address
    elif type(value) is EvaluationEventAddress:
        payload, address = _event_payload(value), value.event_address
    elif type(value) is AuthoredAcquisitionGate:
        payload, address = _gate_payload(value), value.gate_address
    else:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "unknown issued fact type")
    return content_address({
        "issued_fact_type": type(value).__name__,
        "canonical_preimage": payload,
        "canonical_address": address,
    })


def _data_plan_payload(plan: DataRequirementPlan) -> dict[str, Any]:
    records = [
        {
            "authored_node_id": record["authored_node_id"],
            "lowered_path": list(record["lowered_path"]),
            "leaf_component": {
                "component_id": record["leaf_component"][0],
                "component_version": record["leaf_component"][1],
            },
            "requirement": _plain(record["requirement"]),
        }
        for record in plan.requirements
    ]
    return {
        "authored_ir_address": plan.authored_ir_address,
        "resolved_graph_address": plan.resolved_graph_address,
        "implementation_closure_address": plan.implementation_closure_address,
        "registry_snapshot_address": plan.registry_snapshot_address,
        "declaration_addresses": list(plan.declaration_addresses),
        "requirements": records,
        "parameter_binding_provenance": _plain(plan.parameter_binding_provenance),
    }


def _require_exact_authorities(
    graph: Any,
    data_plan: Any,
    resource_plan: Any,
    registry: Any,
) -> None:
    if type(graph) is not ResolvedV2Graph or type(data_plan) is not DataRequirementPlan \
            or type(resource_plan) is not ResourcePlan or type(registry) is not PlatformRegistry:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "schedule inputs are not canonical authority types")
    try:
        graph_address = resolved_v2_graph_address(
            graph.nodes,
            graph.registry_snapshot_address,
            graph.implementation_closure_address,
            graph.registry_snapshot_payload,
            graph.data_requirement_declaration_closure,
        )
    except (ResolutionError, TypeError, ValueError) as exc:
        raise ScheduleRefusal(
            ScheduleRefusalCode.INVALID_AUTHORITY, "resolved graph does not reconstruct"
        ) from exc
    if graph_address != graph.resolved_graph_address:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "resolved graph address is stale")
    if (
        registry.registry_snapshot_address != graph.registry_snapshot_address
        or _plain(registry.registry_snapshot_payload) != _plain(graph.registry_snapshot_payload)
    ):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "registry differs from the resolved graph")
    for value, label in (
        (graph.authored_ir_address, "authored IR"),
        (graph.resolved_graph_address, "resolved graph"),
        (graph.implementation_closure_address, "implementation closure"),
        (graph.registry_snapshot_address, "registry snapshot"),
        (data_plan.plan_address, "data requirement plan"),
        (resource_plan.plan_address, "resource plan"),
    ):
        _address(value, label)
    if content_address(_data_plan_payload(data_plan)) != data_plan.plan_address:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "data requirement plan address is stale")
    identities = {
        "authored_ir_address": graph.authored_ir_address,
        "resolved_graph_address": graph.resolved_graph_address,
        "implementation_closure_address": graph.implementation_closure_address,
        "registry_snapshot_address": graph.registry_snapshot_address,
    }
    if any(getattr(data_plan, name) != value for name, value in identities.items()):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "data plan identity differs from the graph")
    try:
        ResourcePlan(resource_plan.document, resource_plan.plan_address)
    except (ResourcePlanRefusal, TypeError, ValueError) as exc:
        raise ScheduleRefusal(
            ScheduleRefusalCode.INVALID_AUTHORITY, "resource plan does not reconstruct"
        ) from exc
    expected_resource = {
        **identities,
        "data_requirement_plan_address": data_plan.plan_address,
    }
    if any(resource_plan.document[name] != value for name, value in expected_resource.items()):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "resource plan identity differs")


def _topology_edge(edge, node_ids):
    source = edge.get("source", {}) if isinstance(edge, Mapping) else {}
    target = edge.get("target", {}) if isinstance(edge, Mapping) else {}
    if source.get("scope") != "node" or target.get("scope") != "node":
        return None
    left, right = source.get("node_id"), target.get("node_id")
    if left not in node_ids or right not in node_ids:
        _refuse(ScheduleRefusalCode.INVALID_TOPOLOGY, "resolved edge names an unknown node")
    return left, right


def _topology_links(graph):
    node_ids = {node.node_id for node in graph.nodes}
    predecessors = {node_id: set() for node_id in node_ids}
    successors = {node_id: set() for node_id in node_ids}
    topology = graph.topology_document
    if not isinstance(topology, Mapping):
        _refuse(ScheduleRefusalCode.INVALID_TOPOLOGY, "resolved topology is absent")
    for edge in topology.get("edges", ()):
        pair = _topology_edge(edge, node_ids)
        if pair is not None:
            left, right = pair
            successors[left].add(right)
            predecessors[right].add(left)
    return predecessors, successors


def _take_ready_node(ready, pending, successors, order):
    node = ready.pop(0)
    order.append(node)
    for child in sorted(successors[node]):
        pending[child].discard(node)
        if not pending[child] and child not in order and child not in ready:
            ready.append(child)
    ready.sort()


def _topological_order(graph: ResolvedV2Graph) -> tuple[tuple[str, ...], Mapping[str, set[str]]]:
    predecessors, successors = _topology_links(graph)
    pending = {node: set(values) for node, values in predecessors.items()}
    ready = sorted(node for node, values in pending.items() if not values)
    order: list[str] = []
    while ready:
        _take_ready_node(ready, pending, successors, order)
    if len(order) != len(predecessors):
        _refuse(ScheduleRefusalCode.INVALID_TOPOLOGY, "resolved topology is cyclic")
    return tuple(order), successors


def _descendant_nodes(successors, gate_node_id):
    descendants: set[str] = set()
    frontier = list(successors[gate_node_id])
    while frontier:
        node = frontier.pop()
        if node in descendants:
            continue
        descendants.add(node)
        frontier.extend(successors[node])
    return descendants


def _topological_phases(graph: ResolvedV2Graph, gate_node_id: str) -> tuple[tuple[str, ...], ...]:
    if gate_node_id not in {node.node_id for node in graph.nodes}:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORED_GATE, "authored gate node is absent")
    order, successors = _topological_order(graph)
    descendants = _descendant_nodes(successors, gate_node_id)
    unconditional = tuple(node for node in order if node != gate_node_id and node not in descendants)
    dependent = tuple(node for node in order if node in descendants)
    return unconditional, (gate_node_id,), dependent


def _require_authored_boolean_gate(
    graph: ResolvedV2Graph,
    registry: PlatformRegistry,
    gate_node_id: str,
    dependent: tuple[str, ...],
) -> None:
    nodes = [node for node in graph.nodes if node.node_id == gate_node_id]
    if len(nodes) != 1:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORED_GATE, "gate does not name one resolved node")
    node = nodes[0]
    if node.authored_node_id != gate_node_id or node.lowered_path != (gate_node_id,):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORED_GATE, "gate is not an exact authored leaf")
    descriptor = registry.v2_components.get(node.component)
    contract = registry.node_contracts.get(node.component)
    if (
        not isinstance(descriptor, Mapping)
        or not isinstance(contract, Mapping)
        or descriptor.get("domain_family") != "state"
        or descriptor.get("structural_role") not in {"transform", "stateful"}
        or contract.get("visible_family") != "TYPE_5"
    ):
        _refuse(
            ScheduleRefusalCode.INVALID_AUTHORED_GATE,
            "gate is not an accepted authored Logic/State node",
        )
    ports = {port.get("port_id"): port for port in descriptor.get("ports", ())
             if isinstance(port, Mapping)}
    outgoing = []
    for edge in graph.topology_document.get("edges", ()):
        source = edge.get("source", {}) if isinstance(edge, Mapping) else {}
        target = edge.get("target", {}) if isinstance(edge, Mapping) else {}
        if source.get("scope") == "node" and source.get("node_id") == gate_node_id \
                and target.get("scope") == "node":
            outgoing.append((source, target))
    if not outgoing or any(target.get("node_id") not in dependent for _source, target in outgoing):
        _refuse(
            ScheduleRefusalCode.INVALID_AUTHORED_GATE,
            "gate has no exact output edge into its dependent closure",
        )
    by_node = {item.node_id: item for item in graph.nodes}
    for source, target in outgoing:
        source_port = ports.get(source.get("port_id"))
        target_node = by_node.get(target.get("node_id"))
        target_descriptor = registry.v2_components.get(target_node.component) if target_node else None
        target_ports = {
            port.get("port_id"): port for port in target_descriptor.get("ports", ())
            if isinstance(port, Mapping)
        } if isinstance(target_descriptor, Mapping) else {}
        target_port = target_ports.get(target.get("port_id"))
        source_type = source_port.get("type_ref") if isinstance(source_port, Mapping) else None
        target_type = target_port.get("type_ref") if isinstance(target_port, Mapping) else None
        type_key = (
            (source_type.get("type_id"), source_type.get("type_version"))
            if isinstance(source_type, Mapping) else None
        )
        type_descriptor = registry.v2_types.get(type_key) if type_key else None
        target_contract = registry.node_contracts.get(target_node.component) if target_node else None
        if (
            source_port is None
            or source_port.get("direction") != "output"
            or target_port is None
            or target_port.get("direction") != "input"
            or _plain(source_type) != _plain(target_type)
            or not isinstance(type_descriptor, Mapping)
            or type_descriptor.get("runtime_representation") != "bool"
            or contract.get("output_types", {}).get(source.get("port_id")) != "boolean-value/1"
            or not isinstance(target_contract, Mapping)
            or target_contract.get("input_types", {}).get(target.get("port_id")) != "boolean-value/1"
        ):
            _refuse(
                ScheduleRefusalCode.INVALID_AUTHORED_GATE,
                "every gate edge into the dependent closure must carry accepted boolean truth",
            )


def canonical_conditional_requirement_selector(record: Mapping[str, Any]) -> str:
    """Address one exact bound DataRequirementPlan record for cache consumers."""
    try:
        if type(record) is not MappingProxyType or set(record) != {
            "authored_node_id", "lowered_path", "leaf_component", "requirement"
        } or type(record["authored_node_id"]) is not str \
                or type(record["lowered_path"]) is not tuple \
                or type(record["leaf_component"]) is not tuple \
                or len(record["leaf_component"]) != 2:
            raise TypeError
        payload = {
            "authored_node_id": record["authored_node_id"],
            "lowered_path": list(record["lowered_path"]),
            "leaf_component": {
                "component_id": record["leaf_component"][0],
                "component_version": record["leaf_component"][1],
            },
            "requirement": _plain(record["requirement"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ScheduleRefusal(
            ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID,
            "conditional requirement record is malformed",
        ) from exc
    return content_address(payload)


def _conditional_record(
    data_plan: DataRequirementPlan, selector: str
) -> Mapping[str, Any]:
    matches = [
        record for record in data_plan.requirements
        if canonical_conditional_requirement_selector(record) == selector
    ]
    if len(matches) != 1:
        _refuse(
            ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID,
            "conditional requirement is absent or duplicated",
        )
    requirement = matches[0]["requirement"]
    instrument = requirement.get("instrument", {})
    depth = requirement.get("depth", {})
    if instrument.get("type") != "ECONOMIC_SELECTOR" and depth.get("kind") == "NONE":
        _refuse(
            ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID,
            "conditional requirement is not static option/depth demand",
        )
    return matches[0]


def _resource_preflight(
    resource_plan: ResourcePlan,
    trigger_rates: Mapping[str, Mapping[str, int]],
    ceiling: ScheduleResourceCeiling,
) -> tuple[tuple[str, ...], tuple[Mapping[str, Any], ...]]:
    declared = tuple(sorted({row["trigger"] for row in resource_plan.document["trigger_requirements"]}))
    if type(trigger_rates) is not dict:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "trigger rates are not an exact mapping")
    if set(trigger_rates) != set(declared):
        _refuse(ScheduleRefusalCode.UNDECLARED_TRIGGER, "trigger-rate facts do not close declared triggers")
    normalized = []
    total_rate = Fraction(0, 1)
    for trigger in declared:
        rate = trigger_rates[trigger]
        if type(rate) is not dict or set(rate) != {"events", "per_seconds"}:
            _refuse(ScheduleRefusalCode.UNIT_AMBIGUOUS, "trigger rate lacks exact event/time units")
        events = _exact_nonnegative_int(rate["events"], "trigger events", positive=True)
        seconds = _exact_nonnegative_int(rate["per_seconds"], "trigger seconds", positive=True)
        total_rate += Fraction(events, seconds)
        normalized.append(_freeze({"trigger": trigger, "events": events, "per_seconds": seconds}))
    document = resource_plan.document
    history = sum(row["bytes_upper_bound"] for row in document["history_requirements"])
    limits = (
        (history, ceiling.history_bytes_upper_bound, "history bytes"),
        (document["memory_bytes_upper_bound"], ceiling.memory_bytes_upper_bound, "memory bytes"),
        (document["cache_bytes_upper_bound"], ceiling.cache_bytes_upper_bound, "cache bytes"),
        (
            document["queue_concurrency_upper_bound"],
            ceiling.queue_concurrency_upper_bound,
            "queue concurrency",
        ),
    )
    exceeded = [label for demand, limit, label in limits if demand > limit]
    if total_rate > Fraction(ceiling.event_rate_events, ceiling.event_rate_per_seconds):
        exceeded.append("event rate")
    if exceeded:
        _refuse(
            ScheduleRefusalCode.RESOURCE_LIMIT_EXCEEDED,
            "resource ceiling exceeded: " + ", ".join(exceeded),
        )
    return declared, tuple(normalized)


def _require_schedule_scope(owner_id, assignment_id, mode, resource_plan):
    if type(owner_id) is not str or not _SCOPE_ID.fullmatch(owner_id) \
            or type(assignment_id) is not str or not _SCOPE_ID.fullmatch(assignment_id):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "owner or assignment identity is invalid")
    if mode not in {"research", "paper", "live"} or not resource_plan.document["mode_support"].get(mode):
        _refuse(ScheduleRefusalCode.UNSUPPORTED_MODE, "resource plan does not support mode")


def _schedule_unit_contracts(graph, unit_contract_addresses):
    node_ids = {node.node_id for node in graph.nodes}
    if type(unit_contract_addresses) is not dict or set(unit_contract_addresses) != node_ids:
        _refuse(ScheduleRefusalCode.UNIT_AMBIGUOUS, "every resolved node needs one exact unit contract")
    return tuple(sorted((node, _address(value, f"unit contract for {node}"))
                        for node, value in unit_contract_addresses.items()))


def _schedule_maximum_age(data_requirement_plan):
    freshness = [record["requirement"]["freshness"]["maximum_age_seconds"]
                 for record in data_requirement_plan.requirements]
    if not freshness or any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                            for value in freshness):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "data plan lacks exact freshness bounds")
    return min(freshness)


def _schedule_common_values(
    *, owner_id, assignment_id, resolved_graph, data_requirement_plan, resource_plan,
    registry, unit_contract_addresses, event_unit_address, mode, trigger_rates, resource_ceiling,
) -> dict[str, Any]:
    _require_exact_authorities(resolved_graph, data_requirement_plan, resource_plan, registry)
    resource_ceiling = verify_schedule_resource_ceiling(resource_ceiling)
    _require_schedule_scope(owner_id, assignment_id, mode, resource_plan)
    units = _schedule_unit_contracts(resolved_graph, unit_contract_addresses)
    event_unit = _address(event_unit_address, "event unit contract")
    declared, normalized_rates = _resource_preflight(resource_plan, trigger_rates, resource_ceiling)
    maximum_age = _schedule_maximum_age(data_requirement_plan)
    return dict(
        owner_id=owner_id, assignment_id=assignment_id,
        authored_ir_address=resolved_graph.authored_ir_address,
        resolved_graph_address=resolved_graph.resolved_graph_address,
        implementation_closure_address=resolved_graph.implementation_closure_address,
        registry_snapshot_address=resolved_graph.registry_snapshot_address,
        data_requirement_plan_address=data_requirement_plan.plan_address,
        resource_plan_address=resource_plan.plan_address, mode=mode,
        declared_triggers=declared, trigger_rates=normalized_rates,
        reset_requirements=tuple(_freeze(_plain(row)) for row in resource_plan.document["state_requirements"]),
        unit_contract_addresses=units, event_unit_address=event_unit,
        maximum_age_seconds=maximum_age, resource_ceiling_address=resource_ceiling.ceiling_address,
    )


def _issue_evaluation_schedule(values, *, gate_node_id, selector, phases):
    values.update(gate_node_id=gate_node_id, conditional_requirement_selector=selector,
                  unconditional_nodes=phases[0], authored_gate_nodes=phases[1], dependent_nodes=phases[2])
    values["schedule_address"] = content_address(_schedule_payload_values(values))
    return _new_closed_fact(EvaluationScheduleAddress, values)


def compile_evaluation_schedule(
    *, owner_id: str, assignment_id: str, resolved_graph: ResolvedV2Graph,
    data_requirement_plan: DataRequirementPlan, resource_plan: ResourcePlan, registry: PlatformRegistry,
    gate_node_id: str, conditional_requirement_selector: str,
    unit_contract_addresses: Mapping[str, str], event_unit_address: str, mode: str,
    trigger_rates: Mapping[str, Mapping[str, int]], resource_ceiling: ScheduleResourceCeiling,
) -> EvaluationScheduleAddress:
    """Compile one deterministic conditional plan without evaluating or acquiring."""
    values = _schedule_common_values(
        owner_id=owner_id, assignment_id=assignment_id, resolved_graph=resolved_graph,
        data_requirement_plan=data_requirement_plan, resource_plan=resource_plan, registry=registry,
        unit_contract_addresses=unit_contract_addresses, event_unit_address=event_unit_address,
        mode=mode, trigger_rates=trigger_rates, resource_ceiling=resource_ceiling)
    selector = _address(conditional_requirement_selector, "conditional requirement selector")
    conditional = _conditional_record(data_requirement_plan, selector)
    phases = _topological_phases(resolved_graph, gate_node_id)
    _require_authored_boolean_gate(resolved_graph, registry, gate_node_id, phases[2])
    dependent_authored = {node.authored_node_id for node in resolved_graph.nodes if node.node_id in phases[2]}
    if conditional["authored_node_id"] not in dependent_authored:
        _refuse(ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID,
                "conditional requirement is not in the gate-dependent closure")
    return _issue_evaluation_schedule(values, gate_node_id=gate_node_id, selector=selector, phases=phases)


def _require_completed_bar_demand(data_plan, graph, registry):
    for record in data_plan.requirements:
        requirement = record["requirement"]
        if (requirement["instrument"]["type"] != "PHYSICAL"
                or requirement["field"] not in {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}
                or _plain(requirement["depth"]) != {"kind": "NONE", "levels": None}
                or requirement["derived_local"] is not False):
            _refuse(ScheduleRefusalCode.CONDITIONAL_REQUIREMENT_INVALID,
                    "completed-bar scheduling requires physical OHLCV without conditional or derived demand")
    for node in graph.nodes:
        if registry.node_contracts[node.component]["bar_policy"] != "COMPLETED_ONLY":
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "node does not require completed bars")


def compile_completed_bar_evaluation_schedule(
    *, owner_id: str, assignment_id: str, resolved_graph: ResolvedV2Graph,
    data_requirement_plan: DataRequirementPlan, resource_plan: ResourcePlan, registry: PlatformRegistry,
    unit_contract_addresses: Mapping[str, str], event_unit_address: str, mode: str,
    trigger_rates: Mapping[str, Mapping[str, int]], resource_ceiling: ScheduleResourceCeiling,
    freshness_ceiling_seconds: int | None = None,
) -> EvaluationScheduleAddress:
    """Plan research-only completed OHLCV, optionally tightening its freshness budget."""
    if mode != "research":
        _refuse(ScheduleRefusalCode.UNSUPPORTED_MODE, "completed-bar scheduling is research-only")
    values = _schedule_common_values(
        owner_id=owner_id, assignment_id=assignment_id, resolved_graph=resolved_graph,
        data_requirement_plan=data_requirement_plan, resource_plan=resource_plan, registry=registry,
        unit_contract_addresses=unit_contract_addresses, event_unit_address=event_unit_address,
        mode=mode, trigger_rates=trigger_rates, resource_ceiling=resource_ceiling)
    if values["declared_triggers"] != ("completed_bar",):
        _refuse(ScheduleRefusalCode.UNDECLARED_TRIGGER, "completed-bar scheduling requires only completed_bar")
    _require_completed_bar_demand(data_requirement_plan, resolved_graph, registry)
    if freshness_ceiling_seconds is not None:
        ceiling = _exact_nonnegative_int(freshness_ceiling_seconds, "freshness ceiling seconds")
        values["maximum_age_seconds"] = min(values["maximum_age_seconds"], ceiling)
    order, _successors = _topological_order(resolved_graph)
    return _issue_evaluation_schedule(values, gate_node_id=None, selector=None, phases=(order, (), ()))


def _utc_second(value: Any, label: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is not timezone.utc
        or value.microsecond != 0
    ):
        _refuse(
            ScheduleRefusalCode.INVALID_TIME,
            f"{label} must use the immutable whole-second UTC representation",
        )
    return datetime(
        value.year, value.month, value.day, value.hour, value.minute,
        value.second, tzinfo=timezone.utc, fold=value.fold,
    )


def _utc_instant(value: Any, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is not timezone.utc:
        _refuse(ScheduleRefusalCode.INVALID_TIME, f"{label} must use the immutable UTC representation")
    return _copy_exact_runtime_state(value)


def _event_clock_reader(precision):
    if type(precision) is not str or precision not in {"SECOND", "MICROSECOND"}:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "event clock precision is not closed")
    return _utc_second if precision == "SECOND" else _utc_instant


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _require_event_clock_bounds(times, maximum_age_seconds):
    if times["event_at"] > times["cutoff_at"]:
        _refuse(ScheduleRefusalCode.FUTURE_EVENT, "event occurs after the knowledge cutoff")
    if times["completed_at"] > times["cutoff_at"]:
        _refuse(ScheduleRefusalCode.FORMING_OBSERVATION, "observation is not completed at cutoff")
    if times["available_at"] < times["completed_at"]:
        _refuse(
            ScheduleRefusalCode.AVAILABILITY_BEFORE_COMPLETION,
            "availability precedes completion",
        )
    if times["recorded_at"] > times["cutoff_at"] or times["available_at"] > times["cutoff_at"]:
        _refuse(ScheduleRefusalCode.LATE_UNAVAILABLE, "observation was unavailable at cutoff")
    if not (
        times["event_at"] <= times["completed_at"] <= times["available_at"]
        <= times["recorded_at"] <= times["cutoff_at"]
    ):
        _refuse(ScheduleRefusalCode.INVALID_TIME, "event chronology is not causal")
    age_microseconds = (times["cutoff_at"] - times["completed_at"]) // timedelta(microseconds=1)
    if age_microseconds > maximum_age_seconds * 1_000_000:
        _refuse(ScheduleRefusalCode.STALE_OBSERVATION, "observation exceeds declared freshness")


def admit_evaluation_event(
    schedule: EvaluationScheduleAddress,
    *,
    trigger: str,
    observation_address: str,
    event_at: datetime,
    completed_at: datetime,
    available_at: datetime,
    recorded_at: datetime,
    cutoff_at: datetime,
    unit_contract_address: str,
) -> EvaluationEventAddress:
    schedule = verify_evaluation_schedule(schedule)
    _require_exact_string(trigger, "event trigger")
    if trigger not in schedule.declared_triggers:
        _refuse(ScheduleRefusalCode.UNDECLARED_TRIGGER, "event trigger is not declared")
    observation = _address(observation_address, "observation")
    unit = _address(unit_contract_address, "event unit")
    if unit != schedule.event_unit_address:
        _refuse(ScheduleRefusalCode.UNIT_AMBIGUOUS, "event unit differs from the schedule")
    precision = "MICROSECOND" if schedule.gate_node_id is None else "SECOND"
    read_clock = _event_clock_reader(precision)
    times = {name: read_clock(value, name) for name, value in {
        "event_at": event_at, "completed_at": completed_at, "available_at": available_at,
        "recorded_at": recorded_at, "cutoff_at": cutoff_at,
    }.items()}
    _require_event_clock_bounds(times, schedule.maximum_age_seconds)
    values = dict(schedule_address=schedule.schedule_address, trigger=trigger,
                  observation_address=observation, **times,
                  unit_contract_address=unit, clock_precision=precision)
    values["event_address"] = content_address(_event_payload_values(values))
    return _new_closed_fact(EvaluationEventAddress, values)


def _eligibility_plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _eligibility_plain(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_eligibility_plain(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _eligibility_plain(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    return value


def _verify_eligibility_result(result: EligibilityResult) -> None:
    if type(result) is not EligibilityResult:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "eligibility is not compiler-produced")
    payload = {
        "schema": "graph-data-eligibility/1",
        "owner_id": result.owner_id,
        "mode": "RESEARCH",
        "graph_identifier": result.graph_identifier,
        "graph_version": result.graph_version,
        "graph_content_address": result.graph_content_address,
        "resolved_graph_address": result.resolved_graph_address,
        "plan_address": result.plan_address,
        "registry_snapshot_address": result.registry_snapshot_address,
        "input_binding_context_address": result.input_binding_context_address,
        "capability_profile_address": result.capability_profile_address,
        "conformance_address": result.conformance_address,
        "provider_contract_address": result.provider_contract_address,
        "dataset_manifest_addresses": result.dataset_manifest_addresses,
        "instrument_addresses": result.instrument_addresses,
        "truth_snapshot_addresses": result.truth_snapshot_addresses,
        "policy_addresses": result.policy_addresses,
        "requested_start": result.requested_start,
        "requested_end": result.requested_end,
        "as_of": result.as_of,
        "status": result.status,
        "refusals": result.refusals,
    }
    if result.eligibility_address != content_address(_eligibility_plain(payload)):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "eligibility address is stale or forged")


def compile_conditional_acquisition_authority(
    schedule: EvaluationScheduleAddress,
    *,
    data_requirement_plan: DataRequirementPlan,
    capability_assessment: CapabilityAssessment,
    eligibility_result: EligibilityResult,
) -> ConditionalAcquisitionAuthority:
    """Derive conditional support from a detached verified schedule snapshot."""
    snapshot = verify_evaluation_schedule(schedule)
    _require_conditional_schedule(snapshot)
    return _compile_conditional_acquisition_authority_from_snapshot(
        snapshot,
        data_requirement_plan=data_requirement_plan,
        capability_assessment=capability_assessment,
        eligibility_result=eligibility_result,
    )


def _compile_conditional_acquisition_authority_from_snapshot(
    schedule: EvaluationScheduleAddress,
    *,
    data_requirement_plan: DataRequirementPlan,
    capability_assessment: CapabilityAssessment,
    eligibility_result: EligibilityResult,
) -> ConditionalAcquisitionAuthority:
    _require_schedule_runtime_shape(schedule)
    if type(data_requirement_plan) is not DataRequirementPlan:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "conditional compilation lacks schedule/data facts")
    if data_requirement_plan.plan_address != schedule.data_requirement_plan_address:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "conditional data plan differs from schedule")
    try:
        capability_assessment_authority_envelope(capability_assessment)
    except (CapabilityRefusal, TypeError, ValueError) as exc:
        raise ScheduleRefusal(
            ScheduleRefusalCode.INVALID_AUTHORITY, "capability assessment is not canonical"
        ) from exc
    _verify_eligibility_result(eligibility_result)
    expected_selection = content_address({
        "dataset_manifest_addresses": sorted(eligibility_result.dataset_manifest_addresses)
    })
    expected_truth = content_address({
        "truth_snapshot_addresses": sorted(eligibility_result.truth_snapshot_addresses)
    })
    expected_policy = content_address({
        "policy_addresses": sorted(eligibility_result.policy_addresses)
    })
    exact = (
        capability_assessment.owner_id == eligibility_result.owner_id == schedule.owner_id
        and capability_assessment.plan_address == eligibility_result.plan_address
            == schedule.data_requirement_plan_address
        and capability_assessment.registry_snapshot_address
            == eligibility_result.registry_snapshot_address == schedule.registry_snapshot_address
        and eligibility_result.graph_content_address == schedule.authored_ir_address
        and eligibility_result.resolved_graph_address == schedule.resolved_graph_address
        and capability_assessment.capability_profile_address
            == eligibility_result.capability_profile_address
        and capability_assessment.assessment_evidence_address
            == eligibility_result.conformance_address
        and capability_assessment.dataset_manifest_address == expected_selection
        and capability_assessment.market_truth_snapshot_address == expected_truth
        and capability_assessment.evaluation_policy_address == expected_policy
    )
    if not exact:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "capability/eligibility scope differs from schedule")
    rows = [
        row for row in capability_assessment.requirement_results
        if row["selector"] == schedule.conditional_requirement_selector
    ]
    if len(rows) != 1:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "conditional selector lacks exact capability result")
    if schedule.mode != "research" or capability_assessment.mode != "RESEARCH" \
            or eligibility_result.status != "SUPPORTED" or eligibility_result.refusals:
        result = AcquisitionSupport.UNSUPPORTED
    elif rows[0]["result"] == "UNKNOWN":
        result = AcquisitionSupport.UNKNOWN
    elif rows[0]["result"] == "SATISFIED":
        result = AcquisitionSupport.SUPPORTED
    else:
        result = AcquisitionSupport.UNSUPPORTED
    values = {
        "schedule_address": schedule.schedule_address,
        "owner_id": schedule.owner_id,
        "assignment_id": schedule.assignment_id,
        "conditional_requirement_selector": schedule.conditional_requirement_selector,
        "data_requirement_plan_address": schedule.data_requirement_plan_address,
        "resource_plan_address": schedule.resource_plan_address,
        "capability_assessment_address": capability_assessment.authority_address,
        "eligibility_address": eligibility_result.eligibility_address,
        "result": result,
    }
    return _new_closed_fact(ConditionalAcquisitionAuthority, values)


def _require_acquisition_scope(authority, schedule):
    if any(getattr(authority, name) != getattr(schedule, name) for name in (
            "schedule_address", "owner_id", "assignment_id", "conditional_requirement_selector",
            "data_requirement_plan_address", "resource_plan_address")):
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "conditional authority differs from schedule")


def _required_gate_authority(schedule, data_plan, authority, capability, eligibility):
    if any(value is None for value in (authority, capability, eligibility)):
        _refuse(ScheduleRefusalCode.CAPABILITY_UNKNOWN, "conditional authority is absent")
    authority = verify_conditional_acquisition_authority(authority)
    expected = _compile_conditional_acquisition_authority_from_snapshot(
        schedule, data_requirement_plan=data_plan,
        capability_assessment=capability, eligibility_result=eligibility)
    if authority != expected:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "conditional authority was not reconstructed")
    if expected.result is AcquisitionSupport.UNKNOWN:
        _refuse(ScheduleRefusalCode.CAPABILITY_UNKNOWN, "conditional capability is unknown")
    if expected.result is AcquisitionSupport.UNSUPPORTED:
        _refuse(ScheduleRefusalCode.CAPABILITY_UNSUPPORTED, "conditional capability is unsupported")
    _require_acquisition_scope(expected, schedule)
    return expected


def _gate_conditional_values(schedule, data_plan, outcome, authority, capability, eligibility):
    if outcome is not AuthoredGateOutcome.REQUIRED:
        if any(value is not None for value in (authority, capability, eligibility)):
            _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "NOT_REQUIRED cannot carry acquisition authority")
        return None, None, None
    expected = _required_gate_authority(schedule, data_plan, authority, capability, eligibility)
    record = _conditional_record(data_plan, schedule.conditional_requirement_selector)
    return schedule.conditional_requirement_selector, _freeze(_plain(record)), expected.authority_address


def admit_authored_acquisition_gate(
    schedule: EvaluationScheduleAddress,
    *,
    data_requirement_plan: DataRequirementPlan,
    outcome: AuthoredGateOutcome,
    decision_input_address: str,
    authority: ConditionalAcquisitionAuthority | None = None,
    capability_assessment: CapabilityAssessment | None = None,
    eligibility_result: EligibilityResult | None = None,
) -> AuthoredAcquisitionGate:
    schedule = verify_evaluation_schedule(schedule)
    _require_conditional_schedule(schedule)
    if type(data_requirement_plan) is not DataRequirementPlan:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "gate lacks canonical schedule/data facts")
    if data_requirement_plan.plan_address != schedule.data_requirement_plan_address:
        _refuse(ScheduleRefusalCode.INVALID_AUTHORITY, "gate data plan differs from schedule")
    decision = _address(decision_input_address, "gate decision input")
    if type(outcome) is not AuthoredGateOutcome:
        _refuse(ScheduleRefusalCode.INVALID_GATE_OUTCOME, "gate output is not a closed enum")
    if outcome is AuthoredGateOutcome.UNKNOWN:
        _refuse(ScheduleRefusalCode.ACQUISITION_GATE_UNKNOWN, "authored gate output is unknown")
    selector, conditional, authority_address = _gate_conditional_values(
        schedule, data_requirement_plan, outcome, authority, capability_assessment, eligibility_result)
    payload = {
        "schema": "authored-acquisition-gate/1",
        "schedule_address": schedule.schedule_address,
        "gate_node_id": schedule.gate_node_id,
        "outcome": outcome.value,
        "decision_input_address": decision,
        "authority_address": authority_address,
        "conditional_requirement_selector": selector,
        "conditional_requirement": _plain(conditional),
    }
    values = dict(
        schedule_address=schedule.schedule_address,
        gate_node_id=schedule.gate_node_id,
        outcome=outcome,
        decision_input_address=decision,
        authority_address=authority_address,
        conditional_requirement_selector=selector,
        conditional_requirement=conditional,
        gate_address=content_address(payload),
    )
    return _new_closed_fact(AuthoredAcquisitionGate, values)


__all__ = [
    "AcquisitionSupport",
    "AuthoredAcquisitionGate",
    "AuthoredGateOutcome",
    "ConditionalAcquisitionAuthority",
    "EvaluationEventAddress",
    "EvaluationScheduleAddress",
    "ScheduleRefusal",
    "ScheduleRefusalCode",
    "ScheduleResourceCeiling",
    "admit_authored_acquisition_gate",
    "admit_evaluation_event",
    "compile_conditional_acquisition_authority",
    "compile_evaluation_schedule",
    "compile_completed_bar_evaluation_schedule",
    "compile_schedule_resource_ceiling",
    "canonical_conditional_requirement_selector",
    "verify_conditional_acquisition_authority",
    "verify_authored_acquisition_gate",
    "verify_evaluation_event",
    "verify_evaluation_schedule",
    "verify_schedule_resource_ceiling",
]
