"""
The editor plane, read-only.

Four of RFC 0001's five planes now have something real behind them; the Editor
had nothing. This is its first half — the direction that only reads — and the
test that matters most is not that a picture appears but that **no presentation
state exists**: F13 requires it to live beside the graph, and the conforming
default is to derive position from the dependency structure rather than store
it. A layout that were stored would put a coordinate somewhere, and a coordinate
in an artefact is a node whose hash changes when it is dragged.
"""
from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

import pytest

from app.ir.resolve import resolve
from app.ir.schema import GRAPH_KEYS, NODE_KEYS
from app.ir.strategies.expanding_z import GRAPH, LIBRARY
from app.ir.view import graph_view, to_svg


@pytest.fixture(scope="module")
def resolved():
    return resolve(GRAPH, LIBRARY)


@pytest.fixture(scope="module")
def view(resolved):
    return graph_view(resolved)


# ── F13 — there is no presentation state, which is why none can drift ─────

def test_the_grammar_has_nowhere_to_put_a_coordinate():
    """The enforcement is an absence, checked against the schema rather than
    against a comment. If someone adds `position` to a node, this goes red
    before any picture does."""
    for key in ("position", "x", "y", "viewport", "collapsed", "colour", "color"):
        assert key not in NODE_KEYS
        assert key not in GRAPH_KEYS


def test_layout_is_derived_so_the_same_graph_always_draws_the_same(resolved):
    assert graph_view(resolved) == graph_view(resolve(GRAPH, LIBRARY))
    assert to_svg(graph_view(resolved)) == to_svg(graph_view(resolved))


def test_reordering_the_specification_does_not_move_a_node_between_layers():
    """A layer is a fact about dependencies, not about list position. If it
    were positional, editing an unrelated part of the file would redraw the
    whole picture — and a diff of two renders would be meaningless."""
    shuffled = copy.deepcopy(GRAPH)
    nodes = shuffled["nodes"]
    nodes[1], nodes[3] = nodes[3], nodes[1]

    before = {n.instance_id: n.layer for n in graph_view(resolve(GRAPH, LIBRARY)).nodes}
    after = {n.instance_id: n.layer for n in graph_view(resolve(shuffled, LIBRARY)).nodes}
    assert after == before


# ── the layout is readable, and that is a property not a hope ─────────────

def test_every_edge_points_forward(view):
    """Longest-path layering, verified: no edge may point left, or the picture
    stops reading as "values flow this way" and starts needing a legend."""
    layer = {n.instance_id: n.layer for n in view.nodes}
    for edge in view.edges:
        assert layer[edge.source] < layer[edge.target], (
            f"{edge.source} → {edge.target} points backwards")


def test_the_graphs_inputs_are_the_leftmost_column(view):
    """Nodes fed only by the graph's own interface have nothing upstream, so
    they land in layer 0. In this strategy that is the EMA and the true range."""
    first = {n.label for n in view.nodes if n.layer == 0}
    assert "n_ema" in first and "n_tr" in first


def test_no_two_nodes_share_a_position(view):
    assert len({(n.layer, n.row) for n in view.nodes}) == len(view.nodes)


# ── C4 — the picture speaks the authored graph's vocabulary ───────────────

def test_a_node_from_inside_a_subgraph_says_which_authored_node_it_came_from(view):
    """"Diagnostics MUST speak the authored graph's vocabulary." A picture is a
    diagnostic. `n_atr/n_smooth` is drawn as *n_smooth* **in n_atr**, not as an
    opaque leaf the author never placed."""
    smooth = next(n for n in view.nodes if n.instance_id == "n_atr/n_smooth")
    assert smooth.label == "n_smooth"
    assert smooth.container == "n_atr"

    top = next(n for n in view.nodes if n.instance_id == "n_ema")
    assert top.container == ""


def test_two_instances_of_one_definition_are_visibly_distinct(view):
    """The adaptive threshold appears twice. Same definition, different bound
    parameters — and the picture has to show the difference or it is lying by
    omission."""
    both = [n for n in view.nodes
            if n.definition == "indicator.adaptive_threshold v1"]
    assert len(both) == 2
    assert {n.params["pct"] for n in both} == {65.0, 35.0}
    assert both[0].instance_id != both[1].instance_id


def test_what_resolution_computed_is_visible(view):
    """Warmup, purity and cache identity are the three things resolution knows
    that a reader of the specification cannot work out. If the view drops them
    it is a picture of the source, not of the resolved graph."""
    entry = next(n for n in view.nodes if n.instance_id == "n_entry_thr")
    assert entry.warmup == 300
    assert entry.purity == "pure"
    assert entry.cache_id.startswith("sha256:")
    assert view.warmup == 302


