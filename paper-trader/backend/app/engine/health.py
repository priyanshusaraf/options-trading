"""
Provider/data health + freshness. The engine must not crash on a Kite/internet
outage, must never fire SL/TP on a stale or missing price, and must show the UI
that data is stale rather than pretending it is live. This module is pure (no DB,
no network) so it is trivially testable; the runner owns one HealthTracker.
"""
from __future__ import annotations

import datetime as dt


def is_stale(last_ok: dt.datetime | None, now: dt.datetime, max_stale_seconds: float) -> bool:
    """True if the last good update is missing or older than the budget."""
    if last_ok is None:
        return True
    return (now - last_ok).total_seconds() > max_stale_seconds


class _Cat:
    def __init__(self) -> None:
        self.last_ok: dt.datetime | None = None
        self.consecutive_failures: int = 0
        self.last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "last_ok": self.last_ok.isoformat() if self.last_ok else None,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
        }


class HealthTracker:
    """Per-category (quote/candle) success/failure tracking. In-memory; resets on
    restart, which is fine — it only reports current live health."""

    def __init__(self) -> None:
        self._cats: dict[str, _Cat] = {"quote": _Cat(), "candle": _Cat()}

    def _cat(self, category: str) -> _Cat:
        return self._cats.setdefault(category, _Cat())

    def record_ok(self, category: str, now: dt.datetime) -> None:
        c = self._cat(category)
        c.last_ok = now
        c.consecutive_failures = 0

    def record_fail(self, category: str, msg: str, now: dt.datetime) -> None:
        c = self._cat(category)
        c.consecutive_failures += 1
        c.last_error = (msg or "")[:200]

    def should_log_failure(self, category: str) -> bool:
        """Throttle repeated identical outage logs: log the 1st failure, then
        every 30th, so a long outage does not flood the log bus."""
        c = self._cat(category)
        return c.consecutive_failures == 1 or c.consecutive_failures % 30 == 0

    def quote_health(self) -> dict:
        return self._cat("quote").to_dict()

    def candle_health(self) -> dict:
        return self._cat("candle").to_dict()

    def as_dict(self) -> dict:
        return {k: v.to_dict() for k, v in self._cats.items()}
