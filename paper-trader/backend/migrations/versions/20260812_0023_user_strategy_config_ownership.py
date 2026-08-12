"""Own strategy configuration by organization.

Revision ID: 0023
Revises: 0022
"""
from __future__ import annotations

import re
import hashlib
import json
import sqlalchemy as sa
from alembic import op


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "owner"
TABLES = ("watchlists", "watchlist_membership", "strategy_lifecycle",
          "generated_strategies", "runtime_config", "deployments")
PROOF_TABLE = "_strategy_config_0023_rebuild_proofs"


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _foreign_keys_enabled() -> bool:
    return bool(op.get_bind().connection.driver_connection.execute(
        "PRAGMA foreign_keys").fetchone()[0])


def _foreign_keys(enabled: bool) -> None:
    raw = op.get_bind().connection.driver_connection
    raw.commit()
    raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _recover() -> None:
    """A source wins over an incomplete temp; a completed temp is never guessed at."""
    names = _names()
    # Validate every completed source-absent temp before promoting any of them. A later
    # malformed proof must never leave an earlier table promoted in the same retry.
    for table in TABLES:
        temp = f"{table}__0023"
        if table not in names and temp in names:
            _prove_temp(table, temp)
    for table in TABLES:
        temp = f"{table}__0023"
        if table in names and temp in names:
            op.execute(sa.text(f"DROP TABLE {temp}"))
            if PROOF_TABLE in names:
                op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})
        elif table not in names and temp in names:
            op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
            op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _rows_proof(table: str) -> tuple[int, str]:
    rows = op.get_bind().execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()
    body = json.dumps([list(row) for row in rows], default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(body.encode()).hexdigest()


def _schema_digest(table: str) -> str:
    """Digest the complete SQLite table contract, not merely its copied rows."""
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=:table "
        "AND type IN ('table','index','trigger') ORDER BY type,name"), {"table": table}).all()
    canonical = "\n".join(
        f"{row.type}:{row.name}:" + " ".join((row.sql or "").replace(
            table, "__TABLE__").replace('"', '').replace('`', '').split()).lower()
        for row in rows
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _query_proof(query: str) -> tuple[int, str]:
    rows = op.get_bind().execute(sa.text(query)).all()
    body = json.dumps([list(row) for row in rows], default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(body.encode()).hexdigest()


def _ensure_proofs() -> None:
    op.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {PROOF_TABLE} ("
                       "table_name VARCHAR(64) PRIMARY KEY, row_count INTEGER NOT NULL, "
                       "row_digest VARCHAR(64) NOT NULL, direction VARCHAR(8) NOT NULL, "
                       "schema_digest VARCHAR(64) NOT NULL)"))


def _write_proof(table: str, temp: str, *, expected_schema_digest: str) -> None:
    _ensure_proofs()
    count, digest = _rows_proof(temp)
    if _schema_digest(temp) != expected_schema_digest:
        raise RuntimeError(f"0023 target schema proof failed for {table}")
    op.get_bind().execute(
        sa.text(f"INSERT OR REPLACE INTO {PROOF_TABLE} VALUES (:table,:count,:digest,'up',:schema_digest)"),
        {"table": table, "count": count, "digest": digest,
         "schema_digest": expected_schema_digest})


def _prove_temp(table: str, temp: str) -> None:
    if PROOF_TABLE not in _names():
        raise RuntimeError(f"0023 refuses unproven completed rebuild for {table}")
    proof = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest,direction,schema_digest FROM {PROOF_TABLE} WHERE table_name=:table"),
        {"table": table}).one_or_none()
    if proof is None or proof.direction != "up" or _rows_proof(temp) != (proof.row_count, proof.row_digest) \
            or _schema_digest(temp) != proof.schema_digest:
        raise RuntimeError(f"0023 refuses malformed completed rebuild for {table}")


