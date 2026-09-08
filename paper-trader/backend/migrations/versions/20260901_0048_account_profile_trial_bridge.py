"""Add privacy-minimised profile/trial facts and the BETA_TRIAL source.

This is an expand-only vocabulary change for existing entitlement facts. Existing
0046 rows keep their exact meaning. Migration and new binary move together under
writer quiescence; after a BETA_TRIAL event exists, recovery is restore or forward
repair rather than old-binary rollback.
"""
from __future__ import annotations

from alembic import op
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa


revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

PROFILE = "account_profile_evidence"
TRIAL = "account_trial_uses"
EVENT = "platform_entitlement_events"
TABLES = (PROFILE, TRIAL)
FORBIDDEN_SENTINELS = (
    "strategy", "graph", "component", "parameter", "annotation", "dataset",
    "research", "monitoring", "alert", "signal", "instrument", "nifty",
    "banknifty", "broker", "provider_account", "credential", "secret", "token",
    "position", "order", "trade", "balance", "capital", "pnl", "profit", "loss",
    "raw_request", "raw_response", "raw_webhook", "card", "upi", "free_text",
    "attachment", "diagnostic",
)
OLD_SOURCE_CHECK = (
    "source_kind IN ('BILLING_RECEIPT','COUPON_REDEMPTION','COMPLIMENTARY_GRANT')"
)
NEW_SOURCE_CHECK = (
    "source_kind IN ('BILLING_RECEIPT','COUPON_REDEMPTION','COMPLIMENTARY_GRANT','BETA_TRIAL')"
)


