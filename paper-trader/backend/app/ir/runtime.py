"""
The component runtime — the thing that *consumes* a resolved graph.

RFC 0001 §1.3 stops at "Execution — the runtime evaluates the resolved graph;
mechanism out of scope". This module is that runtime for the linear,
completed-candle case the platform actually trades. It is deliberately the very
next thing built after the resolver: a `ResolvedGraph` that nothing evaluates
would be a correct mechanism wired to nothing, which is this codebase's
documented defining defect.

**What the runtime binds that the language does not.** `kernels.py` holds what
a kernel *declares* — warmup, purity, cache identity. This module holds what a
kernel *does*, keyed by the same content address. The split is load-bearing:
resolution reads only declarations, so it stays a pure function of the
specification (C2, C6), and the runtime is the only layer that needs the
implementations at all.

**Three §4 clauses become empirical here rather than merely declared:**

- **C10 (warmup)** — resolution composes a warmup count per node. The runtime
  is what makes it mean something: `EvaluationResult.warmup` is the number of
  leading bars whose values are not yet trustworthy, and `settled()` removes
  them.
- **C11 (lookahead)** — "prevented structurally… a component MUST NOT be able
  to violate it by convention". `check_causality` is the structural test: feed
  a graph a prefix of the bars and the whole of them, and every value the
  prefix produced must be unchanged. A kernel that peeks at a future bar cannot
  survive that, whatever its author intended.
- **C8/C9 (cache identity and purity)** — evaluation memoises on the cache
  identity resolution computed, and never memoises a node whose kernel declares
  an impurity policy.

**C13 is structural here too, by construction:** the runtime looks a kernel up
by its content address and has no other key. There is nowhere for it to learn
where a component came from, so there is nothing for it to branch on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from app.ir.kernels import PURE
from app.ir.resolve import ResolvedGraph, ResolvedNode, topological_order

# A kernel implementation. It is handed its bound parameters and its inputs by
# socket name, and returns its outputs by socket name. It is not handed the
# graph, its own instance id, or anything else that would let it behave
# differently depending on where it was used.
Kernel = Callable[[Mapping[str, Any], Mapping[str, pd.Series]], Mapping[str, pd.Series]]


class EvaluationError(Exception):
    """A resolved graph that cannot be evaluated, named by the clause it fails."""

    def __init__(self, clause: str, instance_id: str, message: str) -> None:
        super().__init__(f"{clause} at {instance_id}: {message}")
        self.clause = clause
        self.instance_id = instance_id
        self.message = message


@dataclass(frozen=True)
class EvaluationResult:
    """The graph's declared outputs, and how many leading bars are unsettled."""

    outputs: Mapping[str, pd.Series]
    values: Mapping[str, Mapping[str, pd.Series]]
    warmup: int
    cache_hits: tuple[str, ...] = ()

    def settled(self) -> dict[str, pd.Series]:
        """C10 — the outputs with the warmup prefix removed.

        A backtest that reads the first bars of an unwarmed indicator is not
        wrong loudly; it is wrong quietly, and then plausible. This is the
        method that stops that being the caller's job to remember.
        """
        return {name: series.iloc[self.warmup:] for name, series in self.outputs.items()}


@dataclass
class Cache:
    """C8 — memoisation keyed by the identity resolution computed.

    Not an LRU and not a store: a dict, because the identity is the interesting
    part and eviction policy is not a language concern.
    """

    entries: dict[str, Mapping[str, pd.Series]] = field(default_factory=dict)
    hits: list[str] = field(default_factory=list)


def evaluate(graph: ResolvedGraph, inputs: Mapping[str, pd.Series],
             implementations: Mapping[str, Kernel],
             cache: Cache | None = None) -> EvaluationResult:
    """Evaluate `graph` over `inputs`, one series per declared graph input."""
    cache = cache if cache is not None else Cache()
    hits_before = len(cache.hits)

    by_id = {n.instance_id: n for n in graph.nodes}
    order = topological_order([n.instance_id for n in graph.nodes], graph.edges)

    # Where each node's input sockets get their values: an edge, or the graph's
    # own interface one level up.
    wiring: dict[tuple[str, str], tuple[str, str]] = {}
    for edge in graph.edges:
        wiring[edge.target] = edge.source
    interface: dict[tuple[str, str], str] = {}
    for name, consumers in graph.inputs.items():
        for consumer in consumers:
            interface[consumer] = name

    produced: dict[str, Mapping[str, pd.Series]] = {}

    for instance_id in order:
        node = by_id[instance_id]
        kernel = implementations.get(node.body_ref)
        if kernel is None:
            raise EvaluationError(
                "C13", instance_id,
                f"no implementation is registered at {node.body_ref}; the "
                "runtime knows a kernel by its content address and by nothing else")

        node_inputs = _inputs_for(node, graph, wiring, interface, inputs, produced)
        produced[instance_id] = _compute(node, kernel, node_inputs, cache)

    outputs = {}
    for name, (instance_id, socket) in graph.outputs.items():
        available = produced.get(instance_id, {})
        if socket not in available:
            raise EvaluationError(
                "C3", instance_id,
                f"the graph declares an output {name!r} taken from {socket!r}, "
                "which this node did not produce")
        outputs[name] = available[socket]

    return EvaluationResult(
        outputs=MappingProxyType(outputs),
        values=MappingProxyType({k: MappingProxyType(dict(v)) for k, v in produced.items()}),
        warmup=graph.warmup,
        cache_hits=tuple(cache.hits[hits_before:]),
    )


