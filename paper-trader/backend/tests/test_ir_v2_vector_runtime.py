"""Mechanical v2 vector-runtime cases for assembly, defaults, and refusal."""
from __future__ import annotations

from copy import deepcopy

import pytest

from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_v2_implementation
from app.ir.resolve import resolve_v2
from app.ir.runtime import EvaluationError, evaluate_v2


TYPE_REF = {"type_id": "runtime.number", "type_version": 1}
_OBSERVED: dict[str, object] = {}


def _port(port_id: str, *, direction: str, assembly: str = "single", minimum: int = 0,
          maximum: int | None = 1, default: object = ...):
    value = {
        "port_id": port_id, "direction": direction, "semantic_flow": "value",
        "semantic_role": "runtime_value", "type_ref": dict(TYPE_REF), "shape": "scalar",
    }
    if direction == "input":
        value["connections"] = {
            "cardinality": (
                "single" if minimum == 1 and maximum == 1
                else "optional" if minimum == 0 and maximum == 1
                else "bounded_many"
            ),
            "min": minimum, "max": maximum, "assembly": assembly,
        }
        if default is not ...:
            value["default"] = default
    return value


def _component(component_id: str, ports: list[dict[str, object]]):
    return {
        "component_id": component_id, "component_version": 1,
        "domain_family": "utility", "structural_role": "transform",
        "ports": ports, "parameters": {},
    }


@pytest.fixture()
def registry():
    components = [
        _component("source", [_port("out", direction="output")]),
        _component("many", [
            _port("values", direction="input", assembly="ordered", minimum=1, maximum=3),
            _port("out", direction="output"),
        ]),
        _component("keyed", [
            _port("values", direction="input", assembly="keyed", minimum=1, maximum=3),
            _port("out", direction="output"),
        ]),
        _component("default", [
            _port("value", direction="input", default=7.0),
            _port("out", direction="output"),
        ]),
        _component("single", [
            _port("value", direction="input", minimum=1, maximum=1),
            _port("out", direction="output"),
        ]),
    ]
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={("runtime.number", 1): {
            "type_id": "runtime.number", "type_version": 1,
            "shapes": ["scalar"], "runtime_representation": "float",
        }},
        v2_components={(component["component_id"], 1): component for component in components},
    )


def _document(nodes, edges, *, output_node: str = "target", output_port: str = "out"):
    return {
        "format_version": 2, "strategy_id": "runtime-cases", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "runtime", "description": None, "tags": []},
        "graph_inputs": [],
        "graph_outputs": [],
        "nodes": nodes,
        "edges": edges,
    }


def _node(node_id: str, component_id: str):
    return {"node_id": node_id, "component": {"component_id": component_id, "component_version": 1}, "parameters": {}}


def _edge(edge_id: str, source_node: str, target_node: str, target_port: str, binding):
    return {
        "edge_id": edge_id,
        "source": {"scope": "node", "node_id": source_node, "port_id": "out"},
        "target": {"scope": "node", "node_id": target_node, "port_id": target_port},
        "binding": binding,
    }


def _implementations(observed=None):
    global _OBSERVED
    _OBSERVED = {} if observed is None else observed
    return {
        ("source", 1): lambda parameters, inputs: {"out": 1.0},
        ("many", 1): _many,
        ("keyed", 1): _keyed,
        ("default", 1): _default,
        ("single", 1): _single,
    }


def _many(_parameters, inputs):
    _OBSERVED["many"] = tuple(inputs["values"])
    return {"out": _OBSERVED["many"]}


def _keyed(_parameters, inputs):
    _OBSERVED["keyed"] = tuple(inputs["values"].items())
    return {"out": _OBSERVED["keyed"]}


def _default(_parameters, inputs):
    _OBSERVED["default"] = inputs["value"]
    return {"out": _OBSERVED["default"]}


