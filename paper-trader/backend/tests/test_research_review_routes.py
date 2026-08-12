import os
import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import research_review_routes as review_routes
from app.core.config import get_settings
from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts as graph_store
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


@pytest.mark.parametrize("prefix", ("/api/ir", "/api/v1/ir"))
def test_every_review_read_route_propagates_the_resolved_owner(prefix, client, monkeypatch):
    """Versioned aliases must not silently fall back to the legacy owner scope."""
    seen: list[tuple[str, str]] = []

    def source(project_id: str, *, owner_id: str):
        seen.append(("timeline", owner_id))
        return {
            "events": [],
            "queues": {"review_needed_runs": [], "pending_candidates": [], "active_findings": []},
            "source_errors": [],
        }

    def notes(project_id: str, *, owner_id: str):
        seen.append(("notes", owner_id))
        return ()

    def views(project_id: str, *, owner_id: str):
        seen.append(("views", owner_id))
        return ()

    def snapshots(project_id: str, *, owner_id: str):
        seen.append(("snapshots", owner_id))
        return ()

    monkeypatch.setattr(review_routes, "owner_id_for", lambda _principal: "owner.spy")
    monkeypatch.setattr(review_routes, "project_review_source", source)
    monkeypatch.setattr(review_routes.review_state, "list_notes", notes)
    monkeypatch.setattr(review_routes.review_state, "list_saved_views", views)
    monkeypatch.setattr(review_routes.review_snapshot_store, "list_snapshots", snapshots)

    base = f"{prefix}/projects/project.spy/review"
    for suffix, expected in (("", "timeline"), ("/notes", "notes"), ("/views", "views"),
                             ("/snapshots", "snapshots"), ("/search?q=needle", "notes")):
        response = client.get(f"{base}{suffix}")
        assert response.status_code == 200
        assert any(scope == expected and owner_id == "owner.spy" for scope, owner_id in seen)
    assert {owner_id for _, owner_id in seen} == {"owner.spy"}


