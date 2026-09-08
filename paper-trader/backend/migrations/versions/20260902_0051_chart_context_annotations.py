"""Add private owner-scoped research chart annotation presentation rows."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None
TABLE = "chart_context_annotations"


def _heads(connection) -> tuple[str, ...]:
    return tuple(connection.execute(sa.text(
        "SELECT version_num FROM alembic_version ORDER BY version_num"
    )).scalars())


def _lock(connection) -> None:
    if connection.dialect.name == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif connection.dialect.name == "postgresql":
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200051)")
    else:
        raise RuntimeError("0051 unsupported database dialect")


def upgrade() -> None:
    connection = op.get_bind()
    _lock(connection)
    heads = _heads(connection)
    if heads != ("0050",):
        raise RuntimeError(f"0051 requires exact 0050 source; found heads={list(heads)}")
    if TABLE in set(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0051 refuses a partial pre-existing annotation table")
    is_sqlite = connection.dialect.name == "sqlite"
    address = ("length(%s) = 71 AND substr(%s,1,7) = 'sha256:' AND "
               "substr(%s,8) = lower(substr(%s,8)) AND substr(%s,8) NOT GLOB '*[^0-9a-f]*'") if is_sqlite else "%s ~ '^sha256:[0-9a-f]{64}$'"
    def address_check(column: str) -> str:
        return address % ((column,) * (5 if is_sqlite else 1))
    json_geometry = "json_valid(geometry_json)" if is_sqlite else "CAST(geometry_json AS JSONB) IS NOT NULL"
    json_applicability = "json_valid(applicability_json)" if is_sqlite else "CAST(applicability_json AS JSONB) IS NOT NULL"
    geometry_size = "length(CAST(geometry_json AS BLOB)) <= 65536" if is_sqlite else "octet_length(geometry_json) <= 65536"
    applicability_size = "length(CAST(applicability_json AS BLOB)) <= 65536" if is_sqlite else "octet_length(applicability_json) <= 65536"
    op.create_table(TABLE,
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("market_context_address", sa.String(71), nullable=False),
        sa.Column("annotation_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("dataset_manifest_address", sa.String(71), nullable=False),
        sa.Column("canonical_instrument_address", sa.String(71), nullable=False),
        sa.Column("timeframe_seconds", sa.Integer(), nullable=False),
        sa.Column("geometry_address", sa.String(71), nullable=False),
        sa.Column("geometry_json", sa.Text(), nullable=False),
        sa.Column("applicability_address", sa.String(71), nullable=False),
        sa.Column("applicability_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "market_context_address", "annotation_id",
                                name="pk_chart_context_annotations"),
        sa.ForeignKeyConstraint(["owner_id"], ["organizations.organization_id"],
                                ondelete="CASCADE", name="fk_chart_context_annotations_owner"),
        sa.CheckConstraint(address_check("market_context_address"), name="ck_chart_context_annotations_context_address"),
        sa.CheckConstraint(address_check("dataset_manifest_address"), name="ck_chart_context_annotations_dataset_address"),
        sa.CheckConstraint(address_check("canonical_instrument_address"), name="ck_chart_context_annotations_instrument_address"),
        sa.CheckConstraint(address_check("geometry_address"), name="ck_chart_context_annotations_geometry_address"),
        sa.CheckConstraint(address_check("applicability_address"), name="ck_chart_context_annotations_applicability_address"),
        sa.CheckConstraint(json_geometry, name="ck_chart_context_annotations_geometry_json"),
        sa.CheckConstraint(json_applicability, name="ck_chart_context_annotations_applicability_json"),
        sa.CheckConstraint(geometry_size, name="ck_chart_context_annotations_geometry_size"),
        sa.CheckConstraint(applicability_size, name="ck_chart_context_annotations_applicability_size"),
        sa.CheckConstraint("revision >= 1", name="ck_chart_context_annotations_revision"),
        sa.CheckConstraint("timeframe_seconds > 0", name="ck_chart_context_annotations_timeframe"),
    )
    op.create_index("ix_chart_context_annotations_owner_context_updated", TABLE,
                    ["owner_id", "market_context_address", "updated_at"])


def downgrade() -> None:
    connection = op.get_bind()
    _lock(connection)
    if _heads(connection) != ("0051",):
        raise RuntimeError("0051 downgrade requires exact 0051 source")
    if TABLE not in set(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0051 downgrade refuses a missing annotation table")
    if connection.scalar(sa.text(f"SELECT count(*) FROM {TABLE}")):
        raise RuntimeError("0051 refuses to discard annotation rows; use restore or forward repair")
    op.drop_table(TABLE)