def _address(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"{column} ~ '^sha256:[0-9a-f]{{64}}$'"
    return (
        f"length({column}) = 71 AND substr({column}, 1, 7) = 'sha256:' AND "
        f"substr({column}, 8) = lower(substr({column}, 8)) AND "
        f"substr({column}, 8) NOT GLOB '*[^0-9a-f]*'"
    )


def _code(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"{column} ~ '^[A-Z][A-Z0-9_]{{0,63}}$'"
    return (
        f"length({column}) BETWEEN 1 AND 64 AND substr({column}, 1, 1) GLOB '[A-Z]' "
        f"AND {column} NOT GLOB '*[^A-Z0-9_]*'"
    )


def _metadata(dialect: str) -> sa.MetaData:
    metadata = sa.MetaData()
    membership = sa.Table(
        "memberships", metadata,
        sa.Column("organization_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), primary_key=True),
        extend_existing=True,
    )
    profile = sa.Table(
        PROFILE, metadata,
        sa.Column("profile_evidence_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(64), nullable=False),
        sa.Column("user_ref", sa.String(64), nullable=False),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("evidence_address", sa.String(71), nullable=False),
        sa.Column("satisfied_fields_json", sa.String(2048), nullable=False),
        sa.Column("attested_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ("owner_ref", "user_ref"),
            (membership.c.organization_id, membership.c.user_id),
            name="fk_account_profile_evidence_membership", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "owner_ref", "user_ref", "policy_address", "evidence_address",
            name="uq_account_profile_evidence_authority",
        ),
        sa.CheckConstraint(_address("policy_address", dialect),
                           name="ck_account_profile_evidence_policy"),
        sa.CheckConstraint(_address("evidence_address", dialect),
                           name="ck_account_profile_evidence_address"),
        sa.CheckConstraint(
            "satisfied_fields_json::jsonb IS NOT NULL" if dialect == "postgresql"
            else "json_valid(satisfied_fields_json)",
            name="ck_account_profile_evidence_fields_json",
        ),
        sa.CheckConstraint(
            "octet_length(satisfied_fields_json) <= 2048" if dialect == "postgresql"
            else "length(CAST(satisfied_fields_json AS BLOB)) <= 2048",
            name="ck_account_profile_evidence_fields_size",
        ),
    )
    sa.Index("ix_account_profile_evidence_current", profile.c.owner_ref,
             profile.c.user_ref, profile.c.policy_address, profile.c.attested_at,
             profile.c.profile_evidence_id)
    trial = sa.Table(
        TRIAL, metadata,
        sa.Column("trial_use_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(64), nullable=False),
        sa.Column("user_ref", sa.String(64), nullable=False),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("profile_evidence_id", sa.String(128), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(128), nullable=False),
        sa.Column("eligibility_authority_address", sa.String(71), nullable=False),
        sa.Column("prior_use_authority_address", sa.String(71), nullable=False),
        sa.Column("decision_basis_address", sa.String(71), nullable=False),
        sa.Column("entitlement_code", sa.String(64), nullable=False),
        sa.Column("entitlement_transition", sa.String(16), nullable=False),
        sa.Column("entitlement_event_id", sa.String(128), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ("owner_ref", "user_ref"),
            (membership.c.organization_id, membership.c.user_id),
            name="fk_account_trial_use_membership", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ("profile_evidence_id",), (profile.c.profile_evidence_id,),
            name="fk_account_trial_use_profile_evidence", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("owner_ref", "user_ref", "policy_address",
                            name="uq_account_trial_use_owner_user_policy"),
        sa.UniqueConstraint("entitlement_event_id",
                            name="uq_account_trial_use_entitlement_event"),
        sa.CheckConstraint(_address("policy_address", dialect),
                           name="ck_account_trial_use_policy"),
        sa.CheckConstraint(_address("eligibility_authority_address", dialect),
                           name="ck_account_trial_use_eligibility"),
        sa.CheckConstraint(_address("prior_use_authority_address", dialect),
                           name="ck_account_trial_use_prior_authority"),
        sa.CheckConstraint(_address("decision_basis_address", dialect),
                           name="ck_account_trial_use_decision_basis"),
        sa.CheckConstraint(_code("entitlement_code", dialect),
                           name="ck_account_trial_use_entitlement_code"),
        sa.CheckConstraint("source_kind IN ('BETA_TRIAL','COUPON_REDEMPTION')",
                           name="ck_account_trial_use_source"),
        sa.CheckConstraint("entitlement_transition = 'GRANT'",
                           name="ck_account_trial_use_transition"),
        sa.CheckConstraint("valid_until > valid_from",
                           name="ck_account_trial_use_validity"),
    )
    sa.Index("ix_account_trial_use_owner_time", trial.c.owner_ref, trial.c.user_ref,
             trial.c.used_at, trial.c.trial_use_id)
    return metadata


def _replace_sqlite_check(connection, old: str, new: str) -> None:
    row = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (EVENT,)
    ).one_or_none()
    if row is None or row[0].count(old) != 1 or new in row[0]:
        raise RuntimeError("0048 refuses unexpected entitlement source schema")
    schema_version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
    connection.exec_driver_sql("PRAGMA writable_schema=ON")
    try:
        connection.exec_driver_sql(
            "UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
            (row[0].replace(old, new), EVENT),
        )
    finally:
        connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    connection.exec_driver_sql(f"PRAGMA schema_version={schema_version + 1}")


def _drop_source_guard(connection, dialect: str) -> None:
    connection.exec_driver_sql(
        "DROP TRIGGER IF EXISTS platform_entitlement_events_source_exact"
    )
    if dialect == "postgresql":
        connection.exec_driver_sql(
            "DROP FUNCTION IF EXISTS platform_entitlement_events_source_exact_fn()"
        )


def _create_source_guard(connection, dialect: str, *, beta: bool) -> None:
    beta_sqlite = (
        " OR (NEW.source_kind='BETA_TRIAL' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM account_trial_uses s WHERE s.trial_use_id=NEW.source_ref "
        "AND s.source_kind='BETA_TRIAL' AND s.owner_ref=NEW.owner_ref "
        "AND s.entitlement_event_id=NEW.event_id AND s.entitlement_code IS NEW.entitlement_code "
        "AND s.entitlement_transition IS NEW.transition AND s.policy_address IS NEW.policy_address "
        "AND s.valid_from IS NEW.valid_from AND s.valid_until IS NEW.valid_until))"
        if beta else ""
    )
    beta_pg = (
        " OR (NEW.source_kind='BETA_TRIAL' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM account_trial_uses s WHERE s.trial_use_id=NEW.source_ref "
        "AND s.source_kind='BETA_TRIAL' AND s.owner_ref=NEW.owner_ref "
        "AND s.entitlement_event_id=NEW.event_id "
        "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
        "AND s.entitlement_transition IS NOT DISTINCT FROM NEW.transition "
        "AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
        "AND s.valid_from IS NOT DISTINCT FROM NEW.valid_from "
        "AND s.valid_until IS NOT DISTINCT FROM NEW.valid_until))"
        if beta else ""
    )
    if dialect == "sqlite":
        connection.exec_driver_sql(
            "CREATE TRIGGER platform_entitlement_events_source_exact BEFORE INSERT ON "
            "platform_entitlement_events WHEN NOT ("
            "(NEW.source_kind='BILLING_RECEIPT' AND NEW.mode IN ('TEST','LIVE') AND EXISTS "
            "(SELECT 1 FROM platform_billing_event_receipts s WHERE s.receipt_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.mode=NEW.mode AND s.event_state='VERIFIED' "
            "AND s.entitlement_code IS NEW.entitlement_code AND s.entitlement_transition IS NEW.transition "
            "AND s.entitlement_policy_address IS NEW.policy_address "
            "AND s.entitlement_valid_from IS NEW.valid_from "
            "AND s.entitlement_valid_until IS NEW.valid_until)) OR "
            "(NEW.source_kind='COUPON_REDEMPTION' AND NEW.mode='INTERNAL' AND EXISTS "
            "(SELECT 1 FROM platform_coupon_redemptions s WHERE s.redemption_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.status='ACCEPTED' "
            "AND s.entitlement_code IS NEW.entitlement_code "
            "AND s.entitlement_transition IS NEW.transition AND s.policy_address IS NEW.policy_address "
            "AND s.entitlement_valid_from IS NEW.valid_from "
            "AND s.entitlement_valid_until IS NEW.valid_until)) OR "
            "(NEW.source_kind='COMPLIMENTARY_GRANT' AND NEW.mode='INTERNAL' AND EXISTS "
            "(SELECT 1 FROM platform_complimentary_entitlement_grants s WHERE s.grant_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.entitlement_code IS NEW.entitlement_code "
            "AND s.action IS NEW.transition AND s.policy_address IS NEW.policy_address "
            "AND s.valid_from IS NEW.valid_from AND s.valid_until IS NEW.valid_until))"
            f"{beta_sqlite}) BEGIN SELECT RAISE(ABORT, 'entitlement event source mismatch'); END"
        )
        return
    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION platform_entitlement_events_source_exact_fn() RETURNS trigger "
        "AS $$ BEGIN IF NOT ((NEW.source_kind='BILLING_RECEIPT' AND NEW.mode IN ('TEST','LIVE') "
        "AND EXISTS (SELECT 1 FROM platform_billing_event_receipts s WHERE s.receipt_id=NEW.source_ref "
        "AND s.owner_ref=NEW.owner_ref AND s.mode=NEW.mode AND s.event_state='VERIFIED' "
        "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
        "AND s.entitlement_transition IS NOT DISTINCT FROM NEW.transition "
        "AND s.entitlement_policy_address IS NOT DISTINCT FROM NEW.policy_address "
        "AND s.entitlement_valid_from IS NOT DISTINCT FROM NEW.valid_from "
        "AND s.entitlement_valid_until IS NOT DISTINCT FROM NEW.valid_until)) OR "
        "(NEW.source_kind='COUPON_REDEMPTION' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM platform_coupon_redemptions s WHERE s.redemption_id=NEW.source_ref "
        "AND s.owner_ref=NEW.owner_ref AND s.status='ACCEPTED' "
        "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
        "AND s.entitlement_transition IS NOT DISTINCT FROM NEW.transition "
        "AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
        "AND s.entitlement_valid_from IS NOT DISTINCT FROM NEW.valid_from "
        "AND s.entitlement_valid_until IS NOT DISTINCT FROM NEW.valid_until)) OR "
        "(NEW.source_kind='COMPLIMENTARY_GRANT' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM platform_complimentary_entitlement_grants s WHERE s.grant_id=NEW.source_ref "
        "AND s.owner_ref=NEW.owner_ref "
        "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
        "AND s.action IS NOT DISTINCT FROM NEW.transition "
        "AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
        "AND s.valid_from IS NOT DISTINCT FROM NEW.valid_from "
        "AND s.valid_until IS NOT DISTINCT FROM NEW.valid_until))"
        f"{beta_pg}) THEN RAISE EXCEPTION 'entitlement event source mismatch'; "
        "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
    )
    connection.exec_driver_sql(
        "CREATE TRIGGER platform_entitlement_events_source_exact BEFORE INSERT ON "
        "platform_entitlement_events FOR EACH ROW EXECUTE FUNCTION "
        "platform_entitlement_events_source_exact_fn()"
    )


def _create_immutable_guards(connection, dialect: str) -> None:
    for table in TABLES:
        if dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {table}_refuse_{operation.lower()} BEFORE {operation} "
                    f"ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
                )
        else:
            function = f"{table}_refuse_mutation_fn"
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
                f"RAISE EXCEPTION '{table} is immutable'; END; $$ LANGUAGE plpgsql"
            )
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table}_refuse_update BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()"
            )
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table}_refuse_delete BEFORE DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()"
            )


