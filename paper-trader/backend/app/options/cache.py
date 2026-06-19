"""
Persistent option-data research cache.

Every option chain the engine downloads is appended to the `option_data` table —
throttled to one snapshot per instrument per cadence so the dataset grows without
exploding — building a local, reusable options history that survives restarts.
"""
from __future__ import annotations

import datetime as dt

from app.db.models import OptionData
from app.db.session import SessionLocal

_last_snapshot: dict[str, dt.datetime] = {}


def persist_chain(chain, inst, now: dt.datetime, snapshot_minutes: float) -> int:
    """Append `chain`'s quotes to OptionData, at most once per `snapshot_minutes`
    per instrument. Returns the number of rows written (0 if throttled)."""
    last = _last_snapshot.get(inst.key)
    if last is not None and (now - last).total_seconds() < snapshot_minutes * 60:
        return 0
    _last_snapshot[inst.key] = now
    rows = 0
    with SessionLocal() as s:
        for q in chain.quotes:
            s.add(OptionData(
                instrument_key=inst.key, ts=now, expiry=chain.expiry,
                strike=q.strike, option_type=q.option_type, tradingsymbol=q.tradingsymbol,
                spot=chain.spot, ltp=q.ltp, bid=q.bid, ask=q.ask,
                oi=q.oi, volume=q.volume, iv=q.iv, delta=q.delta))
            rows += 1
        s.commit()
    return rows


def stats() -> dict:
    """Summary of the accumulated dataset for the research/analytics view."""
    from sqlalchemy import func, select
    with SessionLocal() as s:
        total = s.scalar(select(func.count()).select_from(OptionData)) or 0
        instruments = s.scalar(select(func.count(func.distinct(OptionData.instrument_key)))) or 0
        first = s.scalar(select(func.min(OptionData.ts)))
        last = s.scalar(select(func.max(OptionData.ts)))
    return {
        "rows": total, "instruments": instruments,
        "first_ts": first.isoformat() if first else None,
        "last_ts": last.isoformat() if last else None,
    }
