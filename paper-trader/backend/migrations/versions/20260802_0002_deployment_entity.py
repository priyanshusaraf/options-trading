"""deployment entity: deployments table + deployment_id on every executed row

Revision ID: 0002
Revises: 0001
Created: 2026-08-02

Phase B. Introduces `deployments` and attributes every row that represents an
execution — positions, trades, equity snapshots, signal events, order journal —
to one.

Behaviour preservation is the whole design here:

  * The legacy deployment (id=1) is seeded with `universe_mode='legacy'`,
    `strategy_key=NULL` and `allocation=NULL`, which together mean "resolve exactly
    as before". Nothing reads it differently from the way the system already worked.

  * `deployment_id` lands NOT NULL with `server_default='1'`. That default is what
    makes this additive rather than disruptive: an INSERT that predates any
    knowledge of deployments still succeeds and still lands in the legacy book.
    Call sites are taught to set it explicitly, but none of them *must* be for the
    database to stay consistent.

  * Existing rows are backfilled to 1 before the NOT NULL goes on. They were all
    executed by the one implicit book, so this is a statement of fact, not a guess.

The column is added with a plain ADD COLUMN rather than `batch_alter_table`.
Batch mode rebuilds the table (create-copy-drop-rename), and `positions`/`trades`
are the money record on a live 1GB box: a plain ADD COLUMN with a DEFAULT is
O(1) in SQLite and cannot half-copy. Batch mode is available and will be used the
first time something genuinely needs it (a rename, a type change) — it is not
needed to append a defaulted column.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Tables that record something the system EXECUTED, and therefore something a
# deployment is answerable for. Deliberately excludes reference/config tables
# (universe_instruments, runtime_config, instrument_state, earnings_events,
# option_data) — those describe the platform, not a book, and attributing them to a
# deployment would be a lie that later code would have to reason about.
EXECUTED_ROW_TABLES = (
    "positions",
    "trades",
    "equity_snapshots",
    "signal_events",
    "order_journal",
)


def upgrade() -> None:
    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("strategy_key", sa.String(64), nullable=True),
        sa.Column("strategy_version", sa.String(64), nullable=True),
        sa.Column("account_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("universe_mode", sa.String(16), nullable=False, server_default="legacy"),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id"),
                  nullable=True),
        sa.Column("params_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("allocation", sa.Float(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("armed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("halted_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Seed the legacy book. INSERT OR IGNORE because init_db also seeds it: whichever
    # runs first wins and the other is a no-op, so boot order cannot produce a
    # duplicate or a missing row.
    op.execute(
        "INSERT OR IGNORE INTO deployments "
        "(id, name, strategy_key, strategy_version, account_id, universe_mode, "
        " watchlist_id, params_json, allocation, status, armed, halted_on, notes, "
        " created_at, updated_at) "
        "VALUES (1, 'default', NULL, NULL, 'default', 'legacy', NULL, '{}', NULL, "
        "        'active', 0, NULL, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    for table in EXECUTED_ROW_TABLES:
        op.add_column(table, sa.Column("deployment_id", sa.Integer(), nullable=False,
                                       server_default="1"))
        # Existing rows already carry 1 via the DEFAULT, but state it explicitly:
        # the backfill is the claim being made (these rows belong to the legacy
        # book), and it must not depend on how the DEFAULT happened to apply.
        op.execute(f"UPDATE {table} SET deployment_id = 1 WHERE deployment_id IS NULL")
        op.create_index(f"ix_{table}_deployment_id", table, ["deployment_id"])


def downgrade() -> None:
    for table in EXECUTED_ROW_TABLES:
        op.drop_index(f"ix_{table}_deployment_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("deployment_id")
    op.drop_table("deployments")
