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
    "MCX": (time(9, 0), time(23, 30)),      # commodities (energy/metals) — summer close;
    "MCX_FUT": (time(9, 0), time(23, 30)),  # 23:55 while New York is on standard time (below)
    "NCDEX": (time(9, 0), time(17, 0)),     # agri commodities
    "NCDEX_FUT": (time(9, 0), time(17, 0)),
}
_DEFAULT = (time(9, 15), time(15, 30))
_MCX_SEGMENTS = ("MCX", "MCX_FUT")
_MCX_WINTER_CLOSE = time(23, 55)


def _us_dst(d: dt.date) -> bool:
    """New York daylight time on date `d` (US rule since 2007: second Sunday of
    March → first Sunday of November; judged at noon, like strategy.ta)."""
    def nth_sunday(year: int, month: int, n: int) -> dt.date:
        first = dt.date(year, month, 1)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    return nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)


def session_window(segment: str, day: dt.date) -> tuple[time, time]:
    """(open, close) IST for `segment` on `day`. MCX moves its close with the US DST
    switch: 23:30 while New York is on daylight time, 23:55 otherwise (Nov→Mar) —
    the same schedule `strategy.ta.mcx_close_minute` uses for strategy exits."""
    o, c = SESSIONS.get(segment, _DEFAULT)
    if segment in _MCX_SEGMENTS and not _us_dst(day):
        c = _MCX_WINTER_CLOSE
    return o, c


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def ist_epoch(t) -> int:
    """UNIX epoch (seconds) for a candle/trade timestamp that is in IST.

    Candle timestamps in this app are IST wall-clock: the mock builds them naive,
    and KiteProvider strips the tz keeping the IST wall-clock. The naive value
    must therefore be interpreted as IST — NOT as UTC. The old code did
    `pd.Timestamp(naive).timestamp()`, which pandas treats as UTC, shifting every
    chart bar and backtest trade +5:30 (a 09:15 candle rendered as "2:45pm", a
    15:00 candle as "8:30pm"). Localizing to IST yields the true instant, so any
    viewer renders the real session time.
    """
    if hasattr(t, "to_pydatetime"):        # pandas Timestamp
        t = t.to_pydatetime()
    elif isinstance(t, str):
        t = dt.datetime.fromisoformat(t)
    if t.tzinfo is None:
        t = t.replace(tzinfo=IST)
    return int(t.timestamp())


def is_open(segment: str, when: dt.datetime | None = None) -> bool:
    """True if `segment`'s exchange is in session at `when` (default: now, IST)."""
    t = when or now_ist()
    if t.tzinfo is None:
        t = t.replace(tzinfo=IST)
    t = t.astimezone(IST)
    if t.weekday() >= 5:  # Sat/Sun
        return False
    o, c = session_window(segment, t.date())
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
    _, c = session_window(segment, t.date())
    close_dt = t.replace(hour=c.hour, minute=c.minute, second=0, microsecond=0)
    return max(0.0, (close_dt - t).total_seconds() / 60.0)
