"""
Reusable backtest cache. A sweep result is reusable when the *content* it would
recompute is identical: same instrument, interval, strategy/params signature,
schema version, and the same last completed candle. Then we copy the stored
metrics into the new run instead of re-simulating. SQLite stays the source of
truth; nothing here uses the browser or any external store.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select

from app.db.models import BacktestResult

# v2: return%/equity/CAGR switched from a flat ₹50k base to compounding return on
#     the position's own notional (leverage-free, comparable across instruments).
# v3: added smoothness metrics (calmar/consistency/streak/underwater) + a candle
#     window to the signature so different lookback ranges don't collide in cache.
# v4: honest sizing (affordable-lots, notional, affordable flag) + realised-vs-open
#     split + buy-and-hold benchmark + annualised Sharpe + worst-trade/MAE + true
#     per-cell span (first/last/effective_days/clamped). The stored metric shape
#     changed, so bump to force a clean recompute (no stale-row mixing).
SCHEMA_VERSION = 4


def params_signature(capital: float, *, ema_length: int = 50, z_length: int = 50,
                     entry_z: float = 1.0, slope_lookback: int = 5,
                     window: str = "") -> str:
    """Stable hash of everything that affects a backtest result other than the
    candle data itself. Changing any knob — including the requested date window —
    invalidates the cache so a 1-year run never reuses a 10-year run's metrics."""
    raw = (f"v{SCHEMA_VERSION}|cap={capital}|ema={ema_length}|z={z_length}"
           f"|ez={entry_z}|sl={slope_lookback}|win={window}")
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def find_reusable(session, key: str, interval: str, params_hash: str,
                  last_candle_ts: int) -> BacktestResult | None:
    """Most recent successful result with an identical content key, or None."""
    if last_candle_ts <= 0:
        return None
    q = (select(BacktestResult)
         .where(BacktestResult.instrument_key == key,
                BacktestResult.interval == interval,
                BacktestResult.params_hash == params_hash,
                BacktestResult.last_candle_ts == last_candle_ts,
                BacktestResult.schema_version == SCHEMA_VERSION,
                BacktestResult.error == "")
         .order_by(BacktestResult.id.desc()))
    return session.scalars(q).first()
