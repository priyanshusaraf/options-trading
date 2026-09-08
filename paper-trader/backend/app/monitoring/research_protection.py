"""Display retained research protection rules without inventing a future fill.

These facts describe simulated research policy. They are not authored graph nodes,
broker instructions, admission receipts or permission to place an order.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.ir.hashing import canonical_json, content_address
from app.ir.resource_plan import CanonicalResourceDocument, _plain
from app.monitoring.contracts import ProtectionKind, _enum
from app.monitoring.research_replay import _context
from app.monitoring.research_replay_state import (
    ResearchReplayState, _closed, _finite_float, _float_hex, _from_hex, _require, restore_ratchet,
)
from app.monitoring.state_contracts import _address
from app.strategy.replay_decisions import protection_band

PERCENT = "FRACTION_FROM_SIMULATED_ENTRY"
RATCHET = "ATR_RATCHET_STOP"


@dataclass(frozen=True, slots=True)
class ResearchProtectionRule:
    consumer_address: str
    risk_policy_address: str
    kind: ProtectionKind
    basis: str
    fraction: float | None
    resolved_value: float | None

    schema: ClassVar[str] = "monitoring-research-protection-rule/1"

    def __post_init__(self):
        _address(self.consumer_address, "protection consumer")
        _address(self.risk_policy_address, "retained risk policy")
        _require(type(self.kind) is ProtectionKind, "closed protection kind required")
        _require(type(self.basis) is str and self.basis in (PERCENT, RATCHET), "closed protection basis required")
        if self.basis == PERCENT:
            _finite_float(self.fraction, positive=True)
            _require(self.fraction < 1.0, "protection fraction must be below one")
        else:
            _require(self.kind is ProtectionKind.STOP_LOSS and self.fraction is None,
                     "ratchet describes a stop without a percentage fraction")
        if self.resolved_value is not None:
            _finite_float(self.resolved_value)

    def definition(self):
        return {"schema": self.schema, "consumer_address": self.consumer_address,
            "risk_policy_address": self.risk_policy_address, "kind": self.kind.value,
            "basis": self.basis, "fraction_hex": _float_hex(self.fraction)}

    @property
    def definition_address(self):
        return content_address(self.definition())

    def to_dict(self):
        return {**self.definition(), "definition_address": self.definition_address,
            "resolved_value_hex": _float_hex(self.resolved_value)}

    @classmethod
    def from_dict(cls, value):
        _closed(value, {"schema", "consumer_address", "risk_policy_address", "kind", "basis",
            "fraction_hex", "definition_address", "resolved_value_hex"}, cls.schema)
        result = cls(value["consumer_address"], value["risk_policy_address"], _enum(ProtectionKind, value["kind"], "PROTECTION_KIND"),
            value["basis"], _from_hex(value["fraction_hex"], optional=True),
            _from_hex(value["resolved_value_hex"], optional=True))
        _require(canonical_json(result.to_dict()) == canonical_json(value), "protection definition differs")
        return result


@dataclass(frozen=True, slots=True)
class ResearchProtectionEvidence:
    consumer_address: str
    kind: ProtectionKind
    rules: tuple[ResearchProtectionRule, ...]

    schema: ClassVar[str] = "monitoring-research-protection-evidence/1"

    def __post_init__(self):
        _address(self.consumer_address, "protection consumer")
        _require(type(self.kind) is ProtectionKind, "closed protection kind required")
        _require(type(self.rules) is tuple and len(self.rules) <= 2, "bounded protection rules required")
        for rule in self.rules:
            _require(type(rule) is ResearchProtectionRule, "closed protection rule required")
            rule.__post_init__()
            _require(rule.consumer_address == self.consumer_address and rule.kind is self.kind,
                     "protection rule scope differs")
        bases = tuple(rule.basis for rule in self.rules)
        _require(bases in ((), (PERCENT,), (RATCHET,), (PERCENT, RATCHET)),
                 "protection rules must retain unique stop-before-ratchet precedence")
        _require(len({rule.risk_policy_address for rule in self.rules}) <= 1,
                 "protection rules must retain one risk policy")
        _require(len({rule.resolved_value is None for rule in self.rules}) <= 1,
                 "protection rules must share an entry reference")

    @property
    def status(self):
        if not self.rules:
            return "DISABLED"
        return "UNRESOLVED" if any(rule.resolved_value is None for rule in self.rules) else "RESOLVED"

    def to_dict(self):
        return {"schema": self.schema, "consumer_address": self.consumer_address, "kind": self.kind.value,
            "rules": [rule.to_dict() for rule in self.rules], "status": self.status}

    @classmethod
    def from_dict(cls, value):
        _closed(value, {"schema", "consumer_address", "kind", "rules", "status"}, cls.schema)
        _require(type(value["rules"]) is list and len(value["rules"]) <= 2, "bounded protection rules required")
        result = cls(value["consumer_address"], _enum(ProtectionKind, value["kind"], "PROTECTION_KIND"),
            tuple(ResearchProtectionRule.from_dict(rule) for rule in value["rules"]))
        _require(canonical_json(result.to_dict()) == canonical_json(value), "protection evidence differs")
        return result


def _protection_context(state, consumer, instrument):
    _require(type(state) is ResearchReplayState and type(consumer) is CanonicalResourceDocument,
             "closed research state and consumer required")
    state.__post_init__()
    consumer.__post_init__()
    _require(consumer.schema == "monitoring-research-consumer/1" and consumer.address == state.consumer_address
        and consumer.document["owner_id"] == state.owner_id
        and consumer.document["assignment_id"] == state.assignment_id, "protection consumer scope differs")
    return _context(consumer.document, instrument, state.canonical_instrument_address)


def _intent_position(state, context):
    position = state.position
    if position is not None:
        restore_ratchet(position, context.rm)
    if state.pending is not None and state.pending.kind in ("ENTER", "REVERSE"):
        position = None
    return position


def compile_research_protections(state, *, consumer, instrument):
    """Retain every configured rule; prospective entry levels remain unresolved."""
    context = _protection_context(state, consumer, instrument)
    position = _intent_position(state, context)
    prices = (None, None) if position is None else protection_band(
        {"direction": position.direction, "entry_price": position.entry_price}, context.protective_band)
    policy_address = content_address(_plain(consumer.document["execution_policy"]["risk"]))
    stop, target = [], []
    band = context.protective_band or {}
    for kind, key, price, rules in ((ProtectionKind.STOP_LOSS, "stop_loss_pct", prices[0], stop),
            (ProtectionKind.TAKE_PROFIT, "take_profit_pct", prices[1], target)):
        fraction = band.get(key, 0.0)
        if fraction:
            rules.append(ResearchProtectionRule(consumer.address, policy_address, kind, PERCENT, fraction, price))
    if context.rm is not None:
        stop.append(ResearchProtectionRule(consumer.address, policy_address, ProtectionKind.STOP_LOSS,
            RATCHET, None, None if position is None else position.ratchet_stop))
    return (ResearchProtectionEvidence(consumer.address, ProtectionKind.STOP_LOSS, tuple(stop)),
        ResearchProtectionEvidence(consumer.address, ProtectionKind.TAKE_PROFIT, tuple(target)))
