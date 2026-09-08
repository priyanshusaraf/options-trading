"""Add immutable owner-scoped Component IR v2 graph facts.

Revision ID: 0037
Revises: 0036
"""
from __future__ import annotations

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.models import IrV2GraphVersion

    IrV2GraphVersion.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("0037 refuses destructive removal of IR v2 graph evidence")
