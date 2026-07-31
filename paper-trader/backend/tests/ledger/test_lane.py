import asyncio
from datetime import datetime

from app.ledger.lane import _tick_guarded, run_manual_detect_loop, should_run_now

BASE = datetime(2026, 7, 31, 10, 0, 0)


def test_runs_when_it_has_never_run():
    assert should_run_now(BASE, None, 30.0) is True


def test_runs_once_the_interval_has_elapsed():
    assert should_run_now(datetime(2026, 7, 31, 10, 0, 31), BASE, 30.0) is True


def test_does_not_run_before_the_interval_elapses():
    assert should_run_now(datetime(2026, 7, 31, 10, 0, 10), BASE, 30.0) is False


def test_the_close_window_polls_at_least_once_a_minute():
    # Kite's orderbook is same-day only, so the last minutes of the session are
    # the last chance to capture the day.
    last = datetime(2026, 7, 31, 15, 30, 0)
    assert should_run_now(datetime(2026, 7, 31, 15, 31, 1), last, 3600.0) is True


def test_the_close_window_still_respects_a_one_minute_floor():
    last = datetime(2026, 7, 31, 15, 30, 0)
    assert should_run_now(datetime(2026, 7, 31, 15, 30, 30), last, 3600.0) is False


def test_a_throwing_tick_does_not_propagate():
    """A raise must never kill the lane — a dead lane silently loses the rest of
    the trading day, and the orderbook cannot be re-read tomorrow."""
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("kite down")

    asyncio.run(_tick_guarded(boom))
    assert calls == [1]


def test_the_lane_no_ops_off_kite():
    """MockProvider has no orderbook. The lane must return immediately so the
    suite and scripts/dryrun.py stay green."""
    class _Mock:
        name = "mock"

    async def go():
        await asyncio.wait_for(
            run_manual_detect_loop(_Mock(), None, None, object(), lambda: BASE),
            timeout=2.0)

    asyncio.run(go())   # returns rather than looping forever


def test_the_lane_no_ops_when_disabled():
    class _Kite:
        name = "kite"

    class _Settings:
        manual_detect_enabled = False

    async def go():
        await asyncio.wait_for(
            run_manual_detect_loop(_Kite(), None, None, _Settings(), lambda: BASE),
            timeout=2.0)

    asyncio.run(go())
