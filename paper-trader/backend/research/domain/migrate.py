"""Restart-safe migrations owned solely by the physically separate research DB."""
from __future__ import annotations

import importlib
import hashlib
import json
import pkgutil
import re
from collections.abc import Callable

from sqlalchemy import Boolean, CheckConstraint, Engine, MetaData, UniqueConstraint, inspect, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.schema import CreateIndex, CreateTable, Table

from research.domain.base import LEGACY_OWNER_ID, ResearchBase

VERSION_TABLE = "research_schema_version"
_INTERNAL_MIGRATION_TABLES = frozenset({
    "_research_0002_operation_rebuild_proof", "sqlite_sequence",
})
HEAD_VERSION = "0012"
# Marker shape is a DECLARED DIALECT CONTRACT (foundation audit A-05):
# SQLite stores (version, schema_cookie) because the cookie powers the
# restart fast-path trust check (_schema_cookie vs the stamped value);
# PostgreSQL stores (version) only, because that plane adopts exclusively
# empty databases and has no rebuild history for a cookie to guard.  Neither
# plane may silently grow the other's column; the shape is pinned by
# research_tests/test_foundation_a01_migration_upgrade.py.
_VERSION_COLUMNS = ("version", "schema_cookie")
_LEGACY_MARKER_SHAPE = (("version", "VARCHAR(16)", True, None, 1),)


def head_version() -> str:
    """Return the newest on-disk research migration version.

    The migration runner owns this discovery so evidence commands do not copy a
    head literal from a review report.
    """
    package = importlib.import_module("research.domain.migrations")
    versions = [
        item.name.split("_", 1)[0]
        for item in pkgutil.iter_modules(package.__path__)
        if re.fullmatch(r"\d{4}_.+", item.name)
    ]
    if not versions:
        raise ResearchMigrationError("research migration directory is empty")
    return max(versions)
_CURRENT_MARKER_SHAPE = (
    ("version", "VARCHAR(16)", True, None, 1),
    ("schema_cookie", "INTEGER", True, None, 0),
)
POSTGRESQL_IMMUTABLE_TABLES = (
    "research_experiment_spec",
    "research_optimization_trial",
    "research_strategy_admission",
    "research_dataset_manifests",
    "research_ir_v2_graph_versions",
    "research_dataset_segments_v2",
    "research_dataset_manifests_v2",
    "research_dataset_manifest_segments_v2",
)


class ResearchMigrationError(RuntimeError):
    """A migration refused to make a lossy or structurally unsafe change."""