@pytest.mark.parametrize("prefix", ("/api/ir", "/api/v1/ir"))
def test_every_review_route_passes_exact_owner_to_every_composition_and_store_call(
    prefix, client, monkeypatch,
):
    """A dropped owner argument must not turn any write or read into global state."""
    owner_id = "owner.spy"
    project_id = "project.spy"
    event_id = "event.spy"
    now = dt.datetime(2026, 8, 12, 10, 0, 0)
    source = {
        "events": [{
            "event_id": event_id,
            "type": "graph_version_published",
            "occurred_at": "2026-08-12T10:00:00.000000Z",
            "status": "published",
            "summary": "Owner spy event",
            "references": {
                "graph": None, "run_id": None, "finding_id": None,
                "candidate_id": None,
            },
        }],
        "queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "source_errors": [],
    }
    note = review_routes.review_state.ReviewNote(
        note_id="note.spy", project_id=project_id, event_id=event_id,
        event_type="graph_version_published", body="Owner spy note", created_by="owner",
        revision=0, deleted_at=None, created_at=now, updated_at=now,
    )
    view = review_routes.review_state.ReviewSavedView(
        view_id="view.spy", project_id=project_id, name="Owner spy view",
        filters={"after": None, "before": None, "event_type": None, "limit": 25, "status": None},
        created_by="owner", revision=0, deleted_at=None, created_at=now, updated_at=now,
    )
    snapshot = review_routes.review_snapshot_store.ReviewSnapshot(
        snapshot_id="snapshot.spy", project_id=project_id, label="Owner spy snapshot",
        capture_key="00000000-0000-4000-8000-000000000001",
        manifest={"schema_version": 1, "project_id": project_id},
        content_address="sha256:" + "a" * 64, created_by="owner",
        capture_started_at=now, capture_completed_at=now,
    )
    listing = review_routes.review_snapshot_store.SnapshotListing(
        snapshot_id=snapshot.snapshot_id, project_id=project_id, label=snapshot.label,
        capture_key=snapshot.capture_key, content_address=snapshot.content_address,
        created_by="owner", capture_started_at=now, capture_completed_at=now,
        integrity="verified",
    )
    calls: list[tuple[str, str]] = []

    def source_spy(_project_id: str, *, owner_id: str):
        calls.append(("project_review_source", owner_id))
        return source

    def notes_spy(_project_id: str, *, owner_id: str):
        calls.append(("list_notes", owner_id))
        return (note,)

    def create_note_spy(_project_id: str, *, owner_id: str, **_kwargs):
        calls.append(("create_note", owner_id))
        return note

    def update_note_spy(_project_id: str, _note_id: str, *, owner_id: str, **_kwargs):
        calls.append(("update_note", owner_id))
        return note

    def delete_note_spy(_project_id: str, _note_id: str, *, owner_id: str, **_kwargs):
        calls.append(("delete_note", owner_id))
        return note

    def views_spy(_project_id: str, *, owner_id: str):
        calls.append(("list_saved_views", owner_id))
        return (view,)

    def create_view_spy(_project_id: str, *, owner_id: str, **_kwargs):
        calls.append(("create_saved_view", owner_id))
        return view

    def update_view_spy(_project_id: str, _view_id: str, *, owner_id: str, **_kwargs):
        calls.append(("update_saved_view", owner_id))
        return view

    def delete_view_spy(_project_id: str, _view_id: str, *, owner_id: str, **_kwargs):
        calls.append(("delete_saved_view", owner_id))
        return view

    def capture_spy(_project_id: str, *, owner_id: str, **_kwargs):
        calls.append(("capture_snapshot", owner_id))
        return snapshot

    def snapshots_spy(_project_id: str, *, owner_id: str):
        calls.append(("list_snapshots", owner_id))
        return (listing,)

    def snapshot_spy(_project_id: str, _snapshot_id: str, *, owner_id: str):
        calls.append(("get_snapshot", owner_id))
        return snapshot

    monkeypatch.setattr(review_routes, "owner_id_for", lambda _principal: owner_id)
    monkeypatch.setattr(review_routes, "project_review_source", source_spy)
    monkeypatch.setattr(review_routes.review_state, "list_notes", notes_spy)
    monkeypatch.setattr(review_routes.review_state, "create_note", create_note_spy)
    monkeypatch.setattr(review_routes.review_state, "update_note", update_note_spy)
    monkeypatch.setattr(review_routes.review_state, "delete_note", delete_note_spy)
    monkeypatch.setattr(review_routes.review_state, "list_saved_views", views_spy)
    monkeypatch.setattr(review_routes.review_state, "create_saved_view", create_view_spy)
    monkeypatch.setattr(review_routes.review_state, "update_saved_view", update_view_spy)
    monkeypatch.setattr(review_routes.review_state, "delete_saved_view", delete_view_spy)
    monkeypatch.setattr(review_routes.review_snapshot_store, "capture_snapshot", capture_spy)
    monkeypatch.setattr(review_routes.review_snapshot_store, "list_snapshots", snapshots_spy)
    monkeypatch.setattr(review_routes.review_snapshot_store, "get_snapshot", snapshot_spy)

    base = f"{prefix}/projects/{project_id}/review"
    requests = (
        ("GET", "", None, 200),
        ("POST", "/snapshots", {
            "label": snapshot.label, "capture_key": snapshot.capture_key,
        }, 201),
        ("GET", "/snapshots", None, 200),
        ("GET", f"/snapshots/{snapshot.snapshot_id}", None, 200),
        ("GET", "/search?q=owner", None, 200),
        ("GET", "/notes", None, 200),
        ("POST", "/notes", {"event_id": event_id, "body": "Created note"}, 201),
        ("PATCH", f"/notes/{note.note_id}", {
            "base_revision": 0, "body": "Updated note",
        }, 200),
        ("DELETE", f"/notes/{note.note_id}", {"base_revision": 0}, 204),
        ("GET", "/views", None, 200),
        ("POST", "/views", {"name": view.name, "filters": {"limit": 25}}, 201),
        ("PATCH", f"/views/{view.view_id}", {
            "base_revision": 0, "name": "Updated view", "filters": {"limit": 25},
        }, 200),
        ("DELETE", f"/views/{view.view_id}", {"base_revision": 0}, 204),
    )
    for method, suffix, payload, expected_status in requests:
        response = client.request(method, f"{base}{suffix}", json=payload)
        assert response.status_code == expected_status

    assert calls == [
        ("project_review_source", owner_id),
        ("capture_snapshot", owner_id),
        ("list_snapshots", owner_id),
        ("get_snapshot", owner_id),
        ("project_review_source", owner_id), ("list_notes", owner_id),
        ("project_review_source", owner_id), ("list_notes", owner_id),
        ("project_review_source", owner_id), ("create_note", owner_id),
        ("project_review_source", owner_id), ("update_note", owner_id),
        ("delete_note", owner_id),
        ("list_saved_views", owner_id),
        ("create_saved_view", owner_id),
        ("update_saved_view", owner_id),
        ("delete_saved_view", owner_id),
    ]


