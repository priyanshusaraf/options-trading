"""Restart-safe migrations owned solely by the physically separate research DB."""
from __future__ import annotations

import importlib
from collections.abc import Callable

from sqlalchemy import Engine, UniqueConstraint, inspect
from sqlalchemy.schema import CreateIndex, CreateTable, Table

from research.domain.base import LEGACY_OWNER_ID, ResearchBase

VERSION_TABLE = "research_schema_version"
HEAD_VERSION = "0001"


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
        "(version VARCHAR(16) NOT NULL PRIMARY KEY)"
    )
    connection.exec_driver_sql(f"DELETE FROM {_quoted(VERSION_TABLE)}")
    connection.exec_driver_sql(
        f"INSERT INTO {_quoted(VERSION_TABLE)} (version) VALUES (?)", (HEAD_VERSION,)
    )


def _current_version(connection) -> str | None:
    if VERSION_TABLE not in _table_names(connection):
        return None
    rows = connection.exec_driver_sql(
        f"SELECT version FROM {_quoted(VERSION_TABLE)}"
    ).scalars().all()
    if len(rows) != 1:
        raise ResearchMigrationError("research schema marker is not singular")
    return rows[0]


def _validate_schema(connection) -> None:
    inspector = inspect(connection)
    for table in ResearchBase.metadata.sorted_tables:
        columns = {column["name"]: column for column in inspector.get_columns(table.name)}
        if "owner_id" not in columns or columns["owner_id"]["nullable"]:
            raise ResearchMigrationError(f"{table.name} lacks NOT NULL owner_id")
        actual_primary_key = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
        expected_primary_key = tuple(column.name for column in table.primary_key.columns)
        if actual_primary_key != expected_primary_key:
            raise ResearchMigrationError(
                f"{table.name} primary key drift: {actual_primary_key} != {expected_primary_key}"
            )
        expected_uniques = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        actual_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table.name)
        }
        if not expected_uniques.issubset(actual_uniques):
            raise ResearchMigrationError(f"{table.name} unique-constraint drift")
        actual_indexes = {
            tuple(index["column_names"])
            for index in inspector.get_indexes(table.name)
        }
        for index in table.indexes:
            expected = tuple(column.name for column in index.columns)
            if expected not in actual_indexes:
                raise ResearchMigrationError(f"missing index {table.name}{expected}")
        expected_fks = {
            (tuple(fk.column_keys), fk.referred_table.name)
            for fk in table.foreign_key_constraints
        }
        actual_fks = {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys(table.name)
        }
        if expected_fks != actual_fks:
            raise ResearchMigrationError(f"{table.name} foreign-key drift")
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
    if violations:
        raise ResearchMigrationError(f"foreign-key validation failed: {violations!r}")
    for name in ("research_experiment_spec", "research_optimization_trial"):
        triggers = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
            (name,),
        ).scalars().all()
        expected = {f"trg_{name}_no_update", f"trg_{name}_no_delete"}
        if not expected.issubset(triggers):
            raise ResearchMigrationError(f"{name} immutable triggers are missing")


def _rebuild_unversioned(connection) -> None:
    for table in ResearchBase.metadata.sorted_tables:
        _rebuild_table(connection, table)
    _create_indexes_and_triggers(connection)
    _stamp(connection)


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
        version = _current_version(connection)
        expected_tables = {table.name for table in ResearchBase.metadata.sorted_tables}
        present_tables = _table_names(connection)
        if version == HEAD_VERSION:
            if expected_tables.issubset(present_tables):
                _validate_schema(connection)
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
            migration.upgrade(connection, _rebuild_unversioned)
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
