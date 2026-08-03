"""
The Generation 2 bridge: a resolved IR graph presented as a `Strategy`.

`compute` evaluates the graph over a candle frame and returns the four canonical
boolean columns, so a graph reaches the gate pipeline a hand-written strategy
already goes through — there is no second scoring path. Pure and deterministic:
resolution happens once, the key is the graph's content address, and nothing
here judges anything.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from app.ir.hashing import content_address
from app.ir.resolve import Library, ResolvedGraph, resolve
from app.ir.runtime import Kernel, evaluate
from app.strategy.registry.base import CANONICAL_COLUMNS, Strategy
from research.strategy.builder.ir_components import BAR_INPUTS

# The output mapping, explicit because the proposer's graphs declare one boolean
# `out` and four columns are mandatory:
#   1. an output named for a canonical column binds to that column;
#   2. a lone output under any other name binds to `longEntry` — it is an entry
#      condition, and such a graph states no exit, so the backtest's own
#      end-of-data close is what closes the position;
#   3. every canonical column left unbound is False on every bar — never NaN,
#      never True, so an absent signal can neither open nor close a position;
#   4. warmup bars are False in every column: unsettled is not a signal (C10).
DEFAULT_COLUMN = "longEntry"


class UnmappableGraph(Exception):
    """A graph whose declared outputs cannot bind to the canonical columns."""


def column_mapping(output_names: Sequence[str]) -> dict[str, str]:
    """Canonical column -> the graph output bound to it."""
    canonical = sorted(n for n in output_names if n in CANONICAL_COLUMNS)
    other = sorted(n for n in output_names if n not in CANONICAL_COLUMNS)
    if canonical and other:
        raise UnmappableGraph(
            f"outputs {canonical} name canonical columns and {other} do not; a "
            "graph that half-names them leaves the rest to be guessed")
    if canonical:
        return {name: name for name in canonical}
    if len(other) == 1:
        return {DEFAULT_COLUMN: other[0]}
    raise UnmappableGraph(
        f"cannot bind {list(output_names)} to {list(CANONICAL_COLUMNS)}; name the "
        "outputs for the columns they drive")


def _bar_index(df: pd.DataFrame) -> pd.Index:
    """The bars' own timestamps where the frame carries them — a block that reads
    the clock (`needs_clock`) sees the session, not a row number."""
    return pd.Index(df["date"]) if "date" in df.columns else df.index


def _flags(series: Any, index: pd.Index, warmup: int) -> pd.Series:
    """One graph output as a canonical column: NaN is False, warmup is False."""
    values = series.to_numpy() if isinstance(series, pd.Series) else series
    flags = pd.Series(values, index=index).fillna(False).astype(bool)
    if warmup > 0:
        flags.iloc[:warmup] = False
    return flags


class IRGraphStrategy(Strategy):
    """A resolved IR graph behind the `Strategy` contract."""

    default_params: dict[str, Any] = {}

    def __init__(self, graph: Mapping[str, Any],
                 library: tuple[Library, Mapping[str, Kernel]]) -> None:
        components, implementations = library
        self.graph = graph
        self.implementations = implementations
        self.resolved: ResolvedGraph = resolve(graph, components)
        self.mapping = column_mapping(tuple(self.resolved.outputs))
        self.address = content_address(graph)
        self.key = f"ir.{self.resolved.identifier}.{self.address.split(':')[1][:12]}"
        self.display_name = str(graph.get("display_name") or self.resolved.identifier)
        self.pin_version(self.address)

    def compute(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        """Evaluate the graph and return the frame with the canonical columns."""
        if params:
            # Parameters are bound at resolution. Accepting them here would run
            # one graph and record the binding of another (F14).
            raise ValueError(
                f"{self.key}: parameters are bound at resolution, so "
                f"{sorted(params)} cannot be applied to an already-resolved graph")

        out = df.copy()
        for column in CANONICAL_COLUMNS:
            out[column] = False
        if df.empty:
            return out

        missing = [field for field in BAR_INPUTS if field not in df.columns]
        if missing:
            raise ValueError(f"{self.key}: the candle frame is missing {missing}")

        index = _bar_index(df)
        result = evaluate(
            self.resolved,
            {field: pd.Series(df[field].astype(float).to_numpy(), index=index)
             for field in BAR_INPUTS},
            self.implementations)
        for column, name in self.mapping.items():
            out[column] = _flags(result.outputs[name], df.index, result.warmup)
        return out


__all__ = ["DEFAULT_COLUMN", "IRGraphStrategy", "UnmappableGraph", "column_mapping"]
