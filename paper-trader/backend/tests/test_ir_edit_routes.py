"""Closed edit requests must pass through app.ir.edit and publish atomically."""
from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.ir.strategies.expanding_z import GRAPH


IDENTIFIER = GRAPH["identifier"]
EDIT_URL = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/edits"


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _post(client, base_revision: int, edit: dict | list[dict]):
    edits = edit if isinstance(edit, list) else [edit]
    return client.post(
        EDIT_URL,
        json={"base_revision": base_revision, "edits": edits},
    )


def test_every_edit_primitive_publishes_one_server_version(client):
    edits = [
        {"operation": "rename", "display_name": "Edited graph"},
        {
            "operation": "set_override",
            "instance_id": "n_ema",
            "parameter": "length",
            "value": 51,
        },
        {
            "operation": "clear_override",
            "instance_id": "n_exit_floor",
            "parameter": "factor",
        },
        {
            "operation": "group",
            "identifier": "g_inputs",
            "display_name": "Inputs",
            "members": ["n_ema", "n_atr"],
        },
        {
            "operation": "add_node",
            "instance_id": "n_constant",
            "component_identifier": "value.scalar",
            "component_version": 1,
            "overrides": {"value": 1.0},
        },
        {"operation": "remove_node", "instance_id": "n_constant"},
        {
            "operation": "connect",
            "source": {"instance_id": "n_atr", "socket": "atr"},
            "target": {"instance_id": "n_long_exit", "socket": "reference"},
        },
        {
            "operation": "disconnect",
            "source": {"instance_id": "n_ema", "socket": "out"},
            "target": {"instance_id": "n_long_exit", "socket": "reference"},
        },
    ]

    for offset, edit in enumerate(edits, start=1):
        response = _post(client, offset - 1, edit)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["draft_revision"] == offset
        assert body["version"] == GRAPH["version"] + offset
        assert body["graph"]["version"] == GRAPH["version"] + offset
        assert body["graph"]["parent_version"] == GRAPH["version"] + offset - 1

    first = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/versions/"
        f"{GRAPH['version'] + 1}"
    )
    assert first.status_code == 200
    assert first.json()["graph"]["display_name"] == "Edited graph"


def test_a_required_input_node_can_be_added_and_wired_in_one_version(client):
    response = _post(client, 0, [
        {
            "operation": "add_node",
            "instance_id": "n_ema_slow",
            "component_identifier": "indicator.ema",
            "component_version": 1,
            "overrides": {"length": 200},
        },
        {
            "operation": "connect",
            "source": {"instance_id": "io_in", "socket": "close"},
            "target": {"instance_id": "n_ema_slow", "socket": "source"},
        },
        {
            "operation": "connect",
            "source": {"instance_id": "n_ema_slow", "socket": "out"},
            "target": {"instance_id": "n_long_exit", "socket": "reference"},
        },
        {
            "operation": "disconnect",
            "source": {"instance_id": "n_ema", "socket": "out"},
            "target": {"instance_id": "n_long_exit", "socket": "reference"},
        },
    ])

    assert response.status_code == 201, response.text
    assert response.json()["draft_revision"] == 1
    assert response.json()["version"] == GRAPH["version"] + 1
    assert any(
        node["instance_id"] == "n_ema_slow"
        for node in response.json()["graph"]["nodes"]
    )


@pytest.mark.parametrize(
    ("edit", "clause", "path"),
    [
        (
            {"operation": "remove_node", "instance_id": "n_ghost"},
            "F9",
            "$.nodes.n_ghost",
        ),
        (
            {
                "operation": "add_node",
                "instance_id": "n_missing",
                "component_identifier": "component.does_not_exist",
                "component_version": 1,
            },
            "C5",
            "n_missing",
        ),
        (
            {
                "operation": "connect",
                "source": {"instance_id": "n_min_abs_z", "socket": "out"},
                "target": {"instance_id": "n_long_exit", "socket": "reference"},
            },
            "F7",
            "$.edges[47].structure",
        ),
    ],
)
def test_edit_rejections_return_exact_clause_and_path(client, edit, clause, path):
    response = _post(client, 0, edit)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "edit rejected"
    assert body["violations"][0]["clause"] == clause
    assert body["violations"][0]["path"] == path
    assert body["violations"][0]["message"]


