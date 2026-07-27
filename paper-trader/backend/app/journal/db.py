"""Dedicated SQLAlchemy base + engine factory for journal.db — the owner's
manual/physical trade log. `JournalBase` is a separate `DeclarativeBase` from
`app.db.models.Base` (the execution ledger) so the two can never entangle via
`metadata.create_all`/`drop_all`, and the journal package never imports the
engine, broker, or runner. Mirrors `research/domain/base.py`.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class JournalBase(DeclarativeBase):
    """Declarative base for every journal table. Never shared with the
    execution ledger's Base or the research plane's ResearchBase."""


def make_engine(path: str) -> Engine:
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_journal_db(engine: Engine) -> None:
    """Create all journal tables, then bring a pre-existing file up to date.

    Imports the models module so every mapped class is registered on
    JournalBase.metadata before create_all. `create_all` only ever CREATES —
    it silently skips tables that already exist, so a schema change to an
    existing table needs `migrate_journal_db`."""
    from app.journal import models  # noqa: F401  (registers tables)
    JournalBase.metadata.create_all(engine)
    migrate_journal_db(engine)


# Tables that gained a `book_id` and can take it via plain ADD COLUMN.
_BOOK_SCOPED = ("journal_trades", "journal_missed", "journal_notes")
DEFAULT_BOOK_NAME = "General"


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}


def _ensure_default_book(conn) -> int:
    """The fallback book every un-booked row belongs to. Returns its id."""
    row = conn.execute(text(
        "SELECT id FROM journal_books WHERE is_default = 1 LIMIT 1")).scalar()
    if row is not None:
        return int(row)
    conn.execute(
        text("INSERT INTO journal_books (name, description, is_default, created_at) "
             "VALUES (:n, :d, 1, :t)"),
        # bind as a string: the raw sqlite3 datetime adapter is deprecated on 3.12+,
        # and this is the exact format SQLAlchemy's SQLite DateTime stores
        {"n": DEFAULT_BOOK_NAME, "d": "Entries recorded before journals were split.",
         "t": dt.datetime.now().isoformat(sep=" ")})
    return int(conn.execute(text(
        "SELECT id FROM journal_books WHERE is_default = 1 LIMIT 1")).scalar())


def migrate_journal_db(engine: Engine) -> None:
    """Idempotent, in-place upgrade of an existing journal.db.

    Runs on every cold start, so every step is guarded by an inspection of the
    live schema and re-running is a no-op. The only migration so far is the
    multi-book split: dated rows gain `book_id` and are adopted by the default
    book, and `journal_days` is REBUILT because its primary key changes from
    (entry_date) to (book_id, entry_date) — SQLite cannot alter a PK in place.
    """
    with engine.begin() as conn:
        if "journal_books" not in _tables(conn):
            return                              # nothing to migrate onto yet
        book_id = _ensure_default_book(conn)

        for table in _BOOK_SCOPED:
            if table in _tables(conn) and "book_id" not in _columns(conn, table):
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN book_id INTEGER "
                    f"REFERENCES journal_books(id)"))
            if table in _tables(conn):
                # backfill covers both the fresh ADD COLUMN and any row a crash
                # between the ALTER and the UPDATE left behind
                conn.execute(text(f"UPDATE {table} SET book_id = :b WHERE book_id IS NULL"),
                             {"b": book_id})

        if "journal_days" in _tables(conn) and "book_id" not in _columns(conn, "journal_days"):
            _rebuild_journal_days(conn, book_id)


def _tables(conn) -> set[str]:
    return {r[0] for r in conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table'"))}


def _rebuild_journal_days(conn, book_id: int) -> None:
    """Re-key journal_days on (book_id, entry_date).

    SQLite has no ALTER ... PRIMARY KEY, so this is the documented
    create-copy-drop-rename dance. It runs inside the caller's transaction; FK
    enforcement is deferred for the duration so the DROP cannot trip a child
    reference (`foreign_keys` is a no-op mid-transaction, hence defer_foreign_keys)."""
    conn.execute(text("PRAGMA defer_foreign_keys = ON"))
    conn.execute(text("""
        CREATE TABLE journal_days_new (
            book_id INTEGER NOT NULL REFERENCES journal_books(id),
            entry_date DATE NOT NULL,
            market_view TEXT, result TEXT,
            created_at DATETIME, updated_at DATETIME,
            PRIMARY KEY (book_id, entry_date))"""))
    conn.execute(text(
        "INSERT INTO journal_days_new "
        "(book_id, entry_date, market_view, result, created_at, updated_at) "
        "SELECT :b, entry_date, market_view, result, created_at, updated_at "
        "FROM journal_days"), {"b": book_id})
    conn.execute(text("DROP TABLE journal_days"))
    conn.execute(text("ALTER TABLE journal_days_new RENAME TO journal_days"))
