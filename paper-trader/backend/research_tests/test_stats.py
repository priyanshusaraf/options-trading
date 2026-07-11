"""Statistical gates — the discipline that keeps research honest at this data scale.
Effective sample size (correlated instruments are not independent evidence),
bootstrap lower bounds (is the edge confidently positive?), and the Deflated Sharpe
Ratio (does the edge survive the number of trials that produced it?).
"""
from research.stats.dsr import deflated_sharpe, probabilistic_sharpe
from research.stats.evidence import bootstrap_mean_lower_bound, min_evidence
from research.stats.neff import effective_sample_size
from research.stats.retest import retest_priority


def test_neff_uncorrelated_equals_n():
    assert effective_sample_size(0.0, 200) == 200


def test_neff_perfectly_correlated_is_one():
    assert effective_sample_size(1.0, 200) == 1.0


def test_neff_partial_correlation_shrinks_hard():
    # rho=0.4, n=200 -> ~2.48 independent bets, not 200
    assert 2.3 < effective_sample_size(0.4, 200) < 2.7


def test_neff_clamps_negative_correlation_to_n():
    assert effective_sample_size(-0.3, 50) == 50


def test_bootstrap_lower_bound_positive_for_strong_sample():
    lb = bootstrap_mean_lower_bound([5.0] * 40 + [4.0] * 40, alpha=0.05, seed=1)
    assert lb > 0


def test_bootstrap_lower_bound_negative_for_noisy_break_even():
    lb = bootstrap_mean_lower_bound([10.0, -9.0] * 30, alpha=0.05, seed=1)
    assert lb < 0


def test_bootstrap_is_deterministic_with_seed():
    vals = [1.0, -1.0, 2.0, -0.5] * 20
    assert bootstrap_mean_lower_bound(vals, seed=7) == bootstrap_mean_lower_bound(vals, seed=7)


def test_probabilistic_sharpe_high_for_strong_edge():
    assert probabilistic_sharpe(0.2, 200) > 0.9


def test_probabilistic_sharpe_zero_for_tiny_sample():
    assert probabilistic_sharpe(0.5, 1) == 0.0


def test_deflated_sharpe_decreases_with_more_trials():
    single = deflated_sharpe(0.2, 200, n_trials=1)
    many = deflated_sharpe(0.2, 200, n_trials=500, var_sr=0.01)
    assert many < single


def test_min_evidence_requires_enough_trades_and_confident_edge():
    assert min_evidence([3.0] * 60, min_trades=30, seed=1) is True
    assert min_evidence([3.0] * 10, min_trades=30, seed=1) is False       # too few trades
    assert min_evidence([10.0, -9.5] * 30, min_trades=30, seed=1) is False  # not confidently positive


def test_retest_priority_low_right_after_test_and_never_below_floor():
    p = retest_priority(days_since_test=0, kill_strength=1.0, floor=0.05)
    assert p == 0.05  # just tested + decisively killed -> at the floor, never banned


def test_retest_priority_recovers_as_it_goes_stale():
    fresh = retest_priority(days_since_test=10, kill_strength=0.5)
    stale = retest_priority(days_since_test=400, kill_strength=0.5)
    assert stale > fresh  # a dormant hypothesis becomes worth revisiting


def test_retest_priority_decisive_kill_stays_suppressed_longer():
    at = 180
    marginal = retest_priority(days_since_test=at, kill_strength=0.0)
    decisive = retest_priority(days_since_test=at, kill_strength=1.0)
    assert decisive < marginal  # a coin-flip kill reopens sooner than a decisive one


def test_retest_priority_stays_within_bounds():
    for d in (0, 50, 500, 5000):
        p = retest_priority(days_since_test=d, kill_strength=0.3)
        assert 0.05 <= p <= 1.0
