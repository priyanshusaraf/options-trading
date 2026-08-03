"""
The editor plane, read-only: a `ResolvedGraph` turned into a view model and an
SVG.

Layout is derived from dependency structure, never stored in the artefact (F13);
labels use the authored vocabulary, not the resolved one (C4).
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.ir.resolve import PATH_SEPARATOR, ResolvedGraph, topological_order


@dataclass(frozen=True)
class ViewNode:
    instance_id: str
    label: str
    container: str              # authored node it came from, "" at top level
    definition: str             # "identifier v<version>"
    params: Mapping[str, object]
    warmup: int
    purity: str
    cache_id: str
    derived: bool
    layer: int
    row: int
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
    """F13: presentation state lives beside the graph, keyed by `instance_id`.

    `positions` is sparse — an unmoved node keeps its derived position.
    """

    positions: Mapping[str, tuple[int, int]]

    def placed(self, instance_id: str) -> tuple[int, int] | None:
        return self.positions.get(instance_id)


def graph_view(graph: ResolvedGraph, layout: Layout | None = None) -> GraphView:
    """A layout for `graph`, derived from its dependency structure.

    `layout` overrides the derived position of the nodes it names, and only those.
    """
    ids = [n.instance_id for n in graph.nodes]
    order = topological_order(ids, graph.edges)

    # Longest-path layering, so no edge ever points backwards.
    incoming: dict[str, list[str]] = {i: [] for i in ids}
    for edge in graph.edges:
        if edge.source[0] in incoming and edge.target[0] in incoming:
            incoming[edge.target[0]].append(edge.source[0])

    layer: dict[str, int] = {}
    for instance_id in order:
        layer[instance_id] = max(
            (layer[src] + 1 for src in incoming[instance_id] if src in layer), default=0)

    # Rows break ties on specification order, so the picture is a function of
    # the graph and not of dict iteration.
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

# Advance width per character, by font size. Must be an over-estimate.
CHAR_W = {9: 5.6, 10: 6.2, 12: 7.4}


def fit(text: str, size: int, available: float) -> str:
    """Truncate `text` so it cannot spill out of the space it is given."""
    limit = int(available // CHAR_W[size])
    if limit <= 1:
        return ""
    return text if len(text) <= limit else text[:limit - 1] + "…"


def to_svg(view: GraphView) -> str:
    """A self-contained SVG. No external stylesheet, no script, no font file."""
    at = {n.instance_id: _box(n) for n in view.nodes}
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
