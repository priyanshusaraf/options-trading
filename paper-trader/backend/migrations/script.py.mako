"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Created: ${create_date}

Every revision must be reversible. `downgrade()` raising NotImplementedError is
allowed ONLY when the change genuinely destroys information (dropping a populated
column); say so in a comment. Anything else must roll back cleanly — an
un-backable-out migration on a live money ledger is not a migration, it is a leap.

SQLite cannot ALTER in place: use `op.batch_alter_table(...)` for anything that is
not a plain ADD COLUMN.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
