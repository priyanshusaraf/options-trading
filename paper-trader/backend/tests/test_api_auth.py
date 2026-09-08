"""SEC-1: token auth on the API surface.

The engine is single-user/localhost today but exposed to the LAN/tailnet; any
REST or WS call currently executes unauthenticated (including manual-open,
kill, arm). When PT_API_TOKEN is set, every /api route except the OAuth
redirect endpoints and /api/health must require a matching bearer token.
Empty token (the default) keeps auth OFF for local dev/tests."""
from fastapi.testclient import TestClient
import logging
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.execution.leases import LeaseRepository
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    leases = LeaseRepository(SessionLocal)
    token = leases.claim(owner_id=r.owner_id, broker_account_id=r.broker_account_id,
                         cell_id="auth-test", worker_id="auth-test-worker")
    leases.activate(token, reconciliation_evidence="auth fixture")
    r.broker.execution_lease_token = token
    app.state.runner = r
    return TestClient(app), r


def test_protected_route_without_token_is_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    res = c.post("/api/execution/arm", json={"armed": True})
    assert res.status_code == 401


def test_protected_route_with_correct_bearer_token_is_allowed(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    res = c.post(
        "/api/execution/arm",
        json={"armed": True},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert res.status_code != 401
    assert res.status_code == 202
    assert res.json().get("armed") is False
    assert res.json().get("desired_state") == "armed"


def test_protected_route_with_wrong_token_is_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    res = c.post(
        "/api/execution/arm",
        json={"armed": True},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert res.status_code == 401


def test_x_pt_token_header_is_also_accepted(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    res = c.post(
        "/api/execution/arm",
        json={"armed": True},
        headers={"X-PT-Token": "secret-token"},
    )
    assert res.status_code != 401


def test_auth_disabled_when_token_empty(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "")
    c, _ = _client()
    res = c.post("/api/execution/arm", json={"armed": True})
    assert res.status_code != 401


def test_health_route_exempt_even_with_token(monkeypatch):
    """The claim here is EXEMPTION, not health: /api/health must never answer 401.

    It is a readiness probe now (app/engine/readiness.py) and answers 503 unless
    the engine loops are actually running — this harness constructs a runner but
    never starts them, so 200 is not the right assertion. Asserting `!= 401` says
    exactly what this test is for and stays true regardless of the verdict."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    res = c.get("/api/health")
    assert res.status_code != 401
    assert res.json()["build"], "the probe answers with a body, not an auth challenge"


def test_browser_websocket_auth_quarantines_before_any_private_payload(monkeypatch, caplog):
    """The bearer is never part of a logged handshake or pre-auth response."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    with caplog.at_level(logging.DEBUG):
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "authenticate", "bearer": "secret-token"})
            assert ws.receive_json()["type"] == "state"
    assert "secret-token" not in caplog.text


@pytest.mark.parametrize("payload", (
    {"bearer": "secret-token"},
    {"type": "authenticate", "bearer": "wrong-token"},
))
def test_websocket_bad_first_auth_frame_closes_once_without_private_payload(monkeypatch, payload):
    """The quarantine helper owns rejection, so routes never send a second close."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    with c.websocket_connect("/ws") as ws:
        ws.send_json(payload)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 1008


# Raw URLs deliberately include values that HTTPX normalizes and ASGI decodes.
# Keep this independent of ignored evidence files and of the classifier's regex.
_STATIC_PATH_VALUES = {
    "project_id": (
        "review%3Ftail", "graphs%23tail", "review%23tail",
        "project.normal", "legacy-project", "review", "reviewer", "graphs",
        "experiments", "layouts", "findings", "version-comparisons", "status",
        "%72eview", "project%2Freview", "project%252Freview", "project%5Creview",
        "project%3Freview", "project%23review", ".", "..", "%2E%2E",
    ),
    "scope_id": (
        "scope.normal", "scope.review", "scope.graphs", "scope.status", "review",
        "graphs", "status", "scope.%72eview", "scope.%2Freview",
        "scope.%252Freview", "scope.%5Creview", ".", "..", "%2E%2E",
    ),
    "revision": ("1", "%31", "0", "-1", "review", "%2Freview", "%252Freview", ".", ".."),
}


def _static_action_probe():
    """Use registered route matchers, without running handlers or dependencies."""
    from starlette.routing import get_route_path
    from starlette.responses import JSONResponse
    from starlette.routing import Match
    from app.api.principal import action_for_request
    from app.api.product_object_routes import router
    from app.api.versioning import build_versioned_router, unversioned_path

    routes = [route for source in (router, build_versioned_router(router))
              for route in source.routes if "/static-scopes" in getattr(route, "path", "")]

    async def probe(scope, receive, send):
        matches = [route.path for route in routes if route.matches(scope)[0] is Match.FULL]
        response = JSONResponse({
            "path": scope["path"], "matches": matches,
            "action": action_for_request(scope["method"], unversioned_path(get_route_path(scope))),
        })
        await response(scope, receive, send)

    return routes, TestClient(probe)


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_static_scope_action_matches_registered_routes_after_asgi_decoding(prefix):
    """Every matched static endpoint gets project policy, even for invalid IDs."""
    routes, client = _static_action_probe()
    routes = [r for r in routes if r.path.startswith(prefix + "/ir/")]
    assert len(routes) == 8
    mismatches = []
    count = 0
    for route in routes:
        for method in route.methods:
            for variable, values in _STATIC_PATH_VALUES.items():
                if "{" + variable + "}" not in route.path:
                    continue
                for value in values:
                    path = route.path
                    for key, default in (("project_id", "project.normal"),
                                         ("scope_id", "scope.normal"), ("revision", "1")):
                        path = path.replace("{" + key + "}", value if key == variable else default)
                    result = client.request(method, path).json()
                    count += 1
                    if result["matches"]:
                        expected = "read:project" if method == "GET" else "write:project"
                        if result["action"] != expected:
                            mismatches.append((method, path, result))
    assert count == 269
    assert not mismatches, mismatches


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_static_scope_action_matches_router_end_anchor(static_authorization_http, monkeypatch, prefix):
    """Starlette's end anchor can match before a terminal encoded newline."""
    from tests.test_cross_tenant_idor import _headers
    import app.main as main

    auth_client, issued, _ = static_authorization_http
    observed = []
    original = main.action_for_request

    def observed_action(method, path):
        result = original(method, path)
        observed.append(result)
        return result

    monkeypatch.setattr(main, "action_for_request", observed_action)
    routes, client = _static_action_probe()
    mismatches = []
    count = 0
    for route in routes:
        if not route.path.startswith(prefix + "/ir/"):
            continue
        path = route.path.replace("{project_id}", "review").replace(
            "{scope_id}", "scope.main").replace("{revision}", "1") + "%0A"
        for method in route.methods:
            count += 1
            result = client.request(method, path).json()
            assert result["matches"] == [route.path]
            expected = "read:project" if method == "GET" else "write:project"
            if result["action"] != expected:
                mismatches.append((method, path, result))
            response = auth_client.request(method, path, headers=_headers(issued, "user.a"))
            assert response.status_code == 403
            assert response.json().get("detail", {}).get("capability") == "static_watchlists"
            assert observed[-1] == expected
    assert count == 8
    assert not mismatches, mismatches


@pytest.mark.parametrize("method,path,expected", (
    ("DELETE", "/api/ir/projects/review/static-scopes", "write:review"),
    ("PATCH", "/api/ir/projects/graphs/static-scopes/scope.a", "write:graph"),
    ("HEAD", "/api/ir/projects/experiments/static-scopes", "start:research"),
    ("OPTIONS", "/api/ir/projects/layouts/static-scopes", "write:layout"),
    ("BREW", "/api/ir/projects/review/static-scopes", "write:review"),
    ("GET", "/api/ir/projects/review/static-scopes/", "read:review"),
    ("GET", "/api/ir/projects/review/static-scopes//revisions/1", "read:review"),
    ("POST", "/api/ir/projects/review/static-scopes/scope.a", "write:review"),
    ("GET", "/api/ir/projects/review/static-scopes/scope.a/archive", "read:review"),
    ("GET", "/api/ir/projects/review/static-scopes/scope.a/revisions/1/extra", "read:review"),
    ("GET", "/api/ir/projects/review/static-scopes-extra", "read:review"),
    ("GET", "/api/ir/projects//static-scopes", "read:project"),
    ("GET", "/api/ir/projects/review/graphs/g/static-scopes", "read:review"),
    ("GET", "/other/ir/projects/review/static-scopes", None),
))
def test_static_scope_guard_does_not_reclassify_unmatched_paths_or_methods(method, path, expected):
    """Unsupported shapes retain legacy classification; they gain no static route."""
    _, client = _static_action_probe()
    for prefix in ("/api", "/api/v1"):
        result = client.request(method, path.replace("/api/", prefix + "/", 1))
        # HTTPX suppresses HEAD bodies, so its action is checked directly below.
        if method != "HEAD":
            assert result.json()["matches"] == []
            assert result.json()["action"] == expected
    from app.api.principal import action_for_request
    assert action_for_request(method, path) == expected


@pytest.mark.parametrize("method,path,expected", (
    ("GET", "/api/brokers", "read:brokers"),
    ("POST", "/api/connections", "create:connection"),
    ("POST", "/api/connections/c/credential", "write:credential"),
    ("DELETE", "/api/connections/c", "revoke:connection"),
    ("GET", "/api/execution/state", "read:execution"),
    ("POST", "/api/execution/arm", "authoritative:execution"),
    ("POST", "/api/positions/p/close", "authoritative:execution"),
    ("GET", "/api/backtest/status", "read:backtest"),
    ("POST", "/api/backtest/run", "write:backtest"),
    ("GET", "/api/settings", "read:runtime-config"),
    ("POST", "/api/settings/reset", "write:runtime-config"),
    ("GET", "/api/research/operations/o", "read:research"),
    ("POST", "/api/ir/graphs/g/layout", "write:layout"),
    ("GET", "/api/portfolio/unconverted", None),
    ("POST", "/api/portfolio/watchlists/w", "write:watchlist"),
    ("POST", "/api/ir/projects/p/review", "write:review"),
    ("POST", "/api/ir/projects/p/candidates/c/decisions", "decision:research"),
    ("GET", "/api/ir/projects/p/findings", "read:research"),
    ("POST", "/api/ir/projects/p/experiments", "start:research"),
    ("POST", "/api/ir/projects/p/version-comparisons", "compare:research"),
    ("POST", "/api/ir/projects/p/presentation-edits", "write:layout"),
    ("GET", "/api/ir/projects/p/graphs/g", "read:graph"),
    ("POST", "/api/ir/projects/p/graphs/g/versions", "publish:graph"),
    ("POST", "/api/ir/projects/p/status", "archive:project"),
    ("GET", "/api/ir/projects", "read:project"),
    ("POST", "/api/ir/projects", "write:project"),
    ("GET", "/unclassified", None),
))
def test_non_static_action_families_and_method_normalization_remain_unchanged(method, path, expected):
    from app.api.principal import action_for_request
    from app.api.versioning import unversioned_path
    for prefix in ("/api", "/api/v1"):
        assert action_for_request(method.lower(), unversioned_path(
            path.replace("/api/", prefix + "/", 1))) == expected


@pytest.fixture
def static_authorization_http(monkeypatch):
    """Durable sessions with an explicitly blocked test capability."""
    import datetime as dt
    from sqlalchemy import select
    from app.api.principal import issue_user_session
    from app.core import release_profile
    from app.db.models import Membership, User
    from app.market_truth.identity import CanonicalPhysicalInstrument, persist_canonical_instrument
    from tests.test_cross_tenant_idor import _seed_http_principals

    issued = _seed_http_principals(monkeypatch)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    original_manifest = release_profile.manifest
    assert original_manifest("v0_research_signal", research_enabled=True)["capabilities"]["static_watchlists"]["state"] == (
        release_profile.CapabilityState.ENABLED_WITH_LIMIT.value
    )

    def blocked_static_capability(*args, **kwargs):
        manifest = dict(original_manifest(*args, **kwargs))
        manifest["capabilities"] = dict(manifest["capabilities"])
        manifest["capabilities"]["static_watchlists"] = {
            "state": release_profile.CapabilityState.BLOCKED.value,
        }
        return manifest

    monkeypatch.setattr(release_profile, "manifest", blocked_static_capability)
    instrument = CanonicalPhysicalInstrument("test", "authorization", "NSE", "EQUITY", "SPOT", "INR", None)
    with SessionLocal.begin() as session:
        session.scalar(select(Membership).where(Membership.user_id == "user.a")).role = "owner"
        session.add(User(user_id="member.a", email_normalized="member-a@test", display_name="same"))
        session.flush()
        session.add(Membership(organization_id="org.a", user_id="member.a", role="member"))
        session.flush()
        issued["member.a"] = issue_user_session(session, user_id="member.a", organization_id="org.a",
            expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1))
        persist_canonical_instrument(session, instrument)
    return TestClient(app), issued, instrument.address


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
@pytest.mark.parametrize("project_url", (
    "review", "reviewer", "graphs", "experiments", "layouts", "findings",
    "version-comparisons", "status", "%72eview", "legacy-project",
    "review%3Ftail", "graphs%23tail", "review%23tail", "status%3Ftail",
    "project%5Creview", "project%3Freview", "project%23review",
    "%2E%2E", "p" * 64,
))
def test_static_scope_http_authorization_uses_project_policy(
        static_authorization_http, monkeypatch, prefix, project_url):
    """Test-only capability opening exposes real handlers, policy and owner SQL."""
    from urllib.parse import unquote
    from app.core import release_profile
    from app.db.models import Project
    from tests.test_cross_tenant_idor import _headers
    import app.main as main

    client, issued, instrument = static_authorization_http
    with SessionLocal.begin() as session:
        session.add(Project(project_id=unquote(project_url), owner_id="org.a", name="Project"))
    base = f"{prefix}/ir/projects/{project_url}/static-scopes"
    original_action = main.action_for_request
    actions = []

    def observed_action(method, path):
        action = original_action(method, path)
        actions.append(action)
        return action

    monkeypatch.setattr(main, "action_for_request", observed_action)

    def request(method, suffix="", user="user.a", body=None, status=200):
        response = client.request(method, base + suffix, headers=_headers(issued, user), json=body)
        assert response.status_code == status, response.text
        assert actions[-1] == ("read:project" if method == "GET" else "write:project")
        return response

    # Prove capability refusal before enabling it for the authorization checks.
    refused = request("GET", status=403)
    assert refused.json()["detail"]["capability"] == "static_watchlists"
    original_manifest = release_profile.manifest

    def test_only_enabled(*args, **kwargs):
        manifest = dict(original_manifest(*args, **kwargs))
        manifest["capabilities"] = dict(manifest["capabilities"])
        manifest["capabilities"]["static_watchlists"] = {
            "state": release_profile.CapabilityState.ENABLED.value,
        }
        return manifest

    monkeypatch.setattr(release_profile, "manifest", test_only_enabled)
    body = {"scope_id": "scope.main", "name": "Research", "members": [instrument]}
    assert client.get(base).status_code == 401
    request("POST", user="viewer.a", body=body, status=403)
    request("POST", user="user.b", body=body, status=404)
    first = request("POST", user="member.a", body=body, status=201).json()
    request("GET", user="viewer.a")
    request("GET", "/scope.main", user="viewer.a")
    request("GET", "/scope.main/revisions/%31", user="viewer.a")
    request("GET", "/scope.main", user="user.b", status=404)
    request("GET", "/scope.missing", status=404)
    for suffix in ("/review", "/graphs", "/status", "/scope.main/revisions/review", "/scope.main/revisions/0"):
        request("GET", suffix, user="viewer.a", status=422)
    revision = {"name": "Updated", "members": [instrument], "expected_revision": 1}
    request("POST", "/scope.main/revisions", user="viewer.a", body=revision, status=403)
    request("POST", "/scope.main/revisions", user="user.b", body=revision, status=404)
    second = request("POST", "/scope.main/revisions", user="member.a", body=revision, status=201).json()
    assert second["address"] != first["address"]
    request("POST", "/scope.main/archive", user="viewer.a", body={"expected_revision": 2}, status=403)
    request("POST", "/scope.main/archive", user="user.b", body={"expected_revision": 2}, status=404)
    request("POST", "/scope.main/archive", user="member.a", body={"expected_revision": 2})
    assert request("GET").json()["items"] == []
    for method, suffix, status in (("DELETE", "", 405), ("HEAD", "", 405),
                                   ("BREW", "", 405), ("GET", "/scope.main/archive", 405),
                                   ("GET", "/scope.main/revisions/1/extra", 404)):
        response = client.request(method, base + suffix, headers=_headers(issued, "member.a"))
        assert response.status_code == status
    # These encoded slashes are unmatched after this HTTPX/ASGI transport's decoding.
    for project in ("project%2Freview", "project%252Freview"):
        response = client.get(f"{prefix}/ir/projects/{project}/static-scopes",
                              headers=_headers(issued, "viewer.a"))
        assert response.status_code == 404


def test_auth_transport_uses_the_exact_router_path_callable():
    """Framework upgrades must keep middleware coupled to actual route matching."""
    from starlette.routing import Route
    import app.main as main
    assert getattr(main, "get_route_path", None) is Route.matches.__globals__["get_route_path"]


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
@pytest.mark.parametrize("root_path,mount_prefix", (
    ("", ""), ("/mounted", "/mounted"), ("/nested/prefix", "/nested/prefix"),
    ("/mounted", ""),  # A proxy already stripped the mount from scope.path.
    ("/api", "/api"),  # Strip exactly one mount before version normalization.
))
def test_auth_transport_preserves_encoded_paths_queries_and_mounts(
        static_authorization_http, monkeypatch, prefix, root_path, mount_prefix):
    """Actual middleware, static handlers and owner SQL must see one route path."""
    from app.core import release_profile
    from app.db.models import Project
    from tests.test_cross_tenant_idor import _headers
    import app.main as main

    _, issued, instrument = static_authorization_http
    client = TestClient(app, root_path=root_path)
    with SessionLocal.begin() as session:
        session.add(Project(project_id="status?tail", owner_id="org.a", name="Encoded Project"))
    base = f"{mount_prefix}{prefix}/ir/projects/status%3Ftail/static-scopes"
    classified = []
    original_action = main.action_for_request

    def observed_action(method, path):
        action = original_action(method, path)
        classified.append((path, action))
        return action

    monkeypatch.setattr(main, "action_for_request", observed_action)
    unauthorized = client.get(base)
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"error": "unauthorized"}  # middleware, not a handler fallback
    blocked = client.get(base, headers=_headers(issued, "user.a"))
    assert blocked.status_code == 403
    assert blocked.json().get("detail", {}).get("capability") == "static_watchlists"
    assert classified[-1] == ("/api/ir/projects/status?tail/static-scopes", "read:project")

    # Enable the test capability after proving its blocked state is enforced.
    original_manifest = release_profile.manifest

    def test_only_enabled(*args, **kwargs):
        manifest = dict(original_manifest(*args, **kwargs))
        manifest["capabilities"] = dict(manifest["capabilities"])
        manifest["capabilities"]["static_watchlists"] = {
            "state": release_profile.CapabilityState.ENABLED.value,
        }
        return manifest

    monkeypatch.setattr(release_profile, "manifest", test_only_enabled)
    body = {"scope_id": "scope.main", "name": "Scope", "members": [instrument]}
    assert client.post(base, headers=_headers(issued, "user.a"), json=body).status_code == 201
    assert classified[-1][1] == "write:project"
    for query in ("", "?probe=/graphs&question=%3F&fragment=%23&next=/api/connections/x/credential"):
        response = client.get(base + query, headers=_headers(issued, "viewer.a"))
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert classified[-1] == ("/api/ir/projects/status?tail/static-scopes", "read:project")
    assert client.post(base, headers=_headers(issued, "viewer.a"), json=body).status_code == 403
    assert client.get(base, headers=_headers(issued, "user.b")).status_code == 404
    assert client.delete(base, headers=_headers(issued, "member.a")).status_code == 405
    unmatched = base + "/scope.main/revisions/1/extra"
    assert client.get(unmatched, headers=_headers(issued, "member.a")).status_code == 404
    assert client.get(unmatched).json() == {"error": "unauthorized"}
    # Public health remains exempt at the same mount; ordinary query data does not alter policy.
    health = client.get(f"{mount_prefix}{prefix}/health?probe=private-diagnostics")
    assert health.status_code in (200, 503)


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
@pytest.mark.parametrize("root_path,lookalike", (
    ("/mount", "/mountain"), ("/nested/root", "/nested/rootish"),
))
def test_auth_transport_does_not_strip_prefix_lookalikes(
        static_authorization_http, prefix, root_path, lookalike):
    from tests.test_cross_tenant_idor import _headers
    from starlette.routing import get_route_path

    _, issued, _ = static_authorization_http
    client = TestClient(app, root_path=root_path)
    path = f"{lookalike}{prefix}/ir/projects/status%3Ftail/static-scopes"
    assert get_route_path({"path": path, "root_path": root_path}) == path
    for headers in ({}, _headers(issued, "user.a"), _headers(issued, "viewer.a")):
        response = client.get(path, headers=headers)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("method,path,expected", (
    ("GET", "/api/ir/presets", "read:project"),
    ("POST", "/api/ir/presets", None),
    ("HEAD", "/api/ir/presets", None),
    ("PATCH", "/api/ir/presets", None),
    ("GET", "/api/research/operations/owned", "read:research"),
    ("POST", "/api/research/operations/owned/cancel", "start:research"),
    ("DELETE", "/api/research/operations/owned", "start:research"),
    ("HEAD", "/api/research/operations/owned", "start:research"),
    ("POST", "/api/ir/projects/review/graphs/layouts/versions/1/research-preparations", "start:research"),
    ("POST", "/api/ir/projects/graphs/graphs/review/versions/1/research-operations", "start:research"),
    ("POST", "/api/ir/projects/review/graphs/g/versions/1/research-operations\n", "start:research"),
    ("POST", "/api/ir/projects/review/graphs/g/versions/1/research-operations/", "write:review"),
    ("GET", "/api/ir/projects/review/graphs/g/versions/1/research-preparations", "read:review"),
    ("PATCH", "/api/ir/projects/p/graphs/g/versions/1/research-preparations", "write:graph"),
))
def test_research_actions_use_the_existing_closed_capabilities(method, path, expected):
    from app.api.principal import ACTION_VOCABULARY, action_for_request

    assert action_for_request(method, path) == expected
    assert expected is None or expected in ACTION_VOCABULARY


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_durable_viewer_can_read_global_presets(static_authorization_http, prefix):
    from tests.test_cross_tenant_idor import _headers

    client, issued, _ = static_authorization_http
    path = prefix + "/ir/presets"
    assert client.get(path).status_code == 401
    response = client.get(path, headers=_headers(issued, "viewer.a"))
    assert response.status_code == 200, response.text
    assert isinstance(response.json()["presets"], list)
    assert response.json()["presets"]
    assert client.post(path, headers=_headers(issued, "viewer.a")).status_code == 403


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_durable_viewer_can_read_but_cannot_cancel_research(
        static_authorization_http, monkeypatch, tmp_path, prefix):
    from app.api import research_operation_routes
    from research.config import research_database_url
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.domain.operations import ResearchOperationRepository
    from tests.test_cross_tenant_idor import _headers

    client, issued, _ = static_authorization_http
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setenv("PT_RESEARCH_DATABASE_URL", "")
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", str(tmp_path / "authorization-research.db"))
    engine = make_engine(research_database_url())
    init_research_db(engine)
    ResearchSession = make_sessionmaker(engine)
    try:
        with ResearchSession() as session:
            ResearchOperationRepository(session).enqueue(
                owner_id="org.a", trigger="manual", plan={}, build="synthetic-auth-test",
                provider_mode="mock", operation_id="protected-operation")
        path = prefix + "/research/operations/protected-operation"
        response = client.get(path, headers=_headers(issued, "viewer.a"))
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        with monkeypatch.context() as denied:
            denied.setattr(research_operation_routes, "make_engine",
                           lambda *_args: pytest.fail("viewer cancellation reached research storage"))
            response = client.post(path + "/cancel", headers=_headers(issued, "viewer.a"))
            assert response.status_code == 403
        with ResearchSession() as session:
            repository = ResearchOperationRepository(session)
            operation = repository.get("protected-operation", owner_id="org.a")
            assert operation.status == "pending"
            assert operation.cancel_requested_at is None
            assert repository.events("protected-operation", owner_id="org.a") == []
        assert client.post(path + "/cancel", headers=_headers(issued, "user.b")).status_code == 404
        allowed = client.post(path + "/cancel", headers=_headers(issued, "member.a"))
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "cancelled"
        with ResearchSession() as session:
            assert ResearchOperationRepository(session).get(
                "protected-operation", owner_id="org.a").status == "cancelled"
    finally:
        engine.dispose()


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_research_settings_durable_owner_viewer_and_revocation(static_authorization_http, prefix):
    import uuid
    from sqlalchemy import select
    from app.db.models import Membership
    from research.domain.settings import PLATFORM_DEFAULTS
    from tests.test_cross_tenant_idor import _headers

    client, issued, _ = static_authorization_http
    path = prefix + "/research-settings"
    assert client.get(path).status_code == 401
    first = client.get(path, headers=_headers(issued, "viewer.a"))
    assert first.status_code == 200, first.text
    assert first.json()["workspace"]["revision"] == 0
    assert first.json()["fixed_assumptions"]["fill"] == "existing-next-bar-open"
    body = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "values": PLATFORM_DEFAULTS}
    assert client.put(path, json=body, headers=_headers(issued, "viewer.a")).status_code == 403
    saved = client.put(path, json=body, headers=_headers(issued, "member.a"))
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert client.put(path, json=body, headers=_headers(issued, "member.a")).json() == saved.json()
    foreign = client.get(path, headers=_headers(issued, "user.b"))
    assert foreign.json()["workspace"]["revision"] == 0
    with SessionLocal.begin() as session:
        session.scalar(select(Membership).where(Membership.user_id == "member.a")).status = "revoked"
    assert client.get(path, headers=_headers(issued, "member.a")).status_code == 401


