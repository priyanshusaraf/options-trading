import datetime as dt

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

    app.state.runner = EngineRunner()
    return TestClient(app)


def test_search_route_finds_event_summaries_and_active_owner_notes_on_both_surfaces(client):
    note = client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "Owner ALPHA context"}
    ).json()

    event_page = client.get(f"{BASE}/search", params={"q": "published", "limit": 1})
    assert event_page.status_code == 200
    assert event_page.json()["results"][0]["kind"] == "event"
    assert event_page.json()["results"][0]["text"].startswith("Published ")
    note_page = client.get(
        f"{BASE}/search".replace("/api/", "/api/v1/", 1),
        params={"q": "alpha context"},
    )
    assert note_page.status_code == 200
    assert note_page.json()["results"] == [{
        "result_id": f"note:{note['note_id']}",
        "kind": "note",
        "event_id": EVENT_ID,
        "event_type": "graph_version_published",
        "text": "Owner ALPHA context",
        "timestamp": note["updated_at"],
        "anchor_state": "available",
        "reference": {"run_id": None, "finding_id": None, "candidate_id": None},
    }]
    assert all(
        item["code"] != "REVIEW_NOTE_SOURCE_CORRUPT"
        for item in note_page.json()["source_errors"]
    )


def test_search_is_project_isolated_and_excludes_deleted_notes_and_non_corpus_text(client):
    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()["project_id"]
    other_event = client.get(f"/api/ir/projects/{other}/review").json()["timeline"]["events"]
    assert other_event == []
    local = client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "private-corpus-marker"}
    ).json()
    assert client.get(
        f"/api/ir/projects/{other}/review/search", params={"q": "private-corpus-marker"}
    ).json()["results"] == []
    assert client.request(
        "DELETE", f"{BASE}/notes/{local['note_id']}", json={"base_revision": 0}
    ).status_code == 204
    assert client.get(
        f"{BASE}/search", params={"q": "private-corpus-marker"}
    ).json()["results"] == []

    # These strings exist outside the accepted summary/note corpus and must not become searchable.
    for excluded in ("threshold", "scorecard", "candidate reason", "operation_id"):
        assert client.get(f"{BASE}/search", params={"q": excluded}).json()["results"] == []


def test_missing_anchor_note_remains_searchable_and_source_errors_are_contained(client, monkeypatch):
    from app.api import research_review_routes

    note = client.post(
        f"{BASE}/notes", json={"event_id": EVENT_ID, "body": "human retained context"}
    ).json()
    monkeypatch.setattr(research_review_routes, "project_review_source", lambda _project: {
        "events": [],
        "queues": {"review_needed_runs": [], "pending_candidates": [], "active_findings": []},
        "source_errors": [{
            "source": "graph_version", "source_id": "broken",
            "code": "GRAPH_VERSION_CORRUPT",
        }],
    })

    page = client.get(f"{BASE}/search", params={"q": "retained"}).json()

    assert page["results"][0]["result_id"] == f"note:{note['note_id']}"
    assert page["results"][0]["anchor_state"] == "missing"
    assert page["source_errors"] == [{
        "source": "graph_version", "source_id": "broken", "code": "GRAPH_VERSION_CORRUPT",
    }]
    assert "summary" not in page["results"][0]


def test_corrupt_note_source_is_reported_without_hiding_verified_event_matches(client, monkeypatch):
    from app.api import research_review_routes
    from app.core.review_state import ReviewNote

    valid = client.get(f"{BASE}/search", params={"q": "published"}).json()["results"]
    corrupt = ReviewNote(
        note_id="note.corrupt", project_id=CATALOGUE_PROJECT_ID, event_id=EVENT_ID,
        event_type="graph_version_published", body="", created_by="owner", revision=0,
        deleted_at=None,
        created_at=dt.datetime(2026, 8, 3),
        updated_at=dt.datetime(2026, 8, 3),
    )
    monkeypatch.setattr(research_review_routes.review_state, "list_notes", lambda _project: (corrupt,))

    page = client.get(f"{BASE}/search", params={"q": "published"})

    assert page.status_code == 200
    assert page.json()["results"] == valid
    assert page.json()["source_errors"][-1]["code"] == "REVIEW_NOTE_SOURCE_CORRUPT"


def test_search_query_is_closed_exact_and_cursor_is_bound_to_query(client):
    for params in (
        {"q": "x"},
        {"q": "valid", "unknown": "field"},
        [("q", "valid"), ("q", "duplicate")],
    ):
        response = client.get(f"{BASE}/search", params=params)
        assert response.status_code == 422
        assert response.json()["code"] == "REVIEW_SEARCH_INVALID"

    first = client.get(f"{BASE}/search", params={"q": "published", "limit": 1}).json()
    if first["next_cursor"] is not None:
        mismatch = client.get(f"{BASE}/search", params={
            "q": "different", "cursor": first["next_cursor"],
        })
        assert mismatch.status_code == 422
        assert "another query" in mismatch.json()["message"]


def test_invalid_search_is_rejected_before_loading_any_source(client, monkeypatch):
    from app.api import research_review_routes

    monkeypatch.setattr(
        research_review_routes,
        "project_review_source",
        lambda _project: pytest.fail("invalid query loaded project sources"),
    )
    monkeypatch.setattr(
        research_review_routes.review_state,
        "list_notes",
        lambda _project: pytest.fail("invalid query loaded review notes"),
    )

    response = client.get(f"{BASE}/search", params={"q": "x"})

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_SEARCH_INVALID"


def test_search_never_calls_ir_research_execution_or_review_write_seams(client, monkeypatch):
    from app.core import research_read, review_state
    from app.ir import edit, resolve
    from research.orchestrator import run

    forbidden = lambda *args, **kwargs: pytest.fail("search crossed a forbidden seam")
    monkeypatch.setattr(edit, "apply_batch", forbidden)
    monkeypatch.setattr(resolve, "resolve", forbidden)
    monkeypatch.setattr(research_read, "create_project_finding", forbidden)
    monkeypatch.setattr(research_read, "decide_project_candidate", forbidden)
    monkeypatch.setattr(run, "run_nightly", forbidden)
    monkeypatch.setattr(review_state, "create_note", forbidden)
    monkeypatch.setattr(review_state, "update_note", forbidden)
    monkeypatch.setattr(review_state, "delete_note", forbidden)

    assert client.get(f"{BASE}/search", params={"q": "published"}).status_code == 200
