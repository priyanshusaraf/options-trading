"""Marking and exiting a futures position — on the futures price, and never
through a delivery window.

Two properties carry this file:

**It marks on the FUTURES price, not spot.** A future trades at a basis to its
underlying — tens of points on an index — so marking to spot mis-prices the
position on every risk tick and corrupts both unrealized P&L and the distance to
the stop. Marking to spot would look like it worked.

**The delivery guard outranks every other exit.** A contract inside its delivery
window is closed regardless of P&L, stop, target or staleness, because holding it
is an obligation to deliver rather than a trade. Index futures are cash-settled
so this never fires today — which is exactly why it needs a test that forces it.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.engine.runner import EngineRunner
from app.providers.mock import MockProvider

EXPIRY = dt.date(2026, 8, 27)
NOW = dt.datetime(2026, 8, 3, 11, 0)


def _close(obj):
    """Close the broker's long-lived session.

    PaperBroker holds `self.s = SessionLocal()` for its lifetime by design. A
    test that builds one and walks away leaks an open SQLite connection, and the
    NEXT test's `init_db(reset=True)` — which drops and recreates tables — then
    fails with "database is locked". It passes in isolation and fails in the
    suite, which is the worst way to find out.

    (This is the same long-lived session whose refactor is deliberately deferred
    in the roadmap. Until then, tests close it explicitly.)
    """
    try:
        s = getattr(obj, "s", None) or getattr(getattr(obj, "broker", None), "s", None)
        if s is not None:
            s.close()
    except Exception:
        pass


@pytest.fixture
def runner():
    init_db(reset=True)
    obj = EngineRunner()
    yield obj
    _close(obj)


def _open(r, direction="LONG", price=24_000.0):
    return r.broker.open_futures_position(
        get_instrument("NIFTY"), direction, price, 50, "NFO_FUT", "TEST",
        dt.datetime(2026, 8, 3, 10, 0), EXPIRY, margin=25_000.0)


def test_it_marks_on_the_futures_price_not_spot(runner, monkeypatch):
    pos = _open(runner)
    monkeypatch.setattr(runner.provider, "get_futures_ltp",
                        lambda inst, expiry: 24_150.0)
    monkeypatch.setattr(runner.provider, "get_ltp", lambda inst: 24_000.0)
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    assert pos.last_premium == pytest.approx(24_150.0), \
        "the position was marked to spot, not to the futures price"


def test_an_unpriceable_contract_goes_stale_rather_than_exiting_on_a_wrong_price(
        runner, monkeypatch):
    """No futures price means no exit decision. Acting on spot here would fire a
    stop at a price the contract never traded at."""
    pos = _open(runner)
    monkeypatch.setattr(runner.provider, "get_futures_ltp", lambda inst, expiry: None)
    ticks: dict = {}
    runner._mark_exit_futures(pos, "NIFTY", NOW, ticks, {"NIFTY": pos})
    assert ticks["NIFTY"]["stale"] is True
    assert runner.broker.open_positions(), "a stale mark must not close the position"


def test_the_stop_fires_on_the_futures_price(runner, monkeypatch):
    pos = _open(runner)
    monkeypatch.setattr(runner.provider, "get_futures_ltp",
                        lambda inst, expiry: pos.stop_price - 1.0)
    opens = {"NIFTY": pos}
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, opens)
    assert runner.broker.open_positions() == []
    assert opens == {}


# ── the delivery guard ──────────────────────────────────────────────────────

def test_a_position_inside_its_delivery_window_is_force_closed(runner, monkeypatch):
    """Index futures are cash-settled so this never fires in production — which
    is precisely why it must be forced in a test. A guard that has never been
    observed to act is a guard nobody knows works."""
    pos = _open(runner)
    monkeypatch.setattr(runner.provider, "get_futures_ltp",
                        lambda inst, expiry: 24_050.0)
    monkeypatch.setattr("app.engine.delivery_calendar.CashSettledCalendar.window_for",
                        lambda self, k, e: __import__("app.engine.delivery_calendar",
                                                      fromlist=["DeliveryWindow"])
                        .DeliveryWindow(starts=NOW.date(), ends=e))
    opens = {"NIFTY": pos}
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, opens)
    assert runner.broker.open_positions() == [], "held through a delivery window"
    assert opens == {}


def test_the_delivery_guard_outranks_a_profitable_position(runner, monkeypatch):
    """Closed regardless of P&L. Holding a deliverable contract is an obligation,
    not a trade you get to keep because it is winning."""
    pos = _open(runner)
    monkeypatch.setattr(runner.provider, "get_futures_ltp",
                        lambda inst, expiry: 24_500.0)   # well in profit
    monkeypatch.setattr("app.engine.delivery_calendar.CashSettledCalendar.window_for",
                        lambda self, k, e: __import__("app.engine.delivery_calendar",
                                                      fromlist=["DeliveryWindow"])
                        .DeliveryWindow(starts=NOW.date(), ends=e))
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    trades = runner.broker.s.query(__import__("app.db.models", fromlist=["Trade"]).Trade).all()
    assert trades and trades[-1].exit_reason == "DELIVERY_WINDOW"


def test_a_cash_settled_contract_is_not_force_closed(runner, monkeypatch):
    """The default path: no delivery risk, so the guard must be invisible."""
    pos = _open(runner)
    monkeypatch.setattr(runner.provider, "get_futures_ltp",
                        lambda inst, expiry: 24_010.0)
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    assert runner.broker.open_positions(), "a cash-settled future was force-closed"


def test_the_dispatch_routes_futures_to_its_own_path():
    """mark_and_exit_positions must branch on segment — a futures position
    falling through to the options long-premium path would mark it on an option
    premium it does not have."""
    import inspect
    src = inspect.getsource(EngineRunner.mark_and_exit_positions)
    assert '_mark_exit_futures' in src
    assert 'index_futures' in src


# ── force-flat: no rollovers, ever ──────────────────────────────────────────

def test_a_futures_position_is_force_flattened_at_the_close(runner, monkeypatch):
    """Intraday only. A futures position surviving the close is a carried
    leveraged overnight position nobody chose to hold."""
    from app.core import market_hours
    pos = _open(runner)
    monkeypatch.setattr(market_hours, "minutes_to_close", lambda seg, now: 5)
    runner.square_off_intraday(NOW)
    assert runner.broker.open_positions() == []


def test_expiry_day_gets_no_carve_out(runner, monkeypatch):
    """No 'it is expiry day, let it settle'. Settling is a decision the engine is
    not allowed to make, and there is no rollover code anywhere in engine/ — an
    invariant to preserve, not a gap to fill."""
    from app.core import market_hours
    pos = runner.broker.open_futures_position(
        get_instrument("NIFTY"), "LONG", 24_000.0, 50, "NFO_FUT", "TEST",
        dt.datetime(2026, 8, 27, 10, 0), dt.date(2026, 8, 27), margin=25_000.0)
    monkeypatch.setattr(market_hours, "minutes_to_close", lambda seg, now: 2)
    runner.square_off_intraday(dt.datetime(2026, 8, 27, 15, 28))
    assert runner.broker.open_positions() == [], "held a contract into settlement"


def test_the_squareoff_books_a_futures_trade_not_an_equity_one(runner, monkeypatch):
    """Closing via the equity path would tag the segment wrong and compute
    charges on the equity schedule."""
    from app.db.models import Trade
    from app.core import market_hours
    _open(runner)
    monkeypatch.setattr(market_hours, "minutes_to_close", lambda seg, now: 5)
    runner.square_off_intraday(NOW)
    tr = runner.broker.s.query(Trade).all()[-1]
    assert tr.segment == "index_futures"
    assert tr.exit_reason == "INTRADAY_SQUAREOFF"


def test_far_from_the_close_nothing_is_flattened(runner, monkeypatch):
    from app.core import market_hours
    _open(runner)
    monkeypatch.setattr(market_hours, "minutes_to_close", lambda seg, now: 180)
    runner.square_off_intraday(NOW)
    assert runner.broker.open_positions(), "flattened hours before the close"
