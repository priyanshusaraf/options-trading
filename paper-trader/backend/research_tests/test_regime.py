"""Regime labelling: does this edge exist everywhere, or only in one market?

A strategy that earns in high-volatility trends and gives it back in quiet chop
looks mediocre in aggregate and is actually a good strategy with a missing
filter. Aggregate statistics cannot distinguish those two cases, which is what
this phase is for.

The property that carries every test below is NO LOOK-AHEAD. A regime label is
an input to an experiment, so a label computed with future bars visible would
leak the future into every conditional result built on it — and it would do so
invisibly, because the leak lives in the labelling rather than the strategy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.regime import (REGIMES, UNKNOWN, efficiency_ratio, label_regimes,
                             regime_distribution, regime_trial_multiplier,
                             split_trades_by_regime)


def _trending(n=400, step=1.0):
    close = pd.Series(100 + np.arange(n) * step, dtype=float)
    return pd.DataFrame({"open": close, "high": close + 0.5,
                         "low": close - 0.5, "close": close})


def _choppy(n=400, amp=1.0, seed=0):
    rng = np.random.default_rng(seed)
    close = pd.Series(100 + rng.normal(0, amp, n).cumsum() * 0.05, dtype=float)
    return pd.DataFrame({"open": close, "high": close + amp,
                         "low": close - amp, "close": close})


# ── no look-ahead ───────────────────────────────────────────────────────────

def test_a_label_never_depends_on_a_future_bar():
    """The load-bearing property. Truncating the series must not change any
    label that survives — if it does, the labeller is reading ahead."""
    df = _choppy(400, seed=3)
    full = label_regimes(df)
    prefix = label_regimes(df.iloc[:250].reset_index(drop=True))
    assert list(prefix) == list(full.iloc[:250]), \
        "labels changed when future bars were removed — the labeller leaks"


def test_warmup_bars_are_unknown_not_chop():
    """A bar with no history is UNKNOWN. Calling it 'chop' would invent a
    regime for every series' opening stretch and bias every conditional result."""
    labels = label_regimes(_trending(400))
    assert labels.iloc[0] == UNKNOWN
    assert labels.iloc[5] == UNKNOWN


# ── it actually discriminates ───────────────────────────────────────────────

def test_a_straight_line_is_labelled_trending():
    labels = label_regimes(_trending(400))
    known = [x for x in labels if x != UNKNOWN]
    assert known, "everything was unknown"
    assert all(x.startswith("trend") for x in known), set(known)


def test_noise_is_mostly_labelled_chop():
    labels = label_regimes(_choppy(400, seed=11))
    known = [x for x in labels if x != UNKNOWN]
    chop = sum(1 for x in known if x.startswith("chop"))
    assert chop / len(known) > 0.6, f"only {chop}/{len(known)} bars read as chop"


def test_efficiency_ratio_is_one_for_a_straight_line():
    er = efficiency_ratio(_trending(100)["close"]).dropna()
    assert er.max() == pytest.approx(1.0)
    assert er.min() > 0.99


def test_efficiency_ratio_is_low_for_a_round_trip():
    """Up then back down: large path, zero net displacement."""
    close = pd.Series(list(range(100, 140)) + list(range(140, 100, -1)), dtype=float)
    er = efficiency_ratio(close, window=20).dropna()
    assert er.min() < 0.2


def test_volatility_split_is_relative_to_the_instrument():
    """An absolute ATR% threshold would label every commodity 'high' and every
    index 'low' — the map would describe the universe, not the market state."""
    calm = label_regimes(_choppy(400, amp=0.2, seed=5))
    wild = label_regimes(_choppy(400, amp=20.0, seed=5))
    hi = lambda ls: sum(1 for x in ls if x.endswith("_hi"))  # noqa: E731
    # Both series must produce BOTH buckets; neither is globally "high vol".
    assert hi(calm) > 0 and hi(wild) > 0
    assert hi(calm) < sum(1 for x in calm if x != UNKNOWN)


# ── shape and safety ────────────────────────────────────────────────────────

def test_every_label_is_a_known_regime():
    labels = label_regimes(_choppy(300, seed=2))
    assert set(labels) <= set(REGIMES) | {UNKNOWN}


def test_an_empty_frame_is_not_an_error():
    assert len(label_regimes(pd.DataFrame())) == 0
    assert regime_distribution(pd.Series(dtype=object)) == {}


def test_a_flat_series_does_not_divide_by_zero():
    close = pd.Series([100.0] * 200)
    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close})
    labels = label_regimes(df)
    assert set(labels) <= set(REGIMES) | {UNKNOWN}


# ── the Phase-0 dependency ──────────────────────────────────────────────────

def test_regimes_inflate_the_trial_count():
    """Reporting the best of N regimes is N more chances to be lucky. This is
    exactly why Phase 0 had to land first: before deflation actually engaged,
    conditioning on regime would have been a machine for manufacturing
    regime-specific mirages."""
    labels = label_regimes(_choppy(600, seed=8))
    assert regime_trial_multiplier(labels) >= 2


def test_a_thin_regime_is_not_counted_as_a_trial():
    """A regime with three bars was never really a candidate."""
    labels = pd.Series(["trend_hi"] * 200 + ["chop_lo"] * 3)
    assert regime_trial_multiplier(labels, min_bars=30) == 1


def test_the_multiplier_is_never_zero():
    assert regime_trial_multiplier(pd.Series(dtype=object)) == 1


# ── trade bucketing ─────────────────────────────────────────────────────────

def test_trades_are_bucketed_by_the_regime_AT_ENTRY():
    """Entry, not exit: the regime a trade was opened in is the only one the
    entry decision could have conditioned on. Anything else grades the decision
    using information it did not have."""
    labels = pd.Series(["trend_hi"] * 10 + ["chop_lo"] * 10)

    class T:
        def __init__(self, i): self.i = i

    out = split_trades_by_regime([T(2), T(15)], labels, lambda t: t.i)
    assert len(out["trend_hi"]) == 1
    assert len(out["chop_lo"]) == 1


def test_an_unresolvable_trade_lands_in_unknown_rather_than_being_dropped():
    labels = pd.Series(["trend_hi"] * 5)

    class T:
        i = 999

    out = split_trades_by_regime([T()], labels, lambda t: t.i)
    assert len(out[UNKNOWN]) == 1
