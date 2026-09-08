"""Formula-level variation: price source and smoothing kind as PARAMETERS.

Phase 2's core ask, and the owner's "modified-RSI" request generalised. Instead
of one RSI there is a family: RSI over close / hl2 / hlc3 / ohlc4, smoothed by
sma / ema / wilder / hull — sixteen lawful variants of a single block, all still
whitelisted, all still auditable down to `blocks.py`.

**They are encoded as bounded INTEGERS, not strings, and that is load-bearing.**
The emitted `compute` is AST-validated against a whitelist of block names with
numeric literal arguments only (`validate.py:53-54` rejects anything that is not
an int/float). A string parameter would have required opening that perimeter —
so the categorical is a small integer instead and the entire safety argument is
untouched. Out-of-range codes clamp rather than raise, because a generated
composition must never be able to crash the nightly with an arithmetic accident.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ir.contributors import generated_blocks as B


def _df(n=300, seed=0):
    rng = np.random.default_rng(seed)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, n)))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01 09:15", periods=n, freq="15min"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.uniform(1000, 5000, n),
    })


# ── price source ────────────────────────────────────────────────────────────

def test_every_price_source_code_resolves():
    df = _df()
    for code in range(len(B.PRICE_SOURCES)):
        s = B._source(df, code)
        assert len(s) == len(df)
        assert s.notna().all()


def test_source_zero_is_close_so_existing_behaviour_is_the_default():
    """Code 0 must be plain close: every block that gains a source parameter has
    to keep its current meaning at the default, or adding the parameter silently
    re-tunes strategies that already exist."""
    df = _df()
    pd.testing.assert_series_equal(B._source(df, 0), df["close"], check_names=False)


def test_the_sources_are_actually_different_formulas():
    df = _df()
    vals = [B._source(df, c).iloc[-1] for c in range(len(B.PRICE_SOURCES))]
    assert len(set(round(v, 9) for v in vals)) > 1


def test_hl2_is_the_midpoint():
    df = _df()
    expect = (df["high"] + df["low"]) / 2.0
    pd.testing.assert_series_equal(B._source(df, 1), expect, check_names=False)


def test_an_out_of_range_source_clamps_rather_than_raising():
    """A generated composition must never crash the nightly on an arithmetic
    accident. Clamping keeps it lawful and boring."""
    df = _df()
    assert B._source(df, 99).notna().all()
    assert B._source(df, -3).notna().all()


# ── smoothing kind ──────────────────────────────────────────────────────────

def test_every_smoothing_code_resolves():
    df = _df()
    for code in range(len(B.SMOOTHINGS)):
        s = B._smooth(df["close"], 14, code)
        assert len(s) == len(df)
        assert s.iloc[-1] == s.iloc[-1]      # not NaN at the end


def test_smoothings_are_distinct():
    df = _df()
    tails = [round(float(B._smooth(df["close"], 14, c).iloc[-1]), 6)
             for c in range(len(B.SMOOTHINGS))]
    assert len(set(tails)) >= 3, f"smoothing kinds collapsed to {tails}"


def test_ema_code_matches_the_shared_ema_helper():
    """The generated family must agree with the hand-written strategies' EMA
    convention (ewm adjust=False), not invent a second one."""
    df = _df()
    code = B.SMOOTHINGS.index("ema")
    pd.testing.assert_series_equal(B._smooth(df["close"], 20, code),
                                   B._ema(df["close"], 20), check_names=False)


def test_hull_reacts_faster_than_sma():
    """Sanity that hull is really hull: it is designed to cut lag."""
    df = _df(seed=3)
    sma = B._smooth(df["close"], 30, B.SMOOTHINGS.index("sma"))
    hull = B._smooth(df["close"], 30, B.SMOOTHINGS.index("hull"))
    close = df["close"]
    assert (hull - close).abs().tail(50).mean() < (sma - close).abs().tail(50).mean()


def test_an_out_of_range_smoothing_clamps():
    df = _df()
    assert B._smooth(df["close"], 14, 99).notna().any()


# ── RSI family ──────────────────────────────────────────────────────────────

def test_rsi_stays_within_zero_and_one_hundred():
    df = _df()
    for src in range(len(B.PRICE_SOURCES)):
        for sm in range(len(B.SMOOTHINGS)):
            r = B._rsi(df, 14, src, sm).dropna()
            assert r.between(0, 100).all(), f"RSI out of range for src={src} sm={sm}"


def test_rsi_blocks_return_clean_bools():
    """Warmup safety: a comparison against NaN must yield False, never NaN and
    never a spurious True — `&`/`|` composition depends on it."""
    df = _df()
    for fn in (B.rsi_gt, B.rsi_lt):
        out = fn(df, 14, 70.0, 0, 1)
        assert out.dtype == bool
        assert not out.isna().any()


def test_rsi_gt_and_lt_are_opposites_away_from_the_boundary():
    df = _df()
    hi = B.rsi_gt(df, 14, 55.0, 0, 1)
    lo = B.rsi_lt(df, 14, 55.0, 0, 1)
    assert not (hi & lo).any()


def test_changing_only_the_source_changes_the_signal():
    """The whole point: these are genuinely different strategies, not relabels."""
    df = _df(seed=7)
    a = B.rsi_gt(df, 14, 55.0, 0, 1)
    b = B.rsi_gt(df, 14, 55.0, 3, 1)
    assert not a.equals(b)


def test_changing_only_the_smoothing_changes_the_signal():
    df = _df(seed=7)
    a = B.rsi_gt(df, 14, 55.0, 0, 0)
    b = B.rsi_gt(df, 14, 55.0, 0, 3)
    assert not a.equals(b)


# ── the new plain blocks ────────────────────────────────────────────────────

@pytest.mark.parametrize("fn,args", [
    ("volume_surge", (20, 1.5)),
    ("gap_up_pct", (0.5,)),
    ("gap_down_pct", (0.5,)),
    ("body_frac_gt", (0.5,)),
])
def test_new_blocks_are_warmup_safe_clean_bools(fn, args):
    df = _df()
    out = getattr(B, fn)(df, *args)
    assert out.dtype == bool
    assert not out.isna().any()
    assert len(out) == len(df)


def test_volume_surge_fires_on_a_real_surge():
    df = _df()
    df.loc[df.index[-1], "volume"] = df["volume"].mean() * 20
    assert B.volume_surge(df, 20, 3.0).iloc[-1]


def test_volume_surge_is_false_when_volume_is_missing():
    """Not every instrument/feed carries volume. Absent volume must read as 'no
    surge', never as a signal — a missing column must not manufacture entries."""
    df = _df().drop(columns=["volume"])
    out = B.volume_surge(df, 20, 1.5)
    assert out.dtype == bool and not out.any()


