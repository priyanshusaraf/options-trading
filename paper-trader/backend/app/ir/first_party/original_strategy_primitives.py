"""Typed Component IR v2 primitives needed by the original strategy presets.

The existing analytical components consume market frames, while the existing
``logic.*`` v1 components consume one opaque generic payload.  These new
semantic identities make derived numeric and boolean series composable without
changing either published contract.
"""
from __future__ import annotations

import math
import collections.abc as abc
from types import MappingProxyType
from typing import Any

import pandas as pd

from app.ir import node_contracts, registry, validity
from app.ir.first_party.analytical_v2 import contracts


FLOAT = {"type_id": "analytical.float64", "type_version": 2}
BOOLEAN = {"type_id": "analytical.boolean", "type_version": 2}
MARKET_FRAME = {"type_id": "analytical.market_frame", "type_version": 2}

_COMPONENT_VERSION = 1
# Match the bounded composition policy used by the existing logic primitives.
# Outputs are evaluated once and shared; original presets need up to ten readers.
MAXIMUM_OUTPUT_FANOUT = 32
_LENGTH = {
    "type": "int", "required": True, "default": None, "enum": None,
    "domain": {"minimum": 1, "maximum": 4096}, "units": "bars",
    "serialization": "canonical-json",
}
_VALUE = {
    "type": "float", "required": True, "default": None, "enum": None,
    "domain": {"minimum": -10.0, "maximum": 10.0}, "units": "value",
    "serialization": "canonical-json",
}
_PERCENTILE = {**_VALUE, "domain": {"minimum": 0.0, "maximum": 100.0}, "units": "percent"}
_SWITCH = {**_VALUE, "type": "bool", "domain": None, "units": "boolean"}


def _port(port_id: str, direction: str, type_ref: abc.Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "port_id": port_id, "direction": direction, "semantic_flow": "value",
        "semantic_role": "market_frame" if type_ref == MARKET_FRAME else "derived_value",
        "type_ref": dict(type_ref), "shape": "series",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": "single", "min": 1, "max": 1, "assembly": "single",
        }
    return result


def _component(
    name: str, inputs: tuple[tuple[str, abc.Mapping[str, Any]], ...],
    output_type: abc.Mapping[str, Any], parameters: abc.Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "component_id": f"strategy_math.{name}",
        "component_version": 2 if name in {"close", "high", "low", "true_range"} else _COMPONENT_VERSION,
        "domain_family": "condition" if output_type == BOOLEAN else "transform",
        "structural_role": "transform",
        "ports": [*(_port(port_id, "input", type_ref) for port_id, type_ref in inputs),
                  _port("value", "output", output_type)],
        "parameters": dict(parameters or {}),
    }


_SPECS = {
    "close": _component("close", (("frame", MARKET_FRAME),), FLOAT),
    "value": _component("value", (("alignment", FLOAT),), FLOAT, {"value": _VALUE}),
    "ema_first_close": _component(
        "ema_first_close", (("source", FLOAT),), FLOAT, {"length": _LENGTH}),
    "rolling_stddev_population": _component(
        "rolling_stddev_population", (("source", FLOAT),), FLOAT, {"length": _LENGTH}),
    "lag": _component("lag", (("source", FLOAT),), FLOAT, {"length": _LENGTH}),
    "subtract": _component("subtract", (("left", FLOAT), ("right", FLOAT)), FLOAT),
    "divide": _component("divide", (("left", FLOAT), ("right", FLOAT)), FLOAT),
    "abs": _component("abs", (("source", FLOAT),), FLOAT),
    "gt": _component("gt", (("left", FLOAT), ("right", FLOAT)), BOOLEAN),
    "lt": _component("lt", (("left", FLOAT), ("right", FLOAT)), BOOLEAN),
    "and": _component("and", (("left", BOOLEAN), ("right", BOOLEAN)), BOOLEAN),
    "or": _component("or", (("left", BOOLEAN), ("right", BOOLEAN)), BOOLEAN),
    "fallback_zero": _component("fallback_zero", (("source", FLOAT),), FLOAT),
    "fallback_false": _component("fallback_false", (("source", BOOLEAN),), BOOLEAN),
    "high": _component("high", (("frame", MARKET_FRAME),), FLOAT),
    "low": _component("low", (("frame", MARKET_FRAME),), FLOAT),
    "true_range": _component("true_range", (("frame", MARKET_FRAME),), FLOAT),
    "rma_sma_seed": _component("rma_sma_seed", (("source", FLOAT),), FLOAT, {"length": _LENGTH}),
    "nearest_rank": _component("nearest_rank", (("source", FLOAT),), FLOAT,
                               {"length": _LENGTH, "percentile": _PERCENTILE}),
    "multiply": _component("multiply", (("left", FLOAT), ("right", FLOAT)), FLOAT),
    "maximum": _component("maximum", (("left", FLOAT), ("right", FLOAT)), FLOAT),
    "le": _component("le", (("left", FLOAT), ("right", FLOAT)), BOOLEAN),
    "fallback_value": _component("fallback_value", (("left", FLOAT), ("right", FLOAT)), FLOAT),
    "optional_condition": _component("optional_condition", (("source", BOOLEAN),), BOOLEAN,
                                     {"enabled": _SWITCH, "otherwise": _SWITCH}),
}

