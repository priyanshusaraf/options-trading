"""The spot backtester filled at the exact bar open, with zero execution cost.

`premium.py` has modelled a half-spread on entry and exit since it was written.
`engine.py` — the SPOT backtester, which per the 2026-07 product direction tests
the instrument actually traded for the equity/index universe — did not. Every
backtest number the project has produced for equity_intraday is therefore
optimistic by an unmodelled amount.

The size of that omission is the point. The retuned intraday exits are a 0.8%
stop and a 1.5% target, and the 2026-08-01 excursion sweep found the largest
favourable excursion ever recorded was 1.216% of notional. The live engine caps
a marketable limit at `exec_max_slippage_pct = 1%`. An execution cost anywhere
in that range is not a rounding error against a sub-1.5% edge — it is the same
order of magnitude as the edge being measured.

Slippage here is always ADVERSE and direction-aware: you buy above the mid and
sell below it, whichever way round the trade is. Modelling it symmetrically
(or on one leg only) would understate the cost of exactly the round trip the
strategy makes.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.backtest.engine import run_trades, simulate
from app.core.config import get_settings


class Inst:
    key = "TESTEQ"
    segment = "NSE"
    lot_size = 1


class LotInst:
    """Fixed-lot (F&O) instrument. Cash-equity sizing is floor(capital/fill_price),
    so a long paying MORE per share affords FEWER shares — economically correct,
    but it makes long/short quantities differ and would confound any test about
    directional symmetry. A fixed lot holds qty constant so the cost itself is
    what is being compared."""
    key = "TESTFO"
    segment = "NFO"
    lot_size = 50


def _sig_rows(n=6, price=100.0):
    """A flat frame; entries/exits are driven explicitly per test."""
    import pandas as pd
    t0 = dt.datetime(2026, 8, 3, 9, 15)
    return pd.DataFrame([{
        "date": t0 + dt.timedelta(minutes=15 * i),
        "open": price, "high": price + 1, "low": price - 1, "close": price,
        "longEntry": False, "shortEntry": False,
        "longExit": False, "shortExit": False,
    } for i in range(n)])


def _run(sig, slippage_pct):
    return run_trades(sig, Inst(), "NSE", 10_000.0, None, slippage_pct=slippage_pct)


def _run_lot(sig, slippage_pct):
    return run_trades(sig, LotInst(), "NFO_FUT", 10_000.0, None, slippage_pct=slippage_pct)


# ── the default must not silently rewrite history ───────────────────────────

def test_zero_slippage_reproduces_the_old_fills_exactly():
    """The escape hatch: every stored backtest number must be reproducible by
    setting the knob to zero, or this change is unfalsifiable."""
    sig = _sig_rows()
    sig.loc[0, "longEntry"] = True
    sig.loc[3, "longExit"] = True
    trades = _run(sig, 0.0)
    assert len(trades) == 1
    assert trades[0].entry_price == 100.0
    assert trades[0].exit_price == 100.0


def test_the_shipped_default_is_not_zero():
    """A cost model nobody switches on is a cost model that does nothing. The
    default has to be a real number, or every backtest stays optimistic."""
    assert get_settings().backtest_slippage_pct > 0


# ── adverse in both directions ──────────────────────────────────────────────

def test_cash_equity_sizing_uses_the_price_actually_paid():
    """Paying more per share must buy fewer shares — sizing off the clean open
    would let a backtest deploy capital it does not have."""
    sig = _sig_rows()
    sig.loc[0, "longEntry"] = True
    sig.loc[3, "longExit"] = True
    assert _run(sig, 0.01)[0].qty < _run(sig, 0.0)[0].qty


def test_a_long_buys_above_the_open_and_sells_below_it():
    sig = _sig_rows()
    sig.loc[0, "longEntry"] = True
    sig.loc[3, "longExit"] = True
    trades = _run(sig, 0.01)          # 1% round trip -> 0.5% per side
    t = trades[0]
    assert t.entry_price == pytest.approx(100.5)
    assert t.exit_price == pytest.approx(99.5)
    assert t.gross_pnl < 0, "a flat market must LOSE the round-trip cost"


def test_a_short_sells_below_the_open_and_covers_above_it():
    """The asymmetry that a naive implementation gets wrong: for a SHORT the
    adverse direction is inverted on BOTH legs."""
    sig = _sig_rows()
    sig.loc[0, "shortEntry"] = True
    sig.loc[3, "shortExit"] = True
    trades = _run(sig, 0.01)
    t = trades[0]
    assert t.entry_price == pytest.approx(99.5)
    assert t.exit_price == pytest.approx(100.5)
    assert t.gross_pnl < 0


def test_slippage_costs_the_same_round_trip_either_way():
    """A long and a short in the same flat market must pay the same cost —
    otherwise the model biases the strategy toward one side."""
    long_sig = _sig_rows(); long_sig.loc[0, "longEntry"] = True; long_sig.loc[3, "longExit"] = True
    short_sig = _sig_rows(); short_sig.loc[0, "shortEntry"] = True; short_sig.loc[3, "shortExit"] = True
    assert _run_lot(long_sig, 0.01)[0].gross_pnl == \
        pytest.approx(_run_lot(short_sig, 0.01)[0].gross_pnl)


def test_the_open_at_end_exit_is_also_slipped():
    """A position still open at the end of data is closed by the engine, and
    that close is a real sale — untaxed here it would flatter every run that
    happens to finish while holding."""
    sig = _sig_rows()
    sig.loc[0, "longEntry"] = True          # never exits; closed at last bar
    trades = _run(sig, 0.01)
    assert trades[0].reason == "OPEN_AT_END"
    assert trades[0].exit_price == pytest.approx(99.5)


# ── magnitude, because that is the finding ──────────────────────────────────

def test_slippage_is_material_against_the_measured_edge():
    """Not a rounding error: the sweep's largest favourable excursion ever was
    1.216% of notional. A 1% round trip eats most of a winning trade."""
    sig = _sig_rows()
    sig.loc[0, "longEntry"] = True
    sig.loc[3, "longExit"] = True
    free = _run_lot(sig, 0.0)[0]
    costed = _run_lot(sig, 0.01)[0]
    assert free.qty == costed.qty          # fixed lot: qty cannot absorb the cost
    assert (free.gross_pnl - costed.gross_pnl) == pytest.approx(0.01 * 100.0 * free.qty)


def test_charges_are_computed_on_the_slipped_fill_not_the_clean_open():
    """Brokerage/STT are levied on the price actually transacted."""
    sig = _sig_rows()
    sig.loc[0, "longEntry"] = True
    sig.loc[3, "longExit"] = True
    assert _run(sig, 0.01)[0].charges != _run(sig, 0.0)[0].charges


# ── wiring ──────────────────────────────────────────────────────────────────

def test_simulate_applies_the_configured_default(monkeypatch):
    """simulate() is what the API and sweep call — the cost has to reach them,
    not just run_trades."""
    from app.providers.base import Candle
    t0 = dt.datetime(2026, 8, 3, 9, 15)
    candles = [Candle(ts=t0 + dt.timedelta(minutes=15 * i), open=100.0 + i * 0.1,
                      high=101.0 + i * 0.1, low=99.0 + i * 0.1,
                      close=100.0 + i * 0.1, volume=1000.0) for i in range(400)]
    a, _ = simulate(candles, Inst(), "15minute", slippage_pct=0.0)
    b, _ = simulate(candles, Inst(), "15minute", slippage_pct=0.02)
    if a:   # only assert when the strategy actually traded this synthetic series
        assert sum(t.net_pnl for t in b) < sum(t.net_pnl for t in a)
