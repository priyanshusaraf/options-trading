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
    String,
    Text,
    UniqueConstraint,
    event,
    false,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement


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


def _install_postgresql_immutable_trigger(table, message: str) -> None:
    """Make append-only facts immutable on PostgreSQL as well as SQLite."""
    function_name = f"{table.name}_refuse_mutation"
    event.listen(
        table,
        "after_create",
        DDL(
            f"CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '{message}'; END; $$ LANGUAGE plpgsql"
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
    exchange: Mapped[str] = mapped_column(String(8))        # NFO/BFO/MCX/NCDEX
    # product family + originating strategy (Phase 0 foundation)
    segment: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Content hash of the strategy that executed this row (Phase D). NULL is
    # meaningful and is NOT the same as 'unknown': NULL means the row predates
    # the column and is genuinely unattributable, 'unknown' means a strategy was
    # running but could not be identified. Same three-value rule as build_sha —
    # never collapse the two.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[dt.date] = mapped_column(Date)
    lot_size: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)

    entry_premium: Mapped[float] = mapped_column(Float)
    entry_charges: Mapped[float] = mapped_column(Float)
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
        }


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_owner_account", "owner_id", "broker_account_id"),
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
    exchange: Mapped[str] = mapped_column(String(8))
    # product family + originating strategy (Phase 0 foundation)
    segment: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Content hash of the strategy that executed this row (Phase D). NULL is
    # meaningful and is NOT the same as 'unknown': NULL means the row predates
    # the column and is genuinely unattributable, 'unknown' means a strategy was
    # running but could not be identified. Same three-value rule as build_sha —
    # never collapse the two.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[dt.date] = mapped_column(Date)
    qty: Mapped[int] = mapped_column(Integer)

    entry_premium: Mapped[float] = mapped_column(Float)
    entry_cost: Mapped[float] = mapped_column(Float)
    entry_spot: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)

    exit_premium: Mapped[float] = mapped_column(Float)
    exit_charges: Mapped[float] = mapped_column(Float)
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
            "exit_premium": round(self.exit_premium, 2),
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
            "exit_price_estimated": bool(self.exit_price_estimated),
            "mfe": round(self.mfe or 0.0, 2),
            "mae": round(self.mae or 0.0, 2),
        }


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
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PRIVATE", server_default="PRIVATE")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


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
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: The exact immutable artefact. An edit mints a new version and cannot inherit this row.
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Recorded at activation, re-derived on every reload, and re-checked against the
    #: resolved adapter at the authority gate. Three independent places, on purpose.
    graph_content_address: Mapped[str] = mapped_column(String(71), nullable=False)
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


# Plane-local delivery tables are registered last so they cannot accidentally
# acquire relationships to execution-domain tables. Scope references are values.
from app.events.outbox import define_outbox_models as _define_outbox_models

EXECUTION_OUTBOX_MODELS = _define_outbox_models(Base, "execution")
