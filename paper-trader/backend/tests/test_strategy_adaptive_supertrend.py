"""Adaptive SuperTrend (registry key `adaptive_supertrend`): contract, no look-ahead,
determinism and a few source-parity mechanics. Offline, synthetic data only."""
import numpy as np
import pandas as pd
import pytest

from app.strategy.registry import get_strategy
from app.strategy.registry.adaptive_supertrend import (
    FAITHFUL_PARAMS, METHOD_NAMES, _percentrank)
from app.strategy.registry.base import CANONICAL_COLUMNS

FLAGS = list(CANONICAL_COLUMNS) + ["longAdd", "shortAdd"]
STATE = ["liveDir", "activeDir", "activeMethod"]
# a short selection window so auto-selection actually switches on ~1.5k bars
FAST_AUTO = {**FAITHFUL_PARAMS, "bars_per_day": 58, "perf_lookback_days": 3,
             "min_trades": 2, "base_mult": 2.0}


def _synthetic(n: int = 1500, seed: int = 7) -> pd.DataFrame:
    """Trending legs + chop + noise on a 15m MCX-like clock, with tick volume."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    drift = np.where((t // 250) % 2 == 0, 0.25, -0.25)
    close = 300.0 + np.cumsum(drift + rng.normal(0, 1.2, n)) + 8 * np.sin(t / 15.0)
    high = close + np.abs(rng.normal(0, 0.8, n))
    low = close - np.abs(rng.normal(0, 0.8, n))
    open_ = close + rng.normal(0, 0.5, n)
    dates = pd.date_range("2024-01-01 09:00", periods=n, freq="15min")
    vol = rng.uniform(0.2, 2.0, n)
    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low,
                         "close": close, "volume": vol})


@pytest.fixture(scope="module")
def strat():
    return get_strategy("adaptive_supertrend")


def test_registered(strat):
    assert strat.key == "adaptive_supertrend"
    assert strat.display_name == "Adaptive SuperTrend (auto-select)"
    assert strat.warmup_columns == ("activeST",)


@pytest.mark.parametrize("params", [{}, FAITHFUL_PARAMS, FAST_AUTO])
def test_canonical_columns_boolean(strat, params):
    out = strat.signals(_synthetic(), **params)
    for col in FLAGS:
        assert col in out.columns, col
        assert out[col].dtype == bool, col
    assert len(out) == 1500
    assert out["longEntry"].any() and out["shortEntry"].any()


@pytest.mark.parametrize("params", [{}, FAITHFUL_PARAMS, FAST_AUTO])
def test_no_lookahead_prefix_equals_full(strat, params):
    df = _synthetic()
    full = strat.signals(df, **params)
    for k in (400, 777, 1200):
        pre = strat.signals(df.iloc[:k].copy(), **params)
        for col in FLAGS + STATE:
            np.testing.assert_array_equal(pre[col].to_numpy(), full[col].to_numpy()[:k],
                                          err_msg=f"{col} differs on prefix {k}")
        np.testing.assert_allclose(pre["activeST"].to_numpy(),
                                   full["activeST"].to_numpy()[:k], equal_nan=True)


def test_deterministic(strat):
    df = _synthetic()
    a = strat.signals(df, **FAST_AUTO)
    b = strat.signals(df.copy(), **FAST_AUTO)
    pd.testing.assert_frame_equal(a, b)


def test_auto_selection_switches_methods(strat):
    out = strat.signals(_synthetic(), **FAST_AUTO)
    assert out["activeMethod"].nunique() > 1
    assert set(out["activeMethod"].unique()) <= set(range(len(METHOD_NAMES)))
    manual = strat.signals(_synthetic(), **{**FAST_AUTO, "enable_auto": False,
                                            "manual_method": "Z-Score"})
    assert (manual["activeMethod"] == METHOD_NAMES.index("Z-Score")).all()


def test_exit_flags_are_state_based_and_reverse_entry_carries(strat):
    # no TSL / filters -> pure stop-and-reverse, so direct -1 -> +1 reversals occur
    out = strat.signals(_synthetic(), **{**FAITHFUL_PARAMS, "enable_tsl": False,
                                         "enable_rsi": False, "enable_macd": False})
    lv = out["liveDir"].to_numpy()
    assert (out["longExit"].to_numpy() == (lv != 1)).all()
    assert (out["shortExit"].to_numpy() == (lv != -1)).all()
    le = out["longEntry"].to_numpy()
    flips = np.where((lv[1:-1] == 1) & (lv[:-2] == -1) & (lv[2:] == 1))[0] + 1
    assert len(flips) > 0
    for i in flips:   # reversal: entry on the flip bar AND the next (engine fills next)
        assert le[i] and le[i + 1]


def test_percentrank_pine_semantics():
    x = np.array([1.0, 2.0, 3.0, 2.0, 5.0])
    pr = _percentrank(x, 3)
    assert np.isnan(pr[:3]).all()
    # bar 3 (2.0) vs previous [1,2,3] -> 2 of 3 are <= 2.0
    assert pr[3] == pytest.approx(200.0 / 3)
    # bar 4 (5.0) vs previous [2,3,2] -> all <= 5
    assert pr[4] == pytest.approx(100.0)


def test_tsl_exit_close_confirmed(strat):
    out = strat.signals(_synthetic(), **FAITHFUL_PARAMS)
    lv = out["liveDir"].to_numpy()
    tsl = out["tsl"].to_numpy()
    c = out["close"].to_numpy()
    # every long -> flat transition without a bear signal is a close below the prior TSL
    for i in np.where((lv[1:] == 0) & (lv[:-1] == 1))[0] + 1:
        if not out["bearSignal"].iloc[i]:
            assert c[i] < tsl[i - 1]
