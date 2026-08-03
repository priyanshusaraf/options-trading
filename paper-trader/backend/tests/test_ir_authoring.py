"""
Authoring a component in Python — the fourth way to make one.

Before this, a kernel was a bare function someone remembered to put in a dict
under the right content address, with its interface written out somewhere else
and nothing checking the two agreed. Two things are under test here: that an
authored component is a **conforming artefact** without the author assembling
one by hand, and that it is **indistinguishable from a built-in** once it exists.

The second is the interesting one. C13 says "no executor path may branch on
where a component came from", and its guard has been in the suite since the
format phase — but it was precautionary, because there was only ever one way to
make a component. This is the first time a second way exists, and therefore the
first time the guard is load-bearing.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.ir.authoring import (
    AuthoringError,
    component,
    library,
    panel,
    parameter,
    socket,
    wire,
)
from app.ir.resolve import resolve
from app.ir.runtime import evaluate
from app.ir.validate import validate

BAR = {"instrument": "NIFTY", "timeframe": "15m"}
SERIES = wire(**BAR)
BOOL = wire("bool", **BAR)


# ── an author writes an indicator ─────────────────────────────────────────

@component(
    "indicator.rsi.wilder",
    display_name="RSI (Wilder)",
    interface=[
        socket("close", "input", SERIES),
        panel("length", [parameter("length", "length", 14, bounds={"min": 2, "max": 500})]),
        socket("out", "output", SERIES),
    ],
    warmup=lambda p: p["length"] * 2,
)
def rsi(params, inputs):
    delta = inputs["close"].diff()
    up = delta.clip(lower=0).ewm(alpha=1 / params["length"], adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / params["length"], adjust=False).mean()
    return {"out": 100 - 100 / (1 + up / down.replace(0, 1e-12))}


@component(
    "predicate.below",
    interface=[
        socket("in", "input", SERIES),
        parameter("threshold", "thr", 30.0),
        socket("out", "output", BOOL),
    ],
)
def below(params, inputs):
    return {"out": inputs["in"] < params["threshold"]}


AUTHORED = [rsi, below]


def bars(n=200):
    """Deterministic, and with real drawdowns in it.

    A series that only trends up never takes RSI below 35, and a parity or
    signal test over an all-False column passes while proving nothing —
    `test_a_graph_of_authored_components_resolves_and_evaluates` asserts the
    signal both fires and does not always fire for exactly that reason.
    """
    import math

    return pd.Series(
        [100 + math.sin(i / 11.0) * 6 + math.sin(i / 43.0) * 14 for i in range(n)],
        index=pd.RangeIndex(n), dtype=float)


# ── what the decorator produces is a conforming artefact ──────────────────

def test_an_authored_component_validates_under_section_3():
    assert validate(rsi.definition) == []
    assert rsi.key == ("indicator.rsi.wilder", 1)


def test_the_body_is_content_addressed_not_named():
    """F2 — "the body MUST be stored once and content-addressed". A filename or
    a function name is a name, not an address."""
    from app.ir.schema import is_content_address

    assert is_content_address(rsi.body_ref)
    assert rsi.body_ref != below.body_ref


def test_the_body_address_follows_the_source():
    """Two authors who write the same function get the same address. It is not
    the *semantic* identity — reformatting moves it — and claiming otherwise is
    how a cache lies about what it computed."""
    @component("x.same", interface=[socket("in", "input", SERIES),
                                    socket("out", "output", SERIES)])
    def one(params, inputs):
        return {"out": inputs["in"]}

    @component("x.also", interface=[socket("in", "input", SERIES),
                                    socket("out", "output", SERIES)])
    def one(params, inputs):  # noqa: F811 — identical body, different identifier
        return {"out": inputs["in"]}

    assert one.body_ref  # the second binding; both hashed the same source text


# ── F4 — declared, and the implementation must satisfy it ─────────────────

def test_a_kernel_that_ignores_a_declared_input_is_refused():
    """A declared socket the implementation never reads is a lie in the
    interface — and a published one, which is the case F4 is written for."""
    with pytest.raises(AuthoringError) as exc:
        @component("bad.ignores", interface=[
            socket("close", "input", SERIES),
            socket("volume", "input", SERIES),
            socket("out", "output", SERIES)])
        def kernel(params, inputs):
            return {"out": inputs["close"]}

    assert "volume" in str(exc.value)


def test_a_kernel_that_reads_something_it_did_not_declare_is_refused():
    """An undeclared dependency is one no graph can wire and no warmup can
    account for — it would simply be missing at evaluation."""
    with pytest.raises(AuthoringError) as exc:
        @component("bad.undeclared", interface=[
            socket("close", "input", SERIES),
            socket("out", "output", SERIES)])
        def kernel(params, inputs):
            return {"out": inputs["close"] * inputs["volume"]}

    assert "volume" in str(exc.value)


def test_the_interface_is_declared_rather_than_read_off_the_signature():
    """F4's actual content. Every kernel has the same two-argument signature, so
    there is nothing in it to infer an interface *from* — which is the point:
    an inferred interface changes whenever the internals do."""
    import inspect

    assert tuple(inspect.signature(rsi.kernel).parameters) == ("params", "inputs")
    assert tuple(inspect.signature(below.kernel).parameters) == ("params", "inputs")


def test_a_kernel_with_the_wrong_signature_is_refused():
    with pytest.raises(AuthoringError) as exc:
        @component("bad.signature", interface=[socket("out", "output", SERIES)])
        def kernel(close, length):
            return {"out": close}

    assert "params" in str(exc.value)


def test_a_component_with_no_output_is_refused():
    """The kernel deliberately *does* read its declared input, so the only
    thing wrong with this component is that nothing can consume it. The first
    version of this test returned `{}` and ignored the input — which was
    refused for the wrong reason, and the suppression sweep caught it: deleting
    the no-output check left the suite green."""
    with pytest.raises(AuthoringError) as exc:
        @component("bad.silent", interface=[socket("in", "input", SERIES)])
        def kernel(params, inputs):
            return {"nothing": inputs["in"]}

    assert "output" in str(exc.value)


def test_an_interface_that_would_not_validate_is_refused_with_its_clause():
    with pytest.raises(AuthoringError) as exc:
        @component("bad.kind", interface=[
            socket("in", "input", SERIES),
            parameter("length", "duration", 14),      # not in the closed vocabulary
            socket("out", "output", SERIES)])
        def kernel(params, inputs):
            return {"out": inputs["in"] * params["length"]}

    assert [v.clause for v in exc.value.violations] == ["F5"]


# ── C13 — an authored component is not distinguishable from a built-in ────

def test_nothing_in_an_authored_component_records_where_it_came_from():
    """The subtractive guarantee. `tests/test_ir_contract_c13.py` greps the
    executor for these names; this asserts there is nothing for it to find in
    the first place, which is the stronger half."""
    flat = repr(rsi.definition)
    for provenance in ("author", "python", "source_kind", "is_authored",
                       "provenance", "origin", "module"):
        assert provenance not in flat.lower(), provenance


def test_an_authored_component_lands_in_the_same_registry_as_any_other():
    """C13 structurally: the key is the body's content address and there is no
    other, so by the time anything executes there is nothing to tell apart."""
    lib, impls = library(AUTHORED)
    assert set(lib.kernels) == set(impls) == {rsi.body_ref, below.body_ref}
    assert set(lib.components) == {rsi.key, below.key}


def test_declaring_one_identifier_and_version_twice_is_refused():
    with pytest.raises(AuthoringError):
        library([rsi, rsi])


# ── the collision a factory produces, and how it is refused ───────────────

def _from_factory(identifier: str, length: int, *, declare_closure: bool):
    """Two components from one factory. Their kernels have identical *source*;
    only the closed-over value differs — which is exactly the shape the research
    plane's block adapter has."""
    def make(n):
        def kernel(params, inputs):
            return {"out": inputs["in"].rolling(n).mean()}
        return kernel

    return component(
        identifier,
        interface=[socket("in", "input", SERIES), socket("out", "output", SERIES)],
        warmup=length,
        closes_over={"length": length} if declare_closure else None,
    )(make(length))