def _rebuild(table: str, ddl: str, columns: str, select: str) -> None:
    temp = f"{table}__0023"
    expected = _query_proof(f"SELECT {select} FROM {table} ORDER BY rowid")
    op.execute(sa.text(ddl.replace("__TABLE__", temp)))
    expected_schema_digest = _schema_digest(temp)
    op.execute(sa.text(f"INSERT INTO {temp} ({columns}) SELECT {select} FROM {table}"))
    if _rows_proof(temp) != expected:
        raise RuntimeError(f"0023 source-bound payload proof failed for {table}")
    _write_proof(table, temp, expected_schema_digest=expected_schema_digest)
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temp} RENAME TO {table}"))
    op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _upgrade() -> None:
    owned = lambda table: "owner_id" in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}
    if not owned("watchlists"):
        _rebuild("watchlists", """CREATE TABLE __TABLE__ (
        id INTEGER NOT NULL PRIMARY KEY, owner_id VARCHAR(64) NOT NULL,
        name VARCHAR(64) NOT NULL, strategy_key VARCHAR(64) NOT NULL,
        status VARCHAR(12) NOT NULL, interval VARCHAR(12), notes TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        CONSTRAINT uq_watchlists_owner_name UNIQUE(owner_id,name),
        CONSTRAINT uq_watchlists_owner_id UNIQUE(owner_id,id),
        FOREIGN KEY(owner_id) REFERENCES organizations(organization_id) ON DELETE RESTRICT)""",
        "id,owner_id,name,strategy_key,status,interval,notes,created_at",
        f"id,'{LEGACY_OWNER_ID}',name,strategy_key,status,interval,notes,created_at")
    if not owned("watchlist_membership"):
        _rebuild("watchlist_membership", """CREATE TABLE __TABLE__ (
        owner_id VARCHAR(64) NOT NULL, instrument_key VARCHAR(48) NOT NULL,
        watchlist_id INTEGER NOT NULL, added_at DATETIME NOT NULL,
        PRIMARY KEY(owner_id,instrument_key),
        CONSTRAINT fk_watchlist_membership_owner_watchlist FOREIGN KEY(owner_id,watchlist_id)
          REFERENCES watchlists(owner_id,id) ON DELETE RESTRICT)""",
        "owner_id,instrument_key,watchlist_id,added_at",
        f"'{LEGACY_OWNER_ID}',instrument_key,watchlist_id,added_at")
    if not owned("strategy_lifecycle"):
        _rebuild("strategy_lifecycle", """CREATE TABLE __TABLE__ (
        id INTEGER NOT NULL PRIMARY KEY, owner_id VARCHAR(64) NOT NULL,
        strategy_key VARCHAR(64) NOT NULL, status VARCHAR(12) NOT NULL,
        source VARCHAR(12) NOT NULL, deployed_watchlist_id INTEGER, last_dsr FLOAT,
        note TEXT NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
        CONSTRAINT uq_strategy_lifecycle_owner_key UNIQUE(owner_id,strategy_key),
        CONSTRAINT uq_strategy_lifecycle_owner_id UNIQUE(owner_id,id),
        FOREIGN KEY(owner_id) REFERENCES organizations(organization_id) ON DELETE RESTRICT,
        CONSTRAINT fk_strategy_lifecycle_owner_watchlist FOREIGN KEY(owner_id,deployed_watchlist_id)
          REFERENCES watchlists(owner_id,id) ON DELETE RESTRICT)""",
        "id,owner_id,strategy_key,status,source,deployed_watchlist_id,last_dsr,note,created_at,updated_at",
        f"id,'{LEGACY_OWNER_ID}',strategy_key,status,source,deployed_watchlist_id,last_dsr,note,created_at,updated_at")
    if not owned("generated_strategies"):
        _rebuild("generated_strategies", """CREATE TABLE __TABLE__ (
        owner_id VARCHAR(64) NOT NULL, key VARCHAR(64) NOT NULL, version VARCHAR(64),
        composition_json TEXT NOT NULL, source TEXT NOT NULL, created_at DATETIME NOT NULL,
        PRIMARY KEY(owner_id,key), FOREIGN KEY(owner_id) REFERENCES organizations(organization_id) ON DELETE RESTRICT)""",
        "owner_id,key,version,composition_json,source,created_at",
        f"'{LEGACY_OWNER_ID}',key,version,composition_json,source,created_at")
    if not owned("runtime_config"):
        _rebuild("runtime_config", """CREATE TABLE __TABLE__ (
        owner_id VARCHAR(64) NOT NULL, key VARCHAR(64) NOT NULL, value VARCHAR(64) NOT NULL,
        updated_at DATETIME NOT NULL, PRIMARY KEY(owner_id,key),
        FOREIGN KEY(owner_id) REFERENCES organizations(organization_id) ON DELETE RESTRICT)""",
        "owner_id,key,value,updated_at", f"'{LEGACY_OWNER_ID}',key,value,updated_at")

    # Deployment is MONEY. Keep its exact values and owner but deliberately remove the
    # forbidden cross-plane watchlist foreign key. SQLite's own catalogue is the only
    # authoritative list of historical deployment columns, so preserve it mechanically.
    deployment_has_fk = any(foreign_key["constrained_columns"] == ["watchlist_id"]
                            for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("deployments"))
    if deployment_has_fk:
        # Migration-local target contract. Do not derive target DDL from the source: that
        # would preserve a named cross-plane FK or historical column order forever.
        op.execute(sa.text("""CREATE TABLE deployments__0023 (
            owner_id VARCHAR(64) NOT NULL, id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(64) NOT NULL, strategy_key VARCHAR(64), strategy_version VARCHAR(64),
            broker_account_id VARCHAR(64) NOT NULL, universe_mode VARCHAR(16) NOT NULL DEFAULT 'legacy',
            watchlist_id INTEGER, params_json TEXT NOT NULL DEFAULT '{}', allocation FLOAT,
            status VARCHAR(12) NOT NULL DEFAULT 'active', armed BOOLEAN NOT NULL DEFAULT '0',
            halted_on DATE, notes TEXT NOT NULL DEFAULT '', created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CONSTRAINT uq_deployments_owner_name UNIQUE(owner_id,name),
            FOREIGN KEY(broker_account_id) REFERENCES broker_accounts(broker_account_id))"""))
        expected_schema_digest = _schema_digest("deployments__0023")
        source_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("deployments")}
        target_columns = ("owner_id,id,name,strategy_key,strategy_version,broker_account_id,universe_mode,"
                          "watchlist_id,params_json,allocation,status,armed,halted_on,notes,created_at,updated_at")
        if set(target_columns.split(",")) != source_columns:
            raise RuntimeError("0023 deployment source columns differ from the migration contract")
        expected = _query_proof(f"SELECT {target_columns} FROM deployments ORDER BY rowid")
        op.execute(sa.text(f"INSERT INTO deployments__0023 ({target_columns}) SELECT {target_columns} FROM deployments"))
        if _rows_proof("deployments__0023") != expected:
            raise RuntimeError("0023 source-bound payload proof failed for deployments")
        _write_proof("deployments", "deployments__0023",
                     expected_schema_digest=expected_schema_digest)
        op.execute(sa.text("DROP TABLE deployments"))
        op.execute(sa.text("ALTER TABLE deployments__0023 RENAME TO deployments"))
        op.execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name='deployments'"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_deployments_owner_id ON deployments(owner_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_deployments_owner_account ON deployments(owner_id,broker_account_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_watchlist_membership_owner_watchlist ON watchlist_membership(owner_id,watchlist_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_watchlists_owner_id ON watchlists(owner_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_strategy_lifecycle_owner_id ON strategy_lifecycle(owner_id)"))
    if PROOF_TABLE in _names() and op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {PROOF_TABLE}")).scalar_one() == 0:
        op.execute(sa.text(f"DROP TABLE {PROOF_TABLE}"))


def upgrade() -> None:
    _recover()
    enabled = _foreign_keys_enabled()
    try:
        _foreign_keys(False)
        _upgrade()
        bad = op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).all()
        if bad:
            raise RuntimeError(f"0023 foreign-key validation failed: {bad!r}")
    finally:
        _foreign_keys(enabled)


def downgrade() -> None:
    # Removing the deployment relation is an architectural direction, not a reversible
    # schema tweak. Refuse before changing FK mode or DDL; rows remain byte-for-byte intact.
    raise RuntimeError("0023 downgrade refused: restoring the forbidden MONEY-to-USER watchlist FK is unsafe")
