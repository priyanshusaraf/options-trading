#!/usr/bin/env python
"""Render an IR strategy graph to a self-contained SVG.

    .venv/bin/python scripts/render_ir_graph.py [out.svg]

Reads nothing from the network, touches no database, and opens from disk in any
browser. The layout is derived from the graph's dependency structure — F13 keeps
presentation state out of the artefact, so there is nothing to load and nothing
to save.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.ir.resolve import resolve                      # noqa: E402
from app.ir.strategies.expanding_z import GRAPH, LIBRARY  # noqa: E402
from app.ir.view import graph_view, to_svg              # noqa: E402


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "expanding_z_v4.svg")

    resolved = resolve(GRAPH, LIBRARY)
    view = graph_view(resolved)
    out.write_text(to_svg(view), encoding="utf-8")

    print(f"{view.identifier} v{view.version}")
    print(f"  {len(view.nodes)} nodes across {view.layers} layers, "
          f"{len(view.edges)} edges")
    print(f"  warmup {view.warmup} bars · "
          f"{len(view.inputs)} inputs · {len(view.outputs)} outputs")
    print(f"  {len(resolved.versions)} component versions resolved")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
