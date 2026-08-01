"""Probability of Backtest Overfitting via CSCV (Bailey & Lopez de Prado).

The DSR (`stats/dsr.py`) asks whether a Sharpe is large enough to survive having
been *chosen* from N tries. PBO asks a different question, and a search can pass
one while failing the other: **when you pick the in-sample winner, does it stay a
winner out-of-sample, or does the ranking simply scramble?** A strategy set with
no information at all still produces an impressive best-of-N — DSR prices that
in via the trial count, but only PBO looks at whether the selection *rule* has
any predictive content.

Combinatorially Symmetric Cross-Validation:

1. Split the observation window into `n_splits` (S) equal sub-periods.
2. For every way of choosing S/2 of them as the training set (C(S, S/2)
   combinations, symmetric because the complement is the test set):
   a. rank strategies by training performance; take the best,
   b. find that strategy's rank in the TEST performance,
   c. convert its relative rank ω ∈ (0,1) to a logit λ = ln(ω/(1−ω)).
3. PBO = the fraction of splits with λ ≤ 0 — i.e. how often the in-sample
   winner lands in the bottom half out-of-sample.

The interpretation that matters: **on pure noise this returns ≈ 0.5, not 0.**
An overfitting statistic that reported "clean" on randomness would launder noise
into confidence, which is worse than having no statistic at all. That property is
pinned by test.

Pure and deterministic — no RNG, no I/O — so a promotion decision made from it is
reproducible.
"""
from __future__ import annotations

import dataclasses
import itertools
import math

import numpy as np


@dataclasses.dataclass(frozen=True)
class PBOResult:
    pbo: float                  # fraction of splits whose IS-winner underperformed OOS
    logits: list                # λ per split — the distribution behind the headline
    n_splits_evaluated: int
    n_strategies: int

    @property
    def median_logit(self) -> float:
        return float(np.median(self.logits)) if self.logits else 0.0


def _as_matrix(perf) -> np.ndarray:
    """(observations x strategies) float matrix, or ValueError.

    Refuses rather than coerces: a ragged input silently padded, or a single
    column quietly accepted, would produce a confident number that means nothing.
    """
    try:
        m = np.asarray(perf, dtype=float)
    except (ValueError, TypeError) as e:
        raise ValueError(f"performance matrix is not rectangular numeric data: {e}") from e
    if m.ndim != 2:
        raise ValueError(f"expected a 2-D (observations x strategies) matrix, got {m.ndim}-D")
    if m.shape[1] < 2:
        # PBO is a statement about SELECTION. With one candidate nothing was
        # selected and a rank is undefined — returning 0.0 would read as "not
        # overfit", which is the opposite of what we know (which is nothing).
        raise ValueError("PBO needs at least 2 strategies to rank; selection is "
                         "undefined with one candidate")
    return m


def pbo(perf, *, n_splits: int = 16) -> PBOResult:
    """PBO over a (observations x strategies) performance matrix.

    `perf[t][n]` is strategy n's performance in observation period t — per-period
    net P&L or return. Rows are aggregated by SUM within each sub-period, so the
    unit only has to be additive across time.
    """
    if n_splits % 2 != 0:
        raise ValueError(f"n_splits must be even (CSCV takes S/2 at a time); got {n_splits}")
    m = _as_matrix(perf)
    n_obs, n_strat = m.shape
    if n_obs < n_splits:
        raise ValueError(f"need at least {n_splits} observations to form {n_splits} "
                         f"sub-periods; got {n_obs}")

    # Equal sub-periods; any remainder tail is dropped so every block has the same
    # weight (an oversized final block would quietly dominate the ranking).
    block = n_obs // n_splits
    blocks = np.array([m[i * block:(i + 1) * block].sum(axis=0) for i in range(n_splits)])

    half = n_splits // 2
    logits: list[float] = []
    for train_idx in itertools.combinations(range(n_splits), half):
        test_idx = [i for i in range(n_splits) if i not in train_idx]
        is_perf = blocks[list(train_idx)].sum(axis=0)
        oos_perf = blocks[test_idx].sum(axis=0)

        best = int(np.argmax(is_perf))
        # Rank of the IS winner within the OOS results: 1 = worst .. N = best.
        # Ties share the lower rank, which is the conservative reading (a tie is
        # not evidence the winner held up).
        rank = 1 + int(np.sum(oos_perf < oos_perf[best]))
        omega = rank / (n_strat + 1.0)          # in (0,1), never 0 or 1
        logits.append(math.log(omega / (1.0 - omega)))

    failures = sum(1 for x in logits if x <= 0.0)
    return PBOResult(pbo=failures / len(logits), logits=logits,
                     n_splits_evaluated=len(logits), n_strategies=n_strat)


def pbo_gate(perf, *, n_splits: int = 16, threshold: float = 0.30) -> bool:
    """True if this search is fit to promote a candidate.

    **Fails closed.** A matrix PBO cannot evaluate — too few observations, a
    single candidate, ragged data — returns False, never True. Research that
    could not be checked is not research that passed; same discipline as
    `research/guards.py`.
    """
    try:
        return pbo(perf, n_splits=n_splits).pbo <= threshold
    except ValueError:
        return False
