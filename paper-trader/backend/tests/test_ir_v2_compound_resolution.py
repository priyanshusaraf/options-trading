"""Mechanical v2 compound-resolution contract cases.

These cases intentionally exercise the frozen resolver boundary.  They keep
compound port equality, exact parameter state propagation, recursive closure,
provenance, and literal immutability observable without adding production
fallbacks when the interface is incomplete.
"""
from __future__ import annotations

from copy import deepcopy
import pytest

from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.registry import PlatformRegistry


TYPE_REF = {"type_id": "test.float", "type_version": 1}


def _type() -> dict[str, object]:
    return {
        "type_id": "test.float",
        "type_version": 1,
        "shapes": ["scalar"],
        "runtime_representation": "float",
    }


def _parameter(*, default: object = None, required: bool = True) -> dict[str, object]:
    return {
        "type": "float",
        "required": required,
        "default": default,
        "enum": None,
        "domain": None,
        "units": "value",
        "serialization": "canonical-float",
    }


def _port(port_id: str, direction: str, *, default: object = ...):
    value: dict[str, object] = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "value",
        "type_ref": deepcopy(TYPE_REF),
        "shape": "scalar",
    }
    if direction == "input":
        value["connections"] = {
            "cardinality": "optional" if default is not ... else "single",
            "min": 0 if default is not ... else 1,
            "max": 1,
            "assembly": "single",
        }
        if default is not ...:
            value["default"] = default
    return value


def _leaf(component_id: str, *, parameters: dict[str, object] | None = None):
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "utility",
        "structural_role": "transform",
        "ports": [_port("in", "input"), _port("out", "output")],
        "parameters": parameters or {},
    }


def _compound(
    *,
    component_id: str = "compound.bundle",
    body_nodes: list[dict[str, object]] | None = None,
    public_ports: list[dict[str, object]] | None = None,
    public_parameters: dict[str, object] | None = None,
    bindings: list[dict[str, object]] | None = None,
    body_ports: dict[str, list[dict[str, object]]] | None = None,
):
    body_nodes = body_nodes or []
    body = {
        "graph_inputs": [deepcopy((public_ports or [_port("in", "input", default=0.0)])[0])],
        "graph_outputs": [deepcopy((public_ports or [_port("in", "input", default=0.0), _port("out", "output")])[-1])],
        "nodes": body_nodes,
        "edges": [],
    }
    if body_ports:
        body.update(body_ports)
    elif body_nodes:
        for index, node in enumerate(body_nodes):
            previous = "graph_input" if index == 0 else body_nodes[index - 1]["node_id"]
            body["edges"].append({
                "edge_id": f"body-{index}-input",
                "source": {"scope": "graph_input", "port_id": "in"} if previous == "graph_input" else {"scope": "node", "node_id": previous, "port_id": "out"},
                "target": {"scope": "node", "node_id": node["node_id"], "port_id": "in"},
                "binding": {"kind": "single"},
            })
        body["edges"].append({
            "edge_id": "body-output",
            "source": {"scope": "node", "node_id": body_nodes[-1]["node_id"], "port_id": "out"},
            "target": {"scope": "graph_output", "port_id": "out"},
            "binding": {"kind": "single"},
        })
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "utility",
        "structural_role": "transform",
        "ports": public_ports or [_port("in", "input", default=0.0), _port("out", "output")],
        "parameters": public_parameters or {},
        "compound": {"body": body, "parameter_bindings": bindings or []},
    }


def _registry(components: dict[tuple[str, int], dict[str, object]]):
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types={(TYPE_REF["type_id"], TYPE_REF["type_version"]): _type()},
        v2_components=components,
    )


def _document(component_id: str = "compound.bundle", *, parameters=None):
    return {
        "format_version": 2,
        "strategy_id": "compound-cases",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Compound", "description": None, "tags": []},
        "graph_inputs": [],
        "graph_outputs": [],
        "nodes": [{
            "node_id": "bundle",
            "component": {"component_id": component_id, "component_version": 1},
            "parameters": parameters or {},
        }],
        "edges": [],
    }


def test_compound_public_and_body_ports_must_be_byte_equal():
    public = [_port("in", "input"), _port("out", "output")]
    mismatched_body = {"graph_inputs": [_port("in", "input", default=0.0)], "graph_outputs": [_port("out", "output")]}
    compound = _compound(
        public_ports=public,
        body_nodes=[],
        body_ports=mismatched_body,
    )
    with pytest.raises(ValueError, match="public port differs"):
        _registry({("compound.bundle", 1): compound})


