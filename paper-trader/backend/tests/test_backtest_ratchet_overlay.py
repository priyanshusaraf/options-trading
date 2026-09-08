"""simulate() applies the ratchet overlay iff the strategy declares risk_model:
RATCHET_STOP exits fire close-confirmed and fill next-bar open; ratchet label
wins a same-bar tie with a strategy flag; zero/NaN entry ATR falls back to
flags-only for that trade; v3 (no declaration) never produces RATCHET_STOP."""
import datetime as dt
from dataclasses import dataclass

import pytest

from app.backtest.engine import simulate
from app.strategy.registry.base import Strategy

# Execution cost is pinned to ZERO throughout this file. These tests identify WHICH
# BAR a fill landed on by its price ("bar 5 OPEN, not bar 4 close"), so the shipped
# slippage default (Settings.backtest_slippage_pct, added 2026-08-01) would confound
# the very assertion being made. Cost has its own coverage in test_backtest_slippage.py;
# here the subject is timing.



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
                         strategy=strat, params=FAST, slippage_pct=0.0)
    assert len(trades) == 1
    assert trades[0].reason == "RATCHET_STOP"
    assert trades[0].entry_price == pytest.approx(100.0)
    assert trades[0].exit_price == pytest.approx(97.0)


def test_wick_through_stop_does_not_exit():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 96.0, 100.0)  # low 96 pierces 98; close 100 survives
    strat = StubRatchet(entries={4})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST, slippage_pct=0.0)
    assert len(trades) == 1 and trades[0].reason == "OPEN_AT_END"


def test_same_bar_tie_labels_ratchet_stop():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 98.5, 97.9)   # stop confirms bar 7 …
    strat = StubRatchet(entries={4}, exits={7})   # … and flag also fires bar 7
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST, slippage_pct=0.0)
    assert trades[0].reason == "RATCHET_STOP"     # protective label wins the tie


def test_zero_atr_disables_ratchet_for_that_trade():
    # dead-flat tape: TR == 0 -> ATR == 0 -> ratchet disabled -> flags-only exit
    bars = [(100.0, 100.0, 100.0, 100.0)] * 12
    strat = StubRatchet(entries={4}, exits={8})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST, slippage_pct=0.0)
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


def _reversal_tape():
    import pandas as pd
    bars = [(100, 102, 98, 101), (110, 112, 108, 111),
            (120, 123, 117, 119), (115, 118, 112, 114)]
    candles = mk_candles(bars)
    return pd.DataFrame([dict(date=c.ts, open=c.open, high=c.high, low=c.low, close=c.close,
                              longEntry=i == 0, shortEntry=i == 1,
                              longExit=False, shortExit=False, _ratchet_atr=2.0)
                         for i, c in enumerate(candles)])


def test_opt_in_reverses_fill_bar_pulse_at_next_open_in_one_unit():
    from app.backtest.engine import run_trades
    tape = _reversal_tape()
    legacy = run_trades(tape, Inst(), 'NFO_FUT', 50000, None, event_risk=False, slippage_pct=0)
    assert [(t.direction, t.qty, t.entry_price, t.exit_price) for t in legacy] == [('LONG', 10, 110, 114)]
    trades = run_trades(tape, Inst(), 'NFO_FUT', 50000, None, event_risk=False,
                        slippage_pct=0, replay_policy='pine-reversal-fixed-unit/1')
    assert [(t.direction, t.qty, t.entry_price, t.exit_price) for t in trades] == [
        ('LONG', 1, 110, 120), ('SHORT', 1, 120, 114)]
    assert [trade.lots for trade in trades] == [0, 0]
    assert [trade.notional for trade in trades] == [110, 120]
    assert trades[0].exit_time == trades[1].entry_time
    assert trades[0].reason == 'STRATEGY_REVERSAL'
    assert trades[1].reason == 'OPEN_AT_END'


def _pine_run(tape, rm=None, **kwargs):
    from app.backtest.engine import run_trades
    return run_trades(tape, Inst(), 'NFO_FUT', 50000, rm,
                      replay_policy='pine-reversal-fixed-unit/1', slippage_pct=kwargs.pop('slippage_pct', 0),
                      event_risk=kwargs.pop('event_risk', False), **kwargs)


