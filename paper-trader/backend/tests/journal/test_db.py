"""journal.db must be fully isolated: its own Base, its own engine, never the
execution engine's metadata."""
import os

from app.journal.config import journal_db_path, DEFAULT_JOURNAL_DB
from app.journal.db import JournalBase, make_engine, make_sessionmaker, init_journal_db


def test_journal_db_path_defaults_and_env_override(monkeypatch):
    assert journal_db_path({}) == DEFAULT_JOURNAL_DB
    assert journal_db_path({"PT_JOURNAL_DB_PATH": "/tmp/x.db"}) == "/tmp/x.db"


def test_journal_base_is_not_the_execution_base():
    from app.db.models import Base as ExecBase
    assert JournalBase is not ExecBase
    assert JournalBase.metadata is not ExecBase.metadata


def test_init_journal_db_creates_tables(tmp_path):
    path = str(tmp_path / "journal_test.db")
    engine = make_engine(path)
    init_journal_db(engine)
    from sqlalchemy import inspect
    tables = set(inspect(engine).get_table_names())
    assert {"journal_instruments", "journal_views", "journal_trades",
            "journal_missed", "journal_tags"} <= tables
    Session = make_sessionmaker(engine)
    with Session() as s:
        assert s is not None  # session factory is usable
