"""
`expanding_z_v4`, expressed as a Component IR graph.

RFC 0001 Appendix A.1 expresses this strategy as an abbreviated sketch and calls
the result Gate 1. This module is the same strategy as a **real artefact**: it
validates under §3, resolves under §4, evaluates under the runtime, and its four
boolean outputs are asserted equal to `ExpandingZImpulseV4.compute()` bar for
bar on real candle data (`tests/test_ir_strategy_parity.py`).

**The kernels do not re-implement the strategy.** Each one calls the function in
`app/strategy/registry/expanding_z_v4.py` that `compute()` calls. Writing the
arithmetic again here would be two hand-written implementations of one idea —
the `candles.py` defect, which is the recorded reason C12 exists — and the
parity test would then be measuring a copy against its original rather than
measuring whether the IR can express the composition. What is under test here is
the *language*: whether the strategy's structure survives being written as
components, references, overrides and edges.

**Two findings fell out of writing it:**

1. *A derived parameter is a missing component, not a missing language feature.*
   `exit_abs`'s floor and fallback are `min_abs_z * 0.25` and `min_abs_z * 0.50`
   in the strategy. F10 says an override carries a value only, so at first this
   graph carried the literals `0.15` and `0.30` — correct for the shipped
   `min_abs_z = 0.60` and silently wrong the moment anyone changed it. The
   resolution was not to weaken F10, which is what protects a component author's
   constraints. It was that **a multiplication is a computation, and C14 says
   components compute**: `value.scalar` puts the parameter on a wire and
   `math.scale` derives from it, so the two thresholds now track `min_abs_z`
   instead of remembering one of its values. This is also the first thing in the
   platform to use F7's `scalar` structure axis, which until now was declared
   and never exercised.
2. *`indicator.atr.wilder`'s body is a graph, and the strategy proves it pays.*
   The ATR here is A.2's decomposition — true range into a Wilder smoothing —
   not a leaf. Forking it to an EMA smoothing is a component-reference change,
   which is the Generation-2 property the current block library cannot express
   at all (`_atr` is a private helper with no public identity).
"""
from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import inspect
import math
import pandas as pd

from app.ir.hashing import content_address
from app.ir.causal import (
    BoundTerm, HistoryBound, RecursiveStateContract, causal_contract,
)
from app.ir.registry import DependencyBoundary, registered_kernel
from app.ir.resolve import BOUNDARY_INPUT, BOUNDARY_OUTPUT, Library
from app.strategy.registry.expanding_z_v4 import (
    ExpandingZImpulseV4,
    _as_bool,
    _rma,
    adaptive_threshold,
    directional_entry,
    displacement_lost,
    drift_score,
    impulse,
    range_in_atr,
    zscore,
)

FORMAT_VERSION = 1

BAR = {"instrument": "NIFTY", "timeframe": "15m"}


# ── artefact construction helpers ─────────────────────────────────────────

def _wire(value="float", structure="series"):
    return {"value": value, "structure": structure, "domain": dict(BAR)}


def _socket(identifier, direction, value="float", structure="series"):
    return {"item": "socket", "identifier": identifier, "display_name": identifier,
            "direction": direction, "wire_type": _wire(value, structure)}


def _param(identifier, kind, default):
    return {"item": "parameter", "identifier": identifier, "display_name": identifier,
            "kind": kind, "default": default}


def _component(identifier, interface, seed=None):
    return {
        "format_version": FORMAT_VERSION, "kind": "component",
        "identifier": identifier, "version": 1, "display_name": identifier,
        "interface": interface,
        "body": {"body": "kernel", "ref": content_address(seed or identifier)},
    }


def _node(instance, identifier, **overrides):
    return {"instance_id": instance,
            "component": {"identifier": identifier, "version": 1},
            "overrides": overrides}


def _edge(src_instance, src_socket, tgt_instance, tgt_socket):
    return {"source": {"instance": src_instance, "socket": src_socket},
            "target": {"instance": tgt_instance, "socket": tgt_socket}}


def _boundary(instance, identifier):
    return {"instance_id": instance,
            "component": {"identifier": identifier, "version": 1}, "overrides": {}}


# ── the component library ─────────────────────────────────────────────────