def test_the_whole_strategy_is_drawn(view, resolved):
    # 17 authored nodes, of which `n_atr` is a subgraph that lowers into two —
    # so the resolved graph, and therefore the picture, has 18.
    assert len(view.nodes) == len(resolved.nodes) == 18
    assert len([n for n in GRAPH["nodes"]
                if not n["component"]["identifier"].startswith("graph.")]) == 17
    assert len(view.edges) == len(resolved.edges)
    assert view.inputs == ("close", "high", "low")
    assert set(view.outputs) == {"longEntry", "shortEntry", "longExit", "shortExit"}


# ── the SVG itself ────────────────────────────────────────────────────────

def test_the_svg_is_well_formed(view):
    root = ET.fromstring(to_svg(view))
    assert root.tag.endswith("svg")


def test_the_svg_is_self_contained(view):
    """No CDN, no font file, no script. It has to open from disk in a browser
    with no network, or it is not a deliverable."""
    svg = to_svg(view)
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in svg
    assert "<script" not in svg
    assert "@import" not in svg and "url(" not in svg


def test_every_node_is_labelled_in_the_svg(view):
    svg = to_svg(view)
    for node in view.nodes:
        assert f">{node.label}<" in svg, node.instance_id


def test_no_label_overflows_its_box(view):
    """The first render of this graph spilled `indicator.adaptive_threshold v1`
    out through the right-hand edge of its box. Nothing failed — SVG text does
    not clip — so the picture was wrong and looked fine, which is the exact
    failure mode a visualisation has to be guarded against."""
    from app.ir.view import BOX_W, CHAR_W

    tree = ET.fromstring(to_svg(view))
    ns = "{http://www.w3.org/2000/svg}"
    sizes = {"name": 12, "def": 10, "meta": 10, "in": 9, "warm": 9}

    checked = 0
    for group in tree.iter(f"{ns}g"):
        box = group.find(f"{ns}rect")
        left, right = float(box.get("x")), float(box.get("x")) + BOX_W
        for text in group.iter(f"{ns}text"):
            content = text.text or ""
            size = sizes[text.get("class")]
            span = len(content) * CHAR_W[size]
            if text.get("text-anchor") == "end":
                start, end = float(text.get("x")) - span, float(text.get("x"))
            else:
                start, end = float(text.get("x")), float(text.get("x")) + span
            assert left <= start and end <= right, (
                f"{content!r} runs from {start:.0f} to {end:.0f}, "
                f"outside [{left:.0f}, {right:.0f}]")
            checked += 1

    assert checked >= len(view.nodes) * 3


def test_a_long_label_is_truncated_rather_than_dropped(view):
    """Truncation must leave enough to identify the node. An ellipsis on its
    own is the same as no label."""
    from app.ir.view import fit

    assert fit("indicator.adaptive_threshold v1", 10, 230) == \
        "indicator.adaptive_threshold v1"
    short = fit("indicator.adaptive_threshold v1", 10, 60)
    assert short.endswith("…") and len(short) > 5
    assert fit("anything", 10, 4) == ""


def test_the_svg_grows_with_the_graph_rather_than_clipping_it(view):
    """A fixed canvas silently cuts off the right-hand columns, which is the
    failure mode where a picture looks fine and is wrong."""
    svg = to_svg(view)
    width = int(re.search(r'width="(\d+)"', svg).group(1))
    height = int(re.search(r'height="(\d+)"', svg).group(1))
    from app.ir.view import BOX_H, BOX_W, _box

    for node in view.nodes:
        x, y = _box(node)
        assert x + BOX_W <= width and y + BOX_H <= height, node.instance_id


def test_an_impure_node_is_drawn_differently(resolved):
    """C9's declared policy reaches the picture. An impurity that looks like
    everything else is a declaration nobody reads."""
    from app.ir.kernels import kernel_registry
    from app.ir.resolve import Library
    from app.ir.strategies.expanding_z import EMA

    impure = kernel_registry({**LIBRARY.kernels,
                              EMA["body"]["ref"]: {"purity": "wall_clock"}})
    view = graph_view(resolve(GRAPH, Library(LIBRARY.components, LIBRARY.bodies, impure)))

    assert next(n for n in view.nodes if n.instance_id == "n_ema").purity == "wall_clock"
    assert 'class="node impure"' in to_svg(view)
    assert 'class="node impure"' not in to_svg(graph_view(resolve(GRAPH, LIBRARY)))
