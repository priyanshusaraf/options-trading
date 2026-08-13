"""Independent completed-prefix evaluator for causal strategy admission.

This module deliberately reconstructs graph order and wiring.  It does not
import the vector runtime, its cache, or its private helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from app.ir.causal import CausalDeclarationError
from app.ir.hashing import canonical_json
from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolvedGraph, ResolvedNode


class ReferenceEvaluationError(ValueError):
    """The graph cannot be evaluated from completed bars alone."""


@dataclass(frozen=True)
class PrefixEvaluationResult:
    """Independent evaluator output, shaped for admission parity only."""

    outputs: Mapping[str, Any]
    values: Mapping[str, Mapping[str, Any]]
    warmup: int


def evaluate_prefix_stream(
    graph: ResolvedGraph,
    inputs: Mapping[str, pd.Series],
    registry: PlatformRegistry,
) -> PrefixEvaluationResult:
    """Evaluate one completed bar at a time using an independent graph walk."""
    first, first_state_trace = _evaluate_prefix_stream_once(graph, inputs, registry)
    if first_state_trace:
        _, second_state_trace = _evaluate_prefix_stream_once(graph, inputs, registry)
        mismatch = _first_state_trace_mismatch(first_state_trace, second_state_trace)
        if mismatch is not None:
            node_id, position = mismatch
            raise ReferenceEvaluationError(
                f"recursive state replay diverged at {node_id} completed bar {position + 1}")
    return first


def _evaluate_prefix_stream_once(
    graph: ResolvedGraph,
    inputs: Mapping[str, pd.Series],
    registry: PlatformRegistry,
) -> tuple[PrefixEvaluationResult, Mapping[str, tuple[str, ...]]]:
    """Run one isolated completed-bar replay and retain canonical recursive states."""
    index = _common_index(graph, inputs)
    nodes = {node.instance_id: node for node in graph.nodes}
    order = _topological_order(tuple(nodes), graph)
    incoming = {edge.target: edge.source for edge in graph.edges}
    interface = {
        consumer: name
        for name, consumers in graph.inputs.items()
        for consumer in consumers
    }
    values: dict[str, dict[str, list[Any]]] = {
        node_id: {} for node_id in order
    }
    scalar_sockets: set[tuple[str, str]] = set()
    states: dict[str, object] = {}
    state_trace: dict[str, list[str]] = {}
    bounded_cache: dict[tuple[str, int], Mapping[str, pd.Series]] = {}

    for position, timestamp in enumerate(index):
        end = position + 1
        for node_id in order:
            node = nodes[node_id]
            registration = registry.registrations.get(node.body_ref)
            if registration is None:
                raise ReferenceEvaluationError(
                    f"node {node_id} has no registered implementation")
            contract = node.causal
            if contract is None:
                raise ReferenceEvaluationError(
                    f"node {node_id} has no causal contract")
            node_inputs = _node_input_prefixes(
                node, end, index, inputs, values, scalar_sockets,
                incoming, interface)
            context_series = {
                "bar_timestamp": pd.Series(
                    index[:end], index=index[:end], name="bar_timestamp")
                for name in contract.context_inputs
                if name == "bar_timestamp"
            }
            if contract.history.mode == "causal_recursive":
                recursive = contract.recursive_state
                if recursive is None:
                    raise ReferenceEvaluationError(
                        f"node {node_id} lacks recursive state functions")
                state = states.get(node_id)
                if node_id not in states:
                    state = recursive.initialize(node.params)
                scalar_inputs = {
                    name: (series.iloc[-1] if isinstance(series, pd.Series) else series)
                    for name, series in node_inputs.items()
                }
                scalar_context = {
                    name: series.iloc[-1] for name, series in context_series.items()
                }
                try:
                    state = recursive.advance(
                        state, node.params, scalar_inputs, scalar_context)
                    state_trace.setdefault(node_id, []).append(
                        canonical_json(recursive.encode(state)))
                    outputs = recursive.output(
                        state, node.params, scalar_inputs, scalar_context)
                except (CausalDeclarationError, KeyError, TypeError, ValueError) as exc:
                    raise ReferenceEvaluationError(
                        f"recursive node {node_id} failed at completed bar {end}: {exc}"
                    ) from exc
                states[node_id] = state
                _append_scalars(
                    values[node_id], outputs, node_id, scalar_sockets)
            else:
                history_bars = contract.history.bars(node.params)
                retained = max(1, history_bars)
                bounded_inputs = {
                    name: (series.iloc[-retained:].copy()
                           if isinstance(series, pd.Series) else series)
                    for name, series in node_inputs.items()
                }
                bounded_context = {
                    name: series.iloc[-retained:].copy()
                    for name, series in context_series.items()
                }
                cache_key = (node_id, end)
                outputs = bounded_cache.get(cache_key)
                if outputs is None:
                    outputs = registration.implementation(
                        node.params, bounded_inputs, bounded_context)
                    _validate_prefix_outputs(
                        node, outputs, bounded_inputs, index[:end])
                    bounded_cache[cache_key] = outputs
                _append_last(
                    values[node_id], outputs, node_id, scalar_sockets)

    materialized = {
        node_id: MappingProxyType({
            socket: (items[-1] if (node_id, socket) in scalar_sockets
                     else pd.Series(
                         [float("nan") if item is None else item for item in items],
                         index=index,
                         name=socket,
                     ))
            for socket, items in sockets.items()
        })
        for node_id, sockets in values.items()
    }
    outputs: dict[str, pd.Series] = {}
    for name, (node_id, socket) in graph.outputs.items():
        try:
            outputs[name] = materialized[node_id][socket]
        except KeyError as exc:
            raise ReferenceEvaluationError(
                f"graph output {name} reads absent {node_id}.{socket}") from exc

    return (
        PrefixEvaluationResult(
            outputs=MappingProxyType(outputs),
            values=MappingProxyType(materialized),
            warmup=graph.warmup,
        ),
        MappingProxyType({
            node_id: tuple(states) for node_id, states in state_trace.items()
        }),
    )


def _first_state_trace_mismatch(
    first: Mapping[str, tuple[str, ...]],
    second: Mapping[str, tuple[str, ...]],
) -> tuple[str, int] | None:
    for node_id in sorted(set(first) | set(second)):
        left, right = first.get(node_id, ()), second.get(node_id, ())
        for position, (left_state, right_state) in enumerate(zip(left, right)):
            if left_state != right_state:
                return node_id, position
        if len(left) != len(right):
            return node_id, min(len(left), len(right))
    return None


def _common_index(graph: ResolvedGraph,
                  inputs: Mapping[str, pd.Series]) -> pd.DatetimeIndex:
    missing = tuple(name for name in graph.inputs if name not in inputs)
    if missing:
        raise ReferenceEvaluationError(f"graph inputs are missing {list(missing)}")
    supplied = [inputs[name] for name in graph.inputs]
    if not supplied:
        raise ReferenceEvaluationError("reference evaluation needs indexed graph inputs")
    if any(not isinstance(series, pd.Series) for series in supplied):
        raise ReferenceEvaluationError("every graph input must be a pandas Series")
    index = supplied[0].index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
        raise ReferenceEvaluationError(
            "graph inputs require a timezone-aware DatetimeIndex")
    if not index.is_monotonic_increasing or not index.is_unique:
        raise ReferenceEvaluationError(
            "graph input timestamps must be monotonic and unique")
    if any(not series.index.equals(index) for series in supplied[1:]):
        raise ReferenceEvaluationError("graph inputs do not share one timestamp index")
    return index


def _topological_order(node_ids: tuple[str, ...], graph: ResolvedGraph) -> tuple[str, ...]:
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in graph.edges:
        source, target = edge.source[0], edge.target[0]
        if source not in incoming or target not in incoming:
            raise ReferenceEvaluationError("edge references an unresolved node")
        incoming[target] += 1
        outgoing[source].append(target)
    ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for target in sorted(outgoing[current]):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    if len(ordered) != len(node_ids):
        raise ReferenceEvaluationError("resolved graph contains a cycle")
    return tuple(ordered)


def _node_input_prefixes(
    node: ResolvedNode,
    end: int,
    index: pd.DatetimeIndex,
    graph_inputs: Mapping[str, pd.Series],
    values: Mapping[str, Mapping[str, list[Any]]],
    scalar_sockets: set[tuple[str, str]],
    incoming: Mapping[tuple[str, str], tuple[str, str]],
    interface: Mapping[tuple[str, str], str],
) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    contract = node.causal
    assert contract is not None
    for socket in contract.node_input_sockets:
        target = (node.instance_id, socket)
        if target in interface:
            result[socket] = graph_inputs[interface[target]].iloc[:end].copy()
        elif target in incoming:
            source_node, source_socket = incoming[target]
            try:
                items = values[source_node][source_socket]
            except KeyError as exc:
                raise ReferenceEvaluationError(
                    f"{node.instance_id}.{socket} reads absent "
                    f"{source_node}.{source_socket}") from exc
            if len(items) != end:
                raise ReferenceEvaluationError(
                    f"{source_node}.{source_socket} is not complete through bar {end}")
            result[socket] = (
                items[-1] if (source_node, source_socket) in scalar_sockets
                else pd.Series(
                    [float("nan") if item is None else item for item in items],
                    index=index[:end],
                    name=source_socket,
                )
            )
        else:
            raise ReferenceEvaluationError(
                f"{node.instance_id}.{socket} has no resolved source")
    return result


def _validate_prefix_outputs(node: ResolvedNode, outputs: object,
                             node_inputs: Mapping[str, Any],
                             completed_index: pd.DatetimeIndex) -> None:
    if not isinstance(outputs, Mapping):
        raise ReferenceEvaluationError(
            f"bounded node {node.instance_id} did not return a socket mapping")
    for socket, series in outputs.items():
        if not isinstance(socket, str):
            raise ReferenceEvaluationError(
                f"bounded node {node.instance_id} returned an invalid output")
        if not isinstance(series, pd.Series):
            continue
        indexed_inputs = [value for value in node_inputs.values()
                          if isinstance(value, pd.Series)]
        if not indexed_inputs:
            raise ReferenceEvaluationError(
                f"bounded node {node.instance_id}.{socket} returned a series without input index")
        expected = indexed_inputs[0].index
        if not series.index.equals(expected):
            raise ReferenceEvaluationError(
                f"bounded node {node.instance_id}.{socket} changed the prefix index")
        if not len(series) or series.index[-1] != completed_index[-1]:
            raise ReferenceEvaluationError(
                f"bounded node {node.instance_id}.{socket} omitted the current bar")


def _append_last(target: dict[str, list[Any]], outputs: Mapping[str, Any],
                 node_id: str,
                 scalar_sockets: set[tuple[str, str]]) -> None:
    if not outputs:
        raise ReferenceEvaluationError(f"node {node_id} produced no outputs")
    for socket, series in outputs.items():
        if isinstance(series, pd.Series):
            target.setdefault(socket, []).append(series.iloc[-1])
        else:
            scalar_sockets.add((node_id, socket))
            target.setdefault(socket, []).append(series)


def _append_scalars(target: dict[str, list[Any]], outputs: Mapping[str, Any],
                    node_id: str,
                    scalar_sockets: set[tuple[str, str]]) -> None:
    if not outputs:
        raise ReferenceEvaluationError(f"node {node_id} produced no outputs")
    for socket, value in outputs.items():
        if not isinstance(socket, str):
            raise ReferenceEvaluationError(
                f"recursive node {node_id} returned a non-string socket")
        target.setdefault(socket, []).append(value)


__all__ = [
    "PrefixEvaluationResult",
    "ReferenceEvaluationError",
    "evaluate_prefix_stream",
]
