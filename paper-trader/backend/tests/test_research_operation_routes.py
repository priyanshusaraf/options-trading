import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from research.operations import ResearchOperationRecorder, safe_plan_summary


@pytest.fixture(autouse=True)
def _operation_path(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PT_RESEARCH_OPERATION_RECEIPT", str(tmp_path / "operations.json")
    )
    monkeypatch.setattr(get_settings(), "research_enabled", True)


@pytest.fixture
def client():
    return TestClient(app)


def test_never_run_status_is_explicit_and_versioned(client):
    expected = {"state": "never_run", "active": None, "last": None}

    assert client.get("/api/research/operations/status").json() == expected
    assert client.get("/api/v1/research/operations/status").json() == expected


def test_status_returns_only_persisted_current_and_last_receipts(client, monkeypatch):
    recorder = ResearchOperationRecorder.start(
        Path(os.environ["PT_RESEARCH_OPERATION_RECEIPT"]),
        trigger="nightly",
        build="abc123",
        provider_mode="historical",
        operation_id="operation-1",
        now=lambda: "2026-08-03T01:00:00Z",
    )
    recorder.set_plan(safe_plan_summary([]))

    response = client.get("/api/research/operations/status")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "available"
    assert body["active"]["operation_id"] == "operation-1"
    assert body["active"]["plan"]["items"] == []
    assert body["last"] is None


def test_status_read_never_calls_research_execution(monkeypatch, client):
    from research.orchestrator import run

    monkeypatch.setattr(
        run,
        "run_nightly",
        lambda *args, **kwargs: pytest.fail("status read executed research"),
    )

    assert client.get("/api/research/operations/status").status_code == 200


def test_corrupt_receipt_has_stable_closed_feedback(client, monkeypatch):
    receipt = Path(os.environ["PT_RESEARCH_OPERATION_RECEIPT"])
    receipt.write_text('{"not":"canonical state"}', encoding="utf-8")

    response = client.get("/api/research/operations/status")

    assert response.status_code == 409
    assert response.json() == {
        "code": "RESEARCH_OPERATION_STATE_CORRUPT",
        "message": "research operation status is unavailable because its receipt is invalid",
    }


def test_status_surface_is_read_only_and_research_gated(client, monkeypatch):
    path = "/api/research/operations/status"
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(path).status_code == 405

    monkeypatch.setattr(get_settings(), "research_enabled", False)
    assert client.get(path).status_code == 403
