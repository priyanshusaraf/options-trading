"""Optimization — the stage that runs ONLY after qualification, and always as nested
walk-forward so it cannot overfit its own out-of-sample record.

For each fold: search the (bounded, constrained) grid on the fold's in-sample window,
select the winner by an in-sample objective, then evaluate that winner on the fold's
UNTOUCHED out-of-sample window. Pool the OOS trades across folds — that pooled record
(never used for selection) is what validation and scoring see. Every trial is
recorded; `n_trials` (folds x grid size) feeds the Deflated Sharpe deflation, so
searching harder correctly raises the significance bar.

Signals for each candidate are computed once over the full series (causal) and sliced
per fold via the `run_trades` seam, so a fold's IS/OOS split never shifts the
path-dependent EMA/ATR seeds.
"""
from __future__ import annotations

import dataclasses
import math

from research.evaluation import kernels
from research.strategy.spec import grid, is_valid, param_space

# In-sample selection must reward a *repeatable* edge, not a lucky one. A candidate
# with fewer than this many in-sample trades is not evidence of an edge, however
# large its per-trade P&L, so it is never selected.
_MIN_IS_TRADES = 5


@dataclasses.dataclass
class Trial:
    fold_index: int
    params: dict           # the searched overrides for this trial
    is_objective: float    # in-sample objective (expectancy)
    is_trades: int
    oos_trades: int        # OOS trade count (only for the selected trial; else 0)
    selected: bool


@dataclasses.dataclass
class OptimizationResult:
    trials: list
    per_fold_selected: list   # the winning override dict per fold
    per_fold_oos: list        # OOS BTTrade list per fold (under that fold's winner)
    oos_trades: list          # pooled BTTrade across folds under the selected params
    oos_metrics: object       # BTMetrics of the pooled OOS record
    n_trials: int             # folds x candidates — the DSR deflation count


def _objective(metrics) -> float:
    """Rank in-sample candidates by a trade-count-aware t-statistic (per-trade Sharpe
    · √n), NOT raw expectancy.

    Raw expectancy (mean P&L per trade) rewards a single huge buy-and-hold winner over
    a consistent many-trade edge — and that lone winner then completes no round-trip
    inside a fold's out-of-sample window (0 OOS trades → the candidate spuriously fails
    validation). The t-statistic instead asks "is this mean *reliably* positive?",
    balancing edge size, consistency, and sample count. Candidates below the minimum
    trade floor, or with undefined dispersion (a single trade), are worst."""
    n = metrics.trades
    if n < _MIN_IS_TRADES or metrics.consistency is None:
        return float("-inf")
    return metrics.consistency * math.sqrt(n)


def _key(params: dict):
    return tuple(sorted(params.items()))


def optimize(candles, inst, strategy, *, space=None, n_folds: int = 3,
             capital: float = 50_000.0, base_params=None) -> OptimizationResult:
    base = dict(base_params if base_params is not None else strategy.default_params)
    space = space if space is not None else param_space(strategy.key)
    candidates = [c for c in grid(space) if is_valid(strategy.key, {**base, **c})] or [{}]
    seg = kernels.backtest_charge_segment(inst)
    rm = getattr(strategy, "risk_model", None)

    # one signal frame per candidate, over the full series
    sigs = {_key(c): kernels.compute_signals(candles, strategy, {**base, **c})
            for c in candidates}
    n = min((len(s) for s in sigs.values()), default=0)
    seg_size = n // (n_folds + 1)
    empty = OptimizationResult([], [], [], [], kernels.compute_metrics([], capital), 0)
    if seg_size < 1:
        return empty

    trials: list[Trial] = []
    per_fold_selected: list = []
    per_fold_oos: list = []
    pooled_oos: list = []
    for k in range(n_folds):
        is_end = (k + 1) * seg_size
        oos_end = n if k == n_folds - 1 else (k + 2) * seg_size
        best, best_key, best_obj = candidates[0], _key(candidates[0]), float("-inf")
        fold_records = []
        for c in candidates:
            is_trades = kernels.run_trades(
                sigs[_key(c)].iloc[:is_end].reset_index(drop=True), inst, seg, capital, rm)
            m = kernels.compute_metrics(is_trades, capital)
            obj = _objective(m)
            fold_records.append((c, obj, m.trades))
            if obj > best_obj:
                best, best_key, best_obj = c, _key(c), obj
        oos = kernels.run_trades(
            sigs[best_key].iloc[is_end:oos_end].reset_index(drop=True), inst, seg, capital, rm)
        pooled_oos.extend(oos)
        per_fold_oos.append(oos)
        per_fold_selected.append(best)
        for c, obj, is_n in fold_records:
            sel = _key(c) == best_key
            trials.append(Trial(k, c, obj, is_n, len(oos) if sel else 0, sel))

    return OptimizationResult(
        trials=trials, per_fold_selected=per_fold_selected, per_fold_oos=per_fold_oos,
        oos_trades=pooled_oos, oos_metrics=kernels.compute_metrics(pooled_oos, capital),
        n_trials=n_folds * len(candidates))
