"""Project-owned graph drafts publish into append-only executable versions."""
from __future__ import annotations

import copy
import datetime as dt
import pytest
from sqlalchemy import select

from app.db.models import GraphArtifact, GraphVersion
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts as store
from app.ir.hashing import canonical_json, content_address
from app.ir.strategies.expanding_z import GRAPH


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)


def _graph(identifier: str, display_name: str = "Test graph") -> dict:
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    graph["version"] = 999  # persistence owns version identity, not the caller
    graph.pop("parent_version", None)
    graph["display_name"] = display_name
    return graph


def test_project_owns_an_optimistic_graph_draft():
    project = store.create_project("Desk", "Editor work", owner_id="owner")
    created = store.create_artifact(project.project_id, "strategy.desk", _graph("strategy.desk"), owner_id="owner")

    assert created.project_id == project.project_id
    assert created.identifier == "strategy.desk"
    assert created.revision == 0
    assert created.current_version is None
    assert created.graph["identifier"] == "strategy.desk"
    assert created.graph["version"] == 1
    assert "parent_version" not in created.graph
    assert store.load_draft(project.project_id, "strategy.desk", owner_id="owner") == created


def test_draft_revision_conflict_keeps_the_winning_document():
    project = store.create_project("Desk", owner_id="owner")
    store.create_artifact(project.project_id, "strategy.desk", _graph("strategy.desk"), owner_id="owner")

    winner_graph = _graph("strategy.desk", "Winner")
    winner = store.save_draft(
        project.project_id, "strategy.desk", base_revision=0, graph=winner_graph, owner_id="owner"
    )
    with pytest.raises(store.GraphConflict) as caught:
        store.save_draft(
            project.project_id,
            "strategy.desk",
            base_revision=0,
            graph=_graph("strategy.desk", "Stale"), owner_id="owner",
        )

    assert caught.value.current_revision == 1
    assert store.load_draft(project.project_id, "strategy.desk", owner_id="owner") == winner


def test_ownership_and_archive_state_fail_closed():
    owner = store.create_project("Owner", owner_id="owner")
    other = store.create_project("Other", owner_id="owner")
    store.create_artifact(owner.project_id, "strategy.owner", _graph("strategy.owner"), owner_id="owner")

    with pytest.raises(store.GraphNotFound):
        store.load_draft(other.project_id, "strategy.owner", owner_id="owner")

    archived = store.set_project_status(owner.project_id, "archived", owner_id="owner")
    assert archived.status == "archived"
    with pytest.raises(store.InvalidTransition, match="archived"):
        store.save_draft(
            owner.project_id,
            "strategy.owner",
            base_revision=0,
            graph=_graph("strategy.owner", "Blocked"), owner_id="owner",
        )
    restored = store.set_project_status(owner.project_id, "active", owner_id="owner")
    assert restored.status == "active"
    assert store.save_draft(
        owner.project_id,
        "strategy.owner",
        base_revision=0,
        graph=_graph("strategy.owner", "Restored"), owner_id="owner",
    ).revision == 1
    with pytest.raises(store.InvalidTransition):
        store.set_project_status(owner.project_id, "deleted", owner_id="owner")


def test_publish_is_append_only_and_server_assigns_version_identity():
    project = store.create_project("Desk", owner_id="owner")
    store.create_artifact(project.project_id, "strategy.desk", _graph("strategy.desk"), owner_id="owner")

    first = store.publish_draft(project.project_id, "strategy.desk", base_revision=0, owner_id="owner")
    assert first.version == 1
    assert first.graph["version"] == 1
    assert "parent_version" not in first.graph
    assert first.content_address == content_address(first.graph)

    draft = store.save_draft(
        project.project_id,
        "strategy.desk",
        base_revision=0,
        graph=_graph("strategy.desk", "Second"), owner_id="owner",
    )
    assert draft.graph["version"] == 2
    assert draft.graph["parent_version"] == 1
    second = store.publish_draft(project.project_id, "strategy.desk", base_revision=1, owner_id="owner")

    assert second.version == 2
    assert second.graph["display_name"] == "Second"
    assert first == store.load_version(project.project_id, "strategy.desk", 1, owner_id="owner")
    with pytest.raises(store.InvalidTransition, match="already published"):
        store.publish_draft(project.project_id, "strategy.desk", base_revision=1, owner_id="owner")


def test_different_immutable_json_cannot_claim_one_executable_identity():
    project = store.create_project("Desk", owner_id="owner")
    store.create_artifact(project.project_id, "strategy.desk", _graph("strategy.desk"), owner_id="owner")
    first = store.publish_draft(project.project_id, "strategy.desk", base_revision=0, owner_id="owner")
    different = copy.deepcopy(first.graph)
    different["version"] = 2
    different["parent_version"] = 1
    different["display_name"] = "Different bytes"

    with pytest.raises(ValueError, match="content address does not match"):
        with SessionLocal.begin() as session:
            session.add(GraphVersion(
                graph_identifier="strategy.desk",
                version=2,
                artifact_json=canonical_json(different),
                content_address=first.content_address,
                created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
            ))


def test_publish_failure_after_version_insert_rolls_back_version_and_pointer(monkeypatch):
    project = store.create_project("Desk", owner_id="owner")
    store.create_artifact(project.project_id, "strategy.desk", _graph("strategy.desk"), owner_id="owner")

    def fail_after_insert(*_args):
        raise RuntimeError("injected failure after immutable version insert")

    monkeypatch.setattr(store, "_after_version_insert", fail_after_insert)
    with pytest.raises(RuntimeError, match="injected failure"):
        store.publish_draft(project.project_id, "strategy.desk", base_revision=0, owner_id="owner")

    with SessionLocal() as session:
        artifact = session.get(GraphArtifact, "strategy.desk")
        versions = tuple(session.scalars(select(GraphVersion).where(
            GraphVersion.graph_identifier == "strategy.desk"
        )))
    assert artifact.current_version is None
    assert artifact.published_revision is None
    assert versions == ()


def test_identity_changing_edit_creates_reconciled_presentation_head():
    from app.ir import edit as ir_edit

    def add_constant(graph):
        edited = ir_edit.add_node(
            graph,
            "n_constant",
            "value.scalar",
            1,
            {"value": 1.0},
        )
        return store.EditResult(
            graph=edited,
            applied_operations=({"operation": "add_node"},),
            inverse_operations=({"operation": "remove_node"},),
        )

    publication, layout = store.apply_and_publish(
        store.CATALOGUE_PROJECT_ID,
        GRAPH["identifier"],
        base_revision=0,
        base_presentation_revision=0,
        presentation_operations=(),
        transform=add_constant,
        response_factory=lambda published, carried: (published, carried),
        owner_id="owner",
    )

    assert publication.published.version == GRAPH["version"] + 1
    assert layout.graph_version == publication.published.version
    assert layout.revision == 1
    assert layout.positions == ()
