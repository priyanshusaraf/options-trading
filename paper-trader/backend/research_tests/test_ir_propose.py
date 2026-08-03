"""
Structure search: the proposer, and the one property that matters first.

**Legality.** Every graph a proposer emits must validate, resolve and evaluate.
That is worth establishing before any search objective exists, because a
proposer that emits illegal graphs makes every downstream statistic meaningless
and there is no way to retrofit confidence in numbers already recorded. This
platform has been there: every research finding before 2026-08 is unusable as a
baseline.

So the central test here is a thousand random mutations, every one of which must
survive `validate → resolve → evaluate`. Not a sample of the interesting ones —
all of them.
"""
from __future__ import annotations

import copy
import math

import pandas as pd
import pytest

from app.ir.authoring import component, library, socket, wire
from app.ir.resolve import resolve
from app.ir.runtime import evaluate
from app.ir.validate import validate
from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.ir_components import BAR_INPUTS, derive_all, groups
from research.strategy.builder.propose import (
    MUTATIONS,
    Proposal,
    Vocabulary,
    add_predicate,
    drop_predicate,
    lineage,
    propose,
    rewire,
    swap_predicate,
)

BAR = {"instrument": "NIFTY", "timeframe": "15m"}
BOOL = wire("bool", **BAR)
SERIES = wire(**BAR)


@component("logic.and", interface=[
    socket("a", "input", BOOL), socket("b", "input", BOOL),
    socket("out", "output", BOOL)])
def logic_and(params, inputs):
    return {"out": inputs["a"] & inputs["b"]}


@pytest.fixture(scope="module")
def derived():
    return derive_all(**BAR)


@pytest.fixture(scope="module")
def vocabulary():
    return Vocabulary(
        blocks=tuple(sorted(BLOCKS)),
        bar_inputs=BAR_INPUTS,
        defaults={name: dict(zip([p for p, _ in spec.params], spec.sample_args))
                  for name, spec in BLOCKS.items()},
        block_inputs={name: tuple(spec.inputs) for name, spec in BLOCKS.items()},
        families=groups(),
    )


@pytest.fixture(scope="module")
def lib(derived):
    return library([*derived.values(), logic_and])


def seed_graph() -> dict:
    """The smallest thing worth mutating: two predicates into two combiners.

    Every input is fed, which is the invariant every mutation preserves — and
    since 2026-08-03 the validator enforces it too, given a library (F8).
    """
    bar = SERIES
    nodes = [
        {"instance_id": "io_in", "component": {"identifier": "graph.input", "version": 1},
         "overrides": {}},
        {"instance_id": "n_1",
         "component": {"identifier": "block.price_above_ema", "version": 1},
         "overrides": {"length": 50}},
        {"instance_id": "n_2", "component": {"identifier": "block.zscore_gt", "version": 1},
         "overrides": {"length": 50, "thr": 0.0}},
        {"instance_id": "c_1", "component": {"identifier": "logic.and", "version": 1},
         "overrides": {}},
        {"instance_id": "io_out", "component": {"identifier": "graph.output", "version": 1},
         "overrides": {}},
    ]
    edges = [
        *({"source": {"instance": "io_in", "socket": f},
           "target": {"instance": n, "socket": f}}
          for n, blk in (("n_1", "price_above_ema"), ("n_2", "zscore_gt"))
          for f in BLOCKS[blk].inputs),
        {"source": {"instance": "n_1", "socket": "out"},
         "target": {"instance": "c_1", "socket": "a"}},
        {"source": {"instance": "n_2", "socket": "out"},
         "target": {"instance": "c_1", "socket": "b"}},
        {"source": {"instance": "c_1", "socket": "out"},
         "target": {"instance": "io_out", "socket": "out"}},
    ]
    return {
        "format_version": 1, "kind": "graph",
        "identifier": "generated.seed", "version": 1, "display_name": "seed",
        "interface": [*(socket(f, "input", bar) for f in BAR_INPUTS),
                      socket("out", "output", BOOL)],
        "nodes": nodes, "edges": edges, "groups": [],
    }


def bars(n=260):
    idx = pd.date_range("2026-01-01 09:15", periods=n, freq="15min", tz="Asia/Kolkata")
    close = pd.Series([1000 + math.sin(i / 8.0) * 7 + math.sin(i / 37.0) * 18
                       for i in range(n)], index=idx, dtype=float)
    return {
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 2.0, "low": close - 2.0, "close": close,
        "volume": pd.Series([900 + (i % 19) * 30 for i in range(n)],
                            index=idx, dtype=float),
    }


