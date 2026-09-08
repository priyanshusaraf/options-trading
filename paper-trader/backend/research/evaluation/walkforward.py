"""Walk-forward evaluation over a locked chronological evaluation window.

Signals are computed once over the complete immutable series so causal indicators
keep their historical warmup. Trade replay is then restricted to the locked
validation suffix and divided into contiguous folds.
"""
from __future__ import annotations

import dataclasses

from app.core.market_hours import ist_epoch

from research.evaluation import kernels


def signal_window(signals, *, start_at=None, stop_before=None,
                  expected_bars: int | None = None):
    """Return only bars admitted to one chronological evaluation window."""
    if expected_bars == 0:
        return signals.iloc[:0].reset_index(drop=True)
    selected = signals
    if start_at is not None:
        selected = selected[selected["date"] >= start_at]
    if stop_before is not None:
        selected = selected[selected["date"] < stop_before]
    return selected.reset_index(drop=True)


@dataclasses.dataclass
class FoldResult:
    fold_index: int
    start_ts: int          # epoch of the fold's first bar
    end_ts: int            # epoch of the fold's last bar
    n_bars: int
    trades: list           # list[BTTrade] closed within this fold
    metrics: object        # BTMetrics for this fold


@dataclasses.dataclass
class WalkForwardResult:
    folds: list

    @property
    def oos_expectancies(self) -> list[float]:
        return [f.metrics.expectancy for f in self.folds if f.metrics.trades]

    @property
    def total_oos_trades(self) -> int:
        return sum(f.metrics.trades for f in self.folds)

    @property
    def positive_fold_fraction(self) -> float:
        """Share of folds (that traded) with positive expectancy — a simple, robust
        temporal-stability signal."""
        traded = [f for f in self.folds if f.metrics.trades]
        if not traded:
            return 0.0
        return sum(1 for f in traded if f.metrics.expectancy > 0) / len(traded)


def walk_forward(candles, inst, strategy, params, *, n_folds: int = 4,
                 capital: float = 50_000.0, evaluation_start=None,
                 evaluation_bars: int | None = None) -> WalkForwardResult:
    """Evaluate the locked suffix in contiguous folds after full-series warmup."""
    if n_folds < 1:
        return WalkForwardResult(folds=[])
    sig = signal_window(
        kernels.compute_signals(candles, strategy, params),
        start_at=evaluation_start, expected_bars=evaluation_bars,
    )
    n = len(sig)
    size = n // n_folds
    if size < 1:
        return WalkForwardResult(folds=[])

    seg = kernels.backtest_charge_segment(inst)
    rm = getattr(strategy, "risk_model", None)
    folds: list[FoldResult] = []
    for k in range(n_folds):
        a = k * size
        b = n if k == n_folds - 1 else (k + 1) * size
        window = sig.iloc[a:b].reset_index(drop=True)
        trades = kernels.run_trades(
            window, inst, seg, capital, rm,
            replay_policy=getattr(strategy, "replay_policy", None),
            **kernels.replay_exit_kwargs(strategy),
        )
        metrics = kernels.compute_metrics(trades, capital)
        folds.append(FoldResult(
            fold_index=k,
            start_ts=ist_epoch(window.iloc[0]["date"]),
            end_ts=ist_epoch(window.iloc[-1]["date"]),
            n_bars=len(window), trades=trades, metrics=metrics))
    return WalkForwardResult(folds=folds)