def _create_privacy_guards(connection, dialect: str, metadata: sa.MetaData) -> None:
    for table_name in TABLES:
        table = metadata.tables[table_name]
        textual = tuple(
            column.name for column in table.columns if isinstance(column.type, sa.String)
        )
        if dialect == "sqlite":
            terms = " OR ".join(
                f"instr(lower(COALESCE(NEW.{column},'')), '{term}') > 0"
                for column in textual for term in FORBIDDEN_SENTINELS
            )
            for operation in ("INSERT", "UPDATE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {table_name}_privacy_{operation.lower()} "
                    f"BEFORE {operation} ON {table_name} WHEN {terms} BEGIN "
                    "SELECT RAISE(ABORT, 'platform operations forbidden content'); END"
                )
        else:
            terms = " OR ".join(
                f"position('{term}' in lower(COALESCE(NEW.{column},''))) > 0"
                for column in textual for term in FORBIDDEN_SENTINELS
            )
            function = f"{table_name}_privacy_guard_fn"
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
                f"IF {terms} THEN RAISE EXCEPTION 'platform operations forbidden content'; "
                "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
            )
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table_name}_privacy_guard BEFORE INSERT OR UPDATE "
                f"ON {table_name} FOR EACH ROW EXECUTE FUNCTION {function}()"
            )


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0048 unsupported database dialect")
    heads = tuple(MigrationContext.configure(connection).get_current_heads())
    if heads != ("0047",):
        raise RuntimeError(f"0048 requires exact 0047 source; found heads={list(heads)}")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200048)")
    names = set(sa.inspect(connection).get_table_names())
    present = names.intersection(TABLES)
    if present:
        raise RuntimeError(f"0048 refuses partial or pre-existing account tables: {sorted(present)}")
    metadata = _metadata(dialect)
    for name in TABLES:
        metadata.tables[name].create(connection, checkfirst=False)
    if dialect == "sqlite":
        _replace_sqlite_check(connection, OLD_SOURCE_CHECK, NEW_SOURCE_CHECK)
    else:
        connection.exec_driver_sql(
            "ALTER TABLE platform_entitlement_events DROP CONSTRAINT ck_platform_entitlement_source"
        )
        connection.exec_driver_sql(
            "ALTER TABLE platform_entitlement_events ADD CONSTRAINT "
            f"ck_platform_entitlement_source CHECK ({NEW_SOURCE_CHECK})"
        )
    _drop_source_guard(connection, dialect)
    _create_source_guard(connection, dialect, beta=True)
    _create_immutable_guards(connection, dialect)
    _create_privacy_guards(connection, dialect, metadata)


def downgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    names = set(sa.inspect(connection).get_table_names())
    if EVENT in names:
        beta_count = connection.scalar(sa.text(
            "SELECT count(*) FROM platform_entitlement_events WHERE source_kind='BETA_TRIAL'"
        ))
        if beta_count:
            raise RuntimeError(
                "0048 refuses old-binary rollback after beta facts; restore or forward repair"
            )
    for table in TABLES:
        if table in names and connection.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError(
                "0048 refuses destructive downgrade of account evidence; restore or forward repair"
            )
    _drop_source_guard(connection, dialect)
    for table in reversed(TABLES):
        if table in names:
            op.drop_table(table)
    if dialect == "postgresql":
        for table in TABLES:
            connection.exec_driver_sql(
                f"DROP FUNCTION IF EXISTS {table}_refuse_mutation_fn()"
            )
            connection.exec_driver_sql(
                f"DROP FUNCTION IF EXISTS {table}_privacy_guard_fn()"
            )
    if dialect == "sqlite":
        _replace_sqlite_check(connection, NEW_SOURCE_CHECK, OLD_SOURCE_CHECK)
    else:
        connection.exec_driver_sql(
            "ALTER TABLE platform_entitlement_events DROP CONSTRAINT ck_platform_entitlement_source"
        )
        connection.exec_driver_sql(
            "ALTER TABLE platform_entitlement_events ADD CONSTRAINT "
            f"ck_platform_entitlement_source CHECK ({OLD_SOURCE_CHECK})"
        )
    _create_source_guard(connection, dialect, beta=False)
