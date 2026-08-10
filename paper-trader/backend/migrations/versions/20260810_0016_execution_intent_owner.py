"""an owner on every execution intent

Revision ID: 0016
Revises: 0015
Created: 2026-08-10

Additive. One column, one index, no existing value rewritten — the money record is not touched.

**Why this is not cosmetic.** `ExecutionLifecycleStore.unresolved_entries` decides which
unresolved LIVE entries a restarting broker may adopt, and it matched on
`(deployment_id, account_scope, connection_scope)` with no owner and no broker. Two independent
reviews found the same gap on 2026-08-10. Migration `0015` made it expressible: it scoped
`broker_connections` uniqueness to `(owner_id, scope)` — deliberately, so two owners may each
hold a `kite:legacy` connection — which is exactly the collision the recovery query could not
then disambiguate. The constraint that permits the collision shipped one revision before the
column that resolves it, which is the wrong order and is corrected here.

`server_default='owner'` rather than NULL, matching `broker_connections`. Every pre-existing
intent WAS the original owner's; that is a fact, not a guess, and recording it as NULL would
make "belongs to the owner" indistinguishable from "we lost track of whose this is" on rows that
record real orders.

The column is indexed because it joins the recovery query's WHERE clause, which runs on every
engine start against a growing table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_intents",
        sa.Column("owner_id", sa.String(64), nullable=False, server_default="owner"),
    )
    op.create_index("ix_execution_intents_owner_id", "execution_intents", ["owner_id"])


def downgrade() -> None:
    """Rerunnable, matching revisions 0010–0015.

    A downgrade chain that fails at a later revision leaves this one already applied, and the
    rollback of the enclosing transaction does not reliably restore the dropped objects — so the
    operator's second attempt would hit `no such index` and the chain would stick half-down.
    """
    bind = op.get_bind()
    if bind is None:                                  # offline / --sql mode
        op.drop_column("execution_intents", "owner_id")
        return
    inspector = sa.inspect(bind)
    if not inspector.has_table("execution_intents"):
        return
    if any(ix["name"] == "ix_execution_intents_owner_id"
           for ix in inspector.get_indexes("execution_intents")):
        op.drop_index("ix_execution_intents_owner_id", table_name="execution_intents")
    if any(c["name"] == "owner_id"
           for c in inspector.get_columns("execution_intents")):
        op.drop_column("execution_intents", "owner_id")
