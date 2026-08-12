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


def _table_exists(conn, table: str) -> bool:
    return conn.execute(text(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table}).scalar() is not None


def init_ledger_db(engine: Engine) -> None:
    """Create tables, then bring a pre-existing file up to date.

    create_all only ever CREATEs — it silently skips tables that already exist,
    so any change to an EXISTING table must go through migrate_ledger_db."""
    from app.ledger import models  # noqa: F401  (registers the mapped classes)

    migrate_ledger_db(engine)


def migrate_ledger_db(engine: Engine) -> None:
    """Self-applying migrations. scripts/deploy.sh excludes *.db from rsync, so a
    schema change ships as code and must apply itself on the next boot.

    create_all handles NEW tables and is safe to re-run — that is what a file
    written by an older build needs. Anything that changes an EXISTING table
    needs an explicit ADD COLUMN here, guarded by a PRAGMA table_info check."""
    from app.ledger import models  # noqa: F401  (registers the mapped classes)

    with engine.begin() as conn:
        legacy = []
        for table in ("ledger_snapshot", "ledger_artifact", "ledger_manual_fill"):
            old = f"{table}_legacy_scope"
            if _table_exists(conn, old):
                legacy.append((table, old))
            elif _columns(conn, table) and "owner_id" not in _columns(conn, table):
                conn.execute(text(f"ALTER TABLE {table} RENAME TO {old}"))
                legacy.append((table, old))
    LedgerBase.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, old in legacy:
            if conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar():
                raise RuntimeError(
                    f"refusing ambiguous ledger scope migration for {table}: target already has rows")
            if table == "ledger_snapshot":
                conn.execute(text("INSERT INTO ledger_snapshot (owner_id, broker_account_id, id, version, payload, updated_at) SELECT 'owner', 'account.default', id, version, payload, updated_at FROM " + old))
            elif table == "ledger_artifact":
                conn.execute(text("INSERT INTO ledger_artifact (owner_id, broker_account_id, id, mime, bytes, created_at) SELECT 'owner', 'account.default', id, mime, bytes, created_at FROM " + old))
            else:
                conn.execute(text("INSERT INTO ledger_manual_fill (owner_id, broker_account_id, order_id, tradingsymbol, exchange, product, side, qty, avg_price, order_ts, fill_ts, verdict, raw, claimed_trade, seen_at) SELECT 'owner', 'account.default', order_id, tradingsymbol, exchange, product, side, qty, avg_price, order_ts, fill_ts, verdict, raw, claimed_trade, seen_at FROM " + old))
            conn.execute(text(f"DROP TABLE {old}"))


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
