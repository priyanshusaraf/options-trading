import datetime as dt

from app.journal.db import make_engine, make_sessionmaker, init_journal_db
from app.journal.models import (
    JournalInstrument, JournalView, JournalTrade, JournalMissed, JournalTag)


def _session(tmp_path):
    engine = make_engine(str(tmp_path / "j.db"))
    init_journal_db(engine)
    return make_sessionmaker(engine)()


def test_instrument_roundtrip(tmp_path):
    s = _session(tmp_path)
    s.add(JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                             tick_size=1.0, multiplier=1.0, active=True))
    s.commit()
    row = s.get(JournalInstrument, "GOLDM")
    assert row.lot_size == 10 and row.active is True


def test_view_roundtrip_and_retire(tmp_path):
    s = _session(tmp_path)
    v = JournalView(name="current", thesis="swing minis", created_at=dt.datetime.now())
    s.add(v)
    s.commit()
    assert v.id is not None
    assert v.retired_at is None
    v.retired_at = dt.datetime.now()
    s.commit()
    assert s.get(JournalView, v.id).retired_at is not None


def test_trade_roundtrip_open_and_closed(tmp_path):
    s = _session(tmp_path)
    inst = JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                              tick_size=1.0, multiplier=1.0, active=True)
    view = JournalView(name="current", created_at=dt.datetime.now())
    s.add_all([inst, view])
    s.commit()
    t = JournalTrade(
        instrument_symbol="GOLDM", direction="LONG", lots=1,
        entry_price=72000.0, entry_time=dt.datetime.now(), view_id=view.id,
        setup_tag="breakout", notes="test entry")
    s.add(t)
    s.commit()
    assert t.id is not None
    assert t.exit_price is None and t.exit_time is None
    assert t.manual_net_pnl is None
    t.exit_price, t.exit_time = 72500.0, dt.datetime.now()
    s.commit()
    assert s.get(JournalTrade, t.id).exit_price == 72500.0


def test_missed_roundtrip(tmp_path):
    s = _session(tmp_path)
    inst = JournalInstrument(symbol="SILVERM", exchange="MCX", lot_size=5,
                              tick_size=1.0, multiplier=1.0, active=True)
    s.add(inst)
    s.commit()
    m = JournalMissed(
        instrument_symbol="SILVERM", direction="SHORT", seen_at=dt.datetime.now(),
        setup_tag="reversal", skip_reason="was away from desk",
        hypothetical_entry=90000.0, hypothetical_exit=89500.0)
    s.add(m)
    s.commit()
    assert m.id is not None


def test_tag_curation_unique(tmp_path):
    s = _session(tmp_path)
    s.add(JournalTag(name="breakout"))
    s.commit()
    assert s.get(JournalTag, "breakout") is not None
