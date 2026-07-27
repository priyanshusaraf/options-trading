"""Multi-journal WORKBOOKS — the owner keeps one journal per instrument/theme
(a NIFTY book, a commodities book) instead of a single undifferentiated log.

Every dated artefact (day, trade, missed setup, note) belongs to exactly one book.
Instruments, views, tags and bias stay GLOBAL — they are reference data, not entries.

The migration is the risky half: the live journal.db already holds real rows and
`init_journal_db` is a bare `create_all`, which silently skips existing tables. So the
legacy schema is reproduced here in raw SQL and migrated for real. `journal_days` is
the awkward one — its primary key becomes (book_id, entry_date), and SQLite cannot
alter a primary key in place, so that table is rebuilt.
"""
import datetime as dt

import pytest
from sqlalchemy import inspect, text

from app.journal.db import init_journal_db, make_engine, make_sessionmaker
from app.journal.models import JournalBook, JournalDay, JournalNote, JournalTrade
from app.journal.service import (
    DEFAULT_BOOK_NAME, archive_book, create_book, default_book, list_books,
)

# The journal schema as it existed BEFORE books — what the live VPS file looks like.
LEGACY_SCHEMA = """
CREATE TABLE journal_instruments (
    symbol VARCHAR(32) NOT NULL PRIMARY KEY, exchange VARCHAR(8), lot_size INTEGER,
    tick_size FLOAT, multiplier FLOAT, active BOOLEAN);
CREATE TABLE journal_views (
    id INTEGER NOT NULL PRIMARY KEY, name VARCHAR(64) UNIQUE, thesis TEXT,
    created_at DATETIME, retired_at DATETIME);
CREATE TABLE journal_trades (
    id INTEGER NOT NULL PRIMARY KEY, instrument_symbol VARCHAR(32) NOT NULL,
    direction VARCHAR(8), lots INTEGER, entry_price FLOAT, entry_time DATETIME,
    exit_price FLOAT, exit_time DATETIME, view_id INTEGER, setup_tag VARCHAR(64),
    notes TEXT, manual_net_pnl FLOAT, created_at DATETIME);
CREATE TABLE journal_missed (
    id INTEGER NOT NULL PRIMARY KEY, instrument_symbol VARCHAR(32) NOT NULL,
    direction VARCHAR(8), seen_at DATETIME, setup_tag VARCHAR(64), skip_reason TEXT,
    hypothetical_entry FLOAT, hypothetical_exit FLOAT, notes TEXT);
CREATE TABLE journal_days (
    entry_date DATE NOT NULL PRIMARY KEY, market_view TEXT, result TEXT,
    created_at DATETIME, updated_at DATETIME);
CREATE TABLE journal_notes (
    id INTEGER NOT NULL PRIMARY KEY, noted_at DATETIME, body TEXT,
    instrument_symbol VARCHAR(32));
CREATE TABLE journal_tags (name VARCHAR(64) NOT NULL PRIMARY KEY);
CREATE TABLE journal_bias (
    horizon VARCHAR(8) NOT NULL PRIMARY KEY, stance VARCHAR(32), note TEXT,
    updated_at DATETIME);
"""

LEGACY_ROWS = """
INSERT INTO journal_instruments VALUES ('GOLDM','MCX',10,1.0,1.0,1);
INSERT INTO journal_views VALUES (1,'current','holding gold','2026-07-01 09:00:00',NULL);
INSERT INTO journal_trades VALUES
    (1,'GOLDM','LONG',2,72000.0,'2026-07-02 10:00:00',72500.0,'2026-07-02 14:00:00',
     1,'breakout','held it',4900.0,'2026-07-02 10:00:00');
INSERT INTO journal_missed VALUES
    (1,'GOLDM','SHORT','2026-07-03 11:00:00','fade','was in a meeting',NULL,NULL,NULL);
INSERT INTO journal_days VALUES ('2026-07-02','gold looked strong','+4900','2026-07-02 09:00:00','2026-07-02 16:00:00');
INSERT INTO journal_notes VALUES (1,'2026-07-02 12:00:00','ranting about slippage','GOLDM');
"""


def _legacy_db(tmp_path):
    """A journal.db carrying pre-books data, exactly as the live file does."""
    path = str(tmp_path / "legacy_journal.db")
    engine = make_engine(path)
    with engine.begin() as c:
        for stmt in filter(None, (s.strip() for s in LEGACY_SCHEMA.split(";"))):
            c.execute(text(stmt))
        for stmt in filter(None, (s.strip() for s in LEGACY_ROWS.split(";"))):
            c.execute(text(stmt))
    return engine


def _fresh_db(tmp_path, name="fresh_journal.db"):
    engine = make_engine(str(tmp_path / name))
    init_journal_db(engine)
    return engine


