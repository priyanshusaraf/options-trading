"""Replay mode — re-run a recorded session bar by bar, deterministically.

Phase-1 "validate market data" asked for it, and the reason is diagnostic: when
the engine does something surprising on a live day, the only honest way to
understand it is to feed it that day again, identically, as many times as
needed. A mock market cannot reproduce a real Monday.

**The property that makes this trustworthy is NO LOOK-AHEAD.** `get_candles`
returns history up to and including the cursor and not one bar further. A replay
that leaked future bars would make the engine appear to make decisions it could
never have made live — and it would look like a successful replay, which is the
dangerous part.

**It can never trade.** `is_authenticated()` is False, so the live-order path is
unreachable: `make_broker()` refuses a real LiveBroker without an authenticated
kite provider, and every order endpoint sits behind that. Replay is for reading,
not for doing.

Data format is deliberately boring — a JSON file of
`{"INSTRUMENT_KEY": [{"ts": "...", "open": .., "high": .., "low": .., "close": ..,
"volume": ..}, ...]}` — so a day can be captured from any source (Kite dump, CSV
export, hand-written regression case) without a schema migration.
"""
from __future__ import annotations

import datetime as dt
import json

from app.providers import capabilities as caps
from app.providers.base import Candle, MarketDataProvider


def load_session(path: str) -> dict:
    """Read a replay file into {instrument_key: [Candle, ...]}, oldest first.

    Sorts by timestamp rather than trusting file order: a recording assembled
    from several exports can arrive interleaved, and an out-of-order series would
    silently invert the meaning of "up to the cursor".
    """
    with open(path) as f:
        raw = json.load(f)
    out: dict = {}
    for key, rows in (raw or {}).items():
        candles = []
        for r in rows or []:
            ts = r.get("ts") or r.get("date") or r.get("time")
            when = ts if isinstance(ts, dt.datetime) else dt.datetime.fromisoformat(str(ts))
            candles.append(Candle(
                ts=when.replace(tzinfo=None),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r.get("volume", 0) or 0)))
        out[key] = sorted(candles, key=lambda c: c.ts)
    return out


class ReplayProvider(MarketDataProvider):
    # Deterministic replay of recorded candles: data plus an advanceable clock, no account.
    CAPABILITIES = frozenset({
        caps.HISTORICAL_DATA, caps.LIVE_QUOTES, caps.SIMULATED_CLOCK,
    })
    """Deterministic bar-by-bar replay of a recorded session."""

    name = "replay"

    def __init__(self, path: str) -> None:
        self._data = load_session(path)
        self._cursor = 0
        # The timeline is the union of every instrument's bar times, so
        # instruments with different intervals or gaps stay aligned to one clock
        # rather than each advancing at its own rate.
        stamps = sorted({c.ts for rows in self._data.values() for c in rows})
        self._timeline: list = stamps

    # ── clock ─────────────────────────────────────────────────────────────
    def now(self) -> dt.datetime:
        """The CURRENT BAR's timestamp, not wall-clock time.

        This is what makes market-hours logic, the square-off deadline and every
        staleness check behave as they did on the recorded day. Returning real
        `now()` would replay a Monday's data against a Saturday's clock.
        """
        if not self._timeline:
            return dt.datetime.now()
        i = min(self._cursor, len(self._timeline) - 1)
        return self._timeline[i]

    def advance(self) -> bool:
        """Step one bar. False when the recording is exhausted."""
        if self._cursor >= len(self._timeline) - 1:
            return False
        self._cursor += 1
        return True

    @property
    def progress(self) -> tuple:
        return self._cursor + 1, len(self._timeline)

    # ── market data ───────────────────────────────────────────────────────
    def get_candles(self, inst, interval: str, days: int) -> list:
        """History UP TO AND INCLUDING the cursor. Never further.

        This single line is the whole safety argument for replay mode. Slicing
        past the cursor would hand the engine bars that had not printed yet, and
        the run would still look like a clean replay."""
        key = getattr(inst, "key", inst)
        cutoff = self.now()
        return [c for c in self._data.get(key, []) if c.ts <= cutoff]

    def get_ltp(self, inst) -> float | None:
        bars = self.get_candles(inst, "", 0)
        return bars[-1].close if bars else None

    def get_futures_ltp(self, inst, expiry) -> float | None:
        # A recording carries the underlying series; no separate futures feed is
        # captured, so replay cannot price a contract. None => the caller refuses,
        # which is correct: inventing a basis here would be fabricated data in a
        # tool whose entire purpose is fidelity to what actually happened.
        return None

    def get_option_chain(self, inst, expiry=None):
        return []

    def option_ltp(self, tradingsymbol: str) -> float | None:
        return None

    def is_authenticated(self) -> bool:
        """Always False. Replay must never reach the live-order path — the broker
        factory refuses a real LiveBroker without an authenticated kite provider,
        so this one line keeps a replay from placing an order."""
        return False

    def is_tradable_now(self, inst) -> bool:
        """Defer to the RECORDED clock, so a replay of a live session is 'open'
        for exactly the bars that were in session on the day."""
        from app.core import market_hours
        try:
            return market_hours.is_open(inst.spot_exchange, self.now())
        except Exception:
            return True
