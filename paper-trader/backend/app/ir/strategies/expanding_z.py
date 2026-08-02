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

**Two findings fell out of writing it**, recorded rather than fixed:

1. *A parameter cannot be derived from another parameter.* `exit_abs`'s floor
   and fallback are `min_abs_z * 0.25` and `min_abs_z * 0.50` in the strategy.
   F10 says an override carries a value only, so the graph carries `0.15` and
   `0.30` — correct for the shipped `min_abs_z = 0.60` and silently wrong if
   someone changes it. This is not a defect in F10, which is protecting the
   component author's constraints; it is a missing component. The conforming
   expression is a `scale` component between the parameter and its consumer,
   which requires a parameter to be wirable as a value — the language admits it
   (a parameter and a scalar wire are both values) but nothing in the platform
   authors it yet.
2. *`indicator.atr.wilder`'s body is a graph, and the strategy proves it pays.*
   The ATR here is A.2's decomposition — true range into a Wilder smoothing —
   not a leaf. Forking it to an EMA smoothing is a component-reference change,
   which is the Generation-2 property the current block library cannot express
   at all (`_atr` is a private helper with no public identity).
"""
from __future__ import annotations

from typing import Any

from app.ir.hashing import content_address
from app.ir.kernels import kernel_registry
from app.ir.resolve import BOUNDARY_INPUT, BOUNDARY_OUTPUT, Library
from app.strategy.registry import expanding_z_v4 as impl

FORMAT_VERSION = 1

BAR = {"instrument": "NIFTY", "timeframe": "15m"}


# ── artefact construction helpers ─────────────────────────────────────────

def _wire(value="float"):
    return {"value": value, "structure": "series", "domain": dict(BAR)}


def _socket(identifier, direction, value="float"):
    return {"item": "socket", "identifier": identifier, "display_name": identifier,
            "direction": direction, "wire_type": _wire(value)}


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

ADAPTIVE = _component("indicator.adaptive_threshold", [
    _socket("in", "input"),
    _param("length", "length", 200), _param("pct", "pct", 65.0),
    _param("floor", "thr", 0.60), _param("fallback", "thr", 0.60),
    _socket("out", "output"),
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

COMPONENTS = [EMA, TRUE_RANGE, WILDER, ATR, ZSCORE, ABS, ADAPTIVE, DRIFT,
              RANGE_ATR, LE, IMPULSE, ENTRY, EXIT]


# ── the strategy graph ────────────────────────────────────────────────────
#
# The defaults below are `ExpandingZImpulseV4.default_params`, and the parity
# test asserts that rather than trusting this comment.

D = impl.ExpandingZImpulseV4.default_params

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
        # Two instances of one definition at two percentiles — A.4's shape, in
        # the strategy the platform actually trades.
        _node("n_entry_thr", "indicator.adaptive_threshold",
              length={"param_ref": "adapt_length"}, pct={"param_ref": "entry_pct"},
              floor={"param_ref": "min_abs_z"}, fallback={"param_ref": "min_abs_z"}),
        # See the module docstring, finding 1: these two are literals because a
        # parameter cannot be derived from another parameter. Correct at the
        # shipped min_abs_z = 0.60.
        _node("n_exit_thr", "indicator.adaptive_threshold",
              length={"param_ref": "adapt_length"}, pct={"param_ref": "exit_pct"},
              floor=D["min_abs_z"] * 0.25, fallback=D["min_abs_z"] * 0.50),
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

def _k_ema(params, inputs):
    return {"out": inputs["source"].ewm(span=params["length"], adjust=False).mean()}


def _k_true_range(params, inputs):
    prev = inputs["close"].shift(1)
    import pandas as pd
    return {"out": pd.concat([(inputs["high"] - inputs["low"]).abs(),
                              (inputs["high"] - prev).abs(),
                              (inputs["low"] - prev).abs()], axis=1).max(axis=1)}


def _k_wilder(params, inputs):
    return {"out": impl._rma(inputs["in"], params["length"])}


def _k_zscore(params, inputs):
    return {"out": impl.zscore(inputs["close"], inputs["reference"], params["length"])}


def _k_abs(params, inputs):
    return {"out": inputs["in"].abs()}


def _k_adaptive(params, inputs):
    return {"out": impl.adaptive_threshold(inputs["in"], params["length"], params["pct"],
                                           params["floor"], params["fallback"])}


def _k_drift(params, inputs):
    return {"out": impl.drift_score(inputs["reference"], inputs["atr"],
                                    params["lookback"])}


def _k_range_atr(params, inputs):
    return {"out": impl.range_in_atr(inputs["high"], inputs["low"], inputs["atr"])}


def _k_le(params, inputs):
    return {"out": inputs["in"] <= params["threshold"]}


def _k_impulse(params, inputs):
    return {"out": impl.impulse(inputs["abs_z"], inputs["threshold"],
                                params["require_expansion"],
                                params["allow_reexpansion"])}


def _k_entry(params, inputs):
    return {"out": impl._as_bool(impl.directional_entry(
        inputs["signal_bar_ok"], inputs["impulse"], inputs["z"], inputs["drift"],
        params["min_drift_atr"], params["direction"]))}


def _k_exit(params, inputs):
    return {"out": impl._as_bool(impl.displacement_lost(
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
    DRIFT["body"]["ref"]: _k_drift,
    RANGE_ATR["body"]["ref"]: _k_range_atr,
    LE["body"]["ref"]: _k_le,
    IMPULSE["body"]["ref"]: _k_impulse,
    ENTRY["body"]["ref"]: _k_entry,
    EXIT["body"]["ref"]: _k_exit,
}

# C10 — warmup per component, declared once, composed by resolution. These are
# the bar counts each computation needs before its output means anything.
KERNELS = kernel_registry({
    EMA["body"]["ref"]: {"warmup": D["ema_length"]},
    TRUE_RANGE["body"]["ref"]: {"warmup": 1},
    WILDER["body"]["ref"]: {"warmup": D["atr_length"]},
    ZSCORE["body"]["ref"]: {"warmup": D["z_length"]},
    ABS["body"]["ref"]: {},
    ADAPTIVE["body"]["ref"]: {"warmup": D["adapt_length"]},
    DRIFT["body"]["ref"]: {"warmup": D["slope_lookback"]},
    RANGE_ATR["body"]["ref"]: {},
    LE["body"]["ref"]: {},
    IMPULSE["body"]["ref"]: {"warmup": 2},
    ENTRY["body"]["ref"]: {},
    EXIT["body"]["ref"]: {},
})

LIBRARY = Library(
    components={(c["identifier"], c["version"]): c for c in COMPONENTS},
    bodies={ATR["body"]["ref"]: ATR_BODY},
    kernels=KERNELS,
)
