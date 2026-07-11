"""Effective sample size. Testing one rule across many correlated instruments is
NOT independent corroboration: with average pairwise correlation rho, N instruments
carry only N / (1 + (N-1)*rho) independent bets. For NIFTY large-caps (rho ~ 0.4)
that turns 200 names into ~2.5 independent observations. Breadth must be counted in
`effective_sample_size`, never raw instrument count.
"""
from __future__ import annotations


def effective_sample_size(mean_corr: float, n: int) -> float:
    """N_eff = n / (1 + (n-1)*rho), with rho clamped to [0, 1]. rho<=0 -> n (fully
    independent); rho=1 -> 1 (one bet restated n times)."""
    if n <= 1:
        return float(n)
    rho = min(max(mean_corr, 0.0), 1.0)
    if rho <= 0.0:
        return float(n)
    return n / (1.0 + (n - 1) * rho)
