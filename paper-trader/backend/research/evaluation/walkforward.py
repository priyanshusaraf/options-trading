"""Walk-forward evaluation — the substrate of the validation gate.

Signals are computed ONCE over the full series (causal, so seed-consistent), then
trades are replayed over each contiguous fold window via the extracted `run_trades`
seam. For fixed-parameter validation (the M1 harness over existing strategies) each
fold is an independent out-of-sample slice, so per-fold metrics measure whether the
edge holds across sub-periods — temporal robustness, not curve-fit in-sample fit.
When optimization arrives (M2), the search runs inside each fold's in-sample window
and is scored on the fold's untouched OOS slice; this module is that outer loop.
"""
from __future__ import annotations

import dataclasses

from app.core.market_hours import ist_epoch

from research.evaluation import kernels


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
                 capital: float = 50_000.0) -> WalkForwardResult:
    """Split the (warmup-trimmed) signal frame into `n_folds` contiguous OOS windows
    and evaluate the strategy on each. Returns no folds when there is too little data
    to give every fold at least one bar."""
    if n_folds < 1:
        return WalkForwardResult(folds=[])
    sig = kernels.compute_signals(candles, strategy, params)
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
        trades = kernels.run_trades(window, inst, seg, capital, rm)
        metrics = kernels.compute_metrics(trades, capital)
        folds.append(FoldResult(
            fold_index=k,
            start_ts=ist_epoch(window.iloc[0]["date"]),
            end_ts=ist_epoch(window.iloc[-1]["date"]),
            n_bars=len(window), trades=trades, metrics=metrics))
    return WalkForwardResult(folds=folds)
