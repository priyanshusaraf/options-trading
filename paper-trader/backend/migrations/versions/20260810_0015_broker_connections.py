"""durable per-owner broker connections

Revision ID: 0015
Revises: 0014
Created: 2026-08-10

Additive only. No existing row is read, rewritten or backfilled — the money record is not
touched, and this migration is reversible by dropping one table.

The `owner_id` default is `'owner'` (`models.LEGACY_OWNER_ID`) rather than NULL. On a table that
grants the authority to trade, "belongs to the original owner" and "we do not know whose this is"
must never be the same value.

No foreign keys, deliberately, in either direction:

  * `execution_intents.connection_scope` references a connection BY VALUE. An intent must
    survive the deletion of the connection that authored it — a live order whose connection row
    is gone is still a live order, and a cascade or a null-out would orphan it silently.
  * ADR 0015's plane rule forbids a foreign key crossing a plane boundary, and keeping this table
    FK-free in both directions is what makes moving it later an operation rather than a rewrite.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default="owner"),
        sa.Column("broker", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("label", sa.String(80), nullable=False, server_default=""),
        sa.Column("capabilities_json", sa.Text(), nullable=False, server_default="[]"),
        # Nullable: a connection created but never authenticated is a real state, and it is
        # distinguishable from an empty credential.
        sa.Column("credential_ciphertext", sa.Text(), nullable=True),
        sa.Column("credential_key_id", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        # Per OWNER, not global: two owners may each hold a `kite:legacy` connection and they
        # are different connections. This is what makes the tenancy dimension real.
        sa.UniqueConstraint("owner_id", "scope", name="uq_broker_connection_owner_scope"),
        sa.CheckConstraint("status IN ('active','revoked')",
                           name="ck_broker_connection_status"),
    )
    op.create_index("ix_broker_connections_owner", "broker_connections", ["owner_id"])


def downgrade() -> None:
    """Rerunnable, matching revisions 0010–0014.

    Not defensive style for its own sake. A downgrade chain that fails at a LATER revision
    leaves this one already applied, and the rollback of the enclosing transaction does not
    reliably restore the dropped objects — so the operator's second attempt hits
    `no such index` and the chain is stuck half-down. This was found by
    `test_product_object_downgrade_refuses_non_seed_history`, which downgrades twice on
    purpose.
    """
    bind = op.get_bind()
    if bind is None:                                  # offline / --sql mode
        op.drop_table("broker_connections")
        return
    inspector = sa.inspect(bind)
    if not inspector.has_table("broker_connections"):
        return
    if any(ix["name"] == "ix_broker_connections_owner"
           for ix in inspector.get_indexes("broker_connections")):
        op.drop_index("ix_broker_connections_owner", table_name="broker_connections")
    op.drop_table("broker_connections")
