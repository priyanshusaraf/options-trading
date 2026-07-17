"""Dedicated SQLAlchemy base + engine factory for journal.db — the owner's
manual/physical trade log. `JournalBase` is a separate `DeclarativeBase` from
`app.db.models.Base` (the execution ledger) so the two can never entangle via
`metadata.create_all`/`drop_all`, and the journal package never imports the
engine, broker, or runner. Mirrors `research/domain/base.py`.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
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
    """Create all journal tables. Imports the models module so every mapped
    class is registered on JournalBase.metadata before create_all."""
    from app.journal import models  # noqa: F401  (registers tables)
    JournalBase.metadata.create_all(engine)
