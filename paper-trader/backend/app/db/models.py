"""
SQLAlchemy models — the persistent paper-trading ledger.

Capital and history survive restarts (the owner runs this live over time), so
realized P&L compounds. The reconciliation invariant the dry-run checks:

    cash == initial_capital + realized_pnl - Σ(open position entry_cost)

i.e. every open position has removed its full entry cost (premium×qty + entry
charges) from cash, and every closed trade has folded its net P&L back in.
"""
from __future__ import annotations

import json
import datetime as dt

from app.core.version import get_build_sha
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    DDL,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
    false,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.dml import Insert
from sqlalchemy.types import TypeDecorator


class PasswordVerifier(str):
    """A verifier value that never reveals its material through diagnostics."""

    def __repr__(self) -> str:
        return "<PasswordVerifier redacted>"


class PasswordVerifierType(TypeDecorator):
    """Persist VARCHAR bytes while restoring the redacting value boundary."""

    impl = String(160)
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        return None if value is None else PasswordVerifier(value)

    def process_result_value(self, value, _dialect):
        return None if value is None else PasswordVerifier(value)


class _LowerHexDigest(ColumnElement):
    """Dialect-specific SQL for the same 64-character lowercase digest invariant."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_LowerHexDigest, "sqlite")
def _compile_lower_hex_digest_sqlite(element, _compiler, **_kw):
    name = element.column_name
    return f"length({name}) = 64 AND {name} = lower({name}) AND {name} NOT GLOB '*[^0-9a-f]*'"


@compiles(_LowerHexDigest, "postgresql")
def _compile_lower_hex_digest_postgresql(element, _compiler, **_kw):
    name = element.column_name
    return f"char_length({name}) = 64 AND {name} ~ '^[0-9a-f]{{64}}$'"


class _LegacyFalseDefault(ColumnElement):
    """A false default that preserves SQLite's already-migrated quoted `0`."""

    type = Boolean()
    inherit_cache = True


@compiles(_LegacyFalseDefault, "sqlite")
def _compile_legacy_false_default_sqlite(_element, _compiler, **_kw):
    return "'0'"


@compiles(_LegacyFalseDefault, "postgresql")
def _compile_legacy_false_default_postgresql(_element, _compiler, **_kw):
    return "false"


class _JsonIsValid(ColumnElement):
    """Portable validation for JSON stored as legacy TEXT columns."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_JsonIsValid, "sqlite")
def _compile_json_is_valid_sqlite(element, _compiler, **_kw):
    return f"json_valid({element.column_name})"


@compiles(_JsonIsValid, "postgresql")
def _compile_json_is_valid_postgresql(element, _compiler, **_kw):
    return f"CAST({element.column_name} AS JSONB) IS NOT NULL"


class _SecretFreeJson(ColumnElement):
    """Database guard for JSON object keys that could contain credentials."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_SecretFreeJson, "sqlite")
def _compile_secret_free_json_sqlite(element, _compiler, **_kw):
    return " AND ".join(
        f"instr(lower({element.column_name}), '{term}') = 0"
        for term in ("token", "secret", "password", "api_key", "credential", "authorization")
    )


@compiles(_SecretFreeJson, "postgresql")
def _compile_secret_free_json_postgresql(element, _compiler, **_kw):
    return f"NOT phase4_json_has_secret_key({element.column_name}::jsonb)"


class _JsonTextMatchesColumn(ColumnElement):
    """Require one JSON string property to equal a scalar sibling column."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, json_column: str, json_key: str, column_name: str):
        self.json_column = json_column
        self.json_key = json_key
        self.column_name = column_name


@compiles(_JsonTextMatchesColumn, "sqlite")
def _compile_json_text_matches_column_sqlite(element, _compiler, **_kw):
    return (f"json_extract({element.json_column}, '$.{element.json_key}') "
            f"IS {element.column_name}")


@compiles(_JsonTextMatchesColumn, "postgresql")
def _compile_json_text_matches_column_postgresql(element, _compiler, **_kw):
    field = f"CAST({element.json_column} AS JSONB) -> '{element.json_key}'"
    return (f"{field} IS NOT NULL AND jsonb_typeof({field}) = 'string' AND "
            f"CAST({element.json_column} AS JSONB) ->> '{element.json_key}' "
            f"= {element.column_name}")


class _JsonNumberEquals(ColumnElement):
    """Require one JSON numeric property to equal a scalar sibling value."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, json_column: str, json_key: str, expected: str):
        self.json_column = json_column
        self.json_key = json_key
        self.expected = expected


@compiles(_JsonNumberEquals, "sqlite")
def _compile_json_number_equals_sqlite(element, _compiler, **_kw):
    return (f"json_extract({element.json_column}, '$.{element.json_key}') "
            f"IS {element.expected}")


@compiles(_JsonNumberEquals, "postgresql")
def _compile_json_number_equals_postgresql(element, _compiler, **_kw):
    field = f"CAST({element.json_column} AS JSONB) -> '{element.json_key}'"
    return (f"{field} IS NOT NULL AND jsonb_typeof({field}) = 'number' AND "
            f"({field} #>> '{{}}')::numeric = {element.expected}")


class _ContentAddress(ColumnElement):
    """Portable strict ``sha256:<64 lowercase hex>`` validation."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_ContentAddress, "sqlite")
def _compile_content_address_sqlite(element, _compiler, **_kw):
    name = element.column_name
    return (f"length({name}) = 71 AND substr({name}, 1, 7) = 'sha256:' AND "
            f"substr({name}, 8) = lower(substr({name}, 8)) AND "
            f"substr({name}, 8) NOT GLOB '*[^0-9a-f]*'")


@compiles(_ContentAddress, "postgresql")
def _compile_content_address_postgresql(element, _compiler, **_kw):
    return f"{element.column_name} ~ '^sha256:[0-9a-f]{{64}}$'"


class _NullableContentAddress(_ContentAddress):
    """Allow legacy NULL while refusing malformed newly written receipt keys."""


@compiles(_NullableContentAddress, "sqlite")
def _compile_nullable_content_address_sqlite(element, _compiler, **_kw):
    return f"{element.column_name} IS NULL OR ({_compile_content_address_sqlite(element, _compiler, **_kw)})"


@compiles(_NullableContentAddress, "postgresql")
def _compile_nullable_content_address_postgresql(element, _compiler, **_kw):
    return f"{element.column_name} IS NULL OR ({_compile_content_address_postgresql(element, _compiler, **_kw)})"


class _Utf8SizeAtMost(ColumnElement):
    """Bound canonical UTF-8 documents identically on SQLite and PostgreSQL."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str, maximum: int):
        self.column_name = column_name
        self.maximum = maximum


@compiles(_Utf8SizeAtMost, "sqlite")
def _compile_utf8_size_sqlite(element, _compiler, **_kw):
    return f"length(CAST({element.column_name} AS BLOB)) <= {element.maximum}"


@compiles(_Utf8SizeAtMost, "postgresql")
def _compile_utf8_size_postgresql(element, _compiler, **_kw):
    return f"octet_length({element.column_name}) <= {element.maximum}"


class _ClosedCode(ColumnElement):
    """Portable ``[A-Z][A-Z0-9_]{0,63}`` validation."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_ClosedCode, "sqlite")
def _compile_closed_code_sqlite(element, _compiler, **_kw):
    name = element.column_name
    return (f"length({name}) BETWEEN 1 AND 64 AND substr({name}, 1, 1) GLOB '[A-Z]' "
            f"AND {name} NOT GLOB '*[^A-Z0-9_]*'")


@compiles(_ClosedCode, "postgresql")
def _compile_closed_code_postgresql(element, _compiler, **_kw):
    return f"{element.column_name} ~ '^[A-Z][A-Z0-9_]{{0,63}}$'"


class _NullableClosedCode(_ClosedCode):
    """Closed code validation that preserves an explicit absent dimension."""


@compiles(_NullableClosedCode, "sqlite")
def _compile_nullable_closed_code_sqlite(element, compiler, **kw):
    return f"{element.column_name} IS NULL OR ({_compile_closed_code_sqlite(element, compiler, **kw)})"


@compiles(_NullableClosedCode, "postgresql")
def _compile_nullable_closed_code_postgresql(element, compiler, **kw):
    return f"{element.column_name} IS NULL OR ({_compile_closed_code_postgresql(element, compiler, **kw)})"


class _IsoCurrency(ColumnElement):
    """Portable uppercase ISO-4217 shape without choosing business currencies."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str, *, nullable: bool = False):
        self.column_name = column_name
        self.nullable = nullable


@compiles(_IsoCurrency, "sqlite")
def _compile_iso_currency_sqlite(element, _compiler, **_kw):
    body = (f"length({element.column_name}) = 3 AND "
            f"{element.column_name} NOT GLOB '*[^A-Z]*'")
    return f"{element.column_name} IS NULL OR ({body})" if element.nullable else body


@compiles(_IsoCurrency, "postgresql")
def _compile_iso_currency_postgresql(element, _compiler, **_kw):
    body = f"{element.column_name} ~ '^[A-Z]{{3}}$'"
    return f"{element.column_name} IS NULL OR ({body})" if element.nullable else body


