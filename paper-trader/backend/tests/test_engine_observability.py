"""audit M1 + P3: the two loops caught exceptions but only logged — a silent death
(process alive, trading stopped) with the operator asleep. Add throttled infra
alerts and per-lane heartbeats + a staleness watchdog."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_infra_alert_is_throttled_per_key():
    r = _runner()
    sent = []
    r.notifier._emit = lambda msg: sent.append(msg)
    now = 1000.0
    assert r._alert_infra("signal_loop", "boom", now=now) is True      # first fires
    assert r._alert_infra("signal_loop", "boom", now=now + 5) is False # within window -> throttled
    assert len(sent) == 1
    later = now + r.params.get("infra_alert_throttle_seconds", 300) + 1
    assert r._alert_infra("signal_loop", "boom", now=later) is True     # window elapsed -> fires
    assert len(sent) == 2


def test_infra_alert_keys_are_independent():
    r = _runner()
    sent = []
    r.notifier._emit = lambda msg: sent.append(msg)
    assert r._alert_infra("signal_loop", "a", now=1000.0) is True
    assert r._alert_infra("risk_loop", "b", now=1000.0) is True         # different key -> fires
    assert len(sent) == 2


def test_heartbeat_and_staleness():
    r = _runner()
    r._beat_now("risk", now=1000.0)
    assert r._lane_stale("risk", max_age=30, now=1020.0) is False       # 20s old, fresh
    assert r._lane_stale("risk", max_age=30, now=1040.0) is True        # 40s old, stale
