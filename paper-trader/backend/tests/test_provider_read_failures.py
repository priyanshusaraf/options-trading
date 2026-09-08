"""A failed read must be distinguishable from an empty one.

`get_candles` had no failure channel: `KiteProvider` caught every exception and returned `[]`,
so "the API 500'd", "the token expired" and "this instrument has no history" were one answer.

The cost is not theoretical, and it is not in the adapter. `runner.scan_signals` is written on
the opposite assumption — it wraps the call in `try/except` and, on an exception, records a
`candle` health failure, latches `_mark_token_bad` for an auth error so the remaining
instruments are skipped rather than re-failing, and breaks out of the scan. **None of that
could fire.** The adapter never raised, so on a live token expiry the engine called
`health.record_ok("candle")` on every tick, refreshed `last_scan_ok`, then dropped each
instrument on the short-frame check. The operator's health surface reported a healthy feed
while the connection was returning nothing.

So this is one narrow change with a wide consequence: raise `ProviderReadError` where the read
failed, keep `[]` for genuinely absent history, and the failure handling that already exists
starts working. The message is preserved through the wrapper because `_is_auth_error` reads it.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.providers.base import ProviderReadError
from app.providers.kite import KiteProvider

AUTH_FAILURE = "Incorrect `api_key` or `access_token`."


class _Kite:
    """A KiteConnect double whose transport can be failed one endpoint at a time."""

    def __init__(self, *, dump_fails=False, history_fails=False, history=None) -> None:
        self.dump_fails = dump_fails
        self.history_fails = history_fails
        self.history = history if history is not None else []

    def instruments(self, exchange):
        if self.dump_fails:
            raise Exception(AUTH_FAILURE)
        if exchange == "NSE":
            return [{"instrument_token": 256265, "tradingsymbol": "NIFTY 50",
                     "name": "NIFTY 50", "instrument_type": "EQ", "expiry": "",
                     "strike": 0.0, "lot_size": 0, "tick_size": 0.05}]
        return []

    def historical_data(self, token, from_date, to_date, interval):
        if self.history_fails:
            raise Exception(AUTH_FAILURE)
        return self.history


class _NoThrottle:
    def wait(self, category): return None


def _provider(**kw) -> KiteProvider:
    from app.core.logging import WarnGate

    p = KiteProvider.__new__(KiteProvider)
    p._strict_data_runtime = False
    p.kite = _Kite(**kw)
    p.s = None
    p.api_key = p.api_secret = p.access_token = "fake"
    p._dumps, p._fut_cache, p._tick_cache = {}, {}, {}
    p._throttle = _NoThrottle()
    p._warn = WarnGate()
    return p


NIFTY = get_instrument("NIFTY")


# ── the adapter ──────────────────────────────────────────────────────────────

def test_a_failing_history_call_raises_rather_than_reporting_no_data():
    with pytest.raises(ProviderReadError):
        _provider(history_fails=True).get_candles(NIFTY, "15minute", 30)


def test_a_failing_instrument_dump_raises_too():
    """Token resolution reads the dump. Swallowing that failure produced a `None` token and
    then an empty list — the same wrong answer one call earlier."""
    with pytest.raises(ProviderReadError):
        _provider(dump_fails=True).get_candles(NIFTY, "15minute", 30)


def test_the_raised_error_still_reads_as_an_expired_token():
    """`_is_auth_error` matches on the SDK's message text. A wrapper that discards it would
    latch nothing, and every instrument in the loop would re-fail the same way."""
    from app.engine.runner import EngineRunner

    with pytest.raises(ProviderReadError) as excinfo:
        _provider(history_fails=True).get_candles(NIFTY, "15minute", 30)
    assert EngineRunner._is_auth_error(excinfo.value), (
        "the auth-error latch reads the message; wrapping must preserve it")


def test_genuinely_absent_history_is_still_an_empty_list_not_an_error():
    """The distinction is the entire point. An instrument Kite knows and has no bars for is
    not a failure, and turning it into one would make every thin symbol look like an outage."""
    assert _provider(history=[]).get_candles(NIFTY, "15minute", 30) == []


def test_a_resolvable_instrument_with_bars_is_unaffected():
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    start = dt.datetime(2026, 8, 3, 9, 15, tzinfo=ist)
    rows = [{"date": start + dt.timedelta(minutes=15 * i), "open": 24000.0 + i,
             "high": 24006.0 + i, "low": 23996.0 + i, "close": 24002.0 + i,
             "volume": 15000} for i in range(6)]
    provider = _provider(history=rows)
    provider.now = lambda: dt.datetime(2026, 8, 3, 10, 30)
    bars = provider.get_candles(NIFTY, "15minute", 30)
    assert len(bars) == 5, "the still-forming bar is still dropped"
    assert all(b.ts.tzinfo is None for b in bars), "IST wall-clock is still stripped"


# ── the consequence: the engine's existing failure handling now runs ─────────

def test_the_scan_records_a_failure_and_latches_the_token_instead_of_reporting_health():
    """The behaviour that could not happen before.

    Previously: `record_ok("candle")` every tick, `last_scan_ok` refreshed, no latch, each
    instrument dropped silently on the short-frame check — a healthy-looking feed delivering
    nothing.
    """
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    try:
        failing = _provider(history_fails=True)
        failing.now = lambda: dt.datetime(2026, 8, 3, 11, 0)
        failing.is_tradable_now = lambda inst: True
        r.provider = failing
        r.enabled = ["NIFTY", "BANKNIFTY"]

        before = dict(r.last_scan_ok)
        r.scan_signals()

        assert r._is_token_probably_bad(failing.now()), (
            "an auth failure must latch, or every remaining instrument re-fails identically")
        assert r.last_scan_ok == before, (
            "a failed read must not refresh per-instrument freshness")
    finally:
        try:
            r.broker.s.close()
        except Exception:
            pass
