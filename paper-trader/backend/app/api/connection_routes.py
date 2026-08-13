"""Broker connections over HTTP — the reachable end of `OwnedConnectionStore`.

`broker_connections` has been durable since migration `0015` and the engine already reads it
(`configured_execution_connection` → `runner.py`). Nothing could **write** one except a Python
prompt against the production database, which is the codebase's defining defect wearing its
first shape: a correct mechanism with no caller. This module is the caller.

Three properties are load-bearing and each has a plausible-looking wrong alternative:

**The owner is never a request parameter.** It is derived from the authenticated principal and
handed to the store's constructor, which fixes it for the life of the object. There is no route
here that accepts an `owner_id`, because a route that accepts one can be called with someone
else's — and the object this table grants is the authority to place real orders on a real
account.

**A credential goes in and never comes out.** `POST .../credential` accepts a bundle and answers
with `BrokerConnection.to_dict()`, which carries `has_credential` and no ciphertext. There is no
route that reads a stored credential back; the only consumer is `live_connection`'s late
`token_source`, inside the process. An "export my keys" convenience would make a single API-token
leak equivalent to the brokerage account.

**A missing vault key is a 503, not a stored plaintext.** `seal` refuses, and that refusal
propagates rather than being caught into a partial success — the connection stays
credential-less and the operator is told why.

Kept out on purpose: the interactive broker login flow (Kite's request-token exchange, Angel
One's TOTP). Those are per-broker and belong beside their adapters; this module is the durable
record they would write into, and it is the half that had no way in.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import exists, select, update

from app.api.principal import (
    Principal,
    get_principal,
    is_allowed,
    owner_id_for,
    require,
)
from app.core.credential_vault import CredentialVaultUnavailable, seal
from app.providers.broker_auth import BrokerAuthError, NoInteractiveLogin
from app.db.models import (BrokerAccount, BrokerConnection, OAuthCallbackState,
                           Membership, Organization, User, UserSession)
from app.db.session import SessionLocal
from app.providers import brokers as registry
from app.providers import capabilities as caps
from app.providers.connection_store import ConnectionNotFound, OwnedConnectionStore

router = APIRouter(prefix="/api")


class _ClosedModel(BaseModel):
    """`extra="forbid"` so a typo'd field is a 422 rather than a silently ignored one. On a
    connection create, an ignored field means the row is not what the caller asked for."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ConnectionCreate(_ClosedModel):
    broker: str = Field(min_length=1, max_length=32)
    broker_account_id: str = Field(min_length=1, max_length=64)
    #: Bounded to the column width. The value is written into every `ExecutionIntent` this
    #: connection authors, so a truncated one would silently break restart attribution.
    scope: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=80)
    #: Omitted means "whatever the adapter declares". Supplying a narrower set is legitimate —
    #: a data-only Kite connection — but a wider one is refused by `caps.validate`. Bounded
    #: because the vocabulary is 19 strings long: a 200,000-element array was accepted before
    #: the frozenset collapsed it, which is transient memory for nothing.
    capabilities: list[str] | None = Field(default=None, max_length=len(caps.ALL))


class CredentialWrite(_ClosedModel):
    """The bundle to encrypt. Its keys are broker-specific by design (`access_token` for Kite,
    plus `client_id` for Dhan, a seed for a TOTP broker), so the shape is a flat string map
    rather than a per-broker model — the vault deliberately has no per-broker branch."""

    secrets: dict[str, str] = Field(min_length=1)


#: Bounds on the bundle. Not paranoia about the operator: this is the one route that writes an
#: unbounded caller-supplied structure into a money-plane column, and `seal` will encrypt
#: whatever it is handed.
_MAX_SECRET_KEYS = 12
_MAX_SECRET_LEN = 4096
#: Keys are bounded too. Checking only `.values()` left the field NAMES unbounded, and a single
#: two-million-character key stored a 2.6 MB ciphertext — on a 1 GB droplet whose database is
#: rsynced by `deploy.sh`. Found by an independent security review, 2026-08-11.
_MAX_SECRET_KEY_LEN = 64
_OAUTH_STATE_TTL = dt.timedelta(minutes=10)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _digest_state(raw: str | None) -> str | None:
    if not isinstance(raw, str) or not raw or len(raw) > 512:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _with_state(url: str, state: str) -> str:
    """Add OAuth state without serialising it anywhere but the broker redirect URL."""
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["state"] = state
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                       urlencode(query), parsed.fragment))

