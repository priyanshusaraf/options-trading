"""
The block library expressed as Component IR components.

Step one of Research Plane Generation 2. Generation 1 searches parameters over a
fixed grammar; C14 says structure search is unreachable from that shape. This is
the vocabulary made composable, versioned and typed so a generator can search
over structure instead.

The claim under test is **equivalence**: every derived component computes
exactly what calling the block directly computes, on real bars, bar for bar. If
that does not hold, the derivation is a second implementation of the block
library — which is the `candles.py` defect, and the whole reason the adapter
calls `BlockSpec.fn` rather than reimplementing it.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from app.ir.authoring import library
from app.ir.resolve import resolve
from app.ir.runtime import evaluate
from app.ir.validate import validate
from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.ir_components import (
    BAR_INPUTS,
    derive,
    derive_all,
    groups,
)
from app.ir.contributors.generated_blocks import CAUSAL_MANIFEST

BAR = {"instrument": "NIFTY", "timeframe": "15m"}


@pytest.fixture(scope="module")
def derived():
    return derive_all(**BAR)


def bars(n=320):
    """Real structure — trend, reversal, a shock — and a volume column.

    Flat data makes most of these blocks constant, and an equivalence test
    between two constant series proves nothing. Volume matters specifically:
    `volume_surge` reads False on a frame without it, which is a documented
    past defect of this library.
    """
    idx = pd.date_range("2026-01-01 09:15", periods=n, freq="15min", tz="Asia/Kolkata")
    close = pd.Series(
        [1000 + math.sin(i / 9.0) * 8 + math.sin(i / 41.0) * 20 + (18 if i > 200 else 0)
         for i in range(n)], index=idx, dtype=float)
    return pd.DataFrame({
        "date": idx,
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 2.0 + (pd.Series(range(n), index=idx) % 5) * 0.6,
        "low": close - 2.0 - (pd.Series(range(n), index=idx) % 7) * 0.5,
        "close": close,
        "volume": pd.Series([900 + (i % 23) * 40 + (2500 if i % 61 == 0 else 0)
                             for i in range(n)], index=idx, dtype=float),
    }, index=idx)


# ── the whole vocabulary derives, and derives conformingly ────────────────

def test_every_block_becomes_a_conforming_component(derived):
    assert set(derived) == set(BLOCKS)
    assert len(derived) == 23
    for name, authored in derived.items():
        assert validate(authored.definition) == [], name
        assert authored.key == (f"block.{name}", 1)


def test_the_parameters_are_the_blocks_own(derived):
    """Appendix A.3: "each block's BlockSpec already declares (param_name, kind)
    pairs drawn from the same bounded vocabulary as F5". Read off BlockSpec
    rather than restated, so a block that gains a parameter fails here until it
    is carried across."""
    for name, spec in BLOCKS.items():
        params = [item for item in derived[name].definition["interface"]
                  if item["item"] == "parameter"]
        assert [(p["identifier"], p["kind"]) for p in params] == list(spec.params), name
        assert [p["default"] for p in params] == list(spec.sample_args), name


def test_every_kind_is_in_the_closed_vocabulary(derived):
    from app.ir.schema import KINDS

    for name, authored in derived.items():
        for item in authored.definition["interface"]:
            if item["item"] == "parameter":
                assert item["kind"] in KINDS, (name, item["kind"])


def test_every_block_still_returns_a_boolean(derived):
    """Recorded, not celebrated. Appendix A.2: "every public block returns
    Series[bool] … so a value like ATR cannot be named, shared, or forked
    today". Deriving components does not fix that — the blocks are still
    boolean predicates — and this test pins the gap so closing it is visible."""
    for name, authored in derived.items():
        out = [item for item in authored.definition["interface"]
               if item["item"] == "socket" and item["direction"] == "output"]
        assert len(out) == 1
        assert out[0]["wire_type"]["value"] == "bool", name


# ── the claim that matters: equivalence, not resemblance ──────────────────

def _graph(name: str) -> dict:
    from app.ir.authoring import socket as sock
    from app.ir.authoring import wire as w

    bar = w(**BAR)
    return {
        "format_version": 1, "kind": "graph",
        "identifier": f"probe.{name}", "version": 1, "display_name": name,
        "interface": [*(sock(f, "input", bar) for f in BLOCKS[name].inputs),
                      sock("out", "output", w("bool", **BAR))],
        "nodes": [
            {"instance_id": "io_in",
             "component": {"identifier": "graph.input", "version": 1}, "overrides": {}},
            {"instance_id": "n",
             "component": {"identifier": f"block.{name}", "version": 1}, "overrides": {}},
            {"instance_id": "io_out",
             "component": {"identifier": "graph.output", "version": 1}, "overrides": {}},
        ],
        "edges": [
            *({"source": {"instance": "io_in", "socket": f},
               "target": {"instance": "n", "socket": f}}
              for f in BLOCKS[name].inputs),
            {"source": {"instance": "n", "socket": "out"},
             "target": {"instance": "io_out", "socket": "out"}},
        ],
        "groups": [],
    }


@pytest.mark.parametrize("name", sorted(
    name for name, disposition in CAUSAL_MANIFEST.items()
    if disposition.status == "admitted"))
def test_the_component_computes_exactly_what_the_block_computes(name, derived):
    """Bar for bar, on real bars. The adapter calls `BlockSpec.fn`; if this ever
    fails it means the derivation grew a second implementation, which is the
    defect C12 exists because of."""
    frame = bars()
    spec = BLOCKS[name]

    lib, impls = library([derived[name]])
    graph = _graph(name)
    assert validate(graph) == []

    produced = evaluate(resolve(graph, lib),
                        {f: frame[f] for f in BAR_INPUTS}, impls)
    expected = spec.fn(frame, *spec.sample_args)

    assert produced.outputs["out"].equals(expected), name


def test_quarantined_components_have_no_executable_registration():
    from app.ir.contributors.generated_blocks import BLOCK_COMPONENTS, BLOCK_REGISTRATIONS

    for name, disposition in CAUSAL_MANIFEST.items():
        if disposition.status == "quarantined":
            assert BLOCK_COMPONENTS[name].body_ref not in BLOCK_REGISTRATIONS


def test_the_probe_bars_actually_exercise_the_blocks(derived):
    """The guard against the equivalence above being twenty-three comparisons
    of all-False columns. Not every block can fire on one fixture — some are
    directional opposites — but most must."""
    frame = bars()
    firing = sum(1 for name, spec in BLOCKS.items()
                 if spec.fn(frame, *spec.sample_args).any())
    assert firing >= len(BLOCKS) * 0.6, f"only {firing}/{len(BLOCKS)} blocks ever fire"


def test_volume_reaches_the_blocks_that_need_it():
    """`volume_surge` read False on every real frame once, because the frame it
    was handed had no volume column. The adapter rebuilds the frame from
    declared sockets, which is exactly where that could happen again."""
    frame = bars()
    assert BLOCKS["volume_surge"].fn(frame, *BLOCKS["volume_surge"].sample_args).any()


# ── C10 — warmup is the block's own, over the bound parameters ────────────

def test_warmup_comes_from_the_blocks_own_function(derived):
    lib, _ = library(list(derived.values()))
    for name, spec in BLOCKS.items():
        graph = _graph(name)
        node = resolve(graph, lib).node("n")
        assert node.warmup == int(spec.warmup(spec.sample_args)), name


def test_warmup_follows_an_override_not_the_default(derived):
    """The defect fixed earlier this session, checked on the derived vocabulary
    too: a longer EMA must warm up for longer."""
    lib, _ = library(list(derived.values()))
    graph = _graph("price_above_ema")
    graph["nodes"][1]["overrides"] = {"length": 200}

    base = resolve(_graph("price_above_ema"), lib).node("n").warmup
    assert resolve(graph, lib).node("n").warmup == 200
    assert base == 50


# ── what the interface check could not verify, said out loud ──────────────

def test_the_adapter_is_recorded_as_unchecked_rather_than_passing_silently(derived):
    """One adapter serves all twenty-three blocks, so it reaches `inputs` and
    `params` dynamically and no syntactic check can say what it reads. That is
    reported, not assumed — a check that quietly approves whatever it cannot
    read is the failure this codebase hit with F7."""
    for name, authored in derived.items():
        assert set(authored.unchecked) == {"inputs", "params"}, name


def test_a_hand_authored_component_is_still_fully_checked():
    """The control. If everything were reported unchecked the record would be
    worthless, so a kernel that reads literal keys must still be verified."""
    from tests.test_ir_authoring import rsi

    assert rsi.unchecked == ()


# ── C13 — a derived component says nothing about where it came from ───────

def test_nothing_in_a_derived_component_records_that_it_came_from_a_block(derived):
    """`block.` is in the identifier, which is a name and not a branchable
    field. What must not exist is a *property* an executor could read."""
    flat = repr(derived["zscore_gt"].definition)
    for provenance in ("group", "generated", "research", "source_kind", "family"):
        assert provenance not in flat.lower(), provenance


def test_the_family_metadata_lives_outside_the_components():
    """A generator still needs to know that `ema_slope_up` is a trend block.
    That is metadata *about* components, kept beside them — the same shape F13
    uses for presentation state, and for the same reason."""
    families = groups()
    assert set(families) == {"trend", "momentum", "volatility", "confirmation"}
    assert sum(len(names) for names in families.values()) == len(BLOCKS)
    assert "ema_slope_up" in families["trend"]


# ── the vocabulary composes, which is the point of doing this ─────────────

def test_two_blocks_compose_into_one_graph(derived):
    """Generation 1 could only compose blocks through the emitted-source
    builder. Here composition is a graph: two components, one logical AND,
    wired. That is the shape a structure search can mutate."""
    from app.ir.authoring import component
    from app.ir.authoring import socket as sock
    from app.ir.authoring import wire as w

    boolean = w("bool", **BAR)

    @component("logic.and", interface=[
        sock("a", "input", boolean), sock("b", "input", boolean),
        sock("out", "output", boolean)])
    def logic_and(params, inputs, context_inputs):
        return {"out": inputs["a"] & inputs["b"]}

    bar = w(**BAR)
    graph = {
        "format_version": 1, "kind": "graph",
        "identifier": "generated.probe", "version": 1, "display_name": "probe",
        "interface": [*(sock(f, "input", bar) for f in BAR_INPUTS),
                      sock("out", "output", boolean)],
        "nodes": [
            {"instance_id": "io_in",
             "component": {"identifier": "graph.input", "version": 1}, "overrides": {}},
            {"instance_id": "n_1",
             "component": {"identifier": "block.price_above_ema", "version": 1},
             "overrides": {"length": 20}},
            {"instance_id": "n_2",
             "component": {"identifier": "block.zscore_gt", "version": 1},
             "overrides": {"length": 50, "thr": 0.5}},
            {"instance_id": "n_and",
             "component": {"identifier": "logic.and", "version": 1}, "overrides": {}},
            {"instance_id": "io_out",
             "component": {"identifier": "graph.output", "version": 1}, "overrides": {}},
        ],
        "edges": [
            *({"source": {"instance": "io_in", "socket": f},
               "target": {"instance": n, "socket": f}}
              for f in BAR_INPUTS for n in ("n_1", "n_2")),
            {"source": {"instance": "n_1", "socket": "out"},
             "target": {"instance": "n_and", "socket": "a"}},
            {"source": {"instance": "n_2", "socket": "out"},
             "target": {"instance": "n_and", "socket": "b"}},
            {"source": {"instance": "n_and", "socket": "out"},
             "target": {"instance": "io_out", "socket": "out"}},
        ],
        "groups": [],
    }
    assert validate(graph) == []

    lib, impls = library([derived["price_above_ema"], derived["zscore_gt"], logic_and])
    frame = bars()
    resolved = resolve(graph, lib)
    out = evaluate(resolved, {f: frame[f] for f in BAR_INPUTS}, impls)

    expected = (BLOCKS["price_above_ema"].fn(frame, 20)
                & BLOCKS["zscore_gt"].fn(frame, 50, 0.5))
    assert out.outputs["out"].equals(expected)
    # C10 composes across the whole thing: the z-score's 51 bars dominate.
    assert resolved.warmup == 51
