"""Data-parametric witness construction for the frozen SQLite contract.

Witness rows are caller supplied and never participate in catalog authority.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from research.domain.migrations import sqlite_catalog_contract as contract


def construct(connection: sqlite3.Connection, *, marker: str = contract.TARGET_MARKER,
              missing_guards: Sequence[str] = ()) -> None:
    """Construct only the literal catalog; no migration/runtime import occurs."""
    unknown = set(missing_guards) - set(contract.REPAIRABLE_GUARDS)
    if unknown:
        raise ValueError(f"non-enumerated guard omission: {sorted(unknown)!r}")
    connection.execute("PRAGMA foreign_keys=ON")
    for statement in contract.construct_sql():
        if any(name in statement for name in missing_guards):
            continue
        connection.execute(statement)
    cookie = connection.execute("PRAGMA schema_version").fetchone()[0]
    connection.execute(
        "INSERT INTO research_schema_version(version,schema_cookie) VALUES (?,?)",
        (marker, cookie),
    )


def seed(connection: sqlite3.Connection, rows: Mapping[str, Sequence[Sequence[Any]]]) -> None:
    """Insert declared witness rows without schema inference or default consumption."""
    for table, values in rows.items():
        if table == "research_schema_version":
            raise ValueError("witnesses cannot define marker authority")
        declaration = contract.INVENTORY["tables"].get(table)
        if declaration is None:
            raise ValueError(f"unknown witness table: {table}")
        # Values are bound to frozen declaration order, not a live inventory.
        columns = [item[1] for item in declaration["table_xinfo"] if item[6] == 0]
        placeholders = ",".join("?" for _ in columns)
        for row in values:
            if len(row) != len(columns):
                raise ValueError(f"row width mismatch for {table}")
            connection.execute(f'INSERT INTO "{table}" VALUES ({placeholders})', tuple(row))


def inventory(connection: sqlite3.Connection) -> dict[str, Any]:
    """Read complete native state without normalizing JSON, blobs, or sequences."""
    result: dict[str, Any] = {}
    schema = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
    ).fetchall()
    result["sqlite_schema"] = schema
    result["sqlite_sequence"] = connection.execute(
        "SELECT name,seq FROM sqlite_sequence ORDER BY name"
    ).fetchall()
    tables = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    for table in tables:
        column_info = [tuple(row) for row in connection.execute(f'PRAGMA table_xinfo("{table}")') if row[6] == 0]
        columns = [row[1] for row in column_info]
        storage = connection.execute(
            "SELECT " + ",".join(f'typeof("{c}")' for c in columns) + f' FROM "{table}" ORDER BY rowid'
        ).fetchall()
        result[table] = {
            "columns": columns,
            "column_info": column_info,
            "rows": connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall(),
            "storage": storage,
            "foreign_keys": connection.execute(f'PRAGMA foreign_key_list("{table}")').fetchall(),
            "keys": [
                (index[1], index[2], connection.execute(f'PRAGMA index_info("{index[1]}")').fetchall())
                for index in connection.execute(f'PRAGMA index_list("{table}")').fetchall()
            ],
        }
    return result


def assert_complete_inventory(state: Mapping[str, Any]) -> None:
    """Reject a missing catalog object, table, key, FK, or native sequence fact."""
    declared = {
        (item["type"], item["name"], item["table"], item["sql"])
        for item in contract.INVENTORY["sqlite_schema"]
    }
    observed = set(state["sqlite_schema"])
    if observed != declared:
        raise AssertionError("SQLite immutable catalog inventory differs")
    if len(declared) != 100:
        raise AssertionError("SQLite frozen schema object count differs")
    expected_tables = set(contract.INVENTORY["tables"])
    actual_tables = {row[1] for row in state["sqlite_schema"] if row[0] == "table"}
    if actual_tables != expected_tables or len(expected_tables) != 26:
        raise AssertionError("SQLite table inventory differs")
    if "sqlite_sequence" not in state:
        raise AssertionError("SQLite native sequence state is missing")
