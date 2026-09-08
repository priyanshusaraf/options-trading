"""Mechanical v2 resolution cases for immutable, edge-preserving bundles."""

from copy import deepcopy
from types import MappingProxyType

import pytest

from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolutionError, resolve_v2


TYPE_REF = {"type_id": "test.float", "type_version": 1}


def _port(port_id, *, direction, assembly=None, cardinality=None, minimum=None, maximum=None, default_marker=False):
    result = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "test_value",
        "type_ref": deepcopy(TYPE_REF),
        "shape": "scalar",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": cardinality,
            "min": minimum,
            "max": maximum,
            "assembly": assembly,
        }
        if default_marker:
            result["default"] = 0.0
    return result


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
    ordered = _component(
        "ordered",
        [_port("values", direction="input", assembly="ordered", cardinality="bounded_many", minimum=1, maximum=3)],
    )
    keyed = _component(
        "keyed",
        [_port("values", direction="input", assembly="keyed", cardinality="bounded_many", minimum=1, maximum=3)],
    )
    unordered = _component(
        "unordered",
        [_port("values", direction="input", assembly="unordered", cardinality="bounded_many", minimum=1, maximum=3)],
    )
    optional = _component(
        "optional",
        [_port("value", direction="input", assembly="single", cardinality="optional", minimum=0, maximum=1, default_marker=True)],
    )
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types={(TYPE_REF["type_id"], TYPE_REF["type_version"]): {
            "type_id": TYPE_REF["type_id"],
            "type_version": TYPE_REF["type_version"],
            "shapes": ("scalar",),
            "runtime_representation": "float",
        }},
        v2_components={
            (component["component_id"], 1): component
            for component in (source, ordered, keyed, unordered, optional)
        },
    )


def _document(component_id, edges):
    nodes = [{"node_id": "target", "component": {"component_id": component_id, "component_version": 1}, "parameters": {}}]
    source_nodes = sorted({edge["source"].get("node_id") for edge in edges if edge["source"]["scope"] == "node"})
    nodes = [
        {"node_id": node_id, "component": {"component_id": "source", "component_version": 1}, "parameters": {}}
        for node_id in source_nodes
    ] + nodes
    return {
        "format_version": 2,
        "strategy_id": "bundle-cases",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Bundles", "description": None, "tags": []},
        "graph_inputs": [],
        "graph_outputs": [],
        "nodes": nodes,
        "edges": edges,
    }


def _edge(edge_id, source_node, *, target_port="values", binding=None):
    return {
        "edge_id": edge_id,
        "source": {"scope": "node", "node_id": source_node, "port_id": "out"},
        "target": {"scope": "node", "node_id": "target", "port_id": target_port},
        "binding": binding or {"kind": "unordered"},
    }


def test_ordered_bundle_retains_member_order_and_full_provenance(registry):
    document = _document("ordered", [
        _edge("edge-b", "source-b", binding={"kind": "ordered", "position": 1}),
        _edge("edge-a", "source-a", binding={"kind": "ordered", "position": 0}),
    ])

    bundle = resolve_v2(document, registry).bundles[("target", "values")]

    assert bundle.assembly == "ordered"
    assert [member.edge_id for member in bundle.members] == ["edge-a", "edge-b"]
    assert bundle.members[0].source["node_id"] == "source-a"
    assert bundle.members[1].binding["position"] == 1
    assert bundle.members[0].type_ref == TYPE_REF
    assert bundle.members[0].provenance["edge_id"] == "edge-a"
    assert bundle.members[0].provenance["binding"] == {"kind": "ordered", "position": 0}


def test_keyed_and_unordered_bundles_have_canonical_member_order(registry):
    keyed = _document("keyed", [
        _edge("edge-z", "source-z", binding={"kind": "keyed", "key": "z"}),
        _edge("edge-a", "source-a", binding={"kind": "keyed", "key": "a"}),
    ])
    unordered = _document("unordered", [
        _edge("edge-z", "source-z"),
        _edge("edge-a", "source-a"),
    ])

    keyed_bundle = resolve_v2(keyed, registry).bundles[("target", "values")]
    unordered_bundle = resolve_v2(unordered, registry).bundles[("target", "values")]

    assert [member.binding["key"] for member in keyed_bundle.members] == ["a", "z"]
    assert [member.edge_id for member in unordered_bundle.members] == ["edge-a", "edge-z"]


def test_default_bundle_retains_default_and_provenance(registry):
    resolved = resolve_v2(_document("optional", []), registry)
    bundle = resolved.bundles[("target", "value")]

    assert bundle.members == ()
    assert bundle.default == 0.0
    assert bundle.default_provenance == "port_default"


def test_fanout_preserves_each_target_bundle_and_edge_identity(registry):
    document = _document("ordered", [
        _edge("edge-a", "source-a", binding={"kind": "ordered", "position": 0}),
    ])
    document["nodes"].append({"node_id": "target-two", "component": {"component_id": "ordered", "component_version": 1}, "parameters": {}})
    document["edges"].append({
        "edge_id": "edge-b",
        "source": {"scope": "node", "node_id": "source-a", "port_id": "out"},
        "target": {"scope": "node", "node_id": "target-two", "port_id": "values"},
        "binding": {"kind": "ordered", "position": 0},
    })

    resolved = resolve_v2(document, registry)

    assert resolved.bundles[("target", "values")].members[0].edge_id == "edge-a"
    assert resolved.bundles[("target-two", "values")].members[0].edge_id == "edge-b"


def test_resolution_is_deterministic_and_bundles_are_immutable(registry):
    document = _document("unordered", [_edge("edge-b", "source-b"), _edge("edge-a", "source-a")])
    first = resolve_v2(document, registry)
    shuffled = deepcopy(document)
    shuffled["nodes"].reverse()
    shuffled["edges"].reverse()
    second = resolve_v2(shuffled, registry)

    assert first == second
    bundle = first.bundles[("target", "values")]
    assert isinstance(first.bundles, MappingProxyType)
    with pytest.raises(TypeError):
        first.bundles[("target", "values")] = bundle
    with pytest.raises(TypeError):
        bundle.target["port_id"] = "other"


def test_malformed_binding_is_rejected_before_resolution(registry):
    document = _document("ordered", [_edge("edge-a", "source-a", binding={"kind": "ordered", "position": 1})])

    with pytest.raises(ResolutionError) as error:
        resolve_v2(document, registry)

    assert error.value.clause == "V2"
    assert "binding" in str(error.value).lower() or "position" in str(error.value).lower()


@pytest.mark.parametrize(
    ("component_id", "binding"),
    [
        ("ordered", {"kind": "ordered", "position": 0}),
        ("keyed", {"kind": "keyed", "key": "same"}),
        ("unordered", {"kind": "unordered"}),
    ],
)
def test_duplicate_canonical_bundle_members_reject_before_assembly(registry, component_id, binding):
    document = _document(component_id, [
        _edge("edge-a", "source-a", binding=binding),
        _edge("edge-b", "source-a", binding=deepcopy(binding)),
    ])

    with pytest.raises(ResolutionError) as error:
        resolve_v2(document, registry)

    assert error.value.clause == "V2"
    assert "duplicate" in str(error.value).lower()
