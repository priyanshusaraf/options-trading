"""The ledger DB is structurally isolated from the execution ledger: its own
DeclarativeBase, its own file, its own engine. The engine must never be able to
reach it and it must never be able to reach the engine."""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.models import Base as ExecBase
from app.ledger.config import ledger_db_path
from app.ledger.db import LedgerBase, init_ledger_db, make_engine


def test_ledger_base_is_not_the_execution_base():
    assert LedgerBase is not ExecBase


def test_default_path_is_absolute():
    # A bare relative default lands wherever systemd's WorkingDirectory points,
    # so a restart under a different cwd silently starts a second empty journal.
    assert os.path.isabs(ledger_db_path({}))


def test_env_override_wins():
    assert ledger_db_path({"PT_LEDGER_DB_PATH": "/tmp/x.db"}) == "/tmp/x.db"


def test_init_creates_both_tables(tmp_path):
    engine = make_engine(str(tmp_path / "ledger.db"))
    init_ledger_db(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"ledger_snapshot", "ledger_artifact"} <= names


def test_init_is_idempotent(tmp_path):
    path = str(tmp_path / "ledger.db")
    init_ledger_db(make_engine(path))
    init_ledger_db(make_engine(path))  # must not raise


def test_snapshot_table_permits_exactly_one_row(tmp_path):
    engine = make_engine(str(tmp_path / "ledger.db"))
    init_ledger_db(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO ledger_snapshot (owner_id, broker_account_id, id, version, payload, updated_at)"
            " VALUES ('owner', 'account.default', 1, 1, '{}', '2026-07-31T00:00:00')"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO ledger_snapshot (owner_id, broker_account_id, id, version, payload, updated_at)"
                " VALUES ('owner', 'account.default', 2, 1, '{}', '2026-07-31T00:00:00')"))
