"""Closed edit requests must pass through app.ir.edit and publish atomically."""
from __future__ import annotations

import ast
import copy
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import IrGraphLayout, IrGraphLayoutPosition
from app.db.session import SessionLocal
from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.ir.strategies.expanding_z import GRAPH


IDENTIFIER = GRAPH["identifier"]
EDIT_URL = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/edits"
EDITOR_URL = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/editor"
PRESENTATION_URL = (
    f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/presentation-edits"
)


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


def _post_presentation(
    client,
    *,
    graph_revision: int,
    presentation_revision: int,
    edits: dict | list[dict],
):
    batch = edits if isinstance(edits, list) else [edits]
    return client.post(PRESENTATION_URL, json={
        "base_revision": graph_revision,
        "base_presentation_revision": presentation_revision,
        "edits": batch,
    })


def _create_group(client, *, members: list[str] | None = None):
    before = client.get(EDITOR_URL).json()
    return _post_presentation(
        client,
        graph_revision=before["draft_revision"],
        presentation_revision=before["layout"]["revision"],
        edits={
            "operation": "create_group",
            "identifier": "g_signal",
            "display_name": "Signal",
            "members": members or [],
            "frame": {"x": 10, "y": 20, "width": 300, "height": 180},
            "collapsed": False,
        },
    )