class _ReviewNoteValid(ColumnElement):
    """Require trimmed, control-free review text of at most 4096 UTF-8 bytes."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_ReviewNoteValid, "sqlite")
def _compile_review_note_sqlite(element, _compiler, **_kw):
    name = element.column_name
    controls = " AND ".join(f"instr({name}, char({value})) = 0" for value in (*range(32), 127))
    return (f"{name} = trim({name}) AND length(CAST({name} AS BLOB)) <= 4096 "
            f"AND {controls}")


@compiles(_ReviewNoteValid, "postgresql")
def _compile_review_note_postgresql(element, _compiler, **_kw):
    name = element.column_name
    return f"{name} = btrim({name}) AND octet_length({name}) <= 4096 AND {name} !~ '[[:cntrl:]]'"


def _admission_address_check(table: str) -> CheckConstraint:
    return CheckConstraint(_NullableContentAddress("admission_address"),
                           name=f"ck_{table}_admission_address")


class _AttributionCoherence(ColumnElement):
    """Dialect-identical source/state/address rules for durable execution facts."""

    type = Boolean()
    inherit_cache = True


@compiles(_AttributionCoherence, "sqlite")
def _compile_attribution_coherence_sqlite(_element, _compiler, **_kw):
    return "(" \
        "attribution_state = 'VERIFIED_GRAPH' AND strategy_key LIKE 'ir.%' " \
        "AND strategy_version IS NOT NULL AND length(strategy_version) > 0 " \
        "AND strategy_version NOT GLOB '*[^0-9]*' " \
        "AND graph_address IS NOT NULL AND admission_address IS NOT NULL" \
        ") OR (" \
        "attribution_state = 'NON_GRAPH' AND graph_address IS NULL " \
        "AND (strategy_key IS NULL OR strategy_key NOT LIKE 'ir.%')" \
        ") OR (attribution_state = 'LEGACY_UNVERIFIED' AND graph_address IS NULL)"


@compiles(_AttributionCoherence, "postgresql")
def _compile_attribution_coherence_postgresql(_element, _compiler, **_kw):
    return "(" \
        "attribution_state = 'VERIFIED_GRAPH' AND strategy_key LIKE 'ir.%%' " \
        "AND strategy_version ~ '^[0-9]+$' " \
        "AND graph_address IS NOT NULL AND admission_address IS NOT NULL" \
        ") OR (" \
        "attribution_state = 'NON_GRAPH' AND graph_address IS NULL " \
        "AND (strategy_key IS NULL OR strategy_key NOT LIKE 'ir.%%')" \
        ") OR (attribution_state = 'LEGACY_UNVERIFIED' AND graph_address IS NULL)"


def _graph_attribution_table_args(table: str) -> tuple[CheckConstraint, ...]:
    # 0040 must upgrade populated SQLite parents without rebuilding tables under
    # live foreign keys. The new tuple is therefore enforced by identical
    # INSERT/UPDATE validation triggers on both dialects; the existing receipt
    # address check remains a native CHECK.
    return (_admission_address_check(table),)


def _install_graph_attribution_validation(table) -> None:
    trigger = f"{table.name}_validate_graph_attribution"
    sqlite_valid = (
        "((NEW.attribution_state = 'VERIFIED_GRAPH' AND NEW.strategy_key LIKE 'ir.%%' "
        "AND NEW.strategy_version IS NOT NULL AND length(NEW.strategy_version) > 0 "
        "AND NEW.strategy_version NOT GLOB '*[^0-9]*' "
        "AND NEW.graph_address IS NOT NULL AND length(NEW.graph_address) = 71 "
        "AND substr(NEW.graph_address,1,7) = 'sha256:' "
        "AND substr(NEW.graph_address,8) = lower(substr(NEW.graph_address,8)) "
        "AND substr(NEW.graph_address,8) NOT GLOB '*[^0-9a-f]*' "
        "AND NEW.admission_address IS NOT NULL) OR "
        "(NEW.attribution_state = 'NON_GRAPH' AND NEW.graph_address IS NULL "
        "AND (NEW.strategy_key IS NULL OR NEW.strategy_key NOT LIKE 'ir.%%')) OR "
        "(NEW.attribution_state = 'LEGACY_UNVERIFIED' AND NEW.graph_address IS NULL))")
    for operation in ("INSERT", "UPDATE"):
        event.listen(table, "after_create", DDL(
            f"CREATE TRIGGER {trigger}_{operation.lower()} BEFORE {operation} ON {table.name} "
            f"WHEN NOT {sqlite_valid} BEGIN "
            "SELECT RAISE(ABORT, 'GRAPH_ATTRIBUTION_MISMATCH'); END"
        ).execute_if(dialect="sqlite"))
    function = f"{trigger}_fn"
    event.listen(table, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        "IF NOT (((NEW.attribution_state = 'VERIFIED_GRAPH' "
        "AND NEW.strategy_key LIKE 'ir.%%' AND NEW.strategy_version ~ '^[0-9]+$' "
        "AND NEW.graph_address ~ '^sha256:[0-9a-f]{64}$' "
        "AND NEW.admission_address IS NOT NULL) OR "
        "(NEW.attribution_state = 'NON_GRAPH' AND NEW.graph_address IS NULL "
        "AND (NEW.strategy_key IS NULL OR NEW.strategy_key NOT LIKE 'ir.%%')) OR "
        "(NEW.attribution_state = 'LEGACY_UNVERIFIED' AND NEW.graph_address IS NULL))) THEN "
        "RAISE EXCEPTION 'GRAPH_ATTRIBUTION_MISMATCH'; END IF; RETURN NEW; "
        "END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table.name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    ).execute_if(dialect="postgresql"))


def _install_graph_attribution_insert_guard(table) -> None:
    """Reject stale post-0040 entry writers while migration can retain old rows."""
    trigger = f"{table.name}_refuse_legacy_attribution_insert"
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table.name} "
        "WHEN NEW.attribution_state = 'LEGACY_UNVERIFIED' OR "
        "(NEW.strategy_key LIKE 'ir.%%' AND NEW.attribution_state <> 'VERIFIED_GRAPH') BEGIN "
        "SELECT RAISE(ABORT, 'GRAPH_ATTRIBUTION_UNVERIFIED'); END"
    ).execute_if(dialect="sqlite"))
    function = f"{trigger}_fn"
    event.listen(table, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        "IF NEW.attribution_state = 'LEGACY_UNVERIFIED' OR "
        "(NEW.strategy_key LIKE 'ir.%%' AND NEW.attribution_state <> 'VERIFIED_GRAPH') THEN "
        "RAISE EXCEPTION 'GRAPH_ATTRIBUTION_UNVERIFIED'; END IF; RETURN NEW; "
        "END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table.name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    ).execute_if(dialect="postgresql"))


def _install_postgresql_immutable_trigger(table, message: str, *, sqlstate: str | None = None) -> None:
    """Make append-only facts immutable on PostgreSQL as well as SQLite."""
    function_name = f"{table.name}_refuse_mutation"
    event.listen(
        table,
        "after_create",
        DDL(
            f"CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '{message}'"
            f"{f' USING ERRCODE = {sqlstate!r}' if sqlstate else ''}; END; $$ LANGUAGE plpgsql"
        ).execute_if(dialect="postgresql"),
    )
    event.listen(
        table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {function_name} BEFORE UPDATE OR DELETE ON {table.name} "
            f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
        ).execute_if(dialect="postgresql"),
    )


def _install_immutable_column_guard(table, column: str, message: str) -> None:
    """Keep one nullable identity byte-for-byte stable after row insertion."""
    trigger = f"{table.name}_refuse_{column}_rebind"
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table.name} "
        f"WHEN NEW.{column} IS NOT OLD.{column} BEGIN "
        f"SELECT RAISE(ABORT, '{message}'); END"
    ).execute_if(dialect="sqlite"))
    function = f"{trigger}_fn"
    event.listen(table, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        f"IF NEW.{column} IS DISTINCT FROM OLD.{column} THEN "
        f"RAISE EXCEPTION '{message}'; END IF; RETURN NEW; "
        "END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table.name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    ).execute_if(dialect="postgresql"))


# Segments whose positions are MARGINED rather than fully paid for: only the
# margin left cash, so the position contributes margin + unrealized P&L to equity
# — never its full notional, which would double-count the leverage. They can also
# be genuinely SHORT, unlike the long-premium options path.
#
# A named set rather than a repeated string literal because the two methods below
# must never disagree about which segments are leveraged: one saying "futures are
# margined" while the other says "futures are fully paid" would inflate portfolio
# equity by the notional on every futures tick.
MARGIN_SEGMENTS = frozenset({"equity_intraday", "index_futures"})

# FUNDED segments: the broker lends part of the position and charges interest for
# every day it is held. Their P&L is TIME-DEPENDENT — it worsens while you do
# nothing — which no other segment here is. `mtf` is the only member today.
#
# Separate from MARGIN_SEGMENTS on purpose: both are leveraged, but "only the
# margin left cash" and "interest accrues daily" are different facts, and a
# single set conflating them would silently give futures a carry cost or MTF an
# intraday square-off.
FUNDED_SEGMENTS = frozenset({"mtf"})


class Base(DeclarativeBase):
    pass


# The deployment every pre-existing row belongs to. Before Phase B the system had
# exactly one implicit book — one capital balance, one arm switch, one strategy
# assignment per instrument — and this id names it retroactively. Rows created
# before deployments existed are not "unattributed"; they were all executed by this
# one. Keep it as a constant rather than a literal 1: the number appears in a
# server_default, a seed, a backfill and every lookup default, and those four must
# never drift apart.
LEGACY_DEPLOYMENT_ID = 1
#: The owner every pre-existing row belongs to. This system had exactly one owner until
#: tenancy existed, and that owner is named retroactively rather than left NULL — a NULL
#: owner is indistinguishable from "we lost track of whose this is", and on a table that
#: grants the authority to trade, those two must never look the same. Kept as a constant
#: for the same reason as `LEGACY_DEPLOYMENT_ID`: it appears in a server_default, a seed and
#: every scoped lookup, and those must not drift apart.
#:
#: It is deliberately the SAME string as `app/api/principal.py::OWNER.id`. Two independently
#: invented owner identities would resolve the same human to two different sets of resources —
#: authenticated requests seeing one book and the engine writing to another — and the symptom
#: would be missing data rather than an error. `tests/test_connection_store.py` pins the match.
LEGACY_OWNER_ID = "owner"
LEGACY_USER_ID = "owner-user"
LEGACY_BROKER_ACCOUNT_ID = "account.default"


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_organizations_status"),
    )

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                         server_default="active")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    )

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email_normalized: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                         server_default="active")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)

    @validates("email_normalized")
    def _normalize_email(self, _key: str, value: str) -> str:
        return value.strip().lower()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')",
                        name="ck_memberships_role"),
        CheckConstraint("status IN ('active', 'invited', 'revoked')",
                        name="ck_memberships_status"),
    )

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.organization_id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member",
                                      server_default="member")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                        server_default="active")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)


class UserSession(Base):
    """An opaque bearer credential bound to one active organization membership.

    The bearer itself is never a model field.  Only its lowercase SHA-256 digest
    reaches this table, which makes a database copy unable to authenticate a
    caller by itself.
    """
    __tablename__ = "user_sessions"
    __table_args__ = (
        CheckConstraint(_LowerHexDigest("token_digest"),
                        name="ck_user_sessions_token_digest"),
        ForeignKeyConstraint(
            ("organization_id", "user_id"),
            ("memberships.organization_id", "memberships.user_id"),
            name="fk_user_sessions_active_membership", ondelete="RESTRICT"),
        UniqueConstraint("token_digest", name="uq_user_sessions_token_digest"),
        Index("ix_user_sessions_owner_active", "organization_id", "user_id",
              "revoked_at", "expires_at"),
    )

    # Random, non-secret handle for revocation/audit operations.  It is never a
    # bearer credential and cannot be exchanged for one.
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class BrowserCredential(Base):
    """Versioned verifier only; no password or verifier in object representations."""
    __tablename__ = "browser_credentials"
    __table_args__ = (
        CheckConstraint("length(verifier) BETWEEN 1 AND 160", name="ck_browser_credential_length"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    verifier: Mapped[PasswordVerifier] = mapped_column(PasswordVerifierType(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class EnrollmentInvite(Base):
    __tablename__ = "enrollment_invites"
    __table_args__ = (
        CheckConstraint(_LowerHexDigest("invite_digest"), name="ck_enrollment_digest"),
        CheckConstraint("purpose = 'enrollment'", name="ck_enrollment_purpose"),
        CheckConstraint("expires_at > created_at", name="ck_enrollment_expiry"),
        Index("ix_enrollment_expiry", "expires_at"),
    )
    invite_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class BrowserSession(Base):
    """Idle metadata for the existing UserSession authority, never a second bearer."""
    __tablename__ = "browser_sessions"
    session_id: Mapped[str] = mapped_column(ForeignKey("user_sessions.session_id"), primary_key=True)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class BrowserAuthAttempt(Base):
    __tablename__ = "browser_auth_attempts"
    __table_args__ = (
        CheckConstraint(_LowerHexDigest("key_digest"), name="ck_browser_attempt_digest"),
        CheckConstraint("attempts BETWEEN 1 AND 60", name="ck_browser_attempt_count"),
        Index("ix_browser_attempt_expiry", "expires_at"),
    )
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)


class OAuthCallbackState(Base):
    """One short-lived, digest-only authorization redirect binding.

    The opaque browser value is never stored.  It is an anti-CSRF capability for
    exactly one connection and one durable user session, consumed atomically
    before a provider receives the request token.
    """
    __tablename__ = "oauth_callback_states"
    __table_args__ = (
        CheckConstraint(_LowerHexDigest("state_digest"),
                        name="ck_oauth_callback_states_digest"),
        ForeignKeyConstraint(("organization_id", "user_id"),
                             ("memberships.organization_id", "memberships.user_id"),
                             name="fk_oauth_callback_states_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(("session_id",), ("user_sessions.session_id",),
                             name="fk_oauth_callback_states_session", ondelete="RESTRICT"),
        ForeignKeyConstraint(("connection_id",), ("broker_connections.id",),
                             name="fk_oauth_callback_states_connection", ondelete="RESTRICT"),
        Index("ix_oauth_callback_states_expiry", "expires_at"),
    )

    state_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                     default=dt.datetime.now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # Completion is deliberately distinct from consumption.  The callback spends
    # its anti-CSRF capability before an authenticator runs, so ``consumed_at`` may
    # be present after an exchange failure.  This fact is written atomically with
    # BrokerConnection.last_authenticated_at and binds that write to one browser
    # session without persisting the raw state or request token.
    credential_stored_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, nullable=True)


class BrokerAccount(Base):
    __tablename__ = "broker_accounts"
    __table_args__ = (
        UniqueConstraint("owner_id", "broker", "external_account_id",
                         name="uq_broker_accounts_owner_broker_external"),
        Index("ux_broker_accounts_owner_account", "owner_id", "broker_account_id", unique=True),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_broker_accounts_status"),
    )

    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # By value on purpose: organizations are user-plane while this identity scopes money.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker: Mapped[str] = mapped_column(String(32), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                        server_default="active")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now,
                                                     nullable=False)


class AccountExecutionLease(Base):
    """Durable authority for the one execution actor of a broker account."""
    __tablename__ = "account_execution_leases"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("broker_accounts.owner_id", "broker_accounts.broker_account_id"),
            name="fk_account_execution_leases_account", ondelete="RESTRICT"),
        CheckConstraint("fence_epoch > 0", name="ck_account_execution_leases_epoch"),
        CheckConstraint(
            "state IN ('idle', 'recovering', 'active', 'blocked')",
            name="ck_account_execution_leases_state"),
        CheckConstraint(
            "desired_state IN ('disabled', 'armed')",
            name="ck_account_execution_leases_desired_state"),
        CheckConstraint(
            "effective_state IN ('disabled', 'armed')",
            name="ck_account_execution_leases_effective_state"),
        CheckConstraint("control_revision >= 0", name="ck_account_execution_leases_revision"),
        CheckConstraint(
            "(state = 'idle' AND cell_id IS NULL AND worker_id IS NULL "
            "AND heartbeat_at IS NULL AND expires_at IS NULL) OR "
            "(state <> 'idle' AND cell_id IS NOT NULL AND worker_id IS NOT NULL "
            "AND heartbeat_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND expires_at > heartbeat_at)",
            name="ck_account_execution_leases_holder_shape"),
        CheckConstraint(
            "(state = 'active' AND reconciled_at IS NOT NULL) OR state <> 'active'",
            name="ck_account_execution_leases_active_reconciled"),
        Index("ix_account_execution_leases_expiry_state", "expires_at", "state"),
        Index("ix_account_execution_leases_worker", "cell_id", "worker_id"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                              server_default="1")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="idle",
                                       server_default="idle")
    cell_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    host_diagnostic: Mapped[str] = mapped_column(String(160), nullable=False, default="",
                                                 server_default="")
    claimed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    recovery_started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    reconciled_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    blocked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    block_reason: Mapped[str] = mapped_column(String(200), nullable=False, default="",
                                              server_default="")
    desired_state: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="disabled", server_default="disabled")
    effective_state: Mapped[str] = mapped_column(String(16), nullable=False,
                                                  default="disabled", server_default="disabled")
    control_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default="0")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                     default=dt.datetime.now)


class AccountExecutionLeaseHistory(Base):
    """Sparse authority transitions. Heartbeats deliberately do not land here."""
    __tablename__ = "account_execution_lease_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("account_execution_leases.owner_id", "account_execution_leases.broker_account_id"),
            name="fk_account_execution_history_lease", ondelete="RESTRICT"),
        CheckConstraint("fence_epoch > 0", name="ck_account_execution_history_epoch"),
        CheckConstraint(
            "transition IN ('claim', 'takeover', 'activate', 'block', 'release', "
            "'cancel', 'fence_rejection')",
            name="ck_account_execution_history_transition"),
        Index("ix_account_execution_history_account", "owner_id", "broker_account_id", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_id: Mapped[str] = mapped_column(String(96), nullable=False, default="",
                                         server_default="")
    worker_id: Mapped[str] = mapped_column(String(96), nullable=False, default="",
                                           server_default="")
    transition: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False, default="",
                                        server_default="")
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                      default=dt.datetime.now)


class AccountExecutionCommand(Base):
    """Epoch-stamped money/control command journal; not the event outbox."""
    __tablename__ = "account_execution_commands"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("account_execution_leases.owner_id", "account_execution_leases.broker_account_id"),
            name="fk_account_execution_commands_lease", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "broker_account_id", "idempotency_key",
                         name="uq_account_execution_commands_idempotency"),
        CheckConstraint("fence_epoch > 0", name="ck_account_execution_commands_epoch"),
        CheckConstraint(
            "state IN ('prepared', 'processing', 'sent_unknown', 'acknowledged', 'resolved', "
            "'cancelled', 'failed', 'blocked')",
            name="ck_account_execution_commands_state"),
        CheckConstraint(_LowerHexDigest("request_digest"),
                        name="ck_account_execution_commands_digest"),
        Index("ix_account_execution_commands_recovery", "owner_id", "broker_account_id",
              "state", "fence_epoch"),
        Index("ix_account_execution_commands_age", "state", "updated_at"),
    )
    command_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_id: Mapped[str] = mapped_column(String(96), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(96), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(96), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_tag: Mapped[str] = mapped_column(String(32), nullable=False, default="",
                                            server_default="")
    venue_idempotency_key: Mapped[str] = mapped_column(String(96), nullable=False, default="",
                                                       server_default="")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="prepared",
                                       server_default="prepared")
    broker_order_id: Mapped[str] = mapped_column(String(64), nullable=False, default="",
                                                 server_default="")
    protective_id: Mapped[str] = mapped_column(String(64), nullable=False, default="",
                                               server_default="")
    requested_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_side: Mapped[str] = mapped_column(String(8), nullable=False, default="",
                                                server_default="")
    requested_trigger: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="",
                                            server_default="")
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False, default="",
                                               server_default="")
    expected_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                     default=dt.datetime.now)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_digest: Mapped[str] = mapped_column(String(64), nullable=False, default="",
                                                   server_default="")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                     default=dt.datetime.now)


class Deployment(Base):
    """A strategy, running, with its own parameters, universe, capital and switches.

    THE primary execution object. Before this existed, "what is running" was spread
    across `instrument_state.strategy_key`, `watchlists.strategy_key`, the global
    `Settings`/`runtime_config` merge, and a single in-memory `armed` flag on the
    runner — six places, none of them addressable, and no way for two strategies to
    run different risk parameters or hold the same underlying.

    Everything about this table is designed so that today's behaviour is EXACTLY
    deployment 1 and nothing else changes:

    - `universe_mode='legacy'` means "whatever the per-instrument config and active
      watchlists say", i.e. the existing resolution path, untouched.
    - `allocation=None` means "the whole account", which is what a single book has.
    - `strategy_key=None` means "resolve per instrument, as before" rather than
      pinning one strategy across the book.
    - `armed` starts False, matching the disarm-on-every-start invariant.

    A second deployment therefore cannot appear by accident: it has to be created,
    and until one is, every query that filters by deployment sees the same rows it
    saw before.
    """
    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_deployments_owner_name"),
        Index("ix_deployments_owner_account", "owner_id", "broker_account_id"),
        *_graph_attribution_table_args("deployments"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))

    # ── what runs ────────────────────────────────────────────────────────────
    # NULL = per-instrument resolution (the legacy path). A real deployment pins one.
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Filled by Phase D (immutable strategy identity). NULL until then, and NULL on
    # the legacy deployment forever — it does not pin a strategy, so it cannot pin a
    # version either.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NULL is explicit legacy quarantine.  An address proves causal admission only;
    # later phases still require full deployment preflight before activation.
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="NON_GRAPH", server_default="NON_GRAPH")

    # ── where it runs ────────────────────────────────────────────────────────
    # The broker account this book belongs to. One account today; the column exists
    # so that adding a second is a row, not a schema change.
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    # legacy | watchlist | explicit — how this deployment's instruments are decided.
    universe_mode: Mapped[str] = mapped_column(String(16), default="legacy",
                                               server_default="legacy")
    # By value: deployments are MONEY plane while watchlists are USER plane. Repository
    # composition verifies that a selected watchlist belongs to this deployment's owner.
    watchlist_id: Mapped[int | None] = mapped_column(nullable=True)

    # ── how it is parameterised (Phase C reads this) ─────────────────────────
    # JSON object of deployment-scoped overrides over platform defaults. Empty
    # object = "inherit everything", which is what the legacy deployment does.
    params_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    # ── capital ──────────────────────────────────────────────────────────────
    # NULL = the entire account (today's single-book behaviour). A number caps what
    # this deployment may deploy, so two books can share one account.
    allocation: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── runtime state + lifecycle ────────────────────────────────────────────
    # draft | active | paused | archived. Only `active` is ever scanned.
    status: Mapped[str] = mapped_column(String(12), default="active",
                                        server_default="active")
    # Per-deployment arm, alongside (never instead of) the global master switch.
    # False on creation and reset on every process start — same invariant the global
    # flag has, for the same reason.
    armed: Mapped[bool] = mapped_column(Boolean, default=False,
                                        server_default=_LegacyFalseDefault())
    # Set when this deployment's own daily-loss halt trips; cleared next session.
    halted_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "strategy_key": self.strategy_key,
                "strategy_version": self.strategy_version,
                "graph_address": self.graph_address,
                "admission_address": self.admission_address,
                "attribution_state": self.attribution_state,
                "broker_account_id": self.broker_account_id,
                "universe_mode": self.universe_mode, "watchlist_id": self.watchlist_id,
                "allocation": self.allocation, "status": self.status,
                "armed": self.armed,
                "halted_on": self.halted_on.isoformat() if self.halted_on else None,
                "notes": self.notes}


class ExecutionIntent(Base):
    """The immutable request to open one position through a broker connection."""
    __tablename__ = "execution_intents"
    __table_args__ = (
        CheckConstraint("intent = 'ENTRY'", name="ck_execution_intent_entry"),
        CheckConstraint("requested_qty > 0", name="ck_execution_intent_requested_qty"),
        Index("ix_execution_intents_owner_account", "owner_id", "broker_account_id"),
        *_graph_attribution_table_args("execution_intents"),
    )

    client_intent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), index=True, nullable=False)
    #: Whose money this intent moves. Written at creation and matched by
    #: `unresolved_entries`, so it decides which unresolved live entries a restarting broker
    #: may adopt. Defaulted to `LEGACY_OWNER_ID` rather than NULL for the same reason
    #: `broker_connections.owner_id` is: on a row that records a real order, "belongs to the
    #: original owner" and "we lost track of whose this is" must never look the same.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    broker: Mapped[str] = mapped_column(String(32), nullable=False)
    account_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    connection_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_tag: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    intent: Mapped[str] = mapped_column(String(8), nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    product: Mapped[str | None] = mapped_column(String(16), nullable=True)
    order_type: Mapped[str] = mapped_column(String(12), nullable=False)
    requested_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="NON_GRAPH", server_default="NON_GRAPH")
    context_json: Mapped[str] = mapped_column(
        Text, default="{}", server_default="{}", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.now, nullable=False)
    fence_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ExecutionOrderEvent(Base):
    """One observed lifecycle fact for an execution intent; rows are append-only."""
    __tablename__ = "execution_order_events"
    __table_args__ = (
        CheckConstraint(
            "cumulative_filled_qty >= 0", name="ck_execution_event_filled_qty"),
        CheckConstraint("avg_price >= 0", name="ck_execution_event_avg_price"),
        UniqueConstraint(
            "client_intent_id", "source", "source_event_id",
            name="uq_execution_event_source_identity"),
        Index("ix_execution_order_events_owner_account", "owner_id", "broker_account_id"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_intent_id: Mapped[str] = mapped_column(
        ForeignKey("execution_intents.client_intent_id", ondelete="RESTRICT"),
        nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    broker_status: Mapped[str] = mapped_column(
        String(32), default="", server_default="", nullable=False)
    cumulative_filled_qty: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False)
    avg_price: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False)
    observed_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.now, nullable=False)
    payload_json: Mapped[str] = mapped_column(
        Text, default="{}", server_default="{}", nullable=False)
    anomaly: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False)
    fence_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)


for _trigger_name, _operation in (
    ("execution_order_events_refuse_update", "UPDATE"),
    ("execution_order_events_refuse_delete", "DELETE"),
):
    event.listen(
        ExecutionOrderEvent.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_trigger_name} BEFORE {_operation} "
            "ON execution_order_events BEGIN "
            "SELECT RAISE(ABORT, 'execution_order_events are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )

_install_postgresql_immutable_trigger(
    ExecutionOrderEvent.__table__, "execution_order_events are immutable")


class CapitalState(Base):
    """One ledger per execution book. `cash` and `realized_pnl` are aggregates mutated
    in place, so a paper fill debiting the live book's cash could not be prevented by
    filtering a query — this table needed a row per book, not a predicate.

    A pre-0018 NULL `book` is migrated to the durable ``legacy`` sentinel because a
    composite primary key cannot contain NULL.  It is claimed once from the `mode`
    already stamped on the money rows it produced (`core.execution_book.capital_for_book`);
    it never means a shared book."""

    __tablename__ = "capital_state"
    # `id` remains a compatibility address for historic diagnostics. The composite key is
    # the identity: two customer accounts may both have a paper or live book.
    id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book: Mapped[str] = mapped_column(String(8), primary_key=True, server_default="live")
    initial_capital: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    account_baseline: Mapped[float | None] = mapped_column(Float, nullable=True)  # live account equity when bot-vs-you tracking started
    anchored_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)  # last re-anchor to real broker equity (NULL = never)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class SizingPolicyRecord(Base):
    """Immutable content-addressed sizing policy; never an order authority."""
    __tablename__ = "sizing_policies"
    __table_args__ = (
        CheckConstraint(_ContentAddress("policy_address"), name="ck_sizing_policies_address"),
        CheckConstraint(
            "mode IN ('FIXED_UNITS','FIXED_LOTS','FIXED_CAPITAL','CAPITAL_PCT',"
            "'EQUITY_PCT','RISK_STOP','VOLATILITY_TARGET')",
            name="ck_sizing_policies_mode"),
        CheckConstraint("currency = upper(currency) AND length(currency) = 3",
                        name="ck_sizing_policies_currency"),
        CheckConstraint("version > 0 AND min_quantity > 0",
                        name="ck_sizing_policies_positive"),
        CheckConstraint(_JsonIsValid("canonical_json"),
                        name="ck_sizing_policies_canonical_json"),
        CheckConstraint(
            "fee_buffer_minor >= 0 AND safety_buffer_minor >= 0 AND "
            "(max_quantity IS NULL OR max_quantity >= min_quantity) AND "
            "(max_capital_minor IS NULL OR max_capital_minor > 0)",
            name="ck_sizing_policies_caps"),
        CheckConstraint(
            "(mode = 'FIXED_UNITS' AND fixed_units > 0 AND fixed_lots IS NULL AND "
            "amount_minor IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode = 'FIXED_LOTS' AND fixed_lots > 0 AND fixed_units IS NULL AND "
            "amount_minor IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode = 'FIXED_CAPITAL' AND amount_minor > 0 AND fixed_units IS NULL AND "
            "fixed_lots IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode IN ('CAPITAL_PCT','EQUITY_PCT') AND rate_ppm > 0 AND rate_ppm <= 1000000 "
            "AND fixed_units IS NULL AND fixed_lots IS NULL AND amount_minor IS NULL AND "
            "risk_budget_minor IS NULL AND target_volatility_ppm IS NULL) OR "
            "(mode = 'RISK_STOP' AND risk_budget_minor > 0 AND fixed_units IS NULL AND "
            "fixed_lots IS NULL AND amount_minor IS NULL AND rate_ppm IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode = 'VOLATILITY_TARGET' AND target_volatility_ppm > 0 AND "
            "target_volatility_ppm <= 1000000 AND fixed_units IS NULL AND fixed_lots IS NULL "
            "AND amount_minor IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL)",
            name="ck_sizing_policies_primary_mode"),
    )
    policy_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fixed_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rate_ppm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_budget_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_volatility_ppm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_capital_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fee_buffer_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    safety_buffer_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    allow_resize: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class SizingDecisionRecord(Base):
    __tablename__ = "sizing_decisions"
    __table_args__ = (
        CheckConstraint(_ContentAddress("decision_address"), name="ck_sizing_decisions_address"),
        CheckConstraint(_ContentAddress("product_address"), name="ck_sizing_decisions_product"),
        CheckConstraint(_ContentAddress("inputs_address"), name="ck_sizing_decisions_inputs"),
        CheckConstraint("requested_quantity >= 0 AND admitted_quantity >= 0",
                        name="ck_sizing_decisions_quantity"),
        CheckConstraint("required_capital_minor >= 0 AND estimated_fees_minor >= 0",
                        name="ck_sizing_decisions_money"),
        CheckConstraint(
            "(accepted AND admitted_quantity > 0) OR "
            "(NOT accepted AND admitted_quantity = 0)",
            name="ck_sizing_decisions_outcome"),
        CheckConstraint(_JsonIsValid("input_addresses_json"),
                        name="ck_sizing_decisions_inputs_json"),
    )
    decision_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    policy_address: Mapped[str] = mapped_column(
        ForeignKey("sizing_policies.policy_address", ondelete="RESTRICT"), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    inputs_address: Mapped[str] = mapped_column(String(71), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    required_capital_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estimated_fees_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    binding_constraint: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    resized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    input_addresses_json: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class TargetPositionRequestRecord(Base):
    __tablename__ = "target_position_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("broker_accounts.owner_id", "broker_accounts.broker_account_id"),
            name="fk_target_requests_account", ondelete="RESTRICT"),
        UniqueConstraint("request_address", name="uq_target_requests_address"),
        CheckConstraint(_ContentAddress("request_address"), name="ck_target_requests_address"),
        CheckConstraint(_ContentAddress("product_address"), name="ck_target_requests_product"),
        CheckConstraint("book IN ('paper','live')", name="ck_target_requests_book"),
        CheckConstraint("purpose IN ('ENTRY','TARGET_ADJUSTMENT','RISK_REDUCTION')",
                        name="ck_target_requests_purpose"),
        *_graph_attribution_table_args("target_position_requests"),
    )
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_address: Mapped[str] = mapped_column(String(71), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    book: Mapped[str] = mapped_column(String(8), nullable=False)
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), nullable=False)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(String(24), nullable=False)
    canonical_instrument_key: Mapped[str] = mapped_column(String(64), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    sizing_decision_address: Mapped[str] = mapped_column(
        ForeignKey("sizing_decisions.decision_address", ondelete="RESTRICT"), nullable=False)
    target_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    decision_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class CandidateIntentRecord(Base):
    __tablename__ = "candidate_intents"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("broker_accounts.owner_id", "broker_accounts.broker_account_id"),
            name="fk_candidate_intents_account", ondelete="RESTRICT"),
        UniqueConstraint("candidate_address", name="uq_candidate_intents_address"),
        CheckConstraint(_ContentAddress("candidate_address"), name="ck_candidate_address"),
        CheckConstraint(_ContentAddress("product_address"), name="ck_candidate_product"),
        CheckConstraint(_LowerHexDigest("held_pending_digest"),
                        name="ck_candidate_pending_digest"),
        CheckConstraint(_JsonIsValid("rank_json"), name="ck_candidate_rank_json"),
        CheckConstraint("book IN ('paper','live') AND currency = upper(currency) "
                        "AND length(currency) = 3", name="ck_candidate_book_currency"),
        CheckConstraint("fence_epoch > 0 AND requested_quantity <> 0 "
                        "AND required_capital_minor >= 0", name="ck_candidate_numeric"),
        CheckConstraint("direction IN ('LONG','SHORT')",
                        name="ck_candidate_direction"),
        CheckConstraint("purpose IN ('ENTRY','TARGET_ADJUSTMENT','RISK_REDUCTION')",
                        name="ck_candidate_purpose"),
        CheckConstraint("group_semantics IN ('INDEPENDENT','ATOMIC','RESIZABLE')",
                        name="ck_candidate_group"),
        *_graph_attribution_table_args("candidate_intents"),
    )
    candidate_intent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_address: Mapped[str] = mapped_column(String(71), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    book: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), nullable=False)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(String(24), nullable=False)
    signal_instrument_key: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_instrument_key: Mapped[str] = mapped_column(String(96), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    sizing_decision_address: Mapped[str] = mapped_column(
        ForeignKey("sizing_decisions.decision_address", ondelete="RESTRICT"), nullable=False)
    target_position_request_id: Mapped[str] = mapped_column(
        ForeignKey("target_position_requests.request_id", ondelete="RESTRICT"), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    required_capital_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_semantics: Mapped[str] = mapped_column(String(16), nullable=False)
    freshness_deadline: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    score_scaled: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rank_json: Mapped[str] = mapped_column(Text, nullable=False)
    held_pending_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class CapitalReservationHead(Base):
    __tablename__ = "capital_reservation_heads"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("broker_accounts.owner_id", "broker_accounts.broker_account_id"),
            name="fk_capital_reservation_heads_account", ondelete="RESTRICT"),
        CheckConstraint("book IN ('paper','live') AND currency = upper(currency) "
                        "AND length(currency) = 3", name="ck_reservation_heads_scope"),
        CheckConstraint("revision >= 0", name="ck_reservation_heads_revision"),
    )
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book: Mapped[str] = mapped_column(String(8), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class DecisionBatchRecord(Base):
    __tablename__ = "decision_batches"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id", "book", "currency"),
            ("capital_reservation_heads.owner_id", "capital_reservation_heads.broker_account_id",
             "capital_reservation_heads.book", "capital_reservation_heads.currency"),
            name="fk_decision_batches_head", ondelete="RESTRICT"),
        UniqueConstraint("batch_address", name="uq_decision_batches_address"),
        CheckConstraint(_ContentAddress("batch_address"), name="ck_decision_batch_address"),
        CheckConstraint(_ContentAddress("capital_snapshot_address"),
                        name="ck_decision_batch_capital_snapshot"),
        CheckConstraint(_ContentAddress("margin_snapshot_address"),
                        name="ck_decision_batch_margin_snapshot"),
        CheckConstraint(_ContentAddress("product_policy_address"),
                        name="ck_decision_batch_product_policy"),
        CheckConstraint(_ContentAddress("portfolio_policy_address"),
                        name="ck_decision_batch_portfolio_policy"),
        CheckConstraint(_LowerHexDigest("candidate_set_digest"),
                        name="ck_decision_batch_candidates"),
        CheckConstraint("book IN ('paper','live') AND currency = upper(currency) "
                        "AND length(currency) = 3", name="ck_decision_batch_scope"),
        CheckConstraint("fence_epoch > 0 AND reservation_head_revision >= 0 AND "
                        "margin_available_minor >= 0 AND active_reservation_minor >= 0 AND "
                        "safety_buffer_minor >= 0", name="ck_decision_batch_numeric"),
        CheckConstraint("status IN ('decided','refused')",
                        name="ck_decision_batch_status"),
    )
    decision_batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_address: Mapped[str] = mapped_column(String(71), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    book: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    effective_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    capital_snapshot_address: Mapped[str] = mapped_column(String(71), nullable=False)
    margin_available_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    margin_source: Mapped[str] = mapped_column(String(64), nullable=False)
    margin_observed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    margin_snapshot_address: Mapped[str] = mapped_column(String(71), nullable=False)
    active_reservation_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    safety_buffer_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reservation_head_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    product_policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    sizing_policy_address: Mapped[str] = mapped_column(
        ForeignKey("sizing_policies.policy_address", ondelete="RESTRICT"), nullable=False)
    portfolio_policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    candidate_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    contention_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    tie_break_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    refusal_reason: Mapped[str] = mapped_column(String(200), nullable=False, default="")


class PortfolioAdmissionDecisionRecord(Base):
    __tablename__ = "portfolio_admission_decisions"
    __table_args__ = (
        UniqueConstraint("batch_id", "candidate_intent_id",
                         name="uq_portfolio_decisions_batch_candidate"),
        UniqueConstraint("decision_address", name="uq_portfolio_decisions_address"),
        CheckConstraint(_ContentAddress("decision_address"),
                        name="ck_portfolio_decision_address"),
        CheckConstraint(_JsonIsValid("rank_json"), name="ck_portfolio_decision_rank_json"),
        CheckConstraint(_JsonIsValid("constraints_json"),
                        name="ck_portfolio_decision_constraints_json"),
        CheckConstraint("status IN ('admitted','rejected','resized')",
                        name="ck_portfolio_decision_status"),
        CheckConstraint("requested_quantity <> 0 AND required_capital_minor >= 0 AND "
                        "held_capital_minor >= 0", name="ck_portfolio_decision_numeric"),
        CheckConstraint(
            "(status = 'rejected' AND admitted_quantity = 0 AND reservation_id IS NULL) OR "
            "(status IN ('admitted','resized') AND admitted_quantity <> 0)",
            name="ck_portfolio_decision_outcome"),
    )
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_address: Mapped[str] = mapped_column(String(71), nullable=False)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("decision_batches.decision_batch_id", ondelete="RESTRICT"), nullable=False)
    candidate_intent_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_intents.candidate_intent_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    required_capital_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    held_capital_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    score_scaled: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rank_json: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(String(400), nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CapitalReservationRecord(Base):
    __tablename__ = "capital_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id", "book", "currency"),
            ("capital_reservation_heads.owner_id", "capital_reservation_heads.broker_account_id",
             "capital_reservation_heads.book", "capital_reservation_heads.currency"),
            name="fk_capital_reservations_head", ondelete="RESTRICT"),
        UniqueConstraint("reservation_address", name="uq_capital_reservations_address"),
        UniqueConstraint("decision_id", name="uq_capital_reservations_decision"),
        CheckConstraint(_ContentAddress("reservation_address"),
                        name="ck_capital_reservation_address"),
        CheckConstraint("state IN ('held','submission_pending','partially_consumed',"
                        "'consumed','released','reconciliation_required')",
                        name="ck_capital_reservation_state"),
        CheckConstraint("estimated_minor >= 0 AND consumed_minor >= 0 AND "
                        "consumed_minor <= estimated_minor", name="ck_reservation_money"),
        CheckConstraint("requested_quantity <> 0 AND admitted_quantity <> 0 AND "
                        "consumed_quantity >= 0 AND revision >= 0 AND fence_epoch > 0",
                        name="ck_reservation_quantity_revision"),
    )
    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reservation_address: Mapped[str] = mapped_column(String(71), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    book: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("decision_batches.decision_batch_id", ondelete="RESTRICT"), nullable=False)
    candidate_intent_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_intents.candidate_intent_id", ondelete="RESTRICT"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_admission_decisions.decision_id", ondelete="RESTRICT"),
        nullable=False)
    estimated_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consumed_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    command_id: Mapped[str | None] = mapped_column(
        ForeignKey("account_execution_commands.command_id", ondelete="RESTRICT"), nullable=True)
    last_reconciled_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CapitalReservationEventRecord(Base):
    __tablename__ = "capital_reservation_events"
    __table_args__ = (
        UniqueConstraint("reservation_id", "revision",
                         name="uq_capital_reservation_events_revision"),
        UniqueConstraint("event_address", name="uq_capital_reservation_events_address"),
        CheckConstraint(_ContentAddress("event_address"),
                        name="ck_capital_reservation_event_address"),
        CheckConstraint(_ContentAddress("evidence_address"),
                        name="ck_capital_reservation_event_evidence"),
        CheckConstraint("revision >= 0 AND fence_epoch > 0 AND consumed_minor >= 0 AND "
                        "consumed_quantity >= 0", name="ck_reservation_event_numeric"),
        CheckConstraint("to_state IN ('held','submission_pending','partially_consumed',"
                        "'consumed','released','reconciliation_required')",
                        name="ck_reservation_event_state"),
    )
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_address: Mapped[str] = mapped_column(String(71), nullable=False)
    reservation_id: Mapped[str] = mapped_column(
        ForeignKey("capital_reservations.reservation_id", ondelete="RESTRICT"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    consumed_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consumed_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    fence_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_address: Mapped[str] = mapped_column(String(71), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PositionCampaignRecord(Base):
    __tablename__ = "position_campaigns"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "broker_account_id"),
            ("broker_accounts.owner_id", "broker_accounts.broker_account_id"),
            name="fk_position_campaigns_account", ondelete="RESTRICT"),
        UniqueConstraint("campaign_address", name="uq_position_campaigns_address"),
        CheckConstraint(_ContentAddress("campaign_address"),
                        name="ck_position_campaign_address"),
        CheckConstraint(_ContentAddress("product_address"),
                        name="ck_position_campaign_product"),
        CheckConstraint(_ContentAddress("target_policy_address"),
                        name="ck_position_campaign_target_policy"),
        CheckConstraint("book IN ('paper','live') AND direction IN ('LONG','SHORT')",
                        name="ck_position_campaign_scope"),
        CheckConstraint("status IN ('open','closed','legacy_unattributed') AND revision >= 0",
                        name="ck_position_campaign_state"),
        *_graph_attribution_table_args("position_campaigns"),
    )
    campaign_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_address: Mapped[str] = mapped_column(String(71), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    book: Mapped[str] = mapped_column(String(8), nullable=False)
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), nullable=False)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(String(24), nullable=False)
    canonical_instrument_key: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_instrument_key: Mapped[str] = mapped_column(String(96), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    target_policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    opened_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PositionTrancheRecord(Base):
    __tablename__ = "position_tranches"
    __table_args__ = (
        UniqueConstraint("tranche_address", name="uq_position_tranches_address"),
        CheckConstraint(_ContentAddress("tranche_address"),
                        name="ck_position_tranche_address"),
        CheckConstraint("purpose IN ('ENTRY','ADDITION','REDUCTION') AND "
                        "requested_quantity <> 0 AND admitted_quantity <> 0 AND revision >= 0",
                        name="ck_position_tranche_numeric"),
        CheckConstraint("state IN ('planned','submitted','partially_filled','filled',"
                        "'cancelled','reconciliation_required')",
                        name="ck_position_tranche_state"),
    )
    tranche_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tranche_address: Mapped[str] = mapped_column(String(71), nullable=False)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("position_campaigns.campaign_id", ondelete="RESTRICT"), nullable=False)
    target_position_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("target_position_requests.request_id", ondelete="RESTRICT"), nullable=True)
    candidate_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_intents.candidate_intent_id", ondelete="RESTRICT"), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_batches.decision_batch_id", ondelete="RESTRICT"), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("portfolio_admission_decisions.decision_id", ondelete="RESTRICT"),
        nullable=True)
    reservation_id: Mapped[str | None] = mapped_column(
        ForeignKey("capital_reservations.reservation_id", ondelete="RESTRICT"), nullable=True)
    execution_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("execution_intents.client_intent_id", ondelete="RESTRICT"), nullable=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    terminal_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FillAllocationRecord(Base):
    __tablename__ = "fill_allocations"
    __table_args__ = (
        UniqueConstraint("allocation_address", name="uq_fill_allocations_address"),
        UniqueConstraint("execution_order_event_id", "tranche_id",
                         name="uq_fill_allocations_event_tranche"),
        CheckConstraint(_ContentAddress("allocation_address"),
                        name="ck_fill_allocation_address"),
        CheckConstraint("quantity > 0", name="ck_fill_allocation_quantity"),
    )
    allocation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    allocation_address: Mapped[str] = mapped_column(String(71), nullable=False)
    tranche_id: Mapped[str] = mapped_column(
        ForeignKey("position_tranches.tranche_id", ondelete="RESTRICT"), nullable=False)
    execution_order_event_id: Mapped[int] = mapped_column(
        ForeignKey("execution_order_events.id", ondelete="RESTRICT"), nullable=False)
    trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trades.id", ondelete="RESTRICT"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class InstrumentState(Base):
    __tablename__ = "instrument_state"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    live_interval: Mapped[str] = mapped_column(String(12), default="15minute")
    entries_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    # dual-segment / multi-strategy assignment (Phase 0 foundation)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)  # None = default strategy
    priority_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # "purple" intraday priority
    product: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    overtrade_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # "red" overtrading flag (advisory)
    # Instrument-scoped parameter overrides — the narrowest layer of the
    # Platform -> Deployment -> Instrument chain (app/core/scoped_config.py).
    # "{}" means inherit everything, which every row is today, so this changes
    # nothing until something writes to it.
    params_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_owner_account", "owner_id", "broker_account_id"),
        CheckConstraint(
            "(paper_entry_charge_schedule_id IS NULL) = "
            "(paper_entry_charge_schedule_address IS NULL)",
            name="ck_positions_paper_entry_charge_pair",
        ),
        CheckConstraint(
            _NullableContentAddress("paper_entry_charge_schedule_address"),
            name="ck_positions_paper_entry_charge_address",
        ),
        CheckConstraint(
            "mode = 'paper' OR (paper_entry_charge_schedule_id IS NULL AND "
            "paper_entry_charge_schedule_address IS NULL)",
            name="ck_positions_paper_charge_mode",
        ),
        CheckConstraint(
            "mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR "
            "entry_intent_id IS NOT NULL",
            name="ck_positions_paper_entry_intent_required",
        ),
        *_graph_attribution_table_args("positions"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    # Nullable by design: historic rows predate durable entry intent tracking and
    # remain exactly as recorded rather than being attributed retrospectively.
    entry_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("execution_intents.client_intent_id", ondelete="RESTRICT"),
        index=True, nullable=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))       # LONG | SHORT
    option_type: Mapped[str] = mapped_column(String(4))     # CE | PE
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(16))       # NFO/BFO/NSE_INTRADAY/NFO_FUT
    # product family + originating strategy (Phase 0 foundation)
    segment: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Content hash of the strategy that executed this row (Phase D). NULL is
    # meaningful and is NOT the same as 'unknown': NULL means the row predates
    # the column and is genuinely unattributable, 'unknown' means a strategy was
    # running but could not be identified. Same three-value rule as build_sha —
    # never collapse the two.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="NON_GRAPH", server_default="NON_GRAPH")
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[dt.date] = mapped_column(Date)
    lot_size: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)

    entry_premium: Mapped[float] = mapped_column(Float)
    entry_charges: Mapped[float] = mapped_column(Float)
    # NULL/NULL is permanent historical unknown. New Paper entries persist the
    # exact frozen schedule pair; live rows never use these Paper-only columns.
    paper_entry_charge_schedule_id: Mapped[str | None] = mapped_column(
        String(96), nullable=True)
    paper_entry_charge_schedule_address: Mapped[str | None] = mapped_column(
        String(71), nullable=True)
    entry_cost: Mapped[float] = mapped_column(Float)        # premium*qty + entry charges
    entry_spot: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)
    entry_reason: Mapped[str] = mapped_column(String(400), default="")

    stop_price: Mapped[float] = mapped_column(Float)        # premium floor (SL)
    target_price: Mapped[float] = mapped_column(Float)      # premium ceiling (TP)
    # purple SL/TP tiering (2026-07-17): the SL/TP *percentages* this equity_intraday
    # position was opened with, frozen at entry. NULL for options positions and for
    # legacy equity rows predating this feature — both fall back to the current global
    # intraday_stop_loss_pct/intraday_target_pct knobs at ratchet time.
    entry_sl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_tp_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    last_premium: Mapped[float] = mapped_column(Float, default=0.0)  # live mark
    last_spot: Mapped[float] = mapped_column(Float, default=0.0)
    last_mark_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # highest premium seen since entry — drives the trailing-stop ratchet
    high_water_premium: Mapped[float] = mapped_column(Float, default=0.0)
    # peak-excursion telemetry (E0.3): best/worst unrealized P&L (₹) seen while open,
    # from unrealized_pnl() so it is already segment/direction-aware (e.g. an equity
    # SHORT profits on a spot fall). mfe >= 0, mae <= 0 by construction — both seeded
    # at the 0 excursion at entry. Pure telemetry: never read by cash/P&L/exit logic.
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    # reinforcement + overnight management
    reinforcement_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reinforce_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    held_overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    overnight_pnl: Mapped[float] = mapped_column(Float, default=0.0)   # Σ premium delta across session gaps
    session_close_premium: Mapped[float] = mapped_column(Float, default=0.0)  # mark at last session close
    last_squareoff_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)  # date the daily hold/square-off decision was last made (re-arm each session)
    manual_target: Mapped[bool] = mapped_column(Boolean, default=False)  # owner set the target by hand — reinforcement won't auto-extend it
    no_take_profit: Mapped[bool] = mapped_column(Boolean, default=False)  # owner "let it run": suppress the TP cap (trailing stop still protects)
    gtt_trigger_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Zerodha GTT safety-net stop id (live execution)
    # H2 — live ratchet state (unify onto the backtest-validated RatchetState). NULL =>
    # not ratchet-managed (no risk_model). entry_atr frozen at fill; hw/spot_stop ratchet
    # on completed underlying candles; last_bar_ts guards against double-consuming a bar.
    entry_atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratchet_hw: Mapped[float | None] = mapped_column(Float, nullable=True)
    spot_stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratchet_last_bar_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    mode: Mapped[str] = mapped_column(String(8), default="paper")  # "paper" | "live" — which broker opened it; never mixed in the UI

    def unrealized_pnl(self) -> float:
        """Mark-to-market P&L. Equity intraday and index futures can be real SHORTS
        (profits as price falls); the options path is always long-premium.

        FUNDED (MTF) positions subtract accrued interest. Without it a held
        position looks better every day it is held — the exact opposite of the
        truth — and the error compounds silently for as long as it stays open,
        which for MTF can be weeks. It is the one segment whose P&L moves while
        nothing happens.
        """
        last = self.last_premium or self.entry_premium
        if self.segment in MARGIN_SEGMENTS and self.direction == "SHORT":
            gross = (self.entry_premium - last) * self.qty
        else:
            gross = (last - self.entry_premium) * self.qty
        if self.segment in FUNDED_SEGMENTS:
            gross -= self.accrued_carry()
        return gross

    def accrued_carry(self) -> float:
        """Interest owed so far on a funded position; 0.0 for every other segment.

        Never raises: a carry figure that cannot be computed must not take down
        the mark loop, and 0.0 is the conservative direction here only because
        the alternative is no P&L at all — it is logged as a gap, not treated as
        free money, by the caller that reports it.
        """
        if self.segment not in FUNDED_SEGMENTS:
            return 0.0
        try:
            from app.engine.carry import accrued_to_date
            import datetime as _dt
            entry = self.entry_time.date() if self.entry_time else _dt.date.today()
            today = (self.last_mark_time or self.entry_time or _dt.datetime.now()).date()
            margin = (self.entry_cost or 0.0) - (self.entry_charges or 0.0)
            return accrued_to_date(
                position_value=self.entry_premium * self.qty,
                margin_paid=margin, entry=entry, today=today)
        except Exception:
            return 0.0

    def mtm_value(self) -> float:
        """Contribution to portfolio equity. Options: the contract's liquidation value
        (premium × qty), since the full cost left cash. Leveraged equity (MIS): only
        the MARGIN left cash, so the position returns its margin (entry_cost) plus its
        unrealized P&L — NOT the full notional (last × qty), which double-counts the
        leverage and inflates equity."""
        if self.segment in MARGIN_SEGMENTS:
            return self.entry_cost + self.unrealized_pnl()
        return (self.last_premium or self.entry_premium) * self.qty

    def to_dict(self) -> dict:
        unrealized = self.unrealized_pnl()
        return {
            "id": self.id,
            "instrument_key": self.instrument_key,
            "direction": self.direction,
            "option_type": self.option_type,
            "tradingsymbol": self.tradingsymbol,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "lot_size": self.lot_size,
            "qty": self.qty,
            "entry_premium": round(self.entry_premium, 2),
            "entry_cost": round(self.entry_cost, 2),
            "paper_entry_charge_schedule_id": self.paper_entry_charge_schedule_id,
            "paper_entry_charge_schedule_address": self.paper_entry_charge_schedule_address,
            "entry_time": self.entry_time.isoformat(),
            "entry_reason": self.entry_reason,
            "stop_price": round(self.stop_price, 2),
            "target_price": round(self.target_price, 2),
            "last_premium": round(self.last_premium or self.entry_premium, 2),
            "last_spot": round(self.last_spot, 2),
            "last_mark_time": self.last_mark_time.isoformat() if self.last_mark_time else None,
            "high_water_premium": round(self.high_water_premium or self.entry_premium, 2),
            "mfe": round(self.mfe or 0.0, 2),
            "mae": round(self.mae or 0.0, 2),
            "reinforcement_count": self.reinforcement_count,
            "held_overnight": self.held_overnight,
            "manual_target": self.manual_target,
            "no_take_profit": self.no_take_profit,
            "unrealized_pnl": round(unrealized, 2),
            "mode": self.mode,
            "segment": self.segment or "options",
            "strategy_key": self.strategy_key,
            "strategy_version": self.strategy_version,
            "graph_address": self.graph_address,
            "admission_address": self.admission_address,
            "attribution_state": self.attribution_state,
        }


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_owner_account", "owner_id", "broker_account_id"),
        CheckConstraint(
            "(paper_entry_charge_schedule_id IS NULL) = "
            "(paper_entry_charge_schedule_address IS NULL)",
            name="ck_trades_paper_entry_charge_pair",
        ),
        CheckConstraint(
            "(paper_exit_charge_schedule_id IS NULL) = "
            "(paper_exit_charge_schedule_address IS NULL)",
            name="ck_trades_paper_exit_charge_pair",
        ),
        CheckConstraint(
            _NullableContentAddress("paper_entry_charge_schedule_address"),
            name="ck_trades_paper_entry_charge_address",
        ),
        CheckConstraint(
            _NullableContentAddress("paper_exit_charge_schedule_address"),
            name="ck_trades_paper_exit_charge_address",
        ),
        CheckConstraint(
            "mode = 'paper' OR (paper_entry_charge_schedule_id IS NULL AND "
            "paper_entry_charge_schedule_address IS NULL AND "
            "paper_exit_charge_schedule_id IS NULL AND "
            "paper_exit_charge_schedule_address IS NULL)",
            name="ck_trades_paper_charge_mode",
        ),
        CheckConstraint(
            "mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR "
            "entry_intent_id IS NOT NULL",
            name="ck_trades_paper_entry_intent_required",
        ),
        *_graph_attribution_table_args("trades"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    # NULL preserves the fact that legacy trade rows were created before intents.
    entry_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("execution_intents.client_intent_id", ondelete="RESTRICT"),
        index=True, nullable=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    option_type: Mapped[str] = mapped_column(String(4))
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(16))
    # product family + originating strategy (Phase 0 foundation)
    segment: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Content hash of the strategy that executed this row (Phase D). NULL is
    # meaningful and is NOT the same as 'unknown': NULL means the row predates
    # the column and is genuinely unattributable, 'unknown' means a strategy was
    # running but could not be identified. Same three-value rule as build_sha —
    # never collapse the two.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="NON_GRAPH", server_default="NON_GRAPH")
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[dt.date] = mapped_column(Date)
    qty: Mapped[int] = mapped_column(Integer)

    entry_premium: Mapped[float] = mapped_column(Float)
    paper_entry_charge_schedule_id: Mapped[str | None] = mapped_column(
        String(96), nullable=True)
    paper_entry_charge_schedule_address: Mapped[str | None] = mapped_column(
        String(71), nullable=True)
    entry_cost: Mapped[float] = mapped_column(Float)
    entry_spot: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)

    exit_premium: Mapped[float] = mapped_column(Float)
    exit_charges: Mapped[float] = mapped_column(Float)
    paper_exit_charge_schedule_id: Mapped[str | None] = mapped_column(
        String(96), nullable=True)
    paper_exit_charge_schedule_address: Mapped[str | None] = mapped_column(
        String(71), nullable=True)
    exit_spot: Mapped[float] = mapped_column(Float)
    exit_time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    exit_reason: Mapped[str] = mapped_column(String(32))    # STOP_LOSS|TARGET|STRATEGY_EXIT

    gross_pnl: Mapped[float] = mapped_column(Float)
    charges_total: Mapped[float] = mapped_column(Float)
    net_pnl: Mapped[float] = mapped_column(Float)
    return_pct: Mapped[float] = mapped_column(Float)
    holding_minutes: Mapped[float] = mapped_column(Float)
    win: Mapped[bool] = mapped_column(Boolean)
    # intraday vs overnight attribution
    held_overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    overnight_pnl: Mapped[float] = mapped_column(Float, default=0.0)   # part of net from session gaps
    intraday_pnl: Mapped[float] = mapped_column(Float, default=0.0)    # net - overnight
    reinforcements: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(8), default="paper")  # "paper" | "live" — broker that executed it
    # E0.1: True when exit_premium is a MARK (last_premium / live LTP), not a real
    # fill — reconcile fallbacks (no matching order found, stop-status read failed,
    # stop still resting) and the manual-close paper override. False (default) means
    # a genuine fill: a normal engine exit, a real SL-M/GTT fill, or a real order.
    exit_price_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    # peak-excursion telemetry (E0.3): the position's mfe/mae copied at close, so
    # give-back (Workstream C-P2 / E1) is measurable from the trade log. See
    # Position.mfe/mae for the definition.
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    # Build provenance: the commit this row was executed by. Defaulted at insert
    # from backend/VERSION (written by scripts/deploy.sh) so all four Trade
    # construction sites in broker.py are covered without touching any of them.
    #
    # Three distinguishable states, and the distinction is the point:
    #   <sha>     — executed by an identified build
    #   'unknown' — executed by a process that could not read its VERSION
    #   NULL      — row predates this column (booked before 2026-07-28)
    # Nullable only so the migration can leave historic rows alone; every row
    # written from here on gets a non-NULL value.
    build_sha: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=lambda: get_build_sha()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "instrument_key": self.instrument_key,
            "direction": self.direction,
            "option_type": self.option_type,
            "tradingsymbol": self.tradingsymbol,
            "strike": self.strike,
            "qty": self.qty,
            "entry_premium": round(self.entry_premium, 2),
            "paper_entry_charge_schedule_id": self.paper_entry_charge_schedule_id,
            "paper_entry_charge_schedule_address": self.paper_entry_charge_schedule_address,
            "exit_premium": round(self.exit_premium, 2),
            "paper_exit_charge_schedule_id": self.paper_exit_charge_schedule_id,
            "paper_exit_charge_schedule_address": self.paper_exit_charge_schedule_address,
            "entry_spot": round(self.entry_spot, 2) if self.entry_spot else None,
            "exit_spot": round(self.exit_spot, 2) if self.exit_spot else None,
            "spot_move_pct": (round((self.exit_spot - self.entry_spot) / self.entry_spot * 100, 2)
                              if self.entry_spot and self.exit_spot else None),
            "premium_move_pct": (round((self.exit_premium - self.entry_premium) / self.entry_premium * 100, 2)
                                 if self.entry_premium else None),
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "exit_reason": self.exit_reason,
            "gross_pnl": round(self.gross_pnl, 2),
            "charges_total": round(self.charges_total, 2),
            "net_pnl": round(self.net_pnl, 2),
            "return_pct": round(self.return_pct, 2),
            "holding_minutes": round(self.holding_minutes, 1),
            "win": self.win,
            "held_overnight": self.held_overnight,
            "overnight_pnl": round(self.overnight_pnl, 2),
            "intraday_pnl": round(self.intraday_pnl, 2),
            "reinforcements": self.reinforcements,
            "mode": self.mode,
            "segment": self.segment or "options",
            "strategy_key": self.strategy_key,
            "strategy_version": self.strategy_version,
            "graph_address": self.graph_address,
            "admission_address": self.admission_address,
            "attribution_state": self.attribution_state,
            "exit_price_estimated": bool(self.exit_price_estimated),
            "mfe": round(self.mfe or 0.0, 2),
            "mae": round(self.mae or 0.0, 2),
        }


for _entry_identity_table in (Position.__table__, Trade.__table__):
    _install_immutable_column_guard(
        _entry_identity_table,
        "entry_intent_id",
        f"{_entry_identity_table.name} entry_intent_id is immutable",
    )


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"
    __table_args__ = (
        Index("ix_equity_snapshots_owner_account", "owner_id", "broker_account_id"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    invested: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float)
    open_count: Mapped[int] = mapped_column(Integer)
    # Which execution book this point belongs to (L1.3B). NULL = written before the
    # books were separated; those points belong to whichever book the ledger they were
    # derived from is later attributed to, which is why they are not back-stamped.
    book: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    # optional segment/strategy partition (null = global portfolio snapshot)
    segment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def to_dict(self) -> dict:
        return {
            "time": int(self.time.timestamp()),
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "invested": round(self.invested, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "open_count": self.open_count,
        }


class UniverseInstrument(Base):
    """The dynamic, DB-backed tradable universe. Seeded from the curated list and
    extended at runtime when the owner adds instruments from the homepage /
    backtest winners. `has_options` decides whether the live engine options-trades
    it or just tracks + backtests it."""
    __tablename__ = "universe_instruments"
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    segment: Mapped[str] = mapped_column(String(12))       # NFO/BFO/MCX/NCDEX/NSE/BSE
    spot_exchange: Mapped[str] = mapped_column(String(12))
    spot_symbol: Mapped[str] = mapped_column(String(64))
    option_name: Mapped[str] = mapped_column(String(64), default="")
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    strike_step: Mapped[float] = mapped_column(Float, default=1.0)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    has_options: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(8), default="seed")   # seed | user
    on_home: Mapped[bool] = mapped_column(Boolean, default=False)    # shown on homepage
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # mock seeds (only used by the synthetic market in tests/dryrun)
    mock_spot: Mapped[float] = mapped_column(Float, default=1000.0)
    mock_vol: Mapped[float] = mapped_column(Float, default=0.2)


class UniversePreference(Base):
    """One organization's portfolio choices over canonical market instruments."""
    __tablename__ = "universe_preferences"
    __table_args__ = (
        ForeignKeyConstraint(("instrument_key",), ("universe_instruments.key",),
                             ondelete="RESTRICT", name="fk_universe_preferences_instrument"),
        Index("ix_universe_preferences_owner", "owner_id"),
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"), primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    on_home: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    source: Mapped[str] = mapped_column(String(8), default="seed", server_default=text("'seed'"), nullable=False)


class Watchlist(Base):
    """A named list bound to exactly ONE strategy. Instruments assigned to an *active*
    watchlist are run by the engine on that watchlist's strategy (overriding the
    per-instrument default). New tables (this + the membership below) are created
    additively by `create_all`, so an existing live DB gains them with no ALTER on the
    instrument ledger — behaviour-preserving until a watchlist is actually populated."""
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_watchlists_owner_name"),
        UniqueConstraint("owner_id", "id", name="uq_watchlists_owner_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_key: Mapped[str] = mapped_column(String(64), default="trend_impulse_v3")
    status: Mapped[str] = mapped_column(String(12), default="active")  # active|paused|archived
    interval: Mapped[str | None] = mapped_column(String(12), nullable=True)  # optional default TF
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "strategy_key": self.strategy_key,
                "status": self.status, "interval": self.interval, "notes": self.notes}


class WatchlistMembership(Base):
    """An instrument's membership in a watchlist. `instrument_key` is the primary key,
    so an instrument belongs to AT MOST ONE watchlist — the structural guarantee the
    dispute/incumbency rules rely on."""
    __tablename__ = "watchlist_membership"
    __table_args__ = (
        ForeignKeyConstraint(("owner_id", "watchlist_id"), ("watchlists.owner_id", "watchlists.id"),
                             ondelete="RESTRICT", name="fk_watchlist_membership_owner_watchlist"),
        Index("ix_watchlist_membership_owner_watchlist", "owner_id", "watchlist_id"),
    )
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(nullable=False)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class StrategyLifecycle(Base):
    """The archive: one row per strategy the platform has ever considered, and its
    current lifecycle state. Keeping retired strategies (rather than deleting them)
    is deliberate — a shelved idea can be revived and re-tested when regimes change, or
    tried on a different universe. `last_dsr` carries the last validated performance so
    the archive is a browsable record of what worked, where, and how well."""
    __tablename__ = "strategy_lifecycle"
    __table_args__ = (
        UniqueConstraint("owner_id", "strategy_key", name="uq_strategy_lifecycle_owner_key"),
        UniqueConstraint("owner_id", "id", name="uq_strategy_lifecycle_owner_id"),
        ForeignKeyConstraint(("owner_id", "deployed_watchlist_id"),
                             ("watchlists.owner_id", "watchlists.id"), ondelete="RESTRICT",
                             name="fk_strategy_lifecycle_owner_watchlist"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"), nullable=False, index=True)
    strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="candidate")
    # candidate | running | probation | on_hold | retired
    source: Mapped[str] = mapped_column(String(12), default="builtin")  # builtin | generated
    deployed_watchlist_id: Mapped[int | None] = mapped_column(nullable=True)
    last_dsr: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"strategy_key": self.strategy_key, "status": self.status,
                "source": self.source, "deployed_watchlist_id": self.deployed_watchlist_id,
                "last_dsr": self.last_dsr, "note": self.note}


class GeneratedStrategyRow(Base):
    """A bot-generated strategy that has been APPROVED and deployed, stored as its
    composition JSON (+ the emitted source, for the owner's audit). At engine startup
    `app.core.generated_strategies.register_all` reconstructs each row through the
    sandboxed builder and registers it, so a `gen_*` strategy_key on a watchlist resolves
    to the real generated strategy instead of falling back to the default. Written only
    by the human Approve→Deploy bridge — never by the research process."""
    __tablename__ = "generated_strategies"
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Content hash of the composition (Phase D). `key` is still the PK, so a
    # redeploy of an edited strategy still overwrites in place — recording the
    # version at least makes that overwrite DETECTABLE. Making identity
    # (key, version) is tracked as remaining work.
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    composition_json: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class BacktestComputation(Base):
    """Immutable, ownerless numerical result of a public platform computation."""
    __tablename__ = "backtest_computations"
    execution_address: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_address: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        Index("ix_backtest_computations_dataset", "dataset_address"),
        Index("ix_backtest_computations_strategy", "strategy_key", "strategy_version"),
    )


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        UniqueConstraint("owner_id", "id", name="uq_backtest_runs_owner_id"),
        Index("ix_backtest_runs_owner_created", "owner_id", "created_at"),
        Index("ix_backtest_runs_owner_status", "owner_id", "status"),
        Index("ix_backtest_runs_owner_status_queued", "owner_id", "status", "queued_at"),
        Index("ix_backtest_runs_claim_expires", "claim_expires_at"),
        _admission_address_check("backtest_runs"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"),
        nullable=False, default=LEGACY_OWNER_ID, server_default=LEGACY_OWNER_ID,
        index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    # pending|running|done|error|cancelled.  A worker receives write authority
    # only through the short-lived token below; process-local state is advisory.
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    queued_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claim_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                server_default="0")
    requested_workers: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                                    server_default="1")
    cancel_requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # Validated request manifest used only to reconstruct abandoned work.  It
    # contains no provider object, credential, worker id, or secret.
    request_json: Mapped[str] = mapped_column(Text, default="", server_default="")
    scope: Mapped[str] = mapped_column(String(16), default="liquid")    # liquid|full
    intervals: Mapped[str] = mapped_column(String(128), default="")     # csv
    capital: Mapped[float] = mapped_column(Float, default=50_000.0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(400), default="")
    window: Mapped[str] = mapped_column(String(64), default="")          # lookback label: "1y" | "max" | "2024-01-01→2024-06-01"
    instruments: Mapped[str] = mapped_column(String(400), default="")    # csv of selected keys (empty = whole scope)
    strategies: Mapped[str] = mapped_column(String(400), default="")     # csv of strategy keys this run swept
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "created_at": self.created_at.isoformat(),
            "status": self.status, "scope": self.scope,
            "intervals": [i for i in self.intervals.split(",") if i],
            "capital": self.capital, "total": self.total, "done": self.done,
            "progress": round(100 * self.done / self.total, 1) if self.total else 0.0,
            "note": self.note,
            "window": self.window or "max",
            "instruments": [i for i in self.instruments.split(",") if i],
            "strategies": [s for s in self.strategies.split(",") if s] or ["trend_impulse_v3"],
            # Claim tokens and worker IDs deliberately do not leave the server:
            # they are write capability/topology details, not user-facing state.
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "heartbeat_at": self.heartbeat_at.isoformat() if self.heartbeat_at else None,
            "cancel_requested_at": (self.cancel_requested_at.isoformat()
                                    if self.cancel_requested_at else None),
            "attempt_count": self.attempt_count,
        }


