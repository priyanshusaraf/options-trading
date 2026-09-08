"""Add bounded browser credential/session metadata in the USER plane only.

Frozen DDL; preserve 0042 and every existing identity and money table.
Rollback is restore/forward repair after writer quiescence, never table deletion.
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

DDL = {'postgresql': ['\n'
                'CREATE TABLE browser_credentials (\n'
                '\tuser_id VARCHAR(64) NOT NULL, \n'
                '\tverifier VARCHAR(160) NOT NULL, \n'
                '\tupdated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (user_id), \n'
                '\tCONSTRAINT ck_browser_credential_length CHECK '
                '(length(verifier) BETWEEN 1 AND 160), \n'
                '\tFOREIGN KEY(user_id) REFERENCES users (user_id)\n'
                ')\n'
                '\n',
                '\n'
                'CREATE TABLE enrollment_invites (\n'
                '\tinvite_digest VARCHAR(64) NOT NULL, \n'
                '\temail_normalized VARCHAR(320) NOT NULL, \n'
                '\tpurpose VARCHAR(16) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n'
                '\texpires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n'
                '\tconsumed_at TIMESTAMP WITHOUT TIME ZONE, \n'
                '\tPRIMARY KEY (invite_digest), \n'
                '\tCONSTRAINT ck_enrollment_digest CHECK '
                '(char_length(invite_digest) = 64 AND invite_digest ~ '
                "'^[0-9a-f]{64}$'), \n"
                '\tCONSTRAINT ck_enrollment_purpose CHECK (purpose = '
                "'enrollment'), \n"
                '\tCONSTRAINT ck_enrollment_expiry CHECK (expires_at > '
                'created_at)\n'
                ')\n'
                '\n',
                '\n'
                'CREATE TABLE browser_sessions (\n'
                '\tsession_id VARCHAR(64) NOT NULL, \n'
                '\tlast_seen_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (session_id), \n'
                '\tFOREIGN KEY(session_id) REFERENCES user_sessions '
                '(session_id)\n'
                ')\n'
                '\n',
                '\n'
                'CREATE TABLE browser_auth_attempts (\n'
                '\tkey_digest VARCHAR(64) NOT NULL, \n'
                '\texpires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n'
                '\tattempts INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (key_digest), \n'
                '\tCONSTRAINT ck_browser_attempt_digest CHECK '
                '(char_length(key_digest) = 64 AND key_digest ~ '
                "'^[0-9a-f]{64}$'), \n"
                '\tCONSTRAINT ck_browser_attempt_count CHECK (attempts BETWEEN '
                '1 AND 60)\n'
                ')\n'
                '\n',
                'CREATE INDEX ix_enrollment_expiry ON enrollment_invites '
                '(expires_at)',
                'CREATE INDEX ix_browser_attempt_expiry ON '
                'browser_auth_attempts (expires_at)'],
 'sqlite': ['\n'
            'CREATE TABLE browser_credentials (\n'
            '\tuser_id VARCHAR(64) NOT NULL, \n'
            '\tverifier VARCHAR(160) NOT NULL, \n'
            '\tupdated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (user_id), \n'
            '\tCONSTRAINT ck_browser_credential_length CHECK (length(verifier) '
            'BETWEEN 1 AND 160), \n'
            '\tFOREIGN KEY(user_id) REFERENCES users (user_id)\n'
            ')\n'
            '\n',
            '\n'
            'CREATE TABLE enrollment_invites (\n'
            '\tinvite_digest VARCHAR(64) NOT NULL, \n'
            '\temail_normalized VARCHAR(320) NOT NULL, \n'
            '\tpurpose VARCHAR(16) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\texpires_at DATETIME NOT NULL, \n'
            '\tconsumed_at DATETIME, \n'
            '\tPRIMARY KEY (invite_digest), \n'
            '\tCONSTRAINT ck_enrollment_digest CHECK (length(invite_digest) = '
            '64 AND invite_digest = lower(invite_digest) AND invite_digest NOT '
            "GLOB '*[^0-9a-f]*'), \n"
            '\tCONSTRAINT ck_enrollment_purpose CHECK (purpose = '
            "'enrollment'), \n"
            '\tCONSTRAINT ck_enrollment_expiry CHECK (expires_at > '
            'created_at)\n'
            ')\n'
            '\n',
            '\n'
            'CREATE TABLE browser_sessions (\n'
            '\tsession_id VARCHAR(64) NOT NULL, \n'
            '\tlast_seen_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (session_id), \n'
            '\tFOREIGN KEY(session_id) REFERENCES user_sessions (session_id)\n'
            ')\n'
            '\n',
            '\n'
            'CREATE TABLE browser_auth_attempts (\n'
            '\tkey_digest VARCHAR(64) NOT NULL, \n'
            '\texpires_at DATETIME NOT NULL, \n'
            '\tattempts INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (key_digest), \n'
            '\tCONSTRAINT ck_browser_attempt_digest CHECK (length(key_digest) '
            '= 64 AND key_digest = lower(key_digest) AND key_digest NOT GLOB '
            "'*[^0-9a-f]*'), \n"
            '\tCONSTRAINT ck_browser_attempt_count CHECK (attempts BETWEEN 1 '
            'AND 60)\n'
            ')\n'
            '\n',
            'CREATE INDEX ix_enrollment_expiry ON enrollment_invites '
            '(expires_at)',
            'CREATE INDEX ix_browser_attempt_expiry ON browser_auth_attempts '
            '(expires_at)']}


def upgrade():
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in DDL:
        raise RuntimeError("0043 requires SQLite or PostgreSQL")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200043)")
    tables = {"browser_credentials", "enrollment_invites", "browser_sessions", "browser_auth_attempts"}
    if tables.intersection(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0043 refuses partial/unproven browser auth schema; forward repair required")
    for statement in DDL[dialect]:
        connection.exec_driver_sql(statement)


def downgrade():
    raise RuntimeError("0043 refuses destructive downgrade; quiesce writers and restore or forward repair")
