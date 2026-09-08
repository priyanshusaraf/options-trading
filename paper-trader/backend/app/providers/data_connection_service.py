"""Closed V0 data-provider onboarding service.

This module coordinates the existing owner-scoped store, vault and browser
principal. Production constructs only the dedicated Zerodha DATA authenticator.
Tests inject fakes and never contact the provider.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import secrets
import unicodedata
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import and_, delete, exists, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.api.principal import Principal, owner_id_for
from app.core.credential_vault import (
    CredentialDecryptionFailed,
    CredentialVaultUnavailable,
    seal,
)
from app.db.models import (
    BrokerAccount,
    BrokerConnection,
    Membership,
    OAuthCallbackState,
    Organization,
    User,
    UserSession,
)
from app.db.concurrency import begin_reservation
from app.providers.connection_store import (
    DATA_CAPABILITIES,
    DATA_ONLY_ACCOUNT_NAME,
    DATA_ONLY_ACCOUNT_STATUS,
    DATA_ONLY_EXTERNAL_ACCOUNT_ID,
    DATA_SCOPE_PREFIX,
    ConnectionNotFound,
    DataConnectionConflict,
    DataConnectionUnavailable,
    OwnedConnectionStore,
    is_data_account_anchor,
    validate_data_connection_row,
)


STATE_TTL = dt.timedelta(minutes=10)
MAX_TOKEN_LENGTH = 512
MAX_INSTRUMENT_ROWS = 100_000


class InvalidInstrumentSearch(ValueError):
    """Search parameters are outside the closed current-reference contract."""


class InstrumentSelectionUnavailable(ValueError):
    """The selected provider reference or requested research definition is unavailable."""


def _instrument_query(query: str, exchange: str, limit: int) -> str:
    if (type(query) is not str or not 2 <= len(query.strip()) <= 64
            or unicodedata.normalize("NFC", query.strip()) != query.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in query)):
        raise InvalidInstrumentSearch()
    _search_bounds(exchange, limit)
    return query.strip().upper()


def _search_bounds(exchange: str, limit: int) -> None:
    if (type(exchange) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,16}", exchange) is None
            or type(limit) is not int or not 1 <= limit <= 50):
        raise InvalidInstrumentSearch()


def _cash_instrument(row: dict, exchange: str) -> bool:
    return (row.get("exchange") == exchange and row.get("instrument_type") == "EQ"
            and row.get("segment") in (exchange, "INDICES")
            and row.get("expiry") in (None, ""))


def _instrument_text(value, maximum: int, *, empty: bool = False) -> bool:
    return (type(value) is str and int(not empty) <= len(value) <= maximum
            and re.fullmatch(r"[A-Za-z0-9 .&()'/_+%-]*", value) is not None)


def _instrument_token(value) -> bool:
    return type(value) is int and 0 < value <= 4_294_967_295


def _instrument_reference(row, exchange: str) -> tuple | None:
    if type(row) is not dict or not _cash_instrument(row, exchange):
        return None
    token = row.get("instrument_token")
    symbol, name = row.get("tradingsymbol"), row.get("name")
    if not _instrument_token(token):
        return None
    if not _instrument_text(symbol, 64) or not _instrument_text(name, 128, empty=True):
        return None
    if symbol != symbol.strip() or not symbol.strip():
        return None
    return symbol, token, name, exchange, "INDEX" if row["segment"] == "INDICES" else "EQUITY"


def _catalogue_references(rows):
    from app.providers.zerodha_data_runtime import ZerodhaDataUnavailable
    from app.providers.provider_instrument_reference import ProviderReferenceInvalid, reference_from_row
    if type(rows) is not list or len(rows) > MAX_INSTRUMENT_ROWS:
        raise ZerodhaDataUnavailable("current instrument list is unavailable")
    references = {}
    for row in rows:
        try:
            reference = reference_from_row(row)
        except ProviderReferenceInvalid:
            continue
        references[json.dumps(reference, sort_keys=True)] = reference
    return list(references.values())


def _instrument_matches(rows, query: str, exchange: str, limit: int) -> dict:
    references = _catalogue_references(rows)
    matches = [reference for reference in references
               if (exchange == "ALL" or reference["exchange"] == exchange)
               and query in f"{reference['symbol']} {reference['name']}".upper()]
    selected = sorted(matches, key=lambda item: (
        item["symbol"], item["exchange"], item["token"], json.dumps(item, sort_keys=True)))[:limit + 1]
    return {
        "schema": "strategy-os-provider-instrument-search/2", "provider": "ZERODHA",
        "reference_type": "CURRENT_PROVIDER_REFERENCE", "exchange": exchange, "query": query,
        "available_exchanges": sorted({reference["exchange"] for reference in references}),
        "has_more": len(selected) > limit, "items": selected[:limit],
    }


def _instrument_connection(session, principal: Principal, session_factory):
    owner_id, _, _ = _active_identity(session, principal, lock=False)
    account_id = _account_id(session, owner_id, lock=False)
    row = _active_row(_data_rows(session, owner_id, account_id, lock=False))
    if row is None or not row.credential_ciphertext:
        raise ConnectionNotFound("data connection unavailable")
    try:
        store = OwnedConnectionStore.for_data_role(
            session, owner_id=owner_id, broker_account_id=account_id,
            session_factory=session_factory)
    except ValueError:
        raise DataConnectionUnavailable("data account is unavailable") from None
    store.require_data_connection(row.id)
    return store, row.id


def _fetch_instruments(session_factory, principal: Principal, exchange: str):
    from app.providers.zerodha_data_runtime import ZerodhaDataUnavailable
    with session_factory() as session:
        store, connection_id = _instrument_connection(session, principal, session_factory)
        runtime = store.zerodha_data_runtime(connection_id)
    try:
        return runtime.instruments(None if exchange == "ALL" else exchange), connection_id
    except (ZerodhaDataUnavailable, DataConnectionUnavailable):
        raise
    except Exception:
        raise ZerodhaDataUnavailable("current instrument list is unavailable") from None


def search_instruments(session_factory, principal: Principal, *, query: str,
                       exchange: str = "ALL", limit: int = 20) -> dict:
    """Search all provider catalogue types without granting research authority."""
    query = _instrument_query(query, exchange, limit)
    rows, connection_id = _fetch_instruments(session_factory, principal, "ALL")
    result = _instrument_matches(rows, query, exchange, limit)
    # The provider call runs outside a DB transaction. Recheck durable access in
    # a fresh session before publishing even public provider reference metadata.
    with session_factory() as session:
        _, current_id = _instrument_connection(session, principal, session_factory)
        if current_id != connection_id:
            raise DataConnectionUnavailable("data connection changed during search")
    return result


def _related_provider_rows(rows, token: int, symbol: str, exchange: str):
    if type(rows) is not list or len(rows) > MAX_INSTRUMENT_ROWS:
        raise InstrumentSelectionUnavailable()
    return [row for row in rows if type(row) is dict and (
        row.get("instrument_token") == token or
        (row.get("exchange"), row.get("tradingsymbol")) == (exchange, symbol))]


def _verified_provider_selection(rows, reference):
    from app.providers.provider_instrument_reference import ProviderReferenceInvalid, reference_from_row
    # A duplicate token or exchange/symbol is ambiguous even if only one row is well formed.
    related = _related_provider_rows(rows, reference["token"], reference["symbol"], reference["exchange"])
    if len(related) != 1:
        raise InstrumentSelectionUnavailable()
    try:
        current = reference_from_row(related[0])
    except ProviderReferenceInvalid:
        raise InstrumentSelectionUnavailable() from None
    if current != reference:
        raise InstrumentSelectionUnavailable()
    return current


def select_provider_instrument(session_factory, principal: Principal, *, reference: dict) -> dict:
    """Save an immutable owner selection after rechecking its current provider terms."""
    from app.core.provider_selections import persist_provider_selection
    from app.providers.provider_instrument_reference import validate_reference
    reference = validate_reference(reference)
    rows, connection_id = _fetch_instruments(session_factory, principal, "ALL")
    selected = _verified_provider_selection(rows, reference)
    observed_at = dt.datetime.now(dt.timezone.utc)
    owner_id = owner_id_for(principal)
    with session_factory() as session:
        begin_reservation(session, scope=f"provider-selection:{owner_id}")
        store, current_id = _instrument_connection(session, principal, session_factory)
        if current_id != connection_id:
            raise DataConnectionUnavailable("data connection changed during selection")
        saved = persist_provider_selection(session, owner_id=store.owner_id,
            data_account_id=store.broker_account_id, connection_id=current_id,
            provider="ZERODHA", reference=selected, observed_at=observed_at)
        session.commit()
    return {"schema": "strategy-os-provider-selection/1", **saved,
            "research_resolution": "UNRESOLVED"}


def _selected_instrument(rows, token: int, symbol: str, exchange: str, kind: str) -> tuple:
    related = _related_provider_rows(rows, token, symbol, exchange)
    if len(related) != 1:
        raise InstrumentSelectionUnavailable()
    selected = _instrument_reference(related[0], exchange)
    if selected is None or (selected[0], selected[1], selected[3], selected[4]) != (symbol, token, exchange, kind):
        raise InstrumentSelectionUnavailable()
    if kind == "INDEX" and selected[2] != "NIFTY 50":
        raise InstrumentSelectionUnavailable()
    return selected


def resolve_instrument(session_factory, principal: Principal, *, token: int,
                       symbol: str, exchange: str) -> dict:
    """Register a sourced cash root after an owner-bound current-list recheck."""
    from app.market_truth.identity import persist_canonical_instrument
    from app.market_truth.cash_reference import source_reference_for_symbol
    reference = source_reference_for_symbol(symbol, exchange)
    if not _instrument_token(token) or reference is None:
        raise InstrumentSelectionUnavailable()
    rows, connection_id = _fetch_instruments(session_factory, principal, exchange)
    instrument, evidence = reference
    selected = _selected_instrument(rows, token, symbol, exchange, instrument.asset_class)
    with session_factory() as session:
        # The definition is shared across owners. Serialize first registration
        # before reading it, while keeping the provider call outside this lock.
        begin_reservation(session, scope=f"index-definition:{instrument.address}")
        _, current_id = _instrument_connection(session, principal, session_factory)
        if current_id != connection_id:
            raise DataConnectionUnavailable("data connection changed during selection")
        persist_canonical_instrument(session, instrument)
        session.commit()
    return {
        "schema": "strategy-os-provider-instrument-selection/1",
        "reference_type": "CURRENT_PROVIDER_REFERENCE",
        "instrument": {"address": instrument.address, "definition": instrument.fact()},
        "definition_evidence": evidence,
        "selection": dict(zip(("symbol", "token", "name", "exchange", "kind"), selected)),
        "historical_mapping": "UNVERIFIED",
    }


class LocalDataAuthenticator(Protocol):
    """Test-only seam.  The production dependency returns ``None``."""

    def login_url(self, stable_keys: dict[str, str]) -> str: ...

    def exchange(self, stable_keys: dict[str, str], request_token: str) -> dict[str, str]: ...


def production_data_authenticator():
    """Construct the production Zerodha login seam with its closed DATA transport."""
    from app.providers.broker_auth import KiteAuthenticator
    authenticator = KiteAuthenticator()
    authenticator.callback_passthrough = "ZERODHA_REDIRECT_PARAMS"
    return authenticator


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _identity(principal: Principal) -> tuple[str, str, str]:
    if (principal.kind != "user" or principal.role != "owner"
            or not principal.organization_id or not principal.user_id
            or not principal.session_id):
        raise DataConnectionUnavailable("active owner browser session required")
    owner = owner_id_for(principal)
    if owner != principal.organization_id:
        raise DataConnectionUnavailable("active owner browser session required")
    return owner, principal.user_id, principal.session_id


def _active_identity(session, principal: Principal, *, lock: bool) -> tuple[str, str, str]:
    """Revalidate the principal's durable authority at the service boundary."""
    owner_id, user_id, session_id = _identity(principal)
    now = _now()
    statement = select(UserSession.session_id).join(
        User, User.user_id == UserSession.user_id).join(
        Organization, Organization.organization_id == UserSession.organization_id).join(
        Membership,
        (Membership.organization_id == UserSession.organization_id)
        & (Membership.user_id == UserSession.user_id)).where(
            UserSession.session_id == session_id,
            UserSession.user_id == user_id,
            UserSession.organization_id == owner_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            User.status == "active",
            Organization.status == "active",
            Membership.status == "active",
            Membership.role == "owner",
        )
    if lock:
        statement = statement.with_for_update()
    if session.scalar(statement) is None:
        raise DataConnectionUnavailable("active owner browser session required")
    return owner_id, user_id, session_id