class _JsonShapeAt0009(ColumnElement):
    """Exact accepted 0009 helper, retained only for forward-upgrade validation."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_JsonShapeAt0009, "sqlite")
def _compile_json_shape_at_0009_sqlite(element, _compiler, **_kw):
    return f"json_valid({element.column_name})"


@compiles(_JsonShapeAt0009, "postgresql")
def _compile_json_shape_at_0009_postgresql(element, _compiler, **_kw):
    return f"jsonb_typeof({element.column_name}::jsonb) = 'object'"


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_names(connection) -> set[str]:
    return {
        row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    } - _INTERNAL_MIGRATION_TABLES


def _schema_cookie(connection) -> int:
    return int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())


def _normalise_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.replace("IF NOT EXISTS ", "").replace('"', "").strip()).upper()


def _check_names(table: Table) -> set[str]:
    return {
        constraint.name for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }


def _check_contracts(table: Table, dialect) -> dict[str, str]:
    return {
        constraint.name: _normalise_sql(str(constraint.sqltext.compile(dialect=dialect)))
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }


def _actual_check_contracts(connection, table: Table) -> dict[str, str]:
    """Extract named SQLite CHECK expressions without trusting their names alone."""
    sql = _normalise_sql(connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table.name,)
    ).scalar_one())
    actual = {}
    for name in _check_names(table):
        marker = f"CONSTRAINT {name.upper()} CHECK ("
        start = sql.find(marker)
        if start < 0:
            continue
        index = start + len(marker)
        depth = 1
        end = index
        while end < len(sql) and depth:
            if sql[end] == "(":
                depth += 1
            elif sql[end] == ")":
                depth -= 1
            end += 1
        if depth == 0:
            actual[name] = sql[index:end - 1].strip()
    return actual


def _marker_shape(connection) -> tuple[tuple[str, str, bool, object, int], ...]:
    return tuple(
        (row[1], row[2].upper(), bool(row[3]), row[4], row[5])
        for row in connection.exec_driver_sql(f"PRAGMA table_info({_quoted(VERSION_TABLE)})")
    )


def _create_current_marker(connection) -> None:
    connection.exec_driver_sql(
        f"CREATE TABLE {_quoted(VERSION_TABLE)} "
        "(version VARCHAR(16) NOT NULL PRIMARY KEY, schema_cookie INTEGER NOT NULL)"
    )


def _temporary_name(table: Table) -> str:
    return f"{table.name}__owner_tmp"


def _has_owner_column(connection, name: str) -> bool:
    return any(
        row[1] == "owner_id"
        for row in connection.exec_driver_sql(f"PRAGMA table_info({_quoted(name)})")
    )


def _create_table_at(connection, table: Table, name: str) -> None:
    """Create ``table`` at a deterministic replacement name.

    Foreign keys deliberately still name final tables.  Foreign-key enforcement is
    disabled only for the rebuild, then restored before validation.
    """
    ddl = str(CreateTable(table).compile(dialect=connection.dialect))
    source = _quoted(table.name)
    if source not in ddl:
        source = table.name
    connection.exec_driver_sql(ddl.replace(source, _quoted(name), 1))


def _copy_legacy_rows(connection, table: Table, source: str, target: str) -> None:
    source_columns = {
        row[1] for row in connection.exec_driver_sql(
            f"PRAGMA table_info({_quoted(source)})"
        )
    }
    target_columns = [column.name for column in table.columns]
    if any(column not in source_columns and column != "owner_id" for column in target_columns):
        missing = sorted(
            column for column in target_columns
            if column not in source_columns and column != "owner_id"
        )
        raise ResearchMigrationError(
            f"{source} cannot be rebuilt without dropping columns: {missing}"
        )
    select_columns = [
        (_quoted("owner_id") if "owner_id" in source_columns else "?")
        if column == "owner_id" else _quoted(column)
        for column in target_columns
    ]
    columns_sql = ", ".join(_quoted(column) for column in target_columns)
    select_sql = ", ".join(select_columns)
    connection.exec_driver_sql(
        f"INSERT INTO {_quoted(target)} ({columns_sql}) "
        f"SELECT {select_sql} FROM {_quoted(source)}",
        (LEGACY_OWNER_ID,) if "owner_id" not in source_columns else (),
    )


def _validate_copied_payload(connection, table: Table, source: str, target: str) -> None:
    """Prove the replacement contains exactly the source payload before DROP.

    The model tables have primary keys, so SQLite's set operators cannot hide a
    duplicate during this comparison; the preceding count check covers that
    invariant too.  Keeping this in SQL avoids materialising large trial rows.
    """
    source_columns = {
        row[1] for row in connection.exec_driver_sql(
            f"PRAGMA table_info({_quoted(source)})"
        )
    }
    target_columns = [column.name for column in table.columns]
    source_select = ", ".join(
        _quoted("owner_id") if name == "owner_id" and "owner_id" in source_columns
        else "?" if name == "owner_id" else _quoted(name)
        for name in target_columns
    )
    target_select = ", ".join(_quoted(name) for name in target_columns)
    source_params = (LEGACY_OWNER_ID,) if "owner_id" not in source_columns else ()
    forward = connection.exec_driver_sql(
        f"SELECT {source_select} FROM {_quoted(source)} EXCEPT "
        f"SELECT {target_select} FROM {_quoted(target)}",
        source_params,
    ).first()
    reverse = connection.exec_driver_sql(
        f"SELECT {target_select} FROM {_quoted(target)} EXCEPT "
        f"SELECT {source_select} FROM {_quoted(source)}",
        source_params,
    ).first()
    if forward is not None or reverse is not None:
        raise ResearchMigrationError(f"payload mismatch rebuilding {source}")


def _rebuild_table(connection, table: Table, *, notify: bool = True) -> None:
    source = table.name
    target = _temporary_name(table)
    names = _table_names(connection)
    if source not in names:
        if target in names and _has_owner_column(connection, target):
            connection.exec_driver_sql(
                f"ALTER TABLE {_quoted(target)} RENAME TO {_quoted(source)}"
            )
            return
        raise ResearchMigrationError(f"missing source table {source}")
    if target in names:
        # Source exists, so it is the authoritative copy. A prior temp table is
        # stale regardless of whether the process died before or after copying.
        connection.exec_driver_sql(f"DROP TABLE {_quoted(target)}")
    expected_rows = connection.exec_driver_sql(
        f"SELECT COUNT(*) FROM {_quoted(source)}"
    ).scalar_one()
    _create_table_at(connection, table, target)
    _copy_legacy_rows(connection, table, source, target)
    actual_rows = connection.exec_driver_sql(
        f"SELECT COUNT(*) FROM {_quoted(target)}"
    ).scalar_one()
    if actual_rows != expected_rows:
        raise ResearchMigrationError(
            f"row-count mismatch rebuilding {source}: {expected_rows} != {actual_rows}"
        )
    _validate_copied_payload(connection, table, source, target)
    connection.exec_driver_sql(f"DROP TABLE {_quoted(source)}")
    connection.exec_driver_sql(
        f"ALTER TABLE {_quoted(target)} RENAME TO {_quoted(source)}"
    )
    if notify:
        _after_table_rebuilt(table.name)


def _after_table_rebuilt(_table_name: str) -> None:
    """Failure-injection seam for restart and PRAGMA-restoration tests."""


def _restore_table_contracts(connection, table: Table) -> None:
    """Restore every index and trigger owned by one rebuilt SQLite table."""
    for index in table.indexes:
        connection.exec_driver_sql(
            str(CreateIndex(index).compile(dialect=connection.dialect)))
    for sql in _expected_triggers(tables=(table,)).values():
        connection.exec_driver_sql(sql)


def _after_0010_boundary(_completed_contracts: int) -> None:
    """Failure-injection seam after a complete, validated 0010 boundary."""


def _root_tables() -> tuple[Table, ...]:
    """Synthetic current-metadata subset for retained module-unit fixtures."""
    return tuple(table for table in _pre_0005_tables()
                 if table.name not in {"research_operation", "research_operation_item",
                                       "research_operation_event"}
                 and not table.name.startswith("research_outbox_"))


def _operation_table() -> Table:
    return ResearchBase.metadata.tables["research_operation"]


def _operation_item_table() -> Table:
    return ResearchBase.metadata.tables["research_operation_item"]


def _operation_event_table() -> Table:
    return ResearchBase.metadata.tables["research_operation_event"]


def _tables_through_0002() -> tuple[Table, ...]:
    return tuple(table for table in _pre_0005_tables()
                 if table.name not in {"research_operation_item", "research_operation_event"}
                 and not table.name.startswith("research_outbox_"))


def _tables_through_0003() -> tuple[Table, ...]:
    return tuple(table for table in _pre_0005_tables()
                 if not table.name.startswith("research_outbox_"))


def _pre_0005_tables() -> tuple[Table, ...]:
    """Build a synthetic current-metadata subset labelled pre-0005.

    This helper is not a frozen historical catalog and grants no active-runner
    support. It remains only for direct lower-level migration module tests.
    """
    from research.domain import models  # noqa: F401 - ensure complete metadata registration

    metadata = MetaData()
    for table in _pre_0010_tables():
        if table.name not in {
            "research_strategy_admission", "research_dataset_manifests",
            "research_ir_v2_graph_versions", "research_dataset_segments_v2",
            "research_dataset_manifests_v2", "research_dataset_manifest_segments_v2",
        }:
            table.to_metadata(metadata)
    for name in ("research_experiment_run", "research_promotion_candidate"):
        table = metadata.tables[name]
        address_check = f"ck_{name}_admission_address"
        for constraint in tuple(table.constraints):
            if constraint.name == address_check:
                table.constraints.remove(constraint)
        table._columns.remove(table.c.admission_address)
    return tuple(metadata.sorted_tables)


def _pre_0006_tables() -> tuple[Table, ...]:
    """Exact 0005 schema: v1 receipt rows have no inferred v2 identity."""
    from research.domain import models  # noqa: F401 - ensure receipt metadata is registered
    metadata = MetaData()
    for table in _pre_0010_tables():
        if table.name not in {
            "research_dataset_manifests", "research_ir_v2_graph_versions",
            "research_dataset_segments_v2", "research_dataset_manifests_v2",
            "research_dataset_manifest_segments_v2",
        }:
            table.to_metadata(metadata)
    table = metadata.tables["research_strategy_admission"]
    table._columns.remove(table.c.format_version)
    table._columns.remove(table.c.content_address)
    return tuple(metadata.sorted_tables)


def _pre_0007_tables() -> tuple[Table, ...]:
    """Exact 0006 schema, before dataset provenance and v2 graph evidence."""
    from research.domain import models  # noqa: F401

    metadata = MetaData()
    for table in _pre_0010_tables():
        if table.name not in {
            "research_dataset_manifests", "research_ir_v2_graph_versions",
            "research_dataset_segments_v2", "research_dataset_manifests_v2",
            "research_dataset_manifest_segments_v2",
        }:
            table.to_metadata(metadata)
    return tuple(metadata.sorted_tables)


def _pre_0008_tables() -> tuple[Table, ...]:
    """Exact 0007 schema, before the additive v2 graph evidence table."""
    from research.domain import models  # noqa: F401

    metadata = MetaData()
    for table in _pre_0010_tables():
        if table.name not in {"research_ir_v2_graph_versions", "research_dataset_segments_v2",
                              "research_dataset_manifests_v2",
                              "research_dataset_manifest_segments_v2"}:
            table.to_metadata(metadata)
    return tuple(metadata.sorted_tables)


def _pre_0009_tables() -> tuple[Table, ...]:
    """Exact 0008 schema, before typed dataset authority."""
    from research.domain import models  # noqa: F401

    metadata = MetaData()
    for table in _pre_0010_tables():
        if table.name not in {"research_dataset_segments_v2", "research_dataset_manifests_v2",
                              "research_dataset_manifest_segments_v2"}:
            table.to_metadata(metadata)
    return tuple(metadata.sorted_tables)


def _json_shape_tables_at(new_contract_count: int) -> tuple[Table, ...]:
    """Build one synthetic current-metadata 0010-prefix module fixture.

    This does not establish historical catalog authority or supported replay.
    """
    from research.domain import models  # noqa: F401

    migration = importlib.import_module(
        "research.domain.migrations.0010_research_json_shape_parity")
    if not 0 <= new_contract_count <= len(migration.JSON_SHAPE_SITES):
        raise ValueError("invalid 0010 JSON-shape prefix")
    metadata = MetaData()
    for table in ResearchBase.metadata.sorted_tables:
        table.to_metadata(metadata)
    for index, (table_name, constraint_name, column_name, _shape) in enumerate(
            migration.JSON_SHAPE_SITES):
        if index < new_contract_count:
            continue
        table = metadata.tables[table_name]
        for constraint in tuple(table.constraints):
            if constraint.name == constraint_name:
                table.constraints.remove(constraint)
                break
        else:
            raise ResearchMigrationError(
                f"missing projected JSON constraint {constraint_name}"
            )
        table.append_constraint(CheckConstraint(
            _JsonShapeAt0009(column_name), name=constraint_name))
    return tuple(metadata.sorted_tables)


def _pre_0010_tables() -> tuple[Table, ...]:
    """Exact accepted 0009 research schema, before JSON-shape parity repair."""
    return _json_shape_tables_at(0)


def _upgrade_outbox(connection) -> None:
    from research.domain.models import RESEARCH_OUTBOX_MODELS

    migration = importlib.import_module(
        "research.domain.migrations.0004_transactional_outbox")
    migration.upgrade(connection, RESEARCH_OUTBOX_MODELS)


def _upgrade_strategy_admissions(connection) -> None:
    migration = importlib.import_module(
        "research.domain.migrations.0005_strategy_admissions")
    tables = {table.name: table for table in _pre_0010_tables()}
    migration.upgrade(
        connection,
        tables["research_strategy_admission"],
        (
            tables["research_experiment_run"],
            tables["research_promotion_candidate"],
        ),
    )
    if connection.dialect.name == "sqlite":
        # A-01 prevention invariant: a stage installs its COMPLETE target
        # contract before the marker advances.  The 0004-era database has no
        # admission triggers (the table is born here), so the staged path
        # installs them from the one canonical source — exactly what fresh
        # installs receive wholesale.
        existing = {row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger'").all()}
        for name, sql in _expected_triggers(
                tables=(tables["research_strategy_admission"],)).items():
            if name not in existing:
                connection.exec_driver_sql(sql)


def _upgrade_ir_v2_admissions(connection) -> None:
    migration = importlib.import_module("research.domain.migrations.0006_ir_v2_admissions")
    tables = {table.name: table for table in _pre_0010_tables()}
    migration.upgrade(connection, tables["research_strategy_admission"])


def _upgrade_dataset_provenance(connection) -> None:
    migration = importlib.import_module("research.domain.migrations.0007_phase4_dataset_provenance")
    tables = {table.name: table for table in _pre_0010_tables()}
    migration.upgrade(connection, tables["research_dataset_manifests"])


def _upgrade_ir_v2_graph_versions(connection) -> None:
    migration = importlib.import_module(
        "research.domain.migrations.0008_ir_v2_graph_versions")
    tables = {table.name: table for table in _pre_0010_tables()}
    migration.upgrade(connection, tables["research_ir_v2_graph_versions"])


def _upgrade_dataset_authority(connection) -> None:
    migration = importlib.import_module(
        "research.domain.migrations.0009_phase4_dataset_authority")
    tables = {table.name: table for table in _pre_0010_tables()}
    selected = (
        tables["research_dataset_segments_v2"],
        tables["research_dataset_manifests_v2"],
        tables["research_dataset_manifest_segments_v2"],
    )
    migration.upgrade(connection, selected)
    if connection.dialect.name == "sqlite":
        for sql in _expected_triggers(tables=selected).values():
            connection.exec_driver_sql(sql.replace("CREATE TRIGGER ",
                                                   "CREATE TRIGGER IF NOT EXISTS ", 1))
    else:
        for table in selected:
            function = f"{table.name}_refuse_mutation"
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {_quoted(function)}() RETURNS trigger AS $$ "
                f"BEGIN RAISE EXCEPTION '{table.name} is immutable' "
                "USING ERRCODE = '55000'; END; $$ LANGUAGE plpgsql"
            )
            connection.exec_driver_sql(
                f"CREATE TRIGGER {_quoted(function)} BEFORE UPDATE OR DELETE "
                f"ON {_quoted(table.name)} FOR EACH ROW EXECUTE FUNCTION {_quoted(function)}()"
            )


def _validate_0010_sqlite_state(connection, *, expected: int | None = None) -> int:
    """Return only an exact declared SQLite 0010 restart boundary."""
    allowed = (0, 1, 2, 3, 8)
    candidates = (expected,) if expected is not None else allowed
    if any(candidate not in allowed for candidate in candidates):
        raise ResearchMigrationError("undeclared SQLite 0010 restart boundary")
    expected_names = {table.name for table in ResearchBase.metadata.sorted_tables}
    actual_names = _table_names(connection) - {VERSION_TABLE}
    if actual_names != expected_names:
        raise ResearchMigrationError(
            f"research table-set drift: {sorted(actual_names)} != {sorted(expected_names)}"
        )
    matches = []
    for candidate in candidates:
        try:
            _validate_schema(
                connection, include_marker=False,
                tables=_json_shape_tables_at(candidate),
            )
        except ResearchMigrationError:
            continue
        matches.append(candidate)
    if len(matches) != 1:
        raise ResearchMigrationError(
            f"research SQLite 0010 state is not an exact declared prefix: {matches!r}"
        )
    return matches[0]


def _upgrade_json_shape_parity_sqlite(connection) -> None:
    migration = importlib.import_module(
        "research.domain.migrations.0010_research_json_shape_parity")
    migration.upgrade_sqlite(
        connection, ResearchBase.metadata.sorted_tables,
        validate_state=_validate_0010_sqlite_state,
        rebuild_table=_rebuild_table,
        restore_table_contracts=_restore_table_contracts,
        after_boundary=_after_0010_boundary,
    )


def _complete_0010_sqlite(connection, *, establish_0009: bool) -> None:
    """Create a durable 0009 handoff, then advance through restart boundaries."""
    if establish_0009:
        _validate_0010_sqlite_state(connection, expected=0)
        _stamp(connection, version="0009")
        connection.commit()
    foreign_keys = int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one())
    connection.commit()
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        _upgrade_json_shape_parity_sqlite(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.exec_driver_sql(f"PRAGMA foreign_keys={foreign_keys}")
    _validate_schema(connection, include_marker=False)
    _stamp(connection)
    connection.commit()
    _validate_schema(connection)


def _create_indexes_and_triggers(connection, *, tables=None) -> None:
    selected = tuple(tables or ResearchBase.metadata.sorted_tables)
    for table in selected:
        for index in table.indexes:
            connection.exec_driver_sql(str(CreateIndex(index).compile(dialect=connection.dialect)))
    for name in ("research_experiment_spec", "research_optimization_trial",
                 "research_strategy_admission", "research_ir_v2_graph_versions",
                 "research_dataset_segments_v2", "research_dataset_manifests_v2",
                 "research_dataset_manifest_segments_v2"):
        if name not in {table.name for table in selected}:
            continue
        for operation in ("UPDATE", "DELETE"):
            trigger = f"trg_{name}_no_{operation.lower()}"
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS {_quoted(trigger)} BEFORE {operation} "
                f"ON {_quoted(name)} BEGIN SELECT RAISE(ABORT, '{name} is immutable'); END"
            )


def _stamp(connection, *, version: str = HEAD_VERSION) -> None:
    if VERSION_TABLE not in _table_names(connection):
        _create_current_marker(connection)
    elif _marker_shape(connection) == _LEGACY_MARKER_SHAPE:
        # SQLite cannot add a NOT NULL column without a default to a populated
        # table. Rebuild only this marker, after the caller validated all user
        # tables, to keep the current marker contract exact.
        old = f"{VERSION_TABLE}__legacy_marker"
        connection.exec_driver_sql(f"ALTER TABLE {_quoted(VERSION_TABLE)} RENAME TO {_quoted(old)}")
        _create_current_marker(connection)
        connection.exec_driver_sql(f"DROP TABLE {_quoted(old)}")
    elif _marker_shape(connection) != _CURRENT_MARKER_SHAPE:
        raise ResearchMigrationError("research schema marker contract drift")
    connection.exec_driver_sql(f"DELETE FROM {_quoted(VERSION_TABLE)}")
    connection.exec_driver_sql(
        f"INSERT INTO {_quoted(VERSION_TABLE)} (version, schema_cookie) VALUES (?, ?)",
        (version, _schema_cookie(connection)),
    )


def _current_version(connection) -> tuple[str, int | None] | None:
    if VERSION_TABLE not in _table_names(connection):
        return None
    shape = _marker_shape(connection)
    if shape not in (_LEGACY_MARKER_SHAPE, _CURRENT_MARKER_SHAPE):
        raise ResearchMigrationError("research schema marker contract drift")
    rows = connection.exec_driver_sql(
        f"SELECT version{', schema_cookie' if shape == _CURRENT_MARKER_SHAPE else ''} "
        f"FROM {_quoted(VERSION_TABLE)}"
    ).all()
    if len(rows) != 1:
        raise ResearchMigrationError("research schema marker is not singular")
    return rows[0][0], (
        int(rows[0][1]) if shape == _CURRENT_MARKER_SHAPE else None
    )


def _expected_default(column, dialect) -> str | None:
    if column.server_default is None:
        return None
    return str(column.server_default.arg.compile(dialect=dialect))


def _expected_triggers(*, tables=None) -> dict[str, str]:
    present = ({table.name for table in tables}
               if tables is not None else {
                "research_experiment_spec", "research_optimization_trial",
                "research_strategy_admission",
                "research_dataset_manifests",
                "research_ir_v2_graph_versions",
                "research_dataset_segments_v2", "research_dataset_manifests_v2",
                "research_dataset_manifest_segments_v2",
               })
    immutable = {
        f"trg_{table}_no_{operation.lower()}": (
            f"CREATE TRIGGER trg_{table}_no_{operation.lower()} BEFORE {operation} "
            f"ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
        )
        for table in ("research_experiment_spec", "research_optimization_trial",
                      "research_strategy_admission", "research_dataset_manifests",
                      "research_ir_v2_graph_versions", "research_dataset_segments_v2",
                      "research_dataset_manifests_v2",
                      "research_dataset_manifest_segments_v2") if table in present
        for operation in ("UPDATE", "DELETE")
    }
    if "research_dataset_manifests" in present:
        immutable["research_dataset_manifests_refuse_secret_key"] = (
            "CREATE TRIGGER research_dataset_manifests_refuse_secret_key "
            "BEFORE INSERT ON research_dataset_manifests WHEN EXISTS ("
            "SELECT 1 FROM json_tree(NEW.manifest_json) WHERE key IS NOT NULL AND ("
            " lower(key) LIKE '%token%' OR lower(key) LIKE '%secret%' OR "
            "lower(key) LIKE '%password%' OR lower(key) LIKE '%api_key%' OR "
            "lower(key) LIKE '%credential%' OR lower(key) LIKE '%authorization%'"
            " )) BEGIN SELECT RAISE(ABORT, 'research_dataset_manifests contains credential-bearing key'); END"
        )
    return immutable


def _normalise_fk_options(*, ondelete=None, onupdate=None,
                          deferrable=None, initially=None) -> tuple:
    """Compare FK actions/options even when SQLite's inspector omits nulls."""
    def action(value):
        return value.upper() if isinstance(value, str) else value

    def initial(value):
        return value.upper() if isinstance(value, str) else value

    return (action(ondelete), action(onupdate), deferrable, initial(initially))


