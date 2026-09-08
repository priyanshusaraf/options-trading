"""Immutable Component IR v2 templates for the user's original strategies."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from app.ir import node_contracts
from app.ir.first_party import original_strategy_primitives as primitives


V3_PRESET_ID = "trend_impulse_v3"
V4_PRESET_ID = "expanding_z_v4"
_V3_COMPONENT = ("strategy.trend_impulse_v3", 1)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _primitive(name: str) -> Mapping[str, Any]:
    version = 2 if name in {"close", "high", "low", "true_range"} else 1
    return primitives.V2_COMPONENTS[(f"strategy_math.{name}", version)]


def _port(component: Mapping[str, Any], port_id: str) -> dict[str, Any]:
    return _plain(next(port for port in component["ports"] if port["port_id"] == port_id))


def _node(node_id: str, name: str, **parameters: Any) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "component": {"component_id": f"strategy_math.{name}",
                      "component_version": _primitive(name)["component_version"]},
        "parameters": parameters,
    }


def _edge(edge_id: str, source: str, source_port: str,
          target: str, target_port: str) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "source": ({"scope": "graph_input", "port_id": source_port}
                   if source == "$input" else
                   {"scope": "node", "node_id": source, "port_id": source_port}),
        "target": ({"scope": "graph_output", "port_id": target_port}
                   if target == "$output" else
                   {"scope": "node", "node_id": target, "port_id": target_port}),
        "binding": {"kind": "single"},
    }


def _binary_edges(node: str, left: str, right: str) -> list[dict[str, Any]]:
    return [
        _edge(f"{node}.left", left, "value", node, "left"),
        _edge(f"{node}.right", right, "value", node, "right"),
    ]


def _unary_edge(node: str, source: str) -> dict[str, Any]:
    return _edge(f"{node}.source", source, "value", node, "source")


def _v3_body() -> dict[str, Any]:
    frame_port = _port(_primitive("close"), "frame")
    bool_port = _port(_primitive("and"), "value")
    outputs = [{**bool_port, "port_id": name, "semantic_role": role} for name, role in (
        ("longEntry", "research_long_entry"), ("shortEntry", "research_short_entry"),
        ("longExit", "research_long_exit"), ("shortExit", "research_short_exit"))]
    nodes = [
        _node("close", "close"),
        _node("ema", "ema_first_close"),
        _node("std", "rolling_stddev_population"),
        _node("numerator", "subtract"),
        _node("raw_z", "divide"),
        _node("z", "fallback_zero"),
        _node("ema_prev", "lag"),
        _node("slope", "subtract"),
        _node("zero", "value", value=0.0),
        _node("entry", "value"),
        _node("negative_entry", "subtract"),
        _node("bull", "gt"), _node("bear", "lt"),
        _node("z_prev", "lag", length=1),
        _node("abs_z", "abs"), _node("abs_z_prev", "abs"),
        _node("long_prev_below", "lt"), _node("long_above", "gt"),
        _node("long_expanding", "gt"),
        _node("long_a", "and"), _node("long_b", "and"), _node("long_raw", "and"),
        _node("short_prev_above", "gt"), _node("short_below", "lt"),
        _node("short_expanding", "gt"),
        _node("short_a", "and"), _node("short_b", "and"), _node("short_raw", "and"),
        _node("z_negative", "lt"), _node("z_positive", "gt"),
        _node("long_exit_raw", "or"), _node("short_exit_raw", "or"),
        _node("longEntry", "fallback_false"),
        _node("shortEntry", "fallback_false"),
        _node("longExit", "fallback_false"),
        _node("shortExit", "fallback_false"),
    ]
    edges = [
        _edge("frame.close", "$input", "frame", "close", "frame"),
        _unary_edge("ema", "close"), _unary_edge("std", "close"),
        *_binary_edges("numerator", "close", "ema"),
        *_binary_edges("raw_z", "numerator", "std"),
        _unary_edge("z", "raw_z"), _unary_edge("ema_prev", "ema"),
        *_binary_edges("slope", "ema", "ema_prev"),
        _edge("zero.alignment", "close", "value", "zero", "alignment"),
        _edge("entry.alignment", "close", "value", "entry", "alignment"),
        *_binary_edges("negative_entry", "zero", "entry"),
        *_binary_edges("bull", "slope", "zero"), *_binary_edges("bear", "slope", "zero"),
        _unary_edge("z_prev", "z"), _unary_edge("abs_z", "z"),
        _unary_edge("abs_z_prev", "z_prev"),
        *_binary_edges("long_prev_below", "z_prev", "entry"),
        *_binary_edges("long_above", "z", "entry"),
        *_binary_edges("long_expanding", "z", "z_prev"),
        *_binary_edges("long_a", "bull", "long_prev_below"),
        *_binary_edges("long_b", "long_a", "long_above"),
        *_binary_edges("long_raw", "long_b", "long_expanding"),
        *_binary_edges("short_prev_above", "z_prev", "negative_entry"),
        *_binary_edges("short_below", "z", "negative_entry"),
        *_binary_edges("short_expanding", "abs_z", "abs_z_prev"),
        *_binary_edges("short_a", "bear", "short_prev_above"),
        *_binary_edges("short_b", "short_a", "short_below"),
        *_binary_edges("short_raw", "short_b", "short_expanding"),
        *_binary_edges("z_negative", "z", "zero"),
        *_binary_edges("z_positive", "z", "zero"),
        *_binary_edges("long_exit_raw", "z_negative", "bear"),
        *_binary_edges("short_exit_raw", "z_positive", "bull"),
        _unary_edge("longEntry", "long_raw"),
        _unary_edge("shortEntry", "short_raw"),
        _unary_edge("longExit", "long_exit_raw"),
        _unary_edge("shortExit", "short_exit_raw"),
        *(_edge(f"output.{name}", name, "value", "$output", name) for name in (
            "longEntry", "shortEntry", "longExit", "shortExit")),
    ]
    return {"graph_inputs": [frame_port], "graph_outputs": outputs,
            "nodes": nodes, "edges": edges}


def _parameter(name: str) -> dict[str, Any]:
    component_name, parameter = {
        "ema_length": ("ema_first_close", "length"),
        "z_length": ("rolling_stddev_population", "length"),
        "slope_lookback": ("lag", "length"),
        "entry_z": ("value", "value"),
    }[name]
    return _plain(_primitive(component_name)["parameters"][parameter])


_V3_PARAMETERS = {name: _parameter(name) for name in (
    "ema_length", "z_length", "slope_lookback", "entry_z")}
_V3_BODY = _v3_body()
_V3_DESCRIPTOR = {
    "component_id": _V3_COMPONENT[0], "component_version": _V3_COMPONENT[1],
    "domain_family": "signal", "structural_role": "decision",
    "ports": [*_V3_BODY["graph_inputs"], *_V3_BODY["graph_outputs"]],
    "parameters": _V3_PARAMETERS,
    "compound": {
        "body": _V3_BODY,
        "parameter_bindings": [
            {"parameter_id": "ema_length", "targets": [
                {"node_id": "ema", "parameter_id": "length"}]},
            {"parameter_id": "z_length", "targets": [
                {"node_id": "std", "parameter_id": "length"}]},
            {"parameter_id": "slope_lookback", "targets": [
                {"node_id": "ema_prev", "parameter_id": "length"}]},
            {"parameter_id": "entry_z", "targets": [
                {"node_id": "entry", "parameter_id": "value"}]},
        ],
    },
}

def _v4_body() -> dict[str, Any]:
    nodes = [_node(name, name) for name in ("close", "high", "low", "true_range")]
    edges = [_edge(f"frame.{name}", "$input", "frame", name, "frame")
             for name in ("close", "high", "low", "true_range")]
    unary = [
        ("ema", "ema_first_close", "close", {}),
        ("std", "rolling_stddev_population", "spread", {}),
        ("z", "fallback_zero", "raw_z", {}), ("abs_z", "abs", "z", {}),
        ("atr", "rma_sma_seed", "true_range", {}),
        ("ema_prev", "lag", "ema", {}),
        ("drift", "fallback_zero", "raw_drift", {}),
        ("range_atr", "fallback_zero", "raw_range", {}),
        ("entry_rank", "nearest_rank", "abs_z", {}),
        ("exit_rank", "nearest_rank", "abs_z", {}),
        ("entry_prior", "lag", "entry_rank", {"length": 1}),
        ("exit_prior", "lag", "exit_rank", {"length": 1}),
        ("abs_prev", "lag", "abs_z", {"length": 1}),
        ("abs_prev2", "lag", "abs_z", {"length": 2}),
        ("entry_prev", "lag", "entry_abs", {"length": 1}),
        ("reexpansion_enabled", "optional_condition", "reexpansion", {"otherwise": False}),
        ("expansion_required", "optional_condition", "expanding", {"otherwise": True}),
    ]
    binary = [
        ("spread", "subtract", "close", "ema"),
        ("raw_z", "divide", "spread", "std"),
        ("slope", "subtract", "ema", "ema_prev"),
        ("raw_drift", "divide", "slope", "atr"),
        ("bar_range", "subtract", "high", "low"),
        ("raw_range", "divide", "bar_range", "atr"),
        ("signal_ok", "le", "range_atr", "max_signal_atr"),
        ("entry_fallback", "fallback_value", "entry_prior", "min_abs_z"),
        ("entry_abs", "maximum", "entry_fallback", "min_abs_z"),
        ("exit_floor", "multiply", "min_abs_z", "quarter"),
        ("exit_default", "multiply", "min_abs_z", "half"),
        ("exit_fallback", "fallback_value", "exit_prior", "exit_default"),
        ("exit_abs", "maximum", "exit_fallback", "exit_floor"),
        ("expanding", "gt", "abs_z", "abs_prev"),
        ("above", "gt", "abs_z", "entry_abs"),
        ("previous_at_or_below", "le", "abs_prev", "entry_prev"),
        ("breakout", "and", "above", "previous_at_or_below"),
        ("contracted_previous", "lt", "abs_prev", "abs_prev2"),
        ("reexpansion_a", "and", "above", "expanding"),
        ("reexpansion", "and", "reexpansion_a", "contracted_previous"),
        ("impulse_raw", "or", "breakout", "reexpansion_enabled"),
        ("impulse", "and", "impulse_raw", "expansion_required"),
        ("entry_gate", "and", "signal_ok", "impulse"),
        ("negative_drift", "subtract", "zero", "min_drift_atr"),
        ("bull", "gt", "drift", "min_drift_atr"),
        ("bear", "lt", "drift", "negative_drift"),
        ("positive_z", "gt", "z", "zero"), ("negative_z", "lt", "z", "zero"),
        ("long_a", "and", "entry_gate", "positive_z"),
        ("short_a", "and", "entry_gate", "negative_z"),
        ("long_raw", "and", "long_a", "bull"),
        ("short_raw", "and", "short_a", "bear"),
        ("contracted", "lt", "abs_z", "exit_abs"),
    ]
    for side, comparison, sign in (("long", "lt", "positive_z"), ("short", "gt", "negative_z")):
        binary.extend([
            (f"{side}_drift", comparison, "drift", "zero"),
            (f"{side}_ema", comparison, "close", "ema"),
            (f"{side}_contraction", "and", "contracted", sign),
            (f"{side}_exit_a", "or", f"{side}_drift_enabled", f"{side}_ema_enabled"),
            (f"{side}_exit_raw", "or", f"{side}_exit_a", f"{side}_contraction_enabled"),
        ])
        unary.extend((f"{side}_{kind}_enabled", "optional_condition", f"{side}_{kind}",
                      {"otherwise": False}) for kind in ("drift", "ema", "contraction"))
        unary.extend([(f"{side}Entry", "fallback_false", f"{side}_raw", {}),
                      (f"{side}Exit", "fallback_false", f"{side}_exit_raw", {})])
    for identifier, operation, source, parameters in unary:
        nodes.append(_node(identifier, operation, **parameters))
        edges.append(_unary_edge(identifier, source))
    for identifier, operation, left, right in binary:
        nodes.append(_node(identifier, operation))
        edges.extend(_binary_edges(identifier, left, right))
    for identifier, parameters in (("zero", {"value": 0.0}), ("half", {"value": 0.5}),
                                   ("quarter", {"value": 0.25}), ("min_abs_z", {}),
                                   ("min_drift_atr", {}), ("max_signal_atr", {})):
        nodes.append(_node(identifier, "value", **parameters))
        edges.append(_edge(f"{identifier}.alignment", "close", "value", identifier, "alignment"))
    edges.extend(_edge(f"output.{name}", name, "value", "$output", name)
                 for name in ("longEntry", "shortEntry", "longExit", "shortExit"))
    return {"graph_inputs": _plain(_V3_BODY["graph_inputs"]),
            "graph_outputs": _plain(_V3_BODY["graph_outputs"]), "nodes": nodes, "edges": edges}


def _v4_descriptor() -> dict[str, Any]:
    body = _v4_body()
    targets = {
        "ema_length": [("ema", "length")], "z_length": [("std", "length")],
        "atr_length": [("atr", "length")], "slope_lookback": [("ema_prev", "length")],
        "adapt_length": [("entry_rank", "length"), ("exit_rank", "length")],
        "entry_pct": [("entry_rank", "percentile")], "exit_pct": [("exit_rank", "percentile")],
        "min_abs_z": [("min_abs_z", "value")], "min_drift_atr": [("min_drift_atr", "value")],
        "max_signal_atr": [("max_signal_atr", "value")],
        "require_expansion": [("expansion_required", "enabled")],
        "allow_reexpansion": [("reexpansion_enabled", "enabled")],
        "exit_on_drift_flip": [("long_drift_enabled", "enabled"), ("short_drift_enabled", "enabled")],
        "exit_on_ema_cross": [("long_ema_enabled", "enabled"), ("short_ema_enabled", "enabled")],
        "use_absz_contraction_exit": [("long_contraction_enabled", "enabled"), ("short_contraction_enabled", "enabled")],
    }
    nodes = {node["node_id"]: node for node in body["nodes"]}
    parameters = {}
    for name, bindings in targets.items():
        node_id, parameter = bindings[0]
        key = nodes[node_id]["component"]["component_id"].removeprefix("strategy_math.")
        parameters[name] = _plain(_primitive(key)["parameters"][parameter])
    return {
        "component_id": "strategy.expanding_z_v4_pine", "component_version": 1,
        "domain_family": "signal", "structural_role": "decision",
        "ports": [*body["graph_inputs"], *body["graph_outputs"]], "parameters": parameters,
        "compound": {"body": body, "parameter_bindings": [
            {"parameter_id": name, "targets": [
                {"node_id": node_id, "parameter_id": parameter} for node_id, parameter in bindings]}
            for name, bindings in targets.items()]},
    }


_V4_DESCRIPTOR = _v4_descriptor()


V2_TYPES: Mapping[tuple[str, int], Mapping[str, Any]] = MappingProxyType({})
V2_COMPONENTS = node_contracts._freeze({_V3_COMPONENT: _V3_DESCRIPTOR,
    ("strategy.expanding_z_v4_pine", 1): _V4_DESCRIPTOR})
V2_IMPLEMENTATIONS: Mapping[tuple[str, int], Mapping[str, Any]] = MappingProxyType({})
DATA_REQUIREMENTS: Mapping[tuple[str, int], Mapping[str, Any]] = MappingProxyType({})
NODE_CONTRACTS: Mapping[tuple[str, int], Mapping[str, Any]] = MappingProxyType({})
CONTRACT_BINDINGS: Mapping[tuple[str, int], Mapping[str, Any]] = MappingProxyType({})


def _template(identifier: str, name: str) -> dict[str, Any]:
    frame = _plain(_V3_BODY["graph_inputs"][0])
    outputs = _plain(_V3_BODY["graph_outputs"])
    return {
        "format_version": 2, "strategy_id": identifier, "strategy_version": 1,
        "metadata": {
            "metadata_version": 1, "name": name,
            "description": (
                "Original Trend Impulse V3. EMA uses the first close as its seed. "
                "Z divides close minus EMA by the rolling population standard deviation "
                "of close. Insufficient-history or zero standard deviation explicitly falls back "
                "to zero before the strict entry and exit rules are evaluated. Missing prices remain invalid."
            ),
            "tags": ["original", "preset", "trend-impulse-v3"],
        },
        "graph_inputs": [frame], "graph_outputs": outputs,
        "nodes": [{
            "node_id": "rules", "component": {
                "component_id": _V3_COMPONENT[0], "component_version": _V3_COMPONENT[1]},
            "parameters": {
                "ema_length": 50, "z_length": 50,
                "slope_lookback": 5, "entry_z": 1.0,
            },
        }],
        "edges": [
            _edge("preset.frame", "$input", "frame", "rules", "frame"),
            *(_edge(f"preset.{name}", "rules", name, "$output", name)
              for name in ("longEntry", "shortEntry", "longExit", "shortExit")),
        ],
    }


_V3_TEMPLATE = node_contracts._freeze(_template(V3_PRESET_ID, "Trend Impulse V3 (EMA-z)"))


def _v4_template() -> dict[str, Any]:
    document = _template(V4_PRESET_ID, "Expanding Z Impulse V4 (Pine signal rules)")
    document["metadata"]["description"] = (
        "Original Pine V4 signal rules: residual z-score, prior-bar nearest-rank thresholds, "
        "SMA-seeded Wilder ATR, and crossover with prior equality. Includes discretionary "
        "signal exits. Position sizing, position gates and ratchet stops belong to the "
        "backtest risk model and are not outputs of this signal graph."
    )
    document["metadata"]["tags"] = ["original", "preset", "pine-v5-signal-rules", "expanding-z-v4"]
    document["nodes"][0]["component"] = {
        "component_id": "strategy.expanding_z_v4_pine", "component_version": 1}
    document["nodes"][0]["parameters"] = {
        "ema_length": 50, "z_length": 50, "adapt_length": 200, "atr_length": 14,
        "slope_lookback": 5, "entry_pct": 65.0, "exit_pct": 35.0,
        "min_abs_z": 0.60, "min_drift_atr": 0.08, "max_signal_atr": 2.75,
        "require_expansion": True, "allow_reexpansion": True,
        "use_absz_contraction_exit": False, "exit_on_drift_flip": True, "exit_on_ema_cross": True,
    }
    return document


_V4_TEMPLATE = node_contracts._freeze(_v4_template())
PRESETS = MappingProxyType({V3_PRESET_ID: _V3_TEMPLATE, V4_PRESET_ID: _V4_TEMPLATE})
PRESET_PROVENANCE = node_contracts._freeze({
    V3_PRESET_ID: {"semantic_version": 1, "source": "backend/app/strategy/signals.py",
                   "source_sha256": "f323c15c0263b7dc4fe41418ea7b3927dbf83b1486170488dbe0804e320e5b01"},
    V4_PRESET_ID: {"semantic_version": 1, "source": "strategies/expanding-z-impulse-v4.pine",
                   "source_sha256": "cfe2d7c3cce1c2bff955f91c95e4389cd4401262b55a71a9736d51eaf16d97b9",
                   "scope": "signal rules; risk and position state supplied by execution consumer"},
})


def preset_summaries() -> list[dict[str, Any]]:
    return [{
        "preset_id": identifier,
        "name": template["metadata"]["name"],
        "description": template["metadata"]["description"],
        "parameters": _plain(template["nodes"][0]["parameters"]),
        "provenance": _plain(PRESET_PROVENANCE[identifier]),
        "available": True,
    } for identifier, template in PRESETS.items()]


def instantiate_preset(preset_id: str, identifier: str, name: str | None = None) -> dict[str, Any]:
    template = PRESETS.get(preset_id)
    if template is None:
        raise KeyError(preset_id)
    document = _plain(template)
    document["strategy_id"] = identifier
    document["metadata"]["tags"].append("source-sha256:" + PRESET_PROVENANCE[preset_id]["source_sha256"])
    if name is not None:
        document["metadata"]["name"] = name
    return document


__all__ = [
    "CONTRACT_BINDINGS", "DATA_REQUIREMENTS", "NODE_CONTRACTS", "PRESETS",
    "V2_COMPONENTS", "V2_IMPLEMENTATIONS", "V2_TYPES", "V3_PRESET_ID",
    "V4_PRESET_ID", "instantiate_preset", "preset_summaries",
]
