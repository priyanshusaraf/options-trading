"""Phase 0: deflation has to actually engage.

The Deflated Sharpe Ratio exists to answer one question — "is this the best of N
tries, or is it real?" It sets the significance benchmark to the Sharpe a lucky
best-of-N would post under the null. That benchmark is
`expected_max_sharpe(var_sr, n_trials)`, and it is **identically zero whenever
`var_sr` is zero**:

    if n_trials <= 1 or var_sr <= 0.0:
        return 0.0                        # research/stats/dsr.py:32-33

Nothing computed `var_sr`. `build_scorecard` defaults it to `0.0` and the
orchestrator passed only `n_trials` (`orchestrator/run.py:172`). So the DSR
silently degraded to a PSR against zero, on every candidate, forever — the
search could widen to a thousand trials and the bar would not move. The
docstring in `strategy/builder/search.py` asserted the opposite ("a wider search
*raises* the significance bar"), which made it worse: the lab claimed a
protection it did not have.

The acceptance criterion is the roadmap's own, and it is a falsification test
rather than a unit test: a no-edge universe swept wide must promote NOTHING, and
the same sweep with deflation disabled must promote something — otherwise the
test proves only that the pipeline is generally reluctant, not that deflation is
what stopped it.
"""
from __future__ import annotations

import math
import random

import pytest

from research.stats.dsr import deflated_sharpe, expected_max_sharpe


# ── the benchmark itself ────────────────────────────────────────────────────

def test_the_benchmark_is_zero_without_var_sr_which_is_the_whole_bug():
    """Pinned so nobody 'simplifies' var_sr back out of the call chain."""
    assert expected_max_sharpe(var_sr=0.0, n_trials=1000) == 0.0


def test_the_benchmark_rises_with_search_breadth():
    """The property search.py's docstring claims. It only holds once var_sr is
    real — which is what this phase wires up."""
    narrow = expected_max_sharpe(var_sr=0.04, n_trials=10)
    wide = expected_max_sharpe(var_sr=0.04, n_trials=1000)
    assert 0 < narrow < wide


def test_a_wider_search_lowers_the_dsr_of_an_identical_result():
    """Same observed Sharpe, same sample — more trials must mean less belief."""
    kw = dict(sr=0.15, n=200, var_sr=0.04)
    assert deflated_sharpe(**kw, n_trials=1000) < deflated_sharpe(**kw, n_trials=10)


def test_deflation_can_actually_reject_a_lucky_winner():
    """The point of the exercise: a Sharpe that passes undeflated must be able to
    FAIL once the trial count it came from is accounted for."""
    undeflated = deflated_sharpe(sr=0.12, n=150, n_trials=1, var_sr=0.0)
    deflated = deflated_sharpe(sr=0.12, n=150, n_trials=500, var_sr=0.05)
    assert undeflated > 0.90, "control: this result looks great on its own"
    assert deflated < 0.50, "but it is unremarkable as the best of 500 tries"


# ── var_sr must be computed from the trials actually run ────────────────────

def test_optimization_result_reports_the_dispersion_of_its_trial_sharpes():
    from research.pipeline.optimize import OptimizationResult, Trial

    # Two folds x three candidates, with genuinely dispersed per-trade Sharpes.
    sharpes = [0.05, 0.20, -0.10, 0.15, 0.00, 0.30]
    trials = [Trial(fold_index=i // 3, params={"p": i}, is_objective=s * math.sqrt(100),
                    is_trades=100, oos_trades=0, selected=False, is_sharpe=s)
              for i, s in enumerate(sharpes)]
    res = OptimizationResult(trials=trials, per_fold_selected=[], per_fold_oos=[],
                             oos_trades=[], oos_metrics=None, n_trials=len(trials))
    mean = sum(sharpes) / len(sharpes)
    expected = sum((x - mean) ** 2 for x in sharpes) / len(sharpes)
    assert res.var_sr == pytest.approx(expected)


