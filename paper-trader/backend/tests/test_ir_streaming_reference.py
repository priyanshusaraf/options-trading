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
from app.ir.resolve import ResolvedGraph, ResolvedNode, resolve
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
