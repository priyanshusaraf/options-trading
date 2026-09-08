"""/api/health as a wired readiness probe.

`tests/test_readiness.py` covers the verdict logic as a pure table. This file
covers the things only the real app can prove: that the endpoint is reachable
without auth, that it keeps the shape `deploy.sh` parses, that it returns 503
rather than raising, and — the one that would bite hardest — that a perfectly
healthy MOCK engine reads as healthy, because the heartbeat it measures is on a
wall clock and not the mock's synthetic candle clock.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _runner(client):
    from app.main import app
    return app.state.runner


# ── the contract deploy.sh depends on ───────────────────────────────────────

def test_health_is_200_and_keeps_its_old_shape(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "commit" in body["build"], "deploy.sh greps build.commit out of this body"


def test_health_needs_no_auth_token(client, monkeypatch):
    """It is the one probe that must answer before anything else is trusted, and
    an uptime monitor cannot hold a token.

    Patch the settings INSTANCE, never `get_settings.cache_clear()` — clearing
    the cache swaps the process-wide singleton, so every later test that
    monkeypatched an attribute on the old object silently stops taking effect.
    (It cost two unrelated failures in this suite before it was written this way.)
    """
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/status").status_code == 401   # control: auth IS on


def test_a_healthy_mock_engine_reads_as_healthy(client):
    """The regression this design exists to avoid: `_beat_now` stamps
    `provider.now()`, which under the mock is SIMULATED time jumping a candle per
    tick. Measuring staleness on that clock would report this engine — which is
    fine — as stale. Readiness reads the monotonic beat instead."""
    r = _runner(client)
    r._beat_now("risk")
    r._beat_now("signal")
    body = client.get("/api/readiness").json()
    assert body["ready"] is True
    assert body["loops"]["risk"]["state"] in ("ok", "starting")


# ── it can say no ───────────────────────────────────────────────────────────

def test_a_stalled_risk_lane_returns_503(client, monkeypatch):
    """A real 2026-07-13 failure mode (`risk_loop_stalled`): the lane was starved
    for 30s at a time while /api/health stayed green."""
    r = _runner(client)
    r._beat_wall["risk"] = time.monotonic() - 10_000
    r._beat_wall["signal"] = time.monotonic()
    resp = client.get("/api/readiness")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert "risk_lane" in body["failed_checks"]
    assert "commit" in body["build"], "a 503 must still identify the build it came from"


def test_a_stopped_engine_returns_503(client):
    r = _runner(client)
    r._beat_now("risk")
    r.running = False
    try:
        assert client.get("/api/readiness").status_code == 503
    finally:
        r.running = True


def test_an_unreachable_db_returns_503(client, monkeypatch):
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "_probe_db", lambda: (False, "OperationalError: no such table"))
    resp = client.get("/api/readiness")
    assert resp.status_code == 503
    assert "database" in resp.json()["failed_checks"]


def test_the_db_probe_actually_round_trips_to_the_database(client, monkeypatch):
    """Guard against the probe degenerating into `return True, ""` — it has to
    touch the pool, because pool collapse is the failure it is here to catch."""
    import app.main as main_mod
    import app.db.session as sess_mod

    class _Boom:
        def __enter__(self): raise RuntimeError("pool exhausted")
        def __exit__(self, *a): return False

    monkeypatch.setattr(sess_mod, "SessionLocal", lambda: _Boom())
    ok, err = main_mod._probe_db()
    assert ok is False and "pool exhausted" in err


# ── the probe must never be the thing that breaks ───────────────────────────

def test_a_probe_that_raises_still_answers(client, monkeypatch):
    """A 500 from the health endpoint is indistinguishable from a dead process to
    most monitors, and it would take the deploy verification with it."""
    import app.main as main_mod

    def _boom():
        raise RuntimeError("probe bug")

    monkeypatch.setattr(main_mod, "_readiness_payload", _boom)
    resp = client.get("/api/readiness")
    assert resp.status_code == 503
    assert resp.json()["failed_checks"] == ["probe"]
    assert "commit" in resp.json()["build"]


def test_health_reports_armed_state_without_letting_it_affect_the_verdict(client):
    """Disarmed is the default on every boot and a normal resting state — if it
    counted against readiness, every deploy would fail its own health check."""
    r = _runner(client)
    r._beat_now("risk"); r._beat_now("signal")
    r.armed = False
    resp = client.get("/api/readiness")
    assert resp.status_code == 200
    assert resp.json()["engine"]["armed"] is False


def test_lane_ages_distinguish_never_beaten_from_long_ago(client):
    r = _runner(client)
    r._beat_wall.clear()
    assert r.lane_ages() == {"risk": None, "signal": None}
    r._beat_now("risk")
    assert r.lane_ages()["risk"] is not None
    assert r.lane_ages()["signal"] is None
