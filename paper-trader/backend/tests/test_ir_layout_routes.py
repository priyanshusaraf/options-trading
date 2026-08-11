"""Sparse editor layout persistence must not change executable graph identity."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts as graph_store
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.ir.experiment import record
from app.ir.hashing import content_address
from app.ir.resolve import resolve
from app.ir.strategies.expanding_z import GRAPH
from app.ir.strategies.expanding_z import LIBRARY
from app.ir.view import Layout, graph_view


IDENTIFIER = GRAPH["identifier"]
VERSION = GRAPH["version"]
LAYOUT_URL = f"/api/ir/graphs/{IDENTIFIER}/versions/{VERSION}/layout"
EDIT_URL = (
    f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/edits"
)


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _position(instance_id: str = "n_ema", x: float = 12.5, y: float = -8.0):
    return {"instance_id": instance_id, "x": x, "y": y}


def test_layout_routes_load_a_graph_owned_by_the_resolved_principal(client, monkeypatch):
    owner_id = "owner.layout"
    identifier = "strategy.layout_owner"
    monkeypatch.setattr(get_settings(), "owner_id", owner_id)
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id=owner_id, name="Layout owner"))
    project = graph_store.create_project("Layout", owner_id=owner_id)
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    graph["version"] = 1
    graph.pop("parent_version", None)
    graph_store.create_artifact(project.project_id, identifier, graph, owner_id=owner_id)
    graph_store.publish_draft(project.project_id, identifier, base_revision=0, owner_id=owner_id)

    response = client.get(f"/api/ir/graphs/{identifier}/versions/1/layout")

    assert response.status_code == 200
    assert response.json()["graph_identifier"] == identifier


def test_missing_layout_is_an_empty_revision_zero_document(client):
    response = client.get(LAYOUT_URL)

    assert response.status_code == 200
    assert response.json() == {
        "graph_identifier": IDENTIFIER,
        "graph_version": VERSION,
        "revision": 0,
        "positions": [],
        "groups": [],
    }


def test_sparse_layout_round_trips_and_revision_advances(client):
    saved = client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position()]},
    )

    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert saved.json()["positions"] == [_position()]
    assert client.get(LAYOUT_URL).json() == saved.json()


def test_missing_layout_carries_as_explicit_revision_one(client):
    edited = client.post(
        EDIT_URL,
        json={
            "base_revision": 0,
            "base_presentation_revision": 0,
            "edits": [{
                "operation": "set_display_name",
                "display_name": "Edited",
            }],
        },
    )

    assert edited.status_code == 201, edited.text
    assert edited.json()["layout"] == {
        "graph_identifier": IDENTIFIER,
            "graph_version": VERSION + 1,
            "revision": 1,
            "positions": [],
            "groups": [],
        }


def test_saved_layout_carries_positions_but_not_its_revision_counter(client):
    client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position("n_ema", 1.0, 2.0)]},
    )
    client.put(
        LAYOUT_URL,
        json={"base_revision": 1, "positions": [_position("n_ema", 3.0, 4.0)]},
    )

    edited = client.post(
        EDIT_URL,
        json={
            "base_revision": 0,
            "base_presentation_revision": 2,
            "edits": [{
                "operation": "set_override",
                "instance_id": "n_ema",
                "parameter": "length",
                "value": 60,
            }],
        },
    )

    assert edited.status_code == 201, edited.text
    layout = edited.json()["layout"]
    assert layout["revision"] == 1
    assert layout["positions"] == [_position("n_ema", 3.0, 4.0)]
    url = f"/api/ir/graphs/{IDENTIFIER}/versions/{VERSION + 1}/layout"
    assert client.get(url).json() == layout
    saved = client.put(
        url,
        json={"base_revision": 1, "positions": [_position("n_ema", 5.0, 6.0)]},
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2


def test_source_layout_never_enters_new_graph_content_address(client):
    payload = {
        "base_revision": 0,
        "base_presentation_revision": 0,
        "edits": [{"operation": "set_display_name", "display_name": "Same edit"}],
    }
    without_layout = client.post(EDIT_URL, json=payload).json()["content_address"]

    init_db(reset=True)
    client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position("n_ema", 44.0, 55.0)]},
    )
    payload["base_presentation_revision"] = 1
    with_layout = client.post(EDIT_URL, json=payload).json()["content_address"]

    assert with_layout == without_layout


def test_a_write_replaces_the_sparse_set_instead_of_merging(client):
    client.put(
        LAYOUT_URL,
        json={
            "base_revision": 0,
            "positions": [_position("n_ema"), _position("n_atr", 3.0, 4.0)],
        },
    )

    response = client.put(
        LAYOUT_URL,
        json={"base_revision": 1, "positions": [_position("n_atr", 9.0, 10.0)]},
    )

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["positions"] == [_position("n_atr", 9.0, 10.0)]


def test_stale_revision_is_409_and_does_not_partially_write(client):
    client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position("n_ema", 1.0, 2.0)]},
    )
    client.put(
        LAYOUT_URL,
        json={"base_revision": 1, "positions": [_position("n_ema", 3.0, 4.0)]},
    )

    stale = client.put(
        LAYOUT_URL,
        json={"base_revision": 1, "positions": [_position("n_atr", 5.0, 6.0)]},
    )

    assert stale.status_code == 409
    assert stale.json() == {
        "detail": "layout revision conflict",
        "current_revision": 2,
    }
    assert client.get(LAYOUT_URL).json()["positions"] == [
        _position("n_ema", 3.0, 4.0)
    ]


def test_failure_after_revision_claim_rolls_back_head_and_positions(client, monkeypatch):
    """The revision update, delete and child inserts are one transaction."""
    from app.editor import layouts

    client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position("n_ema", 1.0, 2.0)]},
    )

    def fail_before_child_insert(_session, _instances):
        raise RuntimeError("injected failure after revision claim and sparse delete")

    monkeypatch.setattr(Session, "add_all", fail_before_child_insert)
    with pytest.raises(RuntimeError, match="injected failure"):
        layouts.save_layout(
            IDENTIFIER,
            VERSION,
            base_revision=1,
            positions=[layouts.Position("n_atr", 5.0, 6.0)],
        )

    persisted = client.get(LAYOUT_URL).json()
    assert persisted["revision"] == 1
    assert persisted["positions"] == [_position("n_ema", 1.0, 2.0)]


def test_layout_never_changes_graph_or_component_identity(client):
    graph_before = copy.deepcopy(client.get(f"/api/ir/graphs/{IDENTIFIER}").json())
    source_hash_before = content_address(GRAPH)
    resolved_before = resolve(GRAPH, LIBRARY)
    experiment_binding_before = record("layout-proof", resolved_before, {}, {}).binding

    saved = client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position("n_ema", 90.0, 45.0)]},
    )

    assert saved.status_code == 200
    assert content_address(GRAPH) == source_hash_before
    assert client.get(f"/api/ir/graphs/{IDENTIFIER}").json() == graph_before
    assert saved.json()["positions"] == [_position("n_ema", 90.0, 45.0)]

    persisted = client.get(LAYOUT_URL).json()
    resolved_after = resolve(GRAPH, LIBRARY)
    rendered = graph_view(resolved_after, Layout({
        position["instance_id"]: (position["x"], position["y"])
        for position in persisted["positions"]
    }))
    assert resolved_after.versions == resolved_before.versions
    assert [node.cache_id for node in resolved_after.nodes] == [
        node.cache_id for node in resolved_before.nodes
    ]
    assert record("layout-proof", resolved_after, {}, {}).binding == experiment_binding_before
    assert next(node for node in rendered.nodes if node.instance_id == "n_ema").placed == (
        90.0,
        45.0,
    )


@pytest.mark.parametrize(
    ("url", "payload", "status"),
    [
        (
            "/api/ir/graphs/strategy.unknown/versions/1/layout",
            {"base_revision": 0, "positions": []},
            404,
        ),
        (
            f"/api/ir/graphs/{IDENTIFIER}/versions/{VERSION + 1}/layout",
            {"base_revision": 0, "positions": []},
            404,
        ),
        (
            LAYOUT_URL,
            {"base_revision": 0, "positions": [_position("n_missing")]},
            422,
        ),
        (
            LAYOUT_URL,
            {"base_revision": 0, "positions": [_position("n_atr/n_smooth")]},
            422,
        ),
        (
            LAYOUT_URL,
            {
                "base_revision": 0,
                "positions": [_position("n_ema"), _position("n_ema", 3.0, 4.0)],
            },
            422,
        ),
        (
            LAYOUT_URL,
            {"base_revision": 0, "positions": [_position("n_ema", "NaN", 0.0)]},
            422,
        ),
        (
            LAYOUT_URL,
            {"base_revision": 0, "positions": [], "graph_hash": "must-not-exist"},
            422,
        ),
    ],
)
def test_invalid_layout_writes_are_rejected(client, url, payload, status):
    assert client.put(url, json=payload).status_code == status


def test_orphaned_positions_are_filtered_and_next_write_cleans_them(client):
    client.put(
        LAYOUT_URL,
        json={"base_revision": 0, "positions": [_position("n_ema")]},
    )
    with SessionLocal() as session:
        session.execute(
            text(
                "INSERT INTO ir_graph_layout_positions "
                "(graph_identifier, graph_version, instance_id, x, y) "
                "VALUES (:identifier, :version, 'removed_node', 1.0, 2.0)"
            ),
            {"identifier": IDENTIFIER, "version": VERSION},
        )
        session.commit()

    assert client.get(LAYOUT_URL).json()["positions"] == [_position("n_ema")]

    client.put(LAYOUT_URL, json={"base_revision": 1, "positions": []})
    with SessionLocal() as session:
        remaining = session.execute(
            text(
                "SELECT instance_id FROM ir_graph_layout_positions "
                "WHERE graph_identifier = :identifier AND graph_version = :version"
            ),
            {"identifier": IDENTIFIER, "version": VERSION},
        ).all()
    assert remaining == []


def test_layout_routes_are_mirrored_under_api_v1(client):
    response = client.get(f"/api/v1{LAYOUT_URL.removeprefix('/api')}")
    assert response.status_code == 200