@pytest.mark.parametrize('signal_index', [1, 2])
def test_reversal_is_next_open_and_symmetric(signal_index):
    tape = _reversal_tape()
    tape['shortEntry'] = False
    tape.loc[signal_index, 'shortEntry'] = True
    trades = _pine_run(tape)
    assert len(trades) == 2
    assert trades[0].exit_price == tape.loc[signal_index + 1, 'open']
    assert trades[0].exit_time == trades[1].entry_time
    mirror = tape.copy()
    mirror['longEntry'], mirror['shortEntry'] = tape['shortEntry'], tape['longEntry']
    mirrored = _pine_run(mirror)
    assert [(t.direction, t.entry_price, t.exit_price) for t in mirrored] == [
        ('SHORT', trades[0].entry_price, trades[0].exit_price),
        ('LONG', trades[1].entry_price, trades[1].exit_price)]


def test_reversal_terminal_pulse_never_invents_next_open():
    tape = _reversal_tape()
    tape['shortEntry'] = False
    tape.loc[3, 'shortEntry'] = True
    trades = _pine_run(tape)
    assert len(trades) == 1
    assert trades[0].exit_price == 114
    assert trades[0].reason == 'OPEN_AT_END'


def test_reversal_applies_each_adverse_fill_and_each_charge(monkeypatch):
    from app.backtest import engine
    original = engine.compute_charges_exact
    calls = []
    def recorded(segment, side, price, qty, **kwargs):
        result = original(segment, side, price, qty, **kwargs)
        calls.append((side, price, qty, result['total_minor']))
        return result
    monkeypatch.setattr(engine, 'compute_charges_exact', recorded)
    trades = _pine_run(_reversal_tape(), slippage_pct=0.02)
    assert [(t.entry_price, t.exit_price) for t in trades] == pytest.approx([(111.1, 118.8), (118.8, 115.14)])
    assert [(side, qty) for side, _, qty, _ in calls] == [('BUY', 1), ('SELL', 1), ('SELL', 1), ('BUY', 1)]
    for i, trade in enumerate(trades):
        assert trade.charges == (calls[2*i][3] + calls[2*i+1][3]) / 100
        assert trade.net_pnl == pytest.approx(trade.gross_pnl - trade.charges)
    assert trades[0].gross_pnl == pytest.approx(7.7)
    assert trades[1].gross_pnl == pytest.approx(3.66)


def test_reversal_event_gate_blocks_replacement_not_old_close(monkeypatch):
    from app.backtest import engine
    tape = _reversal_tape()
    monkeypatch.setattr(engine, '_event_blocked_bar', lambda inst, row, product: row['open'] == 120)
    trades = _pine_run(tape, event_risk=True)
    assert len(trades) == 1
    assert trades[0].reason == 'STRATEGY_REVERSAL'
    assert trades[0].exit_price == 120


def test_reversal_resets_ratchet_and_does_not_manage_replacement_fill_bar():
    tape = _reversal_tape()
    # Long risk=2 at110; short replacement risk=10 at120. Its fill-bar close131
    # must not manage the new short, and the following close125 is below stop130.
    tape.loc[2, ['high', 'low', 'close', '_ratchet_atr']] = [132, 117, 131, 10]
    tape.loc[3, ['open', 'high', 'low', 'close', '_ratchet_atr']] = [126, 127, 124, 125, 10]
    tape.loc[4] = {**tape.loc[3].to_dict(), 'date': tape.loc[3, 'date'] + dt.timedelta(minutes=15),
                   'open': 127, 'high': 129, 'low': 126, 'close': 128}
    trades = _pine_run(tape, StubRatchet.risk_model)
    assert len(trades) == 2
    assert trades[0].reason == 'STRATEGY_REVERSAL'
    assert trades[1].reason == 'OPEN_AT_END'
    assert trades[1].exit_price == 128
    assert trades[1].mae_pct == pytest.approx(10)


def test_reversal_future_mutation_preserves_earlier_completed_trade():
    tape = _reversal_tape()
    original = _pine_run(tape)[0]
    changed = tape.copy()
    changed.loc[3, ['open', 'high', 'low', 'close']] = [200, 210, 190, 205]
    assert _pine_run(changed)[0] == original
    assert _pine_run(tape.iloc[:3])[0] == original
    assert _pine_run(tape)[0] == original  # repeat has no accumulated state


