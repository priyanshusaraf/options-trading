"""Add immutable typed Phase 4 dataset bytes and manifest authority."""
from __future__ import annotations


VERSION = "0009"


def upgrade(connection, tables) -> None:
    for table in tables:
        table.create(connection, checkfirst=True)


def downgrade(_connection, _tables) -> None:
    raise RuntimeError("0009 refuses destructive removal of typed dataset authority")