def _account_id(
        session, owner_id: str, *, lock: bool,
        create_if_missing: bool = False) -> str | None:
    statement = select(BrokerAccount).where(
        BrokerAccount.owner_id == owner_id,
        BrokerAccount.broker == "kite",
    ).order_by(BrokerAccount.broker_account_id).limit(2)
    if lock:
        statement = statement.with_for_update()
    accounts = session.scalars(statement).all()
    if not accounts:
        if not create_if_missing:
            return None
        now = _now()
        account = BrokerAccount(
            broker_account_id=_data_only_account_id(owner_id),
            owner_id=owner_id,
            broker="kite",
            external_account_id=DATA_ONLY_EXTERNAL_ACCOUNT_ID,
            display_name=DATA_ONLY_ACCOUNT_NAME,
            status=DATA_ONLY_ACCOUNT_STATUS,
            created_at=now,
            updated_at=now,
        )
        occupied = session.get(BrokerAccount, account.broker_account_id)
        if occupied is not None:
            raise DataConnectionUnavailable(
                "owner-local Zerodha data account is unavailable")
        session.add(account)
        try:
            session.flush()
        except IntegrityError:
            raise DataConnectionUnavailable(
                "owner-local Zerodha data account is unavailable") from None
        return account.broker_account_id
    if len(accounts) != 1 or not is_data_account_anchor(accounts[0]):
        raise DataConnectionUnavailable(
            "exactly one owner-local Zerodha account is required")
    return accounts[0].broker_account_id


