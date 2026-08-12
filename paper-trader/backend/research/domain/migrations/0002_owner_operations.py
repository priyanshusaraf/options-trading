"""Restart-safe creation of durable owner-scoped research operations.

0002 used to trust a table merely because it had the deterministic temporary
name.  That turns an interrupted migration into an arbitrary-DDL promotion
primitive.  This migration records a target-bound proof before it removes the
source and validates the proof again before recovery can rename a temporary.
"""
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import inspect
from sqlalchemy.schema import CreateIndex, CreateTable

VERSION = "0002"
_PROOF_TABLE = "_research_0002_operation_rebuild_proof"


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _names(connection) -> set[str]:
    return {row[0] for row in connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def _temporary(table) -> str:
    return f"{table.name}__owner_tmp"


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace('"', '').strip()).upper()


def _schema_digest(connection, table) -> str:
    # The proof binds to the target's column/PK contract.  Indexes are created
    # only after the final rename because SQLite indexes target table names.
    columns = [tuple(row[1:6]) for row in connection.exec_driver_sql(
        f"PRAGMA table_info({_quote(table.name)})"
    )]
    expected = [
        (column.name, str(column.type.compile(dialect=connection.dialect)).upper(),
         int(not column.nullable),
         str(column.server_default.arg.compile(dialect=connection.dialect))
         if column.server_default is not None else None,
         list(table.primary_key.columns).index(column) + 1 if column.primary_key else 0)
        for column in table.columns
    ]
    # The first branch is used for expected metadata.  The table-name argument
    # lets recovery compare the temp's concrete shape to that contract.
    payload = expected if not columns else columns
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), default=str).encode()).hexdigest()


def _expected_schema_digest(connection, table) -> str:
    return _schema_digest(connection, type("Expected", (), {"name": "__missing__", "columns": table.columns, "primary_key": table.primary_key})())


def _payload_digest(connection, table_name: str, columns: list[str]) -> tuple[int, str]:
    rows = connection.exec_driver_sql(
        f"SELECT {', '.join(_quote(column) for column in columns)} "
        f"FROM {_quote(table_name)} ORDER BY {', '.join(_quote(column) for column in columns)}"
    ).all()
    encoded = json.dumps([list(row) for row in rows], separators=(",", ":"), default=str,
                         ensure_ascii=True)
    return len(rows), hashlib.sha256(encoded.encode()).hexdigest()


def _create_proof_store(connection) -> None:
    connection.exec_driver_sql(
        f"CREATE TABLE IF NOT EXISTS {_quote(_PROOF_TABLE)} "
        "(target VARCHAR(128) NOT NULL PRIMARY KEY, schema_digest VARCHAR(64) NOT NULL, "
        "row_count INTEGER NOT NULL, payload_digest VARCHAR(64) NOT NULL, "
        "phase VARCHAR(16) NOT NULL)"
    )


def _record_proof(connection, *, target: str, schema_digest: str, row_count: int,
                  payload_digest: str) -> None:
    _create_proof_store(connection)
    connection.exec_driver_sql(
        f"INSERT OR REPLACE INTO {_quote(_PROOF_TABLE)} "
        "(target,schema_digest,row_count,payload_digest,phase) VALUES (?,?,?,?, 'built')",
        (target, schema_digest, row_count, payload_digest),
    )


def _verify_proof(connection, table, target: str) -> None:
    if _PROOF_TABLE not in _names(connection):
        raise RuntimeError("unproven completed rebuild")
    proof = connection.exec_driver_sql(
        f"SELECT schema_digest,row_count,payload_digest,phase FROM {_quote(_PROOF_TABLE)} "
        "WHERE target=?", (target,)
    ).first()
    if proof is None or proof[3] != "built":
        raise RuntimeError("unproven completed rebuild")
    expected = _expected_schema_digest(connection, table)
    actual = _schema_digest(connection, type("Target", (), {"name": target, "columns": table.columns, "primary_key": table.primary_key})())
    if proof[0] != expected or actual != expected:
        raise RuntimeError("malformed completed rebuild")
    count, digest = _payload_digest(connection, target, [column.name for column in table.columns])
    if count != proof[1] or digest != proof[2]:
        raise RuntimeError("malformed completed rebuild")


def _create_at(connection, table, target: str) -> None:
    ddl = str(CreateTable(table).compile(dialect=connection.dialect))
    # SQLAlchemy's SQLite compiler may quote the table name or leave it bare.
    # Replace the first declaration occurrence only; FK references (if future
    # revisions add any) must remain bound to their final names.
    quoted = _quote(table.name)
    if quoted in ddl:
        ddl = ddl.replace(quoted, _quote(target), 1)
    else:
        ddl = ddl.replace(table.name, _quote(target), 1)
    connection.exec_driver_sql(ddl)


def _ensure_indexes(connection, table) -> None:
    present = {row[1] for row in connection.exec_driver_sql(
        f"PRAGMA index_list({_quote(table.name)})"
    )}
    for index in table.indexes:
        if index.name not in present:
            connection.exec_driver_sql(str(CreateIndex(index).compile(dialect=connection.dialect)))


def _validate_existing(connection, table) -> None:
    expected = _expected_schema_digest(connection, table)
    actual = _schema_digest(connection, table)
    if actual != expected:
        raise RuntimeError("research_operation schema contract is malformed")


def upgrade(connection, table) -> None:
    source, target = table.name, _temporary(table)
    names = _names(connection)
    if source in names and target in names:
        # Neither copy is safely disposable without a source-to-target proof.
        # Refuse before DDL, preserving forensic/recovery evidence.
        raise RuntimeError("ambiguous research_operation rebuild state")
    if source in names:
        _validate_existing(connection, table)
        _ensure_indexes(connection, table)
        return
    if target in names:
        _verify_proof(connection, table, target)
        connection.exec_driver_sql(f"ALTER TABLE {_quote(target)} RENAME TO {_quote(source)}")
        _ensure_indexes(connection, table)
        return

    _create_at(connection, table, target)
    expected = _expected_schema_digest(connection, table)
    actual = _schema_digest(connection, type("Target", (), {"name": target, "columns": table.columns, "primary_key": table.primary_key})())
    if actual != expected:
        raise RuntimeError("research_operation temporary schema contract is malformed")
    count, digest = _payload_digest(connection, target, [column.name for column in table.columns])
    _record_proof(connection, target=target, schema_digest=expected, row_count=count,
                  payload_digest=digest)
    connection.exec_driver_sql(f"ALTER TABLE {_quote(target)} RENAME TO {_quote(source)}")
    _ensure_indexes(connection, table)


def downgrade(connection, table) -> None:
    """Preflight before all DDL: history and interrupted state are never erased."""
    source, target = table.name, _temporary(table)
    names = _names(connection)
    if target in names:
        raise RuntimeError("0002 refuses downgrade with an interrupted rebuild")
    if source not in names:
        return
    if connection.exec_driver_sql(f"SELECT 1 FROM {_quote(source)} LIMIT 1").first() is not None:
        raise RuntimeError("0002 refuses destructive removal of durable operation history")
    connection.exec_driver_sql(f"DROP TABLE {_quote(source)}")