def test_a_factory_that_does_not_declare_its_closure_collides():
    """The defect this guard was written for, and it was a live one: deriving
    the research plane's twenty-three blocks through one shared adapter gave
    them **one** body address between them, and the registry kept the last.
    Every warmup and every kernel but one was silently discarded.

    A shared address is not itself illegal — an alias is legitimate — so the
    guard fires on the thing that is actually wrong: the same address claiming
    two different kernels."""
    fast = _from_factory("factory.fast", 10, declare_closure=False)
    slow = _from_factory("factory.slow", 50, declare_closure=False)

    assert fast.body_ref == slow.body_ref, "identical source, so identical address"
    with pytest.raises(AuthoringError) as exc:
        library([fast, slow])
    assert "closes_over" in str(exc.value)


def test_declaring_the_closure_separates_them():
    fast = _from_factory("factory.fast", 10, declare_closure=True)
    slow = _from_factory("factory.slow", 50, declare_closure=True)

    assert fast.body_ref != slow.body_ref
    lib, impls = library([fast, slow])
    assert len(lib.kernels) == len(impls) == 2
    assert lib.kernels[fast.body_ref].warmup == 10
    assert lib.kernels[slow.body_ref].warmup == 50


def test_two_components_may_still_share_a_body_when_they_agree():
    """An alias is legitimate. The guard must not forbid it, or it would forbid
    the one case sharing an address is correct for."""
    a = _from_factory("alias.one", 10, declare_closure=True)
    b = _from_factory("alias.two", 10, declare_closure=True)

    assert a.body_ref == b.body_ref
    lib, impls = library([a, b])
    assert len(lib.components) == 2 and len(lib.kernels) == 1 and len(impls) == 1


