"""Probability of Backtest Overfitting via CSCV (Bailey & Lopez de Prado).

The DSR asks "is this Sharpe big enough to survive having been chosen from N
tries?". PBO asks a different and complementary question: "when I pick the
in-sample winner, does it stay a winner out-of-sample — or does the ranking
scramble?" A search can pass DSR and still be pure overfit if the IS ranking
carries no OOS information at all, which is exactly what PBO detects.

CSCV: split the observation window into S sub-periods, take every way of
choosing S/2 of them as the training set, and for each such split find the
IS-best strategy and look up where it lands in the OOS ranking. Its relative
rank ω becomes a logit λ = ln(ω/(1−ω)). PBO is the fraction of splits with
λ ≤ 0 — the in-sample winner landing in the bottom half out-of-sample.

The property that makes this test file worth having is the null: **feed it pure
noise and PBO must come out near 0.5.** A statistic that reports "not overfit"
on noise is worse than no statistic, because it launders randomness into
confidence. Both directions are pinned below.
"""
from __future__ import annotations

import numpy as np
import pytest

from research.stats.pbo import pbo


def _noise(n_obs=64, n_strat=12, seed=0):
    """A pure null: every strategy is the same coin, none has edge."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, size=(n_obs, n_strat))


# ── the null: noise must look overfit ───────────────────────────────────────

def test_pure_noise_gives_pbo_near_one_half_ON_AVERAGE():
    """The load-bearing property, stated at the right level.

    With no real edge anywhere the IS winner is a coin flip to land in the OOS
    bottom half, so PBO ≈ 0.5 — but that is an expectation OVER noise draws, not
    a property of any single draw. In one finite realisation some strategy really
    does have the highest sample mean, and that luck persists across sub-periods,
    so a single matrix can legitimately score anywhere from ~0.1 to ~0.9 (measured
    across 40 seeds). Asserting per-seed would be asserting something false, and
    would flake.

    Measured: mean 0.453 over 40 draws."""
    vals = [pbo(_noise(n_obs=128, seed=s), n_splits=8).pbo for s in range(40)]
    mean = sum(vals) / len(vals)
    assert 0.35 < mean < 0.65, f"noise averaged PBO={mean:.3f} over {len(vals)} draws"


# ── genuine, persistent edge must NOT look overfit ──────────────────────────

def test_a_genuinely_dominant_strategy_gives_a_low_pbo():
    """One strategy is better in every sub-period. The IS winner is the same
    strategy OOS, every time, so PBO collapses toward zero."""
    m = _noise(seed=5)
    m[:, 3] += 3.0                       # strategy 3 has real, persistent edge
    res = pbo(m, n_splits=8)
    assert res.pbo < 0.10, f"a persistently dominant strategy scored PBO={res.pbo:.3f}"


def test_selection_driven_purely_by_local_noise_is_caught():
    """The cleanest possible overfit, and the case PBO exists for.

    Every strategy spikes in exactly ONE sub-period and is noise elsewhere. So
    whichever blocks land in training fully determines the winner — and that
    winner has nothing at all in the test blocks, while the strategies that spike
    THERE beat it. The in-sample ranking carries zero out-of-sample information
    and PBO pins it at 1.0.

    (An earlier version of this test used an edge present only in the first half
    and expected a high PBO. That was wrong: with S=8 only ONE of the 70 splits
    puts all four edge-blocks in training, so PBO correctly came out ~0.014. The
    statistic was right and the test's intuition was not.)"""
    rng = np.random.default_rng(0)
    n_splits, block, n_strat = 8, 16, 8
    m = rng.normal(0.0, 1.0, size=(n_splits * block, n_strat))
    for i in range(n_strat):
        m[i * block:(i + 1) * block, i] += 10.0
    res = pbo(m, n_splits=n_splits)
    assert res.pbo > 0.90, f"a purely noise-selected winner scored PBO={res.pbo:.3f}"


# ── shape of the answer ─────────────────────────────────────────────────────

def test_the_result_carries_the_logits_it_was_computed_from():
    res = pbo(_noise(), n_splits=8)
    from math import comb
    assert len(res.logits) == comb(8, 4)
    assert res.n_splits_evaluated == comb(8, 4)


def test_pbo_is_a_probability():
    res = pbo(_noise(), n_splits=8)
    assert 0.0 <= res.pbo <= 1.0


def test_it_is_deterministic():
    """No RNG of its own: the same matrix must always give the same answer, or a
    promotion decision is not reproducible."""
    m = _noise(seed=11)
    assert pbo(m, n_splits=8).pbo == pbo(m, n_splits=8).pbo


# ── refusals, rather than a confident wrong answer ──────────────────────────

def test_an_odd_split_count_is_refused():
    """CSCV requires S/2 to be an integer; silently rounding would change the
    estimator without saying so."""
    with pytest.raises(ValueError):
        pbo(_noise(), n_splits=7)


def test_a_single_strategy_cannot_be_ranked():
    """PBO is a statement about SELECTION among candidates. With one candidate
    there is no selection, and a rank is meaningless — refuse rather than
    return 0.0, which would read as 'not overfit'."""
    with pytest.raises(ValueError):
        pbo(np.zeros((32, 1)), n_splits=8)


def test_too_few_observations_to_split_is_refused():
    with pytest.raises(ValueError):
        pbo(np.zeros((4, 6)), n_splits=8)


def test_a_ragged_matrix_is_refused():
    with pytest.raises(ValueError):
        pbo([[1.0, 2.0], [3.0]], n_splits=2)


# ── the gate ────────────────────────────────────────────────────────────────

def test_the_gate_rejects_an_overfit_search():
    from research.stats.pbo import pbo_gate
    rng = np.random.default_rng(0)
    m = rng.normal(0.0, 1.0, size=(128, 8))
    for i in range(8):
        m[i * 16:(i + 1) * 16, i] += 10.0
    assert pbo_gate(m, n_splits=8, threshold=0.30) is False


def test_the_gate_passes_a_persistent_edge():
    from research.stats.pbo import pbo_gate
    m = _noise(seed=5)
    m[:, 3] += 3.0
    assert pbo_gate(m, n_splits=8, threshold=0.30) is True


def test_the_gate_fails_closed_when_it_cannot_be_computed():
    """A matrix PBO cannot evaluate must NOT pass the gate. Research that cannot
    be checked is not research that passed — same fail-closed discipline as
    research/guards.py."""
    from research.stats.pbo import pbo_gate
    assert pbo_gate(np.zeros((4, 1)), n_splits=8, threshold=0.30) is False


# ── wiring: the statistic has to reach a decision ───────────────────────────

def test_optimize_produces_a_pbo_matrix(fake_inst, candles_factory):
    """A statistic nothing consumes is exactly the failure `var_sr` had: present,
    correct, and never reaching a decision. The matrix must come out of the real
    search, not a fixture."""
    from research_tests.test_optimize import _strat
    from research.pipeline.optimize import optimize
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3, pbo_blocks=8)
    assert len(res.perf_matrix) == 8, "expected one row per sub-period"
    assert all(len(row) == len(res.perf_matrix[0]) for row in res.perf_matrix)
    assert pbo(res.perf_matrix, n_splits=8).pbo >= 0.0


def test_the_pbo_gate_is_part_of_the_battery():
    """It must be able to FAIL a candidate that clears everything else, or it is
    decoration."""
    from research.pipeline.validate import gates_passed
    battery = {"min_oos_trades": {"passed": True, "value": 40},
               "temporal_stability": {"passed": True, "value": 0.8},
               "confident_edge": {"passed": True, "value": 12.0},
               "slippage_stress_2x": {"passed": True, "value": 4.0},
               "pbo": {"passed": False, "value": 0.62}}
    assert gates_passed(battery) is False


def test_an_uncomputable_pbo_blocks_promotion_rather_than_waving_it_through():
    """Fail-closed, same discipline as research/guards.py: research that could
    not be checked is not research that passed."""
    from research.pipeline.validate import gates_passed
    assert gates_passed({"pbo": {"passed": False, "value": "not computable"}}) is False
