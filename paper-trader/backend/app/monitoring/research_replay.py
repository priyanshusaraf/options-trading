"""Advance one simulated research bar using the original replay engine.

This pure adapter grants no admission or execution authority. The worker must
verify the consumer, canonical input history, consecutive observed bars and fresh
evaluation evidence before calling it. Warmup history never enters this function
as retrospective trades: a newly activated assignment starts with empty state.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import datetime as dt
from types import SimpleNamespace

from app.backtest import engine
from app.core.market_hours import ist_epoch
from app.ir.hashing import canonical_json, content_address
from app.monitoring.research_replay_state import (
    ResearchPendingDecision, ResearchReplayPosition, ResearchReplayState,
    _finite_float, _require, restore_ratchet,
)
from app.monitoring.state_contracts import _address, _identifier, _utc


@dataclass(frozen=True, slots=True)
class ResearchReplayBar:
    owner_id: str
    canonical_instrument_address: str
    timeframe_seconds: int
    opened_at: dt.datetime
    completed_at: dt.datetime
    open: float
    high: float
    low: float
    close: float
    long_entry: bool = False
    short_entry: bool = False
    long_exit: bool = False
    short_exit: bool = False
    atr: float | None = None

    def __post_init__(self):
        _identifier(self.owner_id, "research bar owner")
        _address(self.canonical_instrument_address, "research bar instrument")
        _require(type(self.timeframe_seconds) is int and self.timeframe_seconds in {900, 1800, 3600, 86400},
                 "unsupported research bar timeframe")
        opened, completed = _utc(self.opened_at, "bar open"), _utc(self.completed_at, "bar completion")
        _require(dt.timedelta(0) < completed - opened <= dt.timedelta(seconds=self.timeframe_seconds),
                 "research bar completion differs")
        _bar_values(self)

    @property
    def identity(self):
        return content_address({"schema": "monitoring-completed-bar/1", "owner_id": self.owner_id,
            "instrument_address": self.canonical_instrument_address,
            "timeframe_seconds": self.timeframe_seconds, "event_at": self.opened_at.isoformat()})

    def to_row(self):
        return {"date": self.opened_at, "open": self.open, "high": self.high,
            "low": self.low, "close": self.close, "longEntry": self.long_entry,
            "shortEntry": self.short_entry, "longExit": self.long_exit, "shortExit": self.short_exit,
            "_ratchet_atr": self.atr}


def _bar_values(bar):
    for value in (bar.open, bar.high, bar.low, bar.close):
        _finite_float(value, positive=True)
    _require(bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high,
             "research bar OHLC differs")
    _require(all(type(value) is bool for value in (bar.long_entry, bar.short_entry, bar.long_exit, bar.short_exit)),
             "research signals must be booleans")
    if bar.atr is not None:
        _finite_float(bar.atr, positive=True)


@dataclass(frozen=True, slots=True)
class ResearchReplayTransition:
    before_address: str
    next_state: ResearchReplayState
    opened_position: ResearchReplayPosition | None
    closed_trades: tuple


def _scope(state, bar, consumer):
    from app.ir.resource_plan import CanonicalResourceDocument
    _require(type(state) is ResearchReplayState and type(bar) is ResearchReplayBar, "closed replay inputs required")
    _require(type(consumer) is CanonicalResourceDocument, "canonical replay consumer required")
    state.__post_init__()
    bar.__post_init__()
    consumer.__post_init__()
    document = consumer.document
    _require(consumer.schema == "monitoring-research-consumer/1"
        and document["owner_id"] == state.owner_id == bar.owner_id
        and document["assignment_id"] == state.assignment_id
        and consumer.address == state.consumer_address
        and bar.canonical_instrument_address == state.canonical_instrument_address,
        "research replay scope differs")
    if state.snapshot_sequence:
        _require(bar.identity != state.last_bar_identity and bar.opened_at > state.last_bar_open_at
            and bar.opened_at >= state.last_bar_completed_at, "research bar already consumed or out of order")
    return document


def _context(document, instrument, instrument_address):
    from research.data.canonical_dataset import instrument_key
    from research.orchestrator.v2_preparation import execution_policy, protective_percentages
    from app.ir.resource_plan import _plain
    policy = _plain(document["execution_policy"])
    risk = policy["risk"]
    _finite_float(risk["capital"], positive=True)
    expected = execution_policy(risk["capital"], risk["risk_policy"], **protective_percentages(risk))
    _require(canonical_json(policy) == canonical_json(expected), "retained research execution policy differs")
    _require(document["fill"] == "NEXT_OBSERVED_BAR_OPEN_SIMULATED_ONLY" and document["authority"] == "NONE"
        and document["slippage_pct"] == policy["slippage"]["basis_points"] / 10_000.0,
        "retained research fill policy differs")
    _require(instrument.key == instrument_key(instrument_address) and instrument.name == instrument_address
        and instrument.segment in {"NSE", "BSE"} and type(instrument.lot_size) is int and instrument.lot_size == 1
        and instrument.source == "canonical_dataset", "canonical research instrument required")
    detached = SimpleNamespace(key=instrument.key, segment=instrument.segment, lot_size=instrument.lot_size)
    return engine._ReplayContext(detached, instrument.segment + "_EQ", risk["capital"],
        risk["overlay"]["risk_model"], True, document["slippage_pct"] / 2.0,
        risk["sizing_model"] == "fixed_unit_v1", risk.get("protective_band"))


def _restored_engine_state(state, context):
    restored = engine._ReplayState()
    if state.position is not None:
        position = state.position
        qty, notional, lots = engine._replay_position(context, position.entry_price)
        _require(qty > 0, "retained position is not eligible under original sizing")
        restored.pos = {"direction": position.direction, "entry_price": position.entry_price,
            "entry_time": ist_epoch(position.entry_open_at), "entry_idx": position.entry_sequence,
            "qty": qty, "notional": notional, "lots": lots, "mae_pct": position.mae_pct}
        restored.ratchet = restore_ratchet(position, context.rm)
    if state.pending is not None:
        restored.pending = (state.pending.kind, state.pending.argument, state.snapshot_sequence + 1)
    return restored


def _position(state, bar, replay, sequence):
    position = replay.pos
    if position is None:
        return None
    existing = state.position if position["entry_idx"] != sequence else None
    ratchet = replay.ratchet
    return ResearchReplayPosition(position["direction"], position["entry_price"],
        existing.entry_open_at if existing else bar.opened_at,
        existing.entry_bar_identity if existing else bar.identity, position["entry_idx"],
        (existing.entry_atr if existing else bar.atr) if ratchet else None,
        ratchet.hw if ratchet else None, ratchet.stop if ratchet else None, position["mae_pct"])


def advance_research_replay(state, bar, *, consumer, instrument):
    """Consume one new observed bar; retain terminal decisions without inventing fills."""
    document = _scope(state, bar, consumer)
    context = _context(document, instrument, state.canonical_instrument_address)
    _require(context.rm is None or bar.atr is not None, "research risk ATR is unavailable")
    replay = _restored_engine_state(state, context)
    sequence, row, trades = state.snapshot_sequence + 1, bar.to_row(), []
    if replay.pending is not None:
        engine._fill_replay_pending(replay, context, row, sequence, trades)
    opened = _position(state, bar, replay, sequence) if replay.pos and replay.pos["entry_idx"] == sequence else None
    decision = engine._replay_decision(replay, context, row, sequence)
    pending = ResearchPendingDecision(decision[0], decision[1], bar.identity, bar.completed_at) if decision else None
    next_state = replace(state, snapshot_sequence=sequence, predecessor_snapshot_address=state.address,
        last_bar_identity=bar.identity, last_bar_open_at=bar.opened_at, last_bar_completed_at=bar.completed_at,
        position=_position(state, bar, replay, sequence), pending=pending)
    return ResearchReplayTransition(state.address, next_state, opened, tuple(trades))
