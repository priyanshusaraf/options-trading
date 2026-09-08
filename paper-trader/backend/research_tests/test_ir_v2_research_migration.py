"""Research-plane migration evidence for v2 receipts and graph facts."""

from __future__ import annotations

# Register every mapped table BEFORE any fixture touches
# ``ResearchBase.metadata``: the runner registers models only inside
# ``migrate_research_db``, which is too late for fixtures that build a full
# current schema first (create_all then selectively drop).
from research.domain import models as _research_models  # noqa: F401

import importlib
import hashlib
import os

import pytest
from sqlalchemy import MetaData, inspect, text

from research.domain import migrate
from research.domain.base import ResearchBase, init_research_db, make_engine


def _sqlite_logical_digest(engine) -> str:
    """Digest every durable SQLite catalog, row, sequence, and marker fact."""
    with engine.connect() as connection:
        catalog = tuple(connection.exec_driver_sql(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
        ).all())
        rows = []
        for table in connection.exec_driver_sql(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        ).scalars():
            rows.append((table, tuple(connection.exec_driver_sql(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).all())))
    return hashlib.sha256(repr((catalog, tuple(rows))).encode()).hexdigest()


def _postgresql_logical_digest(engine) -> str:
    """Digest the complete native catalog, rows, sequences, and marker."""
    with engine.connect() as connection:
        tables = tuple(connection.exec_driver_sql(
            "SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY 1"
        ).scalars())
        rows = tuple((table, tuple(connection.exec_driver_sql(
            f'SELECT * FROM "{table}" ORDER BY 1'
        ).all())) for table in tables)
        relations = tuple(connection.exec_driver_sql(
            "SELECT c.relkind,c.relname FROM pg_class c "
            "WHERE c.relnamespace=current_schema()::regnamespace ORDER BY 1,2"
        ).all())
        functions = tuple(connection.exec_driver_sql(
            "SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p "
            "WHERE p.pronamespace=current_schema()::regnamespace ORDER BY 1"
        ).all())
        triggers = tuple(connection.exec_driver_sql(
            "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid "
            "WHERE c.relnamespace=current_schema()::regnamespace "
            "AND NOT t.tgisinternal ORDER BY 1,2"
        ).all())
        sequences = []
        for name in connection.exec_driver_sql(
            "SELECT relname FROM pg_class WHERE "
            "relnamespace=current_schema()::regnamespace AND relkind='S' ORDER BY 1"
        ).scalars():
            sequences.append((name, *connection.exec_driver_sql(
                f'SELECT last_value,is_called FROM "{name}"'
            ).one()))
    return hashlib.sha256(
        repr((relations, functions, triggers, tuple(sequences), rows)).encode()
    ).hexdigest()


_REFUSAL_PATTERN = "Back up.*diagnostic/export.*rebuild"


def _legacy_artifact(owner: str = "legacy-owner") -> tuple[str, str]:
    from app.ir.hashing import canonical_json, content_address

    document = {
        "owner_id": owner,
        "graph_identifier": "legacy-graph",
        "graph_version": 1,
        "graph_address": "sha256:" + "1" * 64,
        "scheme": "v1",
        "contract_suite": "legacy",
        "parity_suite": "legacy",
    }
    encoded = canonical_json(document)
    return encoded, content_address(document)


