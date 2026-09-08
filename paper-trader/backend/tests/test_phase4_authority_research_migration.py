"""Migration and database parity for typed Phase 4 dataset authority."""
from __future__ import annotations

import hashlib
import importlib
import os

import pytest
import sqlalchemy as sa

from research.domain import migrate
from research.domain.base import ResearchBase
from research_tests.test_ir_v2_research_migration import (
    _REFUSAL_PATTERN,
    _postgresql_logical_digest,
    _sqlite_logical_digest,
)
AUTHORITY_TABLES = {
    "research_dataset_segments_v2",
    "research_dataset_manifests_v2",
    "research_dataset_manifest_segments_v2",
}


def _shape(engine: sa.Engine) -> dict[str, list[tuple[str, str, bool]]]:
    inspector = sa.inspect(engine)
    return {
        table: [
            (column["name"], str(column["type"]), column["nullable"])
            for column in inspector.get_columns(table)
        ]
        for table in sorted(AUTHORITY_TABLES)
    }


def _sqlite(tmp_path, name: str) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    return engine


def _create_0008_sqlite(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        tables = migrate._pre_0009_tables()
        for table in tables:
            table.create(connection)
        for sql in migrate._expected_triggers(tables=tables).values():
            connection.exec_driver_sql(sql)
        migrate._stamp(connection, version="0008")


def _create_0009_sqlite(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        tables = migrate._pre_0010_tables()
        for table in tables:
            table.create(connection)
        for sql in migrate._expected_triggers(tables=tables).values():
            connection.exec_driver_sql(sql)
        migrate._stamp(connection, version="0009")


def _rewind_postgresql_json_constraints(engine: sa.Engine, indexes=range(3, 8)) -> None:
    migration = importlib.import_module(
        "research.domain.migrations.0010_research_json_shape_parity")
    historical = {table.name: table for table in migrate._pre_0010_tables()}
    with engine.begin() as connection:
        for index in indexes:
            table_name, constraint_name, _column, _shape = migration.JSON_SHAPE_SITES[index]
            constraint = next(
                item for item in historical[table_name].constraints
                if isinstance(item, sa.CheckConstraint) and item.name == constraint_name
            )
            expression = str(constraint.sqltext.compile(dialect=connection.dialect))
            connection.exec_driver_sql(
                f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{constraint_name}"')
            connection.exec_driver_sql(
                f'ALTER TABLE "{table_name}" ADD CONSTRAINT "{constraint_name}" '
                f'CHECK ({expression})')
        connection.execute(sa.text(
            "UPDATE research_schema_version SET version='0009'"))


def test_adv_013_0011_is_exact_head_and_refuses_destructive_downgrade(tmp_path):
    engine = _sqlite(tmp_path, "head.db")
    migrate.migrate_research_db(engine)
    assert migrate.head_version() == migrate.HEAD_VERSION == "0011"
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT version FROM research_schema_version")) == "0011"
    with pytest.raises(migrate.ResearchMigrationError, match="refuses destructive"):
        migrate.downgrade_research_db(engine)


def test_adv_014_sqlite_fresh_migration_matches_model_ddl(tmp_path):
    migrated = _sqlite(tmp_path, "migrated.db")
    migrate.migrate_research_db(migrated)
    fresh = _sqlite(tmp_path, "fresh.db")
    ResearchBase.metadata.create_all(fresh)
    assert _shape(migrated) == _shape(fresh)
    with migrated.connect() as connection:
        triggers = {row[0] for row in connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))}
    for table in AUTHORITY_TABLES:
        assert f"trg_{table}_no_update" in triggers
        assert f"trg_{table}_no_delete" in triggers


def test_adv_011_012_actual_0008_refuses_and_keeps_legacy_audit_only(tmp_path):
    engine = _sqlite(tmp_path, "upgrade.db")
    _create_0008_sqlite(engine)
    legacy_address = "sha256:" + "a" * 64
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO research_dataset_manifests "
            "(owner_id,digest,provider,dataset_version,market_truth_digest,"
            "capability_digest,manifest_json,created_at) VALUES "
            "('owner-a',:address,'legacy','v1',:address,:address,:manifest,CURRENT_TIMESTAMP)"
        ), {
            "address": legacy_address,
            "manifest": (
                '{"owner_id":"owner-a","provider":"legacy","dataset_version":"v1",'
                '"market_truth_digest":"' + legacy_address + '",'
                '"capability_digest":"' + legacy_address + '","schema_version":1}'
            ),
        })
    before = _sqlite_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert _sqlite_logical_digest(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM research_dataset_manifests WHERE digest=:address"
        ), {"address": legacy_address}) == 1
        assert "research_dataset_manifests_v2" not in sa.inspect(connection).get_table_names()


