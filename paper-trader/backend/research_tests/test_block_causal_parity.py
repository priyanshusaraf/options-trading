"""Manifest-derived vector/streaming parity for admitted generated blocks."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.ir.contributors.generated_blocks import (
    BLOCK_COMPONENTS,
    BLOCKS,
    CAUSAL_MANIFEST,
    PRICE_SOURCES,
    SMOOTHINGS,
    atr_pct,
)
from app.ir.library import REGISTRY
from app.ir.resolve import resolve
from app.ir.runtime import evaluate
from app.ir.streaming_reference import evaluate_prefix_stream


ADMITTED_BLOCK_NAMES = tuple(sorted(
    name for name, disposition in CAUSAL_MANIFEST.items()
    if disposition.status == "admitted"
))


def _wire(value: str) -> dict:
    return {
        "value": value,
        "structure": "series",
        "domain": {"instrument": "*", "timeframe": "*"},
    }


def _socket(name: str, direction: str, value: str) -> dict:
    return {
        "item": "socket", "identifier": name, "display_name": name,
        "direction": direction, "wire_type": _wire(value),
    }


def _block_graph(name: str, overrides: dict[str, object] | None = None) -> dict:
    """One manifest component as an admissible graph, with no local registry copy."""
    spec = BLOCKS[name]
    return {
        "format_version": 1,
        "kind": "graph",
        "identifier": f"causal-parity.{name}",
        "version": 1,
        "display_name": name,
        "interface": [
            *(_socket(field, "input", "float") for field in spec.inputs),
            _socket("longEntry", "output", "bool"),
        ],
        "nodes": [
            {"instance_id": "io_in", "component": {
                "identifier": "graph.input", "version": 1}, "overrides": {}},
            {"instance_id": "block", "component": {
                "identifier": f"block.{name}", "version": 1},
             "overrides": overrides or {}},
            {"instance_id": "io_out", "component": {
                "identifier": "graph.output", "version": 1}, "overrides": {}},
        ],
        "edges": [
            *({"source": {"instance": "io_in", "socket": field},
               "target": {"instance": "block", "socket": field}}
              for field in spec.inputs),
            {"source": {"instance": "block", "socket": "out"},
             "target": {"instance": "io_out", "socket": "longEntry"}},
        ],
        "groups": [],
    }


def _bars(length: int = 80) -> dict[str, pd.Series]:
    """Non-flat deterministic bars that exercise trend, gaps, volume and sessions."""
    index = pd.date_range(
        "2026-01-05 09:15", periods=length, freq="15min", tz="Asia/Kolkata")
    close_values = np.array([
        1_000.0 + math.sin(position / 9.0) * 8.0
        + math.sin(position / 41.0) * 20.0
        + (18.0 if position > 200 else 0.0)
        for position in range(length)
    ])
    close = pd.Series(close_values, index=index, name="close")
    open_ = close.shift(1).fillna(close.iloc[0]).rename("open")
    high = (close + 2.0 + (np.arange(length) % 5) * 0.6).rename("high")
    low = (close - 2.0 - (np.arange(length) % 7) * 0.5).rename("low")
    volume = pd.Series(
        [900.0 + (position % 23) * 40.0 + (2500.0 if position % 61 == 0 else 0.0)
         for position in range(length)],
        index=index,
        name="volume",
    )
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


def _assert_independent_parity(graph: dict, inputs: dict[str, pd.Series]) -> None:
    resolved = resolve(graph, REGISTRY.library)
    supplied = {name: inputs[name] for name in resolved.inputs}
    vector = evaluate(resolved, supplied, REGISTRY.implementations)
    reference = evaluate_prefix_stream(resolved, supplied, REGISTRY)
    pd.testing.assert_series_equal(
        vector.outputs["longEntry"], reference.outputs["longEntry"],
        check_names=False,
    )


@pytest.mark.parametrize("name", ADMITTED_BLOCK_NAMES)
def test_every_admitted_manifest_block_matches_the_independent_prefix_oracle(
    name: str,
) -> None:
    """Hypothesis 8: an admitted manifest block can differ from live step semantics."""
    graph = _block_graph(name)
    _assert_independent_parity(graph, _bars())


@pytest.mark.parametrize(
    ("name", "source", "smooth"),
    [(name, source, smooth)
     for name in ("rsi_gt", "rsi_lt")
     for source in range(len(PRICE_SOURCES))
     for smooth in range(len(SMOOTHINGS))],
)
def test_every_rsi_source_and_smoothing_choice_matches_the_independent_prefix_oracle(
    name: str, source: int, smooth: int,
) -> None:
    """Hypothesis 8: a non-default RSI recursive choice can drift from vector RSI."""
    graph = _block_graph(name, {"source": source, "smooth": smooth})
    _assert_independent_parity(graph, _bars())


def _two_session_bars() -> dict[str, pd.Series]:
    index = pd.DatetimeIndex([
        *pd.date_range("2026-01-05 09:15", periods=5, freq="15min", tz="Asia/Kolkata"),
        *pd.date_range("2026-01-06 09:15", periods=5, freq="15min", tz="Asia/Kolkata"),
    ])
    close = pd.Series([100.0, 150.0, 100.0, 100.0, 100.0,
                       10.0, 11.0, 10.0, 11.0, 14.0], index=index, name="close")
    return {
        "high": (close + 0.5).rename("high"),
        "low": (close - 0.5).rename("low"),
        "close": close,
    }


def test_opening_range_restarts_on_the_second_recorded_session() -> None:
    """Hypothesis 8: session state can accidentally carry the prior day's range."""
    graph = _block_graph("opening_range_break_up")
    inputs = _two_session_bars()
    _assert_independent_parity(graph, inputs)

    result = evaluate_prefix_stream(resolve(graph, REGISTRY.library), inputs, REGISTRY)
    assert bool(result.outputs["longEntry"].iloc[-1]) is True


def _regime_transition_bars() -> dict[str, pd.Series]:
    length = 280
    index = pd.date_range("2026-01-05 09:15", periods=length, freq="15min", tz="Asia/Kolkata")
    low_variance = 100.0 + np.sin(np.arange(140) / 13.0) * 0.25
    high_variance = low_variance[-1] + np.cumsum(
        np.where(np.arange(140) % 2, 3.5, -2.6))
    close = pd.Series(np.r_[low_variance, high_variance], index=index, name="close")
    open_ = close.shift(1).fillna(close.iloc[0]).rename("open")
    range_scale = np.r_[np.full(140, 0.4), np.full(140, 3.0)]
    return {
        "open": open_,
        "high": (np.maximum(open_, close) + range_scale).rename("high"),
        "low": (np.minimum(open_, close) - range_scale).rename("low"),
        "close": close,
    }


def test_regime_expanding_median_transition_matches_the_independent_prefix_oracle() -> None:
    """Hypothesis 8: expanding regime state can diverge after its median changes."""
    graph = _block_graph("regime_is")
    inputs = _regime_transition_bars()
    _assert_independent_parity(graph, inputs)

    frame = pd.DataFrame(inputs)
    expanding_median = atr_pct(frame).expanding(min_periods=20).median().dropna()
    assert expanding_median.round(8).nunique() > 10