class BacktestResult(Base):
    """One (instrument × interval) backtest result. Cached so reruns are instant."""
    __tablename__ = "backtest_results"
    __table_args__ = (
        UniqueConstraint("owner_id", "id", name="uq_backtest_results_owner_id"),
        # A durable sweep cell is an execution fact, not an append-only event.
        # Modern fenced writers always set this deterministic identity; nullable
        # preserves pre-0026/manual historical fixtures that predate resumability.
        Index("uq_backtest_results_owner_run_cell", "owner_id", "run_id", "cell_key",
              unique=True),
        ForeignKeyConstraint(("owner_id", "run_id"),
                             ("backtest_runs.owner_id", "backtest_runs.id"),
                             ondelete="RESTRICT", name="fk_backtest_results_owner_run"),
        Index("ix_backtest_results_owner_run", "owner_id", "run_id"),
        Index("ix_backtest_results_owner_cache", "owner_id", "params_hash", "last_candle_ts"),
        *_graph_attribution_table_args("backtest_results"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"),
        nullable=False, default=LEGACY_OWNER_ID, server_default=LEGACY_OWNER_ID,
        index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    cell_key: Mapped[str | None] = mapped_column(String(192), nullable=True)
    instrument_key: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    segment: Mapped[str] = mapped_column(String(12), default="")   # backtest charge segment
    strategy_key: Mapped[str] = mapped_column(String(64), default="trend_impulse_v3", index=True)
    interval: Mapped[str] = mapped_column(String(12), index=True)
    # Immutable strategy artifact used by the run-cell identity.  A key alone is
    # not enough: a generated key can be republished with different executable
    # bytes while an expired worker is being replaced.
    strategy_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    graph_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    attribution_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="NON_GRAPH", server_default="NON_GRAPH")
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    gross_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    charges: Mapped[float] = mapped_column(Float, default=0.0)
    expectancy: Mapped[float] = mapped_column(Float, default=0.0)
    cagr: Mapped[float | None] = mapped_column(Float, nullable=True)
    # smoothness / quality
    calmar: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency: Mapped[float | None] = mapped_column(Float, nullable=True)  # PER-TRADE hit consistency (not annualised)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)       # annualised Sharpe (cross-frequency comparable)
    max_consec_losses: Mapped[int] = mapped_column(Integer, default=0)
    time_underwater_pct: Mapped[float] = mapped_column(Float, default=0.0)
    worst_trade_pnl: Mapped[float] = mapped_column(Float, default=0.0)  # single worst net P&L (tail risk)
    worst_mae_pct: Mapped[float] = mapped_column(Float, default=0.0)    # worst intra-trade adverse excursion, %
    # honest sizing / affordability
    notional: Mapped[float] = mapped_column(Float, default=0.0)   # 1-lot underlying notional = base capital (entry × lot)
    lots: Mapped[int] = mapped_column(Integer, default=0)         # 1 for F&O (cash: shares); 0 = no trades
    affordable: Mapped[bool] = mapped_column(Boolean, default=True)  # back-compat; real flags computed at payload layer
    option_cost: Mapped[float] = mapped_column(Float, default=0.0)   # est. cost to buy 1 lot of an ATM option (BS), budget-independent
    # realised vs OPEN_AT_END
    open_at_end: Mapped[bool] = mapped_column(Boolean, default=False)
    win_rate_realised: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct_realised: Mapped[float] = mapped_column(Float, default=0.0)
    # benchmark
    bh_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # buy-and-hold over the same span, %
    # true per-(instrument,interval) coverage (honest span disclosure)
    first_ts: Mapped[int] = mapped_column(Integer, default=0)        # epoch of first candle in this cell
    last_ts: Mapped[int] = mapped_column(Integer, default=0)         # epoch of last candle in this cell
    effective_days: Mapped[int] = mapped_column(Integer, default=0)  # actual days covered (first→last)
    clamped: Mapped[bool] = mapped_column(Boolean, default=False)    # requested span exceeded Kite's ceiling
    bars: Mapped[int] = mapped_column(Integer, default=0)
    curve_json: Mapped[str] = mapped_column(Text, default="[]")     # equity curve
    bh_curve_json: Mapped[str] = mapped_column(Text, default="[]")  # buy-and-hold overlay
    trades_json: Mapped[str] = mapped_column(Text, default="[]")    # trade list (drill-down)
    error: Mapped[str] = mapped_column(String(400), default="")
    # synthetic-premium backtest (audit C6) — a Black-Scholes-on-realised-vol
    # premium path computed alongside the spot cell above. A premium-side bug
    # never kills the spot result: it lands in premium_error instead.
    premium_trades: Mapped[int] = mapped_column(Integer, default=0)
    premium_win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    premium_net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    premium_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    premium_profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    premium_max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    premium_expectancy: Mapped[float] = mapped_column(Float, default=0.0)
    premium_charges: Mapped[float] = mapped_column(Float, default=0.0)
    premium_trades_json: Mapped[str] = mapped_column(Text, default="[]")
    premium_error: Mapped[str] = mapped_column(String(200), default="")
    # reusable-cache metadata (content-addressed reuse across runs)
    params_hash: Mapped[str] = mapped_column(String(64), default="")
    last_candle_ts: Mapped[int] = mapped_column(Integer, default=0)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    computed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    def summary(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id,
            "instrument_key": self.instrument_key, "name": self.name,
            "segment": self.segment, "strategy_key": self.strategy_key or "trend_impulse_v3",
            "strategy_version": self.strategy_version,
            "graph_address": self.graph_address,
            "admission_address": self.admission_address,
            "attribution_state": self.attribution_state,
            "interval": self.interval,
            "trades": self.trades, "wins": self.wins,
            "win_rate": round(self.win_rate, 1),
            "profit_factor": round(self.profit_factor, 3) if self.profit_factor is not None else None,
            "max_drawdown_pct": round(self.max_drawdown_pct, 1),
            "return_pct": round(self.return_pct, 1),
            "net_pnl": round(self.net_pnl, 0),
            "gross_pnl": round(self.gross_pnl, 0),
            "charges": round(self.charges, 0),
            "expectancy": round(self.expectancy, 0),
            "cagr": round(self.cagr, 1) if self.cagr is not None else None,
            "calmar": round(self.calmar, 2) if self.calmar is not None else None,
            "consistency": round(self.consistency, 2) if self.consistency is not None else None,
            "sharpe": round(self.sharpe, 2) if self.sharpe is not None else None,
            "max_consec_losses": self.max_consec_losses,
            "time_underwater_pct": round(self.time_underwater_pct, 1),
            "worst_trade_pnl": round(self.worst_trade_pnl, 0),
            "worst_mae_pct": round(self.worst_mae_pct, 1),
            "notional": round(self.notional, 0),
            "option_cost": round(self.option_cost or 0.0, 0),
            "lots": self.lots,
            "affordable": bool(self.affordable),
            "open_at_end": bool(self.open_at_end),
            "win_rate_realised": round(self.win_rate_realised, 1),
            "return_pct_realised": round(self.return_pct_realised, 1),
            "bh_return_pct": round(self.bh_return_pct, 1) if self.bh_return_pct is not None else None,
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "effective_days": self.effective_days,
            "clamped": bool(self.clamped),
            "bars": self.bars,
            "from_cache": self.from_cache,
            "error": self.error,
            # synthetic-premium backtest (audit C6)
            "premium_trades": self.premium_trades,
            "premium_win_rate": round(self.premium_win_rate, 1),
            "premium_net_pnl": round(self.premium_net_pnl, 0),
            "premium_return_pct": round(self.premium_return_pct, 1),
            "premium_profit_factor": (round(self.premium_profit_factor, 3)
                                      if self.premium_profit_factor is not None else None),
            "premium_max_drawdown_pct": round(self.premium_max_drawdown_pct, 1),
            "premium_expectancy": round(self.premium_expectancy, 0),
            "premium_charges": round(self.premium_charges, 0),
            "premium_error": self.premium_error,
        }


class SignalEvent(Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        Index("ix_signal_events_owner_account", "owner_id", "broker_account_id"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    signal: Mapped[str] = mapped_column(String(16))        # LONG_ENTRY | SHORT_ENTRY
    z: Mapped[float] = mapped_column(Float, default=0.0)
    slope: Mapped[float] = mapped_column(Float, default=0.0)
    close: Mapped[float] = mapped_column(Float, default=0.0)
    acted: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(400), default="")

    def to_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "instrument_key": self.instrument_key,
            "signal": self.signal,
            "z": round(self.z, 3),
            "slope": round(self.slope, 3),
            "close": round(self.close, 2),
            "acted": self.acted,
            "note": self.note,
        }


class RuntimeConfig(Base):
    """Runtime parameter overrides (manual-override mode). Each row overrides one
    Settings field by name; absent keys fall back to the code default. Lets the
    owner retune reinforcement / overnight / trailing knobs without code edits."""
    __tablename__ = "runtime_config"
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))   # stringified; coerced to the field's type
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class Project(Base):
    """An organisational editor container; never an execution root."""
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status"),
        UniqueConstraint("owner_id", "name", name="uq_projects_owner_name"),
        UniqueConstraint("owner_id", "project_id", name="uq_projects_owner_project"),
    )

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="",
                                              server_default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                        server_default="active")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class OwnerProviderInstrumentSelection(Base):
    """Immutable USER metadata; DATA account/connection attribution is by value."""
    __tablename__ = "owner_provider_instrument_selections"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    selection_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    data_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    connection_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    reference_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["owner_id"], ["organizations.organization_id"],
                             name="fk_provider_selections_owner", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "data_account_id", "provider", "reference_fingerprint",
                         name="uq_provider_selections_descriptor"),
        CheckConstraint("length(owner_id) BETWEEN 1 AND 64", name="ck_provider_selections_owner"),
        CheckConstraint("length(data_account_id) BETWEEN 1 AND 64", name="ck_provider_selections_account"),
        CheckConstraint("connection_id > 0", name="ck_provider_selections_connection"),
        CheckConstraint("provider = 'ZERODHA'", name="ck_provider_selections_provider"),
        CheckConstraint(_ContentAddress("selection_address"), name="ck_provider_selections_address"),
        CheckConstraint(_ContentAddress("reference_fingerprint"), name="ck_provider_selections_fingerprint"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_provider_selections_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 8192), name="ck_provider_selections_size"),
    )


