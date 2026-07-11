"""Optimization — nested walk-forward. Params are searched on each fold's in-sample
window and the winner is evaluated on the fold's UNTOUCHED out-of-sample window, so
the OOS record is never contaminated by selection. Every trial is recorded (the DSR
deflation ledger). Optimization runs only after qualification (the orchestrator gates
it); here we test the mechanics directly.
"""
from collections import defaultdict

from research.evaluation import kernels
from research.pipeline.optimize import OptimizationResult, optimize
from research.strategy.spec import grid, param_space


def _strat():
    return kernels.get_strategy("trend_impulse_v3")


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
