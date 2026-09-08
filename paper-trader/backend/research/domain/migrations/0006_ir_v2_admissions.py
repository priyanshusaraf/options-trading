"""Add v2 receipt semantic identity without assigning values to v1 rows."""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.schema import CreateColumn

VERSION = "0006"


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def upgrade(connection, admission_table) -> None:
    existing = {column["name"] for column in inspect(connection).get_columns(admission_table.name)}
    for name in ("format_version", "content_address"):
        if name in existing:
            continue
        column_sql = str(CreateColumn(admission_table.c[name]).compile(dialect=connection.dialect))
        connection.exec_driver_sql(
            f"ALTER TABLE {_quoted(admission_table.name)} ADD COLUMN {column_sql}")


def downgrade(_connection, _admission_table) -> None:
    raise RuntimeError("0006 refuses destructive removal of immutable v2 receipt identity")
