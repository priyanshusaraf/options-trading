"""S3.3 proves closed editor output equals hand-authored executable IR."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.db.session import engine, init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.ir.hashing import canonical_json, content_address
from app.ir.strategies.expanding_z import GRAPH


IDENTIFIER = GRAPH["identifier"]
ROOT = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}"


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _hand_authored_reference() -> dict:
    reference = copy.deepcopy(GRAPH)
    reference["version"] = GRAPH["version"] + 1
    reference["parent_version"] = GRAPH["version"]
    reference["nodes"] = [
        node for node in reference["nodes"]
        if node["instance_id"] != "n_exit_fallback"
    ]
    reference["nodes"].append({
        "instance_id": "n_spare",
        "component": {"identifier": "value.scalar", "version": 1},
        "overrides": {"value": 3.0},
    })
    reference["edges"] = [
        edge for edge in reference["edges"]
        if "n_exit_fallback" not in {
            edge["source"]["instance"], edge["target"]["instance"]
        }
    ]
    reference["edges"].append({
        "source": {"instance": "n_exit_floor", "socket": "out"},
        "target": {"instance": "n_exit_thr", "socket": "fallback"},
    })
    return reference


def _structural_operations() -> list[dict]:
    return [
        {
            "operation": "add_node",
            "instance_id": "n_spare",
            "identifier": "value.scalar",
            "version": 1,
            "overrides": {"value": 3.0},
            "domain": None,
            "secret_params": [],
        },
        {
            "operation": "connect",
            "source": {"instance_id": "n_exit_floor", "socket": "out"},
            "target": {"instance_id": "n_exit_thr", "socket": "fallback"},
        },
        {
            "operation": "disconnect",
            "source": {"instance_id": "n_exit_fallback", "socket": "out"},
            "target": {"instance_id": "n_exit_thr", "socket": "fallback"},
        },
        {"operation": "remove_node", "instance_id": "n_exit_fallback"},
    ]


def _prepare_presentation(client: TestClient) -> dict:
    before = client.get(f"{ROOT}/editor").json()
    positioned = client.put(
        f"/api/ir/graphs/{IDENTIFIER}/versions/{before['version']}/layout",
        json={
            "base_revision": 0,
            "positions": [{
                "instance_id": "n_exit_fallback", "x": 40, "y": 80,
            }],
        },
    )
    assert positioned.status_code == 200
    grouped = client.post(f"{ROOT}/presentation-edits", json={
        "base_revision": 0,
        "base_presentation_revision": 1,
        "edits": [{
            "operation": "create_group",
            "identifier": "g_exit",
            "display_name": "Exit",
            "members": ["n_exit_fallback", "n_exit_floor"],
            "frame": {"x": 20, "y": 30, "width": 500, "height": 300},
            "collapsed": False,
        }],
    })
    assert grouped.status_code == 201, grouped.text
    return grouped.json()


def test_closed_history_matches_hand_authored_identity_and_reloads_losslessly(client):
    before = _prepare_presentation(client)
    payload = {
        "base_revision": before["draft_revision"],
        "base_presentation_revision": before["layout"]["revision"],
        "edits": _structural_operations(),
        "presentation_edits": [],
    }
    assert set(payload) == {
        "base_revision", "base_presentation_revision", "edits",
        "presentation_edits",
    }

    response = client.post(f"{ROOT}/edits", json=payload)

    assert response.status_code == 201, response.text
    accepted = response.json()
    expected = _hand_authored_reference()
    assert canonical_json(accepted["authored_graph"]) == canonical_json(expected)
    assert accepted["content_address"] == content_address(expected)
    assert accepted["layout"]["positions"] == []
    assert accepted["layout"]["groups"][0]["members"] == ["n_exit_floor"]

    engine.dispose()
    reloaded = client.get(f"{ROOT}/editor")
    assert reloaded.status_code == 200, reloaded.text
    reloaded_body = reloaded.json()
    assert {**reloaded_body, "command_receipt": accepted["command_receipt"]} == accepted

    receipt = accepted["command_receipt"]
    undone = client.post(f"{ROOT}/edits", json={
        "base_revision": reloaded_body["draft_revision"],
        "base_presentation_revision": reloaded_body["layout"]["revision"],
        "edits": receipt["semantic_inverse_operations"],
        "presentation_edits": receipt["presentation_delta"]["inverse_operations"],
    })
    assert undone.status_code == 201, undone.text
    restored = undone.json()
    assert "n_exit_fallback" in {
        node["instance_id"] for node in restored["authored_graph"]["nodes"]
    }
    assert restored["layout"]["positions"] == [{
        "instance_id": "n_exit_fallback", "x": 40.0, "y": 80.0,
    }]
    assert restored["layout"]["groups"][0]["members"] == [
        "n_exit_fallback", "n_exit_floor",
    ]
