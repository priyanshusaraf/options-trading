"""Keep exact V2 publication receipts beside immutable graph facts."""
from alembic import op
import sqlalchemy as sa

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None
TABLE = "ir_v2_graph_versions"
COLUMN = "publication_receipt_json"


def _source(connection, expected):
    if connection.dialect.name == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif connection.dialect.name == "postgresql":
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200053)")
    else:
        raise RuntimeError("0053 unsupported database dialect")
    heads = tuple(connection.execute(sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
    if heads != (expected,):
        raise RuntimeError(f"0053 requires exact {expected} source")


def _has_receipts(connection):
    return connection.execute(sa.text(
        f"SELECT 1 FROM {TABLE} WHERE {COLUMN} IS NOT NULL LIMIT 1")).first() is not None


def _existing_column(connection):
    column = next((item for item in sa.inspect(connection).get_columns(TABLE) if item["name"] == COLUMN), None)
    if column is None:
        return False
    # Frozen0037 historically creates the then-current model on unmanaged adoption.
    # Accept only its exact empty expansion; never invent or overwrite receipts.
    if not isinstance(column["type"], sa.Text) or not column["nullable"] or column.get("default") is not None:
        raise RuntimeError("0053 refuses an unexpected publication receipt column")
    if _has_receipts(connection):
        raise RuntimeError("0053 refuses preexisting receipt data at the prior head")
    return True


def upgrade():
    connection = op.get_bind()
    _source(connection, "0052")
    if not _existing_column(connection):
        op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True))


def downgrade():
    connection = op.get_bind()
    _source(connection, "0053")
    if _has_receipts(connection):
        raise RuntimeError("0053 refuses to discard publication receipts; use restore or forward repair")
    op.drop_column(TABLE, COLUMN)
