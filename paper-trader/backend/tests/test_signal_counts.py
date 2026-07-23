"""signal_counts: per-instrument entry-signal tallies (today + rolling window)."""
import datetime as dt

from app.db.models import SignalEvent
from app.db.session import SessionLocal, init_db
from app.engine import analytics


def test_signal_counts_today_and_rolling():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)   # naive IST
    with SessionLocal() as s:
        for t in (dt.datetime(2026, 6, 26, 9, 30),   # today
                  dt.datetime(2026, 6, 26, 11, 0),   # today
                  dt.datetime(2026, 6, 23, 10, 0),   # 3 days ago (in 7d window)
                  dt.datetime(2026, 6, 16, 10, 0)):  # 10 days ago (outside 7d)
            s.add(SignalEvent(time=t, instrument_key="GOLDM", signal="LONG_ENTRY"))
        s.commit()
        c = analytics.signal_counts(s, now, rolling_days=7)
    assert c["GOLDM"]["today"] == 2
    assert c["GOLDM"]["rolling"] == 3        # the 10-day-old event is excluded
    assert "SILVERM" not in c                 # no events -> absent (caller defaults to 0)


def test_signal_counts_multiple_instruments_and_boundary():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)
    with SessionLocal() as s:
        s.add(SignalEvent(time=dt.datetime(2026, 6, 26, 0, 0),   # exactly start-of-day → today
                          instrument_key="GOLDM", signal="LONG_ENTRY"))
        s.add(SignalEvent(time=dt.datetime(2026, 6, 25, 23, 59),  # yesterday → rolling only
                          instrument_key="GOLDM", signal="SHORT_ENTRY"))
        s.add(SignalEvent(time=dt.datetime(2026, 6, 20, 10, 0),
                          instrument_key="SILVERM", signal="LONG_ENTRY"))
        s.commit()
        c = analytics.signal_counts(s, now, rolling_days=7)
    assert c["GOLDM"] == {"today": 1, "rolling": 2}
    assert c["SILVERM"] == {"today": 0, "rolling": 1}


def test_signal_counts_accepts_aware_now():
    """tz-aware `now` is normalised to naive before comparing (regression guard)."""
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    with SessionLocal() as s:
        s.add(SignalEvent(time=dt.datetime(2026, 6, 26, 9, 30),
                          instrument_key="GOLDM", signal="LONG_ENTRY"))
        s.commit()
        c = analytics.signal_counts(s, now, rolling_days=7)
    assert c["GOLDM"] == {"today": 1, "rolling": 1}
