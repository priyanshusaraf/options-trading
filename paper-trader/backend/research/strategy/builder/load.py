"""Load a validated Composition into a real, runnable Strategy.

`compile_composition` emits the `compute` source, validates it against the allow-list,
then compiles and `exec`s it in a namespace that contains ONLY the whitelisted block
functions and an EMPTY `__builtins__` — so the generated code cannot import, open files,
call `eval`, or reach any name outside the vetted grammar even if validation somehow
missed something. `GeneratedStrategy` wraps the compiled function as a standard
`Strategy` (subclass of the execution engine's base), so it flows through the identical
backtest / qualify / validate path as a hand-written strategy — nothing downstream knows
it was generated.
"""
from __future__ import annotations

import pandas as pd

from app.strategy.registry.base import CANONICAL_COLUMNS, Strategy
from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.emit import emit_source
from research.strategy.builder.grammar import Composition
from research.strategy.builder.validate import UnsafeStrategyError, validate_source


def compile_composition(comp: Composition, allowed_blocks=None):
    """Return `(compute_fn, source)` for `comp`. Raises UnsafeStrategyError if the
    emitted source fails validation (a composition should never produce unsafe source —
    this is the last-line assertion of that invariant)."""
    source = emit_source(comp)
    validate_source(source, allowed_blocks)
    names = list(allowed_blocks) if allowed_blocks is not None else list(BLOCKS)
    # sandbox globals: only the block callables + an EMPTY builtins map (no open/eval/…)
    sandbox = {"__builtins__": {}}
    sandbox.update({name: BLOCKS[name].fn for name in names})
    code = compile(source, f"<generated:{comp.key}>", "exec")
    local_ns: dict = {}
    exec(code, sandbox, local_ns)  # noqa: S102 — validated source, no-builtins namespace
    fn = local_ns.get("compute")
    if not callable(fn):
        raise UnsafeStrategyError("emitted source produced no compute()")
    return fn, source


class GeneratedStrategy(Strategy):
    """A `Strategy` whose `compute` is generated Python. Holds the source composition +
    emitted text for provenance and the owner's inspection."""

    def __init__(self, comp: Composition, allowed_blocks=None):
        self.key = comp.key
        self.display_name = comp.key
        self.default_params = {}
        self.composition = comp
        self._fn, self.source = compile_composition(comp, allowed_blocks)
        self._warmup = comp.max_warmup()

    def compute(self, df: pd.DataFrame, **params) -> pd.DataFrame:
        out = df.copy()
        cols = self._fn(out)
        for name in CANONICAL_COLUMNS:
            s = pd.Series(cols[name]).reindex(out.index).fillna(False).astype(bool)
            if self._warmup:
                s.iloc[:self._warmup] = False        # no signal before indicators are valid
            out[name] = s.to_numpy()
        # a known indicator column so the engine's warmup-trim has an anchor (harmless:
        # EMA is never NaN, and warmup signals are already zeroed above).
        out["ema"] = out["close"].ewm(span=50, adjust=False).mean()
        return out


def build_strategy(comp: Composition, allowed_blocks=None) -> GeneratedStrategy:
    return GeneratedStrategy(comp, allowed_blocks)
