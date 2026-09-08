"""Separate fixed coupon dates from server-resolved dynamic duration.

0049 is activated only with coupon writers quiesced. Existing 0048 coupon
definitions retain their absolute dates and become explicit FIXED_ABSOLUTE rows.
DYNAMIC_DURATION is a closed V0 shape whose actual dates exist only on the
redemption and its downstream trial/event facts.
"""
from __future__ import annotations

import importlib

from alembic import op
import sqlalchemy as sa


revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

TABLE = "platform_coupon_definitions"
OLD_CHECK_NAME = "ck_platform_coupon_entitlement_validity"
NEW_CHECK_NAME = "ck_platform_coupon_entitlement_shape"
OLD_CHECK = (
    "entitlement_valid_until IS NULL OR "
    "entitlement_valid_until > entitlement_valid_from"
)
NEW_CHECK = (
    "(entitlement_effect_timing = 'FIXED_ABSOLUTE' AND "
    "entitlement_valid_from IS NOT NULL AND entitlement_duration_seconds IS NULL AND "
    "(entitlement_valid_until IS NULL OR entitlement_valid_until > entitlement_valid_from)) "
    "OR (entitlement_effect_timing = 'DYNAMIC_DURATION' AND "
    "entitlement_valid_from IS NULL AND entitlement_valid_until IS NULL AND "
    "entitlement_duration_seconds = 1296000 AND trial_policy_address IS NOT NULL AND "
    "discount_policy_address IS NULL AND entitlement_transition = 'GRANT')"
)


def _columns(connection) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in sa.inspect(connection).get_columns(TABLE)
    }


def _checks(connection) -> dict[str, str]:
    return {
        str(item.get("name")): " ".join(str(item.get("sqltext", "")).split())
        for item in sa.inspect(connection).get_check_constraints(TABLE)
    }


def _preflight_0048(connection) -> None:
    heads = tuple(connection.execute(sa.text(
        "SELECT version_num FROM alembic_version ORDER BY version_num"
    )).scalars())
    if heads != ("0048",):
        raise RuntimeError(f"0049 requires exact 0048 source; found heads={list(heads)}")
    if TABLE not in set(sa.inspect(connection).get_table_names()):
        raise RuntimeError("0049 requires the accepted 0048 coupon definition table")
    columns = _columns(connection)
    if ({"entitlement_effect_timing", "entitlement_duration_seconds"} & set(columns)
            or "entitlement_valid_from" not in columns
            or columns["entitlement_valid_from"]["nullable"]):
        raise RuntimeError("0049 refuses partial or unexpected coupon definition columns")
    checks = _checks(connection)
    if OLD_CHECK_NAME not in checks or NEW_CHECK_NAME in checks:
        raise RuntimeError("0049 refuses partial or unexpected coupon definition checks")


def _sqlite_replace_schema(connection, *, old: str, new: str) -> None:
    row = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
    ).one_or_none()
    if row is None or row[0].count(old) != 1:
        raise RuntimeError("0049 refuses unexpected SQLite coupon definition schema")
    schema_version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
    connection.exec_driver_sql("PRAGMA writable_schema=ON")
    try:
        connection.exec_driver_sql(
            "UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
            (row[0].replace(old, new), TABLE),
        )
    finally:
        connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    connection.exec_driver_sql(f"PRAGMA schema_version={schema_version + 1}")


def _sqlite_upgrade(connection) -> None:
    connection.exec_driver_sql(
        f"ALTER TABLE {TABLE} ADD COLUMN entitlement_effect_timing VARCHAR(24)"
    )
    connection.exec_driver_sql(
        f"ALTER TABLE {TABLE} ADD COLUMN entitlement_duration_seconds INTEGER"
    )
    connection.exec_driver_sql(
        f"UPDATE {TABLE} SET entitlement_effect_timing='FIXED_ABSOLUTE'"
    )
    old_fragment = (
        f"CONSTRAINT {OLD_CHECK_NAME} CHECK ({OLD_CHECK})"
    )
    new_fragment = (
        f"CONSTRAINT {NEW_CHECK_NAME} CHECK ({NEW_CHECK})"
    )
    _sqlite_replace_schema(connection, old=old_fragment, new=new_fragment)
    _sqlite_replace_schema(
        connection,
        old="entitlement_valid_from DATETIME NOT NULL",
        new="entitlement_valid_from DATETIME",
    )
    _sqlite_replace_schema(
        connection,
        old="entitlement_effect_timing VARCHAR(24)",
        new="entitlement_effect_timing VARCHAR(24) NOT NULL",
    )
    _drop_definition_privacy_guard(connection, "sqlite")
    _create_definition_privacy_guard(connection, "sqlite", include_timing=True)


def _postgresql_upgrade(connection) -> None:
    op.add_column(TABLE, sa.Column("entitlement_effect_timing", sa.String(24)))
    op.add_column(TABLE, sa.Column("entitlement_duration_seconds", sa.Integer()))
    connection.execute(sa.text(
        f"UPDATE {TABLE} SET entitlement_effect_timing='FIXED_ABSOLUTE'"
    ))
    op.alter_column(TABLE, "entitlement_valid_from", existing_type=sa.DateTime(),
                    nullable=True)
    op.alter_column(TABLE, "entitlement_effect_timing", existing_type=sa.String(24),
                    nullable=False)
    op.drop_constraint(OLD_CHECK_NAME, TABLE, type_="check")
    op.create_check_constraint(NEW_CHECK_NAME, TABLE, NEW_CHECK)
    _drop_definition_privacy_guard(connection, "postgresql")
    _create_definition_privacy_guard(connection, "postgresql", include_timing=True)


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0049 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        _preflight_0048(connection)
        _sqlite_upgrade(connection)
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200049)")
        _preflight_0048(connection)
        _postgresql_upgrade(connection)


