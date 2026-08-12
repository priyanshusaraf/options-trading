"""Pin restart descriptors and idempotent durable backtest cells.

Revision ID: 0026
Revises: 0025

SQLite cannot add a composite unique constraint safely.  This revision therefore
uses the same proven, restart-safe rebuild protocol as 0024/0025: a target-bound
manifest, source-derived payload digest, validation before every promotion, and
no DDL after a malformed recovery candidate is found.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sqlite3

import sqlalchemy as sa
from alembic import op


revision, down_revision = "0026", "0025"
branch_labels = depends_on = None
PREVIOUS = importlib.import_module("migrations.versions.20260812_0025_backtest_job_claims")
TABLES = ("backtest_runs", "backtest_results")
PROOF_TABLE = "_backtest_0026_rebuild_proofs"
SUFFIX = "__0026"

# These are target manifests derived solely from 0025's checked-in immutable DDL,
# not from a live source table.  Editing an existing database cannot choose what a
# completed temp proves.
RUN_DDL = PREVIOUS.RUN_DDL.replace(
    " cancel_requested_at DATETIME,\n intervals",
    " cancel_requested_at DATETIME, request_json TEXT DEFAULT '' NOT NULL,\n intervals")
RESULT_DDL = PREVIOUS.RESULT_DDL.replace(
    " id INTEGER NOT NULL, owner_id VARCHAR(64) DEFAULT 'owner' NOT NULL, run_id INTEGER NOT NULL,\n",
    " id INTEGER NOT NULL, owner_id VARCHAR(64) DEFAULT 'owner' NOT NULL, run_id INTEGER NOT NULL,\n cell_key VARCHAR(192),\n").replace(
    " strategy_key VARCHAR(64) NOT NULL, interval VARCHAR(12) NOT NULL, trades INTEGER NOT NULL,",
    " strategy_key VARCHAR(64) NOT NULL, interval VARCHAR(12) NOT NULL, strategy_version VARCHAR(128), trades INTEGER NOT NULL,")
RUN_COLUMNS = PREVIOUS.RUN_COLUMNS + ",request_json"
RUN_SELECT_UP = PREVIOUS.RUN_COLUMNS + ",''"
RESULT_COLUMNS = ("id,owner_id,run_id,cell_key,instrument_key,name,segment,strategy_key,interval,"
                  "strategy_version," + PREVIOUS.RESULT_COLUMNS.split("strategy_key,", 1)[1])
RESULT_SELECT_UP = ("id,owner_id,run_id,'legacy:' || id,instrument_key,name,segment,strategy_key,interval,"
                    "'legacy:' || id," + PREVIOUS.RESULT_COLUMNS.split("strategy_key,", 1)[1])
UP_INDEXES = {
    "backtest_runs": PREVIOUS.UP_INDEXES["backtest_runs"],
    "backtest_results": PREVIOUS.UP_INDEXES["backtest_results"] + (
        ("uq_backtest_results_owner_run_cell", "owner_id,run_id,cell_key"),),
}
DOWN_INDEXES = PREVIOUS.UP_INDEXES


def _names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rows(query):
    rows = op.get_bind().execute(sa.text(query)).all()
    encoded = json.dumps([list(row) for row in rows], default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(encoded.encode()).hexdigest()


def _schema_digest(rows):
    body = []
    for row in rows:
        typ, name, sql = (row.type, row.name, row.sql) if hasattr(row, "type") else row
        name, sql = name or "", sql or ""
        for table in TABLES:
            name = re.sub(re.escape(table) + r"(?:__0026)?", f"__{table}__", name)
            sql = re.sub(re.escape(table) + r"(?:__0026)?", f"__{table}__", sql)
        name = name.removesuffix(SUFFIX)
        sql = sql.replace(SUFFIX, "")
        body.append(f"{typ}:{name}:" + " ".join(sql.replace('"', '').replace('`', '').split()).lower())
    return hashlib.sha256("\n".join(body).encode()).hexdigest()


def _schema(table):
    return _schema_digest(op.get_bind().execute(sa.text(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=:name AND type IN ('table','index','trigger') ORDER BY type,name"),
        {"name": table}).all())


def _target_schema(table, *, temporary):
    raw = sqlite3.connect(":memory:")
    try:
        run, result = "backtest_runs" + (SUFFIX if temporary else ""), "backtest_results" + (SUFFIX if temporary else "")
        raw.execute(RUN_DDL.replace("__TABLE__", run)); raw.execute(RESULT_DDL.replace("__TABLE__", result))
        for logical, physical in (("backtest_runs", run), ("backtest_results", result)):
            for name, columns in UP_INDEXES[logical]:
                raw.execute(f"CREATE {'UNIQUE ' if name.startswith('uq_') else ''}INDEX {name}{SUFFIX if temporary else ''} ON {physical}({columns})")
        return _schema_digest(raw.execute("SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? AND type IN ('table','index','trigger') ORDER BY type,name", (table + (SUFFIX if temporary else ""),)).fetchall())
    finally:
        raw.close()


def _indexes(table, physical, *, temporary):
    for name, columns in UP_INDEXES[table]:
        op.execute(sa.text(f"CREATE {'UNIQUE ' if name.startswith('uq_') else ''}INDEX {name}{SUFFIX if temporary else ''} ON {physical}({columns})"))


def _proof(table, temp):
    expected = _target_schema(table, temporary=True)
    if _schema(temp) != expected:
        raise RuntimeError(f"0026 target contract proof failed for {table}")
    count, digest = _rows(f"SELECT * FROM {temp} ORDER BY rowid")
    op.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {PROOF_TABLE} (table_name TEXT PRIMARY KEY,row_count INTEGER NOT NULL,row_digest TEXT NOT NULL,schema_digest TEXT NOT NULL,phase TEXT NOT NULL)"))
    op.get_bind().execute(sa.text(f"INSERT OR REPLACE INTO {PROOF_TABLE} VALUES (:t,:c,:d,:s,'built')"), {"t": table, "c": count, "d": digest, "s": expected})


def _validate(table, physical):
    row = op.get_bind().execute(sa.text(f"SELECT row_count,row_digest,schema_digest,phase FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table}).one_or_none()
    if row is None or row.phase != "built" or _rows(f"SELECT * FROM {physical} ORDER BY rowid") != (row.row_count, row.row_digest) or row.schema_digest != _target_schema(table, temporary=physical.endswith(SUFFIX)) or _schema(physical) != row.schema_digest:
        raise RuntimeError(f"0026 refuses malformed completed rebuild for {table}")


def _recover():
    names = _names()
    # Validate every possibly authoritative temp before touching either table.
    for table in TABLES:
        temp = table + SUFFIX
        if table not in names and temp in names:
            _validate(table, temp)
        elif table in names and temp not in names and PROOF_TABLE in names:
            row = op.get_bind().execute(sa.text(f"SELECT 1 FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table}).first()
            if row:
                _validate(table, table)
    for table in TABLES:
        temp = table + SUFFIX
        if table in names and temp in names:
            op.execute(sa.text(f"DROP TABLE {temp}"))
        elif table not in names and temp in names:
            op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
            for name, _ in UP_INDEXES[table]: op.execute(sa.text(f"DROP INDEX IF EXISTS {name}{SUFFIX}"))
            _indexes(table, table, temporary=False); _validate(table, table)
        if PROOF_TABLE in _names():
            op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table})


def _rebuild(table, ddl, columns, source):
    temp = table + SUFFIX
    expected = _rows(f"SELECT {source} FROM {table} ORDER BY rowid")
    op.execute(sa.text(ddl.replace("__TABLE__", temp)))
    op.execute(sa.text(f"INSERT INTO {temp} ({columns}) SELECT {source} FROM {table}"))
    # Compare the transformed source projection, not physical column order: this
    # revision deliberately inserts `request_json` in the middle of the run DDL.
    if _rows(f"SELECT {columns} FROM {temp} ORDER BY rowid") != expected:
        raise RuntimeError(f"0026 source-bound payload proof failed for {table}")
    _indexes(table, temp, temporary=True); _proof(table, temp)
    op.execute(sa.text(f"DROP TABLE {table}")); op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
    for name, _ in UP_INDEXES[table]: op.execute(sa.text(f"DROP INDEX IF EXISTS {name}{SUFFIX}"))
    _indexes(table, table, temporary=False); _validate(table, table)
    op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table})


def upgrade():
    _recover()
    raw = op.get_bind().connection.driver_connection; enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    try:
        raw.commit(); raw.execute("PRAGMA foreign_keys=OFF")
        run_cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("backtest_runs")}
        result_cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("backtest_results")}
        if "request_json" not in run_cols: _rebuild("backtest_runs", RUN_DDL, RUN_COLUMNS, RUN_SELECT_UP)
        if not {"cell_key", "strategy_version"} <= result_cols: _rebuild("backtest_results", RESULT_DDL, RESULT_COLUMNS, RESULT_SELECT_UP)
        if PROOF_TABLE in _names() and not op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF_TABLE} LIMIT 1")).first():
            op.execute(sa.text(f"DROP TABLE {PROOF_TABLE}"))
        if op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).all(): raise RuntimeError("0026 foreign-key validation failed")
    finally:
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def downgrade():
    # Request descriptors and replay cell identities are durable execution evidence;
    # silently deleting them would make a formerly reproducible run unreproducible.
    if op.get_bind().execute(sa.text("SELECT 1 FROM backtest_runs WHERE request_json != '' LIMIT 1")).first() or op.get_bind().execute(sa.text("SELECT 1 FROM backtest_results WHERE cell_key NOT LIKE 'legacy:%' LIMIT 1")).first():
        raise RuntimeError("0026 downgrade refused: durable replay evidence would be lost")
    raw = op.get_bind().connection.driver_connection; enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    try:
        raw.commit(); raw.execute("PRAGMA foreign_keys=OFF")
        # Only legacy backfills are reversible. Their new values are synthetic
        # (`legacy:<id>` and an empty descriptor), so removing them changes no
        # historical execution fact. Use a fresh source-derived rebuild rather
        # than SQLite's lossy ALTER/DROP COLUMN shorthand.
        for table, ddl, columns in (
            ("backtest_results", PREVIOUS.RESULT_DDL, PREVIOUS.RESULT_COLUMNS),
            ("backtest_runs", PREVIOUS.RUN_DDL, PREVIOUS.RUN_COLUMNS),
        ):
            temp = table + "__0026_down"
            expected = _rows(f"SELECT {columns} FROM {table} ORDER BY rowid")
            op.execute(sa.text(ddl.replace("__TABLE__", temp)))
            op.execute(sa.text(f"INSERT INTO {temp} ({columns}) SELECT {columns} FROM {table}"))
            if _rows(f"SELECT {columns} FROM {temp} ORDER BY rowid") != expected:
                raise RuntimeError(f"0026 downgrade source proof failed for {table}")
            op.execute(sa.text(f"DROP TABLE {table}")); op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
            for name, columns_spec in PREVIOUS.UP_INDEXES[table]:
                op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({columns_spec})"))
        if op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).all():
            raise RuntimeError("0026 downgrade foreign-key validation failed")
    finally:
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")
