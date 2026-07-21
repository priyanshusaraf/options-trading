"""
Daily earnings-calendar refresh (VPS cron, once/day before market open).

Fetches every NSE/BSE cash-equity instrument's next results date from NSE's
board-meetings feed and upserts it into the `earnings_events` cache table. The
live process only ever reads that cache (see app/api/routes.py::earnings_calendar)
— this script is the only thing that ever calls NSE. A failed run leaves the
prior day's cache untouched rather than wiping known-good data.

Run:

    .venv/bin/python scripts/refresh_earnings.py
"""
import os
import sys

# make `app` importable when this file is run directly as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import earnings                      # noqa: E402
from app.core.instruments import all_instruments    # noqa: E402
from app.db.session import init_db, SessionLocal    # noqa: E402


def main() -> int:
    init_db()
    # key -> bare NSE tradingsymbol (key carries the "NSE:"/"BSE:" prefix the
    # rest of the app uses; NSE's board-meetings API wants the bare symbol).
    stocks = {i.key: i.spot_symbol for i in all_instruments() if i.segment in ("NSE", "BSE")}
    if not stocks:
        print("no NSE/BSE stocks in the universe — nothing to refresh")
        return 0
    with SessionLocal() as session:
        result = earnings.refresh_all(session, stocks)
    msg = f"earnings refresh: {result['ok']}/{result['total']} ok"
    if result["failed"]:
        msg += f", failed: {result['failed']}"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
