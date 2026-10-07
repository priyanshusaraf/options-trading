"""Feature library for component analysis (vectorised, no look-ahead)."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import numpy as np
import pandas as pd


def rma(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def atr(df, n=14):
    pc = df.close.shift(1)
    tr = pd.concat([(df.high - df.low), (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def rsi(c, n=14):
    d = c.diff()
    up = rma(d.clip(lower=0), n)
    dn = rma((-d).clip(lower=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def session_vwap(df):
    day = df.index.date
    tp = (df.high + df.low + df.close) / 3
    v = df.volume.clip(lower=1e-9)
    pv = (tp * v).groupby(day).cumsum()
    vv = v.groupby(day).cumsum()
    return pv / vv


def session_bar_no(df):
    return df.groupby(df.index.date).cumcount()


def efficiency_ratio(c, n=20):
    return (c - c.shift(n)).abs() / c.diff().abs().rolling(n).sum()


def build(df):
    f = pd.DataFrame(index=df.index)
    a = atr(df)
    f["atr"] = a
    vw = session_vwap(df)
    bn = session_bar_no(df)
    f["bar_no"] = bn
    f["vwap"] = vw
    f["vslope10"] = np.where(bn >= 10, (vw - vw.shift(10)) / a, np.nan)
    f["vslope5"] = np.where(bn >= 5, (vw - vw.shift(5)) / a, np.nan)
    f["vdist"] = (df.close - vw) / a
    ema50 = df.close.ewm(span=50, adjust=False).mean()
    f["eslope"] = (ema50 - ema50.shift(5)) / a
    f["r"] = rsi(df.close)
    f["er20"] = efficiency_ratio(df.close, 20)
    f["mom4"] = (df.close - df.close.shift(4)) / a
    f["mom16"] = (df.close - df.close.shift(16)) / a
    body = (df.close - df.open) / a
    f["body"] = body
    rng = (df.high - df.low) / a
    f["range"] = rng
    # close location in bar (0 = low, 1 = high)
    f["clv"] = (df.close - df.low) / (df.high - df.low).replace(0, np.nan)
    # relative volume vs same bar-of-session over last 20 sessions
    v = df.volume
    key = bn
    rv = v / v.groupby(key).transform(lambda s: s.shift(1).rolling(20, min_periods=5).mean())
    f["rvol"] = rv
    # divergence (no-lag variant): new N-bar low with RSI above RSI at prior low
    N = 20
    ll = df.low.rolling(N).min()
    newlow = df.low <= ll
    prior_low_idx = df.low.shift(3).rolling(N - 3).apply(np.argmin, raw=True)
    # RSI at prior low position
    rv_arr = f["r"].to_numpy()
    lows = df.low.to_numpy()
    n = len(df)
    bull_div = np.zeros(n, bool)
    bear_div = np.zeros(n, bool)
    hi = df.high.to_numpy()
    for i in range(N, n):
        w0 = i - N
        # prior swing low/high in [i-N, i-3]
        seg_l = lows[w0:i - 2]
        seg_h = hi[w0:i - 2]
        jl = w0 + int(np.argmin(seg_l))
        jh = w0 + int(np.argmax(seg_h))
        if lows[i] < lows[jl] and rv_arr[i] > rv_arr[jl] + 3 and rv_arr[jl] < 40:
            bull_div[i] = True
        if hi[i] > hi[jh] and rv_arr[i] < rv_arr[jh] - 3 and rv_arr[jh] > 60:
            bear_div[i] = True
    f["bull_div"] = bull_div
    f["bear_div"] = bear_div
    # bollinger bandwidth percentile (squeeze)
    sd = df.close.rolling(20).std(ddof=0)
    bw = sd / df.close.rolling(20).mean()
    f["bw_pct"] = bw.rolling(500, min_periods=200).rank(pct=True)
    f["tod"] = df.index.hour + df.index.minute / 60
    return f


def fwd(df, h):
    """forward return in bps from NEXT bar open to close of bar i+h, same session only"""
    day = pd.Series(df.index.date, index=df.index)
    nxt_open = df.open.shift(-1)
    fut_close = df.close.shift(-h)
    same = day.shift(-h) == day
    r = (fut_close / nxt_open - 1) * 1e4
    return r.where(same)
