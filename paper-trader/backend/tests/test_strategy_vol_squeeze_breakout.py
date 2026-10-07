"""vol_squeeze_breakout: canonical contract, no look-ahead, determinism, and an
engine smoke run on synthetic MCX-shaped (09:00-23:00 IST) candles."""
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app.strategy.registry import get_strategy
from app.strategy.registry.base import CANONICAL_COLUMNS
from app.strategy.registry.vol_squeeze_breakout import STRATEGY, VolSqueezeBreakout

FLAG_COLS = CANONICAL_COLUMNS + ("longAdd", "shortAdd")


def _mcx(sessions: int = 60, freq_min: int = 60, seed: int = 7) -> pd.DataFrame:
    """Deterministic MCX-like candles: 09:00-23:00 IST sessions, louder in the
    evening (US hours), alternating quiet coils and directional bursts so the
    squeeze and the breakout both occur."""
    rng = np.random.default_rng(seed)
    rows, px = [], 300.0
    per = (23 * 60 - 9 * 60) // freq_min + 1
    for d in range(sessions):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=d)
        quiet = (d // 3) % 2 == 0           # 3 quiet sessions, then 3 active ones
        drift = 0.0 if quiet else rng.choice([-1.0, 1.0]) * 0.6
        for b in range(per):
            ts = day + pd.Timedelta(minutes=9 * 60 + b * freq_min)
            hour_vol = 2.5 if ts.hour >= 17 else 1.0
            sig = (0.15 if quiet else 1.0) * hour_vol * np.sqrt(freq_min / 60.0)
            o = px
            c = o + drift * np.sqrt(freq_min / 60.0) + rng.normal(0, sig)
            hi = max(o, c) + abs(rng.normal(0, sig * 0.5))
            lo = min(o, c) - abs(rng.normal(0, sig * 0.5))
            rows.append({"date": ts, "open": o, "high": hi, "low": lo, "close": c,
                         "volume": float(rng.uniform(0.5, 1.5) * hour_vol)})
            px = c
    return pd.DataFrame(rows)


def test_registered_with_key_and_label():
    s = get_strategy("vol_squeeze_breakout")
    assert s.key == "vol_squeeze_breakout"
    assert s.display_name == "Volatility Squeeze Breakout"
    assert isinstance(s, VolSqueezeBreakout)


@pytest.mark.parametrize("freq", [15, 30, 60])
def test_canonical_columns_boolean(freq):
    out = STRATEGY.signals(_mcx(freq_min=freq))
    for col in FLAG_COLS:
        assert col in out.columns, col
        assert out[col].dtype == bool, col
    for col in ("atr", "coil", "boxHigh", "boxLow"):
        assert col in out.columns


def test_fires_both_directions_on_synthetic_squeezes():
    out = STRATEGY.signals(_mcx())
    assert out["longEntry"].sum() > 0 and out["shortEntry"].sum() > 0
    # an entry is only ever taken out of a squeeze armed on the previous bar
    armed = out["squeeze"].shift(1, fill_value=False)
    assert not (out["longEntry"] & ~armed).any()
    assert not (out["shortEntry"] & ~armed).any()


def test_works_without_volume_column():
    df = _mcx().drop(columns=["volume"])
    out = STRATEGY.signals(df, min_vol_surge=1.5, vwap_side=True)
    for col in CANONICAL_COLUMNS:
        assert out[col].dtype == bool


@pytest.mark.parametrize("params", [
    {},                                                      # defaults (L1)
    {"min_clv": 0.3, "confirm_bars": 1, "drift_len": 20},    # trigger/direction layers
    {"recoil_len": 8, "time_stop": 20, "exit_box": "far"},   # exit layers
    {"squeeze": "bbkc"}, {"mode": "fade"},
])
def test_no_lookahead_prefix_equals_full(params):
    df = _mcx()
    full = STRATEGY.signals(df, **params)
    assert full[list(CANONICAL_COLUMNS)].to_numpy().any()
    for cut in (200, 431, 650, len(df) - 1):
        part = STRATEGY.signals(df.iloc[:cut].copy(), **params)
        for col in FLAG_COLS:
            assert (part[col].to_numpy() == full[col].iloc[:cut].to_numpy()).all(), \
                f"{col} differs on prefix {cut} ({params})"
        np.testing.assert_allclose(part["coil"].to_numpy(), full["coil"].iloc[:cut].to_numpy(),
                                   equal_nan=True)


def test_deterministic():
    df = _mcx()
    a = STRATEGY.signals(df)
    b = STRATEGY.signals(df.copy())
    pd.testing.assert_frame_equal(a, b)


def test_box_hours_scales_with_timeframe():
    # 30 h box: 30 bars on 60m, 60 bars on 30m -> the same wall-clock box
    s60 = STRATEGY.signals(_mcx(freq_min=60))
    s30 = STRATEGY.signals(_mcx(freq_min=30))
    assert s60["coil"].notna().sum() > 0 and s30["coil"].notna().sum() > 0
    explicit = STRATEGY.signals(_mcx(freq_min=60), box_len=30)
    pd.testing.assert_series_equal(s60["coil"], explicit["coil"])


def test_engine_smoke():
    from app.backtest.engine import simulate
    from app.core.instruments import Instrument
    from app.providers.base import Candle
    df = _mcx()
    candles = [Candle(r.date.to_pydatetime(), r.open, r.high, r.low, r.close, r.volume)
               for r in df.itertuples()]
    inst = Instrument("NATGASMINI", "NATURAL GAS MINI", "MCX", "MCX", "NATGASMINI",
                      "NATGASMINI", lot_size=250, strike_step=5, priority=1,
                      mock_spot=300, mock_vol=0.5)
    trades, _ = simulate(candles, inst, "60m", strategy=STRATEGY,
                         params=dict(STRATEGY.default_params), slippage_pct=0.0004)
    assert len(trades) > 0
    assert all(isinstance(t.entry_time, (int, float)) for t in trades)
    assert all(t.exit_time >= t.entry_time for t in trades)
    assert datetime.fromtimestamp(trades[0].entry_time).year == 2024
