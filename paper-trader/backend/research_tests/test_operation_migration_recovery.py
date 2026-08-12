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


def test_0002_refuses_source_absent_unproven_temp_without_mutating_it(tmp_path):
    """A named temp is not proof that a prior migration safely copied its target."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        migration = importlib.import_module("research.domain.migrations.0002_owner_operations")
        table = ResearchBase.metadata.tables["research_operation"]
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE research_operation__owner_tmp (forged TEXT)")
            with pytest.raises(RuntimeError, match="unproven"):
                migration.upgrade(connection, table)
            assert connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE name='research_operation__owner_tmp'"
            ).scalar_one() == "CREATE TABLE research_operation__owner_tmp (forged TEXT)"
    finally:
        engine.dispose()


def test_full_initializer_never_promotes_an_unproven_0002_temp(tmp_path):
    """Generic recovery must not bypass 0002's source-bound proof check."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE research_operation")
            connection.exec_driver_sql("CREATE TABLE research_operation__owner_tmp (forged TEXT)")
        with pytest.raises((ResearchMigrationError, RuntimeError), match="unproven"):
            init_research_db(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE name='research_operation'"
            ).first() is None
            assert connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE name='research_operation__owner_tmp'"
            ).scalar_one() == "CREATE TABLE research_operation__owner_tmp (forged TEXT)"
    finally:
        engine.dispose()


def test_head_marker_cannot_bless_relaxed_operation_item_check(tmp_path):
    """A named CHECK with a permissive body is schema drift, not a valid head."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            sql = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE name='research_operation_item'"
            ).scalar_one()
            connection.exec_driver_sql("ALTER TABLE research_operation_item RENAME TO item_old")
            connection.exec_driver_sql(sql.replace("research_operation_item", "research_operation_item", 1)
                                       .replace("status IN ('pending', 'running', 'completed')", "1"))
            columns = "owner_id, operation_id, item_key, ordinal, status, run_id, completed_at"
            connection.exec_driver_sql(
                f"INSERT INTO research_operation_item ({columns}) SELECT {columns} FROM item_old"
            )
            connection.exec_driver_sql("DROP TABLE item_old")
        with pytest.raises(ResearchMigrationError, match="check-constraint drift"):
            init_research_db(engine)
    finally:
        engine.dispose()


def test_0002_recovers_only_a_proven_source_absent_temp(tmp_path):
    """Recovery verifies the exact target schema and persisted proof before promotion."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        migration = importlib.import_module("research.domain.migrations.0002_owner_operations")
        table = ResearchBase.metadata.tables["research_operation"]
        with engine.begin() as connection:
            migration.upgrade(connection, table)
            connection.exec_driver_sql("ALTER TABLE research_operation RENAME TO research_operation__owner_tmp")
            migration.upgrade(connection, table)
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM research_operation").scalar_one() == 0
    finally:
        engine.dispose()


def test_0003_upgrades_a_complete_0002_database_without_rewriting_operations(tmp_path):
    """The checkpoint migration is additive and preserves durable job history."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO research_operation "
                "(owner_id,operation_id,trigger,plan_json,status,stage,build,provider_mode,"
                "completed_run_ids_json,created_at,queued_at,attempt_count) "
                "VALUES ('owner','op','manual','{}','pending','startup','b','mock','[]',"
                "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0)"
            )
            connection.exec_driver_sql("DROP TABLE research_operation_item")
            connection.exec_driver_sql("UPDATE research_schema_version SET version='0002'")
        init_research_db(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT owner_id, operation_id FROM research_operation"
            ).one() == ("owner", "op")
            assert connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE name='research_operation_item'"
            ).first() is not None
            assert connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE name='research_operation_event'"
            ).first() is not None
            assert connection.exec_driver_sql(
                "SELECT version FROM research_schema_version"
            ).scalar_one() == "0003"
    finally:
        engine.dispose()


def test_0003_refuses_forged_event_table_without_advancing_marker(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE research_operation_event")
            connection.exec_driver_sql(
                "CREATE TABLE research_operation_event (owner_id VARCHAR(64), operation_id VARCHAR(64))"
            )
            connection.exec_driver_sql("UPDATE research_schema_version SET version='0002'")
        with pytest.raises((ResearchMigrationError, RuntimeError), match="event schema contract"):
            init_research_db(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT version FROM research_schema_version"
            ).scalar_one() == "0002"
    finally:
        engine.dispose()


def test_0003_refuses_nonempty_exact_event_table_from_pre_event_revision(tmp_path):
    """0002 could not write events, so exact-shaped rows are forged evidence."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO research_operation "
                "(owner_id,operation_id,trigger,plan_json,status,stage,build,provider_mode,"
                "completed_run_ids_json,created_at,queued_at,attempt_count) "
                "VALUES ('owner','op','manual','{}','pending','startup','b','mock','[]',"
                "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0)"
            )
            connection.exec_driver_sql(
                "INSERT INTO research_operation_event "
                "(owner_id,operation_id,sequence,event_type,stage,payload_json,created_at) "
                "VALUES ('owner','op',1,'takeover','startup','{}',CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql("DROP TABLE research_operation_item")
            connection.exec_driver_sql("UPDATE research_schema_version SET version='0002'")
        with pytest.raises(RuntimeError, match="event preexists"):
            init_research_db(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT version FROM research_schema_version"
            ).scalar_one() == "0002"
    finally:
        engine.dispose()


def test_0003_refuses_malformed_checkpoint_table_without_advancing_marker(tmp_path):
    """A failed 0003 preflight must remain failed after a second initializer call."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE research_operation_item")
            connection.exec_driver_sql(
                "CREATE TABLE research_operation_item "
                "(owner_id VARCHAR(64), operation_id VARCHAR(64), item_key VARCHAR(128))"
            )
            connection.exec_driver_sql("UPDATE research_schema_version SET version='0002'")
        for _ in range(2):
            with pytest.raises((ResearchMigrationError, RuntimeError), match="contract"):
                init_research_db(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT version FROM research_schema_version"
            ).scalar_one() == "0002"
    finally:
        engine.dispose()


@pytest.mark.parametrize("foreign_keys", [0, 1])
def test_0002_never_changes_caller_foreign_key_mode(tmp_path, foreign_keys):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        migration = importlib.import_module("research.domain.migrations.0002_owner_operations")
        table = ResearchBase.metadata.tables["research_operation"]
        with engine.connect() as connection:
            connection.exec_driver_sql(f"PRAGMA foreign_keys={foreign_keys}")
            migration.upgrade(connection, table)
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == foreign_keys
            connection.commit()
    finally:
        engine.dispose()
