"""Focused Phase 4 refusal tests for the one Component IR v2 validity contract."""
from __future__ import annotations

import math
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_v2_implementation
from app.ir.resolve import ResolvedV2Bundle, ResolvedV2Graph, ResolvedV2Member, ResolvedV2Node
from app.ir.runtime import evaluate_v2
from app.ir.validity import NumericValue, ValidityState, _closed_finite_value, _lists_to_tuples, entry_authorized, fallback, invalid, valid


FLOAT = {"type_id": "strategy-os.float64", "type_version": 1}
def _source_missing(_parameters, _inputs):
    return {"out": NumericValue(ValidityState.MISSING)}


def _source_stale(_parameters, _inputs):
    return {"out": NumericValue(ValidityState.STALE)}


def _source_insufficient(_parameters, _inputs):
    return {"out": NumericValue(ValidityState.INSUFFICIENT_HISTORY)}


def _combine_true(_parameters, _inputs):
    return {"out": NumericValue(ValidityState.VALID, True)}


def _combine_false(_parameters, _inputs):
    return {"out": NumericValue(ValidityState.VALID, False)}


def _port(
    port_id: str,
    direction: str,
    *,
    cardinality: str = "single",
    minimum: int = 1,
    maximum: int = 1,
    assembly: str = "single",
) -> dict[str, object]:
    value: dict[str, object] = {
        "port_id": port_id, "direction": direction, "semantic_flow": "value",
        "semantic_role": "value", "type_ref": FLOAT, "shape": "scalar",
    }
    if direction == "input":
        value["connections"] = {"cardinality": cardinality, "min": minimum, "max": maximum, "assembly": assembly}
    return value


def _component(component_id: str, ports: list[dict[str, object]], policy: str = "propagate") -> dict[str, object]:
    return {
        "component_id": component_id, "component_version": 1, "domain_family": "utility",
        "structural_role": "transform", "ports": ports, "parameters": {},
        "numeric_validity": {"input_policy": policy, "output_policy": "numeric_envelope"},
    }


def _member(node_id: str, port_id: str) -> ResolvedV2Member:
    return ResolvedV2Member("edge", MappingProxyType({"scope": "node", "node_id": node_id, "port_id": port_id}), MappingProxyType({"kind": "single"}), MappingProxyType(FLOAT), MappingProxyType({"edge_id": "edge"}))


def _registry(implementations, components) -> PlatformRegistry:
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={("strategy-os.float64", 1): {"type_id": "strategy-os.float64", "type_version": 1, "shapes": ("scalar",), "runtime_representation": "float"}},
        v2_components=components,
        v2_implementations={key: registered_v2_implementation(component=key, implementation=value, dependency_boundary=DependencyBoundary("declared_objects", (NumericValue, ValidityState, _closed_finite_value, _lists_to_tuples, math))) for key, value in implementations.items()},
    )


def _graph() -> ResolvedV2Graph:
    source_a = _member("source_a", "out")
    source_b = _member("source_b", "out")
    bundle = ResolvedV2Bundle(MappingProxyType({"scope": "node", "node_id": "combine", "port_id": "inputs"}), "ordered", (source_a, source_b), None, None)
    output = _member("combine", "out")
    return ResolvedV2Graph(
        nodes=(ResolvedV2Node("source_a", ("source_a", 1), MappingProxyType({}), MappingProxyType({})), ResolvedV2Node("source_b", ("source_b", 1), MappingProxyType({}), MappingProxyType({})), ResolvedV2Node("combine", ("combine", 1), MappingProxyType({}), MappingProxyType({}))),
        bundles=MappingProxyType({("combine", "inputs"): bundle}), outputs=MappingProxyType({"entry": output}), graph_inputs=MappingProxyType({}),
    )


def test_closed_vocabulary_rejects_unknown_and_nonfinite_valid_values() -> None:
    with pytest.raises(ValueError):
        NumericValue("UNKNOWN")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        valid(math.nan)
    with pytest.raises(ValueError):
        valid(float("inf"))
    assert valid((1.0, 2.0)).value == (1.0, 2.0)
    with pytest.raises(ValueError):
        valid((1.0, math.nan))
    with pytest.raises(ValueError):
        NumericValue(ValidityState.MISSING, 0.0)


