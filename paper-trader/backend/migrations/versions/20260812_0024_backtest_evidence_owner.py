"""Own durable backtest runs and results by organization.

Revision ID: 0024
Revises: 0023
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

import sqlalchemy as sa
from alembic import op


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "owner"
TABLES = ("backtest_runs", "backtest_results")
PROOF_TABLE = "_backtest_0024_rebuild_proofs"


RUN_DDL = """CREATE TABLE __TABLE__ (
 id INTEGER NOT NULL, owner_id VARCHAR(64) DEFAULT 'owner' NOT NULL,
 created_at DATETIME NOT NULL, status VARCHAR(16) NOT NULL, scope VARCHAR(16) NOT NULL,
 intervals VARCHAR(128) NOT NULL, capital FLOAT NOT NULL, total INTEGER NOT NULL,
 done INTEGER NOT NULL, note VARCHAR(400) NOT NULL, window VARCHAR(64) NOT NULL,
 instruments VARCHAR(400) NOT NULL, strategies VARCHAR(400) NOT NULL, PRIMARY KEY (id),
 CONSTRAINT uq_backtest_runs_owner_id UNIQUE (owner_id, id),
 FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT)"""

RESULT_DDL = """CREATE TABLE __TABLE__ (
 id INTEGER NOT NULL, owner_id VARCHAR(64) DEFAULT 'owner' NOT NULL, run_id INTEGER NOT NULL,
 instrument_key VARCHAR(48) NOT NULL, name VARCHAR(64) NOT NULL, segment VARCHAR(12) NOT NULL,
 strategy_key VARCHAR(64) NOT NULL, interval VARCHAR(12) NOT NULL, trades INTEGER NOT NULL,
 wins INTEGER NOT NULL, win_rate FLOAT NOT NULL, profit_factor FLOAT,
 max_drawdown_pct FLOAT NOT NULL, return_pct FLOAT NOT NULL, net_pnl FLOAT NOT NULL,
 gross_pnl FLOAT NOT NULL, charges FLOAT NOT NULL, expectancy FLOAT NOT NULL, cagr FLOAT,
 calmar FLOAT, consistency FLOAT, sharpe FLOAT, max_consec_losses INTEGER NOT NULL,
 time_underwater_pct FLOAT NOT NULL, worst_trade_pnl FLOAT NOT NULL, worst_mae_pct FLOAT NOT NULL,
 notional FLOAT NOT NULL, lots INTEGER NOT NULL, affordable BOOLEAN NOT NULL,
 option_cost FLOAT NOT NULL, open_at_end BOOLEAN NOT NULL, win_rate_realised FLOAT NOT NULL,
 return_pct_realised FLOAT NOT NULL, bh_return_pct FLOAT, first_ts INTEGER NOT NULL,
 last_ts INTEGER NOT NULL, effective_days INTEGER NOT NULL, clamped BOOLEAN NOT NULL,
 bars INTEGER NOT NULL, curve_json TEXT NOT NULL, bh_curve_json TEXT NOT NULL,
 trades_json TEXT NOT NULL, error VARCHAR(400) NOT NULL, premium_trades INTEGER NOT NULL,
 premium_win_rate FLOAT NOT NULL, premium_net_pnl FLOAT NOT NULL, premium_return_pct FLOAT NOT NULL,
 premium_profit_factor FLOAT, premium_max_drawdown_pct FLOAT NOT NULL,
 premium_expectancy FLOAT NOT NULL, premium_charges FLOAT NOT NULL,
 premium_trades_json TEXT NOT NULL, premium_error VARCHAR(200) NOT NULL,
 params_hash VARCHAR(64) NOT NULL, last_candle_ts INTEGER NOT NULL,
 schema_version INTEGER NOT NULL, from_cache BOOLEAN NOT NULL, computed_at DATETIME,
 PRIMARY KEY (id), CONSTRAINT uq_backtest_results_owner_id UNIQUE (owner_id, id),
 CONSTRAINT fk_backtest_results_owner_run FOREIGN KEY(owner_id, run_id) REFERENCES backtest_runs (owner_id, id) ON DELETE RESTRICT,
 FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT)"""

RUN_COLUMNS = "id,owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies"
RUN_SELECT = f"id,'{LEGACY_OWNER_ID}',created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies"
RESULT_COLUMNS = "id,owner_id,run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at"
RESULT_SELECT = f"id,'{LEGACY_OWNER_ID}',run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at"

LEGACY_RUN_DDL = (RUN_DDL
    .replace(" id INTEGER NOT NULL, owner_id VARCHAR(64) DEFAULT 'owner' NOT NULL,\n", " id INTEGER NOT NULL,\n")
    .replace(",\n CONSTRAINT uq_backtest_runs_owner_id UNIQUE (owner_id, id),\n FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT", ""))
LEGACY_RESULT_DDL = (RESULT_DDL
    .replace(" id INTEGER NOT NULL, owner_id VARCHAR(64) DEFAULT 'owner' NOT NULL, run_id INTEGER NOT NULL,\n",
             " id INTEGER NOT NULL, run_id INTEGER NOT NULL,\n")
    .replace(", CONSTRAINT uq_backtest_results_owner_id UNIQUE (owner_id, id),\n"
             " CONSTRAINT fk_backtest_results_owner_run FOREIGN KEY(owner_id, run_id) REFERENCES backtest_runs (owner_id, id) ON DELETE RESTRICT,\n"
             " FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT", ""))
LEGACY_RUN_COLUMNS = RUN_COLUMNS.replace("owner_id,", "")
LEGACY_RESULT_COLUMNS = RESULT_COLUMNS.replace("owner_id,", "")

# The proof must be tied to this revision's intended table *and* physical access
# contract.  Temp indexes use a private suffix while the source is still present;
# they are replaced with these canonical final names immediately after promotion.
UP_INDEXES = {
    "backtest_runs": (
        ("ix_backtest_runs_owner_id", "owner_id"),
        ("ix_backtest_runs_owner_created", "owner_id,created_at"),
        ("ix_backtest_runs_owner_status", "owner_id,status"),
    ),
    "backtest_results": (
        ("ix_backtest_results_owner_id", "owner_id"),
        ("ix_backtest_results_owner_run", "owner_id,run_id"),
        ("ix_backtest_results_owner_cache", "owner_id,params_hash,last_candle_ts"),
        ("ix_backtest_results_run_id", "run_id"),
        ("ix_backtest_results_instrument_key", "instrument_key"),
        ("ix_backtest_results_interval", "interval"),
        ("ix_backtest_results_strategy_key", "strategy_key"),
    ),
}
DOWN_INDEXES = {
    "backtest_runs": (),
    "backtest_results": (
        ("ix_backtest_results_run_id", "run_id"),
        ("ix_backtest_results_instrument_key", "instrument_key"),
        ("ix_backtest_results_interval", "interval"),
        ("ix_backtest_results_strategy_key", "strategy_key"),
    ),
}


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rows(query: str) -> tuple[int, str]:
    value = op.get_bind().execute(sa.text(query)).all()
    body = json.dumps([list(row) for row in value], default=str, separators=(",", ":"))
    return len(value), hashlib.sha256(body.encode()).hexdigest()


def _schema_rows(connection, table: str):
    return connection.execute(sa.text(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=:table "
        "AND type IN ('table','index','trigger') ORDER BY type,name"), {"table": table}).all()


def _schema_digest(rows) -> str:
    # A result table names its run parent. During recovery that parent may already
    # have been promoted, so normalize every migration-local physical name rather
    # than falsely treating a SQLite rename rewrite as a different contract.
    normalized_parts = []
    for row in rows:
        # SQLAlchemy rows expose named attributes; sqlite3's target-manifest
        # connection returns plain tuples.
        row_type, normalized_name, normalized_sql = (
            (row.type, row.name, row.sql)
            if hasattr(row, "type") else (row[0], row[1], row[2])
        )
        normalized_sql = normalized_sql or ""
        for logical in TABLES:
            normalized_sql = re.sub(re.escape(logical) + r"(?:__0024)?",
                                    f"__{logical}__", normalized_sql)
            normalized_name = re.sub(re.escape(logical) + r"(?:__0024)?",
                                     f"__{logical}__", normalized_name)
        normalized_parts.append(
            f"{row_type}:{normalized_name}:" +
            " ".join(normalized_sql.replace('"', '').replace('`', '').split()).lower())
    normalized = "\n".join(normalized_parts)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _schema(table: str) -> str:
    return _schema_digest(_schema_rows(op.get_bind(), table))


def _index_specs(table: str, direction: str):
    return (UP_INDEXES if direction == "up" else DOWN_INDEXES)[table]


def _target_schema(table: str, *, direction: str, temporary: bool) -> str:
    """Digest the revision-owned target manifest, never a recoverable temp table.

    This uses the immutable DDL/index declarations above in a private SQLite
    connection.  The live temp can therefore not choose the contract authenticated
    by its own proof.  Triggers are included by `_schema_rows` (there are none in
    0024) so adding one later changes the digest deliberately.
    """
    raw = sqlite3.connect(":memory:")
    try:
        suffix = "__0024" if temporary else ""
        run_name = "backtest_runs" + suffix
        result_name = "backtest_results" + suffix
        if direction == "up":
            run_ddl, result_ddl = RUN_DDL, RESULT_DDL
        else:
            run_ddl, result_ddl = LEGACY_RUN_DDL, LEGACY_RESULT_DDL
        raw.execute(run_ddl.replace("__TABLE__", run_name))
        raw.execute(result_ddl.replace("__TABLE__", result_name))
        for logical, physical in (("backtest_runs", run_name),
                                  ("backtest_results", result_name)):
            for name, columns in _index_specs(logical, direction):
                index_name = name + ("__0024" if temporary else "")
                raw.execute(f"CREATE INDEX {index_name} ON {physical}({columns})")
        rows = raw.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? "
            "AND type IN ('table','index','trigger') ORDER BY type,name", (table + suffix,)
        ).fetchall()
        return _schema_digest(rows)
    finally:
        raw.close()


def _create_indexes(table: str, physical: str, *, direction: str, temporary: bool) -> None:
    for name, columns in _index_specs(table, direction):
        index_name = name + ("__0024" if temporary else "")
        clause = "" if temporary else " IF NOT EXISTS"
        op.execute(sa.text(f"CREATE INDEX{clause} {index_name} ON {physical}({columns})"))


def _drop_temp_indexes(table: str, *, direction: str) -> None:
    for name, _ in _index_specs(table, direction):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}__0024"))


def _ensure_proofs() -> None:
    op.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {PROOF_TABLE} ("
                       "table_name VARCHAR(64) PRIMARY KEY, row_count INTEGER NOT NULL, "
                       "row_digest VARCHAR(64) NOT NULL, direction VARCHAR(8) NOT NULL, "
                       "schema_digest VARCHAR(64) NOT NULL, phase VARCHAR(16) NOT NULL)"))


def _write_proof(table: str, temp: str, *, direction: str) -> None:
    _ensure_proofs()
    expected_schema = _target_schema(table, direction=direction, temporary=True)
    if _schema(temp) != expected_schema:
        raise RuntimeError(f"0024 source-bound target contract proof failed for {table}")
    count, digest = _rows(f"SELECT * FROM {temp} ORDER BY rowid")
    op.get_bind().execute(sa.text(
        f"INSERT OR REPLACE INTO {PROOF_TABLE} VALUES "
        "(:table,:count,:digest,:direction,:schema,'built')"), {
        "table": table, "count": count, "digest": digest,
        "direction": direction, "schema": expected_schema})


def _prove_temp(table: str, temp: str, *, direction: str) -> None:
    if PROOF_TABLE not in _names():
        raise RuntimeError(f"0024 refuses unproven completed rebuild for {table}")
    proof = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest,direction,schema_digest,phase FROM {PROOF_TABLE} "
        "WHERE table_name=:table"),
        {"table": table}).one_or_none()
    if (proof is None or proof.direction != direction or proof.phase != "built"
            or _rows(f"SELECT * FROM {temp} ORDER BY rowid") != (proof.row_count, proof.row_digest)
            or _schema(temp) != proof.schema_digest
            or proof.schema_digest != _target_schema(table, direction=direction, temporary=True)):
        raise RuntimeError(f"0024 refuses malformed completed rebuild for {table}")


def _prove_promoted(table: str, *, direction: str) -> None:
    """Validate the renamed live table against the proof and final target manifest."""
    if PROOF_TABLE not in _names():
        raise RuntimeError(f"0024 refuses unproven promoted rebuild for {table}")
    proof = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest,direction,schema_digest,phase FROM {PROOF_TABLE} "
        "WHERE table_name=:table"), {"table": table}).one_or_none()
    if proof is None or proof.direction != direction or proof.phase != "built" \
            or proof.schema_digest != _target_schema(table, direction=direction, temporary=True) \
            or _rows(f"SELECT * FROM {table} ORDER BY rowid") != (proof.row_count, proof.row_digest) \
            or _schema(table) != _target_schema(table, direction=direction, temporary=False):
        raise RuntimeError(f"0024 refuses malformed promoted rebuild for {table}")


def _promote_contract(table: str, *, direction: str) -> None:
    _drop_temp_indexes(table, direction=direction)
    _create_indexes(table, table, direction=direction, temporary=False)
    _prove_promoted(table, direction=direction)


def _recover(*, direction: str) -> None:
    names = _names()
    # Validate every completed, source-absent or post-rename candidate before
    # changing any table. A retry must never promote one table then discover a
    # forged proof for the other.
    for table in TABLES:
        temp = f"{table}__0024"
        if table not in names and temp in names:
            _prove_temp(table, temp, direction=direction)
        elif table in names and temp not in names and PROOF_TABLE in names:
            proof = op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table}
            ).scalar_one_or_none()
            if proof is not None:
                _prove_promoted(table, direction=direction)
    for table in TABLES:
        temp = f"{table}__0024"
        if table in names and temp in names:
            op.execute(sa.text(f"DROP TABLE {temp}"))
            if PROOF_TABLE in _names():
                op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})
        elif table not in names and temp in names:
            op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
            _promote_contract(table, direction=direction)
            op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})
        elif table in names and temp not in names and PROOF_TABLE in _names():
            op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _rebuild(table: str, ddl: str, columns: str, source: str, *, direction: str = "up") -> None:
    temp = f"{table}__0024"
    expected = _rows(f"SELECT {source} FROM {table} ORDER BY rowid")
    op.execute(sa.text(ddl.replace("__TABLE__", temp)))
    op.execute(sa.text(f"INSERT INTO {temp} ({columns}) SELECT {source} FROM {table}"))
    if _rows(f"SELECT * FROM {temp} ORDER BY rowid") != expected:
        raise RuntimeError(f"0024 source-bound payload proof failed for {table}")
    _create_indexes(table, temp, direction=direction, temporary=True)
    _write_proof(table, temp, direction=direction)
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
    _promote_contract(table, direction=direction)
    op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _indexes() -> None:
    for table in TABLES:
        _create_indexes(table, table, direction="up", temporary=False)


def upgrade() -> None:
    _recover(direction="up")
    raw = op.get_bind().connection.driver_connection
    enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    try:
        raw.commit(); raw.execute("PRAGMA foreign_keys=OFF")
        run_columns = {col["name"] for col in sa.inspect(op.get_bind()).get_columns("backtest_runs")}
        result_columns = {col["name"] for col in sa.inspect(op.get_bind()).get_columns("backtest_results")}
        if "owner_id" not in run_columns:
            _rebuild("backtest_runs", RUN_DDL, RUN_COLUMNS, RUN_SELECT)
        if "owner_id" not in result_columns:
            _rebuild("backtest_results", RESULT_DDL, RESULT_COLUMNS, RESULT_SELECT)
        _indexes()
        if PROOF_TABLE in _names() and op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {PROOF_TABLE}")).scalar_one() == 0:
            op.execute(sa.text(f"DROP TABLE {PROOF_TABLE}"))
        bad = op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).all()
        if bad:
            raise RuntimeError(f"0024 foreign-key validation failed: {bad!r}")
    finally:
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def downgrade() -> None:
    bind = op.get_bind()
    # Preflight every authoritative candidate before recovery performs any DDL.
    # This matters after an interrupted downgrade where the source may be absent
    # and only a proven temp remains.
    candidates = {}
    names = _names()
    for table in TABLES:
        candidate = table if table in names else f"{table}__0024"
        if candidate not in names:
            raise RuntimeError(f"0024 downgrade refused: missing recovery candidate for {table}")
        candidates[table] = candidate
    unsafe_owner = False
    for candidate in candidates.values():
        columns = {c["name"] for c in sa.inspect(bind).get_columns(candidate)}
        if "owner_id" in columns and bind.execute(sa.text(
                f"SELECT 1 FROM {candidate} WHERE owner_id != :legacy LIMIT 1"),
                {"legacy": LEGACY_OWNER_ID}).first():
            unsafe_owner = True
    run_candidate, result_candidate = candidates["backtest_runs"], candidates["backtest_results"]
    result_columns = {c["name"] for c in sa.inspect(bind).get_columns(result_candidate)}
    run_columns = {c["name"] for c in sa.inspect(bind).get_columns(run_candidate)}
    broken = None
    if "owner_id" in result_columns and "owner_id" in run_columns:
        broken = bind.execute(sa.text(
            f"SELECT 1 FROM {result_candidate} AS result LEFT JOIN {run_candidate} AS run "
            "ON run.owner_id=result.owner_id AND run.id=result.run_id "
            "WHERE run.id IS NULL LIMIT 1")).first()
    if unsafe_owner or broken:
        raise RuntimeError(
            "0024 downgrade refused: owner collapse or composite relation loss is unsafe")
    _recover(direction="down")
    raw = bind.connection.driver_connection
    enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    try:
        raw.commit(); raw.execute("PRAGMA foreign_keys=OFF")
        if "owner_id" in {c["name"] for c in sa.inspect(bind).get_columns("backtest_results")}:
            _rebuild("backtest_results", LEGACY_RESULT_DDL, LEGACY_RESULT_COLUMNS,
                     LEGACY_RESULT_COLUMNS, direction="down")
        if "owner_id" in {c["name"] for c in sa.inspect(bind).get_columns("backtest_runs")}:
            _rebuild("backtest_runs", LEGACY_RUN_DDL, LEGACY_RUN_COLUMNS,
                     LEGACY_RUN_COLUMNS, direction="down")
        for table in TABLES:
            _create_indexes(table, table, direction="down", temporary=False)
        if PROOF_TABLE in _names():
            op.execute(sa.text(f"DROP TABLE {PROOF_TABLE}"))
    finally:
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")
