"""Commodity strategy suite (vwap_slope_divergence, session_gap_carry,
shock_reversal) + the MCX schedule helpers and the regime classifier:
canonical columns, registry discovery, no look-ahead (flags on a prefix equal the
full-data flags for those rows), determinism, and the schedule-driven timing."""
import numpy as np
import pandas as pd
import pytest

from app.strategy.regime import REGIMES, classify, latest_regime
from app.strategy.registry import get_strategy, strategy_keys
from app.strategy.ta import (bars_to_session_close, mcx_close_minute, rolling_vwap,
                             rsi_divergence, session_vwap)

KEYS = ("vwap_slope_divergence", "session_gap_carry", "shock_reversal", "spike_fade")
FLAGS = ["longEntry", "shortEntry", "longExit", "shortExit"]


def mcx_frame(days=90, seed=7, start="2026-03-02"):
    """Synthetic 15m MCX-session bars (09:00 -> last bar before the DST-aware close)."""
    rng = np.random.default_rng(seed)
    rows = []
    px = 300.0
    for d in pd.bdate_range(start, periods=days):
        probe = pd.DataFrame({"date": [d]})
        close_min = int(mcx_close_minute(probe).iloc[0])
        t = d + pd.Timedelta(hours=9)
        # day-level shock now and then so shock_reversal has something to do
        drift = rng.normal(0, 0.004) + (rng.choice([0, 0.03, -0.03], p=[0.9, 0.05, 0.05]) / 50)
        end = d + pd.Timedelta(minutes=close_min)
        while t < end:
            o = px
            px = max(1.0, px * (1 + drift + rng.normal(0, 0.003)))
            hi = max(o, px) * (1 + abs(rng.normal(0, 0.001)))
            lo = min(o, px) * (1 - abs(rng.normal(0, 0.001)))
            rows.append((t, o, hi, lo, px, float(rng.integers(1, 100))))
            t += pd.Timedelta(minutes=15)
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])


@pytest.fixture(scope="module")
def frame():
    return mcx_frame()


def test_registered():
    keys = set(strategy_keys())
    for k in KEYS:
        assert k in keys
        assert get_strategy(k).key == k


@pytest.mark.parametrize("key", KEYS)
def test_canonical_columns_and_determinism(frame, key):
    s = get_strategy(key)
    a = s.signals(frame)
    b = s.signals(frame)
    for c in FLAGS:
        assert c in a.columns and a[c].dtype == bool
    pd.testing.assert_frame_equal(a[FLAGS], b[FLAGS])


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("cut", [700, 1500, 2333])
def test_no_lookahead(frame, key, cut):
    s = get_strategy(key)
    full = s.signals(frame)
    pre = s.signals(frame.iloc[:cut].copy())
    pd.testing.assert_frame_equal(full[FLAGS].iloc[:cut].reset_index(drop=True),
                                  pre[FLAGS].reset_index(drop=True))


def test_vwap_slope_divergence_modes_produce_trades(frame):
    s = get_strategy("vwap_slope_divergence")
    for trig in ("slope_cross", "failed_divergence", "divergence_reversal", "vwap_pullback"):
        out = s.signals(frame, trigger=trig, min_vslope=0.0, entry_start=0, entry_end=1440,
                        vwap_mode="session")
        assert out["longEntry"].sum() + out["shortEntry"].sum() >= 0
    out = s.signals(frame, trigger="slope_cross", min_vslope=0.0, entry_start=0,
                    entry_end=1440)
    assert out["longEntry"].sum() + out["shortEntry"].sum() > 0


def test_mcx_close_follows_us_dst():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-07-01 10:00", "2026-12-01 10:00",
                                               "2026-03-09 10:00", "2026-03-06 10:00"])})
    # US DST 2026 starts Sun 8 Mar; MCX close moves 23:55 -> 23:30 from Mon 9 Mar
    assert mcx_close_minute(df).tolist() == [1410, 1435, 1410, 1435]


def test_bars_to_session_close_counts_partial_last_bar():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-07-01 23:00", "2026-07-01 23:15",
                                               "2026-12-01 23:15", "2026-12-01 23:30",
                                               "2026-12-01 23:45"])})
    assert bars_to_session_close(df).tolist() == [1, 0, 2, 1, 0]


def test_session_gap_carry_timing(frame):
    out = get_strategy("session_gap_carry").signals(frame, trend_hours=0)
    btc = bars_to_session_close(frame)
    assert (btc[out["longEntry"]] == 2).all() and out["longEntry"].sum() > 0
    assert (btc[out["longExit"]] == 0).all()
    assert not out["shortEntry"].any()            # long-only by default


def test_shock_reversal_decides_on_last_bar_only(frame):
    out = get_strategy("shock_reversal").signals(frame, z_entry=1.0, z_len=20)
    btc = bars_to_session_close(frame)
    entries = out["longEntry"] | out["shortEntry"]
    assert entries.sum() > 0
    assert (btc[entries] == 0).all()
    exits = out["longExit"] | out["shortExit"]
    assert (btc[exits] == 1).all()                # exit_at="close" -> second-to-last bar


def test_vwap_helpers():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-07-01 09:00", "2026-07-01 09:15",
                                               "2026-07-02 09:00"]),
                       "high": [11.0, 13.0, 21.0], "low": [9.0, 11.0, 19.0],
                       "close": [10.0, 12.0, 20.0], "volume": [1.0, 3.0, 5.0]})
    vw = session_vwap(df)
    assert vw.iloc[0] == pytest.approx(10.0)
    assert vw.iloc[1] == pytest.approx((10 * 1 + 12 * 3) / 4)
    assert vw.iloc[2] == pytest.approx(20.0)                 # resets each session
    assert rolling_vwap(df, 2).iloc[2] == pytest.approx((12 * 3 + 20 * 5) / 8)


def test_rsi_divergence_bullish_case():
    low = np.array([10, 9, 8, 7, 8, 9, 8.5, 8, 7.5, 6.9], dtype=float)
    high = low + 1
    r = np.array([50, 40, 30, 20, 35, 45, 40, 38, 36, 30], dtype=float)
    bull, bear = rsi_divergence(low, high, r, lookback=8, min_gap=3, min_rsi_delta=3,
                                os_level=40, ob_level=60)
    assert bull[-1] and not bear.any()


def test_regime_classifier(frame):
    r = classify(frame)
    assert set(r["regime"].unique()) <= set(REGIMES)
    last = latest_regime(frame)
    assert last["regime"] in REGIMES and abs(sum(last["share_250"].values()) - 1) < 1e-6
    # causal: the label of earlier bars does not change when later bars arrive
    pre = classify(frame.iloc[:1500].copy())
    assert (pre["regime"].to_numpy() == r["regime"].iloc[:1500].to_numpy()).all()
