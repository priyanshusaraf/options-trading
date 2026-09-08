"""Append immutable owner and strategy research preference histories."""
from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None
TABLES = ("workspace_research_settings_revisions", "strategy_research_settings_revisions")


def _lock(connection):
    if connection.dialect.name == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif connection.dialect.name == "postgresql":
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200052)")
    else:
        raise RuntimeError("0052 unsupported database dialect")


def _require_source(connection, expected):
    _lock(connection)
    heads = tuple(connection.execute(sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
    if heads != (expected,):
        raise RuntimeError(f"0052 requires exact {expected} source")


def _checks(prefix, sqlite):
    address = ("length(content_address) = 71 AND substr(content_address,1,7) = 'sha256:' AND "
               "substr(content_address,8) = lower(substr(content_address,8)) AND "
               "substr(content_address,8) NOT GLOB '*[^0-9a-f]*'") if sqlite else "content_address ~ '^sha256:[0-9a-f]{64}$'"
    valid_json = "json_valid(document_json)" if sqlite else "CAST(document_json AS JSONB) IS NOT NULL"
    size = "length(CAST(document_json AS BLOB)) <= 4096" if sqlite else "octet_length(document_json) <= 4096"
    return [sa.CheckConstraint(sql, name=f"ck_{prefix}_research_settings_{name}") for name, sql in
            (("revision", "revision >= 1"), ("address", address), ("json", valid_json), ("size", size))]


def _create(table, strategy, sqlite):
    prefix = "strategy" if strategy else "workspace"
    keys = ["owner_id", "graph_identifier", "revision"] if strategy else ["owner_id", "revision"]
    columns = [sa.Column("owner_id", sa.String(64), nullable=False),
               sa.Column("revision", sa.Integer(), nullable=False),
               sa.Column("request_id", sa.String(36), nullable=False),
               sa.Column("document_json", sa.Text(), nullable=False),
               sa.Column("content_address", sa.String(71), nullable=False),
               sa.Column("created_by", sa.String(64), nullable=False),
               sa.Column("created_at", sa.DateTime(), nullable=False)]
    if strategy:
        columns.append(sa.Column("graph_identifier", sa.String(128), nullable=False))
        owner_fk = sa.ForeignKeyConstraint(["owner_id", "graph_identifier"], ["graph_artifacts.owner_id", "graph_artifacts.identifier"], ondelete="RESTRICT")
    else:
        owner_fk = sa.ForeignKeyConstraint(["owner_id"], ["organizations.organization_id"])
    op.create_table(table, *columns, sa.PrimaryKeyConstraint(*keys), owner_fk,
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.UniqueConstraint(*keys[:-1], "request_id", name=f"uq_{prefix}_research_settings_request"),
        *_checks(prefix, sqlite))
    _immutable(table, sqlite)


def _immutable(table, sqlite):
    if sqlite:
        for operation in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER {table}_refuse_{operation.lower()} BEFORE {operation} ON {table} "
                       f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END")
        return
    name = f"{table}_refuse_mutation"
    op.execute(f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION '{table} is immutable'; END; $$ LANGUAGE plpgsql")
    op.execute(f"CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()")


def upgrade():
    connection = op.get_bind()
    _require_source(connection, "0051")
    if set(TABLES) & set(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0052 refuses partial pre-existing settings histories")
    for table, strategy in zip(TABLES, (False, True)):
        _create(table, strategy, connection.dialect.name == "sqlite")


def downgrade():
    connection = op.get_bind()
    _require_source(connection, "0052")
    for table in TABLES:
        if connection.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError("0052 refuses to discard research settings history; use restore or forward repair")
    for table in reversed(TABLES):
        op.drop_table(table)
        if connection.dialect.name == "postgresql":
            op.execute(f"DROP FUNCTION {table}_refuse_mutation()")
