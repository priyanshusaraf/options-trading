"""Execution-plane migration evidence for IR v2 receipts and graph facts."""
from __future__ import annotations

import json
import os
import importlib
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.db import migrate
from app.db.models import Base


_BACKEND = Path(__file__).parents[1]
_BASELINE = _BACKEND / "migrations" / "baseline_schema.ddl"
_ADDRESS = "sha256:" + "a" * 64
_GRAPH_ADDRESS = "sha256:" + "b" * 64


def _engine(tmp_path, name: str):
    return sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)


def _apply_baseline(engine) -> None:
    ddl = "\n".join(
        line for line in _BASELINE.read_text().splitlines()
        if not line.strip().startswith("--")
    )
    with engine.begin() as connection:
        for statement in (item.strip() for item in ddl.split(";") if item.strip()):
            connection.execute(sa.text(statement))


def _at_0034(tmp_path, name="at-0034.db"):
    engine = _engine(tmp_path, name)
    _apply_baseline(engine)
    with engine.begin() as connection:
        # Reproduce the pre-0035 0034 receipt table.  Revision 0034's historical
        # table is intentionally explicit here: the current ORM must not be used
        # to manufacture a pre-0035 database, or the additive upgrade could hide
        # a duplicate-column defect.
        connection.execute(sa.text(
            "CREATE TABLE strategy_admissions ("
            "owner_id VARCHAR(64) NOT NULL, "
            "admission_address VARCHAR(71) NOT NULL, "
            "graph_identifier VARCHAR(128) NOT NULL, "
            "graph_version INTEGER NOT NULL, "
            "graph_address VARCHAR(71) NOT NULL, "
            "artifact_json TEXT NOT NULL, "
            "scheme VARCHAR(32) NOT NULL, "
            "contract_suite VARCHAR(32) NOT NULL, "
            "parity_suite VARCHAR(32) NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "PRIMARY KEY (owner_id, admission_address))"
        ))
        connection.execute(sa.text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        ))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES ('0034')"))
    return engine


def _at_0036(tmp_path, name="at-0036.db"):
    engine = _at_0034(tmp_path, name)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0036")
    return engine


def _legacy_receipt():
    return {
        "owner_id": "legacy-owner",
        "graph_identifier": "legacy.graph",
        "graph_version": 1,
        "graph_address": _GRAPH_ADDRESS,
        "scheme": "phase3-causal",
        "contract_suite": "v1",
        "parity_suite": "v1",
    }


def _insert_legacy_receipt(engine) -> str:
    document = _legacy_receipt()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO strategy_admissions "
                "(owner_id, admission_address, graph_identifier, graph_version, "
                "graph_address, artifact_json, scheme, contract_suite, parity_suite, created_at) "
                "VALUES (:owner_id, :admission_address, :graph_identifier, "
                ":graph_version, :graph_address, :artifact_json, :scheme, "
                ":contract_suite, :parity_suite, CURRENT_TIMESTAMP)"
            ),
            {**document, "admission_address": _ADDRESS, "artifact_json": json.dumps(document)},
        )
    return json.dumps(document)


def _columns(engine):
    return {
        column["name"]: (str(column["type"]), bool(column["nullable"]))
        for column in sa.inspect(engine).get_columns("strategy_admissions")
    }


def _graph_columns(engine):
    return {
        column["name"]: (str(column["type"]), bool(column["nullable"]))
        for column in sa.inspect(engine).get_columns("ir_v2_graph_versions")
    }


def _graph_indexes(engine):
    return {
        (index["name"], tuple(index["column_names"]), bool(index.get("unique")))
        for index in sa.inspect(engine).get_indexes("ir_v2_graph_versions")
    }


