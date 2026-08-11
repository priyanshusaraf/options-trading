"""Projects and graph reads are scoped by their organization owner."""
from __future__ import annotations

import copy

import pytest

from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts as store
from app.ir.strategies.expanding_z import GRAPH


@pytest.fixture(autouse=True)
def _database() -> None:
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add_all((
            Organization(organization_id="owner.a", name="Owner A"),
            Organization(organization_id="owner.b", name="Owner B"),
        ))


def _graph(identifier: str) -> dict:
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    graph["version"] = 99
    graph.pop("parent_version", None)
    return graph


def test_project_and_graph_loads_require_owner_and_hide_other_owner() -> None:
    project_a = store.create_project("Same name", owner_id="owner.a")
    project_b = store.create_project("Same name", owner_id="owner.b")
    store.create_artifact(project_a.project_id, "owner.a.graph", _graph("owner.a.graph"), owner_id="owner.a")
    published = store.publish_draft(
        project_a.project_id, "owner.a.graph", base_revision=0, owner_id="owner.a"
    )

    assert {project.project_id for project in store.list_projects(owner_id="owner.a")} == {
        project_a.project_id
    }
    assert {project.project_id for project in store.list_projects(owner_id="owner.b")} == {
        project_b.project_id
    }
    assert store.load_version(
        project_a.project_id, "owner.a.graph", 1, owner_id="owner.a"
    ).content_address == published.content_address
    with pytest.raises(store.GraphNotFound):
        store.load_draft(project_a.project_id, "owner.a.graph", owner_id="owner.b")
    with pytest.raises(store.ProjectNotFound):
        store.set_project_status(project_a.project_id, "archived", owner_id="owner.b")
    with pytest.raises(TypeError):
        store.create_project("Unscoped")
    with pytest.raises(TypeError):
        store.list_projects()
    with pytest.raises(TypeError):
        store.load_draft(project_a.project_id, "owner.a.graph")
    with pytest.raises(TypeError):
        store.load_version(project_a.project_id, "owner.a.graph", 1)