def test_p4_spec_001_supported_tolist_values_are_defensively_immutable() -> None:
    array = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    series = pd.Series([1, 2, 3], dtype="int64")

    accepted_array = NumericValue(ValidityState.VALID, array)
    accepted_series = valid(series)

    assert accepted_array.value == ((1.0, 2.0), (3.0, 4.0))
    assert isinstance(accepted_array.value, tuple)
    assert all(isinstance(row, tuple) for row in accepted_array.value)
    assert accepted_series.value == (1, 2, 3)
    assert isinstance(accepted_series.value, tuple)

    array[0, 0] = np.nan
    series.iloc[0] = 99

    assert accepted_array.value == ((1.0, 2.0), (3.0, 4.0))
    assert accepted_series.value == (1, 2, 3)
    assert accepted_array == NumericValue(ValidityState.VALID, ((1.0, 2.0), (3.0, 4.0)))


@pytest.mark.parametrize(
    "payload",
    [
        [1.0, 2.0],
        {"value": 1.0},
        np.array([1.0, np.nan]),
        pd.Series([1.0, np.inf]),
    ],
)
def test_p4_spec_001_unsupported_or_nonfinite_payloads_fail_closed(payload: object) -> None:
    with pytest.raises(ValueError):
        valid(payload)


def test_multi_input_refusal_is_argument_order_independent() -> None:
    components = {
        ("source_a", 1): _component("source_a", [_port("out", "output")]),
        ("source_b", 1): _component("source_b", [_port("out", "output")]),
        ("combine", 1): _component("combine", [_port("inputs", "input", cardinality="bounded_many", minimum=2, maximum=2, assembly="ordered"), _port("out", "output")]),
    }
    registry = _registry({
        ("source_a", 1): _source_missing,
        ("source_b", 1): _source_stale,
        ("combine", 1): _combine_true,
    }, components)
    result = evaluate_v2(_graph(), {}, registry)["entry"]
    assert result == invalid(ValidityState.INVALID, causes=(ValidityState.MISSING, ValidityState.STALE))
    assert not entry_authorized(result)


def test_same_invalid_cause_propagates_without_false_coercion() -> None:
    components = {
        ("source_a", 1): _component("source_a", [_port("out", "output")]),
        ("source_b", 1): _component("source_b", [_port("out", "output")]),
        ("combine", 1): _component("combine", [_port("inputs", "input", cardinality="bounded_many", minimum=2, maximum=2, assembly="ordered"), _port("out", "output")]),
    }
    registry = _registry({
        ("source_a", 1): _source_insufficient,
        ("source_b", 1): _source_insufficient,
        ("combine", 1): _combine_false,
    }, components)
    result = evaluate_v2(_graph(), {}, registry)["entry"]
    assert result == invalid(ValidityState.INSUFFICIENT_HISTORY)
    assert not entry_authorized(result)


def test_fallback_requires_explicit_policy_and_accepted_state() -> None:
    missing = invalid(ValidityState.MISSING)
    replacement = valid(7.0)
    assert fallback(missing, replacement, (ValidityState.STALE,)) == missing
    assert fallback(missing, replacement, (ValidityState.MISSING,)) == replacement


@pytest.mark.parametrize("value, expected", [(valid(True), True), (valid(False), False), (invalid(ValidityState.NO_TRADE), False)])
def test_only_valid_true_authorizes_entry(value: NumericValue, expected: bool) -> None:
    assert entry_authorized(value) is expected


def test_registry_rejects_implicit_or_unknown_numeric_validity_policy() -> None:
    component = _component("source", [_port("out", "output")])
    component["numeric_validity"] = {"input_policy": "implicit_fill", "output_policy": "numeric_envelope"}
    with pytest.raises(ValueError, match="unknown numeric input policy"):
        _registry({("source", 1): _combine_true}, {("source", 1): component})
