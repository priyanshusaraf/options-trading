"""Technical market-regime classifier (OHLCV only, causal).

Labels every bar as one of:
  TREND      directional and efficient: ADX >= adx_trend AND efficiency ratio >= er_trend
  CHOP       two-sided and inefficient: ADX < adx_chop AND efficiency ratio < er_chop
  SQUEEZE    quiet / compressed: Bollinger bandwidth in the bottom `squeeze_pct` of its
             own trailing history (and not TREND)
  EXPANSION  volatility release: short ATR >= `expansion_ratio` x long ATR (and not TREND)
  NEUTRAL    none of the above
Priority when several apply: TREND > EXPANSION > SQUEEZE > CHOP > NEUTRAL.

It is a diagnostic and an assignment guide — which strategy to run on an
instrument, and how each strategy's trades split by the regime at entry. The
platform does not switch strategies per bar (no cross-strategy movement); each
strategy carries its own regime gate where the research found it useful.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.ta import atr, efficiency_ratio, rma

REGIMES = ("TREND", "EXPANSION", "SQUEEZE", "CHOP", "NEUTRAL")


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ADX (Pine ta.dmi semantics)."""
    h, lo, c = df["high"], df["low"], df["close"]
    up = h.diff()
    dn = -lo.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    pc = c.shift(1)
    tr = pd.concat([(h - lo), (h - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
    atr_n = rma(tr, n)
    pdi = 100 * rma(plus_dm, n) / atr_n
    mdi = 100 * rma(minus_dm, n) / atr_n
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return rma(dx.fillna(0.0), n)


def classify(df: pd.DataFrame, adx_len: int = 14, er_len: int = 20,
             adx_trend: float = 25.0, er_trend: float = 0.30,
             adx_chop: float = 20.0, er_chop: float = 0.20,
             bb_len: int = 20, squeeze_lookback: int = 250, squeeze_pct: float = 0.20,
             atr_short: int = 5, atr_long: int = 50, expansion_ratio: float = 1.4
             ) -> pd.DataFrame:
    """Return a frame with adx, er, bb_pctile, atr_ratio and a `regime` label."""
    c = df["close"]
    a = adx(df, adx_len)
    er = efficiency_ratio(c, er_len)
    sd = c.rolling(bb_len).std(ddof=0)
    bbw = sd / c.rolling(bb_len).mean()
    bb_pct = bbw.rolling(squeeze_lookback, min_periods=max(50, squeeze_lookback // 4)).rank(pct=True)
    ratio = atr(df, atr_short) / atr(df, atr_long)

    trend = (a >= adx_trend) & (er >= er_trend)
    expansion = ~trend & (ratio >= expansion_ratio)
    squeeze = ~trend & ~expansion & (bb_pct <= squeeze_pct)
    chop = ~trend & ~expansion & ~squeeze & (a < adx_chop) & (er < er_chop)
    label = np.select([trend, expansion, squeeze, chop],
                      ["TREND", "EXPANSION", "SQUEEZE", "CHOP"], default="NEUTRAL")
    label = pd.Series(label, index=df.index).where(a.notna() & er.notna(), "NEUTRAL")
    return pd.DataFrame({"adx": a, "er": er, "bb_pctile": bb_pct, "atr_ratio": ratio,
                         "regime": label})


def latest_regime(df: pd.DataFrame, **kw) -> dict:
    """Regime of the last bar plus the share of each regime over the last 250 bars
    (a quick 'what is this instrument doing lately' read for assignment)."""
    r = classify(df, **kw)
    tail = r["regime"].tail(250)
    share = {k: round(float((tail == k).mean()), 3) for k in REGIMES}
    last = r.iloc[-1]
    return {"regime": str(last["regime"]), "adx": float(last["adx"]),
            "er": float(last["er"]), "share_250": share}
