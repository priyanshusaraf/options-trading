"""simulate() applies the ratchet overlay iff the strategy declares risk_model:
RATCHET_STOP exits fire close-confirmed and fill next-bar open; ratchet label
wins a same-bar tie with a strategy flag; zero/NaN entry ATR falls back to
flags-only for that trade; v3 (no declaration) never produces RATCHET_STOP."""
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
    t0 = dt.datetime(2026, 7, 1, 9, 15)
    return [C(t0 + dt.timedelta(minutes=15 * i), *b) for i, b in enumerate(bars)]


class Inst:
    segment = "NFO"
    lot_size = 10


class StubRatchet(Strategy):
    key = "stub_ratchet"
    display_name = "StubR"
    default_params = {}
    risk_model = {"atr_length": 3, "initial_risk_atr": 1.0, "trail_start_r": 99.0,
                  "trail_atr": 1.0, "use_mfe_capture_floor": False,
                  "capture_start_r": 99.0, "capture_pct": 0.5}
    # trail/floor thresholds set unreachably high -> only the INITIAL stop acts,
    # which makes expected exit bars easy to hand-compute.

    def __init__(self, entries=(), exits=()):
        self._e, self._x = set(entries), set(exits)

    def compute(self, df, **p):
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i in self._e for i in range(n)]
        out["shortEntry"] = [False] * n
        out["longExit"] = [i in self._x for i in range(n)]
        out["shortExit"] = [False] * n
        return out


FAST = {"ema_length": 1, "slope_lookback": 0}

# Tape: TR is 2.0 on every bar (high-low=2, no gaps) -> Wilder ATR == 2.0 exactly.
# entry flag bar 4 -> fill bar 5 open=100 -> risk_pts = 1.0*2 = 2 -> stop 98.
FLAT = (100.0, 101.0, 99.0, 100.0)


def test_ratchet_stop_fires_close_confirmed_and_fills_next_open():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 98.5, 97.9)   # close 97.9 <= stop 98 -> confirmed bar 7
    bars[8] = (97.0, 98.0, 96.0, 97.5)     # exit fills at bar 8 OPEN = 97.0
    strat = StubRatchet(entries={4})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "RATCHET_STOP"
    assert trades[0].entry_price == pytest.approx(100.0)
    assert trades[0].exit_price == pytest.approx(97.0)


def test_wick_through_stop_does_not_exit():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 96.0, 100.0)  # low 96 pierces 98; close 100 survives
    strat = StubRatchet(entries={4})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1 and trades[0].reason == "OPEN_AT_END"


def test_same_bar_tie_labels_ratchet_stop():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 98.5, 97.9)   # stop confirms bar 7 …
    strat = StubRatchet(entries={4}, exits={7})   # … and flag also fires bar 7
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert trades[0].reason == "RATCHET_STOP"     # protective label wins the tie


def test_zero_atr_disables_ratchet_for_that_trade():
    # dead-flat tape: TR == 0 -> ATR == 0 -> ratchet disabled -> flags-only exit
    bars = [(100.0, 100.0, 100.0, 100.0)] * 12
    strat = StubRatchet(entries={4}, exits={8})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "STRATEGY_EXIT"    # not RATCHET_STOP, no crash


def test_undeclared_strategy_never_ratchets():
    from app.strategy.registry import get_strategy
    from app.providers.mock import MockProvider
    from app.core.instruments import get_instrument
    prov = MockProvider()
    inst = get_instrument("NIFTY")
    candles = prov.get_candles(inst, "15minute", 90)
    trades, m = simulate(candles, inst, "15minute")   # default v3, no declaration
    assert all(t.reason in ("STRATEGY_EXIT", "OPEN_AT_END") for t in trades)
