"""Persist immutable execution-plane causal-admission receipts.

Revision ID: 0034
Revises: 0033
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.models import StrategyAdmission, _NullableContentAddress


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


_CONSUMERS = (
    "graph_versions",
    "backtest_runs",
    "backtest_results",
    "deployments",
    "ir_shadow_deployments",
    "ir_paper_deployments",
    "positions",
    "trades",
    "execution_intents",
)


def upgrade() -> None:
    bind = op.get_bind()
    StrategyAdmission.__table__.create(bind)
    for table in _CONSUMERS:
        op.add_column(
            table,
            sa.Column(
                "admission_address", sa.String(71),
                sa.CheckConstraint(
                    _NullableContentAddress("admission_address"),
                    name=f"ck_{table}_admission_address",
                ),
                nullable=True,
            ),
        )


def downgrade() -> None:
    # Removing these columns can erase a historical receipt binding from a MONEY row.
    # A rollback is therefore never a safe automatic operation.
    raise RuntimeError("0034 downgrade refuses to discard immutable admission receipts")
