"""simulate() opt-in extensions: volume reaches the strategy, pyramiding adds lots
(one entry order per leg, all legs exit together), session_flat squares off at the
last bar of each day, slippage moves fills against the trade. A strategy that
declares none of them behaves exactly as before."""
import datetime as dt
from dataclasses import dataclass

import pytest

from app.backtest.engine import simulate
from app.engine.charges import compute_charges
from app.strategy.registry.base import Strategy


@dataclass
class C:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class Inst:
    segment = "MCX"
    lot_size = 10


def day(d, n, px=100.0, vol=5.0):
    t0 = dt.datetime(2026, 7, d, 9, 0)
    return [C(t0 + dt.timedelta(minutes=15 * i), px, px + 1, px - 1, px, vol) for i in range(n)]


class Flags(Strategy):
    key = "flags_stub"
    display_name = "flags"
    default_params = {}

    def __init__(self, entries=(), exits=(), adds=(), seen=None):
        self._e, self._x, self._a = set(entries), set(exits), set(adds)
        self.seen = seen

    def compute(self, df, **p):
        if self.seen is not None:
            self.seen.append(list(df.columns))
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i in self._e for i in range(n)]
        out["shortEntry"] = [False] * n
        out["longExit"] = [i in self._x for i in range(n)]
        out["shortExit"] = [False] * n
        out["longAdd"] = [i in self._a for i in range(n)]
        out["shortAdd"] = [False] * n
        return out


FAST = {"ema_length": 1, "slope_lookback": 0}


def test_volume_column_reaches_strategy():
    seen = []
    simulate(day(1, 10), Inst(), "15minute", strategy=Flags(seen=seen), params=FAST)
    assert "volume" in seen[0]


def test_no_declarations_means_single_leg_and_no_square_off():
    cs = day(1, 6) + day(2, 6)
    trades, _ = simulate(cs, Inst(), "15minute", strategy=Flags(entries={1}, exits={9}),
                         params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "STRATEGY_EXIT" and trades[0].lots == 1


def test_pyramiding_adds_legs_and_charges_each_leg():
    cs = day(1, 12)
    cs[4] = C(cs[4].ts, 102.0, 103.0, 101.0, 102.0)      # add fills at 102
    s = Flags(entries={1}, adds={3, 4, 5}, exits={8})
    s.pyramiding = {"max_adds": 2}
    trades, _ = simulate(cs, Inst(), "15minute", strategy=s, params=FAST)
    assert len(trades) == 1
    t = trades[0]
    assert t.lots == 3 and t.qty == 30                    # entry + 2 adds (cap honoured)
    legs = [(100.0, 10), (102.0, 10), (100.0, 10)]
    exp_chg = sum(compute_charges("MCX_FUT", "BUY", px, q)["total"]
                  + compute_charges("MCX_FUT", "SELL", 100.0, q)["total"] for px, q in legs)
    assert t.charges == pytest.approx(exp_chg)
    assert t.gross_pnl == pytest.approx((100.0 - 302.0 / 3) * 30)


def test_adds_ignored_without_declaration():
    s = Flags(entries={1}, adds={3, 4}, exits={8})
    trades, _ = simulate(day(1, 12), Inst(), "15minute", strategy=s, params=FAST)
    assert trades[0].lots == 1


def test_session_flat_squares_off_at_last_bar_close_and_blocks_late_entry():
    cs = day(1, 6) + day(2, 6)
    cs[5] = C(cs[5].ts, 100.0, 101.0, 99.0, 104.0)        # last bar of day 1 closes 104
    s = Flags(entries={1, 5})                              # bar 5 = day-1 last bar
    s.session_flat = True
    trades, _ = simulate(cs, Inst(), "15minute", strategy=s, params=FAST)
    assert trades[0].reason == "SESSION_FLAT"
    assert trades[0].exit_price == pytest.approx(104.0)
    # the entry flagged on the last bar of day 1 must NOT carry into day 2
    assert len(trades) == 1


def test_slippage_moves_both_fills_against_a_long():
    s = Flags(entries={1}, exits={4})
    trades, _ = simulate(day(1, 8), Inst(), "15minute", strategy=s, params=FAST,
                         slippage_pct=0.001)
    t = trades[0]
    assert t.entry_price == pytest.approx(100.1)
    assert t.exit_price == pytest.approx(99.9)
