"""Dedicated SQLAlchemy base + engine factory for research.db.

`ResearchBase` is a *separate* DeclarativeBase from `app.db.models.Base`, so
`metadata.create_all` / `drop_all` can never entangle research.db and
paper_trader.db (a hazard the persistence review flagged). The engine factory
applies the same per-connection PRAGMAs the execution DB uses (WAL, busy_timeout,
foreign keys) — they are per-engine, so a research engine must set its own.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


LEGACY_OWNER_ID = "legacy"


class ResearchBase(DeclarativeBase):
    """Declarative base for every research-plane table. Never shared with the
    execution ledger's Base."""


def make_engine(authority: str) -> Engine:
    """Create a dialect-aware engine for a URL or a legacy SQLite path."""
    url = authority if "://" in authority else f"sqlite:///{authority}"
    backend = make_url(url).get_backend_name()
    if backend == "sqlite":
        engine = create_engine(url, future=True)
    elif backend == "postgresql":
        engine = create_engine(
            url, future=True, pool_pre_ping=True, pool_size=5,
            max_overflow=10, pool_timeout=10,
        )
    else:
        raise RuntimeError("PT_RESEARCH_DATABASE_URL must use sqlite or postgresql")

    if backend == "sqlite":
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


def research_database_exists(authority: str) -> bool:
    """Check plane existence without creating or migrating it."""
    import os

    url = authority if "://" in authority else f"sqlite:///{authority}"
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        return bool(parsed.database and os.path.exists(parsed.database))
    engine = make_engine(url)
    try:
        return "research_schema_version" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def init_research_db(engine: Engine) -> None:
    """Bring the physically separate research database to its owned schema head."""
    from research.domain.migrate import migrate_research_db

    migrate_research_db(engine)
