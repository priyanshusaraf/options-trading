"""Earnings-calendar cache — NSE's board-meetings feed, informational only.

NSE has no dedicated "earnings calendar" endpoint; a company's board meeting
called to approve "Quarterly Results" is the de-facto earnings date for Indian
equities. This module fetches that per-symbol, caches it in `earnings_events`,
and reads it back with a staleness guard. Refreshed once a day by
`scripts/refresh_earnings.py` (VPS cron) — the engine and the live loops never
call this; only the /api/earnings endpoint reads the cache.
"""
from __future__ import annotations

import datetime as dt
import logging

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EarningsEvent

log = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
NSE_BOARD_MEETINGS = f"{NSE_BASE}/api/corporate-board-meetings"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# A cache entry older than this is treated as unknown (not shown) rather than
# risk showing a possibly-stale/wrong date — NSE confirms results dates only a
# week or two ahead, so a long-silent cron should go quiet, not stay confident.
STALE_AFTER_DAYS = 7


class NseFetchError(Exception):
    """NSE couldn't be asked (transport/HTTP/parse failure) — distinct from a
    clean "no meeting scheduled" answer."""


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    s.get(NSE_BASE, timeout=10)  # mints the cookies NSE's API requires
    return s


def _is_results_purpose(purpose: str) -> bool:
    return "result" in purpose.lower()


def fetch_board_meeting(symbol: str, sess: requests.Session | None = None,
                         today: dt.date | None = None) -> dict | None:
    """The nearest upcoming "results" board-meeting entry for `symbol`, or None
    if NSE has nothing scheduled yet. Raises NseFetchError on a transport/parse
    failure so the caller can tell "nothing scheduled" from "couldn't ask".

    NSE's feed returns the last ~20 board-meeting rows, most of which are
    ALREADY PAST (last quarter's results, dividends, etc.) — every row must be
    parsed to a real date and filtered to >= today before picking the nearest
    one. `bm_date` is "DD-Mon-YYYY" (e.g. "17-Jul-2026"); comparing those as
    strings is meaningless (month names don't sort chronologically), which is
    exactly the bug this replaced."""
    s = sess or _session()
    today = today or dt.date.today()
    try:
        r = s.get(NSE_BOARD_MEETINGS, params={"index": "equities", "symbol": symbol}, timeout=10)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        raise NseFetchError(f"{symbol}: {e}") from e
    upcoming = []
    for row in rows:
        if not _is_results_purpose(row.get("bm_purpose", "")):
            continue
        try:
            d = dt.datetime.strptime(row["bm_date"], "%d-%b-%Y").date()
        except (ValueError, KeyError, TypeError):
            continue
        if d < today:
            continue
        upcoming.append((d, row.get("bm_purpose", "")))
    if not upcoming:
        return None
    d, purpose = min(upcoming, key=lambda t: t[0])
    return {"date": d.isoformat(), "purpose": purpose}


def refresh_all(session: Session, universe: dict[str, str], today: dt.date | None = None) -> dict:
    """Fetch + upsert every instrument's next results date. `universe` maps
    instrument key -> bare NSE tradingsymbol to query (e.g.
    {"NSE:ANGELONE": "ANGELONE"} — the key carries the exchange prefix the rest
    of the app uses, but NSE's board-meetings API wants the bare symbol). Cache
    rows are keyed by instrument key so /api/earnings matches straight up
    against SignalRow.key. Best-effort per instrument: one NSE failure doesn't
    abort the rest, and leaves that instrument's prior cache row untouched
    (stale-but-present beats wiping known-good data)."""
    sess = _session()
    ok, failed = 0, []
    for key, nse_symbol in universe.items():
        try:
            info = fetch_board_meeting(nse_symbol, sess, today=today)
        except NseFetchError as e:
            failed.append(key)
            log.warning(f"earnings refresh failed for {key} ({nse_symbol}): {e}")
            continue
        ok += 1
        if info is None:
            continue
        event_date = dt.date.fromisoformat(info["date"])  # fetch_board_meeting already parsed/filtered
        row = session.get(EarningsEvent, key)
        if row is None:
            session.add(EarningsEvent(symbol=key, event_date=event_date,
                                       purpose=info["purpose"], fetched_at=dt.datetime.now()))
        else:
            row.event_date = event_date
            row.purpose = info["purpose"]
            row.fetched_at = dt.datetime.now()
    session.commit()
    return {"ok": ok, "failed": failed, "total": len(universe)}


def earnings_map(session: Session, symbols: list[str], now: dt.date | None = None) -> dict[str, dict]:
    """Cached {symbol: {date, purpose}} for `symbols`, excluding cache entries
    too stale to trust and dates that have already passed."""
    now = now or dt.date.today()
    cutoff = dt.datetime.now() - dt.timedelta(days=STALE_AFTER_DAYS)
    if not symbols:
        return {}
    rows = session.execute(
        select(EarningsEvent).where(EarningsEvent.symbol.in_(symbols))
    ).scalars().all()
    out = {}
    for row in rows:
        if row.fetched_at < cutoff or row.event_date < now:
            continue
        out[row.symbol] = {"date": row.event_date.isoformat(), "purpose": row.purpose}
    return out
