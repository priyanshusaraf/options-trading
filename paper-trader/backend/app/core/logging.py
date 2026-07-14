"""
A tiny in-process log bus.

Everything the engine does (signal evaluated, contract picked, order filled,
position closed, capital skipped) is `emit`ed here. Two consumers read it:
  - the Engine/Logs dashboard view (recent ring buffer + live WebSocket push)
  - stdout, for when the backend is run headless

The engine runs as a single asyncio task, so subscribers are invoked
synchronously on the event-loop thread; the WS manager adapts them to async.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Any, Callable

_stdlogger = logging.getLogger("paper_trader")
if not _stdlogger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    _stdlogger.addHandler(_h)
    _stdlogger.setLevel(logging.INFO)

LogEntry = dict[str, Any]


class WarnGate:
    """Collapses a repeating failure into ONE warning per outage episode, with an
    optional recovery note when it clears — so a stuck condition (e.g. an expired
    Kite token making `margins()` fail every poll) doesn't spam the log/ring buffer.
    `fail(key, msg)` warns only on the first failure of an episode; `ok(key, msg)`
    clears it and (optionally) logs recovery, re-arming the next distinct episode."""

    def __init__(self) -> None:
        self._active: set[str] = set()

    def fail(self, key: str, msg: str) -> None:
        if key not in self._active:
            self._active.add(key)
            log.warn(msg)

    def ok(self, key: str, msg: str | None = None) -> None:
        if key in self._active:
            self._active.discard(key)
            if msg:
                log.info(msg)


class LogBus:
    def __init__(self, maxlen: int = 4000) -> None:
        self._buf: deque[LogEntry] = deque(maxlen=maxlen)
        self._subs: list[Callable[[LogEntry], None]] = []
        self._seq = 0

    def emit(self, level: str, msg: str, instrument: str | None = None, **fields: Any) -> LogEntry:
        self._seq += 1
        entry: LogEntry = {
            "seq": self._seq,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": level.upper(),
            "instrument": instrument,
            "msg": msg,
            **fields,
        }
        self._buf.append(entry)
        tag = f"[{instrument}] " if instrument else ""
        getattr(_stdlogger, level.lower(), _stdlogger.info)(f"{tag}{msg}")
        for cb in list(self._subs):
            try:
                cb(entry)
            except Exception:  # a broken subscriber must never break the engine
                pass
        return entry

    # convenience wrappers
    def info(self, msg: str, **kw: Any) -> LogEntry:
        return self.emit("info", msg, **kw)

    def warn(self, msg: str, **kw: Any) -> LogEntry:
        return self.emit("warning", msg, **kw)

    def error(self, msg: str, **kw: Any) -> LogEntry:
        return self.emit("error", msg, **kw)

    def trade(self, msg: str, **kw: Any) -> LogEntry:
        return self.emit("trade", msg, **kw)

    def recent(self, n: int = 300) -> list[LogEntry]:
        return list(self._buf)[-n:]

    def subscribe(self, cb: Callable[[LogEntry], None]) -> None:
        self._subs.append(cb)

    def unsubscribe(self, cb: Callable[[LogEntry], None]) -> None:
        if cb in self._subs:
            self._subs.remove(cb)


# module-level singleton
log = LogBus()