def _data_only_account_id(owner_id: str) -> str:
    return f"zerodha-data-{hashlib.sha256(owner_id.encode('utf-8')).hexdigest()[:48]}"


def _data_account_condition():
    return or_(
        BrokerAccount.status == "active",
        and_(
            BrokerAccount.status == DATA_ONLY_ACCOUNT_STATUS,
            BrokerAccount.external_account_id == DATA_ONLY_EXTERNAL_ACCOUNT_ID,
            BrokerAccount.display_name == DATA_ONLY_ACCOUNT_NAME,
        ),
    )


def _data_rows(session, owner_id: str, account_id: str, *, lock: bool) -> list[BrokerConnection]:
    statement = select(BrokerConnection).where(
        BrokerConnection.owner_id == owner_id,
        BrokerConnection.broker_account_id == account_id,
    ).order_by(BrokerConnection.id).limit(201)
    if lock:
        statement = statement.with_for_update()
    owner_rows = session.scalars(statement).all()
    if len(owner_rows) > 200:
        raise DataConnectionUnavailable("data connection history is unavailable")
    exact_capabilities = json.dumps(sorted(DATA_CAPABILITIES))
    return [row for row in owner_rows if (
        row.scope.startswith(DATA_SCOPE_PREFIX)
        or (row.broker == "kite" and row.capabilities_json == exact_capabilities)
    )]


