"""Add immutable static research scopes in the USER plane.

0041 money/attribution objects remain untouched. DDL is frozen here, not imported
from evolving ORM models. Interrupted DDL rolls back as one transaction; a partial
unproven catalogue is refused and requires operator-directed forward repair.
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

DDL = {'postgresql': ['\n'
                'CREATE TABLE static_instrument_scopes (\n'
                '\towner_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscope_id VARCHAR(64) NOT NULL, \n'
                '\tname VARCHAR(128) NOT NULL, \n'
                '\trevision INTEGER NOT NULL, \n'
                '\tstatus VARCHAR(16) NOT NULL, \n'
                '\tPRIMARY KEY (owner_id, project_id, scope_id), \n'
                '\tCONSTRAINT fk_static_scopes_project FOREIGN KEY(owner_id, project_id) '
                'REFERENCES projects (owner_id, project_id) ON DELETE RESTRICT, \n'
                '\tCONSTRAINT uq_static_scopes_name UNIQUE (owner_id, project_id, name), \n'
                '\tCONSTRAINT ck_static_scopes_id CHECK (length(scope_id) BETWEEN 1 AND 64), \n'
                '\tCONSTRAINT ck_static_scopes_name CHECK (length(name) BETWEEN 1 AND 128), \n'
                '\tCONSTRAINT ck_static_scopes_revision CHECK (revision > 0), \n'
                "\tCONSTRAINT ck_static_scopes_status CHECK (status IN ('active', 'archived'))\n"
                ')\n'
                '\n',
                '\n'
                'CREATE TABLE static_instrument_scope_revisions (\n'
                '\towner_id VARCHAR(64) NOT NULL, \n'
                '\tproject_id VARCHAR(64) NOT NULL, \n'
                '\tscope_id VARCHAR(64) NOT NULL, \n'
                '\trevision INTEGER NOT NULL, \n'
                '\taddress VARCHAR(71) NOT NULL, \n'
                '\tmembership_address VARCHAR(71) NOT NULL, \n'
                '\tpredecessor VARCHAR(71), \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tPRIMARY KEY (owner_id, project_id, scope_id, revision), \n'
                '\tCONSTRAINT fk_static_revisions_scope FOREIGN KEY(owner_id, project_id, '
                'scope_id) REFERENCES static_instrument_scopes (owner_id, project_id, scope_id) ON '
                'DELETE RESTRICT, \n'
                '\tCONSTRAINT uq_static_revisions_address UNIQUE (address), \n'
                '\tCONSTRAINT uq_static_revisions_chain UNIQUE (owner_id, project_id, scope_id, '
                'address), \n'
                '\tCONSTRAINT fk_static_revisions_predecessor FOREIGN KEY(owner_id, project_id, '
                'scope_id, predecessor) REFERENCES static_instrument_scope_revisions (owner_id, '
                'project_id, scope_id, address), \n'
                '\tCONSTRAINT ck_static_revisions_revision CHECK (revision > 0), \n'
                '\tCONSTRAINT ck_static_revisions_predecessor CHECK ((revision = 1 AND predecessor '
                'IS NULL) OR (revision > 1 AND predecessor IS NOT NULL)), \n'
                '\tCONSTRAINT ck_static_revisions_address CHECK (address ~ '
                "'^sha256:[0-9a-f]{64}$'), \n"
                '\tCONSTRAINT ck_static_revisions_membership CHECK (membership_address ~ '
                "'^sha256:[0-9a-f]{64}$'), \n"
                '\tCONSTRAINT ck_static_revisions_predecessor_address CHECK (predecessor IS NULL '
                "OR (predecessor ~ '^sha256:[0-9a-f]{64}$')), \n"
                '\tCONSTRAINT ck_static_revisions_json CHECK (CAST(canonical_json AS JSONB) IS NOT '
                'NULL)\n'
                ')\n'
                '\n'],
 'sqlite': ['\n'
            'CREATE TABLE static_instrument_scopes (\n'
            '\towner_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscope_id VARCHAR(64) NOT NULL, \n'
            '\tname VARCHAR(128) NOT NULL, \n'
            '\trevision INTEGER NOT NULL, \n'
            '\tstatus VARCHAR(16) NOT NULL, \n'
            '\tPRIMARY KEY (owner_id, project_id, scope_id), \n'
            '\tCONSTRAINT fk_static_scopes_project FOREIGN KEY(owner_id, project_id) REFERENCES '
            'projects (owner_id, project_id) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT uq_static_scopes_name UNIQUE (owner_id, project_id, name), \n'
            '\tCONSTRAINT ck_static_scopes_id CHECK (length(scope_id) BETWEEN 1 AND 64), \n'
            '\tCONSTRAINT ck_static_scopes_name CHECK (length(name) BETWEEN 1 AND 128), \n'
            '\tCONSTRAINT ck_static_scopes_revision CHECK (revision > 0), \n'
            "\tCONSTRAINT ck_static_scopes_status CHECK (status IN ('active', 'archived'))\n"
            ')\n'
            '\n',
            '\n'
            'CREATE TABLE static_instrument_scope_revisions (\n'
            '\towner_id VARCHAR(64) NOT NULL, \n'
            '\tproject_id VARCHAR(64) NOT NULL, \n'
            '\tscope_id VARCHAR(64) NOT NULL, \n'
            '\trevision INTEGER NOT NULL, \n'
            '\taddress VARCHAR(71) NOT NULL, \n'
            '\tmembership_address VARCHAR(71) NOT NULL, \n'
            '\tpredecessor VARCHAR(71), \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tPRIMARY KEY (owner_id, project_id, scope_id, revision), \n'
            '\tCONSTRAINT fk_static_revisions_scope FOREIGN KEY(owner_id, project_id, scope_id) '
            'REFERENCES static_instrument_scopes (owner_id, project_id, scope_id) ON DELETE '
            'RESTRICT, \n'
            '\tCONSTRAINT uq_static_revisions_address UNIQUE (address), \n'
            '\tCONSTRAINT uq_static_revisions_chain UNIQUE (owner_id, project_id, scope_id, '
            'address), \n'
            '\tCONSTRAINT fk_static_revisions_predecessor FOREIGN KEY(owner_id, project_id, '
            'scope_id, predecessor) REFERENCES static_instrument_scope_revisions (owner_id, '
            'project_id, scope_id, address), \n'
            '\tCONSTRAINT ck_static_revisions_revision CHECK (revision > 0), \n'
            '\tCONSTRAINT ck_static_revisions_predecessor CHECK ((revision = 1 AND predecessor IS '
            'NULL) OR (revision > 1 AND predecessor IS NOT NULL)), \n'
            '\tCONSTRAINT ck_static_revisions_address CHECK (length(address) = 71 AND '
            "substr(address, 1, 7) = 'sha256:' AND substr(address, 8) = lower(substr(address, 8)) "
            "AND substr(address, 8) NOT GLOB '*[^0-9a-f]*'), \n"
            '\tCONSTRAINT ck_static_revisions_membership CHECK (length(membership_address) = 71 '
            "AND substr(membership_address, 1, 7) = 'sha256:' AND substr(membership_address, 8) = "
            'lower(substr(membership_address, 8)) AND substr(membership_address, 8) NOT GLOB '
            "'*[^0-9a-f]*'), \n"
            '\tCONSTRAINT ck_static_revisions_predecessor_address CHECK (predecessor IS NULL OR '
            "(length(predecessor) = 71 AND substr(predecessor, 1, 7) = 'sha256:' AND "
            'substr(predecessor, 8) = lower(substr(predecessor, 8)) AND substr(predecessor, 8) NOT '
            "GLOB '*[^0-9a-f]*')), \n"
            '\tCONSTRAINT ck_static_revisions_json CHECK (json_valid(canonical_json))\n'
            ')\n'
            '\n']}


def upgrade():
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in DDL:
        raise RuntimeError("0042 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200042)")
    tables = {"static_instrument_scopes", "static_instrument_scope_revisions"}
    if tables.intersection(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0042 refuses partial/unproven static scope schema; forward repair required")
    for statement in DDL[dialect]:
        connection.exec_driver_sql(statement)
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER static_instrument_scope_revisions_refuse_{action.lower()} "
                f"BEFORE {action} ON static_instrument_scope_revisions BEGIN "
                "SELECT RAISE(ABORT, 'static scope revisions are immutable'); END")
    else:
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION static_instrument_scope_revisions_refuse_mutation() "
            "RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'static scope revisions are immutable'; "
            "END; $$ LANGUAGE plpgsql")
        connection.exec_driver_sql(
            "CREATE TRIGGER static_instrument_scope_revisions_refuse_mutation "
            "BEFORE UPDATE OR DELETE ON static_instrument_scope_revisions "
            "FOR EACH ROW EXECUTE FUNCTION static_instrument_scope_revisions_refuse_mutation()")


def downgrade():
    raise RuntimeError("0042 refuses destructive downgrade; static research facts are retained; quiesce writers and forward repair")
