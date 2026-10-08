"""gold_month_turn: registry discovery, canonical bool columns, determinism, no
look-ahead (flags on a data prefix equal the full-data flags for those rows) and
the calendar timing (enter on the last business day's penultimate bar, exit on
the first live-window bar of the 3rd session of the new month)."""
import numpy as np
import pandas as pd
import pytest

from app.strategy.registry import get_strategy, strategy_keys
from app.strategy.registry.gold_month_turn import _bdays_left_in_month
from app.strategy.ta import bars_to_session_close, mcx_close_minute

KEY = "gold_month_turn"
FLAGS = ["longEntry", "shortEntry", "longExit", "shortExit"]


def mcx_frame(days=110, seed=11, start="2026-03-02", freq_min=15):
    """Synthetic MCX-session bars (09:00 -> the DST-aware close) on business days."""
    rng = np.random.default_rng(seed)
    rows = []
    px = 13000.0
    for d in pd.bdate_range(start, periods=days):
        close_min = int(mcx_close_minute(pd.DataFrame({"date": [d]})).iloc[0])
        t = d + pd.Timedelta(hours=9)
        end = d + pd.Timedelta(minutes=close_min)
        while t < end:
            o = px
            px = max(1.0, px * (1 + rng.normal(0, 0.0015)))
            hi = max(o, px) * (1 + abs(rng.normal(0, 0.0004)))
            lo = min(o, px) * (1 - abs(rng.normal(0, 0.0004)))
            rows.append((t, o, hi, lo, px, float(rng.integers(1, 100))))
            t += pd.Timedelta(minutes=freq_min)
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])


@pytest.fixture(scope="module")
def frame():
    return mcx_frame()


PARAM_SETS = [
    {},                                              # default (L1 only)
    {"exit_at": "next_open"},
    {"exit_at": "close", "hold_sessions": 3},
    {"short_bday": 5, "short_z": -9.0},              # L2 switched on (fires every month)
]


def test_registered():
    assert KEY in strategy_keys()
    s = get_strategy(KEY)
    assert s.key == KEY and s.display_name


@pytest.mark.parametrize("params", PARAM_SETS)
def test_canonical_columns_and_determinism(frame, params):
    s = get_strategy(KEY)
    a = s.signals(frame, **params)
    b = s.signals(frame, **params)
    for c in FLAGS:
        assert c in a.columns and a[c].dtype == bool
    pd.testing.assert_frame_equal(a[FLAGS], b[FLAGS])
    assert a["longEntry"].sum() >= 4            # one per month turn in ~5 months


@pytest.mark.parametrize("params", PARAM_SETS)
@pytest.mark.parametrize("cut", [500, 1333, 2100, 3000])
def test_no_lookahead(frame, params, cut):
    s = get_strategy(KEY)
    full = s.signals(frame, **params)
    pre = s.signals(frame.iloc[:cut].copy(), **params)
    pd.testing.assert_frame_equal(full[FLAGS].iloc[:cut].reset_index(drop=True),
                                  pre[FLAGS].reset_index(drop=True))


def test_bdays_left_is_calendar_only():
    d = pd.Series(pd.to_datetime(["2026-03-31", "2026-03-30", "2026-03-25", "2026-04-30",
                                  "2026-05-29", "2026-05-28"]))
    # 2026-03-31 Tue (last bday), 03-30 Mon (1 left), 03-25 Wed (4 left: 26,27,30,31);
    # 2026-05-29 Fri is the last bday of May (31st is a Sunday)
    assert _bdays_left_in_month(d).tolist() == [0, 1, 4, 0, 0, 1]


def test_entry_and_exit_timing(frame):
    out = get_strategy(KEY).signals(frame)
    to_close = bars_to_session_close(out)
    ent = out[out["longEntry"]]
    # every entry sits on the penultimate bar of a month's last business day
    assert (to_close[ent.index] == 1).all()
    assert (ent["bdaysLeft"] == 0).all()
    assert set(pd.to_datetime(ent["date"]).dt.strftime("%Y-%m-%d")) >= {
        "2026-03-31", "2026-04-30", "2026-05-29", "2026-06-30"}
    # the exit after the March turn: 3rd session of April (Apr 1, Apr 2 held; Apr 3)
    # on the first bar ending >= 09:30 IST
    ex = pd.to_datetime(out.loc[out["longExit"], "date"])
    april = ex[(ex >= "2026-04-01") & (ex < "2026-04-10")]
    assert april.iloc[0] == pd.Timestamp("2026-04-03 09:15")
    assert not out["shortEntry"].any()           # L2 off by default


def test_engine_fills_long_only_across_month_turn(frame):
    from app.backtest.engine import simulate
    from app.core.instruments import Instrument
    from app.providers.base import Candle
    inst = Instrument("GOLDPETAL", "GOLD PETAL", "MCX", "MCX", "GOLDPETAL", "GOLDPETAL",
                      lot_size=1, strike_step=100, priority=2, mock_spot=9000, mock_vol=0.15)
    candles = [Candle(r.date.to_pydatetime(), r.open, r.high, r.low, r.close, r.volume)
               for r in frame.itertuples()]
    trades, _ = simulate(candles, inst, "15m", strategy=get_strategy(KEY))
    assert trades and all(t.direction == "LONG" for t in trades)
    # entries fill at the open of the last bar of the month's last business day
    for t in trades:
        ts = pd.Timestamp(t.entry_time, unit="s", tz="UTC").tz_convert("Asia/Kolkata")
        assert _bdays_left_in_month(pd.Series([ts.tz_localize(None)])).iloc[0] == 0
        assert ts.hour >= 23
