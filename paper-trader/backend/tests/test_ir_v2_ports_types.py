"""Mechanical v2 port and exact-type contract cases."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.ir.formats.v2 import validate_document


FLOAT_SCALAR = {"type_id": "strategy-os.float64", "type_version": 1}
FLOAT_SERIES = {"type_id": "strategy-os.float64-series", "type_version": 1}
BOOL_SCALAR = {"type_id": "strategy-os.bool", "type_version": 1}


def _port(
    port_id: str,
    direction: str,
    type_ref: dict[str, object] = FLOAT_SCALAR,
    *,
    flow: str = "value",
    shape: str = "scalar",
    cardinality: str = "single",
    minimum: int = 1,
    maximum: int | None = 1,
    assembly: str = "single",
    default: object = ...,
) -> dict[str, object]:
    value: dict[str, object] = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": flow,
        "semantic_role": "value",
        "type_ref": deepcopy(type_ref),
        "shape": shape,
    }
    if direction == "input":
        value["connections"] = {
            "cardinality": cardinality,
            "min": minimum,
            "max": maximum,
            "assembly": assembly,
        }
        if default is not ...:
            value["default"] = default
    return value


def _registry(
    *,
    source_output: dict[str, object] | None = None,
    sink_input: dict[str, object] | None = None,
) -> SimpleNamespace:
    source_output = source_output or _port("out", "output")
    sink_input = sink_input or _port("in", "input")
    types = {
        ("strategy-os.float64", 1): {
            "type_id": "strategy-os.float64",
            "type_version": 1,
            "shapes": ("scalar",),
            "runtime_representation": "float",
        },
        ("strategy-os.float64-series", 1): {
            "type_id": "strategy-os.float64-series",
            "type_version": 1,
            "shapes": ("series",),
            "runtime_representation": "tuple[float, ...]",
        },
        ("strategy-os.bool", 1): {
            "type_id": "strategy-os.bool",
            "type_version": 1,
            "shapes": ("scalar",),
            "runtime_representation": "bool",
        },
    }
    components = {
        ("source", 1): {
            "component_id": "source",
            "component_version": 1,
            "domain_family": "market_data",
            "structural_role": "source",
            "ports": [source_output],
            "parameters": {},
        },
        ("sink", 1): {
            "component_id": "sink",
            "component_version": 1,
            "domain_family": "transform",
            "structural_role": "transform",
            "ports": [sink_input],
            "parameters": {},
        },
    }
    return SimpleNamespace(v2_types=types, v2_components=components)


def _document(*, source_output=None, sink_input=None) -> tuple[dict[str, object], SimpleNamespace]:
    registry = _registry(source_output=source_output, sink_input=sink_input)
    target_port = sink_input or _port("in", "input")
    target_assembly = target_port["connections"]["assembly"]
    binding = {"kind": "single" if target_assembly == "single" else target_assembly}
    if target_assembly == "ordered":
        binding["position"] = 0
    document: dict[str, object] = {
        "format_version": 2,
        "strategy_id": "port-cases",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": "Port cases",
            "description": "Exact port contract",
            "tags": ["tests"],
        },
        "graph_inputs": [],
        "graph_outputs": [deepcopy(source_output or _port("out", "output"))],
        "nodes": [
            {"node_id": "source", "component": {"component_id": "source", "component_version": 1}, "parameters": {}},
            {"node_id": "sink", "component": {"component_id": "sink", "component_version": 1}, "parameters": {}},
        ],
        "edges": [
            {
                "edge_id": "source-to-sink",
                "source": {"scope": "node", "node_id": "source", "port_id": "out"},
                "target": {"scope": "node", "node_id": "sink", "port_id": "in"},
                "binding": binding,
            }
        ],
    }
    return document, registry


def _codes(document: dict[str, object], registry: SimpleNamespace) -> list[str]:
    return [violation.code for violation in validate_document(document, registry)]


def test_exact_registered_scalar_type_shape_and_value_flow_validate() -> None:
    document, registry = _document()
    assert validate_document(document, registry) == []


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("shape", "wildcard", "V2_SHAPE"),
        ("semantic_flow", "action", "V2_FLOW"),
        ("type_ref", {"type_id": "any", "type_version": 1}, "V2_TYPE"),
    ],
)
def test_closed_port_contract_rejects_wildcards_and_action_flow(field, value, code) -> None:
    output = _port("out", "output")
    output[field] = value
    document, registry = _document(source_output=output)
    assert code in _codes(document, registry)


def test_unknown_port_key_is_rejected() -> None:
    output = _port("out", "output")
    output["coerce"] = "float64"
    document, registry = _document(source_output=output)
    violations = validate_document(document, registry)
    assert any(v.code == "V2_UNKNOWN_KEY" and v.path == "$.graph_outputs[0].coerce" for v in violations)


def test_exact_shape_mismatch_is_rejected_without_coercion() -> None:
    sink = _port("in", "input", type_ref=FLOAT_SERIES, shape="series")
    document, registry = _document(sink_input=sink)
    assert "V2_TYPE" in _codes(document, registry) or "V2_SHAPE" in _codes(document, registry)


@pytest.mark.parametrize(
    ("cardinality", "minimum", "maximum", "assembly"),
    [
        ("single", 1, 1, "single"),
        ("optional", 0, 1, "single"),
        ("bounded_many", 0, 2, "ordered"),
        ("variadic", 0, None, "unordered"),
    ],
)
def test_cardinality_table_accepts_closed_combinations(cardinality, minimum, maximum, assembly) -> None:
    sink = _port(
        "in",
        "input",
        cardinality=cardinality,
        minimum=minimum,
        maximum=maximum,
        assembly=assembly,
        default=0.0 if minimum == 0 else ...,
    )
    document, registry = _document(sink_input=sink)
    assert validate_document(document, registry) == []


@pytest.mark.parametrize(
    ("minimum", "maximum", "assembly"),
    [(1, 1, "single"), (0, 1, "ordered"), (0, 2, "single")],
)
def test_invalid_cardinality_or_default_is_rejected(minimum, maximum, assembly) -> None:
    sink = _port(
        "in",
        "input",
        cardinality="single" if minimum == 1 else "optional",
        minimum=minimum,
        maximum=maximum,
        assembly=assembly,
        default=0.0,
    )
    document, registry = _document(sink_input=sink)
    assert "V2_DEFAULT" in _codes(document, registry) or "V2_CARDINALITY" in _codes(document, registry)


def test_output_cannot_declare_input_connections_or_default() -> None:
    output = _port("out", "output")
    output["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    document, registry = _document(source_output=output)
    assert "V2_UNKNOWN_KEY" in _codes(document, registry)
