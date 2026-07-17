import datetime as dt

import pytest

from app.journal.db import make_engine, make_sessionmaker, init_journal_db
from app.journal.models import (
    JournalInstrument, JournalView, JournalTrade, JournalMissed, JournalTag)


def _session(tmp_path):
    engine = make_engine(str(tmp_path / "j.db"))
    init_journal_db(engine)
    return make_sessionmaker(engine)()


@pytest.fixture
def session(tmp_path):
    engine = make_engine(str(tmp_path / "journal.db"))
    init_journal_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as s:
        yield s


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


from app.journal.models import JournalBias, JournalDay, JournalNote


def test_journal_day_roundtrip(session):
    session.add(JournalDay(entry_date=dt.date(2026, 7, 17),
                           market_view="nifty broke 24200",
                           result="waiting for monday",
                           created_at=dt.datetime(2026, 7, 17, 9),
                           updated_at=dt.datetime(2026, 7, 17, 9)))
    session.commit()
    row = session.get(JournalDay, dt.date(2026, 7, 17))
    assert row.market_view == "nifty broke 24200"
    assert row.result == "waiting for monday"


def test_journal_note_roundtrip(session):
    note = JournalNote(noted_at=dt.datetime(2026, 7, 17, 14, 32),
                       body="exited +900 too early", instrument_symbol=None)
    session.add(note)
    session.commit()
    assert note.id is not None
    assert session.get(JournalNote, note.id).body == "exited +900 too early"


def test_journal_bias_roundtrip(session):
    session.add(JournalBias(horizon="6M", stance="bullish", note="secular uptrend",
                            updated_at=dt.datetime(2026, 7, 17)))
    session.commit()
    assert session.get(JournalBias, "6M").stance == "bullish"
