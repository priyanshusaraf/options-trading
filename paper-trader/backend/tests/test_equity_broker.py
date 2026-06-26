"""PaperBroker intraday-equity path: MIS sizing books only MARGIN against cash (not
full notional), P&L is direction-aware on the full share move, charges use the
intraday segment, and the ledger reconciliation invariant stays exact through a
round trip — for both a LONG and a real SHORT."""
import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.engine.broker import PaperBroker
from app.engine.charges import compute_charges
from app.db.session import init_db
from app.providers.mock import MockProvider

PARAMS = {"intraday_leverage": 5.0, "intraday_stop_loss_pct": 0.01,
          "intraday_target_pct": 0.02}
NOW = dt.datetime(2024, 1, 2, 10, 0)


def _broker() -> PaperBroker:
    init_db(reset=True)
    return PaperBroker(MockProvider())


def test_open_equity_books_margin_not_full_notional():
    b = _broker()
    cash0 = b.cash()
    pos = b.open_equity_position(get_instrument("NIFTY"), "LONG", price=100.0, qty=200,
                                 charge_segment="NSE_INTRADAY", reason="t", now=NOW,
                                 params=PARAMS)
    assert (pos.segment, pos.option_type, pos.exchange) == ("equity_intraday", "EQ", "NSE_INTRADAY")
    assert pos.qty == 200
    margin = 100.0 * 200 / 5.0                       # 4,000 (not the 20,000 notional)
    assert (cash0 - b.cash()) == pytest.approx(margin + pos.entry_charges, abs=0.01)
    assert pos.stop_price == pytest.approx(99.0)     # LONG: stop below
    assert pos.target_price == pytest.approx(102.0)  # LONG: target above


def test_equity_entry_charges_use_intraday_segment():
    b = _broker()
    pos = b.open_equity_position(get_instrument("NIFTY"), "LONG", 1000.0, 50,
                                 "NSE_INTRADAY", "t", NOW, params=PARAMS)
    assert pos.entry_charges == pytest.approx(
        compute_charges("NSE_INTRADAY", "BUY", 1000.0, 50)["total"])


def test_close_equity_long_profit_reconciles():
    b = _broker()
    pos = b.open_equity_position(get_instrument("NIFTY"), "LONG", 100.0, 200,
                                 "NSE_INTRADAY", "t", NOW, params=PARAMS)
    tr = b.close_equity_position(pos, 102.0, "TARGET", NOW + dt.timedelta(minutes=30))
    assert tr.segment == "equity_intraday" and tr.option_type == "EQ"
    assert tr.gross_pnl == pytest.approx((102.0 - 100.0) * 200)       # 400
    assert tr.net_pnl == pytest.approx(400.0 - tr.charges_total)
    assert tr.win is True
    assert b.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)


def test_close_equity_short_profits_when_price_falls():
    b = _broker()
    pos = b.open_equity_position(get_instrument("NIFTY"), "SHORT", 100.0, 200,
                                 "NSE_INTRADAY", "t", NOW, params=PARAMS)
    assert pos.stop_price == pytest.approx(101.0)    # SHORT: stop above
    assert pos.target_price == pytest.approx(98.0)   # SHORT: target below
    tr = b.close_equity_position(pos, 98.0, "TARGET", NOW + dt.timedelta(minutes=30))
    assert tr.gross_pnl == pytest.approx((100.0 - 98.0) * 200)        # short gains as price drops
    assert tr.net_pnl > 0
    assert b.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)


def test_close_equity_short_loss_when_price_rises():
    b = _broker()
    pos = b.open_equity_position(get_instrument("NIFTY"), "SHORT", 100.0, 200,
                                 "NSE_INTRADAY", "t", NOW, params=PARAMS)
    tr = b.close_equity_position(pos, 103.0, "STOP_LOSS", NOW + dt.timedelta(minutes=10))
    assert tr.gross_pnl == pytest.approx((100.0 - 103.0) * 200)       # -600
    assert tr.net_pnl < 0
    assert b.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)
