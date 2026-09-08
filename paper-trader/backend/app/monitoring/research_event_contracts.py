"""Completed-prefix research decisions, explicitly separate from simulated fills.

One issued prefix evaluation can replay several missed bars. Only its terminal
bar can create an alert; each intermediate decision remains attributable history.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import datetime as dt
from typing import ClassVar

from app.ir.hashing import canonical_json
from app.monitoring.contracts import (
    AlertDerived, EntryReference, EntryReferenceKind, FactValidity, Freshness,
    MonitoringSignalEvent, NoAlert, NoAlertCode, ProtectionKind, SignalAction,
    SignalAlert, StrategyState, _SYMBOL, _enum, _require_code,
)
from app.monitoring.research_protection import ResearchProtectionEvidence
from app.monitoring.research_replay_state import _closed, _require, _state_json
from app.monitoring.state_contracts import _address, _identifier, _parse_time, _time, _utc

_EXTRA_FIELDS = ("consumer_address", "completed_bar_identity", "prefix_completed_at",
    "prefix_available_at", "prefix_recorded_at", "replay_scope", "decision_kind", "simulated_position_state")
_CLOCK_FIELDS = ("event_at", "latest_data_at", "knowledge_cutoff_at", "valid_until",
    "prefix_completed_at", "prefix_available_at", "prefix_recorded_at")
_ENUM_FIELDS = {"previous_state": StrategyState, "target_state": StrategyState,
    "action": SignalAction, "freshness": Freshness, "evaluation_validity": FactValidity,
    "simulated_position_state": StrategyState}


def _research_identity(fact):
    for name in ("owner_id", "assignment_id", "strategy_id"):
        _identifier(getattr(fact, name), name)
    for field in fields(fact):
        if field.name.endswith("_address") or field.name == "completed_bar_identity":
            _address(getattr(fact, field.name), field.name)
    _require(type(fact.display_symbol) is str and _SYMBOL.fullmatch(fact.display_symbol) is not None,
             "safe research display symbol required")
    _require_code(fact.reason_code, "RESEARCH_REASON")
    for name in ("previous_state", "target_state", "action", "freshness", "simulated_position_state"):
        _require(type(getattr(fact, name)) is _ENUM_FIELDS[name], "closed research event enum required")
    _require(fact.state_before_address != fact.state_after_address, "research step must advance state")


def _research_clocks(fact):
    for name in _CLOCK_FIELDS:
        _utc(getattr(fact, name), name)
    _require(fact.latest_data_at == fact.event_at <= fact.prefix_completed_at
        <= fact.prefix_available_at <= fact.prefix_recorded_at <= fact.knowledge_cutoff_at,
        "research prefix clocks differ")
    _require(dt.timedelta(0) < fact.valid_until - fact.event_at <= dt.timedelta(days=1),
        "research alert lifetime differs")
    expected = Freshness.FRESH if fact.knowledge_cutoff_at <= fact.valid_until else Freshness.STALE
    _require(fact.freshness is expected, "research freshness differs from completed bar age")
    expected_scope = "CURRENT" if fact.event_at == fact.prefix_completed_at else "CATCH_UP"
    _require(fact.replay_scope == expected_scope, "research replay scope differs from prefix terminal")


def _research_decision(fact):
    _require(fact.decision_kind in ("NONE", "ENTER", "REVERSE", "EXIT"), "closed research decision required")
    held = fact.simulated_position_state
    if fact.decision_kind == "NONE":
        _require(fact.action is SignalAction.HOLD and fact.target_state is held,
                 "no pending decision must describe the held simulation")
        return
    if fact.decision_kind == "EXIT":
        _require(held is not StrategyState.FLAT and fact.target_state is StrategyState.FLAT
            and fact.action is SignalAction.EXIT, "exit requires a held simulated position")
        return
    _require(fact.target_state in (StrategyState.LONG, StrategyState.SHORT), "entry direction required")
    expected = SignalAction.BUY if fact.target_state is StrategyState.LONG else SignalAction.SELL
    _require(fact.action is expected, "research entry action differs from direction")
    _require((held is StrategyState.FLAT) == (fact.decision_kind == "ENTER")
        and held is not fact.target_state, "research entry or reversal differs from held simulation")


def _research_reference(fact):
    reference = fact.entry_reference
    _require(type(reference) is EntryReference, "closed research signal reference required")
    reference.__post_init__()
    _require(reference.kind is EntryReferenceKind.COMPLETED_EVENT_CLOSE and reference.validity is FactValidity.VALID
        and reference.canonical_instrument_address == fact.canonical_instrument_address
        and reference.observed_at == fact.event_at, "research signal reference differs from completed bar")


def _research_evidence(fact):
    _research_reference(fact)
    unresolved = fact.simulated_position_state is StrategyState.FLAT or fact.decision_kind in ("ENTER", "REVERSE")
    expected = "UNRESOLVED" if unresolved else "RESOLVED"
    policies = set()
    for evidence, kind in ((fact.stop_loss, ProtectionKind.STOP_LOSS), (fact.take_profit, ProtectionKind.TAKE_PROFIT)):
        _require(type(evidence) is ResearchProtectionEvidence, "closed research protection required")
        evidence.__post_init__()
        _require(evidence.kind is kind and evidence.consumer_address == fact.consumer_address,
                 "research protection scope differs")
        _require(evidence.status == (expected if evidence.rules else "DISABLED"), "research protection entry availability differs")
        policies.update(rule.risk_policy_address for rule in evidence.rules)
    _require(len(policies) <= 1, "research protections must retain the same risk policy")


def _research_extra_payload(fact):
    result = {name: getattr(fact, name) for name in _EXTRA_FIELDS}
    for name in ("prefix_completed_at", "prefix_available_at", "prefix_recorded_at"):
        result[name] = _time(result[name])
    result["simulated_position_state"] = fact.simulated_position_state.value
    return {**result, "evaluation_scope": "VERIFIED_COMPLETED_PREFIX", "authority": "NONE"}


def _research_fact_from_dict(cls, value):
    names = {field.name for field in fields(cls)}
    _closed(value, names | {"schema", "address", "evaluation_scope", "authority"}, cls.schema)
    arguments = {name: value[name] for name in names}
    for name in names & _ENUM_FIELDS.keys():
        arguments[name] = _enum(_ENUM_FIELDS[name], value[name], name.upper())
    for name in _CLOCK_FIELDS:
        arguments[name] = _parse_time(value[name], name)
    arguments["entry_reference"] = EntryReference.from_dict(value["entry_reference"])
    for name in ("stop_loss", "take_profit"):
        arguments[name] = ResearchProtectionEvidence.from_dict(value[name])
    result = cls(**arguments)
    _require(canonical_json(result.to_dict()) == canonical_json(value), "research event or copied fields differ")
    return result


@dataclass(frozen=True, slots=True)
class ResearchMonitoringSignalEvent(MonitoringSignalEvent):
    stop_loss: ResearchProtectionEvidence
    take_profit: ResearchProtectionEvidence
    consumer_address: str
    completed_bar_identity: str
    prefix_completed_at: dt.datetime
    prefix_available_at: dt.datetime
    prefix_recorded_at: dt.datetime
    replay_scope: str
    decision_kind: str
    simulated_position_state: StrategyState

    schema: ClassVar[str] = "monitoring-research-signal-event/1"

    def __post_init__(self):
        _research_identity(self)
        _research_clocks(self)
        _research_decision(self)
        _research_evidence(self)
        _require(self.evaluation_validity is FactValidity.VALID, "research decision requires verified evaluation")
        _require(type(self.repeated_target_state) is bool
            and self.repeated_target_state == (self.previous_state is self.target_state), "repeated research intent differs")

    def canonical_payload(self):
        return {**MonitoringSignalEvent.canonical_payload(self), **_research_extra_payload(self)}

    @classmethod
    def from_dict(cls, value):
        return _research_fact_from_dict(cls, value)

    @classmethod
    def from_json(cls, value):
        return cls.from_dict(_state_json(value))


@dataclass(frozen=True, slots=True)
class ResearchSignalAlert(SignalAlert):
    stop_loss: ResearchProtectionEvidence
    take_profit: ResearchProtectionEvidence
    consumer_address: str
    completed_bar_identity: str
    prefix_completed_at: dt.datetime
    prefix_available_at: dt.datetime
    prefix_recorded_at: dt.datetime
    replay_scope: str
    decision_kind: str
    simulated_position_state: StrategyState

    schema: ClassVar[str] = "research-signal-alert/1"

    def __post_init__(self):
        _research_identity(self)
        _research_clocks(self)
        _research_decision(self)
        _research_evidence(self)
        _require(self.replay_scope == "CURRENT" and self.freshness is Freshness.FRESH
            and self.action is not SignalAction.HOLD, "only a fresh terminal research decision may alert")

    def canonical_payload(self):
        return {**SignalAlert.canonical_payload(self), **_research_extra_payload(self)}

    @classmethod
    def from_dict(cls, value):
        return _research_fact_from_dict(cls, value)

    @classmethod
    def from_json(cls, value):
        return cls.from_dict(_state_json(value))


def derive_research_signal_alert(source):
    _require(type(source) is ResearchMonitoringSignalEvent, "closed research event required")
    source.__post_init__()
    if source.replay_scope == "CATCH_UP":
        return NoAlert(source.address, NoAlertCode.REPLAY_CATCH_UP)
    if source.freshness is Freshness.STALE:
        return NoAlert(source.address, NoAlertCode.STALE_DATA)
    if source.action is SignalAction.HOLD:
        return NoAlert(source.address, NoAlertCode.HOLD)
    arguments = {field.name: getattr(source, field.name) for field in fields(ResearchSignalAlert)
        if field.name != "monitoring_event_address"}
    return AlertDerived(ResearchSignalAlert(monitoring_event_address=source.address, **arguments))
