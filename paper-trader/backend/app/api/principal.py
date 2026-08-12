"""Resolved request identity and the one authorization policy boundary.

HTTP and WebSocket adapters only extract a bearer credential.  This module
hashes it, resolves the durable ``UserSession`` record, and then proves its
user, organization and membership remain active before returning a principal.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, Request, WebSocket
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.auth import extract_token
from app.core.config import effective_auth_enabled, get_settings
from app.db.models import (
    LEGACY_OWNER_ID,
    LEGACY_USER_ID,
    Membership,
    Organization,
    User,
    UserSession,
)
from app.db.session import SessionLocal


PrincipalKind = Literal["user", "development_anonymous", "owner", "anonymous_owner", "service"]
SCOPE_ALL = "*"

# Closed product authorization vocabulary.  Route handlers name one of these
# capabilities and repositories bind the resource lookup to organization_id
# before a row can be materialized.  Do not treat arbitrary strings as scopes:
# a typo must deny rather than silently create a permission.
READ_ACTIONS = frozenset({
    "read:project", "read:graph", "read:layout", "read:review",
    "read:research", "read:backtest", "read:watchlist", "read:archive",
    "read:runtime-config", "read:portfolio", "read:execution",
})
MEMBER_ACTIONS = frozenset({
    "write:project", "write:graph", "publish:graph", "write:layout",
    "write:review", "start:research", "compare:research", "write:backtest",
})
ADMIN_ACTIONS = frozenset({
    "archive:project", "write:runtime-config", "write:watchlist",
    "archive:strategy", "decision:research",
})
OWNER_ACTIONS = frozenset({
    "read:brokers", "read:connections", "read:connection", "create:connection", "write:credential",
    "revoke:connection", "authoritative:execution",
})
ACTION_VOCABULARY = READ_ACTIONS | MEMBER_ACTIONS | ADMIN_ACTIONS | OWNER_ACTIONS
ROLE_ACTIONS = {
    "viewer": READ_ACTIONS,
    "member": READ_ACTIONS | MEMBER_ACTIONS,
    "admin": READ_ACTIONS | MEMBER_ACTIONS | ADMIN_ACTIONS,
    "owner": ACTION_VOCABULARY,
}


def action_for_request(method: str, path: str) -> str | None:
    """Return the one closed capability for a tenant-facing HTTP endpoint.

    This deliberately classifies only the USER/research product surface.  The
    money and credential planes keep their explicit Task 5C policy calls; an
    unclassified path is never promoted into this vocabulary by accident.
    """
    method = method.upper()
    if path == "/api/brokers":
        return "read:brokers" if method == "GET" else None
    if path == "/api/connections":
        return "read:connections" if method == "GET" else (
            "create:connection" if method == "POST" else None)
    if path.startswith("/api/connections/"):
        if path.endswith("/credential"):
            return "write:credential" if method == "POST" else None
        if path.endswith("/oauth/initiate"):
            return "write:credential" if method == "POST" else None
        if path.endswith("/login"):
            return "read:connection" if method == "GET" else None
        return "read:connection" if method == "GET" else (
            "revoke:connection" if method == "DELETE" else None)
    execution_exact = {
        "/api/status", "/api/calendar", "/api/login", "/api/session", "/api/instruments",
        "/api/trades", "/api/signals",
        "/api/account-pnl", "/api/dashboard", "/api/positions", "/api/provider-health",
        "/api/execution/state", "/api/execution/arm", "/api/execution/kill",
        "/api/execution/cockpit", "/api/execution/cockpit/deployments",
        "/api/ir-shadow/deployments", "/api/ir-paper/deployments",
    }
    if (path in execution_exact or path.startswith(("/api/ledger/", "/api/positions/", "/api/instruments/",
                                                    "/api/ir-shadow/deployments/",
                                                    "/api/ir-paper/deployments/"))):
        return ("read:execution" if method == "GET" and path not in {"/api/login", "/api/session"}
                else "authoritative:execution")
    if path.startswith("/api/backtest"):
        return "read:backtest" if method == "GET" else "write:backtest"
    if path == "/api/settings":
        return "read:runtime-config" if method == "GET" else "write:runtime-config"
    if path == "/api/settings/reset":
        return "write:runtime-config"
    if path.startswith("/api/research/operations"):
        return "read:research"
    if path.startswith("/api/ir/graphs/") and "/layout" in path:
        return "read:layout" if method == "GET" else "write:layout"
    if path.startswith("/api/portfolio"):
        if path not in {
            "/api/portfolio/promotions", "/api/portfolio/deploy",
            "/api/portfolio/watchlists", "/api/portfolio/archive",
        } and not path.startswith("/api/portfolio/promotions/") and not path.startswith("/api/portfolio/watchlists/") and not path.startswith("/api/portfolio/archive/"):
            # Legacy runner endpoints are not organization-scoped repositories.
            # Task 5C must replace them before durable user principals can use
            # them; leave their action unclassified so the HTTP boundary denies.
            return None
        if method == "GET":
            return "read:portfolio"
        if "/watchlists/" in path:
            return "write:watchlist"
        if "/archive/" in path:
            return "archive:strategy"
        return "write:watchlist"
    if not path.startswith("/api/ir/projects/") and path != "/api/ir/projects":
        return None
    if "/review" in path:
        if method == "GET":
            return "read:review"
        return "write:review"
    if "/candidates/" in path and path.endswith("/decisions"):
        return "decision:research"
    if "/experiments" in path or "/findings" in path or "/version-comparisons" in path:
        if method == "GET":
            return "read:research"
        if "compar" in path:
            return "compare:research"
        return "start:research"
    if "/layouts" in path or "/presentation-edits" in path:
        return "read:layout" if method == "GET" else "write:layout"
    if "/graphs" in path:
        if method == "GET":
            return "read:graph"
        if path.endswith("/versions"):
            return "publish:graph"
        return "write:graph"
    if path.endswith("/status"):
        return "archive:project"
    return "read:project" if method == "GET" else "write:project"


class _WebSocketPayloadRedactionFilter(logging.Filter):
    """Keep WebSocket frame diagnostics without ever formatting frame payloads.

    The ``websockets`` protocol logs incoming frames as ``"< %s"`` where the
    ``Frame`` representation includes its complete text payload.  Our first
    application message contains the bearer, so suppressing DEBUG wholesale is
    not acceptable: it also hides unrelated production diagnostics.  This
    filter replaces only inbound TEXT/BINARY frame records with opcode/length
    metadata before they reach handlers or propagated loggers.
    """

    _TEXT_OR_BINARY = re.compile(r"^< (?:TEXT|BINARY)\b")

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.name.startswith(("uvicorn", "websockets")):
            return True
        frame = record.args[0] if isinstance(record.args, tuple) and record.args else None
        if (record.msg == "< %s" and hasattr(frame, "opcode") and hasattr(frame, "data")):
            data = frame.data
            length = len(data) if isinstance(data, (bytes, bytearray, str)) else 0
            opcode = getattr(getattr(frame, "opcode", None), "name", "frame").lower()
            record.msg = (
                f"< [websocket inbound {opcode} payload redacted; {length} bytes]"
            )
            record.args = ()
            return True
        # Some protocol versions pre-format frames before forwarding records.
        try:
            formatted = record.getMessage()
        except Exception:
            return True
        if self._TEXT_OR_BINARY.match(formatted):
            record.msg = "< [websocket inbound payload redacted]"
            record.args = ()
        return True


def install_websocket_payload_redaction() -> None:
    """Install one idempotent filter before any ASGI WebSocket handshake.

    Uvicorn passes ``uvicorn.error`` into its ``websockets`` protocol, while
    direct protocol deployments use the ``websockets.*`` loggers.  Attach to
    those exact producers; other application and access logs are unchanged.
    """
    for name in ("uvicorn.error", "uvicorn.protocols.websockets",
                 "websockets.protocol", "websockets.server", "websockets.legacy.server"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, _WebSocketPayloadRedactionFilter) for item in logger.filters):
            logger.addFilter(_WebSocketPayloadRedactionFilter())


def _now() -> dt.datetime:
    """SQLite stores the project's datetime values without timezone metadata."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _db_time(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is not None:
        return value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value


