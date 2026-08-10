"""an owner on the money plane

Revision ID: 0017
Revises: 0016
Created: 2026-08-11

Additive. Ten columns, ten indexes, no existing value rewritten — the money record is not
touched.

**What this closes.** Before `0015` nothing in this database recorded whose anything was.
`0015` gave `broker_connections` an owner and `0016` gave `execution_intents` one, which made
*the authority to trade* per-owner. What the orders PRODUCE was still global: a second owner
would have shared the first owner's positions, trades, order journal and equity curve. The
tenancy rule states the shape — ownership is a dimension on the object, not a filter in a route
— and this applies it to the plane where being wrong costs money rather than privacy.

**`server_default='owner'`, matching 0015 and 0016.** Every pre-existing row WAS the original
owner's; that is a fact, not a guess. NULL would make "belongs to the owner" indistinguishable
from "we lost track of whose this is" on rows that record real fills, and this database holds a
live book.

**Every column is indexed** because each one joins a WHERE clause on a table that grows per
trade, per bar or per poll. `positions` and `trades` are read on the risk lane, and hard
invariant 2 says nothing may block an exit.

**THREE MONEY-PLANE TABLES ARE DELIBERATELY ABSENT**, and this is the load-bearing part of this
docstring. `capital_state`, `instrument_state` and `daily_account_snapshot` are keyed so that
only one row can exist per book, per instrument and per day respectively:

    capital_state           UNIQUE(book)  — a second owner's `live` book violates it
    instrument_state        PK(instrument_key)
    daily_account_snapshot  PK(day)

An `owner_id` column on those three would exist, be indexed, be non-null, and be **incapable of
expressing two owners**, because the key above it still says one row. That is this codebase's
defining defect — a mechanism that is correct, tested, and wired to nothing — and adding the
column "for consistency" would plant it in the money plane with a docstring claiming tenancy.
Making them per-owner is a PRIMARY KEY change: not additive, it rewrites the identity of rows in
the money record, and it needs its own slice with its own restore path. Until that slice lands,
those three tables are single-owner and the system is not multi-tenant on capital state.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

#: Ten of the fifteen money-plane tables. The other five: `broker_connections` (0015) and
#: `execution_intents` (0016) already have it; `capital_state`, `instrument_state` and
#: `daily_account_snapshot` cannot take it additively — see the module docstring.
TABLES: tuple[str, ...] = (
    "deployments",
    "positions",
    "trades",
    "order_journal",
    "equity_snapshots",
    "signal_events",
    "execution_order_events",
    "ir_shadow_divergences",
    "ir_shadow_deployments",
    "ir_paper_deployments",
)


def _index_name(table: str) -> str:
    return f"ix_{table}_owner_id"


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("owner_id", sa.String(64), nullable=False, server_default="owner"),
        )
        op.create_index(_index_name(table), table, ["owner_id"])


def downgrade() -> None:
    """Rerunnable, matching revisions 0010–0016.

    A downgrade chain that fails at a later revision leaves this one already applied, and the
    rollback of the enclosing transaction does not reliably restore dropped objects — so the
    operator's second attempt would hit `no such index` and the chain would stick half-down.
    Ten tables make that failure ten times more likely, not less.
    """
    bind = op.get_bind()
    if bind is None:                                  # offline / --sql mode
        for table in TABLES:
            op.drop_index(_index_name(table), table_name=table)
            op.drop_column(table, "owner_id")
        return
    inspector = sa.inspect(bind)
    for table in TABLES:
        if not inspector.has_table(table):
            continue
        if any(ix["name"] == _index_name(table) for ix in inspector.get_indexes(table)):
            op.drop_index(_index_name(table), table_name=table)
        if any(c["name"] == "owner_id" for c in inspector.get_columns(table)):
            op.drop_column(table, "owner_id")
