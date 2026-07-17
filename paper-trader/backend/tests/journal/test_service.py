import datetime as dt

import pytest

from app.journal.db import make_engine, make_sessionmaker, init_journal_db
from app.journal.models import JournalInstrument, JournalView
from app.journal import service


def _session(tmp_path):
    engine = make_engine(str(tmp_path / "j.db"))
    init_journal_db(engine)
    s = make_sessionmaker(engine)()
    s.add(JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                             tick_size=1.0, multiplier=1.0, active=True))
    s.commit()
    return s


@pytest.fixture
def session(tmp_path):
    engine = make_engine(str(tmp_path / "journal.db"))
    init_journal_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as s:
        yield s


def test_ensure_current_view_creates_once(tmp_path):
    s = _session(tmp_path)
    v1 = service.ensure_current_view(s)
    v2 = service.ensure_current_view(s)
    assert v1.id == v2.id  # idempotent — doesn't create a second live view


def test_ensure_current_view_survives_retired_name_collision(tmp_path):
    # Reproduces the original bug: a JournalView named "current" already
    # exists but is retired, and there is no other live view. The old code
    # only checked for a LIVE view by retired_at IS NULL, then always
    # hardcoded name="current" for the auto-created row, which collided with
    # the retired row's UNIQUE(name) and raised IntegrityError.
    s = _session(tmp_path)
    retired = JournalView(name=service.CURRENT_VIEW_NAME,
                           created_at=dt.datetime.now(),
                           retired_at=dt.datetime.now())
    s.add(retired)
    s.commit()

    new_view = service.ensure_current_view(s)  # must not raise

    assert new_view.id != retired.id
    assert new_view.name != retired.name
    assert new_view.retired_at is None


def test_close_trade_unknown_id_raises_value_error(tmp_path):
    s = _session(tmp_path)
    with pytest.raises(ValueError):
        service.close_trade(s, 999999, exit_price=100.0, exit_time=dt.datetime.now())


def test_add_trade_binds_to_current_view_when_unspecified(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now())
    assert t.id is not None
    assert t.view_id == service.ensure_current_view(s).id
    assert t.exit_price is None


def test_close_trade_sets_exit_fields(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now())
    closed = service.close_trade(s, t.id, exit_price=72500.0, exit_time=dt.datetime.now())
    assert closed.exit_price == 72500.0


def test_add_trade_upserts_tag_into_curation_list(tmp_path):
    s = _session(tmp_path)
    service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                       entry_price=72000.0, entry_time=dt.datetime.now(),
                       setup_tag="breakout")
    from app.journal.models import JournalTag
    assert s.get(JournalTag, "breakout") is not None


def test_add_missed_persists(tmp_path):
    s = _session(tmp_path)
    m = service.add_missed(s, symbol="GOLDM", direction="SHORT",
                            seen_at=dt.datetime.now(), skip_reason="lunch",
                            hypothetical_entry=72000.0, hypothetical_exit=71800.0)
    assert m.id is not None


def test_list_trades_open_only_filter(tmp_path):
    s = _session(tmp_path)
    open_t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                                entry_price=72000.0, entry_time=dt.datetime.now())
    closed_t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                                  entry_price=71000.0, entry_time=dt.datetime.now())
    service.close_trade(s, closed_t.id, exit_price=71200.0, exit_time=dt.datetime.now())
    ids = {t.id for t in service.list_trades(s, open_only=True)}
    assert ids == {open_t.id}


def test_trade_unrealized_uses_pnl_module(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now())
    inst = s.get(JournalInstrument, "GOLDM")
    from app.journal.pnl import unrealized_pnl
    expected = unrealized_pnl("LONG", 72000.0, 72200.0, lots=1, lot_size=10, multiplier=1.0)
    assert service.trade_unrealized(t, inst, 72200.0) == expected


def test_stats_by_tag_and_missed_summary(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now(),
                           setup_tag="breakout")
    service.close_trade(s, t.id, exit_price=72500.0, exit_time=dt.datetime.now())
    service.add_missed(s, symbol="GOLDM", direction="LONG", seen_at=dt.datetime.now(),
                        skip_reason="away", hypothetical_entry=72000.0,
                        hypothetical_exit=72400.0)
    out = service.stats(s)
    assert out["by_tag"]["breakout"]["trades"] == 1
    assert out["by_tag"]["breakout"]["wins"] == 1
    assert out["by_tag"]["breakout"]["net_pnl"] > 0
    assert out["missed_summary"]["count"] == 1
    assert out["missed_summary"]["hypothetical_net_pnl"] > 0


def _seed_inst(s, symbol="GOLDM"):
    if s.get(JournalInstrument, symbol) is None:
        s.add(JournalInstrument(symbol=symbol, exchange="MCX", lot_size=10,
                                tick_size=1.0, multiplier=1.0, active=True))
        s.commit()


def test_upsert_day_is_idempotent(session):
    d = dt.date(2026, 7, 17)
    service.upsert_day(session, entry_date=d, market_view="v1")
    service.upsert_day(session, entry_date=d, result="done")
    from app.journal.models import JournalDay
    rows = session.query(JournalDay).all()
    assert len(rows) == 1
    assert rows[0].market_view == "v1"   # preserved
    assert rows[0].result == "done"      # added


def test_add_and_delete_note(session):
    note = service.add_note(session, body="rant", noted_at=dt.datetime(2026, 7, 17, 10))
    assert service.delete_note(session, note.id) is True
    assert service.delete_note(session, note.id) is False


def test_seed_and_upsert_bias(session):
    service.seed_bias(session)
    assert {b.horizon for b in service.list_bias(session)} == {"6M", "1M"}
    service.upsert_bias(session, horizon="6M", stance="bullish", note="uptrend")
    assert next(b for b in service.list_bias(session) if b.horizon == "6M").stance == "bullish"


def test_upsert_bias_unknown_horizon_raises(session):
    service.seed_bias(session)
    import pytest
    with pytest.raises(ValueError):
        service.upsert_bias(session, horizon="3Y", stance="x")


def test_feed_groups_by_date(session):
    _seed_inst(session)
    d = dt.date(2026, 7, 17)
    service.add_note(session, body="morning", noted_at=dt.datetime(2026, 7, 17, 9))
    service.add_trade(session, symbol="GOLDM", direction="LONG", lots=1,
                      entry_price=100.0, entry_time=dt.datetime(2026, 7, 17, 10))
    service.upsert_day(session, entry_date=d, market_view="broke out")
    out = service.feed(session, limit=10)
    day = next(x for x in out["days"] if x["date"] == "2026-07-17")
    assert day["market_view"] == "broke out"
    assert len(day["notes"]) == 1
    assert len(day["trades"]) == 1


def test_feed_day_with_only_notes_appears(session):
    service.add_note(session, body="lone note", noted_at=dt.datetime(2026, 7, 16, 12))
    out = service.feed(session, limit=10)
    assert any(x["date"] == "2026-07-16" for x in out["days"])
