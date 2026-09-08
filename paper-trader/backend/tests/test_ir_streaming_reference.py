"""Independent causal reference evaluation tests."""

from dataclasses import dataclass

import pandas as pd
import pytest

from app.ir.causal import (
    HistoryBound,
    RecursiveStateContract,
    causal_contract,
)
from app.ir.hashing import content_address
from app.ir.library import REGISTRY
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_kernel
from app.ir.resolve import ResolvedEdge, ResolvedGraph, ResolvedNode, resolve
from app.ir.runtime import evaluate
from app.ir.strategies.expanding_z import GRAPH
from app.ir.streaming_reference import ReferenceEvaluationError, evaluate_prefix_stream


@dataclass(frozen=True)
class _ReplayState:
    value: int = 0


_replay_counter = 0


def _replay_initializer(params):
    return _ReplayState()


def _replay_encoder(state):
    return {"value": state.value}


def _replay_update(state, params, node_inputs, context_inputs):
    global _replay_counter
    _replay_counter += 1
    return _ReplayState(_replay_counter)


def _replay_step(state, params, node_inputs, context_inputs):
    return {"out": bool(state.value % 2)}


def _replay_vector(params, node_inputs, context_inputs):
    return {"out": node_inputs["close"].gt(0.0)}


def _inputs() -> dict[str, pd.Series]:
    index = pd.date_range("2026-08-13 09:15", periods=8, freq="5min", tz="Asia/Kolkata")
    close = pd.Series([100.0, 101.0, 99.0, 103.0, 104.0, 102.0, 105.0, 106.0], index=index)
    return {
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": pd.Series(range(100, 108), index=index),
    }


def test_reference_does_not_call_vector_runtime(monkeypatch) -> None:
    """Hypothesis 1: shared runtime logic can make the same defect pass twice."""
    import builtins
    import app.ir.runtime as vector_runtime

    def forbidden(*args, **kwargs):
        raise AssertionError("vector runtime boundary was called")

    monkeypatch.setattr(vector_runtime, "evaluate", forbidden)
    monkeypatch.setattr(vector_runtime, "_compute", forbidden)
    monkeypatch.setattr(vector_runtime, "_inputs_for", forbidden)
    monkeypatch.setattr(vector_runtime, "Cache", forbidden)

    original_import = builtins.__import__

    def no_runtime_import(name, *args, **kwargs):
        if name == "app.ir.runtime":
            raise AssertionError("reference evaluator imported vector runtime")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_runtime_import)

    graph = resolve(GRAPH, REGISTRY.library)
    result = evaluate_prefix_stream(graph, _inputs(), REGISTRY)

    assert len(result.outputs["longEntry"]) == 8


def test_reference_refuses_duplicate_target_collapse_in_a_forged_resolved_graph() -> None:
    graph = resolve(GRAPH, REGISTRY.library)
    forged = ResolvedGraph(
        graph.identifier, graph.version, graph.nodes,
        (*graph.edges, ResolvedEdge(
            source=graph.edges[0].source, target=graph.edges[0].target,
            declared_in=graph.edges[0].declared_in)),
        graph.versions, graph.inputs, graph.outputs, graph.components,
    )

    with pytest.raises(ReferenceEvaluationError, match="more than one source"):
        evaluate_prefix_stream(forged, _inputs(), REGISTRY)


def test_bounded_kernel_receives_only_its_declared_history() -> None:
    """Hypothesis 2: under-declared history must visibly diverge from whole-frame output."""
    def kernel(params, node_inputs, context_inputs):
        close = node_inputs["close"]
        return {"out": close.pct_change(2).fillna(0.0).gt(0.0)}

    body_ref = content_address({"bounded-history-probe": 1})
    contract = causal_contract(
        node_input_sockets=("close",), history=HistoryBound("bounded", constant=1))
    registration = registered_kernel(
        body_ref=body_ref, implementation=kernel, causal=contract,
        dependency_boundary=DependencyBoundary("declared_objects"))
    registry = PlatformRegistry(
        components={
            ("probe.bounded", 1): {
                "format_version": 1, "kind": "component", "identifier": "probe.bounded",
                "version": 1, "display_name": "probe", "interface": (),
                "body": {"body": "kernel", "ref": body_ref},
            }
        },
        bodies={}, registrations={body_ref: registration})
    node = ResolvedNode(
        "n", ("n",), ("probe.bounded", 1), body_ref, {}, None, 0, "pure",
        "cache", contract)
    graph = ResolvedGraph(
        "probe", 1, (node,), (), (("probe.bounded", 1),),
        {"close": (("n", "close"),)}, {"longEntry": ("n", "out")})
    index = pd.date_range("2026-08-13", periods=3, tz="UTC")

    result = evaluate_prefix_stream(
        graph, {"close": pd.Series([1.0, 2.0, 3.0], index=index)}, registry)

    assert result.outputs["longEntry"].tolist() == [False, False, False]


