"""PostgreSQL schema-adoption contracts.

The optional ``PT_TEST_POSTGRES_URL`` integration test runs only where a PostgreSQL
service is supplied. The fast tests pin the branch decisions without pretending a
mock engine proves server behaviour.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import uuid
from copy import deepcopy

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import migrate
from app.db.models import Base, UniversePreference


P5_ATTRIBUTION_TABLES = (
    "deployments", "execution_intents", "positions", "trades", "backtest_results",
)
P5_CAPITAL_TABLES = {
    "sizing_policies", "sizing_decisions", "target_position_requests",
    "candidate_intents", "capital_reservation_heads", "decision_batches",
    "portfolio_admission_decisions", "capital_reservations",
    "capital_reservation_events", "position_campaigns", "position_tranches",
    "fill_allocations",
}


def _install_repository_0037_catalog(connection) -> None:
    """Construct the accepted pre-authority catalogue without any 0040 object.

    This is the same repository-owned historical projection used by the accepted
    Phase 4 PostgreSQL 0037-to-0039 migration test. Revisions 0038 and 0039 then
    build their own tables, functions, triggers, and constraints through Alembic.
    """
    from app.db.models import _PHASE4_SECRET_FUNCTION
    from tests.test_phase4_authority_execution_migration import (
        AUTHORITY_TABLES, LEGACY_TABLES,
    )

    historical = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name in AUTHORITY_TABLES or table.name in P5_CAPITAL_TABLES:
            continue
        copied = table.to_metadata(historical)
        if copied.name in LEGACY_TABLES:
            copied._columns.remove(copied.c.authority_state)
        if copied.name in P5_ATTRIBUTION_TABLES:
            for constraint in tuple(copied.constraints):
                if {column.name for column in constraint.columns} & {
                        "graph_address", "attribution_state"}:
                    copied.constraints.remove(constraint)
            copied._columns.remove(copied.c.graph_address)
            copied._columns.remove(copied.c.attribution_state)
    connection.execute(sa.text(_PHASE4_SECRET_FUNCTION.replace("%%", "%")))
    historical.create_all(connection)


def _postgres_p5_snapshot(connection) -> dict[str, object]:
    owner = "owner.p5.legacy"
    rows = {}
    for table in P5_ATTRIBUTION_TABLES:
        order = "client_intent_id" if table == "execution_intents" else "id"
        rows[table] = [tuple(row) for row in connection.execute(sa.text(
            f"SELECT * FROM {table} WHERE owner_id=:owner ORDER BY {order}"),
            {"owner": owner}).all()]
    sequences = {}
    for table in ("deployments", "positions", "trades", "backtest_results"):
        sequence = connection.execute(sa.text(
            "SELECT pg_get_serial_sequence(:table, 'id')"), {"table": table}).scalar_one()
        assert sequence is not None
        sequences[table] = tuple(connection.exec_driver_sql(
            f"SELECT last_value,is_called FROM {sequence}").one())
    tables = tuple(P5_ATTRIBUTION_TABLES)
    return {
        "head": connection.execute(sa.text(
            "SELECT version_num FROM alembic_version")).scalar_one(),
        "rows": rows,
        "sequences": sequences,
        "columns": [tuple(row) for row in connection.execute(sa.text("""
            SELECT table_name,column_name,data_type,character_maximum_length,is_nullable,column_default
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name = ANY(:tables)
            ORDER BY table_name,ordinal_position
        """), {"tables": list(tables)}).all()],
        "constraints": [tuple(row) for row in connection.execute(sa.text("""
            SELECT c.relname, con.conname, con.contype, pg_get_constraintdef(con.oid, true)
            FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname = ANY(:tables)
            ORDER BY c.relname,con.conname
        """), {"tables": list(tables)}).all()],
        "triggers": [tuple(row) for row in connection.execute(sa.text("""
            SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid,true)
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND NOT t.tgisinternal AND c.relname = ANY(:tables)
            ORDER BY c.relname,t.tgname
        """), {"tables": list(tables)}).all()],
        "functions": [tuple(row) for row in connection.execute(sa.text("""
            SELECT p.proname,pg_get_functiondef(p.oid)
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND (p.proname LIKE '%graph_attribution%'
                 OR p.proname LIKE '%legacy_attribution%')
            ORDER BY p.proname
        """)).all()],
    }


class _Dialect:
    name = "postgresql"


class _Engine:
    dialect = _Dialect()


def test_postgresql_unmanaged_populated_database_is_refused(monkeypatch):
    engine = _Engine()
    monkeypatch.setattr(migrate, "schema_version", lambda _engine: None)
    monkeypatch.setattr(migrate, "_has_tables", lambda _engine: True)

    with pytest.raises(RuntimeError, match="populated unmanaged PostgreSQL"):
        migrate.init_schema(engine, create_all=lambda: None,
                            legacy_migrate=lambda: pytest.fail("legacy migration ran"))


def test_postgresql_empty_database_creates_current_schema_then_stamps_head(monkeypatch):
    engine = _Engine()
    calls = []
    versions = iter((None, "head-42"))
    monkeypatch.setattr(migrate, "schema_version", lambda _engine: next(versions))
    monkeypatch.setattr(migrate, "_has_tables", lambda _engine: False)
    monkeypatch.setattr(migrate, "head_revision", lambda: "head-42")
    monkeypatch.setattr(migrate, "stamp", lambda _engine, revision: calls.append(("stamp", revision)))
    monkeypatch.setattr(migrate, "_validate_postgresql_immutable_triggers",
                        lambda _engine: calls.append(("triggers",)))

    result = migrate.init_schema(engine, create_all=lambda: calls.append(("create_all",)),
                                 legacy_migrate=lambda: pytest.fail("legacy migration ran"))

    assert result == "head-42"
    assert calls == [("create_all",), ("triggers",), ("stamp", "head-42")]


def test_postgresql_head_startup_is_read_only(monkeypatch):
    engine = _Engine()
    monkeypatch.setattr(migrate, "schema_version", lambda _engine: "head-42")
    monkeypatch.setattr(migrate, "head_revision", lambda: "head-42")
    monkeypatch.setattr(migrate, "upgrade_to_head",
                        lambda _engine: pytest.fail("upgrade attempted on head"))
    monkeypatch.setattr(migrate, "_validate_postgresql_immutable_triggers", lambda _engine: None)

    assert migrate.init_schema(engine, create_all=lambda: pytest.fail("create_all ran"),
                               legacy_migrate=lambda: pytest.fail("legacy migration ran")) == "head-42"


def test_postgresql_head_startup_validates_immutable_fact_triggers(monkeypatch):
    engine = _Engine()
    calls = []
    monkeypatch.setattr(migrate, "schema_version", lambda _engine: "head-42")
    monkeypatch.setattr(migrate, "head_revision", lambda: "head-42")
    monkeypatch.setattr(migrate, "_validate_current_schema",
                        lambda _engine, _tables: calls.append("schema"))
    monkeypatch.setattr(migrate, "_validate_postgresql_immutable_triggers",
                        lambda _engine: calls.append("triggers"))

    assert migrate.init_schema(engine, create_all=lambda: pytest.fail("create_all ran"),
                               legacy_migrate=lambda: pytest.fail("legacy migration ran"),
                               expected_tables={"execution_order_events": object()}) == "head-42"
    assert calls == ["schema", "triggers"]


def test_postgresql_boolean_defaults_compile_as_boolean_literals():
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not isinstance(column.type, sa.Boolean) or column.server_default is None:
                continue
            default = migrate._compiled_sql(column.server_default.arg, postgresql.dialect())
            assert default in {"true", "false"}, (
                f"{table.name}.{column.name} has PostgreSQL boolean default {default!r}; "
                "use sqlalchemy.true()/false(), never an integer literal"
            )


def test_postgresql_ddl_has_native_json_guards_and_all_partial_index_predicates():
    tables = "\n".join(
        str(CreateTable(table).compile(dialect=postgresql.dialect()))
        for table in Base.metadata.sorted_tables
    )
    indexes = "\n".join(
        str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for table in Base.metadata.sorted_tables
        for index in table.indexes
    )

    forbidden = ("json_valid", "json_extract", "GLOB", "PRAGMA", "sqlite_master", "rowid")
    assert all(token.lower() not in tables.lower() for token in forbidden)
    assert "CAST(artifact_json AS JSONB) IS NOT NULL" in tables
    assert "CAST(filters_json AS JSONB) IS NOT NULL" in tables
    assert "CAST(manifest_json AS JSONB) IS NOT NULL" in tables
    assert "CAST(artifact_json AS JSONB) -> 'identifier' IS NOT NULL" in tables
    assert "CAST(manifest_json AS JSONB) -> 'project_id' IS NOT NULL" in tables
    assert "CAST(artifact_json AS JSONB) ->> 'identifier' = graph_identifier" in tables
    assert "CAST(manifest_json AS JSONB) ->> 'project_id' = project_id" in tables
    assert "jsonb_typeof(CAST(artifact_json AS JSONB) -> 'identifier') = 'string'" in tables
    assert "jsonb_typeof(CAST(manifest_json AS JSONB) -> 'project_id') = 'string'" in tables
    assert "CAST(artifact_json AS JSONB) -> 'version' IS NOT NULL" in tables
    assert "CAST(manifest_json AS JSONB) -> 'schema_version' IS NOT NULL" in tables
    assert "jsonb_typeof(CAST(artifact_json AS JSONB) -> 'version') = 'number'" in tables
    assert "jsonb_typeof(CAST(manifest_json AS JSONB) -> 'schema_version') = 'number'" in tables
    assert "WHERE deleted_at IS NULL" in indexes
    assert "WHERE state IN ('staged','paper_active','paused')" in indexes
    assert "WHERE state IN ('staged','shadow_active','paused')" in indexes


def test_sqlite_json_guards_and_partial_index_predicates_are_unchanged():
    tables = "\n".join(
        str(CreateTable(table).compile(dialect=sqlite.dialect()))
        for table in Base.metadata.sorted_tables
    )
    indexes = "\n".join(
        str(CreateIndex(index).compile(dialect=sqlite.dialect()))
        for table in Base.metadata.sorted_tables
        for index in table.indexes
    )

    assert "json_valid(artifact_json)" in tables
    assert "json_extract(artifact_json, '$.identifier') IS graph_identifier" in tables
    assert "json_valid(filters_json)" in tables
    assert "json_extract(manifest_json, '$.schema_version') IS 1" in tables
    assert "WHERE deleted_at IS NULL" in indexes
    assert "WHERE state IN ('staged','paper_active','paused')" in indexes
    assert "WHERE state IN ('staged','shadow_active','paused')" in indexes


def test_postgresql_create_profile_installs_immutable_fact_triggers():
    statements: list[str] = []

    def record(statement, *_args, **_kwargs):
        statements.append(str(statement.compile(dialect=engine.dialect)))

    engine = sa.create_mock_engine("postgresql+psycopg://app:secret@db/strategy", record)
    Base.metadata.create_all(engine)
    ddl = "\n".join(statements)

    for table in ("execution_order_events", "graph_versions", "project_review_snapshots",
                  "strategy_admissions"):
        assert f"CREATE OR REPLACE FUNCTION {table}_refuse_mutation()" in ddl
        assert f"BEFORE UPDATE OR DELETE ON {table}" in ddl
    assert "strategy admissions are immutable' USING ERRCODE = '55000'" in ddl


def test_postgresql_immutable_trigger_validator_rejects_one_missing_trigger(monkeypatch):
    seen = []

    class Connection:
        def execute(self, _statement, _params):
            class Result:
                @staticmethod
                def scalars():
                    return ["execution_order_events_refuse_mutation",
                            "graph_versions_refuse_mutation"]
            return Result()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Engine:
        def connect(self):
            seen.append("connect")
            return Connection()

    with pytest.raises(RuntimeError, match="project_review_snapshots_refuse_mutation"):
        migrate._validate_postgresql_immutable_triggers(Engine())
    assert seen == ["connect"]


@pytest.mark.parametrize("tamper", ("disabled", "when_false", "wrong_sqlstate"))
def test_strategy_admission_trigger_validator_rejects_same_name_inert_contract(tamper):
    """A trigger name alone must not bless a receipt table that raw SQL can mutate."""
    row = {
        "tgenabled": "O", "tgtype": 27, "has_no_when": True,
        "relation_schema": "public", "function_schema": "public",
        "proname": "strategy_admissions_refuse_mutation",
        "prosrc": "BEGIN RAISE EXCEPTION 'strategy admissions are immutable' "
                  "USING ERRCODE = '55000'; END;",
        "trigger_definition": "CREATE TRIGGER strategy_admissions_refuse_mutation "
                              "BEFORE UPDATE OR DELETE ON strategy_admissions "
                              "FOR EACH ROW EXECUTE FUNCTION "
                              "strategy_admissions_refuse_mutation()",
    }
    if tamper == "disabled":
        row["tgenabled"] = "D"
    elif tamper == "when_false":
        row["has_no_when"] = False
    else:
        row["prosrc"] = "BEGIN RAISE EXCEPTION 'strategy admissions are immutable' " \
                         "USING ERRCODE = 'P0001'; END;"

    class Result:
        def mappings(self):
            return self

        def one_or_none(self):
            return row

    class Connection:
        def execute(self, _statement):
            return Result()

    with pytest.raises(RuntimeError, match="immutable-trigger contract"):
        migrate._validate_strategy_admission_immutable_trigger(Connection())


def test_strategy_admission_trigger_validator_accepts_exact_catalog_contract():
    row = {
        "tgenabled": "O", "tgtype": 27, "has_no_when": True,
        "relation_schema": "app_test", "function_schema": "app_test",
        "proname": "strategy_admissions_refuse_mutation",
        "prosrc": "BEGIN RAISE EXCEPTION 'strategy admissions are immutable' "
                  "USING ERRCODE = '55000'; END;",
        "trigger_definition": "CREATE TRIGGER strategy_admissions_refuse_mutation "
                              "BEFORE UPDATE OR DELETE ON strategy_admissions "
                              "FOR EACH ROW EXECUTE FUNCTION "
                              "strategy_admissions_refuse_mutation()",
    }

    class Result:
        def mappings(self):
            return self

        def one_or_none(self):
            return row

    class Connection:
        def execute(self, _statement):
            return Result()

    migrate._validate_strategy_admission_immutable_trigger(Connection())


def test_current_schema_validation_rejects_missing_execution_index(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'schema-check.db'}")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(sa.text("DROP INDEX ix_execution_intents_owner_account"))

        with pytest.raises(RuntimeError, match="indexes"):
            migrate._validate_current_schema(engine, Base.metadata.tables)
    finally:
        engine.dispose()


@pytest.mark.parametrize("tamper", [
    "type", "column", "default", "unique", "check", "foreign_key_action", "partial_index",
])
def test_current_schema_validation_rejects_load_bearing_metadata_drift(tmp_path, monkeypatch, tamper):
    """A head stamp cannot make a changed relational contract acceptable."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'schema-contract.db'}")
    try:
        Base.metadata.create_all(engine)
        real = sa.inspect(engine)

        class TamperedInspector:
            def __getattr__(self, name):
                return getattr(real, name)

            def get_columns(self, table_name):
                rows = deepcopy(real.get_columns(table_name))
                if tamper == "type" and table_name == "graph_versions":
                    next(row for row in rows if row["name"] == "content_address")["type"] = sa.String(70)
                if tamper == "column" and table_name == "graph_versions":
                    next(row for row in rows if row["name"] == "content_address")["nullable"] = True
                if tamper == "default" and table_name == "graph_versions":
                    next(row for row in rows if row["name"] == "visibility")["default"] = "'PUBLIC'"
                return rows

            def get_unique_constraints(self, table_name):
                rows = deepcopy(real.get_unique_constraints(table_name))
                if tamper == "unique" and table_name == "user_sessions":
                    return []
                return rows

            def get_check_constraints(self, table_name):
                rows = deepcopy(real.get_check_constraints(table_name))
                if tamper == "check" and table_name == "graph_versions":
                    return [row for row in rows
                            if row["name"] != "ck_graph_versions_valid_json"]
                return rows

            def get_foreign_keys(self, table_name):
                rows = deepcopy(real.get_foreign_keys(table_name))
                if tamper == "foreign_key_action" and table_name == "graph_versions":
                    rows[0]["options"] = {"ondelete": "CASCADE"}
                return rows

            def get_indexes(self, table_name):
                rows = deepcopy(real.get_indexes(table_name))
                if tamper == "partial_index" and table_name == "project_review_saved_views":
                    row = next(item for item in rows
                               if item["name"] == "uq_project_review_saved_views_active_name")
                    row["dialect_options"] = {}
                return rows

        monkeypatch.setattr(migrate, "inspect", lambda _engine: TamperedInspector())
        with pytest.raises(RuntimeError):
            migrate._validate_current_schema(engine, Base.metadata.tables)
    finally:
        engine.dispose()


