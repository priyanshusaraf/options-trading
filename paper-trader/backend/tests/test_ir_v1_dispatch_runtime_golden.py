"""Golden v1 resolution and runtime behavior at the format dispatch seam."""

from dataclasses import replace

import pytest

from app.ir.library import REGISTRY
from app.ir.resolve import ResolutionError, resolve
from app.ir.runtime import EvaluationError, evaluate
from app.ir.strategies.expanding_z import GRAPH
from app.ir.streaming_reference import ReferenceEvaluationError, evaluate_prefix_stream
from tests.test_ir_streaming_reference import _inputs


@pytest.mark.parametrize(
    "version",
    [pytest.param(None, id="missing"), True, False, 1.0, "1", 0, 2, -1],
)
def test_v1_resolve_rejects_unsupported_format_without_partial_resolution(version):
    document = dict(GRAPH)
    if version is None:
        document.pop("format_version")
    else:
        document["format_version"] = version

    with pytest.raises(ResolutionError) as exc:
        resolve(document, REGISTRY.library)

    assert exc.value.clause == "F1"
    assert exc.value.path == "$.format_version"
    expected = dict(GRAPH)
    if version is None:
        expected.pop("format_version")
    else:
        expected["format_version"] = version
    assert document == expected


def test_v1_resolution_is_deterministic_and_retains_selected_format():
    first = resolve(GRAPH, REGISTRY.library)
    second = resolve(GRAPH, REGISTRY.library)

    assert first == second
    assert first.format_version == 1
    assert first.identifier == GRAPH["identifier"]
    assert first.outputs == {
        "longEntry": ("n_long_entry", "out"),
        "shortEntry": ("n_short_entry", "out"),
        "longExit": ("n_long_exit", "out"),
        "shortExit": ("n_short_exit", "out"),
    }


def test_v1_vector_and_independent_prefix_evaluation_remain_compatible():
    graph = resolve(GRAPH, REGISTRY.library)
    inputs = _inputs()

    vector = evaluate(graph, inputs, REGISTRY.implementations)
    prefix = evaluate_prefix_stream(graph, inputs, REGISTRY)

    assert vector.warmup == prefix.warmup == graph.warmup
    assert set(vector.outputs) == set(prefix.outputs) == set(graph.outputs)
    for name in graph.outputs:
        assert vector.outputs[name].equals(prefix.outputs[name])
    for node_id, sockets in vector.values.items():
        for socket, values in sockets.items():
            reference = prefix.values[node_id][socket]
            if hasattr(values, "equals"):
                assert values.equals(reference)
            else:
                assert values == reference


def test_v1_vector_runtime_refuses_forged_unsupported_resolved_graph():
    graph = replace(resolve(GRAPH, REGISTRY.library), format_version=2)

    with pytest.raises(EvaluationError, match="not understood") as exc:
        evaluate(graph, _inputs(), REGISTRY.implementations)

    assert exc.value.clause == "F1"
    assert exc.value.instance_id == "$"


def test_v1_prefix_runtime_refuses_forged_unsupported_resolved_graph():
    graph = replace(resolve(GRAPH, REGISTRY.library), format_version=2)

    with pytest.raises(ReferenceEvaluationError, match="not understood"):
        evaluate_prefix_stream(graph, _inputs(), REGISTRY)
