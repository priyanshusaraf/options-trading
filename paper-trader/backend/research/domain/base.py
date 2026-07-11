"""Dedicated SQLAlchemy base + engine factory for research.db.

`ResearchBase` is a *separate* DeclarativeBase from `app.db.models.Base`, so
`metadata.create_all` / `drop_all` can never entangle research.db and
paper_trader.db (a hazard the persistence review flagged). The engine factory
applies the same per-connection PRAGMAs the execution DB uses (WAL, busy_timeout,
foreign keys) — they are per-engine, so a research engine must set its own.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class ResearchBase(DeclarativeBase):
    """Declarative base for every research-plane table. Never shared with the
    execution ledger's Base."""


def make_engine(path: str) -> Engine:
    """Create a research.db engine with WAL + foreign keys on every connection."""
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
    """Session factory bound to a research engine. `expire_on_commit=False` so ORM
    rows can be handed to workers without a lazy-load round-trip (mirrors the
    execution session's choice)."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_research_db(engine: Engine) -> None:
    """Create all research tables. Imports the models module so every mapped class
    is registered on `ResearchBase.metadata` before `create_all`."""
    from research.domain import models  # noqa: F401  (registers tables)
    ResearchBase.metadata.create_all(engine)
