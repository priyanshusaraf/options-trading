"""Deflated Sharpe Ratio (Bailey & Lopez de Prado). The Probabilistic Sharpe Ratio
asks "is this Sharpe significantly above a benchmark, given sample size, skew and
kurtosis?"; the DSR sets that benchmark to the Sharpe you'd expect to see by luck
from the *number of trials* that produced the winner. It is the single ranking
number hardest to game, because it bakes in trade count, non-normality, and
selection-across-trials — exactly the biases this data scale invites.

Uses `statistics.NormalDist` (stdlib) for the normal CDF / inverse CDF, so no scipy.
"""
from __future__ import annotations

import math
from statistics import NormalDist

_N = NormalDist()
_EULER = 0.5772156649015329  # Euler-Mascheroni


def probabilistic_sharpe(sr: float, n: int, *, skew: float = 0.0, kurt: float = 3.0,
                         sr_benchmark: float = 0.0) -> float:
    """P(true SR > sr_benchmark) for an observed per-observation Sharpe `sr` over `n`
    observations, correcting for skew and (excess-adjusted) kurtosis. n<2 -> 0.0."""
    if n < 2:
        return 0.0
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr))
    return _N.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / denom)


def expected_max_sharpe(var_sr: float, n_trials: int) -> float:
    """The Sharpe a lucky best-of-`n_trials` would post under the null, given the
    variance of trial Sharpes. This is the DSR benchmark. n_trials<=1 -> 0."""
    if n_trials <= 1 or var_sr <= 0.0:
        return 0.0
    a = _N.inv_cdf(1.0 - 1.0 / n_trials)
    b = _N.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_sr) * ((1.0 - _EULER) * a + _EULER * b)


def deflated_sharpe(sr: float, n: int, *, skew: float = 0.0, kurt: float = 3.0,
                    n_trials: int = 1, var_sr: float = 0.0) -> float:
    """DSR = PSR with the benchmark set to the expected best-of-n_trials Sharpe.
    With n_trials=1 this reduces to PSR against zero (no selection to deflate)."""
    sr0 = expected_max_sharpe(var_sr, n_trials)
    return probabilistic_sharpe(sr, n, skew=skew, kurt=kurt, sr_benchmark=sr0)