@pytest.mark.parametrize("target_boundary", (1, 2, 3, 8))
def test_adv_015_retained_0009_refuses_without_marker_only_trust(
        monkeypatch, tmp_path, target_boundary):
    engine = _sqlite(tmp_path, f"restart-{target_boundary}.db")
    _create_0009_sqlite(engine)
    before = _sqlite_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert _sqlite_logical_digest(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT version FROM research_schema_version")) == "0009"
    engine.dispose()
    restarted = _sqlite(tmp_path, f"restart-{target_boundary}.db")
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(restarted)
    assert _sqlite_logical_digest(restarted) == before


def test_0010_refuses_unrelated_sqlite_drift_before_mutation(tmp_path):
    engine = _sqlite(tmp_path, "drift.db")
    _create_0009_sqlite(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_research_dataset_manifest_owner_created")
    before = _sqlite_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert _sqlite_logical_digest(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT version FROM research_schema_version")) == "0009"


def test_0010_refuses_nonprefix_sqlite_old_new_shape_hybrid(tmp_path):
    engine = _sqlite(tmp_path, "shape-hybrid.db")
    _create_0009_sqlite(engine)
    table = ResearchBase.metadata.tables["research_strategy_admission"]
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        migrate._rebuild_table(connection, table, notify=False)
        migrate._restore_table_contracts(connection, table)
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    before = _sqlite_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert _sqlite_logical_digest(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT version FROM research_schema_version")) == "0009"


def test_exact_0009_refusal_preserves_typed_rows_and_json_bytes(tmp_path):
    engine = _sqlite(tmp_path, "preserve.db")
    _create_0009_sqlite(engine)
    segment = "sha256:" + "b" * 64
    manifest = "sha256:" + "c" * 64
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO research_dataset_segments_v2 "
            "(owner_id,segment_address,canonical_bytes,object_bytes,object_address,"
            "byte_digest,byte_length,event_start,event_end,availability_start,"
            "availability_end,authority_state) VALUES "
            "('owner-a',:segment,:payload,:payload,:segment,:segment,1,"
            "'2025-01-01T00:00:00Z','2025-01-01T00:00:01Z',"
            "'2025-01-01T00:00:00Z','2025-01-01T00:00:01Z','VERIFIED_V2')"
        ), {"segment": segment, "payload": b"x"})
        connection.execute(sa.text(
            "INSERT INTO research_dataset_manifests_v2 "
            "(owner_id,manifest_address,canonical_bytes,aggregate_byte_digest,"
            "aggregate_byte_length,segment_addresses_json,instrument_addresses_json,"
            "fields_json,gaps_json,dependency_addresses_json,event_start,event_end,"
            "availability_start,availability_end,authority_state) VALUES "
            "('owner-a',:manifest,:payload,:segment,1,:segments,'[]','[\"close\"]',"
            "'[]','[]','2025-01-01T00:00:00Z','2025-01-01T00:00:01Z',"
            "'2025-01-01T00:00:00Z','2025-01-01T00:00:01Z','VERIFIED_V2')"
        ), {"manifest": manifest, "segment": segment, "payload": b"manifest",
            "segments": f'["{segment}"]'})
        connection.execute(sa.text(
            "INSERT INTO research_dataset_manifest_segments_v2 "
            "(owner_id,manifest_address,ordinal,segment_address) "
            "VALUES ('owner-a',:manifest,0,:segment)"
        ), {"manifest": manifest, "segment": segment})

    def snapshot():
        with engine.connect() as connection:
            rows = tuple(
                tuple(connection.execute(sa.text(
                    f'SELECT * FROM "{name}" ORDER BY 1,2'
                )).all())
                for name in sorted(AUTHORITY_TABLES)
            )
        return rows, hashlib.sha256(repr(rows).encode()).hexdigest()

    before_rows, before_hash = snapshot()
    complete_before = _sqlite_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    after_rows, after_hash = snapshot()
    assert after_rows == before_rows
    assert after_hash == before_hash
    assert _sqlite_logical_digest(engine) == complete_before
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert snapshot() == (after_rows, after_hash)


@pytest.mark.skipif(
    not os.environ.get("PT_TEST_POSTGRES_URL"),
    reason="disposable PostgreSQL 16 URL not supplied",
)
def test_adv_016_disposable_postgresql_fresh_0011_restart_and_hybrid_refusal(
    pg_sandbox,
):
    engine = pg_sandbox.research_engine
    migrate.migrate_research_db(engine)
    fresh_shape = _shape(engine)
    migrate.migrate_research_db(engine)
    assert _shape(engine) == fresh_shape

    with engine.begin() as connection:
        for name in (
            "research_dataset_manifest_segments_v2",
            "research_dataset_manifests_v2",
            "research_dataset_segments_v2",
        ):
            ResearchBase.metadata.tables[name].drop(connection)
        connection.execute(sa.text(
            "UPDATE research_schema_version SET version='0008'"))
    hybrid = _postgresql_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert _postgresql_logical_digest(engine) == hybrid
    engine.dispose()


@pytest.mark.skipif(
    not os.environ.get("PT_TEST_POSTGRES_URL"),
    reason="disposable PostgreSQL 16 URL not supplied",
)
def test_postgresql_old_json_constraint_hybrid_refuses_transactionally(monkeypatch, pg_sandbox):
    engine = pg_sandbox.research_engine
    # The sandbox database is verified empty before use; no drop choreography.
    migrate.migrate_research_db(engine)
    _rewind_postgresql_json_constraints(engine)

    segment = "sha256:" + "d" * 64
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO research_dataset_segments_v2 "
            "(owner_id,segment_address,canonical_bytes,object_bytes,object_address,"
            "byte_digest,byte_length,event_start,event_end,availability_start,"
            "availability_end,authority_state) VALUES "
            "('owner-pg',:segment,:payload,:payload,:segment,:segment,1,"
            "'2025-01-01T00:00:00Z','2025-01-01T00:00:01Z',"
            "'2025-01-01T00:00:00Z','2025-01-01T00:00:01Z','VERIFIED_V2')"
        ), {"segment": segment, "payload": b"p"})

    def snapshot():
        with engine.connect() as connection:
            rows = tuple(
                tuple(connection.execute(sa.text(
                    f'SELECT * FROM "{name}" ORDER BY 1,2'
                )).all())
                for name in sorted(AUTHORITY_TABLES)
            )
        return rows, hashlib.sha256(repr(rows).encode()).hexdigest()

    before_rows, before_hash = snapshot()
    complete_before = _postgresql_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        migrate.migrate_research_db(engine)
    assert _postgresql_logical_digest(engine) == complete_before
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT version FROM research_schema_version")) == "0009"
    assert snapshot() == (before_rows, before_hash)
    engine.dispose()