EMA = _component("indicator.ema", [
    _socket("source", "input"), _param("length", "length", 50), _socket("out", "output"),
])

TRUE_RANGE = _component("indicator.true_range", [
    _socket("high", "input"), _socket("low", "input"), _socket("close", "input"),
    _socket("out", "output"),
])

WILDER = _component("smoothing.wilder", [
    _socket("in", "input"), _param("length", "length", 14), _socket("out", "output"),
])

# A.2 — the ATR whose body is a graph, so a fork is a reference change.
ATR_BODY = {
    "format_version": FORMAT_VERSION, "kind": "graph",
    "identifier": "indicator.atr.wilder.body", "version": 1,
    "display_name": "ATR (Wilder) body",
    "interface": [
        _socket("high", "input"), _socket("low", "input"), _socket("close", "input"),
        _param("length", "length", 14), _socket("atr", "output"),
    ],
    "nodes": [
        _boundary("io_in", BOUNDARY_INPUT),
        _node("n_tr", "indicator.true_range"),
        _node("n_smooth", "smoothing.wilder", length={"param_ref": "length"}),
        _boundary("io_out", BOUNDARY_OUTPUT),
    ],
    "edges": [
        _edge("io_in", "high", "n_tr", "high"),
        _edge("io_in", "low", "n_tr", "low"),
        _edge("io_in", "close", "n_tr", "close"),
        _edge("n_tr", "out", "n_smooth", "in"),
        _edge("n_smooth", "out", "io_out", "atr"),
    ],
    "groups": [],
}

ATR = {
    "format_version": FORMAT_VERSION, "kind": "component",
    "identifier": "indicator.atr.wilder", "version": 1, "display_name": "ATR (Wilder)",
    "interface": ATR_BODY["interface"],
    "body": {"body": "graph", "ref": content_address(ATR_BODY)},
}

ZSCORE = _component("indicator.zscore", [
    _socket("close", "input"), _socket("reference", "input"),
    _param("length", "length", 50), _socket("out", "output"),
])

ABS = _component("math.abs", [_socket("in", "input"), _socket("out", "output")])

# `floor` and `fallback` are scalar *sockets*, not parameters, and that is the
# whole point. In the strategy they are `min_abs_z` and `min_abs_z * 0.25` —
# one parameter and a derivation from it. F10 says an override carries a value
# only, so a derivation cannot live in an override; it lives where derivations
# belong, in a component. See VALUE and SCALE below.
ADAPTIVE = _component("indicator.adaptive_threshold", [
    _socket("in", "input"),
    _param("length", "length", 200), _param("pct", "pct", 65.0),
    _socket("floor", "input", structure="scalar"),
    _socket("fallback", "input", structure="scalar"),
    _socket("out", "output"),
])

# A parameter, as a value on a wire. The override is a `param_ref`, so this is
# how an enclosing graph's parameter reaches something that composes it.
VALUE = _component("value.scalar", [
    _param("value", "thr", 0.0),
    _socket("out", "output", structure="scalar"),
])

# The missing component. `min_abs_z * 0.25` is a computation, and C14's
# division of labour says components compute — so it is a node, wired, visible
# and forkable, rather than a literal typed into an override with a comment
# explaining which parameter it was supposed to track.
SCALE = _component("math.scale", [
    _socket("in", "input", structure="scalar"),
    _param("factor", "mult", 1.0),
    _socket("out", "output", structure="scalar"),
])

DRIFT = _component("indicator.drift_atr", [
    _socket("reference", "input"), _socket("atr", "input"),
    _param("lookback", "length", 5), _socket("out", "output"),
])

RANGE_ATR = _component("indicator.range_atr", [
    _socket("high", "input"), _socket("low", "input"), _socket("atr", "input"),
    _socket("out", "output"),
])

LE = _component("predicate.le", [
    _socket("in", "input"), _param("threshold", "mult", 2.75),
    _socket("out", "output", value="bool"),
])

IMPULSE = _component("predicate.expanding_impulse", [
    _socket("abs_z", "input"), _socket("threshold", "input"),
    _param("require_expansion", "bool", True),
    _param("allow_reexpansion", "bool", True),
    _socket("out", "output", value="bool"),
])

