"""Split tenant portfolio choices from canonical universe facts.

Revision ID: 0031
Revises: 0030
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision, down_revision = "0031", "0030"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "universe_preferences",
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("instrument_key", sa.String(48), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("on_home", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(8), nullable=False, server_default="seed"),
        sa.PrimaryKeyConstraint("owner_id", "instrument_key"),
        sa.ForeignKeyConstraint(("owner_id",), ("organizations.organization_id",), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("instrument_key",), ("universe_instruments.key",), ondelete="RESTRICT"),
    )
    op.create_index("ix_universe_preferences_owner", "universe_preferences", ["owner_id"])
    op.execute(sa.text("""
        INSERT INTO universe_preferences (owner_id, instrument_key, active, on_home, source)
        SELECT 'owner', key, active, on_home, source FROM universe_instruments
        WHERE NOT EXISTS (
            SELECT 1 FROM universe_preferences p
            WHERE p.owner_id = 'owner' AND p.instrument_key = universe_instruments.key
        )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind is not None and bind.execute(sa.text("""
        SELECT 1
        FROM universe_preferences p
        LEFT JOIN universe_instruments u ON u.key = p.instrument_key
        WHERE p.owner_id <> 'owner'
           OR u.key IS NULL
           OR (p.owner_id = 'owner' AND (
               p.active <> u.active OR p.on_home <> u.on_home OR p.source <> u.source
           ))
        LIMIT 1
    """)).first():
        raise RuntimeError("0031 downgrade refuses to discard changed tenant universe preferences")
    op.drop_index("ix_universe_preferences_owner", table_name="universe_preferences")
    op.drop_table("universe_preferences")
