"""
Structure search, bound to what produced it (RFC 0001 F14).

The searcher exists before any objective does, and that ordering is the point:
a run whose graph and component versions were never recorded cannot be
re-scored later, so adding binding late leaves the whole corpus permanently
unattributable. Every research Finding on this platform before 2026-08 is
exactly that, which is why these tests assert the binding is *correct* —
`validate_experiment(record, graph)` — and never merely that the fields exist.
"""
from __future__ import annotations

import pytest

from app.ir.authoring import library
from app.ir.edit import set_override
from app.ir.experiment import conclude, validate_experiment, validate_finding
from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.ir_components import BAR_INPUTS, derive_all, groups
from research.strategy.builder.ir_search import (
    Exploration,
    SearchRejected,
    explore,
    run_once,
)
from research.strategy.builder.propose import Vocabulary
from research_tests.test_ir_propose import BAR, bars, logic_and, seed_graph


@pytest.fixture(scope="module")
def lib():
    return library([*derive_all(**BAR).values(), logic_and])


@pytest.fixture(scope="module")
def vocabulary():
    return Vocabulary(
        blocks=tuple(sorted(BLOCKS)),
        bar_inputs=BAR_INPUTS,
        block_inputs={name: tuple(spec.inputs) for name, spec in BLOCKS.items()},
        defaults={name: dict(zip([p for p, _ in spec.params], spec.sample_args))
                  for name, spec in BLOCKS.items()},
        families=groups(),
    )


@pytest.fixture(scope="module")
def walk(vocabulary, lib):
    return explore(seed_graph(), vocabulary, lib, bars(), seed=5, steps=12)


# ── the binding is correct, not merely present ────────────────────────────

def test_every_record_binds_to_the_graph_that_produced_it(walk):
    """The F14 check with the graph passed in. Without it this asserts only
    that fields are populated — and the failure mode F14 exists for is a
    *stale* binding, which populates every field and names last week's run."""
    assert len(walk.steps) >= 10
    for step in walk.steps:
        assert validate_experiment(step.record, step.resolved) == [], step.record.experiment_id


def test_a_record_from_one_step_does_not_validate_against_another(walk):
    """The converse, or the test above passes on a searcher that binds every
    record to the same graph."""
    first, later = walk.steps[0], walk.steps[-1]
    violations = validate_experiment(first.record, later.resolved)
    assert violations, "a record bound to the seed validated against a 12-step descendant"
    assert {v.path for v in violations} & {"$.node_identities", "$.component_versions",
                                           "$.graph"}


def test_the_record_reaches_versions_only_resolution_can_see(walk):
    """Component versions and node cache identities do not exist in the
    authored graph — they are what resolution computed. A record assembled
    from the spec could not carry them, which is why `record()` takes a
    `ResolvedGraph` and has no parameter for being told them."""
    step = walk.steps[0]
    versions = set(step.record.component_versions)

    assert ("block.price_above_ema", 1) in versions
    assert ("logic.and", 1) in versions
    assert not {v for v in versions if v[0].startswith("graph.")}, \
        "boundary nodes survived into the binding; resolution removes them"

    authored = {n["instance_id"] for n in step.graph["nodes"]}
    for instance, cache_id in step.record.node_identities.items():
        assert cache_id.startswith("sha256:"), instance
    assert set(step.record.node_identities) < authored, \
        "node identities are the resolved leaves, not the authored nodes"


def test_one_binding_never_covers_two_different_graphs(walk):
    """Bindings are not asserted all-distinct: a lineage can return to an
    earlier structure (add a predicate, drop it again), and the same graph over
    the same bars *is* the same binding — that is the address being correct,
    not colliding. What must never happen is the reverse."""
    by_binding: dict[str, list] = {}
    for step in walk.steps:
        assert step.record.binding.startswith("sha256:")
        by_binding.setdefault(step.record.binding, []).append(_canonical(step.graph))

    for graphs in by_binding.values():
        assert all(g == graphs[0] for g in graphs), "one binding over two graphs"
    assert len(by_binding) > len(walk.steps) // 2


def _canonical(graph) -> tuple:
    """Nodes and edges as sets — two graphs differing only in the order edits
    happened to leave their edge list in are the same graph."""
    return (
        tuple(sorted((n["instance_id"], n["component"]["identifier"],
                      n["component"]["version"], tuple(sorted(n.get("overrides", {}).items())))
                     for n in graph["nodes"])),
        tuple(sorted((e["source"]["instance"], e["source"]["socket"],
                      e["target"]["instance"], e["target"]["socket"])
                     for e in graph["edges"])),
    )


# ── determinism, because a binding to an unreplayable run is a fiction ─────

def test_the_same_seed_produces_identical_bindings(vocabulary, lib):
    first = explore(seed_graph(), vocabulary, lib, bars(), seed=3, steps=8)
    second = explore(seed_graph(), vocabulary, lib, bars(), seed=3, steps=8)
    assert [r.binding for r in first.records] == [r.binding for r in second.records]
    assert [r.experiment_id for r in first.records] == \
           [r.experiment_id for r in second.records]
    assert [p.description for p in first.proposals] == \
           [p.description for p in second.proposals]


