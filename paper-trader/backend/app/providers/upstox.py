"""Upstox as a DATA connection. It serves candles and quotes; it places no orders.

Declares exactly two capabilities — `HISTORICAL_DATA` and `LIVE_QUOTES` — and a declaration is a
promise `tests/test_provider_conformance.py` holds this adapter to. Nothing here touches
execution, accounts, option chains or streaming.

**"Upstox data, Zerodha execution" is now real** — 2026-08-10. When this adapter was parked, it
said so honestly: `make_broker` took one provider object and derived the execution credential
from it, so selecting this connection would have built no live broker and fallen silently to
paper. The seam that fixes that is the phase-6 execution connection (`app/providers/connection.py`
+ `PT_EXECUTION_PROVIDER`), and it is built. `tests/test_split_routing.py` drives the whole
composition root with this adapter serving prices and Kite placing the order, and asserts the
credential that reaches Zerodha is Zerodha's — not this one's.

What has NOT changed: this adapter still places no orders and declares no execution capability.
`make_broker` refuses a non-Kite connection outright rather than sending its token to a Kite
endpoint. Making Upstox an execution venue is a separate `ExecutionVenue` implementation, and it
is not this file.

The design record is `docs/engineering/reference/upstox-data-adapter-design.md`. Selecting this
adapter in production remains an owner decision; nothing here does it automatically.

Three Upstox differences drive nearly all the code below, and each one fails silently if it is
got wrong:

  1. **The current trading day comes from a different endpoint.** `/v3/historical-candle/...`
     serves the range; `/v3/historical-candle/intraday/...` serves today. A live 15-minute scan
     needs both, merged.
  2. **Intervals are `unit` and `interval` as separate path segments** — our `15minute` is
     `minutes/15`. An unmapped interval is REFUSED, never rounded: 15-minute bars answered with
     1-minute data changes every indicator's horizon and raises nothing.
  3. **Candles are arrays with `+05:30` timestamps, and the ordering is not to be trusted.** We
     normalise, sort and deduplicate rather than depending on the service's order.
"""
from __future__ import annotations

import datetime as dt

from app.core.instruments import Instrument
from app.core.logging import log
from app.providers import capabilities as caps
from app.providers import upstox_instruments as master
from app.providers.base import Candle, MarketDataProvider, ProviderReadError
from app.providers.instrument_resolver import ResolvedInstrument
from app.providers.upstox_transport import UpstoxTransport


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# This repository's interval vocabulary → Upstox v3 (unit, interval). TOTAL and explicit: an
# interval absent from this table is refused rather than approximated. `MAX_DAYS` in
# `backtest/sweep.py` is the vocabulary being mapped.
INTERVAL_MAP: dict[str, tuple[str, int]] = {
    "minute": ("minutes", 1),
    "3minute": ("minutes", 3),
    "5minute": ("minutes", 5),
    "10minute": ("minutes", 10),
    "15minute": ("minutes", 15),
    "30minute": ("minutes", 30),
    "60minute": ("hours", 1),
    "day": ("days", 1),
}

_INTERVAL_SECONDS: dict[str, int] = {"minutes": 60, "hours": 3600, "days": 86400}


class UnsupportedInterval(ProviderReadError):
    """Asked for an interval this connection does not serve.

    A subclass of `ProviderReadError` so callers that fail closed on a read failure also fail
    closed here — but named separately because it is *our* bug, not an outage, and retrying it
    will never succeed.
    """


def interval_path(interval: str) -> tuple[str, int]:
    unit_and_size = INTERVAL_MAP.get(interval)
    if unit_and_size is None:
        raise UnsupportedInterval(
            f"upstox does not serve interval {interval!r}; supported: "
            f"{sorted(INTERVAL_MAP)} — refusing rather than substituting a nearby interval")
    return unit_and_size


def bar_seconds(interval: str) -> int:
    unit, size = interval_path(interval)
    return _INTERVAL_SECONDS[unit] * size


class UpstoxInstrumentResolver:
    """Upstox's names for a canonical instrument.

    Reads **only** `inst.key` and the provider-owned master. It must never read
    `Instrument.spot_symbol` or `option_name` — those are Kite's mapping data that still lives
    on the canonical object, and a second resolver reading them would resolve Upstox to a Kite
    string. `tests/test_instrument_resolution.py` enforces that.
    """

    name = "upstox"

    def resolve_underlying(self, inst: Instrument) -> ResolvedInstrument | None:
        row = master.lookup(getattr(inst, "key", ""))
        if row is None:
            return None
        return ResolvedInstrument(
            canonical_key=row.canonical_key, provider=self.name,
            symbol=row.tradingsymbol, exchange=row.segment)


