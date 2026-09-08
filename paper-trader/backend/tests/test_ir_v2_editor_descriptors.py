"""Backend editor/product-object descriptor compatibility contracts."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest
from fastapi.testclient import TestClient

from app.editor import descriptors
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.ir.library import LIBRARY
from app.ir.strategies.expanding_z import GRAPH


@pytest.fixture(autouse=True)
def _db():
    from app.db.session import init_db

    init_db(reset=True)


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_v1_editor_descriptors_remain_the_default_and_are_compatible(client):
    response = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{GRAPH['identifier']}/editor"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authored_graph"]["format_version"] == 1
    assert "graph_address" not in body

    catalogue = {
        (item["identifier"], item["version"]): item
        for item in body["component_catalogue"]
    }
    absolute = catalogue[("math.abs", 1)]
    assert [(item["identifier"], item["direction"], item["wire_type"]["value"])
            for item in absolute["sockets"]] == [
                ("in", "input", "float"), ("out", "output", "float")
            ]
    assert absolute["sockets"][0]["has_default_source"] is False

    boundaries = {
        (item["instance_id"], item["identifier"]): item
        for item in body["graph_sockets"]
    }
    assert boundaries[("io_in", "close")]["direction"] == "output"
    assert boundaries[("io_out", "longEntry")]["direction"] == "input"

    # V2 remains an additive backend capability; it is not silently included in
    # the accepted v1 editor catalogue or made the editor's default.
    assert all(item["identifier"] in {key[0] for key in LIBRARY.components}
               for item in body["component_catalogue"])


def test_v1_product_object_contract_keeps_discriminator_and_response_shape(client):
    project = client.post("/api/ir/projects", json={"name": "Descriptor cases"})
    assert project.status_code == 201, project.text
    project_id = project.json()["project_id"]

    document = copy.deepcopy(GRAPH)
    identifier = "strategy.descriptor_v1"
    document["identifier"] = identifier
    response = client.post(
        f"/api/ir/projects/{project_id}/documents/{identifier}",
        json={"format_version": 1, "document": document},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["format_version"] == 1
    assert body["document"]["format_version"] == 1
    assert body["document"]["identifier"] == identifier
    assert isinstance(body["content_address"], str)
    assert "graph_address" not in body


def test_descriptor_mapping_conversion_is_detached_from_immutable_registry_values():
    wire_type = MappingProxyType({
        "value": "float",
        "structure": "series",
        "domain": MappingProxyType({"instrument": "NIFTY"}),
    })
    interface = (MappingProxyType({
        "item": "socket",
        "identifier": "close",
        "direction": "input",
        "wire_type": wire_type,
    }),)

    result = descriptors.sockets(interface)
    assert result[0].wire_type == {
        "value": "float",
        "structure": "series",
        "domain": {"instrument": "NIFTY"},
    }
    result[0].wire_type["domain"]["instrument"] = "BANKNIFTY"
    assert wire_type["domain"]["instrument"] == "NIFTY"

    with pytest.raises(FrozenInstanceError):
        result[0].identifier = "changed"


def test_v2_descriptor_catalogue_is_not_mixed_into_v1_library_surface():
    catalogue = descriptors.component_catalogue(LIBRARY)

    assert catalogue
    assert {(item.identifier, item.version) for item in catalogue} == set(
        LIBRARY.components
    )
    # The v2 registry declarations are a distinct backend IR contract and do
    # not acquire v1 socket descriptors merely by being present in the registry.
    assert not any(item.identifier.startswith("v2.") for item in catalogue)
