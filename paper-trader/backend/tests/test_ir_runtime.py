"""
The component runtime — a resolved graph, evaluated.

The resolver landed one commit before this file, and a `ResolvedGraph` nothing
consumes is a correct mechanism wired to nothing. So this suite exists to make
the resolver's outputs load-bearing: bound parameters really parameterise the
computation, composed warmup really names the unsettled prefix, cache identity
really decides what is recomputed, and the declared purity really decides what
may be cached at all.

The graph under test is Appendix A.4's, with real kernels behind it: Wilder's
ATR decomposed into true range and a smoothing, instantiated twice at 7 and 21,
compared. That is the same artefact the resolver's tests use, so a divergence
between the two files is a real disagreement rather than two fixtures drifting.
"""
from __future__ import annotations

import copy

import pandas as pd
import pytest

from app.ir.kernels import kernel_registry
from app.ir.resolve import Library, resolve
from app.ir.runtime import (
    Cache,
    EvaluationError,
    check_causality,
    evaluate,
)
from tests.test_ir_resolution import (
    ATR,
    ATR_BODY,
    COMPARE_GT,
    DUAL_ATR,
    EMA,
    TRUE_RANGE,
    WILDER,
    library,
)


# ── the kernels, as real computations ─────────────────────────────────────

def k_true_range(params, inputs):
    high, low, close = inputs["high"], inputs["low"], inputs["close"]
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()],
                   axis=1).max(axis=1)
    return {"out": tr}


def k_wilder(params, inputs):
    length = params["length"]
    return {"out": inputs["in"].ewm(alpha=1 / length, adjust=False).mean()}


def k_ema(params, inputs):
    return {"out": inputs["in"].ewm(span=params["length"], adjust=False).mean()}


def k_gt(params, inputs):
    return {"out": inputs["a"] > inputs["b"]}


IMPLEMENTATIONS = {
    TRUE_RANGE["body"]["ref"]: k_true_range,
    WILDER["body"]["ref"]: k_wilder,
    EMA["body"]["ref"]: k_ema,
    COMPARE_GT["body"]["ref"]: k_gt,
}


def bars(n=120):
    """Deterministic, and not monotonic — a monotonic series hides sign errors."""
    idx = pd.RangeIndex(n)
    close = pd.Series([100 + (i % 17) - (i % 5) * 2 + i * 0.05 for i in range(n)],
                      index=idx, dtype=float)
    return {
        "high": close + 1.5 + (close.index % 3) * 0.25,
        "low": close - 1.5 - (close.index % 4) * 0.25,
        "close": close,
    }


@pytest.fixture
def graph():
    return resolve(DUAL_ATR, library())


@pytest.fixture
def result(graph):
    return evaluate(graph, bars(), IMPLEMENTATIONS)


# ── the resolved graph really drives the computation ──────────────────────

def test_the_graphs_declared_output_is_produced(result):
    assert set(result.outputs) == {"signal"}
    assert result.outputs["signal"].dtype == bool
    assert len(result.outputs["signal"]) == 120


def test_the_two_instances_compute_different_things(result):
    """The resolver said `n_fast` and `n_slow` stay distinguishable at lengths
    7 and 21 (C4). This is that claim reaching a number: a 7-bar Wilder average
    and a 21-bar one are not the same series, so the comparison is not constant."""
    fast = result.values["n_fast/n_smooth"]["out"]
    slow = result.values["n_slow/n_smooth"]["out"]
    assert not fast.equals(slow)
    settled = result.outputs["signal"].iloc[result.warmup:]
    assert settled.any() and not settled.all()


def test_a_bound_parameter_actually_parameterises_the_kernel(graph):
    """The override chain — declared default 14, graph override 7, forwarded
    into the body by `{"param_ref": "length"}` — has to arrive at the kernel as
    the number 7, or every layer above it is decoration."""
    seen = {}

    def spy(params, inputs):
        seen[params["length"]] = True
        return k_wilder(params, inputs)

    evaluate(graph, bars(), {**IMPLEMENTATIONS, WILDER["body"]["ref"]: spy})
    assert set(seen) == {7, 21}