def test_stale_edit_is_409_and_creates_no_second_version(client):
    assert _post(
        client, 0, {"operation": "rename", "display_name": "Winner"}
    ).status_code == 201

    stale = _post(
        client, 0, {"operation": "rename", "display_name": "Stale"}
    )

    assert stale.status_code == 409
    assert stale.json() == {
        "detail": "graph draft revision conflict",
        "current_revision": 1,
    }
    assert client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/versions/"
        f"{GRAPH['version'] + 2}"
    ).status_code == 404


def test_failure_after_version_insert_rolls_back_edit_and_pointer(client, monkeypatch):
    from app.editor import graph_artifacts as store

    def fail_after_insert(*_args):
        raise RuntimeError("injected failure after edited version insert")

    monkeypatch.setattr(store, "_after_version_insert", fail_after_insert)
    with pytest.raises(RuntimeError, match="injected failure"):
        _post(client, 0, {"operation": "rename", "display_name": "Must roll back"})

    draft = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/draft"
    ).json()
    assert draft["revision"] == 0
    assert draft["current_version"] == GRAPH["version"]
    assert draft["graph"]["display_name"] == GRAPH["display_name"]
    assert client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/versions/"
        f"{GRAPH['version'] + 1}"
    ).status_code == 404


def test_rename_route_calls_the_ir_edit_primitive(client, monkeypatch):
    from app.ir import edit as ir_edit

    original = ir_edit.rename
    calls = []

    def recording_rename(graph, display_name):
        calls.append((graph["identifier"], display_name))
        return original(graph, display_name)

    monkeypatch.setattr(ir_edit, "rename", recording_rename)
    response = _post(
        client, 0, {"operation": "rename", "display_name": "Observed"}
    )

    assert response.status_code == 201
    assert calls == [(IDENTIFIER, "Observed")]
    assert response.json()["graph"]["display_name"] == "Observed"


def test_edit_ownership_is_hidden_and_arbitrary_fields_are_rejected(client):
    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()
    hidden = client.post(
        f"/api/ir/projects/{other['project_id']}/graphs/{IDENTIFIER}/edits",
        json={
            "base_revision": 0,
            "edits": [{"operation": "rename", "display_name": "Not mine"}],
        },
    )
    assert hidden.status_code == 404

    for payload in (
        {
            "base_revision": 0,
            "version": 99,
            "edits": [{"operation": "rename", "display_name": "No"}],
        },
        {
            "base_revision": 0,
            "edits": [{"operation": "python", "source": "raise SystemExit"}],
        },
        {
            "base_revision": 0,
            "edits": [{
                "operation": "rename",
                "display_name": "No",
                "graph": GRAPH,
            }],
        },
    ):
        assert client.post(EDIT_URL, json=payload).status_code == 422


def test_edit_request_models_are_closed_and_route_is_mirrored(client):
    from app.main import app

    schema = app.openapi()
    for name in (
        "GraphEditRequest",
        "AddNodeEdit",
        "RemoveNodeEdit",
        "SetOverrideEdit",
        "ClearOverrideEdit",
        "ConnectEdit",
        "DisconnectEdit",
        "GroupEdit",
        "RenameEdit",
        "SocketRef",
    ):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False

    response = client.post(
        f"/api/v1{EDIT_URL.removeprefix('/api')}",
        json={
            "base_revision": 0,
            "edits": [{"operation": "rename", "display_name": "Versioned"}],
        },
    )
    assert response.status_code == 201


def test_route_dispatches_only_to_the_eight_ir_edit_primitives():
    path = pathlib.Path(__file__).resolve().parents[1] / "app/api/ir_edit_routes.py"
    tree = ast.parse(path.read_text())
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ir_edit"
    }
    assert calls == {
        "EditRejected",
        "add_node",
        "remove_node",
        "set_override",
        "clear_override",
        "connect",
        "disconnect",
        "group",
        "rename",
    }
    store_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "store"
    }
    assert store_calls == {"apply_and_publish"}
    assert not {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } & {"eval", "exec", "compile"}
