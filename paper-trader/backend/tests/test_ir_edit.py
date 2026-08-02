"""
The editor plane, writing half.

`validate()` has existed since the format phase with nothing calling it on a
write path, because there was no write path. This is the first thing in the
platform that changes an artefact, and the property under test is that it
**cannot store an invalid one**: an edit whose result violates §3 raises,
naming the clause, rather than returning something a caller could persist.

The second property is that presentation state stays out. F13's invariant —
"dragging a node changes its hash and silently defeats cache identity" — is
asserted here as an equality between content addresses, which is the only form
of it that can go red.
"""
from __future__ import annotations

import copy

import pytest

from app.ir.edit import (
    EditRejected,
    add_node,
    clear_override,
    connect,
    disconnect,
    group,
    remove_node,
    rename,
    set_override,
)
from app.ir.hashing import content_address
from app.ir.resolve import resolve
from app.ir.strategies.expanding_z import GRAPH, LIBRARY
from app.ir.validate import validate
from app.ir.view import Layout, graph_view, to_svg


@pytest.fixture
def graph():
    return copy.deepcopy(GRAPH)


# ── every edit returns a conforming artefact, or raises ───────────────────

def test_an_edit_that_would_break_the_format_is_refused(graph):
    """The gate. An override carrying a kind is an F10 violation, and the point
    is that it never becomes a value a caller could store."""
    with pytest.raises(EditRejected) as exc:
        set_override(graph, "n_ema", "length", {"value": 50, "kind": "length"})
    assert [v.clause for v in exc.value.violations] == ["F10"]
    assert validate(graph) == []          # and the original is untouched


def test_a_sweep_in_an_override_is_refused_at_the_edit(graph):
    """C14 reaching the editor: a user cannot type a grid into a parameter box
    and have it stored, because sweeping belongs to the searcher."""
    with pytest.raises(EditRejected) as exc:
        set_override(graph, "n_ema", "length", [10, 20, 50])
    assert [v.clause for v in exc.value.violations] == ["C14"]


def test_no_edit_mutates_its_input(graph):
    """C2's discipline, applied to editing: a caller holding the old graph
    holds the old graph, which is what makes undo a matter of keeping
    references rather than of inverting operations."""
    before = copy.deepcopy(graph)

    add_node(graph, "n_new", "math.abs", 1)
    set_override(graph, "n_ema", "length", 21)
    connect(graph, ("n_ema", "out"), ("n_range", "high"))
    remove_node(graph, "n_range")
    group(graph, "g1", "Group", ["n_ema"])

    assert graph == before


def test_adding_a_node_and_wiring_it_produces_a_resolvable_graph(graph):
    """The end-to-end claim: what the editor writes, the resolver reads."""
    edited = add_node(graph, "n_ema_slow", "indicator.ema", 1, {"length": 200})
    edited = connect(edited, ("n_ema_slow", "out"), ("n_long_exit", "reference"))
    edited = disconnect(edited, ("n_ema", "out"), ("n_long_exit", "reference"))

    resolved = resolve(edited, LIBRARY)
    assert resolved.node("n_ema_slow").params["length"] == 200
    assert (("n_ema_slow", "out"), ("n_long_exit", "reference")) in {
        (e.source, e.target) for e in resolved.edges}


# ── the operations that have to be atomic ─────────────────────────────────

def test_removing_a_node_removes_its_edges_in_the_same_operation(graph):
    """Leaving them would produce a graph referencing a node that is not there.
    A UI offering the two separately would have an invalid state to store
    between them."""
    edited = remove_node(graph, "n_impulse")
    assert validate(edited) == []
    assert not any("n_impulse" in (e["source"]["instance"], e["target"]["instance"])
                   for e in edited["edges"])


def test_removing_a_node_removes_it_from_any_group(graph):
    grouped = group(graph, "g1", "Thresholds", ["n_entry_thr", "n_exit_thr"])
    edited = remove_node(grouped, "n_exit_thr")
    assert edited["groups"][0]["members"] == ["n_entry_thr"]
    assert validate(edited) == []


def test_a_duplicate_instance_id_is_refused(graph):
    with pytest.raises(EditRejected) as exc:
        add_node(graph, "n_ema", "math.abs", 1)
    assert [v.clause for v in exc.value.violations] == ["F9"]


