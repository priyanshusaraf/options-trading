"""Optimization — the stage that runs ONLY after qualification, and always as nested
walk-forward so it cannot overfit its own out-of-sample record.

The bounded grid and all nested folds stay inside the development window. Their
complete trial record supplies the PBO and DSR selection diagnostics. One parameter
set is then selected over the complete development window; the orchestrator freezes
that set before it evaluates the later holdout.

Signals for each candidate are computed once over the full series (causal) and sliced
per fold via the `run_trades` seam, so a fold's IS/OOS split never shifts the
path-dependent EMA/ATR seeds.
"""
from __future__ import annotations

import dataclasses
import math

from research.evaluation import kernels
from research.evaluation.walkforward import signal_window
from research.strategy.spec import grid, is_valid, param_space

# In-sample selection must reward a *repeatable* edge, not a lucky one. A candidate
# with fewer than this many in-sample trades is not evidence of an edge, however
# large its per-trade P&L, so it is never selected.
_MIN_IS_TRADES = 5


@dataclasses.dataclass
class Trial:
    fold_index: int
    params: dict           # the searched overrides for this trial
    is_objective: float    # in-sample objective (trade-count-aware t-stat, see _objective)
    is_trades: int
    oos_trades: int        # OOS trade count (only for the selected trial; else 0)
    selected: bool
    # Per-trade Sharpe of this trial (metrics.consistency), or None when the trial
    # produced no usable dispersion (below the trade floor / a single trade).
    # Recorded rather than back-derived from is_objective: the objective is -inf for
    # those trials, and dividing a sentinel by sqrt(n) yields a number that would
    # silently poison var_sr.
    is_sharpe: float | None = None


@dataclasses.dataclass
class FinalSelectionTrial:
    params: dict
    objective: float | None
    trades: int
    selected: bool
    role: str = "final_development_selection"


@dataclasses.dataclass
class OptimizationResult:
    trials: list
    per_fold_selected: list   # the winning override dict per fold
    per_fold_oos: list        # OOS BTTrade list per fold (under that fold's winner)
    oos_trades: list          # pooled BTTrade across folds under the selected params
    oos_metrics: object       # BTMetrics of the pooled OOS record
    n_trials: int             # folds x candidates — the DSR deflation count
    # (sub-period x candidate) net P&L, the input CSCV/PBO needs. Empty when there
    # was too little data or only one candidate — PBO is a statement about
    # SELECTION, so it is undefined with nothing to select between.
    perf_matrix: list = dataclasses.field(default_factory=list)
    selected_params: dict = dataclasses.field(default_factory=dict)
    final_trials: list = dataclasses.field(default_factory=list)

    @property
    def var_sr(self) -> float:
        """Variance of the trial Sharpes — the OTHER half of DSR deflation.

        `expected_max_sharpe` returns 0 whenever this is 0, which is how the
        deflation benchmark sat at zero on every candidate the lab ever scored:
        n_trials was threaded through, var_sr never was, and a benchmark of zero
        turns the DSR back into a PSR against zero. Widening the search then had
        no effect on the bar at all, while search.py's docstring claimed it did.

        Population (not sample) variance: these trials ARE the search, not a draw
        from a larger pool of them. Trials with no usable dispersion contribute
        nothing rather than a sentinel."""
        vals = [t.is_sharpe for t in self.trials
                if t.is_sharpe is not None and math.isfinite(t.is_sharpe)]
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        return sum((v - mean) ** 2 for v in vals) / len(vals)


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


def _performance_matrix(sigs, candidates, inst, seg, capital, rm, n_blocks: int, *, replay_policy=None, exit_kwargs=None) -> list:
    """(sub-period x candidate) net P&L — the CSCV input for PBO.

    Deliberately computed over CONTIGUOUS equal blocks of the whole series rather
    than reusing the walk-forward folds: CSCV wants many sub-periods (8-16) to have
    enough combinations to be meaningful, while n_folds is 3-4. Costs n_blocks x
    n_candidates extra replays, which is why it is bounded and skipped when there is
    nothing to select between."""
    n = min((len(s) for s in sigs.values()), default=0)
    block = n // n_blocks
    if block < 1 or len(candidates) < 2:
        return []
    matrix = []
    for b in range(n_blocks):
        row = []
        for c in candidates:
            sl = sigs[_key(c)].iloc[b * block:(b + 1) * block].reset_index(drop=True)
            trades = kernels.run_trades(sl, inst, seg, capital, rm, replay_policy=replay_policy, **(exit_kwargs or {}))
            row.append(float(sum(t.net_pnl for t in trades)))
        matrix.append(row)
    return matrix


def _candidate_signals(candles, strategy, base, candidates, *,
                       development_end, development_bars):
    return {
        _key(candidate): signal_window(
            kernels.compute_signals(
                candles, strategy, {**base, **candidate},
            ),
            stop_before=development_end, expected_bars=development_bars,
        )
        for candidate in candidates
    }