def _active_row(rows: list[BrokerConnection]) -> BrokerConnection | None:
    active = [row for row in rows if row.status == "active"]
    if len(active) > 1:
        raise DataConnectionUnavailable("data connection state is unavailable")
    return active[0] if active else None


_ACTION_KEYS = (
    "create", "write_app_keys", "rotate_app_keys", "reauthenticate", "revoke",
)


def _actions(*allowed: str) -> dict[str, bool]:
    admitted = frozenset(allowed)
    return {name: name in admitted for name in _ACTION_KEYS}


def _projection(state: str, actions: dict[str, bool] | None = None) -> dict:
    return {
        "schema": "strategy-os-data-connection-status/1",
        "state": state,
        "provider": "ZERODHA",
        "role": "DATA",
        "ready": False,
        "credential_expiry": "UNVERIFIED",
        "rate_quota": "UNVERIFIED",
        "actions": actions if actions is not None else _actions(),
    }


def status(session, principal: Principal) -> dict:
    """Return one privacy-safe state.  Any unproved fact becomes UNAVAILABLE."""
    try:
        owner_id, user_id, session_id = _active_identity(
            session, principal, lock=False)
        account_id = _account_id(session, owner_id, lock=False)
        if account_id is None:
            return _projection("CONNECTION_REQUIRED", _actions("create"))
        rows = _data_rows(session, owner_id, account_id, lock=False)
        row = _active_row(rows)
        if row is None:
            if rows:
                validate_data_connection_row(rows[-1], active=False)
                if rows[-1].status == "revoked":
                    return _projection("REVOKED", _actions("create"))
                raise DataConnectionUnavailable("data connection state is unavailable")
            return _projection("CONNECTION_REQUIRED", _actions("create"))
        validate_data_connection_row(row)
        if not row.credential_ciphertext:
            return _projection(
                "APP_KEYS_REQUIRED", _actions("write_app_keys", "revoke"))
        store = OwnedConnectionStore.for_data_role(
            session, owner_id=owner_id, broker_account_id=account_id)
        bundle = store.read_data_oauth_bundle(row.id)
        if (not isinstance(bundle.get("api_key"), str) or not bundle["api_key"]
                or not isinstance(bundle.get("api_secret"), str) or not bundle["api_secret"]):
            raise DataConnectionUnavailable("data credential unavailable")
        completed = None
        if row.last_authenticated_at is not None:
            completed = session.scalar(select(OAuthCallbackState.state_digest).where(
                OAuthCallbackState.connection_id == row.id,
                OAuthCallbackState.organization_id == owner_id,
                OAuthCallbackState.user_id == user_id,
                OAuthCallbackState.session_id == session_id,
                OAuthCallbackState.consumed_at.is_not(None),
                OAuthCallbackState.revoked_at.is_(None),
                OAuthCallbackState.credential_stored_at == row.last_authenticated_at,
            ).limit(1))
        if completed is None:
            return _projection(
                "REAUTH_REQUIRED", _actions("reauthenticate", "rotate_app_keys", "revoke"))
        return _projection(
            "SESSION_PRESENT_UNVERIFIED",
            _actions("reauthenticate", "rotate_app_keys", "revoke"),
        )
    except (ConnectionNotFound, CredentialDecryptionFailed,
            CredentialVaultUnavailable, DataConnectionUnavailable, ValueError, TypeError):
        return _projection("UNAVAILABLE")


