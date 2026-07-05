"""Fill model: a signal confirmed on bar i fills at bar i+1's OPEN (Pine
process_orders_on_close=false parity). Applies to entries, strategy-flag exits,
and (Task 4) ratchet stops. A last-bar signal goes unfilled; a still-open
position closes OPEN_AT_END at the last close."""
import datetime as dt
from dataclasses import dataclass

import pytest

from app.backtest.engine import simulate
from app.strategy.registry.base import Strategy


@dataclass
class C:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float


def mk_candles(bars):
    """bars = list of (open, high, low, close); 15-minute spacing."""
    t0 = dt.datetime(2026, 7, 1, 9, 15)
    return [C(t0 + dt.timedelta(minutes=15 * i), *b) for i, b in enumerate(bars)]


class Inst:
    segment = "NFO"
    lot_size = 10


class StubFlags(Strategy):
    """Entry/exit flags at fixed row positions; no indicator columns."""
    key = "stub_flags"
    display_name = "Stub"
    default_params = {}

    def __init__(self, entries=(), exits=(), shorts=False):
        self._e, self._x, self._s = set(entries), set(exits), shorts

    def compute(self, df, **p):
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i in self._e and not self._s for i in range(n)]
        out["shortEntry"] = [i in self._e and self._s for i in range(n)]
        out["longExit"] = [i in self._x for i in range(n)]
        out["shortExit"] = [i in self._x for i in range(n)]
        return out


FAST = {"ema_length": 1, "slope_lookback": 0}   # warmup = 1+0+2 = 3 bars

BARS = [(100, 101, 99, 100.5)] * 12             # flat tape; opens distinct below


def test_entry_and_exit_fill_at_next_bar_open():
    bars = list(BARS)
    bars[5] = (105.0, 106, 104, 105.5)   # bar 5 open — entry fill expected here
    bars[8] = (108.0, 109, 107, 108.5)   # bar 8 open — exit fill expected here
    candles = mk_candles(bars)
    strat = StubFlags(entries={4}, exits={7})
    trades, m = simulate(candles, Inst(), "15minute", strategy=strat, params=FAST)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_price == pytest.approx(105.0)      # bar 5 OPEN, not bar 4 close
    assert t.exit_price == pytest.approx(108.0)       # bar 8 OPEN, not bar 7 close
    assert t.reason == "STRATEGY_EXIT"
    assert t.bars_held == 3                            # fill bar 5 -> fill bar 8


def test_last_bar_entry_signal_goes_unfilled():
    strat = StubFlags(entries={11})
    trades, m = simulate(mk_candles(list(BARS)), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert trades == []


def test_last_bar_exit_flag_becomes_open_at_end_at_last_close():
    strat = StubFlags(entries={4}, exits={11})
    trades, m = simulate(mk_candles(list(BARS)), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "OPEN_AT_END"
    assert trades[0].exit_price == pytest.approx(100.5)   # LAST CLOSE


def test_exit_flag_on_fill_bar_is_ignored_until_next_bar():
    # exit flag raised on the fill bar itself (bar 5) must NOT exit that bar —
    # management starts the bar AFTER the fill (Pine canManage). The flag is
    # still true on bar 6 here, so the exit confirms on 6 and fills on 7's open.
    bars = list(BARS)
    bars[7] = (103.0, 104, 102, 103.5)
    candles = mk_candles(bars)
    strat = StubFlags(entries={4}, exits={5, 6})
    trades, m = simulate(candles, Inst(), "15minute", strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].exit_price == pytest.approx(103.0)   # bar 7 open
    assert trades[0].bars_held == 2


def test_short_side_fills_mirror():
    bars = list(BARS)
    bars[5] = (95.0, 96, 94, 95.5)
    candles = mk_candles(bars)
    strat = StubFlags(entries={4}, exits={8}, shorts=True)
    trades, m = simulate(candles, Inst(), "15minute", strategy=strat, params=FAST)
    assert len(trades) == 1 and trades[0].direction == "SHORT"
    assert trades[0].entry_price == pytest.approx(95.0)