def test_editor_document_is_one_version_coherent_and_mirrored(client):
    response = client.get(EDITOR_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == CATALOGUE_PROJECT_ID
    assert body["identifier"] == IDENTIFIER
    assert body["display_name"] == GRAPH["display_name"]
    assert body["draft_revision"] == 0
    assert body["version"] == GRAPH["version"]
    assert body["authored_graph"] == GRAPH
    assert body["view"]["version"] == body["version"]
    assert body["layout"]["graph_version"] == body["version"]
    assert body["layout"]["revision"] == 0
    assert body["command_receipt"] is None
    editable = {node["instance_id"]: node for node in body["editable_nodes"]}
    atr_length = next(
        item for item in editable["n_atr"]["parameters"]
        if item["identifier"] == "length"
    )
    assert atr_length == {
        "identifier": "length",
        "kind": "length",
        "default": 14,
        "value": 14,
        "overridden": True,
    }

    mirrored = client.get(f"/api/v1{EDITOR_URL.removeprefix('/api')}")
    assert mirrored.status_code == 200
    assert mirrored.json() == body


def test_visual_group_edit_advances_only_the_presentation_revision(client):
    before = client.get(EDITOR_URL).json()

    response = _create_group(client, members=["n_ema"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["version"] == before["version"]
    assert body["draft_revision"] == before["draft_revision"]
    assert body["content_address"] == before["content_address"]
    assert body["layout"]["revision"] == before["layout"]["revision"] + 1
    assert body["layout"]["groups"] == [{
        "identifier": "g_signal",
        "display_name": "Signal",
        "frame": {"x": 10.0, "y": 20.0, "width": 300.0, "height": 180.0},
        "collapsed": False,
        "members": ["n_ema"],
    }]
    receipt = body["command_receipt"]
    assert receipt["semantic_forward_operations"] == []
    assert receipt["semantic_inverse_operations"] == []
    assert receipt["presentation_delta"]["forward_operations"] == [{
        "operation": "create_group",
        "identifier": "g_signal",
        "display_name": "Signal",
        "members": ["n_ema"],
        "frame": {"x": 10.0, "y": 20.0, "width": 300.0, "height": 180.0},
        "collapsed": False,
    }]
    assert receipt["presentation_delta"]["inverse_operations"] == [{
        "operation": "remove_group", "identifier": "g_signal"
    }]


@pytest.mark.parametrize("instance_id", ["n_unknown", "n_atr/n_smooth"])
def test_visual_group_members_reject_unknown_and_derived_nodes(client, instance_id):
    response = _create_group(client, members=[instance_id])

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "PRESENTATION_VALIDATION_FAILED"
    assert body["errors"][0]["operation_index"] == 0
    assert body["errors"][0]["path"][-1] == "members"


def test_visual_group_edits_use_the_shared_presentation_revision(client):
    accepted = _create_group(client)
    assert accepted.status_code == 201, accepted.text

    stale = _post_presentation(
        client,
        graph_revision=0,
        presentation_revision=0,
        edits={
            "operation": "rename_group",
            "identifier": "g_signal",
            "display_name": "Stale",
        },
    )

    assert stale.status_code == 409
    assert stale.json() == {
        "code": "PRESENTATION_REVISION_CONFLICT",
        "message": "Presentation revision conflict",
        "current_revision": None,
        "current_presentation_revision": 1,
        "errors": [],
    }


def test_clear_override_returns_inherited_parameter_metadata(client):
    response = _post(client, 0, {
        "operation": "clear_override",
        "instance_id": "n_atr",
        "parameter": "length",
    })

    assert response.status_code == 201, response.text
    editable = {
        node["instance_id"]: node for node in response.json()["editable_nodes"]
    }
    length = next(
        item for item in editable["n_atr"]["parameters"]
        if item["identifier"] == "length"
    )
    assert length["value"] == 14
    assert length["default"] == 14
    assert length["overridden"] is False


def test_unpublished_and_archived_editor_states_are_explicit(client):
    project = client.post(
        "/api/ir/projects", json={"name": "Draft project", "description": ""}
    ).json()
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = "strategy.unpublished"
    graph.pop("parent_version", None)
    created = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": graph["identifier"], "graph": graph},
    )
    assert created.status_code == 201, created.text
    unpublished = client.get(
        f"/api/ir/projects/{project['project_id']}/graphs/{graph['identifier']}/editor"
    )
    assert unpublished.status_code == 409
    assert unpublished.json()["code"] == "EDITOR_NOT_PUBLISHED"

    archived = client.put(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/status",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    unavailable = client.get(EDITOR_URL)
    assert unavailable.status_code == 409
    assert unavailable.json()["code"] == "EDITOR_ARCHIVED"


def test_display_name_changes_content_but_not_stable_identity(client):
    before = client.get(EDITOR_URL).json()

    response = _post(
        client, 0, {"operation": "set_display_name", "display_name": "New label"}
    )

    assert response.status_code == 201
    after = response.json()
    assert after["identifier"] == before["identifier"]
    assert after["authored_graph"]["identifier"] == before["authored_graph"]["identifier"]
    assert after["display_name"] == "New label"
    assert after["content_address"] != before["content_address"]


@pytest.mark.parametrize(
    ("value", "clause"),
    [("wrong", "C11"), (True, "C11"), (None, "C11"), ({"bad": "shape"}, "F10")],
)
def test_wrong_parameter_type_is_normalized(client, value, clause):
    response = _post(client, 0, {
        "operation": "set_override",
        "instance_id": "n_ema",
        "parameter": "length",
        "value": value,
    })

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "IR_VALIDATION_FAILED"
    assert body["errors"][0]["clause"] == clause


def test_backend_returns_canonical_forward_and_inverse_receipt(client):
    exit_floor = next(
        node for node in GRAPH["nodes"] if node["instance_id"] == "n_exit_floor"
    )
    response = _post(client, 0, [
        {"operation": "set_display_name", "display_name": "Edited"},
        {
            "operation": "set_override",
            "instance_id": "n_ema",
            "parameter": "length",
            "value": 60,
        },
        {
            "operation": "set_override",
            "instance_id": "n_ema",
            "parameter": "new_parameter",
            "value": 1,
        },
    ])

    # The unknown parameter proves the whole batch is rejected before a receipt.
    assert response.status_code == 422
    assert response.json()["code"] == "IR_VALIDATION_FAILED"

    accepted = _post(client, 0, [
        {"operation": "set_display_name", "display_name": "Edited"},
        {
            "operation": "set_override",
            "instance_id": "n_ema",
            "parameter": "length",
            "value": 60,
        },
        {
            "operation": "clear_override",
            "instance_id": "n_exit_floor",
            "parameter": "factor",
        },
    ])
    assert accepted.status_code == 201, accepted.text
    body = accepted.json()
    receipt = body["command_receipt"]
    assert receipt["base_revision"] == 0
    assert receipt["draft_revision"] == 1
    assert receipt["version"] == body["version"]
    assert receipt["content_address"] == body["content_address"]
    assert receipt["applied_operations"][0] == {
        "operation": "set_display_name",
        "display_name": "Edited",
    }
    assert receipt["inverse_operations"] == [
        {
            "operation": "set_override",
            "instance_id": "n_exit_floor",
            "parameter": "factor",
            "value": exit_floor["overrides"]["factor"],
        },
        {
            "operation": "set_override",
            "instance_id": "n_ema",
            "parameter": "length",
            "value": {"param_ref": "ema_length"},
        },
        {
            "operation": "set_display_name",
            "display_name": GRAPH["display_name"],
        },
    ]


def test_response_construction_failure_rolls_back_publication(client, monkeypatch):
    from app.api import ir_routes

    def fail_response(*_args):
        raise RuntimeError("injected editor response failure")

    monkeypatch.setattr(ir_routes, "graph_response", fail_response, raising=False)
    response = _post(
        client, 0, {"operation": "set_display_name", "display_name": "Must roll back"}
    )

    assert response.status_code == 500
    assert response.json()["code"] == "EDITOR_DOCUMENT_FAILED"
    draft = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/draft"
    ).json()
    assert draft["revision"] == 0
    assert draft["current_version"] == GRAPH["version"]
    assert client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/versions/"
        f"{GRAPH['version'] + 1}"
    ).status_code == 404


def test_every_s3_2a_edit_primitive_publishes_one_server_version(client):
    edits = [
        {"operation": "set_display_name", "display_name": "Edited graph"},
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
    ]

    for offset, edit in enumerate(edits, start=1):
        response = _post(client, offset - 1, edit)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["draft_revision"] == offset
        assert body["version"] == GRAPH["version"] + offset
        assert body["authored_graph"]["version"] == GRAPH["version"] + offset
        assert body["authored_graph"]["parent_version"] == GRAPH["version"] + offset - 1
        assert body["view"]["version"] == body["version"]
        assert body["layout"]["graph_version"] == body["version"]
        assert body["command_receipt"]["draft_revision"] == offset

    first = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/versions/"
        f"{GRAPH['version'] + 1}"
    )
    assert first.status_code == 200
    assert first.json()["graph"]["display_name"] == "Edited graph"


