"""Add Phase 4 canonical market-truth reference facts.

Revision ID: 0036
Revises: 0035
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.models import (MarketDataCapabilityProfile, MarketTruthInstrument,
                               MarketTruthProviderMapping, MarketTruthSnapshotRecord)
    for table in (MarketTruthInstrument.__table__, MarketTruthProviderMapping.__table__,
                  MarketTruthSnapshotRecord.__table__, MarketDataCapabilityProfile.__table__):
        table.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("0036 refuses destructive removal of Phase 4 provenance")