V2_TYPES: abc.Mapping[tuple[str, int], abc.Mapping[str, Any]] = MappingProxyType({})
V2_COMPONENTS = node_contracts._freeze({
    (component["component_id"], component["component_version"]): component
    for component in _SPECS.values()
})


class OriginalStrategyPrimitiveError(ValueError):
    """A typed primitive received malformed or misaligned runtime input."""


def _series(inputs: abc.Mapping[str, Any], name: str) -> pd.Series:
    value = inputs.get(name)
    if not isinstance(value, pd.Series) or not isinstance(value.index, pd.DatetimeIndex):
        raise OriginalStrategyPrimitiveError(f"{name} must be an indexed series")
    return value


def _numeric(cell: Any) -> validity.NumericValue:
    if not isinstance(cell, validity.NumericValue):
        raise OriginalStrategyPrimitiveError("derived inputs must use NumericValue")
    return cell


def _aligned(inputs: abc.Mapping[str, Any], names: tuple[str, ...]) -> list[pd.Series]:
    series = [_series(inputs, name) for name in names]
    if any(not item.index.equals(series[0].index) for item in series[1:]):
        raise OriginalStrategyPrimitiveError("derived inputs must have identical indexes")
    return series


def _map_unary(source: pd.Series, operation: abc.Callable[[Any], Any]) -> pd.Series:
    return pd.Series((operation(_numeric(cell)) for cell in source), index=source.index, dtype=object)


def _map_binary(
    left: pd.Series, right: pd.Series,
    operation: abc.Callable[[validity.NumericValue, validity.NumericValue], validity.NumericValue],
) -> pd.Series:
    return pd.Series(
        (operation(_numeric(a), _numeric(b)) for a, b in zip(left, right, strict=True)),
        index=left.index, dtype=object,
    )


def _propagating_binary(
    left: validity.NumericValue, right: validity.NumericValue,
    operation: abc.Callable[[Any, Any], Any],
) -> validity.NumericValue:
    refused = validity.propagate((left, right))
    if refused is not None:
        return refused
    try:
        result = operation(left.value, right.value)
        return validity.valid(result)
    except (ArithmeticError, OverflowError, TypeError, ValueError):
        return validity.invalid(validity.ValidityState.MATHEMATICALLY_UNDEFINED)


def _price_cell(raw: Any) -> validity.NumericValue:
    if isinstance(raw, validity.NumericValue):
        if raw.state is not validity.ValidityState.VALID:
            return raw
        raw = raw.value
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        return validity.invalid(validity.ValidityState.MISSING)
    return validity.valid(float(raw))