def _validate_schema(connection, *, include_marker: bool = True, tables=None) -> None:
    """Reject every visible schema-contract drift, not merely missing owners."""
    inspector = inspect(connection)
    expected = tuple(tables or ResearchBase.metadata.sorted_tables)
    expected_tables = {table.name for table in expected}
    actual_tables = _table_names(connection) - {VERSION_TABLE}
    if (actual_tables != expected_tables if tables is None else not expected_tables <= actual_tables):
        raise ResearchMigrationError(
            f"research table-set drift: {sorted(actual_tables)} != {sorted(expected_tables)}"
        )
    if include_marker:
        if _marker_shape(connection) != _CURRENT_MARKER_SHAPE:
            raise ResearchMigrationError("research schema marker contract drift")
    # Recovery tests intentionally rewind a version marker after a completed
    # newer migration. Accept only the exact known 0005 additive state while
    # validating a 0001–0004 preflight; arbitrary extra columns still refuse.
    #
    # This synthetic current-metadata projection supports retained lower-level
    # module tests only. It is not a historical catalog or active replay path.
    admission_table = ResearchBase.metadata.tables["research_strategy_admission"]
    frozen_admission_table = next(
        table for table in _pre_0010_tables()
        if table.name == admission_table.name)
    validation_tables = list(expected)
    actual_admission_columns = (
        {row[1] for row in connection.exec_driver_sql(
            f"PRAGMA table_info({_quoted(admission_table.name)})")}
        if admission_table.name in actual_tables else set()
    )
    if (tables is not None and admission_table.name in actual_tables
            and any(table.name == admission_table.name for table in expected)
            and not {"format_version", "content_address"} <= {
                column.name for column in next(
                    table for table in expected if table.name == admission_table.name
                ).columns
            }
            and {"format_version", "content_address"} <= actual_admission_columns):
        # Replace, do not append: the old projected table must not be checked
        # against an exact resumable post-DDL state.
        validation_tables = [
            frozen_admission_table if table.name == admission_table.name else table
            for table in validation_tables
        ]
    for table in validation_tables:
        contract_table = table
        actual_column_names = {
            row[1] for row in connection.exec_driver_sql(
                f"PRAGMA table_info({_quoted(table.name)})")
        }
        if (tables is not None
                and table.name in {"research_experiment_run", "research_promotion_candidate"}
                and "admission_address" not in {column.name for column in table.columns}
                and "admission_address" in actual_column_names):
            contract_table = ResearchBase.metadata.tables[table.name]
        pk_positions = {
            column.name: index + 1
            for index, column in enumerate(contract_table.primary_key.columns)
        }
        expected_columns = [
            (
                column.name,
                str(column.type.compile(dialect=connection.dialect)).upper(),
                not column.nullable,
                _expected_default(column, connection.dialect),
                pk_positions.get(column.name, 0),
            )
            for column in contract_table.columns
        ]
        actual_columns = [
            (row[1], row[2].upper(), bool(row[3]), row[4], row[5])
            for row in connection.exec_driver_sql(f"PRAGMA table_info({_quoted(table.name)})")
        ]
        if actual_columns != expected_columns:
            raise ResearchMigrationError(f"{table.name} column contract drift")
        actual_primary_key = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
        expected_primary_key = tuple(column.name for column in contract_table.primary_key.columns)
        if actual_primary_key != expected_primary_key:
            raise ResearchMigrationError(f"{table.name} primary-key drift")
        # SQLite's inspector intentionally omits CHECK constraints.  Validate
        # their normalized bodies before secondary metadata so a relaxed state
        # machine cannot hide behind missing recreated indexes.
        if (_actual_check_contracts(connection, contract_table)
                != _check_contracts(contract_table, connection.dialect)):
            raise ResearchMigrationError(f"{table.name} check-constraint drift")
        expected_uniques = {
            tuple(column.name for column in constraint.columns)
            for constraint in contract_table.constraints if isinstance(constraint, UniqueConstraint)
        }
        actual_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table.name)
        }
        if actual_uniques != expected_uniques:
            raise ResearchMigrationError(f"{table.name} unique-constraint drift")
        expected_indexes = {
            (tuple(index.columns.keys()), bool(index.unique)) for index in contract_table.indexes
        }
        actual_indexes = {
            (tuple(index["column_names"]), bool(index.get("unique")))
            for index in inspector.get_indexes(table.name)
        }
        if actual_indexes != expected_indexes:
            raise ResearchMigrationError(f"{table.name} index drift")
        expected_fks = {
            (
                tuple(fk.column_keys), fk.referred_table.name,
                tuple(element.column.name for element in fk.elements),
                _normalise_fk_options(
                    ondelete=fk.ondelete, onupdate=fk.onupdate,
                    deferrable=fk.deferrable, initially=fk.initially,
                ),
            )
            for fk in contract_table.foreign_key_constraints
        }
        actual_fks = {
            (
                tuple(fk["constrained_columns"]), fk["referred_table"],
                tuple(fk["referred_columns"]),
                _normalise_fk_options(
                    ondelete=fk.get("options", {}).get("ondelete"),
                    onupdate=fk.get("options", {}).get("onupdate"),
                    deferrable=fk.get("options", {}).get("deferrable"),
                    initially=fk.get("options", {}).get("initially"),
                ),
            )
            for fk in inspector.get_foreign_keys(table.name)
        }
        if actual_fks != expected_fks:
            raise ResearchMigrationError(f"{table.name} foreign-key drift")
    actual_triggers = dict(connection.exec_driver_sql(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
    ).all())
    expected_triggers = _expected_triggers(tables=validation_tables)
    if set(actual_triggers) != set(expected_triggers) or any(
        _normalise_sql(actual_triggers[name]) != _normalise_sql(sql)
        for name, sql in expected_triggers.items()
    ):
        raise ResearchMigrationError("research trigger contract drift")
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
    if violations:
        raise ResearchMigrationError(f"foreign-key validation failed: {violations!r}")


