"""Versioned monitoring state for retained research simulation and signal intent."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import ClassVar

from app.ir.hashing import canonical_json, content_address
from app.market_truth.identity import CanonicalPhysicalInstrument
from app.monitoring.contracts import (
    EntryReference, EntryReferenceKind, FactValidity, ProtectionKind, StrategyState,
)
from app.monitoring.evaluation import _canonical_decimal
from app.monitoring.research_prefix import ResearchReplayCheckpoint
from app.monitoring.research_protection import ResearchProtectionEvidence, compile_research_protections
from app.monitoring.research_replay import ResearchReplayBar
from app.monitoring.research_replay_state import ResearchReplayState, _closed, _require, _state_json
from app.monitoring.state_contracts import _address, _parse_time, _time, _utc


def research_intent_state(state):
    _require(type(state) is ResearchReplayState, "closed replay state required")
    state.__post_init__()
    pending = state.pending
    if pending is not None:
        if pending.kind == "EXIT":
            return StrategyState.FLAT
        return StrategyState(pending.argument)
    return StrategyState.FLAT if state.position is None else StrategyState(state.position.direction)


def _snapshot_entry(snapshot):
    reference = snapshot.entry_reference
    _require(type(reference) is EntryReference, "closed signal reference required")
    reference.__post_init__()
    _require(reference.kind is EntryReferenceKind.COMPLETED_EVENT_CLOSE
        and reference.canonical_instrument_address == snapshot.canonical_instrument_address
        and reference.observed_at == snapshot.effective_at, "signal reference scope or clock differs")
    expected = FactValidity.MISSING if snapshot.snapshot_sequence == 0 else FactValidity.VALID
    _require(reference.validity is expected, "signal reference validity differs from state")


def _snapshot_protection(snapshot):
    state = snapshot.checkpoint.state
    prospective = state.position is None or (state.pending is not None and state.pending.kind in ("ENTER", "REVERSE"))
    resolution = "UNRESOLVED" if prospective else "RESOLVED"
    for evidence, kind in ((snapshot.stop_loss, ProtectionKind.STOP_LOSS),
            (snapshot.take_profit, ProtectionKind.TAKE_PROFIT)):
        _require(type(evidence) is ResearchProtectionEvidence, "closed research protection evidence required")
        evidence.__post_init__()
        _require(evidence.kind is kind and evidence.consumer_address == snapshot.checkpoint.state.consumer_address,
                 "snapshot protection scope differs")
        _require(evidence.status == (resolution if evidence.rules else "DISABLED"),
                 "snapshot protection must describe the actual entry availability")


@dataclass(frozen=True, slots=True)
class ResearchMonitoringStateSnapshot:
    checkpoint: ResearchReplayCheckpoint
    predecessor_snapshot_address: str | None
    entry_reference: EntryReference
    stop_loss: ResearchProtectionEvidence
    take_profit: ResearchProtectionEvidence
    evaluation_event_address: str
    effective_at: dt.datetime

    schema: ClassVar[str] = "monitoring-research-state-snapshot/1"

    def __post_init__(self):
        _require(type(self.checkpoint) is ResearchReplayCheckpoint, "closed research checkpoint required")
        self.checkpoint.__post_init__()
        _address(self.evaluation_event_address, "prefix evaluation event")
        _utc(self.effective_at, "snapshot effective time")
        if self.snapshot_sequence == 0:
            _require(self.predecessor_snapshot_address is None, "initial snapshot must not have a predecessor")
        else:
            _address(self.predecessor_snapshot_address, "predecessor monitoring snapshot")
            _require(self.effective_at == self.checkpoint.state.last_bar_completed_at,
                     "snapshot must use its completed bar clock")
        _snapshot_entry(self)
        _snapshot_protection(self)

    @property
    def owner_id(self):
        return self.checkpoint.state.owner_id

    @property
    def assignment_id(self):
        return self.checkpoint.state.assignment_id

    @property
    def canonical_instrument_address(self):
        return self.checkpoint.state.canonical_instrument_address

    @property
    def snapshot_sequence(self):
        return self.checkpoint.state.snapshot_sequence

    @property
    def strategy_state(self):
        """Declared intent; the checkpoint separately retains the simulated position."""
        return research_intent_state(self.checkpoint.state)

    def canonical_payload(self):
        return {"schema": self.schema, "owner_id": self.owner_id, "assignment_id": self.assignment_id,
            "canonical_instrument_address": self.canonical_instrument_address,
            "snapshot_sequence": self.snapshot_sequence, "strategy_state": self.strategy_state.value,
            "predecessor_snapshot_address": self.predecessor_snapshot_address,
            "checkpoint": self.checkpoint.to_dict(), "entry_reference": self.entry_reference.to_dict(),
            "stop_loss": self.stop_loss.to_dict(), "take_profit": self.take_profit.to_dict(),
            "evaluation_event_address": self.evaluation_event_address, "effective_at": _time(self.effective_at),
            "authority": "NONE"}

    @property
    def address(self):
        return content_address(self.canonical_payload())

    def to_dict(self):
        return {**self.canonical_payload(), "address": self.address}

    @classmethod
    def from_dict(cls, value):
        _closed(value, {"schema", "owner_id", "assignment_id", "canonical_instrument_address",
            "snapshot_sequence", "strategy_state", "predecessor_snapshot_address", "checkpoint",
            "entry_reference", "stop_loss", "take_profit", "evaluation_event_address", "effective_at",
            "authority", "address"}, cls.schema)
        result = cls(ResearchReplayCheckpoint.from_dict(value["checkpoint"]),
            value["predecessor_snapshot_address"], EntryReference.from_dict(value["entry_reference"]),
            ResearchProtectionEvidence.from_dict(value["stop_loss"]), ResearchProtectionEvidence.from_dict(value["take_profit"]),
            value["evaluation_event_address"], _parse_time(value["effective_at"], "snapshot effective time"))
        _require(canonical_json(result.to_dict()) == canonical_json(value), "research snapshot or copied fields differ")
        return result

    @classmethod
    def from_json(cls, value):
        return cls.from_dict(_state_json(value))


def _snapshot_step(checkpoint, bar, previous):
    _require(type(checkpoint) is ResearchReplayCheckpoint and type(bar) is ResearchReplayBar,
             "closed checkpoint and completed bar required")
    checkpoint.__post_init__()
    bar.__post_init__()
    state = checkpoint.state
    _require((bar.owner_id, bar.canonical_instrument_address) == (state.owner_id, state.canonical_instrument_address),
             "snapshot bar scope differs")
    if state.snapshot_sequence == 0:
        _require(previous is None, "initial monitoring snapshot must be new")
        return None
    _require(type(previous) is ResearchMonitoringStateSnapshot, "preceding research monitoring snapshot required")
    previous.__post_init__()
    _require((state.owner_id, state.assignment_id, state.canonical_instrument_address, state.consumer_address)
        == (previous.owner_id, previous.assignment_id, previous.canonical_instrument_address,
            previous.checkpoint.state.consumer_address), "preceding research snapshot scope differs")
    _require(state.snapshot_sequence == previous.snapshot_sequence + 1
        and state.predecessor_snapshot_address == previous.checkpoint.state.address,
        "inner research state must extend the preceding monitoring snapshot")
    _require(previous.snapshot_sequence == 0 or checkpoint.history_bars == previous.checkpoint.history_bars + 1,
             "research history must advance by one observed bar")
    _require((state.last_bar_identity, state.last_bar_completed_at) == (bar.identity, bar.completed_at),
             "snapshot bar differs from replay checkpoint")
    return previous.address


def compile_research_monitoring_snapshot(checkpoint, *, bar, previous, consumer, instrument,
        canonical_instrument, source_truth_address, evaluation_event_address):
    """Describe one verified replay step; the worker owns admission and persistence."""
    predecessor = _snapshot_step(checkpoint, bar, previous)
    _require(type(canonical_instrument) is CanonicalPhysicalInstrument
        and canonical_instrument.address == bar.canonical_instrument_address, "canonical signal instrument required")
    stop, target = compile_research_protections(checkpoint.state, consumer=consumer, instrument=instrument)
    value, validity = None, FactValidity.MISSING
    if checkpoint.state.snapshot_sequence:
        value = _canonical_decimal(str(bar.close), "completed signal reference")[1]
        validity = FactValidity.VALID
    reference = EntryReference(EntryReferenceKind.COMPLETED_EVENT_CLOSE, bar.canonical_instrument_address,
        value, canonical_instrument.currency, bar.completed_at, source_truth_address, validity)
    return ResearchMonitoringStateSnapshot(checkpoint, predecessor, reference, stop, target,
        evaluation_event_address, bar.completed_at)
