"""Semantic editor batches validate one final graph and carry exact inverses."""
from __future__ import annotations

import copy

import pytest

from app.ir.edit import (
    AddNode,
    Connect,
    Disconnect,
    EditRejected,
    RemoveNode,
    SocketRef,
    add_node,
    apply_batch,
    connect,
)
from app.ir.hashing import canonical_json
from app.ir.strategies.expanding_z import GRAPH, LIBRARY


@pytest.fixture
def graph():
    return copy.deepcopy(GRAPH)


def test_a_temporarily_unwired_socket_is_allowed_when_the_final_batch_is_valid(graph):
    source = SocketRef("n_ema", "out")
    target = SocketRef("n_long_exit", "reference")

    result = apply_batch(
        graph,
        (Disconnect(source, target), Connect(source, target)),
        LIBRARY.components,
    )
    restored = apply_batch(
        result.graph, result.inverse_operations, LIBRARY.components
    )

    assert result.applied_operations == (
        Disconnect(source, target),
        Connect(source, target),
    )
    assert canonical_json(restored.graph) == canonical_json(graph)


def test_an_invalid_final_state_is_rejected_without_returning_a_graph(graph):
    with pytest.raises(EditRejected) as exc:
        apply_batch(
            graph,
            (Disconnect(
                SocketRef("n_ema", "out"),
                SocketRef("n_long_exit", "reference"),
            ),),
            LIBRARY.components,
        )

    assert exc.value.operation_index is None
    assert [(item.clause, item.path) for item in exc.value.violations] == [
        ("F8", "$.nodes.n_long_exit.reference")
    ]


def test_remove_inverse_restores_the_exact_node_and_all_incident_edges(graph):
    prepared = add_node(
        graph, "n_ema_slow", "indicator.ema", 1, {"length": 200}
    )
    for source, target in (
        (("io_in", "close"), ("n_ema_slow", "source")),
        (("n_ema_slow", "out"), ("n_z", "reference")),
        (("n_ema_slow", "out"), ("n_drift", "reference")),
        (("n_ema_slow", "out"), ("n_long_exit", "reference")),
        (("n_ema_slow", "out"), ("n_short_exit", "reference")),
    ):
        if target[0] != "n_ema_slow":
            prepared = apply_batch(prepared, (Disconnect(SocketRef("n_ema", "out"), SocketRef(*target)), Connect(SocketRef(*source), SocketRef(*target))), LIBRARY.components).graph
        else:
            prepared = connect(prepared, source, target)

    removed = apply_batch(
        prepared, (RemoveNode("n_ema"),), LIBRARY.components
    )
    restored = apply_batch(
        removed.graph, removed.inverse_operations, LIBRARY.components
    )

    assert isinstance(removed.inverse_operations[0], AddNode)
    assert canonical_json(restored.graph) == canonical_json(prepared)


def test_a_primitive_refusal_keeps_its_operation_index(graph):
    with pytest.raises(EditRejected) as exc:
        apply_batch(
            graph,
            (AddNode("n_ema", "math.abs", 1, {}, None, ()),),
            LIBRARY.components,
        )

    assert exc.value.operation_index == 0
    assert exc.value.violations[0].clause == "F9"
