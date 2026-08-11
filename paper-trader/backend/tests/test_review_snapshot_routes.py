import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.engine.runner import EngineRunner


BASE = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review/snapshots"
CAPTURE = {
    "label": "Morning review",
    "capture_key": "2ba56d22-7094-4a8d-9bf5-b84a4e8f083f",
}


@pytest.fixture(autouse=True)
def _database(monkeypatch):
    from app.core import review_snapshot_store

    init_db(reset=True)
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "api_token", "")
    monkeypatch.setattr(review_snapshot_store, "project_review_source", lambda _project: {
        "events": [],
        "queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "source_errors": [],
    })


@pytest.fixture
def client():
    from app.main import app

    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


def test_capture_list_and_read_are_closed_owner_routes_on_both_api_surfaces(client):
    invalid = client.post(BASE, json={**CAPTURE, "events": []})
    assert invalid.status_code == 422

    created = client.post(BASE, json=CAPTURE)
    assert created.status_code == 201
    snapshot = created.json()
    assert snapshot["label"] == "Morning review"
    assert snapshot["created_by"] == "owner"
    assert "capture_window" in snapshot
    assert "as_of" not in snapshot
    assert "global_operations" not in snapshot["manifest"]
    assert set(snapshot["manifest"]) == {
        "schema_version", "project_id", "events", "captured_queues", "notes",
        "source_errors",
    }

    listing = client.get(BASE).json()
    assert listing == {"snapshots": [{key: value for key, value in snapshot.items()
                                      if key != "manifest"}]}
    assert listing["snapshots"][0]["integrity"] == "verified"
    mirrored = client.get(
        f"{BASE}/{snapshot['snapshot_id']}".replace("/api/", "/api/v1/", 1)
    )
    assert mirrored.status_code == 200
    assert mirrored.json() == snapshot


def test_capture_retry_and_source_failure_feedback_are_exact(client, monkeypatch):
    from app.core import review_snapshot_store

    first = client.post(BASE, json=CAPTURE)
    assert first.status_code == 201
    assert client.post(BASE, json=CAPTURE).json() == first.json()
    conflict = client.post(BASE, json={**CAPTURE, "label": "Different"})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "REVIEW_SNAPSHOT_CAPTURE_CONFLICT"

    monkeypatch.setattr(review_snapshot_store, "project_review_source", lambda _project: {
        "events": [],
        "queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "source_errors": [{
            "source": "run", "source_id": "12", "code": "RUN_BINDING_CORRUPT",
        }],
    })
    failed = client.post(BASE, json={
        "label": "Incomplete", "capture_key": "8181ee82-81a4-4b2b-b005-cf0c55abec9c",
    })
    assert failed.status_code == 409
    assert failed.json()["code"] == "REVIEW_SNAPSHOT_SOURCE_INCOMPLETE"
    assert client.get(BASE).json()["snapshots"] == [
        {key: value for key, value in first.json().items() if key != "manifest"}
    ]


def test_snapshot_routes_never_call_edit_resolve_research_or_execution_seams(client, monkeypatch):
    from app.core import research_read
    from app.editor import graph_artifacts, layouts
    from app.ir import edit
    from research.orchestrator import run

    forbidden = lambda *args, **kwargs: pytest.fail("snapshot crossed a forbidden seam")
    # Patch the bindings the call path actually resolves. `graph_artifacts` does
    # `from app.ir.resolve import resolve`, so patching `app.ir.resolve.resolve`
    # would leave its own reference intact and the guard would never fire.
    monkeypatch.setattr(edit, "apply_batch", forbidden)
    monkeypatch.setattr(graph_artifacts, "resolve", forbidden)
    monkeypatch.setattr(layouts, "load_layout_in_session", forbidden)
    monkeypatch.setattr(layouts, "carry_and_reconcile_presentation", forbidden)
    monkeypatch.setattr(layouts, "apply_presentation_batch_in_session", forbidden)
    monkeypatch.setattr(research_read, "create_project_finding", forbidden)
    monkeypatch.setattr(research_read, "decide_project_candidate", forbidden)
    monkeypatch.setattr(research_read, "revise_project_finding", forbidden)
    monkeypatch.setattr(run, "run_nightly", forbidden)

    created = client.post(BASE, json=CAPTURE)
    assert created.status_code == 201
    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{created.json()['snapshot_id']}").status_code == 200


def test_snapshot_routes_are_owner_only_and_closed_to_mutating_methods(client, monkeypatch):
    created = client.post(BASE, json=CAPTURE)
    assert created.status_code == 201
    snapshot_id = created.json()["snapshot_id"]

    for method, path in (
        ("PUT", f"{BASE}/{snapshot_id}"), ("PATCH", f"{BASE}/{snapshot_id}"),
        ("DELETE", f"{BASE}/{snapshot_id}"), ("PUT", BASE), ("DELETE", BASE),
    ):
        assert client.request(method, path, json={}).status_code == 405, (method, path)

    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=CAPTURE).status_code == 401
    assert client.get(f"{BASE}/{snapshot_id}").status_code == 401
    authorized = client.get(BASE, headers={"Authorization": "Bearer secret-token"})
    assert authorized.status_code == 200
    assert authorized.json()["snapshots"][0]["created_by"] == "owner"


def test_capture_cannot_acknowledge_suppress_or_replace_live_queues(client):
    review_before = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review"
    ).json()
    notes_before = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review/notes"
    ).json()

    assert client.post(BASE, json=CAPTURE).status_code == 201

    review_after = client.get(f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review").json()
    # `as_of` is the read clock of the derived view, not queue state; every other
    # field of the live review must be byte-identical after a capture.
    assert {key: value for key, value in review_after.items() if key != "as_of"} == {
        key: value for key, value in review_before.items() if key != "as_of"
    }
    assert client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/review/notes"
    ).json() == notes_before
    assert "snapshot" not in str(review_before)
    assert "captured_queues" not in review_before


def test_snapshot_reads_never_recompute_evidence_or_touch_presentation_state(
    client, monkeypatch,
):
    from app.core import research_read

    forbidden = lambda *args, **kwargs: pytest.fail("snapshot crossed a forbidden seam")
    # `raising=True` is the point: a renamed or deleted seam must break this test
    # rather than silently patch nothing, which is how a guard becomes vacuous.
    monkeypatch.setattr(research_read, "get_graph_run", forbidden, raising=True)
    monkeypatch.setattr(research_read, "list_graph_runs", forbidden, raising=True)

    created = client.post(BASE, json=CAPTURE)
    assert created.status_code == 201
    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{created.json()['snapshot_id']}").status_code == 200


def test_archived_project_serves_history_but_refuses_further_capture(client):
    from app.editor import graph_artifacts

    created = client.post(BASE, json=CAPTURE)
    assert created.status_code == 201
    graph_artifacts.set_project_status(CATALOGUE_PROJECT_ID, "archived")

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{created.json()['snapshot_id']}").status_code == 200
    refused = client.post(BASE, json={
        "label": "After archive", "capture_key": "3c4d1a1e-2f5b-4c6d-8e7f-9a0b1c2d3e4f",
    })
    assert refused.status_code == 409
    assert refused.json()["code"] == "REVIEW_PROJECT_ARCHIVED"
