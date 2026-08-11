"""account-scope every money repository

Revision ID: 0019
Revises: 0018
Created: 2026-08-11

The durable broker-account id is separate from broker/external observation strings.  Every
legacy row is copied onto the account root created by 0018.  SQLite rebuilds are explicit at
the Alembic batch boundary so payload columns and constraints survive the identity change.
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "owner"
LEGACY_BROKER_ACCOUNT_ID = "account.default"

ACCOUNT_TABLES: tuple[str, ...] = (
    "positions",
    "trades",
    "equity_snapshots",
    "order_journal",
    "signal_events",
    "execution_intents",
    "execution_order_events",
    "broker_connections",
    "ir_paper_deployments",
    "ir_shadow_deployments",
    "ir_shadow_divergences",
)

SQLITE_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _account_index(table: str) -> str:
    return f"ix_{table}_owner_account"


def _account_fk(table: str) -> str:
    return f"fk_{table}_broker_account_id_broker_accounts"


def _foreign_keys(enabled: bool) -> None:
    """Toggle SQLite FK enforcement outside a transaction for dependency-safe rebuilds."""
    bind = op.get_bind()
    raw = bind.connection.driver_connection
    # SQLite ignores this pragma inside a transaction.  Alembic is handed an existing
    # connection by the application, so end only the DBAPI transaction while keeping the
    # SQLAlchemy/Alembic connection identity stable.
    raw.commit()
    raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _recreate_event_guards() -> None:
    for trigger_name, operation in (
        ("execution_order_events_refuse_update", "UPDATE"),
        ("execution_order_events_refuse_delete", "DELETE"),
    ):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER {trigger_name} BEFORE {operation} "
            "ON execution_order_events BEGIN "
            "SELECT RAISE(ABORT, 'execution_order_events are immutable'); END"))


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _recover_sqlite_rebuild_temp(table: str, *, temporary: str | None = None) -> None:
    """Make retry safe after SQLite DDL commits between batch rebuild statements."""
    temporary = temporary or f"_alembic_tmp_{table}"
    names = _table_names()
    if table in names and temporary in names:
        # CREATE TEMP completed, but the original table remains authoritative.
        op.execute(sa.text(f"DROP TABLE {temporary}"))
    elif table not in names and temporary in names:
        # DROP original completed before RENAME TEMP; its rows and rebuilt shape are intact.
        op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _restore_account_index(table: str) -> None:
    op.execute(sa.text(
        f"CREATE INDEX IF NOT EXISTS {_account_index(table)} "
        f"ON {table} (owner_id, broker_account_id)"))


def _restore_deployment_indexes() -> None:
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_deployments_owner_id ON deployments (owner_id)"))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_deployments_owner_account "
        "ON deployments (owner_id, broker_account_id)"))


def _restore_inline_entry_fk(table: str) -> None:
    """Restore 0014's inline SQLite FK so its immutable downgrade remains runnable."""
    bind = op.get_bind()
    ddl = bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"
    ), {"table": table}).scalar_one()
    indexes = [row[0] for row in bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:table "
        "AND sql IS NOT NULL ORDER BY name"
    ), {"table": table})]
    temporary = f"{table}__inline0018"
    ddl = re.sub(
        rf'^CREATE TABLE\s+"?{re.escape(table)}"?',
        f"CREATE TABLE {temporary}", ddl, count=1)
    ddl = ddl.replace(
        "entry_intent_id VARCHAR(32)",
        "entry_intent_id VARCHAR(32) REFERENCES execution_intents(client_intent_id) "
        "ON DELETE RESTRICT",
        1,
    )
    # Alembic reflection renders the original inline reference as a named table-level
    # constraint during the 0019 batch rebuild.  Remove that reflected copy after putting
    # the reference back inline.  SQLite can drop an inline-reference column during the
    # immutable 0014 downgrade, but refuses when a table-level FK still names the column.
    ddl = re.sub(
        r",\s*(?:CONSTRAINT\s+\S+\s+)?FOREIGN\s+KEY\s*\(\s*entry_intent_id\s*\)"
        r"\s+REFERENCES\s+execution_intents\s*\(\s*client_intent_id\s*\)"
        r"\s+ON\s+DELETE\s+RESTRICT",
        "",
        ddl,
        count=1,
        flags=re.IGNORECASE,
    )
    op.execute(sa.text(ddl))
    op.execute(sa.text(f"INSERT INTO {temporary} SELECT * FROM {table}"))
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))
    for index_ddl in indexes:
        op.execute(sa.text(index_ddl))


