"""Effective sample size, wired to the decision it should govern.

`effective_sample_size` has existed since M0 and had NO consumer. It encodes a
fact that matters at this data scale: testing one rule across N correlated
instruments is not N independent confirmations. For NIFTY large-caps (rho ~ 0.4)
200 names carry roughly 2.5 independent bets.

The place it belongs is the promotion step. `run_experiment` validates a strategy
per instrument and then does `max(validated, key=dsr)` — picking the best of N.
That is a selection, exactly like picking the best of N parameter draws, and the
DSR must be deflated for it. But deflating by N would overstate the correction,
because the instruments move together. N_eff is the honest count.
"""
from __future__ import annotations

import numpy as np
import pytest

from research.stats.neff import effective_sample_size, mean_pairwise_correlation


def test_identical_series_carry_one_bet():
    s = list(np.linspace(0, 1, 50))
    rho = mean_pairwise_correlation([s, s, s])
    assert rho == pytest.approx(1.0)
    assert effective_sample_size(rho, 3) == pytest.approx(1.0)


def test_independent_series_carry_their_full_count():
    rng = np.random.default_rng(0)
    rows = [rng.normal(size=400) for _ in range(4)]
    rho = mean_pairwise_correlation(rows)
    assert abs(rho) < 0.15
    assert effective_sample_size(max(rho, 0.0), 4) > 3.0


def test_realistically_correlated_names_are_deflated_hard():
    """The number from the module docstring: rho ~ 0.4 turns many names into few
    bets. This is the whole reason the gate exists."""
    assert effective_sample_size(0.4, 200) == pytest.approx(2.48, abs=0.05)


def test_series_are_aligned_on_their_common_tail():
    """Instruments have different history depths. Correlating a long series
    against a short one by position would compare different calendar periods."""
    rng = np.random.default_rng(3)
    long = list(rng.normal(size=300))
    short = long[-100:]
    assert mean_pairwise_correlation([long, short]) == pytest.approx(1.0)


def test_a_flat_series_does_not_poison_the_average():
    """Zero variance correlates with nothing; numpy yields nan for it."""
    rng = np.random.default_rng(4)
    rows = [rng.normal(size=100), rng.normal(size=100), [0.0] * 100]
    rho = mean_pairwise_correlation(rows)
    assert np.isfinite(rho)


def test_fewer_than_two_series_is_zero_not_an_error():
    assert mean_pairwise_correlation([]) == 0.0
    assert mean_pairwise_correlation([[1.0, 2.0, 3.0]]) == 0.0


# ── the consequence ─────────────────────────────────────────────────────────

def test_breadth_deflation_is_bounded_by_the_raw_count():
    """N_eff can never exceed N — the correction may only ever make the bar
    harder, never manufacture independent evidence that is not there."""
    for n in (1, 3, 12, 200):
        for rho in (0.0, 0.2, 0.6, 1.0):
            assert effective_sample_size(rho, n) <= n + 1e-9


def test_picking_the_best_of_correlated_instruments_deflates_less_than_naive_n():
    """Deflating by raw N would overstate the correction — the instruments move
    together, so there were not really N independent tries."""
    from research.stats.dsr import deflated_sharpe
    n, rho = 12, 0.5
    n_eff = effective_sample_size(rho, n)
    assert 1.0 < n_eff < n
    honest = deflated_sharpe(sr=0.15, n=200, n_trials=int(round(n_eff)), var_sr=0.04)
    over = deflated_sharpe(sr=0.15, n=200, n_trials=n, var_sr=0.04)
    assert honest > over, "raw-N deflation is harsher than the evidence justifies"


def test_breadth_deflation_uses_cross_instrument_dispersion_not_the_last_loop_value():
    """A bug caught in review of this very change.

    `var_sr` is assigned per-instrument inside the validation loop. Reusing that
    name at promotion time would have applied whichever instrument happened to be
    iterated LAST — its parameter-search dispersion — to a cross-instrument
    decision. The pool the winner was selected from is the instruments, so the
    dispersion must be measured across them."""
    import inspect
    from research.orchestrator import run as run_mod
    src = inspect.getsource(run_mod.run_experiment)
    assert "breadth_var_sr" in src
    assert "var_sr=breadth_var_sr" in src, \
        "the cross-instrument deflation must not reuse the per-instrument var_sr"
