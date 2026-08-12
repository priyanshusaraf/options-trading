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
DOWN_SUFFIX = "__0026_down"

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
            name = re.sub(re.escape(table) + r"(?:__0026(?:_down)?)?", f"__{table}__", name)
            sql = re.sub(re.escape(table) + r"(?:__0026(?:_down)?)?", f"__{table}__", sql)
        name = name.removesuffix(DOWN_SUFFIX).removesuffix(SUFFIX)
        sql = sql.replace(DOWN_SUFFIX, "").replace(SUFFIX, "")
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


def _down_target_schema(table, *, temporary):
    """Digest the immutable 0025 target, never a mutable source table."""
    raw = sqlite3.connect(":memory:")
    try:
        suffix = DOWN_SUFFIX if temporary else ""
        physical = table + suffix
        ddl = PREVIOUS.RUN_DDL if table == "backtest_runs" else PREVIOUS.RESULT_DDL
        raw.execute(ddl.replace("__TABLE__", physical))
        for name, columns in DOWN_INDEXES[table]:
            raw.execute(f"CREATE {'UNIQUE ' if name.startswith('uq_') else ''}INDEX "
                        f"{name}{suffix} ON {physical}({columns})")
        return _schema_digest(raw.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? "
            "AND type IN ('table','index','trigger') ORDER BY type,name", (physical,)).fetchall())
    finally:
        raw.close()


def _down_indexes(table, physical, *, temporary):
    suffix = DOWN_SUFFIX if temporary else ""
    for name, columns in DOWN_INDEXES[table]:
        op.execute(sa.text(f"CREATE {'UNIQUE ' if name.startswith('uq_') else ''}INDEX "
                           f"{name}{suffix} ON {physical}({columns})"))


def _down_proof(table, temp):
    expected = _down_target_schema(table, temporary=True)
    if _schema(temp) != expected:
        raise RuntimeError(f"0026 downgrade target contract proof failed for {table}")
    count, digest = _rows(f"SELECT * FROM {temp} ORDER BY rowid")
    op.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {PROOF_TABLE} "
                       "(table_name TEXT PRIMARY KEY,row_count INTEGER NOT NULL,"
                       "row_digest TEXT NOT NULL,schema_digest TEXT NOT NULL,phase TEXT NOT NULL)"))
    op.get_bind().execute(sa.text(
        f"INSERT OR REPLACE INTO {PROOF_TABLE} VALUES (:t,:c,:d,:s,'down-built')"),
        {"t": table, "c": count, "d": digest, "s": expected})


def _validate_down(table, physical):
    row = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest,schema_digest,phase FROM {PROOF_TABLE} "
        "WHERE table_name=:t"), {"t": table}).one_or_none()
    actual_rows = _rows(f"SELECT * FROM {physical} ORDER BY rowid")
    target = _down_target_schema(table, temporary=physical.endswith(DOWN_SUFFIX))
    actual_schema = _schema(physical)
    if (row is None or row.phase != "down-built"
            or actual_rows != (row.row_count, row.row_digest)
            or row.schema_digest != target or actual_schema != row.schema_digest):
        raise RuntimeError(f"0026 downgrade refuses malformed completed rebuild for {table}: "
                           f"proof={getattr(row, 'schema_digest', None)} target={target} actual={actual_schema}")


def _recover_down():
    """Restart-safe preflight for every durable downgrade interruption point.

    Validation happens before any DDL.  A source-present temporary is discarded
    only after its manifest verifies; a source-absent temporary is promoted only
    after the same verification.  A forged/unproven candidate leaves the schema
    untouched for investigation.
    """
    names = _names()
    for table in TABLES:
        temp = table + DOWN_SUFFIX
        if temp in names:
            # Create/copy may commit in SQLite before a proof table row exists.
            # The original source is still authoritative, so this is the sole
            # unproved state safe to discard and rebuild from source.
            proof_row = (op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table}).first()
                if PROOF_TABLE in names else None)
            if table not in names or proof_row:
                _validate_down(table, temp)
        elif table in names and PROOF_TABLE in names:
            row = op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table}).first()
            if row:
                _validate_down(table, table)
    for table in TABLES:
        temp = table + DOWN_SUFFIX
        if table in _names() and temp in _names():
            op.execute(sa.text(f"DROP TABLE {temp}"))
        elif table not in _names() and temp in _names():
            op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
            for name, _ in DOWN_INDEXES[table]:
                op.execute(sa.text(f"DROP INDEX IF EXISTS {name}{DOWN_SUFFIX}"))
            _down_indexes(table, table, temporary=False)
            _validate_down(table, table)
        if PROOF_TABLE in _names():
            op.get_bind().execute(sa.text(
                f"DELETE FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table})


def _down_rebuild(table, columns):
    temp = table + DOWN_SUFFIX
    source = f"SELECT {columns} FROM {table} ORDER BY rowid"
    expected = _rows(source)
    ddl = PREVIOUS.RUN_DDL if table == "backtest_runs" else PREVIOUS.RESULT_DDL
    op.execute(sa.text(ddl.replace("__TABLE__", temp)))
    op.execute(sa.text(f"INSERT INTO {temp} ({columns}) SELECT {columns} FROM {table}"))
    if _rows(f"SELECT {columns} FROM {temp} ORDER BY rowid") != expected:
        raise RuntimeError(f"0026 downgrade source-bound payload proof failed for {table}")
    _down_indexes(table, temp, temporary=True)
    _down_proof(table, temp)
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
    for name, _ in DOWN_INDEXES[table]:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}{DOWN_SUFFIX}"))
    _down_indexes(table, table, temporary=False)
    _validate_down(table, table)
    op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:t"), {"t": table})


def downgrade():
    raw = op.get_bind().connection.driver_connection; enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    try:
        raw.commit(); raw.execute("PRAGMA foreign_keys=OFF")
        _recover_down()
        # A prior interrupted invocation may already have recovered both target
        # tables.  It is now safe for Alembic to stamp 0025 without issuing DDL.
        run_columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("backtest_runs")}
        result_columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("backtest_results")}
        if "request_json" not in run_columns and "cell_key" not in result_columns:
            return
        # Request descriptors and replay cell identities are durable execution
        # evidence; silently deleting them would make a formerly reproducible
        # run unreproducible.  This follows recovery preflight so a source-absent
        # completed target is never queried as though it were still 0026.
        if (("request_json" in run_columns and op.get_bind().execute(sa.text(
                    "SELECT 1 FROM backtest_runs WHERE request_json != '' LIMIT 1")).first())
                or ("cell_key" in result_columns and op.get_bind().execute(sa.text(
                    "SELECT 1 FROM backtest_results WHERE cell_key NOT LIKE 'legacy:%' LIMIT 1")).first())):
            raise RuntimeError("0026 downgrade refused: durable replay evidence would be lost")
        # Only legacy backfills are reversible. Their new values are synthetic
        # (`legacy:<id>` and an empty descriptor), so removing them changes no
        # historical execution fact.
        if "cell_key" in result_columns:
            _down_rebuild("backtest_results", PREVIOUS.RESULT_COLUMNS)
        if "request_json" in run_columns:
            _down_rebuild("backtest_runs", PREVIOUS.RUN_COLUMNS)
        if op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).all():
            raise RuntimeError("0026 downgrade foreign-key validation failed")
    finally:
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")
