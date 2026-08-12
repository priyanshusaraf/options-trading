"""Bind broker OAuth redirects to one durable authenticated session.

Revision ID: 0030
Revises: 0029
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision, down_revision = "0030", "0029"
branch_labels = depends_on = None


def upgrade() -> None:
    # New, empty security state.  No historic record is reinterpreted; a user
    # simply begins a new browser login after deployment.
    op.create_table(
        "oauth_callback_states",
        sa.Column("state_digest", sa.String(64), primary_key=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("revoked_at", sa.DateTime()),
        sa.CheckConstraint("length(state_digest) = 64 AND state_digest = lower(state_digest) "
                           "AND state_digest NOT GLOB '*[^0-9a-f]*'",
                           name="ck_oauth_callback_states_digest"),
        sa.ForeignKeyConstraint(("organization_id", "user_id"),
                                ("memberships.organization_id", "memberships.user_id"),
                                name="fk_oauth_callback_states_membership", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("session_id",), ("user_sessions.session_id",),
                                name="fk_oauth_callback_states_session", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("connection_id",), ("broker_connections.id",),
                                name="fk_oauth_callback_states_connection", ondelete="RESTRICT"),
    )
    op.create_index("ix_oauth_callback_states_expiry", "oauth_callback_states", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind is not None and bind.execute(sa.text(
            "SELECT 1 FROM oauth_callback_states LIMIT 1")).first():
        raise RuntimeError("0030 downgrade refuses to discard OAuth callback state")
    op.drop_index("ix_oauth_callback_states_expiry", table_name="oauth_callback_states")
    op.drop_table("oauth_callback_states")
