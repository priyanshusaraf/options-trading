"""record L1 Stage 1 shadow-lane disagreements

Telemetry only. Nothing in the execution path reads this table; it exists so a
disagreement between the authoritative strategy and its Component IR mirror can be
attributed afterwards to an exact graph version, bar and input frame.

`ir_json` is deliberately nullable with no default: NULL means the graph produced no
verdict at all, which is a different fact from a verdict of four false flags.

Revision ID: 0010
Revises: 0009
Created: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_shadow_divergences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("bar_time", sa.DateTime(), nullable=True),
        sa.Column("instrument_key", sa.String(32), nullable=False),
        sa.Column("authoritative_strategy_key", sa.String(64), nullable=False),
        sa.Column("shadow_strategy_key", sa.String(64), nullable=False),
        sa.Column("graph_address", sa.String(71), nullable=False),
        sa.Column("authoritative_json", sa.Text(), nullable=True),
        sa.Column("ir_json", sa.Text(), nullable=True),
        sa.Column("warmup_state", sa.String(16), nullable=False),
        sa.Column("declared_warmup", sa.Integer(), nullable=False),
        sa.Column("frame_id", sa.String(71), nullable=False),
        sa.Column("frame_bars", sa.Integer(), nullable=False),
        sa.Column("frame_first_ts", sa.DateTime(), nullable=True),
        sa.Column("frame_last_ts", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("detail", sa.String(400), nullable=False),
        sa.Column("eval_ms", sa.Float(), nullable=False),
        sa.Column("market_open", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_ir_shadow_divergences_observed_at", "ir_shadow_divergences",
                    ["observed_at"])
    op.create_index("ix_ir_shadow_divergences_instrument_key", "ir_shadow_divergences",
                    ["instrument_key"])
    op.create_index("ix_ir_shadow_divergences_reason", "ir_shadow_divergences", ["reason"])
    op.create_index("ix_ir_shadow_divergences_observed", "ir_shadow_divergences",
                    ["observed_at"])
    # The signal lane re-scans the same completed bar every 2.5 s until the next one
    # prints, so one bar would otherwise arrive dozens of times.
    op.create_index("uq_ir_shadow_divergence_bar", "ir_shadow_divergences",
                    ["instrument_key", "bar_time", "graph_address", "reason"], unique=True)


def downgrade() -> None:
    # Idempotent by inspection, the same shape as 0008 and 0009. A downgrade in this
    # chain can abort in a *later* revision's guard after this one has already run, and
    # the retry must then fail on that guard rather than on a table that is already gone.
    # Only the table is dropped: its indexes go with it, so naming them adds two more
    # ways to die on the retry and no safety.
    #
    # No refusal on non-empty. Unlike review notes, these rows are telemetry the platform
    # produced, reproducible by re-running the shadow lane; there is no user writing here
    # to lose.
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("ir_shadow_divergences"):
        return
    op.drop_table("ir_shadow_divergences")
