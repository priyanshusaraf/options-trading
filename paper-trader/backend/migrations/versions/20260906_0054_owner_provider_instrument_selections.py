"""Add immutable USER provider selections; no research or execution authority.

Frozen additive DDL. V2 watchlists require coordinated readers; no facts are
backfilled or removed and downgrade is forward-repair/restore only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None
TABLE = "owner_provider_instrument_selections"
DDL = {'sqlite': "\nCREATE TABLE owner_provider_instrument_selections (\n\towner_id VARCHAR(64) NOT NULL, \n\tselection_address VARCHAR(71) NOT NULL, \n\tdata_account_id VARCHAR(64) NOT NULL, \n\tconnection_id BIGINT NOT NULL, \n\tprovider VARCHAR(16) NOT NULL, \n\treference_fingerprint VARCHAR(71) NOT NULL, \n\tobserved_at DATETIME NOT NULL, \n\tcanonical_json TEXT NOT NULL, \n\tPRIMARY KEY (owner_id, selection_address), \n\tCONSTRAINT fk_provider_selections_owner FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_provider_selections_descriptor UNIQUE (owner_id, data_account_id, provider, reference_fingerprint), \n\tCONSTRAINT ck_provider_selections_owner CHECK (length(owner_id) BETWEEN 1 AND 64), \n\tCONSTRAINT ck_provider_selections_account CHECK (length(data_account_id) BETWEEN 1 AND 64), \n\tCONSTRAINT ck_provider_selections_connection CHECK (connection_id > 0), \n\tCONSTRAINT ck_provider_selections_provider CHECK (provider = 'ZERODHA'), \n\tCONSTRAINT ck_provider_selections_address CHECK (length(selection_address) = 71 AND substr(selection_address, 1, 7) = 'sha256:' AND substr(selection_address, 8) = lower(substr(selection_address, 8)) AND substr(selection_address, 8) NOT GLOB '*[^0-9a-f]*'), \n\tCONSTRAINT ck_provider_selections_fingerprint CHECK (length(reference_fingerprint) = 71 AND substr(reference_fingerprint, 1, 7) = 'sha256:' AND substr(reference_fingerprint, 8) = lower(substr(reference_fingerprint, 8)) AND substr(reference_fingerprint, 8) NOT GLOB '*[^0-9a-f]*'), \n\tCONSTRAINT ck_provider_selections_json CHECK (json_valid(canonical_json)), \n\tCONSTRAINT ck_provider_selections_size CHECK (length(CAST(canonical_json AS BLOB)) <= 8192)\n)\n\n", 'postgresql': "\nCREATE TABLE owner_provider_instrument_selections (\n\towner_id VARCHAR(64) NOT NULL, \n\tselection_address VARCHAR(71) NOT NULL, \n\tdata_account_id VARCHAR(64) NOT NULL, \n\tconnection_id BIGINT NOT NULL, \n\tprovider VARCHAR(16) NOT NULL, \n\treference_fingerprint VARCHAR(71) NOT NULL, \n\tobserved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tcanonical_json TEXT NOT NULL, \n\tPRIMARY KEY (owner_id, selection_address), \n\tCONSTRAINT fk_provider_selections_owner FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_provider_selections_descriptor UNIQUE (owner_id, data_account_id, provider, reference_fingerprint), \n\tCONSTRAINT ck_provider_selections_owner CHECK (length(owner_id) BETWEEN 1 AND 64), \n\tCONSTRAINT ck_provider_selections_account CHECK (length(data_account_id) BETWEEN 1 AND 64), \n\tCONSTRAINT ck_provider_selections_connection CHECK (connection_id > 0), \n\tCONSTRAINT ck_provider_selections_provider CHECK (provider = 'ZERODHA'), \n\tCONSTRAINT ck_provider_selections_address CHECK (selection_address ~ '^sha256:[0-9a-f]{64}$'), \n\tCONSTRAINT ck_provider_selections_fingerprint CHECK (reference_fingerprint ~ '^sha256:[0-9a-f]{64}$'), \n\tCONSTRAINT ck_provider_selections_json CHECK (CAST(canonical_json AS JSONB) IS NOT NULL), \n\tCONSTRAINT ck_provider_selections_size CHECK (octet_length(canonical_json) <= 8192)\n)\n\n"}


def _source(connection):
    dialect = connection.dialect.name
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif dialect == "postgresql":
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200054)")
    else:
        raise RuntimeError("0054 unsupported database dialect")
    heads = tuple(connection.execute(sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
    if heads != ("0053",):
        raise RuntimeError("0054 requires exact 0053 source")
    if TABLE in sa.inspect(connection).get_table_names():
        raise RuntimeError("0054 refuses a partial pre-existing selection table; forward repair required")
    return dialect


def _immutable(connection, dialect):
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER {TABLE}_refuse_{action.lower()} BEFORE {action} ON {TABLE} "
                "BEGIN SELECT RAISE(ABORT, 'provider selections are immutable'); END")
        return
    connection.exec_driver_sql(
        f"CREATE OR REPLACE FUNCTION {TABLE}_refuse_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'provider selections are immutable'; END; $$ LANGUAGE plpgsql")
    connection.exec_driver_sql(
        f"CREATE TRIGGER {TABLE}_refuse_mutation BEFORE UPDATE OR DELETE ON {TABLE} "
        f"FOR EACH ROW EXECUTE FUNCTION {TABLE}_refuse_mutation()")


def upgrade():
    connection = op.get_bind()
    dialect = _source(connection)
    connection.exec_driver_sql(DDL[dialect])
    _immutable(connection, dialect)


def downgrade():
    raise RuntimeError("0054 retains provider selections and v2 watchlists; use restore or forward repair")
