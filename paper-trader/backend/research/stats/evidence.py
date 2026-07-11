"""Bootstrap evidence gates. At these sample sizes a positive average is not enough
— it must be *confidently* positive. `bootstrap_mean_lower_bound` resamples the
per-trade outcomes and returns the alpha-quantile of the bootstrapped mean; the
`min_evidence` gate then requires both enough trades and a lower bound above zero.
Deterministic given a seed (so a run is reproducible).
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def bootstrap_mean_lower_bound(values: Iterable[float], *, alpha: float = 0.05,
                               n_boot: int = 2000, seed: int = 0) -> float:
    """The alpha-quantile of the bootstrapped mean of `values` (e.g. per-trade net
    P&L). alpha=0.05 -> a one-sided 95% lower confidence bound. Empty -> 0.0."""
    v = np.asarray(list(values), dtype=float)
    if v.size == 0:
        return 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    means = v[idx].mean(axis=1)
    return float(np.quantile(means, alpha))


def min_evidence(values: Iterable[float], *, min_trades: int, alpha: float = 0.05,
                 n_boot: int = 2000, seed: int = 0) -> bool:
    """Hard minimum-evidence gate: at least `min_trades` outcomes AND a bootstrap
    lower bound on the mean strictly above zero."""
    v = list(values)
    if len(v) < min_trades:
        return False
    return bootstrap_mean_lower_bound(v, alpha=alpha, n_boot=n_boot, seed=seed) > 0.0
