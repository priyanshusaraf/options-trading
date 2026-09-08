"""Add one nullable preparation receipt to the frozen 0011 operation table."""
from __future__ import annotations

import importlib
from sqlalchemy import inspect

previous = importlib.import_module("research.domain.migrations.0011_foundation_guard_contract")
TARGET_VERSION = "0012"
COLUMN = "preparation_evidence_json"
_before_marker_advance = lambda _connection: None


def _version(connection):
    if previous.VERSION_TABLE not in inspect(connection).get_table_names():
        return None
    if connection.dialect.name == "sqlite":
        return previous._sqlite_marker(connection)[0]
    return previous._postgresql_marker(connection)


def _sqlite_base_schema(connection):
    result = set()
    for kind, name, table, sql in previous._sqlite_schema(connection):
        if kind == "table" and name == "research_operation":
            addition = f", {COLUMN} TEXT"
            if sql.count(addition) != 1:
                previous._refuse("the preparation column declaration is drifted")
            sql = sql.replace(addition, "", 1)
        result.add((kind, name, table, sql))
    return result


def _validate_sqlite(connection):
    if _sqlite_base_schema(connection) != previous._sqlite_expected_schema():
        previous._refuse("the 0012 preparation catalog is drifted")
    version, cookie = previous._sqlite_marker(connection)
    actual = int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
    if version != TARGET_VERSION or cookie != actual:
        previous._refuse("the 0012 preparation marker is stale")


def upgrade_sqlite(connection):
    previous._certify_frozen_authority()
    if _version(connection) == TARGET_VERSION:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        _validate_sqlite(connection)
        return
    previous.upgrade_sqlite(connection)
    # The previous constructor may already hold BEGIN IMMEDIATE on clean/0010.
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    if _version(connection) == TARGET_VERSION:
        _validate_sqlite(connection)
        return
    previous._validate_sqlite_catalog(connection, allow_missing_guards=False)
    connection.exec_driver_sql(f"ALTER TABLE research_operation ADD COLUMN {COLUMN} TEXT")
    _before_marker_advance(connection)
    cookie = int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
    connection.exec_driver_sql(f'UPDATE "{previous.VERSION_TABLE}" SET version=?,schema_cookie=?', (TARGET_VERSION, cookie))
    _validate_sqlite(connection)


def _validate_postgresql(connection):
    expected = previous._expected_postgresql_catalog()
    expected["columns"] = sorted([*expected["columns"], ("research_operation", COLUMN, "text", False, None)])
    if previous._observe_postgresql_catalog(connection) != expected:
        previous._refuse("the 0012 preparation catalog is drifted")
    if previous._postgresql_marker(connection) != TARGET_VERSION:
        previous._refuse("the 0012 preparation marker is stale")


def upgrade_postgresql(connection):
    previous._certify_frozen_authority()
    major = int(connection.exec_driver_sql("SHOW server_version_num").scalar_one()) // 10000
    if major != 16:
        previous._refuse("the preparation migration requires PostgreSQL 16")
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("SELECT pg_advisory_xact_lock(713120012)")
    if _version(connection) == TARGET_VERSION:
        _validate_postgresql(connection)
        return
    previous.upgrade_postgresql(connection)
    connection.exec_driver_sql(f"ALTER TABLE research_operation ADD COLUMN {COLUMN} TEXT")
    _before_marker_advance(connection)
    connection.exec_driver_sql(f'UPDATE "{previous.VERSION_TABLE}" SET version=%s', (TARGET_VERSION,))
    _validate_postgresql(connection)
