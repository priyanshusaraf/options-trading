"""Repository-owned IR artefacts that the editor may inspect.

A *graph* is strategy-owned and comes from its own module; the *library* it resolves against
is the platform's (`app/ir/library.py`). Keeping those two sources distinct is the point —
before the 2026-08-07 correction this table took both from one strategy, which is how a
strategy came to serve as the platform registry.
"""
from __future__ import annotations

from typing import Any, Mapping

from app.ir.library import LIBRARY
from app.ir.resolve import Library
from app.ir.strategies import expanding_z


def catalogue() -> dict[str, tuple[Mapping[str, Any], Library]]:
    """Return a fixed table, never a caller-controlled resolution registry."""
    return {expanding_z.GRAPH["identifier"]: (expanding_z.GRAPH, LIBRARY)}
