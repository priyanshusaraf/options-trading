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


# ── conditioning: the generator can now say "only in this market" ───────────

def test_the_regime_block_selects_only_its_own_regime():
    from research.strategy.builder.blocks import regime_is
    df = _choppy(400, seed=4)
    labels = label_regimes(df)
    for code, name in enumerate(REGIMES):
        out = regime_is(df, code)
        assert out.dtype == bool
        assert (out == (labels == name)).all(), f"{name} block disagrees with the labeller"


def test_the_regime_blocks_partition_the_known_bars():
    """Every labelled bar belongs to exactly one regime, so the four blocks must
    be mutually exclusive and together cover everything that is not unknown."""
    from research.strategy.builder.blocks import regime_is
    df = _choppy(400, seed=6)
    labels = label_regimes(df)
    masks = [regime_is(df, c) for c in range(len(REGIMES))]
    total = sum(int(m.sum()) for m in masks)
    assert total == int((labels != UNKNOWN).sum())
    for i in range(len(masks)):
        for j in range(i + 1, len(masks)):
            assert not (masks[i] & masks[j]).any(), "regimes overlap"


def test_an_unreadable_frame_narrows_to_nothing_rather_than_removing_the_filter():
    """A broken filter must make the strategy trade LESS, never more. Returning
    all-True would silently delete the condition it was added to impose."""
    from research.strategy.builder.blocks import regime_is
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})     # no high/low columns
    out = regime_is(df, 0)
    assert out.dtype == bool and not out.any()


def test_the_sampler_reaches_regime_conditioning():
    from research.strategy.builder.search import sample_compositions
    found = [c for s in range(20) for c in sample_compositions(limit=8, seed=s)
             if "regime_is(" in str(c.to_dict())]
    assert found, "the generator never conditions on regime"


def test_choosing_a_regime_inflates_the_deflation_count():
    """The Phase-0 dependency, now wired. Picking WHICH of four regimes to
    condition on is a selection, and the DSR has to be told."""
    from research.orchestrator.generate import _regime_multiplier
    plain = {"longEntry": {"all": ["rsi_gt(14, 55.0, 0, 2)"]}}
    conditioned = {"longEntry": {"all": ["rsi_gt(14, 55.0, 0, 2)", "regime_is(0)"]}}
    assert _regime_multiplier(plain) == 1
    assert _regime_multiplier(conditioned) == len(REGIMES)


def test_the_multiplier_keys_on_USE_not_availability():
    """Inflating every candidate because regime blocks exist would deflate ideas
    that never made that choice."""
    from research.orchestrator.generate import _regime_multiplier
    assert _regime_multiplier({"longEntry": {"all": ["roc_gt(10, 0.0)"]}}) == 1
