"""
Volatility engine — measurement layer for the options recommender.

Jobs:
  1. Estimate REALIZED volatility from OHLC bars (better than naive close-to-close).
  2. Contextualise IMPLIED vol vs its own history (IV rank / percentile) and vs
     realized vol (the IV/RV ratio) — the core "is premium cheap or rich" signal.

Dependency-light (numpy/pandas only) so it is portable and unit-testable.
All vols are ANNUALISED. RV = physical-measure (real outcomes); IV = priced.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _safe_log_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(a / b)
    return r[np.isfinite(r)]


def close_to_close_vol(close: Sequence[float], window: int = 20) -> float:
    c = np.asarray(close, dtype=float)
    c = c[np.isfinite(c) & (c > 0)]
    if len(c) < window + 1:
        window = max(2, len(c) - 1)
    rets = _safe_log_ratio(c[1:], c[:-1])[-window:]
    if len(rets) < 2:
        return float("nan")
    return float(np.std(rets, ddof=1) * math.sqrt(TRADING_DAYS))


def parkinson_vol(high: Sequence[float], low: Sequence[float], window: int = 20) -> float:
    h = np.asarray(high, dtype=float); l = np.asarray(low, dtype=float)
    hl = _safe_log_ratio(h, l)[-window:]
    if len(hl) < 2:
        return float("nan")
    daily_var = (1.0 / (4.0 * math.log(2.0))) * np.mean(hl ** 2)
    return float(math.sqrt(daily_var * TRADING_DAYS))


def garman_klass_vol(open_, high, low, close, window: int = 20) -> float:
    o = np.asarray(open_, dtype=float)[-window:]; h = np.asarray(high, dtype=float)[-window:]
    l = np.asarray(low, dtype=float)[-window:]; c = np.asarray(close, dtype=float)[-window:]
    n = min(len(o), len(h), len(l), len(c))
    if n < 2:
        return float("nan")
    o, h, l, c = o[-n:], h[-n:], l[-n:], c[-n:]
    hl = np.log(h / l); co = np.log(c / o)
    daily_var = np.mean(0.5 * hl ** 2 - (2 * math.log(2) - 1) * co ** 2)
    return float(math.sqrt(max(daily_var, 0.0) * TRADING_DAYS))


def yang_zhang_vol(open_, high, low, close, window: int = 20) -> float:
    o = np.asarray(open_, dtype=float); h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float); c = np.asarray(close, dtype=float)
    n = min(len(o), len(h), len(l), len(c))
    if n < window + 1:
        window = max(2, n - 1)
    o, h, l, c = o[-(window + 1):], h[-(window + 1):], l[-(window + 1):], c[-(window + 1):]
    if len(c) < 3:
        return float("nan")
    log_oc = np.log(o[1:] / c[:-1])      # overnight
    log_co = np.log(c[1:] / o[1:])       # open->close
    ho = np.log(h[1:] / o[1:]); lo = np.log(l[1:] / o[1:]); cc = np.log(c[1:] / o[1:])
    rs = ho * (ho - cc) + lo * (lo - cc)
    k = 0.34 / (1.34 + (len(log_oc) + 1) / (len(log_oc) - 1))
    var_o = np.var(log_oc, ddof=1); var_c = np.var(log_co, ddof=1); var_rs = np.mean(rs)
    yz = var_o + k * var_c + (1 - k) * var_rs
    return float(math.sqrt(max(yz, 0.0) * TRADING_DAYS))


def ewma_vol(close: Sequence[float], lam: float = 0.94) -> float:
    c = np.asarray(close, dtype=float)
    c = c[np.isfinite(c) & (c > 0)]
    rets = _safe_log_ratio(c[1:], c[:-1])
    if len(rets) < 2:
        return float("nan")
    var = rets[0] ** 2
    for r in rets[1:]:
        var = lam * var + (1 - lam) * r ** 2
    return float(math.sqrt(var * TRADING_DAYS))


@dataclass
class RealizedVol:
    close_to_close: float
    parkinson: float
    garman_klass: float
    yang_zhang: float
    ewma: float
    blended: float
    window: int

    def as_dict(self) -> dict:
        out = {}
        for k, v in self.__dict__.items():
            if isinstance(v, float):
                out[k] = round(v, 4) if math.isfinite(v) else None
            else:
                out[k] = v
        return out


def realized_vol(df: pd.DataFrame, window: int = 20) -> RealizedVol:
    cols = {c.lower(): c for c in df.columns}
    def col(name):
        return df[cols[name]].to_numpy(dtype=float) if name in cols else None
    close = col("close")
    nan = float("nan")
    if close is None or len(close) < 3:
        return RealizedVol(nan, nan, nan, nan, nan, nan, window)
    o, h, l = col("open"), col("high"), col("low")
    ctc = close_to_close_vol(close, window)
    ewm = ewma_vol(close)
    have_ohlc = o is not None and h is not None and l is not None
    park = parkinson_vol(h, l, window) if (h is not None and l is not None) else nan
    gk = garman_klass_vol(o, h, l, close, window) if have_ohlc else nan
    yz = yang_zhang_vol(o, h, l, close, window) if have_ohlc else nan
    structural = next((v for v in (yz, gk, park, ctc) if math.isfinite(v)), ctc)
    blended = (0.6 * structural + 0.4 * ewm) if math.isfinite(ewm) else structural
    return RealizedVol(ctc, park, gk, yz, ewm, blended, window)


@dataclass
class IVContext:
    current_iv: float
    iv_rank: Optional[float]
    iv_percentile: Optional[float]
    realized_vol: float
    iv_rv_ratio: Optional[float]
    regime: str          # CHEAP / FAIR / RICH / UNKNOWN
    note: str

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        for k in ("current_iv", "iv_rank", "iv_percentile", "realized_vol", "iv_rv_ratio"):
            if isinstance(d[k], float) and math.isfinite(d[k]):
                d[k] = round(d[k], 4)
        return d


def iv_rank(current_iv: float, history: Sequence[float]) -> Optional[float]:
    h = np.asarray([x for x in history if x is not None and math.isfinite(x)], dtype=float)
    if len(h) < 2:
        return None
    lo, hi = float(h.min()), float(h.max())
    if hi - lo < 1e-9:
        return 50.0
    return float(np.clip((current_iv - lo) / (hi - lo) * 100, 0, 100))


def iv_percentile(current_iv: float, history: Sequence[float]) -> Optional[float]:
    h = np.asarray([x for x in history if x is not None and math.isfinite(x)], dtype=float)
    if len(h) < 2:
        return None
    return float((h < current_iv).mean() * 100)


def classify_iv_regime(current_iv, rv, rank, iv_rv_ratio) -> tuple[str, str]:
    votes_rich = votes_cheap = 0
    reasons = []
    if iv_rv_ratio is not None and math.isfinite(iv_rv_ratio):
        if iv_rv_ratio >= 1.25:
            votes_rich += 1; reasons.append(f"IV {iv_rv_ratio:.2f}x realized (options pricing more than the stock delivers)")
        elif iv_rv_ratio <= 0.95:
            votes_cheap += 1; reasons.append(f"IV only {iv_rv_ratio:.2f}x realized (cheap vs actual movement)")
    if rank is not None:
        if rank >= 60:
            votes_rich += 1; reasons.append(f"IV rank {rank:.0f} (high in 1y range)")
        elif rank <= 35:
            votes_cheap += 1; reasons.append(f"IV rank {rank:.0f} (low in 1y range)")
    if votes_rich > votes_cheap:
        return "RICH", "; ".join(reasons)
    if votes_cheap > votes_rich:
        return "CHEAP", "; ".join(reasons)
    if rank is None and (iv_rv_ratio is None or not math.isfinite(iv_rv_ratio)):
        return "UNKNOWN", "insufficient IV history to contextualise"
    return "FAIR", "; ".join(reasons) or "IV in line with realized vol and its own history"


def iv_context(current_iv: float, rv: float, iv_history: Sequence[float]) -> IVContext:
    rank = iv_rank(current_iv, iv_history)
    pct = iv_percentile(current_iv, iv_history)
    ratio = (current_iv / rv) if (rv and math.isfinite(rv) and rv > 0) else None
    regime, note = classify_iv_regime(current_iv, rv, rank, ratio)
    return IVContext(current_iv, rank, pct, rv, ratio, regime, note)


class IVHistoryStore:
    """Persist daily ATM IV per symbol (Kite/NSE don't serve historical IV)."""
    def __init__(self, db_path: str | Path = "data/sqlite/iv_history.db"):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as cx:
            cx.execute("""CREATE TABLE IF NOT EXISTS iv_history (
                symbol TEXT NOT NULL, asof TEXT NOT NULL, atm_iv REAL NOT NULL,
                PRIMARY KEY (symbol, asof))""")

    def record(self, symbol: str, atm_iv: float, asof: Optional[date] = None):
        if atm_iv is None or not math.isfinite(atm_iv):
            return
        asof = (asof or date.today()).isoformat()
        with sqlite3.connect(self.path) as cx:
            cx.execute("INSERT OR REPLACE INTO iv_history(symbol, asof, atm_iv) VALUES (?,?,?)",
                       (symbol.upper(), asof, float(atm_iv)))

    def history(self, symbol: str, lookback_days: int = 252) -> list[float]:
        with sqlite3.connect(self.path) as cx:
            rows = cx.execute(
                "SELECT atm_iv FROM iv_history WHERE symbol=? ORDER BY asof DESC LIMIT ?",
                (symbol.upper(), lookback_days)).fetchall()
        return [r[0] for r in rows]