def _inputs_for(node: ResolvedNode, graph: ResolvedGraph,
                wiring: Mapping[tuple[str, str], tuple[str, str]],
                interface: Mapping[tuple[str, str], str],
                graph_inputs: Mapping[str, pd.Series],
                produced: Mapping[str, Mapping[str, pd.Series]]) -> dict[str, pd.Series]:
    collected: dict[str, pd.Series] = {}

    for (target_id, socket), source in wiring.items():
        if target_id != node.instance_id:
            continue
        upstream = produced.get(source[0], {})
        if source[1] not in upstream:
            raise EvaluationError(
                "C3", node.instance_id,
                f"{source[0]!r} did not produce {source[1]!r}")
        collected[socket] = upstream[source[1]]

    for (target_id, socket), name in interface.items():
        if target_id != node.instance_id:
            continue
        if name not in graph_inputs:
            raise EvaluationError(
                "C3", node.instance_id,
                f"the graph input {name!r} was not supplied")
        collected[socket] = graph_inputs[name]

    return collected


def _compute(node: ResolvedNode, kernel: Kernel,
             node_inputs: Mapping[str, pd.Series], cache: Cache) -> Mapping[str, pd.Series]:
    # C9 — an impure component declares a policy, and a declared impurity is
    # exactly the claim "my output is not a function of my inputs". Caching one
    # would be caching a lie, so purity is what makes the entry legal rather
    # than a flag that makes it convenient.
    cacheable = node.purity == PURE

    if cacheable and node.cache_id in cache.entries:
        cache.hits.append(node.instance_id)
        return cache.entries[node.cache_id]

    outputs = kernel(node.params, node_inputs)
    if not isinstance(outputs, Mapping):
        raise EvaluationError("C3", node.instance_id,
                              "a kernel returns its outputs by socket name")

    _check_index(node, node_inputs, outputs)

    if cacheable:
        cache.entries[node.cache_id] = outputs
    return outputs


def _check_index(node: ResolvedNode, node_inputs: Mapping[str, pd.Series],
                 outputs: Mapping[str, pd.Series]) -> None:
    """C11's cheap half: an output cannot span bars its inputs did not.

    This catches a kernel that reindexes or resamples silently. It does not
    catch a kernel that reads a future bar and writes the answer at the present
    one — nothing local can. `check_causality` is what catches that.
    """
    if not node_inputs:
        return
    expected = next(iter(node_inputs.values())).index
    for socket, series in outputs.items():
        if not isinstance(series, pd.Series):
            raise EvaluationError("C3", node.instance_id,
                                  f"{socket!r} is not a series")
        if not series.index.equals(expected):
            raise EvaluationError(
                "C11", node.instance_id,
                f"{socket!r} spans a different set of bars than its inputs; a "
                "component may not change which bars exist")


# ── C11 — the structural test ─────────────────────────────────────────────

def check_causality(graph: ResolvedGraph, inputs: Mapping[str, pd.Series],
                    implementations: Mapping[str, Kernel],
                    prefixes: Sequence[int] | None = None) -> None:
    """Raise unless every value is a function of the bars up to and including it.

    "Lookahead MUST be prevented structurally. A component MUST NOT be able to
    violate it by convention." Convention is what a docstring claims; this is
    the measurement. Evaluate the graph on the first *n* bars and on all of
    them, and the first *n* results must be identical. A kernel that reads
    ahead — `shift(-1)`, a centred rolling window, a whole-series normalisation
    — produces different values for the same bar depending on what came after
    it, and that difference is what this sees.

    Nautilus gets this property by identity, because a bar-by-bar engine cannot
    express a forward read. §2A of the findings records that whole-series wires
    are the choice this platform made instead, and this function is the price.
    """
    length = len(next(iter(inputs.values())))
    checkpoints = prefixes if prefixes is not None else _default_prefixes(length, graph.warmup)

    full = evaluate(graph, inputs, implementations)

    for n in checkpoints:
        prefix = {name: series.iloc[:n] for name, series in inputs.items()}
        # A fresh cache: a cache hit would return the full-length answer and
        # the check would pass by not running.
        partial = evaluate(graph, prefix, implementations, cache=Cache())

        # Every node, not only the graph's outputs. A component that reads
        # ahead can have its error cancel downstream — divide two series by a
        # max neither knows yet and the comparison between them is unchanged —
        # and checking only what comes out the end would call that causal.
        for instance_id, sockets in partial.values.items():
            for socket, series in sockets.items():
                reference = full.values[instance_id][socket].iloc[:n]
                if series.equals(reference):
                    continue
                first = next((i for i, (a, b) in enumerate(zip(series, reference))
                              if a != b and (a == a or b == b)), None)
                raise EvaluationError(
                    "C11", instance_id,
                    f"with {n} of {length} bars, {socket!r} differs from the same "
                    f"bars of the full run (first at position {first}); a value "
                    "that changes when later bars arrive was read from the future")


def _default_prefixes(length: int, warmup: int) -> list[int]:
    """Checkpoints past warmup, where the values are settled and comparable."""
    first = max(warmup + 1, 1)
    if first >= length:
        return [length]
    return sorted({first, (first + length) // 2, length - 1, length})
