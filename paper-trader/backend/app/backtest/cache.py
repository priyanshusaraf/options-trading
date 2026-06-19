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

SCHEMA_VERSION = 1


def params_signature(capital: float, *, ema_length: int = 50, z_length: int = 50,
                     entry_z: float = 1.0, slope_lookback: int = 5) -> str:
    """Stable hash of everything that affects a backtest result other than the
    candle data itself. Changing any knob invalidates the cache."""
    raw = (f"v{SCHEMA_VERSION}|cap={capital}|ema={ema_length}|z={z_length}"
           f"|ez={entry_z}|sl={slope_lookback}")
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