def _preflight_downgrade(connection) -> None:
    columns = _columns(connection)
    if not {"entitlement_effect_timing", "entitlement_duration_seconds"} <= set(columns):
        raise RuntimeError("0049 downgrade refuses a partial coupon definition schema")
    dynamic = connection.scalar(sa.text(
        f"SELECT count(*) FROM {TABLE} "
        "WHERE entitlement_effect_timing='DYNAMIC_DURATION'"
    ))
    if dynamic:
        raise RuntimeError(
            "0049 refuses old-binary rollback after dynamic coupon activation; "
            "keep writers quiesced and use forward repair"
        )
    malformed = connection.scalar(sa.text(
        f"SELECT count(*) FROM {TABLE} WHERE entitlement_effect_timing!='FIXED_ABSOLUTE' "
        "OR entitlement_duration_seconds IS NOT NULL OR entitlement_valid_from IS NULL"
    ))
    if malformed:
        raise RuntimeError("0049 downgrade refuses non-lossless coupon definitions")


def _drop_definition_privacy_guard(connection, dialect: str) -> None:
    if dialect == "sqlite":
        connection.exec_driver_sql(
            "DROP TRIGGER IF EXISTS platform_coupon_definitions_privacy_insert"
        )
        connection.exec_driver_sql(
            "DROP TRIGGER IF EXISTS platform_coupon_definitions_privacy_update"
        )
    else:
        connection.exec_driver_sql(
            "DROP TRIGGER IF EXISTS platform_coupon_definitions_privacy_guard "
            "ON platform_coupon_definitions"
        )


def _create_definition_privacy_guard(
    connection, dialect: str, *, include_timing: bool,
) -> None:
    revision_0046 = importlib.import_module(
        "migrations.versions.20260830_0046_v0_platform_operations"
    )
    table = revision_0046._revision_metadata(dialect).tables[TABLE]
    textual = tuple(
        column.name for column in table.columns
        if isinstance(column.type, sa.String)
        and column.name not in {"event_type", "surface"}
    )
    if include_timing:
        textual += ("entitlement_effect_timing",)
    terms = revision_0046._PRIVACY_TERMS
    if dialect == "sqlite":
        predicate = " OR ".join(
            f"instr(lower(COALESCE(NEW.{column},'')), '{term}') > 0"
            for column in textual for term in terms
        )
        for operation in ("INSERT", "UPDATE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER {TABLE}_privacy_{operation.lower()} BEFORE {operation} "
                f"ON {TABLE} WHEN {predicate} BEGIN "
                "SELECT RAISE(ABORT, 'platform operations forbidden content'); END"
            )
    else:
        predicate = " OR ".join(
            f"position('{term}' in lower(COALESCE(NEW.{column},''))) > 0"
            for column in textual for term in terms
        )
        connection.exec_driver_sql(
            f"CREATE OR REPLACE FUNCTION {TABLE}_privacy_guard_fn() RETURNS trigger "
            f"AS $$ BEGIN IF {predicate} THEN RAISE EXCEPTION "
            "'platform operations forbidden content'; END IF; RETURN NEW; END; "
            "$$ LANGUAGE plpgsql"
        )
        connection.exec_driver_sql(
            f"CREATE TRIGGER {TABLE}_privacy_guard BEFORE INSERT OR UPDATE ON {TABLE} "
            f"FOR EACH ROW EXECUTE FUNCTION {TABLE}_privacy_guard_fn()"
        )


def _sqlite_downgrade(connection) -> None:
    _drop_definition_privacy_guard(connection, "sqlite")
    _sqlite_replace_schema(
        connection,
        old=f"CONSTRAINT {NEW_CHECK_NAME} CHECK ({NEW_CHECK})",
        new=f"CONSTRAINT {OLD_CHECK_NAME} CHECK ({OLD_CHECK})",
    )
    _sqlite_replace_schema(
        connection,
        old="entitlement_valid_from DATETIME",
        new="entitlement_valid_from DATETIME NOT NULL",
    )
    connection.exec_driver_sql(
        f"ALTER TABLE {TABLE} DROP COLUMN entitlement_duration_seconds"
    )
    connection.exec_driver_sql(
        f"ALTER TABLE {TABLE} DROP COLUMN entitlement_effect_timing"
    )
    _create_definition_privacy_guard(connection, "sqlite", include_timing=False)


def _postgresql_downgrade() -> None:
    connection = op.get_bind()
    _drop_definition_privacy_guard(connection, "postgresql")
    op.drop_constraint(NEW_CHECK_NAME, TABLE, type_="check")
    op.alter_column(TABLE, "entitlement_valid_from", existing_type=sa.DateTime(),
                    nullable=False)
    op.drop_column(TABLE, "entitlement_duration_seconds")
    op.drop_column(TABLE, "entitlement_effect_timing")
    op.create_check_constraint(OLD_CHECK_NAME, TABLE, OLD_CHECK)
    _create_definition_privacy_guard(connection, "postgresql", include_timing=False)


def downgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0049 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        _preflight_downgrade(connection)
        _sqlite_downgrade(connection)
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200049)")
        _preflight_downgrade(connection)
        _postgresql_downgrade()
