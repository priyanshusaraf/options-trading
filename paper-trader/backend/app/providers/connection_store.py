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
import json

from app.core.credential_vault import (
    CredentialDecryptionFailed,
    CredentialVaultUnavailable,
    seal,
    unseal,
)
from app.core.logging import log
from app.db.models import LEGACY_OWNER_ID, BrokerAccount, BrokerConnection
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


class OwnedConnectionStore:
    """CRUD over one owner's broker-account connections. Both scopes are fixed at construction.

    Taking the owner in the constructor rather than per call is the whole design: a method that
    accepts `owner_id` can be called with the wrong one, and this class has no method that can.
    """

    def __init__(self, session, *, owner_id: str, broker_account_id: str,
                 session_factory=None) -> None:
        self.s = session
        self.owner_id = _resolve_owner(owner_id)
        self.broker_account_id = (broker_account_id or "").strip()
        account = self.s.query(BrokerAccount).filter(
            BrokerAccount.broker_account_id == self.broker_account_id,
            BrokerAccount.owner_id == self.owner_id,
            BrokerAccount.status == "active",
        ).one_or_none()
        if account is None:
            raise ValueError("broker account is not available to this owner")
        # Used ONLY by `live_connection`'s late credential read, which outlives this store.
        # Injectable so a test can point it at its own session without a global.
        self._session_factory = session_factory or _default_session_factory

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
        row = self.get(connection_id)
        if row.status != "active":
            raise ConnectionNotFound(
                f"connection {connection_id} is {row.status}, not active")
        ciphertext, key_id = seal(secrets)
        row.credential_ciphertext = ciphertext
        row.credential_key_id = key_id
        row.last_authenticated_at = dt.datetime.now()
        row.updated_at = dt.datetime.now()
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
        row.revoked_at = dt.datetime.now()
        row.updated_at = dt.datetime.now()
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


__all__ = ["OwnedConnectionStore", "ConnectionNotFound", "BrokerNotSupported"]
