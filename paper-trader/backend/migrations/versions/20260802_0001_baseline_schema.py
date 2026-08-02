"""baseline schema (pre-Alembic state, 2026-08-02)

Revision ID: 0001
Revises:
Created: 2026-08-02

THE BASELINE. This revision deliberately does nothing.

Everything the execution database contained on 2026-08-02 was built by
`Base.metadata.create_all()` plus the hand-maintained ADD COLUMN dict in
`app/db/session.py:_migrate_schema()`. That state is the floor: revision 0001
*names* it so later revisions have something to be "after", and so a database
that predates Alembic can be stamped rather than rebuilt.

The canonical DDL of that floor is checked in at
`migrations/baseline_schema.ddl`, generated from the models at this commit. It is
not executed here — a live database already has it. It exists so
`tests/test_schema_migrations.py` can build a synthetic pre-Alembic database and
prove that migrating it forward lands on exactly the schema the ORM expects.

`_migrate_schema()` is frozen as of this revision: it may be read, never extended.
`tests/test_migrate_schema_frozen.py` fails the build if a column is added to it.
Every schema change from here on is a revision in this directory.
"""
from __future__ import annotations

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: the baseline describes a schema that already exists."""


def downgrade() -> None:
    """No-op: there is nothing below the baseline."""
