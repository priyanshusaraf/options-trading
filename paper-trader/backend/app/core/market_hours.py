"""
Indian-market session windows, by segment.

Live trading only makes sense while the relevant exchange is open: off-hours,
no new candle prints, so no fresh crossover can fire — polling Kite then just
burns rate-limit quota and logs noise. The engine uses `is_open(segment)` to
skip closed instruments and to idle when nothing is tradable.

Times are IST. We deliberately do NOT hardcode the trading-holiday calendar:
on a holiday Kite simply returns no new candle, which is harmless (the strategy
state just doesn't advance). Weekends are handled.
"""
from __future__ import annotations

import datetime as dt
from datetime import time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

# (open, close) IST per segment. Equity/index F&O share the cash-session window;
# MCX (metals/energy) runs late; NCDEX agri closes in the evening.
SESSIONS: dict[str, tuple[time, time]] = {
    "NFO": (time(9, 15), time(15, 30)),     # NSE index/stock options
    "BFO": (time(9, 15), time(15, 30)),     # BSE options (SENSEX/BANKEX)
    "NSE": (time(9, 15), time(15, 30)),     # NSE cash equity
    "BSE": (time(9, 15), time(15, 30)),     # BSE cash equity
    "NFO_FUT": (time(9, 15), time(15, 30)),
    "MCX": (time(9, 0), time(23, 30)),      # commodities (energy/metals)
    "MCX_FUT": (time(9, 0), time(23, 30)),
    "NCDEX": (time(9, 0), time(17, 0)),     # agri commodities
    "NCDEX_FUT": (time(9, 0), time(17, 0)),
}
_DEFAULT = (time(9, 15), time(15, 30))


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def is_open(segment: str, when: dt.datetime | None = None) -> bool:
    """True if `segment`'s exchange is in session at `when` (default: now, IST)."""
    t = when or now_ist()
    if t.tzinfo is None:
        t = t.replace(tzinfo=IST)
    t = t.astimezone(IST)
    if t.weekday() >= 5:  # Sat/Sun
        return False
    o, c = SESSIONS.get(segment, _DEFAULT)
    return o <= t.time() <= c


def any_open(segments) -> bool:
    """True if at least one of the given segments is currently in session."""
    return any(is_open(seg) for seg in segments)


def minutes_to_close(segment: str, when: dt.datetime | None = None) -> float | None:
    """Minutes until `segment`'s session closes, or None if it's already closed."""
    t = when or now_ist()
    if t.tzinfo is None:
        t = t.replace(tzinfo=IST)
    t = t.astimezone(IST)
    if not is_open(segment, t):
        return None
    _, c = SESSIONS.get(segment, _DEFAULT)
    close_dt = t.replace(hour=c.hour, minute=c.minute, second=0, microsecond=0)
    return max(0.0, (close_dt - t).total_seconds() / 60.0)
