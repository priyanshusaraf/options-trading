"""Bind incremental simulation to an unchanged, anchored completed-price history.

The worker verifies graph evaluation and admission separately. This adapter uses
the canonical loader's candles and the shared research signal mapping. It cannot
activate an assignment, persist an alert or grant execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
from types import SimpleNamespace
from typing import ClassVar

from app.backtest import engine
from app.ir.hashing import content_address
from app.monitoring.input_producer import MonitoringInputPrefix
from app.monitoring.research_replay import ResearchReplayBar, advance_research_replay, _context
from app.monitoring.research_replay_state import (
    ResearchReplayState, _closed, _finite_float, _require, _state_json,
)
from app.monitoring.state_contracts import _address
from research.data.canonical_dataset import MAX_ROWS
from research.strategy.v2_runtime_strategy import research_signal_columns, _same_index


@dataclass(frozen=True, slots=True)
class ResearchReplayCheckpoint:
    state: ResearchReplayState
    history_address: str | None = None
    history_bars: int = 0

    schema: ClassVar[str] = "research-replay-checkpoint/1"

    def __post_init__(self):
        _require(type(self.state) is ResearchReplayState, "closed research replay state required")
        self.state.__post_init__()
        _require(type(self.history_bars) is int and 0 <= self.history_bars <= MAX_ROWS, "history count differs")
        if self.state.snapshot_sequence == 0:
            _require(self.history_address is None and self.history_bars == 0, "initial checkpoint must be empty")
        else:
            _address(self.history_address, "history prefix")
            _require(self.state.snapshot_sequence <= self.history_bars, "checkpoint history is shorter than replay")

    def canonical_payload(self):
        return {"schema": self.schema, "state": self.state.to_dict(),
            "history_address": self.history_address, "history_bars": self.history_bars}

    @property
    def address(self):
        return content_address(self.canonical_payload())

    def to_dict(self):
        return {**self.canonical_payload(), "address": self.address}

    @classmethod
    def from_dict(cls, value):
        _closed(value, {"schema", "state", "history_address", "history_bars", "address"}, cls.schema)
        checkpoint = cls(ResearchReplayState.from_dict(value["state"]), value["history_address"], value["history_bars"])
        _require(checkpoint.address == value["address"], "checkpoint address differs")
        return checkpoint

    @classmethod
    def from_json(cls, value):
        return cls.from_dict(_state_json(value))


@dataclass(frozen=True, slots=True)
class ResearchPrefixStep:
    checkpoint: ResearchReplayCheckpoint
    transition: object
    bar: ResearchReplayBar


def _prefix_projection(prefix):
    from research.evaluation.phase5_runtime import canonical_research_input_bytes
    _require(type(prefix) is MonitoringInputPrefix, "closed monitoring input prefix required")
    projection = prefix.projection
    opened, completed = projection.bar_open_index, projection.availability_index
    _require(len(opened) == len(completed) == len(prefix.candles) == prefix.bar_count
        and opened.is_unique and opened.is_monotonic_increasing
        and completed.is_unique and completed.is_monotonic_increasing,
        "research prefix clocks differ")
    _require(all(candle.ts == instant for candle, instant in zip(prefix.candles, opened, strict=True)),
             "research candles differ from their original bar clocks")
    digest = content_address({"schema": "verified-research-inputs/1",
        "dataset_manifest_address": prefix.manifest_address,
        "inputs": json.loads(canonical_research_input_bytes(projection.inputs))["inputs"]})
    _require(digest == projection.input_digest, "research input values changed after verification")
    return projection


def _bound_context_resolver(data_plan):
    from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract
    contracts = {}
    for row in data_plan.parameter_binding_provenance:
        receipt = row.get("node_contract_binding")
        if receipt is not None:
            contracts[tuple(row["lowered_path"])] = ResolvedNodeContract(receipt, receipt["bound_contract_address"])

    def resolve(node, _assembled):
        bound = contracts.get(tuple(node.lowered_path))
        return {"bound_contract": bound} if bound is not None else None

    return resolve


def evaluate_research_prefix_outputs(prefix, *, consumer, graph_document, registry):
    """Evaluate real bound nodes; the worker separately admits its schedule and event."""
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.market_data.requirements import compile_data_requirement_plan
    from app.monitoring.evaluation import _frozen_inputs, _registry_authority
    projection = _prefix_projection(prefix)
    consumer.__post_init__()
    _require(projection.manifest.owner_id == consumer.document["owner_id"], "research evaluation owner differs")
    graph = resolve_v2(graph_document, registry)
    _registry_authority(registry, graph)
    actual = (graph.authored_ir_address, graph.resolved_graph_address, graph.implementation_closure_address)
    expected = tuple(consumer.document[key] for key in (
        "graph_version_address", "resolved_graph_address", "graph_implementation_address"))
    _require(actual == expected, "research evaluation graph differs from consumer")
    plan = compile_data_requirement_plan(graph, registry=registry, input_bindings=projection.input_bindings)
    inputs = _frozen_inputs(graph, projection.inputs,
        cutoff_at=prefix.cutoff_at, terminal_at=prefix.completed_at)
    return evaluate_v2(graph, inputs, registry, evaluation_context_resolver=_bound_context_resolver(plan))


def _market_bars(prefix, checkpoint, consumer, timeframe_seconds):
    _require(type(prefix) is MonitoringInputPrefix and type(checkpoint) is ResearchReplayCheckpoint,
             "closed monitoring prefix and checkpoint required")
    checkpoint.__post_init__()
    state = checkpoint.state
    _prefix_projection(prefix)
    _require(consumer.address == state.consumer_address
        and prefix.projection.manifest.owner_id == state.owner_id
        and prefix.projection.manifest.instrument_addresses == (state.canonical_instrument_address,)
        and prefix.projection.manifest.manifest_address == prefix.manifest_address,
        "research prefix scope differs")
    _require(0 < prefix.bar_count == len(prefix.candles) <= MAX_ROWS, "research prefix count differs")
    bars = tuple(ResearchReplayBar(state.owner_id, state.canonical_instrument_address, timeframe_seconds,
        candle.ts, completed.to_pydatetime().astimezone(dt.timezone.utc),
        candle.open, candle.high, candle.low, candle.close)
        for candle, completed in zip(prefix.candles, prefix.projection.availability_index, strict=True))
    _require((bars[-1].identity, bars[-1].opened_at, bars[-1].completed_at)
        == (prefix.bar_identity, prefix.event_at, prefix.completed_at), "research prefix terminal differs")
    return bars


def _history_addresses(bars, candles):
    first = bars[0]
    previous = content_address({"schema": "research-price-history-origin/1",
        "owner_id": first.owner_id, "instrument_address": first.canonical_instrument_address,
        "timeframe_seconds": first.timeframe_seconds})
    addresses = []
    for bar, candle in zip(bars, candles, strict=True):
        volume = candle.volume
        if volume is not None:
            _finite_float(volume)
            _require(volume >= 0, "research volume must be nonnegative")
        previous = content_address({"schema": "research-price-history-prefix/1", "previous_address": previous,
            "bar_identity": bar.identity, "completed_at": bar.completed_at.isoformat(),
            "open_hex": bar.open.hex(), "high_hex": bar.high.hex(), "low_hex": bar.low.hex(),
            "close_hex": bar.close.hex(), "volume_hex": None if volume is None else volume.hex()})
        addresses.append(previous)
    return tuple(addresses)


def _first_unconsumed(checkpoint, bars, histories):
    if checkpoint.state.snapshot_sequence == 0:
        return len(bars) - 1  # Earlier bars warm up indicators without retrospective fills.
    matches = [index for index, bar in enumerate(bars) if bar.identity == checkpoint.state.last_bar_identity]
    _require(len(matches) == 1, "previous completed bar is absent from this history")
    previous = matches[0]
    _require(histories[previous] == checkpoint.history_address and previous + 1 == checkpoint.history_bars
        and bars[previous].completed_at == checkpoint.state.last_bar_completed_at,
        "previous research history changed; explicit reset is required")
    return previous + 1


def _signal_frame(prefix, consumer, graph_document, outputs, instrument_address):
    import pandas as pd
    context = _context(consumer.document, prefix.instrument, instrument_address)
    policy = consumer.document["execution_policy"]
    _, columns, warmup = research_signal_columns(graph_document, outputs,
        prefix.projection.availability_index, policy_address=policy["adapter_policy_address"],
        risk_policy=policy["risk"]["risk_policy"])
    source = engine.prepare_signal_frame(prefix.candles)
    _require(_same_index(pd.DatetimeIndex(source["date"]), prefix.projection.bar_open_index),
             "canonical price and graph clocks differ")
    strategy = SimpleNamespace(risk_model=context.rm, declared_warmup=warmup,
        risk_atr_seed_policy=policy["risk"]["overlay"]["atr_seed_policy"],
        signals=lambda frame, **_params: frame.assign(**columns))
    return engine.compute_signals(prefix.candles, strategy, {}, frame=source), warmup


def _signal_bar(market, row):
    return ResearchReplayBar(market.owner_id, market.canonical_instrument_address, market.timeframe_seconds,
        market.opened_at, market.completed_at, market.open, market.high, market.low, market.close,
        row["longEntry"], row["shortEntry"], row["longExit"], row["shortExit"], row.get("_ratchet_atr"))


def advance_research_prefix(checkpoint, *, prefix, consumer, graph_document, outputs, timeframe_seconds):
    """Process the unconsumed tail, or no bars for an unchanged terminal refetch.

    Returned intermediate steps preserve missed-bar state. The worker must derive
    alerts only from fresh completed decisions, and persist the steps atomically.
    """
    bars = _market_bars(prefix, checkpoint, consumer, timeframe_seconds)
    histories = _history_addresses(bars, prefix.candles)
    first = _first_unconsumed(checkpoint, bars, histories)
    if first == len(bars):
        return ()
    frame, warmup = _signal_frame(prefix, consumer, graph_document, outputs,
        checkpoint.state.canonical_instrument_address)
    _require(first >= warmup and len(frame) == len(bars) - warmup, "research history has not completed warmup")
    steps = []
    for index, row in enumerate(frame.to_dict("records"), start=warmup):
        if index < first:
            continue
        bar = _signal_bar(bars[index], row)
        transition = advance_research_replay(checkpoint.state, bar, consumer=consumer, instrument=prefix.instrument)
        checkpoint = ResearchReplayCheckpoint(transition.next_state, histories[index], index + 1)
        steps.append(ResearchPrefixStep(checkpoint, transition, bar))
    return tuple(steps)
