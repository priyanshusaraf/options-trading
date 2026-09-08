"""
The component runtime — it evaluates a resolved graph.

`kernels.py` holds what a kernel declares; this holds what a kernel does, keyed
by the same content address. That split keeps resolution a pure function of the
specification (C2, C6) and gives the runtime no key but the address (C13).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from app.ir.kernels import PURE
from app.ir.formats.dispatch import UnsupportedFormatVersion, require_resolved_v1
from app.ir.resolve import ResolvedGraph, ResolvedNode, ResolvedV2Graph, ResolvedV2Bundle, topological_order
from app.ir.validity import NumericValue, ValidityState, invalid, propagate

Kernel = Callable[
    [Mapping[str, Any], Mapping[str, pd.Series], Mapping[str, pd.Series]],
    Mapping[str, pd.Series],
]


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
        """C10 — the outputs with the warmup prefix removed."""
        return {name: series.iloc[self.warmup:] for name, series in self.outputs.items()}


@dataclass
class Cache:
    """C8 — memoisation keyed by the identity resolution computed."""

    entries: dict[str, Mapping[str, pd.Series]] = field(default_factory=dict)
    hits: list[str] = field(default_factory=list)


def evaluate(graph: ResolvedGraph, inputs: Mapping[str, pd.Series],
             implementations: Mapping[str, Kernel],
             cache: Cache | None = None) -> EvaluationResult:
    """Evaluate `graph` over `inputs`, one series per declared graph input."""
    try:
        require_resolved_v1(graph.format_version)
    except UnsupportedFormatVersion as exc:
        raise EvaluationError("F1", "$", str(exc)) from exc
    cache = cache if cache is not None else Cache()
    hits_before = len(cache.hits)

    by_id = {n.instance_id: n for n in graph.nodes}
    order = topological_order([n.instance_id for n in graph.nodes], graph.edges)

    wiring: dict[tuple[str, str], tuple[str, str]] = {}
    for edge in graph.edges:
        if edge.target in wiring:
            raise EvaluationError(
                "C3", edge.target[0],
                f"input {edge.target[1]!r} has more than one source")
        wiring[edge.target] = edge.source
    interface: dict[tuple[str, str], str] = {}
    for name, consumers in graph.inputs.items():
        for consumer in consumers:
            if consumer in wiring or consumer in interface:
                raise EvaluationError(
                    "C3", consumer[0],
                    f"input {consumer[1]!r} has more than one source")
            interface[consumer] = name

    produced: dict[str, Mapping[str, pd.Series]] = {}
    timestamp_context = _timestamp_context(graph, inputs)

    for instance_id in order:
        node = by_id[instance_id]
        kernel = implementations.get(node.body_ref)
        if kernel is None:
            raise EvaluationError(
                "C13", instance_id,
                f"no implementation is registered at {node.body_ref}; the "
                "runtime knows a kernel by its content address and by nothing else")

        node_inputs = _inputs_for(node, graph, wiring, interface, inputs, produced)
        context_inputs = {
            name: timestamp_context[name]
            for name in (node.causal.context_inputs if node.causal else ())
        }
        produced[instance_id] = _compute(
            node, kernel, node_inputs, context_inputs, cache)

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


def evaluate_v2(
    graph: ResolvedV2Graph,
    inputs: Mapping[str, Any],
    registry: Any,
    *,
    evaluation_context_resolver: Callable[[ResolvedV2Node, Mapping[str, Any]], Any]
    | None = None,
) -> Mapping[str, Any]:
    """Evaluate fixed v2 topology using resolved input bundles only.

    The v2 calling convention gives a component its canonical parameter values
    and assembly-shaped inputs.  It cannot obtain a registry, provider, clock,
    or mutable topology from this API.
    """
    nodes = {node.node_id: node for node in graph.nodes}
    dependencies = {node_id: set() for node_id in nodes}
    for (target, _), bundle in graph.bundles.items():
        for member in bundle.members:
            if member.source["scope"] == "node":
                dependencies[target].add(member.source["node_id"])
    ready = sorted(node_id for node_id, needs in dependencies.items() if not needs)
    values: dict[str, Mapping[str, Any]] = {}
    while ready:
        node_id = ready.pop(0)
        node = nodes[node_id]
        implementation = registry.v2_implementations.get(node.component)
        if implementation is None:
            raise EvaluationError("V2", node_id, "no declared v2 implementation")
        node_inputs = {
            port_id: _v2_bundle_value(bundle, inputs, values)
            for (target, port_id), bundle in graph.bundles.items() if target == node_id
        }
        declaration = registry.v2_components[node.component].get("numeric_validity")
        if declaration is not None:
            node_inputs, short_circuit = _v2_numeric_inputs(node_id, node_inputs, declaration)
            if short_circuit is not None:
                values[node_id] = MappingProxyType({port["port_id"]: short_circuit for port in registry.v2_components[node.component]["ports"] if port["direction"] == "output"})
                for downstream, needs in dependencies.items():
                    if node_id in needs:
                        needs.remove(node_id)
                        if not needs:
                            ready.append(downstream)
                ready.sort()
                continue
        frozen_inputs = MappingProxyType(node_inputs)
        evaluation_context = (
            evaluation_context_resolver(node, frozen_inputs)
            if evaluation_context_resolver is not None else None
        )
        produced = (
            implementation(
                node.parameters, frozen_inputs,
                evaluation_context=evaluation_context,
            )
            if evaluation_context is not None
            else implementation(node.parameters, frozen_inputs)
        )
        if not isinstance(produced, Mapping):
            raise EvaluationError("V2", node_id, "v2 implementation must return an output mapping")
        if declaration is not None:
            produced = _v2_numeric_outputs(node_id, produced)
        values[node_id] = MappingProxyType(dict(produced))
        for downstream, needs in dependencies.items():
            if node_id in needs:
                needs.remove(node_id)
                if not needs:
                    ready.append(downstream)
        ready.sort()
    if len(values) != len(nodes):
        raise EvaluationError("V2", "$", "v2 topology is not acyclic")
    outputs: dict[str, Any] = {}
    for name, member in graph.outputs.items():
        outputs[name] = _v2_member_value(member, inputs, values)
    return MappingProxyType(outputs)


def _v2_numeric_inputs(node_id: str, inputs: Mapping[str, Any], declaration: Mapping[str, Any]) -> tuple[dict[str, Any], NumericValue | None]:
    if not inputs:
        return {}, None
    envelopes = tuple(_v2_numeric_envelopes(inputs))
    if not envelopes:
        raise EvaluationError("V2", node_id, "numeric-validity component received an unwrapped input")
    refused = propagate(envelopes)
    if refused is not None and declaration["input_policy"] == "propagate":
        return {}, refused
    if declaration["input_policy"] == "explicit_fallback":
        # The component receives the envelopes themselves and must choose an
        # explicit, registry-identified fallback.  The runtime never fills.
        return dict(inputs), None
    return {name: _v2_unwrap_numeric(value) for name, value in inputs.items()}, None


def _v2_numeric_outputs(node_id: str, produced: Mapping[str, Any]) -> Mapping[str, NumericValue]:
    if not all(isinstance(value, NumericValue) for value in produced.values()):
        raise EvaluationError("V2", node_id, "numeric-validity component must return NumericValue outputs")
    return produced


def _v2_numeric_envelopes(values: Any) -> list[NumericValue]:
    if isinstance(values, NumericValue):
        return [values]
    if isinstance(values, Mapping):
        nested = values.values()
    elif isinstance(values, tuple):
        nested = values
    else:
        raise EvaluationError("V2", "$", "numeric-validity component received an unwrapped input")
    result: list[NumericValue] = []
    for value in nested:
        result.extend(_v2_numeric_envelopes(value))
    return result


def _v2_unwrap_numeric(value: Any) -> Any:
    if isinstance(value, NumericValue):
        return value.value
    if isinstance(value, tuple):
        return tuple(_v2_unwrap_numeric(item) for item in value)
    if isinstance(value, Mapping):
        return MappingProxyType({key: _v2_unwrap_numeric(item) for key, item in value.items()})
    raise EvaluationError("V2", "$", "numeric-validity component received an unwrapped input")


def _v2_bundle_value(bundle: ResolvedV2Bundle, graph_inputs: Mapping[str, Any], values: Mapping[str, Mapping[str, Any]]) -> Any:
    if not bundle.members:
        return bundle.default
    pairs = [(member, _v2_member_value(member, graph_inputs, values)) for member in bundle.members]
    if bundle.assembly == "single":
        return pairs[0][1]
    if bundle.assembly == "ordered":
        return tuple(value for _, value in pairs)
    if bundle.assembly == "keyed":
        return MappingProxyType({member.binding["key"]: value for member, value in pairs})
    return tuple(value for _, value in pairs)


def _v2_member_value(member: Any, graph_inputs: Mapping[str, Any], values: Mapping[str, Mapping[str, Any]]) -> Any:
    source = member.source
    if source["scope"] == "graph_input":
        if source["port_id"] not in graph_inputs:
            raise EvaluationError("V2", "$", f"missing graph input {source['port_id']!r}")
        return graph_inputs[source["port_id"]]
    outputs = values.get(source["node_id"], {})
    if source["port_id"] not in outputs:
        raise EvaluationError("V2", source["node_id"], f"missing output {source['port_id']!r}")
    return outputs[source["port_id"]]


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
             node_inputs: Mapping[str, pd.Series],
             context_inputs: Mapping[str, pd.Series],
             cache: Cache) -> Mapping[str, pd.Series]:
    # C9: a declared impurity says the output is not a function of the inputs.
    cacheable = node.purity == PURE

    if cacheable and node.cache_id in cache.entries:
        cache.hits.append(node.instance_id)
        return cache.entries[node.cache_id]

    outputs = kernel(node.params, node_inputs, context_inputs)
    if not isinstance(outputs, Mapping):
        raise EvaluationError("C3", node.instance_id,
                              "a kernel returns its outputs by socket name")

    _check_index(node, node_inputs, outputs)

    if cacheable:
        cache.entries[node.cache_id] = outputs
    return outputs


def _timestamp_context(graph: ResolvedGraph,
                       inputs: Mapping[str, pd.Series]) -> dict[str, pd.Series]:
    """Build context from the common recorded input index, never from a clock."""
    if not any(node.causal and node.causal.context_inputs for node in graph.nodes):
        return {}
    series = [value for value in inputs.values() if isinstance(value, pd.Series)]
    if not series:
        raise EvaluationError("C11", "$", "bar_timestamp context needs indexed inputs")
    index = series[0].index
    if any(not value.index.equals(index) for value in series[1:]):
        raise EvaluationError("C11", "$", "graph inputs do not share one timestamp index")
    if not index.is_monotonic_increasing or not index.is_unique:
        raise EvaluationError("C11", "$", "bar_timestamp index must be monotonic and unique")
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
        raise EvaluationError(
            "C11", "$", "bar_timestamp requires a timezone-aware DatetimeIndex")
    return {"bar_timestamp": pd.Series(index, index=index, name="bar_timestamp")}


def _check_index(node: ResolvedNode, node_inputs: Mapping[str, pd.Series],
                 outputs: Mapping[str, pd.Series]) -> None:
    """C11's cheap half: an output cannot span bars its inputs did not.

    Non-series values have no index and are passed through; `check_causality`
    is what catches an actual forward read.
    """
    expected = next((v.index for v in node_inputs.values()
                     if isinstance(v, pd.Series)), None)
    if expected is None:
        return
    for socket, series in outputs.items():
        if not isinstance(series, pd.Series):
            continue
        if not series.index.equals(expected):
            raise EvaluationError(
                "C11", node.instance_id,
                f"{socket!r} spans a different set of bars than its inputs; a "
                "component may not change which bars exist")


def check_causality(graph: ResolvedGraph, inputs: Mapping[str, pd.Series],
                    implementations: Mapping[str, Kernel],
                    prefixes: Sequence[int] | None = None) -> None:
    """Raise unless every value is a function of the bars up to and including it.

    C11: evaluate on the first *n* bars and on all of them; the first *n*
    results must be identical.
    """
    length = len(next(iter(inputs.values())))
    checkpoints = prefixes if prefixes is not None else _default_prefixes(length, graph.warmup)

    full = evaluate(graph, inputs, implementations)

    for n in checkpoints:
        prefix = {name: series.iloc[:n] for name, series in inputs.items()}
        # A fresh cache: a hit would return the full-length answer and the
        # check would pass by not running.
        partial = evaluate(graph, prefix, implementations, cache=Cache())

        # Every node, not only the outputs: a forward read can cancel downstream.
        for instance_id, sockets in partial.values.items():
            for socket, series in sockets.items():
                whole = full.values[instance_id][socket]
                if not isinstance(series, pd.Series):
                    if series == whole:
                        continue
                    raise EvaluationError(
                        "C11", instance_id,
                        f"with {n} of {length} bars, the scalar {socket!r} is "
                        f"{series!r} but {whole!r} over all of them; a scalar "
                        "that moves with later bars was read from the future")
                reference = whole.iloc[:n]
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
    """Checkpoints past warmup, where values are settled and comparable."""
    first = max(warmup + 1, 1)
    if first >= length:
        return [length]
    return sorted({first, (first + length) // 2, length - 1, length})