def _upgrade_deployments() -> None:
    _recover_sqlite_rebuild_temp(
        "deployments", temporary="deployments__0019")
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("deployments")}
    if "broker_account_id" in columns and "account_id" not in columns:
        _restore_deployment_indexes()
        return
    op.execute(sa.text(
        "UPDATE deployments SET account_id='account.default' WHERE account_id='default'"))
    op.execute(sa.text("""
        CREATE TABLE deployments__0019 (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(64) NOT NULL,
            strategy_key VARCHAR(64),
            strategy_version VARCHAR(64),
            broker_account_id VARCHAR(64) NOT NULL DEFAULT 'account.default',
            universe_mode VARCHAR(16) NOT NULL DEFAULT 'legacy',
            watchlist_id INTEGER,
            params_json TEXT NOT NULL DEFAULT '{}',
            allocation FLOAT,
            status VARCHAR(12) NOT NULL DEFAULT 'active',
            armed BOOLEAN NOT NULL DEFAULT '0',
            halted_on DATE,
            notes TEXT NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            owner_id VARCHAR(64) NOT NULL DEFAULT 'owner',
            CONSTRAINT uq_deployments_owner_name UNIQUE (owner_id, name),
            FOREIGN KEY(watchlist_id) REFERENCES watchlists(id),
            CONSTRAINT fk_deployments_broker_account_id_broker_accounts
                FOREIGN KEY(broker_account_id) REFERENCES broker_accounts(broker_account_id)
        )
    """))
    op.execute(sa.text("""
        INSERT INTO deployments__0019
        (id,name,strategy_key,strategy_version,broker_account_id,universe_mode,watchlist_id,
         params_json,allocation,status,armed,halted_on,notes,created_at,updated_at,owner_id)
        SELECT id,name,strategy_key,strategy_version,account_id,universe_mode,watchlist_id,
               params_json,allocation,status,armed,halted_on,notes,created_at,updated_at,owner_id
        FROM deployments
    """))
    op.execute(sa.text("DROP TABLE deployments"))
    op.execute(sa.text("ALTER TABLE deployments__0019 RENAME TO deployments"))
    _restore_deployment_indexes()


def _remove_legacy_scope_defaults() -> None:
    """Backfill defaults belong to the upgrade, never to future application writes."""
    # 0018/0019 use temporary defaults while a new NOT NULL scope is backfilled.  They
    # must not survive the revision: silently assigning a future write to the legacy
    # tenant is unsafe.  Include the three singleton-identity replacements and
    # deployments, which do not belong to ACCOUNT_TABLES' account-FK rebuild loop.
    for table in (*ACCOUNT_TABLES, "deployments"):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.alter_column("broker_account_id", server_default=None)
            batch.alter_column("owner_id", server_default=None)
    with op.batch_alter_table("instrument_state", recreate="always") as batch:
        batch.alter_column("owner_id", server_default=None)
    for table in ("capital_state", "daily_account_snapshot"):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.alter_column("broker_account_id", server_default=None)


def _downgrade_deployments() -> None:
    op.execute(sa.text("""
        CREATE TABLE deployments__0018 (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(64) NOT NULL UNIQUE,
            strategy_key VARCHAR(64),
            strategy_version VARCHAR(64),
            account_id VARCHAR(64) NOT NULL DEFAULT 'default',
            universe_mode VARCHAR(16) NOT NULL DEFAULT 'legacy',
            watchlist_id INTEGER,
            params_json TEXT NOT NULL DEFAULT '{}',
            allocation FLOAT,
            status VARCHAR(12) NOT NULL DEFAULT 'active',
            armed BOOLEAN NOT NULL DEFAULT '0',
            halted_on DATE,
            notes TEXT NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            owner_id VARCHAR(64) NOT NULL DEFAULT 'owner',
            FOREIGN KEY(watchlist_id) REFERENCES watchlists(id)
        )
    """))
    op.execute(sa.text("""
        INSERT INTO deployments__0018
        (id,name,strategy_key,strategy_version,account_id,universe_mode,watchlist_id,
         params_json,allocation,status,armed,halted_on,notes,created_at,updated_at,owner_id)
        SELECT id,name,strategy_key,strategy_version,'default',universe_mode,watchlist_id,
               params_json,allocation,status,armed,halted_on,notes,created_at,updated_at,owner_id
        FROM deployments
    """))
    op.execute(sa.text("DROP TABLE deployments"))
    op.execute(sa.text("ALTER TABLE deployments__0018 RENAME TO deployments"))
    op.create_index("ix_deployments_owner_id", "deployments", ["owner_id"])