def test_the_seed_graph_is_itself_legal(lib):
    graph = seed_graph()
    assert validate(graph) == []
    components, impls = lib
    out = evaluate(resolve(graph, components), bars(), impls)
    assert out.outputs["out"].dtype == bool


# ── the property: every proposal is a legal graph ─────────────────────────

def test_a_thousand_mutations_all_produce_legal_graphs(vocabulary, lib):
    """The central claim, and the reason to establish it before any objective
    exists: a proposer that emits illegal graphs makes every statistic
    downstream of it meaningless, and confidence in numbers already recorded
    cannot be retrofitted.

    `validate` is the format, `resolve` is §4, and `evaluate` is the runtime —
    all three, because a graph can pass the first and be unresolvable, or
    resolve and have a socket nothing produces.
    """
    components, impls = lib
    inputs = bars()
    graph = seed_graph()
    accepted = 0

    for seed in range(1000):
        proposal = propose(graph, vocabulary, seed=seed)
        if proposal is None:
            continue
        accepted += 1
        assert validate(proposal.graph) == [], proposal.description
        resolved = resolve(proposal.graph, components)
        out = evaluate(resolved, inputs, impls)
        assert out.outputs["out"].dtype == bool, proposal.description

    assert accepted >= 950, f"only {accepted}/1000 proposals landed"


def test_every_mutation_actually_fires_across_those_seeds(vocabulary):
    """The guard against the thousand above being one mutation a thousand
    times. Each of the five must appear, or four of them are untested and the
    legality claim covers less than it looks like it covers."""
    graph = seed_graph()
    seen = set()
    for seed in range(1000):
        proposal = propose(graph, vocabulary, seed=seed)
        if proposal is not None:
            seen.add(proposal.description.split()[0])
    assert seen == {"add", "drop", "swap", "rewire", "retune"}, seen


def test_a_long_lineage_stays_legal(vocabulary, lib):
    """Mutations compound. A proposal that is legal against the seed but not
    against a graph forty edits deep would surface only here."""
    components, impls = lib
    chain = lineage(seed_graph(), vocabulary, seed=7, steps=40)
    assert len(chain) >= 30

    for proposal in chain:
        assert validate(proposal.graph) == [], proposal.description
    final = chain[-1].graph
    out = evaluate(resolve(final, components), bars(), impls)
    assert out.outputs["out"].dtype == bool


# ── determinism, because F14 binds findings to what produced them ─────────

def test_the_same_seed_proposes_the_same_mutation(vocabulary):
    graph = seed_graph()
    first = propose(graph, vocabulary, seed=42)
    second = propose(graph, vocabulary, seed=42)
    assert first.description == second.description
    assert first.graph == second.graph


def test_different_seeds_explore_different_structures(vocabulary):
    graph = seed_graph()
    shapes = {propose(graph, vocabulary, seed=s).description for s in range(40)}
    assert len(shapes) > 10, "the proposer is barely exploring"


def test_a_lineage_replays_exactly(vocabulary):
    a = lineage(seed_graph(), vocabulary, seed=11, steps=15)
    b = lineage(seed_graph(), vocabulary, seed=11, steps=15)
    assert [p.description for p in a] == [p.description for p in b]


def test_there_is_no_unseeded_randomness_in_the_proposer():
    """A search whose proposals cannot be replayed produces findings that
    cannot be re-derived, and F14 binds a finding to what produced it. A
    `Random()` without a seed would make that binding a fiction."""
    import pathlib
    import re

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "research/strategy/builder/propose.py").read_text()
    assert re.search(r"random\.Random\(\s*\)", source) is None
    assert "random.choice(" not in source, "module-level RNG is not seedable"
    for clock in ("import time", "from time", "import datetime", "from datetime",
                  "time.time", "uuid"):
        assert clock not in source, clock


# ── the proposer does not mutate what it was given ────────────────────────

def test_proposing_does_not_touch_the_input_graph(vocabulary):
    graph = seed_graph()
    before = copy.deepcopy(graph)
    for seed in range(50):
        propose(graph, vocabulary, seed=seed)
    assert graph == before


# ── what each mutation is for ─────────────────────────────────────────────

