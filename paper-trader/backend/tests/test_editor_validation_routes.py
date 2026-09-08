from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import GraphArtifact, GraphVersion
from app.db.session import SessionLocal, init_db
from app.ir.strategies.expanding_z import GRAPH


@pytest.fixture(autouse=True)
def _store(monkeypatch):
    init_db(reset=True)
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _published(client):
    project = client.post("/api/v1/ir/projects", json={"name": "Validation", "description": ""}).json()
    document = copy.deepcopy(GRAPH)
    document["identifier"] = "strategy.validation"
    document.pop("parent_version", None)
    created = client.post(f"/api/v1/ir/projects/{project['project_id']}/graphs", json={
        "identifier": document["identifier"], "graph": document,
    })
    assert created.status_code == 201
    first = client.post(
        f"/api/v1/ir/projects/{project['project_id']}/graphs/{document['identifier']}/versions",
        json={"base_revision": 0},
    )
    assert first.status_code == 201
    return project["project_id"], document["identifier"]


def _counts(identifier):
    with SessionLocal() as session:
        artifact = session.scalar(select(GraphArtifact).where(GraphArtifact.identifier == identifier))
        return artifact.draft_revision, artifact.current_version, session.scalar(
            select(func.count()).select_from(GraphVersion).where(GraphVersion.graph_identifier == identifier))


def test_validation_uses_canonical_batch_and_rolls_every_write_back(client):
    project_id, identifier = _published(client)
    editor = client.get(f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/editor").json()
    before = _counts(identifier)
    response = client.post(
        f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/edits/validate",
        json={"base_revision": editor["draft_revision"], "base_presentation_revision": editor["layout"]["revision"],
              "edits": [{"operation": "set_display_name", "display_name": "Validated only"}],
              "presentation_edits": [{"operation": "set_position", "instance_id": editor["editable_nodes"][0]["instance_id"], "x": 40, "y": 80}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True
    assert response.json()["predicted_content_address"].startswith("sha256:")
    assert response.json()["nonauthority"] == "VALIDATION_DOES_NOT_PUBLISH_OR_GRANT_AUTHORITY"
    assert _counts(identifier) == before
    reopened = client.get(f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/editor").json()
    assert reopened["display_name"] != "Validated only"
    assert reopened["layout"]["positions"] == []


def test_invalid_batch_is_a_bounded_nonpublishing_result_and_stale_head_conflicts(client):
    project_id, identifier = _published(client)
    editor = client.get(f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/editor").json()
    before = _counts(identifier)
    invalid = client.post(f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/edits/validate", json={
        "base_revision": editor["draft_revision"], "base_presentation_revision": editor["layout"]["revision"],
        "edits": [{"operation": "set_override", "instance_id": editor["editable_nodes"][0]["instance_id"], "parameter": "does_not_exist", "value": 4}],
        "presentation_edits": [],
    })
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert invalid.json()["predicted_content_address"] is None
    assert invalid.json()["violations"]
    assert _counts(identifier) == before
    stale = client.post(f"/api/v1/ir/projects/{project_id}/graphs/{identifier}/edits/validate", json={
        "base_revision": editor["draft_revision"] + 1, "base_presentation_revision": editor["layout"]["revision"],
        "edits": [{"operation": "set_display_name", "display_name": "Stale"}], "presentation_edits": [],
    })
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "DRAFT_REVISION_CONFLICT"
    assert _counts(identifier) == before
