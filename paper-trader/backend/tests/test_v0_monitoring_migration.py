"""V0 monitoring persistence schema and migration contract."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import uuid

from alembic import command
import pytest
import sqlalchemy as sa

from app.db import migrate
from app.db.models import Base
from app.db.planes import Plane, plane_of
from tests.test_capital_admission_schema import _contract
from tests.test_schema_migrations import _build_from_baseline_at_revision


MONITORING_TABLES = (
    "monitoring_assignments",
    "monitoring_state_snapshots",
    "monitoring_signal_events",
    "monitoring_signal_alerts",
    "monitoring_alert_delivery_attempts",
    "monitoring_alert_attention_events",
    "monitoring_latest_state",
    "monitoring_alert_attention_state",
    "monitoring_signal_reviews",
)

IMMUTABLE_TABLES = frozenset(MONITORING_TABLES[1:6] + (MONITORING_TABLES[8],))
FORBIDDEN = {
    "deployment_id", "broker_account_id", "execution_connection_id",
    "execution_provider", "execution_lease_id", "execution_intent_id",
    "capital", "allocation", "reservation", "quantity", "order_type",
    "order_id", "fill_id", "position_id", "arm_mode", "live_mode",
    "pnl", "balance",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "app.engine", "app.execution", "app.providers", "app.ledger",
    "app.core.deployments", "app.core.execution_binding",
    "app.core.strategy_admissions", "app.api", "app.main",
)
ALLOWED_MONITORING_MODEL_SYMBOLS = frozenset({
    "MonitoringAlertAttentionEventRow",
    "MonitoringAlertAttentionStateRow",
    "MonitoringAlertDeliveryAttemptRow",
    "MonitoringAssignmentRow",
    "MonitoringLatestStateRow",
    "MonitoringSignalAlertRow",
    "MonitoringSignalEventRow",
    "MonitoringSignalReviewRow",
    "MonitoringStateSnapshotRow",
    "Project",
})


def _upgrade(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0044")


def _prior_postgresql_0043(engine: sa.Engine, monkeypatch) -> None:
    from tests import test_postgres_execution_schema as historical

    browser = {
        "browser_credentials", "enrollment_invites", "browser_sessions",
        "browser_auth_attempts",
    }
    static = {"static_instrument_scopes", "static_instrument_scope_revisions"}
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in set(MONITORING_TABLES) | browser | static | {"watchlist_monitoring_revisions"}:
            table.to_metadata(metadata)
    with monkeypatch.context() as patch, engine.begin() as connection:
        patch.setattr(historical, "Base", SimpleNamespace(metadata=metadata))
        historical._install_repository_0037_catalog(connection)
        command.stamp(migrate.alembic_config(connection), "0037")
        command.upgrade(migrate.alembic_config(connection), "0043")
    assert migrate.schema_version(engine) == "0043"
    assert set(MONITORING_TABLES).isdisjoint(sa.inspect(engine).get_table_names())


def test_v0_monitoring_tables_exist_only_in_the_user_plane():
    assert set(MONITORING_TABLES) <= set(Base.metadata.tables)
    assert {name: plane_of(name) for name in MONITORING_TABLES} == {
        name: Plane.USER for name in MONITORING_TABLES
    }


def test_v0_monitoring_revision_remains_unique_below_current_operations_head():
    assert migrate.head_revision() == "0056"
    assert not list(Path(migrate.MIGRATIONS_DIR, "versions").glob("*0044*"))[1:]
    assert not list(Path(migrate.MIGRATIONS_DIR, "versions").glob("*0045*"))[1:]
    assert not list(Path(migrate.MIGRATIONS_DIR, "versions").glob("*0046*"))[1:]
    assert not list(Path(migrate.MIGRATIONS_DIR, "versions").glob("*0047*"))[1:]
    assert not list(Path(migrate.MIGRATIONS_DIR, "versions").glob("*0048*"))[1:]


@pytest.mark.parametrize("marker", ["0044", "0045", "0046", "0047", "0048", "0049", "0050", "0051", "0052", "0053", "0054", "0055", "0056"])
def test_monitoring_schema_accepts_only_the_closed_compatible_head_set(tmp_path, marker):
    from app.monitoring.repository import validate_monitoring_schema
    from tests.test_v0_monitoring_persistence import _engine

    engine = _engine(tmp_path, f"monitoring-compatible-{marker}.db")
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = ?", (marker,))
        validate_monitoring_schema(connection)
    engine.dispose()


@pytest.mark.parametrize("markers", [
    ("0043",), ("0057",), ("branch-paper-charge",), ("unknown",),
    ("0044", "0045"), ("0045", "0046"), ("0046", "0047"),
])
def test_monitoring_schema_refuses_old_future_branch_multiple_and_unknown_heads(
        tmp_path, markers):
    from app.monitoring.repository import MonitoringCorrupt, validate_monitoring_schema
    from tests.test_v0_monitoring_persistence import _engine

    engine = _engine(tmp_path, "monitoring-incompatible-marker.db")
    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM alembic_version")
        for marker in markers:
            connection.exec_driver_sql(
                "INSERT INTO alembic_version(version_num) VALUES (?)", (marker,))
        with pytest.raises(MonitoringCorrupt, match="exact compatible"):
            validate_monitoring_schema(connection)
    engine.dispose()


def _check_count(manifest) -> int:
    return sum(len(table["checks"]) for table in manifest.values())


def test_sqlite_all_112_model_and_reflected_checks_compare_at_compatible_head(tmp_path):
    from app.monitoring.repository import (
        _actual_relational_manifest, _expected_relational_manifest,
        validate_monitoring_schema,
    )
    from tests.test_v0_monitoring_persistence import _engine

    engine = _engine(tmp_path, "monitoring-112-checks.db")
    with engine.connect() as connection:
        expected = _expected_relational_manifest(connection)
        actual = _actual_relational_manifest(connection)
        assert _check_count(expected) == _check_count(actual) == 112
        validate_monitoring_schema(connection)


def test_postgresql16_all_112_model_and_reflected_checks_compare_at_current_head(pg_sandbox):
    from app.monitoring.repository import (
        _actual_relational_manifest, _expected_relational_manifest,
        validate_monitoring_schema,
    )

    engine = pg_sandbox.engine("monitoring_112_checks")
    assert migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    ) == "0048"
    with engine.connect() as connection:
        expected = _expected_relational_manifest(connection)
        actual = _actual_relational_manifest(connection)
        assert _check_count(expected) == _check_count(actual) == 112
        validate_monitoring_schema(connection)


def test_sqlite_0043_upgrade_is_additive_atomic_idempotent_and_model_equal(tmp_path):
    upgraded = _build_from_baseline_at_revision(tmp_path, "monitoring-upgrade.db", "0043")
    with upgraded.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO enrollment_invites "
            "(invite_digest,email_normalized,purpose,created_at,expires_at,consumed_at) "
            "VALUES ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',"
            "'unknown','enrollment','2026-08-29 09:00:00','2026-08-29 10:00:00',NULL)")
    prior_tables = set(sa.inspect(upgraded).get_table_names()) - {"alembic_version"}
    with upgraded.connect() as connection:
        prior_counts = {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                sa.Table(name, sa.MetaData(), autoload_with=connection)))
            for name in prior_tables
        }

    interrupted = False

    def fail_midway(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal interrupted
        if not interrupted and "CREATE TABLE monitoring_signal_events" in statement:
            interrupted = True
            raise RuntimeError("synthetic 0044 interruption")

    sa.event.listen(upgraded, "before_cursor_execute", fail_midway)
    try:
        with pytest.raises(RuntimeError, match="synthetic 0044 interruption"):
            _upgrade(upgraded)
    finally:
        sa.event.remove(upgraded, "before_cursor_execute", fail_midway)
    assert migrate.schema_version(upgraded) == "0043"
    assert set(MONITORING_TABLES).isdisjoint(sa.inspect(upgraded).get_table_names())

    _upgrade(upgraded)
    _upgrade(upgraded)
    assert migrate.schema_version(upgraded) == "0044"
    with upgraded.connect() as connection:
        assert {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                sa.Table(name, sa.MetaData(), autoload_with=connection)))
            for name in prior_tables
        } == prior_counts
        assert connection.exec_driver_sql(
            "SELECT email_normalized,consumed_at FROM enrollment_invites "
            "WHERE invite_digest='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
        ).one() == ("unknown", None)

    fresh = sa.create_engine(f"sqlite:///{tmp_path / 'monitoring-fresh.db'}")
    Base.metadata.create_all(fresh)
    for table in MONITORING_TABLES:
        assert _contract(upgraded, table) == _contract(fresh, table)
    upgraded.dispose()
    fresh.dispose()


def test_monitoring_schema_has_no_authority_columns_or_foreign_keys():
    for name in MONITORING_TABLES:
        table = Base.metadata.tables[name]
        assert FORBIDDEN.isdisjoint(table.c.keys())
        targets = {fk.column.table.name for fk in table.foreign_keys}
        assert targets <= set(MONITORING_TABLES) | {"projects", "memberships"}
        assert "signal_events" not in targets
    events = Base.metadata.tables["monitoring_signal_events"]
    assert "event_id" not in events.c
    assert tuple(column.name for column in events.primary_key.columns) == (
        "owner_id", "assignment_id", "content_address",
    )
    assignment_fks = {
        fk.parent.name for fk in Base.metadata.tables["monitoring_assignments"].foreign_keys
    }
    assert "data_connection_id" not in assignment_fks


def test_sqlite_partial_schema_and_destructive_downgrade_refuse(tmp_path):
    partial = _build_from_baseline_at_revision(tmp_path, "monitoring-partial.db", "0043")
    with partial.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE monitoring_latest_state (wrong INTEGER)")
        connection.exec_driver_sql("INSERT INTO monitoring_latest_state VALUES (7)")
    with pytest.raises(RuntimeError, match="partial/unproven"):
        _upgrade(partial)
    assert migrate.schema_version(partial) == "0043"
    with partial.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT wrong FROM monitoring_latest_state").scalar_one() == 7

    complete = _build_from_baseline_at_revision(tmp_path, "monitoring-complete.db", "0044")
    with pytest.raises(RuntimeError, match="destructive downgrade"):
        with complete.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0043")
    assert migrate.schema_version(complete) == "0044"
    partial.dispose()
    complete.dispose()


def test_append_facts_have_update_and_delete_guards(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'monitoring-triggers.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        triggers = {
            (table, name)
            for table, name in connection.execute(sa.text(
                "SELECT tbl_name,name FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name LIKE 'monitoring_%'"))
        }
    for table in IMMUTABLE_TABLES:
        assert (table, f"{table}_refuse_update") in triggers
        assert (table, f"{table}_refuse_delete") in triggers
    assert ("monitoring_assignments", "monitoring_assignments_refuse_identity_change") in triggers
    assert ("monitoring_assignments", "monitoring_assignments_refuse_delete") in triggers
    engine.dispose()


def _assert_no_authority_imports(path: Path) -> None:
    tree = ast.parse(path.read_text())
    imports = []
    model_symbols = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
            assert not any(alias.name == "app.db.models" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
            if node.module == "app.db.models":
                model_symbols.update(alias.name for alias in node.names)
            assert not (
                node.module == "app.db"
                and any(alias.name == "models" for alias in node.names)
            )
        elif isinstance(node, ast.Call):
            dynamic = (
                isinstance(node.func, ast.Name)
                and node.func.id in {"__import__", "import_module"}
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            )
            assert not dynamic
    assert not [name for name in imports if name.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    assert model_symbols == ALLOWED_MONITORING_MODEL_SYMBOLS
    from app.db import models as model_module
    from app.db.planes import Plane, plane_of
    for symbol in sorted(model_symbols):
        mapped = getattr(model_module, symbol)
        assert plane_of(mapped.__table__.name) is Plane.USER


def test_repository_authority_import_guard_is_mutation_sensitive_and_restores_bytes(tmp_path):
    source = Path(__file__).parents[1] / "app/monitoring/repository.py"
    _assert_no_authority_imports(source)
    isolated = tmp_path / "repository.py"
    original = source.read_bytes()
    isolated.write_bytes(original)
    before = hashlib.sha256(isolated.read_bytes()).hexdigest()
    isolated.write_bytes(original + b"\nfrom app.execution import leases\n")
    with pytest.raises(AssertionError):
        _assert_no_authority_imports(isolated)
    for symbol in (
        "Deployment", "BrokerAccount", "ExecutionIntent", "Position",
        "CapitalReservationRecord", "ExecutionOrderEvent", "FillAllocationRecord",
    ):
        isolated.write_bytes(
            original + f"\nfrom app.db.models import {symbol}\n".encode())
        with pytest.raises(AssertionError):
            _assert_no_authority_imports(isolated)
    for dynamic in (
        "__import__('app.execution.leases')",
        "import importlib\nimportlib.import_module('app.ledger.service')",
        "from importlib import import_module\nimport_module('app.providers.brokers')",
    ):
        isolated.write_bytes(original + b"\n" + dynamic.encode() + b"\n")
        with pytest.raises(AssertionError):
            _assert_no_authority_imports(isolated)
    isolated.write_bytes(original)
    assert hashlib.sha256(isolated.read_bytes()).hexdigest() == before
    _assert_no_authority_imports(isolated)


def _rewrite_sqlite_table(engine, table: str, transform) -> None:
    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        original = raw.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        changed = transform(original)
        assert changed != original
        version = raw.execute("PRAGMA schema_version").fetchone()[0]
        raw.execute("PRAGMA writable_schema=ON")
        raw.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
                    (changed, table))
        raw.execute("PRAGMA writable_schema=OFF")
        raw.execute(f"PRAGMA schema_version={version + 1}")
        raw.commit()


GROUPING_CHECK_PAIRS = {
    "withdrawal": (
        "(lifecycle_state = 'WITHDRAWN' AND withdrawn_at IS NOT NULL) OR "
        "(lifecycle_state <> 'WITHDRAWN' AND withdrawn_at IS NULL)",
        "lifecycle_state = 'WITHDRAWN' AND "
        "(withdrawn_at IS NOT NULL OR lifecycle_state <> 'WITHDRAWN') AND "
        "withdrawn_at IS NULL",
    ),
    "failure_code": (
        "(outcome = 'FAILED' AND failure_code IS NOT NULL) OR "
        "(outcome = 'DELIVERED' AND failure_code IS NULL)",
        "outcome = 'FAILED' AND "
        "(failure_code IS NOT NULL OR outcome = 'DELIVERED') AND "
        "failure_code IS NULL",
    ),
    "nullable_address": (
        "value IS NULL OR (length(value) = 71 AND substr(value,1,7) = 'sha256:' "
        "AND substr(value,8) = lower(substr(value,8)))",
        "(value IS NULL OR length(value) = 71) AND substr(value,1,7) = 'sha256:' "
        "AND substr(value,8) = lower(substr(value,8))",
    ),
    "timestamp": (
        "(read_at IS NULL OR read_at >= alert_event_at) AND "
        "alert_event_at <= alert_valid_until",
        "read_at IS NULL OR (read_at >= alert_event_at AND "
        "alert_event_at <= alert_valid_until)",
    ),
    "arithmetic_check": (
        "(snapshot_sequence = 0 AND predecessor_snapshot_address IS NULL) OR "
        "(snapshot_sequence > 0 AND predecessor_snapshot_address IS NOT NULL)",
        "snapshot_sequence = 0 AND "
        "(predecessor_snapshot_address IS NULL OR snapshot_sequence > 0) AND "
        "predecessor_snapshot_address IS NOT NULL",
    ),
}


@pytest.mark.parametrize("dialect", ("sqlite", "postgresql"))
@pytest.mark.parametrize("family", tuple(GROUPING_CHECK_PAIRS))
def test_check_comparator_distinguishes_same_token_regrouping(dialect, family):
    from app.monitoring.repository import _conservative_check_sql

    original, regrouped = GROUPING_CHECK_PAIRS[family]
    identifiers = frozenset(re.findall(
        r"\b[a-z_][a-z0-9_]*\b", f"{original} {regrouped}".lower()))
    normalize = lambda value: _conservative_check_sql(
        value, identifiers=identifiers, string_identifiers=identifiers,
        postgresql=dialect == "postgresql")
    assert re.sub(r"[()]", "", normalize(original)) == re.sub(
        r"[()]", "", normalize(regrouped))
    assert normalize(original) != normalize(regrouped), dialect


CHECK_LEXICAL_PAIRS = (
    (
        "literal_case", "monitoring_assignments",
        "lifecycle_state = 'ACTIVE'", "lifecycle_state = 'active'", False,
    ),
    (
        "literal_whitespace", "monitoring_assignments",
        "lifecycle_state = 'A B'", "lifecycle_state = 'AB'", False,
    ),
    (
        "metadata_identifier_inside_literal", "monitoring_assignments",
        "lifecycle_state = 'lifecycle_state::text'",
        "lifecycle_state = 'lifecycle_state'", False,
    ),
    (
        "literal_shield_token_bytes", "monitoring_assignments",
        "lifecycle_state = '\ue0001\ue001'", "lifecycle_state = '\ue0000\ue001'", False,
    ),
    (
        "known_lowercase_quote", "monitoring_assignments",
        '"lifecycle_state" = \'ACTIVE\'', "lifecycle_state = 'ACTIVE'", True,
    ),
    (
        "unknown_quote", "monitoring_assignments",
        '"UnknownCase" = \'ACTIVE\'', "UnknownCase = 'ACTIVE'", False,
    ),
    (
        "safe_identifier_text_cast", "monitoring_assignments",
        "lifecycle_state = 'ACTIVE'", "lifecycle_state::text = 'ACTIVE'", "postgresql",
    ),
    (
        "safe_literal_text_cast", "monitoring_assignments",
        "lifecycle_state = 'ACTIVE'", "lifecycle_state = 'ACTIVE'::text", "postgresql",
    ),
    (
        "safe_jsonb_cast", "monitoring_state_snapshots",
        "CAST(canonical_json AS JSONB) ->> 'kind' IS NOT NULL",
        "canonical_json::jsonb ->> 'kind' IS NOT NULL", "postgresql",
    ),
    (
        "authoritative_numeric_cast", "monitoring_state_snapshots",
        "snapshot_sequence::numeric > 0", "snapshot_sequence > 0", False,
    ),
    (
        "unknown_varchar_cast", "monitoring_assignments",
        "lifecycle_state::varchar = 'ACTIVE'", "lifecycle_state = 'ACTIVE'", False,
    ),
)


@pytest.mark.parametrize("dialect", ("sqlite", "postgresql"))
@pytest.mark.parametrize(
    "case,table_name,expected,reflected,equivalent", CHECK_LEXICAL_PAIRS,
)
def test_check_comparator_literal_quote_and_cast_matrix_both_dialects(
    dialect, case, table_name, expected, reflected, equivalent,
):
    from app.monitoring.repository import _check_sql_matches

    should_match = equivalent is True or equivalent == dialect
    assert _check_sql_matches(
        Base.metadata.tables[table_name], "ck_matrix_probe", dialect,
        expected, reflected,
    ) is should_match, case


def test_check_comparator_accepts_only_closed_literal_preserving_rewrites():
    from app.monitoring.repository import _check_sql_matches, _conservative_check_sql

    identifiers = frozenset({
        "canonical_json", "lifecycle_state", "outcome", "payload_size_bytes",
    })
    strings = frozenset({"canonical_json", "lifecycle_state", "outcome"})
    normalize = lambda value: _conservative_check_sql(
        value, identifiers=identifiers, string_identifiers=strings)

    assert normalize('(( "lifecycle_state" = \'ACTIVE\' ))') == normalize(
        "lifecycle_state= 'ACTIVE'")
    assert normalize("lifecycle_state IN ('ACTIVE','PAUSED')") == normalize(
        "lifecycle_state = ANY (ARRAY['ACTIVE'::character varying,"
        "'PAUSED'::character varying]::text[])")
    assert normalize("lifecycle_state IN ('ACTIVE','PAUSED')") == normalize(
        "lifecycle_state::text = ANY (ARRAY["
        "'ACTIVE'::character varying::text,"
        "'PAUSED'::character varying::text])")
    assert normalize("lifecycle_state IN ('ACTIVE','PAUSED')") != normalize(
        "lifecycle_state = ANY (ARRAY['ACTIVE','PAUSED'])")
    assert normalize("CAST(canonical_json AS JSONB) ->> 'kind' IS NOT NULL") == normalize(
        "(canonical_json::jsonb ->> 'kind') IS NOT NULL")
    assert normalize("lifecycle_state = 'ACTIVE'") != normalize(
        "lifecycle_state = 'active'")
    assert normalize("outcome = 'A B'") != normalize("outcome = 'AB'")
    assert normalize("payload_size_bytes > 0") != normalize(
        "payload_size_bytes >= 0")
    assert normalize("payload_size_bytes > 0") != normalize(
        "payload_size_bytes > 1")
    assert normalize("payload_size_bytes::numeric > 0") != normalize(
        "payload_size_bytes > 0")
    assert normalize("lifecycle_state = 'ACTIVE' OR outcome = 'FAILED'") != normalize(
        "outcome = 'FAILED' OR lifecycle_state = 'ACTIVE'")
    with pytest.raises(ValueError, match="outside monitoring metadata"):
        normalize('"UnknownCase" = \'ACTIVE\'')

    assignment_table = Base.metadata.tables["monitoring_assignments"]
    expected, reflected = GROUPING_CHECK_PAIRS["withdrawal"][0], (
        "lifecycle_state = 'WITHDRAWN' AND withdrawn_at IS NOT NULL OR "
        "lifecycle_state <> 'WITHDRAWN' AND withdrawn_at IS NULL"
    )
    assert not _check_sql_matches(
        assignment_table, "ck_unknown_future", "postgresql", expected, reflected)
    assert not _check_sql_matches(
        assignment_table, "ck_monitoring_assignments_lifecycle", "sqlite",
        "lifecycle_state IN ('ACTIVE','PAUSED')",
        "lifecycle_state = ANY (ARRAY['ACTIVE'::character varying,"
        "'PAUSED'::character varying]::text[])",
    )


@pytest.mark.parametrize("mutation", (
    "permissive_trigger", "missing_dedupe_unique", "altered_scoped_fk",
    "type", "nullability", "default", "extra_constraint", "extra_trigger",
    "regrouped_check", "literal_case",
))
def test_sqlite_exact_schema_manifest_mutations_refuse_and_restore(
    tmp_path, mutation,
):
    from app.monitoring.repository import (
        MonitoringCorrupt, MonitoringRepository, monitoring_schema_manifest,
        validate_monitoring_schema, validate_persisted_monitoring,
    )
    from sqlalchemy.orm import Session
    from tests.test_v0_monitoring_persistence import _engine

    engine = _engine(tmp_path, f"schema-manifest-{mutation}.db")
    path = Path(engine.url.database)
    with engine.connect() as connection:
        baseline_manifest = monitoring_schema_manifest(connection)
    engine.dispose()
    baseline_bytes = path.read_bytes()
    mutated = sa.create_engine(f"sqlite:///{path}", future=True)
    if mutation == "permissive_trigger":
        with mutated.begin() as connection:
            connection.exec_driver_sql(
                "DROP TRIGGER monitoring_signal_events_refuse_update")
            connection.exec_driver_sql(
                "CREATE TRIGGER monitoring_signal_events_refuse_update "
                "BEFORE UPDATE ON monitoring_signal_events BEGIN SELECT 1; END")
    elif mutation == "extra_trigger":
        with mutated.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TRIGGER monitoring_signal_events_extra "
                "BEFORE UPDATE ON monitoring_signal_events BEGIN SELECT 1; END")
    elif mutation == "extra_constraint":
        _rewrite_sqlite_table(
            mutated, "monitoring_signal_events",
            lambda sql: sql[:-1] + ", CONSTRAINT ck_monitoring_events_extra "
            "CHECK (created_at IS NOT NULL))",
        )
    elif mutation == "regrouped_check":
        _rewrite_sqlite_table(
            mutated, "monitoring_assignments",
            lambda sql: sql.replace(
                *GROUPING_CHECK_PAIRS["withdrawal"], 1),
        )
    elif mutation == "literal_case":
        _rewrite_sqlite_table(
            mutated, "monitoring_assignments",
            lambda sql: sql.replace("lifecycle_state = 'WITHDRAWN'",
                                    "lifecycle_state = 'withdrawn'", 1),
        )
    elif mutation == "missing_dedupe_unique":
        _rewrite_sqlite_table(mutated, "monitoring_signal_events", lambda sql: sql.replace(
            "CONSTRAINT uq_monitoring_events_dedupe UNIQUE (owner_id, dedupe_address)",
            "CONSTRAINT uq_monitoring_events_dedupe UNIQUE "
            "(owner_id, dedupe_address, assignment_id)", 1,
        ))
    elif mutation == "altered_scoped_fk":
        _rewrite_sqlite_table(mutated, "monitoring_signal_events", lambda sql: sql.replace(
            "CONSTRAINT fk_monitoring_events_assignment FOREIGN KEY(owner_id, assignment_id) "
            "REFERENCES monitoring_assignments (owner_id, assignment_id) ON DELETE RESTRICT",
            "CONSTRAINT fk_monitoring_events_assignment FOREIGN KEY(owner_id, assignment_id) "
            "REFERENCES monitoring_assignments (owner_id, assignment_id) ON DELETE NO ACTION",
            1,
        ))
    elif mutation == "type":
        _rewrite_sqlite_table(mutated, "monitoring_signal_events", lambda sql: sql.replace(
            "dedupe_address VARCHAR(71) NOT NULL",
            "dedupe_address VARCHAR(72) NOT NULL", 1,
        ))
    elif mutation == "nullability":
        _rewrite_sqlite_table(mutated, "monitoring_signal_events", lambda sql: sql.replace(
            "dedupe_address VARCHAR(71) NOT NULL",
            "dedupe_address VARCHAR(71)", 1,
        ))
    else:
        _rewrite_sqlite_table(mutated, "monitoring_signal_events", lambda sql: sql.replace(
            "created_at DATETIME NOT NULL",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL", 1,
        ))
    with mutated.connect() as connection:
        before = {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name]))
            for name in MONITORING_TABLES
        }
        with pytest.raises(MonitoringCorrupt, match="schema contract drift"):
            validate_monitoring_schema(connection)
        if mutation in {"regrouped_check", "literal_case"}:
            with pytest.raises(MonitoringCorrupt, match="schema contract drift"):
                validate_persisted_monitoring(connection)
            with Session(bind=connection) as session:
                with pytest.raises(MonitoringCorrupt, match="schema contract drift"):
                    MonitoringRepository(session, owner_id="tenant.alpha")
        assert connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version").scalar_one() == "0048"
        assert before == {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name]))
            for name in MONITORING_TABLES
        }
    mutated.dispose()
    path.write_bytes(baseline_bytes)
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(baseline_bytes).digest()
    restored = sa.create_engine(f"sqlite:///{path}", future=True)
    with restored.connect() as connection:
        validate_monitoring_schema(connection)
        assert monitoring_schema_manifest(connection) == baseline_manifest
    restored.dispose()


@pytest.mark.parametrize("mutation", (
    "permissive_trigger", "missing_dedupe_unique", "altered_scoped_fk",
    "type", "nullability", "default", "extra_constraint", "extra_trigger",
    "regrouped_check", "literal_case",
))
def test_postgresql_exact_schema_manifest_mutations_refuse_and_rollback(
    pg_sandbox, mutation,
):
    from app.db.copy_contract import stream_table_summary
    from app.monitoring.repository import (
        MonitoringCorrupt, MonitoringRepository, monitoring_schema_manifest,
        validate_monitoring_schema, validate_persisted_monitoring,
    )
    from sqlalchemy.orm import Session
    from tests.test_v0_monitoring_persistence import (
        _exercise_complete_two_owner_matrix,
    )

    engine = pg_sandbox.engine("monitoring_manifest")
    if not sa.inspect(engine).get_table_names():
        migrate.init_schema(
            engine, create_all=lambda: Base.metadata.create_all(engine),
            legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
            expected_tables=Base.metadata.tables,
        )
    assert _exercise_complete_two_owner_matrix(engine)["no_side_effect"] is True
    with engine.connect() as baseline_connection:
        baseline = monitoring_schema_manifest(baseline_connection)
        baseline_marker = baseline_connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version").scalar_one()
        baseline_rows = {
            name: stream_table_summary(
                baseline_connection, Base.metadata.tables[name])
            for name in MONITORING_TABLES
        }
        assert all(summary["rows"] > 0 for summary in baseline_rows.values())
    with engine.connect() as connection:
        transaction = connection.begin()
        if mutation == "permissive_trigger":
            connection.exec_driver_sql(
                "CREATE OR REPLACE FUNCTION monitoring_signal_events_refuse_mutation() "
                "RETURNS trigger AS $$ BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql")
        elif mutation == "missing_dedupe_unique":
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events "
                "DROP CONSTRAINT uq_monitoring_events_dedupe")
        elif mutation == "altered_scoped_fk":
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events "
                "DROP CONSTRAINT fk_monitoring_events_assignment")
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events ADD CONSTRAINT "
                "fk_monitoring_events_assignment FOREIGN KEY(owner_id,assignment_id) "
                "REFERENCES monitoring_assignments(owner_id,assignment_id) ON DELETE CASCADE")
        elif mutation == "type":
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events ALTER COLUMN "
                "dedupe_address TYPE VARCHAR(72)")
        elif mutation == "nullability":
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events ALTER COLUMN "
                "dedupe_address DROP NOT NULL")
        elif mutation == "default":
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events ALTER COLUMN "
                "created_at SET DEFAULT CURRENT_TIMESTAMP")
        elif mutation == "extra_constraint":
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_signal_events ADD CONSTRAINT "
                "ck_monitoring_events_extra CHECK (created_at IS NOT NULL)")
        elif mutation in {"regrouped_check", "literal_case"}:
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_assignments DROP CONSTRAINT "
                "ck_monitoring_assignments_withdrawal")
            changed = (
                GROUPING_CHECK_PAIRS["withdrawal"][1]
                if mutation == "regrouped_check"
                else GROUPING_CHECK_PAIRS["withdrawal"][0].replace(
                    "lifecycle_state = 'WITHDRAWN'",
                    "lifecycle_state = 'withdrawn'", 1)
            )
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_assignments ADD CONSTRAINT "
                f"ck_monitoring_assignments_withdrawal CHECK ({changed}) NOT VALID")
        else:
            connection.exec_driver_sql(
                "CREATE OR REPLACE FUNCTION monitoring_signal_events_extra_fn() "
                "RETURNS trigger AS $$ BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql")
            connection.exec_driver_sql(
                "CREATE TRIGGER monitoring_signal_events_extra BEFORE UPDATE "
                "ON monitoring_signal_events FOR EACH ROW EXECUTE FUNCTION "
                "monitoring_signal_events_extra_fn()")
        before = {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name]))
            for name in MONITORING_TABLES
        }
        with pytest.raises(MonitoringCorrupt, match="schema contract drift"):
            validate_monitoring_schema(connection)
        if mutation in {"regrouped_check", "literal_case"}:
            with pytest.raises(MonitoringCorrupt, match="schema contract drift"):
                validate_persisted_monitoring(connection)
            with Session(bind=connection) as session:
                with pytest.raises(MonitoringCorrupt, match="schema contract drift"):
                    MonitoringRepository(session, owner_id="tenant.alpha")
        assert connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version").scalar_one() == "0048"
        assert before == {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name]))
            for name in MONITORING_TABLES
        }
        transaction.rollback()
    with engine.connect() as connection:
        validate_monitoring_schema(connection)
        assert connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version").scalar_one() == baseline_marker
        assert monitoring_schema_manifest(connection) == baseline
        assert {
            name: stream_table_summary(connection, Base.metadata.tables[name])
            for name in MONITORING_TABLES
        } == baseline_rows


def test_complete_two_owner_repository_matrix_postgresql16(pg_sandbox):
    from tests.test_v0_monitoring_persistence import (
        _exercise_complete_two_owner_matrix, _seed_two_owners,
    )

    engine = pg_sandbox.engine(
        "monitoring_tenant_matrix", pool_size=2, max_overflow=0, pool_timeout=1,
    )
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    )
    _seed_two_owners(engine)
    result = _exercise_complete_two_owner_matrix(engine)
    assert result == {
        "methods": 18,
        "foreign_missing_pairs": 16,
        "same_owner_controls": 18,
        "no_side_effect": True,
    }
    assert engine.pool.checkedout() == 0


def test_concurrent_event_reorder_postgresql16(pg_sandbox):
    from tests.test_v0_monitoring_persistence import (
        _exercise_concurrent_event_reorder, _seed_two_owners,
    )

    engine = pg_sandbox.engine(
        "monitoring_event_reorder", pool_size=2, max_overflow=0, pool_timeout=1,
    )
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    )
    _seed_two_owners(engine)
    result = _exercise_concurrent_event_reorder(engine)
    assert result["persisted"] in {1, 2}
    assert engine.pool.checkedout() == 0


def test_event_order_delayed_retry_and_atomic_refusal_postgresql16(pg_sandbox):
    from sqlalchemy.orm import Session
    from app.db.models import MonitoringSignalEventRow
    from app.monitoring.repository import (
        MonitoringConflict, MonitoringRepository, validate_persisted_monitoring,
    )
    from tests.test_v0_monitoring_persistence import (
        _facts, _owned_facts, _seed_two_owners, _spec, _transition, T0,
    )

    engine = pg_sandbox.engine(
        "monitoring_event_order", pool_size=2, max_overflow=0, pool_timeout=1,
    )
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    )
    _seed_two_owners(engine)
    initial, _unused_after, _unused_event, _unused_alert = _facts()
    first_snapshot, first_event, _first_alert = _transition(initial, 1)
    second_snapshot, second_event, _second_alert = _transition(first_snapshot, 2)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        for snapshot in (initial, first_snapshot, second_snapshot):
            repository.append_state_snapshot(snapshot, created_at=snapshot.effective_at)
        with pytest.raises(MonitoringConflict, match="ordered|current|state_before"):
            repository.append_event(
                second_event, created_at=second_event.knowledge_cutoff_at)
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 0
        repository.append_event(
            first_event, created_at=first_event.knowledge_cutoff_at)
        repository.append_event(
            second_event, created_at=second_event.knowledge_cutoff_at)
        revision = repository.get_assignment(first_event.assignment_id).optimistic_revision
        assert repository.append_event(
            first_event, created_at=first_event.knowledge_cutoff_at) == first_event
        assert repository.get_assignment(
            first_event.assignment_id).optimistic_revision == revision

    atomic_before, atomic_after, atomic_event, _atomic_alert = _owned_facts(
        "tenant.alpha", "assignment.atomic")
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(
            _spec("assignment.atomic", "project.alpha"), now=T0)
        repository.append_state_snapshot(atomic_before, created_at=T0)
        repository.append_state_snapshot(
            atomic_after, created_at=atomic_event.event_at)

        def refuse(*_args, **_kwargs):
            raise MonitoringConflict("synthetic projection refusal")

        repository._advance_latest_projection = refuse
        with pytest.raises(MonitoringConflict, match="synthetic projection refusal"):
            repository.append_event(
                atomic_event, created_at=atomic_event.knowledge_cutoff_at)
    with engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow).where(
                MonitoringSignalEventRow.assignment_id == "assignment.atomic")) == 0
        validate_persisted_monitoring(connection)
    assert engine.pool.checkedout() == 0


def _timing_summary(values):
    ordered = sorted(values)
    assert ordered
    return {
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[max(0, int(len(ordered) * 0.95) - 1)],
        "max": ordered[-1],
    }


def test_postgresql16_mixed_owner_retained_corpus_and_transaction_metrics(pg_sandbox):
    import datetime as dt
    from sqlalchemy.orm import Session
    from app.db.models import (
        Membership, MonitoringAlertDeliveryAttemptRow, MonitoringAssignmentRow,
        Organization, Project, User,
    )
    from app.ir.hashing import canonical_json
    from app.monitoring import contracts
    from app.monitoring.repository import (
        MONITORING_TABLES, MonitoringRepository, validate_persisted_monitoring,
    )
    from tests.test_v0_monitoring_persistence import _owned_facts, _spec, T0

    engine = pg_sandbox.engine(
        "monitoring_resource", pool_size=2, max_overflow=0, pool_timeout=1,
    )
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    )
    owners = [f"tenant.pg.resource.{index:02d}" for index in range(15)]
    with Session(engine) as session, session.begin():
        for index, owner in enumerate(owners):
            user = f"user.pg.resource.{index:02d}"
            project = f"project.pg.resource.{index:02d}"
            session.add(Organization(organization_id=owner, name=owner))
            session.add(User(
                user_id=user, email_normalized=f"{user}@example.test",
                display_name=user,
            ))
            session.flush()
            session.add(Membership(
                organization_id=owner, user_id=user,
                role="owner", status="active",
            ))
            session.add(Project(
                project_id=project, owner_id=owner, name=project,
                description="", status="active",
            ))

    facts = []
    for owner_index, owner in enumerate(owners):
        project = f"project.pg.resource.{owner_index:02d}"
        with Session(engine, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id=owner)
            for assignment_index in range(20):
                assignment_id = f"assignment.{assignment_index:02d}"
                before, after, event, alert = _owned_facts(owner, assignment_id)
                repository.create_assignment(
                    _spec(assignment_id, project), now=T0)
                repository.append_state_snapshot(before, created_at=T0)
                repository.append_state_snapshot(after, created_at=event.event_at)
                facts.append((owner, event, alert))

    append_projection_seconds = []
    for owner, event, alert in facts:
        started = time.perf_counter()
        with Session(engine, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id=owner)
            repository.append_event(event, created_at=event.knowledge_cutoff_at)
            repository.append_alert(alert, created_at=event.knowledge_cutoff_at)
        append_projection_seconds.append(time.perf_counter() - started)

    assignment_cas_seconds = []
    for owner, event, _alert in facts:
        started = time.perf_counter()
        with Session(engine, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id=owner)
            paused = repository.update_assignment(
                event.assignment_id, expected_revision=3,
                lifecycle_state="PAUSED", now=T0 + dt.timedelta(minutes=10),
            )
            repository.update_assignment(
                event.assignment_id, expected_revision=paused.optimistic_revision,
                lifecycle_state="ACTIVE", now=T0 + dt.timedelta(minutes=11),
            )
        assignment_cas_seconds.append(time.perf_counter() - started)

    rebuild_seconds = []
    for owner in owners:
        started = time.perf_counter()
        with Session(engine, expire_on_commit=False) as session, session.begin():
            result = MonitoringRepository(
                session, owner_id=owner).rebuild_projections()
            assert result == {"latest_state": 20, "attention_state": 20}
        rebuild_seconds.append(time.perf_counter() - started)

    lock_wait_seconds = []
    hot_owner = owners[0]
    for _trial in range(20):
        locked = threading.Event()

        def holder():
            with Session(engine) as session, session.begin():
                session.scalar(sa.select(MonitoringAssignmentRow).where(
                    MonitoringAssignmentRow.owner_id == hot_owner,
                    MonitoringAssignmentRow.assignment_id == "assignment.00",
                ).with_for_update())
                locked.set()
                time.sleep(0.03)

        def waiter():
            assert locked.wait(2)
            started = time.perf_counter()
            with Session(engine) as session, session.begin():
                session.scalar(sa.select(MonitoringAssignmentRow).where(
                    MonitoringAssignmentRow.owner_id == hot_owner,
                    MonitoringAssignmentRow.assignment_id == "assignment.00",
                ).with_for_update())
            return time.perf_counter() - started

        with ThreadPoolExecutor(max_workers=2) as pool:
            holder_future = pool.submit(holder)
            waiter_future = pool.submit(waiter)
            holder_future.result(timeout=5)
            lock_wait_seconds.append(waiter_future.result(timeout=5))

    delivery_rows = []
    bulk_seconds = []
    for index, (owner, _event, alert) in enumerate(facts):
        attempts = 2000 if index < 30 else 144 if index < 220 else 143
        for sequence in range(1, attempts + 1):
            attempt = contracts.AlertDeliveryAttempt.create(
                alert=alert, sequence=sequence,
                outcome=contracts.DeliveryOutcome.DELIVERED,
                occurred_at=alert.event_at + dt.timedelta(seconds=sequence),
            )
            delivery_rows.append({
                "owner_id": attempt.owner_id,
                "assignment_id": attempt.assignment_id,
                "attempt_address": attempt.address,
                "attempt_id": attempt.attempt_id,
                "alert_address": attempt.alert_address,
                "sequence": attempt.sequence,
                "channel": attempt.channel.value,
                "outcome": attempt.outcome.value,
                "occurred_at": attempt.occurred_at.replace(tzinfo=None),
                "failure_code": attempt.failure_code,
                "canonical_json": canonical_json(attempt.to_dict()),
                "created_at": attempt.occurred_at.replace(tzinfo=None),
            })
            if len(delivery_rows) == 1000:
                started = time.perf_counter()
                with engine.begin() as connection:
                    connection.execute(
                        sa.insert(MonitoringAlertDeliveryAttemptRow), delivery_rows)
                bulk_seconds.append(time.perf_counter() - started)
                delivery_rows.clear()
    if delivery_rows:
        started = time.perf_counter()
        with engine.begin() as connection:
            connection.execute(
                sa.insert(MonitoringAlertDeliveryAttemptRow), delivery_rows)
        bulk_seconds.append(time.perf_counter() - started)

    with engine.connect() as connection:
        validate_persisted_monitoring(connection)
        table_counts = {
            name: int(connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name])) or 0)
            for name in MONITORING_TABLES
        }
        owner_counts = {
            row[0]: int(row[1]) for row in connection.execute(sa.text(
                "SELECT owner_id,count(*) FROM monitoring_alert_delivery_attempts "
                "GROUP BY owner_id ORDER BY owner_id"))
        }
        assignment_counts = {
            row[0]: int(row[1]) for row in connection.execute(sa.text(
                "SELECT owner_id,count(*) FROM monitoring_assignments "
                "WHERE lifecycle_state='ACTIVE' GROUP BY owner_id ORDER BY owner_id"))
        }
        database_bytes = sum(int(connection.scalar(sa.text(
            "SELECT pg_total_relation_size(CAST(:name AS regclass))"
        ), {"name": name}) or 0) for name in MONITORING_TABLES)
        index_bytes = sum(int(connection.scalar(sa.text(
            "SELECT pg_indexes_size(CAST(:name AS regclass))"
        ), {"name": name}) or 0) for name in MONITORING_TABLES)

    immutable_count = sum(table_counts[name] for name in (
        "monitoring_state_snapshots", "monitoring_signal_events",
        "monitoring_signal_alerts", "monitoring_alert_delivery_attempts",
        "monitoring_alert_attention_events", "monitoring_signal_reviews",
    ))
    metrics = {
        "dialect": "postgresql16",
        "owners": len(owner_counts),
        "active_assignments": sum(assignment_counts.values()),
        "immutable_facts": immutable_count,
        "hot_owner_delivery_facts": max(owner_counts.values()),
        "cold_owner_delivery_facts": min(owner_counts.values()),
        "database_bytes": database_bytes,
        "index_bytes": index_bytes,
        "append_projection_seconds": _timing_summary(append_projection_seconds),
        "assignment_cas_seconds": _timing_summary(assignment_cas_seconds),
        "rebuild_seconds": _timing_summary(rebuild_seconds),
        "lock_wait_seconds": _timing_summary(lock_wait_seconds),
        "bulk_insert_seconds": _timing_summary(bulk_seconds),
        "pool": {
            "size": 2, "max_overflow": 0, "pool_timeout": 1,
            "checked_out_after": engine.pool.checkedout(),
        },
        "table_counts": table_counts,
    }
    print(json.dumps(metrics, sort_keys=True))
    assert len(owner_counts) == 15
    assert assignment_counts == {owner: 20 for owner in owners}
    assert immutable_count == 100_000
    assert max(owner_counts.values()) > min(owner_counts.values())
    for category in (
        append_projection_seconds, assignment_cas_seconds,
        rebuild_seconds, lock_wait_seconds, bulk_seconds,
    ):
        assert max(category) < 1.0
    assert engine.pool.checkedout() == 0


def test_postgresql16_fresh_0043_upgrade_interruption_concurrency_and_restore(
    pg_sandbox, monkeypatch, tmp_path,
):
    from sqlalchemy.orm import Session
    from app.db.copy_contract import stream_table_summary, validate_content_addresses
    from app.monitoring.repository import (
        MonitoringConflict, MonitoringRepository, SignalReview,
        validate_monitoring_schema, validate_persisted_monitoring,
    )
    from app.db.models import Membership, Organization, Project, User
    from tests.test_v0_monitoring_persistence import _facts, _spec, T0
    from app.operations.postgresql_backup import resolve_postgresql16_tools

    fresh = pg_sandbox.engine("monitoring_fresh")
    upgraded = pg_sandbox.engine(
        "monitoring_upgrade", pool_size=2, max_overflow=0, pool_timeout=1,
    )
    restored = pg_sandbox.engine("monitoring_restore")
    with fresh.connect() as connection:
        assert connection.exec_driver_sql("SHOW server_version").scalar_one().startswith("16.")
    assert migrate.init_schema(
        fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    ) == "0048"
    with fresh.connect() as connection:
        validate_monitoring_schema(connection)

    _prior_postgresql_0043(upgraded, monkeypatch)
    with upgraded.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO enrollment_invites "
            "(invite_digest,email_normalized,purpose,created_at,expires_at,consumed_at) "
            "VALUES ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',"
            "'unknown','enrollment','2026-08-29 09:00:00','2026-08-29 10:00:00',NULL)")

    def interrupt(_conn, _cursor, statement, _parameters, _context, _many):
        if "CREATE TABLE monitoring_signal_events" in statement:
            raise RuntimeError("synthetic PG16 0044 interruption")

    sa.event.listen(upgraded, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="synthetic PG16"):
            _upgrade(upgraded)
    finally:
        sa.event.remove(upgraded, "before_cursor_execute", interrupt)
    assert migrate.schema_version(upgraded) == "0043"
    assert set(MONITORING_TABLES).isdisjoint(sa.inspect(upgraded).get_table_names())
    _upgrade(upgraded)
    _upgrade(upgraded)
    assert migrate.schema_version(upgraded) == "0044"
    with upgraded.connect() as connection:
        validate_monitoring_schema(connection)
        assert connection.exec_driver_sql(
            "SELECT email_normalized,consumed_at FROM enrollment_invites "
            "WHERE invite_digest='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
        ).one() == ("unknown", None)
    for table in MONITORING_TABLES:
        assert _contract(upgraded, table) == _contract(fresh, table)

    migration_race = pg_sandbox.engine("monitoring_migration_race")
    _prior_postgresql_0043(migration_race, monkeypatch)
    migration_code = """import sys
