"""
Structure search, Generation 2: a proposer that mutates graphs.

Legality is never checked here — every proposal goes through `app/ir/edit.py`,
so this module knows nothing about the format. Every entry point takes a seed:
no unseeded `Random` anywhere. C14: the proposer proposes, it does not select.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from app.ir.edit import EditRejected, add_node, connect, disconnect, remove_node, set_override

COMBINER = "logic.and"


@dataclass(frozen=True)
class Proposal:
    """One accepted mutation: what changed, and the graph it produced."""

    description: str
    graph: Mapping[str, Any]


@dataclass(frozen=True)
class Vocabulary:
    """What a proposer may reach for."""

    blocks: tuple[str, ...]
    bar_inputs: tuple[str, ...]
    defaults: Mapping[str, Mapping[str, Any]]
    # Per-block declared inputs (F4). Falls back to `bar_inputs` for a block
    # that has not declared, so a partial vocabulary still wires legally.
    block_inputs: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]
    families: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]


def _predicate_nodes(graph: Mapping[str, Any], vocabulary: Vocabulary) -> list[str]:
    placed = {f"block.{name}" for name in vocabulary.blocks}
    return [n["instance_id"] for n in graph["nodes"]
            if n["component"]["identifier"] in placed]


def _combiner_nodes(graph: Mapping[str, Any]) -> list[str]:
    return [n["instance_id"] for n in graph["nodes"]
            if n["component"]["identifier"] == COMBINER]


def _boolean_edges(graph: Mapping[str, Any], vocabulary: Vocabulary) -> list[dict]:
    """Edges carrying a predicate result — the places structure can be spliced."""
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
    """Instance ids derive from the graph's contents, never from an external
    counter, so replaying a seed against a graph agrees."""
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
    for field in (vocabulary.block_inputs or {}).get(block, vocabulary.bar_inputs):
        out = connect(out, ("io_in", field), (instance, field))
    return out, instance


# ── the mutations ─────────────────────────────────────────────────────────
# Every one preserves the invariant that each node input is fed — stricter than
# §3, which admits dangling inputs that cannot be evaluated.

def add_predicate(graph: Mapping[str, Any], vocabulary: Vocabulary,
                  rng: random.Random) -> Proposal | None:
    """Splice a new combiner into an existing edge, with a new block on its
    other input."""
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
    input through to where its output went."""
    predicates = _predicate_nodes(graph, vocabulary)
    if len(predicates) <= 1:
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

    Drop-then-add rather than an in-place identifier edit: the replacement's
    overrides are its own and do not carry over.
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
    """Exchange where two predicates feed — an exchange rather than a move, so
    every input stays fed."""
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
    """Move one parameter."""
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

    An inapplicable mutation returns `None` and the next is tried; `EditRejected`
    is deliberately not caught, since it means a defect in this module.
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
    """`steps` successive mutations, each applied to the last accepted graph."""
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
