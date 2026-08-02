"""H3 — /api/v1 exists, and the unprefixed surface is untouched.

The second half of that sentence is the one that can cost real money: the shipped
SPA and `scripts/deploy.sh` hit unprefixed paths, and deploy.sh's post-deploy
check is a curl of `/api/health` plus `GET /`. So these tests assert the mirror
AND assert that every original path survived the mirroring, byte-identically
where the payload is deterministic.

Test hazard (see CLAUDE.md): `with TestClient(app)` runs the real lifespan and
starts the engine lanes. Everything here needs only the HTTP handler, so every
client below is a BARE `TestClient(app)`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import backtest_routes, portfolio_routes, routes
from app.api.dto import DeploymentSummary, HealthResponse
from app.api.versioning import (
    VERSION_PREFIX,
    build_versioned_router,
    unversioned_path,
    versioned_path,
)
from app.core.config import get_settings
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.ledger import routes as ledger_routes
from app.main import app

_SOURCE_ROUTERS = (routes.router, backtest_routes.router,
                   portfolio_routes.router, ledger_routes.router)


def _client() -> TestClient:
    init_db(reset=True)
    app.state.runner = EngineRunner()
    return TestClient(app)


def _app_paths() -> set[str]:
    """Every path the app can actually serve. FastAPI resolves included routers
    lazily, so `app.routes` alone does not list them — the test client's router
    resolution does, which is also the only listing that proves servability."""
    seen: set[str] = set()

    def walk(routes_):
        for r in routes_:
            inner = getattr(r, "original_router", None)
            if inner is not None:
                walk(inner.routes)
            elif hasattr(r, "path"):
                seen.add(r.path)
    walk(app.router.routes)
    return seen


# ── the path transform ─────────────────────────────────────────────────────

@pytest.mark.parametrize("original,expected", [
    ("/api/status", "/api/v1/status"),
    ("/api/positions/{key}/close", "/api/v1/positions/{key}/close"),
    ("/api/backtest/result/{key}/{interval}", "/api/v1/backtest/result/{key}/{interval}"),
    ("/api/ledger/snapshot", "/api/v1/ledger/snapshot"),
    ("/ws", "/api/v1/ws"),
    ("/ws/instrument/{key}", "/api/v1/ws/instrument/{key}"),
])
def test_versioned_path_transform(original, expected):
    assert versioned_path(original) == expected


def test_versioned_path_is_idempotent():
    """`mount_versioned` runs at module scope in main.py; a reimport (uvicorn
    --reload, a second test importing the app) must not stack /api/v1/v1/..."""
    assert versioned_path("/api/v1/status") is None
    assert versioned_path("/api/v1") is None


def test_non_api_paths_are_not_mirrored():
    """The SPA catch-all and static assets are not API and must stay out."""
    assert versioned_path("/") is None
    assert versioned_path("/assets/app.js") is None
    assert versioned_path("/{full_path:path}") is None


@pytest.mark.parametrize("path", [
    "/api/status", "/api/health", "/api/ledger/snapshot", "/ws",
    "/ws/instrument/{key}", "/", "/assets/x.js",
])
def test_unversioned_path_round_trips(path):
    """The inverse must be exact: the auth gate matches its exemption set on the
    unversioned form, so a lossy inverse would 401 the deploy probe on v1."""
    v = versioned_path(path)
    if v is not None:
        assert unversioned_path(v) == path
    assert unversioned_path(path) == path


# ── the mirror is complete ─────────────────────────────────────────────────

def test_every_source_route_has_a_v1_twin():
    mirror_paths = {r.path for r in build_versioned_router(*_SOURCE_ROUTERS).routes}
    missing = []
    for router in _SOURCE_ROUTERS:
        for route in router.routes:
            want = versioned_path(route.path)
            assert want is not None, f"{route.path} was skipped by the transform"
            if want not in mirror_paths:
                missing.append(route.path)
    assert not missing, f"routes with no /api/v1 twin: {missing}"


def test_mirror_preserves_http_methods():
    """A GET mirrored as a POST is a silently broken alias — the client gets 405
    from a route that exists."""
    def sig(route, path):
        # (path, methods) pairs, not a path→methods map: /api/settings and
        # /api/ledger/snapshot each carry two verbs on one path.
        return (path, frozenset(getattr(route, "methods", None) or ()))

    want = {sig(r, versioned_path(r.path))
            for router in _SOURCE_ROUTERS for r in router.routes}
    got = {sig(r, r.path) for r in build_versioned_router(*_SOURCE_ROUTERS).routes}
    assert got == want


def test_every_original_path_is_still_mounted():
    """The regression that would break production: mirroring must be ADDITIVE."""
    served = _app_paths()
    for router in _SOURCE_ROUTERS:
        for route in router.routes:
            assert route.path in served, f"{route.path} disappeared from the app"
    assert "/api/health" in served


def test_v1_paths_are_mounted_on_the_app():
    served = _app_paths()
    assert f"{VERSION_PREFIX}/status" in served
    assert f"{VERSION_PREFIX}/health" in served
    assert f"{VERSION_PREFIX}/ws" in served


# ── identical behaviour over HTTP ──────────────────────────────────────────

@pytest.mark.parametrize("path", ["/api/strategies", "/api/backtest/status",
                                  "/api/execution/state", "/api/provider-health"])
def test_v1_response_is_byte_identical(path):
    c = _client()
    old = c.get(path)
    new = c.get(versioned_path(path))
    assert old.status_code == new.status_code
    assert old.content == new.content


def test_v1_health_answers_the_same_verdict_as_the_legacy_probe():
    c = _client()
    old, new = c.get("/api/health"), c.get(f"{VERSION_PREFIX}/health")
    assert old.status_code == new.status_code
    assert old.json()["build"] == new.json()["build"]


def test_v1_websocket_serves_the_same_handler():
    c = _client()
    with c.websocket_connect(f"{VERSION_PREFIX}/ws") as ws:
        assert ws.receive_json()["type"] == "state"


def test_router_level_dependencies_survive_the_mirror(monkeypatch):
    """portfolio_routes gates its whole router behind the research freeze flag.
    A mirror that dropped router-level dependencies would open a frozen subsystem
    on the v1 surface — the exact class of bug this mount-time copy could cause."""
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    c = _client()
    assert c.get("/api/portfolio/watchlists").status_code == 403
    assert c.get(f"{VERSION_PREFIX}/portfolio/watchlists").status_code == 403


def test_v1_health_is_auth_exempt_like_the_legacy_probe(monkeypatch):
    """Exemptions are matched on the unversioned path. If that broke, deploy.sh
    would 401 the day it moves to v1 — and it would look like an outage."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c = _client()
    assert c.get(f"{VERSION_PREFIX}/health").status_code != 401


