"""A resolved Component IR graph behind the `Strategy` contract.

**Placement.** This module sits in `app/strategy/`, not in `app/ir/`, so the
dependency direction stays one-way: `app.ir` is the language and knows nothing about
strategies; `app.strategy` knows about both; `app.engine` knows about strategies. Putting
the adapter inside `app.ir` would make the language import the strategy contract and close
that loop for no gain.

It is also deliberately **outside `research/`**. The equivalent adapter used to live at
`research/strategy/builder/ir_strategy.py`, which the engine may never import —
`research/guards.py` lists `app.engine.runner` among the modules the research process must
not touch, and an adapter reachable only from the wrong side of that boundary cannot be
adopted. Research keeps its own bridge; this is the shared one.

**What this module deliberately does not do.** No orchestration, no scoring, no gate
evaluation, no persistence, no order or capital seam. It turns a graph into four boolean
columns and nothing else.

**Every failure here is loud.** The defects this module exists to close all had the same
shape — a graph that silently produced no signal, silently lost its risk model, or silently
became a different strategy. Each is now a typed refusal:

- a frame shorter than the graph's resolved warmup raises `InsufficientHistory` rather than
  returning four all-False columns forever;
- a malformed or partial `risk_model` declaration raises rather than degrading to `None`
  and quietly disabling the live ATR ratchet;
- a frame missing a declared graph input raises naming the input.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from app.ir.hashing import content_address
from app.ir.resolve import Library, ResolvedGraph, resolve
from app.ir.runtime import Kernel, evaluate
from app.strategy.registry.base import CANONICAL_COLUMNS, Strategy

#: A graph declaring one unnamed output binds it here: a lone condition is an entry.
DEFAULT_COLUMN = "longEntry"

#: The keys `Strategy.risk_model` must carry for the live ATR ratchet to be well-formed
#: (`app/strategy/registry/base.py:33-36`). A partial declaration is refused rather than
#: half-applied — the ratchet reads these positionally at `runner.py:478-487`.
RISK_MODEL_KEYS = frozenset({
    "atr_length", "initial_risk_atr", "trail_start_r", "trail_atr",
    "use_mfe_capture_floor", "capture_start_r", "capture_pct",
})


class IRAdapterError(Exception):
    """Base for every refusal this adapter raises, so callers can catch one type."""


class UnmappableGraph(IRAdapterError):
    """A graph whose declared outputs cannot bind to the canonical columns."""


class InsufficientHistory(IRAdapterError):
    """The frame carries no bar the graph considers settled.

    Raised rather than returned because the alternative is the defect this class exists
    to prevent: every canonical column False on every bar, indistinguishable from a
    genuine "no signal", for as long as the frame stays short.
    """

    def __init__(self, key: str, bars: int, warmup: int) -> None:
        self.bars, self.warmup = bars, warmup
        super().__init__(
            f"{key}: {bars} bars cannot settle a graph whose resolved warmup is "
            f"{warmup}; at least {warmup + 1} bars are required")


class InvalidRiskModel(IRAdapterError):
    """A graph declared a risk model that the live ratchet could not use."""


class MissingGraphInput(IRAdapterError):
    """The candle frame does not carry an input the graph declares."""


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


def validate_risk_model(declared: Any, key: str) -> dict[str, Any] | None:
    """Return a well-formed risk model, or `None` when the graph declares none.

    A graph that declares nothing gets `None` — the same as most hand-written strategies,
    and explicit rather than accidental. A graph that declares *something* must declare all
    of it: a partial model would arm the ratchet with a missing threshold.
    """
    if declared is None:
        return None
    if not isinstance(declared, Mapping):
        raise InvalidRiskModel(f"{key}: risk_model must be a mapping, got {type(declared).__name__}")
    supplied = set(declared)
    if supplied != RISK_MODEL_KEYS:
        missing = sorted(RISK_MODEL_KEYS - supplied)
        unknown = sorted(supplied - RISK_MODEL_KEYS)
        raise InvalidRiskModel(
            f"{key}: risk_model must declare exactly {sorted(RISK_MODEL_KEYS)}; "
            f"missing={missing} unknown={unknown}")
    model = dict(declared)
    if not isinstance(model["use_mfe_capture_floor"], bool):
        raise InvalidRiskModel(f"{key}: risk_model.use_mfe_capture_floor must be a bool")
    for name in sorted(RISK_MODEL_KEYS - {"use_mfe_capture_floor"}):
        value = model[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidRiskModel(f"{key}: risk_model.{name} must be a number, got {value!r}")
        if value <= 0:
            raise InvalidRiskModel(f"{key}: risk_model.{name} must be positive, got {value!r}")
    if int(model["atr_length"]) != model["atr_length"]:
        raise InvalidRiskModel(f"{key}: risk_model.atr_length must be a whole number")
    return model


def _bar_index(df: pd.DataFrame) -> pd.Index:
    """The bars' own timestamps where the frame carries them — a block that reads the
    clock (`needs_clock`) must see the session, not a row number."""
    return pd.Index(df["date"]) if "date" in df.columns else df.index


def _flags(series: Any, index: pd.Index, warmup: int) -> pd.Series:
    """One graph output as a canonical column: NaN is False, warmup is False (C10)."""
    values = series.to_numpy() if isinstance(series, pd.Series) else series
    flags = pd.Series(values, index=index).fillna(False).astype(bool)
    if warmup > 0:
        flags.iloc[:warmup] = False
    return flags


class IRGraphStrategy(Strategy):
    """A resolved IR graph behind the `Strategy` contract.

    Identity follows the generated-strategy scheme (`app/core/generated_strategies.py`):
    the **key is stable** across edits so persisted `InstrumentState.strategy_key` rows keep
    resolving, and the **version is the graph's content address** so an edit still changes
    `(key, version)` — the pair the platform treats as the execution artefact. Embedding the
    address in the key instead orphans every binding on the first edit.
    """

    default_params: dict[str, Any] = {}

    #: Two policies the research plane genuinely needs to invert, declared here rather
    #: than forked into a second adapter. Evaluation itself is shared, so the two planes
    #: cannot drift into different readings of what a graph means.
    #:
    #: **Identity.** Execution needs a *stable* key: a persisted
    #: `InstrumentState.strategy_key` must keep resolving after its graph is edited, and a
    #: key carrying the content address orphans every binding on the first edit. A search
    #: needs the opposite — hundreds of candidate graphs coexisting in one registry, each
    #: distinguishable — so it embeds the address.
    key_includes_address: bool = False

    #: **Tolerance.** Execution must refuse a frame it cannot settle, because silently
    #: returning four all-False columns is indistinguishable from a flat market and can
    #: persist unnoticed. A search evaluates many candidates over short and empty windows
    #: and legitimately reads "no signal" as a result rather than an error.
    refuse_insufficient_history: bool = True

    def __init__(self, graph: Mapping[str, Any],
                 library: tuple[Library, Mapping[str, Kernel]]) -> None:
        components, implementations = library
        self.graph = graph
        self.implementations = implementations
        self.resolved: ResolvedGraph = resolve(graph, components)
        self.mapping = column_mapping(tuple(self.resolved.outputs))
        self.address = content_address(graph)
        graph_version = graph.get("version")
        if isinstance(graph_version, bool) or not isinstance(graph_version, int) \
                or graph_version < 1:
            raise ValueError("IR graph version must be a positive integer")
        # Source-domain label used by durable graph attribution.  Strategy.version
        # remains the immutable content identity pinned below.
        self.graph_version_label = str(graph_version)
        self.key = (
            f"ir.{self.resolved.identifier}.{self.address.split(':')[1][:12]}"
            if self.key_includes_address else f"ir.{self.resolved.identifier}")
        self.display_name = str(graph.get("display_name") or self.resolved.identifier)
        self.risk_model = validate_risk_model(graph.get("risk_model"), self.key)
        #: The bar fields this graph actually declares — not a fixed OHLCV tuple. A graph
        #: needing only high/low/close must not fail on a frame that omits volume.
        self.required_inputs: tuple[str, ...] = tuple(self.resolved.inputs)
        #: Read by the backtest warmup trim, which otherwise infers warmup from indicator
        #: columns this adapter does not emit and so would trim nothing at all.
        self.declared_warmup: int = self.resolved.warmup
        self.pin_version(self.address)

    def compute(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        """Evaluate the graph and return the frame with the canonical columns."""
        if params:
            # Parameters are bound at resolution. Accepting them here would run one graph
            # and record the binding of another (F14).
            raise ValueError(
                f"{self.key}: parameters are bound at resolution, so "
                f"{sorted(params)} cannot be applied to an already-resolved graph")

        missing = [field for field in self.required_inputs if field not in df.columns]
        if missing:
            raise MissingGraphInput(
                f"{self.key}: the candle frame is missing {missing}, which this graph "
                f"declares as input(s); it carries {sorted(df.columns)}")

        settled = len(df) - self.declared_warmup
        if settled <= 0 and self.refuse_insufficient_history:
            raise InsufficientHistory(self.key, len(df), self.declared_warmup)

        out = df.copy()
        for column in CANONICAL_COLUMNS:
            out[column] = False
        if settled <= 0:
            # Tolerant policy only: no bar has settled, so every column stays False.
            return out

        index = _bar_index(df)
        # A fresh cache per evaluation, deliberately. `Cache` is keyed on `node.cache_id`,
        # which is fixed at resolution and carries nothing about the input data, so a cache
        # reused across two frames returns the FIRST frame's series for the second — every
        # node a hit, every value wrong. `test_ir_adapter.py` pins this.
        result = evaluate(
            self.resolved,
            {field: pd.Series(df[field].astype(float).to_numpy(), index=index)
             for field in self.required_inputs},
            self.implementations)
        for column, name in self.mapping.items():
            out[column] = _flags(result.outputs[name], df.index, result.warmup)
        return out


__all__ = [
    "DEFAULT_COLUMN", "RISK_MODEL_KEYS", "IRAdapterError", "IRGraphStrategy",
    "InsufficientHistory", "InvalidRiskModel", "MissingGraphInput", "UnmappableGraph",
    "column_mapping", "validate_risk_model",
]
