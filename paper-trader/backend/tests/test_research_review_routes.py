import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.engine.runner import EngineRunner
from app.ir.strategies.expanding_z import GRAPH
from research.config import research_db_path
from research.domain.base import ResearchBase, init_research_db, make_engine
from research.operations import ResearchOperationRecorder, safe_plan_summary


URL = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review"


@pytest.fixture(autouse=True)
def _stores(tmp_path, monkeypatch):
    init_db(reset=True)
    engine = make_engine(research_db_path())
    ResearchBase.metadata.drop_all(engine)
    init_research_db(engine)
    engine.dispose()
    monkeypatch.setenv(
        "PT_RESEARCH_OPERATION_RECEIPT", str(tmp_path / "operations.json")
    )
    monkeypatch.setattr(get_settings(), "research_enabled", True)


@pytest.fixture
def client():
    from app.main import app

    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


def test_review_keeps_project_timeline_separate_from_global_operations(client):
    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "project_id", "as_of", "timeline", "queues", "global_operations",
        "source_errors",
    }
    assert body["project_id"] == CATALOGUE_PROJECT_ID
    assert body["timeline"] == {
        "events": [{
            "event_id": f"graph:{GRAPH['identifier']}:{GRAPH['version']}",
            "type": "graph_version_published",
            "occurred_at": body["timeline"]["events"][0]["occurred_at"],
            "status": "published",
            "summary": f"Published {GRAPH['identifier']} version {GRAPH['version']}",
            "references": {
                "graph": {
                    "identifier": GRAPH["identifier"],
                    "version": GRAPH["version"],
                    "content_address": body["timeline"]["events"][0]["references"]["graph"]["content_address"],
                },
                "run_id": None, "finding_id": None, "candidate_id": None,
            },
        }],
        "next_cursor": None,
    }
    assert body["global_operations"] == {
        "state": "never_run", "active": None, "last": None,
    }
    assert body["queues"]["failed_operation"] is None
    assert body["source_errors"] == []
    assert all(event["type"] != "research_operation" for event in body["timeline"]["events"])
    assert client.get(URL.replace("/api/", "/api/v1/", 1)).json()["timeline"] == body["timeline"]


def test_review_filters_and_query_contract_fail_closed(client):
    assert client.get(URL, params={"event_type": "experiment_run"}).json()["timeline"] == {
        "events": [], "next_cursor": None,
    }
    assert client.get(URL, params={"event_type": "unknown"}).status_code == 422
    assert client.get(URL, params={"unknown": "field"}).status_code == 422
    assert client.get(URL, params={"limit": 101}).status_code == 422
    assert client.get(URL, params={"cursor": "tampered"}).status_code == 422
    assert client.get(URL.replace(CATALOGUE_PROJECT_ID, "project.other")).status_code == 404


def test_failed_global_operation_is_a_queue_but_never_a_project_event(client):
    recorder = ResearchOperationRecorder.start(
        Path(os.environ["PT_RESEARCH_OPERATION_RECEIPT"]),
        trigger="nightly", build="abc123", provider_mode="historical",
        operation_id="global-operation",
        now=lambda: "2026-08-03T01:00:00Z",
    )
    recorder.set_plan(safe_plan_summary([]))
    recorder.transition("generation")
    recorder.fail(now=lambda: "2026-08-03T01:01:00Z")

    body = client.get(URL).json()

    assert body["global_operations"]["last"]["operation_id"] == "global-operation"
    assert body["queues"]["failed_operation"]["operation_id"] == "global-operation"
    assert all("global-operation" not in event["event_id"] for event in body["timeline"]["events"])
    assert all(event["type"] != "research_operation" for event in body["timeline"]["events"])


def test_corrupt_global_receipt_is_contained_from_valid_project_timeline(client):
    receipt = Path(os.environ["PT_RESEARCH_OPERATION_RECEIPT"])
    receipt.write_text('{"tampered":true}', encoding="utf-8")

    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["timeline"]["events"][0]["type"] == "graph_version_published"
    assert body["global_operations"] is None
    assert body["queues"]["failed_operation"] is None
    assert body["source_errors"] == [{
        "source": "global_operation", "source_id": "current_last",
        "code": "OPERATION_STATE_CORRUPT",
    }]


def test_review_surface_is_read_only_and_research_gated(client, monkeypatch):
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(URL).status_code == 405
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    assert client.get(URL).status_code == 403


def test_review_read_never_resolves_executes_or_mutates(client, monkeypatch):
    from app.core import research_read
    from app.ir import resolve as ir_resolve
    from research.data import store as data_store
    from research.orchestrator import run

    forbidden = lambda *args, **kwargs: pytest.fail("review crossed its read boundary")
    monkeypatch.setattr(ir_resolve, "resolve", forbidden)
    monkeypatch.setattr(data_store, "materialize", forbidden)
    monkeypatch.setattr(run, "run_nightly", forbidden)
    monkeypatch.setattr(research_read, "create_project_finding", forbidden)
    monkeypatch.setattr(research_read, "decide_project_candidate", forbidden)

    assert client.get(URL).status_code == 200
