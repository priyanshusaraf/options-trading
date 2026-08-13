"""Regime labelling — trend/chop x volatility, per bar.

The last piece of the research loop: "does this edge exist everywhere, or only
in one kind of market?" A strategy that makes all its money in high-volatility
trends and gives it back in quiet chop looks mediocre in aggregate and is
actually a good strategy with a missing filter. Aggregate statistics cannot tell
those two apart.

**Why this had to come after Phase 0.** Conditioning on regime MULTIPLIES the
trial count: evaluating a candidate in four regimes and reporting the best is
four more chances to be lucky. Before deflation actually engaged (it did not
until today — `var_sr` was never computed) this would have been a machine for
manufacturing regime-specific mirages. `regime_trial_multiplier` exists so the
DSR is told about it.

Pure and deterministic: no DB, no clock, no RNG. Labels are computed from the
same bar data the strategy sees, using only backward-looking windows — a regime
label that peeked ahead would leak the future into every conditional result
built on it.
"""
from __future__ import annotations

import pandas as pd
from app.ir.contributors.generated_blocks import (
    REGIMES,
    UNKNOWN,
    atr_pct,
    efficiency_ratio,
    label_regimes,
)


def regime_distribution(labels: pd.Series) -> dict:
    """How much of the sample sat in each regime — the context that decides
    whether a per-regime result means anything."""
    if labels is None or len(labels) == 0:
        return {}
    counts = labels.value_counts().to_dict()
    return {k: int(v) for k, v in counts.items()}


def split_trades_by_regime(trades, labels: pd.Series, index_of) -> dict:
    """Bucket closed trades by the regime AT ENTRY.

    Entry, not exit, and not an average across the holding period: the regime a
    trade was opened in is the one the entry decision could actually have
    conditioned on. Anything else grades the decision using information it did
    not have.
    """
    out: dict = {r: [] for r in REGIMES}
    out[UNKNOWN] = []
    for t in trades or []:
        try:
            i = index_of(t)
            label = labels.iloc[i] if 0 <= i < len(labels) else UNKNOWN
        except Exception:
            label = UNKNOWN
        out.setdefault(str(label), []).append(t)
    return out


def regime_trial_multiplier(labels: pd.Series, *, min_bars: int = 30) -> int:
    """How many regimes carried enough data to have been selected among.

    Feeds `sibling_trials` so the DSR knows that reporting the best of N regimes
    is N chances to be lucky. Regimes too thin to evaluate are not counted — they
    were never really candidates.
    """
    dist = regime_distribution(labels)
    return max(1, sum(1 for r, n in dist.items() if r != UNKNOWN and n >= min_bars))
