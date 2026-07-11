"""The reuse boundary: the pure, offline simulation kernels the research plane
imports from the execution codebase.

This is the *entire* surface of code the research plane borrows from `app/`. It is
deliberately narrow and deliberately pure — importing this module must never pull
in any capital-moving module (broker/runner/live execution) nor bind the execution
DB engine (`test_importing_kernels_does_not_cross_capital_boundary` enforces this).

Not re-exported on purpose:
- `simulate_premium` — the synthetic-premium path is off the equity-first hot path
  (revived only for the later index-options milestone).
- `sweep` / `cache` — DB-bound orchestration tied to paper_trader.db; the research
  plane owns its own fan-out, persistence, and content-addressing instead.
"""
from app.backtest.engine import simulate
from app.backtest.metrics import (
    BTMetrics,
    BTTrade,
    compute_metrics,
    oos_pass,
    split_metrics,
)
from app.strategy.registry import all_strategies, get_strategy, strategy_keys

__all__ = [
    "simulate",
    "BTMetrics",
    "BTTrade",
    "compute_metrics",
    "split_metrics",
    "oos_pass",
    "get_strategy",
    "all_strategies",
    "strategy_keys",
]