ENTRY = _component("predicate.directional_entry", [
    _socket("signal_bar_ok", "input", value="bool"),
    _socket("impulse", "input", value="bool"),
    _socket("z", "input"), _socket("drift", "input"),
    _param("min_drift_atr", "mult", 0.08),
    _param("direction", "choice", "long"),
    _socket("out", "output", value="bool"),
])

EXIT = _component("predicate.displacement_lost", [
    _socket("drift", "input"), _socket("close", "input"), _socket("reference", "input"),
    _socket("abs_z", "input"), _socket("exit_threshold", "input"), _socket("z", "input"),
    _param("direction", "choice", "long"),
    _param("exit_on_drift_flip", "bool", True),
    _param("exit_on_ema_cross", "bool", True),
    _param("use_absz_contraction_exit", "bool", False),
    _socket("out", "output", value="bool"),
])

COMPONENTS = [EMA, TRUE_RANGE, WILDER, ATR, ZSCORE, ABS, ADAPTIVE, VALUE, SCALE,
              DRIFT, RANGE_ATR, LE, IMPULSE, ENTRY, EXIT]


# ── the strategy graph ────────────────────────────────────────────────────
#
# The defaults below are `ExpandingZImpulseV4.default_params`, and the parity
# test asserts that rather than trusting this comment.

D = ExpandingZImpulseV4.default_params

