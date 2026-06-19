"""Provider health tracking + freshness helper (pure)."""
import datetime as dt

from app.engine.health import is_stale, HealthTracker

NOW = dt.datetime(2026, 6, 19, 12, 0, 0)


def test_is_stale():
    assert is_stale(None, NOW, 30) is True
    assert is_stale(NOW - dt.timedelta(seconds=5), NOW, 30) is False
    assert is_stale(NOW - dt.timedelta(seconds=45), NOW, 30) is True


def test_tracker_counts_and_resets():
    h = HealthTracker()
    h.record_fail("quote", "429 too many requests", NOW)
    h.record_fail("quote", "429 too many requests", NOW)
    assert h.quote_health()["consecutive_failures"] == 2
    assert "429" in h.quote_health()["last_error"]
    h.record_ok("quote", NOW)
    assert h.quote_health()["consecutive_failures"] == 0
    assert h.quote_health()["last_ok"] == NOW.isoformat()


def test_should_log_failure_throttles():
    h = HealthTracker()
    logged = [i for i in range(1, 91) if (h.record_fail("candle", "x", NOW) or h.should_log_failure("candle"))]
    # 1st failure + every 30th (1, 30, 60, 90)
    assert logged == [1, 30, 60, 90]


def test_as_dict_shape():
    h = HealthTracker()
    h.record_ok("candle", NOW)
    d = h.as_dict()
    assert set(d) >= {"quote", "candle"}
    assert d["candle"]["last_ok"] == NOW.isoformat()
