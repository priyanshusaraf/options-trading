"""Feed quality has to be VISIBLE, or the validator is just a silent net.

`app/market_data/candles.py` already de-duplicates, sorts and repairs candles,
and returns a report saying what it did. Nothing consumed that report, so the
engine could have been quietly correcting a broken feed every 2.5 seconds for
weeks with nobody able to tell. "We are protected from bad data" and "the data
is fine" are different claims, and only the second one is worth acting on.

Two constraints shape this:

1. **It must never be fatal.** A dirty feed that the validator successfully
   repaired is not a reason to take the box out of rotation or fail a deploy.
   It is a reason to go look. Degraded, not unready.
2. **It must not flood the log.** The live scan revalidates the same series
   every couple of seconds per instrument. Logging every occurrence would
   reproduce the 2026-07-15 autopsy finding, where a third of the journal was
   one repeating line.
"""
from __future__ import annotations

import datetime as dt

from app.market_data.candles import CandleReport
from app.market_data.quality import FeedQuality


def _now(sec: int = 0) -> dt.datetime:
    return dt.datetime(2026, 8, 1, 9, 15, sec)


def _dirty(**kw) -> CandleReport:
    base = dict(total_in=10, kept=9, duplicates=1, reasons={"duplicate": 1})
    base.update(kw)
    return CandleReport(**base)


def _clean() -> CandleReport:
    return CandleReport(total_in=10, kept=10)


# ── recording ───────────────────────────────────────────────────────────────

def test_a_clean_report_records_nothing():
    q = FeedQuality()
    assert q.record("NIFTY", _clean(), _now()) is False
    assert q.as_dict() == {}
    assert q.anomaly_count() == 0


def test_a_dirty_report_is_recorded_and_worth_logging():
    q = FeedQuality()
    assert q.record("NIFTY", _dirty(), _now()) is True
    assert "NIFTY" in q.as_dict()
    assert q.anomaly_count() == 1


def test_the_record_says_what_was_wrong_and_when():
    q = FeedQuality()
    q.record("NIFTY", _dirty(), _now(5))
    row = q.as_dict()["NIFTY"]
    assert "duplicate" in row["detail"].lower()
    assert row["at"] == _now(5).isoformat()


def test_each_instrument_is_tracked_separately():
    q = FeedQuality()
    q.record("NIFTY", _dirty(), _now())
    q.record("SENSEX", _dirty(duplicates=2, reasons={"duplicate": 2}), _now())
    assert set(q.as_dict()) == {"NIFTY", "SENSEX"}
    assert q.anomaly_count() == 2


# ── throttling: the live scan sees the same series every 2.5s ───────────────

def test_the_same_anomaly_twice_is_only_worth_logging_once():
    q = FeedQuality()
    assert q.record("NIFTY", _dirty(), _now(0)) is True
    assert q.record("NIFTY", _dirty(), _now(1)) is False, \
        "a repeating anomaly would flood the log bus"


def test_a_changed_anomaly_is_worth_logging_again():
    """Different problem, or a different scale of the same problem, is news."""
    q = FeedQuality()
    q.record("NIFTY", _dirty(), _now(0))
    assert q.record("NIFTY", _dirty(duplicates=7, reasons={"duplicate": 7}), _now(1)) is True


def test_recovery_is_recorded_so_a_stale_alarm_does_not_persist():
    """Once the feed comes good the instrument must drop out of the report —
    otherwise a one-off glitch reads as an ongoing fault forever."""
    q = FeedQuality()
    q.record("NIFTY", _dirty(), _now(0))
    q.record("NIFTY", _clean(), _now(1))
    assert q.as_dict() == {}
    assert q.anomaly_count() == 0


def test_a_recurrence_after_recovery_logs_again():
    q = FeedQuality()
    q.record("NIFTY", _dirty(), _now(0))
    q.record("NIFTY", _clean(), _now(1))
    assert q.record("NIFTY", _dirty(), _now(2)) is True


# ── it is a warning, never a failure ────────────────────────────────────────

def test_feed_quality_is_reported_by_readiness_as_degraded_not_fatal():
    """A repaired feed is a reason to look, not a reason to 503 — that would
    fail deploys over data the engine already handled correctly."""
    from app.engine import readiness
    r = readiness.evaluate(
        uptime_seconds=3600.0, db_ok=True, engine_running=True,
        lane_ages={"risk": 1.0, "signal": 2.0}, markets_open=True,
        feed_anomalies=3, thresholds=readiness.Thresholds(),
    )
    assert r["ready"] is True
    assert r["status"] == "degraded"
    assert "feed_quality" in r["degraded_checks"]
    assert "feed_quality" not in r["failed_checks"]


def test_a_clean_feed_adds_no_complaint():
    from app.engine import readiness
    r = readiness.evaluate(
        uptime_seconds=3600.0, db_ok=True, engine_running=True,
        lane_ages={"risk": 1.0, "signal": 2.0}, markets_open=True,
        feed_anomalies=0, thresholds=readiness.Thresholds(),
    )
    assert r["status"] == "ok"


def test_feed_anomalies_default_to_none_so_existing_callers_are_unaffected():
    from app.engine import readiness
    r = readiness.evaluate(
        uptime_seconds=3600.0, db_ok=True, engine_running=True,
        lane_ages={"risk": 1.0, "signal": 2.0}, markets_open=True,
        thresholds=readiness.Thresholds(),
    )
    assert r["status"] == "ok"
