"""Closed HTTP contracts expose persistence without bypassing IR edit operations."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.ir.strategies.expanding_z import GRAPH


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _create_project(client, name="Desk"):
    response = client.post("/api/ir/projects", json={"name": name, "description": "Work"})
    assert response.status_code == 201
    return response.json()


def _graph(identifier="strategy.desk"):
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    graph["version"] = 999
    graph.pop("parent_version", None)
    graph["display_name"] = "Desk graph"
    return graph


def test_project_and_initial_graph_draft_round_trip(client):
    project = _create_project(client)
    created = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": "strategy.desk", "graph": _graph()},
    )

    assert created.status_code == 201
    assert created.json()["project_id"] == project["project_id"]
    assert created.json()["revision"] == 0
    assert created.json()["current_version"] is None
    assert created.json()["graph"]["version"] == 1
    assert client.get(
        f"/api/ir/projects/{project['project_id']}/graphs/strategy.desk/draft"
    ).json() == created.json()


def test_graph_ownership_is_not_disclosed_across_projects(client):
    owner = _create_project(client, "Owner")
    other = _create_project(client, "Other")
    client.post(
        f"/api/ir/projects/{owner['project_id']}/graphs",
        json={"identifier": "strategy.owner", "graph": _graph("strategy.owner")},
    )

    hidden = client.get(
        f"/api/ir/projects/{other['project_id']}/graphs/strategy.owner/draft"
    )
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "graph artefact not found"}


def test_publish_conflict_and_invalid_transition_are_explicit(client):
    project = _create_project(client)
    base = f"/api/ir/projects/{project['project_id']}/graphs/strategy.desk"
    client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": "strategy.desk", "graph": _graph()},
    )

    stale = client.post(f"{base}/versions", json={"base_revision": 7})
    assert stale.status_code == 409
    assert stale.json() == {
        "detail": "graph draft revision conflict",
        "current_revision": 0,
    }

    published = client.post(f"{base}/versions", json={"base_revision": 0})
    assert published.status_code == 201
    assert published.json()["version"] == 1
    assert client.get(f"{base}/versions/1").json() == published.json()

    duplicate = client.post(f"{base}/versions", json={"base_revision": 0})
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "this draft revision is already published"}


def test_version_list_is_server_owned_ordered_and_mirrored(client):
    project = _create_project(client)
    base = f"/api/ir/projects/{project['project_id']}/graphs/strategy.desk"
    client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": "strategy.desk", "graph": _graph()},
    )
    published = client.post(f"{base}/versions", json={"base_revision": 0}).json()

    response = client.get(f"{base}/versions")

    assert response.status_code == 200
    assert response.json() == [{
        "project_id": project["project_id"],
        "identifier": "strategy.desk",
        "version": 1,
        "content_address": published["content_address"],
    }]
    assert client.get(f"/api/v1{base.removeprefix('/api')}/versions").json() == response.json()

    other = _create_project(client, "Other")
    assert client.get(
        f"/api/ir/projects/{other['project_id']}/graphs/strategy.desk/versions"
    ).status_code == 404


def test_invalid_graph_duplicate_identity_and_archived_project_fail_closed(client):
    project = _create_project(client)
    url = f"/api/ir/projects/{project['project_id']}/graphs"

    mismatched = client.post(
        url,
        json={"identifier": "strategy.path", "graph": _graph("strategy.body")},
    )
    assert mismatched.status_code == 422
    assert "identifier" in mismatched.json()["detail"]

    invalid = _graph("strategy.invalid")
    invalid["unexpected"] = True
    rejected = client.post(
        url, json={"identifier": "strategy.invalid", "graph": invalid}
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"].startswith("F13 at $")

    unresolved = _graph("strategy.unresolved")
    unresolved["nodes"].append({
        "instance_id": "n_missing",
        "component": {"identifier": "component.missing", "version": 1},
        "overrides": {},
    })
    assert client.post(
        url,
        json={"identifier": "strategy.unresolved", "graph": unresolved},
    ).status_code == 201
    unresolved_publish = client.post(
        f"{url}/strategy.unresolved/versions",
        json={"base_revision": 0},
    )
    assert unresolved_publish.status_code == 422
    assert unresolved_publish.json()["detail"].startswith("C5 at n_missing:")

    assert client.post(
        url, json={"identifier": "strategy.desk", "graph": _graph()}
    ).status_code == 201
    duplicate = client.post(
        url, json={"identifier": "strategy.desk", "graph": _graph()}
    )
    assert duplicate.status_code == 409

    archived = client.put(
        f"/api/ir/projects/{project['project_id']}/status",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    assert project["project_id"] not in {
        row["project_id"] for row in client.get("/api/ir/projects").json()
    }
    blocked = client.post(
        url,
        json={"identifier": "strategy.blocked", "graph": _graph("strategy.blocked")},
    )
    assert blocked.status_code == 409
    assert "archived" in blocked.json()["detail"]


def test_product_object_contract_is_closed_mirrored_and_has_no_raw_draft_write(client):
    from app.main import app

    schema = app.openapi()
    for name in (
        "ProjectCreateRequest",
        "ProjectStatusRequest",
        "GraphArtifactCreateRequest",
        "GraphPublishRequest",
    ):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False

    project = _create_project(client)
    versioned = client.get("/api/v1/ir/projects")
    assert versioned.status_code == 200
    assert any(row["project_id"] == project["project_id"] for row in versioned.json())

    draft_url = f"/api/ir/projects/{project['project_id']}/graphs/strategy.none/draft"
    for method in ("put", "patch", "delete"):
        assert client.request(method.upper(), draft_url, json={}).status_code == 405
