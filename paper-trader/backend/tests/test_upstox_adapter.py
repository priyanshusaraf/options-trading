"""Upstox adapter semantics that the shared conformance contract cannot express.

The contract in `provider_conformance.py` is deliberately provider-neutral, so three things
specific to this adapter fall outside it — and a suppression sweep confirmed all three were
unguarded when the adapter was restored:

  1. **An unmapped interval is refused, never approximated.** The contract asks for `15minute`,
     which is mapped, so the refusal branch never ran. Answering 15-minute requests with
     1-minute bars raises nothing and changes every indicator's horizon.
  2. **Today's bars come from a second endpoint.** Historical alone still satisfies `min_bars`,
     so dropping the intraday call left the contract green while the newest thing the engine
     could act on was yesterday.
  3. **The forming bar is dropped by the clock, not by position.** Kite's "drop the last
     element" works only because Kite's ordering happens to be stable. Upstox's is not.

These use the adapter's real transport interface. Stubbing `get_candles` would exercise none of
the request-building, merging or normalisation that is actually at risk.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.providers.base import ProviderReadError
from app.providers.upstox import (
    INTERVAL_MAP,
    UnsupportedInterval,
    UpstoxInstrumentResolver,
    UpstoxProvider,
    interval_path,
)
from app.providers.upstox_transport import UpstoxResponse


class _Transport:
    """Records the paths asked for and serves shape-accurate v3 envelopes."""

    def __init__(self, now: dt.datetime, *, intraday: bool = True) -> None:
        self.now = now
        self.paths: list[str] = []
        self._serve_intraday = intraday

    @staticmethod
    def _row(ts: dt.datetime, close: float) -> list:
        # +05:30 offsets and newest-first ordering, exactly as the service sends them.
        return [ts.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                close - 2.0, close + 4.0, close - 6.0, close, 1000.0, 0]

    def get(self, path: str, params=None):
        self.paths.append(path)
        if path.startswith("/v3/market-quote/ltp"):
            return UpstoxResponse(endpoint=path,
                                  data={"NSE_INDEX:Nifty 50": {"last_price": 24012.5}})
        if "/intraday/" in path:
            if not self._serve_intraday:
                return UpstoxResponse(endpoint=path, data={"candles": []})
            # The completed 09:30 bar and the still-forming one containing `now`.
            done = self.now.replace(hour=9, minute=30, second=0, microsecond=0)
            forming = self.now.replace(second=0, microsecond=0)
            return UpstoxResponse(endpoint=path, data={"candles": [
                self._row(forming, 24500.0), self._row(done, TODAYS_CLOSE)]})
        older = self.now - dt.timedelta(days=1)
        return UpstoxResponse(endpoint=path, data={"candles": [
            self._row(older.replace(hour=9, minute=30), 23900.0),
            self._row(older.replace(hour=9, minute=45), 23950.0)]})


TODAYS_CLOSE = 24111.0


def _provider(now: dt.datetime, *, intraday: bool = True):
    p = UpstoxProvider.__new__(UpstoxProvider)
    p.access_token = "fake"
    p._transport = _Transport(now, intraday=intraday)
    p._resolver = UpstoxInstrumentResolver()
    p.now = lambda: now       # a fixed clock; the forming-bar cut is decided against it
    return p, p._transport


@pytest.fixture()
def nifty():
    return get_instrument("NIFTY")


# ── 1. an unmapped interval is refused ────────────────────────────────────

@pytest.mark.parametrize("interval", ["2minute", "45minute", "4hour", "week", "", "15min"])
def test_an_unmapped_interval_is_refused_not_rounded(interval):
    """`UnsupportedInterval` subclasses `ProviderReadError`, so a caller that fails closed on a
    read failure also fails closed here. The alternative — quietly serving the nearest mapped
    interval — is the single most expensive silent bug available to a data adapter."""
    with pytest.raises(UnsupportedInterval):
        interval_path(interval)


def test_the_refusal_happens_before_any_request_is_made(nifty):
    """Ordering matters: refusing *after* the fetch would still return bars in the failure path
    of a caller that swallowed the error."""
    p, transport = _provider(dt.datetime(2026, 8, 10, 10, 7))
    with pytest.raises(ProviderReadError):
        p.get_candles(nifty, "45minute", 5)
    assert transport.paths == [], f"a request was built for an unsupported interval: {transport.paths}"


def test_every_interval_the_engine_uses_is_mapped():
    """Guard the guard. The refusal is only correct if the mapping is COMPLETE for the vocabulary
    this system actually scans on — otherwise the adapter refuses real work correctly and
    uselessly."""
    from app.backtest.sweep import MAX_DAYS
    missing = sorted(set(MAX_DAYS) - set(INTERVAL_MAP))
    assert not missing, f"upstox cannot serve intervals this engine sweeps: {missing}"


# ── 2. today comes from a different endpoint ──────────────────────────────

def test_both_the_historical_and_intraday_endpoints_are_read(nifty):
    p, transport = _provider(dt.datetime(2026, 8, 10, 10, 7))
    p.get_candles(nifty, "15minute", 5)
    assert any("/intraday/" in path for path in transport.paths), (
        f"the current trading day was never requested: {transport.paths}")
    assert any("/intraday/" not in path and "historical-candle" in path
               for path in transport.paths), transport.paths


def test_todays_completed_bar_reaches_the_caller(nifty):
    """The observable consequence of (2). Without the intraday read the newest bar the engine
    could act on is yesterday's — a live 15-minute scan that never fires."""
    p, _ = _provider(dt.datetime(2026, 8, 10, 10, 7))
    bars = p.get_candles(nifty, "15minute", 5)
    today = dt.date(2026, 8, 10)
    assert [b for b in bars if b.ts.date() == today], (
        f"no bar from today in {[b.ts for b in bars]}")
    assert bars[-1].close == TODAYS_CLOSE


# ── 3. the forming bar is cut by the clock ────────────────────────────────

def test_the_still_forming_bar_is_dropped(nifty):
    """A forming bar repaints. Every signal computed on it is computed on a number that has not
    happened yet — and `CLAUDE.md`'s "signals fire only on completed candles" is that rule."""
    now = dt.datetime(2026, 8, 10, 10, 7)
    p, _ = _provider(now)
    bars = p.get_candles(nifty, "15minute", 5)
    assert all(b.ts <= now - dt.timedelta(minutes=15) for b in bars), (
        f"a forming bar survived: {[b.ts for b in bars]}")
    assert 24500.0 not in [b.close for b in bars], "the forming bar's close reached the caller"


def test_bars_are_sorted_ascending_and_naive_ist(nifty):
    """The service sends newest-first with a `+05:30` offset. This repo's candle epoch is naive
    IST throughout; an aware timestamp here would be internally consistent and would raise at a
    comparison far from the adapter."""
    p, _ = _provider(dt.datetime(2026, 8, 10, 10, 7))
    bars = p.get_candles(nifty, "15minute", 5)
    assert [b.ts for b in bars] == sorted(b.ts for b in bars)
    assert all(b.ts.tzinfo is None for b in bars)


def test_a_day_with_no_trading_yet_still_returns_history(nifty):
    """An empty intraday response is a successful read of a day with no completed bars — not a
    failure, and not a reason to drop the history."""
    p, _ = _provider(dt.datetime(2026, 8, 10, 9, 20), intraday=False)
    assert len(p.get_candles(nifty, "15minute", 5)) == 2