def test_current_schema_validation_accepts_postgresql_catalog_representation(monkeypatch):
    """The structural validator accepts stable PostgreSQL catalog representations."""
    dialect = postgresql.dialect()

    class Inspector:
        def get_table_names(self):
            return list(Base.metadata.tables)

        def get_columns(self, table_name):
            table = Base.metadata.tables[table_name]
            rows = []
            for column in table.columns:
                actual_type = column.type.compile(dialect=dialect)
                actual_type = actual_type.replace("TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP")
                actual_type = actual_type.replace("FLOAT", "DOUBLE PRECISION")
                default = migrate._compiled_sql(
                    column.server_default.arg if column.server_default is not None else None,
                    dialect)
                if default is not None and default.startswith("'"):
                    suffix = "text" if isinstance(column.type, sa.Text) else "character varying"
                    default = f"{default}::{suffix}"
                elif column.primary_key and isinstance(column.type, sa.Integer):
                    default = f"nextval('{table_name}_{column.name}_seq'::regclass)"
                rows.append({
                    "name": column.name,
                    "type": actual_type,
                    "nullable": column.nullable,
                    "default": default,
                })
            return rows

        def get_pk_constraint(self, table_name):
            return {"constrained_columns": [column.name for column in
                                             Base.metadata.tables[table_name].primary_key.columns]}

        def get_foreign_keys(self, table_name):
            return [{
                "constrained_columns": [element.parent.name for element in constraint.elements],
                "referred_table": constraint.elements[0].column.table.name,
                "referred_columns": [element.column.name for element in constraint.elements],
                "options": {"ondelete": constraint.ondelete, "onupdate": constraint.onupdate},
            } for constraint in Base.metadata.tables[table_name].foreign_key_constraints]

        def get_unique_constraints(self, table_name):
            rows = []
            for constraint in Base.metadata.tables[table_name].constraints:
                if not isinstance(constraint, sa.UniqueConstraint):
                    continue
                columns = [column.name for column in constraint.columns]
                name = constraint.name or f"{table_name}_{'_'.join(columns)}_key"
                rows.append({"name": name, "column_names": columns})
            return rows

        def get_check_constraints(self, table_name):
            rows = []
            for constraint in Base.metadata.tables[table_name].constraints:
                if not isinstance(constraint, sa.CheckConstraint) or constraint.name is None:
                    continue
                rows.append({"name": constraint.name, "sqltext": "catalog-deparsed"})
            return rows

        def get_indexes(self, table_name):
            rows = []
            for index in Base.metadata.tables[table_name].indexes:
                where = index.dialect_options["postgresql"].get("where")
                rows.append({
                    "name": index.name,
                    "column_names": [column.name for column in index.columns],
                    "unique": index.unique,
                    "dialect_options": {"postgresql_where": "catalog-deparsed"}
                    if where is not None else {},
                })
            return rows

    monkeypatch.setattr(migrate, "inspect", lambda _engine: Inspector())
    engine = type("Engine", (), {"dialect": dialect})()
    migrate._validate_current_schema(engine, Base.metadata.tables)