# ── C10 — warmup names the prefix that is not yet trustworthy ─────────────

def test_c10_warmup_comes_from_the_resolver_not_from_the_runtime(graph, result):
    assert result.warmup == graph.warmup == 15


def test_c10_settled_removes_exactly_the_warmup_prefix(result):
    settled = result.settled()["signal"]
    assert len(settled) == 120 - 15
    assert settled.equals(result.outputs["signal"].iloc[15:])


# ── C8 — cache identity decides what is recomputed ────────────────────────

def test_c8_an_identical_graph_is_not_recomputed(graph):
    cache = Cache()
    evaluate(graph, bars(), IMPLEMENTATIONS, cache=cache)
    second = evaluate(graph, bars(), IMPLEMENTATIONS, cache=cache)
    assert set(second.cache_hits) == {n.instance_id for n in graph.nodes}


def test_c8_a_change_upstream_invalidates_everything_downstream():
    """Transitivity, measured. Change `n_fast`'s length and the comparison
    three hops downstream must recompute — the property Prefect's `TaskSource`
    lacks, because it excludes nested tasks."""
    cache = Cache()
    evaluate(resolve(DUAL_ATR, library()), bars(), IMPLEMENTATIONS, cache=cache)

    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["overrides"]["length"] = 8
    after = evaluate(resolve(spec, library()), bars(), IMPLEMENTATIONS, cache=cache)

    assert "n_cmp" not in after.cache_hits
    assert "n_fast/n_smooth" not in after.cache_hits
    # The untouched branch is still a hit, or the cache would be worthless.
    assert "n_slow/n_smooth" in after.cache_hits


def test_c9_a_declared_impurity_is_never_cached():
    """"My output is not a function of my inputs" is what an impurity policy
    says. Caching that would be caching a lie — which is exactly what ComfyUI's
    IS_CHANGED buys, at the cost of the cache's value as a provenance claim."""
    lib = library()
    impure = kernel_registry({**lib.kernels,
                              COMPARE_GT["body"]["ref"]: {"purity": "account_state"}})
    graph = resolve(DUAL_ATR, Library(lib.components, lib.bodies, impure))

    cache = Cache()
    evaluate(graph, bars(), IMPLEMENTATIONS, cache=cache)
    second = evaluate(graph, bars(), IMPLEMENTATIONS, cache=cache)

    assert "n_cmp" not in second.cache_hits
    assert "n_fast/n_smooth" in second.cache_hits


# ── C11 — lookahead, measured rather than asserted ────────────────────────

def test_c11_the_honest_graph_is_causal(graph):
    """The control. If this ever fails, the check is broken, not the kernels."""
    check_causality(graph, bars(), IMPLEMENTATIONS)


LOOKAHEAD_KERNELS = {
    "shift(-1) — tomorrow's value, today":
        lambda params, inputs: {"out": k_wilder(params, inputs)["out"].shift(-1).bfill()},
    "centred window — half the window is the future":
        lambda params, inputs: {
            "out": inputs["in"].rolling(params["length"], center=True,
                                        min_periods=1).mean()},
    "whole-series normalisation — the max is not known yet":
        lambda params, inputs: {
            "out": k_wilder(params, inputs)["out"] / inputs["in"].max()},
}


@pytest.mark.parametrize("description, kernel", list(LOOKAHEAD_KERNELS.items()))
def test_c11_every_shape_of_lookahead_is_caught(graph, description, kernel):
    """Three real ways a kernel reads the future, none of which announces
    itself. `A component MUST NOT be able to violate it by convention` — so the
    author's intent is not consulted, only whether a settled value changed when
    later bars arrived.

    The third is why the check reads every node rather than only the graph's
    outputs: dividing both branches by a max neither bar knew yet leaves
    `fast > slow` **identical**, so an outputs-only check calls it causal. It
    was written that way first and this case caught it."""
    with pytest.raises(EvaluationError) as exc:
        check_causality(graph, bars(),
                        {**IMPLEMENTATIONS, WILDER["body"]["ref"]: kernel})
    assert exc.value.clause == "C11"


