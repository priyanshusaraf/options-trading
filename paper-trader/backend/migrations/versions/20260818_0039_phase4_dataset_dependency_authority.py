"""Add the nine closed DatasetManifest dependency authorities.

Revision ID: 0039
Revises: 0038
"""
from __future__ import annotations

from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.models import (
        AuthorityAdjustmentPolicy,
        AuthorityAlignmentPolicy,
        AuthorityDatasetCorrection,
        AuthorityDatasetCreationEvidence,
        AuthorityDeterministicAlgorithm,
        AuthorityMissingDataPolicy,
        AuthorityNormalizationTransform,
        AuthorityRawSchema,
        AuthorityRollPolicy,
    )

    bind = op.get_bind()
    for model in (
        AuthorityRawSchema,
        AuthorityNormalizationTransform,
        AuthorityAlignmentPolicy,
        AuthorityMissingDataPolicy,
        AuthorityAdjustmentPolicy,
        AuthorityRollPolicy,
        AuthorityDatasetCorrection,
        AuthorityDatasetCreationEvidence,
        AuthorityDeterministicAlgorithm,
    ):
        model.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("0039 refuses destructive removal of dataset dependency authority")
