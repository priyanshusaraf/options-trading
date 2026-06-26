"""Expanding Z Impulse V4 — Python port of the *signal half* of
strategies/expanding-z-impulse-v4.pine.

Lineage (kept in the .pine header too): the AbsZ adaptive-percentile impulse +
ATR-drift direction + the mandatory V3 "still-expanding" entry gate, with exits =
the displacement-lost set (EMA cross ≡ z<0, and EMA-drift flip). The Pine risk
engine (initial ATR stop → Chandelier trail → MFE-capture floor) is intentionally
NOT ported here: the live engine already owns the stop/target/trail layer, and the
backtest measures the raw signal edge. A strategy only decides direction + when its
edge has expired.

Pine→pandas parity:
  * ta.ema      -> ewm(span, adjust=False)          (same as signals.py)
  * ta.stdev    -> rolling(z).std(ddof=0)           (POPULATION stdev)
  * ta.atr      -> Wilder RMA of True Range (ewm alpha=1/n, adjust=False)
  * ta.crossover(a,b) -> a[1] < b[1] and a > b       (same convention as signals.py)
  * ta.percentile_nearest_rank(s, len, p) -> nearest-rank over the last `len` bars
  * prior-bar thresholds (entryAbs/exitAbs use [1]) replicated via .shift(1)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


def _rma(s: pd.Series, n: int) -> pd.Series:
    # Wilder's moving average (Pine ta.rma): recursive 1/n smoothing.
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return _rma(tr, n)


def _crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    return ((a.shift(1) < b.shift(1)) & (a > b)).fillna(False)


def _percentile_nearest_rank(s: pd.Series, length: int, pct: float) -> pd.Series:
    """Nearest-rank percentile over a trailing window of `length` bars. NaN values
    inside the warmup window are dropped so the early transition bars stay sane;
    once the window is fully populated this is exactly Pine's definition."""
    def f(w: np.ndarray) -> float:
        w = w[~np.isnan(w)]
        n = len(w)
        if n == 0:
            return np.nan
        arr = np.sort(w)
        rank = int(np.ceil(pct / 100.0 * n))
        rank = min(max(rank, 1), n)
        return float(arr[rank - 1])
    return s.rolling(length, min_periods=length).apply(f, raw=True)


def _as_bool(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


class ExpandingZImpulseV4(Strategy):
    key = "expanding_z_v4"
    display_name = "Expanding Z Impulse V4"
    default_params = {
        "ema_length": 50, "z_length": 50, "adapt_length": 200, "atr_length": 14,
        "slope_lookback": 5, "entry_pct": 65.0, "exit_pct": 35.0,
        "min_abs_z": 0.60, "min_drift_atr": 0.08, "max_signal_atr": 2.75,
        "require_expansion": True, "allow_reexpansion": True,
        "use_absz_contraction_exit": False,
        "exit_on_drift_flip": True, "exit_on_ema_cross": True,
    }

    def compute(self, df: pd.DataFrame, ema_length: int = 50, z_length: int = 50,
                adapt_length: int = 200, atr_length: int = 14, slope_lookback: int = 5,
                entry_pct: float = 65.0, exit_pct: float = 35.0, min_abs_z: float = 0.60,
                min_drift_atr: float = 0.08, max_signal_atr: float = 2.75,
                require_expansion: bool = True, allow_reexpansion: bool = True,
                use_absz_contraction_exit: bool = False, exit_on_drift_flip: bool = True,
                exit_on_ema_cross: bool = True) -> pd.DataFrame:
        out = df.copy()
        c, high, low = out["close"], out["high"], out["low"]

        ema = c.ewm(span=ema_length, adjust=False).mean()
        atr = _atr(high, low, c, atr_length)

        spread = c - ema
        sd = spread.rolling(z_length).std(ddof=0)
        z = pd.Series(np.where(sd > 0, spread / sd, 0.0), index=out.index)
        absZ = z.abs()

        entry_raw = _percentile_nearest_rank(absZ, adapt_length, entry_pct)
        exit_raw = _percentile_nearest_rank(absZ, adapt_length, exit_pct)
        # prior-bar thresholds (Pine entryAbsRaw[1]) avoid current-bar contamination
        entry_abs = np.maximum(entry_raw.shift(1).fillna(min_abs_z), min_abs_z)
        exit_abs = np.maximum(exit_raw.shift(1).fillna(min_abs_z * 0.50), min_abs_z * 0.25)
        entry_abs = pd.Series(entry_abs, index=out.index)
        exit_abs = pd.Series(exit_abs, index=out.index)

        drift = pd.Series(np.where(atr > 0, (ema - ema.shift(slope_lookback)) / atr, 0.0),
                          index=out.index)
        bull_drift = drift > min_drift_atr
        bear_drift = drift < -min_drift_atr

        range_atr = pd.Series(np.where(atr > 0, (high - low) / atr, 0.0), index=out.index)
        signal_bar_ok = range_atr <= max_signal_atr

        # ── entry: adaptive impulse + mandatory still-expanding gate ──────────
        expanding = absZ > absZ.shift(1)
        breakout = _crossover(absZ, entry_abs)
        reexpansion = ((absZ > entry_abs) & (absZ > absZ.shift(1))
                       & (absZ.shift(1) < absZ.shift(2)))
        impulse = breakout | (reexpansion if allow_reexpansion else False)
        if require_expansion:
            impulse = impulse & expanding

        long_entry = signal_bar_ok & impulse & (z > 0) & bull_drift
        short_entry = signal_bar_ok & impulse & (z < 0) & bear_drift

        # ── exits: displacement-lost set (engine owns the stop/trail) ─────────
        long_exit = pd.Series(False, index=out.index)
        short_exit = pd.Series(False, index=out.index)
        if exit_on_drift_flip:
            long_exit = long_exit | (drift < 0)
            short_exit = short_exit | (drift > 0)
        if exit_on_ema_cross:
            long_exit = long_exit | (c < ema)
            short_exit = short_exit | (c > ema)
        if use_absz_contraction_exit:
            long_exit = long_exit | ((absZ < exit_abs) & (z > 0))
            short_exit = short_exit | ((absZ < exit_abs) & (z < 0))

        out["ema"] = ema
        out["atr"] = atr
        out["z"] = z
        out["absZ"] = absZ
        out["entryAbs"] = entry_abs
        out["exitAbs"] = exit_abs
        out["driftScore"] = drift
        out["longEntry"] = _as_bool(long_entry)
        out["shortEntry"] = _as_bool(short_entry)
        out["longExit"] = _as_bool(long_exit)
        out["shortExit"] = _as_bool(short_exit)
        return out


STRATEGY = ExpandingZImpulseV4()