def create(session, principal: Principal) -> BrokerConnection:
    owner_id, _, _ = _identity(principal)
    begin_reservation(session, scope=f"v0-zerodha-data-account:{owner_id}")
    owner_id, _, _ = _active_identity(session, principal, lock=True)
    account_id = _account_id(
        session, owner_id, lock=True, create_if_missing=True)
    if account_id is None:  # Defensive: create_if_missing must resolve one row.
        raise DataConnectionUnavailable("Zerodha data account is unavailable")
    store = OwnedConnectionStore.for_data_role(
        session, owner_id=owner_id, broker_account_id=account_id)
    return store.create_data_connection()


def write_app_keys(
        session, principal: Principal, keys: dict[str, str], *, rotate: bool,
) -> BrokerConnection:
    owner_id, _, _ = _active_identity(session, principal, lock=True)
    account_id = _account_id(session, owner_id, lock=True)
    rows = _data_rows(session, owner_id, account_id, lock=True)
    row = _active_row(rows)
    if row is None:
        raise ConnectionNotFound("data connection unavailable")
    store = OwnedConnectionStore.for_data_role(
        session, owner_id=owner_id, broker_account_id=account_id)
    return store.write_data_app_keys(row.id, keys, rotate=rotate)


def revoke(session, principal: Principal) -> BrokerConnection:
    owner_id, _, _ = _active_identity(session, principal, lock=True)
    account_id = _account_id(session, owner_id, lock=True)
    rows = _data_rows(session, owner_id, account_id, lock=True)
    row = _active_row(rows)
    if row is None:
        raise ConnectionNotFound("data connection unavailable")
    now = _now()
    session.execute(update(OAuthCallbackState).where(
        OAuthCallbackState.connection_id == row.id,
        OAuthCallbackState.organization_id == owner_id,
        OAuthCallbackState.revoked_at.is_(None),
    ).values(revoked_at=now))
    store = OwnedConnectionStore.for_data_role(
        session, owner_id=owner_id, broker_account_id=account_id)
    return store.revoke(row.id)


def _stable_keys(store: OwnedConnectionStore, connection_id: int) -> dict[str, str]:
    bundle = store.read_data_oauth_bundle(connection_id)
    keys = {name: bundle.get(name) for name in ("api_key", "api_secret")}
    if any(not isinstance(value, str) or not value for value in keys.values()):
        raise DataConnectionUnavailable("application keys are required")
    return {name: str(value) for name, value in keys.items()}


