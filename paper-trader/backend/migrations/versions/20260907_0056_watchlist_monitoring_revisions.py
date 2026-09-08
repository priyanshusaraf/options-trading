"""Append immutable per-watchlist-member monitoring configuration revisions.

No histories are rewritten or dropped. Roll back application code only if it
accepts this additive head; schema recovery is restore or forward repair.
"""
from alembic import op
import sqlalchemy as sa

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None
TABLE = "watchlist_monitoring_revisions"
PREFIX = "watchlist_monitoring"


def _source(connection):
    dialect = connection.dialect.name
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif dialect == "postgresql":
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200056)")
    else:
        raise RuntimeError("0056 unsupported database dialect")
    heads = tuple(connection.execute(sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
    if heads != ("0055",):
        raise RuntimeError("0056 requires exact 0055 source")
    if TABLE in sa.inspect(connection).get_table_names():
        raise RuntimeError("0056 refuses partial pre-existing watchlist monitoring history")
    return dialect == "sqlite"


def _address(column, sqlite):
    if sqlite:
        return (f"length({column}) = 71 AND substr({column},1,7) = 'sha256:' AND "
                f"substr({column},8) = lower(substr({column},8)) AND "
                f"substr({column},8) NOT GLOB '*[^0-9a-f]*'")
    return f"{column} ~ '^sha256:[0-9a-f]{{64}}$'"


def _copied(column, sqlite, *, number=False):
    if sqlite:
        return f"json_extract(canonical_json, '$.{column}') IS {column}"
    field = f"CAST(canonical_json AS JSONB) -> '{column}'"
    kind = "number" if number else "string"
    value = f"({field} #>> '{{}}')::numeric" if number else f"CAST(canonical_json AS JSONB) ->> '{column}'"
    return f"{field} IS NOT NULL AND jsonb_typeof({field}) = '{kind}' AND {value} = {column}"


def _checks(sqlite):
    checks = {
        "revision": "revision > 0", "member": "length(member_key) BETWEEN 1 AND 128",
        "request": "length(request_id) = 36",
        "predecessor": "(revision = 1 AND predecessor_address IS NULL) OR (revision > 1 AND predecessor_address IS NOT NULL)",
        "intent": "monitoring_intent IN ('MONITOR', 'PAUSE')",
        "address": _address("address", sqlite),
        "predecessor_address": "predecessor_address IS NULL OR (" + _address("predecessor_address", sqlite) + ")",
        "json": "json_valid(canonical_json)" if sqlite else "CAST(canonical_json AS JSONB) IS NOT NULL",
        "size": "length(CAST(canonical_json AS BLOB)) <= 16384" if sqlite else "octet_length(canonical_json) <= 16384",
        "copy_revision": _copied("revision", sqlite, number=True),
    }
    checks.update({"copy_" + key: _copied(key, sqlite) for key in
                   ("address", "owner_id", "project_id", "scope_id", "member_key", "monitoring_intent")})
    return [sa.CheckConstraint(value, name="ck_" + PREFIX + "_" + name) for name, value in checks.items()]


def _create(sqlite):
    keys = ("owner_id", "project_id", "scope_id", "member_key")
    op.create_table(TABLE,
        *(sa.Column(name, sa.String(128 if name == "member_key" else 64), nullable=False) for name in keys),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("address", sa.String(71), nullable=False),
        sa.Column("predecessor_address", sa.String(71), nullable=True),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("monitoring_intent", sa.String(8), nullable=False),
        sa.Column("assignment_id", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint(*keys, "revision"),
        sa.ForeignKeyConstraint(keys[:3], ["static_instrument_scopes." + key for key in keys[:3]],
                                name="fk_" + PREFIX + "_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_" + PREFIX + "_creator", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id", "assignment_id"],
            ["monitoring_assignments.owner_id", "monitoring_assignments.assignment_id"],
            name="fk_" + PREFIX + "_assignment", ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_" + PREFIX + "_request"),
        sa.UniqueConstraint(*keys, "address", name="uq_" + PREFIX + "_chain"),
        sa.ForeignKeyConstraint((*keys, "predecessor_address"), [TABLE + "." + key for key in (*keys, "address")],
                                name="fk_" + PREFIX + "_predecessor", ondelete="RESTRICT"),
        *_checks(sqlite))


def _immutable(sqlite):
    message = "watchlist monitoring revisions are immutable"
    if sqlite:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER {TABLE}_refuse_{action.lower()} BEFORE {action} ON {TABLE} "
                       f"BEGIN SELECT RAISE(ABORT, '{message}'); END")
        return
    name = TABLE + "_refuse_mutation"
    op.execute(f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION '{message}'; END; $$ LANGUAGE plpgsql")
    op.execute(f"CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION {name}()")


def upgrade():
    sqlite = _source(op.get_bind())
    _create(sqlite)
    _immutable(sqlite)


def downgrade():
    raise RuntimeError("0056 retains watchlist monitoring history; use restore or forward repair")
