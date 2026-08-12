"""Execution-database URL resolution and dialect-specific engine profiles."""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url

from app.core.config import Settings


def database_url(settings: Settings) -> str:
    """Return the execution database authority, preserving the local SQLite boundary."""
    if settings.database_url.strip():
        url = settings.database_url.strip()
        if settings.production and make_url(url).get_backend_name() != "postgresql":
            raise RuntimeError("PT_PRODUCTION=1 requires a PostgreSQL PT_DATABASE_URL")
        return url
    if settings.production:
        raise RuntimeError("PT_DATABASE_URL is required when PT_PRODUCTION=1")
    return f"sqlite:///{settings.db_path}"


def create_database_engine(url: str) -> Engine:
    """Build one engine with settings that are valid for its dialect."""
    backend = make_url(url).get_backend_name()
    if backend == "sqlite":
        return create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            pool_timeout=10,
        )
    if backend == "postgresql":
        return create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=10,
        )
    raise RuntimeError("PT_DATABASE_URL must use sqlite or postgresql")


def configure_connection_profile(engine: Engine) -> Engine:
    """Apply connection setup only where the database supports it."""
    if engine.dialect.name != "sqlite":
        return engine

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.close()

    return engine


def create_execution_engine(settings: Settings, *, engine_factory=create_database_engine) -> Engine:
    """Create the configured execution engine through an injectable factory."""
    return configure_connection_profile(engine_factory(database_url(settings)))