def _rebuild_unversioned(connection) -> None:
    tables = _root_tables()
    for table in tables:
        _rebuild_table(connection, table)
    _create_indexes_and_triggers(connection, tables=tables)
    _validate_schema(connection, include_marker=False, tables=tables)
    _stamp(connection, version="0001")


def _migration_schema_digest(connection, *, tables=None) -> str:
    """Digest schema dimensions consumed by the retained 0001 module fixture."""
    selected = tuple(tables or ResearchBase.metadata.sorted_tables)
    contract = {}
    for table in selected:
        contract[table.name] = {
            "columns": [
                (column.name, str(column.type.compile(dialect=connection.dialect)).upper(),
                 bool(column.nullable), _expected_default(column, connection.dialect),
                 bool(column.primary_key))
                for column in table.columns
            ],
            "primary_key": tuple(column.name for column in table.primary_key.columns),
            "uniques": sorted(
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
            ),
            "indexes": sorted(
                (tuple(index.columns.keys()), bool(index.unique)) for index in table.indexes
            ),
            "foreign_keys": sorted(
                (tuple(fk.column_keys), fk.referred_table.name,
                 tuple(element.column.name for element in fk.elements),
                 _normalise_fk_options(
                     ondelete=fk.ondelete, onupdate=fk.onupdate,
                     deferrable=fk.deferrable, initially=fk.initially,
                 ))
                for fk in table.foreign_key_constraints
            ),
            "checks": _check_contracts(table, connection.dialect),
        }
    contract["triggers"] = sorted(
        (name, _normalise_sql(sql)) for name, sql in _expected_triggers(tables=selected).items()
    )
    return hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _recover_interrupted_swaps(connection) -> None:
    """Resolve deterministic rebuild leftovers before reading the version marker."""
    names = _table_names(connection)
    for table in ResearchBase.metadata.sorted_tables:
        source = table.name
        target = _temporary_name(table)
        if source == "research_operation" and target in names:
            # 0002's deterministic temporary name is deliberately *not* proof
            # that it contains a valid operation table.  Its migration owns the
            # source-bound proof record and is the only code allowed to promote
            # or reject an interrupted operation rebuild.  Generic recovery
            # must never turn a forged temp table into durable scheduler state.
            migration = importlib.import_module(
                "research.domain.migrations.0002_owner_operations"
            )
            migration.upgrade(connection, table)
            names = _table_names(connection)
            continue
        if (source not in names and target in names
                and (_has_owner_column(connection, target)
                     or source.startswith("research_outbox_"))):
            connection.exec_driver_sql(
                f"ALTER TABLE {_quoted(target)} RENAME TO {_quoted(source)}"
            )
        elif source in names and target in names:
            connection.exec_driver_sql(f"DROP TABLE {_quoted(target)}")