def test_a_different_seed_produces_different_bindings(vocabulary, lib):
    first = explore(seed_graph(), vocabulary, lib, bars(), seed=3, steps=8)
    other = explore(seed_graph(), vocabulary, lib, bars(), seed=4, steps=8)
    assert [r.binding for r in first.records] != [r.binding for r in other.records]


def test_experiment_ids_are_derived_from_the_walk_not_a_counter(vocabulary, lib):
    walk = explore(seed_graph(), vocabulary, lib, bars(), seed=9, steps=4)
    ids = [r.experiment_id for r in walk.records]
    assert len(set(ids)) == len(ids), "two runs sharing an id are two runs nobody can tell apart"
    assert ids[0] == "search/9/000"
    assert ids == sorted(ids)


def test_there_is_no_unseeded_randomness_or_clock_in_the_searcher():
    import re

    source = _source()
    assert re.search(r"random\.Random\(\s*\)", source) is None
    for clock in ("import time", "from time", "import datetime", "from datetime",
                  "time.time", "uuid", "random.choice("):
        assert clock not in source, clock


# ── the data digest ───────────────────────────────────────────────────────

def test_the_data_digest_follows_the_bars(vocabulary, lib):
    """The same graph over different bars is a different result. A digest that
    did not move would let a finding from January support a claim about June."""
    same = bars()
    a = explore(seed_graph(), vocabulary, lib, bars(), seed=1, steps=2)
    b = explore(seed_graph(), vocabulary, lib, same, seed=1, steps=2)
    c = explore(seed_graph(), vocabulary, lib, bars(n=300), seed=1, steps=2)

    assert a.records[0].data_digest == b.records[0].data_digest
    assert a.records[0].data_digest != c.records[0].data_digest
    assert a.records[0].binding != c.records[0].binding


# ── every explored graph is legal ─────────────────────────────────────────

def test_every_explored_graph_validates_resolves_and_evaluates(vocabulary, lib):
    """The proposer's guarantee, re-asserted at the point runs are recorded:
    a record of an illegal graph is a measurement of nothing."""
    from app.ir.resolve import resolve
    from app.ir.runtime import evaluate
    from app.ir.validate import validate

    components, impls = lib
    walk = explore(seed_graph(), vocabulary, lib, bars(), seed=21, steps=25)
    assert len(walk.steps) >= 20

    for step in walk.steps:
        assert validate(step.graph, components.components) == []
        out = evaluate(resolve(step.graph, components), bars(), impls)
        assert out.outputs["out"].dtype == bool


def test_an_illegal_graph_is_refused_rather_than_recorded(lib):
    """Fail closed. Recording it would put an unattributable row in the corpus,
    which is the exact debt §7 documents."""
    graph = seed_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["instance_id"] != "c_1"]

    with pytest.raises(SearchRejected):
        run_once(graph, lib, bars(), experiment_id="search/0/000")


def test_the_record_carries_what_the_run_measured(walk):
    """Counts, from `evaluate` — a record whose result is empty binds nothing
    to the graph it took so much care to identify."""
    for step in walk.steps:
        result = step.record.result
        assert result["outputs"]["out"]["bars"] == 260
        assert result["warmup"] > 0
    assert len({step.record.result["outputs"]["out"]["true"]
                for step in walk.steps}) > 1, "every graph measured identically"


# ── findings (C14: this module explores, it never judges) ──────────────────

def test_a_finding_validates_against_its_experiment_and_not_a_moved_one(
        vocabulary, lib):
    """A finding carries its experiment's binding. Move one parameter, re-run,
    and the finding must no longer validate — "the experiment was re-run or
    re-parameterised and this finding was left behind"."""
    walk = explore(seed_graph(), vocabulary, lib, bars(), seed=2, steps=1)
    original = walk.records[0]
    finding = conclude("f_1", original, {"fires": original.result["outputs"]["out"]["true"]})

    assert validate_finding(finding, original) == []

    moved = set_override(seed_graph(), "n_1", "length", 60)
    _, rerun = run_once(moved, lib, bars(), experiment_id="search/2/000")

    assert rerun.experiment_id == original.experiment_id
    assert rerun.binding != original.binding
    violations = validate_finding(finding, rerun)
    assert [v.path for v in violations] == ["$.binding"]


def test_the_searcher_does_not_score_anything():
    """C14 — components compute, searchers search. The moment a fitness lands
    in here, "explore and record" becomes "sweep and keep the best", which is
    Generation 1 with extra steps."""
    source = _source().lower()
    for scoring in ("sharpe", "score(", "fitness", "rank(", "objective", "pnl",
                    "best", "select("):
        assert scoring not in source, scoring

    assert set(Exploration.__dataclass_fields__) == {"seed", "steps"}


def test_the_searcher_owns_no_opinion_about_the_format():
    source = _source()
    assert "format_version" not in source
    assert "from app.ir.experiment import" in source
    assert "from research.strategy.builder.propose import" in source


def _source() -> str:
    import pathlib

    return (pathlib.Path(__file__).resolve().parents[1]
            / "research/strategy/builder/ir_search.py").read_text()
