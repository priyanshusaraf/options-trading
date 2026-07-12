"""Strategy registry — the single place the platform resolves a strategy by key.

Every module dropped in this package that exposes a module-level `STRATEGY`
(a `Strategy` instance) is auto-discovered and registered under its `.key`. To add
a strategy you commit one file here (the owner's "put the python code in from our
end"); no UI builder, no runtime exec of pasted code.

Resolution is fail-safe: an unknown/None key falls back to the default strategy so
a stale per-instrument assignment can never crash a tick or a backtest.
"""
from __future__ import annotations

import importlib
import pkgutil

from .base import CANONICAL_COLUMNS, Strategy

DEFAULT_STRATEGY_KEY = "trend_impulse_v3"

_REGISTRY: dict[str, Strategy] = {}
_SKIP = {"base"}


def _discover() -> None:
    if _REGISTRY:
        return
    import app.strategy.registry as pkg
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name in _SKIP:
            continue
        m = importlib.import_module(f"{pkg.__name__}.{mod.name}")
        strat = getattr(m, "STRATEGY", None)
        if isinstance(strat, Strategy) and strat.key:
            _REGISTRY[strat.key] = strat


def register(strat: Strategy) -> None:
    """Register (or replace) a strategy at runtime — the seam for deployed generated
    strategies, which are reconstructed from the DB at engine startup rather than
    dropped in as a module. Committing a module with a `STRATEGY` remains the path for
    hand-written strategies; this never runs pasted code (the generated strategy was
    already emitted, AST-validated, and sandbox-loaded by the builder)."""
    _discover()
    if isinstance(strat, Strategy) and strat.key:
        _REGISTRY[strat.key] = strat


def all_strategies() -> list[Strategy]:
    _discover()
    return sorted(_REGISTRY.values(), key=lambda s: s.display_name or s.key)


def strategy_keys() -> list[str]:
    _discover()
    return [s.key for s in all_strategies()]


def get_strategy(key: str | None) -> Strategy:
    """Resolve a strategy by key; unknown/None → the default strategy."""
    _discover()
    if key and key in _REGISTRY:
        return _REGISTRY[key]
    return _REGISTRY[DEFAULT_STRATEGY_KEY]


def strategy_meta() -> list[dict]:
    """Lightweight list for the UI: key, label, default params."""
    return [{"key": s.key, "display_name": s.display_name,
             "default_params": dict(s.default_params)} for s in all_strategies()]


__all__ = ["Strategy", "CANONICAL_COLUMNS", "DEFAULT_STRATEGY_KEY", "register",
           "all_strategies", "strategy_keys", "get_strategy", "strategy_meta"]
