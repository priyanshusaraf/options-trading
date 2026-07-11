"""The research plane persists to its own research.db on its own declarative base.

These tests pin the isolation the persistence design depends on: a dedicated
ResearchBase whose metadata never contains execution tables (so create_all can
never entangle the two databases), and an engine with WAL + foreign keys on.
"""
from sqlalchemy import text

from research.config import research_db_path
from research.domain.base import ResearchBase, make_engine, make_sessionmaker


def test_research_db_path_defaults_to_research_db():
    assert research_db_path(env={}).endswith("research.db")


def test_research_db_path_honors_env(tmp_path):
    p = str(tmp_path / "elsewhere.db")
    assert research_db_path(env={"PT_RESEARCH_DB_PATH": p}) == p


def test_research_base_contains_no_execution_tables():
    tables = set(ResearchBase.metadata.tables)
    for exec_table in ("positions", "capital_state", "instrument_state", "trades"):
        assert exec_table not in tables


def test_execution_base_contains_no_research_tables():
    # importing app models must not register research tables on the execution base
    from app.db.models import Base as ExecBase
    exec_tables = set(ExecBase.metadata.tables)
    for research_table in ResearchBase.metadata.tables:
        assert research_table not in exec_tables


def test_make_engine_enables_wal_and_foreign_keys(tmp_path):
    engine = make_engine(str(tmp_path / "r.db"))
    with engine.connect() as c:
        journal_mode = c.exec_driver_sql("PRAGMA journal_mode").scalar()
        foreign_keys = c.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1


def test_sessionmaker_roundtrips_against_research_db(tmp_path):
    engine = make_engine(str(tmp_path / "r.db"))
    ResearchBase.metadata.create_all(engine)
    Session = make_sessionmaker(engine)
    with Session() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1
