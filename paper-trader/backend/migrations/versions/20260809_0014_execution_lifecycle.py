"""immutable durable entry lifecycle schema

Revision ID: 0014
Revises: 0013
Created: 2026-08-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_intents",
        sa.Column("client_intent_id", sa.String(32), primary_key=True),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("broker", sa.String(32), nullable=False),
        sa.Column("account_scope", sa.String(64), nullable=False),
        sa.Column("connection_scope", sa.String(64), nullable=False),
        sa.Column("broker_tag", sa.String(20), nullable=False, unique=True),
        sa.Column("intent", sa.String(8), nullable=False),
        sa.Column("instrument_key", sa.String(64), nullable=False),
        sa.Column("tradingsymbol", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("product", sa.String(16), nullable=True),
        sa.Column("order_type", sa.String(12), nullable=False),
        sa.Column("requested_qty", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("decision_price", sa.Float(), nullable=True),
        sa.Column("signal_at", sa.DateTime(), nullable=True),
        sa.Column("strategy_key", sa.String(64), nullable=True),
        sa.Column("strategy_version", sa.String(64), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("intent = 'ENTRY'", name="ck_execution_intent_entry"),
        sa.CheckConstraint("requested_qty > 0", name="ck_execution_intent_requested_qty"),
    )
    op.create_index("ix_execution_intents_deployment_id", "execution_intents", ["deployment_id"])
    op.create_index("ix_execution_intents_instrument_key", "execution_intents", ["instrument_key"])

    op.create_table(
        "execution_order_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_intent_id", sa.String(32), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("source_event_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("broker_order_id", sa.String(32), nullable=True),
        sa.Column("broker_status", sa.String(32), nullable=False, server_default=""),
        sa.Column("cumulative_filled_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("anomaly", sa.String(200), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(
            ["client_intent_id"], ["execution_intents.client_intent_id"],
            ondelete="RESTRICT"),
        sa.CheckConstraint(
            "cumulative_filled_qty >= 0", name="ck_execution_event_filled_qty"),
        sa.CheckConstraint("avg_price >= 0", name="ck_execution_event_avg_price"),
        sa.UniqueConstraint(
            "client_intent_id", "source", "source_event_id",
            name="uq_execution_event_source_identity"),
    )
    op.create_index("ix_execution_order_events_kind", "execution_order_events", ["kind"])
    op.create_index(
        "ix_execution_order_events_broker_order_id", "execution_order_events",
        ["broker_order_id"])

    # Nullable links are additive: historic positions and trades stay unmodified.
    for table in ("positions", "trades"):
        # SQLite cannot ALTER TABLE to add a separate FK constraint. Keeping the
        # reference inline gives it the same RESTRICT semantics without rebuilding
        # a money table or rewriting any legacy row.
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN entry_intent_id VARCHAR(32) "
            "REFERENCES execution_intents(client_intent_id) ON DELETE RESTRICT"
        )
        op.create_index(f"ix_{table}_entry_intent_id", table, ["entry_intent_id"])

    for trigger_name, operation in (
        ("execution_order_events_refuse_update", "UPDATE"),
        ("execution_order_events_refuse_delete", "DELETE"),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE {operation} "
            "ON execution_order_events BEGIN "
            "SELECT RAISE(ABORT, 'execution_order_events are immutable'); END"
        )


def downgrade() -> None:
    # An interrupted downgrade must be rerunnable, matching revisions 0010–0013.
    from alembic import context

    bind = op.get_bind() if context.is_offline_mode() is False else None
    if bind is None:
        _drop_lifecycle_schema()
        return

    inspector = sa.inspect(bind)
    if inspector.has_table("execution_order_events"):
        for trigger_name in (
            "execution_order_events_refuse_update",
            "execution_order_events_refuse_delete",
        ):
            bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name}"))
        op.drop_table("execution_order_events")

    # The nullable links may hold real rows. Remove them before their parent table
    # so SQLite's enforced RESTRICT action cannot block the downgrade.
    for table in ("positions", "trades"):
        columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        if "entry_intent_id" not in columns:
            continue
        indexes = {index["name"] for index in sa.inspect(bind).get_indexes(table)}
        index_name = f"ix_{table}_entry_intent_id"
        if index_name in indexes:
            op.drop_index(index_name, table_name=table)
        op.drop_column(table, "entry_intent_id")
    if sa.inspect(bind).has_table("execution_intents"):
        op.drop_table("execution_intents")


def _drop_lifecycle_schema() -> None:
    for trigger_name in (
        "execution_order_events_refuse_update",
        "execution_order_events_refuse_delete",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
    op.drop_table("execution_order_events")
    for table in ("positions", "trades"):
        op.drop_index(f"ix_{table}_entry_intent_id", table_name=table)
        op.drop_column(table, "entry_intent_id")
    op.drop_table("execution_intents")
