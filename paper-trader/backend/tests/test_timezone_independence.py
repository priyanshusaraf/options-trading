"""The system must not depend on the host's timezone.

Measured 2026-08-01: the production droplet is set to **IST**. DigitalOcean
droplets default to **UTC**. So if that box is ever rebuilt, restored, or
replaced, it comes up 5.5 hours off — and nothing in the codebase would notice,
because correctness currently rests partly on a machine setting rather than on
code.

The consequences are not cosmetic. Everything in this app speaks IST wall-clock:
candle timestamps, the market-hours windows, the square-off deadline, the
mark-staleness guard that decides whether a stop is allowed to fire. A 5.5-hour
shift would put the engine's idea of "now" outside the session for the entire
trading day, or — worse — make every position's last mark look 5.5 hours stale,
at which point the staleness guard suppresses SL/TP on live money.

These tests run the real logic under `TZ=UTC` and assert it still gets IST
right. They are the check that turns "it happens to be configured correctly"
into "it cannot be configured wrongly".
"""
from __future__ import annotations

import datetime as dt
import os
import time

import pytest

from app.core.market_hours import IST, ist_epoch, is_open, now_ist


@pytest.fixture
def utc_host():
    """Pretend this process is running on a UTC box, like a fresh droplet."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


def test_now_ist_is_ist_even_on_a_utc_host(utc_host):
    """The engine's notion of 'now' must be IST regardless of the host."""
    n = now_ist()
    assert n.tzinfo is not None, "a naive 'now' inherits the host timezone"
    assert n.utcoffset() == dt.timedelta(hours=5, minutes=30)


def test_market_hours_do_not_shift_with_the_host(utc_host):
    """11:00 IST is mid-session on a Monday, on any box."""
    monday_1100_ist = dt.datetime(2026, 8, 3, 11, 0)
    assert is_open("NSE", monday_1100_ist) is True


def test_a_closed_time_stays_closed_on_a_utc_host(utc_host):
    """05:30 IST is 00:00 UTC — the case a naive conversion gets wrong."""
    monday_0530_ist = dt.datetime(2026, 8, 3, 5, 30)
    assert is_open("NSE", monday_0530_ist) is False


def test_candle_epochs_are_interpreted_as_ist_not_host_local(utc_host):
    """A naive candle timestamp is IST wall-clock. Reading it as host-local
    would move every bar by the host offset — the 2026-07 H7 bug, where a UTC
    host truncated the history window 5.5h early and silently dropped the most
    recent bars."""
    bar = dt.datetime(2026, 8, 3, 15, 0)           # 15:00 IST
    expected = int(bar.replace(tzinfo=IST).timestamp())
    assert ist_epoch(bar) == expected


def test_ist_epoch_is_stable_across_host_timezones():
    """The same candle must map to the same instant no matter where it is read."""
    bar = dt.datetime(2026, 8, 3, 15, 0)
    old = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "UTC"; time.tzset()
        utc_view = ist_epoch(bar)
        os.environ["TZ"] = "Asia/Kolkata"; time.tzset()
        ist_view = ist_epoch(bar)
        os.environ["TZ"] = "America/New_York"; time.tzset()
        ny_view = ist_epoch(bar)
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()
    assert utc_view == ist_view == ny_view


def test_the_mark_staleness_guard_does_not_break_on_a_utc_host(utc_host):
    """The dangerous one.

    `broker.mark()` stamps `last_mark_time` from the PROVIDER clock (IST), but
    falls back to a naive `datetime.now()` when no time is passed. On a UTC host
    those two differ by 5.5 hours, and the staleness guard compares them — a mark
    that just happened would look 19,800 seconds old, and `is_stale` suppresses
    SL/TP on a stale mark. That is a stop silently not firing on real money.
    """
    from app.engine.health import is_stale
    provider_now = now_ist().replace(tzinfo=None)      # what the engine records
    host_now = dt.datetime.now()                        # what the fallback records
    drift = abs((provider_now - host_now).total_seconds())
    assert drift > 3600, "precondition: this host is not UTC-offset from IST"
    # The guard must not see a fresh mark as stale. Stamped from the provider
    # clock and compared against the provider clock, it never does.
    assert is_stale(provider_now, provider_now, 30) is False
    # ...but stamped from the HOST clock it would, which is why the fallback is
    # a latent hazard rather than a harmless default.
    assert is_stale(host_now, provider_now, 30) is True


def test_the_mark_fallback_now_uses_ist(utc_host):
    """Regression: the fallback must be IST wall-clock, so it agrees with the
    provider clock the staleness guard compares it against."""
    import inspect
    from app.engine import broker as broker_mod
    src = inspect.getsource(broker_mod.PaperBroker.mark)
    assert "now_ist()" in src
    assert "now or dt.datetime.now()" not in src