def _with_state(url: str, raw_state: str, *, zerodha_redirect_params: bool) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.fragment
            or any(name in {"state", "redirect_params"} for name, _ in query)):
        raise DataConnectionUnavailable("authenticator login URL is invalid")
    if zerodha_redirect_params:
        query.append(("redirect_params", urlencode({"state": raw_state})))
    else:
        query.append(("state", raw_state))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                       urlencode(query), ""))


def initiate(session, principal: Principal,
             authenticator: LocalDataAuthenticator | None) -> str:
    if authenticator is None:
        raise DataConnectionUnavailable("data provider authentication is unavailable")
    owner_id, user_id, session_id = _active_identity(
        session, principal, lock=True)
    now = _now()
    account_id = _account_id(session, owner_id, lock=True)
    rows = _data_rows(session, owner_id, account_id, lock=True)
    row = _active_row(rows)
    if row is None:
        raise ConnectionNotFound("data connection unavailable")
    store = OwnedConnectionStore.for_data_role(
        session, owner_id=owner_id, broker_account_id=account_id)
    stable_keys = _stable_keys(store, row.id)
    login_url = authenticator.login_url(dict(stable_keys))
    raw_state = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    session.execute(delete(OAuthCallbackState).where(
        OAuthCallbackState.connection_id == row.id,
        OAuthCallbackState.organization_id == owner_id,
        (
            OAuthCallbackState.consumed_at.is_not(None)
            | OAuthCallbackState.revoked_at.is_not(None)
            | (OAuthCallbackState.expires_at <= now)
        ),
    ))
    session.execute(update(OAuthCallbackState).where(
        OAuthCallbackState.connection_id == row.id,
        OAuthCallbackState.organization_id == owner_id,
        OAuthCallbackState.revoked_at.is_(None),
    ).values(revoked_at=now))
    session.add(OAuthCallbackState(
        state_digest=digest,
        connection_id=row.id,
        session_id=session_id,
        user_id=user_id,
        organization_id=owner_id,
        created_at=now,
        expires_at=now + STATE_TTL,
    ))
    session.flush()
    return _with_state(
        login_url,
        raw_state,
        zerodha_redirect_params=(
            getattr(authenticator, "callback_passthrough", None)
            == "ZERODHA_REDIRECT_PARAMS"
        ),
    )


def _digest_state(raw_state: str | None) -> str | None:
    if (not isinstance(raw_state, str) or not raw_state
            or len(raw_state) > MAX_TOKEN_LENGTH):
        return None
    return hashlib.sha256(raw_state.encode("utf-8")).hexdigest()


