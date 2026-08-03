"""persist project review notes and saved filter views

Revision ID: 0008
Revises: 0007
Created: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_review_notes",
        sa.Column("note_id", sa.String(64), primary_key=True),
        sa.Column(
            "project_id", sa.String(64),
            sa.ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(event_id) BETWEEN 1 AND 200", name="ck_review_note_event_id"
        ),
        sa.CheckConstraint(
            "event_type IN ('graph_version_published', 'experiment_run', "
            "'finding_created', 'candidate_created', 'candidate_decided')",
            name="ck_review_note_event_type",
        ),
        sa.CheckConstraint(
            "length(body) BETWEEN 1 AND 4000", name="ck_review_note_body"
        ),
        sa.CheckConstraint("created_by = 'owner'", name="ck_review_note_owner"),
        sa.CheckConstraint("revision >= 0", name="ck_review_note_revision"),
    )
    op.create_index(
        "ix_project_review_notes_project_event",
        "project_review_notes", ["project_id", "event_id"],
    )
    op.create_table(
        "project_review_saved_views",
        sa.Column("view_id", sa.String(64), primary_key=True),
        sa.Column(
            "project_id", sa.String(64),
            sa.ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(name) BETWEEN 1 AND 80", name="ck_review_view_name"
        ),
        sa.CheckConstraint(
            "json_valid(filters_json)", name="ck_review_view_filters_json"
        ),
        sa.CheckConstraint("created_by = 'owner'", name="ck_review_view_owner"),
        sa.CheckConstraint("revision >= 0", name="ck_review_view_revision"),
    )
    op.create_index(
        "ix_project_review_saved_views_project",
        "project_review_saved_views", ["project_id"],
    )
    op.create_index(
        "uq_project_review_saved_views_active_name",
        "project_review_saved_views", ["project_id", "name"], unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_notes = inspector.has_table("project_review_notes")
    has_views = inspector.has_table("project_review_saved_views")
    count = 0
    if has_notes:
        count += bind.scalar(sa.text("SELECT COUNT(*) FROM project_review_notes"))
    if has_views:
        count += bind.scalar(sa.text("SELECT COUNT(*) FROM project_review_saved_views"))
    if count:
        raise RuntimeError(
            "0008 downgrade refused: review notes or saved views exist; export and "
            "verify a restore before removing user writing"
        )
    if has_views:
        op.drop_index(
            "uq_project_review_saved_views_active_name",
            table_name="project_review_saved_views",
        )
        op.drop_index(
            "ix_project_review_saved_views_project",
            table_name="project_review_saved_views",
        )
        op.drop_table("project_review_saved_views")
    if has_notes:
        op.drop_index(
            "ix_project_review_notes_project_event", table_name="project_review_notes"
        )
        op.drop_table("project_review_notes")