GRAPH: dict[str, Any] = {
    "format_version": FORMAT_VERSION, "kind": "graph",
    "identifier": "strategy.expanding_z_impulse", "version": 4,
    "display_name": "Expanding Z Impulse V4",
    "interface": [
        _socket("high", "input"), _socket("low", "input"), _socket("close", "input"),
        {"item": "panel", "identifier": "trend", "display_name": "Trend", "items": [
            _param("ema_length", "length", D["ema_length"]),
            _param("slope_lookback", "length", D["slope_lookback"]),
        ]},
        {"item": "panel", "identifier": "zscore", "display_name": "Z-Score", "items": [
            _param("z_length", "length", D["z_length"]),
            _param("adapt_length", "length", D["adapt_length"]),
            _param("entry_pct", "pct", D["entry_pct"]),
            _param("exit_pct", "pct", D["exit_pct"]),
            _param("min_abs_z", "thr", D["min_abs_z"]),
        ]},
        {"item": "panel", "identifier": "volatility", "display_name": "Volatility",
         "items": [
             _param("atr_length", "length", D["atr_length"]),
             _param("min_drift_atr", "mult", D["min_drift_atr"]),
             _param("max_signal_atr", "mult", D["max_signal_atr"]),
         ]},
        {"item": "panel", "identifier": "behaviour", "display_name": "Behaviour", "items": [
            _param("require_expansion", "bool", D["require_expansion"]),
            _param("allow_reexpansion", "bool", D["allow_reexpansion"]),
            _param("use_absz_contraction_exit", "bool", D["use_absz_contraction_exit"]),
            _param("exit_on_drift_flip", "bool", D["exit_on_drift_flip"]),
            _param("exit_on_ema_cross", "bool", D["exit_on_ema_cross"]),
        ]},
        _socket("longEntry", "output", value="bool"),
        _socket("shortEntry", "output", value="bool"),
        _socket("longExit", "output", value="bool"),
        _socket("shortExit", "output", value="bool"),
    ],
    "nodes": [
        _boundary("io_in", BOUNDARY_INPUT),
        _node("n_ema", "indicator.ema", length={"param_ref": "ema_length"}),
        _node("n_atr", "indicator.atr.wilder", length={"param_ref": "atr_length"}),
        _node("n_z", "indicator.zscore", length={"param_ref": "z_length"}),
        _node("n_absz", "math.abs"),
        # `min_abs_z` on a wire, and its two derivations as nodes. The exit
        # threshold's floor and fallback now *track* the parameter instead of
        # being literals that happen to match today's value of it.
        _node("n_min_abs_z", "value.scalar", value={"param_ref": "min_abs_z"}),
        _node("n_exit_floor", "math.scale", factor=0.25),
        _node("n_exit_fallback", "math.scale", factor=0.50),
        # Two instances of one definition at two percentiles — A.4's shape, in
        # the strategy the platform actually trades.
        _node("n_entry_thr", "indicator.adaptive_threshold",
              length={"param_ref": "adapt_length"}, pct={"param_ref": "entry_pct"}),
        _node("n_exit_thr", "indicator.adaptive_threshold",
              length={"param_ref": "adapt_length"}, pct={"param_ref": "exit_pct"}),
        _node("n_drift", "indicator.drift_atr", lookback={"param_ref": "slope_lookback"}),
        _node("n_range", "indicator.range_atr"),
        _node("n_signal_ok", "predicate.le", threshold={"param_ref": "max_signal_atr"}),
        _node("n_impulse", "predicate.expanding_impulse",
              require_expansion={"param_ref": "require_expansion"},
              allow_reexpansion={"param_ref": "allow_reexpansion"}),
        _node("n_long_entry", "predicate.directional_entry", direction="long",
              min_drift_atr={"param_ref": "min_drift_atr"}),
        _node("n_short_entry", "predicate.directional_entry", direction="short",
              min_drift_atr={"param_ref": "min_drift_atr"}),
        _node("n_long_exit", "predicate.displacement_lost", direction="long",
              exit_on_drift_flip={"param_ref": "exit_on_drift_flip"},
              exit_on_ema_cross={"param_ref": "exit_on_ema_cross"},
              use_absz_contraction_exit={"param_ref": "use_absz_contraction_exit"}),
        _node("n_short_exit", "predicate.displacement_lost", direction="short",
              exit_on_drift_flip={"param_ref": "exit_on_drift_flip"},
              exit_on_ema_cross={"param_ref": "exit_on_ema_cross"},
              use_absz_contraction_exit={"param_ref": "use_absz_contraction_exit"}),
        _boundary("io_out", BOUNDARY_OUTPUT),
    ],
    "edges": [
        _edge("io_in", "close", "n_ema", "source"),
        _edge("io_in", "high", "n_atr", "high"),
        _edge("io_in", "low", "n_atr", "low"),
        _edge("io_in", "close", "n_atr", "close"),

        _edge("io_in", "close", "n_z", "close"),
        _edge("n_ema", "out", "n_z", "reference"),
        _edge("n_z", "out", "n_absz", "in"),
        _edge("n_absz", "out", "n_entry_thr", "in"),
        _edge("n_absz", "out", "n_exit_thr", "in"),

        _edge("n_min_abs_z", "out", "n_entry_thr", "floor"),
        _edge("n_min_abs_z", "out", "n_entry_thr", "fallback"),
        _edge("n_min_abs_z", "out", "n_exit_floor", "in"),
        _edge("n_min_abs_z", "out", "n_exit_fallback", "in"),
        _edge("n_exit_floor", "out", "n_exit_thr", "floor"),
        _edge("n_exit_fallback", "out", "n_exit_thr", "fallback"),

        _edge("n_ema", "out", "n_drift", "reference"),
        _edge("n_atr", "atr", "n_drift", "atr"),

        _edge("io_in", "high", "n_range", "high"),
        _edge("io_in", "low", "n_range", "low"),
        _edge("n_atr", "atr", "n_range", "atr"),
        _edge("n_range", "out", "n_signal_ok", "in"),

        _edge("n_absz", "out", "n_impulse", "abs_z"),
        _edge("n_entry_thr", "out", "n_impulse", "threshold"),

        _edge("n_signal_ok", "out", "n_long_entry", "signal_bar_ok"),
        _edge("n_impulse", "out", "n_long_entry", "impulse"),
        _edge("n_z", "out", "n_long_entry", "z"),
        _edge("n_drift", "out", "n_long_entry", "drift"),

        _edge("n_signal_ok", "out", "n_short_entry", "signal_bar_ok"),
        _edge("n_impulse", "out", "n_short_entry", "impulse"),
        _edge("n_z", "out", "n_short_entry", "z"),
        _edge("n_drift", "out", "n_short_entry", "drift"),

        _edge("n_drift", "out", "n_long_exit", "drift"),
        _edge("io_in", "close", "n_long_exit", "close"),
        _edge("n_ema", "out", "n_long_exit", "reference"),
        _edge("n_absz", "out", "n_long_exit", "abs_z"),
        _edge("n_exit_thr", "out", "n_long_exit", "exit_threshold"),
        _edge("n_z", "out", "n_long_exit", "z"),

        _edge("n_drift", "out", "n_short_exit", "drift"),
        _edge("io_in", "close", "n_short_exit", "close"),
        _edge("n_ema", "out", "n_short_exit", "reference"),
        _edge("n_absz", "out", "n_short_exit", "abs_z"),
        _edge("n_exit_thr", "out", "n_short_exit", "exit_threshold"),
        _edge("n_z", "out", "n_short_exit", "z"),

        _edge("n_long_entry", "out", "io_out", "longEntry"),
        _edge("n_short_entry", "out", "io_out", "shortEntry"),
        _edge("n_long_exit", "out", "io_out", "longExit"),
        _edge("n_short_exit", "out", "io_out", "shortExit"),
    ],
    "groups": [],
}