for _selection_action in ("UPDATE", "DELETE"):
    event.listen(OwnerProviderInstrumentSelection.__table__, "after_create", DDL(
        f"CREATE TRIGGER owner_provider_instrument_selections_refuse_{_selection_action.lower()} "
        f"BEFORE {_selection_action} ON owner_provider_instrument_selections BEGIN "
        "SELECT RAISE(ABORT, 'provider selections are immutable'); END"
    ).execute_if(dialect="sqlite"))
_install_postgresql_immutable_trigger(OwnerProviderInstrumentSelection.__table__,
                                      "provider selections are immutable")


class StaticInstrumentScope(Base):
    """Named research container; membership lives only in immutable revisions."""
    __tablename__ = "static_instrument_scopes"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "project_id"],
                             ["projects.owner_id", "projects.project_id"],
                             name="fk_static_scopes_project", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "project_id", "name", name="uq_static_scopes_name"),
        CheckConstraint("length(scope_id) BETWEEN 1 AND 64", name="ck_static_scopes_id"),
        CheckConstraint("length(name) BETWEEN 1 AND 128", name="ck_static_scopes_name"),
        CheckConstraint("revision > 0", name="ck_static_scopes_revision"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_static_scopes_status"),
    )
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class StaticInstrumentScopeRevision(Base):
    __tablename__ = "static_instrument_scope_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "project_id", "scope_id"],
            ["static_instrument_scopes.owner_id", "static_instrument_scopes.project_id",
             "static_instrument_scopes.scope_id"], name="fk_static_revisions_scope", ondelete="RESTRICT"),
        UniqueConstraint("address", name="uq_static_revisions_address"),
        UniqueConstraint("owner_id", "project_id", "scope_id", "address", name="uq_static_revisions_chain"),
        ForeignKeyConstraint(["owner_id", "project_id", "scope_id", "predecessor"],
            ["static_instrument_scope_revisions.owner_id", "static_instrument_scope_revisions.project_id",
             "static_instrument_scope_revisions.scope_id", "static_instrument_scope_revisions.address"],
            name="fk_static_revisions_predecessor"),
        CheckConstraint("revision > 0", name="ck_static_revisions_revision"),
        CheckConstraint("(revision = 1 AND predecessor IS NULL) OR (revision > 1 AND predecessor IS NOT NULL)",
                        name="ck_static_revisions_predecessor"),
        CheckConstraint(_ContentAddress("address"), name="ck_static_revisions_address"),
        CheckConstraint(_ContentAddress("membership_address"), name="ck_static_revisions_membership"),
        CheckConstraint(_NullableContentAddress("predecessor"), name="ck_static_revisions_predecessor_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_static_revisions_json"),
    )
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(String(71), nullable=False)
    membership_address: Mapped[str] = mapped_column(String(71), nullable=False)
    predecessor: Mapped[str | None] = mapped_column(String(71), nullable=True)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)


for _static_action in ("UPDATE", "DELETE"):
    event.listen(StaticInstrumentScopeRevision.__table__, "after_create", DDL(
        f"CREATE TRIGGER static_instrument_scope_revisions_refuse_{_static_action.lower()} "
        f"BEFORE {_static_action} ON static_instrument_scope_revisions BEGIN "
        "SELECT RAISE(ABORT, 'static scope revisions are immutable'); END"
    ).execute_if(dialect="sqlite"))
_install_postgresql_immutable_trigger(StaticInstrumentScopeRevision.__table__,
                                      "static scope revisions are immutable")


class WatchlistMonitoringRevision(Base):
    """Immutable per-member monitoring choices, separate from executable identity."""
    __tablename__ = "watchlist_monitoring_revisions"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    address: Mapped[str] = mapped_column(String(71), nullable=False)
    predecessor_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    monitoring_intent: Mapped[str] = mapped_column(String(8), nullable=False)
    assignment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "project_id", "scope_id"],
            ["static_instrument_scopes.owner_id", "static_instrument_scopes.project_id", "static_instrument_scopes.scope_id"],
            name="fk_watchlist_monitoring_scope", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_watchlist_monitoring_creator", ondelete="RESTRICT"),
        ForeignKeyConstraint(["owner_id", "assignment_id"],
            ["monitoring_assignments.owner_id", "monitoring_assignments.assignment_id"],
            name="fk_watchlist_monitoring_assignment", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "request_id", name="uq_watchlist_monitoring_request"),
        UniqueConstraint("owner_id", "project_id", "scope_id", "member_key", "address", name="uq_watchlist_monitoring_chain"),
        ForeignKeyConstraint(["owner_id", "project_id", "scope_id", "member_key", "predecessor_address"],
            ["watchlist_monitoring_revisions.owner_id", "watchlist_monitoring_revisions.project_id",
             "watchlist_monitoring_revisions.scope_id", "watchlist_monitoring_revisions.member_key",
             "watchlist_monitoring_revisions.address"], name="fk_watchlist_monitoring_predecessor", ondelete="RESTRICT"),
        CheckConstraint("revision > 0", name="ck_watchlist_monitoring_revision"),
        CheckConstraint("length(member_key) BETWEEN 1 AND 128", name="ck_watchlist_monitoring_member"),
        CheckConstraint("length(request_id) = 36", name="ck_watchlist_monitoring_request"),
        CheckConstraint("(revision = 1 AND predecessor_address IS NULL) OR (revision > 1 AND predecessor_address IS NOT NULL)",
                        name="ck_watchlist_monitoring_predecessor"),
        CheckConstraint("monitoring_intent IN ('MONITOR', 'PAUSE')", name="ck_watchlist_monitoring_intent"),
        CheckConstraint(_ContentAddress("address"), name="ck_watchlist_monitoring_address"),
        CheckConstraint(_NullableContentAddress("predecessor_address"), name="ck_watchlist_monitoring_predecessor_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_watchlist_monitoring_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_watchlist_monitoring_size"),
        *(CheckConstraint(_JsonTextMatchesColumn("canonical_json", key, key), name="ck_watchlist_monitoring_copy_" + key)
          for key in ("address", "owner_id", "project_id", "scope_id", "member_key", "monitoring_intent")),
        CheckConstraint(_JsonNumberEquals("canonical_json", "revision", "revision"), name="ck_watchlist_monitoring_copy_revision"),
    )


for _watchlist_monitoring_action in ("UPDATE", "DELETE"):
    event.listen(WatchlistMonitoringRevision.__table__, "after_create", DDL(
        f"CREATE TRIGGER watchlist_monitoring_revisions_refuse_{_watchlist_monitoring_action.lower()} "
        f"BEFORE {_watchlist_monitoring_action} ON watchlist_monitoring_revisions BEGIN "
        "SELECT RAISE(ABORT, 'watchlist monitoring revisions are immutable'); END"
    ).execute_if(dialect="sqlite"))
_install_postgresql_immutable_trigger(WatchlistMonitoringRevision.__table__,
                                      "watchlist monitoring revisions are immutable")


class GraphArtifact(Base):
    """One stable graph lineage with an optimistic-concurrency working draft."""
    __tablename__ = "graph_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "project_id"],
            ["projects.owner_id", "projects.project_id"],
            ondelete="RESTRICT",
            name="fk_graph_artifacts_owner_project",
        ),
        CheckConstraint("draft_revision >= 0", name="ck_graph_artifacts_draft_revision"),
        CheckConstraint(
            "published_revision IS NULL OR "
            "(published_revision >= 0 AND published_revision <= draft_revision)",
            name="ck_graph_artifacts_published_revision",
        ),
        CheckConstraint(
            "(current_version IS NULL) = (published_revision IS NULL)",
            name="ck_graph_artifacts_publication_state",
        ),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_json: Mapped[str] = mapped_column(Text, nullable=False)
    draft_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class GraphVersion(Base):
    """An append-only executable IR artefact."""
    __tablename__ = "graph_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "graph_identifier"],
            ["graph_artifacts.owner_id", "graph_artifacts.identifier"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("version >= 1", name="ck_graph_versions_version"),
        CheckConstraint(_JsonIsValid("artifact_json"), name="ck_graph_versions_valid_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "identifier", "graph_identifier"),
                        name="ck_graph_versions_identifier_matches_json"),
        CheckConstraint(_JsonNumberEquals("artifact_json", "version", "version"),
                        name="ck_graph_versions_version_matches_json"),
        CheckConstraint("visibility = 'PRIVATE'", name="ck_graph_versions_private_visibility"),
        Index("ix_graph_versions_content_address", "content_address"),
        _admission_address_check("graph_versions"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PRIVATE", server_default="PRIVATE")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class IrV2GraphVersion(Base):
    """An owner-scoped immutable Component IR v2 graph fact.

    This is deliberately separate from legacy ``GraphVersion`` and grants no
    runtime or execution authority.
    """
    __tablename__ = "ir_v2_graph_versions"
    __table_args__ = (
        CheckConstraint("graph_version >= 1", name="ck_ir_v2_graph_versions_version"),
        CheckConstraint("format_version = 2", name="ck_ir_v2_graph_versions_format"),
        CheckConstraint(_JsonIsValid("artifact_json"),
                        name="ck_ir_v2_graph_versions_valid_json"),
        CheckConstraint(_JsonTextMatchesColumn(
            "artifact_json", "strategy_id", "graph_identifier"),
            name="ck_ir_v2_graph_versions_identifier_matches_json"),
        CheckConstraint(_JsonNumberEquals(
            "artifact_json", "strategy_version", "graph_version"),
            name="ck_ir_v2_graph_versions_version_matches_json"),
        CheckConstraint(_ContentAddress("content_address"),
                        name="ck_ir_v2_graph_versions_content_address"),
        CheckConstraint(_ContentAddress("graph_address"),
                        name="ck_ir_v2_graph_versions_graph_address"),
        CheckConstraint(_ContentAddress("registry_snapshot_address"),
                        name="ck_ir_v2_graph_versions_registry_address"),
        Index("ix_ir_v2_graph_versions_content_address", "content_address"),
        Index("ix_ir_v2_graph_versions_graph_address", "graph_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    format_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default=text("2"))
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    registry_snapshot_address: Mapped[str] = mapped_column(String(71), nullable=False)
    publication_receipt_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class IrV2EditorPresentation(Base):
    """Owner-scoped v2 canvas state, excluded from executable identity."""
    __tablename__ = "ir_v2_editor_presentations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "graph_identifier"],
            ["graph_artifacts.owner_id", "graph_artifacts.identifier"],
            ondelete="RESTRICT",
            name="fk_ir_v2_editor_presentations_graph",
        ),
        CheckConstraint("format_version = 2", name="ck_ir_v2_editor_presentations_format"),
        CheckConstraint("revision >= 0", name="ck_ir_v2_editor_presentations_revision"),
        CheckConstraint(_JsonIsValid("presentation_json"),
                        name="ck_ir_v2_editor_presentations_valid_json"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    format_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default=text("2"))
    presentation_json: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class ChartContextAnnotation(Base):
    """Private research-only drawing state; never part of executable identity."""
    __tablename__ = "chart_context_annotations"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id"], ["organizations.organization_id"],
                             ondelete="CASCADE", name="fk_chart_context_annotations_owner"),
        CheckConstraint(_ContentAddress("market_context_address"),
                        name="ck_chart_context_annotations_context_address"),
        CheckConstraint(_ContentAddress("dataset_manifest_address"),
                        name="ck_chart_context_annotations_dataset_address"),
        CheckConstraint(_ContentAddress("canonical_instrument_address"),
                        name="ck_chart_context_annotations_instrument_address"),
        CheckConstraint(_ContentAddress("geometry_address"),
                        name="ck_chart_context_annotations_geometry_address"),
        CheckConstraint(_ContentAddress("applicability_address"),
                        name="ck_chart_context_annotations_applicability_address"),
        CheckConstraint(_JsonIsValid("geometry_json"),
                        name="ck_chart_context_annotations_geometry_json"),
        CheckConstraint(_JsonIsValid("applicability_json"),
                        name="ck_chart_context_annotations_applicability_json"),
        CheckConstraint(_Utf8SizeAtMost("geometry_json", 65536),
                        name="ck_chart_context_annotations_geometry_size"),
        CheckConstraint(_Utf8SizeAtMost("applicability_json", 65536),
                        name="ck_chart_context_annotations_applicability_size"),
        CheckConstraint("revision >= 1", name="ck_chart_context_annotations_revision"),
        CheckConstraint("timeframe_seconds > 0", name="ck_chart_context_annotations_timeframe"),
        Index("ix_chart_context_annotations_owner_context_updated", "owner_id",
              "market_context_address", "updated_at"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_context_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    annotation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_manifest_address: Mapped[str] = mapped_column(String(71), nullable=False)
    canonical_instrument_address: Mapped[str] = mapped_column(String(71), nullable=False)
    timeframe_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_address: Mapped[str] = mapped_column(String(71), nullable=False)
    geometry_json: Mapped[str] = mapped_column(Text, nullable=False)
    applicability_address: Mapped[str] = mapped_column(String(71), nullable=False)
    applicability_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                     default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                     default=dt.datetime.now)


class StrategyAdmission(Base):
    """One owner-scoped, append-only causal-admission receipt.

    This records only the proof that a graph passed Phase 3 causal admission.  It
    is deliberately not Strategy Preflight and grants no provider, deployment, or
    execution authority by itself.
    """
    __tablename__ = "strategy_admissions"
    __table_args__ = (
        CheckConstraint(_ContentAddress("admission_address"),
                        name="ck_strategy_admissions_address_format"),
        CheckConstraint(_ContentAddress("graph_address"),
                        name="ck_strategy_admissions_graph_address_format"),
        CheckConstraint("graph_version >= 1", name="ck_strategy_admissions_graph_version"),
        CheckConstraint(_JsonIsValid("artifact_json"),
                        name="ck_strategy_admissions_valid_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "owner_id", "owner_id"),
                        name="ck_strategy_admissions_owner_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn(
            "artifact_json", "graph_identifier", "graph_identifier"),
            name="ck_strategy_admissions_graph_identifier_matches_json"),
        CheckConstraint(_JsonNumberEquals("artifact_json", "graph_version", "graph_version"),
                        name="ck_strategy_admissions_graph_version_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "graph_address", "graph_address"),
                        name="ck_strategy_admissions_graph_address_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "scheme", "scheme"),
                        name="ck_strategy_admissions_scheme_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "contract_suite", "contract_suite"),
                        name="ck_strategy_admissions_contract_suite_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "parity_suite", "parity_suite"),
                        name="ck_strategy_admissions_parity_suite_matches_json"),
        UniqueConstraint("owner_id", "graph_identifier", "graph_version", "admission_address",
                         name="uq_strategy_admissions_owner_graph_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admission_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_suite: Mapped[str] = mapped_column(String(32), nullable=False)
    parity_suite: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)
    # NULL is deliberate for admitted v1 rows: no legacy receipt is inferred.
    # These are last so fresh-model DDL matches additive migration column order.
    format_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_address: Mapped[str | None] = mapped_column(String(71), nullable=True)


# Phase 4 reference facts are deliberately separate from provider connections and
# execution records.  They contain no credentials and are append-only by schema.
class MarketTruthInstrument(Base):
    __tablename__ = "market_truth_instruments"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    identity_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    authority_state: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'LEGACY_UNVERIFIED'"))
    __table_args__ = (CheckConstraint(_ContentAddress("address"), name="ck_market_truth_instruments_address"),
                      CheckConstraint(_JsonIsValid("identity_json"), name="ck_market_truth_instruments_json"))


class MarketTruthProviderMapping(Base):
    __tablename__ = "market_truth_provider_mappings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_address: Mapped[str] = mapped_column(String(71), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_token: Mapped[str] = mapped_column(String(256), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    authority_state: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'LEGACY_UNVERIFIED'"))
    __table_args__ = (ForeignKeyConstraint(["instrument_address"], ["market_truth_instruments.address"]),
                      CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_market_truth_mapping_interval"),
                      UniqueConstraint("provider", "provider_token", "effective_from", name="uq_market_truth_provider_token_from"))


class MarketTruthSnapshotRecord(Base):
    __tablename__ = "market_truth_snapshots"
    digest: Mapped[str] = mapped_column(String(71), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    authority_state: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'LEGACY_UNVERIFIED'"))
    __table_args__ = (CheckConstraint(_ContentAddress("digest"), name="ck_market_truth_snapshots_digest"),
                      CheckConstraint(_JsonIsValid("payload_json"), name="ck_market_truth_snapshots_json"),
                      CheckConstraint("quality IN ('OBSERVED','RECONSTRUCTED','UNKNOWN')", name="ck_market_truth_snapshots_quality"))


def _assert_market_truth_content_address(values: dict, *, json_field: str, digest_field: str) -> None:
    """Reject non-canonical or wrongly addressed reference facts before SQL execution."""
    from app.ir.hashing import canonical_json, content_address

    payload = values.get(json_field)
    digest = values.get(digest_field)
    if payload is None or digest is None:
        return
    try:
        document = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{json_field} must be valid canonical JSON") from exc
    if canonical_json(document) != payload or content_address(document) != digest:
        raise ValueError(f"{digest_field} does not match {json_field}")


def _insert_rows_with_inline_values(clauseelement, multiparams, params) -> list[dict]:
    """Normalize controlled SQLAlchemy Core INSERT values, including ``.values``."""
    normalize = lambda values: {
        getattr(column, "key", column): getattr(value, "value", value)
        for column, value in values.items()
    }
    multi_values = [
        normalize(row)
        for group in (getattr(clauseelement, "_multi_values", None) or ())
        for row in group
    ]
    inline = {
        getattr(column, "key", column): getattr(value, "value", value)
        for column, value in (getattr(clauseelement, "_values", None) or {}).items()
    }
    supplied = multiparams or ([params] if params else [])
    if multi_values:
        return multi_values
    if supplied:
        return [{**inline, **dict(row)} for row in supplied]
    return [inline] if inline else []


def _assert_capability_content_address(values: dict) -> None:
    from app.ir.hashing import content_address

    document = _canonical_secret_free_capability(values["capability_json"])
    if content_address(document) != values["digest"]:
        raise ValueError("capability digest does not match capability_json")


@event.listens_for(Engine, "before_execute", retval=True)
def _market_truth_core_identity_guard(connection, clauseelement, multiparams, params, execution_options):
    """Guard controlled SQLAlchemy Core inserts, including inline ``.values``.

    Raw driver SQL is deliberately outside this application persistence boundary.
    """
    if not isinstance(clauseelement, Insert):
        return clauseelement, multiparams, params
    fields = {
        "market_truth_instruments": ("identity_json", "address"),
        "market_truth_snapshots": ("payload_json", "digest"),
        "authority_canonical_instruments": ("canonical_json", "address"),
        "authority_provider_entities": ("canonical_json", "address"),
        "authority_provider_products": ("canonical_json", "address"),
        "authority_provider_contracts": ("canonical_json", "address"),
        "authority_provider_aliases": ("canonical_json", "address"),
        "authority_raw_segments": ("canonical_json", "address"),
        "authority_provider_observations": ("canonical_json", "address"),
        "authority_normalized_observations": ("canonical_json", "address"),
    }.get(clauseelement.table.name)
    capability = clauseelement.table.name == "market_data_capability_profiles"
    if fields is None and not capability:
        return clauseelement, multiparams, params
    rows = _insert_rows_with_inline_values(clauseelement, multiparams, params)
    for row in rows:
        if fields is not None:
            _assert_market_truth_content_address(row, json_field=fields[0], digest_field=fields[1])
        else:
            _assert_capability_content_address(row)
    return clauseelement, multiparams, params


@event.listens_for(MarketTruthInstrument, "before_insert")
def _instrument_identity_matches_json(_mapper, _connection, target) -> None:
    _assert_market_truth_content_address(target.__dict__, json_field="identity_json", digest_field="address")


@event.listens_for(MarketTruthSnapshotRecord, "before_insert")
def _snapshot_identity_matches_json(_mapper, _connection, target) -> None:
    _assert_market_truth_content_address(target.__dict__, json_field="payload_json", digest_field="digest")


class MarketDataCapabilityProfile(Base):
    __tablename__ = "market_data_capability_profiles"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    digest: Mapped[str] = mapped_column(String(71), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    authority_state: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'LEGACY_UNVERIFIED'"))
    __table_args__ = (CheckConstraint(_ContentAddress("digest"), name="ck_market_data_capability_digest"),
                      CheckConstraint(_JsonIsValid("capability_json"), name="ck_market_data_capability_json"),
                      CheckConstraint(_SecretFreeJson("capability_json"), name="ck_market_data_capability_no_secret"))


def _authority_fact_constraints(prefix: str):
    return (
        CheckConstraint(_ContentAddress("address"), name=f"ck_{prefix}_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name=f"ck_{prefix}_json"),
        CheckConstraint("authority_state = 'VERIFIED_V2'", name=f"ck_{prefix}_verified"),
    )


class AuthorityCanonicalInstrument(Base):
    __tablename__ = "authority_canonical_instruments"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    venue_code: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    economic_underlier_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["economic_underlier_address"],
                             ["authority_canonical_instruments.address"]),
        *_authority_fact_constraints("authority_canonical_instruments"),
    )


class AuthorityProviderEntity(Base):
    __tablename__ = "authority_provider_entities"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    entity_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = _authority_fact_constraints("authority_provider_entities")


class AuthorityProviderProduct(Base):
    __tablename__ = "authority_provider_products"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    entity_address: Mapped[str] = mapped_column(String(71), nullable=False)
    product_code: Mapped[str] = mapped_column(String(128), nullable=False)
    observation_namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["entity_address"], ["authority_provider_entities.address"]),
        UniqueConstraint("entity_address", "product_code", name="uq_authority_provider_product"),
        UniqueConstraint("entity_address", "observation_namespace",
                         name="uq_authority_provider_namespace"),
        *_authority_fact_constraints("authority_provider_products"),
    )


class AuthorityProviderContract(Base):
    __tablename__ = "authority_provider_contracts"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from",
                        name="ck_authority_provider_contract_interval"),
        UniqueConstraint("owner_id", "product_address", "mode", "effective_from",
                         name="uq_authority_provider_contract_scope"),
        *_authority_fact_constraints("authority_provider_contracts"),
    )


class AuthorityProviderAlias(Base):
    __tablename__ = "authority_provider_aliases"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    instrument_address: Mapped[str] = mapped_column(String(71), nullable=False)
    provider_token: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(256), nullable=False)
    observation_namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    provider_contract_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    receipt_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        ForeignKeyConstraint(["instrument_address"], ["authority_canonical_instruments.address"]),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from",
                        name="ck_authority_provider_alias_interval"),
        ForeignKeyConstraint(["provider_contract_address"], ["authority_provider_contracts.address"]),
        ForeignKeyConstraint(["receipt_address"], ["authority_raw_segments.address"]),
        CheckConstraint(
            "(schema = 'provider-instrument-mapping/1' AND provider_contract_address IS NULL "
            "AND receipt_address IS NULL) OR (schema = 'provider-instrument-mapping/2' "
            "AND provider_contract_address IS NOT NULL AND receipt_address IS NOT NULL "
            "AND effective_to IS NOT NULL)", name="ck_authority_provider_alias_scope"),
        Index("uq_authority_provider_alias_token", "product_address", "observation_namespace",
              "provider_token", "effective_from", unique=True,
              sqlite_where=text("schema = 'provider-instrument-mapping/1'"),
              postgresql_where=text("schema = 'provider-instrument-mapping/1'")),
        UniqueConstraint("provider_contract_address", "receipt_address",
                         name="uq_authority_provider_alias_response"),
        *_authority_fact_constraints("authority_provider_aliases"),
    )


class AuthorityRawSegment(Base):
    __tablename__ = "authority_raw_segments"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    contract_address: Mapped[str] = mapped_column(String(71), nullable=False)
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        ForeignKeyConstraint(["contract_address"], ["authority_provider_contracts.address"]),
        CheckConstraint(_LowerHexDigest("byte_digest"), name="ck_authority_raw_segments_digest"),
        CheckConstraint("byte_length > 0", name="ck_authority_raw_segments_length"),
        *_authority_fact_constraints("authority_raw_segments"),
    )


class AuthorityProviderObservation(Base):
    __tablename__ = "authority_provider_observations"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_address: Mapped[str] = mapped_column(String(71), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    contract_address: Mapped[str] = mapped_column(String(71), nullable=False)
    mapping_address: Mapped[str] = mapped_column(String(71), nullable=False)
    raw_segment_address: Mapped[str] = mapped_column(String(71), nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    available_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    correction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    supersedes_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["entity_address"], ["authority_provider_entities.address"]),
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        ForeignKeyConstraint(["contract_address"], ["authority_provider_contracts.address"]),
        ForeignKeyConstraint(["mapping_address"], ["authority_provider_aliases.address"]),
        ForeignKeyConstraint(["raw_segment_address"], ["authority_raw_segments.address"]),
        ForeignKeyConstraint(["supersedes_address"], ["authority_provider_observations.address"]),
        CheckConstraint("resolution_seconds > 0", name="ck_authority_provider_observation_resolution"),
        UniqueConstraint("owner_id", "product_address", "correction_id",
                         name="uq_authority_provider_observation_correction"),
        *_authority_fact_constraints("authority_provider_observations"),
    )


