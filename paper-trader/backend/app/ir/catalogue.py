"""Repository-owned IR artefacts that the editor may inspect."""
from __future__ import annotations

from typing import Any, Mapping

from app.ir.resolve import Library
from app.ir.strategies import expanding_z


def catalogue() -> dict[str, tuple[Mapping[str, Any], Library]]:
    """Return a fixed table, never a caller-controlled resolution registry."""
    return {expanding_z.GRAPH["identifier"]: (expanding_z.GRAPH, expanding_z.LIBRARY)}
