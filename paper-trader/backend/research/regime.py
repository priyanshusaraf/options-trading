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

import numpy as np
import pandas as pd

# Trend vs chop is decided by the EFFICIENCY RATIO (Kaufman): net displacement
# over the window divided by the total path walked. 1.0 = a straight line,
# ~0 = the price went nowhere loudly. It is chosen over ADX because it is a
# single bounded number with no smoothing constants to tune, so the labels are
# reproducible rather than parameter-sensitive.
TREND_WINDOW = 20
TREND_CUTOFF = 0.35

# Volatility buckets are RELATIVE to the instrument's own history: an absolute
# ATR% threshold would label every commodity "high" and every index "low", and
# the resulting map would describe the universe rather than the market state.
VOL_WINDOW = 20
VOL_LOOKBACK = 200

REGIMES = ("trend_hi", "trend_lo", "chop_hi", "chop_lo")
UNKNOWN = "unknown"


def efficiency_ratio(close: pd.Series, window: int = TREND_WINDOW) -> pd.Series:
    """Net move / total path over `window`. NaN during warmup, never 0.0 —
    a warmup bar is UNKNOWN, and calling it 0 would label it 'chop'."""
    net = (close - close.shift(window)).abs()
    path = close.diff().abs().rolling(window).sum()
    return net / path.replace(0.0, np.nan)


def atr_pct(df: pd.DataFrame, window: int = VOL_WINDOW) -> pd.Series:
    """True range as a percentage of close, smoothed. Backward-looking only."""
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev).abs(), (low - prev).abs()],
                   axis=1).max(axis=1)
    return (tr.rolling(window).mean() / close.replace(0.0, np.nan)) * 100.0


def label_regimes(df: pd.DataFrame, *, trend_window: int = TREND_WINDOW,
                  trend_cutoff: float = TREND_CUTOFF,
                  vol_window: int = VOL_WINDOW,
                  vol_lookback: int = VOL_LOOKBACK) -> pd.Series:
    """One label per bar: trend_hi | trend_lo | chop_hi | chop_lo | unknown.

    The volatility split uses an EXPANDING median of the instrument's own ATR%,
    not a full-series quantile. A full-series quantile would be computed with
    future bars visible and would leak: bar 10's label would depend on bar 900's
    volatility. Expanding keeps every label a function of the past alone, which
    is the whole reason these labels can be used in an experiment at all.
    """
    if df is None or len(df) == 0:
        return pd.Series(dtype=object)
    er = efficiency_ratio(df["close"], trend_window)
    vol = atr_pct(df, vol_window)
    # min_periods keeps the early bars UNKNOWN rather than comparing against a
    # median of two observations.
    med = vol.expanding(min_periods=max(2, vol_lookback // 10)).median()

    trending = er >= trend_cutoff
    high_vol = vol >= med
    known = er.notna() & vol.notna() & med.notna()

    out = np.where(
        trending,
        np.where(high_vol, "trend_hi", "trend_lo"),
        np.where(high_vol, "chop_hi", "chop_lo"),
    )
    return pd.Series(np.where(known, out, UNKNOWN), index=df.index, dtype=object)


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