def _nested_trials(sigs, candidates, inst, seg, capital, rm, n_folds, seg_size, *, replay_policy=None, exit_kwargs=None, progress=None):
    exit_kwargs = exit_kwargs or {}
    trials, selected_params, per_fold_oos, pooled_oos = [], [], [], []
    for fold_index in range(n_folds):
        is_end = (fold_index + 1) * seg_size
        oos_end = len(next(iter(sigs.values()))) \
            if fold_index == n_folds - 1 else (fold_index + 2) * seg_size
        best, best_key, best_objective = (
            candidates[0], _key(candidates[0]), float("-inf")
        )
        fold_records = []
        for candidate in candidates:
            is_trades = kernels.run_trades(
                sigs[_key(candidate)].iloc[:is_end].reset_index(drop=True),
                inst, seg, capital, rm, replay_policy=replay_policy, **exit_kwargs,
            )
            metrics = kernels.compute_metrics(is_trades, capital)
            objective = _objective(metrics)
            sharpe = metrics.consistency if metrics.trades >= _MIN_IS_TRADES else None
            fold_records.append((candidate, objective, metrics.trades, sharpe))
            _observe_trial(progress, "nested_trials", candidate, objective, metrics.trades, fold_index, sharpe)
            if objective > best_objective:
                best, best_key, best_objective = candidate, _key(candidate), objective
        oos = kernels.run_trades(
            sigs[best_key].iloc[is_end:oos_end].reset_index(drop=True),
            inst, seg, capital, rm, replay_policy=replay_policy, **exit_kwargs,
        )
        pooled_oos.extend(oos)
        per_fold_oos.append(oos)
        selected_params.append(best)
        _observe_selection(progress, "nested_trials", best, fold_index)
        trials.extend(
            Trial(
                fold_index, candidate, objective, is_trades,
                len(oos) if _key(candidate) == best_key else 0,
                _key(candidate) == best_key, is_sharpe=sharpe,
            )
            for candidate, objective, is_trades, sharpe in fold_records
        )
    return trials, selected_params, per_fold_oos, pooled_oos


def _select_params(sigs, candidates, inst, seg, capital, rm, base, *, replay_policy=None, exit_kwargs=None, progress=None):
    evaluated = []
    for candidate in candidates:
        trades = kernels.run_trades(
            sigs[_key(candidate)], inst, seg, capital, rm, replay_policy=replay_policy, **(exit_kwargs or {}),
        )
        metrics = kernels.compute_metrics(trades, capital)
        objective = _objective(metrics)
        evaluated.append((candidate, objective, len(trades)))
        sharpe = metrics.consistency if metrics.trades >= _MIN_IS_TRADES else None
        _observe_trial(progress, "final_development_trials", candidate, objective, len(trades), -1, sharpe)
    selected = max(evaluated, key=lambda row: row[1])[0]
    _observe_selection(progress, "final_development_trials", selected, -1)
    trials = [FinalSelectionTrial(
        params={**base, **candidate},
        objective=objective if math.isfinite(objective) else None, trades=trades,
        selected=_key(candidate) == _key(selected),
    ) for candidate, objective, trades in evaluated]
    return selected, trials


def optimize(candles, inst, strategy, *, space=None, n_folds: int = 3,
             capital: float = 50_000.0, base_params=None,
             pbo_blocks: int = 8, development_end=None,
             development_bars: int | None = None) -> OptimizationResult:
    base = dict(base_params if base_params is not None else strategy.default_params)
    space = space if space is not None else param_space(strategy.key)
    candidates = [c for c in grid(space) if is_valid(strategy.key, {**base, **c})] or [{}]
    sigs = _candidate_signals(
        candles, strategy, base, candidates,
        development_end=development_end, development_bars=development_bars,
    )
    return optimize_signal_frames(sigs, candidates, inst, strategy, n_folds=n_folds,
        capital=capital, base=base, pbo_blocks=pbo_blocks)


def _observe_trial(progress, role, candidate, objective, trades, fold_index, sharpe):
    if progress is not None:
        progress[role].append({"params": dict(candidate), "fold_index": fold_index,
            "objective": objective if math.isfinite(objective) else None,
            "trades": trades, "is_sharpe": sharpe, "selected": False})


def _observe_selection(progress, role, selected, fold_index):
    if progress is not None:
        for row in progress[role]:
            if row["fold_index"] == fold_index:
                row["selected"] = _key(row["params"]) == _key(selected)


def optimize_signal_frames(sigs, candidates, inst, strategy, *, n_folds=3,
                           capital=50_000.0, base=None, pbo_blocks=8, progress=None):
    """Shared nested/final selection over already development-clipped candidate frames."""
    base = {} if base is None else base
    seg = kernels.backtest_charge_segment(inst)
    rm = getattr(strategy, "risk_model", None)
    replay_policy = getattr(strategy, "replay_policy", None)
    exit_kwargs = kernels.replay_exit_kwargs(strategy)
    n = min((len(s) for s in sigs.values()), default=0)
    seg_size = n // (n_folds + 1)
    empty = OptimizationResult(
        [], [], [], [], kernels.compute_metrics([], capital), 0,
        selected_params=base,
    )
    if seg_size < 1:
        return empty

    trials, per_fold_selected, per_fold_oos, pooled_oos = _nested_trials(
        sigs, candidates, inst, seg, capital, rm, n_folds, seg_size, replay_policy=replay_policy, exit_kwargs=exit_kwargs, progress=progress,
    )
    selected, final_trials = _select_params(
        sigs, candidates, inst, seg, capital, rm, base, replay_policy=replay_policy, exit_kwargs=exit_kwargs, progress=progress,
    )
    return OptimizationResult(
        trials=trials, per_fold_selected=per_fold_selected, per_fold_oos=per_fold_oos,
        oos_trades=pooled_oos, oos_metrics=kernels.compute_metrics(pooled_oos, capital),
        n_trials=n_folds * len(candidates),
        perf_matrix=_performance_matrix(
            sigs, candidates, inst, seg, capital, rm, pbo_blocks,
            replay_policy=replay_policy, exit_kwargs=exit_kwargs,
        ),
        selected_params={**base, **selected},
        final_trials=final_trials,
    )