#: These bounds are checked HERE and deliberately not expressed as `constr(max_length=...)` on
#: the model. A pydantic length failure puts the rejected value into the 422 body's `input`
#: field, which would send a live access token back over the wire in an error envelope — the
#: exact leak the handler in `main.py` now strips. Moving the bound "up into the model" is the
#: obvious-looking refactor and it reopens that hole.


def _open(session, principal: Principal, broker_account_id: str, broker: str) -> OwnedConnectionStore:
    """One place that binds a session to an owner, so no route can resolve the owner its own
    slightly different way."""
    owner_id = owner_id_for(principal)
    account = session.scalar(select(BrokerAccount.broker_account_id).where(
        BrokerAccount.owner_id == owner_id,
        BrokerAccount.broker_account_id == broker_account_id,
        BrokerAccount.broker == broker,
        BrokerAccount.status == "active"))
    if account is None:
        raise ConnectionNotFound("no broker account for this owner")
    return OwnedConnectionStore(
        session, owner_id=owner_id,
        broker_account_id=account)


def _store_for_connection(session, principal: Principal, connection_id: int) -> OwnedConnectionStore:
    """Bind an existing connection through owner + active-account SQL before use."""
    owner_id = owner_id_for(principal)
    account_id = session.scalar(select(BrokerConnection.broker_account_id).join(
        BrokerAccount, BrokerAccount.broker_account_id == BrokerConnection.broker_account_id).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == owner_id,
            BrokerConnection.broker == BrokerAccount.broker,
            BrokerAccount.owner_id == owner_id,
            BrokerAccount.status == "active",
        ))
    if account_id is None:
        raise ConnectionNotFound(f"no connection {connection_id} for this owner")
    return OwnedConnectionStore(session, owner_id=owner_id, broker_account_id=account_id)


def _authorized(store: OwnedConnectionStore, principal: Principal,
                action: str, connection_id: int):
    """Load the row and put it through the policy.

    The store's query already filters on owner, so this is a second, independent check on the
    same fact — deliberately. They fail differently: the query filter is *data scoping* and lives
    in the store; `is_allowed` is *policy* and lives in `principal.py`, which is the file
    `.claude/rules/tenancy-security.md` says authorization must be reviewable from. If the filter
    is ever dropped in a refactor, this still refuses, and vice versa.

    It is also the first caller that hands `is_allowed` a genuinely owned object. A policy that
    can enforce ownership and is never given anything owned is the unconsumed-mechanism defect
    with an authorization label on it.
    """
    row = store.get(connection_id)
    if not is_allowed(principal, action, row):
        # Reported as absent, NOT forbidden. A 403 confirms the id exists, and ids are guessable
        # — the same non-disclosure rule `ConnectionNotFound` exists for. The refusal is the
        # policy's; only how it is *shown* is the route's business.
        raise ConnectionNotFound(f"no connection {connection_id} for this owner")
    return row


@router.get("/brokers")
def list_brokers(principal: Principal = Depends(get_principal)) -> dict:
    """The registry, as the operator sees it.

    `status` is the field that matters and it is reported verbatim: a `planned` broker appears in
    this list with its documentation URL and is refused at create. Hiding the planned rows would
    make "we do not support this yet" indistinguishable from "we have never heard of it", and the
    work list is the honest answer to "which brokers can I use".
    """
    require(principal, "read:brokers")
    return {"brokers": [
        {
            "key": b.key,
            "display_name": b.display_name,
            "status": b.status.value,
            "auth": b.auth.value,
            "docs_url": b.docs_url,
            # Derived from the registry row rather than declared twice. `roles` is what a caller
            # actually needs: "supported" does not mean "can execute" — Upstox is supported and
            # serves data only.
            "roles": {"data": b.data is not None, "execution": b.venue is not None},
            "notes": b.notes,
        }
        for b in registry.BROKERS
    ]}