def complete(
        session_factory, *, raw_state: str | None, request_token: str | None,
        authenticator: LocalDataAuthenticator | None,
) -> bool:
    """Consume once, fake-exchange outside a transaction, then store atomically."""
    digest = _digest_state(raw_state)
    if (authenticator is None or digest is None or not isinstance(request_token, str)
            or not request_token or len(request_token) > MAX_TOKEN_LENGTH):
        return False
    now = _now()
    with session_factory() as session:
        callback = session.scalar(select(OAuthCallbackState).join(
            UserSession, UserSession.session_id == OAuthCallbackState.session_id).join(
            Membership,
            (Membership.organization_id == UserSession.organization_id)
            & (Membership.user_id == UserSession.user_id)).join(
            User, User.user_id == UserSession.user_id).join(
            Organization, Organization.organization_id == UserSession.organization_id).join(
            BrokerConnection, BrokerConnection.id == OAuthCallbackState.connection_id).join(
            BrokerAccount,
            BrokerAccount.broker_account_id == BrokerConnection.broker_account_id).where(
                OAuthCallbackState.state_digest == digest,
                OAuthCallbackState.expires_at > now,
                OAuthCallbackState.revoked_at.is_(None),
                OAuthCallbackState.consumed_at.is_(None),
                UserSession.session_id == OAuthCallbackState.session_id,
                UserSession.user_id == OAuthCallbackState.user_id,
                UserSession.organization_id == OAuthCallbackState.organization_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                Membership.status == "active",
                Membership.role == "owner",
                User.status == "active",
                Organization.status == "active",
                BrokerConnection.owner_id == OAuthCallbackState.organization_id,
                BrokerConnection.status == "active",
                BrokerConnection.broker == "kite",
                BrokerConnection.scope.like(f"{DATA_SCOPE_PREFIX}%"),
                BrokerConnection.capabilities_json == json.dumps(sorted(DATA_CAPABILITIES)),
                BrokerAccount.owner_id == OAuthCallbackState.organization_id,
                BrokerAccount.broker == "kite",
                _data_account_condition(),
            ))
        if callback is None:
            return False
        consumed = session.execute(update(OAuthCallbackState).where(
            OAuthCallbackState.state_digest == digest,
            OAuthCallbackState.expires_at > now,
            OAuthCallbackState.revoked_at.is_(None),
            OAuthCallbackState.consumed_at.is_(None),
        ).values(consumed_at=now))
        if consumed.rowcount != 1:
            session.rollback()
            return False
        owner_id = callback.organization_id
        user_id = callback.user_id
        session_id = callback.session_id
        connection_id = callback.connection_id
        account_id = session.scalar(select(BrokerConnection.broker_account_id).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == owner_id,
        ))
        try:
            store = OwnedConnectionStore.for_data_role(
                session, owner_id=owner_id, broker_account_id=account_id)
            stable_keys = _stable_keys(store, connection_id)
        except (ConnectionNotFound, CredentialDecryptionFailed,
                CredentialVaultUnavailable, DataConnectionUnavailable, ValueError):
            session.commit()
            return False
        session.commit()
    try:
        exchanged = authenticator.exchange(dict(stable_keys), request_token)
    except Exception:
        return False
    if (not isinstance(exchanged, dict)
            or not isinstance(exchanged.get("access_token"), str)
            or not exchanged["access_token"] or len(exchanged["access_token"]) > 4096):
        return False
    bundle = {**stable_keys, "access_token": exchanged["access_token"]}
    try:
        ciphertext, key_id = seal(bundle)
    except CredentialVaultUnavailable:
        return False
    stored_at = _now()
    with session_factory() as session:
        identity_active = exists(select(UserSession.session_id).join(
            User, User.user_id == UserSession.user_id).join(
            Organization, Organization.organization_id == UserSession.organization_id).join(
            Membership,
            (Membership.organization_id == UserSession.organization_id)
            & (Membership.user_id == UserSession.user_id)).where(
                UserSession.session_id == session_id,
                UserSession.user_id == user_id,
                UserSession.organization_id == owner_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > stored_at,
                User.status == "active",
                Organization.status == "active",
                Membership.status == "active",
                Membership.role == "owner",
        ))
        account_active = exists(select(BrokerAccount.broker_account_id).where(
            BrokerAccount.broker_account_id == account_id,
            BrokerAccount.owner_id == owner_id,
            BrokerAccount.broker == "kite",
            _data_account_condition(),
        ))
        changed = session.execute(update(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == owner_id,
            BrokerConnection.broker_account_id == account_id,
            BrokerConnection.broker == "kite",
            BrokerConnection.scope.like(f"{DATA_SCOPE_PREFIX}%"),
            BrokerConnection.capabilities_json == json.dumps(sorted(DATA_CAPABILITIES)),
            BrokerConnection.status == "active",
            identity_active,
            account_active,
        ).values(
            credential_ciphertext=ciphertext,
            credential_key_id=key_id,
            last_authenticated_at=stored_at,
            updated_at=stored_at,
        ))
        receipt = session.execute(update(OAuthCallbackState).where(
            OAuthCallbackState.state_digest == digest,
            OAuthCallbackState.connection_id == connection_id,
            OAuthCallbackState.organization_id == owner_id,
            OAuthCallbackState.user_id == user_id,
            OAuthCallbackState.session_id == session_id,
            OAuthCallbackState.consumed_at.is_not(None),
            OAuthCallbackState.revoked_at.is_(None),
            OAuthCallbackState.credential_stored_at.is_(None),
        ).values(credential_stored_at=stored_at))
        if changed.rowcount != 1 or receipt.rowcount != 1:
            session.rollback()
            return False
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=account_id,
            aggregate_type="broker_connection", aggregate_id=str(connection_id),
            event_type="execution.connection.changed", projection="connections",
            producer_key=(f"connection:{connection_id}:data-oauth:"
                          f"{hashlib.sha256((session_id + stored_at.isoformat()).encode()).hexdigest()}"),
            facts={"state": "session_present_unverified", "ready": False},
        )
        session.commit()
    return True


__all__ = [
    "LocalDataAuthenticator", "production_data_authenticator", "status", "create",
    "write_app_keys", "initiate", "complete", "revoke", "search_instruments",
]
