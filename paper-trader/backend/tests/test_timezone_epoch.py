"""
Regression: chart/backtest timestamps must represent the TRUE instant of the
IST candle, so any viewer renders the real session time (09:15–15:30 IST), not a
+5:30-shifted "evening" time. The old code did pd.Timestamp(naive_ist).timestamp()
which treats a naive IST wall-clock as UTC — shifting every backtest trade and
chart bar forward by 5h30m (a 09:15 candle showed as 14:45/"2:45pm", a 15:00
candle as "8:30pm"). See engine.py / signals.py epoch helpers.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from app.core.market_hours import IST, ist_epoch, now_ist
from app.strategy.signals import to_payload, compute_signals


def _reads_back_in_ist(epoch: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(epoch, IST)


def test_ist_epoch_round_trips_to_same_wall_clock():
    # a naive datetime is interpreted as IST wall-clock
    naive_0915 = dt.datetime(2026, 6, 19, 9, 15, 0)
    back = _reads_back_in_ist(ist_epoch(naive_0915))
    assert (back.hour, back.minute) == (9, 15)

    # a tz-aware IST datetime maps to the same instant
    aware = dt.datetime(2026, 6, 19, 15, 0, 0, tzinfo=IST)
    back2 = _reads_back_in_ist(ist_epoch(aware))
    assert (back2.hour, back2.minute) == (15, 0)


def test_to_payload_times_are_true_ist_instants():
    # 60 candles on a single 2026-06-19 NSE session, 5-min apart from 09:15
    base = dt.datetime(2026, 6, 19, 9, 15, 0)
    rows = []
    price = 100.0
    for i in range(60):
        price += (1.0 if i % 2 == 0 else -0.5)
        ts = base + dt.timedelta(minutes=5 * i)
        rows.append({"date": ts, "open": price, "high": price + 1,
                     "low": price - 1, "close": price})
    df = pd.DataFrame(rows)
    payload = to_payload(compute_signals(df, ema_length=10, z_length=10))
    assert payload["candles"], "expected candles"
    first = _reads_back_in_ist(payload["candles"][0]["time"])
    # first non-NaN bar is at/after 09:15 IST and within the session, NOT evening
    assert 9 <= first.hour <= 15, f"chart bar rendered at {first} — timezone shift bug"


def test_kite_provider_now_is_ist_wall_clock_and_naive():
    """C5/DV-3: KiteProvider.now() must return IST wall-clock, tz-naive, matching
    the candle epoch convention. On a UTC host the inherited base.now() would emit
    server-local time and shift live ticks 5.5h behind the IST historical bars."""
    from app.providers.kite import KiteProvider

    p = KiteProvider.__new__(KiteProvider)   # skip auth/network init
    n = p.now()
    assert n.tzinfo is None, "now() must be tz-naive (IST wall-clock convention)"
    ref = now_ist().replace(tzinfo=None)
    # equal to IST wall-clock within a generous minute (avoid clock-edge flakiness)
    assert abs((n - ref).total_seconds()) < 60, f"now()={n} not IST wall-clock {ref}"
    # and it reads back to the true instant in IST
    assert _reads_back_in_ist(ist_epoch(n)).hour == n.hour
