"""the execution book on capital_state and equity_snapshots (L1.3B)

`positions.mode` and `trades.mode` already named the book. `capital_state` and
`equity_snapshots` did not, and that is why this slice needed a migration rather than only
call-site changes: `capital_state.cash` and `capital_state.realized_pnl` are aggregates
mutated in place on one row, so no `WHERE` clause could stop a paper fill debiting the live
ledger. A predicate cannot partition a number; only a row per book can.

Both columns are added NULL and **nothing is back-stamped**. On `capital_state`, NULL means
"the single pre-slice ledger, not yet attributed"; `core/execution_book.capital_for_book`
attributes it exactly once, from the `mode` already stamped on the money rows that ledger
produced, and refuses if both books hold rows. On `equity_snapshots`, NULL means "recorded
before the books were separated" and stays readable rather than being rewritten — the same
posture ADR 0012 §4.1b took with historical attribution.

The partial unique index is what makes the claim safe to repeat: two rows for one book
would split a ledger in half silently. It is partial so the unclaimed legacy row is exempt.

**Why the index and not a CHECK.** ADR 0012 §3.1a prefers a schema constraint to a runtime
one, and `ir_shadow_deployments` got CHECKs because `create_table` can carry them. Adding
one to an *existing* SQLite table needs a table rebuild, and alembic's batch rebuild is not
safe here: pysqlite does not open a transaction for DDL, so a rebuild left behind by a
downgrade that raises is still there on the retry (`_alembic_tmp_capital_state already
exists`). The structural lock that matters is the one kept — two rows for one book is the
failure that silently splits a ledger; an unrecognised *value* in the column cannot arise,
because `capital_for_book` is the only writer and refuses anything outside `BOOKS`.

Revision ID: 0012
Revises: 0011
Created: 2026-08-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("capital_state", sa.Column("book", sa.String(8), nullable=True))
    op.create_index("uq_capital_state_book", "capital_state", ["book"], unique=True,
                    sqlite_where=sa.text("book IS NOT NULL"))

    op.add_column("equity_snapshots", sa.Column("book", sa.String(8), nullable=True))
    op.create_index("ix_equity_snapshots_book", "equity_snapshots", ["book"])


def downgrade() -> None:
    # Idempotent, matching 0010/0011: an aborted downgrade must not leave `head`
    # unreachable because an index it already dropped is gone.
    from alembic import context

    bind = op.get_bind() if context.is_offline_mode() is False else None
    if bind is None:
        op.drop_index("ix_equity_snapshots_book", table_name="equity_snapshots")
        op.drop_column("equity_snapshots", "book")
        op.drop_index("uq_capital_state_book", table_name="capital_state")
        op.drop_column("capital_state", "book")
        return

    inspector = sa.inspect(bind)
    for table, index in (("equity_snapshots", "ix_equity_snapshots_book"),
                         ("capital_state", "uq_capital_state_book")):
        if index in {i["name"] for i in inspector.get_indexes(table)}:
            op.drop_index(index, table_name=table)
        if "book" in {c["name"] for c in inspector.get_columns(table)}:
            op.drop_column(table, "book")