def test_0037_is_one_additive_historical_revision_and_its_schema_matches_models(tmp_path):
    # This fixture is intentionally stamped at 0034 and contains the exact parent
    # universe required through 0037. Later migrations have their own production-
    # shaped fixtures. Keep this test historical instead of asking a 0034-only
    # fixture to prove unrelated future parents.
    script = ScriptDirectory.from_config(migrate.alembic_config())
    revision = script.get_revision("0037")
    assert revision.down_revision == "0036"
    revision_under_test = "0037"
    assert script.get_revision(migrate.head_revision()) is not None

    fresh = _engine(tmp_path, "fresh.db")
    Base.metadata.create_all(fresh)
    upgraded = _at_0034(tmp_path, "upgraded.db")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), revision_under_test)

    expected = _columns(fresh)
    actual = _columns(upgraded)
    assert actual["format_version"] == expected["format_version"] == ("INTEGER", True)
    assert actual["content_address"] == expected["content_address"] == ("VARCHAR(71)", True)
    assert _graph_columns(upgraded) == _graph_columns(fresh)
    assert _graph_indexes(upgraded) == _graph_indexes(fresh)
    assert migrate.schema_version(upgraded) == revision_under_test


def test_0035_empty_sqlite_upgrade_is_idempotent_and_restart_safe(tmp_path):
    engine = _at_0034(tmp_path)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0035")
    assert migrate.schema_version(engine) == "0035"
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0035")
    assert migrate.schema_version(engine) == "0035"
    assert _columns(engine)["format_version"] == ("INTEGER", True)


def test_0035_populated_sqlite_upgrade_never_rewrites_or_backfills_v1_receipts(tmp_path):
    engine = _at_0034(tmp_path)
    before = _insert_legacy_receipt(engine)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0035")
    with engine.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT artifact_json, format_version, content_address "
                "FROM strategy_admissions WHERE admission_address=:address"
            ),
            {"address": _ADDRESS},
        ).one()
    assert row.artifact_json == before
    assert row.format_version is None
    assert row.content_address is None


def test_0035_refuses_lossy_rollback_and_keeps_schema_at_head(tmp_path):
    engine = _at_0034(tmp_path)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0035")
        with pytest.raises(RuntimeError, match="refuses"):
            command.downgrade(migrate.alembic_config(connection), "0034")
    assert migrate.schema_version(engine) == "0035"
    assert "format_version" in _columns(engine)


def test_0035_refusal_preserves_marker_and_recovers_sqlite_upgrade(monkeypatch, tmp_path):
    engine = _at_0034(tmp_path)
    _insert_legacy_receipt(engine)
    # Inject at the migration operation boundary without changing production files.
    from importlib import import_module
    revision = import_module("migrations.versions.20260816_0035_ir_v2_admissions")
    original_add = revision.op.add_column
    calls = 0

    def interrupt(table, column):
        nonlocal calls
        calls += 1
        original_add(table, column)
        if calls == 2:
            raise RuntimeError("injected 0035 refusal")

    monkeypatch.setattr(revision.op, "add_column", interrupt)
    with pytest.raises(RuntimeError, match="injected 0035 refusal"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0035")
    assert migrate.schema_version(engine) == "0034"

    monkeypatch.setattr(revision.op, "add_column", original_add)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0035")
    assert migrate.schema_version(engine) == "0035"
    assert _columns(engine)["format_version"] == ("INTEGER", True)
    assert _columns(engine)["content_address"] == ("VARCHAR(71)", True)
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT format_version, content_address FROM strategy_admissions "
            "WHERE admission_address=:address"), {"address": _ADDRESS}).one()
    assert row == (None, None)


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"), reason="disposable PostgreSQL URL not supplied")
def test_0035_disposable_postgresql_empty_and_populated_upgrade():
    url = os.environ["PT_TEST_POSTGRES_URL"]
    engine = sa.create_engine(url, future=True)
    try:
        with engine.begin() as connection:
            Base.metadata.drop_all(connection)
            Base.metadata.create_all(connection)
            command.stamp(migrate.alembic_config(connection), "0034")
            command.upgrade(migrate.alembic_config(connection), "0035")
        assert migrate.schema_version(engine) == "0035"
        assert _columns(engine)["content_address"] == ("VARCHAR(71)", True)
    finally:
        engine.dispose()