def test_gap_blocks_are_mutually_exclusive():
    df = _df()
    assert not (B.gap_up_pct(df, 0.1) & B.gap_down_pct(df, 0.1)).any()


# ── registry integrity ──────────────────────────────────────────────────────

def test_every_new_block_is_registered_with_a_spec():
    for name in ("rsi_gt", "rsi_lt", "volume_surge", "gap_up_pct",
                 "gap_down_pct", "body_frac_gt"):
        assert name in B.BLOCKS, f"{name} is not in the whitelist"
        assert name in B.block_names()


def test_every_registered_block_runs_on_its_sample_args():
    """The registry's sample_args seed the search — a spec whose own sample
    crashes would take the nightly down."""
    df = _df()
    for name, spec in B.BLOCKS.items():
        out = spec.fn(df, *spec.sample_args)
        assert out.dtype == bool, f"{name} did not return bools"
        assert not out.isna().any(), f"{name} leaked NaN"


def test_choice_params_are_declared_as_choice_kind():
    """So the grammar bounds them as small integers rather than treating a source
    code as an unbounded length."""
    for name in ("rsi_gt", "rsi_lt"):
        kinds = dict(B.BLOCKS[name].params)
        assert kinds.get("source") == "choice"
        assert kinds.get("smooth") == "choice"
