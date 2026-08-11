"""Bounded growth for the append-only telemetry tables.

Measured on production 2026-08-01: `paper_trader.db` is **108 MB** and grows ~5 MB/day —
`option_data` ~17k rows/day, `signal_events` ~9k/day, `equity_snapshots` ~8.6k/day. The
droplet has 1 GB of RAM with 134 MB free, two memory leaks have already OOM'd it, and there
is no resize coming. Left alone the file passes half a gigabyte inside a quarter.

**The money record is never pruned.** `trades`, `positions`, `order_journal` and
`capital_state` are the ledger: the cash invariant is computed from them, they are not
regenerable, and a missing row there is an unrecoverable accounting hole. Only telemetry
ages out.

`equity_snapshots` is DOWNSAMPLED rather than deleted, because the equity curve is the only
long-run record of how the bot actually performed — thinning it to one row per interval
keeps the shape at every age while removing ~99% of the rows.

A window of `0` (or negative) means **keep forever**, never "delete everything". The
opposite reading would turn one fat-fingered setting into permanent data loss.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import delete, select

from app.db.models import (
    EquitySnapshot, IrShadowDivergence, OptionData, SignalEvent)
from app.db.session import SessionLocal


@dataclass(frozen=True)
class RetentionPolicy:
    enabled: bool = True
    option_data_days: int = 90          # local option history — Kite sells no replacement
    signal_events_days: int = 90
    equity_full_days: int = 7           # full resolution inside this window
    equity_downsample_minutes: int = 15  # outside it, keep ~1 row per this many minutes


def prune(now: dt.datetime, policy: RetentionPolicy | None = None, *, owner_id: str,
          broker_account_id: str) -> dict[str, int]:
    """Apply `policy` and return {table: rows_removed}. Idempotent."""
    p = policy or RetentionPolicy()
    report = {"option_data": 0, "signal_events": 0, "equity_snapshots": 0,
              "ir_shadow_divergences": 0}
    if not p.enabled:
        return report

    with SessionLocal() as s:
        if p.option_data_days > 0:
            cutoff = now - dt.timedelta(days=p.option_data_days)
            report["option_data"] = s.execute(
                delete(OptionData).where(OptionData.ts < cutoff)).rowcount or 0
        if p.signal_events_days > 0:
            cutoff = now - dt.timedelta(days=p.signal_events_days)
            report["signal_events"] = s.execute(
                delete(SignalEvent).where(
                    SignalEvent.owner_id == owner_id,
                    SignalEvent.broker_account_id == broker_account_id,
                    SignalEvent.time < cutoff)).rowcount or 0
            # L1 Stage 1 shadow disagreements share the signal-telemetry window on
            # purpose: same class of row, and a disagreement is not worth keeping longer
            # than the signal it concerns. Sharing the knob also avoids shipping a
            # Settings field with no UI to show it.
            report["ir_shadow_divergences"] = s.execute(
                delete(IrShadowDivergence)
                .where(IrShadowDivergence.owner_id == owner_id,
                       IrShadowDivergence.broker_account_id == broker_account_id,
                       IrShadowDivergence.observed_at < cutoff)).rowcount or 0
        if p.equity_full_days > 0 and p.equity_downsample_minutes > 0:
            report["equity_snapshots"] = _downsample_equity(
                s, now - dt.timedelta(days=p.equity_full_days),
                p.equity_downsample_minutes, owner_id=owner_id,
                broker_account_id=broker_account_id)
        s.commit()
    return report


def _downsample_equity(s, cutoff: dt.datetime, bucket_minutes: int, *, owner_id: str,
                       broker_account_id: str) -> int:
    """Keep the FIRST snapshot in each `bucket_minutes` window older than `cutoff`;
    delete the rest.

    Done in Python over ids rather than as one clever SQL statement because the bucket
    key has to be computed from a DATETIME the same way SQLite and SQLAlchemy both agree
    on, and a wrong bucket expression here silently deletes the wrong rows. Reading ids
    first also makes the operation obviously bounded and inspectable."""
    rows = s.execute(
        select(EquitySnapshot.id, EquitySnapshot.time, EquitySnapshot.segment)
        .where(EquitySnapshot.owner_id == owner_id,
               EquitySnapshot.broker_account_id == broker_account_id,
               EquitySnapshot.time < cutoff)
        .order_by(EquitySnapshot.time)).all()
    if not rows:
        return 0

    keep: set[int] = set()
    seen: set[tuple] = set()
    bucket = max(1, int(bucket_minutes)) * 60
    for rid, when, segment in rows:
        # Keep one row per (segment, time-bucket): the per-segment curves are separate
        # series and thinning them together would erase whole segments' history.
        key = (segment, int(when.timestamp()) // bucket)
        if key in seen:
            continue
        seen.add(key)
        keep.add(rid)

    doomed = [rid for rid, _, _ in rows if rid not in keep]
    if not doomed:
        return 0
    removed = 0
    for i in range(0, len(doomed), 500):          # bounded IN() lists
        chunk = doomed[i:i + 500]
        removed += s.execute(
            delete(EquitySnapshot).where(
                EquitySnapshot.owner_id == owner_id,
                EquitySnapshot.broker_account_id == broker_account_id,
                EquitySnapshot.id.in_(chunk))).rowcount or 0
    return removed


def vacuum() -> None:
    """Reclaim the freed pages. SQLite's DELETE only marks pages reusable — without this
    the file never actually shrinks, which on a 1 GB box is the whole point.

    Rewrites the entire database and takes an exclusive lock, so it must only run with
    the market closed and no position open. The caller owns that decision."""
    from sqlalchemy import text

    from app.db.session import engine
    with engine.connect() as conn:
        conn.execute(text("VACUUM"))