def test_c11_a_kernel_may_not_change_which_bars_exist(graph):
    """The cheap half, caught locally: a kernel that resamples or reindexes
    silently would make every downstream alignment a guess."""
    def resampler(params, inputs):
        return {"out": inputs["in"].iloc[::2]}

    with pytest.raises(EvaluationError) as exc:
        evaluate(graph, bars(), {**IMPLEMENTATIONS, WILDER["body"]["ref"]: resampler})
    assert exc.value.clause == "C11"


def test_c11_the_check_uses_a_fresh_cache_or_it_would_pass_by_not_running(graph):
    """A cache hit would hand back the full-length answer and the comparison
    would compare a series to itself. This is the test that would have caught
    that if the check had been written the easy way."""
    cache = Cache()
    evaluate(graph, bars(), IMPLEMENTATIONS, cache=cache)
    with pytest.raises(EvaluationError):
        check_causality(graph, bars(),
                        {**IMPLEMENTATIONS,
                         WILDER["body"]["ref"]: lambda p, i: {"out": i["in"].shift(-1).bfill()}})


# ── C13 — the runtime has nothing to branch on ────────────────────────────

def test_c13_a_kernel_is_known_only_by_its_content_address(graph):
    """The runtime's lookup key is the body's content address and there is no
    other. A component's origin is not representable here, so no execution path
    can branch on it — C13 held subtractively, again."""
    import inspect
    text = inspect.getsource(evaluate)
    assert "body_ref" in text
    for provenance in ("is_generated", "is_marketplace", "source_kind", "provenance"):
        assert provenance not in text


def test_c13_an_unregistered_kernel_fails_rather_than_falling_back(graph):
    thinned = {k: v for k, v in IMPLEMENTATIONS.items()
               if k != COMPARE_GT["body"]["ref"]}
    with pytest.raises(EvaluationError) as exc:
        evaluate(graph, bars(), thinned)
    assert exc.value.instance_id == "n_cmp"


# ── the graph's own interface ─────────────────────────────────────────────

def test_a_missing_graph_input_is_named_not_defaulted(graph):
    supplied = bars()
    del supplied["close"]
    with pytest.raises(EvaluationError) as exc:
        evaluate(graph, supplied, IMPLEMENTATIONS)
    assert exc.value.clause == "C3" and "close" in exc.value.message


def test_a_component_published_from_the_graph_evaluates_identically():
    """C15's equivalence, carried one stage further than the resolver could
    take it: the published component does not merely resolve to the same nodes,
    it computes the same numbers."""
    from app.ir.resolve import body_for, publish

    ref, body = body_for(DUAL_ATR)
    direct = evaluate(resolve(DUAL_ATR, library()), bars(), IMPLEMENTATIONS)
    published = evaluate(
        resolve(publish(DUAL_ATR), library(bodies={ref: body})), bars(), IMPLEMENTATIONS)
    assert published.outputs["signal"].equals(direct.outputs["signal"])


def test_the_atr_component_can_be_evaluated_on_its_own():
    """A.2's decomposability, end to end: `indicator.atr.wilder` is a component
    whose body is a graph, and it is runnable by itself rather than only as
    part of something larger. That is the Generation-2 property the current
    block library fails — `_atr` is a private helper with no public identity."""
    out = evaluate(resolve(ATR, library(), parameters={"length": 14}),
                   bars(), IMPLEMENTATIONS)
    assert set(out.outputs) == {"atr"}
    assert out.warmup == 15
    assert (out.settled()["atr"] > 0).all()


def test_the_body_and_the_component_agree_on_what_atr_is():
    """The body graph resolved directly and the component that wraps it must
    compute the same series, or the wrapper is doing something the language
    does not say it does."""
    direct = evaluate(resolve(ATR_BODY, library(), parameters={"length": 14}),
                      bars(), IMPLEMENTATIONS)
    wrapped = evaluate(resolve(ATR, library(), parameters={"length": 14}),
                       bars(), IMPLEMENTATIONS)
    assert direct.outputs["atr"].equals(wrapped.outputs["atr"])
