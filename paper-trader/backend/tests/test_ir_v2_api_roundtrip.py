"""Focused HTTP evidence for the opt-in Component IR v2 document contract."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from types import SimpleNamespace

import pytest

from app.editor import graph_artifacts
from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for


def _registry() -> SimpleNamespace:
    number = {
        "type_id": "number",
        "type_version": 1,
        "shapes": ["scalar"],
        "runtime_representation": "float",
    }
    output = {
        "port_id": "out",
        "direction": "output",
        "semantic_flow": "value",
        "semantic_role": "result",
        "type_ref": {"type_id": "number", "type_version": 1},
        "shape": "scalar",
    }
    source = {
        "component_id": "constant",
        "component_version": 1,
        "domain_family": "transform",
        "structural_role": "source",
        "ports": [output],
        "parameters": {},
    }
    return SimpleNamespace(
        v2_types={("number", 1): number},
        v2_components={("constant", 1): source},
    )


def _document() -> dict[str, object]:
    return {
        "format_version": 2,
        "strategy_id": "api-roundtrip",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": "API roundtrip",
            "description": "Canonical HTTP fixture",
            "tags": ["beta", "alpha"],
        },
        "graph_inputs": [],
        "graph_outputs": [
            {
                "port_id": "result",
                "direction": "output",
                "semantic_flow": "value",
                "semantic_role": "result",
                "type_ref": {"type_id": "number", "type_version": 1},
                "shape": "scalar",
            }
        ],
        "nodes": [
            {
                "node_id": "source",
                "component": {"component_id": "constant", "component_version": 1},
                "parameters": {},
            }
        ],
        "edges": [
            {
                "edge_id": "result-wire",
                "source": {"scope": "node", "node_id": "source", "port_id": "out"},
                "target": {"scope": "graph_output", "port_id": "result"},
                "binding": {"kind": "single"},
            }
        ],
    }


@pytest.fixture(autouse=True)
def _db_and_v2_registry(monkeypatch):
    from app.db.session import init_db
    import app.ir.library as library

    init_db(reset=True)
    registry = _registry()
    monkeypatch.setattr(library, "REGISTRY", registry)
    monkeypatch.setattr(graph_artifacts, "REGISTRY", registry)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _project(client) -> str:
    response = client.post(
        "/api/ir/projects",
        json={"name": f"API-{uuid.uuid4().hex}", "description": ""},
    )
    assert response.status_code == 201
    return response.json()["project_id"]


def _create(client, document=None, *, identifier="api-roundtrip"):
    project_id = _project(client)
    document = copy.deepcopy(document or _document())
    document["strategy_id"] = identifier
    response = client.post(
        f"/api/ir/projects/{project_id}/documents/{identifier}",
        json={"format_version": 2, "document": document},
    )
    return project_id, response


def test_v2_complete_document_create_read_roundtrip_preserves_addresses(client):
    project_id, created = _create(client)
    assert created.status_code == 201
    body = created.json()
    expected = canonical_document(_document(), _registry())
    assert body["format_version"] == 2
    assert body["document"] == expected
    assert body["content_address"] == content_address_for(expected, _registry())
    assert body["graph_address"] == graph_address_for(expected, _registry())

    read = client.get(
        f"/api/ir/projects/{project_id}/documents/api-roundtrip/1",
        params={"format_version": "2"},
    )
    assert read.status_code == 200
    assert read.json() == body


def test_v2_object_key_and_tag_node_edge_reordering_has_same_identity(client):
    original = _document()
    reordered = copy.deepcopy(original)
    reordered["metadata"]["tags"] = ["alpha", "beta"]
    reordered["nodes"] = list(reversed(reordered["nodes"]))
    reordered["edges"] = list(reversed(reordered["edges"]))
    reordered = {key: reordered[key] for key in reversed(list(reordered))}
    assert content_address_for(original, _registry()) == content_address_for(reordered, _registry())
    assert graph_address_for(original, _registry()) == graph_address_for(reordered, _registry())
    _, second = _create(client, reordered)
    assert second.status_code == 201
    assert second.json()["content_address"] == content_address_for(reordered | {"strategy_id": "api-roundtrip"}, _registry())
    assert second.json()["graph_address"] == graph_address_for(reordered | {"strategy_id": "api-roundtrip"}, _registry())


def test_v2_metadata_change_is_content_only_and_graph_change_is_executable(client):
    _, original = _create(client, identifier="original")
    metadata = copy.deepcopy(_document())
    metadata["metadata"]["description"] = "changed"
    _, changed_metadata = _create(client, metadata, identifier="metadata")
    assert changed_metadata.status_code == 201
    assert changed_metadata.json()["content_address"] != original.json()["content_address"]
    assert changed_metadata.json()["graph_address"] == original.json()["graph_address"]

    executable = copy.deepcopy(_document())
    executable["edges"][0]["edge_id"] = "changed-wire"
    _, changed_graph = _create(client, executable, identifier="executable")
    assert changed_graph.status_code == 201
    assert changed_graph.json()["graph_address"] != original.json()["graph_address"]


def test_v2_closed_metadata_rejects_unknown_field_without_persistence(client):
    project_id = _project(client)
    document = _document()
    document["strategy_id"] = "rejected"
    document["metadata"]["unexpected"] = True
    response = client.post(
        f"/api/ir/projects/{project_id}/documents/rejected",
        json={"format_version": 2, "document": document},
    )
    assert response.status_code == 422
    assert "V2_UNKNOWN_KEY" in response.json()["detail"]
    assert client.get(
        f"/api/ir/projects/{project_id}/documents/rejected/1",
        params={"format_version": "2"},
    ).status_code == 404


def test_v2_canonical_byte_vector_is_stable():
    canonical = canonical_document(_document(), _registry())
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == "01789c44f486fca9dc95624a08bff554607459c83c87b5904c456906a79e4ca2"


@pytest.mark.parametrize("version", [None, True, 1.0, "2", 3])
def test_missing_boolean_float_string_and_unsupported_versions_refuse_atomically(client, version):
    project_id = _project(client)
    payload = {"document": _document()}
    if version is not None:
        payload["format_version"] = version
    response = client.post(
        f"/api/ir/projects/{project_id}/documents/bad-version",
        json=payload,
    )
    assert response.status_code == 422
    assert client.get(
        f"/api/ir/projects/{project_id}/documents/bad-version/1",
        params={"format_version": "2"},
    ).status_code == 404


def test_v2_request_discriminator_mismatch_refuses_atomically(client):
    project_id = _project(client)
    document = _document()
    response = client.post(
        f"/api/ir/projects/{project_id}/documents/mismatch",
        json={"format_version": 2, "document": {**document, "format_version": 1}},
    )
    assert response.status_code == 422
    assert client.get(
        f"/api/ir/projects/{project_id}/documents/mismatch/1",
        params={"format_version": "2"},
    ).status_code == 404
