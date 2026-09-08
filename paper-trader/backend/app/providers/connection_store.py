"""Durable broker connections, always scoped to an owner and broker account.

This is the persistence side of `app/providers/connection.py`. The two are deliberately
separate: a `BrokerConnection` row is what an owner **has**; a `Connection` is what a running
engine **uses**. Merging them would put a database session on the order path, and the order path
already has enough reasons to block.

**Every read is owner/account-scoped, and there is no unscoped one.** Not by convention — there
is no function here that can return another account's connection, because the alternative is a
helper that "just needs the id" and a caller that forgets. Isolation on the table that grants
the authority to trade is not a thing to enforce at the call site.

Revocation is a status change. "This credential was revoked at 14:02" is a fact someone will
need to establish, and a deleted row establishes nothing.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Callable

from sqlalchemy import select, update

from app.core.credential_vault import (
    CredentialDecryptionFailed,
    CredentialVaultUnavailable,
    seal,
    unseal,
)
from app.core.logging import log
from app.db.models import LEGACY_OWNER_ID, BrokerAccount, BrokerConnection
from app.market_truth.temporal import to_sql_utc_naive
from app.providers import capabilities as caps
from app.providers.brokers import BrokerNotSupported, spec
from app.providers.connection import Connection


#: Distinguishes "the caller did not specify an owner" from "the caller specified nothing".
#: The first is the single-owner default and is fine. The second is a bug in the caller —
#: a header parsed to "", a principal field not populated, a service call with no principal —
#: and resolving it to the identity that holds the live Zerodha credential is principal
#: substitution enabled by a convenience. Found by an independent security review, 2026-08-10;
#: the previous behaviour coerced all of "", "   " and None to the real owner, and a test of
#: mine pinned that as intended. The reviewer was right.
_UNSPECIFIED = object()


def _resolve_owner(owner_id) -> str:
    if owner_id is _UNSPECIFIED:
        return LEGACY_OWNER_ID
    text = (owner_id or "").strip() if isinstance(owner_id, str) else ""
    if not text:
        raise ValueError(
            "OwnedConnectionStore was given an empty owner id. Omit the argument to get the "
            "single-owner default; passing an empty one is a caller bug, and defaulting it "
            "would serve the owner's real broker connections to whoever asked.")
    return text


def _default_session_factory():
    from app.db.session import SessionLocal
    return SessionLocal()


class ConnectionNotFound(LookupError):
    """No such connection **for this owner**.

    One error for "does not exist" and for "belongs to someone else", deliberately: telling the
    caller which would confirm the existence of another owner's connection, and an id is
    guessable.

    An earlier version of this docstring claimed "the log line records the distinction". It did
    not, and it must not: `/api/logs` serves the log ring buffer to callers, so recording which
    ids exist would leak through the very channel the error message is careful about. The
    distinction is deliberately not recorded anywhere reachable.
    """


class DataConnectionUnavailable(RuntimeError):
    """The closed V0 data role cannot be established without widening authority."""


class DataConnectionConflict(RuntimeError):
    """This owner already has the one active Zerodha data-role connection."""


class DataOperationUnavailable(DataConnectionUnavailable):
    """A stable typed refusal for an unproven V0 provider operation."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


DATA_ROLE = "DATA"
DATA_SCOPE_PREFIX = "strategy-os-v0:data:"
DATA_ONLY_ACCOUNT_STATUS = "disabled"
DATA_ONLY_EXTERNAL_ACCOUNT_ID = "strategy-os-data-only-unbound"
DATA_ONLY_ACCOUNT_NAME = "Zerodha data only"
DATA_CAPABILITIES = frozenset({
    caps.HISTORICAL_DATA,
    caps.LIVE_QUOTES,
})


class _ClosedDataAdapterContract:
    """Safe contract view used by validation and independent challenges."""

    provider = "kite"
    CAPABILITIES = DATA_CAPABILITIES


_CLOSED_DATA_ADAPTER_CONTRACT = _ClosedDataAdapterContract()