def token_digest(credential: str | None) -> str | None:
    """Return the canonical digest without retaining or comparing bearer plaintext."""
    if not isinstance(credential, str) or not credential or credential != credential.strip():
        return None
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()




@dataclass(frozen=True)
class Principal:
    """Immutable resolved identity.  ``id`` remains a compatibility alias for user id."""

    id: str
    kind: PrincipalKind
    scopes: frozenset[str]
    user_id: str | None = None
    organization_id: str | None = None
    role: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.user_id is None and self.kind == "user":
            object.__setattr__(self, "user_id", self.id)

    @property
    def is_owner(self) -> bool:
        return self.role == "owner" or self.kind in ("owner", "anonymous_owner")

    @property
    def authenticated(self) -> bool:
        return self.kind not in ("development_anonymous", "anonymous_owner")

    def has_scope(self, scope: str) -> bool:
        return SCOPE_ALL in self.scopes or scope in self.scopes

    def to_dict(self) -> dict[str, Any]:
        if self.kind in ("owner", "anonymous_owner"):
            return {"id": self.id, "kind": self.kind, "scopes": sorted(self.scopes),
                    "authenticated": self.authenticated}
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "role": self.role,
            "kind": self.kind,
            "scopes": sorted(self.scopes),
            "authenticated": self.authenticated,
        }


