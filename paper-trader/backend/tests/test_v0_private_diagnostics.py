"""HTTP consumers must receive useful V0 failures, never private diagnostic values."""
from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging import log
import app.main as main


SECRET = "SYNTHETIC_PRIVATE_MARKER"
PRIVATE = f"postgresql://user:{SECRET}@invalid/db SELECT secret FROM private /private/{SECRET}.sql"


@pytest.fixture
def v0(monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "release_profile", "v0_research_signal")
    monkeypatch.setattr(settings, "release_service_role", "api")
    monkeypatch.setattr(settings, "research_enabled", True)
    monkeypatch.setattr(settings, "api_token", "")
    caplog.set_level(logging.DEBUG, logger="paper_trader")
    entries = []
    log.subscribe(entries.append)
    # No lifespan is needed for invalid requests: do not start a runner or services.
    client = TestClient(main.app)
    yield client
    client.close()
    log.unsubscribe(entries.append)
    assert SECRET not in caplog.text
    assert SECRET not in json.dumps(entries)


class HealthySession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        return None


class FailingSession(HealthySession):
    def execute(self, *_args):
        raise RuntimeError(PRIVATE)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("plane", ["execution", "ledger", "research"])
def test_readiness_redacts_real_probe_exception(v0, monkeypatch, prefix, plane):
    factories = dict.fromkeys(("execution", "ledger", "research"), HealthySession)
    factories[plane] = FailingSession
    monkeypatch.setattr(main.app.state, "v0_plane_sessionmakers", factories, raising=False)
    response = v0.get(f"{prefix}/readiness")
    assert response.status_code == 503
    assert SECRET not in response.text
    body = response.json()
    assert body["failed_checks"] == [f"database:{plane}"]
    assert body["ok"] is body["ready"] is False
    assert body["engine"] == {"present": False}
    assert body["execution_authority"] is False
    assert body["database_planes"][plane] == {"ok": False, "error": "DATABASE_PROBE_FAILED"}


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_missing_plane_and_recovery_keep_truthful_status(v0, monkeypatch, prefix):
    factories = dict.fromkeys(("execution", "ledger"), HealthySession)
    monkeypatch.setattr(main.app.state, "v0_plane_sessionmakers", factories, raising=False)
    failed = v0.get(f"{prefix}/readiness")
    assert failed.status_code == 503
    assert failed.json()["failed_checks"] == ["database:research"]
    assert failed.json()["database_planes"]["research"]["error"] == "DATABASE_SESSION_UNAVAILABLE"
    factories["research"] = HealthySession
    healthy = v0.get(f"{prefix}/readiness")
    assert healthy.status_code == 200
    assert healthy.json()["failed_checks"] == []
    assert all(p == {"ok": True, "error": ""} for p in healthy.json()["database_planes"].values())


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("db_ok", [True, False])
def test_public_schema_failure_is_closed_and_does_not_change_health_verdict(v0, monkeypatch, prefix, db_ok):
    from app.db import migrate

    def fail(_engine):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(migrate, "schema_state", fail)
    monkeypatch.setattr(main, "_probe_db", lambda: (db_ok, PRIVATE))
    response = v0.get(f"{prefix}/health")
    assert response.status_code == (200 if db_ok else 503)
    assert SECRET not in response.text
    assert response.json()["schema"] == {
        "current": None, "head": None, "up_to_date": None, "error": "SCHEMA_PROBE_FAILED",
    }


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("path,payload,field", [
    ("/ir/projects", {"name": {SECRET: PRIVATE}}, "name"),
    ("/ir/projects", {"name": "name", "description": [PRIVATE]}, "description"),
    ("/ir/projects/p/graphs", {"identifier": "graph", "graph": PRIVATE}, "graph"),
    ("/ir/projects", {"name": "name", SECRET: PRIVATE}, "field"),
])
def test_request_input_and_arbitrary_field_names_are_closed(v0, prefix, path, payload, field):
    response = v0.post(prefix + path, json=payload)
    assert response.status_code == 422
    assert SECRET not in response.text
    body = response.json()
    assert body["code"] == "REQUEST_VALIDATION_FAILED"
    assert body["detail"][0]["loc"] == ["body", field]
    assert set(body["detail"][0]) == {"loc", "type", "msg"}


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("path,payload,code", [
    ("/ir/projects/p/graphs/g/edits", {
        "base_revision": 0, "base_presentation_revision": 0,
        "edits": [{"operation": SECRET}],
    }, "REQUEST_VALIDATION_FAILED"),
    ("/ir/projects/p/graphs/g/versions/1/experiments", {SECRET: PRIVATE}, "EXPERIMENT_REQUEST_INVALID"),
])
def test_existing_ir_envelopes_keep_codes_without_unsafe_details(v0, prefix, path, payload, code):
    response = v0.post(prefix + path, json=payload)
    assert response.status_code == 422
    assert SECRET not in response.text
    body = response.json()
    assert body["code"] == code
    assert "errors" in body and "detail" not in body
    if path.endswith("/edits"):
        assert body["errors"][0]["operation_index"] == 0
        assert body["errors"][0]["path"] == ["edits", 0]


def test_custom_validator_message_context_and_type_are_not_trusted(v0):
    error = RequestValidationError([{
        "loc": ("body", "name", SECRET), "type": SECRET, "msg": PRIVATE,
        "ctx": {"error": ValueError(PRIVATE)}, "input": PRIVATE,
    }])
    request = Request({"type": "http", "path": "/api/ir/projects", "headers": []})
    response = asyncio.run(main.editor_request_validation_handler(request, error))
    assert response.status_code == 422
    assert SECRET not in response.body.decode()
    assert json.loads(response.body)["detail"] == [{
        "loc": ["body", "name", "field"], "type": "value_error", "msg": "Invalid value",
    }]


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_malformed_json_does_not_echo_parser_context(v0, prefix):
    response = v0.post(f"{prefix}/ir/projects", content='{"name": "' + SECRET,
                       headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert SECRET not in response.text
    assert response.json()["detail"][0]["type"] == "json_invalid"


def test_standard_validation_and_probe_diagnostics_remain_compatible(monkeypatch):
    from app.db import migrate

    monkeypatch.setattr(get_settings(), "release_profile", "standard")
    monkeypatch.setattr(get_settings(), "api_token", "")
    client = TestClient(main.app, raise_server_exceptions=True)
    try:
        response = client.post("/api/ir/projects", json={"name": ["ordinary invalid input"]})
        assert response.status_code == 422
        assert response.json()["detail"][0]["input"] == ["ordinary invalid input"]
    finally:
        client.close()

    def fail(_engine):
        raise RuntimeError("ordinary schema error")

    monkeypatch.setattr(migrate, "schema_state", fail)
    assert main._schema_info()["error"] == "ordinary schema error"