@router.get("/connections")
def list_connections(
    include_revoked: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
) -> dict:
    """This owner's connections. Bounded at the query by `MAX_CONNECTIONS`, per the tenancy
    rule that an unbounded list read is a memory path into the risk lane."""
    require(principal, "read:connections")
    with SessionLocal() as s:
        q = select(BrokerConnection).where(BrokerConnection.owner_id == owner_id_for(principal))
        if not include_revoked:
            q = q.where(BrokerConnection.status == "active")
        rows = s.scalars(q.order_by(BrokerConnection.id).limit(200)).all()
        return {"connections": [r.to_dict() for r in rows]}


@router.get("/connections/{connection_id}")
def get_connection(connection_id: int,
                   principal: Principal = Depends(get_principal)) -> dict:
    require(principal, "read:connections")
    with SessionLocal() as s:
        try:
            store = _store_for_connection(s, principal, connection_id)
            return _authorized(store, principal, "read:connection", connection_id).to_dict()
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/connections", status_code=status.HTTP_201_CREATED)
def create_connection(body: ConnectionCreate,
                      principal: Principal = Depends(get_principal)) -> dict:
    """Register a connection to a broker this build can actually serve.

    The refusals are the interesting part. An unknown broker and a `planned` one both become 400
    with the registry's own message — which names the documentation URL — because a connection
    that looks configured and can never work is discovered at 09:15 otherwise. A duplicate
    `(owner, broker account, scope)` becomes 409 rather than a 500 from the unique constraint:
    two connections sharing a scope inside one account would make lifecycle attribution
    ambiguous.
    """
    require(principal, "create:connection")
    # Refused, not silently stripped. `"kite:main "` and `"kite:main"` are different strings to
    # `uq_broker_connection_owner_account_scope`, so the 409 above never fires and the account
    # ends up with
    # two visually identical scopes — worse than two literally identical ones, because
    # `ExecutionIntent.connection_scope` is what restart recovery matches on. Normalising it
    # instead would leave the caller's record disagreeing with what they asked for, and
    # `configured_execution_connection` strips its env var but matches the stored value
    # unstripped, so the padded row would be invisible to the engine at start.
    if body.scope != body.scope.strip():
        raise HTTPException(
            status_code=422,
            detail="a connection scope may not have leading or trailing whitespace")
    declared = (frozenset(body.capabilities)
                if body.capabilities is not None else None)
    with SessionLocal() as s:
        try:
            requested = registry.spec(body.broker)
            if requested.load_data() is None and requested.load_venue() is None:
                raise registry.BrokerNotSupported(
                    f"broker {requested.key!r} ({requested.display_name}) is {requested.status.value} "
                    f"— it has no adapter in this build, so a connection to it could never be "
                    f"used. See {requested.docs_url}.")
            normalized_broker = requested.key
            row = _open(s, principal, body.broker_account_id, normalized_broker).create(
                broker=normalized_broker, scope=body.scope, label=body.label,
                capabilities=declared)
            s.commit()
        except registry.BrokerNotSupported as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except caps.UnknownCapability as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except IntegrityError as e:
            s.rollback()
            raise HTTPException(
                status_code=409,
                detail=(f"a connection with scope {body.scope!r} already exists for this "
                        "broker account"),
            ) from e
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail="broker account unavailable") from e
        return row.to_dict()


