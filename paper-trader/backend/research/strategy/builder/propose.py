"""
Structure search, Generation 2: a proposer that mutates graphs.

Generation 1 searched *parameters* over a fixed composition. RFC 0001 C14 names
the ceiling that creates — "vectorbt builds parameter grids into the indicator
contract itself, which silently defines *search = parameter sweeping* for
everything downstream, and the research plane inherited that shape. **Structure
search is not reachable from a design where components sweep themselves.**" With
the block vocabulary expressed as components, the thing being searched can be
the graph.

**Legality is the property, and it is not checked here.** Every proposal goes
through `app/ir/edit.py`, which refuses to return an artefact that violates §3.
So this module contains no validation of its own and no knowledge of the format
— a proposal is either an edit the gate accepted or it is nothing. That is why
the writing half of the editor plane was built before this one: a proposer with
its own idea of what a legal graph is would be a second implementation of §3,
which is the defect C12 exists because of.

**Determinism.** Every proposer takes a seed and derives its choices from it. A
search whose proposals cannot be replayed produces findings that cannot be
re-derived, and F14 binds findings to what produced them — a `Random` seeded
from the clock would make that binding a fiction. There is no `Random()` without
a seed anywhere in this file.

**What this deliberately does not do.** It does not score, rank, or select. C14
again: components compute, searchers search — and a *proposer* proposes. What to
keep is the evaluator's decision, and mixing the two is how "search" quietly
becomes "sweep" a second time.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from app.ir.edit import EditRejected, add_node, connect, disconnect, remove_node, set_override

# The proposer only ever wires boolean predicates into a combiner, which is the
# shape the current block vocabulary admits: every block returns Series[bool]
# (Appendix A.2 records that as the library's limitation, not the IR's).
COMBINER = "logic.and"


@dataclass(frozen=True)
class Proposal:
    """One accepted mutation: what changed, and the graph it produced."""

    description: str
    graph: Mapping[str, Any]


@dataclass(frozen=True)
class Vocabulary:
    """What a proposer may reach for.

    `blocks` are the predicate components it may place; `bar_inputs` are the
    graph interface sockets every block consumes; `defaults` supplies a starting
    override per block so a placed node is immediately meaningful.
    """

    blocks: tuple[str, ...]
    bar_inputs: tuple[str, ...]
    defaults: Mapping[str, Mapping[str, Any]]
    families: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]


def _predicate_nodes(graph: Mapping[str, Any], vocabulary: Vocabulary) -> list[str]:
    placed = {f"block.{name}" for name in vocabulary.blocks}
    return [n["instance_id"] for n in graph["nodes"]
            if n["component"]["identifier"] in placed]


def _combiner_nodes(graph: Mapping[str, Any]) -> list[str]:
    return [n["instance_id"] for n in graph["nodes"]
            if n["component"]["identifier"] == COMBINER]


def _boolean_edges(graph: Mapping[str, Any], vocabulary: Vocabulary) -> list[dict]:
    """Edges carrying a predicate result — the places structure can be spliced.

    Bar inputs are excluded: they are plumbing, and rewiring `close` into a
    different node is not a structural idea, it is a type error waiting to be
    one.
    """
    carriers = set(_predicate_nodes(graph, vocabulary)) | set(_combiner_nodes(graph))
    return [e for e in graph["edges"]
            if e["source"]["instance"] in carriers and e["source"]["socket"] == "out"]


def _target_of(graph: Mapping[str, Any], instance: str) -> dict | None:
    return next((e["target"] for e in graph["edges"]
                 if e["source"]["instance"] == instance
                 and e["source"]["socket"] == "out"), None)


def _sources_into(graph: Mapping[str, Any], instance: str) -> dict[str, dict]:
    return {e["target"]["socket"]: e["source"] for e in graph["edges"]
            if e["target"]["instance"] == instance}


def _next_id(graph: Mapping[str, Any], stem: str) -> str:
    """Instance ids derive from the graph's contents, never from a counter that
    lives outside it — the same discipline C7 imposes on resolution, so two
    proposers replaying the same seed against the same graph agree."""
    existing = {n["instance_id"] for n in graph["nodes"]}
    n = 1
    while f"{stem}_{n}" in existing:
        n += 1
    return f"{stem}_{n}"


def _place_predicate(graph: Mapping[str, Any], vocabulary: Vocabulary,
                     block: str) -> tuple[Mapping[str, Any], str]:
    """Add a block node and feed it the bars. Never leaves an input unfed."""
    instance = _next_id(graph, "n")
    out = add_node(graph, instance, f"block.{block}", 1,
                   dict(vocabulary.defaults.get(block, {})))
    for field in vocabulary.bar_inputs:
        out = connect(out, ("io_in", field), (instance, field))
    return out, instance


# ── the mutations ─────────────────────────────────────────────────────────
#
# Every one of them preserves the graph's invariant: each node input is fed.
# That is stricter than §3 requires and deliberately so — a graph with a
# dangling input is a legal artefact that cannot be evaluated, and a proposer
# emitting those would make the legality claim about the format rather than
# about the thing being searched.

def add_predicate(graph: Mapping[str, Any], vocabulary: Vocabulary,
                  rng: random.Random) -> Proposal | None:
    """Splice a new combiner into an existing edge, with a new block on its
    other input. Always applicable, and always fully fed."""
    edges = _boolean_edges(graph, vocabulary)
    if not edges:
        return None
    spliced = rng.choice(edges)
    source, target = spliced["source"], spliced["target"]

    block = rng.choice(vocabulary.blocks)
    out, instance = _place_predicate(graph, vocabulary, block)
    combiner = _next_id(out, "c")
    out = add_node(out, combiner, COMBINER, 1)
    out = disconnect(out, (source["instance"], source["socket"]),
                     (target["instance"], target["socket"]))
    out = connect(out, (source["instance"], source["socket"]), (combiner, "a"))
    out = connect(out, (instance, "out"), (combiner, "b"))
    out = connect(out, (combiner, "out"), (target["instance"], target["socket"]))
    return Proposal(
        f"add {block} as {instance} through {combiner} "
        f"before {target['instance']}.{target['socket']}", out)


def drop_predicate(graph: Mapping[str, Any], vocabulary: Vocabulary,
                   rng: random.Random) -> Proposal | None:
    """Remove a block and the combiner it fed, splicing that combiner's other
    input through to where its output went. Nothing is left dangling."""
    predicates = _predicate_nodes(graph, vocabulary)
    if len(predicates) <= 1:
        # A graph with no predicates is legal §3 and meaningless research.
        return None

    victim = rng.choice(predicates)
    into = _target_of(graph, victim)
    if into is None or into["instance"] not in _combiner_nodes(graph):
        return None
    combiner = into["instance"]

    feeds = _sources_into(graph, combiner)
    survivor = next((src for socket, src in feeds.items() if socket != into["socket"]),
                    None)
    onward = _target_of(graph, combiner)
    if survivor is None or onward is None:
        return None

    out = remove_node(graph, victim)
    out = remove_node(out, combiner)
    out = connect(out, (survivor["instance"], survivor["socket"]),
                  (onward["instance"], onward["socket"]))
    return Proposal(f"drop {victim} and {combiner}", out)


def swap_predicate(graph: Mapping[str, Any], vocabulary: Vocabulary,
                   rng: random.Random) -> Proposal | None:
    """Replace one block with another, keeping its position in the structure.

    Expressed as drop-then-add rather than an in-place identifier edit, because
    the replacement's parameters are its own: an override that meant `length`
    for an EMA does not mean `length` for a volume surge, and F10 gives an
    override no way to say which it was.
    """
    predicates = _predicate_nodes(graph, vocabulary)
    if not predicates:
        return None
    victim = rng.choice(predicates)
    into = _target_of(graph, victim)
    if into is None:
        return None

    block = rng.choice(vocabulary.blocks)
    out = remove_node(graph, victim)
    out, instance = _place_predicate(out, vocabulary, block)
    out = connect(out, (instance, "out"), (into["instance"], into["socket"]))
    return Proposal(f"swap {victim} → {block} as {instance}", out)


def rewire(graph: Mapping[str, Any], vocabulary: Vocabulary,
           rng: random.Random) -> Proposal | None:
    """Exchange where two predicates feed.

    The mutation that is *only* possible once structure is the search space —
    Generation 1 had no representation in which this is expressible. Expressed
    as an exchange rather than a move, so every input stays fed.
    """
    predicates = _predicate_nodes(graph, vocabulary)
    if len(predicates) < 2:
        return None
    left, right = rng.sample(sorted(predicates), 2)
    a, b = _target_of(graph, left), _target_of(graph, right)
    if a is None or b is None or (a["instance"], a["socket"]) == (b["instance"], b["socket"]):
        return None

    out = disconnect(graph, (left, "out"), (a["instance"], a["socket"]))
    out = disconnect(out, (right, "out"), (b["instance"], b["socket"]))
    out = connect(out, (left, "out"), (b["instance"], b["socket"]))
    out = connect(out, (right, "out"), (a["instance"], a["socket"]))
    return Proposal(f"rewire {left} ↔ {right}", out)


def retune(graph: Mapping[str, Any], vocabulary: Vocabulary,
           rng: random.Random) -> Proposal | None:
    """Move one parameter. Included so structure search subsumes Generation 1
    rather than replacing it — but as *one* mutation among five, not as the
    definition of search."""
    candidates = [n for n in graph["nodes"]
                  if n["instance_id"] in _predicate_nodes(graph, vocabulary)
                  and n.get("overrides")]
    if not candidates:
        return None
    node = rng.choice(candidates)
    name = rng.choice(sorted(node["overrides"]))
    value = node["overrides"][name]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    scale = rng.choice((0.5, 0.75, 1.5, 2.0))
    moved = max(1, int(round(value * scale))) if isinstance(value, int) \
        else round(value * scale, 6)
    return Proposal(f"retune {node['instance_id']}.{name} {value} → {moved}",
                    set_override(graph, node["instance_id"], name, moved))


MUTATIONS: tuple[Callable[..., Proposal | None], ...] = (
    add_predicate, drop_predicate, swap_predicate, rewire, retune,
)


# ── the proposer ──────────────────────────────────────────────────────────

def propose(graph: Mapping[str, Any], vocabulary: Vocabulary, *, seed: int,
            attempts: int = 8) -> Proposal | None:
    """One legal mutation of `graph`, or `None` if none of the attempts landed.

    A mutation that cannot apply — dropping the last predicate, rewiring with
    one combiner — returns `None` and the next is tried. A mutation the **gate**
    rejects is not caught: an `EditRejected` here means the proposer built
    something the format forbids, which is a defect in this module rather than
    an unlucky draw, and swallowing it would let the search quietly degrade to
    whichever mutations happen to be legal.
    """
    rng = random.Random(seed)
    for _ in range(attempts):
        mutation = rng.choice(MUTATIONS)
        proposal = mutation(graph, vocabulary, rng)
        if proposal is not None:
            return proposal
    return None


def lineage(graph: Mapping[str, Any], vocabulary: Vocabulary, *, seed: int,
            steps: int) -> list[Proposal]:
    """`steps` successive mutations, each applied to the last accepted graph.

    Returned as the whole chain rather than only the endpoint, because a
    finding about the endpoint is worth nothing without the path — the same
    reason F14 binds a result to everything that produced it.
    """
    rng = random.Random(seed)
    out: list[Proposal] = []
    current = graph
    for step in range(steps):
        proposal = propose(current, vocabulary, seed=rng.randrange(2**31))
        if proposal is None:
            break
        out.append(proposal)
        current = proposal.graph
    return out


__all__ = ["Proposal", "Vocabulary", "propose", "lineage", "MUTATIONS", "EditRejected"]