def test_mock_mode_cannot_reset_a_postgresql_execution_database(monkeypatch):
    from app.db import session as session_module

    class _MockSettings:
        provider = "mock"

    monkeypatch.setattr(session_module, "engine", _Engine())
    monkeypatch.setattr(session_module, "get_settings", lambda: _MockSettings())

    with pytest.raises(RuntimeError, match="SQLite"):
        session_module.init_db(reset=True)


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_optional_postgres_fresh_schema_is_complete_and_idempotent():
    """Live PostgreSQL proof, intentionally opt-in for developer and CI services."""
    from app.db.models import Base

    base_url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"phase3_execution_{uuid.uuid4().hex}"
    admin = sa.create_engine(base_url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = str(sa.engine.make_url(base_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}))
    engine = sa.create_engine(url, future=True)
    try:
        migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine),
                            legacy_migrate=lambda: pytest.fail("legacy migration ran"),
                            expected_tables=Base.metadata.tables)
        assert migrate.schema_version(engine) == migrate.head_revision()
        assert set(sa.inspect(engine).get_table_names()) >= set(Base.metadata.tables)
        assert migrate.init_schema(engine, create_all=lambda: pytest.fail("second create_all"),
                                   legacy_migrate=lambda: pytest.fail("legacy migration ran"),
                                   expected_tables=Base.metadata.tables) == migrate.head_revision()
        with engine.connect() as conn:
            collapsed_default = conn.execute(sa.text("""
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = 'ir_graph_layout_groups'
                  AND column_name = 'collapsed'
            """), {"schema": schema}).scalar_one()
        assert collapsed_default.lower().startswith("false")

        with engine.begin() as conn:
            with pytest.raises(sa.exc.ProgrammingError, match="boolean"):
                conn.execute(sa.text("""
                    INSERT INTO ir_graph_layout_groups
                        (owner_id, graph_identifier, graph_version, identifier,
                         display_name, x, y, width, height, collapsed)
                    VALUES ('owner', 'graph', 1, 'group', 'Group', 0, 0, 1, 1, 0)
                """))
        with engine.begin() as conn:
            with pytest.raises(sa.exc.IntegrityError,
                               match="ck_ir_paper_deployment_authority"):
                conn.execute(sa.text("""
                    INSERT INTO ir_paper_deployments
                         (project_id, graph_identifier, graph_version,
                         graph_content_address, deployment_id, instrument_key,
                         interval, strategy_key, authority, created_at, updated_at,
                         owner_id, broker_account_id)
                    VALUES ('project', 'graph', 1, 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
                            1, 'instrument', '1m', 'strategy', 'non_authoritative',
                            NOW(), NOW(), 'owner', 'account')
                """))
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_p5_graph_attribution_fresh_exact_0039_interruption_and_restore_postgresql16(
        pg_sandbox, tmp_path):
    """History-built 0039, transactional 0040, and clean restore retain exact facts."""
    from tests.test_phase5_graph_paper_attribution_schema import (
        _seed_0039_attribution_corpus,
    )

    fresh = pg_sandbox.engine("p5_fresh")
    upgraded = pg_sandbox.engine("p5_upgrade")
    restored = pg_sandbox.engine("p5_restore")
    with fresh.connect() as connection:
        assert connection.execute(sa.text("SHOW server_version")).scalar_one().startswith("16.14")
    assert migrate.init_schema(
        fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail("legacy migration ran"),
        expected_tables=Base.metadata.tables) == migrate.head_revision()

    # Build the accepted prior catalogue at 0037, then run the repository's 0038
    # and 0039 migrations. No current-schema object is dropped to synthesize history.
    with upgraded.begin() as connection:
        _install_repository_0037_catalog(connection)
        command.stamp(migrate.alembic_config(connection), "0037")
        command.upgrade(migrate.alembic_config(connection), "0039")
        corpus = _seed_0039_attribution_corpus(connection)
        for table in ("deployments", "positions", "trades", "backtest_results"):
            connection.execute(sa.text(
                "SELECT setval(pg_get_serial_sequence(:table,'id'), "
                f"(SELECT MAX(id) FROM {table}), true)"), {"table": table})
    assert migrate.schema_version(upgraded) == "0039"
    with upgraded.connect() as connection:
        before_0039 = _postgres_p5_snapshot(connection)
        assert before_0039["head"] == "0039"
        assert all(not any(value == "graph_address" for value in column)
                   for column in before_0039["columns"])
        assert all(rows[0][next(index for index, item in enumerate(
            sa.inspect(connection).get_columns(table)) if item["name"] == "strategy_version")]
            == corpus["strategy_version"]
            for table, rows in before_0039["rows"].items())

    interrupted = False
    def interrupt_0040(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal interrupted
        normalized = " ".join(statement.split())
        if (not interrupted
                and normalized.startswith("CREATE TRIGGER positions_validate_graph_attribution")):
            interrupted = True
            raise RuntimeError("injected 0040 migration interruption")

    sa.event.listen(upgraded, "after_cursor_execute", interrupt_0040)
    try:
        with pytest.raises(RuntimeError, match="0040 migration interruption"):
            with upgraded.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0040")
    finally:
        sa.event.remove(upgraded, "after_cursor_execute", interrupt_0040)
    assert interrupted and migrate.schema_version(upgraded) == "0039"
    with upgraded.connect() as connection:
        assert _postgres_p5_snapshot(connection) == before_0039

    # A fresh connection represents process restart after the interrupted command.
    upgraded.dispose()
    upgraded = sa.create_engine(pg_sandbox.url("p5_upgrade"), future=True)
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0040")
    assert migrate.schema_version(upgraded) == "0040"
    with upgraded.connect() as connection:
        source_0040 = _postgres_p5_snapshot(connection)
        assert source_0040["head"] == "0040"
        for table, rows in source_0040["rows"].items():
            assert len(rows) == 1, table
        assert len(source_0040["triggers"]) == 9
        assert len(source_0040["functions"]) == 9

    tool_directories = (
        Path("/opt/homebrew/opt/postgresql@16/bin"),
        Path("/usr/local/opt/postgresql@16/bin"),
        Path("/opt/local/lib/postgresql16/bin"),
    )
    pg_dump = shutil.which("pg_dump") or next(
        (str(path / "pg_dump") for path in tool_directories
         if (path / "pg_dump").is_file()), None)
    pg_restore = shutil.which("pg_restore") or next(
        (str(path / "pg_restore") for path in tool_directories
         if (path / "pg_restore").is_file()), None)
    assert pg_dump and pg_restore
    assert "16.14" in subprocess.run(
        [pg_dump, "--version"], check=True, capture_output=True, text=True).stdout
    assert "16.14" in subprocess.run(
        [pg_restore, "--version"], check=True, capture_output=True, text=True).stdout
    backup = tmp_path / "p5-0040.dump"
    dump_url = str(sa.engine.make_url(pg_sandbox.url("p5_upgrade")).set(
        drivername="postgresql"))
    restore_url = str(sa.engine.make_url(pg_sandbox.url("p5_restore")).set(
        drivername="postgresql"))
    subprocess.run([
        pg_dump, "--format=custom", "--no-owner", "--no-acl",
        f"--file={backup}", dump_url,
    ], check=True, capture_output=True, text=True)
    assert backup.stat().st_size > 0
    subprocess.run([
        pg_restore, "--no-owner", "--no-acl", "--exit-on-error",
        f"--dbname={restore_url}", str(backup),
    ], check=True, capture_output=True, text=True)
    with restored.connect() as connection:
        restored_0040 = _postgres_p5_snapshot(connection)
    assert restored_0040 == source_0040

    with restored.begin() as connection:
        with pytest.raises(sa.exc.DBAPIError, match="GRAPH_ATTRIBUTION_UNVERIFIED"):
            connection.execute(sa.text(
                "INSERT INTO deployments "
                "(id,owner_id,name,strategy_key,strategy_version,broker_account_id,"
                "universe_mode,params_json,status,armed,notes,created_at,updated_at) VALUES "
                "(9999,:owner,'stale','ir.graph','1',:account,'explicit','{}',"
                "'draft',false,'',NOW(),NOW())"),
                {"owner": corpus["owner_id"], "account": corpus["account_id"]})
