"""The primitive block library: hand-written, unit-tested pure predicates over the
candle frame. The composition builder only ever *references* these by name — it never
writes indicator math — so every generated strategy is auditable down to vetted blocks.

Each block is `(df, *numeric_params) -> bool Series`, indexed like df, warmup-safe
(NaN comparisons yield False, never a spurious True or a NaN)."""
import datetime as dt

import pandas as pd

from research.strategy.builder import blocks


def _df(closes, highs=None, lows=None):
    n = len(closes)
    base = dt.datetime(2024, 1, 1, 9, 15)
    highs = highs if highs is not None else [c + 0.5 for c in closes]
    lows = lows if lows is not None else [c - 0.5 for c in closes]
    return pd.DataFrame({
        "date": [base + dt.timedelta(minutes=15 * i) for i in range(n)],
        "open": list(closes), "high": highs, "low": lows, "close": list(closes),
    })


UP = _df(list(range(1, 61)))
DOWN = _df(list(range(60, 0, -1)))


def test_ema_slope_direction():
    assert bool(blocks.ema_slope_up(UP, 20, 5).iloc[-1]) is True
    assert bool(blocks.ema_slope_up(DOWN, 20, 5).iloc[-1]) is False
    assert bool(blocks.ema_slope_down(DOWN, 20, 5).iloc[-1]) is True
    assert bool(blocks.ema_slope_down(UP, 20, 5).iloc[-1]) is False


def test_price_vs_ema():
    assert bool(blocks.price_above_ema(UP, 20).iloc[-1]) is True
    assert bool(blocks.price_below_ema(UP, 20).iloc[-1]) is False
    assert bool(blocks.price_below_ema(DOWN, 20).iloc[-1]) is True


def test_zscore_threshold_and_cross():
    assert bool(blocks.zscore_gt(UP, 20, 0.0).iloc[-1]) is True
    assert bool(blocks.zscore_lt(UP, 20, 0.0).iloc[-1]) is False
    assert bool(blocks.zscore_lt(DOWN, 20, 0.0).iloc[-1]) is True
    # a cross fires on at most a handful of bars, never every bar
    xs = blocks.zscore_cross_up(UP, 20, 0.5)
    assert xs.dtype == bool and xs.sum() < len(xs)


def test_roc_direction():
    assert bool(blocks.roc_gt(UP, 10, 0.0).iloc[-1]) is True
    assert bool(blocks.roc_lt(DOWN, 10, 0.0).iloc[-1]) is True


def test_volatility_gates_are_boolean():
    for s in (blocks.atr_pct_lt(UP, 14, 100.0), blocks.range_atr_lt(UP, 14, 5.0)):
        assert s.dtype == bool and not s.isna().any()


def test_still_expanding_z_is_boolean():
    s = blocks.still_expanding_z(UP, 20)
    assert s.dtype == bool and not s.isna().any()


def test_every_block_returns_clean_boolean_series():
    """Warmup safety contract: every block returns a bool Series, df-indexed, with no
    NaN — so & / | composition can never leak a NaN or a phantom True into a signal."""
    assert len(blocks.BLOCKS) >= 12
    for name, spec in blocks.BLOCKS.items():
        s = spec.fn(UP, *spec.sample_args)
        assert isinstance(s, pd.Series), name
        assert s.dtype == bool, name
        assert not s.isna().any(), name
        assert list(s.index) == list(UP.index), name


def test_warmup_window_produces_no_signal():
    # during the rolling-std warmup the z-score is 0, so a +thr cross cannot fire
    s = blocks.zscore_cross_up(UP, 20, 1.0)
    assert not s.iloc[:19].any()
