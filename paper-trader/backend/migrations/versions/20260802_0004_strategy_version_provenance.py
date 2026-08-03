"""strategy version provenance on the money record

Revision ID: 0004
Revises: 0003
Created: 2026-08-02

Phase D. `strategy_key` alone cannot say WHICH strategy executed a trade, because a
key is mutable: `generated_strategies.key` is the primary key with no version, so
redeploying an edited strategy rewrites history in place — past trades attributed to
`gen_x` silently start pointing at different logic. Every backtest, attribution
report and marketplace performance claim built on that is unfalsifiable.

This adds the content hash alongside the key on the rows that record an execution.

NULLABLE WITH NO DEFAULT, deliberately — the same three-value rule `trades.build_sha`
already establishes, and for the same reason:

    a hash      this row's strategy is identified
    'unknown'   the strategy was running but could not be identified
    NULL        the row predates the column, and is genuinely unattributable

Backfilling existing rows with a hash computed today would assert that the current
source is what executed them, which is exactly the lie the column exists to prevent.
The 72 real trades stay NULL.

`generated_strategies.version` is added but `key` remains the primary key. Making
identity `(key, version)` is a larger change — it needs the deploy bridge to write
both, and the registry to resolve both — and it is recorded in
`docs/reports/2026-08-02-architecture-migration.md` as remaining work rather than half-done
here.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No server_default on either: see the module docstring. A default would make
    # every legacy row claim a provenance it does not have.
    op.add_column("positions", sa.Column("strategy_version", sa.String(64),
                                         nullable=True))
    op.add_column("trades", sa.Column("strategy_version", sa.String(64),
                                      nullable=True))
    op.add_column("generated_strategies", sa.Column("version", sa.String(64),
                                                    nullable=True))


def downgrade() -> None:
    for table, col in (("positions", "strategy_version"),
                       ("trades", "strategy_version"),
                       ("generated_strategies", "version")):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(col)
