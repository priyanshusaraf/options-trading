"""audit H16: booking a partial MIS-equity close. Direction-aware P&L, proportional
cost/charge split, and the cash invariant exact to the paisa (a SHORT profits when
price falls — the failure mode of copying the options long-only formula)."""
import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.broker import PaperBroker


def _broker():
    init_db(reset=True)
    from app.providers.mock import MockProvider
    return PaperBroker(MockProvider())


def _now():
    return dt.datetime(2026, 7, 10, 10, 0)


def test_partial_close_equity_long_keeps_invariant_and_splits_cost():
    b = _broker()
    inst = get_instrument("NIFTY")
    pos = b.open_equity_position(inst, "LONG", 100.0, 100, "NSE_INTRADAY", "t", _now(), params={})
    original_cost = pos.entry_cost
    tr = b.book_partial_close_equity(pos, 40, 105.0, "PARTIAL", _now())
    assert b.reconcile()["diff"] == 0.0                       # paisa-exact
    assert pos.qty == 60                                       # remainder open
    assert tr.qty == 40 and tr.gross_pnl == pytest.approx((105.0 - 100.0) * 40)
    assert tr.entry_cost + pos.entry_cost == pytest.approx(original_cost)   # split adds back


def test_partial_close_equity_short_profits_when_price_falls():
    b = _broker()
    inst = get_instrument("NIFTY")
    pos = b.open_equity_position(inst, "SHORT", 100.0, 100, "NSE_INTRADAY", "t", _now(), params={})
    tr = b.book_partial_close_equity(pos, 50, 95.0, "PARTIAL", _now())   # covered lower
    assert tr.gross_pnl == pytest.approx((100.0 - 95.0) * 50)            # SHORT: (entry-exit)*qty
    assert tr.net_pnl > 0
    assert b.reconcile()["diff"] == 0.0


def test_partial_close_equity_short_loses_when_price_rises():
    b = _broker()
    inst = get_instrument("NIFTY")
    pos = b.open_equity_position(inst, "SHORT", 100.0, 100, "NSE_INTRADAY", "t", _now(), params={})
    tr = b.book_partial_close_equity(pos, 50, 108.0, "PARTIAL", _now())
    assert tr.gross_pnl == pytest.approx((100.0 - 108.0) * 50)           # negative
    assert tr.net_pnl < 0
    assert b.reconcile()["diff"] == 0.0


def test_partial_then_full_remainder_stays_invariant():
    b = _broker()
    inst = get_instrument("NIFTY")
    pos = b.open_equity_position(inst, "LONG", 100.0, 100, "NSE_INTRADAY", "t", _now(), params={})
    b.book_partial_close_equity(pos, 40, 103.0, "PARTIAL", _now())
    assert b.reconcile()["diff"] == 0.0
    b.close_equity_position(pos, 106.0, "CLOSE", _now())      # close the remaining 60
    assert b.reconcile()["diff"] == 0.0
