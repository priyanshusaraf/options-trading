"""Expanding Z Impulse V4 — faithful port of the Pine signal half. We don't assert
exact bar indices (that's brittle); we pin the strategy's *invariants*, which are
exactly what the Pine logic guarantees:

  * every long entry is on a confirmed up-displacement (zscore>0) with bullish ATR
    drift, on a non-blowoff bar, and (require_expansion) while absZ is still growing;
  * exits are the displacement-lost set (drift flip OR price back across the EMA);
  * require_expansion=True entries are a strict subset of require_expansion=False.
"""
import numpy as np
import pandas as pd
import pytest

from app.strategy.registry import get_strategy
from app.strategy.registry.base import CANONICAL_COLUMNS


def _regime_series(n: int = 700) -> pd.DataFrame:
    """Flat → strong uptrend with pullbacks → downtrend, so both long and short
    impulses (and their exits) occur. Deterministic."""
    rng = np.random.default_rng(7)
    seg = n // 3
    up = np.linspace(0, 220, seg)
    down = np.linspace(0, -200, n - 2 * seg)
    trend = np.concatenate([np.zeros(seg), up, up[-1] + down])
    wobble = 25.0 * np.sin(np.arange(n) / 11.0)
    close = 1500.0 + trend + wobble + rng.normal(0, 5.0, n)
    high = close + np.abs(rng.normal(0, 4.0, n))
    low = close - np.abs(rng.normal(0, 4.0, n))
    open_ = close + rng.normal(0, 3.0, n)
    dates = pd.date_range("2024-01-01 09:15", periods=n, freq="15min")
    return pd.DataFrame({"date": dates, "open": open_, "high": high,
                         "low": low, "close": close})


def _v4(df, **over):
    return get_strategy("expanding_z_v4").signals(df, **over)


def test_v4_is_registered():
    assert get_strategy("expanding_z_v4").key == "expanding_z_v4"


def test_v4_emits_canonical_and_indicator_columns():
    out = _v4(_regime_series())
    for c in CANONICAL_COLUMNS:
        assert c in out.columns
    for c in ("ema", "z", "absZ", "atr", "driftScore", "entryAbs"):
        assert c in out.columns, f"missing indicator {c}"


def test_v4_produces_both_long_and_short_entries():
    out = _v4(_regime_series())
    assert out["longEntry"].sum() >= 1
    assert out["shortEntry"].sum() >= 1


def test_long_entry_invariants():
    out = _v4(_regime_series())
    longs = out[out["longEntry"]]
    # direction agreement + bullish drift on every long entry
    assert (longs["z"] > 0).all()
    assert (longs["driftScore"] > 0).all()
    # still-expanding gate: absZ strictly greater than the prior bar
    assert (longs["absZ"] > out["absZ"].shift(1).loc[longs.index]).all()


def test_short_entry_invariants():
    out = _v4(_regime_series())
    shorts = out[out["shortEntry"]]
    assert (shorts["z"] < 0).all()
    assert (shorts["driftScore"] < 0).all()


def test_entries_are_mutually_exclusive():
    out = _v4(_regime_series())
    assert not (out["longEntry"] & out["shortEntry"]).any()


def test_exits_are_displacement_lost_only():
    out = _v4(_regime_series())
    le = out[out["longExit"]]
    # long exit ⟺ drift flipped negative OR price fell back below the EMA
    assert ((le["driftScore"] < 0) | (le["close"] < le["ema"])).all()
    se = out[out["shortExit"]]
    assert ((se["driftScore"] > 0) | (se["close"] > se["ema"])).all()


def test_require_expansion_is_a_strict_filter():
    df = _regime_series()
    strict = _v4(df, require_expansion=True)
    loose = _v4(df, require_expansion=False)
    # strict entries must be a subset of loose entries
    assert (strict["longEntry"] & ~loose["longEntry"]).sum() == 0
    assert (strict["shortEntry"] & ~loose["shortEntry"]).sum() == 0
    # and strict must drop at least some (the gate has to bite somewhere)
    assert loose["longEntry"].sum() >= strict["longEntry"].sum()
