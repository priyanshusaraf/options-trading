"""Add immutable owner-scoped causal-admission receipts to research.

The consumer columns are deliberately nullable: a 0004 row has no independently
recomputable receipt merely because this schema revision exists, so it remains
``LEGACY_UNADMITTED`` until a later exact backfill proves it.
"""
from __future__ import annotations

from sqlalchemy import CheckConstraint, inspect
from sqlalchemy.schema import CreateColumn


VERSION = "0005"


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _address_constraint(table):
    return next(
        constraint for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == f"ck_{table.name}_admission_address"
    )


def _add_nullable_address(connection, table) -> None:
    existing = {column["name"] for column in inspect(connection).get_columns(table.name)}
    if "admission_address" in existing:
        return
    column_sql = str(CreateColumn(table.c.admission_address).compile(
        dialect=connection.dialect))
    constraint = _address_constraint(table)
    check_sql = str(constraint.sqltext.compile(dialect=connection.dialect))
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql(
            f"ALTER TABLE {_quoted(table.name)} ADD COLUMN {column_sql}")
        connection.exec_driver_sql(
            f"ALTER TABLE {_quoted(table.name)} ADD CONSTRAINT {_quoted(constraint.name)} "
            f"CHECK ({check_sql})")
        return
    connection.exec_driver_sql(
        f"ALTER TABLE {_quoted(table.name)} ADD COLUMN {column_sql} "
        f"CONSTRAINT {_quoted(constraint.name)} CHECK ({check_sql})")


def upgrade(connection, admission_table, consumer_tables) -> None:
    """Create the append-only store and add nullable checked consumer addresses."""
    admission_table.create(connection, checkfirst=True)
    for table in consumer_tables:
        _add_nullable_address(connection, table)


def downgrade(_connection, _admission_table, _consumer_tables) -> None:
    raise RuntimeError("0005 refuses destructive removal of causal admission receipts")