@pytest.mark.parametrize("user", ["user.a", "user.b"])
def test_from_settings_missing_graph_is_typed_and_owner_neutral(static_authorization_http, monkeypatch, user):
    from tests.test_cross_tenant_idor import _headers
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    client, issued, _ = static_authorization_http
    response = client.post(
        "/api/v1/ir/projects/missing/graphs/missing/versions/1/research-preparations/from-settings",
        headers=_headers(issued, user), json={
            "request_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "dataset_manifest_address": "sha256:" + "0" * 64,
            "dataset_as_of": "2026-09-05T00:00:00+00:00", "hypothesis": "Missing graph",
            "expected_workspace_revision": 0, "expected_strategy_revision": 0,
        })
    assert response.status_code == 404
    assert response.json() == {"code": "V2_GRAPH_NOT_FOUND",
        "message": "Choose a saved strategy owned by this workspace."}


def test_published_alert_history_attention_and_own_review_are_owner_scoped(static_authorization_http):
    import datetime as dt
    from sqlalchemy import select
    from app.api.principal import issue_user_session
    from app.db.models import Membership
    from tests.test_cross_tenant_idor import _headers
    from tests.test_v0_monitoring_persistence import _seed_two_owners
    from tests.test_v0_monitoring_inbox_query import _seed
    client, issued, _ = static_authorization_http
    bind = SessionLocal.kw["bind"]
    _seed_two_owners(bind)
    first, _, beta = _seed(bind)
    with SessionLocal.begin() as session:
        for name, user, owner in [("alpha", "user.alpha", "tenant.alpha"), ("beta", "user.beta", "tenant.beta")]:
            issued[name] = issue_user_session(session, user_id=user, organization_id=owner,
                expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1))
    root = "/api/v1/monitoring"
    assert client.get(root + "/alerts").status_code == 401
    page = client.get(root + "/alerts", headers=_headers(issued, "alpha"))
    assert page.status_code == 200, page.text
    assert page.json()["schema"] == "monitoring-alert-page/2"
    assert page.headers["cache-control"] == "no-store"
    assert len(page.json()["items"]) == 2
    beta_page = client.get(root + "/alerts", headers=_headers(issued, "beta"))
    assert [row["alert_address"] for row in beta_page.json()["items"]] == [beta.alert.address]
    path = f"{root}/assignments/{first.alert.assignment_id}/alerts/{first.alert.address}"
    assert client.get(path, headers=_headers(issued, "beta")).status_code == 404
    assert client.post(path + "/attention", headers=_headers(issued, "beta"), json={"expected_sequence": 0, "action": "READ"}).status_code == 404
    detail = client.get(path, headers=_headers(issued, "alpha")).json()
    saved = client.post(path + "/attention", headers=_headers(issued, "alpha"), json={"expected_sequence": detail["last_sequence"], "action": "READ"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["is_unread"] is False
    assert client.get(path + "/review", headers=_headers(issued, "alpha")).json()["review"] is None
    review_body = {"disposition": "CONFIRMED", "reason_code": "RULES_MATCH", "note": "Checked against the saved strategy."}
    review = client.post(path + "/review", headers=_headers(issued, "alpha"), json=review_body)
    assert review.status_code == 200, review.text
    readback = client.get(path + "/review", headers=_headers(issued, "alpha"))
    assert readback.json()["review"]["review_address"] == review.json()["review_address"]
    assert readback.json()["review"]["note"] == review_body["note"]
    with SessionLocal.begin() as session:
        session.scalar(select(Membership).where(Membership.user_id == "user.alpha")).role = "viewer"
    assert client.get(path, headers=_headers(issued, "alpha")).status_code == 200
    assert client.post(path + "/attention", headers=_headers(issued, "alpha"), json={"expected_sequence": saved.json()["last_sequence"], "action": "ACKNOWLEDGE"}).status_code == 403
    with SessionLocal.begin() as session:
        session.scalar(select(Membership).where(Membership.user_id == "user.alpha")).status = "revoked"
    assert client.get(path, headers=_headers(issued, "alpha")).status_code == 401
