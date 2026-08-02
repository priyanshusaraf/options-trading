"""
The editor plane, read-only: a resolved graph, made visible.

Of RFC 0001's five planes (§1.2) the **Editor** is the one with nothing behind
it. This module is its first half — the direction that only reads. It turns a
`ResolvedGraph` into a view model and an SVG, so the structure of a strategy can
be looked at rather than only asserted about.

**Layout is derived, never stored.** F13 says presentation state persists
*beside* the graph, keyed by stable identifier, and is not part of the artefact
grammar — "without this separation, dragging a node changes its hash and
silently defeats cache identity". The conforming default, and the one taken
here, is to not have presentation state at all: position is a pure function of
the graph's dependency structure. When an editor later lets a human drag a node,
what it persists goes in a side table keyed by `instance_id`, and this function
stays the fallback for every graph nobody has arranged by hand.

**The view speaks the authored vocabulary.** C4 requires diagnostics to name the
graph the author wrote, not the resolved one, and a picture is a diagnostic.
`n_atr/n_smooth` is drawn as *n_smooth* inside *n_atr* rather than as an opaque
leaf, so a node that came from three levels down inside a subgraph is traceable
to the node the author actually placed.

Nothing here is wired into a route, a template or the frontend build. It is
imported by its tests and by `scripts/render_ir_graph.py`.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.ir.resolve import PATH_SEPARATOR, ResolvedGraph, topological_order


@dataclass(frozen=True)
class ViewNode:
    instance_id: str
    label: str                  # the leaf's own authored name
    container: str              # the authored node it came from, "" at top level
    definition: str             # "identifier v<version>"
    params: Mapping[str, object]
    warmup: int
    purity: str
    cache_id: str
    derived: bool
    layer: int
    row: int
    # Set only when a human has arranged this node. F13 keeps it out of the
    # artefact; it arrives from a `Layout` beside it.
    placed: tuple[int, int] | None = None


@dataclass(frozen=True)
class ViewEdge:
    source: str
    target: str
    source_socket: str
    target_socket: str
    derived: bool


@dataclass(frozen=True)
class GraphView:
    identifier: str
    version: int
    nodes: tuple[ViewNode, ...]
    edges: tuple[ViewEdge, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    warmup: int

    @property
    def layers(self) -> int:
        return max((n.layer for n in self.nodes), default=-1) + 1


@dataclass(frozen=True)
class Layout:
    """Presentation state, stored **beside** the graph — F13, literally.

    "Presentation state MUST persist beside the graph, keyed by stable
    identifier, and is not part of the artefact grammar. Ephemeral state MUST
    NOT be persisted. Without this separation, dragging a node changes its hash
    and silently defeats cache identity."

    So this is a separate object keyed by `instance_id`, and the graph does not
    know it exists. A graph with a hand-arranged layout and the same graph
    without one have the same content address — which is the invariant the
    whole clause is for, and `test_ir_view.py` asserts it directly.

    `positions` is sparse on purpose: a node nobody has moved keeps its derived
    position, so an author who arranges two nodes does not thereby take
    ownership of the other sixteen.
    """

    positions: Mapping[str, tuple[int, int]]

    def placed(self, instance_id: str) -> tuple[int, int] | None:
        return self.positions.get(instance_id)


def graph_view(graph: ResolvedGraph, layout: Layout | None = None) -> GraphView:
    """A layout for `graph`, derived from its dependency structure.

    `layout` overrides the derived position of the nodes it names, and only
    those. It is never read from or written to the artefact.
    """
    ids = [n.instance_id for n in graph.nodes]
    order = topological_order(ids, graph.edges)

    # Longest-path layering: a node sits one column right of its deepest input.
    # Longest rather than shortest so an edge never points backwards, which is
    # what makes the picture readable as "time flows left to right".
    incoming: dict[str, list[str]] = {i: [] for i in ids}
    for edge in graph.edges:
        if edge.source[0] in incoming and edge.target[0] in incoming:
            incoming[edge.target[0]].append(edge.source[0])

    layer: dict[str, int] = {}
    for instance_id in order:
        layer[instance_id] = max(
            (layer[src] + 1 for src in incoming[instance_id] if src in layer), default=0)

    # Rows break ties on the specification's node order, so the picture is a
    # function of the graph and not of dict iteration (C1's spirit, applied to
    # something a human looks at).
    rows: dict[int, int] = {}
    view_nodes = []
    for node in graph.nodes:
        column = layer[node.instance_id]
        row = rows.get(column, 0)
        rows[column] = row + 1
        path = node.path
        view_nodes.append(ViewNode(
            instance_id=node.instance_id,
            label=path[-1] if path else node.instance_id,
            container=PATH_SEPARATOR.join(path[:-1]),
            definition=f"{node.definition[0]} v{node.definition[1]}",
            params=node.params,
            warmup=node.warmup,
            purity=node.purity,
            cache_id=node.cache_id,
            derived=node.derived_from is not None,
            layer=column,
            row=row,
            placed=layout.placed(node.instance_id) if layout else None,
        ))

    return GraphView(
        identifier=graph.identifier,
        version=graph.version,
        nodes=tuple(view_nodes),
        edges=tuple(ViewEdge(source=e.source[0], target=e.target[0],
                             source_socket=e.source[1], target_socket=e.target[1],
                             derived=e.derived)
                    for e in graph.edges),
        inputs=tuple(graph.inputs),
        outputs=tuple(graph.outputs),
        warmup=graph.warmup,
    )


# ── SVG ───────────────────────────────────────────────────────────────────

BOX_W, BOX_H = 250, 62
GAP_X, GAP_Y = 90, 30
PAD = 28
HEADER = 54

# Advance width per character, by font size, for the monospace stack above.
# Approximate on purpose — it only has to be an over-estimate, because the
# consequence of being wrong is text spilling out of a box, and
# `test_no_label_overflows_its_box` is what stops that shipping.
CHAR_W = {9: 5.6, 10: 6.2, 12: 7.4}


def fit(text: str, size: int, available: float) -> str:
    """Truncate `text` so it cannot spill out of the space it is given."""
    limit = int(available // CHAR_W[size])
    if limit <= 1:
        return ""
    return text if len(text) <= limit else text[:limit - 1] + "…"


def to_svg(view: GraphView) -> str:
    """A self-contained SVG. No external stylesheet, no script, no font file.

    Theme-aware via `prefers-color-scheme`, because this is meant to be opened
    in a browser and looked at, not embedded in an app that owns the palette.
    """
    at = {n.instance_id: _box(n) for n in view.nodes}
    # Extents come from where the boxes actually are, so a hand-placed node
    # cannot end up outside the canvas.
    width = int(max((x for x, _ in at.values()), default=0) + BOX_W + PAD)
    height = int(max((y for _, y in at.values()), default=0) + BOX_H + PAD)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="ui-monospace,SFMono-Regular,'
        f'Menlo,monospace">',
        _STYLE,
        f'<rect class="bg" x="0" y="0" width="{width}" height="{height}"/>',
        f'<text class="title" x="{PAD}" y="30">{html.escape(view.identifier)} '
        f'v{view.version}</text>',
        f'<text class="sub" x="{PAD}" y="46">{len(view.nodes)} nodes · '
        f'{len(view.edges)} edges · warmup {view.warmup} bars · '
        f'inputs {", ".join(view.inputs) or "—"} · '
        f'outputs {", ".join(view.outputs) or "—"}</text>',
    ]

    # Edges first so boxes paint over their endpoints.
    for edge in view.edges:
        if edge.source not in at or edge.target not in at:
            continue
        x1, y1 = at[edge.source]
        x2, y2 = at[edge.target]
        sx, sy = x1 + BOX_W, y1 + BOX_H / 2
        tx, ty = x2, y2 + BOX_H / 2
        mid = (sx + tx) / 2
        cls = "edge derived" if edge.derived else "edge"
        parts.append(
            f'<path class="{cls}" d="M {sx} {sy} C {mid} {sy} {mid} {ty} {tx} {ty}"/>')

    for node in view.nodes:
        x, y = at[node.instance_id]
        cls = "node derived" if node.derived else "node"
        if node.purity != "pure":
            cls += " impure"
        inner = BOX_W - 20
        badge = f"in {node.container}" if node.container else ""
        warm = f"↺{node.warmup}"

        parts.append(f'<g class="{cls}">')
        parts.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="6"/>')
        parts.append(
            f'<text class="name" x="{x + 10}" y="{y + 19}">'
            f'{html.escape(fit(node.label, 12, inner - len(badge) * CHAR_W[9] - 8))}'
            f'</text>')
        if badge:
            # C4 — a node expanded from inside a subgraph says which authored
            # node it came from, rather than appearing from nowhere.
            parts.append(f'<text class="in" x="{x + BOX_W - 10}" y="{y + 19}" '
                         f'text-anchor="end">{html.escape(badge)}</text>')
        parts.append(f'<text class="def" x="{x + 10}" y="{y + 35}">'
                     f'{html.escape(fit(node.definition, 10, inner))}</text>')
        parts.append(
            f'<text class="meta" x="{x + 10}" y="{y + 51}">'
            f'{html.escape(fit(_params(node.params), 10, inner - len(warm) * CHAR_W[9] - 8))}'
            f'</text>')
        parts.append(f'<text class="warm" x="{x + BOX_W - 10}" y="{y + 51}" '
                     f'text-anchor="end">{warm}</text>')
        parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


def _box(node: ViewNode) -> tuple[float, float]:
    if node.placed is not None:
        return (float(node.placed[0]), float(node.placed[1]))
    return (PAD + node.layer * (BOX_W + GAP_X),
            HEADER + PAD + node.row * (BOX_H + GAP_Y))


def _params(params: Mapping[str, object]) -> str:
    return ", ".join(f"{k}={_short(v)}" for k, v in list(params.items())[:3])


def _short(value: object) -> str:
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


_STYLE = """<style>
  .bg { fill: #fbfbfa; }
  .title { fill: #1a1a18; font-size: 15px; font-weight: 600; }
  .sub, .def { fill: #6b6b66; font-size: 10px; }
  .node rect { fill: #ffffff; stroke: #d6d5d0; stroke-width: 1.25; }
  .node.derived rect { stroke-dasharray: 4 3; }
  .node.impure rect { stroke: #b8722f; }
  .name { fill: #1a1a18; font-size: 12px; font-weight: 600; }
  .in, .warm { fill: #9a9a94; font-size: 9px; }
  .meta { fill: #4a4a46; font-size: 10px; }
  .edge { fill: none; stroke: #c2c1bb; stroke-width: 1.25; }
  .edge.derived { stroke-dasharray: 3 3; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #16161a; }
    .title { fill: #f2f2ef; }
    .sub, .def { fill: #8a8a86; }
    .node rect { fill: #1e1e24; stroke: #3a3a42; }
    .node.impure rect { stroke: #d09050; }
    .name { fill: #f2f2ef; }
    .in, .warm { fill: #6a6a70; }
    .meta { fill: #b8b8b2; }
    .edge { stroke: #3a3a42; }
  }
</style>"""
