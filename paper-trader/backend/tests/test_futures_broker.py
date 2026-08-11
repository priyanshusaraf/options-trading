"""Futures open -> mark -> close, and the ledger invariant that must survive it.

The hard invariant for this whole system is
`cash == initial + realized − Σ(open entry_cost)`, to the paisa. A new segment
that books cash differently breaks it silently: the number stays plausible and
drifts, and nothing announces it. So the load-bearing test here is not "does a
futures trade work" but "does the ledger still reconcile exactly, at every stage
of the trade".

Futures are margined and leveraged far harder than MIS equity — a NIFTY contract
is ₹1.2 crore of notional against ~₹25k of margin — which is exactly why only
the margin may leave cash and why the notional must never touch the ledger.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.models import CapitalState, Position, Trade
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider

EXPIRY = dt.date(2026, 8, 27)


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
def broker():
    init_db(reset=True)
    obj = PaperBroker(MockProvider(), broker_account_id="account.default")
    yield obj
    _close(obj)


def _reconciles(b) -> float:
    """The invariant, returned as a signed drift so a test can assert on 0."""
    cap = b.capital()
    open_cost = sum(p.entry_cost for p in b.open_positions())
    return cap.cash - (cap.initial_capital + cap.realized_pnl - open_cost)


def _open(b, direction="LONG", price=24_000.0, qty=50, margin=25_000.0):
    return b.open_futures_position(
        get_instrument("NIFTY"), direction, price, qty, "NFO_FUT", "TEST",
        dt.datetime(2026, 8, 3, 10, 0), EXPIRY, margin=margin)


# ── the invariant ───────────────────────────────────────────────────────────

def test_the_ledger_reconciles_before_during_and_after(broker):
    assert _reconciles(broker) == pytest.approx(0.0, abs=1e-6)
    pos = _open(broker)
    assert _reconciles(broker) == pytest.approx(0.0, abs=1e-6), "open broke the invariant"
    broker.mark(pos, 24_100.0, 24_100.0, dt.datetime(2026, 8, 3, 11, 0))
    assert _reconciles(broker) == pytest.approx(0.0, abs=1e-6), "marking moved cash"
    broker.close_futures_position(pos, 24_100.0, "TARGET", dt.datetime(2026, 8, 3, 12, 0))
    assert _reconciles(broker) == pytest.approx(0.0, abs=1e-6), "close broke the invariant"


def test_only_the_margin_leaves_cash_never_the_notional(broker):
    """₹1.2 crore of notional against ₹25k of margin. If notional touched cash the
    account would go deeply negative on the first contract."""
    start = broker.capital().cash
    _open(broker, price=24_000.0, qty=50, margin=25_000.0)
    spent = start - broker.capital().cash
    assert spent < 30_000, f"₹{spent:,.0f} left cash — the notional leaked into the ledger"
    assert spent > 25_000, "charges were not booked"


# ── direction ───────────────────────────────────────────────────────────────

def test_a_short_future_profits_when_price_falls(broker):
    pos = _open(broker, direction="SHORT")
    tr = broker.close_futures_position(pos, 23_900.0, "TARGET",
                                       dt.datetime(2026, 8, 3, 12, 0))
    assert tr.gross_pnl == pytest.approx(100.0 * 50)
    assert tr.net_pnl < tr.gross_pnl, "charges were not deducted"


def test_charges_land_on_the_correct_leg_for_a_short(broker):
    """A SHORT opens by SELLING. STT is a sell-side tax, so a short's ENTRY is the
    taxed leg — the error that made equity shorts misreport (safety item E7)."""
    long_ = _open(broker, direction="LONG")
    short = _open(broker, direction="SHORT")
    assert short.entry_charges > long_.entry_charges


# ── margin must never be guessed ────────────────────────────────────────────

def test_opening_without_a_margin_is_refused(broker):
    """SPAN is portfolio-scanned and instrument-specific. Equity can fall back to
    notional/leverage because MIS leverage is roughly knowable; a guessed futures
    margin would be a fabricated number sitting directly in the ledger."""
    for bad in (0.0, -1.0, None):
        with pytest.raises(ValueError, match="margin"):
            _open(broker, margin=bad)


# ── the row itself ──────────────────────────────────────────────────────────

def test_the_position_is_tagged_as_its_own_segment(broker):
    pos = _open(broker)
    assert pos.segment == "index_futures"
    assert pos.option_type == "FUT"
    assert pos.expiry == EXPIRY, "the contract expiry must survive onto the row"


def test_stops_are_direction_aware(broker):
    long_ = _open(broker, direction="LONG")
    short = _open(broker, direction="SHORT")
    assert long_.stop_price < 24_000.0 < long_.target_price
    assert short.stop_price > 24_000.0 > short.target_price


def test_the_trade_row_records_the_segment_and_return_on_margin(broker):
    pos = _open(broker)
    tr = broker.close_futures_position(pos, 24_100.0, "TARGET",
                                       dt.datetime(2026, 8, 3, 12, 0))
    assert tr.segment == "index_futures"
    # Return is on MARGIN, not notional — otherwise a 5,000-rupee gain on ₹25k of
    # margin would report as 0.04% instead of 20%.
    assert tr.return_pct > 10


def test_closing_leaves_no_open_position(broker):
    pos = _open(broker)
    broker.close_futures_position(pos, 24_100.0, "TARGET",
                                  dt.datetime(2026, 8, 3, 12, 0))
    assert broker.open_positions() == []
