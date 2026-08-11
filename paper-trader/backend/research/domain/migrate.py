"""Restart-safe migrations owned solely by the physically separate research DB."""
from __future__ import annotations

import importlib
import re
from collections.abc import Callable

from sqlalchemy import Engine, UniqueConstraint, inspect
from sqlalchemy.schema import CreateIndex, CreateTable, Table

from research.domain.base import LEGACY_OWNER_ID, ResearchBase

VERSION_TABLE = "research_schema_version"
HEAD_VERSION = "0001"
_VERSION_COLUMNS = ("version", "schema_cookie")


class ResearchMigrationError(RuntimeError):
    """A migration refused to make a lossy or structurally unsafe change."""


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_names(connection) -> set[str]:
    return {
        row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _schema_cookie(connection) -> int:
    return int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())


def _normalise_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.replace("IF NOT EXISTS ", "").replace('"', "").strip()).upper()


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


def _rebuild_table(connection, table: Table) -> None:
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
    _after_table_rebuilt(table.name)


def _after_table_rebuilt(_table_name: str) -> None:
    """Failure-injection seam for restart and PRAGMA-restoration tests."""


def _create_indexes_and_triggers(connection) -> None:
    for table in ResearchBase.metadata.sorted_tables:
        for index in table.indexes:
            connection.exec_driver_sql(str(CreateIndex(index).compile(dialect=connection.dialect)))
    for name in ("research_experiment_spec", "research_optimization_trial"):
        for operation in ("UPDATE", "DELETE"):
            trigger = f"trg_{name}_no_{operation.lower()}"
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS {_quoted(trigger)} BEFORE {operation} "
                f"ON {_quoted(name)} BEGIN SELECT RAISE(ABORT, '{name} is immutable'); END"
            )


def _stamp(connection) -> None:
    connection.exec_driver_sql(
        f"CREATE TABLE IF NOT EXISTS {_quoted(VERSION_TABLE)} "
        "(version VARCHAR(16) NOT NULL PRIMARY KEY, schema_cookie INTEGER NOT NULL)"
    )
    columns = tuple(row[1] for row in connection.exec_driver_sql(
        f"PRAGMA table_info({_quoted(VERSION_TABLE)})"
    ))
    if columns == ("version",):
        connection.exec_driver_sql(
            f"ALTER TABLE {_quoted(VERSION_TABLE)} ADD COLUMN schema_cookie INTEGER"
        )
    elif columns != _VERSION_COLUMNS:
        raise ResearchMigrationError("research schema marker contract drift")
    connection.exec_driver_sql(f"DELETE FROM {_quoted(VERSION_TABLE)}")
    connection.exec_driver_sql(
        f"INSERT INTO {_quoted(VERSION_TABLE)} (version, schema_cookie) VALUES (?, ?)",
        (HEAD_VERSION, _schema_cookie(connection)),
    )


def _current_version(connection) -> tuple[str, int | None] | None:
    if VERSION_TABLE not in _table_names(connection):
        return None
    columns = tuple(row[1] for row in connection.exec_driver_sql(
        f"PRAGMA table_info({_quoted(VERSION_TABLE)})"
    ))
    if columns not in (("version",), _VERSION_COLUMNS):
        raise ResearchMigrationError("research schema marker contract drift")
    rows = connection.exec_driver_sql(
        f"SELECT version{', schema_cookie' if len(columns) == 2 else ''} "
        f"FROM {_quoted(VERSION_TABLE)}"
    ).all()
    if len(rows) != 1:
        raise ResearchMigrationError("research schema marker is not singular")
    return rows[0][0], (int(rows[0][1]) if len(columns) == 2 and rows[0][1] is not None else None)


def _expected_default(column, dialect) -> str | None:
    if column.server_default is None:
        return None
    return str(column.server_default.arg.compile(dialect=dialect))


def _expected_triggers() -> dict[str, str]:
    return {
        f"trg_{table}_no_{operation.lower()}": (
            f"CREATE TRIGGER trg_{table}_no_{operation.lower()} BEFORE {operation} "
            f"ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
        )
        for table in ("research_experiment_spec", "research_optimization_trial")
        for operation in ("UPDATE", "DELETE")
    }