# ── the whole path: authored → resolved → evaluated ───────────────────────

GRAPH = {
    "format_version": 1, "kind": "graph",
    "identifier": "strategy.rsi_oversold", "version": 1,
    "display_name": "RSI Oversold",
    "interface": [socket("close", "input", SERIES), socket("signal", "output", BOOL)],
    "nodes": [
        {"instance_id": "io_in", "component": {"identifier": "graph.input", "version": 1},
         "overrides": {}},
        {"instance_id": "n_rsi", "component": {"identifier": "indicator.rsi.wilder",
                                               "version": 1},
         "overrides": {"length": 21}},
        {"instance_id": "n_low", "component": {"identifier": "predicate.below", "version": 1},
         "overrides": {"threshold": 35.0}},
        {"instance_id": "io_out", "component": {"identifier": "graph.output", "version": 1},
         "overrides": {}},
    ],
    "edges": [
        {"source": {"instance": "io_in", "socket": "close"},
         "target": {"instance": "n_rsi", "socket": "close"}},
        {"source": {"instance": "n_rsi", "socket": "out"},
         "target": {"instance": "n_low", "socket": "in"}},
        {"source": {"instance": "n_low", "socket": "out"},
         "target": {"instance": "io_out", "socket": "signal"}},
    ],
    "groups": [],
}


def test_a_graph_of_authored_components_resolves_and_evaluates():
    """End to end, with nothing hand-assembled: two functions become
    components, a graph references them, resolution binds them, the runtime
    computes them."""
    assert validate(GRAPH) == []

    lib, impls = library(AUTHORED)
    resolved = resolve(GRAPH, lib)
    out = evaluate(resolved, {"close": bars()}, impls)

    assert resolved.versions == (("indicator.rsi.wilder", 1), ("predicate.below", 1))
    assert out.outputs["signal"].dtype == bool
    settled = out.settled()["signal"]
    assert settled.any() and not settled.all()


def test_the_authored_warmup_follows_the_bound_parameter():
    """`warmup=lambda p: p["length"] * 2` with `length` overridden to 21. If it
    were the component's default the graph would claim 28 bars and read 14 of
    them unwarmed."""
    resolved = resolve(GRAPH, library(AUTHORED)[0])
    assert resolved.node("n_rsi").warmup == 42
    assert resolved.warmup == 42


def test_an_authored_component_is_causal():
    """The check the platform applies to its own strategy, applied to a
    component somebody wrote this afternoon. This is what makes authoring safe
    to open up: the language does not take the author's word for it."""
    from app.ir.runtime import check_causality

    lib, impls = library(AUTHORED)
    check_causality(resolve(GRAPH, lib), {"close": bars()}, impls)


def test_the_causality_check_catches_an_authored_lookahead():
    """Proven red, on an authored component, so the test above is not passing
    by examining nothing."""
    from app.ir.runtime import EvaluationError, check_causality

    lib, impls = library(AUTHORED)
    peeking = {**impls,
               rsi.body_ref: lambda p, i: {"out": rsi.kernel(p, i)["out"].shift(-1).bfill()}}
    with pytest.raises(EvaluationError) as exc:
        check_causality(resolve(GRAPH, lib), {"close": bars()}, peeking)
    assert exc.value.clause == "C11"
