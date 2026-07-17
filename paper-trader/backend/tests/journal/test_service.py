import datetime as dt

from app.journal.db import make_engine, make_sessionmaker, init_journal_db
from app.journal.models import JournalInstrument
from app.journal import service


def _session(tmp_path):
    engine = make_engine(str(tmp_path / "j.db"))
    init_journal_db(engine)
    s = make_sessionmaker(engine)()
    s.add(JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                             tick_size=1.0, multiplier=1.0, active=True))
    s.commit()
    return s


def test_ensure_current_view_creates_once(tmp_path):
    s = _session(tmp_path)
    v1 = service.ensure_current_view(s)
    v2 = service.ensure_current_view(s)
    assert v1.id == v2.id  # idempotent — doesn't create a second live view


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
