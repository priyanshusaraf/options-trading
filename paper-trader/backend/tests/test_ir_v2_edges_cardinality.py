"""Mechanical v2 edge, binding, cardinality, and canonical-order cases."""

from copy import deepcopy

import pytest

from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for, validate_document
from app.ir.registry import PlatformRegistry


TYPE_REF = {"type_id": "test.float", "type_version": 1}


def _port(port_id, *, direction, cardinality=None, minimum=None, maximum=None, assembly=None, default_marker=False):
    value = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "test_value",
        "type_ref": deepcopy(TYPE_REF),
        "shape": "scalar",
    }
    if direction == "input":
        value["connections"] = {
            "cardinality": cardinality,
            "min": minimum,
            "max": maximum,
            "assembly": assembly,
        }
        if default_marker:
            value["default"] = 0.0
    return value


def _component(component_id, ports):
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "utility",
        "structural_role": "transform",
        "ports": ports,
        "parameters": {},
    }


@pytest.fixture()
def registry():
    source = _component("source", [_port("out", direction="output")])
    single = _component(
        "single",
        [_port("value", direction="input", cardinality="single", minimum=1, maximum=1, assembly="single")],
    )
    many = _component(
        "many",
        [_port("values", direction="input", cardinality="bounded_many", minimum=1, maximum=2, assembly="ordered")],
    )
    optional = _component(
        "optional",
        [_port("value", direction="input", cardinality="optional", minimum=0, maximum=1, assembly="single", default_marker=True)],
    )
    invalid_default = _component(
        "invalid_default",
        [_port("value", direction="input", cardinality="single", minimum=1, maximum=1, assembly="single", default_marker=True)],
    )
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types={
            (TYPE_REF["type_id"], TYPE_REF["type_version"]): {
                "type_id": TYPE_REF["type_id"],
                "type_version": TYPE_REF["type_version"],
                "shapes": ("scalar",),
                "runtime_representation": "float",
            }
        },
        v2_components={
            (component["component_id"], 1): component
            for component in (source, single, many, optional, invalid_default)
        },
    )


def _document(*, component_id="single", edges=None, metadata=None, nodes=None):
    if nodes is None:
        nodes = [
            {"node_id": "source", "component": {"component_id": "source", "component_version": 1}, "parameters": {}},
            {"node_id": "target", "component": {"component_id": component_id, "component_version": 1}, "parameters": {}},
        ]
    return {
        "format_version": 2,
        "strategy_id": "edge-cases",
        "strategy_version": 1,
        "metadata": metadata or {"metadata_version": 1, "name": "Edges", "description": None, "tags": ["z", "a"]},
        "graph_inputs": [],
        "graph_outputs": [],
        "nodes": nodes,
        "edges": edges or [],
    }


def _edge(edge_id, *, target_port="value", binding=None, source_node="source", target_node="target"):
    return {
        "edge_id": edge_id,
        "source": {"scope": "node", "node_id": source_node, "port_id": "out"},
        "target": {"scope": "node", "node_id": target_node, "port_id": target_port},
        "binding": binding or {"kind": "single"},
    }


def _codes(document, registry):
    return {violation.code for violation in validate_document(document, registry)}


def test_validate_document_reports_ordered_object_violations_for_non_mapping_edges(registry):
    document = _document(edges=[None, "not-an-edge"])

    violations = validate_document(document, registry)

    assert [(violation.code, violation.path) for violation in violations[:2]] == [
        ("V2_OBJECT", "$.edges[0]"),
        ("V2_OBJECT", "$.edges[1]"),
    ]


def test_validate_document_rejects_an_ordinary_node_to_node_cycle(registry):
    cycle_component = _component(
        "cycle",
        [
            _port("value", direction="input", cardinality="single", minimum=1, maximum=1, assembly="single"),
            _port("out", direction="output"),
        ],
    )
    registry = PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types=registry.v2_types,
        v2_components={**registry.v2_components, ("cycle", 1): cycle_component},
    )
    document = _document(
        nodes=[
            {"node_id": "left", "component": {"component_id": "cycle", "component_version": 1}, "parameters": {}},
            {"node_id": "right", "component": {"component_id": "cycle", "component_version": 1}, "parameters": {}},
        ],
        edges=[
            _edge("left-to-right", source_node="left", target_node="right"),
            _edge("right-to-left", source_node="right", target_node="left"),
        ],
    )

    violations = validate_document(document, registry)

    assert [(violation.code, violation.path) for violation in violations] == [
        ("V2_CYCLE", "$.edges"),
    ]


def test_single_cardinality_accepts_one_edge_and_rejects_missing_or_extra(registry):
    one = _document(edges=[_edge("e1")])
    assert _codes(one, registry) == set()

    two = _document(edges=[_edge("e1"), _edge("e2")])
    assert "V2_CARDINALITY" in _codes(two, registry)

    no_edges = _document()
    assert "V2_CARDINALITY" in _codes(no_edges, registry)