def migrate_research_db(engine: Engine) -> None:
    """Run the finite clean/0010/0011/0012 direct migration contract."""
    direct = importlib.import_module(
        "research.domain.migrations.0012_v2_preparation_evidence"
    )
    try:
        with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                direct.upgrade_postgresql(connection)
            elif engine.dialect.name == "sqlite":
                direct.upgrade_sqlite(connection)
            else:
                raise ResearchMigrationError(
                    f"unsupported research database dialect {engine.dialect.name!r}"
                )
    except direct.previous.FoundationMigrationError as error:
        raise ResearchMigrationError(str(error)) from error

def _normalise_function_body(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _postgresql_trigger_contracts(connection) -> dict[str, tuple]:
    rows = connection.execute(text("""
        SELECT trigger.tgname, relation.relname, trigger.tgenabled,
               trigger.tgtype, procedure.proname, procedure.prosrc,
               pg_get_expr(trigger.tgqual, trigger.tgrelid)
        FROM pg_trigger AS trigger
        JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        JOIN pg_proc AS procedure ON procedure.oid = trigger.tgfoid
        JOIN pg_namespace AS procedure_namespace
          ON procedure_namespace.oid = procedure.pronamespace
        WHERE NOT trigger.tgisinternal
          AND namespace.nspname = current_schema()
          AND procedure_namespace.nspname = current_schema()
          AND relation.relname = ANY(:tables)
    """), {"tables": list(POSTGRESQL_IMMUTABLE_TABLES)}).all()
    return {
        row[0]: (
            row[1], row[2], int(row[3]), row[4],
            _normalise_function_body(row[5]), row[6],
        )
        for row in rows
    }


def _validate_postgresql_contract(connection, metadata) -> None:
    from app.db.plane_schema import validate_postgresql_plane

    validate_postgresql_plane(
        connection, metadata,
        marker_table=VERSION_TABLE, plane="research",
    )
    expected = {
        f"{table}_refuse_mutation": (
            table,
            "O",  # enabled for the origin/normal replication role
            27,   # ROW | BEFORE | DELETE | UPDATE
            f"{table}_refuse_mutation",
            _normalise_function_body(
                f"BEGIN RAISE EXCEPTION '{table} is immutable' "
                "USING ERRCODE = '55000'; END;"
                if table in {
                    "research_strategy_admission",
                    "research_ir_v2_graph_versions",
                    "research_dataset_segments_v2",
                    "research_dataset_manifests_v2",
                    "research_dataset_manifest_segments_v2",
                }
                else f"BEGIN RAISE EXCEPTION '{table} is immutable'; END;"
            ),
            None,  # no WHEN predicate may suppress the refusal trigger
        )
        for table in POSTGRESQL_IMMUTABLE_TABLES
    }
    actual = _postgresql_trigger_contracts(connection)
    if actual != expected:
        raise ResearchMigrationError(
            "research PostgreSQL immutable-trigger contract drift: "
            f"actual={actual!r} expected={expected!r}"
        )


def _validate_postgresql(connection) -> None:
    _validate_postgresql_contract(connection, ResearchBase.metadata)


def _validate_0010_postgresql_state(connection, *, expected: int | None = None) -> int:
    """Return only an exact ordered PostgreSQL 0010 constraint prefix."""
    allowed = tuple(range(3, 9))
    candidates = (expected,) if expected is not None else allowed
    if any(candidate not in allowed for candidate in candidates):
        raise ResearchMigrationError("undeclared PostgreSQL 0010 restart boundary")
    matches = []
    for candidate in candidates:
        metadata = MetaData()
        for table in _json_shape_tables_at(candidate):
            table.to_metadata(metadata)
        try:
            _validate_postgresql_contract(connection, metadata)
        except (ResearchMigrationError, RuntimeError):
            continue
        matches.append(candidate)
    if len(matches) != 1:
        raise ResearchMigrationError(
            f"research PostgreSQL 0010 state is not an exact declared prefix: {matches!r}"
        )
    return matches[0]


def _upgrade_json_shape_parity_postgresql(connection) -> None:
    migration = importlib.import_module(
        "research.domain.migrations.0010_research_json_shape_parity")
    migration.upgrade_postgresql(
        connection, ResearchBase.metadata.sorted_tables,
        validate_state=_validate_0010_postgresql_state,
        after_boundary=_after_0010_boundary,
    )


def _migrate_postgresql(engine: Engine) -> None:
    """Adopt only an empty target; never replay SQLite rebuild migrations."""
    with engine.begin() as connection:
        names = set(inspect(connection).get_table_names())
        if VERSION_TABLE not in names:
            if names:
                raise ResearchMigrationError(
                    "Refusing populated unmanaged PostgreSQL research database"
                )
            ResearchBase.metadata.create_all(connection)
            connection.execute(text(
                f'CREATE TABLE "{VERSION_TABLE}" '
                '(version VARCHAR(16) NOT NULL PRIMARY KEY)'
            ))
            connection.execute(text(
                f'INSERT INTO "{VERSION_TABLE}" (version) VALUES (:version)'
            ), {"version": HEAD_VERSION})
            _validate_postgresql(connection)
            return

        marker_columns = inspect(connection).get_columns(VERSION_TABLE)
        if (len(marker_columns) != 1 or marker_columns[0]["name"] != "version"):
            raise ResearchMigrationError("research PostgreSQL schema marker contract drift")
        rows = connection.execute(text(
            f'SELECT version FROM "{VERSION_TABLE}"'
        )).scalars().all()
        if rows and rows[0] != HEAD_VERSION:
            # Historical replay reproduces, in isolation: provenance- and
            # authority-era DDL carries CHECK constraints calling
            # phase4_json_has_secret_key, but that function is otherwise
            # installed only by the DatasetManifest before_create event hook,
            # which replay bypasses. Install the identical function first;
            # CREATE OR REPLACE keeps repeated replays idempotent.
            from research.domain.models import _PHASE4_SECRET_FUNCTION

            connection.exec_driver_sql(_PHASE4_SECRET_FUNCTION)
        if rows == ["0003"]:
            outbox_names = {
                table.name for table in ResearchBase.metadata.sorted_tables
                if table.name.startswith("research_outbox_")
            }
            if outbox_names & names:
                raise ResearchMigrationError("partial research outbox migration")
            _upgrade_outbox(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": "0004"})
            rows = ["0004"]
        if rows == ["0004"]:
            _upgrade_strategy_admissions(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": "0005"})
            rows = ["0005"]
        if rows == ["0005"]:
            _upgrade_ir_v2_admissions(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": "0006"})
            rows = ["0006"]
        if rows == ["0006"]:
            _upgrade_dataset_provenance(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": "0007"})
            rows = ["0007"]
        if rows == ["0007"]:
            _upgrade_ir_v2_graph_versions(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": "0008"})
            rows = ["0008"]
        if rows == ["0008"]:
            _upgrade_dataset_authority(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": "0009"})
            rows = ["0009"]
        if rows == ["0009"]:
            _upgrade_json_shape_parity_postgresql(connection)
            connection.execute(text(
                f'UPDATE "{VERSION_TABLE}" SET version = :version'
            ), {"version": HEAD_VERSION})
            rows = [HEAD_VERSION]
        if rows != [HEAD_VERSION]:
            raise ResearchMigrationError(
                f"unsupported research PostgreSQL schema version {rows!r}; expected head"
            )
        _validate_postgresql(connection)


def downgrade_research_db(_engine: Engine) -> None:
    """Explicitly refuse destructive downgrade until a lossless reverse is needed."""
    raise ResearchMigrationError(
        "research schema downgrade is unsupported and refuses destructive DDL. "
        "Back up the database, use a read-only diagnostic/export if needed, "
        "then restore or rebuild a clean research database."
    )
