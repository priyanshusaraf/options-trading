"""Readiness probe: /api/health must be able to say NO.

`/api/health` returned 200 throughout BOTH 2026-07 outages — the .env clobber
(every `GET /` a 404) and the memory-leak/DB-pool collapse. That is why
`scripts/deploy.sh` has to curl `GET /` separately to notice a broken deploy.
A probe that cannot fail is not a probe.

The verdict logic lives in `app/engine/readiness.py` as a pure function — no DB,
no network, no clock of its own — for the same reason `engine/health.py` is pure:
so every state below is a table row rather than an integration setup.

Two rules carry most of the weight here and both are load-bearing:

1. **Only the fast (risk) lane is fatal.** It marks open positions and fires
   SL/TP, so a stall there means real money is unmanaged. The signal lane
   legitimately stops beating overnight (`runner.run_signal_loop` takes the
   `any_open`-false branch and never reaches `_beat_now`), and `deploy.sh`
   refuses to run *during* market hours — so a fatal signal lane would 503 on
   every legitimate deploy.
2. **Ages are wall-clock, never the provider clock.** `_beat_now` stamps
   `provider.now()`, which under the mock provider is *simulated* time that
   jumps a candle per tick. Measuring staleness on that clock reports a
   perfectly healthy dev engine as stale.
"""
from __future__ import annotations

import pytest

from app.engine import readiness as rd


T = rd.Thresholds(risk_stale_seconds=90.0, signal_stale_seconds=600.0,
                  startup_grace_seconds=45.0)


def _eval(**kw):
    base = dict(
        uptime_seconds=3600.0,
        db_ok=True,
        db_error="",
        engine_running=True,
        lane_ages={"risk": 1.0, "signal": 2.0},
        markets_open=True,
        provider_auth_error=False,
        thresholds=T,
    )
    base.update(kw)
    return rd.evaluate(**base)


# ── the happy path still looks like the old contract ────────────────────────

def test_a_healthy_engine_is_ready():
    r = _eval()
    assert r["ready"] is True
    assert r["status"] == "ok"
    assert r["failed_checks"] == []


# ── the fast lane is fatal ──────────────────────────────────────────────────

def test_a_stalled_risk_lane_is_unready():
    """The one the outages needed: stops are not firing on real money."""
    r = _eval(lane_ages={"risk": 91.0, "signal": 2.0})
    assert r["ready"] is False
    assert r["status"] == "unready"
    assert "risk_lane" in r["failed_checks"]
    assert r["loops"]["risk"]["state"] == "stale"


def test_the_risk_lane_budget_is_inclusive_at_the_boundary():
    """Exactly at the budget is not yet stale — a >= here would flap the probe
    once per second against a lane beating at its budget."""
    assert _eval(lane_ages={"risk": 90.0, "signal": 2.0})["ready"] is True
    assert _eval(lane_ages={"risk": 90.001, "signal": 2.0})["ready"] is False


def test_a_risk_lane_that_never_started_is_unready_once_the_grace_is_over():
    """The task died at startup. Before the grace elapses this is 'starting';
    after it, a lane that has never beaten is dead, not merely slow."""
    r = _eval(uptime_seconds=46.0, lane_ages={"risk": None, "signal": None})
    assert r["ready"] is False
    assert r["loops"]["risk"]["state"] == "dead"
    assert "risk_lane" in r["failed_checks"]


def test_the_risk_lane_is_fatal_even_when_markets_are_closed():
    """It has no market-hours branch — it beats every tick, all night. Overnight
    staleness there is a real stall, and overnight is exactly when deploys run."""
    r = _eval(markets_open=False, lane_ages={"risk": 300.0, "signal": None})
    assert r["ready"] is False
    assert "risk_lane" in r["failed_checks"]


# ── the slow lane is NOT fatal ──────────────────────────────────────────────

def test_a_silent_signal_lane_overnight_is_ok_not_degraded():
    """The engine idles with the market shut. This must be plain 'ok': deploys
    happen out of hours and deploy.sh only accepts a healthy probe."""
    r = _eval(markets_open=False, lane_ages={"risk": 1.0, "signal": None})
    assert r["ready"] is True
    assert r["status"] == "ok"
    assert r["loops"]["signal"]["state"] == "idle"


def test_a_signal_lane_that_stopped_beating_overnight_is_idle_not_stale():
    r = _eval(markets_open=False, lane_ages={"risk": 1.0, "signal": 9_000.0})
    assert r["ready"] is True
    assert r["loops"]["signal"]["state"] == "idle"


