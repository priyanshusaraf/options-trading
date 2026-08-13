"""
The Component IR, measured against the strategy the platform actually trades.

RFC 0001 Gate 1 was "five real artefacts expressed", and Appendix A.1 expresses
`expanding_z_v4` as an abbreviated sketch. A sketch in a markdown document
proves what its author believed. This file resolves and evaluates the real
graph and asserts its four boolean outputs equal `ExpandingZImpulseV4.compute()`
**bar for bar**, which is the difference between a language that looks
expressive and one that is.

What this does and does not prove. The kernels call the same functions
`compute()` calls, so this is **not** a re-derivation of the strategy's
arithmetic — deliberately, because a second copy is the `candles.py` defect and
C12 exists because of it. What is under test is the *language*: whether fifteen
parameters, a decomposed ATR whose body is a graph, two instances of one
threshold definition at two percentiles, four directional predicates and
forty-one edges compose into the same signals the hand-written strategy
produces.

Nothing here runs in production. The engine still calls `compute()`.
"""
from __future__ import annotations

import copy

import pandas as pd
import pytest

from app.ir.resolve import resolve
from app.ir.runtime import Cache, check_causality, evaluate
from app.ir.strategies.expanding_z import GRAPH, IMPLEMENTATIONS, LIBRARY
from app.ir.validate import validate
from app.strategy.registry.expanding_z_v4 import STRATEGY

OUTPUTS = ("longEntry", "shortEntry", "longExit", "shortExit")


def candles(n=400):
    """Deterministic bars with real structure — trends, reversals and a shock.

    Flat or monotonic data makes almost every predicate constant, and a parity
    test over two constant series proves nothing.
    """
    import math

    closes = []
    price = 1000.0
    for i in range(n):
        price += math.sin(i / 9.0) * 3.0 + math.sin(i / 47.0) * 6.0
        price += 25.0 if i == 150 else 0.0
        price -= 30.0 if i == 260 else 0.0
        closes.append(price)

    idx = pd.date_range("2026-01-01 09:15", periods=n, freq="15min", tz="Asia/Kolkata")
    close = pd.Series(closes, index=idx, dtype=float)
    high = close + 2.0 + (pd.Series(range(n), index=idx) % 5) * 0.7
    low = close - 2.0 - (pd.Series(range(n), index=idx) % 7) * 0.6
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]),
                         "high": high, "low": low, "close": close,
                         "volume": 1000.0}, index=idx)


@pytest.fixture(scope="module")
def frame():
    return candles()


@pytest.fixture(scope="module")
def graph():
    return resolve(GRAPH, LIBRARY)


@pytest.fixture(scope="module")
def evaluated(graph, frame):
    return evaluate(graph, {"high": frame["high"], "low": frame["low"],
                            "close": frame["close"]}, IMPLEMENTATIONS)


# ── the artefact is conforming before anything is claimed about it ────────

def test_the_strategy_graph_validates_under_section_3():
    assert validate(GRAPH) == []


def test_every_component_in_the_library_validates():
    for (identifier, _), component in LIBRARY.components.items():
        assert validate(component) == [], identifier
    for ref, body in LIBRARY.bodies.items():
        assert validate(body) == [], ref


def test_the_graph_declares_the_strategys_real_parameters():
    """Appendix A.1 says fifteen real parameters, five of them booleans. Read
    off `default_params` rather than restated, so a change to the strategy that
    is not carried into the graph fails here."""
    declared = {}
    for item in GRAPH["interface"]:
        if item["item"] == "panel":
            declared.update({p["identifier"]: p["default"] for p in item["items"]})

    assert declared == STRATEGY.default_params
    assert len(declared) == 15
    assert sum(1 for item in GRAPH["interface"] if item["item"] == "panel") == 4


# ── the parity claim ──────────────────────────────────────────────────────

def test_the_graph_produces_the_strategys_signals_bar_for_bar(evaluated, frame):
    """The whole point. Four boolean columns, four hundred bars, exact."""
    expected = STRATEGY.compute(frame)
    for name in OUTPUTS:
        produced = evaluated.outputs[name]
        assert produced.equals(expected[name]), name


def test_the_signals_are_not_trivially_constant(evaluated):
    """A parity test between two all-False series passes and means nothing."""
    for name in OUTPUTS:
        column = evaluated.outputs[name]
        assert column.any(), f"{name} never fires — the fixture is too flat"
        assert not column.all(), f"{name} always fires"


def test_entries_actually_fire_on_this_fixture(evaluated):
    entries = evaluated.outputs["longEntry"].sum() + evaluated.outputs["shortEntry"].sum()
    assert entries >= 3, f"only {entries} entries — parity would be weakly tested"


def test_a_changed_parameter_changes_the_signals_in_both(evaluated, frame):
    """Parity at one point could be a coincidence of defaults. Move a parameter
    and the graph and the strategy must move together."""
    tightened = copy.deepcopy(GRAPH)
    for item in tightened["interface"]:
        if item.get("identifier") == "zscore":
            for p in item["items"]:
                if p["identifier"] == "entry_pct":
                    p["default"] = 90.0

    produced = evaluate(resolve(tightened, LIBRARY),
                        {"high": frame["high"], "low": frame["low"],
                         "close": frame["close"]}, IMPLEMENTATIONS)
    expected = STRATEGY.compute(frame, entry_pct=90.0)

    assert produced.outputs["longEntry"].equals(expected["longEntry"])
    assert not produced.outputs["longEntry"].equals(evaluated.outputs["longEntry"])


