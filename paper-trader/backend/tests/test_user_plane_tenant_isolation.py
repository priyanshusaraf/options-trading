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


def test_load_version_uses_one_absent_shape_for_owner_graph_and_version_misses() -> None:
    project = store.create_project("Owner A", owner_id="owner.a")
    store.create_artifact(
        project.project_id, "owner.a.graph", _graph("owner.a.graph"), owner_id="owner.a"
    )
    store.publish_draft(project.project_id, "owner.a.graph", base_revision=0, owner_id="owner.a")

    def absent_shape(**request):
        with pytest.raises(store.GraphNotFound) as caught:
            store.load_version(**request)
        return type(caught.value), caught.value.args, str(caught.value)

    wrong_owner = absent_shape(
        project_id=project.project_id, identifier="owner.a.graph", version=1, owner_id="owner.b"
    )
    absent_version = absent_shape(
        project_id=project.project_id, identifier="owner.a.graph", version=2, owner_id="owner.a"
    )
    absent_graph = absent_shape(
        project_id=project.project_id, identifier="absent.graph", version=1, owner_id="owner.a"
    )

    assert wrong_owner == absent_version == absent_graph


def test_list_versions_hides_another_owners_graph_as_an_absent_graph() -> None:
    project = store.create_project("Owner A", owner_id="owner.a")
    store.create_artifact(
        project.project_id, "owner.a.graph", _graph("owner.a.graph"), owner_id="owner.a"
    )

    with pytest.raises(store.GraphNotFound) as wrong_owner:
        store.list_versions(project.project_id, "owner.a.graph", owner_id="owner.b")
    with pytest.raises(store.GraphNotFound) as absent_graph:
        store.list_versions(project.project_id, "absent.graph", owner_id="owner.a")

    assert type(wrong_owner.value) is type(absent_graph.value) is store.GraphNotFound


def test_project_version_events_do_not_duplicate_for_another_owned_project() -> None:
    project = store.create_project("First", owner_id="owner.a")
    store.create_project("Second", owner_id="owner.a")
    store.create_artifact(project.project_id, "owner.a.events", _graph("owner.a.events"), owner_id="owner.a")
    store.publish_draft(project.project_id, "owner.a.events", base_revision=0, owner_id="owner.a")

    assert [event.identifier for event in store.list_project_version_events(
        project.project_id, owner_id="owner.a"
    )] == ["owner.a.events"]
