"""
Each block declares the columns it reads (F4), and the declaration is verified
against what it actually does.

An AST walk cannot do this job: `regime_is` reaches through `research/regime.py`
and `opening_range_break_*` through helpers, so a syntactic check would have to
chase every call across every module and would still miss a dynamic one. The
empirical check is both simpler and stronger — run the block on a frame
containing only what it declared, and demand the same answer.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from research.strategy.builder.blocks import BLOCKS

OHLCV = ("open", "high", "low", "close", "volume")


def frame(n=260):
    idx = pd.date_range("2026-01-01 09:15", periods=n, freq="15min", tz="Asia/Kolkata")
    close = pd.Series([1000 + math.sin(i / 8.0) * 7 + math.sin(i / 37.0) * 18
                       for i in range(n)], index=idx, dtype=float)
    return pd.DataFrame({
        "date": idx,
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 2.0 + (pd.Series(range(n), index=idx) % 5) * 0.4,
        "low": close - 2.0 - (pd.Series(range(n), index=idx) % 7) * 0.3,
        "close": close,
        "volume": pd.Series([900 + (i % 19) * 30 + (2600 if i % 53 == 0 else 0)
                             for i in range(n)], index=idx, dtype=float),
    }, index=idx)


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_a_block_needs_only_what_it_declares(name):
    """The declaration is authoritative and the implementation must satisfy it.

    Under-declaring is the failure that matters: the IR adapter builds each
    node's frame from the declared sockets, so a block reading a column it did
    not declare gets a frame without it. Some of these blocks fail *closed* on a
    missing column — `volume_surge` reads False, `time_of_day` returns all-False
    — which means under-declaration would not raise. It would silently switch
    the filter off, and a generated strategy would quietly lose a condition
    somebody added on purpose.
    """
    spec = BLOCKS[name]
    full = frame()
    kept = list(spec.inputs) + (["date"] if spec.needs_clock else [])
    narrowed = full[kept].copy()

    assert spec.fn(narrowed, *spec.sample_args).equals(spec.fn(full, *spec.sample_args)), name


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_a_block_does_not_declare_what_it_never_reads(name):
    """Over-declaring is milder but not free: it makes a node depend on data it
    does not use, which shows up as spurious edges in a graph and as cache
    invalidation that need not have happened.

    Tested by *removal*, not by perturbation. The first version of this test
    scaled each column by a positive constant and demanded the output move —
    which fails on most of these blocks for a mathematical reason rather than a
    declarative one: `close > EMA(close)` is invariant under a positive affine
    change to `close`. It was measuring the wrong thing."""
    spec = BLOCKS[name]
    if any(kind == "choice" for _, kind in spec.params):
        pytest.skip("a choice parameter selects the data source — see the union test below")
    if spec.needs_clock:
        pytest.skip("its value input exists to carry the index, so removal cannot detect it")
    full = frame()
    kept = list(spec.inputs) + (["date"] if spec.needs_clock else [])
    reference = spec.fn(full[kept].copy(), *spec.sample_args)

    for column in spec.inputs:
        without = [c for c in kept if c != column]
        try:
            same = spec.fn(full[without].copy(), *spec.sample_args).equals(reference)
        except Exception:
            continue                      # needed it — the declaration is right
        if same:
            pytest.fail(f"{name} declares {column!r} but computes the same without it")


@pytest.mark.parametrize("name", sorted(
    n for n, s in BLOCKS.items() if any(k == "choice" for _, k in s.params)))
def test_a_choice_parameter_widens_the_declaration_to_the_union(name):
    """A declaration covers the block's whole parameter domain, not the sample
    args. `rsi_gt` reads only `close` at `source=0` and all four OHLC at
    `source=3` (ohlc4), so declaring all four is correct and the removal test
    above would wrongly call it over-declared — which it did, on three blocks,
    until this test existed to say why.

    Checked across every lawful value of every choice parameter."""
    spec = BLOCKS[name]
    full = frame()
    kept = list(spec.inputs) + (["date"] if spec.needs_clock else [])
    positions = [i for i, (_, kind) in enumerate(spec.params) if kind == "choice"]

    checked = 0
    for position in positions:
        for value in range(6):                    # codes clamp, so this covers the domain
            args = list(spec.sample_args)
            args[position] = value
            assert spec.fn(full[kept].copy(), *args).equals(spec.fn(full, *args)), \
                f"{name} at {spec.params[position][0]}={value} needs more than it declares"
            checked += 1
    assert checked >= 6


def test_the_declarations_are_not_all_the_full_frame():
    """The point of the exercise. If every block still declared all five columns
    the narrowing would have achieved nothing, and the test above would pass
    vacuously."""
    narrowed = [n for n, s in BLOCKS.items() if set(s.inputs) != set(OHLCV)]
    assert len(narrowed) == len(BLOCKS)
    assert sum(len(s.inputs) for s in BLOCKS.values()) < len(BLOCKS) * len(OHLCV) * 0.6


def test_the_clock_is_declared_separately_from_the_values():
    """Bar timestamps are the series *index*, not a value on a wire — F7's value
    types are float/int/bool and a datetime is none of them. Declaring the clock
    as a socket would have needed a format amendment; declaring it as a property
    of the block needs none.

    A clock-only block still declares one value input: its output is a series
    indexed like the frame, so it needs at least one series to know which bars
    exist. `time_of_day` declared nothing at first and produced an empty
    series."""
    clock_blocks = {n for n, s in BLOCKS.items() if s.needs_clock}
    assert clock_blocks == {"time_of_day", "opening_range_break_up",
                            "opening_range_break_down"}
    for name in clock_blocks:
        assert "date" not in BLOCKS[name].inputs, name
        assert BLOCKS[name].context_inputs == ("bar_timestamp",), name

    for name, spec in BLOCKS.items():
        if name not in clock_blocks:
            assert spec.context_inputs == (), name


def test_every_declared_column_is_a_real_ohlcv_column():
    for name, spec in BLOCKS.items():
        assert set(spec.inputs) <= set(OHLCV), name


def test_a_clock_block_reads_false_rather_than_raising_without_its_clock():
    """Why under-declaration is silent here, stated as a test rather than a
    comment: these blocks fail closed."""
    full = frame()
    for name in ("time_of_day", "opening_range_break_up"):
        spec = BLOCKS[name]
        without = full[list(spec.inputs)].copy()
        assert not spec.fn(without, *spec.sample_args).any(), name
