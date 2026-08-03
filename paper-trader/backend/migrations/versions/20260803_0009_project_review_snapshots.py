"""persist immutable project review snapshots

Revision ID: 0009
Revises: 0008
Created: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_review_snapshots",
        sa.Column("snapshot_id", sa.String(64), primary_key=True),
        sa.Column(
            "project_id", sa.String(64),
            sa.ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("capture_key", sa.String(36), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("content_address", sa.String(71), nullable=False),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("capture_started_at", sa.DateTime(), nullable=False),
        sa.Column("capture_completed_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(label) BETWEEN 1 AND 80", name="ck_review_snapshot_label"
        ),
        sa.CheckConstraint(
            "length(capture_key) = 36", name="ck_review_snapshot_capture_key"
        ),
        sa.CheckConstraint("created_by = 'owner'", name="ck_review_snapshot_owner"),
        sa.CheckConstraint(
            "json_valid(manifest_json)", name="ck_review_snapshot_manifest_json"
        ),
        sa.CheckConstraint(
            "json_extract(manifest_json, '$.schema_version') = 1",
            name="ck_review_snapshot_schema_version",
        ),
        sa.CheckConstraint(
            "json_extract(manifest_json, '$.project_id') IS project_id",
            name="ck_review_snapshot_project_matches_json",
        ),
        sa.CheckConstraint(
            "capture_completed_at >= capture_started_at",
            name="ck_review_snapshot_capture_window",
        ),
    )
    op.create_index(
        "ix_project_review_snapshots_project_completed",
        "project_review_snapshots", ["project_id", "capture_completed_at"],
    )
    op.create_index(
        "uq_project_review_snapshots_capture_key",
        "project_review_snapshots", ["project_id", "capture_key"], unique=True,
    )
    op.execute(
        "CREATE TRIGGER project_review_snapshots_refuse_update "
        "BEFORE UPDATE ON project_review_snapshots BEGIN "
        "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER project_review_snapshots_refuse_delete "
        "BEFORE DELETE ON project_review_snapshots BEGIN "
        "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("project_review_snapshots"):
        return
    count = bind.scalar(sa.text("SELECT COUNT(*) FROM project_review_snapshots"))
    if count:
        raise RuntimeError(
            "0009 downgrade refused: review snapshots exist; export and verify a "
            "restore before removing historical review records"
        )
    op.execute("DROP TRIGGER IF EXISTS project_review_snapshots_refuse_delete")
    op.execute("DROP TRIGGER IF EXISTS project_review_snapshots_refuse_update")
    op.drop_index(
        "uq_project_review_snapshots_capture_key",
        table_name="project_review_snapshots",
    )
    op.drop_index(
        "ix_project_review_snapshots_project_completed",
        table_name="project_review_snapshots",
    )
    op.drop_table("project_review_snapshots")