def test_0037_empty_sqlite_upgrade_is_idempotent_and_restart_safe(tmp_path):
    engine = _at_0036(tmp_path)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0037")
    assert migrate.schema_version(engine) == "0037"
    first = _graph_columns(engine)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0037")
    assert migrate.schema_version(engine) == "0037"
    assert _graph_columns(engine) == first


def test_0037_upgrade_preserves_v1_receipt_bytes_and_does_not_infer_graph_evidence(tmp_path):
    engine = _at_0036(tmp_path)
    before = _insert_legacy_receipt(engine)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0037")
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT artifact_json, format_version, content_address "
            "FROM strategy_admissions WHERE admission_address=:address"),
            {"address": _ADDRESS},
        ).one()
        assert row.artifact_json == before
        assert row.format_version is None
        assert row.content_address is None
        assert connection.scalar(sa.text("SELECT count(*) FROM ir_v2_graph_versions")) == 0


def test_0037_interrupted_graph_create_leaves_marker_pre_head_and_recovers(monkeypatch, tmp_path):
    engine = _at_0036(tmp_path)
    revision = importlib.import_module(
        "migrations.versions.20260817_0037_ir_v2_graph_versions"
    )
    original_create = sa.Table.create
    interrupted = False

    def interrupt(table, *args, **kwargs):
        nonlocal interrupted
        result = original_create(table, *args, **kwargs)
        if table.name == "ir_v2_graph_versions" and not interrupted:
            interrupted = True
            raise RuntimeError("injected 0037 interruption")
        return result

    monkeypatch.setattr(sa.Table, "create", interrupt)
    with pytest.raises(RuntimeError, match="injected 0037 interruption"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0037")
    assert migrate.schema_version(engine) == "0036"
    assert "ir_v2_graph_versions" in sa.inspect(engine).get_table_names()

    monkeypatch.setattr(sa.Table, "create", original_create)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0037")
    assert migrate.schema_version(engine) == "0037"
    assert _graph_columns(engine)


def test_0037_refuses_destructive_rollback_and_keeps_graph_schema(tmp_path):
    engine = _at_0036(tmp_path)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0037")
        with pytest.raises(RuntimeError, match="refuses"):
            command.downgrade(migrate.alembic_config(connection), "0036")
    assert migrate.schema_version(engine) == "0037"
    assert "ir_v2_graph_versions" in sa.inspect(engine).get_table_names()


@pytest.mark.skipif(
    not os.environ.get("PT_TEST_POSTGRES_URL"),
    reason="disposable PostgreSQL URL not supplied",
)
def test_0037_disposable_postgresql_upgrade_matches_model_contract():
    engine = sa.create_engine(os.environ["PT_TEST_POSTGRES_URL"], future=True)
    try:
        with engine.begin() as connection:
            Base.metadata.drop_all(connection)
            historical_tables = [
                table for table in Base.metadata.sorted_tables
                if table.name != "ir_v2_graph_versions"
            ]
            Base.metadata.create_all(connection, tables=historical_tables)
            command.stamp(migrate.alembic_config(connection), "0036")
            command.upgrade(migrate.alembic_config(connection), "0037")
        inspector = sa.inspect(engine)
        assert migrate.schema_version(engine) == "0037"
        assert [item["name"] for item in inspector.get_columns(
            "ir_v2_graph_versions"
        )] == [column.name for column in Base.metadata.tables[
            "ir_v2_graph_versions"
        ].columns]
        assert tuple(inspector.get_pk_constraint(
            "ir_v2_graph_versions")["constrained_columns"] or ()) == (
            "owner_id", "graph_identifier", "graph_version"
        )
    finally:
        engine.dispose()
