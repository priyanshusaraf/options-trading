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


def mean_pairwise_correlation(series: list) -> float:
    """Average pairwise Pearson correlation across equal-length return series.

    Fewer than two usable series -> 0.0 (nothing to be correlated WITH, so the
    honest answer is "no shared movement measured", not "assume independence" —
    with one series `effective_sample_size` returns 1 either way).

    Series are truncated to their common length: instruments have different
    history depths, and correlating a long one against a short one on positional
    index would compare different calendar periods.
    """
    import numpy as np

    rows = [np.asarray(s, dtype=float) for s in series if s is not None and len(s) > 1]
    if len(rows) < 2:
        return 0.0
    n = min(len(r) for r in rows)
    if n < 2:
        return 0.0
    m = np.vstack([r[-n:] for r in rows])          # align on the most RECENT n
    # Drop degenerate (zero-variance) rows: a flat series correlates with nothing
    # and numpy would emit nan for it.
    keep = m[m.std(axis=1) > 0]
    if keep.shape[0] < 2:
        return 0.0
    c = np.corrcoef(keep)
    iu = np.triu_indices_from(c, k=1)
    vals = c[iu]
    vals = vals[np.isfinite(vals)]
    return float(vals.mean()) if vals.size else 0.0