def test_a_derived_parameter_tracks_the_parameter_it_derives_from(frame):
    """The finding that writing this graph produced, and its fix.

    `exit_abs`'s floor is `min_abs_z * 0.25` in the strategy. An override
    carries a value only (F10), so the first version of this graph carried the
    literal `0.15` — right at the shipped `min_abs_z = 0.60` and silently wrong
    the moment anyone moved it. It is now a `value.scalar` on a wire into a
    `math.scale`, because a multiplication is a computation and components
    compute (C14).

    Moving `min_abs_z` is what tells the two apart: with a literal the exit
    threshold would not move, and parity against the strategy — which does
    multiply — would break. The contraction exit is switched on so the exit
    threshold actually reaches an output.
    """
    moved = copy.deepcopy(GRAPH)
    for item in moved["interface"]:
        if item.get("identifier") == "zscore":
            for p in item["items"]:
                if p["identifier"] == "min_abs_z":
                    p["default"] = 1.20
        if item.get("identifier") == "behaviour":
            for p in item["items"]:
                if p["identifier"] == "use_absz_contraction_exit":
                    p["default"] = True

    inputs = {"high": frame["high"], "low": frame["low"], "close": frame["close"]}
    graph = resolve(moved, LIBRARY)
    produced = evaluate(graph, inputs, IMPLEMENTATIONS)
    expected = STRATEGY.compute(frame, min_abs_z=1.20, use_absz_contraction_exit=True)

    assert graph.node("n_exit_floor").params["factor"] == 0.25
    assert produced.values["n_min_abs_z"]["out"] == 1.20
    assert produced.values["n_exit_floor"]["out"] == pytest.approx(0.30)
    for name in OUTPUTS:
        assert produced.outputs[name].equals(expected[name]), name


def test_the_contraction_exit_is_actually_exercised_by_that_test(frame):
    """Without this, the test above could pass on a graph whose exit threshold
    reaches nothing — the flag would be on and the wire still dead."""
    off = STRATEGY.compute(frame, min_abs_z=1.20, use_absz_contraction_exit=False)
    on = STRATEGY.compute(frame, min_abs_z=1.20, use_absz_contraction_exit=True)
    assert not off["longExit"].equals(on["longExit"])


def test_the_scalar_axis_is_used_and_not_merely_declared(graph):
    """F7 has carried `scalar` since the format phase and nothing produced one.
    These three nodes are the first, and they are not series: a scalar that were
    quietly a series would broadcast and hide the difference."""
    assert not isinstance(
        evaluate(graph, {"high": candles()["high"], "low": candles()["low"],
                         "close": candles()["close"]}, IMPLEMENTATIONS)
        .values["n_min_abs_z"]["out"], pd.Series)

    for identifier in ("value.scalar", "math.scale"):
        component = LIBRARY.components[(identifier, 1)]
        structures = {s["wire_type"]["structure"] for s in component["interface"]
                      if s["item"] == "socket"}
        assert structures == {"scalar"}, identifier


# ── what resolution says about the strategy ───────────────────────────────

def test_the_atr_is_a_subgraph_not_a_leaf(graph):
    """A.2's decomposition, in the real strategy: `indicator.atr.wilder`'s body
    is a graph, so its nodes resolve underneath `n_atr` by instance path. This
    is the Generation-2 property the current block library cannot express —
    `_atr` there is a private helper with no public identity."""
    assert graph.node("n_atr/n_tr") is not None
    assert graph.node("n_atr/n_smooth") is not None
    assert graph.node("n_atr") is None
    assert ("indicator.atr.wilder", 1) in graph.versions
    assert ("smoothing.wilder", 1) in graph.versions


def test_one_threshold_definition_serves_two_percentiles(graph):
    """A.4's shape, in the strategy that books the trades: two instances of
    `indicator.adaptive_threshold`, distinguishable by their bound parameters."""
    entry = graph.node("n_entry_thr")
    exit_ = graph.node("n_exit_thr")
    assert entry.definition == exit_.definition
    assert entry.params["pct"] == 65.0 and exit_.params["pct"] == 35.0


def test_a_forwarded_parameter_reaches_the_kernel_inside_the_body(graph):
    """`atr_length` is declared on the graph, overridden onto `n_atr`, and
    forwarded by `{"param_ref": "length"}` into the smoothing node inside the
    ATR's body. Three hops; the number that arrives is what matters."""
    assert graph.node("n_atr/n_smooth").params["length"] == 14


def test_warmup_composes_to_the_deepest_chain(graph):
    """C10 through the real strategy: the adaptive threshold's 200 bars sit on
    top of the z-score's 50 and the EMA's 50, and the entry predicate cannot
    produce a trustworthy value before all of them can."""
    assert graph.node("n_entry_thr").warmup == 200 + 50 + 50
    assert graph.warmup == graph.node("n_long_entry").warmup == 302