@pytest.mark.parametrize(
    ("parameters", "expected_kind", "expected_value"),
    [
        ({"gain": 3.5}, "explicit", 3.5),
        ({}, "default", 2.0),
        ({}, "absence", None),
    ],
)
def test_compound_public_parameter_state_reaches_every_bound_target(
    parameters: dict[str, object], expected_kind: str, expected_value: object
):
    descriptor = _parameter(default=2.0 if expected_kind == "default" else None, required=expected_kind != "absence")
    child = _leaf("leaf.scale", parameters={"gain": descriptor, "literal": _parameter(default=7.0)})
    compound = _compound(
        body_nodes=[
            {"node_id": "first", "component": {"component_id": "leaf.scale", "component_version": 1}, "parameters": {"literal": 7.0}},
            {"node_id": "second", "component": {"component_id": "leaf.scale", "component_version": 1}, "parameters": {"literal": 7.0}},
        ],
        public_parameters={"gain": descriptor},
        bindings=[{"parameter_id": "gain", "targets": [
            {"node_id": "first", "parameter_id": "gain"},
            {"node_id": "second", "parameter_id": "gain"},
        ]}],
    )
    registry = _registry({("leaf.scale", 1): child, ("compound.bundle", 1): compound})
    resolved = resolve_v2(_document(parameters=parameters), registry)

    leaves = {node.node_id: node for node in resolved.nodes if node.node_id != "bundle"}
    assert {node.parameters["gain"] for node in leaves.values()} == {expected_value}
    assert all(node.parameters["literal"] == 7.0 for node in leaves.values())
    assert all(node.parameter_provenance["gain"]["kind"] == expected_kind for node in leaves.values())
    assert all("bundle" in node.parameter_provenance["gain"]["path"] for node in leaves.values())


def test_nested_compound_provenance_contains_full_instance_and_target_path():
    parameter = _parameter()
    leaf = _leaf("leaf.scale", parameters={"gain": parameter})
    inner = _compound(
        component_id="compound.inner",
        body_nodes=[{"node_id": "leaf", "component": {"component_id": "leaf.scale", "component_version": 1}, "parameters": {}}],
        public_parameters={"gain": parameter},
        bindings=[{"parameter_id": "gain", "targets": [{"node_id": "leaf", "parameter_id": "gain"}]}],
    )
    outer = _compound(
        body_nodes=[{"node_id": "inner", "component": {"component_id": "compound.inner", "component_version": 1}, "parameters": {}}],
        public_parameters={"gain": parameter},
        bindings=[{"parameter_id": "gain", "targets": [{"node_id": "inner", "parameter_id": "gain"}]}],
    )
    registry = _registry({("leaf.scale", 1): leaf, ("compound.inner", 1): inner, ("compound.bundle", 1): outer})
    resolved = resolve_v2(_document(parameters={"gain": 4.0}), registry)

    leaf_node = next(node for node in resolved.nodes if node.node_id.endswith("leaf"))
    provenance = leaf_node.parameter_provenance["gain"]
    assert provenance["path"] == ("bundle", "inner", "leaf")
    assert provenance["target_paths"] == (("inner", "gain"), ("leaf", "gain"))