def test_editing_a_node_that_is_not_there_is_refused(graph):
    for action in (lambda: set_override(graph, "n_ghost", "length", 1),
                   lambda: remove_node(graph, "n_ghost"),
                   lambda: clear_override(graph, "n_ghost", "length")):
        with pytest.raises(EditRejected):
            action()


def test_an_edge_to_a_node_that_is_not_there_is_refused(graph):
    with pytest.raises(EditRejected) as exc:
        connect(graph, ("n_ema", "out"), ("n_ghost", "in"))
    assert [v.clause for v in exc.value.violations] == ["F9"]


def test_clearing_an_override_restores_the_declared_default(graph):
    edited = clear_override(graph, "n_exit_floor", "factor")
    assert "factor" not in next(n for n in edited["nodes"]
                                if n["instance_id"] == "n_exit_floor")["overrides"]
    assert resolve(edited, LIBRARY).node("n_exit_floor").params["factor"] == 1.0


def test_a_duplicate_edge_is_refused(graph):
    existing = graph["edges"][0]
    with pytest.raises(EditRejected):
        connect(graph,
                (existing["source"]["instance"], existing["source"]["socket"]),
                (existing["target"]["instance"], existing["target"]["socket"]))


# ── F13 — dragging a node must not change its hash ────────────────────────

def test_a_layout_does_not_change_the_graphs_content_address(graph):
    """The clause, stated as the only thing that can go red: "dragging a node
    changes its hash and silently defeats cache identity". Presentation state
    lives beside the graph, so an arranged graph and an unarranged one are the
    same artefact."""
    before = content_address(graph)

    resolved = resolve(graph, LIBRARY)
    arranged = Layout({"n_ema": (900, 900), "n_z": (40, 700)})
    view = graph_view(resolved, arranged)

    assert content_address(graph) == before
    assert next(n for n in view.nodes if n.instance_id == "n_ema").placed == (900, 900)


def test_a_layout_does_not_change_any_cache_identity(graph):
    """The consequence the clause actually protects. If layout reached the
    graph, every cached result downstream of a dragged node would be discarded."""
    resolved = resolve(graph, LIBRARY)
    plain = {n.instance_id: n.cache_id for n in resolved.nodes}

    graph_view(resolved, Layout({"n_ema": (900, 900)}))
    assert {n.instance_id: n.cache_id for n in resolve(graph, LIBRARY).nodes} == plain


def test_a_layout_is_sparse_so_arranging_two_nodes_does_not_own_the_rest(graph):
    resolved = resolve(graph, LIBRARY)
    derived = {n.instance_id: (n.layer, n.row) for n in graph_view(resolved).nodes}
    arranged = graph_view(resolved, Layout({"n_ema": (900, 900)}))

    for node in arranged.nodes:
        if node.instance_id != "n_ema":
            assert node.placed is None
            assert (node.layer, node.row) == derived[node.instance_id]


def test_a_hand_placed_node_stays_inside_the_canvas(graph):
    """A stored position outside the derived extents used to be drawn off the
    edge of the image, which is invisible until someone opens the file."""
    import re

    view = graph_view(resolve(graph, LIBRARY), Layout({"n_ema": (2400, 1500)}))
    svg = to_svg(view)
    width = int(re.search(r'width="(\d+)"', svg).group(1))
    height = int(re.search(r'height="(\d+)"', svg).group(1))
    assert width > 2400 and height > 1500


# ── F2 — a display name is never referenced, and what that does not mean ──

def test_renaming_breaks_no_reference(graph):
    """The clause that costs one field and saves every stored graph from the
    first rename: nothing points at a display name, so the graph still resolves
    to exactly the same thing."""
    renamed = rename(graph, "Expanding Z Impulse (retuned)")
    assert resolve(renamed, LIBRARY).nodes == resolve(graph, LIBRARY).nodes
    assert resolve(renamed, LIBRARY).versions == resolve(graph, LIBRARY).versions


def test_renaming_does_change_the_artefacts_content_address(graph):
    """Pinned deliberately, because it is a real question rather than an
    accident. F2 requires the display name to be *in* the artefact and F13
    hashes the artefact, so a cosmetic rename mints a new body address. Whether
    it should is a matter for an amendment (§6); what must not happen is the
    behaviour changing without anyone noticing, so this test exists to make the
    decision visible."""
    assert content_address(rename(graph, "Something Else")) != content_address(graph)