# Compatibility names remain available to dependency overrides and legacy
# single-owner callers. Real authentication never returns OWNER directly; it
# returns a durable-session principal.  The named development principal stays
# deliberately distinct from OWNER while retaining its legacy owner capability.
OWNER = Principal(id="owner", kind="owner", scopes=frozenset({SCOPE_ALL}),
                  user_id=LEGACY_USER_ID, organization_id=LEGACY_OWNER_ID, role="owner")
DEVELOPMENT_ANONYMOUS = Principal(
    id="anonymous-owner", kind="anonymous_owner", scopes=frozenset({SCOPE_ALL}))
ANONYMOUS_OWNER = DEVELOPMENT_ANONYMOUS


@dataclass(frozen=True)
class IssuedBearerCredential:
    """One-time issuance result; only this in-memory return carries the bearer value."""

    session_id: str
    token: str
    expires_at: dt.datetime


def auth_enabled() -> bool:
    return effective_auth_enabled(get_settings())


def _active_membership(session: Session, *, user_id: str, organization_id: str) -> Membership | None:
    return session.scalar(
        select(Membership).join(User, User.user_id == Membership.user_id).join(
            Organization, Organization.organization_id == Membership.organization_id).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
            Membership.status == "active",
            User.status == "active",
            Organization.status == "active",
        ))


def issue_user_session(session: Session, *, user_id: str, organization_id: str,
                       expires_at: dt.datetime,
                       session_id: str | None = None) -> IssuedBearerCredential:
    """Create a session for an existing active membership.

    Tokens generated here contain 32 random bytes (256 random bits) before URL
    encoding.  The issuance interface never accepts caller-chosen bearer
    material, so a weak test/demo value cannot accidentally enter production.
    """
    membership = _active_membership(session, user_id=user_id, organization_id=organization_id)
    if membership is None:
        raise ValueError("cannot issue a session for an inactive membership")
    raw = secrets.token_urlsafe(32)
    digest = token_digest(raw)
    if digest is None:
        raise ValueError("bearer credential is malformed")
    expiry = _db_time(expires_at)
    handle = session_id or secrets.token_urlsafe(18)
    session.add(UserSession(session_id=handle, token_digest=digest, user_id=user_id,
                            organization_id=organization_id, issued_at=_now(),
                            expires_at=expiry))
    return IssuedBearerCredential(session_id=handle, token=raw, expires_at=expiry)


