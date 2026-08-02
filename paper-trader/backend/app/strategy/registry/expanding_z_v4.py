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


# ── the strategy's steps, named ───────────────────────────────────────────
#
# These were inline in `compute` until 2026-08-02. They are extracted, not
# rewritten: `compute` calls them in the same order with the same arguments, so
# behaviour is unchanged and the existing strategy and backtest tests are the
# regression protection.
#
# The reason they are named is that the Component IR needs kernels for
# `expanding_z_v4`, and a kernel that re-implements the expression beside the
# strategy would be two hand-written copies of one idea — the `candles.py`
# defect, which C12 exists because of. `app/ir/strategies/expanding_z.py` binds
# its kernels to *these* functions, so there is one implementation and the IR
# graph expresses the composition rather than duplicating the arithmetic.

def zscore(close: pd.Series, ema: pd.Series, z_length: int) -> pd.Series:
    spread = close - ema
    sd = spread.rolling(z_length).std(ddof=0)
    return pd.Series(np.where(sd > 0, spread / sd, 0.0), index=close.index)


def adaptive_threshold(abs_z: pd.Series, adapt_length: int, pct: float,
                       floor: float, fallback: float) -> pd.Series:
    """Pine's adaptive percentile, read off the *prior* bar.

    The `.shift(1)` is what keeps the current bar out of its own threshold.
    """
    raw = _percentile_nearest_rank(abs_z, adapt_length, pct)
    return pd.Series(np.maximum(raw.shift(1).fillna(fallback), floor),
                     index=abs_z.index)


def drift_score(ema: pd.Series, atr: pd.Series, slope_lookback: int) -> pd.Series:
    return pd.Series(
        np.where(atr > 0, (ema - ema.shift(slope_lookback)) / atr, 0.0),
        index=ema.index)


def range_in_atr(high: pd.Series, low: pd.Series, atr: pd.Series) -> pd.Series:
    return pd.Series(np.where(atr > 0, (high - low) / atr, 0.0), index=high.index)


def impulse(abs_z: pd.Series, entry_abs: pd.Series, require_expansion: bool,
            allow_reexpansion: bool) -> pd.Series:
    expanding = abs_z > abs_z.shift(1)
    breakout = _crossover(abs_z, entry_abs)
    reexpansion = ((abs_z > entry_abs) & (abs_z > abs_z.shift(1))
                   & (abs_z.shift(1) < abs_z.shift(2)))
    out = breakout | (reexpansion if allow_reexpansion else False)
    return out & expanding if require_expansion else out


def directional_entry(signal_bar_ok: pd.Series, impulse_now: pd.Series,
                      z: pd.Series, drift: pd.Series, min_drift_atr: float,
                      direction: str) -> pd.Series:
    if direction == "long":
        return signal_bar_ok & impulse_now & (z > 0) & (drift > min_drift_atr)
    return signal_bar_ok & impulse_now & (z < 0) & (drift < -min_drift_atr)


def displacement_lost(drift: pd.Series, close: pd.Series, ema: pd.Series,
                      abs_z: pd.Series, exit_abs: pd.Series, z: pd.Series,
                      direction: str, exit_on_drift_flip: bool,
                      exit_on_ema_cross: bool,
                      use_absz_contraction_exit: bool) -> pd.Series:
    long_side = direction == "long"
    out = pd.Series(False, index=close.index)
    if exit_on_drift_flip:
        out = out | (drift < 0 if long_side else drift > 0)
    if exit_on_ema_cross:
        out = out | (close < ema if long_side else close > ema)
    if use_absz_contraction_exit:
        out = out | ((abs_z < exit_abs) & (z > 0 if long_side else z < 0))
    return out


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
    # Pine risk engine defaults (expanding-z-impulse-v4.pine inputs, lines 98-104):
    # the backtest arbiter applies these; the .pine applies them natively in TV.
    risk_model = {
        "atr_length": 14, "initial_risk_atr": 1.25,
        "trail_start_r": 1.75, "trail_atr": 3.0,
        "use_mfe_capture_floor": True,
        "capture_start_r": 1.25, "capture_pct": 0.35,
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

        z = zscore(c, ema, z_length)
        absZ = z.abs()

        # prior-bar thresholds (Pine entryAbsRaw[1]) avoid current-bar contamination
        entry_abs = adaptive_threshold(absZ, adapt_length, entry_pct,
                                       floor=min_abs_z, fallback=min_abs_z)
        exit_abs = adaptive_threshold(absZ, adapt_length, exit_pct,
                                      floor=min_abs_z * 0.25, fallback=min_abs_z * 0.50)

        drift = drift_score(ema, atr, slope_lookback)
        signal_bar_ok = range_in_atr(high, low, atr) <= max_signal_atr

        # ── entry: adaptive impulse + mandatory still-expanding gate ──────────
        impulse_now = impulse(absZ, entry_abs, require_expansion, allow_reexpansion)
        long_entry = directional_entry(signal_bar_ok, impulse_now, z, drift,
                                       min_drift_atr, "long")
        short_entry = directional_entry(signal_bar_ok, impulse_now, z, drift,
                                        min_drift_atr, "short")

        # ── exits: displacement-lost set (engine owns the stop/trail) ─────────
        exit_flags = dict(exit_on_drift_flip=exit_on_drift_flip,
                          exit_on_ema_cross=exit_on_ema_cross,
                          use_absz_contraction_exit=use_absz_contraction_exit)
        long_exit = displacement_lost(drift, c, ema, absZ, exit_abs, z, "long",
                                      **exit_flags)
        short_exit = displacement_lost(drift, c, ema, absZ, exit_abs, z, "short",
                                       **exit_flags)

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
