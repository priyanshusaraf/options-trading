"""The startup orphan sweep must alert on REAL orphans only.

Production, every single restart (2026-07-31 logs, nine of them plus nine Telegram
messages):

    ERROR RECOVER: tagged order 2083062708562862080 (BHEL) has no journal row
    ERROR RECOVER: tagged order 2083051353772433408 (SBIN) has no journal row
    … ×9

None of them were orphans. They were the bot's OWN resting SL-M protective stops: those
are placed with the same `pt-bot` tag but their ids live in `positions.gtt_trigger_id`,
never in `order_journal`, so the sweep could not recognise them. The cost isn't noise for
its own sake — an alert that cries wolf nine times a day is an alert nobody reads, and a
genuine orphaned order (a real crash between the journal write and the placement ack, a
real position the bot has lost track of) would arrive in exactly the same channel and be
ignored. This is the alert that guards hard invariant #2.
"""
import datetime as dt

from app.db.models import (
    LEGACY_BROKER_ACCOUNT_ID,
    LEGACY_DEPLOYMENT_ID,
    LEGACY_OWNER_ID,
    OrderJournal,
    Position,
)
from app.db.session import SessionLocal, init_db
from app.engine.live_broker import TAG, LiveBroker


class _Client:
    """Minimal order-book stub — only what the sweep touches."""

    def __init__(self, orderbook):
        self._orderbook = orderbook

    def orders(self):
        return self._orderbook


def _broker(orderbook, monkeypatch):
    init_db(reset=True)
    b = LiveBroker.__new__(LiveBroker)          # no live wiring; the sweep is self-contained
    b.s = SessionLocal()
    b.client = _Client(orderbook)
    b.owner_id = LEGACY_OWNER_ID
    b.broker_account_id = LEGACY_BROKER_ACCOUNT_ID
    b.deployment_id = LEGACY_DEPLOYMENT_ID
    b.alerts = []
    b._notify = lambda msg: b.alerts.append(msg)
    return b


def _journal_row(order_id, symbol, intent="ENTRY"):
    return OrderJournal(
        owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
        deployment_id=LEGACY_DEPLOYMENT_ID,
        order_id=order_id, tradingsymbol=symbol, instrument_key=symbol, side="BUY",
        kind="equity", intent=intent, qty=10, status="TERMINAL",
        placed_at=dt.datetime(2026, 7, 31, 9, 30))


def _position(symbol, stop_order_id):
    return Position(
        owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
        deployment_id=LEGACY_DEPLOYMENT_ID,
        instrument_key=symbol, direction="LONG", option_type="", tradingsymbol=symbol,
        exchange="NSE", segment="equity_intraday", strike=0.0,
        expiry=dt.date(2026, 7, 31),
        lot_size=1, qty=10, entry_premium=100.0, entry_charges=1.0, entry_cost=1000.0,
        entry_spot=100.0, entry_time=dt.datetime(2026, 7, 31, 9, 30),
        stop_price=99.0, target_price=102.0, gtt_trigger_id=stop_order_id)


def test_the_bots_own_resting_stop_is_not_reported_as_an_orphan(monkeypatch):
    """THE production false alarm: entry is journaled, its SL-M is not — but the SL-M id
    is on the position, so the bot plainly knows about it."""
    b = _broker([{"order_id": "ENTRY-1", "tradingsymbol": "BHEL", "tag": TAG},
                 {"order_id": "STOP-1", "tradingsymbol": "BHEL", "tag": TAG}], monkeypatch)
    with SessionLocal() as s:
        s.add(_journal_row("ENTRY-1", "BHEL"))
        s.add(_position("BHEL", "STOP-1"))
        s.commit()

    b._recover_tag_sweep()
    assert b.alerts == []


def test_a_stop_from_a_position_already_closed_is_not_an_orphan(monkeypatch):
    """A position closed earlier today has no row left, but its cancelled/filled SL-M is
    still in the day's order book. Judging orphanhood from open positions alone would
    re-raise the same false alarm every restart until midnight — which is exactly the
    shape of the production symptom (it repeated on every restart)."""
    b = _broker([{"order_id": "STOP-OLD", "tradingsymbol": "SBIN", "tag": TAG}], monkeypatch)
    with SessionLocal() as s:
        s.add(_journal_row("STOP-OLD", "SBIN", intent="STOP"))
        s.commit()

    b._recover_tag_sweep()
    assert b.alerts == []


def test_a_genuinely_unknown_tagged_order_is_still_reported(monkeypatch):
    """The signal this alert exists for must survive the fix."""
    b = _broker([{"order_id": "GHOST", "tradingsymbol": "RELIANCE", "tag": TAG}], monkeypatch)
    b._recover_tag_sweep()
    assert len(b.alerts) == 1
    assert "GHOST" in b.alerts[0]


def test_orders_that_are_not_ours_are_ignored(monkeypatch):
    """The owner's own discretionary orders carry no pt-bot tag and are none of the
    bot's business."""
    b = _broker([{"order_id": "YOURS", "tradingsymbol": "DIXON", "tag": ""},
                 {"order_id": "YOURS2", "tradingsymbol": "NETWEB"}], monkeypatch)
    b._recover_tag_sweep()
    assert b.alerts == []


def test_order_ids_match_across_int_and_str(monkeypatch):
    """Kite has returned order ids as both ints and strings. A type mismatch would make
    EVERY bot order look untracked — the same false alarm by a different route."""
    b = _broker([{"order_id": 2083062706012725248, "tradingsymbol": "BHEL", "tag": TAG}],
                monkeypatch)
    with SessionLocal() as s:
        s.add(_journal_row("2083062706012725248", "BHEL"))
        s.commit()

    b._recover_tag_sweep()
    assert b.alerts == []


def test_an_unreadable_order_book_does_not_claim_everything_is_clean(monkeypatch):
    """"Failed to look" must never read as "found nothing" — the project has been bitten
    by that exact conflation before."""
    class _Broken:
        def orders(self):
            raise RuntimeError("kite down")

    b = _broker([], monkeypatch)
    b.client = _Broken()
    b._recover_tag_sweep()
    assert len(b.alerts) == 1
    assert "could not" in b.alerts[0].lower() or "unable" in b.alerts[0].lower()
