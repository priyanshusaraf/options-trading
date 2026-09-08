"""Add nullable v2 semantic receipt identity without rewriting v1 evidence.

Revision ID: 0035
Revises: 0034
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("strategy_admissions")}
    # SQLite may durably apply an additive ALTER before an interrupted Alembic
    # transaction stamps this revision.  Re-entry therefore completes only the
    # missing half and remains refusal-safe for every existing historical row.
    if "format_version" not in existing:
        op.add_column("strategy_admissions", sa.Column("format_version", sa.Integer(), nullable=True))
    if "content_address" not in existing:
        op.add_column("strategy_admissions", sa.Column("content_address", sa.String(71), nullable=True))


def downgrade() -> None:
    raise RuntimeError("0035 downgrade refuses to discard immutable v2 receipt identity")
