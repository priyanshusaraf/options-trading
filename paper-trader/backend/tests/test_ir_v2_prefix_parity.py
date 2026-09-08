"""Independent v2 vector/prefix parity and killed-mutation cases."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest

from app.ir.resolve import ResolvedV2Bundle, ResolvedV2Member, resolve_v2
from app.ir.runtime import evaluate_v2
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_v2_implementation
from app.ir import streaming_reference
from app.ir.streaming_reference import evaluate_v2_prefix_stream


SERIES = {"type_id": "test.series", "type_version": 1}


def _port(port_id: str, direction: str) -> dict[str, object]:
    value: dict[str, object] = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "value",
        "type_ref": deepcopy(SERIES),
        "shape": "series",
    }
    if direction == "input":
        value["connections"] = {
            "cardinality": "single",
            "min": 1,
            "max": 1,
            "assembly": "single",
        }
    return value


def _registry() -> SimpleNamespace:
    types = {
        ("test.series", 1): {
            "type_id": "test.series",
            "type_version": 1,
            "shapes": ("series",),
            "runtime_representation": "pandas.Series",
        }
    }
    components = {}
    for component_id in ("identity", "cumulative"):
        ports = [_port("out", "output")]
        if component_id in {"identity", "cumulative"}:
            ports.insert(0, _port("values", "input"))
        if component_id == "identity":
            ports[0]["connections"] = {
                "cardinality": "optional", "min": 0, "max": 1, "assembly": "single"
            }
        components[(component_id, 1)] = {
            "component_id": component_id,
            "component_version": 1,
            "domain_family": "utility",
            "structural_role": "transform",
            "ports": ports,
            "parameters": {},
        }
    return SimpleNamespace(v2_types=types, v2_components=components)


def _document() -> dict[str, object]:
    output = _port("result", "output")
    return {
        "format_version": 2,
        "strategy_id": "prefix-parity",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": "Prefix parity",
            "description": "Causal fixed-topology parity fixture",
            "tags": ["parity"],
        },
        "graph_inputs": [],
        "graph_outputs": [output],
        "nodes": [
            {
                "node_id": "identity",
                "component": {"component_id": "identity", "component_version": 1},
                "parameters": {},
            },
            {
                "node_id": "cumulative",
                "component": {"component_id": "cumulative", "component_version": 1},
                "parameters": {},
            },
        ],
        "edges": [
            {
                "edge_id": "identity-to-cumulative",
                "source": {"scope": "node", "node_id": "identity", "port_id": "out"},
                "target": {"scope": "node", "node_id": "cumulative", "port_id": "values"},
                "binding": {"kind": "single"},
            },
        ],
    }


def _inputs() -> dict[str, pd.Series]:
    index = pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC")
    return {"prices": pd.Series([1.0, 2.0, 3.0, 4.0], index=index)}


def _implementations():
    def identity(_parameters, inputs):
        return {"out": inputs["values"]}

    def cumulative(_parameters, inputs):
        return {"out": inputs["values"].cumsum()}

    return {("identity", 1): identity, ("cumulative", 1): cumulative}


def _executable_registry(base=None, implementations=None):
    implementations = _implementations() if implementations is None else implementations
    components = _registry().v2_components if base is None else base.v2_components
    types = _registry().v2_types if base is None else base.v2_types
    return PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=types,
        v2_components=components,
        v2_implementations={
            key: registered_v2_implementation(
                component=key, implementation=implementation,
                dependency_boundary=DependencyBoundary("defining_module"),
            ) for key, implementation in implementations.items()
        },
    )


def _resolved_graph():
    graph = resolve_v2(_document(), _registry())
    input_member = ResolvedV2Member(
        edge_id="input-to-identity",
        source={"scope": "graph_input", "port_id": "prices"},
        binding={"kind": "single"},
        type_ref=SERIES,
        provenance={"edge_id": "input-to-identity"},
    )
    bundles = dict(graph.bundles)
    bundles[("identity", "values")] = ResolvedV2Bundle(
        target={"scope": "node", "node_id": "identity", "port_id": "values"},
        assembly="single",
        members=(input_member,),
        default=None,
        default_provenance=None,
    )
    output = ResolvedV2Member(
        edge_id="cumulative-to-output",
        source={"scope": "node", "node_id": "cumulative", "port_id": "out"},
        binding={"kind": "single"},
        type_ref=SERIES,
        provenance={"edge_id": "cumulative-to-output"},
    )
    return replace(graph, bundles=bundles, outputs={"result": output})


def test_v2_vector_and_independent_prefix_outputs_agree_causally():
    graph = _resolved_graph()
    inputs = _inputs()
    registry = _executable_registry()
    vector = evaluate_v2(graph, inputs, registry)
    prefix = evaluate_v2_prefix_stream(graph, inputs, registry)

    assert set(vector) == set(prefix) == {"result"}
    assert vector["result"].equals(prefix["result"])
    assert vector["result"].tolist() == [1.0, 3.0, 6.0, 10.0]


def test_v2_prefix_evaluation_is_repeatable_and_input_order_independent():
    document = _document()
    graph = _resolved_graph()
    inputs = _inputs()
    registry = _executable_registry()
    first = evaluate_v2_prefix_stream(graph, inputs, registry)
    second = evaluate_v2_prefix_stream(graph, dict(reversed(tuple(inputs.items()))), registry)

    assert first["result"].equals(second["result"])
    assert evaluate_v2(graph, inputs, registry)["result"].equals(first["result"])


def test_killed_prefix_mutation_is_detected(monkeypatch):
    graph = _resolved_graph()
    inputs = _inputs()
    registry = _executable_registry()
    expected = evaluate_v2(graph, inputs, registry)["result"]
    original = streaming_reference._evaluate_v2_once

    def mutated(graph_value, input_value, implementations):
        result = dict(original(graph_value, input_value, implementations))
        result["result"] = result["result"].shift(-1).fillna(0.0)
        return result

    monkeypatch.setattr(streaming_reference, "_evaluate_v2_once", mutated)
    killed = evaluate_v2_prefix_stream(graph, inputs, registry)["result"]

    assert not expected.equals(killed)


@pytest.mark.parametrize("engine", ["reference", "incremental"])
def test_scalar_middle_prefix_corruption_is_refused_even_when_final_matches(monkeypatch, engine):
    from app.ir import incremental_runtime
    from app.market_data.requirements import compile_data_requirement_plan
    from tests.test_v0_monitoring_intent_contract import (
        DEFAULT_REGISTRY, monitoring_series_graph, monitoring_series_inputs,
    )

    graph, inputs = monitoring_series_graph(), monitoring_series_inputs()
    module, function = ((streaming_reference, "_evaluate_v2_once") if engine == "reference"
                        else (incremental_runtime, "_evaluate_incremental_once"))
    original = getattr(module, function)

    def corrupt_middle(graph, inputs, registry, **kwargs):
        result = dict(original(graph, inputs, registry, **kwargs))
        if len(inputs["left"]) == 2:
            result["buy"] = {**result["buy"], "requested": False}
        return result

    monkeypatch.setattr(module, function, corrupt_middle)
    if engine == "reference":
        with pytest.raises(streaming_reference.ReferenceEvaluationError, match="scalar output differs"):
            evaluate_v2_prefix_stream(graph, inputs, DEFAULT_REGISTRY)
    else:
        plan = incremental_runtime.accept_research_resource_plan(
            graph, compile_data_requirement_plan(graph, registry=DEFAULT_REGISTRY), DEFAULT_REGISTRY)
        with pytest.raises(incremental_runtime.IncrementalRuntimeRefusal, match="independent prefix evaluation refused"):
            incremental_runtime.evaluate_incremental_v2(graph, inputs, DEFAULT_REGISTRY, plan,
                                                      event_kind="completed_bar", maximum_events=3)


def test_all_series_prefix_does_not_add_vector_evaluations(monkeypatch):
    from app.ir import runtime

    def unexpected(*args, **kwargs):
        pytest.fail("all-Series path must not perform extra vector evaluation")

    monkeypatch.setattr(runtime, "evaluate_v2", unexpected)
    result = evaluate_v2_prefix_stream(_resolved_graph(), _inputs(), _executable_registry())
    assert result["result"].tolist() == [1., 3., 6., 10.]


def test_scalar_prefix_uses_exact_prefix_and_context(monkeypatch):
    from app.ir import runtime
    from tests.test_v0_monitoring_intent_contract import (
        DEFAULT_REGISTRY, monitoring_series_graph, monitoring_series_inputs,
    )
    original = runtime.evaluate_v2
    observed = []

    def resolver(node, inputs):
        return None

    def observe(graph, inputs, registry, *, evaluation_context_resolver):
        assert evaluation_context_resolver is resolver
        observed.append(tuple(inputs["left"].index))
        return original(graph, inputs, registry, evaluation_context_resolver=evaluation_context_resolver)

    monkeypatch.setattr(runtime, "evaluate_v2", observe)
    inputs = monitoring_series_inputs()
    evaluate_v2_prefix_stream(monitoring_series_graph(), inputs, DEFAULT_REGISTRY, evaluation_context_resolver=resolver)
    assert observed == [tuple(inputs["left"].index[:end]) for end in (1, 2, 3)]


def test_empty_prefix_refuses():
    inputs = {name: value.iloc[:0] for name, value in _inputs().items()}
    with pytest.raises(streaming_reference.ReferenceEvaluationError, match="empty"):
        evaluate_v2_prefix_stream(_resolved_graph(), inputs, _executable_registry())


def test_declared_scalar_cannot_return_series():
    from tests.test_v0_monitoring_intent_contract import (
        DEFAULT_REGISTRY, monitoring_series_graph, monitoring_series_inputs,
    )
    graph, inputs = monitoring_series_graph(), monitoring_series_inputs()
    current = dict(evaluate_v2(graph, inputs, DEFAULT_REGISTRY))
    current["buy"] = inputs["left"]
    with pytest.raises(streaming_reference.ReferenceEvaluationError, match="scalar output contains a Series"):
        streaming_reference._v2_check_scalar_prefix(graph, inputs, DEFAULT_REGISTRY, current, {"buy"}, None)


def test_recursive_compound_lowering_has_vector_prefix_parity():
    """Independent evaluators must consume the same lowered nested topology."""
    boundary_in = _port("values", "input")
    boundary_out = _port("out", "output")
    identity = {
        "component_id": "identity",
        "component_version": 1,
        "domain_family": "utility",
        "structural_role": "transform",
        "ports": [_port("values", "input"), _port("out", "output")],
        "parameters": {},
    }

    def compound(component_id: str, child_id: str, child_component: str) -> dict[str, object]:
        return {
            "component_id": component_id,
            "component_version": 1,
            "domain_family": "utility",
            "structural_role": "transform",
            "ports": [deepcopy(boundary_in), deepcopy(boundary_out)],
            "parameters": {},
            "compound": {
                "body": {
                    "graph_inputs": [deepcopy(boundary_in)],
                    "graph_outputs": [deepcopy(boundary_out)],
                    "nodes": [{
                        "node_id": child_id,
                        "component": {"component_id": child_component, "component_version": 1},
                        "parameters": {},
                    }],
                    "edges": [
                        {
                            "edge_id": f"{child_id}-input",
                            "source": {"scope": "graph_input", "port_id": "values"},
                            "target": {"scope": "node", "node_id": child_id, "port_id": "values"},
                            "binding": {"kind": "single"},
                        },
                        {
                            "edge_id": f"{child_id}-output",
                            "source": {"scope": "node", "node_id": child_id, "port_id": "out"},
                            "target": {"scope": "graph_output", "port_id": "out"},
                            "binding": {"kind": "single"},
                        },
                    ],
                },
                "parameter_bindings": [],
            },
        }

    components = {
            ("identity", 1): identity,
            ("compound.inner", 1): compound("compound.inner", "identity", "identity"),
            ("compound.outer", 1): compound("compound.outer", "inner", "compound.inner"),
    }
    registry = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=_registry().v2_types,
        v2_components=components,
        v2_implementations={
            ("identity", 1): registered_v2_implementation(
                component=("identity", 1),
                implementation=lambda _p, inputs: {"out": inputs["values"]},
                dependency_boundary=DependencyBoundary("defining_module"),
            ),
        },
    )
    document = {
        "format_version": 2,
        "strategy_id": "nested-prefix-parity",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Nested", "description": None, "tags": []},
        "graph_inputs": [deepcopy(boundary_in)],
        "graph_outputs": [deepcopy(boundary_out)],
        "nodes": [{"node_id": "outer", "component": {"component_id": "compound.outer", "component_version": 1}, "parameters": {}}],
        "edges": [
            {
                "edge_id": "public-input",
                "source": {"scope": "graph_input", "port_id": "values"},
                "target": {"scope": "node", "node_id": "outer", "port_id": "values"},
                "binding": {"kind": "single"},
            },
            {
                "edge_id": "public-output",
                "source": {"scope": "node", "node_id": "outer", "port_id": "out"},
                "target": {"scope": "graph_output", "port_id": "out"},
                "binding": {"kind": "single"},
            },
        ],
    }
    graph = resolve_v2(document, registry)
    vector = evaluate_v2(graph, {"values": _inputs()["prices"]}, registry)
    prefix = evaluate_v2_prefix_stream(graph, {"values": _inputs()["prices"]}, registry)
    assert vector["out"].equals(prefix["out"])
    assert vector["out"].tolist() == [1.0, 2.0, 3.0, 4.0]
