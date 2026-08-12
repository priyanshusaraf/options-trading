"""Add ownerless immutable public backtest computation artifacts.

Revision ID: 0027
Revises: 0026
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

import sqlalchemy as sa
from alembic import op


revision, down_revision = "0027", "0026"
branch_labels = depends_on = None
TABLE, TEMP, PROOF = "backtest_computations", "backtest_computations__0027", "_backtest_0027_creation_proofs"
DDL = """CREATE TABLE __TABLE__ (
 execution_address VARCHAR(64) NOT NULL,
 dataset_address VARCHAR(64) NOT NULL,
 strategy_key VARCHAR(64) NOT NULL,
 strategy_version VARCHAR(128) NOT NULL,
 policy_address VARCHAR(64) NOT NULL,
 schema_version INTEGER NOT NULL,
 payload_json TEXT NOT NULL,
 payload_digest VARCHAR(64) NOT NULL,
 PRIMARY KEY (execution_address)
)"""
INDEXES = (("ix_backtest_computations_dataset", "dataset_address"),
           ("ix_backtest_computations_strategy", "strategy_key,strategy_version"))


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _digest(rows) -> str:
    body = []
    for row in rows:
        typ, name, sql = row.type, row.name or "", row.sql or ""
        name = re.sub(r"backtest_computations(?:__0027)?", "__table__", name)
        sql = re.sub(r"backtest_computations(?:__0027)?", "__table__", sql)
        name = name.removesuffix("__0027")
        sql = sql.replace("__0027", "")
        body.append(f"{typ}:{name}:" + " ".join(sql.replace('"', '').replace('`', '').split()).lower())
    return hashlib.sha256("\n".join(body).encode()).hexdigest()


def _schema(table: str) -> str:
    rows = op.get_bind().execute(sa.text(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=:name AND type IN ('table','index','trigger') ORDER BY type,name"),
        {"name": table}).all()
    return _digest(rows)


def _target_schema(*, temporary: bool) -> str:
    raw = sqlite3.connect(":memory:")
    try:
        table, suffix = (TEMP, "__0027") if temporary else (TABLE, "")
        raw.execute(DDL.replace("__TABLE__", table))
        for name, columns in INDEXES:
            raw.execute(f"CREATE INDEX {name}{suffix} ON {table}({columns})")
        class R:
            def __init__(self, row): self.type, self.name, self.sql = row
        rows = raw.execute("SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? AND type IN ('table','index','trigger') ORDER BY type,name", (table,)).fetchall()
        return _digest([R(row) for row in rows])
    finally:
        raw.close()


def _indexes(table: str, *, temporary: bool) -> None:
    suffix = "__0027" if temporary else ""
    for name, columns in INDEXES:
        op.execute(sa.text(f"CREATE INDEX {name}{suffix} ON {table}({columns})"))


def _promote_indexes() -> None:
    """Finish an interruption after table rename but before index rename."""
    names = {row[0] for row in op.get_bind().execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=:t"), {"t": TABLE})}
    if not any(f"{name}__0027" in names for name, _ in INDEXES):
        return
    for name, _ in INDEXES:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}__0027"))
    _indexes(TABLE, temporary=False)


def _proof(table: str) -> None:
    expected = _target_schema(temporary=table == TEMP)
    if _schema(table) != expected or op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
        raise RuntimeError("0027 target contract proof failed")
    op.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {PROOF} (table_name TEXT PRIMARY KEY,row_count INTEGER NOT NULL,schema_digest TEXT NOT NULL,phase TEXT NOT NULL)"))
    op.get_bind().execute(sa.text(f"INSERT OR REPLACE INTO {PROOF} VALUES (:t,0,:s,'built')"),
                          {"t": TABLE, "s": expected})


def _validate(table: str) -> None:
    row = op.get_bind().execute(sa.text(f"SELECT row_count,schema_digest,phase FROM {PROOF} WHERE table_name=:t"), {"t": TABLE}).one_or_none()
    if (row is None or row.row_count != 0 or row.phase != "built"
            or _schema(table) != row.schema_digest
            or row.schema_digest != _target_schema(temporary=table == TEMP)
            or op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()):
        raise RuntimeError("0027 refuses malformed completed public computation table")


def _clear_proof() -> None:
    if PROOF in _names():
        op.get_bind().execute(sa.text(f"DELETE FROM {PROOF} WHERE table_name=:t"), {"t": TABLE})
        if not op.get_bind().execute(sa.text(f"SELECT 1 FROM {PROOF} LIMIT 1")).first():
            op.execute(sa.text(f"DROP TABLE {PROOF}"))


def _recover() -> None:
    names = _names()
    if TEMP in names:
        if TABLE not in names:
            if PROOF not in names:
                raise RuntimeError("0027 refuses unproven source-absent temporary table")
            _validate(TEMP)
            op.execute(sa.text(f"ALTER TABLE {TEMP} RENAME TO {TABLE}"))
            _promote_indexes(); _validate(TABLE)
        else:
            if PROOF in names and op.get_bind().execute(sa.text(f"SELECT 1 FROM {PROOF} WHERE table_name=:t"), {"t": TABLE}).first():
                _validate(TEMP)
            op.execute(sa.text(f"DROP TABLE {TEMP}"))
    if TABLE in _names() and PROOF in _names():
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {PROOF} WHERE table_name=:t"), {"t": TABLE}).first():
            _promote_indexes()
            _validate(TABLE)
        _clear_proof()
    # Once its proof has been cleaned a completed table may contain real cache
    # rows, so validate the immutable target shape but never its row count.
    if TABLE in _names() and PROOF not in _names() and _schema(TABLE) != _target_schema(temporary=False):
        raise RuntimeError("0027 refuses existing public computation table with non-target schema")


def upgrade():
    _recover()
    if TABLE in _names(): return
    raw = op.get_bind().connection.driver_connection
    enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    try:
        raw.commit(); raw.execute("PRAGMA foreign_keys=OFF")
        op.execute(sa.text(DDL.replace("__TABLE__", TEMP))); _indexes(TEMP, temporary=True); _proof(TEMP)
        op.execute(sa.text(f"ALTER TABLE {TEMP} RENAME TO {TABLE}"))
        _promote_indexes(); _validate(TABLE); _clear_proof()
        if op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).all(): raise RuntimeError("0027 foreign-key validation failed")
    finally:
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def downgrade():
    _recover()
    if TABLE not in _names(): return
    if op.get_bind().execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
        raise RuntimeError("0027 downgrade refuses to discard immutable public computation artifacts")
    op.execute(sa.text(f"DROP TABLE {TABLE}"))
