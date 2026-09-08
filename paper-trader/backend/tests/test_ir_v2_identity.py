from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from app.ir.formats.v2 import (
    canonical_document,
    content_address_for,
    graph_address_for,
)


def _registry() -> SimpleNamespace:
    value = {
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
    input_port = {
        "port_id": "in",
        "direction": "input",
        "semantic_flow": "value",
        "semantic_role": "input",
        "type_ref": {"type_id": "number", "type_version": 1},
        "shape": "scalar",
        "connections": {
            "cardinality": "optional",
            "min": 0,
            "max": 1,
            "assembly": "single",
        },
    }
    component = {
        "component_id": "constant",
        "component_version": 1,
        "domain_family": "transform",
        "structural_role": "source",
        "ports": [input_port, output],
        "parameters": {},
    }
    return SimpleNamespace(
        v2_types={("number", 1): value},
        v2_components={("constant", 1): component},
    )


def _document() -> dict:
    return {
        "format_version": 2,
        "strategy_id": "identity-fixture",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": "Identity fixture",
            "description": "A complete document for identity metamorphic tests.",
            "tags": ["alpha", "beta"],
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
                "node_id": "a",
                "component": {"component_id": "constant", "component_version": 1},
                "parameters": {},
            },
            {
                "node_id": "b",
                "component": {"component_id": "constant", "component_version": 1},
                "parameters": {},
            },
        ],
        "edges": [
            {
                "edge_id": "wire",
                "source": {"scope": "node", "node_id": "a", "port_id": "out"},
                "target": {"scope": "node", "node_id": "b", "port_id": "in"},
                "binding": {"kind": "single"},
            }
        ],
    }


def _reverse_mapping_order(value):
    if isinstance(value, dict):
        return {
            key: _reverse_mapping_order(value[key])
            for key in reversed(list(value))
        }
    if isinstance(value, list):
        return [_reverse_mapping_order(item) for item in value]
    return value


def test_key_tag_node_and_edge_ordering_preserve_both_addresses():
    registry = _registry()
    original = _document()
    reordered = _reverse_mapping_order(copy.deepcopy(original))
    reordered["metadata"]["tags"] = list(reversed(reordered["metadata"]["tags"]))
    reordered["nodes"] = list(reversed(reordered["nodes"]))
    reordered["edges"] = list(reversed(reordered["edges"]))

    assert content_address_for(original, registry) == content_address_for(reordered, registry)
    assert graph_address_for(original, registry) == graph_address_for(reordered, registry)
    assert canonical_document(original, registry) == canonical_document(reordered, registry)


def test_metadata_only_change_changes_content_but_not_executable_address():
    registry = _registry()
    original = _document()
    changed = copy.deepcopy(original)
    changed["metadata"]["description"] = "A revised descriptive note."

    assert content_address_for(original, registry) != content_address_for(changed, registry)
    assert graph_address_for(original, registry) == graph_address_for(changed, registry)


@pytest.mark.parametrize("field", ["position", "viewport"])
def test_presentation_fields_are_rejected(field):
    document = _document()
    document[field] = {"x": 10, "y": 20}

    with pytest.raises(ValueError, match="V2_UNKNOWN_KEY"):
        content_address_for(document, _registry())


def test_executable_node_mutation_changes_graph_address():
    registry = _registry()
    original = _document()
    changed = copy.deepcopy(original)
    changed["nodes"][0]["parameters"] = {"value": 2}

    assert graph_address_for(original, registry) != graph_address_for(changed, registry)


def test_executable_edge_mutation_changes_graph_address():
    registry = _registry()
    original = _document()
    changed = copy.deepcopy(original)
    changed["edges"][0]["edge_id"] = "wire-renamed"

    assert graph_address_for(original, registry) != graph_address_for(changed, registry)