def _single(_parameters, inputs):
    _OBSERVED["single"] = inputs["value"]
    return {"out": _OBSERVED["single"]}


def _executable_registry(registry, observed=None):
    implementations = _implementations(observed)
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types=registry.v2_types,
        v2_components=registry.v2_components,
        v2_implementations={
            key: registered_v2_implementation(
                component=key, implementation=implementation,
                dependency_boundary=DependencyBoundary("defining_module"),
            )
            for key, implementation in implementations.items()
        },
    )


def test_vector_assembles_many_inputs_in_declared_order_and_key_order(registry):
    document = _document(
        [_node("a", "source"), _node("b", "source"), _node("target", "many")],
        [
            _edge("e2", "b", "target", "values", {"kind": "ordered", "position": 1}),
            _edge("e1", "a", "target", "values", {"kind": "ordered", "position": 0}),
        ],
    )
    graph = resolve_v2(document, registry)
    observed = {}
    evaluate_v2(graph, {}, _executable_registry(registry, observed))
    assert observed["many"] == (1.0, 1.0)
    assert [member.edge_id for member in graph.bundles[("target", "values")].members] == ["e1", "e2"]

    keyed = deepcopy(document)
    keyed["nodes"][-1] = _node("target", "keyed")
    keyed["edges"][0]["binding"] = {"kind": "keyed", "key": "right"}
    keyed["edges"][1]["binding"] = {"kind": "keyed", "key": "left"}
    keyed_graph = resolve_v2(keyed, registry)
    observed = {}
    evaluate_v2(keyed_graph, {}, _executable_registry(registry, observed))
    assert observed["keyed"] == (("left", 1.0), ("right", 1.0))


def test_vector_resolution_and_result_are_deterministic_under_document_reordering(registry):
    document = _document(
        [_node("a", "source"), _node("b", "source"), _node("target", "many")],
        [
            _edge("e2", "b", "target", "values", {"kind": "ordered", "position": 1}),
            _edge("e1", "a", "target", "values", {"kind": "ordered", "position": 0}),
        ],
    )
    reordered = deepcopy(document)
    reordered["nodes"].reverse()
    reordered["edges"].reverse()
    first, second = resolve_v2(document, registry), resolve_v2(reordered, registry)
    assert first == second
    first_seen, second_seen = {}, {}
    evaluate_v2(first, {}, _executable_registry(registry, first_seen))
    evaluate_v2(second, {}, _executable_registry(registry, second_seen))
    assert first_seen == second_seen


def test_vector_uses_declared_default_and_fanout_keeps_branches_independent(registry):
    document = _document(
        [_node("source", "source"), _node("first", "single"), _node("second", "single"), _node("defaulted", "default")],
        [
            _edge("fanout-a", "source", "first", "value", {"kind": "single"}),
            _edge("fanout-b", "source", "second", "value", {"kind": "single"}),
        ],
        output_node="first",
    )
    graph = resolve_v2(document, registry)
    assert graph.bundles[("defaulted", "value")].default == 7.0
    observed = {}
    evaluate_v2(graph, {}, _executable_registry(registry, observed))
    assert observed["single"] == 1.0
    assert observed["default"] == 7.0


def test_vector_fails_closed_for_absent_implementation_and_cyclic_topology(registry):
    document = _document(
        [_node("a", "source"), _node("target", "single")],
        [_edge("e1", "a", "target", "value", {"kind": "single"})],
    )
    graph = resolve_v2(document, registry)
    with pytest.raises(EvaluationError, match="no declared v2 implementation"):
        evaluate_v2(graph, {}, registry)

    cyclic = _document(
        [_node("a", "single"), _node("b", "single")],
        [
            _edge("ab", "a", "b", "value", {"kind": "single"}),
            _edge("ba", "b", "a", "value", {"kind": "single"}),
        ],
    )
    with pytest.raises(Exception, match="v2 topology"):
        resolve_v2(cyclic, registry)