import sqlalchemy as sa
from alembic import command
from app.db import migrate
engine=sa.create_engine(sys.argv[1],future=True)
try:
 with engine.begin() as connection:
  command.upgrade(migrate.alembic_config(connection),'0044')
 print(migrate.schema_version(engine))
except RuntimeError as error:
 if 'partial/unproven' not in str(error): raise
 print('clean-refusal')
finally:
 engine.dispose()
"""
    process_environment = dict(
        os.environ, PT_DISABLE_DOTENV="1", PT_PROVIDER="mock",
        PT_EXECUTION="paper", PT_LIVE_ACK="",
    )
    migration_processes = [subprocess.Popen(
        [sys.executable, "-c", migration_code, str(migration_race.url)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=process_environment,
    ) for _ in range(2)]
    migration_outputs = [process.communicate(timeout=60) for process in migration_processes]
    assert all(process.returncode == 0 for process in migration_processes), migration_outputs
    migration_results = [stdout.strip() for stdout, _stderr in migration_outputs]
    assert migration_results.count("0044") in {1, 2}
    assert set(migration_results) <= {"0044", "clean-refusal"}
    assert migrate.schema_version(migration_race) == "0044"
    with migration_race.connect() as connection:
        validate_monitoring_schema(connection)

    with Session(upgraded) as session, session.begin():
        session.add(Organization(organization_id="tenant.alpha", name="tenant.alpha"))
        session.add(User(user_id="user.alpha", email_normalized="alpha@example.test",
                         display_name="Alpha"))
        session.flush()
        session.add(Membership(organization_id="tenant.alpha", user_id="user.alpha",
                               role="owner", status="active"))
        session.add(Project(project_id="project.alpha", owner_id="tenant.alpha",
                            name="project.alpha", description="", status="active"))
    with Session(upgraded, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)

    barrier = threading.Barrier(2)

    import datetime as _dt

    def revise(index: int):
        with Session(upgraded, expire_on_commit=False) as session:
            try:
                with session.begin():
                    repository = MonitoringRepository(session, owner_id="tenant.alpha")
                    barrier.wait()
                    return repository.update_assignment(
                        "assignment.alpha", expected_revision=1,
                        lifecycle_state="PAUSED", now=T0 + _dt.timedelta(seconds=index + 1),
                    ).optimistic_revision
            except MonitoringConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        revisions = list(pool.map(revise, (0, 1)))
    assert revisions.count("conflict") == 1 and revisions.count(2) == 1

    before, after, event, alert = _facts()
    with Session(upgraded, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.update_assignment(
            "assignment.alpha", expected_revision=2,
            lifecycle_state="ACTIVE", now=T0 + _dt.timedelta(seconds=3))
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=event.event_at)

    event_barrier = threading.Barrier(2)

    def append_event(_index: int):
        with Session(upgraded, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id="tenant.alpha")
            event_barrier.wait()
            return repository.append_event(event, created_at=event.knowledge_cutoff_at).address

    with ThreadPoolExecutor(max_workers=2) as pool:
        addresses = list(pool.map(append_event, (0, 1)))
    assert addresses == [event.address, event.address]

    with Session(upgraded, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.append_alert(alert, created_at=event.knowledge_cutoff_at)
    review = SignalReview(
        owner_id="tenant.alpha", assignment_id=event.assignment_id,
        monitoring_event_address=event.address, reviewer_user_id="user.alpha",
        disposition="CONFIRMED", reason_code="MATCHED_EXPECTATION", note="",
        created_at=T0 + _dt.timedelta(minutes=5),
    )
    review_barrier = threading.Barrier(2)

    def append_review(_index: int):
        with Session(upgraded, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id="tenant.alpha")
            review_barrier.wait()
            return repository.append_review(review).address

    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(pool.map(append_review, (0, 1)))
    assert reviews == [review.address, review.address]
    with upgraded.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            Base.metadata.tables["monitoring_signal_events"])) == 1
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            Base.metadata.tables["monitoring_signal_reviews"])) == 1
        validate_content_addresses(connection, Base.metadata)
        summary = {
            name: stream_table_summary(connection, Base.metadata.tables[name])
            for name in MONITORING_TABLES
        }

    explain_statements = {
        "assignments": (
            "SELECT assignment_id FROM monitoring_assignments "
            "WHERE owner_id='tenant.alpha' AND lifecycle_state='ACTIVE' "
            "ORDER BY assignment_id LIMIT 101"
        ),
        "events": (
            "SELECT content_address FROM monitoring_signal_events "
            "WHERE owner_id='tenant.alpha' AND assignment_id='assignment.alpha' "
            "ORDER BY event_at,content_address LIMIT 101"
        ),
        "inbox": (
            "SELECT alert_address FROM monitoring_alert_attention_state "
            "WHERE owner_id='tenant.alpha' AND is_unread=true "
            "ORDER BY alert_event_at,alert_address LIMIT 101"
        ),
        "rebuild": (
            "SELECT snapshot_address FROM monitoring_state_snapshots "
            "WHERE owner_id='tenant.alpha' AND assignment_id='assignment.alpha' "
            f"AND canonical_instrument_address='{event.canonical_instrument_address}' "
            "ORDER BY snapshot_sequence"
        ),
    }
    query_plans = {}
    with upgraded.begin() as connection:
        connection.exec_driver_sql("SET LOCAL enable_seqscan=off")
        for name, statement in explain_statements.items():
            plan = connection.exec_driver_sql(
                f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {statement}").scalar_one()
            rendered = json.dumps(plan, sort_keys=True)
            assert "Index" in rendered and "Seq Scan" not in rendered
            query_plans[name] = rendered

    release = threading.Event()
    two_connections = threading.Event()
    state_lock = threading.Lock()
    acquired = 0

    def hold_pool_connection(_index: int):
        nonlocal acquired
        try:
            with upgraded.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
                with state_lock:
                    acquired += 1
                    if acquired == 2:
                        two_connections.set()
                release.wait(3)
                return "acquired"
        except sa.exc.TimeoutError:
            return "backpressure"

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(hold_pool_connection, index) for index in range(4)]
        assert two_connections.wait(2)
        time.sleep(1.2)
        release.set()
        pool_results = [future.result(timeout=5) for future in futures]
    assert pool_results.count("acquired") == 2
    assert pool_results.count("backpressure") == 2
    assert upgraded.pool.checkedout() == 0
    print(json.dumps({
        "query_plan_index_paths": sorted(query_plans),
        "pool": {"size": 2, "max_overflow": 0, "workers": 4,
                 "acquired": 2, "backpressure": 2, "checked_out_after": 0},
    }, sort_keys=True))

    role_suffix = uuid.uuid4().hex[:12]
    monitor_role = f"monitor_local_{role_suffix}"
    operator_role = f"operator_local_{role_suffix}"
    with upgraded.begin() as connection:
        connection.exec_driver_sql(f'CREATE ROLE "{monitor_role}" NOLOGIN')
        connection.exec_driver_sql(f'CREATE ROLE "{operator_role}" NOLOGIN')
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{monitor_role}"')
        connection.exec_driver_sql(
            f'GRANT SELECT ON monitoring_assignments,monitoring_state_snapshots,'
            f'monitoring_signal_events,monitoring_signal_alerts TO "{monitor_role}"')
        connection.exec_driver_sql(
            f'GRANT INSERT ON monitoring_state_snapshots,monitoring_signal_events,'
            f'monitoring_signal_alerts TO "{monitor_role}"')
        connection.exec_driver_sql(
            f'GRANT SELECT,UPDATE ON monitoring_latest_state TO "{monitor_role}"')
    try:
        with upgraded.connect() as connection:
            privileges = connection.execute(sa.text(
                "SELECT "
                "has_table_privilege(:role,'monitoring_assignments','SELECT'),"
                "has_table_privilege(:role,'monitoring_assignments','UPDATE'),"
                "has_table_privilege(:role,'monitoring_signal_events','INSERT'),"
                "has_table_privilege(:role,'monitoring_signal_reviews','INSERT'),"
                "has_table_privilege(:role,'broker_accounts','SELECT')"
            ), {"role": monitor_role}).one()
            operator_privilege = connection.scalar(sa.text(
                "SELECT has_table_privilege(:role,'monitoring_signal_events','SELECT')"
            ), {"role": operator_role})
        assert privileges == (True, False, True, False, False)
        assert operator_privilege is False
        with pytest.raises(sa.exc.DBAPIError, match="permission denied"):
            with upgraded.begin() as connection:
                connection.exec_driver_sql(f'SET LOCAL ROLE "{monitor_role}"')
                connection.exec_driver_sql("SELECT count(*) FROM broker_accounts").scalar_one()
        with pytest.raises(sa.exc.DBAPIError, match="permission denied"):
            with upgraded.begin() as connection:
                connection.exec_driver_sql(f'SET LOCAL ROLE "{operator_role}"')
                connection.exec_driver_sql(
                    "SELECT count(*) FROM monitoring_signal_events").scalar_one()
    finally:
        with upgraded.begin() as connection:
            connection.exec_driver_sql(f'DROP OWNED BY "{monitor_role}"')
            connection.exec_driver_sql(f'DROP OWNED BY "{operator_role}"')
            connection.exec_driver_sql(f'DROP ROLE "{monitor_role}"')
            connection.exec_driver_sql(f'DROP ROLE "{operator_role}"')

    pg_dump, pg_restore = resolve_postgresql16_tools()
    artifact = tmp_path / "monitoring.dump"
    source_url = str(sa.engine.make_url(
        pg_sandbox.url("monitoring_upgrade")).set(drivername="postgresql"))
    target_url = str(sa.engine.make_url(
        pg_sandbox.url("monitoring_restore")).set(drivername="postgresql"))
    subprocess.run([
        str(pg_dump), "--format=custom", "--no-owner", "--no-acl",
        f"--file={artifact}", source_url,
    ], check=True, capture_output=True, text=True)
    subprocess.run([
        str(pg_restore), "--no-owner", "--no-acl", "--exit-on-error",
        f"--dbname={target_url}", str(artifact),
    ], check=True, capture_output=True, text=True)
    assert migrate.schema_version(restored) == "0044"
    with restored.connect() as connection:
        from app.monitoring.repository import (
            _actual_relational_manifest, _check_sql_matches,
            _expected_relational_manifest,
        )
        expected_relational = _expected_relational_manifest(connection)
        actual_relational = _actual_relational_manifest(connection)
        restore_check_mismatches = []
        for table_name in MONITORING_TABLES:
            table = Base.metadata.tables[table_name]
            for expected_check, actual_check in zip(
                expected_relational[table_name]["checks"],
                actual_relational[table_name]["checks"], strict=True,
            ):
                if (
                    expected_check[0] != actual_check[0]
                    or not _check_sql_matches(
                        table, expected_check[0], connection.dialect.name,
                        expected_check[1], actual_check[1])
                ):
                    restore_check_mismatches.append({
                        "table": table_name,
                        "name": expected_check[0],
                        "expected": expected_check[1],
                        "actual": actual_check[1],
                    })
        assert not restore_check_mismatches, json.dumps(
            restore_check_mismatches, indent=2, sort_keys=True)
        validate_persisted_monitoring(connection)
        assert {
            name: stream_table_summary(connection, Base.metadata.tables[name])
            for name in MONITORING_TABLES
        } == summary
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        with restored.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE monitoring_signal_events SET canonical_json='{}'")
    with pytest.raises(sa.exc.DBAPIError, match="identity is immutable"):
        with restored.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE monitoring_assignments SET strategy_id='forged'")
    with Session(restored) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        assert repository.get_event(event.assignment_id, event.address) == event


def test_sqlite_to_postgresql16_copy_revalidates_monitoring_documents_and_projections(
    pg_sandbox, tmp_path,
):
    from sqlalchemy.orm import Session
    from app.db.copy_contract import CopyPlane, copy_planes, verify_planes
    from app.monitoring.repository import MonitoringRepository, validate_persisted_monitoring
    from tests.test_v0_monitoring_persistence import _engine, _facts, _spec, T0

    source = _engine(tmp_path, "monitoring-copy-source.db")
    before, after, event, alert = _facts()
    with Session(source, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=event.event_at)
        repository.append_event(event, created_at=event.knowledge_cutoff_at)
        repository.append_alert(alert, created_at=event.knowledge_cutoff_at)
    source_path = Path(source.url.database).resolve()
    source.dispose()
    destination_url = pg_sandbox.url("monitoring_copy")

    def initialize(engine):
        migrate.init_schema(
            engine, create_all=lambda: Base.metadata.create_all(engine),
            legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
            expected_tables=Base.metadata.tables,
        )

    def validate(engine):
        assert migrate.schema_version(engine) == "0048"
        migrate._validate_current_schema(engine, Base.metadata.tables)
        with engine.connect() as connection:
            validate_persisted_monitoring(connection)

    plane = CopyPlane(
        name="execution", source_path=source_path,
        destination_url=destination_url, metadata=Base.metadata,
        marker_table="alembic_version", source_head="0048",
        initialize_destination=initialize, validate_destination=validate,
        destination_head="0048",
    )
    report = copy_planes([plane], batch_size=2)
    verify_planes([plane], report)
    with Session(pg_sandbox.engine("monitoring_copy")) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        assert repository.get_event(event.assignment_id, event.address) == event
        assert repository.get_attention_state(
            alert.assignment_id, alert.address).last_sequence == 0


def _watchlist_monitoring_seed(engine):
    from app.db.models import StaticInstrumentScope
    from tests.test_v0_monitoring_persistence import _seed_two_owners
    _seed_two_owners(engine)
    with engine.begin() as connection:
        for owner, project in (("tenant.alpha", "project.alpha"), ("tenant.beta", "project.beta")):
            connection.execute(StaticInstrumentScope.__table__.insert().values(
                owner_id=owner, project_id=project, scope_id="watchlist.main", name="Main",
                revision=1, status="active"))


def _watchlist_monitoring_row(**changes):
    from datetime import datetime
    from app.ir.hashing import canonical_json, content_address
    row = dict(owner_id="tenant.alpha", project_id="project.alpha", scope_id="watchlist.main",
        member_key="INFY", revision=1, request_id=str(uuid.uuid4()), predecessor_address=None,
        created_by="user.alpha", created_at=datetime(2026, 9, 7), monitoring_intent="PAUSE", assignment_id=None)
    row.update(changes)
    payload = {key: value for key, value in row.items() if key != "created_at"}
    row["address"] = content_address(payload)
    row["canonical_json"] = canonical_json({**payload, "address": row["address"]})
    return row


def _watchlist_monitoring_assert_history(engine):
    from app.db.models import WatchlistMonitoringRevision
    table = WatchlistMonitoringRevision.__table__
    first = _watchlist_monitoring_row()
    second = _watchlist_monitoring_row(revision=2, predecessor_address=first["address"], monitoring_intent="MONITOR")
    with engine.begin() as connection:
        connection.execute(table.insert(), first)
        connection.execute(table.insert(), second)
    for statement in (table.update().values(monitoring_intent="PAUSE"), table.delete()):
        with pytest.raises(sa.exc.DBAPIError, match="immutable"), engine.begin() as connection:
            connection.execute(statement)
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.address).order_by(table.c.revision)).scalars().all() == [first["address"], second["address"]]
    return first


def test_watchlist_monitoring_0056_sqlite_managed_chain_and_model_parity(tmp_path):
    from app.db.models import WatchlistMonitoringRevision
    upgraded = _build_from_baseline_at_revision(tmp_path, "watchlist-0054.db", "0054")
    with upgraded.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()
    alias_rebuilds = []
    def observe(connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("ALTER TABLE _0055_authority_provider_aliases RENAME"):
            alias_rebuilds.append(connection.connection.driver_connection.execute("PRAGMA foreign_keys").fetchone()[0])
    sa.event.listen(upgraded, "before_cursor_execute", observe)
    assert migrate.upgrade_to_head(upgraded) == "0056"
    sa.event.remove(upgraded, "before_cursor_execute", observe)
    assert alias_rebuilds == [0]
    with upgraded.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    fresh = sa.create_engine(f"sqlite:///{tmp_path/'watchlist-fresh.db'}")
    Base.metadata.create_all(fresh)
    table = WatchlistMonitoringRevision.__table__.name
    assert _contract(upgraded, table) == _contract(fresh, table)
    assert plane_of(table) is Plane.USER
    _watchlist_monitoring_seed(upgraded)
    _watchlist_monitoring_assert_history(upgraded)
    assert migrate.init_schema(upgraded, create_all=lambda: pytest.fail("same-head create"),
        legacy_migrate=lambda: pytest.fail("same-head adoption")) == "0056"
    upgraded.dispose()
    fresh.dispose()


def test_watchlist_monitoring_0056_interruption_keeps_0055_for_retry(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "watchlist-interrupted.db", "0054")
    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        if "CREATE TABLE watchlist_monitoring_revisions" in statement:
            raise RuntimeError("synthetic 0056 interruption")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    with pytest.raises(RuntimeError, match="synthetic 0056 interruption"):
        migrate.upgrade_to_head(engine)
    sa.event.remove(engine, "before_cursor_execute", interrupt)
    assert migrate.schema_version(engine) == "0055"
    assert "watchlist_monitoring_revisions" not in sa.inspect(engine).get_table_names()
    assert "receipt_address" in {column["name"] for column in sa.inspect(engine).get_columns("authority_provider_aliases")}
    assert migrate.upgrade_to_head(engine) == "0056"
    engine.dispose()


@pytest.mark.parametrize("change", ["json_owner", "json_revision", "json_address", "json_intent", "size", "first_predecessor", "later_no_predecessor", "foreign_member", "duplicate_request", "creator", "assignment"])
def test_watchlist_monitoring_0056_sqlite_constraints(tmp_path, change):
    from app.db.models import WatchlistMonitoringRevision
    from tests.test_v0_monitoring_persistence import _engine
    engine = _engine(tmp_path, "watchlist-constraints-" + change + ".db")
    # _engine already seeds owners; the helper is idempotent for those identities.
    _watchlist_monitoring_seed(engine)
    table = WatchlistMonitoringRevision.__table__
    first = _watchlist_monitoring_row()
    with engine.begin() as connection:
        connection.execute(table.insert(), first)
    candidate = _watchlist_monitoring_row(member_key="OTHER")
    if change.startswith("json_"):
        field = {"json_owner": "owner_id", "json_revision": "revision", "json_address": "address", "json_intent": "monitoring_intent"}[change]
        payload = json.loads(candidate["canonical_json"])
        payload[field] = 9 if field == "revision" else "ALTERED"
        candidate["canonical_json"] = json.dumps(payload)
    elif change == "size":
        payload = json.loads(candidate["canonical_json"])
        payload["padding"] = "🌱" * 5000
        candidate["canonical_json"] = json.dumps(payload, ensure_ascii=False)
    else:
        updates = {"first_predecessor": {"predecessor_address": first["address"]},
            "later_no_predecessor": {"revision": 2},
            "foreign_member": {"revision": 2, "predecessor_address": first["address"]},
            "duplicate_request": {"request_id": first["request_id"]},
            "creator": {"created_by": "missing-user"}, "assignment": {"assignment_id": "missing-assignment"}}
        candidate = _watchlist_monitoring_row(member_key="OTHER", **updates[change])
    with pytest.raises(sa.exc.DBAPIError), engine.begin() as connection:
        connection.execute(table.insert(), candidate)
    engine.dispose()


def test_watchlist_monitoring_0056_postgresql_upgrade_and_immutable_parity(pg_sandbox):
    from app.db.models import WatchlistMonitoringRevision
    upgraded = pg_sandbox.engine("watchlist_0056_upgrade")
    fresh = pg_sandbox.engine("watchlist_0056_fresh")
    table = WatchlistMonitoringRevision.__table__.name
    with upgraded.begin() as connection:
        Base.metadata.create_all(connection, tables=[item for item in Base.metadata.sorted_tables if item.name != table])
        command.stamp(migrate.alembic_config(connection), "0055")
    _watchlist_monitoring_seed(upgraded)
    assert migrate.init_schema(upgraded, create_all=lambda: pytest.fail("managed create"),
        legacy_migrate=lambda: pytest.fail("managed adoption"), expected_tables=Base.metadata.tables) == "0056"
    Base.metadata.create_all(fresh)
    assert _contract(upgraded, table) == _contract(fresh, table)
    _watchlist_monitoring_assert_history(upgraded)
    with upgraded.begin() as connection:
        with pytest.raises(RuntimeError, match="restore or forward repair"):
            command.downgrade(migrate.alembic_config(connection), "0055")
    assert migrate.schema_version(upgraded) == "0056"


def test_watchlist_monitoring_0056_refuses_partial_table_without_overwriting(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "watchlist-partial.db", "0054")
    assert migrate._upgrade_response_aliases(engine) == "0055"
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE watchlist_monitoring_revisions (retained_note TEXT)")
        connection.exec_driver_sql("INSERT INTO watchlist_monitoring_revisions VALUES ('retain this partial state')")
    with pytest.raises(RuntimeError, match="partial pre-existing"):
        migrate.upgrade_to_head(engine)
    assert migrate.schema_version(engine) == "0055"
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT retained_note FROM watchlist_monitoring_revisions").scalar() == "retain this partial state"
    engine.dispose()