# ── the kernels: bound to the strategy's own functions, never rewritten ───

def _k_ema(params, inputs, context_inputs):
    return {"out": inputs["source"].ewm(span=params["length"], adjust=False).mean()}


def _k_true_range(params, inputs, context_inputs):
    prev = inputs["close"].shift(1)
    return {"out": pd.concat([(inputs["high"] - inputs["low"]).abs(),
                              (inputs["high"] - prev).abs(),
                              (inputs["low"] - prev).abs()], axis=1).max(axis=1)}


def _k_wilder(params, inputs, context_inputs):
    return {"out": _rma(inputs["in"], params["length"])}


def _k_zscore(params, inputs, context_inputs):
    return {"out": zscore(inputs["close"], inputs["reference"], params["length"])}


def _k_abs(params, inputs, context_inputs):
    return {"out": inputs["in"].abs()}


def _k_adaptive(params, inputs, context_inputs):
    return {"out": adaptive_threshold(inputs["in"], params["length"], params["pct"],
                                      inputs["floor"], inputs["fallback"])}


def _k_value(params, inputs, context_inputs):
    return {"out": params["value"]}


def _k_scale(params, inputs, context_inputs):
    return {"out": inputs["in"] * params["factor"]}


def _k_drift(params, inputs, context_inputs):
    return {"out": drift_score(inputs["reference"], inputs["atr"],
                               params["lookback"])}


def _k_range_atr(params, inputs, context_inputs):
    return {"out": range_in_atr(inputs["high"], inputs["low"], inputs["atr"])}


def _k_le(params, inputs, context_inputs):
    return {"out": inputs["in"] <= params["threshold"]}


def _k_impulse(params, inputs, context_inputs):
    return {"out": impulse(inputs["abs_z"], inputs["threshold"],
                           params["require_expansion"],
                           params["allow_reexpansion"])}


def _k_entry(params, inputs, context_inputs):
    return {"out": _as_bool(directional_entry(
        inputs["signal_bar_ok"], inputs["impulse"], inputs["z"], inputs["drift"],
        params["min_drift_atr"], params["direction"]))}


def _k_exit(params, inputs, context_inputs):
    return {"out": _as_bool(displacement_lost(
        inputs["drift"], inputs["close"], inputs["reference"], inputs["abs_z"],
        inputs["exit_threshold"], inputs["z"], params["direction"],
        params["exit_on_drift_flip"], params["exit_on_ema_cross"],
        params["use_absz_contraction_exit"]))}


IMPLEMENTATIONS = {
    EMA["body"]["ref"]: _k_ema,
    TRUE_RANGE["body"]["ref"]: _k_true_range,
    WILDER["body"]["ref"]: _k_wilder,
    ZSCORE["body"]["ref"]: _k_zscore,
    ABS["body"]["ref"]: _k_abs,
    ADAPTIVE["body"]["ref"]: _k_adaptive,
    VALUE["body"]["ref"]: _k_value,
    SCALE["body"]["ref"]: _k_scale,
    DRIFT["body"]["ref"]: _k_drift,
    RANGE_ATR["body"]["ref"]: _k_range_atr,
    LE["body"]["ref"]: _k_le,
    IMPULSE["body"]["ref"]: _k_impulse,
    ENTRY["body"]["ref"]: _k_entry,
    EXIT["body"]["ref"]: _k_exit,
}


@dataclass(frozen=True)
class _SmoothState:
    value: float | None = None
    missing_bars: int = 0
    observations: int = 0
    old_weight: float = 1.0