class AuthorityNormalizedObservation(Base):
    __tablename__ = "authority_normalized_observations"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_address: Mapped[str] = mapped_column(String(71), nullable=False)
    market_truth_address: Mapped[str] = mapped_column(String(71), nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    available_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["instrument_address"], ["authority_canonical_instruments.address"]),
        CheckConstraint("resolution_seconds > 0", name="ck_authority_normalized_observation_resolution"),
        *_authority_fact_constraints("authority_normalized_observations"),
    )


class AuthorityNormalizedObservationInput(Base):
    __tablename__ = "authority_normalized_observation_inputs"
    normalized_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_observation_address: Mapped[str] = mapped_column(String(71), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["normalized_address"], ["authority_normalized_observations.address"]),
        ForeignKeyConstraint(["provider_observation_address"],
                             ["authority_provider_observations.address"]),
        CheckConstraint("ordinal >= 0", name="ck_authority_normalized_input_ordinal"),
        UniqueConstraint("normalized_address", "provider_observation_address",
                         name="uq_authority_normalized_input"),
    )


class AuthorityMarketTruthSnapshot(Base):
    """Storage shape only; typed authority is owned by the next capsule."""
    __tablename__ = "authority_market_truth_snapshots"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    authority_scope: Mapped[str] = mapped_column(String(128), nullable=False)
    quality: Mapped[str] = mapped_column(String(24), nullable=False)
    knowledge_cutoff: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    effective_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'LEGACY_UNVERIFIED'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        CheckConstraint("authority_state IN ('LEGACY_UNVERIFIED','VERIFIED_V2')",
                        name="ck_authority_truth_state"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from",
                        name="ck_authority_truth_interval"),
        CheckConstraint(_ContentAddress("address"), name="ck_authority_truth_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_authority_truth_json"),
    )


class AuthorityProviderConformance(Base):
    __tablename__ = "authority_provider_conformance"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    observed_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    observed_to: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'LEGACY_UNVERIFIED'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        CheckConstraint("authority_state IN ('LEGACY_UNVERIFIED','VERIFIED_V2')",
                        name="ck_authority_conformance_state"),
        CheckConstraint("observed_to > observed_from", name="ck_authority_conformance_interval"),
        CheckConstraint(_ContentAddress("address"), name="ck_authority_conformance_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_authority_conformance_json"),
    )


class AuthorityCapabilityProfile(Base):
    __tablename__ = "authority_capability_profiles"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    product_address: Mapped[str] = mapped_column(String(71), nullable=False)
    contract_address: Mapped[str] = mapped_column(String(71), nullable=False)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'LEGACY_UNVERIFIED'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        ForeignKeyConstraint(["contract_address"], ["authority_provider_contracts.address"]),
        CheckConstraint("authority_state IN ('LEGACY_UNVERIFIED','VERIFIED_V2')",
                        name="ck_authority_profile_state"),
        CheckConstraint("expires_at > observed_at", name="ck_authority_profile_interval"),
        CheckConstraint(_ContentAddress("address"), name="ck_authority_profile_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_authority_profile_json"),
    )


class AuthorityCapabilityAssessment(Base):
    __tablename__ = "authority_capability_assessments"
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_address: Mapped[str] = mapped_column(String(71), nullable=False)
    dataset_address: Mapped[str] = mapped_column(String(71), nullable=False)
    truth_address: Mapped[str] = mapped_column(String(71), nullable=False)
    assessed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'LEGACY_UNVERIFIED'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(["profile_address"], ["authority_capability_profiles.address"]),
        CheckConstraint("authority_state IN ('LEGACY_UNVERIFIED','VERIFIED_V2')",
                        name="ck_authority_assessment_state"),
        CheckConstraint(_ContentAddress("address"), name="ck_authority_assessment_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_authority_assessment_json"),
    )


def _dataset_authority_constraints(prefix: str):
    return (
        CheckConstraint(_ContentAddress("address"), name=f"ck_{prefix}_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name=f"ck_{prefix}_json"),
        CheckConstraint(_JsonIsValid("dependency_addresses_json"),
                        name=f"ck_{prefix}_dependencies_json"),
        CheckConstraint("authority_state = 'VERIFIED_V2'", name=f"ck_{prefix}_verified"),
    )


class _DatasetAuthorityColumns:
    """Copied authority columns shared by nine physically separate typed tables."""
    address: Mapped[str] = mapped_column(String(71), primary_key=True)
    schema: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    dependency_addresses_json: Mapped[str] = mapped_column(Text, nullable=False)
    role_value: Mapped[str] = mapped_column(String(256), nullable=False)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(24), nullable=False,
                                                 server_default=text("'VERIFIED_V2'"))


class AuthorityRawSchema(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_raw_schemas"
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        ForeignKeyConstraint(["contract_address"], ["authority_provider_contracts.address"]),
        *_dataset_authority_constraints("authority_raw_schemas"),
    )


class AuthorityNormalizationTransform(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_normalization_transforms"
    __table_args__ = _dataset_authority_constraints("authority_normalization_transforms")


class AuthorityAlignmentPolicy(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_alignment_policies"
    __table_args__ = _dataset_authority_constraints("authority_alignment_policies")


class AuthorityMissingDataPolicy(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_missing_data_policies"
    __table_args__ = _dataset_authority_constraints("authority_missing_data_policies")


class AuthorityAdjustmentPolicy(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_adjustment_policies"
    __table_args__ = _dataset_authority_constraints("authority_adjustment_policies")


class AuthorityRollPolicy(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_roll_policies"
    __table_args__ = _dataset_authority_constraints("authority_roll_policies")


class AuthorityDatasetCreationEvidence(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_dataset_creation_evidence"
    __table_args__ = _dataset_authority_constraints("authority_dataset_creation_evidence")


class AuthorityDeterministicAlgorithm(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_deterministic_algorithms"
    __table_args__ = _dataset_authority_constraints("authority_deterministic_algorithms")


class AuthorityDatasetCorrection(_DatasetAuthorityColumns, Base):
    __tablename__ = "authority_dataset_corrections"
    __table_args__ = (
        ForeignKeyConstraint(["product_address"], ["authority_provider_products.address"]),
        ForeignKeyConstraint(["contract_address"], ["authority_provider_contracts.address"]),
        UniqueConstraint("owner_id", "product_address", "contract_address", "role_value",
                         name="uq_authority_dataset_correction_sequence"),
        *_dataset_authority_constraints("authority_dataset_corrections"),
    )


def _canonical_secret_free_capability(value: str) -> dict:
    from app.ir.hashing import canonical_json

    try:
        document = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("capability_json must be valid canonical JSON") from exc
    if not isinstance(document, dict) or canonical_json(document) != value:
        raise ValueError("capability_json must be canonical JSON object bytes")

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if any(part in key.lower() for part in ("token", "secret", "password", "api_key", "credential", "authorization")):
                    raise ValueError("capability_json must not contain credential-bearing keys")
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(document)
    return document


@event.listens_for(MarketDataCapabilityProfile, "before_insert")
def _capability_identity_matches_json(_mapper, _connection, target) -> None:
    from app.ir.hashing import content_address

    if content_address(_canonical_secret_free_capability(target.capability_json)) != target.digest:
        raise ValueError("capability digest does not match capability_json")


_PHASE4_SECRET_FUNCTION = """
CREATE OR REPLACE FUNCTION phase4_json_has_secret_key(payload jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    WITH RECURSIVE nodes(value) AS (
        SELECT payload
        UNION ALL
        SELECT child.value FROM nodes CROSS JOIN LATERAL (
            SELECT value FROM jsonb_each(CASE WHEN jsonb_typeof(nodes.value) = 'object' THEN nodes.value ELSE '{}'::jsonb END)
            UNION ALL
            SELECT value FROM jsonb_array_elements(CASE WHEN jsonb_typeof(nodes.value) = 'array' THEN nodes.value ELSE '[]'::jsonb END)
        ) AS child
    )
    SELECT EXISTS (
        SELECT 1 FROM nodes CROSS JOIN LATERAL jsonb_object_keys(CASE WHEN jsonb_typeof(nodes.value) = 'object' THEN nodes.value ELSE '{}'::jsonb END) AS key
        WHERE (
            lower(key) LIKE '%%token%%' OR lower(key) LIKE '%%secret%%' OR
            lower(key) LIKE '%%password%%' OR lower(key) LIKE '%%api_key%%' OR
            lower(key) LIKE '%%credential%%' OR lower(key) LIKE '%%authorization%%'
        )
    )
$$
"""

event.listen(MarketDataCapabilityProfile.__table__, "before_create", DDL(_PHASE4_SECRET_FUNCTION).execute_if(dialect="postgresql"))
event.listen(MarketDataCapabilityProfile.__table__, "after_create", DDL("""
    CREATE TRIGGER market_data_capability_profiles_refuse_secret_key
    BEFORE INSERT ON market_data_capability_profiles
    WHEN EXISTS (SELECT 1 FROM json_tree(NEW.capability_json) WHERE key IS NOT NULL AND (
        lower(key) LIKE '%%token%%' OR lower(key) LIKE '%%secret%%' OR lower(key) LIKE '%%password%%' OR
        lower(key) LIKE '%%api_key%%' OR lower(key) LIKE '%%credential%%' OR lower(key) LIKE '%%authorization%%'
    ))
    BEGIN SELECT RAISE(ABORT, 'market_data_capability_profiles contains credential-bearing key'); END
""").execute_if(dialect="sqlite"))


def _make_phase4_reference_immutable(table) -> None:
    """Reference facts are append-only in both supported database dialects."""
    for operation in ("UPDATE", "DELETE"):
        trigger = f"{table.name}_refuse_{operation.lower()}"
        event.listen(
            table,
            "after_create",
            DDL(
                f"CREATE TRIGGER {trigger} BEFORE {operation} ON {table.name} "
                f"BEGIN SELECT RAISE(ABORT, '{table.name} is immutable'); END"
            ).execute_if(dialect="sqlite"),
        )
    _install_postgresql_immutable_trigger(table, f"{table.name} is immutable")


for _phase4_reference_table in (
    MarketTruthInstrument.__table__,
    MarketTruthProviderMapping.__table__,
    MarketTruthSnapshotRecord.__table__,
    MarketDataCapabilityProfile.__table__,
    AuthorityCanonicalInstrument.__table__,
    AuthorityProviderEntity.__table__,
    AuthorityProviderProduct.__table__,
    AuthorityProviderContract.__table__,
    AuthorityProviderAlias.__table__,
    AuthorityRawSegment.__table__,
    AuthorityProviderObservation.__table__,
    AuthorityNormalizedObservation.__table__,
    AuthorityNormalizedObservationInput.__table__,
    AuthorityMarketTruthSnapshot.__table__,
    AuthorityProviderConformance.__table__,
    AuthorityCapabilityProfile.__table__,
    AuthorityCapabilityAssessment.__table__,
    AuthorityRawSchema.__table__,
    AuthorityNormalizationTransform.__table__,
    AuthorityAlignmentPolicy.__table__,
    AuthorityMissingDataPolicy.__table__,
    AuthorityAdjustmentPolicy.__table__,
    AuthorityRollPolicy.__table__,
    AuthorityDatasetCorrection.__table__,
    AuthorityDatasetCreationEvidence.__table__,
    AuthorityDeterministicAlgorithm.__table__,
):
    _make_phase4_reference_immutable(_phase4_reference_table)


for _authority_fact_model in (
    AuthorityCanonicalInstrument, AuthorityProviderEntity, AuthorityProviderProduct,
    AuthorityProviderContract, AuthorityProviderAlias, AuthorityRawSegment,
    AuthorityProviderObservation, AuthorityNormalizedObservation,
    AuthorityRawSchema, AuthorityNormalizationTransform, AuthorityAlignmentPolicy,
    AuthorityMissingDataPolicy, AuthorityAdjustmentPolicy, AuthorityRollPolicy,
    AuthorityDatasetCorrection, AuthorityDatasetCreationEvidence,
    AuthorityDeterministicAlgorithm,
):
    event.listen(
        _authority_fact_model,
        "before_insert",
        lambda _mapper, _connection, target: _assert_market_truth_content_address(
            target.__dict__, json_field="canonical_json", digest_field="address"),
    )


event.listen(
    AuthorityProviderAlias.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER authority_provider_aliases_refuse_overlap "
        "BEFORE INSERT ON authority_provider_aliases BEGIN "
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM authority_provider_aliases AS existing "
        "WHERE NEW.schema = 'provider-instrument-mapping/1' "
        "AND existing.schema = 'provider-instrument-mapping/1' "
        "AND existing.product_address = NEW.product_address "
        "AND existing.observation_namespace = NEW.observation_namespace "
        "AND (existing.provider_token = NEW.provider_token "
        "OR existing.provider_symbol = NEW.provider_symbol "
        "OR existing.instrument_address = NEW.instrument_address) "
        "AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) "
        "AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) "
        "THEN RAISE(ABORT, 'authority provider alias overlaps') END; END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    AuthorityProviderAlias.__table__,
    "after_create",
    DDL(
        "CREATE OR REPLACE FUNCTION authority_provider_aliases_refuse_overlap() "
        "RETURNS trigger AS $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM authority_provider_aliases AS existing "
        "WHERE NEW.schema = 'provider-instrument-mapping/1' "
        "AND existing.schema = 'provider-instrument-mapping/1' "
        "AND existing.product_address = NEW.product_address "
        "AND existing.observation_namespace = NEW.observation_namespace "
        "AND (existing.provider_token = NEW.provider_token "
        "OR existing.provider_symbol = NEW.provider_symbol "
        "OR existing.instrument_address = NEW.instrument_address) "
        "AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) "
        "AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) "
        "THEN RAISE EXCEPTION 'authority provider alias overlaps'; END IF; "
        "RETURN NEW; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"),
)
event.listen(
    AuthorityProviderAlias.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER authority_provider_aliases_refuse_overlap "
        "BEFORE INSERT ON authority_provider_aliases FOR EACH ROW "
        "EXECUTE FUNCTION authority_provider_aliases_refuse_overlap()"
    ).execute_if(dialect="postgresql"),
)


event.listen(
    MarketTruthProviderMapping.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER market_truth_provider_mapping_refuse_overlap "
        "BEFORE INSERT ON market_truth_provider_mappings BEGIN "
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM market_truth_provider_mappings AS existing "
        "WHERE existing.provider = NEW.provider "
        "AND (existing.provider_token = NEW.provider_token "
        "OR existing.instrument_address = NEW.instrument_address) "
        "AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) "
        "AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) "
        "THEN RAISE(ABORT, 'market truth mapping overlaps an existing identity') END; END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    MarketTruthProviderMapping.__table__,
    "after_create",
    DDL(
        "CREATE OR REPLACE FUNCTION market_truth_provider_mapping_refuse_overlap() "
        "RETURNS trigger AS $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM market_truth_provider_mappings AS existing "
        "WHERE existing.provider = NEW.provider "
        "AND (existing.provider_token = NEW.provider_token "
        "OR existing.instrument_address = NEW.instrument_address) "
        "AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) "
        "AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) "
        "THEN RAISE EXCEPTION 'market truth mapping overlaps an existing identity'; END IF; "
        "RETURN NEW; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"),
)
event.listen(
    MarketTruthProviderMapping.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER market_truth_provider_mapping_refuse_overlap "
        "BEFORE INSERT ON market_truth_provider_mappings "
        "FOR EACH ROW EXECUTE FUNCTION market_truth_provider_mapping_refuse_overlap()"
    ).execute_if(dialect="postgresql"),
)


def _strategy_admission_identity_matches_json(target: StrategyAdmission) -> None:
    """Reject ORM writes whose receipt bytes, key, or copied identity disagree."""
    from app.ir.hashing import canonical_json, content_address

    try:
        document = json.loads(target.artifact_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("strategy admission artifact_json must be valid canonical JSON") from exc
    if canonical_json(document) != target.artifact_json:
        raise ValueError("strategy admission artifact_json must be canonical JSON")
    if content_address(document) != target.admission_address:
        raise ValueError("strategy admission address does not match artifact_json")
    for name in ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme",
                 "contract_suite", "parity_suite"):
        if document.get(name) != getattr(target, name):
            raise ValueError(f"strategy admission {name} does not match artifact_json")
    if document.get("format_version") == 2:
        if target.format_version != 2 or document.get("content_address") != target.content_address:
            raise ValueError("strategy admission v2 semantic identity does not match artifact_json")
    elif target.format_version is not None or target.content_address is not None:
        raise ValueError("legacy strategy admission semantic identity must remain null")


@event.listens_for(StrategyAdmission, "before_insert")
def _strategy_admission_before_insert(_mapper, _connection, target) -> None:
    _strategy_admission_identity_matches_json(target)


@event.listens_for(StrategyAdmission, "before_update")
@event.listens_for(StrategyAdmission, "before_delete")
def _strategy_admission_orm_mutation_refused(_mapper, _connection, _target) -> None:
    raise ValueError("strategy admissions are immutable")


for _trigger_name, _operation in (
    ("strategy_admissions_refuse_update", "UPDATE"),
    ("strategy_admissions_refuse_delete", "DELETE"),
):
    event.listen(
        StrategyAdmission.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_trigger_name} BEFORE {_operation} "
            "ON strategy_admissions BEGIN "
            "SELECT RAISE(ABORT, 'strategy admissions are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )

_install_postgresql_immutable_trigger(
    StrategyAdmission.__table__, "strategy admissions are immutable", sqlstate="55000")


@event.listens_for(IrV2GraphVersion, "before_insert")
def _ir_v2_graph_version_before_insert(_mapper, _connection, target) -> None:
    from app.ir.v2_graph_versions import facts_from_row

    facts_from_row(target)


@event.listens_for(IrV2GraphVersion, "before_update")
@event.listens_for(IrV2GraphVersion, "before_delete")
def _ir_v2_graph_version_orm_mutation_refused(_mapper, _connection, _target) -> None:
    raise ValueError("IR v2 graph versions are immutable")


for _trigger_name, _operation in (
    ("ir_v2_graph_versions_refuse_update", "UPDATE"),
    ("ir_v2_graph_versions_refuse_delete", "DELETE"),
):
    event.listen(
        IrV2GraphVersion.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_trigger_name} BEFORE {_operation} "
            "ON ir_v2_graph_versions BEGIN "
            "SELECT RAISE(ABORT, 'IR v2 graph versions are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )

_install_postgresql_immutable_trigger(
    IrV2GraphVersion.__table__, "IR v2 graph versions are immutable", sqlstate="55000")


@event.listens_for(GraphVersion, "before_insert")
def _graph_version_identity_matches_json(_mapper, _connection, target) -> None:
    """Refuse ORM persistence when executable bytes and identity diverge."""
    import json

    from app.ir.hashing import canonical_json, content_address

    document = json.loads(target.artifact_json)
    if canonical_json(document) != target.artifact_json:
        raise ValueError("graph version artifact_json must be canonical JSON")
    if content_address(document) != target.content_address:
        raise ValueError("graph version content address does not match artifact_json")


event.listen(
    GraphVersion.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER graph_versions_refuse_update "
        "BEFORE UPDATE ON graph_versions BEGIN "
        "SELECT RAISE(ABORT, 'graph versions are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
_install_postgresql_immutable_trigger(GraphVersion.__table__, "graph versions are immutable")
event.listen(
    GraphVersion.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER graph_versions_refuse_delete "
        "BEFORE DELETE ON graph_versions BEGIN "
        "SELECT RAISE(ABORT, 'graph versions are immutable'); END"
    ).execute_if(dialect="sqlite"),
)


class IrGraphLayout(Base):
    """Revision head for sparse editor coordinates on one graph version.

    This is presentation state. It points at an immutable graph identity but is
    never an input to graph or component hashing. A parent row exists even when
    its position set is empty so optimistic concurrency still has a revision.
    """
    __tablename__ = "ir_graph_layouts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "graph_identifier", "graph_version"],
            ["graph_versions.owner_id", "graph_versions.graph_identifier", "graph_versions.version"],
            ondelete="RESTRICT",
            name="fk_ir_graph_layouts_graph_version",
        ),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class IrGraphLayoutPosition(Base):
    """One authored node whose derived placement the editor has overridden."""
    __tablename__ = "ir_graph_layout_positions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "graph_identifier", "graph_version"],
            ["ir_graph_layouts.owner_id", "ir_graph_layouts.graph_identifier", "ir_graph_layouts.graph_version"],
            ondelete="CASCADE",
        ),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)


class IrGraphLayoutGroup(Base):
    """One visual group in the revisioned presentation document."""
    __tablename__ = "ir_graph_layout_groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "graph_identifier", "graph_version"],
            ["ir_graph_layouts.owner_id", "ir_graph_layouts.graph_identifier", "ir_graph_layouts.graph_version"],
            ondelete="CASCADE",
            name="fk_ir_graph_layout_groups_layout",
        ),
        CheckConstraint("length(identifier) > 0", name="ck_ir_groups_identifier"),
        CheckConstraint("length(display_name) > 0", name="ck_ir_groups_display_name"),
        CheckConstraint("width > 0", name="ck_ir_groups_width"),
        CheckConstraint("height > 0", name="ck_ir_groups_height"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    collapsed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class IrGraphLayoutGroupMember(Base):
    """One authored instance included in a visual group."""
    __tablename__ = "ir_graph_layout_group_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "graph_identifier", "graph_version", "group_identifier"],
            [
                "ir_graph_layout_groups.owner_id",
                "ir_graph_layout_groups.graph_identifier",
                "ir_graph_layout_groups.graph_version",
                "ir_graph_layout_groups.identifier",
            ],
            ondelete="CASCADE",
            name="fk_ir_graph_layout_group_members_group",
        ),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class IrGraphLayoutOrphanArchive(Base):
    """Reversible quarantine for a pre-0006 layout with no graph version."""
    __tablename__ = "ir_graph_layout_orphan_archive"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    archived_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class IrGraphLayoutPositionOrphanArchive(Base):
    """Sparse positions quarantined with an orphan layout parent."""
    __tablename__ = "ir_graph_layout_position_orphan_archive"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)


class ProjectReviewNote(Base):
    """Mutable owner writing anchored to, but never copied into, a review event."""
    __tablename__ = "project_review_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "project_id"],
            ["projects.owner_id", "projects.project_id"],
            ondelete="RESTRICT",
            name="fk_project_review_notes_owner_project",
        ),
        CheckConstraint("length(event_id) BETWEEN 1 AND 200", name="ck_review_note_event_id"),
        CheckConstraint(
            "event_type IN ('graph_version_published', 'experiment_run', "
            "'finding_created', 'candidate_created', 'candidate_decided')",
            name="ck_review_note_event_type",
        ),
        CheckConstraint("length(body) BETWEEN 1 AND 4000", name="ck_review_note_body"),
        CheckConstraint("length(created_by) BETWEEN 1 AND 64", name="ck_review_note_owner"),
        CheckConstraint("revision >= 0", name="ck_review_note_revision"),
        Index("ix_project_review_notes_owner_project_event", "owner_id", "project_id", "event_id"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    note_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)


class ProjectReviewSavedView(Base):
    """A named canonical review filter document; never a persisted cursor."""
    __tablename__ = "project_review_saved_views"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "project_id"],
            ["projects.owner_id", "projects.project_id"],
            ondelete="RESTRICT",
            name="fk_project_review_saved_views_owner_project",
        ),
        CheckConstraint("length(name) BETWEEN 1 AND 80", name="ck_review_view_name"),
        CheckConstraint(_JsonIsValid("filters_json"), name="ck_review_view_filters_json"),
        CheckConstraint("length(created_by) BETWEEN 1 AND 64", name="ck_review_view_owner"),
        CheckConstraint("revision >= 0", name="ck_review_view_revision"),
        Index("ix_project_review_saved_views_owner_project", "owner_id", "project_id"),
        Index(
            "uq_project_review_saved_views_active_name",
            "owner_id", "project_id", "name", unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    view_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)


class ProjectReviewSnapshot(Base):
    """Append-only historical observation of the closed project review projection."""
    __tablename__ = "project_review_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "project_id"],
            ["projects.owner_id", "projects.project_id"],
            ondelete="RESTRICT",
            name="fk_project_review_snapshots_owner_project",
        ),
        CheckConstraint("length(label) BETWEEN 1 AND 80", name="ck_review_snapshot_label"),
        CheckConstraint("length(capture_key) = 36", name="ck_review_snapshot_capture_key"),
        CheckConstraint("length(created_by) BETWEEN 1 AND 64", name="ck_review_snapshot_owner"),
        CheckConstraint(_JsonIsValid("manifest_json"), name="ck_review_snapshot_manifest_json"),
        CheckConstraint(_JsonNumberEquals("manifest_json", "schema_version", "1"),
                        name="ck_review_snapshot_schema_version"),
        CheckConstraint(_JsonTextMatchesColumn("manifest_json", "project_id", "project_id"),
                        name="ck_review_snapshot_project_matches_json"),
        CheckConstraint(
            "capture_completed_at >= capture_started_at",
            name="ck_review_snapshot_capture_window",
        ),
        Index("ix_project_review_snapshots_owner_project_completed", "owner_id", "project_id", "capture_completed_at"),
        Index(
            "uq_project_review_snapshots_capture_key",
            "owner_id", "project_id", "capture_key", unique=True,
        ),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    capture_key: Mapped[str] = mapped_column(String(36), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    capture_started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    capture_completed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


@event.listens_for(ProjectReviewSnapshot, "before_insert")
def _review_snapshot_identity_matches_json(_mapper, _connection, target) -> None:
    import json

    from app.core.review_snapshot import validate_snapshot_manifest
    from app.ir.hashing import canonical_json

    document = json.loads(target.manifest_json)
    if canonical_json(document) != target.manifest_json:
        raise ValueError("review snapshot manifest_json must be canonical JSON")
    validated = validate_snapshot_manifest(document)
    if validated.content_address != target.content_address:
        raise ValueError("review snapshot content address does not match manifest_json")


for trigger_name, operation in (
    ("project_review_snapshots_refuse_update", "UPDATE"),
    ("project_review_snapshots_refuse_delete", "DELETE"),
):
    event.listen(
        ProjectReviewSnapshot.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {trigger_name} BEFORE {operation} "
            "ON project_review_snapshots BEGIN "
            "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )

_install_postgresql_immutable_trigger(
    ProjectReviewSnapshot.__table__, "review snapshots are immutable")


class OptionData(Base):
    """Persistent option-chain research dataset. Every distinct contract quote we
    fetch is appended (deduped at snapshot cadence) to build a growing local
    options history that survives restarts and is reusable for research."""
    __tablename__ = "option_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    expiry: Mapped[dt.date] = mapped_column(Date)
    strike: Mapped[float] = mapped_column(Float)
    option_type: Mapped[str] = mapped_column(String(4))   # CE | PE
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    spot: Mapped[float] = mapped_column(Float, default=0.0)
    ltp: Mapped[float] = mapped_column(Float, default=0.0)
    bid: Mapped[float] = mapped_column(Float, default=0.0)
    ask: Mapped[float] = mapped_column(Float, default=0.0)
    oi: Mapped[int] = mapped_column(Integer, default=0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    iv: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)


class DailyAccountSnapshot(Base):
    """One row per IST calendar day: the real Kite account equity at last capture.
    The Calendar view derives YOUR discretionary daily P&L from the day-over-day
    change in account_net minus the bot's booked P&L that day (the bot's side comes
    straight from the Trade ledger). Recorded forward from go-live, so history
    builds from the first live day."""
    __tablename__ = "daily_account_snapshot"
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)   # "YYYY-MM-DD" IST
    account_net: Mapped[float] = mapped_column(Float, default=0.0)        # total account equity (margins.net)
    account_available: Mapped[float] = mapped_column(Float, default=0.0)  # free funds (live_balance)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"day": self.day, "account_net": round(self.account_net, 2),
                "account_available": round(self.account_available, 2)}


