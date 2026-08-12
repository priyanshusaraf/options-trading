"""Add execution-plane transactional outbox tables.

Revision ID: 0033
Revises: 0032
"""
from alembic import op

from app.db.models import EXECUTION_OUTBOX_MODELS

revision, down_revision = "0033", "0032"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (
        EXECUTION_OUTBOX_MODELS.StreamHead,
        EXECUTION_OUTBOX_MODELS.Event,
        EXECUTION_OUTBOX_MODELS.ConsumerCursor,
        EXECUTION_OUTBOX_MODELS.ConsumerReceipt,
        EXECUTION_OUTBOX_MODELS.RetentionWatermark,
    ):
        model.__table__.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    for model in (
        EXECUTION_OUTBOX_MODELS.RetentionWatermark,
        EXECUTION_OUTBOX_MODELS.ConsumerReceipt,
        EXECUTION_OUTBOX_MODELS.ConsumerCursor,
        EXECUTION_OUTBOX_MODELS.Event,
        EXECUTION_OUTBOX_MODELS.StreamHead,
    ):
        model.__table__.drop(bind)