def test_reference_rejects_nondeterministic_recursive_state_replay() -> None:
    """Hypothesis 2: repeated incremental state transitions must encode identically."""
    global _replay_counter
    _replay_counter = 0
    body_ref = content_address({"recursive-replay-probe": 1})
    registered = registered_kernel(
        body_ref=body_ref,
        implementation=_replay_vector,
        causal=causal_contract(
            node_input_sockets=("close",), history=HistoryBound("bounded")),
        dependency_boundary=DependencyBoundary("declared_objects"),
    )
    registry = PlatformRegistry(
        components={
            ("probe.recursive", 1): {
                "format_version": 1, "kind": "component", "identifier": "probe.recursive",
                "version": 1, "display_name": "probe", "interface": (),
                "body": {"body": "kernel", "ref": body_ref},
            }
        },
        bodies={}, registrations={body_ref: registered},
    )
    recursive = causal_contract(
        node_input_sockets=("close",),
        history=HistoryBound("causal_recursive"),
        recursive_state=RecursiveStateContract(
            _replay_initializer,
            _ReplayState,
            _replay_encoder,
            _replay_update,
            _replay_step,
        ),
    )
    node = ResolvedNode(
        "n", ("n",), ("probe.recursive", 1), body_ref, {}, None, 0, "pure",
        "cache", recursive,
    )
    graph = ResolvedGraph(
        "probe", 1, (node,), (), (("probe.recursive", 1),),
        {"close": (("n", "close"),)}, {"longEntry": ("n", "out")},
    )
    index = pd.date_range("2026-08-13", periods=3, tz="UTC")

    with pytest.raises(ReferenceEvaluationError, match="state replay diverged"):
        evaluate_prefix_stream(
            graph, {"close": pd.Series([1.0, 2.0, 3.0], index=index)}, registry)


@pytest.mark.parametrize("fixture_name", ["monotonic", "nan-prefix"])
def test_wilder_recursive_stream_matches_shipped_vector_bytes(fixture_name: str) -> None:
    """Hypothesis 8: a recursive Wilder transition can drift from vector semantics."""
    from app.strategy.causal_fixtures import FIXTURE_SUITES

    fixture = next(
        item for item in FIXTURE_SUITES.require("causal-fixtures/1").fixtures
        if item.name == fixture_name)
    graph = resolve(GRAPH, REGISTRY.library)
    inputs = {name: fixture.inputs[name] for name in graph.inputs}

    vector = evaluate(graph, inputs, REGISTRY.implementations)
    reference = evaluate_prefix_stream(graph, inputs, REGISTRY)

    def canonical(values: pd.Series) -> list[float | None]:
        return [None if pd.isna(value) else float(value) for value in values]

    assert canonical(vector.values["n_atr/n_smooth"]["out"]) == canonical(
        reference.values["n_atr/n_smooth"]["out"])


@pytest.mark.parametrize("unit", ["us", "ns"])
def test_fixture_identity_normalizes_timestamp_resolution(unit: str) -> None:
    """Hypothesis 5: receipt identity must not depend on pandas datetime resolution."""
    from app.strategy.causal_fixtures import (
        CausalFixture, CausalFixtureSuite, canonical_fixture_manifest)

    index = pd.date_range("2026-08-13", periods=2, tz="UTC").as_unit(unit)
    suite = CausalFixtureSuite((CausalFixture(
        "resolution", {"close": pd.Series([1.0, 2.0], index=index)}),))

    manifest = canonical_fixture_manifest(suite)
    assert manifest["fixtures"][0]["inputs"]["close"]["index_utc_ns"] == [
        1786579200000000000, 1786665600000000000]


