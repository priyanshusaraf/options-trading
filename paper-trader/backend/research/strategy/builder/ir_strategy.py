"""The Generation 2 bridge: a resolved IR graph presented as a `Strategy`.

Evaluation is **shared** with the execution-facing adapter (`app/strategy/ir_adapter.py`),
so the research plane and any future live adoption cannot drift into two different readings
of what a graph means. Only the two policies research genuinely needs to invert live here,
and each is inverted for a stated reason rather than by accident:

- **Identity includes the content address.** A search holds hundreds of candidate graphs at
  once and must tell them apart; execution needs the opposite, a key stable across edits so
  a persisted instrument binding keeps resolving.
- **A frame it cannot settle is not an error.** The search evaluates candidates over short
  and empty windows and legitimately reads "no signal" as a result; in execution the same
  silence is indistinguishable from a flat market and must be refused loudly.
"""
from __future__ import annotations

from app.strategy.ir_adapter import (
    DEFAULT_COLUMN,
    UnmappableGraph,
    _bar_index,
    _flags,
    column_mapping,
)
from app.strategy.ir_adapter import IRGraphStrategy as _SharedIRGraphStrategy


class IRGraphStrategy(_SharedIRGraphStrategy):
    """The research-plane reading of a graph: uniquely keyed, tolerant of short windows."""

    key_includes_address = True
    refuse_insufficient_history = False


__all__ = [
    "DEFAULT_COLUMN", "IRGraphStrategy", "UnmappableGraph", "_bar_index", "_flags",
    "column_mapping",
]
