"""Scope response aliases to contract and retained receipt; preserve /1 facts.

SQLite requires writer quiescence and the managed runner with FK enforcement
suspended outside its atomic rebuild transaction. Restore/forward repair only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None
TABLE = "authority_provider_aliases"
TEMP = "_0055_authority_provider_aliases"
DDL = {'sqlite': ["\nCREATE TABLE authority_provider_aliases (\n\taddress VARCHAR(71) NOT NULL, \n\tschema VARCHAR(64) NOT NULL, \n\tcanonical_json TEXT NOT NULL, \n\tproduct_address VARCHAR(71) NOT NULL, \n\tinstrument_address VARCHAR(71) NOT NULL, \n\tprovider_token VARCHAR(256) NOT NULL, \n\tprovider_symbol VARCHAR(256) NOT NULL, \n\tobservation_namespace VARCHAR(128) NOT NULL, \n\teffective_from DATETIME NOT NULL, \n\teffective_to DATETIME, \n\tauthority_state VARCHAR(24) DEFAULT 'VERIFIED_V2' NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tprovider_contract_address VARCHAR(71), \n\treceipt_address VARCHAR(71), \n\tPRIMARY KEY (address), \n\tFOREIGN KEY(product_address) REFERENCES authority_provider_products (address), \n\tFOREIGN KEY(instrument_address) REFERENCES authority_canonical_instruments (address), \n\tCONSTRAINT ck_authority_provider_alias_interval CHECK (effective_to IS NULL OR effective_to > effective_from), \n\tFOREIGN KEY(provider_contract_address) REFERENCES authority_provider_contracts (address), \n\tFOREIGN KEY(receipt_address) REFERENCES authority_raw_segments (address), \n\tCONSTRAINT ck_authority_provider_alias_scope CHECK ((schema = 'provider-instrument-mapping/1' AND provider_contract_address IS NULL AND receipt_address IS NULL) OR (schema = 'provider-instrument-mapping/2' AND provider_contract_address IS NOT NULL AND receipt_address IS NOT NULL AND effective_to IS NOT NULL)), \n\tCONSTRAINT uq_authority_provider_alias_response UNIQUE (provider_contract_address, receipt_address), \n\tCONSTRAINT ck_authority_provider_aliases_address CHECK (length(address) = 71 AND substr(address, 1, 7) = 'sha256:' AND substr(address, 8) = lower(substr(address, 8)) AND substr(address, 8) NOT GLOB '*[^0-9a-f]*'), \n\tCONSTRAINT ck_authority_provider_aliases_json CHECK (json_valid(canonical_json)), \n\tCONSTRAINT ck_authority_provider_aliases_verified CHECK (authority_state = 'VERIFIED_V2')\n)\n\n", "CREATE UNIQUE INDEX uq_authority_provider_alias_token ON authority_provider_aliases (product_address, observation_namespace, provider_token, effective_from) WHERE schema = 'provider-instrument-mapping/1'", "CREATE TRIGGER authority_provider_aliases_refuse_update BEFORE UPDATE ON authority_provider_aliases BEGIN SELECT RAISE(ABORT, 'authority_provider_aliases is immutable'); END", "CREATE TRIGGER authority_provider_aliases_refuse_delete BEFORE DELETE ON authority_provider_aliases BEGIN SELECT RAISE(ABORT, 'authority_provider_aliases is immutable'); END", "CREATE TRIGGER authority_provider_aliases_refuse_overlap BEFORE INSERT ON authority_provider_aliases BEGIN SELECT CASE WHEN EXISTS (SELECT 1 FROM authority_provider_aliases AS existing WHERE NEW.schema = 'provider-instrument-mapping/1' AND existing.schema = 'provider-instrument-mapping/1' AND existing.product_address = NEW.product_address AND existing.observation_namespace = NEW.observation_namespace AND (existing.provider_token = NEW.provider_token OR existing.provider_symbol = NEW.provider_symbol OR existing.instrument_address = NEW.instrument_address) AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) THEN RAISE(ABORT, 'authority provider alias overlaps') END; END"], 'postgresql': ["\nCREATE TABLE authority_provider_aliases (\n\taddress VARCHAR(71) NOT NULL, \n\tschema VARCHAR(64) NOT NULL, \n\tcanonical_json TEXT NOT NULL, \n\tproduct_address VARCHAR(71) NOT NULL, \n\tinstrument_address VARCHAR(71) NOT NULL, \n\tprovider_token VARCHAR(256) NOT NULL, \n\tprovider_symbol VARCHAR(256) NOT NULL, \n\tobservation_namespace VARCHAR(128) NOT NULL, \n\teffective_from TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\teffective_to TIMESTAMP WITHOUT TIME ZONE, \n\tauthority_state VARCHAR(24) DEFAULT 'VERIFIED_V2' NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tprovider_contract_address VARCHAR(71), \n\treceipt_address VARCHAR(71), \n\tPRIMARY KEY (address), \n\tFOREIGN KEY(product_address) REFERENCES authority_provider_products (address), \n\tFOREIGN KEY(instrument_address) REFERENCES authority_canonical_instruments (address), \n\tCONSTRAINT ck_authority_provider_alias_interval CHECK (effective_to IS NULL OR effective_to > effective_from), \n\tFOREIGN KEY(provider_contract_address) REFERENCES authority_provider_contracts (address), \n\tFOREIGN KEY(receipt_address) REFERENCES authority_raw_segments (address), \n\tCONSTRAINT ck_authority_provider_alias_scope CHECK ((schema = 'provider-instrument-mapping/1' AND provider_contract_address IS NULL AND receipt_address IS NULL) OR (schema = 'provider-instrument-mapping/2' AND provider_contract_address IS NOT NULL AND receipt_address IS NOT NULL AND effective_to IS NOT NULL)), \n\tCONSTRAINT uq_authority_provider_alias_response UNIQUE (provider_contract_address, receipt_address), \n\tCONSTRAINT ck_authority_provider_aliases_address CHECK (address ~ '^sha256:[0-9a-f]{64}$'), \n\tCONSTRAINT ck_authority_provider_aliases_json CHECK (CAST(canonical_json AS JSONB) IS NOT NULL), \n\tCONSTRAINT ck_authority_provider_aliases_verified CHECK (authority_state = 'VERIFIED_V2')\n)\n\n", "CREATE UNIQUE INDEX uq_authority_provider_alias_token ON authority_provider_aliases (product_address, observation_namespace, provider_token, effective_from) WHERE schema = 'provider-instrument-mapping/1'", "CREATE OR REPLACE FUNCTION authority_provider_aliases_refuse_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'authority_provider_aliases is immutable'; END; $$ LANGUAGE plpgsql", 'CREATE TRIGGER authority_provider_aliases_refuse_mutation BEFORE UPDATE OR DELETE ON authority_provider_aliases FOR EACH ROW EXECUTE FUNCTION authority_provider_aliases_refuse_mutation()', "CREATE OR REPLACE FUNCTION authority_provider_aliases_refuse_overlap() RETURNS trigger AS $$ BEGIN IF EXISTS (SELECT 1 FROM authority_provider_aliases AS existing WHERE NEW.schema = 'provider-instrument-mapping/1' AND existing.schema = 'provider-instrument-mapping/1' AND existing.product_address = NEW.product_address AND existing.observation_namespace = NEW.observation_namespace AND (existing.provider_token = NEW.provider_token OR existing.provider_symbol = NEW.provider_symbol OR existing.instrument_address = NEW.instrument_address) AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) THEN RAISE EXCEPTION 'authority provider alias overlaps'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql", 'CREATE TRIGGER authority_provider_aliases_refuse_overlap BEFORE INSERT ON authority_provider_aliases FOR EACH ROW EXECUTE FUNCTION authority_provider_aliases_refuse_overlap()']}
OLD_COLUMNS = ("address", "schema", "canonical_json", "product_address", "instrument_address",
    "provider_token", "provider_symbol", "observation_namespace", "effective_from", "effective_to",
    "authority_state", "created_at")


def _source(connection):
    dialect = connection.dialect.name
    if dialect == "sqlite":
        if connection.exec_driver_sql("PRAGMA foreign_keys").scalar():
            raise RuntimeError("0055 requires managed SQLite foreign-key suspension before transaction")
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif dialect == "postgresql":
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200055)")
    else:
        raise RuntimeError("0055 unsupported database dialect")
    heads = tuple(connection.execute(sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
    if heads != ("0054",):
        raise RuntimeError("0055 requires exact 0054 source")
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if TEMP in inspector.get_table_names() or columns != set(OLD_COLUMNS):
        raise RuntimeError("0055 refuses partial or unexpected alias schema; forward repair required")
    return dialect


def _sqlite_rebuild(connection):
    objects = connection.execute(sa.text(
        "SELECT name, sql FROM sqlite_master WHERE tbl_name = :table "
        "AND type IN ('index', 'trigger') AND sql IS NOT NULL ORDER BY name"),
        {"table": TABLE}).all()
    connection.exec_driver_sql(DDL["sqlite"][0].replace("CREATE TABLE " + TABLE, "CREATE TABLE " + TEMP, 1))
    columns = ", ".join(OLD_COLUMNS)
    connection.exec_driver_sql(f"INSERT INTO {TEMP} ({columns}) SELECT {columns} FROM {TABLE}")
    connection.exec_driver_sql(f"DROP TABLE {TABLE}")
    connection.exec_driver_sql(f"ALTER TABLE {TEMP} RENAME TO {TABLE}")
    replaced = {"uq_authority_provider_alias_token", "authority_provider_aliases_refuse_update",
                "authority_provider_aliases_refuse_delete", "authority_provider_aliases_refuse_overlap"}
    for name, statement in objects:
        if name not in replaced:
            connection.exec_driver_sql(statement)
    for statement in DDL["sqlite"][1:]:
        connection.exec_driver_sql(statement)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
        raise RuntimeError("0055 rebuilt aliases violate retained foreign keys")


def _postgresql_alter(connection):
    connection.exec_driver_sql(f"LOCK TABLE {TABLE} IN ACCESS EXCLUSIVE MODE")
    connection.exec_driver_sql(f"ALTER TABLE {TABLE} "
        "ADD COLUMN provider_contract_address VARCHAR(71) REFERENCES authority_provider_contracts(address), "
        "ADD COLUMN receipt_address VARCHAR(71) REFERENCES authority_raw_segments(address), "
        "ADD CONSTRAINT ck_authority_provider_alias_scope CHECK "
        "((schema = 'provider-instrument-mapping/1' AND provider_contract_address IS NULL AND receipt_address IS NULL) "
        "OR (schema = 'provider-instrument-mapping/2' AND provider_contract_address IS NOT NULL "
        "AND receipt_address IS NOT NULL AND effective_to IS NOT NULL)), "
        "ADD CONSTRAINT uq_authority_provider_alias_response UNIQUE (provider_contract_address, receipt_address), "
        "DROP CONSTRAINT uq_authority_provider_alias_token")
    connection.exec_driver_sql(DDL["postgresql"][1])
    connection.exec_driver_sql(DDL["postgresql"][-2])


def upgrade():
    connection = op.get_bind()
    dialect = _source(connection)
    if dialect == "sqlite":
        _sqlite_rebuild(connection)
    else:
        _postgresql_alter(connection)


def downgrade():
    raise RuntimeError("0055 retains response attribution; use restore or forward repair")