def test_replay_policy_refuses_unknown_policy_and_conflicting_entries():
    from app.backtest.engine import run_trades
    tape = _reversal_tape()
    with pytest.raises(ValueError, match='BACKTEST_REPLAY_POLICY_UNSUPPORTED'):
        run_trades(tape, Inst(), 'NFO_FUT', 50000, None, replay_policy='unknown')
    tape.loc[0, 'shortEntry'] = True
    with pytest.raises(ValueError, match='PINE_REPLAY_CONFLICTING_ENTRIES'):
        _pine_run(tape)
    legacy = run_trades(tape, Inst(), 'NFO_FUT', 50000, None, slippage_pct=0, event_risk=False)
    assert legacy[0].direction == 'LONG'  # legacy priority remains untouched


def test_simulate_forwards_explicit_replay_policy():
    class Reversing(StubRatchet):
        risk_model = None
        replay_policy = 'pine-reversal-fixed-unit/1'
        def compute(self, df, **p):
            result = super().compute(df, **p)
            result['shortEntry'] = [i == 1 for i in range(len(df))]
            return result
    tape = _reversal_tape()
    candles = [C(row.date, row.open, row.high, row.low, row.close) for row in tape.itertuples()]
    trades, _ = simulate(candles, Inst(), '15minute', strategy=Reversing(entries={0}), params=FAST, slippage_pct=0)
    assert len(trades) == 2
    assert [trade.qty for trade in trades] == [1, 1]


@pytest.mark.parametrize('policy', [None, 'pine-reversal-fixed-unit/1'])
def test_event_gate_preserves_legacy_sizing_order_and_blocks_initial_fill(monkeypatch, policy):
    from app.backtest import engine
    calls = []
    original_position = engine._position
    def position(*args):
        calls.append('position')
        return original_position(*args)
    def blocked(*args):
        calls.append('event')
        return True
    monkeypatch.setattr(engine, '_position', position)
    monkeypatch.setattr(engine, '_event_blocked_bar', blocked)
    assert engine.run_trades(_reversal_tape(), Inst(), 'NFO_FUT', 50000, None,
                             event_risk=True, slippage_pct=0, replay_policy=policy) == []
    assert calls == (['position', 'event', 'position', 'event'] if policy is None else ['event', 'event'])


def test_fixed_unit_cash_metadata_does_not_use_cash_budget():
    from app.backtest.engine import run_trades
    class Cash:
        segment = 'NSE'
        lot_size = 1
    trades = run_trades(_reversal_tape(), Cash(), 'NSE_EQ', 50000, None,
                        event_risk=False, slippage_pct=0, replay_policy='pine-reversal-fixed-unit/1')
    assert [trade.qty for trade in trades] == [1, 1]
    assert [trade.lots for trade in trades] == [1, 1]


@pytest.mark.parametrize('policy', [None, 'pine-reversal-fixed-unit/1'])
def test_canonical_cash_charge_segment_keeps_equity_event_product(monkeypatch, policy):
    from app.backtest import engine
    class Cash:
        segment = 'NSE'
        lot_size = 1
    products = []
    monkeypatch.setattr(engine, '_event_blocked_bar', lambda inst, row, product: products.append(product) or True)
    trades = engine.run_trades(_reversal_tape(), Cash(), 'NSE_EQ', 50000, None,
                               event_risk=True, slippage_pct=0, replay_policy=policy)
    assert trades == []
    assert products == ['equity_intraday', 'equity_intraday']


def test_simulate_short_history_returns_no_trade_under_replay_policy():
    strategy = StubRatchet(entries={0})
    strategy.replay_policy = 'pine-reversal-fixed-unit/1'
    trades, metrics = simulate(mk_candles([FLAT]), Inst(), '15minute', strategy=strategy,
                               params=FAST, slippage_pct=0)
    assert trades == []
    assert metrics.trades == 0


def test_simulate_empty_signals_retains_only_observed_benchmark():
    import pandas as pd
    strategy = StubRatchet(entries={0})
    strategy.replay_policy = 'pine-reversal-fixed-unit/1'
    trades, metrics = simulate(mk_candles([FLAT] * 4), Inst(), '15minute', strategy=strategy,
                               params=FAST, slippage_pct=0, signals=pd.DataFrame())
    assert trades == []
    assert metrics.bh_return_pct == 0
    assert len(metrics.bh_curve) == 2
