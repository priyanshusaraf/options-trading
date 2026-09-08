"""Independent completed-prefix evaluator for causal strategy admission.

This module independently reconstructs graph order and wiring. Declared scalar
outputs also receive a vector comparison at every prefix; reconstruction never
uses the vector runtime's traversal, cache or private helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

import pandas as pd

from app.ir.causal import CausalDeclarationError
from app.ir.formats.dispatch import UnsupportedFormatVersion, require_resolved_v1
from app.ir.hashing import canonical_json
from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolvedGraph, ResolvedNode, ResolvedV2Graph
from app.ir.first_party.logic_state import StateSeriesResult


class ReferenceEvaluationError(ValueError):
    """The graph cannot be evaluated from completed bars alone."""


@dataclass(frozen=True)
class PrefixEvaluationResult:
    """Independent evaluator output, shaped for admission parity only."""

    outputs: Mapping[str, Any]
    values: Mapping[str, Mapping[str, Any]]
    warmup: int


def evaluate_v2_prefix_stream(
    graph: ResolvedV2Graph,
    inputs: Mapping[str, Any],
    registry: Any,
    *,
    evaluation_context_resolver: Callable[[Any, Mapping[str, Any]], Any]
    | None = None,
) -> Mapping[str, Any]:
    """Independent v2 completed-prefix evaluator for fixed topology.

    Dependency order and bundle assembly are reconstructed here. Scalar outputs
    are compared with ``runtime.evaluate_v2`` at every prefix before retaining
    the latest scalar; Series outputs retain their complete reconstructed history.
    """
    index = _v2_causal_index(graph, inputs, registry)
    if index is None:
        return _evaluate_v2_once_with_context(
            graph, inputs, registry, evaluation_context_resolver,
        )
    outputs: dict[str, list[Any]] = {}
    state_outputs: dict[str, StateSeriesResult] = {}
    scalar_names = _v2_scalar_output_names(graph)
    scalar_outputs: dict[str, Any] = {}
    for end in range(1, len(index) + 1):
        prefix = {
            name: _v2_prefix_value(value, end, index)
            for name, value in inputs.items()
        }
        current = _evaluate_v2_once_with_context(
            graph, prefix, registry, evaluation_context_resolver,
        )
        _v2_check_scalar_prefix(graph, prefix, registry, current, scalar_names, evaluation_context_resolver)
        _v2_collect_prefix(current, end, scalar_names, outputs, state_outputs, scalar_outputs)
    return _v2_prefix_outputs(index, outputs, state_outputs, scalar_outputs)


def _v2_scalar_output_names(graph):
    """Use addressed authored output shapes, never component names or values."""
    topology = graph.topology_document
    return frozenset(row["port_id"] for row in topology["graph_outputs"]
                     if row["descriptor"].get("shape") == "scalar")


def _v2_check_scalar_prefix(graph, prefix, registry, current, names, resolver):
    if not names:
        return
    # Only scalar-output graphs pay for this extra vector walk. Compare every
    # causal prefix: matching the final scalar alone would hide earlier errors.
    from app.ir.runtime import evaluate_v2
    vector = evaluate_v2(graph, prefix, registry, evaluation_context_resolver=resolver)
    for name in names:
        actual, expected = current[name], vector[name]
        if isinstance(actual, pd.Series) or isinstance(expected, pd.Series):
            raise ReferenceEvaluationError("declared scalar output contains a Series")
        if actual != expected:
            raise ReferenceEvaluationError("scalar output differs at a causal prefix")


def _v2_collect_prefix(current, end, scalar_names, collected, state_outputs, scalar_outputs):
    for name, value in current.items():
        if isinstance(value, StateSeriesResult):
            if len(value.values) != end:
                raise ReferenceEvaluationError("recursive output length differs from causal prefix")
            collected.setdefault(name, []).append(value.values[-1])
            state_outputs[name] = value
        elif name in scalar_names:
            scalar_outputs[name] = value
        else:
            collected.setdefault(name, []).append(value.iloc[-1] if isinstance(value, pd.Series) else value)


def _v2_prefix_outputs(index, collected, state_outputs, scalar_outputs):
    if index.empty:
        raise ReferenceEvaluationError("completed prefix is empty")
    return MappingProxyType({**scalar_outputs, **{
        name: (
            StateSeriesResult(
                tuple(values), state_outputs[name].state_payload,
                state_outputs[name].last_event_time,
            )
            if name in state_outputs else pd.Series(values, index=index)
        )
        for name, values in collected.items()
    }})


def _evaluate_v2_once_with_context(
    graph: ResolvedV2Graph,
    inputs: Mapping[str, Any],
    registry: Any,
    resolver: Callable[[Any, Mapping[str, Any]], Any] | None,
) -> Mapping[str, Any]:
    if resolver is None:
        return _evaluate_v2_once(graph, inputs, registry)
    return _evaluate_v2_once(
        graph, inputs, registry,
        evaluation_context_resolver=resolver,
    )


def _evaluate_v2_once(
    graph: ResolvedV2Graph,
    inputs: Mapping[str, Any],
    registry: Any,
    *,
    evaluation_context_resolver: Callable[[Any, Mapping[str, Any]], Any]
    | None = None,
) -> Mapping[str, Any]:
    nodes = {node.node_id: node for node in graph.nodes}
    waiting = {node_id: set() for node_id in nodes}
    for (node_id, _), bundle in graph.bundles.items():
        for member in bundle.members:
            if member.source["scope"] == "node":
                waiting[node_id].add(member.source["node_id"])
    ready = sorted(node_id for node_id, needs in waiting.items() if not needs)
    values: dict[str, Mapping[str, Any]] = {}
    while ready:
        node_id = ready.pop(0); node = nodes[node_id]
        implementation = registry.v2_implementations.get(node.component)
        if implementation is None:
            raise ReferenceEvaluationError(f"node {node_id} has no v2 implementation")
        assembled: dict[str, Any] = {}
        for (target, port_id), bundle in graph.bundles.items():
            if target != node_id:
                continue
            members = []
            for member in bundle.members:
                source = member.source
                if source["scope"] == "graph_input":
                    if source["port_id"] not in inputs:
                        raise ReferenceEvaluationError(f"missing graph input {source['port_id']}")
                    value = inputs[source["port_id"]]
                else:
                    value = values[source["node_id"]][source["port_id"]]
                members.append((member, value))
            if not members:
                assembled[port_id] = bundle.default
            elif bundle.assembly == "single":
                assembled[port_id] = members[0][1]
            elif bundle.assembly == "keyed":
                assembled[port_id] = MappingProxyType({member.binding["key"]: value for member, value in members})
            else:
                assembled[port_id] = tuple(value for _, value in members)
        frozen_inputs = MappingProxyType(assembled)
        evaluation_context = (
            evaluation_context_resolver(node, frozen_inputs)
            if evaluation_context_resolver is not None else None
        )
        result = (
            implementation(
                node.parameters, frozen_inputs,
                evaluation_context=evaluation_context,
            )
            if evaluation_context is not None
            else implementation(node.parameters, frozen_inputs)
        )
        if not isinstance(result, Mapping):
            raise ReferenceEvaluationError(f"node {node_id} returned non-mapping outputs")
        values[node_id] = MappingProxyType(dict(result))
        for downstream in sorted(waiting):
            if node_id in waiting[downstream]:
                waiting[downstream].remove(node_id)
                if not waiting[downstream]: ready.append(downstream)
        ready.sort()
    if len(values) != len(nodes):
        raise ReferenceEvaluationError("v2 topology is cyclic")
    result: dict[str, Any] = {}
    for name, member in graph.outputs.items():
        source = member.source
        result[name] = inputs[source["port_id"]] if source["scope"] == "graph_input" else values[source["node_id"]][source["port_id"]]
    return MappingProxyType(result)


_STATE_SEQUENCE_FIELDS = (
    "series", "a_series", "b_series", "event_times", "reset_series",
)


def _v2_indexed_series(value):
    if isinstance(value, pd.Series):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(series for child in value.values() for series in _v2_indexed_series(child))
    return ()


def _v2_valid_clock(index):
    return (isinstance(index, pd.DatetimeIndex) and index.tz is not None
            and index.is_monotonic_increasing and index.is_unique)


def _v2_series_clock(inputs):
    series = _v2_indexed_series(inputs)
    index = series[0].index if series else None
    if series and (not _v2_valid_clock(index)
                   or any(not value.index.equals(index) for value in series[1:])):
        raise ReferenceEvaluationError("v2 graph inputs must share one aware index")
    return index


def _v2_legacy_clock(value):
    times = value["event_times"]
    if not isinstance(times, tuple) or not times:
        raise ReferenceEvaluationError("recursive event_times must be immutable")
    index = pd.DatetimeIndex(times)
    if not _v2_valid_clock(index):
        raise ReferenceEvaluationError("recursive event_times are not one causal sequence")
    _v2_legacy_sequences(value, len(index))
    return index


def _v2_legacy_sequences(value, length):
    for field in _STATE_SEQUENCE_FIELDS:
        if field in value and (not isinstance(value[field], tuple) or len(value[field]) != length):
            raise ReferenceEvaluationError(f"recursive {field} length differs from event_times")


def _v2_has_recursive_node(graph, registry):
    return any((getattr(registry, "node_contracts", {}).get(node.component) or {}).get("execution_form")
               == "RECURSIVE" for node in graph.nodes)


def _v2_causal_index(
    graph: ResolvedV2Graph,
    inputs: Mapping[str, Any],
    registry: Any,
) -> pd.DatetimeIndex | None:
    index = _v2_series_clock(inputs)
    if not _v2_has_recursive_node(graph, registry):
        return index
    nested = [_v2_legacy_clock(value) for value in inputs.values()
              if isinstance(value, Mapping) and "event_times" in value]
    if index is not None:
        nested.append(index)
    return _v2_recursive_clock(nested)


def _v2_recursive_clock(clocks):
    if not clocks or clocks[0].empty:
        raise ReferenceEvaluationError("recursive graph input lacks event_times or indexed fields")
    if any(not item.equals(clocks[0]) for item in clocks[1:]):
        raise ReferenceEvaluationError("recursive graph inputs use different causal clocks")
    return clocks[0]


def _v2_prefix_value(value: Any, end: int, index: pd.DatetimeIndex) -> Any:
    if isinstance(value, pd.Series):
        return value.iloc[:end]
    if isinstance(value, Mapping):
        result = dict(value)
        if "event_times" in value and pd.DatetimeIndex(value["event_times"]).equals(index):
            for field in _STATE_SEQUENCE_FIELDS:
                if field in result:
                    result[field] = result[field][:end]
        return {name: _v2_prefix_value(item, end, index) for name, item in result.items()}
    return value


def evaluate_prefix_stream(
    graph: ResolvedGraph,
    inputs: Mapping[str, pd.Series],
    registry: PlatformRegistry,
) -> PrefixEvaluationResult:
    """Evaluate one completed bar at a time using an independent graph walk."""
    try:
        require_resolved_v1(graph.format_version)
    except UnsupportedFormatVersion as exc:
        raise ReferenceEvaluationError(str(exc)) from exc
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
    incoming: dict[tuple[str, str], tuple[str, str]] = {}
    for edge in graph.edges:
        if edge.target in incoming:
            raise ReferenceEvaluationError(
                f"input {edge.target[0]}.{edge.target[1]} has more than one source")
        incoming[edge.target] = edge.source
    interface: dict[tuple[str, str], str] = {}
    for name, consumers in graph.inputs.items():
        for consumer in consumers:
            if consumer in incoming or consumer in interface:
                raise ReferenceEvaluationError(
                    f"input {consumer[0]}.{consumer[1]} has more than one source")
            interface[consumer] = name
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
