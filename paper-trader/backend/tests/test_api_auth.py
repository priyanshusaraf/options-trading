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
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
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
