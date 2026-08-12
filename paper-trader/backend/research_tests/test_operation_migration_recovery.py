import importlib

import pytest
from sqlalchemy import text

from research.domain.base import ResearchBase, init_research_db, make_engine
from research.domain.migrate import ResearchMigrationError


def test_0002_rejects_malformed_existing_table_before_it_can_be_stamped(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE research_operation (operation_id TEXT)")
            connection.exec_driver_sql("CREATE TABLE research_schema_version (version VARCHAR(16) NOT NULL PRIMARY KEY, schema_cookie INTEGER NOT NULL)")
            connection.exec_driver_sql("INSERT INTO research_schema_version VALUES ('0001', 1)")
        with pytest.raises(ResearchMigrationError):
            init_research_db(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version FROM research_schema_version")).scalar_one() == "0001"
    finally:
        engine.dispose()


def test_0002_empty_cleanup_and_nonempty_refusal(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        migration = importlib.import_module("research.domain.migrations.0002_owner_operations")
        table = ResearchBase.metadata.tables["research_operation"]
        with engine.begin() as connection:
            migration.downgrade(connection, table)
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='research_operation'").first() is None
            connection.exec_driver_sql("UPDATE research_schema_version SET version='0001'")
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO research_operation (owner_id,operation_id,trigger,plan_json,status,stage,build,provider_mode,completed_run_ids_json,created_at,queued_at,attempt_count) VALUES ('a','b','manual','{}','pending','startup','b','m','[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0)")
            with pytest.raises(RuntimeError, match="refuses"):
                migration.downgrade(connection, table)
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM research_operation").scalar_one() == 1
    finally:
        engine.dispose()