@pytest.mark.parametrize(
    "operation",
    ["rename", "add_node", "remove_node", "connect", "disconnect", "group", "python"],
)
def test_structural_and_unknown_operations_are_closed(operation, client):
    response = _post(client, 0, {"operation": operation})

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


@pytest.mark.parametrize(
    ("edit", "operation_index", "clause", "path"),
    [
        (
            {
                "operation": "set_override",
                "instance_id": "n_ghost",
                "parameter": "length",
                "value": 10,
            },
            0,
            "F9",
            ["nodes", "n_ghost"],
        ),
        (
            {
                "operation": "set_override",
                "instance_id": "n_ema",
                "parameter": "does_not_exist",
                "value": 10,
            },
            None,
            "C3",
            ["n_ema", "overrides", "does_not_exist"],
        ),
        (
            {
                "operation": "set_override",
                "instance_id": "n_atr/n_smooth",
                "parameter": "length",
                "value": 10,
            },
            0,
            "F9",
            ["nodes", "n_atr/n_smooth"],
        ),
    ],
)
def test_edit_rejections_return_exact_clause_and_path(
    client, edit, operation_index, clause, path
):
    response = _post(client, 0, edit)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "IR_VALIDATION_FAILED"
    assert body["current_revision"] is None
    assert body["errors"][0]["operation_index"] == operation_index
    assert body["errors"][0]["clause"] == clause
    assert body["errors"][0]["path"] == path
    assert body["errors"][0]["message"]


def test_stale_edit_is_409_and_creates_no_second_version(client):
    assert _post(
        client, 0, {"operation": "set_display_name", "display_name": "Winner"}
    ).status_code == 201

    stale = _post(
        client, 0, {"operation": "set_display_name", "display_name": "Stale"}
    )

    assert stale.status_code == 409
    assert stale.json() == {
        "code": "DRAFT_REVISION_CONFLICT",
        "message": "Graph draft revision conflict",
        "current_revision": 1,
        "current_presentation_revision": None,
        "errors": [],
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
        _post(client, 0, {"operation": "set_display_name", "display_name": "Must roll back"})

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


def test_failure_after_layout_prepare_rolls_back_graph_and_layout(client, monkeypatch):
    from app.editor import layouts

    def fail_after_layout(*_args):
        raise RuntimeError("injected failure after carried layout preparation")

    monkeypatch.setattr(layouts, "_after_layout_prepare", fail_after_layout)
    with pytest.raises(RuntimeError, match="carried layout preparation"):
        _post(
            client,
            0,
            {"operation": "set_display_name", "display_name": "Must roll back"},
        )

    draft = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/draft"
    ).json()
    assert draft["revision"] == 0
    assert draft["current_version"] == GRAPH["version"]
    with SessionLocal() as session:
        assert session.get(
            IrGraphLayout, (IDENTIFIER, GRAPH["version"] + 1)
        ) is None
        positions = tuple(session.scalars(select(IrGraphLayoutPosition).where(
            IrGraphLayoutPosition.graph_identifier == IDENTIFIER,
            IrGraphLayoutPosition.graph_version == GRAPH["version"] + 1,
        )))
    assert positions == ()


