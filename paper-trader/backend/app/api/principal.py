"""H3 (Phase H) — who is asking, and the one place that decides if they may.

Today this system has exactly ONE user: the owner, holding one shared bearer
token (`PT_API_TOKEN`). That is not going to change in this phase — no multi-user
features are being built here. What IS being built is the seam: a `Principal`
object that exists on every request, and a single `require()` call that
authorization rules can later be written inside. The audit's H3 finding is not
"auth is weak", it is "there is no principal in the system", so permissions and
licensing have nothing to attach to.

Two deliberate choices worth defending:

**There is no null principal.** When `PT_API_TOKEN` is empty — the dev/mock/test
default, and the current production posture on a tailnet-only box — auth is
disabled, and resolution yields an explicit `ANONYMOUS_OWNER` rather than `None`.
If it yielded `None`, every future caller would grow an `if principal is None`
branch, and that branch would be the one nobody tests and everybody gets wrong.
The identity is different (`anonymous-owner` vs `owner`) and `authenticated` says
which, so a later phase can refuse to serve a sensitive route to an unauthenticated
principal without inventing the distinction retroactively.

**Rejection is not a principal.** A supplied-but-wrong token resolves to `None`
from `resolve_*`, which the middleware turns into 401. `None` therefore means
exactly one thing — "credential presented and refused" — and never reaches a route.

Scopes are modelled now and unused now, on purpose: `{"*"}` today, real scope
strings when there is a second kind of caller. The shape is the deliverable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, Request, WebSocket

from app.api.auth import extract_token, token_ok, ws_authorized
from app.core.config import get_settings
from app.db.models import LEGACY_OWNER_ID

# `owner` holds the shared token; `anonymous_owner` is the same human on a box
# with auth switched off. Both are the owner — the distinction is how we know it.
PrincipalKind = Literal["owner", "anonymous_owner"]

# The wildcard scope. A real scope vocabulary belongs to the phase that has a
# second principal to write it for; inventing one now would be fiction.
SCOPE_ALL = "*"


@dataclass(frozen=True)
class Principal:
    """Immutable identity of the caller. Frozen because a request handler that
    can mutate its own principal is an authorization bug waiting to happen."""

    id: str
    kind: PrincipalKind
    scopes: frozenset[str]

    @property
    def is_owner(self) -> bool:
        return self.kind in ("owner", "anonymous_owner")

    @property
    def authenticated(self) -> bool:
        """Did this principal actually present a credential? False when auth is
        disabled — which is a configuration statement, not a security claim."""
        return self.kind == "owner"

    def has_scope(self, scope: str) -> bool:
        return SCOPE_ALL in self.scopes or scope in self.scopes

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "scopes": sorted(self.scopes),
                "authenticated": self.authenticated}


# The single-owner world, stated explicitly rather than implied by the absence of
# any other value. Module-level singletons: identity comparison is meaningful.
OWNER = Principal(id="owner", kind="owner", scopes=frozenset({SCOPE_ALL}))
ANONYMOUS_OWNER = Principal(
    id="anonymous-owner", kind="anonymous_owner", scopes=frozenset({SCOPE_ALL}))


def auth_enabled() -> bool:
    return bool(get_settings().api_token)


def resolve_principal(supplied_token: str | None) -> Principal | None:
    """Core resolution, framework-free so it is unit-testable without a request.

    Returns `None` ONLY for a rejected credential. Note the ordering: auth-disabled
    is checked first, so an unset token can never be "matched" by a caller sending
    an empty string — `token_ok` already guards that, and this keeps the two in step.
    """
    if not auth_enabled():
        return ANONYMOUS_OWNER
    return OWNER if token_ok(supplied_token) else None


def resolve_http_principal(request: Request) -> Principal | None:
    return resolve_principal(extract_token(request.headers))


def resolve_ws_principal(ws: WebSocket) -> Principal | None:
    """WebSockets carry the token as a query param (browsers cannot set headers
    on a WS handshake), so it goes through `ws_authorized` rather than the header
    extractor — one function, so the two paths cannot drift apart."""
    if not auth_enabled():
        return ANONYMOUS_OWNER
    return OWNER if ws_authorized(ws) else None


def get_principal(request: Request) -> Principal:
    """FastAPI dependency: `principal: Principal = Depends(get_principal)`.

    Reads what the middleware already resolved (one resolution per request), and
    falls back to resolving inline for the cases where the middleware did not run
    — a route called through a bare ASGI harness, or a future sub-application.
    The fallback re-checks the credential rather than assuming anonymity; a
    fallback that defaulted to `ANONYMOUS_OWNER` would be a bypass.
    """
    principal = getattr(request.state, "principal", None)
    if principal is None:
        principal = resolve_http_principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return principal


# ── the authorization boundary ─────────────────────────────────────────────
# ONE function. Every future rule goes inside it, and reviewing authorization
# means reading this file. The moment a check appears anywhere else, the property
# that makes this seam worth having is gone.

class Forbidden(HTTPException):
    def __init__(self, detail: str = "forbidden") -> None:
        super().__init__(status_code=403, detail=detail)


def is_allowed(principal: Principal | None, action: str, resource: Any = None) -> bool:
    """The policy, as a pure predicate.

    Currently: the owner may do everything. That is not a placeholder that forgot
    to be filled in — it is the accurate statement of a single-user system, and
    writing it as code means the day a second principal exists, the diff is
    confined to this function instead of being a hunt through 45 routes.

    `resource` is accepted and ignored on purpose. Per-resource authorization
    (H3's "no per-resource authorization") needs a resource identity to hang off,
    and C1 is about to re-key resources away from the instrument symbol — taking
    the argument now means that phase changes policy, not every call site.
    """
    if principal is None:
        return False
    return principal.is_owner


def owner_id_for(principal: Principal | None) -> str:
    """The `owner_id` column value this principal's rows belong to.

    Deliberately NOT `principal.id`. `ANONYMOUS_OWNER.id` is `"anonymous-owner"`, and auth
    disabled is the shipped default and the current production posture on the tailnet-only box —
    so keying rows on the principal id would file every connection created with auth off under an
    owner the engine never reads. `LiveBroker` and `configured_execution_connection` both resolve
    the owner from `settings.owner_id`, and this returns the same value so the API writes the rows
    the engine reads. The two identities are the same human; `kind` is how we know which.

    Raises for anything that is not an owner, so a future non-owner principal cannot silently
    acquire the owner's connections by falling through a default.
    """
    if principal is None or not principal.is_owner:
        raise Forbidden("no owner identity for this principal")
    configured = (get_settings().owner_id or "").strip()
    return configured or LEGACY_OWNER_ID


def require(principal: Principal | None, action: str, resource: Any = None) -> None:
    """Assert authorization or raise. `require`, not `check`, because a boolean
    returned into an `if` is a check somebody eventually forgets to write."""
    if not is_allowed(principal, action, resource):
        raise Forbidden(f"principal is not permitted to {action}")
