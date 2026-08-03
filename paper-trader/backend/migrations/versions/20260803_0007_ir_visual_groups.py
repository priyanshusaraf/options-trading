"""store visual groups beside executable graph versions

Revision ID: 0007
Revises: 0006
Created: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_graph_layout_groups",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("collapsed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["graph_identifier", "graph_version"],
            ["ir_graph_layouts.graph_identifier", "ir_graph_layouts.graph_version"],
            ondelete="CASCADE",
            name="fk_ir_graph_layout_groups_layout",
        ),
        sa.CheckConstraint("length(identifier) > 0", name="ck_ir_groups_identifier"),
        sa.CheckConstraint("length(display_name) > 0", name="ck_ir_groups_display_name"),
        sa.CheckConstraint("width > 0", name="ck_ir_groups_width"),
        sa.CheckConstraint("height > 0", name="ck_ir_groups_height"),
        sa.PrimaryKeyConstraint("graph_identifier", "graph_version", "identifier"),
    )
    op.create_table(
        "ir_graph_layout_group_members",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("group_identifier", sa.String(128), nullable=False),
        sa.Column("instance_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(
            ["graph_identifier", "graph_version", "group_identifier"],
            [
                "ir_graph_layout_groups.graph_identifier",
                "ir_graph_layout_groups.graph_version",
                "ir_graph_layout_groups.identifier",
            ],
            ondelete="CASCADE",
            name="fk_ir_graph_layout_group_members_group",
        ),
        sa.PrimaryKeyConstraint(
            "graph_identifier", "graph_version", "group_identifier", "instance_id"
        ),
    )


def downgrade() -> None:
    # SQLite DDL survives the later 0006 downgrade refusal. Idempotence lets an
    # operator correct that refusal and retry without a half-downgraded schema.
    op.execute("DROP TABLE IF EXISTS ir_graph_layout_group_members")
    op.execute("DROP TABLE IF EXISTS ir_graph_layout_groups")