def test_bounded_many_requires_contiguous_ordered_bindings(registry):
    valid = _document(
        component_id="many",
        edges=[
            _edge("e1", target_port="values", binding={"kind": "ordered", "position": 0}),
            _edge("e2", target_port="values", binding={"kind": "ordered", "position": 1}),
        ],
    )
    assert _codes(valid, registry) == set()

    duplicate_position = deepcopy(valid)
    duplicate_position["edges"][1]["binding"]["position"] = 0
    assert "V2_BINDING" in _codes(duplicate_position, registry)

    wrong_kind = deepcopy(valid)
    # Keep a position field so the negative case reaches the deterministic
    # binding-kind check even when the target assembly is ordered.
    wrong_kind["edges"][0]["binding"] = {"kind": "single", "position": 0}
    assert "V2_BINDING" in _codes(wrong_kind, registry)


def test_edge_bindings_reject_unknown_fields_and_duplicate_edge_ids(registry):
    unknown = _document(edges=[_edge("e1", binding={"kind": "single", "position": 0})])
    assert "V2_UNKNOWN_KEY" in _codes(unknown, registry)

    duplicate = _document(edges=[_edge("e1"), _edge("e1")])
    assert "V2_DUPLICATE" in _codes(duplicate, registry)


@pytest.mark.parametrize(
    ("component_id", "binding"),
    [
        ("single", {"kind": "single"}),
        ("many", {"kind": "ordered", "position": 0}),
    ],
)
def test_duplicate_canonical_node_tuples_reject_distinct_edge_ids(registry, component_id, binding):
    """An edge id cannot make the same source-target-binding tuple distinct."""
    document = _document(
        component_id=component_id,
        edges=[
            _edge("edge-a", target_port="value" if component_id == "single" else "values", binding=binding),
            _edge("edge-b", target_port="value" if component_id == "single" else "values", binding=deepcopy(binding)),
        ],
    )

    assert "V2_DUPLICATE" in _codes(document, registry)


def test_duplicate_canonical_graph_input_boundary_tuple_rejects_distinct_edge_ids(registry):
    document = _document(
        edges=[
            {
                "edge_id": "edge-a",
                "source": {"scope": "graph_input", "port_id": "in"},
                "target": {"scope": "node", "node_id": "target", "port_id": "value"},
                "binding": {"kind": "single"},
            },
            {
                "edge_id": "edge-b",
                "source": {"scope": "graph_input", "port_id": "in"},
                "target": {"scope": "node", "node_id": "target", "port_id": "value"},
                "binding": {"kind": "single"},
            },
        ],
    )
    document["graph_inputs"] = [_port("in", direction="input")]

    assert "V2_DUPLICATE" in _codes(document, registry)


def test_duplicate_canonical_graph_output_boundary_tuple_rejects_distinct_edge_ids(registry):
    document = _document(
        nodes=[{"node_id": "source", "component": {"component_id": "source", "component_version": 1}, "parameters": {}}],
        edges=[
            {
                "edge_id": "edge-a",
                "source": {"scope": "node", "node_id": "source", "port_id": "out"},
                "target": {"scope": "graph_output", "port_id": "out"},
                "binding": {"kind": "single"},
            },
            {
                "edge_id": "edge-b",
                "source": {"scope": "node", "node_id": "source", "port_id": "out"},
                "target": {"scope": "graph_output", "port_id": "out"},
                "binding": {"kind": "single"},
            },
        ],
    )
    document["graph_outputs"] = [_port("out", direction="output")]

    assert "V2_DUPLICATE" in _codes(document, registry)


def test_optional_input_default_is_allowed_but_required_default_is_rejected(registry):
    optional = _document(component_id="optional")
    optional["edges"] = []
    assert _codes(optional, registry) == set()

    required = _document(component_id="invalid_default", edges=[_edge("e1")])
    assert "V2_DEFAULT" in _codes(required, registry)


def test_edge_endpoints_are_closed_and_must_name_existing_nodes(registry):
    missing_node = _document(edges=[_edge("e1", source_node="does-not-exist")])
    assert "V2_ENDPOINT" in _codes(missing_node, registry)

    graph_output_as_source = _document(edges=[
        {
            "edge_id": "e1",
            "source": {"scope": "graph_output", "port_id": "out"},
            "target": {"scope": "node", "node_id": "target", "port_id": "value"},
            "binding": {"kind": "single"},
        }
    ])
    assert "V2_DIRECTION" in _codes(graph_output_as_source, registry)


def test_canonical_order_normalizes_tags_nodes_and_edges_without_changing_addresses(registry):
    first = _document(
        component_id="many",
        edges=[
            _edge("e2", target_port="values", binding={"kind": "ordered", "position": 1}),
            _edge("e1", target_port="values", binding={"kind": "ordered", "position": 0}),
        ],
    )
    second = deepcopy(first)
    second["metadata"]["tags"] = ["a", "z"]
    second["nodes"].reverse()
    second["edges"].reverse()

    assert _codes(first, registry) == set()
    assert _codes(second, registry) == set()
    assert canonical_document(first, registry) == canonical_document(second, registry)
    assert content_address_for(first, registry) == content_address_for(second, registry)
    assert graph_address_for(first, registry) == graph_address_for(second, registry)


def test_descriptive_metadata_changes_content_address_but_not_graph_address(registry):
    first = _document(edges=[_edge("e1")])
    second = deepcopy(first)
    second["metadata"]["name"] = "Renamed"

    assert _codes(first, registry) == set()
    assert _codes(second, registry) == set()
    assert content_address_for(first, registry) != content_address_for(second, registry)
    assert graph_address_for(first, registry) == graph_address_for(second, registry)