# ── a book exists from the start ─────────────────────────────────────────
def test_fresh_db_gets_a_default_book(tmp_path):
    engine = _fresh_db(tmp_path)
    with make_sessionmaker(engine)() as s:
        books = list_books(s)
        assert [b.name for b in books] == [DEFAULT_BOOK_NAME]
        assert default_book(s).id == books[0].id


def test_books_are_uniquely_named(tmp_path):
    engine = _fresh_db(tmp_path)
    with make_sessionmaker(engine)() as s:
        create_book(s, name="NIFTY")
        with pytest.raises(Exception):
            create_book(s, name="NIFTY")


def test_archived_book_is_hidden_unless_asked_for(tmp_path):
    engine = _fresh_db(tmp_path)
    with make_sessionmaker(engine)() as s:
        b = create_book(s, name="OLD")
        archive_book(s, b.id)
        assert "OLD" not in [x.name for x in list_books(s)]
        assert "OLD" in [x.name for x in list_books(s, include_archived=True)]


def test_the_default_book_cannot_be_archived(tmp_path):
    """It is the fallback every un-booked write lands in — losing it orphans rows."""
    engine = _fresh_db(tmp_path)
    with make_sessionmaker(engine)() as s:
        with pytest.raises(ValueError):
            archive_book(s, default_book(s).id)


# ── migration of a live, populated journal.db ────────────────────────────
def test_migration_adds_books_to_a_legacy_db(tmp_path):
    engine = _legacy_db(tmp_path)
    init_journal_db(engine)
    assert "journal_books" in set(inspect(engine).get_table_names())
    with make_sessionmaker(engine)() as s:
        assert default_book(s) is not None


def test_legacy_rows_are_adopted_by_the_default_book(tmp_path):
    engine = _legacy_db(tmp_path)
    init_journal_db(engine)
    with make_sessionmaker(engine)() as s:
        bid = default_book(s).id
        assert s.get(JournalTrade, 1).book_id == bid
        assert s.get(JournalNote, 1).book_id == bid
        assert s.execute(text("SELECT book_id FROM journal_missed")).scalar() == bid
        assert s.execute(text("SELECT book_id FROM journal_days")).scalar() == bid


def test_migration_preserves_every_legacy_value(tmp_path):
    """A migration that silently drops the owner's history is worse than no feature."""
    engine = _legacy_db(tmp_path)
    init_journal_db(engine)
    with make_sessionmaker(engine)() as s:
        t = s.get(JournalTrade, 1)
        assert (t.instrument_symbol, t.direction, t.lots) == ("GOLDM", "LONG", 2)
        assert (t.entry_price, t.exit_price, t.manual_net_pnl) == (72000.0, 72500.0, 4900.0)
        assert t.setup_tag == "breakout" and t.notes == "held it"
        day = s.execute(text(
            "SELECT market_view, result FROM journal_days")).one()
        assert day == ("gold looked strong", "+4900")


def test_two_books_can_hold_the_same_date(tmp_path):
    """journal_days was keyed on entry_date alone; per-book days need (book, date)."""
    engine = _fresh_db(tmp_path)
    with make_sessionmaker(engine)() as s:
        a, b = default_book(s).id, create_book(s, name="NIFTY").id
        s.add(JournalDay(book_id=a, entry_date=dt.date(2026, 7, 27), market_view="gold"))
        s.add(JournalDay(book_id=b, entry_date=dt.date(2026, 7, 27), market_view="nifty"))
        s.commit()
        views = {r.book_id: r.market_view for r in s.query(JournalDay).all()}
        assert views == {a: "gold", b: "nifty"}


def test_migration_is_idempotent(tmp_path):
    """init runs on every cold start — a second pass must not duplicate or destroy."""
    engine = _legacy_db(tmp_path)
    init_journal_db(engine)
    init_journal_db(engine)
    init_journal_db(engine)
    with make_sessionmaker(engine)() as s:
        assert len(list_books(s)) == 1
        assert s.execute(text("SELECT COUNT(*) FROM journal_trades")).scalar() == 1
        assert s.execute(text("SELECT COUNT(*) FROM journal_days")).scalar() == 1
        assert s.get(JournalTrade, 1).manual_net_pnl == 4900.0


def test_a_second_book_starts_empty(tmp_path):
    """Scoping is the whole point: a new book must not inherit the old one's rows."""
    engine = _legacy_db(tmp_path)
    init_journal_db(engine)
    with make_sessionmaker(engine)() as s:
        nifty = create_book(s, name="NIFTY")
        rows = s.query(JournalTrade).filter(JournalTrade.book_id == nifty.id).all()
        assert rows == []
