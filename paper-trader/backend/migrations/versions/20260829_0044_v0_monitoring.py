"""Add owner-scoped V0 monitoring evidence in the USER plane.

The nine tables are additive and do not read, rewrite or backfill legacy signal,
execution, position, ledger or money rows. Rollback is restore/forward repair
after writer quiescence; durable monitoring evidence is never dropped here.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


TABLES = (
    "monitoring_assignments",
    "monitoring_state_snapshots",
    "monitoring_signal_events",
    "monitoring_signal_alerts",
    "monitoring_alert_delivery_attempts",
    "monitoring_alert_attention_events",
    "monitoring_latest_state",
    "monitoring_alert_attention_state",
    "monitoring_signal_reviews",
)


def _address(column: str, dialect: str, *, nullable: bool = False) -> str:
    if dialect == "postgresql":
        body = f"{column} ~ '^sha256:[0-9a-f]{{64}}$'"
    else:
        body = (f"length({column}) = 71 AND substr({column}, 1, 7) = 'sha256:' AND "
                f"substr({column}, 8) = lower(substr({column}, 8)) AND "
                f"substr({column}, 8) NOT GLOB '*[^0-9a-f]*'")
    return f"{column} IS NULL OR ({body})" if nullable else body


def _json(column: str, dialect: str) -> str:
    return (f"CAST({column} AS JSONB) IS NOT NULL" if dialect == "postgresql"
            else f"json_valid({column})")


def _json_text(json_column: str, key: str, column: str, dialect: str) -> str:
    if dialect == "postgresql":
        field = f"CAST({json_column} AS JSONB) -> '{key}'"
        return (f"{field} IS NOT NULL AND jsonb_typeof({field}) = 'string' AND "
                f"CAST({json_column} AS JSONB) ->> '{key}' = {column}")
    return f"json_extract({json_column}, '$.{key}') IS {column}"


def _json_number(json_column: str, key: str, column: str, dialect: str) -> str:
    if dialect == "postgresql":
        field = f"CAST({json_column} AS JSONB) -> '{key}'"
        return (f"{field} IS NOT NULL AND jsonb_typeof({field}) = 'number' AND "
                f"({field} #>> '{{}}')::numeric = {column}")
    return f"json_extract({json_column}, '$.{key}') IS {column}"


def _utf8_size(column: str, maximum: int, dialect: str) -> str:
    return (f"octet_length({column}) <= {maximum}" if dialect == "postgresql"
            else f"length(CAST({column} AS BLOB)) <= {maximum}")


def _closed_code(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"{column} ~ '^[A-Z][A-Z0-9_]{{0,63}}$'"
    return (f"length({column}) BETWEEN 1 AND 64 AND substr({column}, 1, 1) GLOB '[A-Z]' "
            f"AND {column} NOT GLOB '*[^A-Z0-9_]*'")


def _review_note(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return (f"{column} = btrim({column}) AND octet_length({column}) <= 4096 "
                f"AND {column} !~ '[[:cntrl:]]'")
    controls = " AND ".join(f"instr({column}, char({value})) = 0" for value in (*range(32), 127))
    return (f"{column} = trim({column}) AND length(CAST({column} AS BLOB)) <= 4096 "
            f"AND {controls}")


def _ck(expression: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(expression, name=name)


def _create_tables(dialect: str) -> None:
    op.create_table(
        "monitoring_assignments",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("optimistic_revision", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(16), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("strategy_id", sa.String(128), nullable=False),
        sa.Column("graph_version_address", sa.String(71), nullable=False),
        sa.Column("resolved_graph_address", sa.String(71), nullable=False),
        sa.Column("registry_address", sa.String(71), nullable=False),
        sa.Column("implementation_closure_address", sa.String(71), nullable=False),
        sa.Column("research_admission_address", sa.String(71), nullable=False),
        sa.Column("static_scope_revision_address", sa.String(71), nullable=False),
        sa.Column("role_binding_address", sa.String(71), nullable=False),
        sa.Column("data_connection_id", sa.Integer(), nullable=False),
        sa.Column("capability_profile_address", sa.String(71), nullable=False),
        sa.Column("resource_plan_address", sa.String(71), nullable=False),
        sa.Column("evaluation_trigger_address", sa.String(71), nullable=False),
        sa.Column("state_reset_policy_address", sa.String(71), nullable=False),
        sa.Column("current_state_snapshot_address", sa.String(71), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id"),
        sa.ForeignKeyConstraint(("owner_id", "project_id"), ("projects.owner_id", "projects.project_id"),
                                name="fk_monitoring_assignments_project", ondelete="RESTRICT"),
        _ck("optimistic_revision >= 1", "ck_monitoring_assignments_revision"),
        _ck("lifecycle_state IN ('ACTIVE', 'PAUSED', 'WITHDRAWN')", "ck_monitoring_assignments_lifecycle"),
        _ck("(lifecycle_state = 'WITHDRAWN' AND withdrawn_at IS NOT NULL) OR "
            "(lifecycle_state <> 'WITHDRAWN' AND withdrawn_at IS NULL)",
            "ck_monitoring_assignments_withdrawal"),
        _ck("data_connection_id > 0", "ck_monitoring_assignments_data_connection"),
        _ck(_address("graph_version_address", dialect), "ck_monitoring_assignments_graph"),
        _ck(_address("resolved_graph_address", dialect), "ck_monitoring_assignments_resolved"),
        _ck(_address("registry_address", dialect), "ck_monitoring_assignments_registry"),
        _ck(_address("implementation_closure_address", dialect), "ck_monitoring_assignments_implementation"),
        _ck(_address("research_admission_address", dialect), "ck_monitoring_assignments_admission"),
        _ck(_address("static_scope_revision_address", dialect), "ck_monitoring_assignments_scope"),
        _ck(_address("role_binding_address", dialect), "ck_monitoring_assignments_roles"),
        _ck(_address("capability_profile_address", dialect), "ck_monitoring_assignments_capability"),
        _ck(_address("resource_plan_address", dialect), "ck_monitoring_assignments_resource"),
        _ck(_address("evaluation_trigger_address", dialect), "ck_monitoring_assignments_trigger"),
        _ck(_address("state_reset_policy_address", dialect), "ck_monitoring_assignments_reset"),
        _ck(_address("current_state_snapshot_address", dialect, nullable=True), "ck_monitoring_assignments_current_snapshot"),
    )
    op.create_index("ix_monitoring_assignments_owner_lifecycle", "monitoring_assignments",
                    ("owner_id", "lifecycle_state", "assignment_id"))
    op.create_index("ix_monitoring_assignments_owner_project", "monitoring_assignments",
                    ("owner_id", "project_id", "assignment_id"))

    op.create_table(
        "monitoring_state_snapshots",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("canonical_instrument_address", sa.String(71), nullable=False),
        sa.Column("snapshot_address", sa.String(71), nullable=False),
        sa.Column("snapshot_sequence", sa.Integer(), nullable=False),
        sa.Column("predecessor_snapshot_address", sa.String(71), nullable=True),
        sa.Column("strategy_state", sa.String(8), nullable=False),
        sa.Column("entry_reference_json", sa.Text(), nullable=False),
        sa.Column("stop_loss_json", sa.Text(), nullable=False),
        sa.Column("take_profit_json", sa.Text(), nullable=False),
        sa.Column("evaluation_event_address", sa.String(71), nullable=False),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id"),
                                ("monitoring_assignments.owner_id", "monitoring_assignments.assignment_id"),
                                name="fk_monitoring_snapshots_assignment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ("owner_id", "assignment_id", "canonical_instrument_address", "predecessor_snapshot_address"),
            ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
             "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
            name="fk_monitoring_snapshots_predecessor", ondelete="RESTRICT",
            deferrable=True, initially="DEFERRED"),
        sa.UniqueConstraint("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_sequence",
                            name="uq_monitoring_snapshots_sequence"),
        _ck("snapshot_sequence >= 0", "ck_monitoring_snapshots_sequence"),
        _ck("(snapshot_sequence = 0 AND predecessor_snapshot_address IS NULL) OR "
            "(snapshot_sequence > 0 AND predecessor_snapshot_address IS NOT NULL)",
            "ck_monitoring_snapshots_predecessor"),
        _ck("strategy_state IN ('FLAT', 'LONG', 'SHORT')", "ck_monitoring_snapshots_state"),
        _ck(_address("canonical_instrument_address", dialect), "ck_monitoring_snapshots_instrument"),
        _ck(_address("snapshot_address", dialect), "ck_monitoring_snapshots_address"),
        _ck(_address("predecessor_snapshot_address", dialect, nullable=True), "ck_monitoring_snapshots_predecessor_address"),
        _ck(_address("evaluation_event_address", dialect), "ck_monitoring_snapshots_evaluation"),
        _ck(_json("entry_reference_json", dialect), "ck_monitoring_snapshots_entry_json"),
        _ck(_json("stop_loss_json", dialect), "ck_monitoring_snapshots_stop_json"),
        _ck(_json("take_profit_json", dialect), "ck_monitoring_snapshots_target_json"),
        _ck(_json("canonical_json", dialect), "ck_monitoring_snapshots_canonical_json"),
        _ck(_utf8_size("canonical_json", 16384, dialect), "ck_monitoring_snapshots_canonical_size"),
        _ck(_json_text("canonical_json", "address", "snapshot_address", dialect), "ck_monitoring_snapshots_json_address"),
        _ck(_json_text("canonical_json", "owner_id", "owner_id", dialect), "ck_monitoring_snapshots_json_owner"),
        _ck(_json_text("canonical_json", "assignment_id", "assignment_id", dialect), "ck_monitoring_snapshots_json_assignment"),
        _ck(_json_text("canonical_json", "canonical_instrument_address", "canonical_instrument_address", dialect), "ck_monitoring_snapshots_json_instrument"),
        _ck(_json_text("canonical_json", "evaluation_event_address", "evaluation_event_address", dialect), "ck_monitoring_snapshots_json_evaluation"),
        _ck(_json_text("canonical_json", "strategy_state", "strategy_state", dialect), "ck_monitoring_snapshots_json_state"),
        _ck(_json_number("canonical_json", "snapshot_sequence", "snapshot_sequence", dialect), "ck_monitoring_snapshots_json_sequence"),
    )
    op.create_index("ix_monitoring_snapshots_sequence", "monitoring_state_snapshots",
                    ("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_sequence"))

    op.create_table(
        "monitoring_signal_events",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("content_address", sa.String(71), nullable=False),
        sa.Column("dedupe_address", sa.String(71), nullable=False),
        sa.Column("canonical_instrument_address", sa.String(71), nullable=False),
        sa.Column("evaluation_event_address", sa.String(71), nullable=False),
        sa.Column("graph_version_address", sa.String(71), nullable=False),
        sa.Column("implementation_closure_address", sa.String(71), nullable=False),
        sa.Column("state_before_address", sa.String(71), nullable=False),
        sa.Column("state_after_address", sa.String(71), nullable=False),
        sa.Column("event_at", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "content_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id"),
                                ("monitoring_assignments.owner_id", "monitoring_assignments.assignment_id"),
                                name="fk_monitoring_events_assignment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "canonical_instrument_address", "state_before_address"),
                                ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
                                 "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
                                name="fk_monitoring_events_state_before", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "canonical_instrument_address", "state_after_address"),
                                ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
                                 "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
                                name="fk_monitoring_events_state_after", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "dedupe_address", name="uq_monitoring_events_dedupe"),
        sa.UniqueConstraint("owner_id", "assignment_id", "canonical_instrument_address",
                            "evaluation_event_address", "graph_version_address",
                            "implementation_closure_address", "state_before_address",
                            name="uq_monitoring_events_business_effect"),
        _ck(_address("content_address", dialect), "ck_monitoring_events_address"),
        _ck(_address("dedupe_address", dialect), "ck_monitoring_events_dedupe"),
        _ck(_address("canonical_instrument_address", dialect), "ck_monitoring_events_instrument"),
        _ck(_address("evaluation_event_address", dialect), "ck_monitoring_events_evaluation"),
        _ck(_address("graph_version_address", dialect), "ck_monitoring_events_graph"),
        _ck(_address("implementation_closure_address", dialect), "ck_monitoring_events_implementation"),
        _ck(_address("state_before_address", dialect), "ck_monitoring_events_state_before"),
        _ck(_address("state_after_address", dialect), "ck_monitoring_events_state_after"),
        _ck("event_at <= valid_until", "ck_monitoring_events_time"),
        _ck(_json("canonical_json", dialect), "ck_monitoring_events_json"),
        _ck(_utf8_size("canonical_json", 16384, dialect), "ck_monitoring_events_json_size"),
        _ck(_json_text("canonical_json", "address", "content_address", dialect), "ck_monitoring_events_json_address"),
        _ck(_json_text("canonical_json", "owner_id", "owner_id", dialect), "ck_monitoring_events_json_owner"),
        _ck(_json_text("canonical_json", "assignment_id", "assignment_id", dialect), "ck_monitoring_events_json_assignment"),
        _ck(_json_text("canonical_json", "canonical_instrument_address", "canonical_instrument_address", dialect), "ck_monitoring_events_json_instrument"),
        _ck(_json_text("canonical_json", "evaluation_event_address", "evaluation_event_address", dialect), "ck_monitoring_events_json_evaluation"),
        _ck(_json_text("canonical_json", "graph_version_address", "graph_version_address", dialect), "ck_monitoring_events_json_graph"),
        _ck(_json_text("canonical_json", "implementation_closure_address", "implementation_closure_address", dialect), "ck_monitoring_events_json_implementation"),
        _ck(_json_text("canonical_json", "state_before_address", "state_before_address", dialect), "ck_monitoring_events_json_before"),
        _ck(_json_text("canonical_json", "state_after_address", "state_after_address", dialect), "ck_monitoring_events_json_after"),
    )
    op.create_index("ix_monitoring_events_cursor", "monitoring_signal_events",
                    ("owner_id", "assignment_id", "event_at", "content_address"))
    op.create_index("ix_monitoring_events_state", "monitoring_signal_events",
                    ("owner_id", "assignment_id", "canonical_instrument_address", "event_at", "content_address"))

    op.create_table(
        "monitoring_signal_alerts",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("alert_address", sa.String(71), nullable=False),
        sa.Column("monitoring_event_address", sa.String(71), nullable=False),
        sa.Column("canonical_instrument_address", sa.String(71), nullable=False),
        sa.Column("event_at", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "alert_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "monitoring_event_address"),
                                ("monitoring_signal_events.owner_id", "monitoring_signal_events.assignment_id",
                                 "monitoring_signal_events.content_address"),
                                name="fk_monitoring_alerts_event", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "assignment_id", "monitoring_event_address", name="uq_monitoring_alerts_event"),
        _ck(_address("alert_address", dialect), "ck_monitoring_alerts_address"),
        _ck(_address("monitoring_event_address", dialect), "ck_monitoring_alerts_event"),
        _ck(_address("canonical_instrument_address", dialect), "ck_monitoring_alerts_instrument"),
        _ck("event_at <= valid_until", "ck_monitoring_alerts_time"),
        _ck(_json("canonical_json", dialect), "ck_monitoring_alerts_json"),
        _ck(_utf8_size("canonical_json", 16384, dialect), "ck_monitoring_alerts_json_size"),
        _ck(_json_text("canonical_json", "address", "alert_address", dialect), "ck_monitoring_alerts_json_address"),
        _ck(_json_text("canonical_json", "owner_id", "owner_id", dialect), "ck_monitoring_alerts_json_owner"),
        _ck(_json_text("canonical_json", "assignment_id", "assignment_id", dialect), "ck_monitoring_alerts_json_assignment"),
        _ck(_json_text("canonical_json", "monitoring_event_address", "monitoring_event_address", dialect), "ck_monitoring_alerts_json_event"),
        _ck(_json_text("canonical_json", "canonical_instrument_address", "canonical_instrument_address", dialect), "ck_monitoring_alerts_json_instrument"),
    )
    op.create_index("ix_monitoring_alerts_owner_cursor", "monitoring_signal_alerts",
                    ("owner_id", "event_at", "alert_address"))
    op.create_index("ix_monitoring_alerts_assignment_cursor", "monitoring_signal_alerts",
                    ("owner_id", "assignment_id", "event_at", "alert_address"))

    op.create_table(
        "monitoring_alert_delivery_attempts",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("attempt_address", sa.String(71), nullable=False),
        sa.Column("attempt_id", sa.String(71), nullable=False),
        sa.Column("alert_address", sa.String(71), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "attempt_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "alert_address"),
                                ("monitoring_signal_alerts.owner_id", "monitoring_signal_alerts.assignment_id",
                                 "monitoring_signal_alerts.alert_address"),
                                name="fk_monitoring_delivery_alert", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "attempt_id", name="uq_monitoring_delivery_request"),
        sa.UniqueConstraint("owner_id", "assignment_id", "alert_address", "sequence", "channel",
                            name="uq_monitoring_delivery_sequence"),
        _ck("sequence >= 1", "ck_monitoring_delivery_sequence"),
        _ck("channel = 'IN_APP'", "ck_monitoring_delivery_channel"),
        _ck("outcome IN ('DELIVERED', 'FAILED')", "ck_monitoring_delivery_outcome"),
        _ck("(outcome = 'FAILED' AND failure_code IS NOT NULL) OR "
            "(outcome = 'DELIVERED' AND failure_code IS NULL)", "ck_monitoring_delivery_failure"),
        _ck(_address("attempt_address", dialect), "ck_monitoring_delivery_address"),
        _ck(_address("attempt_id", dialect), "ck_monitoring_delivery_request_address"),
        _ck(_address("alert_address", dialect), "ck_monitoring_delivery_alert_address"),
        _ck(_json("canonical_json", dialect), "ck_monitoring_delivery_json"),
        _ck(_utf8_size("canonical_json", 16384, dialect), "ck_monitoring_delivery_json_size"),
        _ck(_json_text("canonical_json", "address", "attempt_address", dialect), "ck_monitoring_delivery_json_address"),
        _ck(_json_text("canonical_json", "attempt_id", "attempt_id", dialect), "ck_monitoring_delivery_json_request"),
    )
    op.create_index("ix_monitoring_delivery_sequence", "monitoring_alert_delivery_attempts",
                    ("owner_id", "assignment_id", "alert_address", "sequence"))
    op.create_index("ix_monitoring_delivery_outcome", "monitoring_alert_delivery_attempts",
                    ("owner_id", "outcome", "occurred_at"))

    op.create_table(
        "monitoring_alert_attention_events",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("attention_event_address", sa.String(71), nullable=False),
        sa.Column("request_id", sa.String(71), nullable=False),
        sa.Column("alert_address", sa.String(71), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "attention_event_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "alert_address"),
                                ("monitoring_signal_alerts.owner_id", "monitoring_signal_alerts.assignment_id",
                                 "monitoring_signal_alerts.alert_address"),
                                name="fk_monitoring_attention_alert", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_monitoring_attention_request"),
        sa.UniqueConstraint("owner_id", "assignment_id", "alert_address", "sequence",
                            name="uq_monitoring_attention_sequence"),
        _ck("sequence >= 1", "ck_monitoring_attention_sequence"),
        _ck("action IN ('READ', 'ACKNOWLEDGE', 'DISMISS')", "ck_monitoring_attention_action"),
        _ck(_address("attention_event_address", dialect), "ck_monitoring_attention_address"),
        _ck(_address("request_id", dialect), "ck_monitoring_attention_request_address"),
        _ck(_address("alert_address", dialect), "ck_monitoring_attention_alert_address"),
        _ck(_json("canonical_json", dialect), "ck_monitoring_attention_json"),
        _ck(_utf8_size("canonical_json", 16384, dialect), "ck_monitoring_attention_json_size"),
        _ck(_json_text("canonical_json", "address", "attention_event_address", dialect), "ck_monitoring_attention_json_address"),
        _ck(_json_text("canonical_json", "request_id", "request_id", dialect), "ck_monitoring_attention_json_request"),
    )
    op.create_index("ix_monitoring_attention_sequence", "monitoring_alert_attention_events",
                    ("owner_id", "assignment_id", "alert_address", "sequence"))

    op.create_table(
        "monitoring_latest_state",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("canonical_instrument_address", sa.String(71), nullable=False),
        sa.Column("snapshot_address", sa.String(71), nullable=False),
        sa.Column("last_event_address", sa.String(71), nullable=True),
        sa.Column("snapshot_sequence", sa.Integer(), nullable=False),
        sa.Column("strategy_state", sa.String(8), nullable=False),
        sa.Column("projection_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "canonical_instrument_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_address"),
                                ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
                                 "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
                                name="fk_monitoring_latest_snapshot", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "last_event_address"),
                                ("monitoring_signal_events.owner_id", "monitoring_signal_events.assignment_id",
                                 "monitoring_signal_events.content_address"),
                                name="fk_monitoring_latest_event", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_address",
                            name="uq_monitoring_latest_snapshot"),
        _ck(_address("canonical_instrument_address", dialect), "ck_monitoring_latest_instrument"),
        _ck(_address("snapshot_address", dialect), "ck_monitoring_latest_snapshot"),
        _ck(_address("last_event_address", dialect, nullable=True), "ck_monitoring_latest_event"),
        _ck("snapshot_sequence >= 0", "ck_monitoring_latest_sequence"),
        _ck("strategy_state IN ('FLAT', 'LONG', 'SHORT')", "ck_monitoring_latest_state"),
        _ck("projection_revision >= 1", "ck_monitoring_latest_revision"),
    )
    op.create_index("ix_monitoring_latest_updated", "monitoring_latest_state",
                    ("owner_id", "assignment_id", "updated_at"))

    op.create_table(
        "monitoring_alert_attention_state",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("alert_address", sa.String(71), nullable=False),
        sa.Column("projection_address", sa.String(71), nullable=False),
        sa.Column("alert_event_at", sa.DateTime(), nullable=False),
        sa.Column("alert_valid_until", sa.DateTime(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("is_unread", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("projection_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "alert_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "alert_address"),
                                ("monitoring_signal_alerts.owner_id", "monitoring_signal_alerts.assignment_id",
                                 "monitoring_signal_alerts.alert_address"),
                                name="fk_monitoring_attention_state_alert", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "projection_address", name="uq_monitoring_attention_state_projection"),
        _ck(_address("alert_address", dialect), "ck_monitoring_attention_state_alert"),
        _ck(_address("projection_address", dialect), "ck_monitoring_attention_state_address"),
        _ck("alert_event_at <= alert_valid_until", "ck_monitoring_attention_state_alert_time"),
        _ck("last_sequence >= 0", "ck_monitoring_attention_state_sequence"),
        _ck("projection_revision >= 1", "ck_monitoring_attention_state_revision"),
        _ck("read_at IS NULL OR read_at >= alert_event_at", "ck_monitoring_attention_state_read"),
        _ck("acknowledged_at IS NULL OR acknowledged_at >= alert_event_at", "ck_monitoring_attention_state_ack"),
        _ck("dismissed_at IS NULL OR dismissed_at >= alert_event_at", "ck_monitoring_attention_state_dismiss"),
    )
    op.create_index("ix_monitoring_attention_inbox", "monitoring_alert_attention_state",
                    ("owner_id", "is_unread", "alert_event_at", "alert_address"))
    op.create_index("ix_monitoring_attention_assignment", "monitoring_alert_attention_state",
                    ("owner_id", "assignment_id", "alert_event_at", "alert_address"))

    op.create_table(
        "monitoring_signal_reviews",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=False),
        sa.Column("review_address", sa.String(71), nullable=False),
        sa.Column("monitoring_event_address", sa.String(71), nullable=False),
        sa.Column("reviewer_user_id", sa.String(64), nullable=False),
        sa.Column("disposition", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "assignment_id", "review_address"),
        sa.ForeignKeyConstraint(("owner_id", "assignment_id", "monitoring_event_address"),
                                ("monitoring_signal_events.owner_id", "monitoring_signal_events.assignment_id",
                                 "monitoring_signal_events.content_address"),
                                name="fk_monitoring_reviews_event", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("owner_id", "reviewer_user_id"),
                                ("memberships.organization_id", "memberships.user_id"),
                                name="fk_monitoring_reviews_membership", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "assignment_id", "monitoring_event_address", "reviewer_user_id",
                            name="uq_monitoring_reviews_author"),
        _ck(_address("review_address", dialect), "ck_monitoring_reviews_address"),
        _ck(_address("monitoring_event_address", dialect), "ck_monitoring_reviews_event"),
        _ck("disposition IN ('CONFIRMED', 'REJECTED')", "ck_monitoring_reviews_disposition"),
        _ck(_closed_code("reason_code", dialect), "ck_monitoring_reviews_reason"),
        _ck(_review_note("note", dialect), "ck_monitoring_reviews_note"),
        _ck(_json("canonical_json", dialect), "ck_monitoring_reviews_json"),
        _ck(_utf8_size("canonical_json", 16384, dialect), "ck_monitoring_reviews_json_size"),
        _ck(_json_text("canonical_json", "address", "review_address", dialect), "ck_monitoring_reviews_json_address"),
        _ck(_json_text("canonical_json", "owner_id", "owner_id", dialect), "ck_monitoring_reviews_json_owner"),
        _ck(_json_text("canonical_json", "assignment_id", "assignment_id", dialect), "ck_monitoring_reviews_json_assignment"),
        _ck(_json_text("canonical_json", "monitoring_event_address", "monitoring_event_address", dialect), "ck_monitoring_reviews_json_event"),
        _ck(_json_text("canonical_json", "reviewer_user_id", "reviewer_user_id", dialect), "ck_monitoring_reviews_json_reviewer"),
    )
    op.create_index("ix_monitoring_reviews_cursor", "monitoring_signal_reviews",
                    ("owner_id", "assignment_id", "created_at", "review_address"))
    op.create_index("ix_monitoring_reviews_disposition", "monitoring_signal_reviews",
                    ("owner_id", "disposition", "created_at"))


def _create_triggers(connection, dialect: str) -> None:
    immutable = TABLES[1:6] + (TABLES[8],)
    if dialect == "sqlite":
        for table in immutable:
            for action in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {table}_refuse_{action.lower()} BEFORE {action} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END")
        identity = (
            "owner_id", "assignment_id", "project_id", "strategy_id", "graph_version_address",
            "resolved_graph_address", "registry_address", "implementation_closure_address",
            "research_admission_address", "static_scope_revision_address", "role_binding_address",
            "data_connection_id", "capability_profile_address", "resource_plan_address",
            "evaluation_trigger_address", "state_reset_policy_address", "created_at",
        )
        changed = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in identity)
        connection.exec_driver_sql(
            "CREATE TRIGGER monitoring_assignments_refuse_identity_change BEFORE UPDATE "
            f"ON monitoring_assignments WHEN {changed} BEGIN "
            "SELECT RAISE(ABORT, 'monitoring assignment identity is immutable'); END")
        connection.exec_driver_sql(
            "CREATE TRIGGER monitoring_assignments_refuse_delete BEFORE DELETE ON monitoring_assignments "
            "BEGIN SELECT RAISE(ABORT, 'monitoring assignments are durable'); END")
        return
    for table in immutable:
        connection.exec_driver_sql(
            f"CREATE OR REPLACE FUNCTION {table}_refuse_mutation() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '{table} is immutable'; END; $$ LANGUAGE plpgsql")
        connection.exec_driver_sql(
            f"CREATE TRIGGER {table}_refuse_mutation BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {table}_refuse_mutation()")
    identity = (
        "owner_id", "assignment_id", "project_id", "strategy_id", "graph_version_address",
        "resolved_graph_address", "registry_address", "implementation_closure_address",
        "research_admission_address", "static_scope_revision_address", "role_binding_address",
        "data_connection_id", "capability_profile_address", "resource_plan_address",
        "evaluation_trigger_address", "state_reset_policy_address", "created_at",
    )
    changed = " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in identity)
    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION monitoring_assignments_refuse_identity_change_fn() "
        f"RETURNS trigger AS $$ BEGIN IF {changed} THEN "
        "RAISE EXCEPTION 'monitoring assignment identity is immutable'; END IF; "
        "RETURN NEW; END; $$ LANGUAGE plpgsql")
    connection.exec_driver_sql(
        "CREATE TRIGGER monitoring_assignments_refuse_identity_change BEFORE UPDATE ON monitoring_assignments "
        "FOR EACH ROW EXECUTE FUNCTION monitoring_assignments_refuse_identity_change_fn()")
    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION monitoring_assignments_refuse_delete_fn() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'monitoring assignments are durable'; END; $$ LANGUAGE plpgsql")
    connection.exec_driver_sql(
        "CREATE TRIGGER monitoring_assignments_refuse_delete BEFORE DELETE ON monitoring_assignments "
        "FOR EACH ROW EXECUTE FUNCTION monitoring_assignments_refuse_delete_fn()")


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0044 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200044)")
    if set(TABLES).intersection(sa.inspect(connection).get_table_names()):
        raise RuntimeError(
            "0044 refuses partial/unproven monitoring schema; clean restore or forward repair required")
    _create_tables(dialect)
    _create_triggers(connection, dialect)


def downgrade() -> None:
    raise RuntimeError(
        "0044 refuses destructive downgrade; retain monitoring facts, quiesce writers, "
        "and use verified restore or forward repair")
