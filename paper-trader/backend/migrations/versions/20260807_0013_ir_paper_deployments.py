"""paper-authoritative IR deployments (L1.3C)

The first table in this codebase through which IR output may create execution state. It
binds one approved immutable graph version to one instrument and interval, **in the paper
book**, with verified evidence lineage and an explicit rollback target.

`execution_mode` is CHECK-constrained to `paper` and `authority` to `authoritative`, which
is the whole reviewed grant and no more. The owner granted `(ir_graph, paper,
authoritative)` on 2026-08-07 and did not grant the live pair; a column the database
refuses to set to `live` cannot be widened by a route, a data fix, a restart path or a
mistaken service call — only by a reviewed schema change. `GRANTS` in
`core/execution_binding.py` is the gate; this is the lock on the same door, and the two
fail closed independently.

Deliberately a **separate table from `ir_shadow_deployments`** rather than a wider CHECK on
it. That object is an observer — no capital, no orders, no arm state, no authority, and a
service with no mode parameter. One row that means either "watched" or "traded" depending
on a column is the collapse ADR 0012 keeps refusing.

Equally deliberately **not a second deployment model**: the `Deployment` row still owns the
account, universe, parameters, allocation and arm. This attaches to one and adds only what
a `Deployment` cannot carry — which exact graph version, on what evidence, for which
instrument.

`rollback_strategy_key` is nullable and explicit. NULL means "there was no previous
authority here", which is a different statement from "we will work it out at runtime" —
inferring a rollback target is the silent-substitution failure this project has closed
twice.

Revision ID: 0013
Revises: 0012
Created: 2026-08-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_paper_deployments",
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
        sa.Column("rollback_strategy_key", sa.String(64), nullable=True),
        sa.Column("runtime_source", sa.String(16), nullable=False,
                  server_default="ir_graph"),
        sa.Column("execution_mode", sa.String(16), nullable=False,
                  server_default="paper"),
        sa.Column("authority", sa.String(20), nullable=False,
                  server_default="authoritative"),
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
                           name="ck_ir_paper_deployment_source"),
        sa.CheckConstraint("execution_mode = 'paper'",
                           name="ck_ir_paper_deployment_mode"),
        sa.CheckConstraint("authority = 'authoritative'",
                           name="ck_ir_paper_deployment_authority"),
        sa.CheckConstraint("state IN ('staged','paper_active','paused','retired')",
                           name="ck_ir_paper_deployment_state"),
        sa.CheckConstraint("graph_version >= 1", name="ck_ir_paper_deployment_version"),
        sa.CheckConstraint("revision >= 0", name="ck_ir_paper_deployment_revision"),
    )
    op.create_index("uq_ir_paper_deployment_active", "ir_paper_deployments",
                    ["deployment_id", "instrument_key", "interval"], unique=True,
                    sqlite_where=sa.text(
                        "state IN ('staged','paper_active','paused')"))
    op.create_index("ix_ir_paper_deployments_state", "ir_paper_deployments", ["state"])
    op.create_index("ix_ir_paper_deployments_project_id", "ir_paper_deployments",
                    ["project_id"])
    op.create_index("ix_ir_paper_deployments_deployment_id", "ir_paper_deployments",
                    ["deployment_id"])
    op.create_index("ix_ir_paper_deployments_instrument_key", "ir_paper_deployments",
                    ["instrument_key"])


def downgrade() -> None:
    # Same idempotent shape as 0010–0012: an aborted downgrade must not leave `head`
    # unreachable because an index it already dropped is gone. Dropping the table takes
    # its indexes.
    from alembic import context

    bind = op.get_bind() if context.is_offline_mode() is False else None
    if bind is not None and not sa.inspect(bind).has_table("ir_paper_deployments"):
        return
    op.drop_table("ir_paper_deployments")