@pytest.mark.parametrize("prefix", ("/api/ir", "/api/v1/ir"))
def test_public_review_owner_misses_match_absence_without_leaking_or_mutating_rows(
    prefix, client, monkeypatch,
):
    """Foreign IDs must have the exact public shape of absence, including capture retries."""
    with SessionLocal.begin() as session:
        session.add_all((
            Organization(organization_id="owner.a", name="Owner A"),
            Organization(organization_id="owner.b", name="Owner B"),
        ))
    project_a = graph_store.create_project("Route owner A", owner_id="owner.a")
    project_b = graph_store.create_project("Route owner B", owner_id="owner.b")
    note_a = review_routes.review_state.create_note(
        project_a.project_id, owner_id="owner.a", event_id="run:a",
        event_type="experiment_run", body="Owner A private note", created_by="owner",
    )
    view_a = review_routes.review_state.create_saved_view(
        project_a.project_id, owner_id="owner.a", name="Owner A private view",
        filters={"limit": 25}, created_by="owner",
    )
    capture_key = "00000000-0000-4000-8000-000000000011"
    snapshot_a = review_routes.review_snapshot_store.capture_snapshot(
        project_a.project_id, owner_id="owner.a", label="Owner A private snapshot",
        capture_key=capture_key, created_by="owner",
        source_loader=lambda _project: {
            "events": [],
            "queues": {
                "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
            },
            "source_errors": [],
        },
    )
    owner_a_before = (
        review_routes.review_state.list_notes(project_a.project_id, owner_id="owner.a"),
        review_routes.review_state.list_saved_views(project_a.project_id, owner_id="owner.a"),
        review_routes.review_snapshot_store.get_snapshot(
            project_a.project_id, snapshot_a.snapshot_id, owner_id="owner.a",
        ),
    )
    monkeypatch.setattr(review_routes, "owner_id_for", lambda _principal: "owner.b")
    local_base = f"{prefix}/projects/{project_b.project_id}/review"
    foreign_base = f"{prefix}/projects/{project_a.project_id}/review"
    absent_base = f"{prefix}/projects/project.absent/review"

    def response(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
        result = client.request(method, url, json=payload)
        return result.status_code, result.json()

    state_not_found = {
        "code": "REVIEW_STATE_NOT_FOUND", "message": "review state not found",
    }
    snapshot_not_found = {
        "code": "REVIEW_SNAPSHOT_NOT_FOUND", "message": "review snapshot not found",
    }
    project_not_found = {
        "code": "REVIEW_PROJECT_NOT_FOUND", "message": "project not found",
    }
    note_delete_foreign = response(
        "DELETE", f"{local_base}/notes/{note_a.note_id}", {"base_revision": 0},
    )
    note_delete_absent = response(
        "DELETE", f"{local_base}/notes/note.absent", {"base_revision": 0},
    )
    assert note_delete_foreign == note_delete_absent == (404, state_not_found)
    view_update_foreign = response("PATCH", f"{local_base}/views/{view_a.view_id}", {
        "base_revision": 0, "name": "No foreign revision", "filters": {"limit": 25},
    })
    view_update_absent = response("PATCH", f"{local_base}/views/view.absent", {
        "base_revision": 0, "name": "No absent revision", "filters": {"limit": 25},
    })
    assert view_update_foreign == view_update_absent == (404, state_not_found)
    view_delete_foreign = response(
        "DELETE", f"{local_base}/views/{view_a.view_id}", {"base_revision": 0},
    )
    view_delete_absent = response(
        "DELETE", f"{local_base}/views/view.absent", {"base_revision": 0},
    )
    assert view_delete_foreign == view_delete_absent == (404, state_not_found)
    snapshot_get_foreign = response("GET", f"{local_base}/snapshots/{snapshot_a.snapshot_id}")
    snapshot_get_absent = response("GET", f"{local_base}/snapshots/snapshot.absent")
    assert snapshot_get_foreign == snapshot_get_absent == (404, snapshot_not_found)

    assert response("GET", f"{foreign_base}/snapshots") == response(
        "GET", f"{absent_base}/snapshots",
    ) == (404, project_not_found)
    retry = {"label": snapshot_a.label, "capture_key": capture_key}
    assert response("POST", f"{foreign_base}/snapshots", retry) == response(
        "POST", f"{absent_base}/snapshots", retry,
    ) == (404, project_not_found)
    conflict = {**retry, "label": "Different potential capture conflict"}
    assert response("POST", f"{foreign_base}/snapshots", conflict) == response(
        "POST", f"{absent_base}/snapshots", conflict,
    ) == (404, project_not_found)

    for _status, body in (
        note_delete_foreign, view_update_foreign, view_delete_foreign,
        snapshot_get_foreign,
    ):
        assert set(body) == {"code", "message"}
        assert not {"current_revision", "created_at", "updated_at", "content_address"} & set(body)
        assert "owner.a" not in str(body)
    assert (
        review_routes.review_state.list_notes(project_a.project_id, owner_id="owner.a"),
        review_routes.review_state.list_saved_views(project_a.project_id, owner_id="owner.a"),
        review_routes.review_snapshot_store.get_snapshot(
            project_a.project_id, snapshot_a.snapshot_id, owner_id="owner.a",
        ),
    ) == owner_a_before
    assert review_routes.review_state.list_notes(project_b.project_id, owner_id="owner.b") == ()
    assert review_routes.review_state.list_saved_views(project_b.project_id, owner_id="owner.b") == ()
    assert review_routes.review_snapshot_store.list_snapshots(project_b.project_id, owner_id="owner.b") == ()


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