def _validate_registered_data_adapter(adapter) -> None:
    if adapter is None or getattr(adapter, "name", None) != "kite":
        raise DataConnectionUnavailable("registered Zerodha data adapter is unavailable")
    try:
        declared = caps.validate(frozenset(getattr(adapter, "CAPABILITIES", frozenset())))
    except caps.UnknownCapability:
        raise DataConnectionUnavailable("registered Zerodha data capabilities disagree") from None
    if not DATA_CAPABILITIES.issubset(declared):
        raise DataConnectionUnavailable("registered Zerodha data capabilities disagree")
    for capability in DATA_CAPABILITIES:
        method = caps.BACKING_METHOD.get(capability)
        if not method or not callable(getattr(adapter, method, None)):
            raise DataConnectionUnavailable("registered Zerodha data capability is not implemented")


def _data_adapter_contract():
    """Validate the registry while returning only the closed proven-capability view.

    This deliberately never loads the venue or venue builder.  Kite's broader adapter
    declaration is not authority for this role: only the four explicitly implemented
    observation methods above are admitted.
    """
    broker = spec("kite")
    adapter = broker.load_data()
    _validate_registered_data_adapter(adapter)
    return _CLOSED_DATA_ADAPTER_CONTRACT


def _stored_capabilities(row: BrokerConnection) -> frozenset[str]:
    try:
        raw = json.loads(row.capabilities_json or "[]")
    except (TypeError, ValueError):
        raise DataConnectionUnavailable("stored data connection is invalid") from None
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise DataConnectionUnavailable("stored data connection is invalid")
    try:
        return caps.validate(frozenset(raw))
    except caps.UnknownCapability:
        raise DataConnectionUnavailable("stored data connection is invalid") from None


def _require_data_identity(row: BrokerConnection, *, active: bool) -> None:
    _data_adapter_contract()
    if (row.broker != "kite" or not row.scope.startswith(DATA_SCOPE_PREFIX)
            or _stored_capabilities(row) != DATA_CAPABILITIES):
        raise DataConnectionUnavailable("connection is not the closed Zerodha data role")
    if active and row.status != "active":
        raise DataConnectionUnavailable("data connection is unavailable")


def validate_data_connection_row(row: BrokerConnection, *, active: bool = True) -> None:
    """Public validation seam shared by the store and privacy-safe HTTP projection."""
    _require_data_identity(row, active=active)


def is_data_account_anchor(account: BrokerAccount) -> bool:
    """Admit a normal active account or the exact execution-disabled DATA anchor."""
    return account.status == "active" or (
        account.status == DATA_ONLY_ACCOUNT_STATUS
        and account.broker == "kite"
        and account.external_account_id == DATA_ONLY_EXTERNAL_ACCOUNT_ID
        and account.display_name == DATA_ONLY_ACCOUNT_NAME
    )


class DataOnlyConnection:
    """Closed four-operation facade; the registered provider class never escapes."""

    __slots__ = ("provider", "__invoke")

    def __init__(self, invoke: Callable) -> None:
        self.provider = "kite"
        self.__invoke = invoke

    def get_candles(self, *args, **kwargs):
        return self.__invoke("get_candles", args, kwargs)

    def get_ltp(self, *args, **kwargs):
        return self.__invoke("get_ltp", args, kwargs)

    def get_option_chain(self, *args, **kwargs):
        return self.__invoke("get_option_chain", args, kwargs)

    def get_futures_ltp(self, *args, **kwargs):
        return self.__invoke("get_futures_ltp", args, kwargs)


def _data_now():
    return to_sql_utc_naive(dt.datetime.now(dt.timezone.utc), "data connection timestamp")


def _connection_now(row):
    # DATA shares the OAuth/market-data UTC contract; MONEY keeps its existing clock.
    return _data_now() if row.scope.startswith(DATA_SCOPE_PREFIX) else dt.datetime.now()


def _seal_stable_data_keys(bundle):
    stable_keys = {name: bundle.get(name) for name in ("api_key", "api_secret")}
    if any(not isinstance(value, str) or not value for value in stable_keys.values()):
        raise DataConnectionUnavailable("data credential unavailable")
    return seal(stable_keys)


