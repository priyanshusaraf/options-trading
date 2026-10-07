"""Shared technical-analysis primitives for registry strategies.

Pine-parity conventions (same as signals.py / expanding_z_v4.py):
  * ta.rma    -> ewm(alpha=1/n, adjust=False)
  * ta.atr    -> Wilder RMA of True Range
  * ta.rsi    -> Wilder RSI
  * ta.stdev  -> POPULATION stdev (ddof=0)

Session helpers assume the candle `date` column is IST wall-clock (how every
provider in this platform delivers candles) and that one calendar date == one
trading session (true for NSE and MCX: MCX closes 23:30/23:55 IST, same day).
Everything here is causal: the value on bar i uses bars <= i only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat([(df["high"] - df["low"]).abs(),
                      (df["high"] - pc).abs(),
                      (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return rma(true_range(df), n)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = rma(d.clip(lower=0), n)
    dn = rma((-d).clip(lower=0), n)
    rs = up / dn.replace(0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    # all-up window (dn == 0) -> RSI 100, Pine behaviour
    return out.where(dn != 0, 100.0).where(up.notna())


def session_key(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["date"]).dt.date


def session_bar_no(df: pd.DataFrame) -> pd.Series:
    """0 for the first bar of each session, 1 for the next, …"""
    return df.groupby(session_key(df)).cumcount()


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP of the typical price (resets at each session open,
    like Kite's VWAP). Bars with zero/absent volume get a tiny weight so the
    VWAP degrades to an average price instead of dividing by zero."""
    key = session_key(df)
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    v = df["volume"] if "volume" in df.columns else pd.Series(0.0, index=df.index)
    v = v.fillna(0.0).clip(lower=0.0) + 1e-9
    return (tp * v).groupby(key).cumsum() / v.groupby(key).cumsum()


def rolling_vwap(df: pd.DataFrame, n: int) -> pd.Series:
    """Rolling VWAP of the typical price over the last n bars (crosses sessions,
    so its slope stays continuous overnight — useful for multi-day holds)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    v = df["volume"] if "volume" in df.columns else pd.Series(0.0, index=df.index)
    v = v.fillna(0.0).clip(lower=0.0) + 1e-9
    return (tp * v).rolling(n, min_periods=n).sum() / v.rolling(n, min_periods=n).sum()


def session_vwap_sd(df: pd.DataFrame, vwap: pd.Series) -> pd.Series:
    """Volume-weighted standard deviation of the typical price around the
    session VWAP (the classic VWAP-band sigma)."""
    key = session_key(df)
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    v = df["volume"] if "volume" in df.columns else pd.Series(0.0, index=df.index)
    v = v.fillna(0.0).clip(lower=0.0) + 1e-9
    ex2 = (tp * tp * v).groupby(key).cumsum() / v.groupby(key).cumsum()
    return np.sqrt((ex2 - vwap * vwap).clip(lower=0.0))


def efficiency_ratio(close: pd.Series, n: int = 20) -> pd.Series:
    """Kaufman efficiency ratio: |net move| / path length over n bars (0 = pure
    chop, 1 = straight line)."""
    path = close.diff().abs().rolling(n).sum()
    return (close - close.shift(n)).abs() / path.replace(0, np.nan)


def minutes_of_day(df: pd.DataFrame) -> pd.Series:
    d = pd.to_datetime(df["date"])
    return d.dt.hour * 60 + d.dt.minute


def rsi_divergence(low: np.ndarray, high: np.ndarray, r: np.ndarray, lookback: int = 20,
                   min_gap: int = 3, min_rsi_delta: float = 3.0,
                   os_level: float = 40.0, ob_level: float = 60.0
                   ) -> tuple[np.ndarray, np.ndarray]:
    """No-lag RSI divergence on the CURRENT bar (no pivot confirmation delay).

    bullish[i]: bar i prints a new low below the lowest low of [i-lookback, i-min_gap]
                while RSI(i) is at least `min_rsi_delta` above the RSI at that prior
                low, and the prior low was in weak territory (RSI < os_level).
    bearish[i]: mirror on highs (prior high RSI > ob_level, RSI now lower).
    """
    n = len(low)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    for i in range(lookback, n):
        w0 = i - lookback
        w1 = i - min_gap + 1
        if w1 <= w0 or np.isnan(r[i]):
            continue
        jl = w0 + int(np.argmin(low[w0:w1]))
        jh = w0 + int(np.argmax(high[w0:w1]))
        if low[i] < low[jl] and not np.isnan(r[jl]) and r[jl] < os_level \
                and r[i] > r[jl] + min_rsi_delta:
            bull[i] = True
        if high[i] > high[jh] and not np.isnan(r[jh]) and r[jh] > ob_level \
                and r[i] < r[jh] - min_rsi_delta:
            bear[i] = True
    return bull, bear


def mcx_close_minute(df: pd.DataFrame) -> pd.Series:
    """MCX evening-session close in IST minutes-of-day for each bar's date:
    23:30 (1410) while New York is on daylight time, 23:55 (1435) otherwise —
    MCX moves its close with the US DST switch."""
    d = pd.to_datetime(df["date"])
    days = d.dt.normalize()
    uniq = pd.DatetimeIndex(days.unique())
    noon = (uniq + pd.Timedelta(hours=12)).tz_localize("America/New_York",
                                                       nonexistent="shift_forward",
                                                       ambiguous=False)
    dst = pd.Series([bool(t.dst()) for t in noon], index=uniq)
    return pd.Series(np.where(days.map(dst).to_numpy(), 1410, 1435), index=df.index)


def bar_minutes(df: pd.DataFrame) -> int:
    """The candle interval in minutes (median spacing of consecutive bars)."""
    d = pd.to_datetime(df["date"])
    if len(d) < 3:
        return 15
    m = d.diff().dt.total_seconds().div(60).dropna()
    m = m[m > 0]
    return int(m.median()) if len(m) else 15


def bars_to_session_close(df: pd.DataFrame, close_minute: pd.Series | int | None = None
                          ) -> pd.Series:
    """How many bars come AFTER this one before the session close, from the
    exchange schedule (no look-ahead): 0 = this is the last bar of the session,
    1 = second-to-last, … Uses the MCX close unless `close_minute` is given."""
    tf = bar_minutes(df)
    cm = mcx_close_minute(df) if close_minute is None else close_minute
    end = minutes_of_day(df) + tf
    gap = pd.Series(cm, index=df.index) - end
    return np.ceil(gap.clip(lower=0) / tf).astype(int)   # a partial last bar still counts
