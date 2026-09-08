"""Add presentation-only persistence for canonical Component IR v2 editing.

The table is additive USER-plane state.  Old binaries ignore it.  There is no
backfill: an absent row means canonical empty presentation revision zero.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

TABLE = "ir_v2_editor_presentations"


def _json_valid(dialect: str) -> str:
    return "presentation_json IS JSON" if dialect == "postgresql" else "json_valid(presentation_json)"


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0047 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200047)")
    if TABLE in sa.inspect(connection).get_table_names():
        raise RuntimeError("0047 refuses a partial or pre-existing presentation table")
    op.create_table(
        TABLE,
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("presentation_json", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "graph_identifier",
                                name="pk_ir_v2_editor_presentations"),
        sa.ForeignKeyConstraint(
            ("owner_id", "graph_identifier"),
            ("graph_artifacts.owner_id", "graph_artifacts.identifier"),
            name="fk_ir_v2_editor_presentations_graph", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("format_version = 2", name="ck_ir_v2_editor_presentations_format"),
        sa.CheckConstraint("revision >= 0", name="ck_ir_v2_editor_presentations_revision"),
        sa.CheckConstraint(_json_valid(dialect), name="ck_ir_v2_editor_presentations_valid_json"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if TABLE not in sa.inspect(connection).get_table_names():
        return
    count = connection.scalar(sa.text(f"SELECT count(*) FROM {TABLE}"))
    if count:
        raise RuntimeError("0047 refuses to drop nonempty presentation facts; restore or forward repair")
    op.drop_table(TABLE)
