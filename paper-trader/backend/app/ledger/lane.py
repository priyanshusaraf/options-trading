"""The manual-trade detection lane.

Deliberately NOT part of the engine's two cooperative loops, and it never takes
runner._lock. The 2026-07-13 `risk_loop_stalled` incident was a sweep holding
that lock for 30s; this lane touches an entirely different database and
genuinely does not need it. If it dies, trading is unaffected.

It forces a sweep near session close, because Kite's orderbook is same-day only:
whatever this lane has not seen by midnight is gone from the broker forever.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, time

from app.core.async_tasks import to_thread_drained
from app.core.logging import log

# Force a sweep in this window regardless of cadence, so a late start or a
# restart at 15:20 still captures the day before the orderbook resets.
_CLOSE_SWEEP_START = time(15, 25)
_CLOSE_SWEEP_END = time(15, 45)

# How often the lane wakes to decide whether to poll. Kept small and cheap; the
# actual broker call is gated by should_run_now().
_TICK_SECONDS = 5.0


def should_run_now(now: datetime, last_run: datetime | None, interval: float) -> bool:
    if last_run is None:
        return True
    if _CLOSE_SWEEP_START <= now.time() <= _CLOSE_SWEEP_END:
        # Inside the close window, poll at least once a minute regardless of a
        # slower configured cadence.
        return (now - last_run).total_seconds() >= 60
    return (now - last_run).total_seconds() >= interval


async def _tick_guarded(fn) -> None:
    """Run one detection tick, swallowing everything.

    A raise here must never kill the lane: Kite's orderbook is same-day only, so
    a dead lane silently loses the rest of the trading day."""
    try:
        await to_thread_drained(fn)
    except Exception as e:
        log.warn(f"manual-detect tick failed: {e}")


async def run_manual_detect_loop(provider, exec_sessionmaker, ledger_sm,
                                 settings, clock) -> None:
    """Poll the Kite orderbook for trades the owner placed by hand.

    READ-ONLY with respect to the execution ledger. It reads order_journal and
    positions to learn what belongs to the bot, and writes only to ledger.db.
    """
    if getattr(provider, "name", None) != "kite":
        # MockProvider has no orderbook. No-op cleanly so the test suite and
        # scripts/dryrun.py stay green.
        log.info("manual-detect: provider is not kite — lane disabled")
        return
    if not getattr(settings, "manual_detect_enabled", True):
        log.info("manual-detect: disabled by settings")
        return

    from app.ledger.detect import detect_manual_fills

    last: datetime | None = None
    log.info("manual-detect: lane started")
    while True:
        try:
            now = clock()
            interval = float(getattr(settings, "manual_detect_seconds", 30.0) or 30.0)
            if should_run_now(now, last, interval):
                last = now

                def tick() -> None:
                    with exec_sessionmaker() as exec_s:
                        n = detect_manual_fills(provider, exec_s, ledger_sm, now)
                    if n:
                        log.info(f"manual-detect: {n} new manual fill(s) "
                                 f"awaiting your reasoning")

                await _tick_guarded(tick)
        except asyncio.CancelledError:
            log.info("manual-detect: lane stopped")
            raise
        except Exception as e:
            # Belt and braces: even a failure computing `now` must not end the
            # lane, for the same same-day-only reason.
            log.warn(f"manual-detect loop error: {e}")
        await asyncio.sleep(_TICK_SECONDS)