def test_recursive_compound_lowering_preserves_boundary_edges_and_nested_provenance():
    """A compound body is an ordinary closed graph, not a node list hint.

    The outer graph, inner body, and leaf each have an explicit boundary edge.
    Resolution must lower the complete topology while retaining the authored
    public/internal edge identities and the full instance path.
    """
    parameter = _parameter()
    leaf = _leaf("leaf.scale", parameters={"gain": parameter})
    boundary_in = _port("in", "input", default=0.0)
    boundary_out = _port("out", "output")

    def body(node_id: str, component_id: str) -> dict[str, object]:
        return {
            "graph_inputs": [deepcopy(boundary_in)],
            "graph_outputs": [deepcopy(boundary_out)],
            "nodes": [{
                "node_id": node_id,
                "component": {"component_id": component_id, "component_version": 1},
                "parameters": {},
            }],
            "edges": [
                {
                    "edge_id": f"{node_id}-input",
                    "source": {"scope": "graph_input", "port_id": "in"},
                    "target": {"scope": "node", "node_id": node_id, "port_id": "in"},
                    "binding": {"kind": "single"},
                },
                {
                    "edge_id": f"{node_id}-output",
                    "source": {"scope": "node", "node_id": node_id, "port_id": "out"},
                    "target": {"scope": "graph_output", "port_id": "out"},
                    "binding": {"kind": "single"},
                },
            ],
        }

    inner = _compound(
        component_id="compound.inner",
        body_nodes=[],
        public_ports=[deepcopy(boundary_in), deepcopy(boundary_out)],
        public_parameters={"gain": parameter},
        bindings=[{"parameter_id": "gain", "targets": [{"node_id": "leaf", "parameter_id": "gain"}]}],
        body_ports=body("leaf", "leaf.scale"),
    )
    outer = _compound(
        body_nodes=[],
        public_ports=[deepcopy(boundary_in), deepcopy(boundary_out)],
        public_parameters={"gain": parameter},
        bindings=[{"parameter_id": "gain", "targets": [{"node_id": "inner", "parameter_id": "gain"}]}],
        body_ports=body("inner", "compound.inner"),
    )
    document = _document(parameters={"gain": 4.0})
    document["graph_inputs"] = [deepcopy(boundary_in)]
    document["graph_outputs"] = [deepcopy(boundary_out)]
    document["edges"] = [
        {
            "edge_id": "public-input",
            "source": {"scope": "graph_input", "port_id": "in"},
            "target": {"scope": "node", "node_id": "bundle", "port_id": "in"},
            "binding": {"kind": "single"},
        },
        {
            "edge_id": "public-output",
            "source": {"scope": "node", "node_id": "bundle", "port_id": "out"},
            "target": {"scope": "graph_output", "port_id": "out"},
            "binding": {"kind": "single"},
        },
    ]
    registry = _registry({
        ("leaf.scale", 1): leaf,
        ("compound.inner", 1): inner,
        ("compound.bundle", 1): outer,
    })

    resolved = resolve_v2(document, registry)

    assert [node.node_id for node in resolved.nodes] == ["bundle/inner/leaf"]
    leaf_node = resolved.nodes[0]
    assert leaf_node.parameters["gain"] == 4.0
    assert leaf_node.parameter_provenance["gain"]["path"] == ("bundle", "inner", "leaf")
    assert leaf_node.parameter_provenance["gain"]["target_paths"] == (("inner", "gain"), ("leaf", "gain"))
    assert resolved.outputs["out"].provenance["edge_id"] == "public-output"
    assert resolved.outputs["out"].provenance["source"]["node_id"] == "bundle/inner/leaf"


def test_two_level_input_provenance_retains_public_internal_nested_and_leaf_edges():
    """Input lowering keeps every authored edge hop and its compound path."""
    boundary_in = _port("in", "input", default=0.0)
    boundary_out = _port("out", "output")

    def body(node_id: str, component_id: str) -> dict[str, object]:
        return {
            "graph_inputs": [deepcopy(boundary_in)],
            "graph_outputs": [deepcopy(boundary_out)],
            "nodes": [{
                "node_id": node_id,
                "component": {"component_id": component_id, "component_version": 1},
                "parameters": {},
            }],
            "edges": [
                {
                    "edge_id": f"{node_id}-input",
                    "source": {"scope": "graph_input", "port_id": "in"},
                    "target": {"scope": "node", "node_id": node_id, "port_id": "in"},
                    "binding": {"kind": "single"},
                },
                {
                    "edge_id": f"{node_id}-output",
                    "source": {"scope": "node", "node_id": node_id, "port_id": "out"},
                    "target": {"scope": "graph_output", "port_id": "out"},
                    "binding": {"kind": "single"},
                },
            ],
        }

    leaf = _leaf("leaf.scale", parameters={})
    inner = _compound(
        component_id="compound.inner",
        public_ports=[deepcopy(boundary_in), deepcopy(boundary_out)],
        body_ports=body("leaf", "leaf.scale"),
    )
    outer = _compound(
        public_ports=[deepcopy(boundary_in), deepcopy(boundary_out)],
        body_ports=body("inner", "compound.inner"),
    )
    document = _document()
    document["graph_inputs"] = [deepcopy(boundary_in)]
    document["graph_outputs"] = [deepcopy(boundary_out)]
    document["edges"] = [
        {
            "edge_id": "public-input",
            "source": {"scope": "graph_input", "port_id": "in"},
            "target": {"scope": "node", "node_id": "bundle", "port_id": "in"},
            "binding": {"kind": "single"},
        },
        {
            "edge_id": "public-output",
            "source": {"scope": "node", "node_id": "bundle", "port_id": "out"},
            "target": {"scope": "graph_output", "port_id": "out"},
            "binding": {"kind": "single"},
        },
    ]
    registry = _registry({
        ("leaf.scale", 1): leaf,
        ("compound.inner", 1): inner,
        ("compound.bundle", 1): outer,
    })

    resolved = resolve_v2(document, registry)
    member = resolved.bundles[("bundle/inner/leaf", "in")].members[0]

    assert member.edge_id == "public-input"
    assert member.provenance["edge_id"] == "public-input"
    assert [hop["edge_id"] for hop in member.provenance["edge_path"]] == [
        "public-input", "inner-input", "leaf-input",
    ]
    assert [hop["path"] for hop in member.provenance["edge_path"]] == [
        (), ("bundle",), ("bundle", "inner"),
    ]
    assert [hop["binding"] for hop in member.provenance["edge_path"]] == [
        {"kind": "single"}, {"kind": "single"}, {"kind": "single"},
    ]


