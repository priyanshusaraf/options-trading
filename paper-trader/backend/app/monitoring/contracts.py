"""Pure unpublished contracts for monitoring alerts and tenant attention.

The facts in this module stop before persistence, publication, or any external
effect.  Authored protection values are display evidence, not venue instructions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import re
from typing import Any, ClassVar, Iterable

from app.ir.hashing import canonical_json, content_address


_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")
_SYMBOL = re.compile(r"^[^\x00-\x1f\x7f]{1,64}$")


class MonitoringContractError(ValueError):
    """A closed monitoring fact or replay contract was violated."""


class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"


class StrategyState(Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


class FactValidity(Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    INVALID = "INVALID"
    REFUSED = "REFUSED"


class Freshness(Enum):
    FRESH = "FRESH"
    STALE = "STALE"


class EntryReferenceKind(Enum):
    COMPLETED_EVENT_CLOSE = "COMPLETED_EVENT_CLOSE"


class ProtectionKind(Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class ProtectionBasis(Enum):
    ABSOLUTE_PRICE = "ABSOLUTE_PRICE"
    PERCENT_FROM_ENTRY_REFERENCE = "PERCENT_FROM_ENTRY_REFERENCE"
    DISTANCE_FROM_ENTRY_REFERENCE = "DISTANCE_FROM_ENTRY_REFERENCE"
    VERIFIED_INDICATOR_DISTANCE = "VERIFIED_INDICATOR_DISTANCE"


class ProtectionUnits(Enum):
    PRICE = "PRICE"
    RATE = "RATE"
    PRICE_POINTS = "PRICE_POINTS"


class DeliveryChannel(Enum):
    IN_APP = "IN_APP"


class DeliveryOutcome(Enum):
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class AttentionAction(Enum):
    READ = "READ"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    DISMISS = "DISMISS"


class NoAlertCode(Enum):
    HOLD = "HOLD"
    REPLAY_CATCH_UP = "REPLAY_CATCH_UP"
    EVALUATION_REFUSED = "EVALUATION_REFUSED"
    MISSING_DATA = "MISSING_DATA"
    INVALID_DATA = "INVALID_DATA"
    STALE_DATA = "STALE_DATA"
    REPEATED_TARGET_STATE = "REPEATED_TARGET_STATE"
    INVALID_ENTRY_REFERENCE = "INVALID_ENTRY_REFERENCE"
    INVALID_PROTECTION = "INVALID_PROTECTION"
    INVALID_PROTECTION_GEOMETRY = "INVALID_PROTECTION_GEOMETRY"
    ACTION_STATE_MISMATCH = "ACTION_STATE_MISMATCH"


def _require_enum(value: Any, expected: type[Enum], label: str) -> None:
    if type(value) is not expected:
        raise MonitoringContractError(f"{label}_CLOSED_VALUE_REQUIRED")


def _require_identifier(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise MonitoringContractError(f"{label}_IDENTIFIER_REQUIRED")


def _require_address(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise MonitoringContractError(f"{label}_CONTENT_ADDRESS_REQUIRED")


def _require_code(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        raise MonitoringContractError(f"{label}_CLOSED_CODE_REQUIRED")


def _require_decimal(value: Any, label: str, *, positive: bool = True) -> None:
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise MonitoringContractError(f"{label}_CANONICAL_DECIMAL_REQUIRED")
    if positive and value == "0":
        raise MonitoringContractError(f"{label}_POSITIVE_DECIMAL_REQUIRED")


def _require_utc(value: Any, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is not timezone.utc:
        raise MonitoringContractError(f"{label}_UTC_REQUIRED")


def _time(value: datetime) -> str:
    _require_utc(value, "TIME")
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise MonitoringContractError(f"{label}_UTC_REQUIRED")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise MonitoringContractError(f"{label}_UTC_REQUIRED") from exc
    if _time(parsed) != value:
        raise MonitoringContractError(f"{label}_UTC_REQUIRED")
    return parsed


def _enum(enum_type: type[Enum], value: Any, label: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise MonitoringContractError(f"{label}_CLOSED_VALUE_REQUIRED") from exc


class _AddressedFact:
    schema: ClassVar[str]

    def canonical_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.canonical_payload()).encode("utf-8")

    @property
    def address(self) -> str:
        return content_address(self.canonical_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_payload(), "address": self.address}


@dataclass(frozen=True, slots=True)
class EntryReference:
    kind: EntryReferenceKind
    canonical_instrument_address: str
    value: str | None
    currency: str
    observed_at: datetime
    source_truth_address: str
    validity: FactValidity

    schema: ClassVar[str] = "monitoring-entry-reference/1"

    def __post_init__(self) -> None:
        _require_enum(self.kind, EntryReferenceKind, "ENTRY_REFERENCE_KIND")
        _require_enum(self.validity, FactValidity, "ENTRY_REFERENCE_VALIDITY")
        _require_address(self.canonical_instrument_address, "ENTRY_REFERENCE_INSTRUMENT")
        _require_address(self.source_truth_address, "ENTRY_REFERENCE_TRUTH")
        _require_utc(self.observed_at, "ENTRY_REFERENCE_OBSERVED_AT")
        if not isinstance(self.currency, str) or not re.fullmatch(r"^[A-Z]{3}$", self.currency):
            raise MonitoringContractError("ENTRY_REFERENCE_CURRENCY_REQUIRED")
        if self.validity is FactValidity.VALID:
            _require_decimal(self.value, "ENTRY_REFERENCE_VALUE")
        elif self.value is not None:
            raise MonitoringContractError("INVALID_ENTRY_REFERENCE_HAS_VALUE")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "kind": self.kind.value,
            "canonical_instrument_address": self.canonical_instrument_address,
            "value": self.value,
            "currency": self.currency,
            "observed_at": _time(self.observed_at),
            "source_truth_address": self.source_truth_address,
            "validity": self.validity.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        if not isinstance(value, dict) or set(value) != {
            "schema", "kind", "canonical_instrument_address", "value", "currency",
            "observed_at", "source_truth_address", "validity",
        } or value["schema"] != cls.schema:
            raise MonitoringContractError("ENTRY_REFERENCE_SCHEMA")
        return cls(
            kind=_enum(EntryReferenceKind, value["kind"], "ENTRY_REFERENCE_KIND"),
            canonical_instrument_address=value["canonical_instrument_address"],
            value=value["value"], currency=value["currency"],
            observed_at=_parse_time(value["observed_at"], "ENTRY_REFERENCE_OBSERVED_AT"),
            source_truth_address=value["source_truth_address"],
            validity=_enum(FactValidity, value["validity"], "ENTRY_REFERENCE_VALIDITY"),
        )


@dataclass(frozen=True, slots=True)
class ProtectionEvidence:
    kind: ProtectionKind
    basis: ProtectionBasis
    authored_component_id: str
    authored_component_version: int
    authored_component_address: str
    authored_contract_address: str
    authored_parameters_address: str
    authored_value: str
    units: ProtectionUnits
    resolved_value: str | None
    resolution_address: str
    validity: FactValidity

    schema: ClassVar[str] = "monitoring-protection-evidence/1"

    def __post_init__(self) -> None:
        _require_enum(self.kind, ProtectionKind, "PROTECTION_KIND")
        _require_enum(self.basis, ProtectionBasis, "PROTECTION_BASIS")
        _require_enum(self.units, ProtectionUnits, "PROTECTION_UNITS")
        _require_enum(self.validity, FactValidity, "PROTECTION_VALIDITY")
        _require_identifier(self.authored_component_id, "PROTECTION_COMPONENT")
        if type(self.authored_component_version) is not int or self.authored_component_version < 1:
            raise MonitoringContractError("PROTECTION_COMPONENT_VERSION")
        for label, value in (
            ("PROTECTION_COMPONENT", self.authored_component_address),
            ("PROTECTION_CONTRACT", self.authored_contract_address),
            ("PROTECTION_PARAMETERS", self.authored_parameters_address),
            ("PROTECTION_RESOLUTION", self.resolution_address),
        ):
            _require_address(value, label)
        _require_decimal(self.authored_value, "PROTECTION_AUTHORED_VALUE")
        if self.validity is FactValidity.VALID:
            _require_decimal(self.resolved_value, "PROTECTION_RESOLVED_VALUE")
        elif self.resolved_value is not None:
            raise MonitoringContractError("INVALID_PROTECTION_HAS_RESOLVED_VALUE")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "kind": self.kind.value,
            "basis": self.basis.value,
            "authored_component_id": self.authored_component_id,
            "authored_component_version": self.authored_component_version,
            "authored_component_address": self.authored_component_address,
            "authored_contract_address": self.authored_contract_address,
            "authored_parameters_address": self.authored_parameters_address,
            "authored_value": self.authored_value,
            "units": self.units.value,
            "resolved_value": self.resolved_value,
            "resolution_address": self.resolution_address,
            "validity": self.validity.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        expected = {
            "schema", "kind", "basis", "authored_component_id",
            "authored_component_version", "authored_component_address",
            "authored_contract_address", "authored_parameters_address",
            "authored_value", "units", "resolved_value", "resolution_address", "validity",
        }
        if not isinstance(value, dict) or set(value) != expected or value["schema"] != cls.schema:
            raise MonitoringContractError("PROTECTION_EVIDENCE_SCHEMA")
        return cls(
            kind=_enum(ProtectionKind, value["kind"], "PROTECTION_KIND"),
            basis=_enum(ProtectionBasis, value["basis"], "PROTECTION_BASIS"),
            authored_component_id=value["authored_component_id"],
            authored_component_version=value["authored_component_version"],
            authored_component_address=value["authored_component_address"],
            authored_contract_address=value["authored_contract_address"],
            authored_parameters_address=value["authored_parameters_address"],
            authored_value=value["authored_value"],
            units=_enum(ProtectionUnits, value["units"], "PROTECTION_UNITS"),
            resolved_value=value["resolved_value"], resolution_address=value["resolution_address"],
            validity=_enum(FactValidity, value["validity"], "PROTECTION_VALIDITY"),
        )


@dataclass(frozen=True, slots=True)
class MonitoringSignalEvent(_AddressedFact):
    owner_id: str
    assignment_id: str
    strategy_id: str
    graph_version_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    admission_address: str
    canonical_instrument_address: str
    display_symbol: str
    previous_state: StrategyState
    target_state: StrategyState
    action: SignalAction
    evaluation_event_address: str
    event_at: datetime
    latest_data_at: datetime
    knowledge_cutoff_at: datetime
    valid_until: datetime
    evaluation_validity: FactValidity
    freshness: Freshness
    repeated_target_state: bool
    entry_reference: EntryReference
    stop_loss: ProtectionEvidence
    take_profit: ProtectionEvidence
    state_before_address: str
    state_after_address: str
    provider_evidence_address: str
    dataset_address: str
    reason_code: str
    reason_evidence_address: str

    schema: ClassVar[str] = "monitoring-signal-event/1"

    def __post_init__(self) -> None:
        for label, value in (
            ("OWNER", self.owner_id), ("ASSIGNMENT", self.assignment_id),
            ("STRATEGY", self.strategy_id),
        ):
            _require_identifier(value, label)
        for label, value in (
            ("GRAPH_VERSION", self.graph_version_address),
            ("RESOLVED_GRAPH", self.resolved_graph_address),
            ("IMPLEMENTATION_CLOSURE", self.implementation_closure_address),
            ("ADMISSION", self.admission_address),
            ("CANONICAL_INSTRUMENT", self.canonical_instrument_address),
            ("EVALUATION_EVENT", self.evaluation_event_address),
            ("STATE_BEFORE", self.state_before_address),
            ("STATE_AFTER", self.state_after_address),
            ("PROVIDER_EVIDENCE", self.provider_evidence_address),
            ("DATASET", self.dataset_address),
            ("REASON_EVIDENCE", self.reason_evidence_address),
        ):
            _require_address(value, label)
        if not isinstance(self.display_symbol, str) or not _SYMBOL.fullmatch(self.display_symbol):
            raise MonitoringContractError("DISPLAY_SYMBOL_SAFE_TEXT_REQUIRED")
        for value, expected, label in (
            (self.previous_state, StrategyState, "PREVIOUS_STATE"),
            (self.target_state, StrategyState, "TARGET_STATE"),
            (self.action, SignalAction, "SIGNAL_ACTION"),
            (self.evaluation_validity, FactValidity, "EVALUATION_VALIDITY"),
            (self.freshness, Freshness, "FRESHNESS"),
        ):
            _require_enum(value, expected, label)
        if type(self.repeated_target_state) is not bool:
            raise MonitoringContractError("REPEATED_TARGET_STATE_BOOLEAN_REQUIRED")
        for label, value in (
            ("EVENT_AT", self.event_at), ("LATEST_DATA_AT", self.latest_data_at),
            ("KNOWLEDGE_CUTOFF_AT", self.knowledge_cutoff_at),
            ("VALID_UNTIL", self.valid_until),
        ):
            _require_utc(value, label)
        if not self.latest_data_at <= self.event_at <= self.knowledge_cutoff_at <= self.valid_until:
            raise MonitoringContractError("MONITORING_EVENT_TIME_NOT_MONOTONIC")
        if not isinstance(self.entry_reference, EntryReference):
            raise MonitoringContractError("ENTRY_REFERENCE_REQUIRED")
        if self.entry_reference.canonical_instrument_address != self.canonical_instrument_address:
            raise MonitoringContractError("ENTRY_REFERENCE_INSTRUMENT_MISMATCH")
        if self.entry_reference.observed_at > self.latest_data_at:
            raise MonitoringContractError("ENTRY_REFERENCE_AFTER_LATEST_DATA")
        if not isinstance(self.stop_loss, ProtectionEvidence) or self.stop_loss.kind is not ProtectionKind.STOP_LOSS:
            raise MonitoringContractError("STOP_LOSS_EVIDENCE_REQUIRED")
        if not isinstance(self.take_profit, ProtectionEvidence) or self.take_profit.kind is not ProtectionKind.TAKE_PROFIT:
            raise MonitoringContractError("TAKE_PROFIT_EVIDENCE_REQUIRED")
        _require_code(self.reason_code, "REASON")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "strategy_id": self.strategy_id,
            "graph_version_address": self.graph_version_address,
            "resolved_graph_address": self.resolved_graph_address,
            "implementation_closure_address": self.implementation_closure_address,
            "admission_address": self.admission_address,
            "canonical_instrument_address": self.canonical_instrument_address,
            "display_symbol": self.display_symbol,
            "previous_state": self.previous_state.value,
            "target_state": self.target_state.value,
            "action": self.action.value,
            "evaluation_event_address": self.evaluation_event_address,
            "event_at": _time(self.event_at),
            "latest_data_at": _time(self.latest_data_at),
            "knowledge_cutoff_at": _time(self.knowledge_cutoff_at),
            "valid_until": _time(self.valid_until),
            "evaluation_validity": self.evaluation_validity.value,
            "freshness": self.freshness.value,
            "repeated_target_state": self.repeated_target_state,
            "entry_reference": self.entry_reference.to_dict(),
            "stop_loss": self.stop_loss.to_dict(),
            "take_profit": self.take_profit.to_dict(),
            "state_before_address": self.state_before_address,
            "state_after_address": self.state_after_address,
            "provider_evidence_address": self.provider_evidence_address,
            "dataset_address": self.dataset_address,
            "reason_code": self.reason_code,
            "reason_evidence_address": self.reason_evidence_address,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        payload = _verified_payload(value, cls.schema, {
            "schema", "owner_id", "assignment_id", "strategy_id",
            "graph_version_address", "resolved_graph_address",
            "implementation_closure_address", "admission_address",
            "canonical_instrument_address", "display_symbol", "previous_state",
            "target_state", "action", "evaluation_event_address", "event_at",
            "latest_data_at", "knowledge_cutoff_at", "valid_until",
            "evaluation_validity", "freshness", "repeated_target_state",
            "entry_reference", "stop_loss", "take_profit", "state_before_address",
            "state_after_address", "provider_evidence_address", "dataset_address",
            "reason_code", "reason_evidence_address",
        })
        try:
            result = cls(
                owner_id=payload["owner_id"], assignment_id=payload["assignment_id"],
                strategy_id=payload["strategy_id"],
                graph_version_address=payload["graph_version_address"],
                resolved_graph_address=payload["resolved_graph_address"],
                implementation_closure_address=payload["implementation_closure_address"],
                admission_address=payload["admission_address"],
                canonical_instrument_address=payload["canonical_instrument_address"],
                display_symbol=payload["display_symbol"],
                previous_state=_enum(StrategyState, payload["previous_state"], "PREVIOUS_STATE"),
                target_state=_enum(StrategyState, payload["target_state"], "TARGET_STATE"),
                action=_enum(SignalAction, payload["action"], "SIGNAL_ACTION"),
                evaluation_event_address=payload["evaluation_event_address"],
                event_at=_parse_time(payload["event_at"], "EVENT_AT"),
                latest_data_at=_parse_time(payload["latest_data_at"], "LATEST_DATA_AT"),
                knowledge_cutoff_at=_parse_time(payload["knowledge_cutoff_at"], "KNOWLEDGE_CUTOFF_AT"),
                valid_until=_parse_time(payload["valid_until"], "VALID_UNTIL"),
                evaluation_validity=_enum(FactValidity, payload["evaluation_validity"], "EVALUATION_VALIDITY"),
                freshness=_enum(Freshness, payload["freshness"], "FRESHNESS"),
                repeated_target_state=payload["repeated_target_state"],
                entry_reference=EntryReference.from_dict(payload["entry_reference"]),
                stop_loss=ProtectionEvidence.from_dict(payload["stop_loss"]),
                take_profit=ProtectionEvidence.from_dict(payload["take_profit"]),
                state_before_address=payload["state_before_address"],
                state_after_address=payload["state_after_address"],
                provider_evidence_address=payload["provider_evidence_address"],
                dataset_address=payload["dataset_address"], reason_code=payload["reason_code"],
                reason_evidence_address=payload["reason_evidence_address"],
            )
        except KeyError as exc:
            raise MonitoringContractError("MONITORING_SIGNAL_EVENT_SCHEMA") from exc
        _verify_serialized_address(value, result.address)
        return result


@dataclass(frozen=True, slots=True)
class SignalAlert(_AddressedFact):
    owner_id: str
    assignment_id: str
    monitoring_event_address: str
    strategy_id: str
    graph_version_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    admission_address: str
    canonical_instrument_address: str
    display_symbol: str
    previous_state: StrategyState
    target_state: StrategyState
    action: SignalAction
    evaluation_event_address: str
    event_at: datetime
    latest_data_at: datetime
    knowledge_cutoff_at: datetime
    valid_until: datetime
    freshness: Freshness
    entry_reference: EntryReference
    stop_loss: ProtectionEvidence
    take_profit: ProtectionEvidence
    state_before_address: str
    state_after_address: str
    provider_evidence_address: str
    dataset_address: str
    reason_code: str
    reason_evidence_address: str

    schema: ClassVar[str] = "signal-alert/1"

    def __post_init__(self) -> None:
        _require_identifier(self.owner_id, "OWNER")
        _require_identifier(self.assignment_id, "ASSIGNMENT")
        _require_identifier(self.strategy_id, "STRATEGY")
        for label, value in (
            ("MONITORING_EVENT", self.monitoring_event_address),
            ("GRAPH_VERSION", self.graph_version_address),
            ("RESOLVED_GRAPH", self.resolved_graph_address),
            ("IMPLEMENTATION_CLOSURE", self.implementation_closure_address),
            ("ADMISSION", self.admission_address),
            ("CANONICAL_INSTRUMENT", self.canonical_instrument_address),
            ("EVALUATION_EVENT", self.evaluation_event_address),
            ("STATE_BEFORE", self.state_before_address),
            ("STATE_AFTER", self.state_after_address),
            ("PROVIDER_EVIDENCE", self.provider_evidence_address),
            ("DATASET", self.dataset_address),
            ("REASON_EVIDENCE", self.reason_evidence_address),
        ):
            _require_address(value, label)
        if not isinstance(self.display_symbol, str) or not _SYMBOL.fullmatch(self.display_symbol):
            raise MonitoringContractError("DISPLAY_SYMBOL_SAFE_TEXT_REQUIRED")
        _require_enum(self.previous_state, StrategyState, "PREVIOUS_STATE")
        _require_enum(self.target_state, StrategyState, "TARGET_STATE")
        _require_enum(self.action, SignalAction, "SIGNAL_ACTION")
        _require_enum(self.freshness, Freshness, "FRESHNESS")
        if self.action not in {SignalAction.BUY, SignalAction.SELL, SignalAction.EXIT}:
            raise MonitoringContractError("ALERT_ACTION_INELIGIBLE")
        if self.freshness is not Freshness.FRESH:
            raise MonitoringContractError("ALERT_FRESHNESS_REQUIRED")
        for label, value in (
            ("EVENT_AT", self.event_at), ("LATEST_DATA_AT", self.latest_data_at),
            ("KNOWLEDGE_CUTOFF_AT", self.knowledge_cutoff_at), ("VALID_UNTIL", self.valid_until),
        ):
            _require_utc(value, label)
        if not self.latest_data_at <= self.event_at <= self.knowledge_cutoff_at <= self.valid_until:
            raise MonitoringContractError("ALERT_TIME_NOT_MONOTONIC")
        if self.entry_reference.canonical_instrument_address != self.canonical_instrument_address:
            raise MonitoringContractError("ALERT_ENTRY_INSTRUMENT_MISMATCH")
        if self.entry_reference.observed_at > self.latest_data_at:
            raise MonitoringContractError("ALERT_ENTRY_AFTER_LATEST_DATA")
        if self.stop_loss.kind is not ProtectionKind.STOP_LOSS or self.take_profit.kind is not ProtectionKind.TAKE_PROFIT:
            raise MonitoringContractError("ALERT_PROTECTION_KIND_MISMATCH")
        if any(value.validity is not FactValidity.VALID for value in (
            self.entry_reference, self.stop_loss, self.take_profit,
        )):
            raise MonitoringContractError("ALERT_REQUIRES_VALID_EVIDENCE")
        expected = {
            SignalAction.BUY: ({StrategyState.FLAT, StrategyState.SHORT}, StrategyState.LONG),
            SignalAction.SELL: ({StrategyState.FLAT, StrategyState.LONG}, StrategyState.SHORT),
            SignalAction.EXIT: ({StrategyState.LONG, StrategyState.SHORT}, StrategyState.FLAT),
        }
        previous, target = expected[self.action]
        if self.previous_state not in previous or self.target_state is not target:
            raise MonitoringContractError("ALERT_ACTION_STATE_MISMATCH")
        if not _resolved_geometry_is_valid(
            self.action, self.previous_state, self.entry_reference.value,
            self.stop_loss.resolved_value, self.take_profit.resolved_value,
        ):
            raise MonitoringContractError("ALERT_PROTECTION_GEOMETRY")
        _require_code(self.reason_code, "REASON")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "monitoring_event_address": self.monitoring_event_address,
            "strategy_id": self.strategy_id,
            "graph_version_address": self.graph_version_address,
            "resolved_graph_address": self.resolved_graph_address,
            "implementation_closure_address": self.implementation_closure_address,
            "admission_address": self.admission_address,
            "canonical_instrument_address": self.canonical_instrument_address,
            "display_symbol": self.display_symbol,
            "previous_state": self.previous_state.value,
            "target_state": self.target_state.value,
            "action": self.action.value,
            "evaluation_event_address": self.evaluation_event_address,
            "event_at": _time(self.event_at),
            "latest_data_at": _time(self.latest_data_at),
            "knowledge_cutoff_at": _time(self.knowledge_cutoff_at),
            "valid_until": _time(self.valid_until),
            "freshness": self.freshness.value,
            "entry_reference": self.entry_reference.to_dict(),
            "stop_loss": self.stop_loss.to_dict(),
            "take_profit": self.take_profit.to_dict(),
            "state_before_address": self.state_before_address,
            "state_after_address": self.state_after_address,
            "provider_evidence_address": self.provider_evidence_address,
            "dataset_address": self.dataset_address,
            "reason_code": self.reason_code,
            "reason_evidence_address": self.reason_evidence_address,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        payload = _verified_payload(value, cls.schema, {
            "schema", "owner_id", "assignment_id", "monitoring_event_address",
            "strategy_id", "graph_version_address", "resolved_graph_address",
            "implementation_closure_address", "admission_address",
            "canonical_instrument_address", "display_symbol", "previous_state",
            "target_state", "action", "evaluation_event_address", "event_at",
            "latest_data_at", "knowledge_cutoff_at", "valid_until",
            "freshness", "entry_reference", "stop_loss", "take_profit", "state_before_address",
            "state_after_address", "provider_evidence_address", "dataset_address",
            "reason_code", "reason_evidence_address",
        })
        try:
            result = cls(
                owner_id=payload["owner_id"], assignment_id=payload["assignment_id"],
                monitoring_event_address=payload["monitoring_event_address"],
                strategy_id=payload["strategy_id"],
                graph_version_address=payload["graph_version_address"],
                resolved_graph_address=payload["resolved_graph_address"],
                implementation_closure_address=payload["implementation_closure_address"],
                admission_address=payload["admission_address"],
                canonical_instrument_address=payload["canonical_instrument_address"],
                display_symbol=payload["display_symbol"],
                previous_state=_enum(StrategyState, payload["previous_state"], "PREVIOUS_STATE"),
                target_state=_enum(StrategyState, payload["target_state"], "TARGET_STATE"),
                action=_enum(SignalAction, payload["action"], "SIGNAL_ACTION"),
                evaluation_event_address=payload["evaluation_event_address"],
                event_at=_parse_time(payload["event_at"], "EVENT_AT"),
                latest_data_at=_parse_time(payload["latest_data_at"], "LATEST_DATA_AT"),
                knowledge_cutoff_at=_parse_time(payload["knowledge_cutoff_at"], "KNOWLEDGE_CUTOFF_AT"),
                valid_until=_parse_time(payload["valid_until"], "VALID_UNTIL"),
                freshness=_enum(Freshness, payload["freshness"], "FRESHNESS"),
                entry_reference=EntryReference.from_dict(payload["entry_reference"]),
                stop_loss=ProtectionEvidence.from_dict(payload["stop_loss"]),
                take_profit=ProtectionEvidence.from_dict(payload["take_profit"]),
                state_before_address=payload["state_before_address"],
                state_after_address=payload["state_after_address"],
                provider_evidence_address=payload["provider_evidence_address"],
                dataset_address=payload["dataset_address"], reason_code=payload["reason_code"],
                reason_evidence_address=payload["reason_evidence_address"],
            )
        except KeyError as exc:
            raise MonitoringContractError("SIGNAL_ALERT_SCHEMA") from exc
        _verify_serialized_address(value, result.address)
        return result


@dataclass(frozen=True, slots=True)
class NoAlert:
    monitoring_event_address: str
    code: NoAlertCode

    schema: ClassVar[str] = "signal-alert-derivation-refusal/1"

    def __post_init__(self) -> None:
        _require_address(self.monitoring_event_address, "MONITORING_EVENT")
        _require_enum(self.code, NoAlertCode, "NO_ALERT_CODE")

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json({
            "schema": self.schema, "monitoring_event_address": self.monitoring_event_address,
            "code": self.code.value,
        }).encode("utf-8")


@dataclass(frozen=True, slots=True)
class AlertDerived:
    alert: SignalAlert
    schema: ClassVar[str] = "signal-alert-derived/1"

    def __post_init__(self) -> None:
        if not isinstance(self.alert, SignalAlert):
            raise MonitoringContractError("SIGNAL_ALERT_REQUIRED")


def _resolved_geometry_is_valid(
    action: SignalAction,
    previous_state: StrategyState,
    entry_reference: str | None,
    stop_loss: str | None,
    take_profit: str | None,
) -> bool:
    try:
        entry_value = Decimal(entry_reference)
        stop_value = Decimal(stop_loss)
        target_value = Decimal(take_profit)
    except (TypeError, ValueError):
        return False
    direction = (
        StrategyState.LONG if action is SignalAction.BUY
        else StrategyState.SHORT if action is SignalAction.SELL
        else previous_state
    )
    if direction is StrategyState.LONG:
        return stop_value < entry_value < target_value
    if direction is StrategyState.SHORT:
        return target_value < entry_value < stop_value
    return False


def derive_signal_alert(source: MonitoringSignalEvent) -> AlertDerived | NoAlert:
    if not isinstance(source, MonitoringSignalEvent):
        raise MonitoringContractError("MONITORING_SIGNAL_EVENT_REQUIRED")
    if source.evaluation_validity is FactValidity.REFUSED:
        return NoAlert(source.address, NoAlertCode.EVALUATION_REFUSED)
    if source.evaluation_validity is FactValidity.MISSING:
        return NoAlert(source.address, NoAlertCode.MISSING_DATA)
    if source.evaluation_validity is FactValidity.INVALID:
        return NoAlert(source.address, NoAlertCode.INVALID_DATA)
    if source.freshness is Freshness.STALE:
        return NoAlert(source.address, NoAlertCode.STALE_DATA)
    if source.action is SignalAction.HOLD:
        return NoAlert(source.address, NoAlertCode.HOLD)
    if source.repeated_target_state or source.previous_state is source.target_state:
        return NoAlert(source.address, NoAlertCode.REPEATED_TARGET_STATE)
    if source.entry_reference.validity is not FactValidity.VALID:
        return NoAlert(source.address, NoAlertCode.INVALID_ENTRY_REFERENCE)
    if source.stop_loss.validity is not FactValidity.VALID or source.take_profit.validity is not FactValidity.VALID:
        return NoAlert(source.address, NoAlertCode.INVALID_PROTECTION)
    expected = {
        SignalAction.BUY: (StrategyState.LONG, {StrategyState.FLAT, StrategyState.SHORT}),
        SignalAction.SELL: (StrategyState.SHORT, {StrategyState.FLAT, StrategyState.LONG}),
        SignalAction.EXIT: (StrategyState.FLAT, {StrategyState.LONG, StrategyState.SHORT}),
    }
    target, previous = expected[source.action]
    if source.target_state is not target or source.previous_state not in previous:
        return NoAlert(source.address, NoAlertCode.ACTION_STATE_MISMATCH)
    if not _resolved_geometry_is_valid(
        source.action, source.previous_state, source.entry_reference.value,
        source.stop_loss.resolved_value, source.take_profit.resolved_value,
    ):
        return NoAlert(source.address, NoAlertCode.INVALID_PROTECTION_GEOMETRY)
    alert = SignalAlert(
        owner_id=source.owner_id, assignment_id=source.assignment_id,
        monitoring_event_address=source.address, strategy_id=source.strategy_id,
        graph_version_address=source.graph_version_address,
        resolved_graph_address=source.resolved_graph_address,
        implementation_closure_address=source.implementation_closure_address,
        admission_address=source.admission_address,
        canonical_instrument_address=source.canonical_instrument_address,
        display_symbol=source.display_symbol, previous_state=source.previous_state,
        target_state=source.target_state, action=source.action,
        evaluation_event_address=source.evaluation_event_address,
        event_at=source.event_at, latest_data_at=source.latest_data_at,
        knowledge_cutoff_at=source.knowledge_cutoff_at, valid_until=source.valid_until,
        freshness=source.freshness,
        entry_reference=source.entry_reference, stop_loss=source.stop_loss,
        take_profit=source.take_profit, state_before_address=source.state_before_address,
        state_after_address=source.state_after_address,
        provider_evidence_address=source.provider_evidence_address,
        dataset_address=source.dataset_address, reason_code=source.reason_code,
        reason_evidence_address=source.reason_evidence_address,
    )
    return AlertDerived(alert)


@dataclass(frozen=True, slots=True)
class AlertDeliveryAttempt(_AddressedFact):
    owner_id: str
    assignment_id: str
    alert_address: str
    sequence: int
    channel: DeliveryChannel
    outcome: DeliveryOutcome
    occurred_at: datetime
    failure_code: str | None

    schema: ClassVar[str] = "alert-delivery-attempt/1"

    def __post_init__(self) -> None:
        _require_identifier(self.owner_id, "OWNER")
        _require_identifier(self.assignment_id, "ASSIGNMENT")
        _require_address(self.alert_address, "ALERT")
        if type(self.sequence) is not int or self.sequence < 1:
            raise MonitoringContractError("DELIVERY_SEQUENCE_REQUIRED")
        _require_enum(self.channel, DeliveryChannel, "DELIVERY_CHANNEL")
        _require_enum(self.outcome, DeliveryOutcome, "DELIVERY_OUTCOME")
        _require_utc(self.occurred_at, "DELIVERY_OCCURRED_AT")
        if self.outcome is DeliveryOutcome.FAILED:
            _require_code(self.failure_code, "DELIVERY_FAILURE")
        elif self.failure_code is not None:
            raise MonitoringContractError("DELIVERED_ATTEMPT_HAS_FAILURE")

    @property
    def attempt_id(self) -> str:
        return content_address({
            "schema": "alert-delivery-request/1", "owner_id": self.owner_id,
            "assignment_id": self.assignment_id, "alert_address": self.alert_address,
            "sequence": self.sequence, "channel": self.channel.value,
        })

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "attempt_id": self.attempt_id,
            "owner_id": self.owner_id, "assignment_id": self.assignment_id,
            "alert_address": self.alert_address, "sequence": self.sequence,
            "channel": self.channel.value, "outcome": self.outcome.value,
            "occurred_at": _time(self.occurred_at), "failure_code": self.failure_code,
        }

    @classmethod
    def create(cls, *, alert: SignalAlert, sequence: int, outcome: DeliveryOutcome,
               occurred_at: datetime, failure_code: str | None = None):
        if not isinstance(alert, SignalAlert):
            raise MonitoringContractError("SIGNAL_ALERT_REQUIRED")
        return cls(
            owner_id=alert.owner_id, assignment_id=alert.assignment_id,
            alert_address=alert.address, sequence=sequence, channel=DeliveryChannel.IN_APP,
            outcome=outcome, occurred_at=occurred_at, failure_code=failure_code,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        payload = _verified_payload(value, cls.schema, {
            "schema", "attempt_id", "owner_id", "assignment_id", "alert_address",
            "sequence", "channel", "outcome", "occurred_at", "failure_code",
        })
        try:
            result = cls(
                owner_id=payload["owner_id"], assignment_id=payload["assignment_id"],
                alert_address=payload["alert_address"], sequence=payload["sequence"],
                channel=_enum(DeliveryChannel, payload["channel"], "DELIVERY_CHANNEL"),
                outcome=_enum(DeliveryOutcome, payload["outcome"], "DELIVERY_OUTCOME"),
                occurred_at=_parse_time(payload["occurred_at"], "DELIVERY_OCCURRED_AT"),
                failure_code=payload["failure_code"],
            )
            if payload["attempt_id"] != result.attempt_id:
                raise MonitoringContractError("DELIVERY_ATTEMPT_IDENTITY_MISMATCH")
        except KeyError as exc:
            raise MonitoringContractError("DELIVERY_ATTEMPT_SCHEMA") from exc
        _verify_serialized_address(value, result.address)
        return result


def validate_delivery_attempts(
    alert: SignalAlert, attempts: Iterable[AlertDeliveryAttempt],
) -> tuple[AlertDeliveryAttempt, ...]:
    if not isinstance(alert, SignalAlert):
        raise MonitoringContractError("SIGNAL_ALERT_REQUIRED")
    unique: dict[str, AlertDeliveryAttempt] = {}
    for attempt in attempts:
        if not isinstance(attempt, AlertDeliveryAttempt):
            raise MonitoringContractError("DELIVERY_ATTEMPT_REQUIRED")
        if (attempt.owner_id, attempt.assignment_id, attempt.alert_address) != (
            alert.owner_id, alert.assignment_id, alert.address,
        ):
            raise MonitoringContractError("DELIVERY_ATTEMPT_SCOPE_MISMATCH")
        existing = unique.get(attempt.attempt_id)
        if existing is not None and existing != attempt:
            raise MonitoringContractError("DUPLICATE_ATTEMPT_CONFLICT")
        unique[attempt.attempt_id] = attempt
    ordered = tuple(sorted(unique.values(), key=lambda fact: fact.sequence))
    previous_time = alert.event_at
    for expected_sequence, attempt in enumerate(ordered, 1):
        if attempt.sequence != expected_sequence:
            raise MonitoringContractError("DELIVERY_SEQUENCE_GAP")
        if attempt.occurred_at < previous_time:
            raise MonitoringContractError("DELIVERY_TIME_NOT_MONOTONIC")
        previous_time = attempt.occurred_at
    return ordered


@dataclass(frozen=True, slots=True)
class AlertAttentionEvent(_AddressedFact):
    owner_id: str
    assignment_id: str
    alert_address: str
    sequence: int
    action: AttentionAction
    occurred_at: datetime

    schema: ClassVar[str] = "alert-attention-event/1"

    def __post_init__(self) -> None:
        _require_identifier(self.owner_id, "OWNER")
        _require_identifier(self.assignment_id, "ASSIGNMENT")
        _require_address(self.alert_address, "ALERT")
        if type(self.sequence) is not int or self.sequence < 1:
            raise MonitoringContractError("ATTENTION_SEQUENCE_REQUIRED")
        _require_enum(self.action, AttentionAction, "ATTENTION_ACTION")
        _require_utc(self.occurred_at, "ATTENTION_OCCURRED_AT")

    @property
    def request_id(self) -> str:
        return content_address({
            "schema": "alert-attention-request/1", "owner_id": self.owner_id,
            "assignment_id": self.assignment_id, "alert_address": self.alert_address,
            "sequence": self.sequence, "action": self.action.value,
        })

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "request_id": self.request_id,
            "owner_id": self.owner_id, "assignment_id": self.assignment_id,
            "alert_address": self.alert_address, "sequence": self.sequence,
            "action": self.action.value, "occurred_at": _time(self.occurred_at),
        }

    @classmethod
    def create(cls, *, alert: SignalAlert, sequence: int, action: AttentionAction,
               occurred_at: datetime):
        if not isinstance(alert, SignalAlert):
            raise MonitoringContractError("SIGNAL_ALERT_REQUIRED")
        return cls(
            owner_id=alert.owner_id, assignment_id=alert.assignment_id,
            alert_address=alert.address, sequence=sequence, action=action,
            occurred_at=occurred_at,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        payload = _verified_payload(value, cls.schema, {
            "schema", "request_id", "owner_id", "assignment_id", "alert_address",
            "sequence", "action", "occurred_at",
        })
        try:
            result = cls(
                owner_id=payload["owner_id"], assignment_id=payload["assignment_id"],
                alert_address=payload["alert_address"], sequence=payload["sequence"],
                action=_enum(AttentionAction, payload["action"], "ATTENTION_ACTION"),
                occurred_at=_parse_time(payload["occurred_at"], "ATTENTION_OCCURRED_AT"),
            )
            if payload["request_id"] != result.request_id:
                raise MonitoringContractError("ATTENTION_REQUEST_IDENTITY_MISMATCH")
        except KeyError as exc:
            raise MonitoringContractError("ATTENTION_EVENT_SCHEMA") from exc
        _verify_serialized_address(value, result.address)
        return result


@dataclass(frozen=True, slots=True)
class AlertAttentionProjection(_AddressedFact):
    owner_id: str
    assignment_id: str
    alert_address: str
    alert_event_at: datetime
    alert_valid_until: datetime
    last_sequence: int
    is_unread: bool
    read_at: datetime | None
    acknowledged_at: datetime | None
    dismissed_at: datetime | None

    schema: ClassVar[str] = "alert-attention-projection/1"

    def __post_init__(self) -> None:
        _require_identifier(self.owner_id, "OWNER")
        _require_identifier(self.assignment_id, "ASSIGNMENT")
        _require_address(self.alert_address, "ALERT")
        _require_utc(self.alert_event_at, "ALERT_EVENT_AT")
        _require_utc(self.alert_valid_until, "ALERT_VALID_UNTIL")
        if self.alert_valid_until < self.alert_event_at:
            raise MonitoringContractError("PROJECTION_ALERT_TIME_NOT_MONOTONIC")
        if type(self.last_sequence) is not int or self.last_sequence < 0:
            raise MonitoringContractError("PROJECTION_SEQUENCE_REQUIRED")
        if type(self.is_unread) is not bool:
            raise MonitoringContractError("PROJECTION_UNREAD_BOOLEAN_REQUIRED")
        for label, value in (
            ("READ_AT", self.read_at), ("ACKNOWLEDGED_AT", self.acknowledged_at),
            ("DISMISSED_AT", self.dismissed_at),
        ):
            if value is not None:
                _require_utc(value, label)
                if value < self.alert_event_at:
                    raise MonitoringContractError(f"{label}_BEFORE_ALERT")
        if self.last_sequence == 0 and (
            not self.is_unread or any(value is not None for value in (
                self.read_at, self.acknowledged_at, self.dismissed_at,
            ))
        ):
            raise MonitoringContractError("INITIAL_ATTENTION_STATE_INVALID")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "owner_id": self.owner_id,
            "assignment_id": self.assignment_id, "alert_address": self.alert_address,
            "alert_event_at": _time(self.alert_event_at),
            "alert_valid_until": _time(self.alert_valid_until),
            "last_sequence": self.last_sequence, "is_unread": self.is_unread,
            "read_at": _time(self.read_at) if self.read_at is not None else None,
            "acknowledged_at": _time(self.acknowledged_at) if self.acknowledged_at is not None else None,
            "dismissed_at": _time(self.dismissed_at) if self.dismissed_at is not None else None,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        payload = _verified_payload(value, cls.schema, {
            "schema", "owner_id", "assignment_id", "alert_address",
            "alert_event_at", "alert_valid_until", "last_sequence", "is_unread",
            "read_at", "acknowledged_at", "dismissed_at",
        })
        try:
            result = cls(
                owner_id=payload["owner_id"], assignment_id=payload["assignment_id"],
                alert_address=payload["alert_address"],
                alert_event_at=_parse_time(payload["alert_event_at"], "ALERT_EVENT_AT"),
                alert_valid_until=_parse_time(payload["alert_valid_until"], "ALERT_VALID_UNTIL"),
                last_sequence=payload["last_sequence"], is_unread=payload["is_unread"],
                read_at=_optional_time(payload["read_at"], "READ_AT"),
                acknowledged_at=_optional_time(payload["acknowledged_at"], "ACKNOWLEDGED_AT"),
                dismissed_at=_optional_time(payload["dismissed_at"], "DISMISSED_AT"),
            )
        except KeyError as exc:
            raise MonitoringContractError("ATTENTION_PROJECTION_SCHEMA") from exc
        _verify_serialized_address(value, result.address)
        return result


def rebuild_attention_projection(
    alert: SignalAlert, events: Iterable[AlertAttentionEvent],
) -> AlertAttentionProjection:
    if not isinstance(alert, SignalAlert):
        raise MonitoringContractError("SIGNAL_ALERT_REQUIRED")
    unique: dict[str, AlertAttentionEvent] = {}
    for event in events:
        if not isinstance(event, AlertAttentionEvent):
            raise MonitoringContractError("ATTENTION_EVENT_REQUIRED")
        if (event.owner_id, event.assignment_id, event.alert_address) != (
            alert.owner_id, alert.assignment_id, alert.address,
        ):
            raise MonitoringContractError("ATTENTION_EVENT_SCOPE_MISMATCH")
        existing = unique.get(event.request_id)
        if existing is not None and existing != event:
            raise MonitoringContractError("DUPLICATE_ATTENTION_REQUEST_CONFLICT")
        unique[event.request_id] = event
    ordered = tuple(sorted(unique.values(), key=lambda fact: fact.sequence))
    read_at = acknowledged_at = dismissed_at = None
    previous_time = alert.event_at
    for expected_sequence, event in enumerate(ordered, 1):
        if event.sequence != expected_sequence:
            raise MonitoringContractError("ATTENTION_SEQUENCE_GAP")
        if event.occurred_at < previous_time:
            raise MonitoringContractError("ATTENTION_TIME_NOT_MONOTONIC")
        previous_time = event.occurred_at
        if event.action is AttentionAction.READ and read_at is None:
            read_at = event.occurred_at
        elif event.action is AttentionAction.ACKNOWLEDGE and acknowledged_at is None:
            acknowledged_at = event.occurred_at
        elif event.action is AttentionAction.DISMISS and dismissed_at is None:
            dismissed_at = event.occurred_at
    return AlertAttentionProjection(
        owner_id=alert.owner_id, assignment_id=alert.assignment_id,
        alert_address=alert.address, alert_event_at=alert.event_at,
        alert_valid_until=alert.valid_until, last_sequence=len(ordered),
        is_unread=not ordered, read_at=read_at, acknowledged_at=acknowledged_at,
        dismissed_at=dismissed_at,
    )


def _verified_payload(value: Any, schema: str, expected: set[str]) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema") != schema
        or set(value) != expected | {"address"}
    ):
        raise MonitoringContractError("SERIALIZED_FACT_SCHEMA")
    return {key: item for key, item in value.items() if key != "address"}


def _verify_serialized_address(value: dict[str, Any], actual: str) -> None:
    if value["address"] != actual:
        raise MonitoringContractError("SERIALIZED_FACT_ADDRESS_MISMATCH")


def _optional_time(value: Any, label: str) -> datetime | None:
    return None if value is None else _parse_time(value, label)


__all__ = [
    "AlertAttentionEvent", "AlertAttentionProjection", "AlertDeliveryAttempt",
    "AlertDerived", "AttentionAction", "DeliveryChannel", "DeliveryOutcome",
    "EntryReference", "EntryReferenceKind", "FactValidity", "Freshness",
    "MonitoringContractError", "MonitoringSignalEvent", "NoAlert", "NoAlertCode",
    "ProtectionBasis", "ProtectionEvidence", "ProtectionKind", "ProtectionUnits",
    "SignalAction", "SignalAlert", "StrategyState", "derive_signal_alert",
    "rebuild_attention_projection", "validate_delivery_attempts",
]
