"""Persistence for L1 Stage 1 shadow disagreements. Telemetry only.

Three properties matter more than anything this module does:

1. **Its own session.** `EngineRunner` holds one shared SQLAlchemy session under a lock
   across both lanes; a failed write on that session leaves it needing a rollback before
   the authoritative path can use it again (H3). So the shadow writes through
   `SessionLocal()` and closes it, and a shadow database failure is invisible to the lane
   that trades.
2. **It cannot raise.** Every entry point returns a value and logs; none propagates.
3. **It writes disagreements only.** Agreement is counted in memory, not stored.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import delete, select

from app.core.logging import log
from app.db.models import IrShadowDivergence
from app.db.session import SessionLocal
from app.engine.ir_shadow import AGREEMENT, ShadowObservation


def _flags_json(flags: dict[str, bool] | None) -> str | None:
    """`None` stays NULL: "the graph refused" is not "the graph said false"."""
    return None if flags is None else json.dumps(flags, sort_keys=True)


def _naive(value: dt.datetime | None) -> dt.datetime | None:
    """Bar timestamps arrive tz-aware from the candle frame; every other DateTime column
    in this schema is naive local time. Store them the same way rather than mixing."""
    if value is None or value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def record(observation: ShadowObservation, *, market_open: bool, owner_id: str,
           broker_account_id: str) -> bool:
    """Persist one disagreement. Returns True only when a row was written.

    False means "nothing to write" (the lanes agreed), "already written" (the same
    completed bar is re-scanned every 2.5 s), or "the write failed" — all three are
    non-events for the caller, which must carry on either way.
    """
    if observation is None or observation.reason == AGREEMENT:
        return False
    try:
        with SessionLocal() as session:
            row = IrShadowDivergence(
                owner_id=owner_id, broker_account_id=broker_account_id,
                observed_at=_naive(observation.observed_at),
                bar_time=_naive(observation.bar_time),
                instrument_key=observation.instrument_key,
                authoritative_strategy_key=observation.authoritative_strategy_key,
                shadow_strategy_key=observation.shadow_strategy_key,
                graph_address=observation.graph_address,
                authoritative_json=_flags_json(observation.authoritative),
                ir_json=_flags_json(observation.ir),
                warmup_state=observation.warmup_state,
                declared_warmup=observation.declared_warmup,
                frame_id=observation.frame_id,
                frame_bars=observation.frame_bars,
                frame_first_ts=_naive(observation.frame_first_ts),
                frame_last_ts=_naive(observation.frame_last_ts),
                reason=observation.reason,
                detail=observation.detail,
                eval_ms=round(observation.eval_seconds * 1000.0, 3),
                market_open=bool(market_open),
            )
            if _already_recorded(session, row):
                return False
            session.add(row)
            session.commit()
            return True
    except Exception as error:                            # noqa: BLE001 — see module docs
        log.error(f"shadow divergence not recorded: {error}", event="IR_SHADOW_STORE")
        return False


def _already_recorded(session, row: IrShadowDivergence) -> bool:
    """The unique index is the real guard; this avoids provoking it on every re-scan."""
    existing = session.scalar(
        select(IrShadowDivergence.id)
        .where(IrShadowDivergence.owner_id == row.owner_id,
               IrShadowDivergence.broker_account_id == row.broker_account_id,
               IrShadowDivergence.instrument_key == row.instrument_key,
               IrShadowDivergence.bar_time == row.bar_time,
               IrShadowDivergence.graph_address == row.graph_address,
               IrShadowDivergence.reason == row.reason))
    return existing is not None


def recent(*, owner_id: str, broker_account_id: str, limit: int = 50,
           instrument_key: str | None = None) -> list[dict]:
    """The newest disagreements, for the observability endpoint. Never raises."""
    try:
        with SessionLocal() as session:
            query = select(IrShadowDivergence).where(
                IrShadowDivergence.owner_id == owner_id,
                IrShadowDivergence.broker_account_id == broker_account_id).order_by(
                IrShadowDivergence.observed_at.desc(), IrShadowDivergence.id.desc())
            if instrument_key:
                query = query.where(IrShadowDivergence.instrument_key == instrument_key)
            return [_to_dict(row) for row in session.scalars(query.limit(max(1, limit)))]
    except Exception as error:                            # noqa: BLE001
        log.error(f"shadow divergence read failed: {error}", event="IR_SHADOW_STORE")
        return []


def counts_by_reason(*, owner_id: str, broker_account_id: str) -> dict[str, int]:
    """How many of each classification have ever been recorded. Never raises."""
    from sqlalchemy import func

    try:
        with SessionLocal() as session:
            return {reason: int(total) for reason, total in session.execute(
                select(IrShadowDivergence.reason, func.count())
                .where(IrShadowDivergence.owner_id == owner_id,
                       IrShadowDivergence.broker_account_id == broker_account_id)
                .group_by(IrShadowDivergence.reason))}
    except Exception as error:                            # noqa: BLE001
        log.error(f"shadow divergence count failed: {error}", event="IR_SHADOW_STORE")
        return {}


def prune(cutoff: dt.datetime | None, *, owner_id: str,
          broker_account_id: str) -> int:
    """Delete rows observed strictly before `cutoff`. A `None` cutoff deletes nothing —
    the standing retention rule here is that "keep forever" never means "delete
    everything" (`app/engine/retention.py`)."""
    if cutoff is None:
        return 0
    try:
        with SessionLocal() as session:
            deleted = session.execute(
                delete(IrShadowDivergence)
                .where(IrShadowDivergence.owner_id == owner_id,
                       IrShadowDivergence.broker_account_id == broker_account_id,
                       IrShadowDivergence.observed_at < cutoff)).rowcount or 0
            session.commit()
            return int(deleted)
    except Exception as error:                            # noqa: BLE001
        log.error(f"shadow divergence prune failed: {error}", event="IR_SHADOW_STORE")
        return 0


def _to_dict(row: IrShadowDivergence) -> dict:
    return {
        "observed_at": row.observed_at.isoformat() if row.observed_at else None,
        "bar_time": row.bar_time.isoformat() if row.bar_time else None,
        "instrument_key": row.instrument_key,
        "authoritative_strategy_key": row.authoritative_strategy_key,
        "shadow_strategy_key": row.shadow_strategy_key,
        "graph_address": row.graph_address,
        "authoritative": json.loads(row.authoritative_json) if row.authoritative_json else None,
        "ir": json.loads(row.ir_json) if row.ir_json else None,
        "warmup_state": row.warmup_state,
        "declared_warmup": row.declared_warmup,
        "frame_id": row.frame_id,
        "frame_bars": row.frame_bars,
        "frame_first_ts": row.frame_first_ts.isoformat() if row.frame_first_ts else None,
        "frame_last_ts": row.frame_last_ts.isoformat() if row.frame_last_ts else None,
        "reason": row.reason,
        "detail": row.detail,
        "eval_ms": row.eval_ms,
        "market_open": row.market_open,
    }


__all__ = ["counts_by_reason", "prune", "recent", "record"]
