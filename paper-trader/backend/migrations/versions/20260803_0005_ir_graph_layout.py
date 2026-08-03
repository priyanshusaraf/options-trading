"""add sparse, versioned IR graph editor layouts

Revision ID: 0005
Revises: 0004
Created: 2026-08-03

Coordinates are presentation state keyed beside an immutable graph identity. The
parent keeps an optimistic-concurrency revision even for an empty layout; child
rows exist only for authored nodes the user moved.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_graph_layouts",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("graph_identifier", "graph_version"),
    )
    op.create_table(
        "ir_graph_layout_positions",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(128), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["graph_identifier", "graph_version"],
            ["ir_graph_layouts.graph_identifier", "ir_graph_layouts.graph_version"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("graph_identifier", "graph_version", "instance_id"),
    )


def downgrade() -> None:
    op.drop_table("ir_graph_layout_positions")
    op.drop_table("ir_graph_layouts")