def upgrade() -> None:
    _foreign_keys(False)
    try:
        _upgrade_deployments()
        for table in ACCOUNT_TABLES:
            _recover_sqlite_rebuild_temp(table)
            if "broker_account_id" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}:
                _restore_account_index(table)
                continue
            reflect_args = ()
            if table in ("positions", "trades"):
                reflect_args = (sa.Column(
                    "entry_intent_id", sa.String(32),
                    sa.ForeignKey("execution_intents.client_intent_id", ondelete="RESTRICT")),)
            with op.batch_alter_table(
                    table, recreate="always", reflect_args=reflect_args) as batch:
                batch.add_column(sa.Column(
                    "broker_account_id", sa.String(64), nullable=False,
                    server_default=LEGACY_BROKER_ACCOUNT_ID))
                batch.create_foreign_key(
                    _account_fk(table), "broker_accounts",
                    ["broker_account_id"], ["broker_account_id"])
                batch.create_index(
                    _account_index(table), ["owner_id", "broker_account_id"])
                if table == "broker_connections":
                    batch.drop_constraint(
                        "uq_broker_connection_owner_scope", type_="unique")
                    batch.create_unique_constraint(
                        "uq_broker_connection_owner_account_scope",
                        ["owner_id", "broker_account_id", "scope"])
                if table == "ir_shadow_divergences":
                    batch.drop_index("uq_ir_shadow_divergence_bar")
                    batch.create_index("uq_ir_shadow_divergence_bar", ["owner_id", "broker_account_id", "instrument_key", "bar_time", "graph_address", "reason"], unique=True)
            _restore_account_index(table)
        _remove_legacy_scope_defaults()
        _recreate_event_guards()
    finally:
        _foreign_keys(True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    scoped_tables = ("deployments", *ACCOUNT_TABLES)
    has_account_column = {
        table: "broker_account_id" in {
            column["name"] for column in inspector.get_columns(table)}
        for table in scoped_tables
    }
    # SQLite DDL is not transactionally rolled back. A later revision can refuse a deep
    # downgrade after this revision has already rebuilt every table, while Alembic's
    # version row remains at 0019. Retrying must treat that fully-applied physical shape as
    # idempotent; a mixed shape is evidence of an interrupted rebuild and is unsafe to
    # guess through.
    if not any(has_account_column.values()):
        return
    if not all(has_account_column.values()):
        missing = sorted(table for table, present in has_account_column.items() if not present)
        raise RuntimeError(
            "money account-scope downgrade found a partially rebuilt schema; "
            f"missing broker_account_id on {missing}")
    duplicate_name = bind.execute(sa.text(
        "SELECT 1 FROM deployments GROUP BY name HAVING COUNT(*) > 1 LIMIT 1"
    )).scalar()
    if duplicate_name is not None:
        raise RuntimeError(
            "lossy downgrade refused: tenant-local deployment names would collide")
    if bind.execute(sa.text(
        "SELECT 1 FROM deployments WHERE broker_account_id != :legacy LIMIT 1"
    ), {"legacy": LEGACY_BROKER_ACCOUNT_ID}).scalar() is not None:
        raise RuntimeError(
            "lossy downgrade refused: non-legacy deployment account scope would be lost")
    for table in ACCOUNT_TABLES:
        if bind.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE broker_account_id != :legacy LIMIT 1"
        ), {"legacy": LEGACY_BROKER_ACCOUNT_ID}).scalar() is not None:
            raise RuntimeError(
                f"lossy downgrade refused: non-legacy {table} account scope would be lost")

    _foreign_keys(False)
    try:
        _downgrade_deployments()
        for table in ACCOUNT_TABLES:
            with op.batch_alter_table(
                    table, recreate="always",
                    naming_convention=SQLITE_NAMING_CONVENTION) as batch:
                if table == "broker_connections":
                    batch.drop_constraint(
                        "uq_broker_connection_owner_account_scope", type_="unique")
                    batch.create_unique_constraint(
                        "uq_broker_connection_owner_scope", ["owner_id", "scope"])
                if table == "ir_shadow_divergences":
                    batch.drop_index("uq_ir_shadow_divergence_bar")
                    batch.create_index(
                        "uq_ir_shadow_divergence_bar",
                        ["instrument_key", "bar_time", "graph_address", "reason"],
                        unique=True)
                batch.drop_index(_account_index(table))
                batch.drop_constraint(_account_fk(table), type_="foreignkey")
                batch.drop_column("broker_account_id")
        for table in ("positions", "trades"):
            _restore_inline_entry_fk(table)
        _recreate_event_guards()
    finally:
        _foreign_keys(True)