def _validate_schema(connection, *, include_marker: bool = True) -> None:
    """Reject every visible schema-contract drift, not merely missing owners."""
    inspector = inspect(connection)
    expected_tables = {table.name for table in ResearchBase.metadata.sorted_tables}
    actual_tables = _table_names(connection) - {VERSION_TABLE}
    if actual_tables != expected_tables:
        raise ResearchMigrationError(
            f"research table-set drift: {sorted(actual_tables)} != {sorted(expected_tables)}"
        )
    if include_marker:
        marker_columns = tuple(row[1] for row in connection.exec_driver_sql(
            f"PRAGMA table_info({_quoted(VERSION_TABLE)})"
        ))
        if marker_columns != _VERSION_COLUMNS:
            raise ResearchMigrationError("research schema marker contract drift")
    for table in ResearchBase.metadata.sorted_tables:
        pk_positions = {
            column.name: index + 1
            for index, column in enumerate(table.primary_key.columns)
        }
        expected_columns = [
            (
                column.name,
                str(column.type.compile(dialect=connection.dialect)).upper(),
                not column.nullable,
                _expected_default(column, connection.dialect),
                pk_positions.get(column.name, 0),
            )
            for column in table.columns
        ]
        actual_columns = [
            (row[1], row[2].upper(), bool(row[3]), row[4], row[5])
            for row in connection.exec_driver_sql(f"PRAGMA table_info({_quoted(table.name)})")
        ]
        if actual_columns != expected_columns:
            raise ResearchMigrationError(f"{table.name} column contract drift")
        actual_primary_key = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
        expected_primary_key = tuple(column.name for column in table.primary_key.columns)
        if actual_primary_key != expected_primary_key:
            raise ResearchMigrationError(f"{table.name} primary-key drift")
        expected_uniques = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
        }
        actual_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table.name)
        }
        if actual_uniques != expected_uniques:
            raise ResearchMigrationError(f"{table.name} unique-constraint drift")
        expected_indexes = {
            (tuple(index.columns.keys()), bool(index.unique)) for index in table.indexes
        }
        actual_indexes = {
            (tuple(index["column_names"]), bool(index.get("unique")))
            for index in inspector.get_indexes(table.name)
        }
        if actual_indexes != expected_indexes:
            raise ResearchMigrationError(f"{table.name} index drift")
        expected_fks = {
            (tuple(fk.column_keys), fk.referred_table.name, tuple(element.column.name for element in fk.elements))
            for fk in table.foreign_key_constraints
        }
        actual_fks = {
            (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
            for fk in inspector.get_foreign_keys(table.name)
        }
        if actual_fks != expected_fks:
            raise ResearchMigrationError(f"{table.name} foreign-key drift")
    actual_triggers = dict(connection.exec_driver_sql(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
    ).all())
    expected_triggers = _expected_triggers()
    if set(actual_triggers) != set(expected_triggers) or any(
        _normalise_sql(actual_triggers[name]) != _normalise_sql(sql)
        for name, sql in expected_triggers.items()
    ):
        raise ResearchMigrationError("research trigger contract drift")
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
    if violations:
        raise ResearchMigrationError(f"foreign-key validation failed: {violations!r}")


def _rebuild_unversioned(connection) -> None:
    for table in ResearchBase.metadata.sorted_tables:
        _rebuild_table(connection, table)
    _create_indexes_and_triggers(connection)
    _validate_schema(connection, include_marker=False)
    _stamp(connection)


def _migration_table_signature() -> dict[str, tuple[str, ...]]:
    """The 0001 contract must not silently acquire future model columns/tables."""
    return {
        table.name: tuple(column.name for column in table.columns)
        for table in ResearchBase.metadata.sorted_tables
    }


def _recover_interrupted_swaps(connection) -> None:
    """Resolve deterministic rebuild leftovers before reading the version marker."""
    names = _table_names(connection)
    for table in ResearchBase.metadata.sorted_tables:
        source = table.name
        target = _temporary_name(table)
        if source not in names and target in names and _has_owner_column(connection, target):
            connection.exec_driver_sql(
                f"ALTER TABLE {_quoted(target)} RENAME TO {_quoted(source)}"
            )
        elif source in names and target in names:
            connection.exec_driver_sql(f"DROP TABLE {_quoted(target)}")


def migrate_research_db(engine: Engine) -> None:
    """Migrate empty, unversioned legacy, or already-head research databases."""
    from research.domain import models  # noqa: F401 - register every mapped table

    with engine.connect() as connection:
        _recover_interrupted_swaps(connection)
        connection.commit()
        marker = _current_version(connection)
        version = marker[0] if marker else None
        marker_cookie = marker[1] if marker else None
        expected_tables = {table.name for table in ResearchBase.metadata.sorted_tables}
        present_tables = _table_names(connection)
        if version == HEAD_VERSION:
            if expected_tables.issubset(present_tables):
                if marker_cookie == _schema_cookie(connection):
                    if int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()) != 1:
                        raise ResearchMigrationError("research foreign-key enforcement is disabled")
                    return
                _validate_schema(connection)
                connection.exec_driver_sql(
                    f"UPDATE {_quoted(VERSION_TABLE)} SET schema_cookie=?", (_schema_cookie(connection),)
                )
                connection.commit()
                return
            # Test and maintenance code may have intentionally dropped every
            # research table while the database-owned marker remains.  This is a
            # fresh-schema path, never an attempt to alter a populated database.
            if not (expected_tables & present_tables):
                ResearchBase.metadata.create_all(connection)
                _stamp(connection)
                connection.commit()
                _validate_schema(connection)
                return
            raise ResearchMigrationError("versioned research schema is incomplete")
        if version is not None:
            raise ResearchMigrationError(f"unsupported research schema version {version!r}")

        names = present_tables
        if not any(name in names or _temporary_name(table) in names for name, table in (
            (table.name, table) for table in ResearchBase.metadata.sorted_tables
        )):
            ResearchBase.metadata.create_all(connection)
            _stamp(connection)
            connection.commit()
            _validate_schema(connection)
            return

        foreign_keys = int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one())
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        try:
            migration = importlib.import_module(
                "research.domain.migrations.0001_owner_scoped_roots"
            )
            migration.upgrade(
                connection, _rebuild_unversioned,
                table_signature=_migration_table_signature(),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.exec_driver_sql(f"PRAGMA foreign_keys={foreign_keys}")
        _validate_schema(connection)


def downgrade_research_db(_engine: Engine) -> None:
    """Explicitly refuse destructive downgrade until a lossless reverse is needed."""
    raise ResearchMigrationError(
        "research schema downgrade is unsupported and refuses destructive DDL"
    )