def _smooth_initializer(params):
    return _SmoothState()


def _smooth_encoder(state):
    return {"value": state.value, "missing_bars": state.missing_bars,
            "observations": state.observations, "old_weight": state.old_weight}


def _ewm_state_update(state, current, alpha):
    """Match pandas ``ewm(adjust=False, ignore_na=False)`` transition order."""
    if state.value is None:
        return state if pd.isna(current) else _SmoothState(float(current), 0, 1, 1.0)
    old_weight = state.old_weight * (1.0 - alpha)
    if pd.isna(current):
        return _SmoothState(
            state.value, state.missing_bars + 1, state.observations, old_weight)
    current = float(current)
    if state.value != current:
        # pandas' Cython implementation contracts the weighted multiply-add;
        # preserving that operation makes the recursive stream byte-identical.
        new_weight = 1.0 - old_weight if alpha == 0.5 else alpha
        value = math.fma(old_weight, state.value, new_weight * current)
        value /= old_weight + new_weight
    else:
        value = state.value
    return _SmoothState(value, 0, state.observations + 1, 1.0)


def _ema_state_update(state, params, inputs, context):
    current = float(inputs["source"])
    alpha = 2.0 / (int(params["length"]) + 1.0)
    return _ewm_state_update(state, current, alpha)


def _wilder_state_update(state, params, inputs, context):
    current = float(inputs["in"])
    alpha = 1.0 / int(params["length"])
    return _ewm_state_update(state, current, alpha)


def _smooth_step(state, params, inputs, context):
    return {"out": state.value}


def _wilder_step(state, params, inputs, context):
    return {"out": state.value if state.observations >= int(params["length"]) else None}


def _bounded(*sockets, constant=0, terms=()):
    return causal_contract(
        node_input_sockets=tuple(sockets),
        history=HistoryBound("bounded", constant=constant, terms=terms),
    )


def _recursive(sockets, update, step=_smooth_step):
    return causal_contract(
        node_input_sockets=tuple(sockets),
        history=HistoryBound("causal_recursive", terms=(BoundTerm("length"),)),
        recursive_state=RecursiveStateContract(
            _smooth_initializer, _SmoothState, _smooth_encoder, update, step),
    )


_CAUSAL = {
    EMA["body"]["ref"]: _recursive(("source",), _ema_state_update),
    TRUE_RANGE["body"]["ref"]: _bounded("high", "low", "close", constant=2),
    WILDER["body"]["ref"]: _recursive(("in",), _wilder_state_update, _wilder_step),
    ZSCORE["body"]["ref"]: _bounded(
        "close", "reference", terms=(BoundTerm("length"),)),
    ABS["body"]["ref"]: _bounded("in"),
    ADAPTIVE["body"]["ref"]: _bounded(
        "in", "floor", "fallback", terms=(BoundTerm("length"),)),
    VALUE["body"]["ref"]: _bounded(),
    SCALE["body"]["ref"]: _bounded("in"),
    DRIFT["body"]["ref"]: _bounded(
        "reference", "atr", constant=1, terms=(BoundTerm("lookback"),)),
    RANGE_ATR["body"]["ref"]: _bounded("high", "low", "atr"),
    LE["body"]["ref"]: _bounded("in"),
    IMPULSE["body"]["ref"]: _bounded("abs_z", "threshold", constant=3),
    ENTRY["body"]["ref"]: _bounded("signal_bar_ok", "impulse", "z", "drift"),
    EXIT["body"]["ref"]: _bounded(
        "drift", "close", "reference", "abs_z", "exit_threshold", "z"),
}

