"""Make durable sweep result cells idempotent across claim replacement.

Revision ID: 0026
Revises: 0025
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("backtest_results")}


def upgrade() -> None:
    """Backfill legacy identity before installing the idempotency constraint.

    The historical rows cannot be reinterpreted as current planned cells: their
    execution address was optional.  Give each one a stable legacy identity,
    then require all new durable claimed writes to name a real cell key.
    """
    columns = _columns()
    if "request_json" not in columns:
        op.add_column("backtest_runs", sa.Column("request_json", sa.Text(), nullable=False,
                                                  server_default=""))
    if "cell_key" not in columns:
        op.add_column("backtest_results", sa.Column("cell_key", sa.String(192), nullable=True))
    if "strategy_version" not in _columns():
        op.add_column("backtest_results", sa.Column("strategy_version", sa.String(128), nullable=True))
    op.execute(sa.text(
        "UPDATE backtest_results SET cell_key='legacy:' || id WHERE cell_key IS NULL"))
    op.execute(sa.text(
        "UPDATE backtest_results SET strategy_version='legacy:' || id WHERE strategy_version IS NULL"))
    duplicate = op.get_bind().execute(sa.text(
        "SELECT owner_id,run_id,cell_key FROM backtest_results "
        "GROUP BY owner_id,run_id,cell_key HAVING COUNT(*) > 1 LIMIT 1")).first()
    if duplicate:
        raise RuntimeError("0026 refuses duplicate durable backtest cell identity")
    op.create_index("uq_backtest_results_owner_run_cell", "backtest_results",
                    ["owner_id", "run_id", "cell_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_backtest_results_owner_run_cell", table_name="backtest_results")
    op.drop_column("backtest_results", "strategy_version")
    op.drop_column("backtest_results", "cell_key")
    op.drop_column("backtest_runs", "request_json")