def test_a_stalled_signal_lane_during_market_hours_is_degraded_but_still_ready():
    """No new entries is bad, but it is not the same emergency as unmanaged
    positions — it must be visible without failing the probe."""
    r = _eval(markets_open=True, lane_ages={"risk": 1.0, "signal": 601.0})
    assert r["ready"] is True
    assert r["status"] == "degraded"
    assert "signal_lane" in r["degraded_checks"]
    assert r["loops"]["signal"]["state"] == "stale"


def test_unknown_market_hours_never_manufactures_a_degraded_signal_lane():
    """If we could not resolve the session (a provider read threw), the honest
    answer is 'no complaint', not a guess — this alarm would cry wolf nightly."""
    r = _eval(markets_open=None, lane_ages={"risk": 1.0, "signal": 9_000.0})
    assert r["status"] == "ok"
    assert r["loops"]["signal"]["state"] == "idle"


# ── startup ─────────────────────────────────────────────────────────────────

def test_a_freshly_booted_process_is_starting_not_unready():
    """deploy.sh restarts the service and polls; a boot that has not reached its
    first beat yet must not read as a failed deploy."""
    r = _eval(uptime_seconds=3.0, lane_ages={"risk": None, "signal": None})
    assert r["ready"] is True
    assert r["status"] == "starting"
    assert r["loops"]["risk"]["state"] == "starting"


def test_starting_is_distinguishable_from_ok_so_a_deploy_can_wait_for_it():
    """deploy.sh must be able to tell 'not up yet' from 'up and healthy',
    otherwise it accepts the first 200 and never actually verifies the lanes."""
    assert _eval(uptime_seconds=3.0, lane_ages={"risk": None, "signal": None})["status"] \
        == "starting"
    assert _eval()["status"] == "ok"


# ── infrastructure ──────────────────────────────────────────────────────────

def test_an_unreachable_db_is_unready():
    r = _eval(db_ok=False, db_error="database is locked")
    assert r["ready"] is False
    assert "database" in r["failed_checks"]
    assert r["db"]["error"] == "database is locked"


def test_a_stopped_engine_is_unready():
    """`runner.running` false means the loops have been told to exit — the
    process is up and serving, which is precisely the failure mode a liveness
    stub cannot see."""
    r = _eval(engine_running=False)
    assert r["ready"] is False
    assert "engine_running" in r["failed_checks"]


def test_an_expired_kite_token_is_degraded_not_unready():
    """The owner re-auths each morning; a stale token must be visible without
    taking the box out of rotation or failing a deploy."""
    r = _eval(provider_auth_error=True)
    assert r["ready"] is True
    assert r["status"] == "degraded"
    assert "provider_auth" in r["degraded_checks"]


def test_a_fatal_check_outranks_a_degraded_one():
    r = _eval(db_ok=False, provider_auth_error=True)
    assert r["status"] == "unready"


def test_every_check_is_reported_not_just_the_first_failure():
    """One 503 that hides three broken things costs an incident its diagnosis."""
    r = _eval(db_ok=False, engine_running=False,
              lane_ages={"risk": 900.0, "signal": 900.0})
    assert set(r["failed_checks"]) == {"database", "engine_running", "risk_lane"}


def test_checks_carry_a_human_reason():
    detail = {c["name"]: c["detail"] for c in _eval(db_ok=False)["checks"]}
    assert detail["database"], "a failed check with no reason is a dead end at 3am"


# ── shape ───────────────────────────────────────────────────────────────────

def test_ages_are_reported_for_the_operator():
    r = _eval(lane_ages={"risk": 1.5, "signal": 2.5})
    assert r["loops"]["risk"]["age_seconds"] == 1.5
    assert r["loops"]["signal"]["age_seconds"] == 2.5
    assert r["loops"]["risk"]["budget_seconds"] == 90.0


def test_a_lane_that_never_beat_reports_a_null_age_not_a_zero():
    """Zero would read as 'beat just now' — the exact inversion of the truth."""
    r = _eval(uptime_seconds=3.0, lane_ages={"risk": None, "signal": None})
    assert r["loops"]["risk"]["age_seconds"] is None


@pytest.mark.parametrize("status", ["ok", "starting", "degraded"])
def test_only_unready_is_not_ready(status):
    """`ready` and `status` must never disagree — deploy.sh keys off one and a
    human reads the other."""
    cases = {
        "ok": {},
        "starting": dict(uptime_seconds=3.0, lane_ages={"risk": None, "signal": None}),
        "degraded": dict(provider_auth_error=True),
    }
    r = _eval(**cases[status])
    assert r["status"] == status and r["ready"] is True
