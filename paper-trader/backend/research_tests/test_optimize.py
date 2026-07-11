"""Optimization — nested walk-forward. Params are searched on each fold's in-sample
window and the winner is evaluated on the fold's UNTOUCHED out-of-sample window, so
the OOS record is never contaminated by selection. Every trial is recorded (the DSR
deflation ledger). Optimization runs only after qualification (the orchestrator gates
it); here we test the mechanics directly.
"""
from collections import defaultdict

from research.evaluation import kernels
from research.pipeline.optimize import OptimizationResult, _objective, optimize
from research.strategy.spec import grid, param_space


def _strat():
    return kernels.get_strategy("trend_impulse_v3")


class _M:
    """Minimal BTMetrics stand-in for objective unit tests."""
    def __init__(self, trades, expectancy, consistency):
        self.trades = trades
        self.expectancy = expectancy
        self.consistency = consistency


def test_objective_prefers_many_consistent_trades_over_one_big_trade():
    # The bug: raw expectancy makes a single huge buy-and-hold win beat a real
    # many-trade edge; that winner then completes 0 round-trips out-of-sample.
    one_big = _M(trades=1, expectancy=500_000.0, consistency=None)
    many_consistent = _M(trades=40, expectancy=1_500.0, consistency=0.5)
    assert _objective(many_consistent) > _objective(one_big)


def test_objective_excludes_too_few_trades():
    # a lone trade (or a handful) is not evidence of an edge, however big
    assert _objective(_M(trades=1, expectancy=1e9, consistency=None)) == float("-inf")
    assert _objective(_M(trades=3, expectancy=1e9, consistency=2.0)) == float("-inf")


def test_objective_is_a_trade_count_aware_t_stat():
    base = _M(trades=40, expectancy=100, consistency=0.3)
    more_consistent = _M(trades=40, expectancy=100, consistency=0.6)
    more_trades = _M(trades=90, expectancy=100, consistency=0.3)
    assert _objective(more_consistent) > _objective(base)   # higher per-trade Sharpe wins
    assert _objective(more_trades) > _objective(base)        # more trades at same edge wins (√n)


def test_optimize_records_every_trial_and_pools_oos(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    n_candidates = len(grid(param_space("trend_impulse_v3")))
    assert res.n_trials == 3 * n_candidates
    assert len(res.trials) == 3 * n_candidates
    assert len(res.per_fold_selected) == 3
    assert res.oos_metrics is not None


def test_optimize_selects_params_from_the_grid(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    g = grid(param_space("trend_impulse_v3"))
    assert all(sel in g for sel in res.per_fold_selected)


def test_optimize_selected_is_best_in_sample_objective_per_fold(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    by_fold = defaultdict(list)
    for t in res.trials:
        by_fold[t.fold_index].append(t)
    for trials in by_fold.values():
        selected = [t for t in trials if t.selected]
        assert len(selected) == 1
        assert selected[0].is_objective == max(t.is_objective for t in trials)


def test_optimize_insufficient_data_is_safe(fake_inst, candles_factory):
    res = optimize(candles_factory(40), fake_inst, _strat(), n_folds=8)
    assert isinstance(res, OptimizationResult)
    assert res.oos_metrics is not None