def _field(inputs: abc.Mapping[str, Any], name: str) -> abc.Mapping[str, Any]:
    frame = inputs.get("frame")
    if not isinstance(frame, abc.Mapping):
        raise OriginalStrategyPrimitiveError("frame must contain canonical fields")
    close = frame.get(name)
    if not isinstance(close, pd.Series) or not isinstance(close.index, pd.DatetimeIndex):
        raise OriginalStrategyPrimitiveError(f"frame.{name} must be an indexed series")
    return {"value": pd.Series((_price_cell(raw) for raw in close), index=close.index, dtype=object)}


def _close(_parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    return _field(inputs, "close")


def _value(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "alignment")
    raw = parameters.get("value", 0.0)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise OriginalStrategyPrimitiveError("value must be finite")
    return {"value": pd.Series((validity.valid(float(raw)) for _ in source),
                               index=source.index, dtype=object)}


def _length(parameters: abc.Mapping[str, Any]) -> int:
    value = parameters.get("length", 1)
    if type(value) is not int or not 1 <= value <= 4096:
        raise OriginalStrategyPrimitiveError("length must be an integer from 1 to 4096")
    return value


def _ema(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    length = _length(parameters)
    alpha = 2.0 / (length + 1.0)
    mean: float | None = None
    refused = None
    cells = []
    for cell in source:
        item = _numeric(cell)
        refused = validity.propagate((item,)) if refused is None else refused
        if refused is not None:
            cells.append(refused)
            continue
        mean = float(item.value) if mean is None else mean + alpha * (float(item.value) - mean)
        cells.append(validity.valid(mean))
    return {"value": pd.Series(cells, index=source.index, dtype=object)}


def _rolling_stddev(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    length = _length(parameters)
    window: list[validity.NumericValue] = []
    cells = []
    for cell in source:
        item = _numeric(cell)
        window.append(item)
        if len(window) > length:
            del window[0]
        refused = validity.propagate(window)
        if refused is not None:
            cells.append(refused)
            continue
        if len(window) < length:
            cells.append(validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY))
            continue
        mean = math.fsum(cell.value for cell in window) / length
        variance = math.fsum((cell.value - mean) ** 2 for cell in window) / length
        cells.append(validity.valid(math.sqrt(variance)))
    return {"value": pd.Series(cells, index=source.index, dtype=object)}


def _lag(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    length = _length(parameters)
    missing = validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY)
    cells = [missing] * min(length, len(source)) + list(source.iloc[:-length])
    return {"value": pd.Series(cells, index=source.index, dtype=object)}


def _binary(name: str, inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    left, right = _aligned(inputs, ("left", "right"))
    operations: dict[str, abc.Callable[[Any, Any], Any]] = {
        "subtract": lambda a, b: a - b,
        "divide": lambda a, b: a / b,
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "and": lambda a, b: bool(a and b),
        "or": lambda a, b: bool(a or b),
        "multiply": lambda a, b: a * b,
        "maximum": max,
        "le": lambda a, b: a <= b,
    }
    return {"value": _map_binary(
        left, right,
        lambda a, b: _propagating_binary(a, b, operations[name]),
    )}


def _true_range(inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    high, low, close = (_field(inputs, name)["value"] for name in ("high", "low", "close"))
    _aligned({"high": high, "low": low, "close": close}, ("high", "low", "close"))
    cells = []
    previous = None
    for h, l, c in zip(high, low, close, strict=True):
        refused = validity.propagate((h, l, c) if previous is None else (h, l, c, previous))
        if refused is not None:
            cells.append(refused)
        else:
            value = h.value - l.value
            if previous is not None:
                value = max(value, abs(h.value - previous.value), abs(l.value - previous.value))
            cells.append(validity.valid(value))
        previous = c
    return {"value": pd.Series(cells, index=close.index, dtype=object)}


def _rma(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    length = _length(parameters)
    seed = []
    mean = None
    refused = None
    cells = []
    for cell in source:
        item = _numeric(cell)
        refused = validity.propagate((item,)) if refused is None else refused
        if refused is not None:
            cells.append(refused)
            continue
        if mean is None:
            seed.append(float(item.value))
            if len(seed) < length:
                cells.append(validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY))
                continue
            mean = math.fsum(seed) / length
        else:
            mean = float(item.value) / length + (1.0 - 1.0 / length) * mean
        cells.append(validity.valid(mean))
    return {"value": pd.Series(cells, index=source.index, dtype=object)}


def _nearest_rank(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    length = _length(parameters)
    pct = parameters["percentile"]
    if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not 0 <= pct <= 100:
        raise OriginalStrategyPrimitiveError("percentile must be from 0 to 100")
    rank = max(1, math.ceil(pct * length / 100)) - 1
    cells = []
    for index in range(len(source)):
        window = [_numeric(cell) for cell in source.iloc[max(0, index-length+1):index+1]]
        refused = validity.propagate(window)
        if refused is not None:
            cells.append(refused)
        elif len(window) < length:
            cells.append(validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY))
        else:
            cells.append(validity.valid(sorted(cell.value for cell in window)[rank]))
    return {"value": pd.Series(cells, index=source.index, dtype=object)}


def _optional_condition(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    if type(parameters["enabled"]) is not bool or type(parameters["otherwise"]) is not bool:
        raise OriginalStrategyPrimitiveError("condition switches must be boolean")
    if parameters["enabled"]:
        return {"value": source.copy()}
    return {"value": pd.Series([validity.valid(parameters["otherwise"])] * len(source),
                               index=source.index, dtype=object)}


def _fallback_value(inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    left, right = _aligned(inputs, ("left", "right"))
    return {"value": _map_binary(left, right, lambda a, b: validity.fallback(
        a, b, (validity.ValidityState.INSUFFICIENT_HISTORY,
               validity.ValidityState.MATHEMATICALLY_UNDEFINED)))}


def _abs(_parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any]) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    return {"value": _map_unary(
        source,
        lambda cell: cell if cell.state is not validity.ValidityState.VALID
        else validity.valid(abs(cell.value)),
    )}


def _fallback(inputs: abc.Mapping[str, Any], replacement: Any) -> abc.Mapping[str, Any]:
    source = _series(inputs, "source")
    accepted = (
        validity.ValidityState.INSUFFICIENT_HISTORY,
        validity.ValidityState.MATHEMATICALLY_UNDEFINED,
    )
    return {"value": _map_unary(
        source,
        lambda cell: validity.fallback(cell, validity.valid(replacement), accepted),
    )}


def _check_context(name, context):
    if context is None:
        return
    if not isinstance(context, abc.Mapping) or set(context) != {"bound_contract"}:
        raise OriginalStrategyPrimitiveError("source context must contain its bound contract")
    bound = context["bound_contract"]
    if not isinstance(bound, contracts.ResolvedNodeContract) or bound.document["component"] != {
            "component_id": f"strategy_math.{name}", "component_version": 2}:
        raise OriginalStrategyPrimitiveError("source context belongs to another component")


def _implementation(name: str):
    def implementation(parameters: abc.Mapping[str, Any], inputs: abc.Mapping[str, Any],
                       _name: str = name, *, evaluation_context=None):
        _check_context(_name, evaluation_context)
        kernels = {
            "close": _close, "value": _value, "ema_first_close": _ema,
            "rolling_stddev_population": _rolling_stddev, "lag": _lag, "abs": _abs,
            "rma_sma_seed": _rma, "nearest_rank": _nearest_rank,
            "optional_condition": _optional_condition,
        }
        if _name in kernels:
            return kernels[_name](parameters, inputs)
        if _name in ("high", "low"):
            return _field(inputs, _name)
        if _name == "true_range":
            return _true_range(inputs)
        if _name == "fallback_value":
            return _fallback_value(inputs)
        replacements = {"fallback_zero": 0.0, "fallback_false": False}
        if _name in replacements:
            return _fallback(inputs, replacements[_name])
        return _binary(_name, inputs)
    return implementation


_BOUNDARY = registry.DependencyBoundary(
    "defining_module", (abc, math, pd, validity, contracts),
)
V2_IMPLEMENTATIONS = node_contracts._freeze({
    key: registry.registered_v2_implementation(
        component=key,
        implementation=_implementation(key[0].removeprefix("strategy_math.")),
        dependency_boundary=_BOUNDARY,
    )
    for key in V2_COMPONENTS
})


_SOURCE_FIELDS = {"close": ("CLOSE",), "high": ("HIGH",), "low": ("LOW",),
                  "true_range": ("CLOSE", "HIGH", "LOW")}


def source_contract(name):
    descriptor = _SPECS[name]
    source = name in _SOURCE_FIELDS
    component = (descriptor["component_id"], descriptor["component_version"])
    fields = _SOURCE_FIELDS.get(name, ())
    rule = {"rule_id": component[0] + ".binding", "rule_version": 1}
    result = {
        "stable_node_id": component[0], "semantic_version": component[1],
        "visible_family": "TYPE_4" if source else "TYPE_2",
        "input_types": {port["port_id"]: port["type_ref"]["type_id"] + "/series"
                        for port in descriptor["ports"] if port["direction"] == "input"},
        "output_types": {"value": descriptor["ports"][-1]["type_ref"]["type_id"] + "/series"},
        "required_market_fields": sorted(field.lower() for field in fields),
        "required_resolution": {"timeframe_seconds": 1, "alignment": "BAR_CLOSE"},
        "warmup_history": 0,
        "execution_form": "RECURSIVE" if name in {"ema_first_close", "rma_sma_seed"} else "ROLLING",
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/1", "reasons": []},
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "EXPLICIT_VALIDITY", "causal_declaration": "COMPLETED_EVENT_PREFIX",
        # The existing incremental runtime re-evaluates each completed prefix.
        # No checkpoint/state-payload API is claimed by these array kernels.
        "evaluation_triggers": ["completed_bar"], "streaming_support": True, "batch_support": True,
        "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [],
        "resource_profile": {"compute_microseconds_per_event": 200000,
            "memory_bytes_upper_bound": 4194304, "history_bytes_upper_bound": 4194304,
            "state_bytes_upper_bound": 4194304, "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": 1 if source else 0, "fanout_upper_bound": MAXIMUM_OUTPUT_FANOUT},
        "reference_provenance": [node_contracts.content_address({"original-strategy-primitive": name,
            "component_version": component[1]})],
    }
    if source:
        result.update({"schema": "first-party-node-contract/2", "warmup_history": rule,
            "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
            "state_reset_policy": {"schema": "state-reset-policy/2", "reasons": []},
            "parameter_binding": {"scheme": "analytical-contract-binding/1", **rule,
                                  "parameter_names": [], "input_ports": ["frame"]}})
    return node_contracts._freeze(result)


def _source_binding(name):
    fields = _SOURCE_FIELDS[name]
    builder = contracts.binding_result

    def bind(parameters, inputs, _fields=fields, _builder=builder):
        if parameters:
            raise ValueError("market field selection has no parameters")
        return _builder(inputs, fields_by_port={"frame": _fields}, warmup_history=0,
                        output_warmup={"value": 0})

    return bind


NODE_CONTRACTS = node_contracts._freeze({key: source_contract(key[0].removeprefix("strategy_math."))
                                       for key in V2_COMPONENTS})
DATA_REQUIREMENTS = node_contracts._freeze({key: {
    "schema": "data-requirement-declaration/1", "classification": "NO_DATA", "requirements": []}
    for key in V2_COMPONENTS if key[0].removeprefix("strategy_math.") not in _SOURCE_FIELDS})
CONTRACT_BINDINGS = node_contracts._freeze({
    (f"strategy_math.{name}", 2): registry.registered_contract_binding(
        component=(f"strategy_math.{name}", 2), source_contract=source_contract(name),
        implementation=_source_binding(name),
        dependency_boundary=registry.DependencyBoundary("defining_module", (contracts.binding_result,)))
    for name in _SOURCE_FIELDS
})


__all__ = [
    "BOOLEAN", "FLOAT", "MARKET_FRAME", "CONTRACT_BINDINGS",
    "DATA_REQUIREMENTS", "NODE_CONTRACTS", "V2_COMPONENTS",
    "V2_IMPLEMENTATIONS", "V2_TYPES",
]