def test_v2_reference_slices_nested_canonical_fields_and_keeps_legacy_state_sequences():
    from types import SimpleNamespace
    from app.ir.streaming_reference import _v2_causal_index, _v2_prefix_value
    index = pd.date_range("2026-01-01", periods=3, tz="UTC")
    values = pd.Series([10., 11., 12.], index=index)
    graph = SimpleNamespace(nodes=(SimpleNamespace(component=("probe", 2)),))
    registry = SimpleNamespace(node_contracts={("probe", 2): {"execution_form": "RECURSIVE"}})
    inputs = {"market": {"nested": {"close": values}},
              "state": {"event_times": tuple(index), "series": (True, False, True)}}
    assert _v2_causal_index(graph, inputs, registry).equals(index)
    assert _v2_causal_index(graph, {"market": {"close": values}}, registry).equals(index)
    prefix = _v2_prefix_value(inputs, 2, index)
    assert prefix["market"]["nested"]["close"].tolist() == [10., 11.]
    assert prefix["state"] == {"event_times": tuple(index[:2]), "series": (True, False)}
    assert len(inputs["market"]["nested"]["close"]) == 3
    wrong = {"market": {"close": values}, "other": {"close": values.set_axis(index + pd.Timedelta(seconds=1))}}
    with pytest.raises(ReferenceEvaluationError, match="share one aware index"):
        _v2_causal_index(graph, wrong, registry)
    with pytest.raises(ReferenceEvaluationError, match="different causal clocks"):
        _v2_causal_index(graph, {"market": {"close": values},
            "state": {"event_times": tuple(index + pd.Timedelta(seconds=1))}}, registry)


def test_v2_nested_clock_rejects_incomplete_legacy_and_unknown_causal_inputs():
    from types import SimpleNamespace
    from app.ir.streaming_reference import _v2_causal_index
    graph = SimpleNamespace(nodes=(SimpleNamespace(component=("probe", 2)),))
    recursive = SimpleNamespace(node_contracts={("probe", 2): {"execution_form": "RECURSIVE"}})
    stateless = SimpleNamespace(node_contracts={("probe", 2): {"execution_form": "STATELESS"}})
    index = pd.date_range("2026-01-01", periods=2, tz="UTC")
    assert _v2_causal_index(graph, {}, stateless) is None
    assert _v2_causal_index(graph, {"close": pd.Series([1., 2.], index=index)}, stateless).equals(index)
    cases = [({}, "lacks event_times"),
             ({"market": {"close": pd.Series([], index=index[:0])}}, "lacks event_times"),
             ({"state": {"event_times": list(index)}}, "must be immutable"),
             ({"state": {"event_times": tuple(index.tz_localize(None))}}, "one causal sequence"),
             ({"state": {"event_times": tuple(index[::-1])}}, "one causal sequence"),
             ({"state": {"event_times": (index[0], index[0])}}, "one causal sequence"),
             ({"state": {"event_times": tuple(index), "series": (True,)}}, "length differs"),
             ({"market": {"close": pd.Series([1., 2.])}}, "aware index"),
             ({"market": {"close": pd.Series([1., 2.], index=index.tz_localize(None))}}, "aware index")]
    for inputs, reason in cases:
        with pytest.raises(ReferenceEvaluationError, match=reason):
            _v2_causal_index(graph, inputs, recursive)


@pytest.mark.parametrize("fault", ["reverse", "duplicate", "nat"])
@pytest.mark.parametrize("recursive", [False, True])
def test_v2_nested_series_rejects_noncausal_clocks(fault, recursive):
    from types import SimpleNamespace
    from app.ir.streaming_reference import _v2_causal_index
    index = pd.date_range("2026-01-01", periods=2, tz="UTC")
    if fault == "reverse": index = index[::-1]
    elif fault == "duplicate": index = pd.DatetimeIndex([index[0], index[0]])
    else: index = pd.DatetimeIndex([index[0], pd.NaT])
    graph = SimpleNamespace(nodes=(SimpleNamespace(component=("probe", 2)),))
    registry = SimpleNamespace(node_contracts={("probe", 2): {"execution_form": "RECURSIVE" if recursive else "STATELESS"}})
    with pytest.raises(ReferenceEvaluationError, match="share one aware index"):
        _v2_causal_index(graph, {"frame": {"close": pd.Series([1., 2.], index=index)}}, registry)