# C10 — warmup per component, composed by resolution.
#
# Every one of these is a function of the node's *bound* parameters, not of the
# component's default. It was written with the defaults first, and that was
# wrong in a way nothing would have reported: a node overriding `length` to 200
# would still have claimed it warmed up in 50 bars, and a backtest would have
# read 150 bars of an unwarmed indicator and looked entirely plausible.
_KERNEL_FIELDS = {
    EMA["body"]["ref"]: {"warmup": lambda p: p["length"], "causal": _CAUSAL[EMA["body"]["ref"]]},
    TRUE_RANGE["body"]["ref"]: {"warmup": 1, "causal": _CAUSAL[TRUE_RANGE["body"]["ref"]]},
    WILDER["body"]["ref"]: {"warmup": lambda p: p["length"], "causal": _CAUSAL[WILDER["body"]["ref"]]},
    ZSCORE["body"]["ref"]: {"warmup": lambda p: p["length"], "causal": _CAUSAL[ZSCORE["body"]["ref"]]},
    ABS["body"]["ref"]: {"causal": _CAUSAL[ABS["body"]["ref"]]},
    ADAPTIVE["body"]["ref"]: {"warmup": lambda p: p["length"], "causal": _CAUSAL[ADAPTIVE["body"]["ref"]]},
    VALUE["body"]["ref"]: {"causal": _CAUSAL[VALUE["body"]["ref"]]},
    SCALE["body"]["ref"]: {"causal": _CAUSAL[SCALE["body"]["ref"]]},
    DRIFT["body"]["ref"]: {"warmup": lambda p: p["lookback"], "causal": _CAUSAL[DRIFT["body"]["ref"]]},
    RANGE_ATR["body"]["ref"]: {"causal": _CAUSAL[RANGE_ATR["body"]["ref"]]},
    LE["body"]["ref"]: {"causal": _CAUSAL[LE["body"]["ref"]]},
    # Needs the current bar and the two before it (absZ[1], absZ[2]).
    IMPULSE["body"]["ref"]: {"warmup": 2, "causal": _CAUSAL[IMPULSE["body"]["ref"]]},
    ENTRY["body"]["ref"]: {"causal": _CAUSAL[ENTRY["body"]["ref"]]},
    EXIT["body"]["ref"]: {"causal": _CAUSAL[EXIT["body"]["ref"]]},
}


def _external_dependencies(implementation, recursive_state):
    """Derive external helpers/modules; identity independently checks exact equality."""
    roots = [implementation]
    if recursive_state is not None:
        roots.extend((recursive_state.initializer, recursive_state.state_type,
                      recursive_state.state_encoder, recursive_state.update,
                      recursive_state.step))
    found: dict[int, object] = {}
    seen: set[int] = set()

    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if inspect.ismodule(value):
            found[id(value)] = value
            return
        if inspect.isfunction(value):
            closure = inspect.getclosurevars(value)
            for dependency in (*closure.globals.values(), *closure.nonlocals.values()):
                if inspect.ismodule(dependency):
                    found[id(dependency)] = dependency
                elif inspect.isfunction(dependency) or inspect.isclass(dependency):
                    if getattr(dependency, "__module__", None) == __name__:
                        visit(dependency)
                    elif inspect.isfunction(dependency):
                        found[id(dependency)] = dependency
                        visit(dependency)
                    elif getattr(dependency, "__module__", None) not in {
                            "builtins", "dataclasses"}:
                        found[id(dependency)] = dependency
            return
        if inspect.isclass(value) and getattr(value, "__module__", None) == __name__:
            for member in vars(value).values():
                raw = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
                if inspect.isfunction(raw):
                    visit(raw)

    for root in roots:
        visit(root)
    return tuple(sorted(found.values(), key=lambda item: (
        getattr(item, "__module__", ""),
        getattr(item, "__qualname__", getattr(item, "__name__", "")),
    )))


REGISTRATIONS = {}
for _ref, _implementation in IMPLEMENTATIONS.items():
    _fields = _KERNEL_FIELDS[_ref]
    _causal = _fields["causal"]
    REGISTRATIONS[_ref] = registered_kernel(
        body_ref=_ref,
        implementation=_implementation,
        causal=_causal,
        dependency_boundary=DependencyBoundary(
            "defining_module",
            _external_dependencies(_implementation, _causal.recursive_state)),
        warmup=_fields.get("warmup", 0),
    )

KERNELS = {ref: registration.spec for ref, registration in REGISTRATIONS.items()}

LIBRARY = Library(
    components={(c["identifier"], c["version"]): c for c in COMPONENTS},
    bodies={ATR["body"]["ref"]: ATR_BODY},
    kernels=KERNELS,
)

assert set(REGISTRATIONS) == {
    component["body"]["ref"] for component in COMPONENTS
    if component["body"]["body"] == "kernel"
}
