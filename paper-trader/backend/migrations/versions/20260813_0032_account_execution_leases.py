"""Add durable account execution leases, history and command evidence.

Revision ID: 0032
Revises: 0031
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision, down_revision = "0032", "0031"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_index("ux_broker_accounts_owner_account", "broker_accounts",
                    ["owner_id", "broker_account_id"], unique=True)
    op.add_column("execution_intents", sa.Column("fence_epoch", sa.Integer(), nullable=True))
    op.add_column("execution_order_events", sa.Column("fence_epoch", sa.Integer(), nullable=True))
    op.add_column("order_journal", sa.Column("fence_epoch", sa.Integer(), nullable=True))
    op.create_table(
        "account_execution_leases",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(16), nullable=False, server_default="idle"),
        sa.Column("cell_id", sa.String(96)), sa.Column("worker_id", sa.String(96)),
        sa.Column("host_diagnostic", sa.String(160), nullable=False, server_default=""),
        sa.Column("claimed_at", sa.DateTime()), sa.Column("heartbeat_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()), sa.Column("recovery_started_at", sa.DateTime()),
        sa.Column("reconciled_at", sa.DateTime()), sa.Column("blocked_at", sa.DateTime()),
        sa.Column("block_reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("desired_state", sa.String(16), nullable=False, server_default="disabled"),
        sa.Column("effective_state", sa.String(16), nullable=False, server_default="disabled"),
        sa.Column("control_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "broker_account_id"),
        sa.ForeignKeyConstraint(
            ["owner_id", "broker_account_id"],
            ["broker_accounts.owner_id", "broker_accounts.broker_account_id"],
            name="fk_account_execution_leases_account", ondelete="RESTRICT"),
        sa.CheckConstraint("fence_epoch > 0", name="ck_account_execution_leases_epoch"),
        sa.CheckConstraint("state IN ('idle', 'recovering', 'active', 'blocked')",
                           name="ck_account_execution_leases_state"),
        sa.CheckConstraint("desired_state IN ('disabled', 'armed')",
                           name="ck_account_execution_leases_desired_state"),
        sa.CheckConstraint("effective_state IN ('disabled', 'armed')",
                           name="ck_account_execution_leases_effective_state"),
        sa.CheckConstraint("control_revision >= 0", name="ck_account_execution_leases_revision"),
        sa.CheckConstraint(
            "(state = 'idle' AND cell_id IS NULL AND worker_id IS NULL "
            "AND heartbeat_at IS NULL AND expires_at IS NULL) OR "
            "(state <> 'idle' AND cell_id IS NOT NULL AND worker_id IS NOT NULL "
            "AND heartbeat_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND expires_at > heartbeat_at)", name="ck_account_execution_leases_holder_shape"),
        sa.CheckConstraint(
            "(state = 'active' AND reconciled_at IS NOT NULL) OR state <> 'active'",
            name="ck_account_execution_leases_active_reconciled"),
    )
    op.create_index("ix_account_execution_leases_expiry_state", "account_execution_leases",
                    ["expires_at", "state"])
    op.create_index("ix_account_execution_leases_worker", "account_execution_leases",
                    ["cell_id", "worker_id"])
    op.create_table(
        "account_execution_lease_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False),
        sa.Column("cell_id", sa.String(96), nullable=False, server_default=""),
        sa.Column("worker_id", sa.String(96), nullable=False, server_default=""),
        sa.Column("transition", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id", "broker_account_id"],
            ["account_execution_leases.owner_id", "account_execution_leases.broker_account_id"],
            name="fk_account_execution_history_lease", ondelete="RESTRICT"),
        sa.CheckConstraint("fence_epoch > 0", name="ck_account_execution_history_epoch"),
        sa.CheckConstraint("transition IN ('claim', 'takeover', 'activate', 'block', "
                           "'release', 'cancel', 'fence_rejection')",
                           name="ck_account_execution_history_transition"),
    )
    op.create_index("ix_account_execution_history_account", "account_execution_lease_history",
                    ["owner_id", "broker_account_id", "id"])
    op.create_table(
        "account_execution_commands",
        sa.Column("command_id", sa.String(64), primary_key=True),
        sa.Column("idempotency_key", sa.String(96), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False),
        sa.Column("cell_id", sa.String(96), nullable=False),
        sa.Column("worker_id", sa.String(96), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(96), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("broker_tag", sa.String(32), nullable=False, server_default=""),
        sa.Column("venue_idempotency_key", sa.String(96), nullable=False, server_default=""),
        sa.Column("state", sa.String(16), nullable=False, server_default="prepared"),
        sa.Column("broker_order_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("protective_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("requested_qty", sa.Integer()),
        sa.Column("requested_side", sa.String(8), nullable=False, server_default=""),
        sa.Column("requested_trigger", sa.Float()),
        sa.Column("error_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("actor_user_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("expected_revision", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime()), sa.Column("acknowledged_at", sa.DateTime()),
        sa.Column("resolved_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_by_epoch", sa.Integer()),
        sa.Column("resolution_digest", sa.String(64), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id", "broker_account_id"],
            ["account_execution_leases.owner_id", "account_execution_leases.broker_account_id"],
            name="fk_account_execution_commands_lease", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "broker_account_id", "idempotency_key",
                            name="uq_account_execution_commands_idempotency"),
        sa.CheckConstraint("fence_epoch > 0", name="ck_account_execution_commands_epoch"),
        sa.CheckConstraint("state IN ('prepared', 'processing', 'sent_unknown', 'acknowledged', "
                           "'resolved', 'cancelled', 'failed', 'blocked')",
                           name="ck_account_execution_commands_state"),
        sa.CheckConstraint("length(request_digest) = 64 AND request_digest = lower(request_digest)",
                           name="ck_account_execution_commands_digest"),
    )
    op.create_index("ix_account_execution_commands_recovery", "account_execution_commands",
                    ["owner_id", "broker_account_id", "state", "fence_epoch"])
    op.create_index("ix_account_execution_commands_age", "account_execution_commands",
                    ["state", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_account_execution_commands_age", table_name="account_execution_commands")
    op.drop_index("ix_account_execution_commands_recovery", table_name="account_execution_commands")
    op.drop_table("account_execution_commands")
    op.drop_index("ix_account_execution_history_account",
                  table_name="account_execution_lease_history")
    op.drop_table("account_execution_lease_history")
    op.drop_index("ix_account_execution_leases_worker", table_name="account_execution_leases")
    op.drop_index("ix_account_execution_leases_expiry_state", table_name="account_execution_leases")
    op.drop_table("account_execution_leases")
    op.drop_column("order_journal", "fence_epoch")
    op.drop_column("execution_order_events", "fence_epoch")
    op.drop_column("execution_intents", "fence_epoch")
    op.drop_index("ux_broker_accounts_owner_account", table_name="broker_accounts")