class OrderJournal(Base):
    """Persisted record of every real order the bot places (H13). Its WORKING set is
    the durable mirror of LiveBroker._inflight ∪ _pending_entries — the in-memory
    trackers are wiped on restart, so a crash in the ~10s order-poll window would
    otherwise leave an order whose outcome is unknown and unrecoverable. A row is
    written WORKING before placement, stamped with the order id once it acks, and
    marked TERMINAL on resolution. recover_journal() replays WORKING rows on startup.
    Every site that pops _inflight/_pending_entries must mark its row terminal so the
    two stay in lockstep."""
    __tablename__ = "order_journal"
    __table_args__ = (
        Index("ix_order_journal_owner_account", "owner_id", "broker_account_id"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    instrument_key: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(8))          # BUY | SELL
    kind: Mapped[str] = mapped_column(String(12))         # options | equity
    intent: Mapped[str] = mapped_column(String(8))        # ENTRY | EXIT
    qty: Mapped[int] = mapped_column(Integer, default=0)
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="WORKING", index=True)   # WORKING | TERMINAL
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # FILLED | REJECTED | CANCELLED | ADOPTED | DEAD | RACED_FILL | NEVER_PLACED | UNKNOWN
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    placed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    fence_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EarningsEvent(Base):
    """Cached next-results date per NSE/BSE cash-equity symbol, refreshed once a
    day by scripts/refresh_earnings.py from NSE's board-meetings feed. Purely
    informational — the /api/earnings endpoint reads this cache; the engine never
    touches it."""
    __tablename__ = "earnings_events"
    symbol: Mapped[str] = mapped_column(String(48), primary_key=True)
    event_date: Mapped[dt.date] = mapped_column(Date)
    purpose: Mapped[str] = mapped_column(String(128), default="")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class IrShadowDivergence(Base):
    """L1 Stage 1 — one recorded disagreement between the authoritative strategy and its
    Component IR mirror.

    **This table is telemetry, never a money record.** Nothing in the execution path reads
    it; it exists so a disagreement observed weeks ago can be attributed to an exact graph
    version, an exact bar and an exact input frame, which is the whole point of running a
    shadow lane before adopting one.

    Only *disagreements* land here. Agreeing bars are counted in memory
    (`app/engine/ir_shadow_metrics.py`) — persisting every agreeing bar would add tens of
    thousands of rows a week on a 1 GB box and tell you nothing you did not already know.

    `ir_json` is nullable **on purpose**: NULL means the graph produced no verdict at all
    (it refused — insufficient history, a missing input, a runtime error), which is a
    different fact from a verdict of four `false` flags. Collapsing those two is the exact
    silent-degradation shape ADR 0011 exists to prevent, so the column may not be given a
    default.
    """

    __tablename__ = "ir_shadow_divergences"
    __table_args__ = (
        # The signal lane re-scans the same completed bar every 2.5 s until the next one
        # prints, so one bar would otherwise arrive dozens of times. One (instrument, bar,
        # graph, reason) is one row; `reason` is in the key because a bar that later fails
        # a *different* way is a different fact worth keeping.
        Index("uq_ir_shadow_divergence_bar", "owner_id", "broker_account_id", "instrument_key", "bar_time", "graph_address", "reason", unique=True),
        Index("ix_ir_shadow_divergences_observed", "observed_at"),
        Index("ix_ir_shadow_divergences_owner_account", "owner_id", "broker_account_id"),
    )
    #: Whose money this row records. See migration 0017.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)

    id: Mapped[int] = mapped_column(primary_key=True)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    bar_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    instrument_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    authoritative_strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    shadow_strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The graph's content address — `(key, version)` is the execution artefact, and this
    #: is the version half. A disagreement that cannot name its graph is unattributable.
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    authoritative_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ir_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warmup_state: Mapped[str] = mapped_column(String(16), nullable=False, default="settled")
    declared_warmup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Content address of the exact bars the graph was given — same data, same identity.
    frame_id: Mapped[str] = mapped_column(String(71), nullable=False, default="")
    frame_bars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frame_first_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    frame_last_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    eval_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Whether the instrument's market was open when this was observed. Stage 1 closes on
    #: "zero unexplained in-hours insufficient-history events", so out-of-hours events must
    #: be distinguishable from in-hours ones rather than counted together.
    market_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class IrPaperDeployment(Base):
    """A **paper-authoritative** deployment of one immutable graph version to one instrument.

    L1.3C, and the first record in this codebase that lets IR output create execution
    state. It states, durably and with lineage:

        *this approved graph version is authoritative for this instrument at this interval
        in the PAPER book, on this evidence, at this revision*

    and it is structurally unable to state the same thing about the live book.

    **Why this is not `ir_shadow_deployments` with a wider CHECK.** That object is an
    observer: no capital, no orders, no arm state, no authority, and a service with no mode
    parameter. Widening it would make one row mean either "watched" or "traded" depending
    on a column, which is exactly the collapse ADR 0012 keeps refusing. Two tables, two
    vocabularies, two locks.

    **Why this is not a second deployment model either.** The `Deployment` row remains THE
    execution object — it owns the account, the universe, the parameters, the allocation
    and the arm. This record attaches to one, and adds only what a `Deployment` cannot
    carry: which exact graph version, verified by what evidence, for which instrument and
    interval. `deployment_id` is a column here for the same reason it is on `positions`.

    **Why the lifecycle lives here rather than on `Deployment.status`.** The engine pins
    `deployment_id = LEGACY_DEPLOYMENT_ID`; one deployment runs, and every instrument in
    the book shares its status. Pausing one graph binding by pausing that deployment would
    stop the whole book. The lifecycle is therefore per-binding, for the same reason
    L1.3A's is (ADR 0012 §3.1a).

    **Why `execution_mode` and `authority` are CHECK-constrained columns.** The owner
    granted `(ir_graph, paper, authoritative)` and nothing else. A column the database
    refuses to set to `live` cannot be widened by a route, a data fix, a restart path or a
    mistaken service call — only by a reviewed schema change. `GRANTS` is the gate; this is
    the lock on the same door; they fail closed independently.

    **`rollback_strategy_key` is explicit and nullable.** Retiring a binding must restore a
    *named* previous authority or none at all. Inferring the target at runtime — "whatever
    the instrument row said before", "the default" — is the silent-substitution failure
    this project has closed twice already. NULL means "there was no previous authority",
    which is a different statement from "we will work it out later".
    """

    __tablename__ = "ir_paper_deployments"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        # One live paper authority per (deployment, instrument, interval). Retired rows are
        # excluded so superseding frees the slot without deleting what once traded there.
        Index("uq_ir_paper_deployment_active", "deployment_id", "instrument_key",
              "interval", unique=True,
              sqlite_where=text("state IN ('staged','paper_active','paused')"),
              postgresql_where=text("state IN ('staged','paper_active','paused')")),
        Index("ix_ir_paper_deployments_state", "state"),
        Index("ix_ir_paper_deployments_owner_account", "owner_id", "broker_account_id"),
        CheckConstraint("runtime_source = 'ir_graph'",
                        name="ck_ir_paper_deployment_source"),
        CheckConstraint("execution_mode = 'paper'",
                        name="ck_ir_paper_deployment_mode"),
        CheckConstraint("authority = 'authoritative'",
                        name="ck_ir_paper_deployment_authority"),
        CheckConstraint("state IN ('staged','paper_active','paused','retired')",
                        name="ck_ir_paper_deployment_state"),
        CheckConstraint("graph_version >= 1", name="ck_ir_paper_deployment_version"),
        CheckConstraint("revision >= 0", name="ck_ir_paper_deployment_revision"),
        _admission_address_check("ir_paper_deployments"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: The exact immutable artefact. An edit mints a new version and cannot inherit this row.
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Recorded at activation, re-derived on every reload, and re-checked against the
    #: resolved adapter at the authority gate. Three independent places, on purpose.
    graph_content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    evidence_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: **The graph content address the research decision approved** — not the address of
    #: the decision envelope, which the name might suggest. It is the address research
    #: recorded for the artefact its experiment ran on, derived independently of this plane
    #: by `research/orchestrator/graph_experiment.build_graph_provenance`.
    #:
    #: Load-bearing since 2026-08-08 rather than decorative: `_require_evidence` requires
    #: it to equal `graph_content_address` at activation and resume, which is what binds
    #: admission to *bytes* rather than to an identifier and version. Before that check the
    #: two were both stored and never compared, and a decision approving one artefact could
    #: admit another of the same name — proven reachable, not theorised.
    #:
    #: The name is retained deliberately: renaming would be a migration for naming alone on
    #: a table carrying live paper authority, and the contract is stated unambiguously here,
    #: in `_require_evidence`, and in ADR 0013 instead.
    evidence_content_address: Mapped[str] = mapped_column(String(71), nullable=False,
                                                          default="", server_default="")
    evidence_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    deployment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    instrument_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    #: The stable key the adapter registers under — identity across edits, not of a build.
    strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Where authority returns when this binding retires. Explicit; NULL means "none".
    rollback_strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    runtime_source: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="ir_graph",
                                                server_default="ir_graph")
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="paper", server_default="paper")
    authority: Mapped[str] = mapped_column(String(20), nullable=False,
                                           default="authoritative",
                                           server_default="authoritative")
    admission_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                               server_default=_LegacyFalseDefault())
    admission_reason: Mapped[str] = mapped_column(String(400), nullable=False,
                                                  default="", server_default="")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="staged",
                                       server_default="staged")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                          server_default="0")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    #: Whose money this row records. Kept at the historical physical-column tail
    #: so fresh SQLite schema matches migrated live ledgers exactly.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id",
                   name="fk_ir_paper_deployments_broker_account_id_broker_accounts"),
        nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "owner_id": self.owner_id,
            "broker_account_id": self.broker_account_id,
            "project_id": self.project_id,
            "graph_identifier": self.graph_identifier,
            "graph_version": self.graph_version,
            "graph_content_address": self.graph_content_address,
            "evidence_run_id": self.evidence_run_id,
            "evidence_candidate_id": self.evidence_candidate_id,
            "evidence_content_address": self.evidence_content_address,
            "evidence_verified_at": (self.evidence_verified_at.isoformat()
                                     if self.evidence_verified_at else None),
            "deployment_id": self.deployment_id,
            "instrument_key": self.instrument_key, "interval": self.interval,
            "strategy_key": self.strategy_key,
            "rollback_strategy_key": self.rollback_strategy_key,
            "runtime_source": self.runtime_source,
            "execution_mode": self.execution_mode, "authority": self.authority,
            "admission_ok": self.admission_ok, "admission_reason": self.admission_reason,
            "state": self.state, "revision": self.revision, "note": self.note,
        }


class IrShadowDeployment(Base):
    """A managed, **non-authoritative** shadow deployment of one immutable graph version.

    L1.3A turns the IR shadow pairing from runtime machinery into a server-owned record.
    It lets the platform state, durably and with lineage:

        *this approved graph version is deployed to this instrument at this interval in
        shadow mode, with this evidence and this admission state*

    and it is structurally unable to state that the graph may influence an order.

    **Why the identities are separate columns.** Project, graph identifier, graph version,
    content address, evidence lineage, deployment, instrument, interval and strategy key
    are nine different facts. The recorded defect class in this codebase is one layer
    asserting another's fact, and the cheapest way to commit it is to encode several of
    them in the strategy key and parse it back out. `strategy_key` here is the *stable
    execution identity* only — it survives a graph edit, which is exactly why it cannot
    identify the version that ran.

    **Why `execution_mode` and `authority` are columns with CHECK constraints rather than
    application logic.** ADR 0012 §3.2 reserves paper authority to the owner. A column the
    database refuses to set to anything but `shadow`/`non_authoritative` cannot be widened
    by a route, a migration data-fix, a restart path or a mistaken service call — only by a
    reviewed schema change. `AUTHORITY_BY_SOURCE` is the gate; this is the lock on the same
    door, and the two fail closed independently.

    **Why evidence is recorded rather than foreign-keyed.** The approval lineage lives in
    the research plane's own database (hard invariant 5: isolated, read-only bridges only).
    A cross-database foreign key is impossible and a cross-database write would breach the
    isolation, so activation *verifies* the lineage through the read-only bridge and
    records the verified identity. The row therefore states what was checked and when, and
    re-verification on reload is what keeps that claim honest rather than historical.
    """

    __tablename__ = "ir_shadow_deployments"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        # One live shadow evaluator per (deployment, instrument, interval). Retired and
        # paused rows are excluded so a retirement frees the slot without deleting the
        # history that says what once ran there.
        Index("uq_ir_shadow_deployment_active", "deployment_id", "instrument_key",
              "interval", unique=True,
              sqlite_where=text("state IN ('staged','shadow_active','paused')"),
              postgresql_where=text("state IN ('staged','shadow_active','paused')")),
        Index("ix_ir_shadow_deployments_state", "state"),
        Index("ix_ir_shadow_deployments_owner_account", "owner_id", "broker_account_id"),
        CheckConstraint("runtime_source = 'ir_graph'",
                        name="ck_ir_shadow_deployment_source"),
        CheckConstraint("execution_mode = 'shadow'",
                        name="ck_ir_shadow_deployment_mode"),
        CheckConstraint("authority = 'non_authoritative'",
                        name="ck_ir_shadow_deployment_authority"),
        CheckConstraint("state IN ('staged','shadow_active','paused','retired')",
                        name="ck_ir_shadow_deployment_state"),
        CheckConstraint("graph_version >= 1", name="ck_ir_shadow_deployment_version"),
        CheckConstraint("revision >= 0", name="ck_ir_shadow_deployment_revision"),
        _admission_address_check("ir_shadow_deployments"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    #: Which project owns the logic. Not derivable from the graph identifier.
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: The exact immutable artefact. `(identifier, version)` is the executable identity;
    #: an edit mints a new version and therefore cannot inherit this row.
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Recorded at activation and re-verified on every reload. A content address that stops
    #: matching its version means the bytes moved under a row that claims to name them.
    graph_content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    #: Verified research lineage, recorded rather than foreign-keyed (see the class
    #: docstring). NULL run id means "staged without evidence", which may not activate.
    evidence_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_content_address: Mapped[str] = mapped_column(String(71), nullable=False,
                                                          default="", server_default="")
    evidence_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    #: Which book this observes. It observes it; it never writes to it.
    deployment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    instrument_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    #: The stable key the adapter registers under — identity across edits, not of a build.
    strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_source: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="ir_graph",
                                                server_default="ir_graph")
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="shadow",
                                                server_default="shadow")
    authority: Mapped[str] = mapped_column(String(20), nullable=False,
                                           default="non_authoritative",
                                           server_default="non_authoritative")
    #: The warmup/history verdict from the Stage 1 admission contract, decided before
    #: activation so an impossible pairing is refused rather than discovered per-scan.
    admission_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                               server_default=_LegacyFalseDefault())
    admission_reason: Mapped[str] = mapped_column(String(400), nullable=False,
                                                  default="", server_default="")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="staged",
                                       server_default="staged")
    #: Optimistic concurrency. Every transition names the revision it believes it is
    #: acting on, so two operators cannot silently overwrite one another's decision.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                          server_default="0")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    #: Whose money this row records. Kept at the historical physical-column tail
    #: so fresh SQLite schema matches migrated live ledgers exactly.
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id",
                   name="fk_ir_shadow_deployments_broker_account_id_broker_accounts"),
        nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "owner_id": self.owner_id,
            "broker_account_id": self.broker_account_id,
            "project_id": self.project_id,
            "graph_identifier": self.graph_identifier,
            "graph_version": self.graph_version,
            "graph_content_address": self.graph_content_address,
            "evidence_run_id": self.evidence_run_id,
            "evidence_candidate_id": self.evidence_candidate_id,
            "evidence_content_address": self.evidence_content_address,
            "evidence_verified_at": (self.evidence_verified_at.isoformat()
                                     if self.evidence_verified_at else None),
            "deployment_id": self.deployment_id,
            "instrument_key": self.instrument_key, "interval": self.interval,
            "strategy_key": self.strategy_key, "runtime_source": self.runtime_source,
            "execution_mode": self.execution_mode, "authority": self.authority,
            "admission_ok": self.admission_ok, "admission_reason": self.admission_reason,
            "state": self.state, "revision": self.revision, "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }




class BrokerConnection(Base):
    """A credentialed link one owner holds to one broker — durable, encrypted, revocable.

    Until now a connection was constructed per process from environment variables: one
    implicit owner, one implicit credential, discarded on restart. That is why
    `Connection` (app/providers/connection.py) is a runtime value object with a late-bound
    `token_source` and no persistence. This table is its durable form, and the two are
    deliberately separate: the row is what an owner *has*, and `Connection` is what a
    running engine *uses*. Merging them would put a database session on the order path.

    **ADR 0015 places this in the money plane.** Not on recovery cost — losing a row costs a
    re-login, and Kite tokens expire daily anyway — but on blast radius: a row here is the
    authority to place real orders on a real account. Two consequences that are load-bearing
    rather than stylistic:

      * `scope` is the same string written into `ExecutionIntent.connection_scope` and matched
        by restart recovery. Keeping connections and intents in one plane is what keeps
        attribution a join rather than a hope. It is **by value, not a foreign key** — ADR 0015's
        no-cross-plane-FK rule applies within a plane too here, because an intent must survive
        the deletion of the connection that authored it. A live order whose connection row is
        gone is still a live order, and nulling its scope would orphan it.
      * The credential is stored encrypted and the **key is not in the database** — it comes
        from the process environment. A database compromise alone must not be a credential
        compromise, and that is only true if the key is never a row.

    Revocation is a status change, never a delete. "This credential was revoked at 14:02" is a
    fact someone will need to establish, and a deleted row establishes nothing.
    """

    __tablename__ = "broker_connections"
    __table_args__ = (
        # One scope per owner, not one globally: two owners may both hold a `kite:legacy`
        # connection, and they are different connections. Scoping the uniqueness by owner is
        # what makes the tenancy dimension real rather than decorative.
        UniqueConstraint("owner_id", "broker_account_id", "scope",
                         name="uq_broker_connection_owner_account_scope"),
        Index("ix_broker_connections_owner", "owner_id"),
        Index("ix_broker_connections_owner_account", "owner_id", "broker_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(
        ForeignKey("broker_accounts.broker_account_id"), nullable=False)
    #: The broker registry key (`app/providers/brokers.py`). An identifier, not a label.
    broker: Mapped[str] = mapped_column(String(32), nullable=False)
    #: What `ExecutionIntent.connection_scope` carries. See the class docstring.
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="",
                                       server_default="")
    #: Declared capabilities, as a JSON array. Stored rather than recomputed from the adapter
    #: class because an owner may hold a connection whose entitlements are narrower than what
    #: the adapter can do — a data-only Kite connection is a legitimate thing to grant.
    capabilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]",
                                                   server_default="[]")
    #: AES-GCM ciphertext of the credential bundle, base64. NULL means "no credential stored"
    #: — a connection that has been created but never authenticated, which is a real state and
    #: is distinguishable from an empty credential.
    credential_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Which key encrypted it. Stored so a key rotation can find the rows it still has to
    #: re-wrap, instead of discovering them one failed decrypt at a time on the order path.
    credential_key_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                        server_default="active")   # active | revoked
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    #: When this connection last held a working credential. Distinct from `updated_at`, which
    #: moves for a label edit — the operator's question is "when did this last work".
    last_authenticated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Safe to serialise. **No credential field appears here, and none may be added** —
        this dict reaches the API, the logs and the operator's browser."""
        return {
            "id": self.id, "owner_id": self.owner_id,
            "broker_account_id": self.broker_account_id, "broker": self.broker,
            "scope": self.scope, "label": self.label,
            "capabilities": json.loads(self.capabilities_json or "[]"),
            "status": self.status,
            "has_credential": bool(self.credential_ciphertext),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_authenticated_at": (self.last_authenticated_at.isoformat()
                                      if self.last_authenticated_at else None),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


def _make_phase5_fact_immutable(table) -> None:
    for operation in ("UPDATE", "DELETE"):
        event.listen(table, "after_create", DDL(
            f"CREATE TRIGGER {table.name}_refuse_{operation.lower()} "
            f"BEFORE {operation} ON {table.name} BEGIN "
            f"SELECT RAISE(ABORT, '{table.name} is immutable'); END"
        ).execute_if(dialect="sqlite"))
    _install_postgresql_immutable_trigger(table, f"{table.name} is immutable")