@router.post("/connections/{connection_id}/credential")
def store_credential(connection_id: int, body: CredentialWrite,
                     principal: Principal = Depends(get_principal)) -> dict:
    """Encrypt and persist this connection's credential bundle.

    503 when no vault key is configured. That is the correct code and not a 500: the request was
    valid, the server cannot currently satisfy it, and the operator's fix is to set
    `PT_CREDENTIAL_KEY` and retry. The alternative — catching the refusal and reporting success
    with the credential dropped — is the shape this codebase keeps producing.

    The bundle never appears in the response, and no `except` here interpolates `body`. A
    validation message quoting the rejected value would put a live access token in the log ring
    buffer that `/api/logs` serves.
    """
    require(principal, "write:credential")
    if len(body.secrets) > _MAX_SECRET_KEYS:
        raise HTTPException(
            status_code=422,
            detail=f"a credential bundle may hold at most {_MAX_SECRET_KEYS} fields")
    if any(len(k) > _MAX_SECRET_KEY_LEN or len(v) > _MAX_SECRET_LEN
           for k, v in body.secrets.items()):
        raise HTTPException(
            status_code=422,
            detail=f"a credential field name may be at most {_MAX_SECRET_KEY_LEN} characters "
                   f"and its value at most {_MAX_SECRET_LEN}")
    with SessionLocal() as s:
        try:
            store = _store_for_connection(s, principal, connection_id)
            _authorized(store, principal, "write:credential", connection_id)
            row = store.store_credential(connection_id, dict(body.secrets))
            s.commit()
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except CredentialVaultUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        return row.to_dict()


@router.delete("/connections/{connection_id}")
def revoke_connection(connection_id: int,
                      principal: Principal = Depends(get_principal)) -> dict:
    """Revoke. The row survives and the ciphertext does not — see `OwnedConnectionStore.revoke`.

    `DELETE` is the honest verb for the caller's intent even though no row is deleted; the
    response carries `status: "revoked"` and `revoked_at`, so what actually happened is visible
    rather than implied.
    """
    require(principal, "revoke:connection")
    with SessionLocal() as s:
        try:
            store = _store_for_connection(s, principal, connection_id)
            _authorized(store, principal, "revoke:connection", connection_id)
            row = store.revoke(connection_id)
            s.commit()
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return row.to_dict()


# ── acquiring a credential ────────────────────────────────────────────────
# The half that made "a connection row exists" fall short of "a user connected their broker".
# `/api/login` and `/api/session` already exist and drive the process-global provider into
# `access_token.json` — one file, one account. These are their per-connection equivalents and
# they deliberately do not touch that file.

class SessionExchange(_ClosedModel):
    request_token: str = Field(min_length=1, max_length=512)


def _authenticator(broker: str):
    spec = registry.spec(broker)
    auth = spec.load_authenticator()
    if auth is None:
        raise HTTPException(
            status_code=501,
            detail=f"no login flow is implemented for {spec.display_name}. Its API "
                   f"documentation is at {spec.docs_url}; an adapter written without reading it "
                   f"is how a flow that looks right fails at 06:00.")
    return auth


@router.get("/connections/{connection_id}/login")
def connection_login_url(connection_id: int,
                         principal: Principal = Depends(get_principal)) -> dict:
    """Where to send this connection's browser to authenticate.

    Returns the URL rather than redirecting. A 302 from an API the frontend calls with fetch()
    is followed transparently by the browser and lands the JSON parser on Zerodha's HTML; the
    caller needs the URL so it can navigate deliberately.

    The app keys come from THIS connection's stored secrets. There is no fallback to the
    process-wide `KITE_API_KEY`: that would run every owner's login through the owner's own
    Zerodha app registration, which is a cross-tenant credential path wearing a default.
    """
    require(principal, "read:connections")
    with SessionLocal() as s:
        try:
            store = _store_for_connection(s, principal, connection_id)
            row = _authorized(store, principal, "read:connection", connection_id)
            auth = _authenticator(row.broker)
            secrets = store.live_connection(connection_id).secrets_source()
            return {"connection_id": row.id, "broker": row.broker,
                    "login_url": auth.login_url(secrets)}
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except NoInteractiveLogin as e:
            # 400, not 501: nothing is missing. This broker genuinely has no redirect flow and
            # the message says what to do instead.
            raise HTTPException(status_code=400, detail=str(e)) from e
        except BrokerAuthError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