def test_rename_route_publishes_the_batch_result(client):
    response = _post(
        client, 0, {"operation": "set_display_name", "display_name": "Observed"}
    )

    assert response.status_code == 201
    assert response.json()["authored_graph"]["display_name"] == "Observed"


def test_edit_ownership_is_hidden_and_arbitrary_fields_are_rejected(client):
    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()
    hidden = client.post(
        f"/api/ir/projects/{other['project_id']}/graphs/{IDENTIFIER}/edits",
        json={
            "base_revision": 0,
            "edits": [{"operation": "set_display_name", "display_name": "Not mine"}],
        },
    )
    assert hidden.status_code == 404

    for payload in (
        {
            "base_revision": 0,
            "version": 99,
            "edits": [{"operation": "set_display_name", "display_name": "No"}],
        },
        {
            "base_revision": 0,
            "edits": [{"operation": "python", "source": "raise SystemExit"}],
        },
        {
            "base_revision": 0,
            "edits": [{
                "operation": "set_display_name",
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
        "SetOverrideEdit",
        "ClearOverrideEdit",
        "SetDisplayNameEdit",
    ):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False

    response = client.post(
        f"/api/v1{EDIT_URL.removeprefix('/api')}",
        json={
            "base_revision": 0,
            "edits": [{"operation": "set_display_name", "display_name": "Versioned"}],
        },
    )
    assert response.status_code == 201


def test_edit_batch_bounds_are_closed(client):
    empty = client.post(EDIT_URL, json={"base_revision": 0, "edits": []})
    assert empty.status_code == 422
    assert empty.json()["code"] == "REQUEST_VALIDATION_FAILED"

    edits = [
        {"operation": "set_display_name", "display_name": f"Name {index}"}
        for index in range(32)
    ]
    assert client.post(
        EDIT_URL, json={"base_revision": 0, "edits": edits}
    ).status_code == 201

    init_db(reset=True)
    too_many = client.post(
        EDIT_URL,
        json={"base_revision": 0, "edits": edits + [edits[-1]]},
    )
    assert too_many.status_code == 422
    assert too_many.json()["code"] == "REQUEST_VALIDATION_FAILED"


@pytest.mark.parametrize(
    "value",
    [
        "x" * 4097,
        {str(index): index for index in range(257)},
    ],
)
def test_noncanonical_or_unbounded_override_values_are_rejected(client, value):
    response = _post(client, 0, {
        "operation": "set_override",
        "instance_id": "n_ema",
        "parameter": "length",
        "value": value,
    })

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_numbers_are_rejected(client, literal):
    response = client.post(
        EDIT_URL,
        content=(
            '{"base_revision":0,"edits":[{"operation":"set_override",'
            '"instance_id":"n_ema","parameter":"length","value":'
            f"{literal}" + "}]}"
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_override_value_depth_is_bounded(client):
    value: object = 1
    for _ in range(9):
        value = [value]

    response = _post(client, 0, {
        "operation": "set_override",
        "instance_id": "n_ema",
        "parameter": "length",
        "value": value,
    })

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_route_dispatches_semantic_changes_only_through_the_ir_batch_boundary():
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
    assert "apply_batch" in calls
    assert not calls & {"set_override", "clear_override", "rename", "add_node",
                        "remove_node", "connect", "disconnect", "group"}
    store_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "store"
    }
    assert store_calls == {
        "EditResult",
        "apply_and_publish",
        "apply_presentation",
        "load_editor_snapshot",
    }
    assert not {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } & {"eval", "exec", "compile"}
