"""Direct finite evidence for the research 0011 migration.

The two corpora below are fixed caller data.  Frozen dialect declarations build
the 0010 catalogs; the test never derives an old schema from current models.
"""
from __future__ import annotations

import hashlib
import importlib
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from research.domain.migrate import (
    HEAD_VERSION,
    ResearchMigrationError,
    head_version,
    migrate_research_db,
)
from research.domain.migrations import postgresql_0010_contract as pg_contract
from research.domain.migrations import sqlite_catalog_contract as sqlite_contract
from tests.foundation_postgresql_0010_builder import (
    construct as construct_postgresql_0010,
    seed as seed_postgresql,
    set_sequence_state,
)
from tests.foundation_sqlite_catalog_builder import (
    construct as construct_sqlite_0010,
    seed as seed_sqlite,
)


direct = importlib.import_module(
    "research.domain.migrations.0011_foundation_guard_contract"
)


def _corpus(owner: str, identifier: int, binary: bytes) -> dict[str, list[tuple]]:
    stamp = "2026-01-01 00:00:00" if identifier == 7 else "2026-02-02 03:04:05"
    address = lambda character: "sha256:" + character * 64
    segment, object_address, digest, manifest = (address(c) for c in "abcd")
    graph, content, registry, admission = (address(c) for c in "ef01")
    manifest_json = (
        f'{{ "owner_id" : "{owner}", "provider" : "fixture", '
        f'"dataset_version" : "v{identifier}", "market_truth_digest" : "{digest}", '
        f'"capability_digest" : "{object_address}", "schema_version" : 1 }}'
    )
    artifact = f'{{ "strategy_id" : "graph-{identifier}", "strategy_version" : 1 }}'
    admission_json = (
        f'{{"owner_id":"{owner}","graph_identifier":"graph-{identifier}",'
        f'"graph_version":1,"graph_address":"{graph}","scheme":"scheme",'
        '"contract_suite":"contract","parity_suite":"parity"}'
    )
    return {
        "research_program": [(identifier, owner, "Café 東京 🧪", "नमस्ते", "active", stamp)],
        "research_hypothesis": [(identifier, owner, identifier, "hypothesis", "open", 1.0, None, stamp)],
        "research_experiment_spec": [(owner, f"spec-{identifier}", identifier, None, "{ \"raw\" : true }", "a" * 40, "q1", "o1", "v1", "s1", identifier, stamp)],
        "research_experiment_run": [(identifier, owner, f"spec-{identifier}", "completed", "accept", 1.5, "{ \"metric\" : 1 }", "", stamp, stamp, stamp, admission)],
        "research_finding": [(identifier, owner, identifier, "finding", "support", 0.9, identifier, None, stamp)],
        "research_promotion_candidate": [(identifier, owner, identifier, "p" * 64, "[ 1, 2 ]", "{ \"x\" : 1 }", "candidate", "a" * 40, stamp, admission)],
        "research_shadow_session": [(identifier, owner, identifier, "2026-01-01", "SPY", 2, 1, 3.25, stamp)],
        "research_optimization_trial": [(identifier, owner, identifier, "SPY", 0, "{ \"p\" : 1 }", 1.2, 4, 2, True, stamp)],
        "research_block_edge": [(owner, "risk", "SPY", 2, 1, identifier, stamp)],
        "research_generated_strategy": [(owner, f"strategy-{identifier}", artifact, "fixture", stamp)],
        "research_ir_v2_graph_versions": [(owner, f"graph-{identifier}", 1, artifact, 2, content, graph, registry, stamp)],
        "research_strategy_admission": [(owner, admission, f"graph-{identifier}", 1, graph, admission_json, "scheme", "contract", "parity", stamp, 2, content)],
        "research_dataset_segments_v2": [(owner, segment, binary, b"\x80bytes" if identifier == 7 else b"\x81data", object_address, digest, len(binary), "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "VERIFIED_V2")],
        "research_dataset_manifests_v2": [(owner, manifest, binary, digest, len(binary), f'[ "{segment}" ]', "[ ]", "[ ]", "[ ]", "[ ]", "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "VERIFIED_V2")],
        "research_dataset_manifest_segments_v2": [(owner, manifest, 0, segment)],
        "research_dataset_manifests": [(owner, address("9"), "fixture", f"v{identifier}", digest, object_address, manifest_json, stamp)],
        "research_operation": [(owner, f"op-{identifier}", "manual", "{ \"plan\" : true }", "completed", "completed", None, "a" * 40, "fixture", f"[ {identifier} ]", stamp, stamp, stamp, stamp, stamp, None, None, None, 1, None)],
        "research_operation_event": [(owner, f"op-{identifier}", 1, "completed", "completed", "{ \"event\" : true }", stamp)],
        "research_operation_item": [(owner, f"op-{identifier}", "item", 0, "completed", identifier, stamp)],
        "research_outbox_event": [(identifier, f"00000000-0000-0000-0000-{identifier:012d}", "private", owner, owner, None, "program", str(identifier), 1, "created", 1, "{ \"payload\" : true }", content, f"producer-{identifier}", stamp, "projection")],
        "research_outbox_stream_head": [("program", str(identifier), 1, stamp)],
        "research_outbox_consumer_cursor": [(f"consumer-{identifier}", identifier, None, None, None, None, "", stamp)],
        "research_outbox_consumer_receipt": [(f"consumer-{identifier}", f"00000000-0000-0000-0000-{identifier:012d}", f"effect-{identifier}", stamp)],
        "research_outbox_retention_watermark": [(owner, identifier, stamp)],
    }


CORPORA = (
    _corpus("owner-α", 7, b"\x00alpha\xff"),
    _corpus("owner-β", 101, b"\x00beta\xfe"),
)


def _sqlite_engine(tmp_path: Path, name: str = "research.sqlite"):
    return create_engine(f"sqlite+pysqlite:///{tmp_path / name}")


def _sqlite_data_state(connection) -> tuple:
    state = []
    for table in sorted(sqlite_contract.INVENTORY["tables"]):
        if table in {"research_schema_version", "sqlite_sequence"}:
            continue
        columns = [item[1] for item in sqlite_contract.INVENTORY["tables"][table]["table_xinfo"] if item[6] == 0]
        rows = connection.exec_driver_sql(
            f'SELECT {",".join(chr(34) + column + chr(34) for column in columns)} FROM "{table}" ORDER BY rowid'
        ).all()
        state.append((table, tuple(tuple(row) for row in rows)))
    sequences = connection.exec_driver_sql(
        "SELECT name,seq FROM sqlite_sequence ORDER BY name"
    ).all()
    return tuple(state), tuple(tuple(row) for row in sequences)


def _sqlite_file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sqlite_complete_state(connection) -> tuple:
    return (
        tuple(connection.exec_driver_sql(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
        ).all()),
        _sqlite_data_state(connection),
        tuple(connection.exec_driver_sql(
            "SELECT version,schema_cookie FROM research_schema_version"
        ).one()),
    )


def _seed_sqlite_0010(engine, corpus, *, missing_guards=()):
    raw = engine.raw_connection()
    try:
        construct_sqlite_0010(raw, marker="0010", missing_guards=missing_guards)
        seed_sqlite(raw, corpus)
        raw.commit()
    finally:
        raw.close()


def test_research_head_is_discovered_as_0011():
    assert HEAD_VERSION == head_version() == "0012"


def test_corrupted_frozen_catalog_attestation_refuses_before_clean_install(tmp_path, monkeypatch):
    engine = _sqlite_engine(tmp_path)
    monkeypatch.setattr(direct, "_SQLITE_ATTESTATION", "0" * 64)
    with pytest.raises(ResearchMigrationError, match="frozen SQLite catalog authority is corrupted"):
        migrate_research_db(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
        ).all() == []


def test_clean_sqlite_reaches_exact_0011_and_is_deterministic(tmp_path):
    engine = _sqlite_engine(tmp_path)
    migrate_research_db(engine)
    with engine.connect() as connection:
        first = _sqlite_data_state(connection)
        marker = connection.exec_driver_sql(
            "SELECT version,schema_cookie FROM research_schema_version"
        ).one()
        assert marker == (HEAD_VERSION, connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
    migrate_research_db(engine)
    with engine.connect() as connection:
        assert _sqlite_data_state(connection) == first
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION


@pytest.mark.parametrize(
    ("corpus", "missing_guards"),
    ((CORPORA[0], sqlite_contract.REPAIRABLE_GUARDS[:2]),
     (CORPORA[1], sqlite_contract.REPAIRABLE_GUARDS[2:])),
    ids=("unicode-binary", "spaced-json-large-ids"),
)
def test_exact_populated_sqlite_0010_preserves_all_rows_sequences_and_bytes(
    tmp_path, corpus, missing_guards,
):
    engine = _sqlite_engine(tmp_path)
    _seed_sqlite_0010(engine, corpus, missing_guards=missing_guards)
    with engine.connect() as connection:
        before = _sqlite_data_state(connection)
    migrate_research_db(engine)
    with engine.connect() as connection:
        assert _sqlite_data_state(connection) == before
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION
        program = connection.exec_driver_sql("SELECT owner_id,name,thesis FROM research_program").one()
        assert tuple(program) == tuple(corpus["research_program"][0][1:4])
        assert connection.exec_driver_sql("SELECT canonical_bytes FROM research_dataset_segments_v2").scalar_one() == corpus["research_dataset_segments_v2"][0][2]
        assert connection.exec_driver_sql("SELECT manifest_json FROM research_dataset_manifests").scalar_one() == corpus["research_dataset_manifests"][0][6]


@pytest.mark.parametrize("table", (
    "research_experiment_spec", "research_optimization_trial",
    "research_strategy_admission", "research_dataset_manifests",
    "research_ir_v2_graph_versions", "research_dataset_segments_v2",
    "research_dataset_manifests_v2", "research_dataset_manifest_segments_v2",
))
@pytest.mark.parametrize("operation", ("UPDATE", "DELETE"))
def test_every_sqlite_immutable_guard_rejects_real_sql(tmp_path, table, operation):
    engine = _sqlite_engine(tmp_path, f"{table}-{operation}.sqlite")
    _seed_sqlite_0010(engine, CORPORA[0], missing_guards=sqlite_contract.REPAIRABLE_GUARDS)
    migrate_research_db(engine)
    with engine.begin() as connection:
        if operation == "UPDATE":
            statement = f'UPDATE "{table}" SET rowid=rowid'
        else:
            statement = f'DELETE FROM "{table}"'
        with pytest.raises(Exception, match="immutable"):
            connection.exec_driver_sql(statement)


def test_sqlite_secret_insert_guard_rejects_real_insert(tmp_path):
    engine = _sqlite_engine(tmp_path)
    _seed_sqlite_0010(engine, CORPORA[0], missing_guards=sqlite_contract.REPAIRABLE_GUARDS)
    migrate_research_db(engine)
    row = list(CORPORA[0]["research_dataset_manifests"][0])
    row[1] = "sha256:" + "8" * 64
    row[6] = row[6][:-2] + ', "api_key" : "forbidden" }'
    with engine.begin() as connection, pytest.raises(Exception, match="credential-bearing"):
        connection.exec_driver_sql(
            "INSERT INTO research_dataset_manifests VALUES (?,?,?,?,?,?,?,?)", tuple(row)
        )


@pytest.mark.parametrize("case", (
    "unversioned", "0001", "0002", "0003", "0004", "0005", "0006",
    "0007", "0008", "0009", "unknown", "future", "downgraded",
    "corrupt-marker", "drift", "hybrid", "stale-cookie",
))
def test_every_unsupported_sqlite_state_refuses_before_write_with_identical_digest(tmp_path, case):
    path = tmp_path / f"{case}.sqlite"
    engine = _sqlite_engine(tmp_path, path.name)
    if case == "unversioned":
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE legacy_data(value BLOB)")
            connection.exec_driver_sql("INSERT INTO legacy_data VALUES (?)", (b"preserve",))
    else:
        _seed_sqlite_0010(engine, CORPORA[0])
        with engine.begin() as connection:
            if case in {f"{value:04d}" for value in range(1, 10)} | {"unknown", "future", "downgraded"}:
                value = case if case[0].isdigit() else {"unknown": "banana", "future": "9999", "downgraded": "-001"}[case]
                connection.exec_driver_sql("UPDATE research_schema_version SET version=?", (value,))
            elif case == "corrupt-marker":
                connection.exec_driver_sql("INSERT INTO research_schema_version VALUES (?,?)", ("0010-copy", 1))
            elif case == "drift":
                connection.exec_driver_sql("CREATE TABLE unexpected(value TEXT)")
                connection.exec_driver_sql("UPDATE research_schema_version SET schema_cookie=(SELECT schema_version FROM pragma_schema_version)")
            elif case == "hybrid":
                connection.exec_driver_sql("DROP TRIGGER trg_research_experiment_spec_no_update")
                connection.exec_driver_sql("UPDATE research_schema_version SET schema_cookie=(SELECT schema_version FROM pragma_schema_version)")
            elif case == "stale-cookie":
                connection.exec_driver_sql("UPDATE research_schema_version SET schema_cookie=schema_cookie-1")
    before = _sqlite_file_digest(path)
    with pytest.raises(ResearchMigrationError, match="Back up.*diagnostic/export.*rebuild"):
        migrate_research_db(engine)
    engine.dispose()
    assert _sqlite_file_digest(path) == before


def test_sqlite_interruption_is_atomic_and_restart_is_deterministic(tmp_path, monkeypatch):
    engine = _sqlite_engine(tmp_path)
    _seed_sqlite_0010(engine, CORPORA[0], missing_guards=sqlite_contract.REPAIRABLE_GUARDS)
    with engine.connect() as connection:
        before = _sqlite_complete_state(connection)
    monkeypatch.setattr(direct, "_before_marker_advance", lambda _connection: (_ for _ in ()).throw(KeyboardInterrupt("cut")))
    with pytest.raises(KeyboardInterrupt, match="cut"):
        migrate_research_db(engine)
    engine.dispose()
    with engine.connect() as connection:
        assert _sqlite_complete_state(connection) == before
    monkeypatch.setattr(direct, "_before_marker_advance", lambda _connection: None)
    migrate_research_db(engine)
    assert engine.connect().exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION


@pytest.fixture
def postgresql_engine():
    url = os.environ.get("PT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("requires disposable PostgreSQL 16")
    admin = create_engine(url)
    schema = f"direct_0011_{uuid4().hex}"
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def _postgresql_state(connection) -> tuple:
    rows = []
    for table in sorted(item["name"] for item in pg_contract.CATALOG_0010["tables"]):
        rows.append((table, tuple(tuple(row) for row in connection.exec_driver_sql(f'SELECT * FROM "{table}" ORDER BY 1').all())))
    sequences = []
    for name in connection.exec_driver_sql("SELECT relname FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='S' ORDER BY relname").scalars():
        sequences.append((name, *connection.exec_driver_sql(f'SELECT last_value,is_called FROM "{name}"').one()))
    return tuple(rows), tuple(sequences)


def _postgresql_complete_digest(connection) -> str:
    """Independent native digest; it does not call the product catalog observer."""
    tables = tuple(connection.exec_driver_sql(
        "SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY 1"
    ).scalars())
    rows = tuple((table, tuple(sorted((tuple(row) for row in connection.exec_driver_sql(
        f'SELECT * FROM "{table}"'
    ).all()), key=repr))) for table in tables)
    views = tuple(connection.exec_driver_sql(
        "SELECT viewname,definition FROM pg_views WHERE schemaname=current_schema() ORDER BY 1"
    ).all())
    materialized_views = tuple(connection.exec_driver_sql(
        "SELECT matviewname,definition FROM pg_matviews WHERE schemaname=current_schema() ORDER BY 1"
    ).all())
    columns = tuple(connection.exec_driver_sql(
        "SELECT c.relkind,c.relname,a.attname,format_type(a.atttypid,a.atttypmod),"
        "a.attnotnull,pg_get_expr(ad.adbin,ad.adrelid) FROM pg_attribute a "
        "JOIN pg_class c ON c.oid=a.attrelid LEFT JOIN pg_attrdef ad "
        "ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum "
        "WHERE c.relnamespace=current_schema()::regnamespace "
        "AND c.relkind IN ('r','v','m') AND a.attnum>0 AND NOT a.attisdropped "
        "ORDER BY 1,2,a.attnum"
    ).all())
    constraints = tuple(connection.exec_driver_sql(
        "SELECT c.relname,con.contype,con.conname,pg_get_constraintdef(con.oid) "
        "FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid "
        "WHERE con.connamespace=current_schema()::regnamespace ORDER BY 1,2,3"
    ).all())
    explicit_indexes = tuple(connection.exec_driver_sql(
        "SELECT c.relname,i.relname,pg_get_indexdef(i.oid) FROM pg_index x "
        "JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid "
        "LEFT JOIN pg_constraint owned ON owned.conindid=x.indexrelid "
        "AND owned.connamespace=current_schema()::regnamespace "
        "WHERE c.relnamespace=current_schema()::regnamespace AND owned.oid IS NULL "
        "ORDER BY 1,2"
    ).all())
    bindings = tuple(connection.exec_driver_sql(
        "SELECT c.relname,a.attname,pg_get_serial_sequence(c.oid::regclass::text,a.attname) "
        "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "LEFT JOIN pg_attrdef ad ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum "
        "WHERE c.relnamespace=current_schema()::regnamespace AND c.relkind='r' "
        "AND a.attnum>0 AND NOT a.attisdropped "
        "AND pg_get_expr(ad.adbin,ad.adrelid) LIKE 'nextval%%' ORDER BY 1,2"
    ).all())
    sequences = []
    for name in connection.exec_driver_sql(
        "SELECT relname FROM pg_class WHERE relnamespace=current_schema()::regnamespace "
        "AND relkind='S' ORDER BY 1"
    ).scalars():
        sequences.append((name, *connection.exec_driver_sql(
            f'SELECT last_value,is_called FROM "{name}"'
        ).one()))
    functions = tuple(connection.exec_driver_sql(
        "SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p "
        "WHERE p.pronamespace=current_schema()::regnamespace ORDER BY 1"
    ).all())
    triggers = tuple(connection.exec_driver_sql(
        "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
        "JOIN pg_class c ON c.oid=t.tgrelid "
        "WHERE c.relnamespace=current_schema()::regnamespace AND NOT t.tgisinternal "
        "ORDER BY 1,2"
    ).all())
    payload = repr((tables, rows, views, materialized_views, columns, constraints,
                    explicit_indexes, bindings, tuple(sequences), functions, triggers)).encode()
    return hashlib.sha256(payload).hexdigest()


def _seed_postgresql_0010(engine, corpus, ordinal):
    with engine.begin() as connection:
        construct_postgresql_0010(connection)
        seed_postgresql(connection, corpus)
        for offset, name in enumerate(direct._expected_postgresql_catalog()["sequences"]):
            set_sequence_state(connection, name, 70 + ordinal + offset, False)


def test_clean_postgresql16_reaches_exact_0011_and_is_deterministic(postgresql_engine):
    migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION
    migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION


@pytest.mark.parametrize(("corpus", "ordinal"), ((CORPORA[0], 1), (CORPORA[1], 2)))
def test_exact_populated_postgresql16_0010_preserves_all_rows_sequences_and_bytes(postgresql_engine, corpus, ordinal):
    _seed_postgresql_0010(postgresql_engine, corpus, ordinal)
    with postgresql_engine.connect() as connection:
        before = _postgresql_state(connection)
    migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert _postgresql_state(connection) == before
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION
        assert connection.exec_driver_sql("SELECT manifest_json FROM research_dataset_manifests").scalar_one() == corpus["research_dataset_manifests"][0][6]


@pytest.mark.parametrize("table", (
    "research_experiment_spec", "research_optimization_trial",
    "research_strategy_admission", "research_dataset_manifests",
    "research_ir_v2_graph_versions", "research_dataset_segments_v2",
    "research_dataset_manifests_v2", "research_dataset_manifest_segments_v2",
))
@pytest.mark.parametrize("operation", ("UPDATE", "DELETE"))
def test_every_postgresql_immutable_guard_rejects_real_sql(postgresql_engine, table, operation):
    _seed_postgresql_0010(postgresql_engine, CORPORA[0], 1)
    migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        transaction = connection.begin()
        savepoint = connection.begin_nested()
        with pytest.raises(Exception, match="immutable"):
            connection.exec_driver_sql(f'{operation} FROM "{table}"' if operation == "DELETE" else f'UPDATE "{table}" SET owner_id=owner_id')
        savepoint.rollback()
        transaction.rollback()


def test_postgresql_secret_insert_guard_rejects_real_insert(postgresql_engine):
    _seed_postgresql_0010(postgresql_engine, CORPORA[0], 1)
    migrate_research_db(postgresql_engine)
    row = list(CORPORA[0]["research_dataset_manifests"][0])
    row[1] = "sha256:" + "8" * 64
    row[6] = row[6][:-2] + ', "token" : "forbidden" }'
    with postgresql_engine.connect() as connection:
        with pytest.raises(Exception):
            connection.exec_driver_sql(
                "INSERT INTO research_dataset_manifests VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", tuple(row)
            )


def test_postgresql_interruption_rolls_back_and_restart_reaches_0011(postgresql_engine, monkeypatch):
    _seed_postgresql_0010(postgresql_engine, CORPORA[0], 1)
    with postgresql_engine.connect() as connection:
        before = _postgresql_state(connection)
    monkeypatch.setattr(direct, "_before_marker_advance", lambda _connection: (_ for _ in ()).throw(KeyboardInterrupt("cut")))
    with pytest.raises(KeyboardInterrupt, match="cut"):
        migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == "0010"
        assert _postgresql_state(connection) == before
    monkeypatch.setattr(direct, "_before_marker_advance", lambda _connection: None)
    migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == HEAD_VERSION


@pytest.mark.parametrize("case", (
    "unversioned", "0001", "0002", "0003", "0004", "0005", "0006",
    "0007", "0008", "0009", "unknown", "future", "downgraded",
    "corrupt-marker", "drift", "hybrid", "extra-table", "extra-view",
    "extra-materialized-view", "extra-index", "extra-function", "extra-sequence",
    "extra-trigger", "extra-constraint",
))
def test_every_unsupported_postgresql_state_refuses_before_write_with_identical_digest(
    postgresql_engine, case,
):
    if case == "unversioned":
        with postgresql_engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE legacy_data(value bytea)")
            connection.exec_driver_sql("INSERT INTO legacy_data VALUES (%s)", (b"preserve",))
    else:
        _seed_postgresql_0010(postgresql_engine, CORPORA[0], 1)
        with postgresql_engine.begin() as connection:
            if case in {f"{value:04d}" for value in range(1, 10)} | {"unknown", "future", "downgraded"}:
                value = case if case[0].isdigit() else {"unknown": "banana", "future": "9999", "downgraded": "-001"}[case]
                connection.exec_driver_sql("UPDATE research_schema_version SET version=%s", (value,))
            elif case == "corrupt-marker":
                connection.exec_driver_sql("ALTER TABLE research_schema_version ADD COLUMN schema_cookie integer")
            elif case == "drift":
                connection.exec_driver_sql("CREATE TABLE research_unexpected(value text)")
            elif case == "hybrid":
                connection.exec_driver_sql("DROP TRIGGER research_experiment_spec_refuse_mutation ON research_experiment_spec")
            elif case == "extra-table":
                connection.exec_driver_sql("CREATE TABLE unrelated(value text)")
            elif case == "extra-view":
                connection.exec_driver_sql(
                    "CREATE VIEW unrelated_view AS SELECT owner_id FROM research_program"
                )
            elif case == "extra-materialized-view":
                connection.exec_driver_sql(
                    "CREATE MATERIALIZED VIEW unrelated_materialized AS "
                    "SELECT owner_id FROM research_program"
                )
            elif case == "extra-index":
                connection.exec_driver_sql(
                    "CREATE INDEX unrelated_index ON research_program(owner_id)"
                )
            elif case == "extra-function":
                connection.exec_driver_sql(
                    "CREATE FUNCTION unrelated_function() RETURNS integer "
                    "LANGUAGE sql IMMUTABLE AS $$ SELECT 1 $$"
                )
            elif case == "extra-sequence":
                connection.exec_driver_sql("CREATE SEQUENCE unrelated_sequence")
            elif case == "extra-trigger":
                connection.exec_driver_sql(
                    "CREATE TRIGGER unrelated_trigger BEFORE UPDATE ON "
                    "research_experiment_spec FOR EACH ROW EXECUTE FUNCTION "
                    "research_experiment_spec_refuse_mutation()"
                )
            elif case == "extra-constraint":
                connection.exec_driver_sql(
                    "ALTER TABLE research_program ADD CONSTRAINT unrelated_constraint "
                    "CHECK (id > 0)"
                )
    with postgresql_engine.connect() as connection:
        before = _postgresql_complete_digest(connection)
    with pytest.raises(ResearchMigrationError, match="Back up.*diagnostic/export.*rebuild"):
        migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert _postgresql_complete_digest(connection) == before


def test_postgresql_version_only_marker_and_sqlite_cookie_contract(tmp_path, postgresql_engine):
    sqlite_engine = _sqlite_engine(tmp_path)
    migrate_research_db(sqlite_engine)
    with sqlite_engine.connect() as connection:
        assert [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(research_schema_version)")] == ["version", "schema_cookie"]
    migrate_research_db(postgresql_engine)
    with postgresql_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='research_schema_version' ORDER BY ordinal_position").scalars().all() == ["version"]


def test_preparation_0012_adds_nullable_receipt_to_exact_0011_and_restarts(tmp_path):
    from sqlalchemy import inspect
    target = importlib.import_module("research.domain.migrations.0012_v2_preparation_evidence")
    engine = create_engine(f"sqlite:///{tmp_path / 'preparation.db'}")
    with engine.begin() as connection:
        direct.upgrade_sqlite(connection)
        connection.exec_driver_sql("INSERT INTO research_operation(owner_id,operation_id,trigger,plan_json,status,stage,build,provider_mode,completed_run_ids_json,created_at,queued_at,attempt_count) VALUES ('owner-a','old','manual','{}','pending','startup','old','mock','[]','2026-01-01','2026-01-01',0)")
    migrate_research_db(engine)
    migrate_research_db(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT preparation_evidence_json FROM research_operation WHERE operation_id='old'").scalar_one() is None
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == target.TARGET_VERSION
        column = next(row for row in inspect(connection).get_columns("research_operation") if row["name"] == target.COLUMN)
        assert column["nullable"] is True
    engine.dispose()


def test_preparation_0012_empty_and_interrupted_upgrade(tmp_path, monkeypatch):
    target = importlib.import_module("research.domain.migrations.0012_v2_preparation_evidence")
    engine = create_engine(f"sqlite:///{tmp_path / 'preparation-empty.db'}")
    def interrupt(_connection):
        raise RuntimeError("interrupted before preparation marker")
    monkeypatch.setattr(target, "_before_marker_advance", interrupt)
    with pytest.raises(RuntimeError, match="interrupted"):
        migrate_research_db(engine)
    monkeypatch.setattr(target, "_before_marker_advance", lambda _connection: None)
    migrate_research_db(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == "0012"
        assert connection.exec_driver_sql("SELECT count(*) FROM research_operation").scalar_one() == 0
    engine.dispose()