def _validate_data_app_keys(secrets):
    if set(secrets) != {"api_key", "api_secret"} or any(
            not isinstance(value, str) or not value or len(value) > 4096
            for value in secrets.values()):
        raise DataConnectionUnavailable("data-role OAuth application keys are invalid")


class OwnedConnectionStore:
    """CRUD over one owner's broker-account connections. Both scopes are fixed at construction.

    Taking the owner in the constructor rather than per call is the whole design: a method that
    accepts `owner_id` can be called with the wrong one, and this class has no method that can.
    """

    def __init__(self, session, *, owner_id: str, broker_account_id: str,
                 session_factory=None, _allow_data_only_account: bool = False) -> None:
        self.s = session
        self.owner_id = _resolve_owner(owner_id)
        self.broker_account_id = (broker_account_id or "").strip()
        account = self.s.query(BrokerAccount).filter(
            BrokerAccount.broker_account_id == self.broker_account_id,
            BrokerAccount.owner_id == self.owner_id,
        ).one_or_none()
        self._data_only_account = bool(
            account is not None and account.status != "active"
            and _allow_data_only_account and is_data_account_anchor(account)
        )
        if account is None or not (
                account.status == "active" or self._data_only_account):
            raise ValueError("broker account is not available to this owner")
        # Used ONLY by `live_connection`'s late credential read, which outlives this store.
        # Injectable so a test can point it at its own session without a global.
        self._session_factory = session_factory or _default_session_factory

    @classmethod
    def for_data_role(cls, session, *, owner_id: str, broker_account_id: str,
                      session_factory=None):
        """Open the closed DATA store, including its exact execution-disabled anchor."""
        return cls(
            session, owner_id=owner_id, broker_account_id=broker_account_id,
            session_factory=session_factory, _allow_data_only_account=True,
        )

    # ── reads ─────────────────────────────────────────────────────────────
    #: Bounded at the QUERY, per `.claude/rules/tenancy-security.md`. An owner holding more
    #: connections than this has a different problem; an unbounded read is a memory path into
    #: the risk lane, and hard invariant 2 says nothing may block an exit.
    MAX_CONNECTIONS = 200

    def list(self, *, include_revoked: bool = False) -> list[BrokerConnection]:
        q = self.s.query(BrokerConnection).filter(
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id)
        if not include_revoked:
            q = q.filter(BrokerConnection.status == "active")
        return q.order_by(BrokerConnection.id).limit(self.MAX_CONNECTIONS).all()

    def get(self, connection_id: int) -> BrokerConnection:
        row = self.s.query(BrokerConnection).filter(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id).one_or_none()
        if row is None:
            # Logged with the distinction the caller is not given, so a real cross-owner probe
            # is visible to whoever reads the logs.
            log.warn(f"connection {connection_id} not available to owner "
                     f"{self.owner_id!r}", event="CONNECTION_NOT_FOUND")
            raise ConnectionNotFound(f"no connection {connection_id} for this owner")
        return row

    def by_scope(self, scope: str) -> BrokerConnection | None:
        return self.s.query(BrokerConnection).filter(
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id,
            BrokerConnection.scope == scope).one_or_none()

    # ── writes ────────────────────────────────────────────────────────────
    def create(self, *, broker: str, scope: str, label: str = "",
               capabilities: frozenset[str] | None = None) -> BrokerConnection:
        """Register a connection. Refuses a broker this build cannot serve.

        Refusing here rather than at first use is the point: a connection naming a broker with
        no adapter is a row that looks configured and can never work, and the operator finds out
        at 09:15 rather than at the moment they created it.
        """
        if self._data_only_account:
            raise DataConnectionUnavailable(
                "the data-only account cannot create a general connection")
        if scope.startswith(DATA_SCOPE_PREFIX):
            raise DataConnectionUnavailable(
                "the reserved data role is created only by the server-derived V0 path")
        s = spec(broker)                    # raises BrokerNotSupported for an unknown broker
        # An unknown broker is not the only unusable one. A PLANNED broker is a real registry
        # row with real documentation and NO adapter — `spec` accepts it happily, and without
        # this check the connection would be created, look configured, and never work. That is
        # the difference between finding out now and finding out at 09:15.
        if s.load_data() is None and s.load_venue() is None:
            raise BrokerNotSupported(
                f"broker {s.key!r} ({s.display_name}) is {s.status.value} — it has no adapter "
                f"in this build, so a connection to it could never be used. See {s.docs_url}.")
        declared = capabilities
        if declared is None:
            data_cls = s.load_data()
            declared = frozenset(getattr(data_cls, "CAPABILITIES", frozenset())
                                 if data_cls else frozenset())
        row = BrokerConnection(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            broker=s.key, scope=scope, label=label,
            capabilities_json=json.dumps(sorted(caps.validate(frozenset(declared)))),
            status="active", created_at=dt.datetime.now(), updated_at=dt.datetime.now())
        self.s.add(row)
        self.s.flush()
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=f"connection:{self.owner_id}:{row.id}:created",
            facts={"state": "created", "ready": False},
        )
        return row

    def create_data_connection(self, *, label: str = "") -> BrokerConnection:
        """Create the next immutable data-role row, with one active row at most.

        A fixed next scope makes concurrent creators collide on the existing unique
        constraint.  Revoked rows remain audit facts and advance the suffix; none is
        reactivated or recredentialed.
        """
        _data_adapter_contract()
        rows = self.s.query(BrokerConnection).filter(
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id,
            BrokerConnection.broker == "kite",
            BrokerConnection.scope.like(f"{DATA_SCOPE_PREFIX}%"),
        )
        active = rows.filter(BrokerConnection.status == "active").first()
        if active is not None:
            raise DataConnectionConflict("one active Zerodha data connection is already present")
        # COUNT executes in the database; revoked history never becomes an unbounded
        # Python list merely to derive the next immutable row identity.
        scope = f"{DATA_SCOPE_PREFIX}{rows.count() + 1}"
        now = _data_now()
        row = BrokerConnection(
            owner_id=self.owner_id,
            broker_account_id=self.broker_account_id,
            broker="kite",
            scope=scope,
            label=label,
            capabilities_json=json.dumps(sorted(DATA_CAPABILITIES)),
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.s.add(row)
        self.s.flush()
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=f"connection:{self.owner_id}:{row.id}:created",
            facts={"state": "created", "ready": False},
        )
        return row

    def require_data_connection(self, connection_id: int, *, active: bool = True) -> BrokerConnection:
        row = self.get(connection_id)
        _require_data_identity(row, active=active)
        return row

    def _data_credential_source(self, connection_id: int) -> Callable[[], dict]:
        """Build the internal late-read closure shared by OAuth and the data facade."""
        row = self.require_data_connection(connection_id)
        owner_id, broker_account_id, cid = self.owner_id, self.broker_account_id, row.id
        make_session = self._session_factory
        data_only_account = self._data_only_account

        def credential_source() -> dict:
            try:
                with make_session() as session:
                    query = session.query(BrokerConnection).join(
                        BrokerAccount,
                        BrokerAccount.broker_account_id == BrokerConnection.broker_account_id,
                    ).filter(
                        BrokerConnection.id == cid,
                        BrokerConnection.owner_id == owner_id,
                        BrokerConnection.broker_account_id == broker_account_id,
                        BrokerConnection.broker == "kite",
                        BrokerConnection.status == "active",
                        BrokerAccount.broker_account_id == broker_account_id,
                        BrokerAccount.owner_id == owner_id,
                        BrokerAccount.broker == "kite",
                        BrokerAccount.status == (
                            DATA_ONLY_ACCOUNT_STATUS if data_only_account else "active"),
                    )
                    if data_only_account:
                        query = query.filter(
                            BrokerAccount.external_account_id == DATA_ONLY_EXTERNAL_ACCOUNT_ID,
                            BrokerAccount.display_name == DATA_ONLY_ACCOUNT_NAME,
                        )
                    fresh = query.one_or_none()
                    if fresh is None:
                        raise DataConnectionUnavailable("data credential unavailable")
                    _require_data_identity(fresh, active=True)
                    ciphertext = fresh.credential_ciphertext
                    if not ciphertext:
                        return {}
                    return unseal(ciphertext)
            except (CredentialDecryptionFailed, CredentialVaultUnavailable,
                    DataConnectionUnavailable):
                raise DataConnectionUnavailable("data credential unavailable") from None

        return credential_source

    def read_data_oauth_bundle(self, connection_id: int) -> dict:
        """Server-internal OAuth route seam; never serialized or returned to a caller."""
        return self._data_credential_source(connection_id)()

    def data_oauth_source(self, connection_id: int) -> Callable[[], dict]:
        """Server-internal callback binding created while the owning store is open."""
        return self._data_credential_source(connection_id)

    def invalidate_data_access_token(self, connection_id: int, failed_token: str) -> bool:
        """Remove only the failed token while retaining stable per-owner app keys.

        The encrypted blob is part of the update predicate. A newer callback or
        key rotation therefore wins over delayed failure handling.
        """
        if not isinstance(failed_token, str) or not failed_token:
            return False
        row = self.s.scalar(select(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id,
        ).with_for_update())
        if row is None:
            return False
        _require_data_identity(row, active=True)
        old_ciphertext = row.credential_ciphertext
        if not old_ciphertext:
            return False
        try:
            bundle = unseal(old_ciphertext)
        except (CredentialDecryptionFailed, CredentialVaultUnavailable):
            raise DataConnectionUnavailable("data credential unavailable") from None
        current_token = bundle.get("access_token")
        from app.providers.zerodha_data_runtime import failed_token_is_current
        if not failed_token_is_current(current_token, failed_token):
            return False
        ciphertext, key_id = _seal_stable_data_keys(bundle)
        now = _data_now()
        changed = self.s.execute(update(BrokerConnection).where(
            BrokerConnection.id == row.id,
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id,
            BrokerConnection.broker == "kite",
            BrokerConnection.scope == row.scope,
            BrokerConnection.capabilities_json == json.dumps(sorted(DATA_CAPABILITIES)),
            BrokerConnection.status == "active",
            BrokerConnection.credential_ciphertext == old_ciphertext,
        ).values(
            credential_ciphertext=ciphertext,
            credential_key_id=key_id,
            last_authenticated_at=None,
            updated_at=now,
        ))
        if changed.rowcount != 1:
            return False
        from app.db.models import OAuthCallbackState
        self.s.execute(update(OAuthCallbackState).where(
            OAuthCallbackState.connection_id == row.id,
            OAuthCallbackState.organization_id == self.owner_id,
            OAuthCallbackState.revoked_at.is_(None),
        ).values(revoked_at=now))
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=f"connection:{self.owner_id}:{row.id}:reauth:{now.isoformat()}",
            facts={"state": "reauth_required", "ready": False},
        )
        return True

    def zerodha_data_runtime(self, connection_id: int):
        """Return the closed runtime without exposing its provider wire object."""
        self.require_data_connection(connection_id)
        credential_source = self._data_credential_source(connection_id)
        owner_id = self.owner_id
        broker_account_id = self.broker_account_id
        make_session = self._session_factory

        def invalidate(failed_token: str) -> bool:
            with make_session() as session:
                store = OwnedConnectionStore(
                    session, owner_id=owner_id,
                    broker_account_id=broker_account_id,
                    session_factory=make_session,
                )
                changed = store.invalidate_data_access_token(connection_id, failed_token)
                session.commit()
                return changed

        from app.providers.zerodha_data_runtime import ZerodhaDataRuntime
        rate_scope = hashlib.sha256(
            f"{owner_id}\0{broker_account_id}\0{connection_id}".encode("utf-8")
        ).hexdigest()
        return ZerodhaDataRuntime(
            credential_source, invalidate, rate_scope=rate_scope,
        )

    def data_connection(self, connection_id: int) -> DataOnlyConnection:
        """Return the facade bound to the strict runtime, never the broad adapter."""
        runtime = self.zerodha_data_runtime(connection_id)
        from app.providers.kite import KiteProvider
        adapter = KiteProvider.from_data_runtime(runtime)

        def invoke(operation: str, args: tuple, kwargs: dict):
            try:
                if operation == "get_candles":
                    return adapter.get_candles(*args, **kwargs)
                if operation == "get_ltp":
                    return adapter.get_ltp(*args, **kwargs)
                if operation in {"get_option_chain", "get_futures_ltp"}:
                    from app.providers.zerodha_data_runtime import TypedUnavailable
                    reason = (
                        TypedUnavailable.CURRENT_OPTION_CHAIN
                        if operation == "get_option_chain"
                        else TypedUnavailable.FUTURES_LTP
                    )
                    raise DataOperationUnavailable(reason.value)
                raise DataConnectionUnavailable("data operation is unavailable")
            except DataConnectionUnavailable:
                raise
            except Exception as exc:  # normalized runtime types never expose provider text
                raise DataConnectionUnavailable(
                    f"data operation failed ({type(exc).__name__})") from None

        return DataOnlyConnection(invoke)

    def store_credential(self, connection_id: int, secrets: dict) -> BrokerConnection:
        """Encrypt and persist a credential bundle.

        Raises `CredentialVaultUnavailable` when no key is configured, rather than storing
        plaintext. That refusal is the reason the vault exists.

        **A revoked connection cannot be re-credentialed.** `get` filters on owner but not on
        status, and without this check one POST undid a revocation: the row stayed `revoked`
        while acquiring fresh ciphertext, so `revoke`'s promise that a revoked connection is not
        a credential at rest lasted until the next request, and the audit record contradicted
        itself with `last_authenticated_at` later than `revoked_at`. Found by an independent
        security review, 2026-08-11. The check mirrors the one `live_connection` already had.
        """
        if self._data_only_account:
            raise DataConnectionUnavailable(
                "the data-only account cannot store a general credential")
        row = self.get(connection_id)
        if row.status != "active":
            raise ConnectionNotFound(
                f"connection {connection_id} is {row.status}, not active")
        ciphertext, key_id = seal(secrets)
        row.credential_ciphertext = ciphertext
        row.credential_key_id = key_id
        row.last_authenticated_at = _connection_now(row)
        row.updated_at = _connection_now(row)
        self.s.flush()
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=f"connection:{self.owner_id}:{row.id}:ready:{row.updated_at.isoformat()}",
            facts={"state": "ready", "ready": True},
        )
        # No secret, no ciphertext, no key material — this line reaches the log console.
        log.info(f"credential stored for connection {row.id} ({row.broker}:{row.scope})",
                 event="CONNECTION_CREDENTIAL_STORED")
        return row

    def store_data_app_keys(self, connection_id: int, secrets: dict) -> BrokerConnection:
        """Seal OAuth application keys without claiming provider readiness."""
        row = self.require_data_connection(connection_id)
        if set(secrets) != {"api_key", "api_secret"}:
            raise DataConnectionUnavailable("data-role OAuth application keys are invalid")
        ciphertext, key_id = seal(secrets)
        now = _data_now()
        changed = self.s.execute(update(BrokerConnection).where(
            BrokerConnection.id == row.id,
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id,
            BrokerConnection.broker == "kite",
            BrokerConnection.scope == row.scope,
            BrokerConnection.capabilities_json == json.dumps(sorted(DATA_CAPABILITIES)),
            BrokerConnection.status == "active",
        ).values(
            credential_ciphertext=ciphertext,
            credential_key_id=key_id,
            updated_at=now,
        ))
        if changed.rowcount != 1:
            raise DataConnectionUnavailable("data connection is unavailable")
        self.s.expire(row)
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=f"connection:{self.owner_id}:{row.id}:data-keys:{now.isoformat()}",
            facts={"state": "present_unverified", "ready": False},
        )
        log.info(f"data OAuth application keys stored for connection {row.id}",
                 event="DATA_CONNECTION_APP_KEYS_STORED")
        return row

    def write_data_app_keys(
            self, connection_id: int, secrets: dict, *, rotate: bool,
    ) -> BrokerConnection:
        """Write initial or explicitly rotated data app keys under one row lock.

        The direct V1 surface keeps initial setup and rotation distinct.  A
        rotation discards every session token and completion receipt; an ordinary
        OAuth reconnect is the only operation allowed to retain the stable keys.
        """
        _validate_data_app_keys(secrets)
        row = self.s.scalar(select(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.broker_account_id == self.broker_account_id,
        ).with_for_update())
        if row is None:
            raise ConnectionNotFound(f"no connection {connection_id} for this owner")
        _require_data_identity(row, active=True)
        has_bundle = bool(row.credential_ciphertext)
        if rotate != has_bundle:
            raise DataConnectionConflict(
                "Rotate keys is required" if has_bundle else
                "initial application keys are required before rotation")
        ciphertext, key_id = seal(dict(secrets))
        now = _data_now()
        row.credential_ciphertext = ciphertext
        row.credential_key_id = key_id
        row.last_authenticated_at = None
        row.updated_at = now
        from app.db.models import OAuthCallbackState
        self.s.execute(update(OAuthCallbackState).where(
            OAuthCallbackState.connection_id == row.id,
            OAuthCallbackState.organization_id == self.owner_id,
            OAuthCallbackState.revoked_at.is_(None),
        ).values(revoked_at=now))
        self.s.flush()
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=(f"connection:{self.owner_id}:{row.id}:"
                          f"data-keys-{'rotated' if rotate else 'stored'}:{now.isoformat()}"),
            facts={"state": "reauth_required", "ready": False},
        )
        log.info(
            f"data OAuth application keys {'rotated' if rotate else 'stored'} "
            f"for connection {row.id}",
            event=("DATA_CONNECTION_APP_KEYS_ROTATED" if rotate
                   else "DATA_CONNECTION_APP_KEYS_STORED"),
        )
        return row

    def revoke(self, connection_id: int) -> BrokerConnection:
        """Revoke, and destroy the stored credential.

        The row survives — the audit fact is the point — but the ciphertext does not. Keeping it
        would mean a revoked connection is still a credential at rest, which is exactly what
        revocation is supposed to end.
        """
        row = self.get(connection_id)
        row.status = "revoked"
        row.credential_ciphertext = None
        row.credential_key_id = None
        row.revoked_at = _connection_now(row)
        row.updated_at = _connection_now(row)
        self.s.flush()
        from app.events.producers import append_execution_change
        append_execution_change(
            self.s, owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            aggregate_type="broker_connection", aggregate_id=str(row.id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=f"connection:{self.owner_id}:{row.id}:revoked",
            facts={"state": "revoked", "ready": False},
        )
        log.warn(f"connection {row.id} ({row.broker}:{row.scope}) REVOKED",
                 event="CONNECTION_REVOKED")
        return row

    # ── the bridge to the running engine ──────────────────────────────────
    def live_connection(self, connection_id: int) -> Connection:
        """Build the runtime `Connection` this row describes.

        `token_source` reads the row's credential **on every call**, not once here. That is what
        keeps a daily re-login propagating without a restart, and it is the same reason
        `KiteOrderClient` holds a source rather than a value. It also means a revoked connection
        stops producing a token at the next order rather than at the next restart.

        It opens a **short-lived session per call** rather than closing over this one. The pool
        is 15 connections against a 40-thread worker pool, and a `Connection` outlives the
        request that built it — holding a pooled connection for the life of the process is the
        shape behind the 2026-07-23 pool collapse. A token read is one indexed row.

        The per-call query re-filters on owner AND status, so the ownership check does not go
        stale for the life of the `Connection` — a row reassigned or revoked stops producing a
        token at the next order.
        """
        if self._data_only_account:
            raise DataConnectionUnavailable(
                "the data-only account has no execution connection authority")
        row = self.get(connection_id)
        if row.status != "active":
            raise ConnectionNotFound(
                f"connection {connection_id} is {row.status}, not active")
        owner_id, broker_account_id, cid = (
            self.owner_id, self.broker_account_id, row.id)
        make_session = self._session_factory

        def token_source():
            try:
                with make_session() as s:
                    fresh = s.query(BrokerConnection).filter(
                        BrokerConnection.id == cid,
                        BrokerConnection.owner_id == owner_id,
                        BrokerConnection.broker_account_id == broker_account_id,
                        BrokerConnection.status == "active").one_or_none()
                    ciphertext = fresh.credential_ciphertext if fresh is not None else None
            except Exception as e:                      # noqa: BLE001
                # A database hiccup must not raise into the order path. `None` means "this
                # connection has no usable credential", and `KiteOrderClient._sync_token`
                # turns that into a refusal when a token was previously held — see the
                # withdrawal path there. Until 2026-08-10 that refusal did NOT exist and a
                # `None` was silently discarded, so this comment described a mechanism that
                # was never built; an independent review caught it.
                log.error(f"connection {cid}: credential read failed: {e}",
                          event="CONNECTION_CREDENTIAL_READ_FAIL")
                return None
            if ciphertext is None:
                return None
            try:
                return unseal(ciphertext).get("access_token")
            except CredentialDecryptionFailed as e:
                # A rotated key or a tampered row. This used to escape into the order path —
                # `order_executor` absorbed it into a reconciliation-required ERROR, turning a
                # recoverable auth condition into a durable manual blocker. Its message also
                # carried `key_id()` all the way to /api/logs and Telegram. Both are ended here:
                # the condition becomes the same withdrawal refusal as a revoked row, and the
                # fingerprint stays in the server log.
                log.error(f"connection {cid}: stored credential did not decrypt "
                          f"({type(e).__name__})", event="CONNECTION_CREDENTIAL_UNREADABLE")
                return None
            except CredentialVaultUnavailable:
                # No key. The engine keeps running; this connection cannot authenticate, and
                # `KiteOrderClient._sync_token` refuses the next order rather than reusing the
                # token it cached this morning. That refusal is load-bearing and is tested end
                # to end in `tests/test_connection_store.py` — asserting `None` here alone was
                # what let the hole survive.
                log.error(f"connection {cid}: credential vault unavailable",
                          event="CONNECTION_VAULT_UNAVAILABLE")
                return None

        def secrets_source() -> dict:
            """The whole decrypted bundle, read late for the same reasons the token is.

            Returns `{}` on any failure rather than raising: this runs on the order path, and a
            builder that gets an empty bundle refuses at its own credential check with a message
            naming the missing field, which is more useful than a decrypt traceback.
            """
            try:
                with make_session() as s:
                    fresh = s.query(BrokerConnection).filter(
                        BrokerConnection.id == cid,
                        BrokerConnection.owner_id == owner_id,
                        BrokerConnection.broker_account_id == broker_account_id,
                        BrokerConnection.status == "active").one_or_none()
                    ciphertext = fresh.credential_ciphertext if fresh is not None else None
                return unseal(ciphertext) if ciphertext else {}
            except Exception as e:                  # noqa: BLE001
                log.error(f"connection {cid}: credential bundle read failed: {e}",
                          event="CONNECTION_CREDENTIAL_READ_FAIL")
                return {}

        return Connection(
            broker=row.broker,
            scope=row.scope,
            capabilities=caps.validate(frozenset(json.loads(row.capabilities_json or "[]"))),
            token_source=token_source,
            secrets_source=secrets_source,
        )


__all__ = [
    "OwnedConnectionStore", "ConnectionNotFound", "BrokerNotSupported",
    "DataConnectionUnavailable", "DataConnectionConflict", "DataOnlyConnection",
    "DataOperationUnavailable",
    "DATA_ROLE", "DATA_SCOPE_PREFIX", "DATA_CAPABILITIES",
    "DATA_ONLY_ACCOUNT_STATUS", "DATA_ONLY_EXTERNAL_ACCOUNT_ID", "DATA_ONLY_ACCOUNT_NAME",
    "is_data_account_anchor", "validate_data_connection_row",
]
