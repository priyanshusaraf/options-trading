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