def revoke_user_session(session: Session, session_id: str,
                        *, revoked_at: dt.datetime | None = None) -> bool:
    """Atomically revoke at most one still-active session without reading its bearer."""
    result = session.execute(update(UserSession).where(
        UserSession.session_id == session_id,
        UserSession.revoked_at.is_(None),
    ).values(revoked_at=_db_time(revoked_at or _now())))
    return result.rowcount == 1


def bootstrap_legacy_session(session: Session, legacy_token: str | None) -> UserSession | None:
    """Bind an old configured token to the seeded identity without plaintext comparison.

    A digest already bound to another identity is left untouched.  That makes an
    accidental or hostile foreign binding visible to callers without silently
    reassigning a credential that belongs to someone else.
    """
    digest = token_digest(legacy_token)
    if digest is None:
        return None
    existing = session.scalar(select(UserSession).where(UserSession.token_digest == digest))
    if existing is not None:
        if (existing.user_id != LEGACY_USER_ID
                or existing.organization_id != LEGACY_OWNER_ID):
            raise RuntimeError("legacy token digest is already bound to a foreign user session")
        return existing
    row = UserSession(session_id=secrets.token_urlsafe(18), token_digest=digest,
                      user_id=LEGACY_USER_ID, organization_id=LEGACY_OWNER_ID,
                      issued_at=_now(), expires_at=dt.datetime(9999, 12, 31))
    session.add(row)
    return row


def resolve_principal(supplied_token: str | None) -> Principal | None:
    """Resolve one credential or fail closed without leaking why it failed.

    The first query is against ``user_sessions.token_digest`` alone.  Unknown
    credentials therefore do not materialize a user or membership and all
    unknown, malformed, expired and revoked credentials return the same ``None``.
    """
    if not auth_enabled():
        return DEVELOPMENT_ANONYMOUS
    digest = token_digest(supplied_token)
    if digest is None:
        return None
    now = _now()
    try:
        with SessionLocal() as session:
            user_session = session.scalar(select(UserSession).where(
                UserSession.token_digest == digest,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            ))
            # Normal bootstraps create this row in ``init_db``.  This small
            # compatibility fallback covers an already-running process whose
            # configured legacy token was rotated without a restart; it compares
            # only digests and never persists or compares bearer plaintext.
            if user_session is None and secrets.compare_digest(
                    digest, token_digest(get_settings().api_token) or ""):
                bootstrap_legacy_session(session, get_settings().api_token)
                session.commit()
                user_session = session.scalar(select(UserSession).where(
                    UserSession.token_digest == digest,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                ))
            if user_session is None:
                return None
            return _principal_for_active_session(session, user_session)
    except OperationalError:
        # Startup performs init_db before the app accepts requests.  A direct
        # caller racing a failed/incomplete startup must fail closed rather than
        # turn a missing migration into an exception or anonymous access.
        return None


def _principal_for_active_session(session: Session, user_session: UserSession) -> Principal | None:
    """The one membership-aware conversion used by HTTP and WS proof boundaries."""
    membership = _active_membership(session, user_id=user_session.user_id,
                                    organization_id=user_session.organization_id)
    if membership is None:
        return None
    # Preserve the established public principal contract for the one legacy
    # bootstrap credential.  Its backing identity is nevertheless a durable
    # UserSession linked to ``owner-user`` / ``owner``; this singleton only
    # maintains the old API shape for dependency overrides and callers.
    if (user_session.user_id == LEGACY_USER_ID
            and user_session.organization_id == LEGACY_OWNER_ID):
        return Principal(id=OWNER.id, kind=OWNER.kind, scopes=OWNER.scopes,
                         user_id=OWNER.user_id, organization_id=OWNER.organization_id,
                         role=OWNER.role, session_id=user_session.session_id)
    # Roles are persisted independently of scopes.  Task 5B introduces
    # resource-family permissions; active memberships retain the existing broad
    # route capability until that conversion is complete.
    return Principal(id=user_session.user_id, kind="user", scopes=frozenset({SCOPE_ALL}),
                     user_id=user_session.user_id,
                     organization_id=user_session.organization_id,
                     role=membership.role, session_id=user_session.session_id)