class UpstoxProvider(MarketDataProvider):
    name = "upstox"
    # Data only. Every other capability is absent because it is not implemented, and a
    # declaration is a promise rather than an aspiration.
    CAPABILITIES = frozenset({caps.HISTORICAL_DATA, caps.LIVE_QUOTES})

    def __init__(self, transport: UpstoxTransport | None = None, token_source=None) -> None:
        self.access_token: str | None = None
        self._transport = transport or UpstoxTransport(
            token_source or (lambda: self.access_token))
        self._resolver = UpstoxInstrumentResolver()

    # ── auth ──────────────────────────────────────────────────────────────
    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    # ── identity ──────────────────────────────────────────────────────────
    def resolve_underlying(self, inst: Instrument) -> ResolvedInstrument | None:
        return self._resolver.resolve_underlying(inst)

    def _instrument_key(self, inst: Instrument) -> str | None:
        row = master.lookup(getattr(inst, "key", ""))
        return row.instrument_key if row else None

    # ── market data ───────────────────────────────────────────────────────
    def get_candles(self, inst: Instrument, interval: str, days: int) -> list[Candle]:
        """Completed bars, oldest first, historical range merged with the current day.

        Raises `ProviderReadError` when the read fails. `[]` means the read SUCCEEDED and this
        instrument had no bars — the distinction the whole failure channel exists for.
        """
        unit, size = interval_path(interval)          # refuses before any request is made
        key = self._instrument_key(inst)
        if not key:
            log.warn("no upstox instrument key", instrument=getattr(inst, "key", "?"))
            return []

        now = self.now()
        to_date = now.date()
        from_date = to_date - dt.timedelta(days=max(1, days))

        rows: list[list] = []
        # Historical: note the path order — {to_date} BEFORE {from_date}. Reversed, this returns
        # an empty window rather than an error, which is the silent wrong answer in this adapter.
        hist = self._transport.get(
            f"/v3/historical-candle/{key}/{unit}/{size}/{to_date.isoformat()}/"
            f"{from_date.isoformat()}")
        rows.extend(_candle_rows(hist))
        # The current trading day is a DIFFERENT endpoint. Without it a live scan never sees
        # today's bars at all, and the newest thing the engine could act on would be yesterday.
        intraday = self._transport.get(
            f"/v3/historical-candle/intraday/{key}/{unit}/{size}")
        intraday_rows = _candle_rows(intraday)

        return _merge(rows, intraday_rows, now=now, seconds=bar_seconds(interval))

    def get_ltp(self, inst: Instrument) -> float | None:
        key = self._instrument_key(inst)
        if not key:
            return None
        resp = self._transport.get("/v3/market-quote/ltp", params={"instrument_key": key})
        for row in resp.data.values():
            if not isinstance(row, dict):
                continue
            px = row.get("last_price", row.get("ltp"))
            if isinstance(px, (int, float)):
                return float(px)
        return None


def _candle_rows(resp) -> list[list]:
    """The `candles` array out of an Upstox envelope, refusing anything else.

    A malformed payload must not read as "no bars": that is the same conflation the failure
    channel was built to end, arriving one layer higher.
    """
    candles = resp.data.get("candles")
    if candles is None:
        return []
    if not isinstance(candles, list):
        raise ProviderReadError(
            f"upstox {resp.endpoint}: candles was {type(candles).__name__}, not a list")
    return candles


def _to_candle(row) -> Candle:
    """`[ts, o, h, l, c, volume, oi]` → `Candle`, with the timestamp normalised to naive IST.

    This codebase's candle epoch is naive IST throughout — `kite.py` strips the tz off every raw
    bar for the same reason, and the frontend re-anchors offset-less times to +05:30. An aware
    timestamp here would be internally consistent and mutually incompatible with every other
    adapter, and would raise at a comparison far from this line.
    """
    if not isinstance(row, (list, tuple)) or len(row) < 6:
        raise ProviderReadError(f"upstox: malformed candle row {row!r}")
    try:
        ts = dt.datetime.fromisoformat(str(row[0]))
        o, h, low, c, vol = (float(row[1]), float(row[2]), float(row[3]),
                             float(row[4]), float(row[5]))
    except ProviderReadError:
        raise
    except Exception as e:                            # noqa: BLE001
        raise ProviderReadError(f"upstox: uninterpretable candle row {row!r}") from e
    ts = (ts.astimezone(IST) if ts.tzinfo is not None else ts).replace(tzinfo=None)
    return Candle(ts=ts, open=o, high=h, low=low, close=c, volume=vol)


def _merge(historical: list, intraday: list, *, now: dt.datetime, seconds: int) -> list[Candle]:
    """Normalise, deduplicate, sort ascending, and drop only the still-forming bar.

    Every step is deliberate, and none of them may be replaced by "trust the response":

      * the two endpoints OVERLAP, so a shared timestamp appears twice — the intraday copy wins,
        being the fresher observation of the same interval;
      * ordering is not guaranteed either way, so we sort rather than reverse-if-needed;
      * the forming bar is decided by the clock and the interval (`ts + interval > now`), not by
        position. "Drop the last element" is Kite's shortcut, correct only because Kite's
        ordering happens to be stable — here it would delete a real completed bar, or keep a
        forming one that repaints every live signal computed on it.
    """
    by_ts: dict[dt.datetime, Candle] = {}
    for row in historical:
        bar = _to_candle(row)
        by_ts[bar.ts] = bar
    for row in intraday:
        bar = _to_candle(row)
        by_ts[bar.ts] = bar                          # intraday wins an overlap, deliberately
    ordered = sorted(by_ts.values(), key=lambda b: b.ts)
    cutoff = now - dt.timedelta(seconds=seconds)
    return [b for b in ordered if b.ts <= cutoff]