def _install_phase5_identity_guard(table, columns: tuple[str, ...]) -> None:
    trigger = f"{table.name}_refuse_identity_change"
    sqlite_change = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in columns)
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table.name} "
        f"WHEN {sqlite_change} BEGIN "
        f"SELECT RAISE(ABORT, '{table.name} identity is immutable'); END"
    ).execute_if(dialect="sqlite"))
    function = f"{trigger}_fn"
    pg_change = " OR ".join(
        f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in columns)
    event.listen(table, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        f"IF {pg_change} THEN RAISE EXCEPTION '{table.name} identity is immutable'; "
        "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table.name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    ).execute_if(dialect="postgresql"))


def _install_phase5_delete_guard(table) -> None:
    trigger = f"{table.name}_refuse_delete"
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE DELETE ON {table.name} BEGIN "
        f"SELECT RAISE(ABORT, '{table.name} is durable'); END"
    ).execute_if(dialect="sqlite"))
    function = f"{trigger}_fn"
    event.listen(table, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        f"RAISE EXCEPTION '{table.name} is durable'; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {trigger} BEFORE DELETE ON {table.name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    ).execute_if(dialect="postgresql"))


for _phase5_immutable_table in (
    SizingPolicyRecord.__table__, SizingDecisionRecord.__table__,
    TargetPositionRequestRecord.__table__, CandidateIntentRecord.__table__,
    DecisionBatchRecord.__table__, PortfolioAdmissionDecisionRecord.__table__,
    CapitalReservationEventRecord.__table__, FillAllocationRecord.__table__,
):
    _make_phase5_fact_immutable(_phase5_immutable_table)

_install_phase5_identity_guard(CapitalReservationRecord.__table__, (
    "reservation_address", "owner_id", "broker_account_id", "book", "currency",
    "batch_id", "candidate_intent_id", "decision_id", "estimated_minor",
    "requested_quantity", "admitted_quantity", "fence_epoch", "created_at",
))
_install_phase5_identity_guard(PositionCampaignRecord.__table__, (
    "campaign_address", "owner_id", "broker_account_id", "book", "deployment_id",
    "strategy_key", "strategy_version", "admission_address", "graph_address",
    "attribution_state", "canonical_instrument_key", "execution_instrument_key",
    "product_address", "direction", "target_policy_address", "position_id",
    "opened_at",
))
_install_phase5_identity_guard(PositionTrancheRecord.__table__, (
    "tranche_address", "campaign_id", "target_position_request_id",
    "candidate_intent_id", "batch_id", "decision_id", "reservation_id",
    "execution_intent_id", "purpose", "requested_quantity",
    "admitted_quantity", "created_at",
))
for _phase5_durable_lineage_table in (
        PositionCampaignRecord.__table__, PositionTrancheRecord.__table__):
    _install_phase5_delete_guard(_phase5_durable_lineage_table)


for _graph_fact_table in (
    Deployment.__table__, ExecutionIntent.__table__, Position.__table__,
    Trade.__table__, BacktestResult.__table__, TargetPositionRequestRecord.__table__,
    CandidateIntentRecord.__table__, PositionCampaignRecord.__table__,
):
    _install_graph_attribution_validation(_graph_fact_table)
for _graph_entry_table in (
    Deployment.__table__, ExecutionIntent.__table__, Position.__table__, BacktestResult.__table__,
    TargetPositionRequestRecord.__table__, CandidateIntentRecord.__table__,
    PositionCampaignRecord.__table__):
    _install_graph_attribution_insert_guard(_graph_entry_table)


class MonitoringAssignmentRow(Base):
    """Owner-scoped monitoring activation with no execution or money authority."""

    __tablename__ = "monitoring_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "project_id"), ("projects.owner_id", "projects.project_id"),
            name="fk_monitoring_assignments_project", ondelete="RESTRICT"),
        CheckConstraint("optimistic_revision >= 1", name="ck_monitoring_assignments_revision"),
        CheckConstraint(
            "lifecycle_state IN ('ACTIVE', 'PAUSED', 'WITHDRAWN')",
            name="ck_monitoring_assignments_lifecycle"),
        CheckConstraint(
            "(lifecycle_state = 'WITHDRAWN' AND withdrawn_at IS NOT NULL) OR "
            "(lifecycle_state <> 'WITHDRAWN' AND withdrawn_at IS NULL)",
            name="ck_monitoring_assignments_withdrawal"),
        CheckConstraint("data_connection_id > 0", name="ck_monitoring_assignments_data_connection"),
        CheckConstraint(_ContentAddress("graph_version_address"), name="ck_monitoring_assignments_graph"),
        CheckConstraint(_ContentAddress("resolved_graph_address"), name="ck_monitoring_assignments_resolved"),
        CheckConstraint(_ContentAddress("registry_address"), name="ck_monitoring_assignments_registry"),
        CheckConstraint(_ContentAddress("implementation_closure_address"), name="ck_monitoring_assignments_implementation"),
        CheckConstraint(_ContentAddress("research_admission_address"), name="ck_monitoring_assignments_admission"),
        CheckConstraint(_ContentAddress("static_scope_revision_address"), name="ck_monitoring_assignments_scope"),
        CheckConstraint(_ContentAddress("role_binding_address"), name="ck_monitoring_assignments_roles"),
        CheckConstraint(_ContentAddress("capability_profile_address"), name="ck_monitoring_assignments_capability"),
        CheckConstraint(_ContentAddress("resource_plan_address"), name="ck_monitoring_assignments_resource"),
        CheckConstraint(_ContentAddress("evaluation_trigger_address"), name="ck_monitoring_assignments_trigger"),
        CheckConstraint(_ContentAddress("state_reset_policy_address"), name="ck_monitoring_assignments_reset"),
        CheckConstraint(_NullableContentAddress("current_state_snapshot_address"), name="ck_monitoring_assignments_current_snapshot"),
        Index("ix_monitoring_assignments_owner_lifecycle", "owner_id", "lifecycle_state", "assignment_id"),
        Index("ix_monitoring_assignments_owner_project", "owner_id", "project_id", "assignment_id"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    optimistic_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(16), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version_address: Mapped[str] = mapped_column(String(71), nullable=False)
    resolved_graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    registry_address: Mapped[str] = mapped_column(String(71), nullable=False)
    implementation_closure_address: Mapped[str] = mapped_column(String(71), nullable=False)
    research_admission_address: Mapped[str] = mapped_column(String(71), nullable=False)
    static_scope_revision_address: Mapped[str] = mapped_column(String(71), nullable=False)
    role_binding_address: Mapped[str] = mapped_column(String(71), nullable=False)
    data_connection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    capability_profile_address: Mapped[str] = mapped_column(String(71), nullable=False)
    resource_plan_address: Mapped[str] = mapped_column(String(71), nullable=False)
    evaluation_trigger_address: Mapped[str] = mapped_column(String(71), nullable=False)
    state_reset_policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    current_state_snapshot_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    withdrawn_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class MonitoringStateSnapshotRow(Base):
    __tablename__ = "monitoring_state_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id"),
            ("monitoring_assignments.owner_id", "monitoring_assignments.assignment_id"),
            name="fk_monitoring_snapshots_assignment", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "canonical_instrument_address", "predecessor_snapshot_address"),
            ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
             "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
            name="fk_monitoring_snapshots_predecessor", ondelete="RESTRICT",
            deferrable=True, initially="DEFERRED"),
        UniqueConstraint(
            "owner_id", "assignment_id", "canonical_instrument_address", "snapshot_sequence",
            name="uq_monitoring_snapshots_sequence"),
        CheckConstraint("snapshot_sequence >= 0", name="ck_monitoring_snapshots_sequence"),
        CheckConstraint(
            "(snapshot_sequence = 0 AND predecessor_snapshot_address IS NULL) OR "
            "(snapshot_sequence > 0 AND predecessor_snapshot_address IS NOT NULL)",
            name="ck_monitoring_snapshots_predecessor"),
        CheckConstraint("strategy_state IN ('FLAT', 'LONG', 'SHORT')", name="ck_monitoring_snapshots_state"),
        CheckConstraint(_ContentAddress("canonical_instrument_address"), name="ck_monitoring_snapshots_instrument"),
        CheckConstraint(_ContentAddress("snapshot_address"), name="ck_monitoring_snapshots_address"),
        CheckConstraint(_NullableContentAddress("predecessor_snapshot_address"), name="ck_monitoring_snapshots_predecessor_address"),
        CheckConstraint(_ContentAddress("evaluation_event_address"), name="ck_monitoring_snapshots_evaluation"),
        CheckConstraint(_JsonIsValid("entry_reference_json"), name="ck_monitoring_snapshots_entry_json"),
        CheckConstraint(_JsonIsValid("stop_loss_json"), name="ck_monitoring_snapshots_stop_json"),
        CheckConstraint(_JsonIsValid("take_profit_json"), name="ck_monitoring_snapshots_target_json"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_monitoring_snapshots_canonical_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_monitoring_snapshots_canonical_size"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "address", "snapshot_address"), name="ck_monitoring_snapshots_json_address"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "owner_id", "owner_id"), name="ck_monitoring_snapshots_json_owner"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "assignment_id", "assignment_id"), name="ck_monitoring_snapshots_json_assignment"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "canonical_instrument_address", "canonical_instrument_address"), name="ck_monitoring_snapshots_json_instrument"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "evaluation_event_address", "evaluation_event_address"), name="ck_monitoring_snapshots_json_evaluation"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "strategy_state", "strategy_state"), name="ck_monitoring_snapshots_json_state"),
        CheckConstraint(_JsonNumberEquals("canonical_json", "snapshot_sequence", "snapshot_sequence"), name="ck_monitoring_snapshots_json_sequence"),
        Index("ix_monitoring_snapshots_sequence", "owner_id", "assignment_id", "canonical_instrument_address", "snapshot_sequence"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    canonical_instrument_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    snapshot_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    snapshot_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    predecessor_snapshot_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    strategy_state: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_reference_json: Mapped[str] = mapped_column(Text, nullable=False)
    stop_loss_json: Mapped[str] = mapped_column(Text, nullable=False)
    take_profit_json: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_event_address: Mapped[str] = mapped_column(String(71), nullable=False)
    effective_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringSignalEventRow(Base):
    __tablename__ = "monitoring_signal_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id"),
            ("monitoring_assignments.owner_id", "monitoring_assignments.assignment_id"),
            name="fk_monitoring_events_assignment", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "canonical_instrument_address", "state_before_address"),
            ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
             "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
            name="fk_monitoring_events_state_before", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "canonical_instrument_address", "state_after_address"),
            ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
             "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
            name="fk_monitoring_events_state_after", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "dedupe_address", name="uq_monitoring_events_dedupe"),
        UniqueConstraint(
            "owner_id", "assignment_id", "canonical_instrument_address",
            "evaluation_event_address", "graph_version_address",
            "implementation_closure_address", "state_before_address",
            name="uq_monitoring_events_business_effect"),
        CheckConstraint(_ContentAddress("content_address"), name="ck_monitoring_events_address"),
        CheckConstraint(_ContentAddress("dedupe_address"), name="ck_monitoring_events_dedupe"),
        CheckConstraint(_ContentAddress("canonical_instrument_address"), name="ck_monitoring_events_instrument"),
        CheckConstraint(_ContentAddress("evaluation_event_address"), name="ck_monitoring_events_evaluation"),
        CheckConstraint(_ContentAddress("graph_version_address"), name="ck_monitoring_events_graph"),
        CheckConstraint(_ContentAddress("implementation_closure_address"), name="ck_monitoring_events_implementation"),
        CheckConstraint(_ContentAddress("state_before_address"), name="ck_monitoring_events_state_before"),
        CheckConstraint(_ContentAddress("state_after_address"), name="ck_monitoring_events_state_after"),
        CheckConstraint("event_at <= valid_until", name="ck_monitoring_events_time"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_monitoring_events_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_monitoring_events_json_size"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "address", "content_address"), name="ck_monitoring_events_json_address"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "owner_id", "owner_id"), name="ck_monitoring_events_json_owner"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "assignment_id", "assignment_id"), name="ck_monitoring_events_json_assignment"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "canonical_instrument_address", "canonical_instrument_address"), name="ck_monitoring_events_json_instrument"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "evaluation_event_address", "evaluation_event_address"), name="ck_monitoring_events_json_evaluation"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "graph_version_address", "graph_version_address"), name="ck_monitoring_events_json_graph"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "implementation_closure_address", "implementation_closure_address"), name="ck_monitoring_events_json_implementation"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "state_before_address", "state_before_address"), name="ck_monitoring_events_json_before"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "state_after_address", "state_after_address"), name="ck_monitoring_events_json_after"),
        Index("ix_monitoring_events_cursor", "owner_id", "assignment_id", "event_at", "content_address"),
        Index("ix_monitoring_events_state", "owner_id", "assignment_id", "canonical_instrument_address", "event_at", "content_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    content_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    dedupe_address: Mapped[str] = mapped_column(String(71), nullable=False)
    canonical_instrument_address: Mapped[str] = mapped_column(String(71), nullable=False)
    evaluation_event_address: Mapped[str] = mapped_column(String(71), nullable=False)
    graph_version_address: Mapped[str] = mapped_column(String(71), nullable=False)
    implementation_closure_address: Mapped[str] = mapped_column(String(71), nullable=False)
    state_before_address: Mapped[str] = mapped_column(String(71), nullable=False)
    state_after_address: Mapped[str] = mapped_column(String(71), nullable=False)
    event_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringSignalAlertRow(Base):
    __tablename__ = "monitoring_signal_alerts"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "monitoring_event_address"),
            ("monitoring_signal_events.owner_id", "monitoring_signal_events.assignment_id",
             "monitoring_signal_events.content_address"),
            name="fk_monitoring_alerts_event", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "assignment_id", "monitoring_event_address", name="uq_monitoring_alerts_event"),
        CheckConstraint(_ContentAddress("alert_address"), name="ck_monitoring_alerts_address"),
        CheckConstraint(_ContentAddress("monitoring_event_address"), name="ck_monitoring_alerts_event"),
        CheckConstraint(_ContentAddress("canonical_instrument_address"), name="ck_monitoring_alerts_instrument"),
        CheckConstraint("event_at <= valid_until", name="ck_monitoring_alerts_time"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_monitoring_alerts_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_monitoring_alerts_json_size"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "address", "alert_address"), name="ck_monitoring_alerts_json_address"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "owner_id", "owner_id"), name="ck_monitoring_alerts_json_owner"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "assignment_id", "assignment_id"), name="ck_monitoring_alerts_json_assignment"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "monitoring_event_address", "monitoring_event_address"), name="ck_monitoring_alerts_json_event"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "canonical_instrument_address", "canonical_instrument_address"), name="ck_monitoring_alerts_json_instrument"),
        Index("ix_monitoring_alerts_owner_cursor", "owner_id", "event_at", "alert_address"),
        Index("ix_monitoring_alerts_assignment_cursor", "owner_id", "assignment_id", "event_at", "alert_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    alert_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    monitoring_event_address: Mapped[str] = mapped_column(String(71), nullable=False)
    canonical_instrument_address: Mapped[str] = mapped_column(String(71), nullable=False)
    event_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringAlertDeliveryAttemptRow(Base):
    __tablename__ = "monitoring_alert_delivery_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "alert_address"),
            ("monitoring_signal_alerts.owner_id", "monitoring_signal_alerts.assignment_id",
             "monitoring_signal_alerts.alert_address"),
            name="fk_monitoring_delivery_alert", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "attempt_id", name="uq_monitoring_delivery_request"),
        UniqueConstraint("owner_id", "assignment_id", "alert_address", "sequence", "channel",
                         name="uq_monitoring_delivery_sequence"),
        CheckConstraint("sequence >= 1", name="ck_monitoring_delivery_sequence"),
        CheckConstraint("channel = 'IN_APP'", name="ck_monitoring_delivery_channel"),
        CheckConstraint("outcome IN ('DELIVERED', 'FAILED')", name="ck_monitoring_delivery_outcome"),
        CheckConstraint(
            "(outcome = 'FAILED' AND failure_code IS NOT NULL) OR "
            "(outcome = 'DELIVERED' AND failure_code IS NULL)",
            name="ck_monitoring_delivery_failure"),
        CheckConstraint(_ContentAddress("attempt_address"), name="ck_monitoring_delivery_address"),
        CheckConstraint(_ContentAddress("attempt_id"), name="ck_monitoring_delivery_request_address"),
        CheckConstraint(_ContentAddress("alert_address"), name="ck_monitoring_delivery_alert_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_monitoring_delivery_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_monitoring_delivery_json_size"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "address", "attempt_address"), name="ck_monitoring_delivery_json_address"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "attempt_id", "attempt_id"), name="ck_monitoring_delivery_json_request"),
        Index("ix_monitoring_delivery_sequence", "owner_id", "assignment_id", "alert_address", "sequence"),
        Index("ix_monitoring_delivery_outcome", "owner_id", "outcome", "occurred_at"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    attempt_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(71), nullable=False)
    alert_address: Mapped[str] = mapped_column(String(71), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringAlertAttentionEventRow(Base):
    __tablename__ = "monitoring_alert_attention_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "alert_address"),
            ("monitoring_signal_alerts.owner_id", "monitoring_signal_alerts.assignment_id",
             "monitoring_signal_alerts.alert_address"),
            name="fk_monitoring_attention_alert", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "request_id", name="uq_monitoring_attention_request"),
        UniqueConstraint("owner_id", "assignment_id", "alert_address", "sequence",
                         name="uq_monitoring_attention_sequence"),
        CheckConstraint("sequence >= 1", name="ck_monitoring_attention_sequence"),
        CheckConstraint("action IN ('READ', 'ACKNOWLEDGE', 'DISMISS')", name="ck_monitoring_attention_action"),
        CheckConstraint(_ContentAddress("attention_event_address"), name="ck_monitoring_attention_address"),
        CheckConstraint(_ContentAddress("request_id"), name="ck_monitoring_attention_request_address"),
        CheckConstraint(_ContentAddress("alert_address"), name="ck_monitoring_attention_alert_address"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_monitoring_attention_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_monitoring_attention_json_size"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "address", "attention_event_address"), name="ck_monitoring_attention_json_address"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "request_id", "request_id"), name="ck_monitoring_attention_json_request"),
        Index("ix_monitoring_attention_sequence", "owner_id", "assignment_id", "alert_address", "sequence"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    attention_event_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(71), nullable=False)
    alert_address: Mapped[str] = mapped_column(String(71), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringLatestStateRow(Base):
    __tablename__ = "monitoring_latest_state"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_address"),
            ("monitoring_state_snapshots.owner_id", "monitoring_state_snapshots.assignment_id",
             "monitoring_state_snapshots.canonical_instrument_address", "monitoring_state_snapshots.snapshot_address"),
            name="fk_monitoring_latest_snapshot", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "last_event_address"),
            ("monitoring_signal_events.owner_id", "monitoring_signal_events.assignment_id",
             "monitoring_signal_events.content_address"),
            name="fk_monitoring_latest_event", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "assignment_id", "canonical_instrument_address", "snapshot_address",
                         name="uq_monitoring_latest_snapshot"),
        CheckConstraint(_ContentAddress("canonical_instrument_address"), name="ck_monitoring_latest_instrument"),
        CheckConstraint(_ContentAddress("snapshot_address"), name="ck_monitoring_latest_snapshot"),
        CheckConstraint(_NullableContentAddress("last_event_address"), name="ck_monitoring_latest_event"),
        CheckConstraint("snapshot_sequence >= 0", name="ck_monitoring_latest_sequence"),
        CheckConstraint("strategy_state IN ('FLAT', 'LONG', 'SHORT')", name="ck_monitoring_latest_state"),
        CheckConstraint("projection_revision >= 1", name="ck_monitoring_latest_revision"),
        Index("ix_monitoring_latest_updated", "owner_id", "assignment_id", "updated_at"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    canonical_instrument_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    snapshot_address: Mapped[str] = mapped_column(String(71), nullable=False)
    last_event_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    snapshot_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_state: Mapped[str] = mapped_column(String(8), nullable=False)
    projection_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringAlertAttentionStateRow(Base):
    __tablename__ = "monitoring_alert_attention_state"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "alert_address"),
            ("monitoring_signal_alerts.owner_id", "monitoring_signal_alerts.assignment_id",
             "monitoring_signal_alerts.alert_address"),
            name="fk_monitoring_attention_state_alert", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "projection_address", name="uq_monitoring_attention_state_projection"),
        CheckConstraint(_ContentAddress("alert_address"), name="ck_monitoring_attention_state_alert"),
        CheckConstraint(_ContentAddress("projection_address"), name="ck_monitoring_attention_state_address"),
        CheckConstraint("alert_event_at <= alert_valid_until", name="ck_monitoring_attention_state_alert_time"),
        CheckConstraint("last_sequence >= 0", name="ck_monitoring_attention_state_sequence"),
        CheckConstraint("projection_revision >= 1", name="ck_monitoring_attention_state_revision"),
        CheckConstraint("read_at IS NULL OR read_at >= alert_event_at", name="ck_monitoring_attention_state_read"),
        CheckConstraint("acknowledged_at IS NULL OR acknowledged_at >= alert_event_at", name="ck_monitoring_attention_state_ack"),
        CheckConstraint("dismissed_at IS NULL OR dismissed_at >= alert_event_at", name="ck_monitoring_attention_state_dismiss"),
        Index("ix_monitoring_attention_inbox", "owner_id", "is_unread", "alert_event_at", "alert_address"),
        Index("ix_monitoring_attention_assignment", "owner_id", "assignment_id", "alert_event_at", "alert_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    alert_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    projection_address: Mapped[str] = mapped_column(String(71), nullable=False)
    alert_event_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    alert_valid_until: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    is_unread: Mapped[bool] = mapped_column(Boolean, nullable=False)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    dismissed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    projection_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class MonitoringSignalReviewRow(Base):
    __tablename__ = "monitoring_signal_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "assignment_id", "monitoring_event_address"),
            ("monitoring_signal_events.owner_id", "monitoring_signal_events.assignment_id",
             "monitoring_signal_events.content_address"),
            name="fk_monitoring_reviews_event", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ("owner_id", "reviewer_user_id"),
            ("memberships.organization_id", "memberships.user_id"),
            name="fk_monitoring_reviews_membership", ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "assignment_id", "monitoring_event_address", "reviewer_user_id",
                         name="uq_monitoring_reviews_author"),
        CheckConstraint(_ContentAddress("review_address"), name="ck_monitoring_reviews_address"),
        CheckConstraint(_ContentAddress("monitoring_event_address"), name="ck_monitoring_reviews_event"),
        CheckConstraint("disposition IN ('CONFIRMED', 'REJECTED')", name="ck_monitoring_reviews_disposition"),
        CheckConstraint(_ClosedCode("reason_code"), name="ck_monitoring_reviews_reason"),
        CheckConstraint(_ReviewNoteValid("note"), name="ck_monitoring_reviews_note"),
        CheckConstraint(_JsonIsValid("canonical_json"), name="ck_monitoring_reviews_json"),
        CheckConstraint(_Utf8SizeAtMost("canonical_json", 16384), name="ck_monitoring_reviews_json_size"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "address", "review_address"), name="ck_monitoring_reviews_json_address"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "owner_id", "owner_id"), name="ck_monitoring_reviews_json_owner"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "assignment_id", "assignment_id"), name="ck_monitoring_reviews_json_assignment"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "monitoring_event_address", "monitoring_event_address"), name="ck_monitoring_reviews_json_event"),
        CheckConstraint(_JsonTextMatchesColumn("canonical_json", "reviewer_user_id", "reviewer_user_id"), name="ck_monitoring_reviews_json_reviewer"),
        Index("ix_monitoring_reviews_cursor", "owner_id", "assignment_id", "created_at", "review_address"),
        Index("ix_monitoring_reviews_disposition", "owner_id", "disposition", "created_at"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    monitoring_event_address: Mapped[str] = mapped_column(String(71), nullable=False)
    reviewer_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    disposition: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)


def _make_monitoring_fact_immutable(table) -> None:
    for operation in ("UPDATE", "DELETE"):
        event.listen(table, "after_create", DDL(
            f"CREATE TRIGGER {table.name}_refuse_{operation.lower()} "
            f"BEFORE {operation} ON {table.name} BEGIN "
            f"SELECT RAISE(ABORT, '{table.name} is immutable'); END"
        ).execute_if(dialect="sqlite"))
    _install_postgresql_immutable_trigger(table, f"{table.name} is immutable")


def _install_monitoring_assignment_guards(table) -> None:
    mutable = {
        "optimistic_revision", "lifecycle_state", "current_state_snapshot_address",
        "updated_at", "withdrawn_at",
    }
    immutable = tuple(column.name for column in table.columns if column.name not in mutable)
    sqlite_change = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in immutable)
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER monitoring_assignments_refuse_identity_change "
        f"BEFORE UPDATE ON monitoring_assignments WHEN {sqlite_change} BEGIN "
        "SELECT RAISE(ABORT, 'monitoring assignment identity is immutable'); END"
    ).execute_if(dialect="sqlite"))
    event.listen(table, "after_create", DDL(
        "CREATE TRIGGER monitoring_assignments_refuse_delete BEFORE DELETE ON monitoring_assignments "
        "BEGIN SELECT RAISE(ABORT, 'monitoring assignments are durable'); END"
    ).execute_if(dialect="sqlite"))
    pg_change = " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in immutable)
    event.listen(table, "after_create", DDL(
        "CREATE OR REPLACE FUNCTION monitoring_assignments_refuse_identity_change_fn() "
        "RETURNS trigger AS $$ BEGIN "
        f"IF {pg_change} THEN RAISE EXCEPTION 'monitoring assignment identity is immutable'; "
        "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        "CREATE TRIGGER monitoring_assignments_refuse_identity_change BEFORE UPDATE ON monitoring_assignments "
        "FOR EACH ROW EXECUTE FUNCTION monitoring_assignments_refuse_identity_change_fn()"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        "CREATE OR REPLACE FUNCTION monitoring_assignments_refuse_delete_fn() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'monitoring assignments are durable'; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        "CREATE TRIGGER monitoring_assignments_refuse_delete BEFORE DELETE ON monitoring_assignments "
        "FOR EACH ROW EXECUTE FUNCTION monitoring_assignments_refuse_delete_fn()"
    ).execute_if(dialect="postgresql"))


_install_monitoring_assignment_guards(MonitoringAssignmentRow.__table__)
for _monitoring_immutable_table in (
    MonitoringStateSnapshotRow.__table__, MonitoringSignalEventRow.__table__,
    MonitoringSignalAlertRow.__table__, MonitoringAlertDeliveryAttemptRow.__table__,
    MonitoringAlertAttentionEventRow.__table__, MonitoringSignalReviewRow.__table__,
):
    _make_monitoring_fact_immutable(_monitoring_immutable_table)


# The account-commerce bridge stores attestations and one prior-use fact, never
# the profile values that caused a field to be satisfied.
class AccountProfileEvidenceRow(Base):
    __tablename__ = "account_profile_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_ref", "user_ref"),
            ("memberships.organization_id", "memberships.user_id"),
            name="fk_account_profile_evidence_membership", ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "owner_ref", "user_ref", "policy_address", "evidence_address",
            name="uq_account_profile_evidence_authority",
        ),
        CheckConstraint(_ContentAddress("policy_address"),
                        name="ck_account_profile_evidence_policy"),
        CheckConstraint(_ContentAddress("evidence_address"),
                        name="ck_account_profile_evidence_address"),
        CheckConstraint(_JsonIsValid("satisfied_fields_json"),
                        name="ck_account_profile_evidence_fields_json"),
        CheckConstraint(_Utf8SizeAtMost("satisfied_fields_json", 2048),
                        name="ck_account_profile_evidence_fields_size"),
        Index("ix_account_profile_evidence_current", "owner_ref", "user_ref",
              "policy_address", "attested_at", "profile_evidence_id"),
    )

    profile_evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    user_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    evidence_address: Mapped[str] = mapped_column(String(71), nullable=False)
    satisfied_fields_json: Mapped[str] = mapped_column(String(2048), nullable=False)
    attested_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class AccountTrialUseRow(Base):
    __tablename__ = "account_trial_uses"
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_ref", "user_ref"),
            ("memberships.organization_id", "memberships.user_id"),
            name="fk_account_trial_use_membership", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("profile_evidence_id",),
            ("account_profile_evidence.profile_evidence_id",),
            name="fk_account_trial_use_profile_evidence", ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_ref", "user_ref", "policy_address",
                         name="uq_account_trial_use_owner_user_policy"),
        UniqueConstraint("entitlement_event_id",
                         name="uq_account_trial_use_entitlement_event"),
        CheckConstraint(_ContentAddress("policy_address"),
                        name="ck_account_trial_use_policy"),
        CheckConstraint(_ContentAddress("eligibility_authority_address"),
                        name="ck_account_trial_use_eligibility"),
        CheckConstraint(_ContentAddress("prior_use_authority_address"),
                        name="ck_account_trial_use_prior_authority"),
        CheckConstraint(_ContentAddress("decision_basis_address"),
                        name="ck_account_trial_use_decision_basis"),
        CheckConstraint(_ClosedCode("entitlement_code"),
                        name="ck_account_trial_use_entitlement_code"),
        CheckConstraint("source_kind IN ('BETA_TRIAL','COUPON_REDEMPTION')",
                        name="ck_account_trial_use_source"),
        CheckConstraint("entitlement_transition = 'GRANT'",
                        name="ck_account_trial_use_transition"),
        CheckConstraint("valid_until > valid_from",
                        name="ck_account_trial_use_validity"),
        Index("ix_account_trial_use_owner_time", "owner_ref", "user_ref",
              "used_at", "trial_use_id"),
    )

    trial_use_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    user_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    profile_evidence_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    eligibility_authority_address: Mapped[str] = mapped_column(String(71), nullable=False)
    prior_use_authority_address: Mapped[str] = mapped_column(String(71), nullable=False)
    decision_basis_address: Mapped[str] = mapped_column(String(71), nullable=False)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    entitlement_transition: Mapped[str] = mapped_column(String(16), nullable=False)
    entitlement_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    valid_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


# The OPERATIONS tables deliberately use opaque owner references and only
# plane-local foreign keys. They cannot navigate into account or product data.
class PlatformPlanVersionRow(Base):
    __tablename__ = "platform_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_code", "version", name="uq_platform_plan_code_version"),
        CheckConstraint(_ClosedCode("plan_code"), name="ck_platform_plan_code"),
        CheckConstraint("version >= 1 AND amount_minor >= 0", name="ck_platform_plan_numbers"),
        CheckConstraint(_IsoCurrency("currency"), name="ck_platform_plan_currency"),
        CheckConstraint("billing_interval IN ('UNKNOWN','MONTH','YEAR')", name="ck_platform_plan_interval"),
        CheckConstraint("policy_state IN ('UNKNOWN','APPROVED','RETIRED')", name="ck_platform_plan_policy"),
        CheckConstraint(_ContentAddress("entitlement_set_address"), name="ck_platform_plan_entitlement"),
        CheckConstraint(_NullableContentAddress("test_provider_plan_address"), name="ck_platform_plan_test_provider"),
        CheckConstraint(_NullableContentAddress("live_provider_plan_address"), name="ck_platform_plan_live_provider"),
    )
    plan_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    entitlement_set_address: Mapped[str] = mapped_column(String(71), nullable=False)
    policy_state: Mapped[str] = mapped_column(String(16), nullable=False)
    test_provider_plan_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    live_provider_plan_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformCouponDefinitionRow(Base):
    __tablename__ = "platform_coupon_definitions"
    __table_args__ = (
        ForeignKeyConstraint(("plan_version_id",), ("platform_plan_versions.plan_version_id",),
                             name="fk_platform_coupon_plan", ondelete="RESTRICT"),
        UniqueConstraint("coupon_digest", name="uq_platform_coupon_digest"),
        CheckConstraint(_LowerHexDigest("coupon_digest"), name="ck_platform_coupon_digest"),
        CheckConstraint(_ContentAddress("policy_address"), name="ck_platform_coupon_policy"),
        CheckConstraint(_NullableContentAddress("trial_policy_address"), name="ck_platform_coupon_trial"),
        CheckConstraint(_NullableContentAddress("discount_policy_address"), name="ck_platform_coupon_discount"),
        CheckConstraint(_ClosedCode("entitlement_code"), name="ck_platform_coupon_entitlement_code"),
        CheckConstraint("entitlement_transition IN ('GRANT','RENEW','EXPIRE','REVOKE')",
                        name="ck_platform_coupon_entitlement_transition"),
        CheckConstraint(
            "(entitlement_effect_timing = 'FIXED_ABSOLUTE' AND "
            "entitlement_valid_from IS NOT NULL AND entitlement_duration_seconds IS NULL AND "
            "(entitlement_valid_until IS NULL OR entitlement_valid_until > entitlement_valid_from)) "
            "OR (entitlement_effect_timing = 'DYNAMIC_DURATION' AND "
            "entitlement_valid_from IS NULL AND entitlement_valid_until IS NULL AND "
            "entitlement_duration_seconds = 1296000 AND trial_policy_address IS NOT NULL AND "
            "discount_policy_address IS NULL AND entitlement_transition = 'GRANT')",
            name="ck_platform_coupon_entitlement_shape"),
        CheckConstraint("status IN ('UNKNOWN','ACTIVE','SUSPENDED','EXPIRED')", name="ck_platform_coupon_status"),
        CheckConstraint("max_redemptions IS NULL OR max_redemptions >= 1", name="ck_platform_coupon_max"),
        CheckConstraint("per_owner_limit >= 1 AND per_owner_limit <= 100", name="ck_platform_coupon_owner_limit"),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_platform_coupon_validity"),
        Index("ix_platform_coupon_status_validity", "status", "valid_from", "valid_until"),
    )
    coupon_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    coupon_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    trial_policy_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    discount_policy_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    entitlement_transition: Mapped[str] = mapped_column(String(16), nullable=False)
    entitlement_valid_from: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    entitlement_valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    valid_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_owner_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    # Additive 0049 fields remain last so fresh and upgraded catalogs are exact.
    entitlement_effect_timing: Mapped[str] = mapped_column(String(24), nullable=False)
    entitlement_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PlatformCouponRedemptionRow(Base):
    __tablename__ = "platform_coupon_redemptions"
    __table_args__ = (
        ForeignKeyConstraint(("coupon_id",), ("platform_coupon_definitions.coupon_id",),
                             name="fk_platform_redemption_coupon", ondelete="RESTRICT"),
        UniqueConstraint("coupon_id", "owner_ref", "policy_address", name="uq_platform_redemption_owner_policy"),
        CheckConstraint(_ContentAddress("policy_address"), name="ck_platform_redemption_policy"),
        CheckConstraint("status IN ('ACCEPTED','REVOKED')", name="ck_platform_redemption_status"),
        CheckConstraint(_ClosedCode("entitlement_code"), name="ck_platform_redemption_entitlement_code"),
        CheckConstraint("entitlement_transition IN ('GRANT','RENEW','EXPIRE','REVOKE')",
                        name="ck_platform_redemption_entitlement_transition"),
        CheckConstraint("entitlement_valid_until IS NULL OR entitlement_valid_until > entitlement_valid_from",
                        name="ck_platform_redemption_entitlement_validity"),
        Index("ix_platform_redemptions_owner_time", "owner_ref", "redeemed_at", "redemption_id"),
    )
    redemption_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    coupon_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    entitlement_transition: Mapped[str] = mapped_column(String(16), nullable=False)
    entitlement_valid_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    entitlement_valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


event.listen(PlatformCouponRedemptionRow.__table__, "after_create", DDL(
    "CREATE TRIGGER platform_coupon_redemptions_capacity BEFORE INSERT "
    "ON platform_coupon_redemptions WHEN NEW.status='ACCEPTED' AND ("
    "((SELECT max_redemptions FROM platform_coupon_definitions WHERE coupon_id=NEW.coupon_id) "
    "IS NOT NULL AND (SELECT count(*) FROM platform_coupon_redemptions WHERE "
    "coupon_id=NEW.coupon_id AND status='ACCEPTED') >= (SELECT max_redemptions FROM "
    "platform_coupon_definitions WHERE coupon_id=NEW.coupon_id)) OR "
    "((SELECT count(*) FROM platform_coupon_redemptions WHERE coupon_id=NEW.coupon_id "
    "AND owner_ref=NEW.owner_ref AND status='ACCEPTED') >= (SELECT per_owner_limit FROM "
    "platform_coupon_definitions WHERE coupon_id=NEW.coupon_id))) BEGIN "
    "SELECT RAISE(ABORT, 'coupon redemption capacity exhausted'); END"
).execute_if(dialect="sqlite"))
event.listen(PlatformCouponRedemptionRow.__table__, "after_create", DDL(
    "CREATE OR REPLACE FUNCTION platform_coupon_redemptions_capacity_fn() RETURNS trigger "
    "AS $$ DECLARE maximum integer; owner_maximum integer; BEGIN "
    "SELECT max_redemptions,per_owner_limit INTO maximum,owner_maximum FROM "
    "platform_coupon_definitions WHERE coupon_id=NEW.coupon_id FOR UPDATE; "
    "IF NEW.status='ACCEPTED' AND ((maximum IS NOT NULL AND (SELECT count(*) FROM "
    "platform_coupon_redemptions WHERE coupon_id=NEW.coupon_id AND status='ACCEPTED') >= maximum) "
    "OR ((SELECT count(*) FROM platform_coupon_redemptions WHERE coupon_id=NEW.coupon_id "
    "AND owner_ref=NEW.owner_ref AND status='ACCEPTED') >= owner_maximum)) THEN "
    "RAISE EXCEPTION 'coupon redemption capacity exhausted'; END IF; RETURN NEW; END; "
    "$$ LANGUAGE plpgsql"
).execute_if(dialect="postgresql"))
event.listen(PlatformCouponRedemptionRow.__table__, "after_create", DDL(
    "CREATE TRIGGER platform_coupon_redemptions_capacity BEFORE INSERT ON "
    "platform_coupon_redemptions FOR EACH ROW EXECUTE FUNCTION "
    "platform_coupon_redemptions_capacity_fn()"
).execute_if(dialect="postgresql"))


