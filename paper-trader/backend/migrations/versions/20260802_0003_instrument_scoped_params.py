"""instrument-scoped parameter overrides

Revision ID: 0003
Revises: 0002
Created: 2026-08-02

Phase C. Completes the Platform -> Deployment -> Instrument resolution chain by
giving `instrument_state` the same `params_json` shape `deployments` already has.

Why a JSON column rather than a generic (scope, scope_id, key, value) table:
`runtime_config` is already that table at platform scope, and it earns the shape
because the Settings UI edits one key at a time and needs per-key provenance
(`overridden`). Deployment and instrument overrides are written as a set — a
deployment's parameters arrive and change together — so a blob is the honest
representation and avoids a three-way join on the signal loop's hot path.

Empty `{}` on every row means "inherit everything", so this revision changes no
behaviour whatsoever: `resolve()` with an all-empty instrument layer returns
exactly what `effective()` returned before it existed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instrument_state",
                  sa.Column("params_json", sa.Text(), nullable=False,
                            server_default="{}"))
    op.execute("UPDATE instrument_state SET params_json = '{}' "
               "WHERE params_json IS NULL")


def downgrade() -> None:
    # Dropping this loses any instrument-scoped tuning that was set. That is
    # information destruction, but it is recoverable-by-retyping rather than
    # irreversible (no money record is involved), so the downgrade is allowed to
    # proceed rather than refusing.
    with op.batch_alter_table("instrument_state") as batch:
        batch.drop_column("params_json")