def resolve_http_principal(request: Request) -> Principal | None:
    return resolve_principal(extract_token(request.headers))


def resolve_ws_principal(ws: WebSocket) -> Principal | None:
    """WebSockets never accept a bearer during the logged handshake.

    ``authenticate_websocket`` below performs first-frame authentication after
    accept, before joining a delivery channel.  This function exists only as a
    rejection boundary for callers that previously tried query/header/cookie
    token resolution.
    """
    return None


def resolve_ws_proof(_session_id: str | None, _nonce: str, bearer: str | None) -> Principal | None:
    """Resolve the quarantined first application frame through the HTTP service."""
    return resolve_principal(bearer)


async def authenticate_websocket(ws: WebSocket) -> Principal | None:
    """Quarantine a socket until it proves possession of its session bearer."""
    await ws.accept()
    if not auth_enabled():
        return DEVELOPMENT_ANONYMOUS
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
        payload = json.loads(raw)
    except Exception:
        await ws.close(code=1008)
        return None
    principal = resolve_ws_proof(None, "", payload.get("bearer")) \
        if isinstance(payload, dict) and payload.get("type") == "authenticate" else None
    if principal is None:
        await ws.close(code=1008)
    return principal


def get_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        principal = resolve_http_principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return principal


class Forbidden(HTTPException):
    def __init__(self, detail: str = "forbidden") -> None:
        super().__init__(status_code=403, detail=detail)


def is_allowed(principal: Principal | None, action: str, resource: Any = None) -> bool:
    """Fail-closed role/scope/owner policy for an owned product resource."""
    if principal is None or action not in ACTION_VOCABULARY:
        return False
    role = "owner" if principal.kind in ("owner", "anonymous_owner") else principal.role
    allowed_by_role = ROLE_ACTIONS.get(role or "", frozenset())
    if action not in allowed_by_role or not principal.has_scope(action):
        return False
    resource_owner = getattr(resource, "owner_id", None)
    # Connections are Task 5C.  Their collection routes have no existing row
    # to bind, so preserve the owner-only collection contract without granting
    # a resource-less capability to USER/research actions.
    if resource_owner is None:
        return role == "owner" and action in OWNER_ACTIONS
    try:
        owner_id = owner_id_for(principal)
    except Forbidden:
        return False
    if str(resource_owner) != owner_id:
        return False
    return True


def is_request_allowed(principal: Principal | None, action: str) -> bool:
    """Apply the closed action policy before an owner-scoped repository lookup.

    SQL repositories still bind every supplied identifier to the organization
    before materializing an object.  At this boundary there is intentionally no
    client-supplied resource to authorize, so use the principal's derived owner
    only to exercise the same policy predicate.
    """
    if principal is None:
        return False
    try:
        owner_id = owner_id_for(principal)
    except Forbidden:
        return False

    class _RequestOwner:
        def __init__(self, value: str):
            self.owner_id = value

    return is_allowed(principal, action, _RequestOwner(owner_id))


def owner_id_for(principal: Principal | None) -> str:
    if principal is None:
        raise Forbidden("no owner identity for this principal")
    # Existing dependency overrides use the original owner-shaped principal.
    if principal.kind in ("owner", "anonymous_owner"):
        configured = (get_settings().owner_id or "").strip()
        return configured or LEGACY_OWNER_ID
    if principal.organization_id:
        return principal.organization_id
    raise Forbidden("no owner identity for this principal")


def require(principal: Principal | None, action: str, resource: Any = None) -> None:
    if not is_allowed(principal, action, resource):
        raise Forbidden(f"principal is not permitted to {action}")
