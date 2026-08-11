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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.api.principal import (
    Principal,
    get_principal,
    is_allowed,
    owner_id_for,
    require,
)
from app.core.credential_vault import CredentialVaultUnavailable
from app.providers.broker_auth import BrokerAuthError, NoInteractiveLogin
from app.db.models import BrokerAccount
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

#: These bounds are checked HERE and deliberately not expressed as `constr(max_length=...)` on
#: the model. A pydantic length failure puts the rejected value into the 422 body's `input`
#: field, which would send a live access token back over the wire in an error envelope — the
#: exact leak the handler in `main.py` now strips. Moving the bound "up into the model" is the
#: obvious-looking refactor and it reopens that hole.


def _open(session, principal: Principal) -> OwnedConnectionStore:
    """One place that binds a session to an owner, so no route can resolve the owner its own
    slightly different way."""
    owner_id = owner_id_for(principal)
    accounts = list(session.scalars(select(BrokerAccount).where(
        BrokerAccount.owner_id == owner_id,
        BrokerAccount.status == "active").order_by(BrokerAccount.broker_account_id).limit(2)))
    if len(accounts) != 1:
        raise HTTPException(
            status_code=409,
            detail="owner must have exactly one active broker account for this endpoint")
    return OwnedConnectionStore(
        session, owner_id=owner_id,
        broker_account_id=accounts[0].broker_account_id)


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
        rows = _open(s, principal).list(include_revoked=include_revoked)
        return {"connections": [r.to_dict() for r in rows]}


@router.get("/connections/{connection_id}")
def get_connection(connection_id: int,
                   principal: Principal = Depends(get_principal)) -> dict:
    require(principal, "read:connections")
    with SessionLocal() as s:
        try:
            store = _open(s, principal)
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
            row = _open(s, principal).create(
                broker=body.broker, scope=body.scope, label=body.label,
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
            store = _open(s, principal)
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
            store = _open(s, principal)
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
            store = _open(s, principal)
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


@router.post("/connections/{connection_id}/session")
def connection_complete_session(connection_id: int, body: SessionExchange,
                                principal: Principal = Depends(get_principal)) -> dict:
    """Exchange the broker's one-time token and seal the result.

    A POST, and authenticated as the owner of this connection — deliberately not a GET the
    broker can redirect to. `/api/session` is a GET on the auth-exempt list because it receives
    Zerodha's redirect directly; that is acceptable for one hard-coded account and is not
    acceptable here, where the request names WHICH connection to write a credential into. An
    unauthenticated GET taking a connection id would let anyone who could reach the port bind a
    credential of their choosing to another owner's connection.

    The exchanged bundle carries the app keys through, so tomorrow's re-login still has
    something to authenticate with.
    """
    require(principal, "write:credential")
    with SessionLocal() as s:
        try:
            store = _open(s, principal)
            row = _authorized(store, principal, "write:credential", connection_id)
            auth = _authenticator(row.broker)
            secrets = store.live_connection(connection_id).secrets_source()
            bundle = auth.exchange(secrets, body.request_token)
            saved = store.store_credential(connection_id, bundle)
            s.commit()
            return saved.to_dict()
        except ConnectionNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except NoInteractiveLogin as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except BrokerAuthError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except CredentialVaultUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
