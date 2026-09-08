"""Record successful session-bound data-connection OAuth completion.

The state was already consumed before provider exchange at 0049.  A nullable,
unbackfilled completion timestamp is the smallest fact that distinguishes a
successful credential write from a consumed-but-failed callback.  Credential
writers are quiesced while this additive migration runs.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None

TABLE = "oauth_callback_states"
COLUMN = "credential_stored_at"


def _heads(connection) -> tuple[str, ...]:
    return tuple(connection.execute(sa.text(
        "SELECT version_num FROM alembic_version ORDER BY version_num"
    )).scalars())


def _columns(connection) -> set[str]:
    return {str(column["name"]) for column in sa.inspect(connection).get_columns(TABLE)}


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0050 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200050)")
    heads = _heads(connection)
    if heads != ("0049",):
        raise RuntimeError(f"0050 requires exact 0049 source; found heads={list(heads)}")
    if TABLE not in set(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0050 requires oauth_callback_states")
    if COLUMN in _columns(connection):
        raise RuntimeError("0050 refuses a partial pre-existing completion column")
    op.add_column(TABLE, sa.Column(COLUMN, sa.DateTime(), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0050 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200050)")
    heads = _heads(connection)
    if heads != ("0050",):
        raise RuntimeError(f"0050 downgrade requires exact 0050 source; found heads={list(heads)}")
    if COLUMN not in _columns(connection):
        raise RuntimeError("0050 downgrade refuses a missing completion column")
    completed = connection.scalar(sa.text(
        f"SELECT count(*) FROM {TABLE} WHERE {COLUMN} IS NOT NULL"
    ))
    if completed:
        raise RuntimeError(
            "0050 refuses to discard successful OAuth completion facts; "
            "keep the additive schema or use restore/forward repair"
        )
    op.drop_column(TABLE, COLUMN)
