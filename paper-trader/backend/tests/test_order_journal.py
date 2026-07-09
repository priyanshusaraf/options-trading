"""audit H13: persisted order journal — the durable mirror of the in-memory
in-flight trackers, so a crash mid-order-poll is recoverable on restart."""
from sqlalchemy import select

from app.db.models import OrderJournal
from app.db.session import init_db, SessionLocal


def test_order_journal_table_is_created():
    init_db(reset=True)
    with SessionLocal() as s:
        assert list(s.scalars(select(OrderJournal))) == []   # table exists, empty


from tests.test_live_broker import FakeClient, _broker, _open


def _entry_rows(b):
    return b.s.scalars(select(OrderJournal).where(OrderJournal.intent == "ENTRY")).all()


def test_filled_entry_writes_terminal_filled_row_with_order_id():
    c = FakeClient(fill_price=100.0)                 # full fill
    b = _broker(c)
    _open(b, c)
    rows = _entry_rows(b)
    assert len(rows) == 1
    r = rows[0]
    assert r.order_id == "OID-1" and r.kind == "options"
    assert r.status == "TERMINAL" and r.resolution == "FILLED"
    assert r.filled_qty > 0


def test_timed_out_entry_leaves_a_working_row_with_order_id():
    c = FakeClient(status="OPEN", filled_qty=0)      # never confirms in the window
    b = _broker(c)
    b.poll_seconds = 0.001
    _open(b, c)
    r = _entry_rows(b)[0]
    assert r.status == "WORKING" and r.order_id == "OID-1"   # recoverable on restart


def test_rejected_entry_is_terminal_rejected():
    c = FakeClient(status="REJECTED", filled_qty=0)
    b = _broker(c)
    _open(b, c)
    r = _entry_rows(b)[0]
    assert r.status == "TERMINAL" and r.resolution == "REJECTED"


from app.engine.live_broker import LiveBroker
from app.providers.mock import MockProvider


def _fresh_broker_same_db(client):
    prov = MockProvider()
    prov.account_positions = lambda: []
    return LiveBroker(prov, client, poll_seconds=0.0, timeout_seconds=0.0)


def test_recover_adopts_a_late_filled_entry_after_restart():
    c1 = FakeClient(status="OPEN", filled_qty=0)           # entry times out
    b1 = _broker(c1)
    b1.poll_seconds = 0.001
    pos, q, chain = _open(b1, c1)
    assert pos is None                                      # nothing booked; WORKING journal row
    # restart: fresh broker on the SAME DB, the order has since COMPLETED
    c2 = FakeClient(status="COMPLETE", filled_qty=q.lot_size, fill_price=100.0)
    b2 = _fresh_broker_same_db(c2)
    recovered = b2.recover_journal(b2.provider.now())
    assert "NIFTY" in recovered
    assert b2.position_for("NIFTY") is not None             # adopted into the book
    assert b2.reconcile()["diff"] == 0.0                    # invariant exact
    working = b2.s.scalars(select(OrderJournal).where(OrderJournal.status == "WORKING")).all()
    assert working == []                                    # row resolved (ADOPTED)


def test_recover_books_a_filled_exit_ledger_only():
    c1 = FakeClient(fill_price=100.0)                       # open fills fully
    b1 = _broker(c1)
    pos, q, chain = _open(b1, c1)
    b1.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol, "quantity": pos.qty}]
    # a close that times out with no fill -> WORKING EXIT journal row
    c1._status, c1._filled_qty = "OPEN", 0
    b1.poll_seconds = 0.001
    assert b1.close_position(pos, 90.0, "t", b1.provider.now(), chain.spot) is None
    assert b1.position_for("NIFTY") is not None             # still open in the book
    # restart: the exit order has since filled fully
    c2 = FakeClient(status="COMPLETE", filled_qty=q.lot_size, fill_price=92.0)
    b2 = _fresh_broker_same_db(c2)
    recovered = b2.recover_journal(b2.provider.now())
    assert "NIFTY25JAN24100CE" in recovered or b2.position_for("NIFTY") is None
    assert b2.position_for("NIFTY") is None                 # booked closed at the real fill
    assert c2.placed == []                                  # NO new real order placed in recovery
    assert b2.reconcile()["diff"] == 0.0
