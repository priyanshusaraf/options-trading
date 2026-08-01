"""Per-instrument feed quality — makes candle validation visible.

`candles.validate_candles` de-duplicates, sorts and repairs bars and hands back
a report of what it did. Without a consumer for that report the engine could
quietly correct a broken feed every couple of seconds for weeks and nobody could
tell. "We are protected from bad data" and "the data is fine" are different
claims, and only the second one is worth acting on.

In-memory and per-process, like `engine/health.HealthTracker` next to it: this
describes the feed as it looks right now, not a history. Two rules it exists to
enforce:

**Never fatal.** A dirty bar the validator successfully repaired is a reason to
go and look, not a reason to take the box out of rotation or fail a deploy.
Readiness reports it as degraded.

**Never noisy.** The live scan revalidates the same series every ~2.5s per
instrument. `record` returns whether this is worth a log line, which is true
only when the anomaly *changes* — otherwise one bad feed reproduces the
2026-07-15 autopsy, where a third of the log was a single repeating line.
"""
from __future__ import annotations

import datetime as dt


class FeedQuality:
    """Tracks which instruments are currently producing anomalous candles."""

    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}

    def record(self, key: str, report, now: dt.datetime) -> bool:
        """Record one validation result. Returns True if the caller should LOG.

        A clean report clears any previous anomaly for the instrument — a
        one-off glitch must not read as an ongoing fault forever, which is the
        failure mode that makes people stop believing a warning light.
        """
        if report.clean:
            self._rows.pop(key, None)
            return False

        detail = report.summary()
        previous = self._rows.get(key)
        self._rows[key] = {
            "detail": detail,
            "at": now.isoformat(),
            "kept": report.kept,
            "total_in": report.total_in,
        }
        # Worth logging only when the problem is new or has changed shape.
        return previous is None or previous["detail"] != detail

    def as_dict(self) -> dict:
        """Instruments currently anomalous. Empty dict = the feed looks clean."""
        return dict(self._rows)

    def anomaly_count(self) -> int:
        return len(self._rows)
