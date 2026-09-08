"""Execution migration parity for additive Phase 4 authority storage."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.db import migrate
from app.db.models import AuthorityProviderEntity, Base, _PHASE4_SECRET_FUNCTION
from app.market_truth.identity import ProviderEntity

BACKEND = Path(__file__).parents[1]
BASELINE = BACKEND / "migrations" / "baseline_schema.ddl"
AUTHORITY_TABLES = {
    "authority_canonical_instruments", "authority_provider_entities",
    "authority_provider_products", "authority_provider_contracts",
    "authority_provider_aliases", "authority_raw_segments",
    "authority_provider_observations", "authority_normalized_observations",
    "authority_normalized_observation_inputs", "authority_market_truth_snapshots",
    "authority_provider_conformance", "authority_capability_profiles",
    "authority_capability_assessments",
    "authority_raw_schemas", "authority_normalization_transforms",
    "authority_alignment_policies", "authority_missing_data_policies",
    "authority_adjustment_policies", "authority_roll_policies",
    "authority_dataset_corrections", "authority_dataset_creation_evidence",
    "authority_deterministic_algorithms",
}
LEGACY_TABLES = {
    "market_truth_instruments", "market_truth_provider_mappings",
    "market_truth_snapshots", "market_data_capability_profiles",
}


def _sqlite(tmp_path, name):
    return sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)


def _apply_baseline(engine):
    ddl = "\n".join(line for line in BASELINE.read_text().splitlines()
                    if not line.strip().startswith("--"))
    with engine.begin() as connection:
        for statement in (item.strip() for item in ddl.split(";") if item.strip()):
            connection.execute(sa.text(statement))


def _migrate_empty_sqlite(tmp_path, name="migrated.db"):
    engine = _sqlite(tmp_path, name)
    _apply_baseline(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES ('0001')"))
        command.upgrade(migrate.alembic_config(connection), "0039")
    return engine


def _shape(engine, tables):
    inspector = sa.inspect(engine)
    return {table: [(column["name"], str(column["type"]), column["nullable"])
                    for column in inspector.get_columns(table)] for table in sorted(tables)}


def test_adv_013_0039_is_exact_single_head_and_refuses_version_skew_downgrade(tmp_path):
    script = ScriptDirectory.from_config(migrate.alembic_config())
    assert script.get_revision("0038").down_revision == "0037"
    assert script.get_revision("0039").down_revision == "0038"
    assert script.get_revision("0040").down_revision == "0039"
    engine = _migrate_empty_sqlite(tmp_path)
    assert migrate.schema_version(engine) == "0039"
    with pytest.raises(RuntimeError, match="refuses destructive"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0038")
    assert migrate.schema_version(engine) == "0039"


def test_adv_014_0039_sqlite_fresh_migration_matches_model_ddl(tmp_path):
    migrated = _migrate_empty_sqlite(tmp_path)
    fresh = _sqlite(tmp_path, "fresh.db")
    Base.metadata.create_all(fresh)
    expected = _shape(fresh, AUTHORITY_TABLES | LEGACY_TABLES)
    expected["authority_provider_aliases"] = [column for column in expected["authority_provider_aliases"]
        if column[0] not in {"provider_contract_address", "receipt_address"}]
    assert _shape(migrated, AUTHORITY_TABLES | LEGACY_TABLES) == expected
    inspector = sa.inspect(migrated)
    assert AUTHORITY_TABLES <= set(inspector.get_table_names())
    assert all(any(column["name"] == "authority_state" for column in inspector.get_columns(table))
               for table in LEGACY_TABLES)


def test_adv_011_0037_opaque_rows_remain_legacy_unverified(tmp_path):
    engine = _sqlite(tmp_path, "upgrade.db")
    _apply_baseline(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES ('0001')"))
        command.upgrade(migrate.alembic_config(connection), "0037")
        connection.execute(sa.text(
            "INSERT INTO market_truth_instruments(address,identity_json,created_at) "
            "VALUES (:a,:j,CURRENT_TIMESTAMP)"),
            {"a": "sha256:" + "a" * 64, "j": '{"legacy":"opaque"}'})
        command.upgrade(migrate.alembic_config(connection), "0039")
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT authority_state FROM market_truth_instruments")) == "LEGACY_UNVERIFIED"


def test_adv_012_mixed_legacy_and_typed_rows_cannot_cross_authority(tmp_path):
    engine = _sqlite(tmp_path, "mixed.db")
    _apply_baseline(engine)
    legacy_address = "sha256:" + "b" * 64
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES ('0001')"))
        command.upgrade(migrate.alembic_config(connection), "0037")
        connection.execute(sa.text(
            "INSERT INTO market_truth_instruments(address,identity_json,created_at) "
            "VALUES (:a,:j,CURRENT_TIMESTAMP)"),
            {"a": legacy_address, "j": '{"legacy":"opaque"}'})
        command.upgrade(migrate.alembic_config(connection), "0039")
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO authority_canonical_instruments "
                "(address,schema,canonical_json,venue_code,asset_class,contract_kind,currency,"
                "economic_underlier_address,authority_state,created_at) VALUES "
                "(:a,'canonical-instrument/1','{}','XNSE','OPTION','WEEKLY_OPTION','INR',"
                ":legacy,'VERIFIED_V2',CURRENT_TIMESTAMP)"),
                {"a": "sha256:" + "c" * 64, "legacy": legacy_address})
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT authority_state FROM market_truth_instruments WHERE address=:a"),
            {"a": legacy_address}) == "LEGACY_UNVERIFIED"
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM authority_canonical_instruments")) == 0


def test_adv_015_actual_0037_upgrade_restart_preserves_audit_rows(monkeypatch, tmp_path):
    engine = _sqlite(tmp_path, "restart.db")
    _apply_baseline(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES ('0001')"))
        command.upgrade(migrate.alembic_config(connection), "0037")
        connection.execute(sa.text(
            "INSERT INTO market_truth_instruments(address,identity_json,created_at) "
            "VALUES (:a,:j,CURRENT_TIMESTAMP)"),
            {"a": "sha256:" + "d" * 64, "j": '{"legacy":"audit"}'})
    from app.db.models import AuthorityProviderProduct
    original = AuthorityProviderProduct.__table__.create
    interrupted = False

    def fail_once(*args, **kwargs):
        nonlocal interrupted
        original(*args, **kwargs)
        if not interrupted:
            interrupted = True
            raise RuntimeError("injected 0038 interruption")

    monkeypatch.setattr(AuthorityProviderProduct.__table__, "create", fail_once)
    with pytest.raises(RuntimeError, match="injected 0038 interruption"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0038")
    assert migrate.schema_version(engine) == "0037"
    monkeypatch.setattr(AuthorityProviderProduct.__table__, "create", original)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0038")
    assert migrate.schema_version(engine) == "0038"
    engine.dispose()
    restarted = _sqlite(tmp_path, "restart.db")
    assert migrate.schema_version(restarted) == "0038"
    with restarted.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT identity_json, authority_state FROM market_truth_instruments"
        )).one() == ('{"legacy":"audit"}', "LEGACY_UNVERIFIED")


def test_adv_015_interrupted_0039_rolls_back_then_restarts_at_exact_head(monkeypatch, tmp_path):
    engine = _sqlite(tmp_path, "restart-0039.db")
    _apply_baseline(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES ('0001')"))
        command.upgrade(migrate.alembic_config(connection), "0038")

    from app.db.models import AuthorityDatasetCreationEvidence
    original = AuthorityDatasetCreationEvidence.__table__.create
    interrupted = False

    def fail_once(*args, **kwargs):
        nonlocal interrupted
        original(*args, **kwargs)
        if not interrupted:
            interrupted = True
            raise RuntimeError("injected 0039 interruption")

    monkeypatch.setattr(AuthorityDatasetCreationEvidence.__table__, "create", fail_once)
    with pytest.raises(RuntimeError, match="injected 0039 interruption"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0039")
    assert migrate.schema_version(engine) == "0038"
    interrupted_tables = set(sa.inspect(engine).get_table_names())
    assert {"authority_raw_schemas", "authority_dataset_creation_evidence"} <= interrupted_tables
    assert "authority_deterministic_algorithms" not in interrupted_tables

    monkeypatch.setattr(AuthorityDatasetCreationEvidence.__table__, "create", original)
    engine.dispose()
    restarted = _sqlite(tmp_path, "restart-0039.db")
    with restarted.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0039")
    assert migrate.schema_version(restarted) == "0039"
    assert AUTHORITY_TABLES <= set(sa.inspect(restarted).get_table_names())


def test_0039_sqlite_constraints_triggers_and_transaction_atomicity(tmp_path):
    engine = _migrate_empty_sqlite(tmp_path)
    address = "sha256:" + "a" * 64
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO authority_provider_entities "
                "(address,schema,canonical_json,entity_code,authority_state,created_at) "
                "VALUES (:a,'provider-entity/1','{}','x','LEGACY_UNVERIFIED',CURRENT_TIMESTAMP)"),
                {"a": address})
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM authority_provider_entities")) == 0
        triggers = {row[0] for row in connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))}
    assert "authority_provider_entities_refuse_update" in triggers
    assert "authority_provider_aliases_refuse_overlap" in triggers


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="disposable PostgreSQL 16 URL not supplied")
def test_0038_disposable_postgresql16_fresh_upgrade_restart_model_and_trigger_parity(
    pg_sandbox,
):
    engine = pg_sandbox.execution_engine
    # Fresh-install contract: an empty database reaches exactly the one
    # current head, whatever it is — not a pinned number that rots.
    assert migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
        expected_tables=Base.metadata.tables) == migrate.head_revision()
    fresh_shape = _shape(engine, AUTHORITY_TABLES | LEGACY_TABLES)
    # Exactly one migration head may exist, and it is what installs target.
    assert ScriptDirectory.from_config(
        migrate.alembic_config()).get_heads() == [migrate.head_revision()]
    assert migrate.init_schema(
        engine, create_all=lambda: (_ for _ in ()).throw(AssertionError("create path")),
        legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
        expected_tables=Base.metadata.tables) == migrate.head_revision()
    engine = pg_sandbox.engine("historical_0037")
    historical = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in AUTHORITY_TABLES:
            copied = table.to_metadata(historical)
            if table.name in LEGACY_TABLES:
                copied._columns.remove(copied.c.authority_state)
    with engine.begin() as connection:
        connection.execute(sa.text(_PHASE4_SECRET_FUNCTION.replace("%%", "%")))
        historical.create_all(connection)
        command.stamp(migrate.alembic_config(connection), "0037")
        connection.execute(sa.text(
            "INSERT INTO market_truth_instruments(address,identity_json,created_at) "
            "VALUES (:a,:j,CURRENT_TIMESTAMP)"),
            {"a": "sha256:" + "a" * 64, "j": '{"legacy":"opaque"}'})
        command.upgrade(migrate.alembic_config(connection), "0039")
    assert migrate.schema_version(engine) == "0039"
    migrated_shape = _shape(engine, AUTHORITY_TABLES | LEGACY_TABLES)
    historical_shape = dict(fresh_shape)
    historical_shape["authority_provider_aliases"] = [column for column in fresh_shape["authority_provider_aliases"]
        if column[0] not in {"provider_contract_address", "receipt_address"}]
    assert migrated_shape == historical_shape
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT authority_state FROM market_truth_instruments")) == "LEGACY_UNVERIFIED"
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM pg_trigger WHERE tgname="
            "'authority_provider_aliases_refuse_overlap'")) == 1
    entity = ProviderEntity("strategy-os", "atomic-provider", "Atomic Provider Ltd")
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(sa.insert(AuthorityProviderEntity), {
                "address": entity.address, "schema": entity.SCHEMA,
                "canonical_json": entity.canonical_bytes.decode(),
                "entity_code": entity.entity_code, "authority_state": "VERIFIED_V2"})
            connection.execute(sa.text(
                "INSERT INTO authority_provider_entities "
                "(address,schema,canonical_json,entity_code,authority_state,created_at) "
                "VALUES (:a,'provider-entity/1','{}','invalid','LEGACY_UNVERIFIED',CURRENT_TIMESTAMP)"),
                {"a": "sha256:" + "f" * 64})
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM authority_provider_entities WHERE address=:a"),
            {"a": entity.address}) == 0
    with engine.begin() as connection:
        connection.execute(sa.insert(AuthorityProviderEntity), {
            "address": entity.address, "schema": entity.SCHEMA,
            "canonical_json": entity.canonical_bytes.decode(),
            "entity_code": entity.entity_code, "authority_state": "VERIFIED_V2"})
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE authority_provider_entities SET entity_code='changed' WHERE address=:a"),
                {"a": entity.address})
    with pytest.raises(RuntimeError, match="refuses destructive"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0038")
    assert migrate.schema_version(engine) == "0039"
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0039")
    assert migrate.schema_version(engine) == "0039"
    recreated = pg_sandbox.engine("fresh_recreated")
    Base.metadata.create_all(recreated)
    assert _shape(recreated, AUTHORITY_TABLES | LEGACY_TABLES) == fresh_shape


_ALIAS_DEPENDENCY_TABLES = (
    "authority_canonical_instruments", "authority_provider_entities", "authority_provider_products",
    "authority_provider_contracts", "authority_provider_aliases", "authority_raw_segments",
    "authority_provider_observations")


def _seed_v1_alias_migration(engine):
    """Put actual closed /1 observation bytes into the historical schema."""
    from sqlalchemy.orm import Session
    from tests.test_v0_kite_observations import authorities, T0, dt, map_historical_candles
    from app.market_data.observations import persist_raw_segment, persist_provider_observation
    source = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(source)
    with Session(source) as session, session.begin():
        context, _ = authorities(session=session)
        batch = map_historical_candles({"status": "success", "data": {"candles": [
            ["2026-08-31T09:15:00+05:30", 100, 102, 99, 101, 1234]]}},
            context=context, resolution_seconds=900,
            available_at=T0+dt.timedelta(minutes=16), recorded_at=T0+dt.timedelta(minutes=17),
            as_of=T0+dt.timedelta(minutes=18))
        for raw in batch.raw_segments:
            persist_raw_segment(session, raw)
        for observation in batch.observations:
            persist_provider_observation(session, observation)
    with source.connect() as original, engine.begin() as target:
        for name in _ALIAS_DEPENDENCY_TABLES:
            table = sa.Table(name, sa.MetaData(), autoload_with=target)
            rows = original.execute(sa.select(Base.metadata.tables[name])).mappings().all()
            if rows:
                target.execute(table.insert(), [{key: value for key, value in row.items() if key in table.c}
                                                for row in rows])
    source.dispose()
    return context.mapping, batch.observations


def _alias_migration_snapshot(engine):
    with engine.connect() as connection:
        return {name: tuple(connection.execute(sa.text(
            f"SELECT address, canonical_json FROM {name} ORDER BY address")))
            for name in _ALIAS_DEPENDENCY_TABLES}


def _verify_alias_migration(engine, alias, observations, snapshot):
    from sqlalchemy.orm import Session
    from app.market_truth.identity import load_provider_alias
    from app.market_data.observations import load_provider_observation
    assert _alias_migration_snapshot(engine) == snapshot
    with Session(engine) as session:
        assert load_provider_alias(session, alias.address) == alias
        assert tuple(load_provider_observation(session, item.address) for item in observations) == observations
    with engine.begin() as connection, pytest.raises(sa.exc.DBAPIError, match="immutable"):
        connection.exec_driver_sql("UPDATE authority_provider_aliases SET provider_symbol = 'REWRITE'")
    with engine.begin() as connection, pytest.raises(sa.exc.DBAPIError, match="immutable"):
        connection.exec_driver_sql("DELETE FROM authority_provider_aliases")
    from dataclasses import replace
    collision = replace(alias, provider_token="other-token")
    with engine.begin() as connection, pytest.raises(sa.exc.DBAPIError, match="overlaps"):
        table = sa.Table("authority_provider_aliases", sa.MetaData(), autoload_with=connection)
        typed = dict(connection.execute(sa.select(table).where(table.c.address == alias.address)).mappings().one())
        typed.update(address=collision.address, canonical_json=collision.canonical_bytes.decode(),
                     provider_token=collision.provider_token)
        connection.execute(table.insert().values(**typed))



@pytest.mark.parametrize("foreign_keys", [False, True])
def test_response_alias_0055_sqlite_preserves_populated_inbound_fks_and_restore(tmp_path, foreign_keys):
    import sqlite3
    from tests.test_schema_migrations import _build_from_baseline_at_revision
    from tests.test_capital_admission_schema import _contract
    engine = _build_from_baseline_at_revision(tmp_path, "alias-0054.db", "0054")
    alias, observations = _seed_v1_alias_migration(engine)
    before = _alias_migration_snapshot(engine)
    with engine.connect() as connection:
        connection.connection.driver_connection.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")
    assert migrate.upgrade_to_head(engine) == "0055"
    assert migrate.upgrade_to_head(engine) == "0055"
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == int(foreign_keys)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        fks = sa.inspect(connection).get_foreign_keys("authority_provider_observations")
        assert any(fk["referred_table"] == "authority_provider_aliases" for fk in fks)
    _verify_alias_migration(engine, alias, observations, before)
    fresh = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(fresh)
    assert _contract(engine, "authority_provider_aliases") == _contract(fresh, "authority_provider_aliases")
    with sqlite3.connect(engine.url.database) as source, sqlite3.connect(tmp_path/"alias-restored.db") as restored:
        source.backup(restored)
    restored_engine = sa.create_engine(f"sqlite:///{tmp_path}/alias-restored.db")
    assert migrate.schema_version(restored_engine) == "0055"
    _verify_alias_migration(restored_engine, alias, observations, before)
    with engine.begin() as connection, pytest.raises(RuntimeError, match="retains response"):
        command.downgrade(migrate.alembic_config(connection), "0054")
    for item in (engine, fresh, restored_engine):
        item.dispose()


@pytest.mark.parametrize("foreign_keys", [False, True])
@pytest.mark.parametrize("boundary", ["copy", "drop", "rename", "stamp"])
def test_response_alias_0055_rolls_back_every_rebuild_boundary_and_restores_fk_mode(tmp_path, foreign_keys, boundary):
    from tests.test_schema_migrations import _build_from_baseline_at_revision
    engine = _build_from_baseline_at_revision(tmp_path, "alias-interrupt.db", "0054")
    alias, observations = _seed_v1_alias_migration(engine)
    before = _alias_migration_snapshot(engine)
    with engine.connect() as connection:
        connection.connection.driver_connection.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")
    targets = {"copy": "INSERT INTO _0055_AUTHORITY_PROVIDER_ALIASES", "drop": "DROP TABLE AUTHORITY_PROVIDER_ALIASES",
        "rename": "ALTER TABLE _0055_AUTHORITY_PROVIDER_ALIASES RENAME", "stamp": "UPDATE ALEMBIC_VERSION"}
    def interrupt(_connection, _cursor, statement, *_args):
        if targets[boundary] in " ".join(statement.upper().split()):
            raise RuntimeError("injected alias rebuild interruption")
    sa.event.listen(engine, "after_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected alias"):
            migrate.upgrade_to_head(engine)
    finally:
        sa.event.remove(engine, "after_cursor_execute", interrupt)
    assert migrate.schema_version(engine) == "0054"
    assert _alias_migration_snapshot(engine) == before
    assert "_0055_authority_provider_aliases" not in sa.inspect(engine).get_table_names()
    assert "receipt_address" not in {row["name"] for row in sa.inspect(engine).get_columns("authority_provider_aliases")}
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == int(foreign_keys)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert migrate.upgrade_to_head(engine) == "0055"
    _verify_alias_migration(engine, alias, observations, before)
    engine.dispose()


def _install_v1_alias_pg(engine):
    """Create the accepted0054 shape with frozen0038 /1 alias DDL."""
    script = ScriptDirectory.from_config(migrate.alembic_config())
    frozen = script.get_revision("0038").module.ALIAS_DDL["postgresql"]
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name == "authority_provider_aliases":
                for statement in frozen:
                    connection.exec_driver_sql(statement)
            else:
                table.create(connection)
        command.stamp(migrate.alembic_config(connection), "0054")


def test_response_alias_0055_postgresql_populated_upgrade_restore_and_native_scope(pg_sandbox, tmp_path):
    import subprocess
    from dataclasses import replace
    from sqlalchemy.orm import Session
    from tests.test_v0_kite_observations import _retrospective_inputs
    from tests.test_capital_admission_schema import _contract
    from app.market_truth.identity import persist_provider_identity, persist_provider_alias, MarketTruthError
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    engine = pg_sandbox.engine("alias_upgrade")
    restored = pg_sandbox.engine("alias_restored")
    fresh = pg_sandbox.engine("alias_fresh")
    _install_v1_alias_pg(engine)
    alias, observations = _seed_v1_alias_migration(engine)
    before = _alias_migration_snapshot(engine)
    def interrupt_alias_alter(_connection, _cursor, statement, *_args):
        if "ALTER TABLE authority_provider_aliases ADD COLUMN provider_contract_address" in statement:
            raise RuntimeError("injected PostgreSQL alias ALTER failure")
    sa.event.listen(engine, "after_cursor_execute", interrupt_alias_alter)
    try:
        with pytest.raises(RuntimeError, match="injected PostgreSQL"):
            migrate.upgrade_to_head(engine)
    finally:
        sa.event.remove(engine, "after_cursor_execute", interrupt_alias_alter)
    assert migrate.schema_version(engine) == "0054"
    assert _alias_migration_snapshot(engine) == before
    assert "receipt_address" not in {column["name"] for column in sa.inspect(engine).get_columns("authority_provider_aliases")}
    assert migrate.upgrade_to_head(engine) == "0055"
    assert migrate.upgrade_to_head(engine) == "0055"
    _verify_alias_migration(engine, alias, observations, before)
    Base.metadata.create_all(fresh)
    assert _contract(engine, "authority_provider_aliases") == _contract(fresh, "authority_provider_aliases")
    inputs = _retrospective_inputs()
    with Session(engine) as session, session.begin():
        first = prepare_historical_attribution(**inputs)
        other = replace(inputs["contract"], owner_id="owner-b")
        for contract in (inputs["contract"], other):
            persist_provider_identity(session, inputs["entity"], inputs["product"], contract)
        second = prepare_historical_attribution(**{**inputs, "owner_id": "owner-b", "contract": other})
        for attribution in (first, second, first):
            persist_historical_attribution(session, attribution)
        with pytest.raises(MarketTruthError, match="overlaps"):
            persist_provider_alias(session, replace(first.mapping, provider_symbol="CONTRADICTION"))
    conflict = replace(first.mapping, provider_symbol="NATIVE_CONTRADICTION")
    with engine.begin() as connection, pytest.raises(sa.exc.IntegrityError, match="uq_authority_provider_alias_response"):
        table = sa.Table("authority_provider_aliases", sa.MetaData(), autoload_with=connection)
        row = dict(connection.execute(sa.select(table).where(table.c.address == first.mapping.address)).mappings().one())
        row.update(address=conflict.address, canonical_json=conflict.canonical_bytes.decode(), provider_symbol=conflict.provider_symbol)
        connection.execute(table.insert().values(**row))
    from app.operations.postgresql_backup import resolve_postgresql16_tools
    pg_dump, pg_restore = resolve_postgresql16_tools()
    backup = tmp_path/"alias.dump"
    source_url = str(sa.engine.make_url(pg_sandbox.url("alias_upgrade")).set(drivername="postgresql"))
    target_url = str(sa.engine.make_url(pg_sandbox.url("alias_restored")).set(drivername="postgresql"))
    subprocess.run([str(pg_dump), "--format=custom", "--no-owner", "--no-acl", f"--file={backup}", source_url],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(pg_restore), "--no-owner", "--no-acl", "--exit-on-error", f"--dbname={target_url}", str(backup)],
                   check=True, capture_output=True, text=True)
    assert migrate.schema_version(restored) == "0055"
    _verify_alias_migration(restored, alias, observations, _alias_migration_snapshot(engine))
    from app.market_data.kite_historical_attribution import load_historical_attribution
    with Session(restored) as session:
        assert load_historical_attribution(session, first.mapping) == first
        assert load_historical_attribution(session, second.mapping) == second


@pytest.mark.parametrize("failure", ["temporary", "column", "stale", "orphan"])
def test_response_alias_0055_refuses_partial_stale_or_inconsistent_source(tmp_path, failure):
    from tests.test_schema_migrations import _build_from_baseline_at_revision
    engine = _build_from_baseline_at_revision(tmp_path, "alias-refusal.db", "0054")
    _seed_v1_alias_migration(engine)
    if failure == "orphan":
        with engine.connect() as connection:
            connection.connection.driver_connection.execute("PRAGMA foreign_keys=OFF")
    with engine.begin() as connection:
        if failure == "temporary":
            connection.exec_driver_sql("CREATE TABLE _0055_authority_provider_aliases (unproven INTEGER)")
        elif failure == "column":
            connection.exec_driver_sql("ALTER TABLE authority_provider_aliases ADD COLUMN receipt_address TEXT")
        elif failure == "stale":
            command.stamp(migrate.alembic_config(connection), "0053", purge=True)
        else:
            table = sa.Table("authority_provider_observations", sa.MetaData(), autoload_with=connection)
            row = dict(connection.execute(sa.select(table)).mappings().first())
            from dataclasses import replace
            from app.market_data.observations import ProviderObservation
            orphan = replace(ProviderObservation.from_bytes(row["canonical_json"].encode()),
                mapping_address="sha256:"+"b"*64, correction_id="orphan")
            row.update(address=orphan.address, canonical_json=orphan.canonical_bytes.decode(),
                       mapping_address=orphan.mapping_address, correction_id=orphan.correction_id)
            connection.execute(table.insert().values(**row))
    before = _alias_migration_snapshot(engine)
    with engine.connect() as connection:
        connection.connection.driver_connection.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(RuntimeError, match="partial|exact accepted|foreign keys"):
        migrate.upgrade_to_head(engine)
    assert migrate.schema_version(engine) == ("0053" if failure == "stale" else "0054")
    assert _alias_migration_snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    engine.dispose()


def test_response_alias_0055_direct_migration_requires_pretransaction_fk_suspension(tmp_path):
    from tests.test_schema_migrations import _build_from_baseline_at_revision
    engine = _build_from_baseline_at_revision(tmp_path, "alias-direct.db", "0054")
    with engine.connect() as connection:
        connection.connection.driver_connection.execute("PRAGMA foreign_keys=ON")
    with engine.begin() as connection, pytest.raises(RuntimeError, match="managed SQLite foreign-key suspension"):
        command.upgrade(migrate.alembic_config(connection), "0055")
    assert migrate.schema_version(engine) == "0054"
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    # An explicitly suspended connection still gets an atomic BEGIN before DDL.
    with engine.connect() as connection:
        connection.connection.driver_connection.execute("PRAGMA foreign_keys=OFF")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0055")
    assert migrate.schema_version(engine) == "0055"
    engine.dispose()


def test_response_alias_0055_source_refuses_wrong_head_and_unsupported_dialect(tmp_path):
    from types import SimpleNamespace
    from tests.test_schema_migrations import _build_from_baseline_at_revision
    module = ScriptDirectory.from_config(migrate.alembic_config()).get_revision("0055").module
    with pytest.raises(RuntimeError, match="unsupported database dialect"):
        module._source(SimpleNamespace(dialect=SimpleNamespace(name="unsupported")))
    engine = _build_from_baseline_at_revision(tmp_path, "alias-source.db", "0053")
    with engine.connect() as connection:
        connection.connection.driver_connection.execute("PRAGMA foreign_keys=OFF")
    with engine.begin() as connection, pytest.raises(RuntimeError, match="requires exact 0054 source"):
        module._source(connection)
    assert migrate.schema_version(engine) == "0053"
    engine.dispose()


@pytest.fixture(autouse=True)
def _freeze_response_alias_0055_head(request, monkeypatch):
    if request.node.name.startswith("test_response_alias_0055_"):
        monkeypatch.setattr(migrate, "head_revision", lambda: "0055")