class PlatformBillingBindingRow(Base):
    __tablename__ = "platform_billing_bindings"
    __table_args__ = (
        UniqueConstraint("owner_ref", "mode", "merchant_address", "integration_address",
                         name="uq_platform_billing_owner_integration"),
        UniqueConstraint("binding_id", "owner_ref", "mode", "merchant_address",
                         "integration_address", "provider_customer_ref",
                         "provider_subscription_ref", name="uq_platform_billing_attribution"),
        UniqueConstraint("mode", "merchant_address", "integration_address",
                         "provider_customer_ref", "provider_subscription_ref",
                         name="uq_platform_billing_provider_binding"),
        CheckConstraint("mode IN ('TEST','LIVE')", name="ck_platform_billing_mode"),
        CheckConstraint("status IN ('UNKNOWN','PENDING','ACTIVE','PAUSED','CANCELLED')", name="ck_platform_billing_status"),
        CheckConstraint(_ContentAddress("merchant_address"), name="ck_platform_billing_merchant"),
        CheckConstraint(_ContentAddress("integration_address"), name="ck_platform_billing_integration"),
        Index("ix_platform_billing_owner_status", "owner_ref", "mode", "status", "binding_id"),
    )
    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    merchant_address: Mapped[str] = mapped_column(String(71), nullable=False)
    integration_address: Mapped[str] = mapped_column(String(71), nullable=False)
    provider_customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_subscription_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformBillingEventReceiptRow(Base):
    __tablename__ = "platform_billing_event_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ("binding_id", "owner_ref", "mode", "merchant_address", "integration_address",
             "provider_customer_ref", "provider_subscription_ref"),
            ("platform_billing_bindings.binding_id", "platform_billing_bindings.owner_ref",
             "platform_billing_bindings.mode", "platform_billing_bindings.merchant_address",
             "platform_billing_bindings.integration_address",
             "platform_billing_bindings.provider_customer_ref",
             "platform_billing_bindings.provider_subscription_ref"),
            name="fk_platform_receipt_binding_attribution", ondelete="RESTRICT"),
        UniqueConstraint("mode", "merchant_address", "integration_address", "provider_event_ref",
                         name="uq_platform_receipt_provider_event_boundary"),
        CheckConstraint("mode IN ('TEST','LIVE')", name="ck_platform_receipt_mode"),
        CheckConstraint("event_type IN ('SUBSCRIPTION_AUTHENTICATED','SUBSCRIPTION_ACTIVATED','SUBSCRIPTION_CHARGED','SUBSCRIPTION_PAUSED','SUBSCRIPTION_CANCELLED','PAYMENT_CAPTURED','PAYMENT_FAILED')", name="ck_platform_receipt_type"),
        CheckConstraint("event_state IN ('VERIFIED','REJECTED','UNKNOWN')", name="ck_platform_receipt_state"),
        CheckConstraint(_LowerHexDigest("raw_body_digest"), name="ck_platform_receipt_digest"),
        CheckConstraint("facts_schema_version = 1", name="ck_platform_receipt_facts_version"),
        CheckConstraint("amount_minor IS NULL OR amount_minor >= 0", name="ck_platform_receipt_amount"),
        CheckConstraint(_IsoCurrency("currency", nullable=True), name="ck_platform_receipt_currency"),
        CheckConstraint(_NullableClosedCode("entitlement_code"), name="ck_platform_receipt_entitlement_code"),
        CheckConstraint("entitlement_transition IS NULL OR entitlement_transition IN ('GRANT','RENEW','EXPIRE','REVOKE')",
                        name="ck_platform_receipt_entitlement_transition"),
        CheckConstraint(_NullableContentAddress("entitlement_policy_address"),
                        name="ck_platform_receipt_entitlement_policy"),
        CheckConstraint("entitlement_valid_until IS NULL OR (entitlement_valid_from IS NOT NULL AND "
                        "entitlement_valid_until > entitlement_valid_from)",
                        name="ck_platform_receipt_entitlement_validity"),
        CheckConstraint("(entitlement_code IS NULL AND entitlement_transition IS NULL AND "
                        "entitlement_policy_address IS NULL AND entitlement_valid_from IS NULL AND "
                        "entitlement_valid_until IS NULL) OR (entitlement_code IS NOT NULL AND "
                        "entitlement_transition IS NOT NULL AND entitlement_policy_address IS NOT NULL AND "
                        "entitlement_valid_from IS NOT NULL)", name="ck_platform_receipt_entitlement_envelope"),
        Index("ix_platform_receipts_owner_time", "owner_ref", "received_at", "receipt_id"),
    )
    receipt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    merchant_address: Mapped[str] = mapped_column(String(71), nullable=False)
    integration_address: Mapped[str] = mapped_column(String(71), nullable=False)
    provider_customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_event_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_state: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_body_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    facts_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    provider_payment_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_subscription_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_invoice_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entitlement_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entitlement_transition: Mapped[str | None] = mapped_column(String(16), nullable=True)
    entitlement_policy_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    entitlement_valid_from: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    entitlement_valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformEntitlementEventRow(Base):
    __tablename__ = "platform_entitlement_events"
    __table_args__ = (
        UniqueConstraint("source_kind", "source_ref", name="uq_platform_entitlement_source"),
        CheckConstraint(_ClosedCode("entitlement_code"), name="ck_platform_entitlement_code"),
        CheckConstraint("mode IN ('TEST','LIVE','INTERNAL')", name="ck_platform_entitlement_mode"),
        CheckConstraint("source_kind IN ('BILLING_RECEIPT','COUPON_REDEMPTION','COMPLIMENTARY_GRANT','BETA_TRIAL')", name="ck_platform_entitlement_source"),
        CheckConstraint("transition IN ('GRANT','RENEW','EXPIRE','REVOKE')", name="ck_platform_entitlement_transition"),
        CheckConstraint(_ContentAddress("policy_address"), name="ck_platform_entitlement_policy"),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_platform_entitlement_validity"),
        Index("ix_platform_entitlement_reduce", "owner_ref", "entitlement_code", "mode", "effective_at", "event_id"),
    )
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    transition: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    valid_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    effective_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformCurrentEntitlementRow(Base):
    __tablename__ = "platform_current_entitlements"
    __table_args__ = (
        ForeignKeyConstraint(("source_event_id",), ("platform_entitlement_events.event_id",),
                             name="fk_platform_current_event", ondelete="RESTRICT"),
        CheckConstraint(_ClosedCode("entitlement_code"), name="ck_platform_current_code"),
        CheckConstraint("mode IN ('TEST','LIVE','INTERNAL')", name="ck_platform_current_mode"),
        CheckConstraint("state IN ('UNKNOWN','ACTIVE','INACTIVE')", name="ck_platform_current_state"),
        CheckConstraint("projection_version >= 1", name="ck_platform_current_version"),
        Index("ix_platform_current_owner_state", "owner_ref", "state", "entitlement_code"),
    )
    owner_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    entitlement_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rebuilt_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformComplimentaryEntitlementGrantRow(Base):
    __tablename__ = "platform_complimentary_entitlement_grants"
    __table_args__ = (
        ForeignKeyConstraint(("operator_binding_id",), ("platform_operator_bindings.binding_id",),
                             name="fk_platform_grant_operator", ondelete="RESTRICT"),
        CheckConstraint(_ClosedCode("entitlement_code"), name="ck_platform_grant_code"),
        CheckConstraint("action IN ('GRANT','REVOKE')", name="ck_platform_grant_action"),
        CheckConstraint(_ContentAddress("policy_address"), name="ck_platform_grant_policy"),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_platform_grant_validity"),
        Index("ix_platform_grants_owner_time", "owner_ref", "created_at", "grant_id"),
    )
    grant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_address: Mapped[str] = mapped_column(String(71), nullable=False)
    valid_from: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    operator_binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformAnalyticsSubjectRow(Base):
    __tablename__ = "platform_analytics_subjects"
    __table_args__ = (
        UniqueConstraint("subject_id", name="uq_platform_analytics_subject"),
        CheckConstraint(_LowerHexDigest("pseudonym_digest"), name="ck_platform_analytics_pseudonym"),
        Index("ix_platform_analytics_owner", "owner_ref", "subject_id"),
    )
    owner_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    pseudonym_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    exported_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class PlatformAnalyticsEventRow(Base):
    __tablename__ = "platform_analytics_events"
    __table_args__ = (
        ForeignKeyConstraint(("owner_ref", "subject_id"),
                             ("platform_analytics_subjects.owner_ref", "platform_analytics_subjects.subject_id"),
                             name="fk_platform_analytics_subject", ondelete="RESTRICT"),
        CheckConstraint("schema_version = 1", name="ck_platform_analytics_schema"),
        CheckConstraint("event_type IN ('SESSION_STARTED','WORKSPACE_OPENED','RESEARCH_STARTED','RESEARCH_COMPLETED','DEPLOYMENT_FLOW_OPENED','ERROR_SHOWN')", name="ck_platform_analytics_type"),
        CheckConstraint("surface IN ('SHELL','WORKSPACE','RESEARCH','DEPLOYMENT')", name="ck_platform_analytics_surface"),
        CheckConstraint("outcome IN ('SUCCEEDED','FAILED','ABANDONED','UNKNOWN')", name="ck_platform_analytics_outcome"),
        CheckConstraint("dimension_a IS NULL OR dimension_a IN ('DESKTOP','WEB','EMPTY','RETRY','MANUAL')",
                        name="ck_platform_analytics_dimension_a"),
        CheckConstraint("dimension_b IS NULL OR dimension_b IN ('DESKTOP','WEB','EMPTY','RETRY','MANUAL')",
                        name="ck_platform_analytics_dimension_b"),
        Index("ix_platform_analytics_event_rollup", "event_type", "occurred_at", "event_id"),
        Index("ix_platform_analytics_owner_time", "owner_ref", "occurred_at", "event_id"),
    )
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    surface: Mapped[str] = mapped_column(String(24), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    dimension_a: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dimension_b: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformSupportRequestRow(Base):
    __tablename__ = "platform_support_requests"
    __table_args__ = (
        CheckConstraint("category IN ('ACCOUNT_ACCESS','BILLING','PRODUCT_USAGE','DATA_QUALITY','OTHER_STRUCTURED')", name="ck_platform_support_category"),
        CheckConstraint("schema_version = 1", name="ck_platform_support_schema"),
        CheckConstraint("detail_code IN ('LOGIN_FAILED','PAYMENT_FAILED','PRODUCT_GUIDANCE','DATA_MISMATCH','OTHER_DECLARED')",
                        name="ck_platform_support_detail"),
        CheckConstraint("status IN ('OPEN','IN_REVIEW','WAITING_CUSTOMER','RESOLVED','CLOSED')", name="ck_platform_support_status"),
        UniqueConstraint("request_id", "owner_ref", name="uq_platform_support_request_owner"),
        Index("ix_platform_support_owner_status", "owner_ref", "status", "updated_at", "request_id"),
    )
    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    detail_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    exported_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class PlatformSupportReplyRow(Base):
    __tablename__ = "platform_support_replies"
    __table_args__ = (
        ForeignKeyConstraint(("request_id", "owner_ref"),
                             ("platform_support_requests.request_id", "platform_support_requests.owner_ref"),
                             name="fk_platform_support_reply_request_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(("operator_binding_id",), ("platform_operator_bindings.binding_id",),
                             name="fk_platform_support_reply_operator", ondelete="RESTRICT"),
        CheckConstraint("schema_version = 1", name="ck_platform_support_reply_schema"),
        CheckConstraint("response_code IN ('ACKNOWLEDGED','NEEDS_ACCOUNT_ACTION','BILLING_REVIEWED',"
                        "'RESOLVED_WITH_GUIDANCE','CANNOT_ASSIST')", name="ck_platform_support_response"),
        Index("ix_platform_support_replies_request", "request_id", "created_at", "reply_id"),
    )
    reply_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    response_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class PlatformOperatorBindingRow(Base):
    __tablename__ = "platform_operator_bindings"
    __table_args__ = (
        UniqueConstraint("binding_id", name="uq_platform_operator_binding"),
        CheckConstraint("operator_slot = 'FOUNDER'", name="ck_platform_operator_founder_slot"),
        CheckConstraint("status IN ('UNKNOWN','ACTIVE','REVOKED')", name="ck_platform_operator_status"),
        CheckConstraint(_ContentAddress("permission_profile_address"), name="ck_platform_operator_permissions"),
        CheckConstraint(_ContentAddress("bootstrap_evidence_address"), name="ck_platform_operator_bootstrap"),
        CheckConstraint("(status = 'REVOKED' AND revoked_at IS NOT NULL) OR (status <> 'REVOKED' AND revoked_at IS NULL)", name="ck_platform_operator_revocation"),
    )
    operator_slot: Mapped[str] = mapped_column(String(16), primary_key=True)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    principal_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    permission_profile_address: Mapped[str] = mapped_column(String(71), nullable=False)
    bootstrap_evidence_address: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class PlatformOperatorAuditEventRow(Base):
    __tablename__ = "platform_operator_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(("operator_binding_id",), ("platform_operator_bindings.binding_id",),
                             name="fk_platform_audit_operator", ondelete="RESTRICT"),
        CheckConstraint("permission_class IN ('BILLING_READ','SUPPORT_WRITE','ENTITLEMENT_WRITE','AUDIT_WRITE')", name="ck_platform_audit_permission"),
        CheckConstraint("action_class IN ('VIEW_AGGREGATE','REPLY_SUPPORT','ISSUE_COMPLIMENTARY','REVOKE_COMPLIMENTARY','CHANGE_BINDING')", name="ck_platform_audit_action"),
        CheckConstraint("target_class IN ('SUBSCRIPTION','SUPPORT_REQUEST','ENTITLEMENT','OPERATOR_BINDING')", name="ck_platform_audit_target"),
        CheckConstraint("outcome IN ('SUCCEEDED','REFUSED','FAILED')", name="ck_platform_audit_outcome"),
        CheckConstraint("length(target_redacted_id) BETWEEN 16 AND 64", name="ck_platform_audit_redacted_length"),
        CheckConstraint(_LowerHexDigest("target_redacted_id"), name="ck_platform_audit_redacted_digest"),
        Index("ix_platform_audit_time", "occurred_at", "audit_event_id"),
    )
    audit_event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    operator_binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    permission_class: Mapped[str] = mapped_column(String(24), nullable=False)
    action_class: Mapped[str] = mapped_column(String(32), nullable=False)
    target_class: Mapped[str] = mapped_column(String(24), nullable=False)
    target_redacted_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


_OPERATIONS_FORBIDDEN_SENTINELS = (
    "strategy", "graph", "component", "parameter", "annotation", "dataset",
    "research", "monitoring", "alert", "signal", "instrument", "nifty",
    "banknifty", "broker", "provider_account", "credential", "secret", "token", "position", "order",
    "trade", "balance", "capital", "pnl", "profit", "loss", "raw_request",
    "raw_response", "raw_webhook", "card", "upi", "free_text", "attachment",
    "diagnostic",
)
_OPERATIONS_PRIVACY_SYSTEM_COLUMNS = frozenset({"event_type", "surface"})


def _install_operations_privacy_guard(table) -> None:
    textual = tuple(column.name for column in table.columns
                    if isinstance(column.type, String)
                    and column.name not in _OPERATIONS_PRIVACY_SYSTEM_COLUMNS)
    sqlite_terms = " OR ".join(
        f"instr(lower(COALESCE(NEW.{column},'')), '{term}') > 0"
        for column in textual for term in _OPERATIONS_FORBIDDEN_SENTINELS)
    for operation in ("INSERT", "UPDATE"):
        event.listen(table, "after_create", DDL(
            f"CREATE TRIGGER {table.name}_privacy_{operation.lower()} BEFORE {operation} "
            f"ON {table.name} WHEN {sqlite_terms} BEGIN "
            "SELECT RAISE(ABORT, 'platform operations forbidden content'); END"
        ).execute_if(dialect="sqlite"))
    pg_terms = " OR ".join(
        f"position('{term}' in lower(COALESCE(NEW.{column},''))) > 0"
        for column in textual for term in _OPERATIONS_FORBIDDEN_SENTINELS)
    function = f"{table.name}_privacy_guard_fn"
    event.listen(table, "after_create", DDL(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        f"IF {pg_terms} THEN RAISE EXCEPTION 'platform operations forbidden content'; "
        "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {table.name}_privacy_guard BEFORE INSERT OR UPDATE ON {table.name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    ).execute_if(dialect="postgresql"))


def _install_entitlement_source_exact_guard(table) -> None:
    event.listen(table, "after_create", DDL(
        "CREATE TRIGGER platform_entitlement_events_source_exact BEFORE INSERT ON "
        "platform_entitlement_events WHEN NOT ("
        "(NEW.source_kind='BILLING_RECEIPT' AND NEW.mode IN ('TEST','LIVE') AND EXISTS "
        "(SELECT 1 FROM platform_billing_event_receipts s WHERE s.receipt_id=NEW.source_ref "
        "AND s.owner_ref=NEW.owner_ref AND s.mode=NEW.mode AND s.event_state='VERIFIED' "
        "AND s.entitlement_code IS NEW.entitlement_code AND s.entitlement_transition IS NEW.transition "
        "AND s.entitlement_policy_address IS NEW.policy_address AND s.entitlement_valid_from IS NEW.valid_from "
        "AND s.entitlement_valid_until IS NEW.valid_until)) OR "
        "(NEW.source_kind='COUPON_REDEMPTION' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM platform_coupon_redemptions s WHERE s.redemption_id=NEW.source_ref "
        "AND s.owner_ref=NEW.owner_ref AND s.status='ACCEPTED' AND s.entitlement_code IS NEW.entitlement_code "
        "AND s.entitlement_transition IS NEW.transition AND s.policy_address IS NEW.policy_address "
        "AND s.entitlement_valid_from IS NEW.valid_from AND s.entitlement_valid_until IS NEW.valid_until)) OR "
        "(NEW.source_kind='COMPLIMENTARY_GRANT' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM platform_complimentary_entitlement_grants s WHERE s.grant_id=NEW.source_ref "
        "AND s.owner_ref=NEW.owner_ref AND s.entitlement_code IS NEW.entitlement_code "
        "AND s.action IS NEW.transition AND s.policy_address IS NEW.policy_address "
        "AND s.valid_from IS NEW.valid_from AND s.valid_until IS NEW.valid_until)) OR "
        "(NEW.source_kind='BETA_TRIAL' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM account_trial_uses s WHERE s.trial_use_id=NEW.source_ref "
        "AND s.source_kind='BETA_TRIAL' AND s.owner_ref=NEW.owner_ref "
        "AND s.entitlement_event_id=NEW.event_id AND s.entitlement_code IS NEW.entitlement_code "
        "AND s.entitlement_transition IS NEW.transition AND s.policy_address IS NEW.policy_address "
        "AND s.valid_from IS NEW.valid_from AND s.valid_until IS NEW.valid_until))) BEGIN "
        "SELECT RAISE(ABORT, 'entitlement event source mismatch'); END"
    ).execute_if(dialect="sqlite"))
    event.listen(table, "after_create", DDL(
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
        "AND s.owner_ref=NEW.owner_ref AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
        "AND s.action IS NOT DISTINCT FROM NEW.transition AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
        "AND s.valid_from IS NOT DISTINCT FROM NEW.valid_from AND s.valid_until IS NOT DISTINCT FROM NEW.valid_until)) OR "
        "(NEW.source_kind='BETA_TRIAL' AND NEW.mode='INTERNAL' AND EXISTS "
        "(SELECT 1 FROM account_trial_uses s WHERE s.trial_use_id=NEW.source_ref "
        "AND s.source_kind='BETA_TRIAL' AND s.owner_ref=NEW.owner_ref "
        "AND s.entitlement_event_id=NEW.event_id "
        "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
        "AND s.entitlement_transition IS NOT DISTINCT FROM NEW.transition "
        "AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
        "AND s.valid_from IS NOT DISTINCT FROM NEW.valid_from "
        "AND s.valid_until IS NOT DISTINCT FROM NEW.valid_until))) "
        "THEN RAISE EXCEPTION 'entitlement event source mismatch'; END IF; RETURN NEW; END; "
        "$$ LANGUAGE plpgsql"
    ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        "CREATE TRIGGER platform_entitlement_events_source_exact BEFORE INSERT ON "
        "platform_entitlement_events FOR EACH ROW EXECUTE FUNCTION "
        "platform_entitlement_events_source_exact_fn()"
    ).execute_if(dialect="postgresql"))


for _operations_immutable_table in (
    AccountProfileEvidenceRow.__table__, AccountTrialUseRow.__table__,
    PlatformPlanVersionRow.__table__, PlatformCouponRedemptionRow.__table__,
    PlatformBillingEventReceiptRow.__table__, PlatformEntitlementEventRow.__table__,
    PlatformComplimentaryEntitlementGrantRow.__table__, PlatformAnalyticsEventRow.__table__,
    PlatformSupportReplyRow.__table__, PlatformOperatorBindingRow.__table__,
    PlatformOperatorAuditEventRow.__table__,
):
    _make_monitoring_fact_immutable(_operations_immutable_table)

_install_entitlement_source_exact_guard(PlatformEntitlementEventRow.__table__)

for _operations_private_table in (
    AccountProfileEvidenceRow.__table__, AccountTrialUseRow.__table__,
    PlatformPlanVersionRow.__table__, PlatformCouponDefinitionRow.__table__,
    PlatformCouponRedemptionRow.__table__, PlatformBillingBindingRow.__table__,
    PlatformBillingEventReceiptRow.__table__, PlatformEntitlementEventRow.__table__,
    PlatformCurrentEntitlementRow.__table__, PlatformComplimentaryEntitlementGrantRow.__table__,
    PlatformAnalyticsSubjectRow.__table__, PlatformAnalyticsEventRow.__table__,
    PlatformSupportRequestRow.__table__, PlatformSupportReplyRow.__table__,
    PlatformOperatorBindingRow.__table__, PlatformOperatorAuditEventRow.__table__,
):
    _install_operations_privacy_guard(_operations_private_table)


def install_platform_operations_postgresql_security(_metadata, connection, **_kw) -> None:
    """Install least-privilege runtime roles for migration and fresh create_all."""
    if connection.dialect.name != "postgresql":
        return
    roles = ("operations_billing", "operations_analytics",
             "operations_support", "operations_operator")
    for role in roles:
        connection.exec_driver_sql(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            f"'{role}') THEN CREATE ROLE {role} NOLOGIN; END IF; END $$")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {role}")
    operations_tables = tuple(
        table.name for table in Base.metadata.sorted_tables
        if table.name.startswith("platform_"))
    connection.exec_driver_sql(
        f"REVOKE ALL ON {','.join(operations_tables)} FROM PUBLIC")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_plan_versions,platform_coupon_definitions,"
        "platform_billing_bindings,platform_billing_event_receipts,"
        "platform_entitlement_events,platform_complimentary_entitlement_grants TO operations_billing")
    connection.exec_driver_sql(
        "GRANT SELECT,INSERT ON platform_coupon_redemptions TO operations_billing")
    connection.exec_driver_sql(
        "GRANT SELECT,INSERT,UPDATE,DELETE ON platform_current_entitlements TO operations_billing")
    connection.exec_driver_sql("GRANT INSERT ON platform_analytics_events TO operations_analytics")
    connection.exec_driver_sql(
        "GRANT SELECT,INSERT,UPDATE ON platform_support_requests TO operations_support")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_support_replies TO operations_support")
    connection.exec_driver_sql(
        "CREATE OR REPLACE VIEW platform_analytics_event_counts AS "
        "SELECT schema_version,event_type,surface,outcome,count(*) AS event_count "
        "FROM platform_analytics_events GROUP BY schema_version,event_type,surface,outcome")
    connection.exec_driver_sql(
        "CREATE OR REPLACE VIEW platform_operator_entitlement_counts AS "
        "SELECT entitlement_code,mode,state,count(*) AS entitlement_count "
        "FROM platform_current_entitlements GROUP BY entitlement_code,mode,state")
    connection.exec_driver_sql(
        "CREATE OR REPLACE VIEW platform_operator_support_counts AS "
        "SELECT category,detail_code,status,count(*) AS request_count "
        "FROM platform_support_requests GROUP BY category,detail_code,status")
    connection.exec_driver_sql(
        "REVOKE ALL ON platform_analytics_event_counts,platform_operator_entitlement_counts,"
        "platform_operator_support_counts FROM PUBLIC")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_analytics_event_counts TO operations_analytics")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_operator_entitlement_counts,platform_operator_support_counts "
        "TO operations_operator")
    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION platform_append_operator_audit("
        "p_audit_event_id varchar,p_operator_binding_id varchar,p_permission_class varchar,"
        "p_action_class varchar,p_target_class varchar,p_target_redacted_id varchar,"
        "p_outcome varchar,p_occurred_at timestamp) RETURNS void LANGUAGE plpgsql "
        "SECURITY DEFINER SET search_path = public AS $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM platform_operator_bindings WHERE "
        "binding_id=p_operator_binding_id AND operator_slot='FOUNDER' AND status='ACTIVE') "
        "THEN RAISE EXCEPTION 'active founder operator binding required'; END IF; "
        "INSERT INTO platform_operator_audit_events(audit_event_id,operator_binding_id,"
        "permission_class,action_class,target_class,target_redacted_id,outcome,occurred_at) "
        "VALUES(p_audit_event_id,p_operator_binding_id,p_permission_class,p_action_class,"
        "p_target_class,p_target_redacted_id,p_outcome,p_occurred_at); END $$")
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION platform_append_operator_audit(varchar,varchar,varchar,varchar,"
        "varchar,varchar,varchar,timestamp) FROM PUBLIC")
    connection.exec_driver_sql(
        "GRANT EXECUTE ON FUNCTION platform_append_operator_audit(varchar,varchar,varchar,varchar,"
        "varchar,varchar,varchar,timestamp) TO operations_operator")


event.listen(Base.metadata, "after_create", install_platform_operations_postgresql_security)


# Plane-local delivery tables are registered last so they cannot accidentally
# acquire relationships to execution-domain tables. Scope references are values.
from app.events.outbox import define_outbox_models as _define_outbox_models

EXECUTION_OUTBOX_MODELS = _define_outbox_models(Base, "execution")


class WorkspaceResearchSettingsRevision(Base):
    """Append-only research preferences; never runtime execution configuration."""
    __tablename__ = "workspace_research_settings_revisions"
    owner_id: Mapped[str] = mapped_column(ForeignKey("organizations.organization_id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_workspace_research_settings_request"),
        CheckConstraint("revision >= 1", name="ck_workspace_research_settings_revision"),
        CheckConstraint(_ContentAddress("content_address"), name="ck_workspace_research_settings_address"),
        CheckConstraint(_JsonIsValid("document_json"), name="ck_workspace_research_settings_json"),
        CheckConstraint(_Utf8SizeAtMost("document_json", 4096), name="ck_workspace_research_settings_size"),
    )


class StrategyResearchSettingsRevision(Base):
    """Sparse explicit intent; disabling retains intent but inherits future defaults."""
    __tablename__ = "strategy_research_settings_revisions"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "graph_identifier"],
                             ["graph_artifacts.owner_id", "graph_artifacts.identifier"], ondelete="RESTRICT"),
        UniqueConstraint("owner_id", "graph_identifier", "request_id", name="uq_strategy_research_settings_request"),
        CheckConstraint("revision >= 1", name="ck_strategy_research_settings_revision"),
        CheckConstraint(_ContentAddress("content_address"), name="ck_strategy_research_settings_address"),
        CheckConstraint(_JsonIsValid("document_json"), name="ck_strategy_research_settings_json"),
        CheckConstraint(_Utf8SizeAtMost("document_json", 4096), name="ck_strategy_research_settings_size"),
    )


for _research_settings_table in (WorkspaceResearchSettingsRevision.__table__, StrategyResearchSettingsRevision.__table__):
    _make_monitoring_fact_immutable(_research_settings_table)
