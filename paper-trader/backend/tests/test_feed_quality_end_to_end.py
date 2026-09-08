"""A dirty candle feed must travel all the way to /api/health.

Every link in this chain has unit tests: `validate_candles` detects anomalies,
`FeedQuality` records and throttles them, `readiness.evaluate` marks the probe
degraded, and the endpoint serialises `provider_feed`. What has never been
proven is that they are actually CONNECTED — which is precisely the failure mode
this codebase keeps producing, and which unit tests cannot see.

It matters now rather than later: `provider_feed` has been empty every time it
was checked, because the market was closed. On Monday it will either populate or
it will not, and if the chain is broken the symptom is indistinguishable from a
clean feed. "Empty because nothing is wrong" and "empty because nothing is
wired" look identical from outside.

So this drives a genuinely corrupt series through the real scan and asserts it
comes out the far end.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.providers.base import Candle


def _dirty_series(n=80, base=100.0):
    """A series with duplicates AND an inverted bar — two different anomalies,
    so a chain that only handles one is still caught."""
    t0 = dt.datetime(2026, 8, 3, 9, 15)
    out = []
    for i in range(n):
        px = base + i * 0.1
        out.append(Candle(ts=t0 + dt.timedelta(minutes=15 * i), open=px,
                          high=px + 0.5, low=px - 0.5, close=px + 0.2, volume=100.0))
    out.append(out[-1])                       # duplicate timestamp
    bad = out[10]
    out[10] = Candle(ts=bad.ts, open=bad.open, high=bad.low - 5.0,   # high below low
                     low=bad.high, close=bad.close, volume=bad.volume)
    return out


@pytest.fixture
def client():
    """A TestClient WITHOUT the lifespan, and its own runner.

    Entering the lifespan starts the real signal and risk lanes as background
    tasks. This test then calls `scan_signals()` synchronously from the test
    thread — concurrently with the risk lane, on the SAME shared broker session.
    The engine serialises its two lanes with `_lock`; a direct call bypasses
    that, and the result was
    `InvalidRequestError: This session is in 'prepared' state`, failing a
    different test on each run. Driving the scan directly is only safe against a
    runner whose loops are not running.

    Both lanes are beaten so the readiness verdict is not `starting`, which
    deliberately outranks `degraded` — in production a feed anomaly happens hours
    into a session, not during boot.
    """
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.main import app

    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.running = True
    r._beat_now("risk")
    r._beat_now("signal")
    app.state.runner = r
    try:
        yield TestClient(app)
    finally:
        r.broker.close()


def _runner():
    from app.main import app
    return app.state.runner


def test_a_corrupt_feed_reaches_the_health_endpoint(client, monkeypatch):
    """The end-to-end claim: corrupt candles in, `provider_feed` out."""
    r = _runner()
    monkeypatch.setattr(r.provider, "get_candles",
                        lambda inst, interval, days: _dirty_series(), raising=False)
    monkeypatch.setattr(r.provider, "is_tradable_now", lambda inst: True, raising=False)

    r.scan_signals()

    assert r.feed_quality.anomaly_count() > 0, \
        "the scan repaired a corrupt feed without recording it"
    body = client.get("/api/readiness").json()
    assert body["provider_feed"], "anomalies never reached /api/health"
    assert body["status"] == "degraded", \
        "a dirty feed did not degrade the probe"
    assert "feed_quality" in body["degraded_checks"]


def test_a_dirty_feed_is_degraded_not_unready(client, monkeypatch):
    """It must NOT 503. The bars were repaired before any strategy saw them, so
    this is a reason to look, not a reason to take the box out of rotation and
    fail a deploy."""
    r = _runner()
    monkeypatch.setattr(r.provider, "get_candles",
                        lambda inst, interval, days: _dirty_series(), raising=False)
    monkeypatch.setattr(r.provider, "is_tradable_now", lambda inst: True, raising=False)
    r.scan_signals()
    assert client.get("/api/readiness").status_code == 200


def test_the_report_names_the_instrument_and_the_problem(client, monkeypatch):
    """A warning that does not say WHICH instrument or WHAT was wrong cannot be
    acted on at 09:20."""
    r = _runner()
    monkeypatch.setattr(r.provider, "get_candles",
                        lambda inst, interval, days: _dirty_series(), raising=False)
    monkeypatch.setattr(r.provider, "is_tradable_now", lambda inst: True, raising=False)
    r.scan_signals()
    feed = client.get("/api/readiness").json()["provider_feed"]
    key, row = next(iter(feed.items()))
    assert key
    detail = row["detail"].lower()
    assert "duplicate" in detail or "repair" in detail or "corrupt" in detail, detail


def test_a_clean_feed_leaves_the_probe_alone(client, monkeypatch):
    """The control. Without it, a probe stuck permanently on 'degraded' would
    pass the tests above and tell nobody anything."""
    r = _runner()
    r.feed_quality._rows.clear()
    clean = _dirty_series()[:-1]
    clean[10] = Candle(ts=clean[10].ts, open=100.0, high=101.0, low=99.0,
                       close=100.5, volume=100.0)
    monkeypatch.setattr(r.provider, "get_candles",
                        lambda inst, interval, days: clean, raising=False)
    monkeypatch.setattr(r.provider, "is_tradable_now", lambda inst: True, raising=False)
    r.scan_signals()
    assert r.feed_quality.anomaly_count() == 0
    assert client.get("/api/readiness").json()["provider_feed"] == {}


def test_a_recovered_feed_clears_the_warning(client, monkeypatch):
    """A one-off glitch must not read as an ongoing fault forever — that is how
    a warning light stops being believed."""
    r = _runner()
    monkeypatch.setattr(r.provider, "is_tradable_now", lambda inst: True, raising=False)
    monkeypatch.setattr(r.provider, "get_candles",
                        lambda inst, interval, days: _dirty_series(), raising=False)
    r.scan_signals()
    assert r.feed_quality.anomaly_count() > 0

    clean = _dirty_series()[:-1]
    clean[10] = Candle(ts=clean[10].ts, open=100.0, high=101.0, low=99.0,
                       close=100.5, volume=100.0)
    monkeypatch.setattr(r.provider, "get_candles",
                        lambda inst, interval, days: clean, raising=False)
    r.scan_signals()
    assert client.get("/api/readiness").json()["provider_feed"] == {}
