"""Engine, base and migrations for the ledger DB.

The ledger package never imports the engine, broker, or runner. Nothing under
app/engine/ may import this package. That isolation is structural, not a
convention: a bug here must never be able to become a real-money bug.
"""
from __future__ import annotations

import threading

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.ledger.config import ledger_db_path


class LedgerBase(DeclarativeBase):
    """Never share this with app.db.models.Base or the research plane's base."""


def make_engine(path: str) -> Engine:
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}


def init_ledger_db(engine: Engine) -> None:
    """Create tables, then bring a pre-existing file up to date.

    create_all only ever CREATEs — it silently skips tables that already exist,
    so any change to an EXISTING table must go through migrate_ledger_db."""
    from app.ledger import models  # noqa: F401  (registers the mapped classes)

    LedgerBase.metadata.create_all(engine)
    migrate_ledger_db(engine)


def migrate_ledger_db(engine: Engine) -> None:
    """Self-applying migrations. scripts/deploy.sh excludes *.db from rsync, so a
    schema change ships as code and must apply itself on the next boot.

    create_all handles NEW tables and is safe to re-run — that is what a file
    written by an older build needs. Anything that changes an EXISTING table
    needs an explicit ADD COLUMN here, guarded by a PRAGMA table_info check."""
    from app.ledger import models  # noqa: F401  (registers the mapped classes)

    # create_all handles NEW tables and is safe to re-run — it creates what is
    # missing and skips what exists. That is exactly what a ledger.db written by
    # an older build needs when a new table (e.g. ledger_manual_fill) ships.
    LedgerBase.metadata.create_all(engine)

    with engine.begin() as conn:
        _ = _columns(conn, "ledger_snapshot")
        _ = _columns(conn, "ledger_manual_fill")


_sessionmaker: sessionmaker | None = None
_lock = threading.Lock()


def get_sessionmaker() -> sessionmaker:
    """Lazy, double-checked. The deleted journal package learned this the hard
    way: a production 500 from two threads racing table creation."""
    global _sessionmaker
    if _sessionmaker is None:
        with _lock:
            if _sessionmaker is None:
                engine = make_engine(ledger_db_path())
                init_ledger_db(engine)
                _sessionmaker = sessionmaker(
                    bind=engine, expire_on_commit=False, future=True)
    return _sessionmaker
