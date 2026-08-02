"""H3 (Phase H) — API versioning applied at MOUNT time, not in the route sources.

Why it is done this way rather than by editing the decorators
-------------------------------------------------------------
The ~45 REST routes carry their full path in the decorator (`@router.get(
"/api/status")`), not on the router. That means `include_router(prefix="/api/v1")`
cannot produce `/api/v1/status` — it produces `/api/v1/api/status`. The obvious
alternative, rewriting 45 decorator strings, is a large diff spread across three
route modules that other phases are editing right now, and every edited line is a
chance to change a LIVE path by one character. The shipped SPA and
`scripts/deploy.sh` both hardcode unprefixed paths, and a typo there is an outage,
not a test failure.

So instead: the same endpoint callables are registered a SECOND time under
rewritten paths. Nothing about the existing registration is touched, which is why
the old paths stay byte-identical — they are literally the same route objects
serving the same handlers as before this module existed.

Deprecation path (write it down now, execute it in a later phase)
-----------------------------------------------------------------
1. NOW (this phase): both surfaces live. `/api/*` is canonical for every shipped
   client; `/api/v1/*` is an alias with identical behaviour.
2. NEXT: point `frontend/src/lib/api.ts` at a single `API_BASE = "/api/v1"`, and
   the WebSocket URLs at `/api/v1/ws`. One constant, one commit, revertible.
3. THEN: `deploy.sh` and any uptime monitor move to `/api/v1/health` — but
   `/api/health` must be kept exempt from auth and alive regardless, because a
   probe URL is the last thing that should churn.
4. LATER: mark the unprefixed routes `deprecated=True` (OpenAPI only, no
   behaviour change) and add a `Deprecation` response header, so a forgotten
   caller shows up in the access log before anything breaks.
5. ONLY THEN: stop mounting the unprefixed surface. Not before a full release
   where the access log shows zero unprefixed traffic.
   `/api/v2` is introduced by mounting the same routers a third time with a
   different transform — the transform, not the source, is where a version lives.

What is NOT versioned: the SPA fallback and `/assets` (not API), and — for now —
nothing else. WebSockets ARE mirrored (`/ws` → `/api/v1/ws`) so a client that
adopts v1 does not have to keep one foot in the unversioned world.
"""
from __future__ import annotations

import inspect

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute

# The single place the current version is spelled. Everything else derives.
CURRENT_VERSION = "v1"
API_ROOT = "/api"
VERSION_PREFIX = f"{API_ROOT}/{CURRENT_VERSION}"

# Every version this process serves, newest first. Used by tests and by anything
# that needs to reason about "is this a versioned path" without string surgery.
SERVED_VERSIONS = (CURRENT_VERSION,)


def versioned_path(path: str) -> str | None:
    """`/api/status` → `/api/v1/status`. Returns None for paths that must not be
    mirrored, so the caller can skip rather than guess.

    Already-versioned paths return None: mounting is idempotent, which matters
    because `mount_versioned` is called from module scope in `main.py` and a
    reimport (uvicorn --reload, a test importing app twice) must not stack
    `/api/v1/v1/...` onto the app.
    """
    if path.startswith(f"{VERSION_PREFIX}/") or path == VERSION_PREFIX:
        return None
    if path == API_ROOT or path.startswith(f"{API_ROOT}/"):
        return f"{VERSION_PREFIX}{path[len(API_ROOT):]}"
    if path == "/ws" or path.startswith("/ws/"):
        return f"{VERSION_PREFIX}{path}"
    return None


def unversioned_path(path: str) -> str:
    """`/api/v1/health` → `/api/health`; anything else unchanged.

    The inverse of `versioned_path`, and the reason it exists: middleware that
    matches on paths (the auth gate's exemption set, the access-log filter) must
    make the SAME decision for both surfaces. Without this, adding a version
    prefix would have silently un-exempted `/api/health` from auth and taken the
    deploy probe down with a 401.
    """
    for v in SERVED_VERSIONS:
        prefix = f"{API_ROOT}/{v}"
        if path == prefix:
            return API_ROOT
        if path.startswith(f"{prefix}/"):
            rest = path[len(prefix):]
            # `/api/v1/ws` was mirrored from `/ws`, not from `/api/ws`.
            return rest if rest.startswith("/ws") else f"{API_ROOT}{rest}"
    return path


# Attributes copied verbatim from the source route onto the mirror. Filtered
# against the installed FastAPI's signature below, so a version bump that adds
# or drops a keyword degrades to "not copied" instead of TypeError at import —
# and import failure here is a dead process, not a failed request.
_ROUTE_ATTRS = (
    "response_model", "status_code", "tags", "dependencies", "summary",
    "description", "response_description", "responses", "deprecated",
    "response_model_include", "response_model_exclude", "response_model_by_alias",
    "response_model_exclude_unset", "response_model_exclude_defaults",
    "response_model_exclude_none", "include_in_schema", "response_class",
    "callbacks", "openapi_extra", "generate_unique_id_function",
    "strict_content_type",
)

_ACCEPTED = set(inspect.signature(APIRouter.add_api_route).parameters)


def _mirror_api_route(dest: APIRouter, route: APIRoute, path: str) -> None:
    kwargs = {
        name: getattr(route, name)
        for name in _ROUTE_ATTRS
        if name in _ACCEPTED and hasattr(route, name)
    }
    # `route.dependencies` already contains the SOURCE ROUTER's router-level
    # dependencies (FastAPI folds them in at decoration time) — portfolio_routes
    # gates every route behind `_research_gate` that way. Copying them here and
    # NOT re-declaring them on the mirror router is what keeps the gate on the
    # v1 surface exactly once.
    dest.add_api_route(
        path,
        route.endpoint,
        methods=sorted(route.methods or {"GET"}),
        # Route names and operation ids must stay unique or the OpenAPI schema
        # collides and `url_for` becomes ambiguous.
        name=f"{CURRENT_VERSION}_{route.name}",
        operation_id=(f"{CURRENT_VERSION}_{route.operation_id}"
                      if route.operation_id else None),
        **kwargs,
    )


def _mirror_ws_route(dest: APIRouter, route: APIWebSocketRoute, path: str) -> None:
    dest.add_api_websocket_route(
        path, route.endpoint, name=f"{CURRENT_VERSION}_{route.name}",
        dependencies=list(route.dependencies or []),
    )


def build_versioned_router(*routers: APIRouter) -> APIRouter:
    """A router carrying `/api/v1/...` mirrors of every route in `routers`.

    Pure — takes routers, returns a router — so a test can assert the full mirror
    map without constructing an app or starting the engine lanes.
    """
    mirror = APIRouter()
    for router in routers:
        for route in router.routes:
            path = versioned_path(getattr(route, "path", ""))
            if path is None:
                continue
            if isinstance(route, APIRoute):
                _mirror_api_route(mirror, route, path)
            elif isinstance(route, APIWebSocketRoute):
                _mirror_ws_route(mirror, route, path)
            # Anything else (Mount, static) is deliberately not mirrored.
    return mirror


def mount_versioned(app: FastAPI, *routers: APIRouter) -> APIRouter:
    """Mount the `/api/v1` mirror onto `app`. Additive: call AFTER the routers
    have been included unprefixed, and before the SPA catch-all is registered
    (`/{full_path:path}` would otherwise swallow `/api/v1/...` — it 404s anything
    starting with `api/`, so a mis-ordered mount is a hard 404, not a subtle bug).
    """
    mirror = build_versioned_router(*routers)
    app.include_router(mirror)
    return mirror
