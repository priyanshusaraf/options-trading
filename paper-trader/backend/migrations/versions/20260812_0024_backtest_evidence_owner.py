"""Own durable backtest runs and results by organization.

Revision ID: 0024
Revises: 0023
"""
from __future__ import annotations

import hashlib
import json
import re

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
 CONSTRAINT fk_backtest_results_owner_run FOREIGN KEY(owner_id, run_id)
   REFERENCES backtest_runs (owner_id, id) ON DELETE RESTRICT,
 FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT)"""

RUN_COLUMNS = "id,owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies"
RUN_SELECT = f"id,'{LEGACY_OWNER_ID}',created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies"
RESULT_COLUMNS = "id,owner_id,run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at"
RESULT_SELECT = f"id,'{LEGACY_OWNER_ID}',run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at"


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rows(query: str) -> tuple[int, str]:
    value = op.get_bind().execute(sa.text(query)).all()
    body = json.dumps([list(row) for row in value], default=str, separators=(",", ":"))
    return len(value), hashlib.sha256(body.encode()).hexdigest()


def _schema(table: str) -> str:
    sql = op.get_bind().execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"), {"table": table}
    ).scalar_one()
    # A result table names its run parent. During recovery that parent may already
    # have been promoted, so normalize every migration-local physical name rather
    # than falsely treating a SQLite rename rewrite as a different contract.
    normalized_sql = sql
    for logical in TABLES:
        normalized_sql = re.sub(re.escape(logical) + r"(?:__0024)?",
                                f"__{logical}__", normalized_sql)
    normalized = " ".join(normalized_sql.replace('"', '').replace('`', '').split()).lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _ensure_proofs() -> None:
    op.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {PROOF_TABLE} ("
                       "table_name VARCHAR(64) PRIMARY KEY, row_count INTEGER NOT NULL, "
                       "row_digest VARCHAR(64) NOT NULL, schema_digest VARCHAR(64) NOT NULL)"))


def _write_proof(table: str, temp: str) -> None:
    _ensure_proofs()
    count, digest = _rows(f"SELECT * FROM {temp} ORDER BY rowid")
    op.get_bind().execute(sa.text(f"INSERT OR REPLACE INTO {PROOF_TABLE} VALUES (:table,:count,:digest,:schema)"), {
        "table": table, "count": count, "digest": digest, "schema": _schema(temp)})


def _prove_temp(table: str, temp: str) -> None:
    if PROOF_TABLE not in _names():
        raise RuntimeError(f"0024 refuses unproven completed rebuild for {table}")
    proof = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest,schema_digest FROM {PROOF_TABLE} WHERE table_name=:table"),
        {"table": table}).one_or_none()
    if proof is None or _rows(f"SELECT * FROM {temp} ORDER BY rowid") != (proof.row_count, proof.row_digest) \
            or _schema(temp) != proof.schema_digest:
        raise RuntimeError(f"0024 refuses malformed completed rebuild for {table}")


def _recover() -> None:
    names = _names()
    # Validate every completed, source-absent or post-rename candidate before
    # changing any table. A retry must never promote one table then discover a
    # forged proof for the other.
    for table in TABLES:
        temp = f"{table}__0024"
        if table not in names and temp in names:
            _prove_temp(table, temp)
        elif table in names and temp not in names and PROOF_TABLE in names:
            proof = op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table}
            ).scalar_one_or_none()
            if proof is not None:
                _prove_temp(table, table)
    for table in TABLES:
        temp = f"{table}__0024"
        if table in names and temp in names:
            op.execute(sa.text(f"DROP TABLE {temp}"))
            if PROOF_TABLE in _names():
                op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})
        elif table not in names and temp in names:
            op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
            op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})
        elif table in names and temp not in names and PROOF_TABLE in _names():
            op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _rebuild(table: str, ddl: str, columns: str, source: str) -> None:
    temp = f"{table}__0024"
    expected = _rows(f"SELECT {source} FROM {table} ORDER BY rowid")
    op.execute(sa.text(ddl.replace("__TABLE__", temp)))
    op.execute(sa.text(f"INSERT INTO {temp} ({columns}) SELECT {source} FROM {table}"))
    if _rows(f"SELECT * FROM {temp} ORDER BY rowid") != expected:
        raise RuntimeError(f"0024 source-bound payload proof failed for {table}")
    _write_proof(table, temp)
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
    op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _indexes() -> None:
    for sql in (
        "CREATE INDEX IF NOT EXISTS ix_backtest_runs_owner_id ON backtest_runs(owner_id)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_runs_owner_created ON backtest_runs(owner_id,created_at)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_runs_owner_status ON backtest_runs(owner_id,status)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_owner_id ON backtest_results(owner_id)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_owner_run ON backtest_results(owner_id,run_id)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_owner_cache ON backtest_results(owner_id,params_hash,last_candle_ts)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_run_id ON backtest_results(run_id)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_instrument_key ON backtest_results(instrument_key)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_interval ON backtest_results(interval)",
        "CREATE INDEX IF NOT EXISTS ix_backtest_results_strategy_key ON backtest_results(strategy_key)",
    ):
        op.execute(sa.text(sql))


def upgrade() -> None:
    _recover()
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
    raise RuntimeError("0024 downgrade refused: removing owned backtest evidence loses tenant isolation")
