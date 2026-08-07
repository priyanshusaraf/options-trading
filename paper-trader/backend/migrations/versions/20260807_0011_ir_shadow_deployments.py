"""managed non-authoritative shadow deployments (L1.3A)

A server-owned binding from an approved immutable graph version to an instrument and
interval, in shadow mode. It carries lineage — project, graph identifier, version, content
address, evidence — and it is structurally incapable of carrying authority.

`execution_mode` and `authority` are CHECK-constrained to `shadow` / `non_authoritative`.
That is deliberate and is the point of the table: ADR 0012 §3.2 reserves paper authority to
the owner, and a column the database refuses to widen cannot be widened by a route, a
restart path, a data fix or a mistaken service call — only by a reviewed schema change.

Evidence is recorded, not foreign-keyed: the approval lineage lives in the research plane's
own database (hard invariant 5 — isolated, read-only bridges only), so a cross-database
foreign key is impossible and a cross-database write would breach the isolation. Activation
verifies through the read-only bridge and records what it verified.

The partial unique index covers only live states, so retiring a binding frees the
(deployment, instrument, interval) slot without deleting the record of what ran there.

Revision ID: 0011
Revises: 0010
Created: 2026-08-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_shadow_deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("graph_content_address", sa.String(71), nullable=False),
        sa.Column("evidence_run_id", sa.Integer(), nullable=True),
        sa.Column("evidence_candidate_id", sa.Integer(), nullable=True),
        sa.Column("evidence_content_address", sa.String(71), nullable=False,
                  server_default=""),
        sa.Column("evidence_verified_at", sa.DateTime(), nullable=True),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("instrument_key", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(16), nullable=False),
        sa.Column("strategy_key", sa.String(64), nullable=False),
        sa.Column("runtime_source", sa.String(16), nullable=False,
                  server_default="ir_graph"),
        sa.Column("execution_mode", sa.String(16), nullable=False,
                  server_default="shadow"),
        sa.Column("authority", sa.String(20), nullable=False,
                  server_default="non_authoritative"),
        sa.Column("admission_ok", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("admission_reason", sa.String(400), nullable=False, server_default=""),
        sa.Column("state", sa.String(16), nullable=False, server_default="staged"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["graph_identifier", "graph_version"],
            ["graph_versions.graph_identifier", "graph_versions.version"],
            ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("runtime_source = 'ir_graph'",
                           name="ck_ir_shadow_deployment_source"),
        sa.CheckConstraint("execution_mode = 'shadow'",
                           name="ck_ir_shadow_deployment_mode"),
        sa.CheckConstraint("authority = 'non_authoritative'",
                           name="ck_ir_shadow_deployment_authority"),
        sa.CheckConstraint("state IN ('staged','shadow_active','paused','retired')",
                           name="ck_ir_shadow_deployment_state"),
        sa.CheckConstraint("graph_version >= 1", name="ck_ir_shadow_deployment_version"),
        sa.CheckConstraint("revision >= 0", name="ck_ir_shadow_deployment_revision"),
    )
    op.create_index("uq_ir_shadow_deployment_active", "ir_shadow_deployments",
                    ["deployment_id", "instrument_key", "interval"], unique=True,
                    sqlite_where=sa.text(
                        "state IN ('staged','shadow_active','paused')"))
    op.create_index("ix_ir_shadow_deployments_state", "ir_shadow_deployments", ["state"])
    op.create_index("ix_ir_shadow_deployments_project_id", "ir_shadow_deployments",
                    ["project_id"])
    op.create_index("ix_ir_shadow_deployments_deployment_id", "ir_shadow_deployments",
                    ["deployment_id"])
    op.create_index("ix_ir_shadow_deployments_instrument_key", "ir_shadow_deployments",
                    ["instrument_key"])


def downgrade() -> None:
    # Same idempotent shape as 0010: an aborted downgrade must not leave `head` unreachable
    # because an index it already dropped is gone. Dropping the table takes its indexes.
    from alembic import context

    bind = op.get_bind() if context.is_offline_mode() is False else None
    if bind is not None and not sa.inspect(bind).has_table("ir_shadow_deployments"):
        return
    op.drop_table("ir_shadow_deployments")
