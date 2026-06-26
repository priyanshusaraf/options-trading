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