def test_v1_routes_are_behind_the_same_token_gate(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c = _client()
    assert c.get(f"{VERSION_PREFIX}/status").status_code == 401
    ok = c.get(f"{VERSION_PREFIX}/status",
               headers={"Authorization": "Bearer secret-token"})
    assert ok.status_code == 200


# ── the DTOs describe what is actually served ──────────────────────────────

def test_health_payload_validates_against_the_dto():
    """The DTO's only defence against becoming decorative: it is checked against
    the real payload, not against itself."""
    c = _client()
    body = c.get("/api/health").json()
    parsed = HealthResponse.model_validate(body)
    assert parsed.build is not None and parsed.build.commit
    assert parsed.status in ("ok", "starting", "degraded", "unready")
    assert parsed.ok is parsed.ready


@pytest.mark.parametrize("payload,expect_dry", [
    ({"dry_run": True, "watchlist": "w1", "strategy_key": "s1",
      "accepted": ["A"], "rejected": []}, True),
    ({"dry_run": False, "watchlist_id": 7, "assigned": ["A"], "rejected": [],
      "note": "staged — effective on next engine restart, then ARM"}, False),
])
def test_deployment_summary_adapts_both_legacy_shapes(payload, expect_dry):
    """One endpoint, two payload shapes (preview vs commit) — the reason this DTO
    exists. Both must land in one shape without the caller branching."""
    d = DeploymentSummary.from_legacy_payload(payload)
    assert d.dry_run is expect_dry
    assert d.accepted == ["A"]
    assert d.staged is True
