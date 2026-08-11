"""tenancy roots and account-scoped singleton money state

Revision ID: 0018
Revises: 0017
Created: 2026-08-11

The three rebuilt money tables deliberately keep their historic payload columns intact. Their
old singleton addresses are replaced in the same operation, so a second customer may hold the
same book, instrument, or calendar day without sharing a ledger row.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "owner"
LEGACY_USER_ID = "owner-user"
LEGACY_BROKER_ACCOUNT_ID = "account.default"
# `capital_state.book` is VARCHAR(8).  This is intentionally a durable address rather
# than NULL because the rebuilt composite primary key cannot contain NULL.
LEGACY_UNATTRIBUTED_BOOK = "legacy"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("organization_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_organizations_status"),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("email_normalized", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    )
    op.create_table(
        "memberships",
        sa.Column("organization_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')",
                           name="ck_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'invited', 'revoked')",
                           name="ck_memberships_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "broker_accounts",
        sa.Column("broker_account_id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker", sa.String(32), nullable=False),
        sa.Column("external_account_id", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_id", "broker", "external_account_id",
                            name="uq_broker_accounts_owner_broker_external"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_broker_accounts_status"),
    )
    op.create_index("ix_broker_accounts_owner_id", "broker_accounts", ["owner_id"])

    now = "CURRENT_TIMESTAMP"
    op.execute(sa.text(
        "INSERT INTO organizations (organization_id, name, status, created_at, updated_at) "
        f"VALUES ('{LEGACY_OWNER_ID}', 'Legacy owner', 'active', {now}, {now})"))
    op.execute(sa.text(
        "INSERT INTO users (user_id, email_normalized, display_name, status, created_at, updated_at) "
        f"VALUES ('{LEGACY_USER_ID}', 'owner@legacy.local', 'Legacy owner', 'active', {now}, {now})"))
    op.execute(sa.text(
        "INSERT INTO memberships (organization_id, user_id, role, status, created_at, updated_at) "
        f"VALUES ('{LEGACY_OWNER_ID}', '{LEGACY_USER_ID}', 'owner', 'active', {now}, {now})"))
    op.execute(sa.text(
        "INSERT INTO broker_accounts "
        "(broker_account_id, owner_id, broker, external_account_id, display_name, status, created_at, updated_at) "
        f"VALUES ('{LEGACY_BROKER_ACCOUNT_ID}', '{LEGACY_OWNER_ID}', 'legacy', 'default', "
        f"'Default account', 'active', {now}, {now})"))

    # SQLite cannot alter a primary key. Copy every payload field explicitly: SELECT * would
    # make an added column's position part of the migration contract and risks silent drift.
    op.execute(sa.text("""
        CREATE TABLE capital_state__0018 (
            id INTEGER UNIQUE,
            broker_account_id VARCHAR(64) NOT NULL DEFAULT 'account.default',
            book VARCHAR(8) NOT NULL DEFAULT 'live',
            initial_capital FLOAT NOT NULL,
            cash FLOAT NOT NULL,
            realized_pnl FLOAT NOT NULL,
            account_baseline FLOAT,
            anchored_at DATETIME,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (broker_account_id, book)
        )
    """))
    op.execute(sa.text(f"""
        INSERT INTO capital_state__0018
        (id, broker_account_id, book, initial_capital, cash, realized_pnl, account_baseline, anchored_at, updated_at)
        SELECT id, '{LEGACY_BROKER_ACCOUNT_ID}', COALESCE(book, '{LEGACY_UNATTRIBUTED_BOOK}'), initial_capital, cash,
               realized_pnl, account_baseline, anchored_at, updated_at
        FROM capital_state
    """))
    op.execute(sa.text("DROP TABLE capital_state"))
    op.execute(sa.text("ALTER TABLE capital_state__0018 RENAME TO capital_state"))

    op.execute(sa.text("""
        CREATE TABLE instrument_state__0018 (
            owner_id VARCHAR(64) NOT NULL DEFAULT 'owner',
            instrument_key VARCHAR(32) NOT NULL,
            enabled BOOLEAN NOT NULL,
            live_interval VARCHAR(12) NOT NULL,
            entries_blocked BOOLEAN NOT NULL,
            strategy_key VARCHAR(64),
            priority_flag BOOLEAN NOT NULL,
            product VARCHAR(16) NOT NULL,
            overtrade_flag BOOLEAN NOT NULL,
            params_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (owner_id, instrument_key)
        )
    """))
    op.execute(sa.text(f"""
        INSERT INTO instrument_state__0018
        (owner_id, instrument_key, enabled, live_interval, entries_blocked, strategy_key,
         priority_flag, product, overtrade_flag, params_json)
        SELECT '{LEGACY_OWNER_ID}', instrument_key, enabled, live_interval, entries_blocked,
               strategy_key, priority_flag, product, overtrade_flag, params_json
        FROM instrument_state
    """))
    op.execute(sa.text("DROP TABLE instrument_state"))
    op.execute(sa.text("ALTER TABLE instrument_state__0018 RENAME TO instrument_state"))

    op.execute(sa.text("""
        CREATE TABLE daily_account_snapshot__0018 (
            broker_account_id VARCHAR(64) NOT NULL DEFAULT 'account.default',
            day VARCHAR(10) NOT NULL,
            account_net FLOAT NOT NULL,
            account_available FLOAT NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (broker_account_id, day)
        )
    """))
    op.execute(sa.text(f"""
        INSERT INTO daily_account_snapshot__0018
        (broker_account_id, day, account_net, account_available, updated_at)
        SELECT '{LEGACY_BROKER_ACCOUNT_ID}', day, account_net, account_available, updated_at
        FROM daily_account_snapshot
    """))
    op.execute(sa.text("DROP TABLE daily_account_snapshot"))
    op.execute(sa.text("ALTER TABLE daily_account_snapshot__0018 RENAME TO daily_account_snapshot"))


def downgrade() -> None:
    bind = op.get_bind()
    # Dropping tenant roots is reversible only while this revision's single legacy
    # compatibility root is the *only* root.  A later customer must never disappear
    # merely because an operator asks Alembic to walk backwards.
    root_counts = {
        "organizations": ("organization_id", LEGACY_OWNER_ID),
        "users": ("user_id", LEGACY_USER_ID),
        "broker_accounts": ("broker_account_id", LEGACY_BROKER_ACCOUNT_ID),
    }
    for table, (key, legacy_id) in root_counts.items():
        if bind.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE {key} != :legacy_id LIMIT 1"
        ), {"legacy_id": legacy_id}).scalar() is not None:
            raise RuntimeError(
                f"tenancy downgrade refused: non-legacy {table} root would be lost")
    if bind.execute(sa.text(
        "SELECT 1 FROM memberships WHERE organization_id != :organization_id "
        "OR user_id != :user_id LIMIT 1"
    ), {"organization_id": LEGACY_OWNER_ID, "user_id": LEGACY_USER_ID}).scalar() is not None:
        raise RuntimeError("tenancy downgrade refused: non-legacy membership would be lost")
    collisions = {
        "capital_state": "book",
        "instrument_state": "instrument_key",
        "daily_account_snapshot": "day",
    }
    for table, old_key in collisions.items():
        if bind.execute(sa.text(
            f"SELECT 1 FROM {table} GROUP BY {old_key} HAVING COUNT(*) > 1 LIMIT 1"
        )).scalar() is not None:
            raise RuntimeError(
                f"lossy downgrade refused: multiple account-scoped {table} rows share old key {old_key}")

    # A later downgrade can refuse after this revision completed. SQLite DDL is not
    # transactionally reversible in that path, so clean only a prior failed attempt's
    # transient tables before retrying; never touch a live table here.
    for temporary in ("capital_state__0017", "instrument_state__0017",
                      "daily_account_snapshot__0017"):
        op.execute(sa.text(f"DROP TABLE IF EXISTS {temporary}"))

    op.execute(sa.text("""
        CREATE TABLE capital_state__0017 (
            id INTEGER PRIMARY KEY,
            book VARCHAR(8), initial_capital FLOAT NOT NULL, cash FLOAT NOT NULL,
            realized_pnl FLOAT NOT NULL DEFAULT 0, account_baseline FLOAT,
            anchored_at DATETIME, updated_at DATETIME NOT NULL
        )
    """))
    op.execute(sa.text("""
        INSERT INTO capital_state__0017
        (id, book, initial_capital, cash, realized_pnl, account_baseline, anchored_at, updated_at)
        SELECT id, CASE WHEN book = 'legacy' THEN NULL ELSE book END,
               initial_capital, cash, realized_pnl, account_baseline, anchored_at, updated_at
        FROM capital_state
    """))
    op.execute(sa.text("DROP TABLE capital_state"))
    op.execute(sa.text("ALTER TABLE capital_state__0017 RENAME TO capital_state"))
    op.execute(sa.text("CREATE UNIQUE INDEX uq_capital_state_book ON capital_state (book) WHERE book IS NOT NULL"))

    op.execute(sa.text("""
        CREATE TABLE instrument_state__0017 (
            instrument_key VARCHAR(32) PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT 1,
            live_interval VARCHAR(12) NOT NULL DEFAULT '15minute', entries_blocked BOOLEAN NOT NULL DEFAULT 0,
            strategy_key VARCHAR(64), priority_flag BOOLEAN NOT NULL DEFAULT 0,
            product VARCHAR(16) NOT NULL DEFAULT 'options', overtrade_flag BOOLEAN NOT NULL DEFAULT 0,
            params_json TEXT NOT NULL DEFAULT '{}'
        )
    """))
    op.execute(sa.text("""
        INSERT INTO instrument_state__0017
        (instrument_key, enabled, live_interval, entries_blocked, strategy_key, priority_flag,
         product, overtrade_flag, params_json)
        SELECT instrument_key, enabled, live_interval, entries_blocked, strategy_key, priority_flag,
               product, overtrade_flag, params_json FROM instrument_state
    """))
    op.execute(sa.text("DROP TABLE instrument_state"))
    op.execute(sa.text("ALTER TABLE instrument_state__0017 RENAME TO instrument_state"))

    op.execute(sa.text("""
        CREATE TABLE daily_account_snapshot__0017 (
            day VARCHAR(10) PRIMARY KEY, account_net FLOAT NOT NULL DEFAULT 0,
            account_available FLOAT NOT NULL DEFAULT 0, updated_at DATETIME NOT NULL
        )
    """))
    op.execute(sa.text("""
        INSERT INTO daily_account_snapshot__0017 (day, account_net, account_available, updated_at)
        SELECT day, account_net, account_available, updated_at FROM daily_account_snapshot
    """))
    op.execute(sa.text("DROP TABLE daily_account_snapshot"))
    op.execute(sa.text("ALTER TABLE daily_account_snapshot__0017 RENAME TO daily_account_snapshot"))

    op.drop_table("broker_accounts")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
