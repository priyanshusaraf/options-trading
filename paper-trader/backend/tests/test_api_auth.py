"""SEC-1: token auth on the API surface.

The engine is single-user/localhost today but exposed to the LAN/tailnet; any
REST or WS call currently executes unauthenticated (including manual-open,
kill, arm). When PT_API_TOKEN is set, every /api route except the OAuth
redirect endpoints and /api/health must require a matching bearer token.
Empty token (the default) keeps auth OFF for local dev/tests."""
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner()
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
    assert res.json().get("armed") is True


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
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    c, _ = _client()
    res = c.get("/api/health")
    assert res.status_code == 200