def _start_oauth(connection_id: int, principal: Principal) -> dict:
    """Create a one-use browser binding for a connection owned by this session."""
    require(principal, "write:credential")
    if not principal.session_id or not principal.user_id or not principal.organization_id:
        raise HTTPException(status_code=403, detail="authenticated session required")
    with SessionLocal() as s:
        try:
            active = s.scalar(select(UserSession.session_id).where(
                UserSession.session_id == principal.session_id,
                UserSession.user_id == principal.user_id,
                UserSession.organization_id == principal.organization_id,
                UserSession.revoked_at.is_(None), UserSession.expires_at > _now()))
            if active is None:
                raise ConnectionNotFound("no active authenticated connection")
            store = _store_for_connection(s, principal, connection_id)
            row = _authorized(store, principal, "write:credential", connection_id)
            auth = _authenticator(row.broker)
            credential_bundle = store.live_connection(connection_id).secrets_source()
            login_url = auth.login_url(credential_bundle)
            raw_state = secrets.token_urlsafe(32)
            state_digest = _digest_state(raw_state)
            assert state_digest is not None
            s.add(OAuthCallbackState(
                state_digest=state_digest, connection_id=row.id,
                session_id=principal.session_id, user_id=principal.user_id,
                organization_id=principal.organization_id, created_at=_now(),
                expires_at=_now() + _OAUTH_STATE_TTL))
            s.commit()
            return {"connection_id": row.id,
                    "login_url": _with_state(login_url, raw_state)}
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except NoInteractiveLogin as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except BrokerAuthError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except CredentialVaultUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/connections/{connection_id}/oauth/initiate")
def connection_oauth_initiate(connection_id: int,
                              principal: Principal = Depends(get_principal)) -> dict:
    return _start_oauth(connection_id, principal)


def _consume_callback_state(session, *, digest: str, now: dt.datetime) -> bool:
    """Spend this unexpired OAuth capability once with one portable CAS."""
    consumed = session.execute(update(OAuthCallbackState).where(
        OAuthCallbackState.state_digest == digest,
        OAuthCallbackState.expires_at > now,
        OAuthCallbackState.revoked_at.is_(None),
        OAuthCallbackState.consumed_at.is_(None),
    ).values(consumed_at=now))
    return consumed.rowcount == 1


def _store_callback_credential(
        session, *, connection_id: int, owner_id: str, broker_account_id: str,
        user_id: str, session_id: str, secrets: dict, now: dt.datetime
) -> BrokerConnection | None:
    """Store only while the callback identity and connection are still active.

    The connection status predicate is on the credential UPDATE itself. It is
    therefore also the row-lock acquisition point: revoke-before-update makes
    this return ``None``; update-before-revoke commits a credential which the
    waiting revoke then destroys.
    """
    ciphertext, key_id = seal(secrets)
    identity_is_active = exists(select(UserSession.session_id).join(
        User, User.user_id == UserSession.user_id).join(
        Organization,
        Organization.organization_id == UserSession.organization_id).join(
        Membership,
        (Membership.organization_id == UserSession.organization_id) &
        (Membership.user_id == UserSession.user_id)).where(
            UserSession.session_id == session_id,
            UserSession.user_id == user_id,
            UserSession.organization_id == owner_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            User.status == "active",
            Organization.status == "active",
            Membership.status == "active",
            Membership.role == "owner",
    ))
    account_is_active = exists(select(BrokerAccount.broker_account_id).where(
        BrokerAccount.broker_account_id == broker_account_id,
        BrokerAccount.owner_id == owner_id,
        BrokerAccount.status == "active",
    ))
    changed = session.execute(update(BrokerConnection).where(
        BrokerConnection.id == connection_id,
        BrokerConnection.owner_id == owner_id,
        BrokerConnection.broker_account_id == broker_account_id,
        BrokerConnection.status == "active",
        identity_is_active,
        account_is_active,
    ).values(
        credential_ciphertext=ciphertext,
        credential_key_id=key_id,
        last_authenticated_at=now,
        updated_at=now,
    ))
    if changed.rowcount != 1:
        return None
    from app.events.producers import append_execution_change

    mutation_id = hashlib.sha256(
        f"{connection_id}|{owner_id}|{user_id}|{session_id}|{now.isoformat()}".encode()
    ).hexdigest()
    append_execution_change(
        session, owner_id=owner_id, broker_account_id=broker_account_id,
        aggregate_type="broker_connection", aggregate_id=str(connection_id),
        event_type="execution.connection.changed", projection="connections",
        producer_key=f"connection:{connection_id}:oauth:{mutation_id}",
        facts={"state": "ready", "ready": True},
    )
    return session.get(BrokerConnection, connection_id)


