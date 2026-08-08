"""Every hand-written strategy must be causal: no value may depend on a future bar.

The IR proves this for graphs. `check_causality` (C11) evaluates a resolved graph on the
first *n* bars and on all of them and requires the first *n* results to agree at **every**
node, and `test_ir_strategy_parity.py` runs it against the reference artefact.

Nothing did that for the hand-written strategies — which are what the live engine actually
executes and what every backtest number is measured on. `trend_impulse_v3` is the default
registry strategy and had no causality proof at all.

Why it matters more here than it looks. `backtest/engine.py:compute_signals` computes the
signal frame over the **full** candle series and only then hands folds to the walk-forward
replay, deliberately, so path-dependent EMA/ATR seeds stay consistent across folds. That is
correct *if and only if* every indicator is causal. The moment one is not — a full-sample
quantile, a centred window, a backward fill, a `shift(-1)` — the out-of-sample folds are
scored using information from their own future, and the leak is invisible: the equity curve
simply looks better. This test is what makes that deliberate design safe.

The check is the same one C11 makes, applied through the `Strategy` contract instead of
through the graph runtime, and it is run on **real recorded market series** rather than
synthetic ramps, because a monotonic fixture can hide a look-ahead that only bites when the
series turns.
"""
from __future__ import annotations

import csv
import pathlib

import pandas as pd
import pytest

from app.strategy.registry import all_strategies, resolve_strategy
from app.strategy.registry import IR_NAMESPACE
from app.strategy.registry.base import CANONICAL_COLUMNS

DATA = pathlib.Path(__file__).parent / "data" / "real_spot_series.csv"


def _real_series() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    with DATA.open() as handle:
        for row in csv.DictReader(handle):
            out.setdefault(row["instrument_key"], []).append(float(row["spot"]))
    return out


def _frame(closes: list[float]) -> pd.DataFrame:
    """A production-shaped OHLCV frame, matching `test_ir_adapter.frame`."""
    close = pd.Series(closes, dtype=float)
    prev = close.shift(1).fillna(close.iloc[0]) if len(close) else close
    spread = close.abs() * 0.0005
    return pd.DataFrame({
        "date": pd.date_range("2026-06-22 09:15", periods=len(close), freq="15min",
                              tz="Asia/Kolkata"),
        "open": prev,
        "high": pd.concat([close, prev], axis=1).max(axis=1) + spread,
        "low": pd.concat([close, prev], axis=1).min(axis=1) - spread,
        "close": close,
        "volume": pd.Series(1000.0, index=close.index),
    })


def _longest_real_series() -> list[float]:
    series = _real_series()
    return max(series.values(), key=len)


# The instrument with the most recorded bars, so the prefixes below sit well past any
# strategy's warmup and the comparison is over settled values rather than NaN.
CLOSES = _longest_real_series()
PREFIXES = [int(len(CLOSES) * f) for f in (0.55, 0.7, 0.85, 0.95)]

STRATEGY_KEYS = sorted(s.key for s in all_strategies()
                       if not s.key.startswith(IR_NAMESPACE))


def _disagreements(full: pd.DataFrame, partial: pd.DataFrame, n: int) -> list[str]:
    """Columns where the prefix run and the full run disagree over their shared bars."""
    bad = []
    for col in partial.columns:
        if col not in full.columns or col == "date":
            continue
        a = full[col].iloc[:n].reset_index(drop=True)
        b = partial[col].iloc[:n].reset_index(drop=True)
        if len(a) != len(b):
            bad.append(f"{col}: length {len(b)} vs {len(a)}")
            continue
        # NaN must compare equal to NaN: a warmup row is "not yet known" in both runs.
        if a.dtype == bool or b.dtype == bool:
            differs = (a.astype(object) != b.astype(object))
        else:
            differs = ~((a == b) | (a.isna() & b.isna()))
        if bool(differs.any()):
            first = int(differs.idxmax())
            bad.append(f"{col}: first disagreement at bar {first} "
                       f"({b.iloc[first]!r} on the prefix vs {a.iloc[first]!r} on the full run)")
    return bad


@pytest.mark.parametrize("key", STRATEGY_KEYS)
@pytest.mark.parametrize("n", PREFIXES)
def test_the_strategy_cannot_read_the_future(key, n):
    """Evaluate on the first n bars and on all of them; the first n must agree.

    Asserted over every column the strategy emits, not only the four canonical ones — an
    indicator that peeks can be laundered into a signal that happens to agree on this
    series, and the intermediate column is where the leak is actually visible.
    """
    strat = resolve_strategy(key)
    frame = _frame(CLOSES)

    full = strat.signals(frame.copy())
    partial = strat.signals(frame.iloc[:n].copy())

    bad = _disagreements(full, partial, min(n, len(partial)))
    assert not bad, (
        f"{key} is not causal — its output over the first {n} bars changes when later bars "
        f"exist: {bad}. `compute_signals` computes over the full series before the "
        f"walk-forward folds are cut, so this leaks the fold's own future into its score."
    )


@pytest.mark.parametrize("key", STRATEGY_KEYS)
def test_the_causality_check_would_catch_a_lookahead(key):
    """The guard above must be able to fail.

    A strategy whose signals are shifted BACKWARD by one bar has read exactly one bar of
    the future. If the comparison cannot see that, it cannot see a real leak either — and
    a causality test that always passes is worse than none, because it is cited as proof.
    """
    strat = resolve_strategy(key)
    frame = _frame(CLOSES)
    n = PREFIXES[0]

    full = strat.signals(frame.copy())
    partial = strat.signals(frame.iloc[:n].copy())

    # Inject the leak into the prefix run: pull each canonical column one bar earlier, so
    # bar i now carries what bar i+1 knew.
    leaked = partial.copy()
    for col in CANONICAL_COLUMNS:
        leaked[col] = leaked[col].shift(-1).fillna(False).astype(bool)

    bad = _disagreements(full, leaked, min(n, len(leaked)))
    assert bad, (
        f"the comparison did not notice a one-bar look-ahead in {key}; it cannot be "
        f"evidence of causality"
    )


def test_every_registered_strategy_is_covered():
    """A new strategy must not join the registry without landing in this file's coverage.

    Parametrisation is derived from the live registry, so this is really asserting it
    is non-empty and was actually discovered — an empty registry would make every test
    above vacuously pass by not running.
    """
    assert STRATEGY_KEYS, "no strategies discovered — the causality parametrisation is empty"
    assert len(STRATEGY_KEYS) >= 2, STRATEGY_KEYS
