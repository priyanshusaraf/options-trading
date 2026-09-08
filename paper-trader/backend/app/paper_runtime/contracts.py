"""Closed, content-addressed contracts for the local V0 paper runtime.

These facts grant no live or provider authority.  They carry caller-resolved paper
authority into one deterministic command and keep every upstream address intact.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, ClassVar

from app.ir.hashing import canonical_json, content_address
from app.monitoring.contracts import (
    FactValidity,
    Freshness,
    MonitoringSignalEvent,
    SignalAction,
    StrategyState,
)


_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_INTENT = re.compile(r"^[0-9a-f]{32}$")
_CANONICAL_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9]|\.0)?$")


class PaperRuntimeRefusal(ValueError):
    """A runtime fact or effect cannot be proved safe and exact."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EffectPreference(Enum):
    ALERTS = "ALERTS"
    PAPER = "PAPER"
    BOTH = "BOTH"


class AssignmentLifecycle(Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    WITHDRAWN = "WITHDRAWN"


class PaperAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"


class BranchStatus(Enum):
    NOT_SELECTED = "NOT_SELECTED"
    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    NO_EFFECT = "NO_EFFECT"
    REFUSED = "REFUSED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


def _require_address(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise PaperRuntimeRefusal(f"{label}_CONTENT_ADDRESS_REQUIRED")


def _require_identifier(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise PaperRuntimeRefusal(f"{label}_IDENTIFIER_REQUIRED")


def _require_utc(value: Any, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is not dt.timezone.utc:
        raise PaperRuntimeRefusal(f"{label}_UTC_REQUIRED")


def _positive_decimal(value: Any, label: str) -> Decimal:
    if not isinstance(value, str) or not _CANONICAL_DECIMAL.fullmatch(value):
        raise PaperRuntimeRefusal(f"{label}_CANONICAL_REQUIRED")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise PaperRuntimeRefusal(f"{label}_CANONICAL_REQUIRED") from exc
    if not result.is_finite() or result <= 0:
        raise PaperRuntimeRefusal(f"{label}_CANONICAL_REQUIRED")
    return result


def _time(value: dt.datetime) -> str:
    _require_utc(value, "TIME")
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_time(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise PaperRuntimeRefusal(f"{label}_UTC_REQUIRED")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise PaperRuntimeRefusal(f"{label}_UTC_REQUIRED") from exc
    if _time(parsed) != value:
        raise PaperRuntimeRefusal(f"{label}_UTC_REQUIRED")
    return parsed


def _enum(kind: type[Enum], value: Any, label: str):
    try:
        return kind(value)
    except (TypeError, ValueError) as exc:
        raise PaperRuntimeRefusal(f"{label}_CLOSED_VALUE_REQUIRED") from exc


class _Addressed:
    schema: ClassVar[str]

    def canonical_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def address(self) -> str:
        return content_address(self.canonical_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_payload(), "address": self.address}


def _payload(value: Any, schema: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) not in (fields, fields | {"address"}):
        raise PaperRuntimeRefusal(f"{schema.upper().replace('-', '_').replace('/', '_')}_SCHEMA")
    if value.get("schema") != schema:
        raise PaperRuntimeRefusal(f"{schema.upper().replace('-', '_').replace('/', '_')}_SCHEMA")
    return {key: value[key] for key in fields}


def _verify_address(serialized: dict[str, Any], fact: _Addressed) -> None:
    if "address" in serialized and serialized["address"] != fact.address:
        raise PaperRuntimeRefusal("SERIALIZED_ADDRESS_MISMATCH")


@dataclass(frozen=True, slots=True)
class PaperInstrumentAuthority(_Addressed):
    owner_id: str
    monitoring_assignment_id: str
    deployment_id: int
    broker_account_id: str
    instrument_key: str
    strategy_key: str
    strategy_version: str
    graph_address: str
    attribution_state: str
    canonical_instrument_address: str
    admission_address: str
    candidate_intent_id: str
    candidate_address: str
    decision_id: str
    decision_address: str
    reservation_id: str
    reservation_address: str
    approved_quantity: int
    required_capital: str
    charge_segment: str
    paper_book_address: str
    fence_epoch: int
    valid_from: dt.datetime
    valid_until: dt.datetime

    schema: ClassVar[str] = "paper-instrument-authority/1"

    def __post_init__(self) -> None:
        for label, value in (("OWNER", self.owner_id), ("MONITORING_ASSIGNMENT", self.monitoring_assignment_id),
                             ("BROKER_ACCOUNT", self.broker_account_id), ("INSTRUMENT", self.instrument_key),
                             ("STRATEGY", self.strategy_key), ("STRATEGY_VERSION", self.strategy_version),
                             ("ATTRIBUTION_STATE", self.attribution_state),
                             ("CHARGE_SEGMENT", self.charge_segment),
                             ("CANDIDATE_INTENT", self.candidate_intent_id),
                             ("CAPITAL_DECISION", self.decision_id),
                             ("CAPITAL_RESERVATION", self.reservation_id)):
            _require_identifier(value, label)
        for label, value in (("CANONICAL_INSTRUMENT", self.canonical_instrument_address),
                             ("ADMISSION", self.admission_address), ("GRAPH", self.graph_address),
                             ("CANDIDATE", self.candidate_address),
                             ("CAPITAL_DECISION", self.decision_address),
                             ("CAPITAL_RESERVATION", self.reservation_address),
                             ("PAPER_BOOK", self.paper_book_address)):
            _require_address(value, label)
        if type(self.deployment_id) is not int or self.deployment_id < 1:
            raise PaperRuntimeRefusal("DEPLOYMENT_ID_REQUIRED")
        if type(self.approved_quantity) is not int or self.approved_quantity < 1:
            raise PaperRuntimeRefusal("APPROVED_QUANTITY_REQUIRED")
        if type(self.fence_epoch) is not int or self.fence_epoch < 1:
            raise PaperRuntimeRefusal("FENCE_EPOCH_REQUIRED")
        _positive_decimal(self.required_capital, "REQUIRED_CAPITAL")
        _require_utc(self.valid_from, "AUTHORITY_VALID_FROM")
        _require_utc(self.valid_until, "AUTHORITY_VALID_UNTIL")
        if self.valid_from >= self.valid_until:
            raise PaperRuntimeRefusal("AUTHORITY_WINDOW_INVALID")

    def canonical_payload(self) -> dict[str, Any]:
        return {"schema": self.schema, "owner_id": self.owner_id,
                "monitoring_assignment_id": self.monitoring_assignment_id,
                "deployment_id": self.deployment_id, "broker_account_id": self.broker_account_id,
                "instrument_key": self.instrument_key, "strategy_key": self.strategy_key,
                "strategy_version": self.strategy_version, "graph_address": self.graph_address,
                "attribution_state": self.attribution_state,
                "canonical_instrument_address": self.canonical_instrument_address,
                "admission_address": self.admission_address,
                "candidate_intent_id": self.candidate_intent_id,
                "candidate_address": self.candidate_address,
                "decision_id": self.decision_id, "decision_address": self.decision_address,
                "reservation_id": self.reservation_id,
                "reservation_address": self.reservation_address,
                "approved_quantity": self.approved_quantity,
                "required_capital": self.required_capital, "charge_segment": self.charge_segment,
                "paper_book_address": self.paper_book_address, "fence_epoch": self.fence_epoch,
                "valid_from": _time(self.valid_from), "valid_until": _time(self.valid_until)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        fields = {"schema", "owner_id", "monitoring_assignment_id", "deployment_id",
                  "broker_account_id", "instrument_key", "canonical_instrument_address",
                  "strategy_key", "strategy_version", "graph_address", "attribution_state",
                  "admission_address", "candidate_intent_id", "candidate_address",
                  "decision_id", "decision_address", "reservation_id", "reservation_address",
                  "approved_quantity", "required_capital", "charge_segment",
                  "paper_book_address", "fence_epoch", "valid_from", "valid_until"}
        p = _payload(value, cls.schema, fields)
        values = {key: item for key, item in p.items() if key != "schema"}
        fact = cls(**{**values, "valid_from": _parse_time(p["valid_from"], "AUTHORITY_VALID_FROM"),
                      "valid_until": _parse_time(p["valid_until"], "AUTHORITY_VALID_UNTIL")})
        _verify_address(value, fact)
        return fact


@dataclass(frozen=True, slots=True)
class RuntimeAssignment(_Addressed):
    owner_id: str
    monitoring_assignment_id: str
    preference: EffectPreference
    lifecycle: AssignmentLifecycle
    deployment_id: int
    graph_version_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    instrument_authority_address: str
    effective_from: dt.datetime
    valid_until: dt.datetime

    schema: ClassVar[str] = "paper-runtime-assignment/1"

    def __post_init__(self) -> None:
        _require_identifier(self.owner_id, "OWNER")
        _require_identifier(self.monitoring_assignment_id, "MONITORING_ASSIGNMENT")
        if type(self.preference) is not EffectPreference:
            raise PaperRuntimeRefusal("EFFECT_PREFERENCE_CLOSED_VALUE_REQUIRED")
        if type(self.lifecycle) is not AssignmentLifecycle:
            raise PaperRuntimeRefusal("ASSIGNMENT_LIFECYCLE_CLOSED_VALUE_REQUIRED")
        if type(self.deployment_id) is not int or self.deployment_id < 1:
            raise PaperRuntimeRefusal("DEPLOYMENT_ID_REQUIRED")
        for label, value in (("GRAPH_VERSION", self.graph_version_address),
                             ("RESOLVED_GRAPH", self.resolved_graph_address),
                             ("IMPLEMENTATION_CLOSURE", self.implementation_closure_address),
                             ("INSTRUMENT_AUTHORITY", self.instrument_authority_address)):
            _require_address(value, label)
        _require_utc(self.effective_from, "ASSIGNMENT_EFFECTIVE_FROM")
        _require_utc(self.valid_until, "ASSIGNMENT_VALID_UNTIL")
        if self.effective_from >= self.valid_until:
            raise PaperRuntimeRefusal("ASSIGNMENT_WINDOW_INVALID")

    def canonical_payload(self) -> dict[str, Any]:
        return {"schema": self.schema, "owner_id": self.owner_id,
                "monitoring_assignment_id": self.monitoring_assignment_id,
                "preference": self.preference.value, "lifecycle": self.lifecycle.value,
                "deployment_id": self.deployment_id,
                "graph_version_address": self.graph_version_address,
                "resolved_graph_address": self.resolved_graph_address,
                "implementation_closure_address": self.implementation_closure_address,
                "instrument_authority_address": self.instrument_authority_address,
                "effective_from": _time(self.effective_from), "valid_until": _time(self.valid_until)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        fields = {"schema", "owner_id", "monitoring_assignment_id", "preference", "lifecycle",
                  "deployment_id", "graph_version_address", "resolved_graph_address",
                  "implementation_closure_address", "instrument_authority_address",
                  "effective_from", "valid_until"}
        p = _payload(value, cls.schema, fields)
        values = {key: item for key, item in p.items() if key != "schema"}
        fact = cls(**{**values, "preference": _enum(EffectPreference, p["preference"], "EFFECT_PREFERENCE"),
                      "lifecycle": _enum(AssignmentLifecycle, p["lifecycle"], "ASSIGNMENT_LIFECYCLE"),
                      "effective_from": _parse_time(p["effective_from"], "ASSIGNMENT_EFFECTIVE_FROM"),
                      "valid_until": _parse_time(p["valid_until"], "ASSIGNMENT_VALID_UNTIL")})
        _verify_address(value, fact)
        return fact


def deterministic_client_intent_id(assignment_address: str, event_address: str,
                                   action: PaperAction) -> str:
    _require_address(assignment_address, "RUNTIME_ASSIGNMENT")
    _require_address(event_address, "MONITORING_EVENT")
    if type(action) is not PaperAction:
        raise PaperRuntimeRefusal("PAPER_ACTION_CLOSED_VALUE_REQUIRED")
    payload = canonical_json({"domain": "strategy-os-paper-runtime-intent/1",
                              "runtime_assignment_address": assignment_address,
                              "monitoring_event_address": event_address,
                              "action": action.value}).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=16).hexdigest()


def paper_book_scope_address(owner_id: str, broker_account_id: str) -> str:
    _require_identifier(owner_id, "OWNER")
    _require_identifier(broker_account_id, "BROKER_ACCOUNT")
    return content_address({
        "schema": "strategy-os.paper-book-scope/v1",
        "owner_id": owner_id,
        "broker_account_id": broker_account_id,
        "book": "paper",
        "currency": "INR",
    })


@dataclass(frozen=True, slots=True)
class PaperCommand(_Addressed):
    owner_id: str
    deployment_id: int
    instrument_key: str
    runtime_assignment_address: str
    instrument_authority_address: str
    monitoring_event_address: str
    action: PaperAction
    client_intent_id: str
    approved_quantity: int
    entry_reference: str | None
    stop_loss: str | None
    take_profit: str | None
    graph_version_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    canonical_instrument_address: str
    admission_address: str
    capital_decision_address: str
    capital_reservation_address: str
    paper_book_address: str
    evaluation_event_address: str
    event_at: dt.datetime
    valid_until: dt.datetime

    schema: ClassVar[str] = "paper-command/1"

    def __post_init__(self) -> None:
        _require_identifier(self.owner_id, "OWNER")
        _require_identifier(self.instrument_key, "INSTRUMENT")
        if type(self.deployment_id) is not int or self.deployment_id < 1:
            raise PaperRuntimeRefusal("DEPLOYMENT_ID_REQUIRED")
        if type(self.action) is not PaperAction:
            raise PaperRuntimeRefusal("PAPER_ACTION_CLOSED_VALUE_REQUIRED")
        if not isinstance(self.client_intent_id, str) or not _INTENT.fullmatch(self.client_intent_id):
            raise PaperRuntimeRefusal("CLIENT_INTENT_ID_REQUIRED")
        if type(self.approved_quantity) is not int or self.approved_quantity < 0:
            raise PaperRuntimeRefusal("APPROVED_QUANTITY_REQUIRED")
        for label, value in (("RUNTIME_ASSIGNMENT", self.runtime_assignment_address),
                             ("INSTRUMENT_AUTHORITY", self.instrument_authority_address),
                             ("MONITORING_EVENT", self.monitoring_event_address),
                             ("GRAPH_VERSION", self.graph_version_address),
                             ("RESOLVED_GRAPH", self.resolved_graph_address),
                             ("IMPLEMENTATION_CLOSURE", self.implementation_closure_address),
                             ("CANONICAL_INSTRUMENT", self.canonical_instrument_address),
                             ("ADMISSION", self.admission_address),
                             ("CAPITAL_DECISION", self.capital_decision_address),
                             ("CAPITAL_RESERVATION", self.capital_reservation_address),
                             ("PAPER_BOOK", self.paper_book_address),
                             ("EVALUATION_EVENT", self.evaluation_event_address)):
            _require_address(value, label)
        expected = deterministic_client_intent_id(
            self.runtime_assignment_address, self.monitoring_event_address, self.action)
        if expected != self.client_intent_id:
            raise PaperRuntimeRefusal("CLIENT_INTENT_ID_MISMATCH")
        if self.action is PaperAction.HOLD:
            if self.approved_quantity != 0 or any(v is not None for v in (
                    self.entry_reference, self.stop_loss, self.take_profit)):
                raise PaperRuntimeRefusal("HOLD_MUST_HAVE_NO_EFFECT")
        else:
            if self.approved_quantity < 1:
                raise PaperRuntimeRefusal("APPROVED_QUANTITY_REQUIRED")
            for label, value in (("ENTRY_REFERENCE", self.entry_reference),
                                 ("STOP_LOSS", self.stop_loss), ("TAKE_PROFIT", self.take_profit)):
                _positive_decimal(value, label)
        _require_utc(self.event_at, "EVENT_AT")
        _require_utc(self.valid_until, "VALID_UNTIL")

    def canonical_payload(self) -> dict[str, Any]:
        return {"schema": self.schema, "owner_id": self.owner_id,
                "deployment_id": self.deployment_id, "instrument_key": self.instrument_key,
                "runtime_assignment_address": self.runtime_assignment_address,
                "instrument_authority_address": self.instrument_authority_address,
                "monitoring_event_address": self.monitoring_event_address,
                "action": self.action.value, "client_intent_id": self.client_intent_id,
                "approved_quantity": self.approved_quantity,
                "entry_reference": self.entry_reference, "stop_loss": self.stop_loss,
                "take_profit": self.take_profit, "graph_version_address": self.graph_version_address,
                "resolved_graph_address": self.resolved_graph_address,
                "implementation_closure_address": self.implementation_closure_address,
                "canonical_instrument_address": self.canonical_instrument_address,
                "admission_address": self.admission_address,
                "capital_decision_address": self.capital_decision_address,
                "capital_reservation_address": self.capital_reservation_address,
                "paper_book_address": self.paper_book_address,
                "evaluation_event_address": self.evaluation_event_address,
                "event_at": _time(self.event_at), "valid_until": _time(self.valid_until)}

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, assignment: RuntimeAssignment,
                  authority: PaperInstrumentAuthority, event: MonitoringSignalEvent):
        fields = {"schema", "owner_id", "deployment_id", "instrument_key",
                  "runtime_assignment_address", "instrument_authority_address",
                  "monitoring_event_address", "action", "client_intent_id",
                  "approved_quantity", "entry_reference", "stop_loss", "take_profit",
                  "graph_version_address", "resolved_graph_address",
                  "implementation_closure_address", "canonical_instrument_address",
                  "admission_address", "capital_decision_address",
                  "capital_reservation_address", "paper_book_address",
                  "evaluation_event_address", "event_at", "valid_until"}
        p = _payload(value, cls.schema, fields)
        values = {key: item for key, item in p.items() if key != "schema"}
        fact = cls(**{**values, "action": _enum(PaperAction, p["action"], "PAPER_ACTION"),
                      "event_at": _parse_time(p["event_at"], "EVENT_AT"),
                      "valid_until": _parse_time(p["valid_until"], "VALID_UNTIL")})
        _verify_address(value, fact)
        validate_runtime_relations(assignment, authority, event, fact)
        return fact


def validate_runtime_relations(
        assignment: RuntimeAssignment, authority: PaperInstrumentAuthority,
        event: MonitoringSignalEvent, command: PaperCommand, *,
        broker_owner_id: str | None = None, broker_account_id: str | None = None,
        broker_deployment_id: int | None = None, broker_fence_epoch: int | None = None) -> None:
    """Validate the one closed relation across every paper-runtime source fact.

    Addresses authenticate bytes, not copied fields. Every use site supplies the
    exact source facts again so a real authority address cannot bless a modified
    command or context.
    """
    if (type(assignment) is not RuntimeAssignment
            or type(authority) is not PaperInstrumentAuthority
            or type(event) is not MonitoringSignalEvent
            or type(command) is not PaperCommand):
        raise PaperRuntimeRefusal("RUNTIME_SOURCE_FACTS_REQUIRED")
    action = PaperAction(event.action.value)
    expected_state = {PaperAction.BUY: StrategyState.LONG,
                      PaperAction.SELL: StrategyState.SHORT,
                      PaperAction.EXIT: StrategyState.FLAT}.get(action)
    prices = (event.entry_reference.value, event.stop_loss.resolved_value,
              event.take_profit.resolved_value)
    expected_prices = (None, None, None) if action is PaperAction.HOLD else prices
    expected_quantity = 0 if action is PaperAction.HOLD else authority.approved_quantity
    exact = (
        assignment.owner_id == authority.owner_id == event.owner_id == command.owner_id
        and assignment.monitoring_assignment_id
            == authority.monitoring_assignment_id == event.assignment_id
        and assignment.deployment_id == authority.deployment_id == command.deployment_id
        and assignment.instrument_authority_address == authority.address
        and command.runtime_assignment_address == assignment.address
        and command.instrument_authority_address == authority.address
        and command.monitoring_event_address == event.address
        and command.action is action
        and command.client_intent_id == deterministic_client_intent_id(
            assignment.address, event.address, action)
        and command.instrument_key == authority.instrument_key
        and command.approved_quantity == expected_quantity
        and (command.entry_reference, command.stop_loss, command.take_profit) == expected_prices
        and assignment.graph_version_address
            == event.graph_version_address == command.graph_version_address
        and authority.graph_address == event.graph_version_address
        and assignment.resolved_graph_address
            == event.resolved_graph_address == command.resolved_graph_address
        and assignment.implementation_closure_address
            == event.implementation_closure_address
            == command.implementation_closure_address
        and authority.canonical_instrument_address
            == event.canonical_instrument_address
            == command.canonical_instrument_address
        and authority.admission_address == event.admission_address == command.admission_address
        and authority.strategy_key == event.strategy_id
        and authority.decision_address == command.capital_decision_address
        and authority.reservation_address == command.capital_reservation_address
        and authority.paper_book_address == command.paper_book_address
        and event.evaluation_event_address == command.evaluation_event_address
        and event.event_at == command.event_at
        and event.valid_until == command.valid_until
        and event.evaluation_validity is FactValidity.VALID
        and event.freshness is Freshness.FRESH
        and assignment.effective_from <= event.event_at <= assignment.valid_until
        and authority.valid_from <= event.event_at <= authority.valid_until
        and (expected_state is None or event.target_state is expected_state)
        and (assignment.lifecycle is AssignmentLifecycle.ACTIVE
             or action is PaperAction.EXIT)
    )
    if not exact:
        raise PaperRuntimeRefusal("RUNTIME_SOURCE_RELATION_MISMATCH")
    broker_values = (broker_owner_id, broker_account_id,
                     broker_deployment_id, broker_fence_epoch)
    if any(value is not None for value in broker_values) and (
            broker_owner_id != authority.owner_id
            or broker_account_id != authority.broker_account_id
            or broker_deployment_id != authority.deployment_id
            or broker_fence_epoch != authority.fence_epoch):
        raise PaperRuntimeRefusal("RUNTIME_BROKER_RELATION_MISMATCH")


def plan_paper_command(assignment: RuntimeAssignment, authority: PaperInstrumentAuthority,
                       event: MonitoringSignalEvent, *, now: dt.datetime) -> PaperCommand:
    _require_utc(now, "USE_TIME")
    action = PaperAction(event.action.value)
    if assignment.lifecycle is not AssignmentLifecycle.ACTIVE and action is not PaperAction.EXIT:
        raise PaperRuntimeRefusal("RUNTIME_ASSIGNMENT_NOT_ACTIVE_FOR_ENTRY")
    if not assignment.effective_from <= event.event_at <= assignment.valid_until:
        raise PaperRuntimeRefusal("RUNTIME_ASSIGNMENT_TIME_MISMATCH")
    if not authority.valid_from <= event.event_at <= authority.valid_until:
        raise PaperRuntimeRefusal("INSTRUMENT_AUTHORITY_TIME_MISMATCH")
    if event.event_at > now:
        raise PaperRuntimeRefusal("MONITORING_EVENT_IN_FUTURE")
    if now < assignment.effective_from or now < authority.valid_from:
        raise PaperRuntimeRefusal("RUNTIME_AUTHORITY_NOT_YET_EFFECTIVE")
    if now > assignment.valid_until or now > authority.valid_until:
        raise PaperRuntimeRefusal("RUNTIME_AUTHORITY_EXPIRED")
    if now > event.valid_until:
        raise PaperRuntimeRefusal("MONITORING_EVENT_EXPIRED")
    if event.evaluation_validity is not FactValidity.VALID:
        raise PaperRuntimeRefusal("MONITORING_EVENT_INVALID")
    if event.freshness is not Freshness.FRESH:
        raise PaperRuntimeRefusal("MONITORING_EVENT_STALE")
    exact = (
        assignment.owner_id == authority.owner_id == event.owner_id
        and assignment.monitoring_assignment_id == authority.monitoring_assignment_id == event.assignment_id
        and assignment.deployment_id == authority.deployment_id
        and assignment.instrument_authority_address == authority.address
        and assignment.graph_version_address == event.graph_version_address
        and assignment.resolved_graph_address == event.resolved_graph_address
        and assignment.implementation_closure_address == event.implementation_closure_address
        and authority.canonical_instrument_address == event.canonical_instrument_address
        and authority.admission_address == event.admission_address
        and authority.strategy_key == event.strategy_id
        and authority.graph_address == event.graph_version_address
    )
    if not exact:
        raise PaperRuntimeRefusal("RUNTIME_AUTHORITY_MISMATCH")
    expected_state = {PaperAction.BUY: StrategyState.LONG, PaperAction.SELL: StrategyState.SHORT,
                      PaperAction.EXIT: StrategyState.FLAT}.get(action)
    if expected_state is not None and event.target_state is not expected_state:
        raise PaperRuntimeRefusal("ACTION_STATE_MISMATCH")
    if action is PaperAction.HOLD:
        qty, entry, stop, target = 0, None, None, None
    else:
        if (event.entry_reference.validity is not FactValidity.VALID
                or event.stop_loss.validity is not FactValidity.VALID
                or event.take_profit.validity is not FactValidity.VALID):
            raise PaperRuntimeRefusal("PAPER_PRICE_EVIDENCE_INVALID")
        qty = authority.approved_quantity
        entry = event.entry_reference.value
        stop = event.stop_loss.resolved_value
        target = event.take_profit.resolved_value
    intent_id = deterministic_client_intent_id(assignment.address, event.address, action)
    command = PaperCommand(
        owner_id=event.owner_id, deployment_id=authority.deployment_id,
        instrument_key=authority.instrument_key, runtime_assignment_address=assignment.address,
        instrument_authority_address=authority.address, monitoring_event_address=event.address,
        action=action, client_intent_id=intent_id, approved_quantity=qty,
        entry_reference=entry, stop_loss=stop, take_profit=target,
        graph_version_address=event.graph_version_address,
        resolved_graph_address=event.resolved_graph_address,
        implementation_closure_address=event.implementation_closure_address,
        canonical_instrument_address=event.canonical_instrument_address,
        admission_address=event.admission_address,
        capital_decision_address=authority.decision_address,
        capital_reservation_address=authority.reservation_address,
        paper_book_address=authority.paper_book_address,
        evaluation_event_address=event.evaluation_event_address,
        event_at=event.event_at, valid_until=event.valid_until)
    validate_runtime_relations(assignment, authority, event, command)
    return command


def canonical_runtime_context(command: PaperCommand, assignment: RuntimeAssignment,
                              authority: PaperInstrumentAuthority,
                              event: MonitoringSignalEvent) -> str:
    """Canonical broker context retaining every runtime/source address in full."""
    validate_runtime_relations(assignment, authority, event, command)
    return canonical_json({
        "schema": "paper-runtime-context/1", "client_intent_id": command.client_intent_id,
        "action": command.action.value, "runtime_assignment_address": command.runtime_assignment_address,
        "instrument_authority_address": authority.address, "monitoring_event_address": event.address,
        "owner_id": command.owner_id, "deployment_id": command.deployment_id,
        "instrument_key": command.instrument_key, "approved_quantity": command.approved_quantity,
        "paper_command_address": command.address, "graph_version_address": command.graph_version_address,
        "resolved_graph_address": command.resolved_graph_address,
        "implementation_closure_address": command.implementation_closure_address,
        "canonical_instrument_address": command.canonical_instrument_address,
        "admission_address": command.admission_address,
        "capital_decision_address": command.capital_decision_address,
        "capital_reservation_address": command.capital_reservation_address,
        "paper_book_address": command.paper_book_address,
        "evaluation_event_address": command.evaluation_event_address,
        "state_before_address": event.state_before_address, "state_after_address": event.state_after_address,
        "provider_evidence_address": event.provider_evidence_address, "dataset_address": event.dataset_address,
        "entry_reference": command.entry_reference, "stop_loss": command.stop_loss,
        "take_profit": command.take_profit, "event_at": _time(command.event_at),
        "valid_until": _time(command.valid_until),
        "fence_epoch": authority.fence_epoch,
        "runtime_assignment": assignment.to_dict(),
        "instrument_authority": authority.to_dict(),
        "monitoring_event": event.to_dict(),
    })


def _decode_runtime_context_json(
        value: str, *, client_intent_id: str | None = None,
        assignment: RuntimeAssignment | None = None,
        authority: PaperInstrumentAuthority | None = None,
        event: MonitoringSignalEvent | None = None,
        broker_owner_id: str | None = None, broker_account_id: str | None = None,
        broker_deployment_id: int | None = None,
        broker_fence_epoch: int | None = None) -> tuple[
            dict[str, Any], RuntimeAssignment, PaperInstrumentAuthority,
            MonitoringSignalEvent, PaperCommand]:
    if not isinstance(value, str):
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_JSON_REQUIRED")
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_JSON_INVALID") from exc
    fields = {"schema", "client_intent_id", "action", "runtime_assignment_address",
              "instrument_authority_address", "monitoring_event_address", "paper_command_address",
              "owner_id", "deployment_id", "instrument_key", "approved_quantity",
              "graph_version_address", "resolved_graph_address", "implementation_closure_address",
              "canonical_instrument_address", "admission_address", "capital_decision_address",
              "capital_reservation_address", "paper_book_address", "evaluation_event_address",
              "state_before_address", "state_after_address", "provider_evidence_address",
              "dataset_address", "entry_reference", "stop_loss", "take_profit", "event_at",
              "valid_until", "fence_epoch", "runtime_assignment", "instrument_authority",
              "monitoring_event"}
    if not isinstance(parsed, dict) or set(parsed) != fields or parsed.get("schema") != "paper-runtime-context/1":
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_SCHEMA")
    if canonical_json(parsed) != value:
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_NOT_CANONICAL")
    for field in (name for name in fields if name.endswith("_address")):
        _require_address(parsed[field], field.upper())
    if not _INTENT.fullmatch(str(parsed["client_intent_id"])):
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_INTENT_INVALID")
    action = _enum(PaperAction, parsed["action"], "PAPER_ACTION")
    expected_intent_id = deterministic_client_intent_id(
        parsed["runtime_assignment_address"], parsed["monitoring_event_address"], action)
    if parsed["client_intent_id"] != expected_intent_id:
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_INTENT_MISMATCH")
    if client_intent_id is not None and parsed["client_intent_id"] != client_intent_id:
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_INTENT_MISMATCH")
    decoded_assignment = RuntimeAssignment.from_dict(parsed["runtime_assignment"])
    decoded_authority = PaperInstrumentAuthority.from_dict(parsed["instrument_authority"])
    decoded_event = MonitoringSignalEvent.from_dict(parsed["monitoring_event"])
    if ((assignment is not None and assignment != decoded_assignment)
            or (authority is not None and authority != decoded_authority)
            or (event is not None and event != decoded_event)):
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_SOURCE_MISMATCH")
    command = PaperCommand(
        owner_id=parsed["owner_id"], deployment_id=parsed["deployment_id"],
        instrument_key=parsed["instrument_key"],
        runtime_assignment_address=parsed["runtime_assignment_address"],
        instrument_authority_address=parsed["instrument_authority_address"],
        monitoring_event_address=parsed["monitoring_event_address"], action=action,
        client_intent_id=parsed["client_intent_id"],
        approved_quantity=parsed["approved_quantity"],
        entry_reference=parsed["entry_reference"], stop_loss=parsed["stop_loss"],
        take_profit=parsed["take_profit"],
        graph_version_address=parsed["graph_version_address"],
        resolved_graph_address=parsed["resolved_graph_address"],
        implementation_closure_address=parsed["implementation_closure_address"],
        canonical_instrument_address=parsed["canonical_instrument_address"],
        admission_address=parsed["admission_address"],
        capital_decision_address=parsed["capital_decision_address"],
        capital_reservation_address=parsed["capital_reservation_address"],
        paper_book_address=parsed["paper_book_address"],
        evaluation_event_address=parsed["evaluation_event_address"],
        event_at=_parse_time(parsed["event_at"], "EVENT_AT"),
        valid_until=_parse_time(parsed["valid_until"], "VALID_UNTIL"))
    if command.address != parsed["paper_command_address"]:
        raise PaperRuntimeRefusal("RUNTIME_CONTEXT_COMMAND_MISMATCH")
    if type(parsed["fence_epoch"]) is not int or parsed["fence_epoch"] < 1:
        raise PaperRuntimeRefusal("FENCE_EPOCH_REQUIRED")
    if parsed["fence_epoch"] != decoded_authority.fence_epoch:
        raise PaperRuntimeRefusal("RUNTIME_SOURCE_RELATION_MISMATCH")
    validate_runtime_relations(
        decoded_assignment, decoded_authority, decoded_event, command,
        broker_owner_id=broker_owner_id, broker_account_id=broker_account_id,
        broker_deployment_id=broker_deployment_id,
        broker_fence_epoch=broker_fence_epoch)
    return parsed, decoded_assignment, decoded_authority, decoded_event, command


def validate_runtime_context_json(
        value: str, *, client_intent_id: str | None = None,
        assignment: RuntimeAssignment | None = None,
        authority: PaperInstrumentAuthority | None = None,
        event: MonitoringSignalEvent | None = None,
        broker_owner_id: str | None = None, broker_account_id: str | None = None,
        broker_deployment_id: int | None = None,
        broker_fence_epoch: int | None = None) -> dict[str, Any]:
    """Strictly decode a canonical context and return its serialized document."""
    return _decode_runtime_context_json(
        value, client_intent_id=client_intent_id, assignment=assignment,
        authority=authority, event=event, broker_owner_id=broker_owner_id,
        broker_account_id=broker_account_id,
        broker_deployment_id=broker_deployment_id,
        broker_fence_epoch=broker_fence_epoch)[0]


def runtime_sources_from_context_json(
        value: str, *, client_intent_id: str,
        broker_owner_id: str, broker_account_id: str,
        broker_deployment_id: int, broker_fence_epoch: int
) -> tuple[dict[str, Any], RuntimeAssignment, PaperInstrumentAuthority,
           MonitoringSignalEvent, PaperCommand]:
    """Return the exact source facts already authenticated by strict context decode."""
    return _decode_runtime_context_json(
        value, client_intent_id=client_intent_id,
        broker_owner_id=broker_owner_id, broker_account_id=broker_account_id,
        broker_deployment_id=broker_deployment_id,
        broker_fence_epoch=broker_fence_epoch)


@dataclass(frozen=True, slots=True)
class BranchResult:
    branch: str
    status: BranchStatus
    effect_id: str | None
    refusal: str | None

    def __post_init__(self) -> None:
        if self.branch not in {"ALERT", "PAPER"} or type(self.status) is not BranchStatus:
            raise PaperRuntimeRefusal("BRANCH_RESULT_CLOSED_VALUE_REQUIRED")
        if self.effect_id is not None and (not isinstance(self.effect_id, str)
                                           or not _INTENT.fullmatch(self.effect_id)):
            raise PaperRuntimeRefusal("BRANCH_EFFECT_ID_INVALID")
        if self.refusal is not None and (not isinstance(self.refusal, str)
                                         or not re.fullmatch(r"^[A-Z][A-Z0-9_:]{0,127}$", self.refusal)):
            raise PaperRuntimeRefusal("BRANCH_REFUSAL_CODE_INVALID")
        effect_required = self.status in {
            BranchStatus.APPLIED, BranchStatus.ALREADY_APPLIED,
            BranchStatus.REFUSED, BranchStatus.RECONCILIATION_REQUIRED,
        }
        if effect_required and self.effect_id is None:
            raise PaperRuntimeRefusal("BRANCH_EFFECT_ID_REQUIRED")
        if not effect_required and self.effect_id is not None:
            raise PaperRuntimeRefusal("BRANCH_EFFECT_ID_FORBIDDEN")
        refusal_required = self.status in {
            BranchStatus.REFUSED, BranchStatus.RECONCILIATION_REQUIRED,
        }
        if refusal_required != (self.refusal is not None):
            raise PaperRuntimeRefusal("BRANCH_REFUSAL_RELATIONSHIP_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return {"branch": self.branch, "status": self.status.value,
                "effect_id": self.effect_id, "refusal": self.refusal}

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        if not isinstance(value, dict) or set(value) != {"branch", "status", "effect_id", "refusal"}:
            raise PaperRuntimeRefusal("BRANCH_RESULT_SCHEMA")
        return cls(branch=value["branch"], status=_enum(BranchStatus, value["status"], "BRANCH_STATUS"),
                   effect_id=value["effect_id"], refusal=value["refusal"])


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    command: PaperCommand
    preference: EffectPreference
    alert: BranchResult
    paper: BranchResult

    def __post_init__(self) -> None:
        if type(self.preference) is not EffectPreference:
            raise PaperRuntimeRefusal("RUNTIME_RESULT_PREFERENCE_INVALID")
        if self.alert.branch != "ALERT" or self.paper.branch != "PAPER":
            raise PaperRuntimeRefusal("RUNTIME_RESULT_BRANCH_MISMATCH")
        selected_alert = self.preference in {EffectPreference.ALERTS, EffectPreference.BOTH}
        selected_paper = self.preference in {EffectPreference.PAPER, EffectPreference.BOTH}
        if selected_alert == (self.alert.status is BranchStatus.NOT_SELECTED) \
                or selected_paper == (self.paper.status is BranchStatus.NOT_SELECTED):
            raise PaperRuntimeRefusal("RUNTIME_RESULT_SELECTION_MISMATCH")
        selected = tuple(result for chosen, result in (
            (selected_alert, self.alert), (selected_paper, self.paper)) if chosen)
        if self.command.action is PaperAction.HOLD:
            if any(result.status is not BranchStatus.NO_EFFECT for result in selected):
                raise PaperRuntimeRefusal("RUNTIME_RESULT_HOLD_MISMATCH")
        elif any(result.status is BranchStatus.NO_EFFECT for result in selected):
            raise PaperRuntimeRefusal("RUNTIME_RESULT_EFFECT_MISMATCH")

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command.to_dict(), "preference": self.preference.value,
                "alert": self.alert.to_dict(),
                "paper": self.paper.to_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, assignment: RuntimeAssignment,
                  authority: PaperInstrumentAuthority, event: MonitoringSignalEvent):
        if not isinstance(value, dict) or set(value) != {"command", "preference", "alert", "paper"}:
            raise PaperRuntimeRefusal("RUNTIME_RESULT_SCHEMA")
        result = cls(command=PaperCommand.from_dict(
                         value["command"], assignment=assignment,
                         authority=authority, event=event),
                     preference=_enum(EffectPreference, value["preference"], "EFFECT_PREFERENCE"),
                     alert=BranchResult.from_dict(value["alert"]),
                     paper=BranchResult.from_dict(value["paper"]))
        return result