def test_var_sr_ignores_trials_that_never_produced_a_sharpe():
    """Candidates below the trade floor score -inf and have no Sharpe. Including
    them would poison the variance with a sentinel."""
    from research.pipeline.optimize import OptimizationResult, Trial

    good = [Trial(0, {}, 1.0, 100, 0, False, is_sharpe=0.1),
            Trial(0, {}, 1.0, 100, 0, False, is_sharpe=0.3)]
    dead = [Trial(0, {}, float("-inf"), 2, 0, False, is_sharpe=None)]
    res = OptimizationResult(good + dead, [], [], [], None, 3)
    assert res.var_sr == pytest.approx(0.01)      # var of {0.1, 0.3}


def test_a_single_trial_has_no_dispersion_and_deflates_nothing():
    from research.pipeline.optimize import OptimizationResult, Trial
    res = OptimizationResult([Trial(0, {}, 1.0, 100, 0, True, is_sharpe=0.2)],
                             [], [], [], None, 1)
    assert res.var_sr == 0.0


# ── the acceptance criterion ────────────────────────────────────────────────

def _no_edge_sharpes(n_trials: int, seed: int = 7) -> list[float]:
    """Trial Sharpes drawn from a TRUE null: mean zero, realistic dispersion.
    This is what a wide search over a no-edge universe produces."""
    rng = random.Random(seed)
    return [rng.gauss(0.0, 0.2) for _ in range(n_trials)]


def test_a_no_edge_universe_swept_wide_promotes_nothing():
    """ACCEPTANCE (roadmap Workstream A, Phase 0).

    Sweep a no-edge universe with a wide search, take the LUCKIEST result — the
    one a naive pipeline would promote — and require that deflation rejects it.
    """
    n_trials = 400
    sharpes = _no_edge_sharpes(n_trials)
    var_sr = sum((s - sum(sharpes) / len(sharpes)) ** 2 for s in sharpes) / len(sharpes)
    luckiest = max(sharpes)

    dsr = deflated_sharpe(sr=luckiest, n=120, n_trials=n_trials, var_sr=var_sr)
    assert dsr < 0.95, (
        f"the best of {n_trials} coin flips (Sharpe {luckiest:.3f}) cleared a 0.95 "
        f"promotion bar — deflation is not engaging")


def test_the_same_sweep_promotes_freely_with_deflation_stubbed_off():
    """The other half of the acceptance, and the half that makes it meaningful:
    without deflation the SAME no-edge winner sails through. If this failed, the
    test above would prove only that the pipeline is squeamish, not that
    deflation is what caught it."""
    sharpes = _no_edge_sharpes(400)
    luckiest = max(sharpes)
    undeflated = deflated_sharpe(sr=luckiest, n=120, n_trials=1, var_sr=0.0)
    assert undeflated > 0.95, (
        "control failed: this no-edge winner should look promotable when the "
        "selection bias is ignored")


# ── the composition search is a trial count too (Phase 0 item 1) ────────────

def test_sibling_trials_multiplies_the_deflation_count():
    """`run_generated` enumerates N compositions and keeps the best, but each one
    is scored by its own `run_experiment`, which can only see its own parameter
    grid. Without a sibling count each composition is priced as though it were the
    only thing ever tried — understating the selection bias by exactly N."""
    import inspect
    from research.orchestrator.run import run_experiment
    sig = inspect.signature(run_experiment)
    assert "sibling_trials" in sig.parameters
    assert sig.parameters["sibling_trials"].default == 1, \
        "the default must leave single-strategy runs untouched"


def test_run_generated_passes_the_composition_count_as_siblings():
    import inspect
    from research.orchestrator import generate
    src = inspect.getsource(generate.run_generated)
    assert "sibling_trials=len(compositions)" in src


def test_more_siblings_means_a_harder_bar():
    """The consequence: the same result, found while also trying 24 other ideas,
    must score lower than one found on the first try."""
    alone = deflated_sharpe(sr=0.15, n=200, n_trials=12, var_sr=0.04)
    among_many = deflated_sharpe(sr=0.15, n=200, n_trials=12 * 24, var_sr=0.04)
    assert among_many < alone
