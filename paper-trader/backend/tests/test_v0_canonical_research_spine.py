"""Cross-route V0 research spine without a production fixture or second authority."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import GraphArtifact, GraphVersion, Organization, Project
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts as graph_store
from app.ir.strategies.expanding_z import GRAPH
from research.config import research_db_path
from research.domain.base import ResearchBase, init_research_db, make_engine


@pytest.fixture(autouse=True)
def _stores(monkeypatch):
    init_db(reset=True)
    engine = make_engine(research_db_path())
    ResearchBase.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS research_schema_version")
    init_research_db(engine)
    engine.dispose()
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _counts() -> tuple[int, int, int]:
    with SessionLocal() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (
            Project, GraphArtifact, GraphVersion,
        ))


def test_owner_authored_project_graph_editor_revision_and_review_reopen(client):
    project = client.post("/api/v1/ir/projects", json={
        "name": "Owner-authored research", "description": "No imported strategy fixture.",
    })
    assert project.status_code == 201, project.text
    project_id = project.json()["project_id"]
    project_page = client.get("/api/v1/ir/projects/research-spine/index?limit=50")
    assert project_page.status_code == 200, project_page.text
    assert project_page.json()["schema"] == "strategy-os-research-project-page/1"
    assert project_page.json()["next_cursor"] is None
    assert project.json() in project_page.json()["items"]
    identifier = "strategy.owner-authored"
    document = copy.deepcopy(GRAPH)
    document["identifier"] = identifier
    document["display_name"] = "Owner-authored graph"
    document["version"] = 999
    document.pop("parent_version", None)

    created = client.post(f"/api/v1/ir/projects/{project_id}/graphs", json={
        "identifier": identifier, "graph": document,
    })
    assert created.status_code == 201, created.text
    assert created.json()["revision"] == 0
    assert created.json()["current_version"] is None

    indexed = client.get(f"/api/v1/ir/projects/{project_id}/graphs?limit=50")
    assert indexed.status_code == 200
    assert indexed.json()["items"] == [{
        "identifier": identifier, "display_name": "Owner-authored graph",
        "draft_revision": 0, "current_version": None,
    }]

    first = client.post(
        f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/versions",
        json={"base_revision": 0},
    )
    assert first.status_code == 201, first.text
    editor_url = f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/editor"
    editor = client.get(editor_url)
    assert editor.status_code == 200, editor.text
    edited = client.post(editor_url.removesuffix("/editor") + "/edits", json={
        "base_revision": editor.json()["draft_revision"],
        "base_presentation_revision": editor.json()["layout"]["revision"],
        "edits": [{"operation": "set_display_name", "display_name": "Reviewed graph"}],
        "presentation_edits": [],
    })
    assert edited.status_code == 201, edited.text
    assert edited.json()["version"] == 2
    assert edited.json()["content_address"] != first.json()["content_address"]

    versions = client.get(editor_url.removesuffix("/editor") + "/versions")
    assert versions.status_code == 200
    assert [(item["version"], item["content_address"]) for item in versions.json()] == [
        (1, first.json()["content_address"]), (2, edited.json()["content_address"]),
    ]
    reopened = client.get(editor_url)
    assert reopened.status_code == 200
    assert reopened.json()["display_name"] == "Reviewed graph"
    assert reopened.json()["version"] == 2
    assert reopened.json()["content_address"] == edited.json()["content_address"]

    review = client.get(f"/api/v1/ir/projects/{project_id}/review?limit=50")
    assert review.status_code == 200, review.text
    graph_events = [event for event in review.json()["timeline"]["events"]
                    if event["type"] == "graph_version_published"]
    assert [event["references"]["graph"]["version"] for event in graph_events] == [2, 1]
    assert all(event["references"]["graph"]["content_address"] for event in graph_events)
    runs = client.get(
        f"/api/v1/ir/projects/{project_id}/research-spine/experiments?limit=25"
    )
    assert runs.status_code == 200, runs.text
    assert runs.json() == {
        "schema": "strategy-os-research-run-page/1",
        "project_id": project_id,
        "runs": [],
        "next_cursor": None,
    }


def test_project_index_is_owner_scoped_and_keyset_bounded(client):
    created = [client.post("/api/v1/ir/projects", json={
        "name": f"Project {index}", "description": "",
    }).json() for index in range(3)]
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="owner.foreign-index", name="Foreign"))
    foreign = graph_store.create_project("Foreign project", owner_id="owner.foreign-index")
    first = client.get("/api/v1/ir/projects/research-spine/index?limit=2")
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert first.json()["next_cursor"] == first.json()["items"][-1]["project_id"]
    second = client.get(
        "/api/v1/ir/projects/research-spine/index?limit=2&after="
        + first.json()["next_cursor"]
    )
    assert second.status_code == 200
    seen = [item["project_id"] for item in first.json()["items"] + second.json()["items"]]
    assert set(item["project_id"] for item in created).issubset(seen)
    assert foreign.project_id not in seen
    assert seen == sorted(seen)
    assert second.json()["next_cursor"] is None


def test_bounded_run_page_projects_detail_reads_without_leaking_evidence_payload(
    client, monkeypatch,
):
    from app.api import research_spine_routes

    project = client.post("/api/v1/ir/projects", json={
        "name": "Run page", "description": "",
    }).json()
    graph = {
        "project_id": project["project_id"], "identifier": "strategy.run-page",
        "version": 1, "content_address": "sha256:" + "a" * 64,
    }
    monkeypatch.setattr(
        research_spine_routes, "_owner_run_ids",
        lambda **_kwargs: ([7], False),
    )
    monkeypatch.setattr(
        research_spine_routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: {
            "run_id": 7, "spec_id": "a" * 32, "status": "completed",
            "decision": "archive", "evidence_state": "verified",
            "graph": graph, "candidate": None,
            "evidence": {"private_large_result": "must stay on detail"},
        },
    )
    response = client.get(
        f"/api/v1/ir/projects/{project['project_id']}/research-spine/experiments?limit=25"
    )
    assert response.status_code == 200, response.text
    assert response.json()["runs"] == [{
        "run_id": 7, "spec_id": "a" * 32, "status": "completed",
        "decision": "archive", "evidence_state": "verified",
        "graph": graph, "candidate": None,
    }]


def test_foreign_and_guessed_research_spine_identities_share_private_absence_without_writes(
    client, monkeypatch,
):
    owner = "owner.spine-a"
    other = "owner.spine-b"
    with SessionLocal.begin() as session:
        session.add_all([Organization(organization_id=owner, name="A"), Organization(organization_id=other, name="B")])
    monkeypatch.setattr(get_settings(), "owner_id", owner)
    project = client.post("/api/v1/ir/projects", json={"name": "Private", "description": ""}).json()
    identifier = "strategy.private"
    document = copy.deepcopy(GRAPH)
    document["identifier"] = identifier
    document.pop("parent_version", None)
    assert client.post(f"/api/v1/ir/projects/{project['project_id']}/graphs", json={
        "identifier": identifier, "graph": document,
    }).status_code == 201
    assert client.post(
        f"/api/v1/ir/projects/{project['project_id']}/graphs/{identifier}/versions",
        json={"base_revision": 0},
    ).status_code == 201
    before = _counts()

    monkeypatch.setattr(get_settings(), "owner_id", other)
    missing_project = "project.guessed"
    pairs = [
        (f"/api/v1/ir/projects/{project['project_id']}/graphs?limit=50",
         f"/api/v1/ir/projects/{missing_project}/graphs?limit=50"),
        (f"/api/v1/ir/projects/{project['project_id']}/graphs/{identifier}/editor",
         f"/api/v1/ir/projects/{missing_project}/graphs/{identifier}/editor"),
        (f"/api/v1/ir/projects/{project['project_id']}/graphs/{identifier}/versions",
         f"/api/v1/ir/projects/{missing_project}/graphs/{identifier}/versions"),
        (f"/api/v1/ir/projects/{project['project_id']}/review?limit=50",
         f"/api/v1/ir/projects/{missing_project}/review?limit=50"),
        (f"/api/v1/ir/projects/{project['project_id']}/research-spine/experiments?limit=25",
         f"/api/v1/ir/projects/{missing_project}/research-spine/experiments?limit=25"),
    ]
    for foreign, guessed in pairs:
        left = client.get(foreign)
        right = client.get(guessed)
        assert left.status_code == right.status_code == 404
        assert left.json() == right.json()
    assert _counts() == before