def test_two_level_output_provenance_retains_direct_edge_id_and_reverse_leaf_path():
    """Output provenance remains directly addressable while retaining nested hops."""
    boundary_in = _port("in", "input", default=0.0)
    boundary_out = _port("out", "output")

    def body(node_id: str, component_id: str) -> dict[str, object]:
        return {
            "graph_inputs": [deepcopy(boundary_in)],
            "graph_outputs": [deepcopy(boundary_out)],
            "nodes": [{
                "node_id": node_id,
                "component": {"component_id": component_id, "component_version": 1},
                "parameters": {},
            }],
            "edges": [
                {
                    "edge_id": f"{node_id}-input",
                    "source": {"scope": "graph_input", "port_id": "in"},
                    "target": {"scope": "node", "node_id": node_id, "port_id": "in"},
                    "binding": {"kind": "single"},
                },
                {
                    "edge_id": f"{node_id}-output",
                    "source": {"scope": "node", "node_id": node_id, "port_id": "out"},
                    "target": {"scope": "graph_output", "port_id": "out"},
                    "binding": {"kind": "single"},
                },
            ],
        }

    leaf = _leaf("leaf.scale", parameters={})
    inner = _compound(
        component_id="compound.inner",
        public_ports=[deepcopy(boundary_in), deepcopy(boundary_out)],
        body_ports=body("leaf", "leaf.scale"),
    )
    outer = _compound(
        public_ports=[deepcopy(boundary_in), deepcopy(boundary_out)],
        body_ports=body("inner", "compound.inner"),
    )
    document = _document()
    document["graph_inputs"] = [deepcopy(boundary_in)]
    document["graph_outputs"] = [deepcopy(boundary_out)]
    document["edges"] = [
        {
            "edge_id": "public-input",
            "source": {"scope": "graph_input", "port_id": "in"},
            "target": {"scope": "node", "node_id": "bundle", "port_id": "in"},
            "binding": {"kind": "single"},
        },
        {
            "edge_id": "public-output",
            "source": {"scope": "node", "node_id": "bundle", "port_id": "out"},
            "target": {"scope": "graph_output", "port_id": "out"},
            "binding": {"kind": "single"},
        },
    ]
    registry = _registry({
        ("leaf.scale", 1): leaf,
        ("compound.inner", 1): inner,
        ("compound.bundle", 1): outer,
    })

    resolved = resolve_v2(document, registry)
    provenance = resolved.outputs["out"].provenance

    assert resolved.outputs["out"].edge_id == "graph-output:out"
    assert provenance["edge_id"] == "public-output"
    assert [hop["edge_id"] for hop in provenance["edge_path"]] == [
        "leaf-output", "inner-output", "public-output",
    ]
    assert [hop["path"] for hop in provenance["edge_path"]] == [
        ("bundle", "inner"), ("bundle",), (),
    ]
    assert [hop["binding"] for hop in provenance["edge_path"]] == [
        {"kind": "single"}, {"kind": "single"}, {"kind": "single"},
    ]


def test_compound_cycle_is_rejected_before_partial_resolution():
    parameter = _parameter()
    cyclic = _compound(
        component_id="compound.cycle",
        body_nodes=[{"node_id": "self", "component": {"component_id": "compound.cycle", "component_version": 1}, "parameters": {}}],
        public_parameters={"gain": parameter},
        bindings=[{"parameter_id": "gain", "targets": [{"node_id": "self", "parameter_id": "gain"}]}],
    )
    with pytest.raises(ValueError, match="component reference cycle"):
        _registry({("compound.cycle", 1): cyclic})
