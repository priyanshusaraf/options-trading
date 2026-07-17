"""2026-07-15 autopsy log-noise fixes: ~34% of the 3-day journal was UI polling
GETs, and one LT SL-M failure repeated 1,820x/day buried everything else."""
import logging

from app.core.logging import log


def _record(msg: str) -> logging.LogRecord:
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, msg, (), None)


def test_polling_route_access_filter_suppresses_known_noisy_paths():
    from app.main import _PollingRouteFilter
    f = _PollingRouteFilter()
    assert f.filter(_record('"GET /api/execution/state HTTP/1.1" 200 OK')) is False
    assert f.filter(_record('"GET /api/status HTTP/1.1" 200 OK')) is False
    assert f.filter(_record('"GET /api/signals HTTP/1.1" 200 OK')) is False
    # real, rare, mutating routes must still show up
    assert f.filter(_record('"POST /api/positions/manual-open HTTP/1.1" 200 OK')) is True
    assert f.filter(_record('"POST /api/execution/arm HTTP/1.1" 200 OK')) is True


def test_error_ratelimited_emits_once_per_window(monkeypatch):
    calls = []
    monkeypatch.setattr(log, "emit", lambda *a, **k: calls.append((a, k)))
    log._ratelimit_seen.clear()
    for _ in range(5):
        log.error_ratelimited("SL-M stop place failed LT: tick size",
                              key="LT:SLM_FAIL", event="SLM_FAIL")
    assert len(calls) == 1   # only the first of the 5 identical calls actually emits


def test_error_ratelimited_separates_distinct_keys(monkeypatch):
    """Two different instruments failing must BOTH surface — the limiter keys on
    (key, event), it isn't a global mute."""
    calls = []
    monkeypatch.setattr(log, "emit", lambda *a, **k: calls.append((a, k)))
    log._ratelimit_seen.clear()
    log.error_ratelimited("fail LT", key="LT:SLM_FAIL", event="SLM_FAIL")
    log.error_ratelimited("fail SUZLON", key="SUZLON:SLM_FAIL", event="SLM_FAIL")
    assert len(calls) == 2


def test_error_ratelimited_re_emits_after_window(monkeypatch):
    calls = []
    clock = {"t": 1000.0}
    monkeypatch.setattr(log, "emit", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr("time.monotonic", lambda: clock["t"])
    log._ratelimit_seen.clear()
    log.error_ratelimited("fail", key="LT:SLM_FAIL", event="SLM_FAIL", window_seconds=60.0)
    clock["t"] += 30.0
    log.error_ratelimited("fail", key="LT:SLM_FAIL", event="SLM_FAIL", window_seconds=60.0)
    assert len(calls) == 1   # still inside the window — suppressed
    clock["t"] += 31.0
    log.error_ratelimited("fail", key="LT:SLM_FAIL", event="SLM_FAIL", window_seconds=60.0)
    assert len(calls) == 2   # window elapsed — the problem re-surfaces
