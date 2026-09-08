"""Golden compatibility cases for the accepted v1 IR HTTP surface."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.ir.strategies.expanding_z import GRAPH


@pytest.fixture(autouse=True)
def _database():
    init_db(reset=True)


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _v1_graph(identifier: str) -> dict:
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    return graph


def test_project_and_graph_writers_keep_v1_response_and_error_goldens(client):
    created = client.post(
        "/api/ir/projects",
        json={"name": "Compatibility desk", "description": "v1 API"},
    )
    assert created.status_code == 201
    project = created.json()
    assert set(project) == {"project_id", "name", "description", "status"}
    assert project["name"] == "Compatibility desk"
    assert project["description"] == "v1 API"
    assert project["status"] == "active"

    listed = client.get("/api/ir/projects")
    assert listed.status_code == 200
    assert project in listed.json()

    invalid_project = client.post(
        "/api/ir/projects",
        json={"name": "", "description": "v1 API"},
    )
    assert invalid_project.status_code == 422
    assert invalid_project.json()["detail"]

    identifier = "compat.v1.graph"
    graph = _v1_graph(identifier)
    expected_graph = {**graph, "version": 1}
    expected_graph.pop("parent_version", None)
    draft = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": identifier, "graph": graph},
    )
    assert draft.status_code == 201, draft.text
    draft_body = draft.json()
    assert set(draft_body) == {
        "project_id", "identifier", "display_name", "revision",
        "current_version", "graph",
    }
    assert draft_body["project_id"] == project["project_id"]
    assert draft_body["identifier"] == identifier
    assert draft_body["graph"] == expected_graph

    loaded_draft = client.get(
        f"/api/ir/projects/{project['project_id']}/graphs/{identifier}/draft"
    )
    assert loaded_draft.status_code == 200
    assert loaded_draft.json() == draft_body

    versions_before = client.get(
        f"/api/ir/projects/{project['project_id']}/graphs/{identifier}/versions"
    )
    assert versions_before.status_code == 200
    assert versions_before.json() == []

    published = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs/{identifier}/versions",
        json={"base_revision": draft_body["revision"]},
    )
    assert published.status_code == 201, published.text
    published_body = published.json()
    assert set(published_body) == {
        "project_id", "identifier", "version", "content_address", "graph",
    }
    assert published_body["graph"] == expected_graph
    assert published_body["version"] == expected_graph["version"]
    assert published_body["content_address"].startswith("sha256:")

    fetched = client.get(
        f"/api/ir/projects/{project['project_id']}/graphs/{identifier}/versions/"
        f"{published_body['version']}"
    )
    assert fetched.status_code == 200
    assert fetched.json() == published_body

    versions_after = client.get(
        f"/api/ir/projects/{project['project_id']}/graphs/{identifier}/versions"
    )
    assert versions_after.status_code == 200
    assert versions_after.json() == [{
        "project_id": project["project_id"],
        "identifier": identifier,
        "version": published_body["version"],
        "content_address": published_body["content_address"],
    }]

    conflict = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs/{identifier}/versions",
        json={"base_revision": 0},
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "this draft revision is already published"}

    bad_graph = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": "compat.v2.rejected", "graph": {**graph, "format_version": 2}},
    )
    assert bad_graph.status_code == 422
    assert bad_graph.json()["detail"] == "legacy graph writer accepts only format_version 1"

    archived = client.put(
        f"/api/ir/projects/{project['project_id']}/status",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    assert archived.json() == {**project, "status": "archived"}


def test_v1_document_envelope_round_trips_and_rejects_format_mismatch(client):
    identifier = "compat.v1.document"
    document = _v1_graph(identifier)
    payload = {"format_version": 1, "document": document}
    created = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/documents/{identifier}",
        json=payload,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert set(body) == {"format_version", "document", "content_address"}
    assert body["format_version"] == 1
    expected_document = {**document, "version": 1}
    expected_document.pop("parent_version", None)
    assert body["document"] == expected_document
    assert body["content_address"].startswith("sha256:")

    read = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/documents/{identifier}/1",
        params={"format_version": "1"},
    )
    assert read.status_code == 200
    assert read.json() == body

    wrong_envelope = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/documents/compat.v1.mismatch",
        json={"format_version": 1, "document": {**document, "format_version": 2}},
    )
    assert wrong_envelope.status_code == 422
    assert wrong_envelope.json()["detail"] == "document format_version must match the request discriminator"


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("missing", {"document": {"format_version": 1}}),
        ("boolean", {"format_version": True, "document": {"format_version": 1}}),
        ("float", {"format_version": 1.5, "document": {"format_version": 1}}),
        ("string", {"format_version": "1", "document": {"format_version": 1}}),
        ("unsupported", {"format_version": 3, "document": {"format_version": 3}}),
    ],
)
def test_document_format_refusals_are_closed_and_do_not_persist(client, label, payload):
    identifier = f"compat.v1.refused.{label}"
    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/documents/{identifier}",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]

    draft = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{identifier}/draft"
    )
    assert draft.status_code == 404
    assert draft.json() == {"detail": "graph artefact not found"}


def test_document_v1_read_requires_explicit_supported_query_discriminator(client):
    identifier = "compat.v1.query"
    document = _v1_graph(identifier)
    created = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/documents/{identifier}",
        json={"format_version": 1, "document": document},
    )
    assert created.status_code == 201, created.text

    for value in (None, "true", "1.5", "one", "3"):
        params = {} if value is None else {"format_version": value}
        response = client.get(
            f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/documents/{identifier}/{document['version']}",
            params=params,
        )
        assert response.status_code == 422
        assert response.json()["detail"]