@router.get("/oauth/callback")
def oauth_callback(state: str | None = None, request_token: str | None = None) -> dict:
    """Consume a durable state before exchanging a broker request token.

    This is intentionally the sole callback surface that may be reached without
    a bearer.  All invalid state shapes return the same response and never call
    a provider, so state guessing cannot reveal a connection or cause an
    exchange for someone else's account.
    """
    digest = _digest_state(state)
    if digest is None or not request_token or len(request_token) > 512:
        raise HTTPException(status_code=400, detail="invalid login callback")
    now = _now()
    with SessionLocal() as s:
        callback = s.scalar(select(OAuthCallbackState).join(
            UserSession, UserSession.session_id == OAuthCallbackState.session_id).join(
            Membership, (Membership.organization_id == UserSession.organization_id) &
                        (Membership.user_id == UserSession.user_id)).join(
            User, User.user_id == UserSession.user_id).join(
            Organization, Organization.organization_id == UserSession.organization_id).join(
            BrokerConnection, BrokerConnection.id == OAuthCallbackState.connection_id).join(
            BrokerAccount, BrokerAccount.broker_account_id == BrokerConnection.broker_account_id).where(
                OAuthCallbackState.state_digest == digest,
                OAuthCallbackState.expires_at > now,
                OAuthCallbackState.revoked_at.is_(None),
                OAuthCallbackState.consumed_at.is_(None),
                UserSession.session_id == OAuthCallbackState.session_id,
                UserSession.user_id == OAuthCallbackState.user_id,
                UserSession.organization_id == OAuthCallbackState.organization_id,
                UserSession.revoked_at.is_(None), UserSession.expires_at > now,
                Membership.status == "active", Membership.role == "owner",
                User.status == "active", Organization.status == "active",
                BrokerConnection.owner_id == OAuthCallbackState.organization_id,
                BrokerConnection.status == "active",
                BrokerAccount.owner_id == OAuthCallbackState.organization_id,
                BrokerAccount.status == "active",
            ))
        if callback is None:
            raise HTTPException(status_code=400, detail="invalid login callback")
        if not _consume_callback_state(s, digest=digest, now=now):
            s.rollback()
            raise HTTPException(status_code=400, detail="invalid login callback")
        owner_id = callback.organization_id
        connection_id = callback.connection_id
        broker_account_id = s.scalar(select(BrokerConnection.broker_account_id).where(
            BrokerConnection.id == connection_id))
        store = OwnedConnectionStore(
            s, owner_id=owner_id, broker_account_id=broker_account_id)
        try:
            row = store.get(connection_id)
            broker = row.broker
            secrets_source = store.live_connection(row.id).secrets_source
        except (ConnectionNotFound, CredentialVaultUnavailable):
            s.commit()  # retain the consumed state after a failed lookup
            raise HTTPException(status_code=400, detail="invalid login callback")
        # Commit the spent capability before external broker I/O. A slow exchange
        # must not retain SQLite's writer lane or a PostgreSQL row lock, and a
        # duplicate callback must already fail while the provider is blocked.
        s.commit()
    try:
        bundle = _authenticator(broker).exchange(secrets_source(), request_token)
    except (NoInteractiveLogin, BrokerAuthError, CredentialVaultUnavailable):
        raise HTTPException(status_code=400, detail="invalid login callback")
    with SessionLocal() as s:
        try:
            saved = _store_callback_credential(
                s, connection_id=connection_id, owner_id=owner_id,
                broker_account_id=broker_account_id, user_id=callback.user_id,
                session_id=callback.session_id, secrets=bundle, now=_now())
            if saved is None:
                raise ConnectionNotFound("OAuth callback identity is no longer active")
            result = saved.to_dict()
            s.commit()
            return result
        except (ConnectionNotFound, CredentialVaultUnavailable):
            s.rollback()
            raise HTTPException(status_code=400, detail="invalid login callback")