def _make_populated_0005(path):
    """Create the exact pre-0006 schema with one admitted legacy row."""
    tables = migrate._pre_0006_tables()
    metadata = MetaData()
    for table in tables:
        table.to_metadata(metadata)
    engine = make_engine(str(path))
    with engine.begin() as connection:
        metadata.create_all(connection)
        for table_name in ("research_experiment_spec", "research_optimization_trial",
                           "research_strategy_admission"):
            if table_name not in {table.name for table in tables}:
                continue
            for operation in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER trg_{table_name}_no_{operation.lower()} "
                    f"BEFORE {operation} ON {table_name} BEGIN "
                    f"SELECT RAISE(ABORT, '{table_name} is immutable'); END")
        connection.execute(text(
            'CREATE TABLE "research_schema_version" '
            '(version VARCHAR(16) NOT NULL PRIMARY KEY, schema_cookie INTEGER NOT NULL)'))
        connection.execute(text(
            'INSERT INTO "research_schema_version" (version, schema_cookie) '
            'VALUES (\'0005\', 0)'))
        artifact, address = _legacy_artifact()
        connection.execute(text(
            'INSERT INTO research_strategy_admission '
            '(owner_id, admission_address, graph_identifier, graph_version, graph_address, '
            'artifact_json, scheme, contract_suite, parity_suite, created_at) '
            'VALUES (:owner, :address, :identifier, 1, :graph, :artifact, :scheme, '
            ':contract, :parity, CURRENT_TIMESTAMP)'), {
                "owner": "legacy-owner", "address": address,
                "identifier": "legacy-graph", "graph": "sha256:" + "1" * 64,
                "artifact": artifact, "scheme": "v1", "contract": "legacy",
                "parity": "legacy",
            })
    return engine, address


def _make_populated_0007(path):
    """Genuine 0007 state, constructed by FORWARD REPLAY through the real migrations.

    Foundation-audit A-04: the previous builder created current-model
    metadata (post-0010 constraint shapes), dropped one table and stamped a
    0007 marker — a hybrid whose failures prove nothing.  History is instead
    replayed: the genuine seeded-0005 fixture, then the production 0006 and
    0007 migrations, then the era marker.  No hand-written historical DDL.
    """
    engine, address = _make_populated_0005(path)
    with engine.begin() as connection:
        migrate._upgrade_ir_v2_admissions(connection)
        migrate._upgrade_dataset_provenance(connection)
        connection.exec_driver_sql(
            "UPDATE research_schema_version SET version = '0007'")
    return engine, address


@pytest.fixture
def disposable_postgresql_engine(pg_sandbox):
    """A private, verified-empty research database per test (shared contract).

    The previous fixture reused the whole harness database and dropped only
    ``ResearchBase`` tables plus the marker — execution-side tables from other
    shards survived into the next test. Isolation now comes from the sandbox
    (unique per-test database), not from cleanup of a shared namespace.
    """
    engine = pg_sandbox.research_engine
    try:
        yield engine
    finally:
        engine.dispose()


def _make_genuine_postgresql_0007(engine):
    """Genuine PostgreSQL 0007 state (shared builder, production chain only)."""
    from tests.research_history_fixtures import make_genuine_postgresql_research_state

    make_genuine_postgresql_research_state(engine, "0007")
    with engine.connect() as connection:
        assert "research_dataset_manifests" in inspect(connection).get_table_names()


def test_empty_sqlite_upgrade_reaches_head_with_exact_v2_columns(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        inspector = inspect(engine)
        columns = {column["name"]: column for column in inspector.get_columns(
            "research_strategy_admission")}
        assert columns["format_version"]["nullable"] is True
        assert columns["content_address"]["nullable"] is True
        graph_columns = {column["name"]: column for column in inspect(engine).get_columns(
            "research_ir_v2_graph_versions")}
        assert list(graph_columns) == [
            "owner_id", "graph_identifier", "graph_version", "artifact_json",
            "format_version", "content_address", "graph_address",
            "registry_snapshot_address", "created_at",
        ]
        assert graph_columns["format_version"]["nullable"] is False
        with engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version FROM research_schema_version")).scalar_one() == migrate.HEAD_VERSION
    finally:
        engine.dispose()


def test_populated_sqlite_0005_refuses_and_preserves_legacy_nulls_and_payload(tmp_path):
    engine, address = _make_populated_0005(tmp_path / "research.db")
    try:
        before = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            init_research_db(engine)
        assert _sqlite_logical_digest(engine) == before
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT artifact_json, admission_address "
                "FROM research_strategy_admission WHERE admission_address=:address"),
                {"address": address}).one()
            assert row.artifact_json == _legacy_artifact()[0]
            assert row.admission_address == address
            assert connection.scalar(text(
                "SELECT version FROM research_schema_version")) == "0005"
    finally:
        engine.dispose()


