"""Loading: validated source → a real, runnable Strategy. The generated `compute` is
compiled and exec'd in a namespace with NO builtins and only the vetted block library
injected, then wrapped as a `Strategy` that emits the canonical columns. This is where
'the bot's own Python actually runs' — and it runs sandboxed."""
import datetime as dt
import math

import pandas as pd

from research.strategy.builder.grammar import Composition
from research.strategy.builder.load import (
    GeneratedStrategy,
    build_strategy,
    compile_composition,
)

_SPEC = {
    "key": "gen_test_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def _trending_df(n=600):
    """Rising drift + oscillation, so the z-score repeatedly crosses ±1 (well past
    warmup) — the regime a cross-based composition is designed to trade."""
    base = dt.datetime(2024, 1, 1, 9, 15)
    rows = []
    for i in range(n):
        px = 100.0 + 0.15 * i + 6.0 * math.sin(i / 9.0)
        rows.append((base + dt.timedelta(minutes=15 * i), px - 0.4, px + 0.9, px - 0.9, px))
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])


def test_build_strategy_is_a_strategy_emitting_canonical_columns():
    strat = build_strategy(Composition.from_dict(_SPEC))
    assert isinstance(strat, GeneratedStrategy)
    assert strat.key == "gen_test_v1"
    out = strat.signals(_trending_df())
    for col in ("longEntry", "shortEntry", "longExit", "shortExit"):
        assert col in out.columns and out[col].dtype == bool


def test_generated_strategy_actually_fires_entries():
    strat = build_strategy(Composition.from_dict(_SPEC))
    out = strat.signals(_trending_df())
    assert out["longEntry"].sum() >= 1        # a real edge fires on a trending series


def test_no_signal_before_warmup():
    comp = Composition.from_dict(_SPEC)
    out = build_strategy(comp).signals(_trending_df())
    w = comp.max_warmup()
    assert not out["longEntry"].iloc[:w].any()
    assert not out["shortEntry"].iloc[:w].any()


def test_compiled_compute_runs_without_builtins():
    fn, src = compile_composition(Composition.from_dict(_SPEC))
    builtins_map = fn.__globals__.get("__builtins__", {})
    # empty builtins → open/eval/__import__ are unreachable from inside compute
    assert builtins_map == {} or all(k not in builtins_map for k in ("open", "eval", "__import__"))
    # the injected globals are ONLY block functions (+ the empty builtins slot)
    injected = {k for k in fn.__globals__ if k != "__builtins__"}
    from research.strategy.builder.blocks import BLOCKS
    assert injected <= set(BLOCKS)


def test_generated_source_is_stored_on_the_strategy():
    strat = build_strategy(Composition.from_dict(_SPEC))
    assert "def compute(df" in strat.source
    assert "ema_slope_up(df, 50, 5)" in strat.source