def test_rewire_is_the_mutation_generation_1_could_not_express(vocabulary):
    """Generation 1 searched parameters over a fixed composition; there was no
    representation in which "move this predicate to a different combiner" is a
    thing you can say. This test is that sentence, executed."""
    import random

    # Grown first, so the two predicates being exchanged feed *different*
    # combiners. On the two-node seed a rewire only swaps a↔b on one `and`,
    # which is structurally real and semantically a no-op — a weak thing to
    # demonstrate the mutation with.
    graph = seed_graph()
    for seed in range(6):
        grown = add_predicate(graph, vocabulary, random.Random(seed))
        if grown is not None:
            graph = grown.graph

    proposal = None
    for seed in range(200):
        proposal = rewire(graph, vocabulary, random.Random(seed))
        if proposal is not None and _targets(proposal.graph) != _targets(graph):
            break
    assert proposal is not None
    assert validate(proposal.graph) == []
    assert _targets(proposal.graph) != _targets(graph)
    assert len(proposal.graph["nodes"]) == len(graph["nodes"]), "rewire adds no nodes"
    assert len(proposal.graph["edges"]) == len(graph["edges"]), "rewire adds no edges"


def _targets(graph) -> set:
    """Every edge as (source, target instance, target socket) — the socket
    matters, or an exchange between the two inputs of one node reads as no
    change at all."""
    return {(e["source"]["instance"], e["source"]["socket"],
             e["target"]["instance"], e["target"]["socket"]) for e in graph["edges"]}


def test_drop_never_empties_the_graph(vocabulary):
    """A graph with no predicates is legal §3 and meaningless research. The
    proposer refuses rather than emitting it — the distinction between "the
    format allows it" and "it is worth measuring" is the searcher's to make."""
    import random

    graph = seed_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["instance_id"] != "n_2"]
    graph["edges"] = [e for e in graph["edges"]
                      if "n_2" not in (e["source"]["instance"], e["target"]["instance"])]

    assert drop_predicate(graph, vocabulary, random.Random(0)) is None


def test_swap_replaces_a_block_without_carrying_its_parameters(vocabulary):
    """An override that meant `length` for an EMA does not mean `length` for a
    volume surge, and F10 gives an override no way to say which it was. So swap
    is drop-then-add, and the replacement gets its own defaults."""
    import random

    graph = seed_graph()
    proposal = None
    for seed in range(50):
        proposal = swap_predicate(graph, vocabulary, random.Random(seed))
        if proposal is not None:
            break
    assert proposal is not None and validate(proposal.graph) == []

    for node in proposal.graph["nodes"]:
        identifier = node["component"]["identifier"]
        if identifier.startswith("block."):
            name = identifier.removeprefix("block.")
            declared = {p for p, _ in BLOCKS[name].params}
            assert set(node["overrides"]) <= declared, name


def test_add_feeds_the_new_node_its_bars(vocabulary, lib):
    """A placed node with unwired inputs would resolve — its sockets are simply
    unfed — and then fail at evaluation. The mutation wires them in the same
    proposal, which is why legality is asserted through `evaluate` and not only
    through `validate`."""
    import random

    components, impls = lib
    graph = seed_graph()
    proposal = add_predicate(graph, vocabulary, random.Random(3))
    assert proposal is not None

    evaluate(resolve(proposal.graph, components), bars(), impls)


# ── the searcher boundary (C14) ───────────────────────────────────────────

def test_the_proposer_does_not_score_anything():
    """"Components compute; searchers search" — and a proposer proposes. What
    to keep is the evaluator's decision, and mixing the two is how search
    quietly becomes sweep a second time."""
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "research/strategy/builder/propose.py").read_text()
    for scoring in ("sharpe", "score(", "fitness", "rank(", "objective", "pnl"):
        assert scoring not in source.lower(), scoring

    assert set(Proposal.__dataclass_fields__) == {"description", "graph"}


def test_the_proposer_owns_no_opinion_about_the_format():
    """Every proposal goes through `app/ir/edit.py`. A proposer with its own
    idea of what a legal graph is would be a second implementation of §3 —
    the defect C12 exists because of."""
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "research/strategy/builder/propose.py").read_text()
    assert "validate(" not in source
    assert "format_version" not in source
    assert "from app.ir.edit import" in source


def test_all_five_mutations_are_reachable_from_the_registry():
    assert len(MUTATIONS) == 5
    assert {m.__name__ for m in MUTATIONS} == {
        "add_predicate", "drop_predicate", "swap_predicate", "rewire", "retune"}