def test_research_upgrade_is_restart_safe_and_schema_parity_is_exact(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        first = inspect(engine).get_columns("research_strategy_admission")
        init_research_db(engine)
        second = inspect(engine).get_columns("research_strategy_admission")
        assert [(item["name"], item["nullable"], str(item["type"])) for item in first] == [
            (item["name"], item["nullable"], str(item["type"])) for item in second]
        assert migrate.head_version() == migrate.HEAD_VERSION
    finally:
        engine.dispose()


def test_interrupted_0006_hybrid_refuses_on_restart_without_advancing_marker(monkeypatch, tmp_path):
    engine, _address = _make_populated_0005(tmp_path / "research.db")
    migration = importlib.import_module("research.domain.migrations.0006_ir_v2_admissions")
    original = migration.upgrade

    def fail_after_mutation(connection, table):
        original(connection, table)
        raise RuntimeError("injected 0006 failure")

    monkeypatch.setattr(migration, "upgrade", fail_after_mutation)
    try:
        with pytest.raises(RuntimeError, match="injected 0006 failure"):
            with engine.begin() as connection:
                # Inject through the SAME frozen projection the runner passes
                # (migrate._upgrade_ir_v2_admissions), not current metadata:
                # the surviving DDL must be the shape the pre-0006 validator
                # owns, or the restart test proves a hybrid, not recovery.
                migration.upgrade(connection, {
                    table.name: table for table in migrate._pre_0010_tables()
                }["research_strategy_admission"])
        with engine.connect() as connection:
            columns = {item["name"] for item in inspect(connection).get_columns(
                "research_strategy_admission")}
            # SQLite DDL survives the failed transaction. The marker is the
            # recovery authority and must remain pre-upgrade until restart.
            assert {"format_version", "content_address"} <= columns
            assert connection.execute(text(
                "SELECT version FROM research_schema_version")).scalar_one() == "0005"
        interrupted = _sqlite_logical_digest(engine)
        monkeypatch.setattr(migration, "upgrade", original)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            init_research_db(engine)
        assert _sqlite_logical_digest(engine) == interrupted
        with engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version FROM research_schema_version")).scalar_one() == "0005"
            row = connection.execute(text(
                "SELECT format_version, content_address, artifact_json "
                "FROM research_strategy_admission")).one()
            assert row.format_version is None
            assert row.content_address is None
            assert row.artifact_json == _legacy_artifact()[0]
    finally:
        engine.dispose()


def test_research_downgrade_refuses_destructive_removal(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        with pytest.raises(migrate.ResearchMigrationError, match="downgrade is unsupported"):
            migrate.downgrade_research_db(engine)
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="requires the disposable PostgreSQL 16 harness")
def test_disposable_postgresql_empty_upgrade_has_matching_head_and_columns(
    disposable_postgresql_engine,
):
    engine = disposable_postgresql_engine
    init_research_db(engine)
    columns = {item["name"] for item in inspect(engine).get_columns(
        "research_strategy_admission")}
    assert {"format_version", "content_address"} <= columns
    graph_columns = [item["name"] for item in inspect(engine).get_columns(
        "research_ir_v2_graph_versions")]
    assert graph_columns == [
        "owner_id", "graph_identifier", "graph_version", "artifact_json",
        "format_version", "content_address", "graph_address",
        "registry_snapshot_address", "created_at",
    ]
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT version FROM research_schema_version")).scalar_one() == migrate.HEAD_VERSION


def test_0008_empty_sqlite_upgrade_is_idempotent_and_restart_safe(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        first = inspect(engine).get_columns("research_ir_v2_graph_versions")
        init_research_db(engine)
        second = inspect(engine).get_columns("research_ir_v2_graph_versions")
        assert [(item["name"], item["nullable"], str(item["type"])) for item in first] == [
            (item["name"], item["nullable"], str(item["type"])) for item in second]
        # A-04 refresh: this assertion pinned head when 0008 was head; the
        # idempotent-restart intent is preserved at the current head.
        assert migrate.head_version() == migrate.HEAD_VERSION
    finally:
        engine.dispose()


def test_0008_refuses_destructive_downgrade_and_keeps_graph_schema(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with pytest.raises(migrate.ResearchMigrationError, match="downgrade is unsupported"):
            migrate.downgrade_research_db(engine)
        with engine.connect() as connection:
            # A-04 refresh: pinned "0008" when 0008 was head; the refused
            # downgrade must leave the marker at the head it defended.
            assert connection.scalar(text(
                "SELECT version FROM research_schema_version")) == migrate.HEAD_VERSION
        assert "research_ir_v2_graph_versions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_populated_0007_refuses_and_preserves_v1_bytes_without_graph_inference(tmp_path):
    engine, address = _make_populated_0007(tmp_path / "research.db")
    try:
        before = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            init_research_db(engine)
        assert _sqlite_logical_digest(engine) == before
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT format_version, content_address, artifact_json "
                "FROM research_strategy_admission WHERE admission_address=:address"),
                {"address": address},
            ).one()
            assert row.format_version is None
            assert row.content_address is None
            assert row.artifact_json == _legacy_artifact()[0]
            assert "research_ir_v2_graph_versions" not in inspect(connection).get_table_names()
    finally:
        engine.dispose()


def test_interrupted_0008_hybrid_refuses_on_restart_without_advancing_marker(monkeypatch, tmp_path):
    engine, _address = _make_populated_0007(tmp_path / "research.db")
    migration = importlib.import_module("research.domain.migrations.0008_ir_v2_graph_versions")
    original = migration.upgrade

    def fail_after_mutation(connection, table):
        original(connection, table)
        raise RuntimeError("injected 0008 failure")

    monkeypatch.setattr(migration, "upgrade", fail_after_mutation)
    try:
        with pytest.raises(RuntimeError, match="injected 0008 failure"):
            with engine.begin() as connection:
                migration.upgrade(
                    connection,
                    ResearchBase.metadata.tables["research_ir_v2_graph_versions"],
                )
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT version FROM research_schema_version")) == "0007"
            assert "research_ir_v2_graph_versions" in inspect(connection).get_table_names()
        monkeypatch.setattr(migration, "upgrade", original)
        interrupted = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            init_research_db(engine)
        assert _sqlite_logical_digest(engine) == interrupted
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT version FROM research_schema_version")) == "0007"
    finally:
        engine.dispose()


@pytest.mark.parametrize("drift", ("missing", "altered"))
def test_0008_restart_refuses_surviving_graph_trigger_drift(monkeypatch, tmp_path, drift):
    engine, _address = _make_populated_0007(tmp_path / f"research-{drift}.db")
    migration = importlib.import_module("research.domain.migrations.0008_ir_v2_graph_versions")
    original = migration.upgrade

    def fail_after_mutation(connection, table):
        original(connection, table)
        raise RuntimeError("injected 0008 failure")

    monkeypatch.setattr(migration, "upgrade", fail_after_mutation)
    try:
        with pytest.raises(RuntimeError, match="injected 0008 failure"):
            with engine.begin() as connection:
                migration.upgrade(
                    connection,
                    ResearchBase.metadata.tables["research_ir_v2_graph_versions"],
                )
        monkeypatch.setattr(migration, "upgrade", original)
        trigger = "trg_research_ir_v2_graph_versions_no_update"
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP TRIGGER "{trigger}"')
            if drift == "altered":
                connection.exec_driver_sql(
                    'CREATE TRIGGER "trg_research_ir_v2_graph_versions_no_update" '
                    "BEFORE UPDATE ON research_ir_v2_graph_versions BEGIN "
                    "SELECT RAISE(ABORT, 'altered graph trigger'); END"
                )
        before = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            init_research_db(engine)
        assert _sqlite_logical_digest(engine) == before
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT version FROM research_schema_version")) == "0007"
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not os.environ.get("PT_TEST_POSTGRES_URL"),
    reason="requires the disposable PostgreSQL 16 harness",
)
def test_disposable_postgresql_0007_refuses_before_catalog_or_marker_write(
    disposable_postgresql_engine,
):
    engine = disposable_postgresql_engine
    _make_genuine_postgresql_0007(engine)
    before = _postgresql_logical_digest(engine)
    with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        init_research_db(engine)
    with engine.connect() as connection:
        assert _postgresql_logical_digest(engine) == before
        assert connection.execute(text(
            "SELECT version FROM research_schema_version")).scalar_one() \
            == "0007"
