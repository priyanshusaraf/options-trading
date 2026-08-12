"""Versioned addition of durable owner-scoped research operation authority."""
from sqlalchemy.schema import CreateIndex, CreateTable

VERSION = "0002"


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade(connection, table) -> None:
    names = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
    temporary = f"{table.name}__owner_tmp"
    if table.name not in names and temporary in names:
        connection.exec_driver_sql(f"ALTER TABLE {_quote(temporary)} RENAME TO {_quote(table.name)}")
    elif table.name not in names:
        connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)))
    elif temporary in names:
        connection.exec_driver_sql(f"DROP TABLE {_quote(temporary)}")
    existing = {row[1] for row in connection.exec_driver_sql(f"PRAGMA index_list({_quote(table.name)})")}
    for index in table.indexes:
        if index.name not in existing:
            connection.exec_driver_sql(str(CreateIndex(index).compile(dialect=connection.dialect)))


def downgrade(connection, table) -> None:
    """Only an empty 0002 control table may be removed by a maintenance rollback."""
    if connection.exec_driver_sql(f"SELECT 1 FROM {_quote(table.name)} LIMIT 1").first() is not None:
        raise RuntimeError("0002 refuses destructive removal of durable operation history")
    connection.exec_driver_sql(f"DROP TABLE {_quote(table.name)}")