def test_warmup_follows_the_bound_parameter_not_the_components_default(frame):
    """The defect this test was written for, and the reason C10 says warmup is
    **derived** per component rather than declared as a number.

    The kernel registry first gave each component a constant taken from the
    strategy's defaults. A node overriding `ema_length` to 200 would then still
    have claimed it warmed up in 50 bars — and nothing would have reported it.
    The backtest would have read 150 bars of an unwarmed EMA and looked
    entirely plausible, which is the worst shape a defect can have here.
    """
    slower = copy.deepcopy(GRAPH)
    for item in slower["interface"]:
        if item.get("identifier") == "trend":
            for p in item["items"]:
                if p["identifier"] == "ema_length":
                    p["default"] = 200

    graph = resolve(slower, LIBRARY)
    assert graph.node("n_ema").warmup == 200
    # …and it composes downstream: the z-score adds its own 50 on top.
    assert graph.node("n_z").warmup == 250
    assert graph.warmup == resolve(GRAPH, LIBRARY).warmup + 150


def test_a_warmup_that_is_a_function_still_cannot_read_the_future(frame):
    """C11 is checked at resolution now, because that is the first moment the
    parameters exist. A function returning a negative is the same read of the
    future a negative constant was, and is refused the same way."""
    from app.ir.kernels import KernelDeclarationError, kernel_registry
    from app.ir.resolve import Library
    from app.ir.strategies.expanding_z import EMA

    peeking = kernel_registry({**LIBRARY.kernels,
                               EMA["body"]["ref"]: {"warmup": lambda p: -p["length"]}})
    with pytest.raises(KernelDeclarationError) as exc:
        resolve(GRAPH, Library(LIBRARY.components, LIBRARY.bodies, peeking))
    assert exc.value.clause == "C11"


def test_the_declared_signals_settle_after_warmup(evaluated):
    settled = evaluated.settled()
    assert len(settled["longEntry"]) == 400 - evaluated.warmup


# ── C11 on the real strategy ──────────────────────────────────────────────

def test_the_real_strategy_is_causal(graph, frame):
    """The strategy's own claim — "signals fire only on completed candles" —
    stops being a convention and becomes a measurement. Every node, not just
    the four outputs: a lookahead that cancels downstream would otherwise pass.

    This is a genuinely new check on production strategy code. It passing is
    evidence about `expanding_z_v4`, not only about the IR.
    """
    check_causality(graph, {"high": frame["high"], "low": frame["low"],
                            "close": frame["close"]}, IMPLEMENTATIONS)


def test_the_causality_check_would_catch_a_lookahead_here(graph, frame):
    """Proof the check above can go red on this graph rather than passing
    because nothing was examined."""
    from app.ir.strategies.expanding_z import EMA
    peeking = {**IMPLEMENTATIONS,
               EMA["body"]["ref"]: lambda p, i, c: {
                   "out": i["source"].ewm(span=p["length"], adjust=False).mean()
                   .shift(-1).bfill()}}
    with pytest.raises(Exception) as exc:
        check_causality(graph, {"high": frame["high"], "low": frame["low"],
                                "close": frame["close"]}, peeking)
    assert getattr(exc.value, "clause", None) == "C11"


# ── C8 on the real strategy ───────────────────────────────────────────────

def test_re_evaluating_the_same_strategy_is_all_cache_hits(graph, frame):
    inputs = {"high": frame["high"], "low": frame["low"], "close": frame["close"]}
    cache = Cache()
    evaluate(graph, inputs, IMPLEMENTATIONS, cache=cache)
    again = evaluate(graph, inputs, IMPLEMENTATIONS, cache=cache)
    assert set(again.cache_hits) == {n.instance_id for n in graph.nodes}


def test_changing_one_parameter_recomputes_only_what_depends_on_it(graph, frame):
    """The economic claim behind C8: a sweep over `entry_pct` must not
    recompute the EMA, the ATR or the z-score. vectorbt's answer to this is to
    build the sweep into the indicator, which is what C14 forbids."""
    inputs = {"high": frame["high"], "low": frame["low"], "close": frame["close"]}
    cache = Cache()
    evaluate(graph, inputs, IMPLEMENTATIONS, cache=cache)

    moved = copy.deepcopy(GRAPH)
    for item in moved["interface"]:
        if item.get("identifier") == "zscore":
            for p in item["items"]:
                if p["identifier"] == "entry_pct":
                    p["default"] = 70.0
    after = evaluate(resolve(moved, LIBRARY), inputs, IMPLEMENTATIONS, cache=cache)

    hits = set(after.cache_hits)
    for reused in ("n_ema", "n_atr/n_tr", "n_atr/n_smooth", "n_z", "n_absz",
                   "n_drift", "n_range", "n_signal_ok", "n_exit_thr"):
        assert reused in hits, f"{reused} should not have been recomputed"
    for recomputed in ("n_entry_thr", "n_impulse", "n_long_entry", "n_short_entry"):
        assert recomputed not in hits, f"{recomputed} depends on entry_pct"
