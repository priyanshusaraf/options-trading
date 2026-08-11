"""F-03: transport health and usable-frame freshness are two different claims.

`scan_signals` stamped `last_scan_ok[key]` the instant `get_candles` returned without
raising — before the validator ran and before the short-frame check. A provider that is
reachable but returning nothing (a fresh listing, a mis-resolved token, a feed that has
dropped history) therefore fed the cockpit a *fresh* per-instrument scan time for an
instrument on which no signal frame was ever evaluated. Row shows fresh, signal shows the
last one from whenever the data last worked.

Transport health (`health.record_ok("candle")`) is the honest answer for an empty-but-
successful read: the connection is fine. Per-instrument freshness is not — it must only
advance when a frame the strategy could actually be evaluated on was produced.

Four distinct states, one assertion pair each:

| state                | transport   | last_scan_ok |
|----------------------|-------------|--------------|
| failed transport     | failure     | unchanged    |
| valid empty history  | ok          | unchanged    |
| short history        | ok          | unchanged    |
| valid completed frame| ok          | advanced     |
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.providers.base import Candle, ProviderReadError

BEFORE = dt.datetime(2026, 8, 9, 10, 0)
NOW = dt.datetime(2026, 8, 9, 11, 0)


class _Provider:
    """Only what `scan_signals` reads. `candles` is the whole experiment."""

    def __init__(self, candles) -> None:
        self._candles = candles
        self.calls = 0

    def now(self):
        return NOW

    def is_tradable_now(self, inst):
        return True

    def get_candles(self, inst, interval, days):
        self.calls += 1
        if isinstance(self._candles, Exception):
            raise self._candles
        return list(self._candles)


def _bars(n: int) -> list[Candle]:
    """`n` well-formed, strictly-spaced completed 15m bars."""
    start = dt.datetime(2026, 8, 7, 9, 15)
    out = []
    for i in range(n):
        base = 24000.0 + (i % 7) * 3.0
        out.append(Candle(ts=start + dt.timedelta(minutes=15 * i), open=base,
                          high=base + 6.0, low=base - 6.0, close=base + 2.0,
                          volume=15000.0))
    return out


@pytest.fixture
def runner():
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.enabled = {"NIFTY"}
    r.last_scan_ok["NIFTY"] = BEFORE     # a stale-but-present prior scan
    yield r
    try:
        r.broker.s.close()
    except Exception:
        pass


def _scan(r, candles):
    r.provider = _Provider(candles)
    r.scan_signals()
    return r.provider


# ── state 1: failed transport ────────────────────────────────────────────────

def test_failed_transport_records_a_failure_and_does_not_advance_freshness(runner):
    _scan(runner, ProviderReadError("historical_data failed: 503"))
    assert runner.health.candle_health()["consecutive_failures"] >= 1
    assert runner.last_scan_ok["NIFTY"] == BEFORE


# ── state 2: valid empty history ─────────────────────────────────────────────

def test_valid_empty_history_is_transport_ok_but_not_fresh(runner):
    _scan(runner, [])
    assert runner.health.candle_health()["consecutive_failures"] == 0, (
        "an empty-but-successful read is not a transport failure")
    assert runner.last_scan_ok["NIFTY"] == BEFORE, (
        "no frame was evaluated — the cockpit must not be told the scan is fresh")


# ── state 3: short history ───────────────────────────────────────────────────

def test_short_history_is_transport_ok_but_not_fresh(runner):
    short = _bars(runner.settings.ema_length + 4)   # one below the usable threshold
    _scan(runner, short)
    assert runner.health.candle_health()["consecutive_failures"] == 0
    assert runner.last_scan_ok["NIFTY"] == BEFORE, (
        "a frame too short to evaluate is not a scan")


# ── state 4: a valid completed frame ─────────────────────────────────────────

def test_a_usable_frame_advances_freshness(runner):
    _scan(runner, _bars(runner.settings.ema_length + 40))
    assert runner.health.candle_health()["consecutive_failures"] == 0
    assert runner.last_scan_ok["NIFTY"] == NOW, (
        "the fix must not stop real scans from reporting fresh")
    assert runner.state.get("NIFTY"), "a usable frame should have been evaluated"
