import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.engine.runner import EngineRunner
from app.ir.strategies.expanding_z import GRAPH


BASE = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review"
EVENT_ID = f"graph:{GRAPH['identifier']}:{GRAPH['version']}"


@pytest.fixture(autouse=True)
def _database(monkeypatch):
    init_db(reset=True)
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "api_token", "")


@pytest.fixture
def client():
    from app.main import app

    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


def test_note_crud_is_revisioned_and_owner_normalized_on_both_api_surfaces(client):
    created = client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "Review baseline"}
    )
    assert created.status_code == 201
    note = created.json()
    assert note["created_by"] == "owner"
    assert note["event_type"] == "graph_version_published"
    assert note["anchor_state"] == "available"
    assert note["revision"] == 0

    assert client.get(f"{BASE}/notes").json() == {"notes": [note]}
    assert client.get(f"{BASE}/notes".replace("/api/", "/api/v1/", 1)).json() == {
        "notes": [note]
    }
    updated = client.patch(
        f"{BASE}/notes/{note['note_id']}",
        json={"base_revision": 0, "body": "Reviewed baseline"},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 1
    stale = client.patch(
        f"{BASE}/notes/{note['note_id']}",
        json={"base_revision": 0, "body": "Must not persist"},
    )
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == 1
    assert client.get(f"{BASE}/notes").json()["notes"][0]["body"] == "Reviewed baseline"
    deleted = client.request(
        "DELETE", f"{BASE}/notes/{note['note_id']}", json={"base_revision": 1}
    )
    assert deleted.status_code == 204
    assert client.get(f"{BASE}/notes").json() == {"notes": []}


def test_note_anchor_is_server_derived_project_only_and_does_not_change_review(client):
    before = client.get(BASE).json()
    for event_id in ("invented:1", "operation:global-operation"):
        response = client.post(
            f"{BASE}/notes", json={"event_id": event_id, "body": "Invalid anchor"}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "REVIEW_NOTE_ANCHOR_INVALID"

    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()["project_id"]
    wrong = client.post(
        f"/api/ir/projects/{other}/review/notes",
        json={"event_id": EVENT_ID, "body": "Wrong project"},
    )
    assert wrong.status_code == 422

    assert client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "Valid context"}
    ).status_code == 201
    after = client.get(BASE).json()
    assert after["timeline"] == before["timeline"]
    assert after["queues"] == before["queues"]


def test_saved_view_crud_rejects_cursor_and_retains_stale_intent(client):
    created = client.post(f"{BASE}/views", json={
        "name": "Failed runs",
        "filters": {"event_type": "experiment_run", "status": "failed", "limit": 25},
    })
    assert created.status_code == 201
    view = created.json()
    assert view["filters"] == {
        "after": None, "before": None, "event_type": "experiment_run",
        "limit": 25, "status": "failed",
    }
    assert client.get(f"{BASE}/views").json() == {"views": [view]}

    duplicate = client.post(f"{BASE}/views", json={
        "name": "Failed runs", "filters": {"status": "failed"},
    })
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "REVIEW_VIEW_NAME_CONFLICT"
    invalid = client.post(f"{BASE}/views", json={
        "name": "Cursor", "filters": {"cursor": "opaque"},
    })
    assert invalid.status_code == 422
    stale = client.patch(f"{BASE}/views/{view['view_id']}", json={
        "base_revision": 7, "name": "Changed", "filters": {"status": "active"},
    })
    assert stale.status_code == 409
    assert client.get(f"{BASE}/views").json()["views"][0]["name"] == "Failed runs"

    updated = client.patch(f"{BASE}/views/{view['view_id']}", json={
        "base_revision": 0, "name": "Active findings",
        "filters": {"event_type": "finding_created", "status": "active", "limit": 50},
    })
    assert updated.status_code == 200
    assert updated.json()["revision"] == 1
    assert client.request(
        "DELETE", f"{BASE}/views/{view['view_id']}", json={"base_revision": 1}
    ).status_code == 204
    assert client.get(f"{BASE}/views").json() == {"views": []}


def test_authenticated_and_auth_disabled_owner_share_durable_review_state(client, monkeypatch):
    assert client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "Local owner note"}
    ).status_code == 201

    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    unauthorized = client.get(f"{BASE}/notes")
    assert unauthorized.status_code == 401
    authenticated = client.get(
        f"{BASE}/notes", headers={"Authorization": "Bearer secret-token"}
    )
    assert authenticated.status_code == 200
    assert authenticated.json()["notes"][0]["created_by"] == "owner"


def test_disappeared_source_keeps_note_without_copying_a_stale_summary(client, monkeypatch):
    from app.api import research_review_routes

    created = client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "Retain human context"}
    ).json()
    monkeypatch.setattr(research_review_routes, "project_review_source", lambda _project, *, owner_id: {
        "events": [],
        "queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "source_errors": [],
    })

    note = client.get(f"{BASE}/notes").json()["notes"][0]

    assert note["note_id"] == created["note_id"]
    assert note["body"] == "Retain human context"
    assert note["anchor_state"] == "missing"
    assert "summary" not in note


def test_review_state_routes_never_call_ir_research_or_execution_writes(client, monkeypatch):
    from app.core import research_read
    from app.ir import edit, resolve
    from research.orchestrator import run

    forbidden = lambda *args, **kwargs: pytest.fail("review state crossed a forbidden seam")
    monkeypatch.setattr(edit, "apply_batch", forbidden)
    monkeypatch.setattr(resolve, "resolve", forbidden)
    monkeypatch.setattr(research_read, "create_project_finding", forbidden)
    monkeypatch.setattr(research_read, "decide_project_candidate", forbidden)
    monkeypatch.setattr(run, "run_nightly", forbidden)

    assert client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "Bounded note"}
    ).status_code == 201
    assert client.post(f"{BASE}/views", json={
        "name": "Published", "filters": {"status": "published"},
    }).status_code == 201
