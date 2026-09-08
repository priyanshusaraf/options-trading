"""Dhan as a DATA connection. It serves candles and quotes; it places no orders.

Declares exactly two capabilities — `HISTORICAL_DATA` and `LIVE_QUOTES` — and a declaration is a
promise `tests/test_provider_conformance.py` holds this adapter to. Naming it for execution is
refused by `make_broker`, not half-served.

Written on 2026-08-10 **from https://dhanhq.co/docs/v2/ read at the time of writing**, not from
the shape of the two adapters that came before it. Four differences from Upstox, each of which
returns a plausible wrong answer rather than an error if it is got wrong:

  1. **The response is COLUMNAR.** Dhan sends `{"open": [...], "high": [...], "low": [...],
     "close": [...], "volume": [...], "timestamp": [...]}` — six parallel arrays — where Upstox
     sends a list of rows. A row-oriented parser does not raise on this; it iterates the `open`
     array and reads floats as though they were candles.
  2. **Intervals are integers and the set is INCOMPLETE.** Intraday accepts `1, 5, 15, 25, 60`
     minutes. This system sweeps `3minute`, `10minute` and `30minute` as well, and **Dhan cannot
     serve any of them.** They are refused. Substituting the nearest is the single most
     expensive silent bug available to a data adapter, and "nearest" is available here in a way
     it was not for Upstox, which makes the temptation worse rather than better.
  3. **`toDate` is non-inclusive on the daily endpoint.** Passing today's date returns nothing
     for today. The end of the window is therefore advanced by a day deliberately.
  4. **Timestamps are epoch integers**, not ISO strings with an offset. This repo's candle epoch
     is naive IST throughout, so they are converted through IST and stripped.

There is no hand-typed instrument seed — see `dhan_instruments.py` for why that is a deliberate
correction rather than an omission.
"""
from __future__ import annotations

import datetime as dt

from app.core.instruments import Instrument
from app.core.logging import log
from app.market_data.numeric import NumericIngressError, market_float
from app.providers import capabilities as caps
from app.providers import dhan_instruments as master
from app.providers.base import Candle, MarketDataProvider, ProviderReadError
from app.providers.dhan_transport import DhanTransport
from app.providers.instrument_resolver import ResolvedInstrument

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def candle_from_columns_row(raw_ts, columns: dict, index: int) -> Candle:
    """One dhan parallel-array position → ``Candle``.

    A-02 ingress gate: every OHLCV value passes ``market_float`` — a wire
    boolean is refused with the provider's typed refusal, never coerced to
    ``1.0``/``0.0``.
    """
    try:
        ts = dt.datetime.fromtimestamp(float(raw_ts), tz=IST).replace(tzinfo=None)
        return Candle(ts=ts,
                      open=market_float(columns["open"][index], field="dhan candle open"),
                      high=market_float(columns["high"][index], field="dhan candle high"),
                      low=market_float(columns["low"][index], field="dhan candle low"),
                      close=market_float(columns["close"][index], field="dhan candle close"),
                      volume=market_float(columns["volume"][index], field="dhan candle volume"))
    except NumericIngressError as e:
        raise ProviderReadError(f"dhan {e}") from e

#: This repository's interval vocabulary → Dhan's intraday `interval` minutes. TOTAL for what
#: Dhan serves, and deliberately MISSING `3minute`, `10minute` and `30minute`: the API documents
#: 1/5/15/25/60 and nothing else. An absent entry is refused, never approximated.
INTRADAY_MINUTES: dict[str, int] = {
    "minute": 1,
    "5minute": 5,
    "15minute": 15,
    "60minute": 60,
}

#: Daily bars come from a different endpoint with no interval field at all.
DAILY_INTERVALS = frozenset({"day"})

#: Documented: "Only 90 days of data can be polled at once" on the intraday endpoint.
MAX_INTRADAY_DAYS = 90


class UnsupportedInterval(ProviderReadError):
    """Asked for an interval this connection does not serve.

    A subclass of `ProviderReadError` so callers that fail closed on a read failure also fail
    closed here — but named separately because it is a *coverage* fact, not an outage, and
    retrying it will never succeed. For Dhan this is a real and permanent gap for three of the
    intervals this engine sweeps, and a deployment on Dhan must not be configured to use them.
    """


def supported_intervals() -> frozenset[str]:
    """What this connection can actually scan on.

    Exposed rather than implied because it is narrower than the engine's vocabulary, and a
    deployment bound to this connection has to be able to find that out before it is running.
    """
    return frozenset(INTRADAY_MINUTES) | DAILY_INTERVALS


def _require_interval(interval: str) -> int | None:
    """Minutes for an intraday interval, `None` for daily. Raises for anything else."""
    if interval in DAILY_INTERVALS:
        return None
    minutes = INTRADAY_MINUTES.get(interval)
    if minutes is None:
        raise UnsupportedInterval(
            f"dhan does not serve interval {interval!r}; it serves "
            f"{sorted(supported_intervals())} — refusing rather than substituting a nearby "
            f"interval, which would change every indicator's horizon and raise nothing")
    return minutes


class DhanInstrumentResolver:
    """Dhan's names for a canonical instrument.

    Reads **only** `inst.key` and the provider-owned master. It must never read
    `Instrument.spot_symbol` or `option_name` — those are Kite's mapping data that still lives on
    the canonical object, and a second resolver reading them would resolve Dhan to a Kite string.
    """

    name = "dhan"

    def resolve_underlying(self, inst: Instrument) -> ResolvedInstrument | None:
        row = master.lookup(getattr(inst, "key", ""))
        if row is None:
            return None
        return ResolvedInstrument(
            canonical_key=row.canonical_key, provider=self.name,
            symbol=row.tradingsymbol, exchange=row.exchange_segment)


class DhanProvider(MarketDataProvider):
    name = "dhan"
    # Data only. Every other capability is absent because it is not implemented, and a
    # declaration is a promise rather than an aspiration.
    CAPABILITIES = frozenset({caps.HISTORICAL_DATA, caps.LIVE_QUOTES})

    def __init__(self, transport: DhanTransport | None = None,
                 token_source=None, client_id_source=None) -> None:
        self.access_token: str | None = None
        self.client_id: str | None = None
        self._transport = transport or DhanTransport(
            token_source or (lambda: self.access_token),
            client_id_source or (lambda: self.client_id))
        self._resolver = DhanInstrumentResolver()

    # ── auth ──────────────────────────────────────────────────────────────
    def is_authenticated(self) -> bool:
        # Both, deliberately. A token with no client id authenticates nothing, and reporting
        # that connection as authenticated makes every subsequent refusal look like an outage.
        return bool(self.access_token and self.client_id)

    # ── identity ──────────────────────────────────────────────────────────
    def resolve_underlying(self, inst: Instrument) -> ResolvedInstrument | None:
        return self._resolver.resolve_underlying(inst)

    # ── market data ───────────────────────────────────────────────────────
    def get_candles(self, inst: Instrument, interval: str, days: int) -> list[Candle]:
        """Completed bars, oldest first.

        Raises `ProviderReadError` when the read fails. `[]` means the read SUCCEEDED and this
        instrument had no bars — the distinction the whole failure channel exists for.
        """
        minutes = _require_interval(interval)      # refuses before any request is built
        row = master.lookup(getattr(inst, "key", ""))
        if row is None:
            log.warn("no dhan instrument", instrument=getattr(inst, "key", "?"))
            return []

        now = self.now()
        if minutes is None:
            resp = self._transport.post("/charts/historical", {
                "securityId": row.security_id,
                "exchangeSegment": row.exchange_segment,
                "instrument": row.instrument,
                "fromDate": (now.date() - dt.timedelta(days=max(1, days))).isoformat(),
                # Non-inclusive, documented. Passing today's date returns nothing for today —
                # the whole current session missing, with a successful-looking response.
                "toDate": (now.date() + dt.timedelta(days=1)).isoformat(),
            })
            bar_seconds = 86400
        else:
            window = min(max(1, days), MAX_INTRADAY_DAYS)
            resp = self._transport.post("/charts/intraday", {
                "securityId": row.security_id,
                "exchangeSegment": row.exchange_segment,
                "instrument": row.instrument,
                "interval": minutes,
                "fromDate": (now - dt.timedelta(days=window)).strftime("%Y-%m-%d %H:%M:%S"),
                "toDate": now.strftime("%Y-%m-%d %H:%M:%S"),
            })
            bar_seconds = minutes * 60

        bars = _columns_to_candles(resp)
        # Forming bars are cut by the clock and the interval, never by position. Dhan documents
        # no ordering guarantee, and "drop the last element" is only ever correct by luck.
        cutoff = now - dt.timedelta(seconds=bar_seconds)
        return [b for b in bars if b.ts <= cutoff]

    def get_ltp(self, inst: Instrument) -> float | None:
        row = master.lookup(getattr(inst, "key", ""))
        if row is None:
            return None
        resp = self._transport.post(
            "/marketfeed/ltp", {row.exchange_segment: [int(row.security_id)]})
        segment = resp.data.get(row.exchange_segment)
        if not isinstance(segment, dict):
            return None
        quote = segment.get(str(row.security_id))
        if not isinstance(quote, dict):
            return None
        px = quote.get("last_price")
        return float(px) if isinstance(px, (int, float)) else None


def _columns_to_candles(resp) -> list[Candle]:
    """Six parallel arrays → `Candle`s, oldest first.

    The parallel-array layout is the one thing about this adapter most likely to go wrong
    silently, so every assumption it rests on is checked rather than trusted:

      * a missing `timestamp` array means there are no bars, not that indices line up elsewhere;
      * **ragged arrays are refused.** Zipping to the shortest would build candles from mixed
        rows — an open from one minute and a close from another — which is not a bad candle, it
        is a fabricated one, and no downstream check would ever notice.
    """
    data = resp.data
    stamps = data.get("timestamp")
    if stamps is None:
        return []
    columns = {name: data.get(name) for name in
               ("open", "high", "low", "close", "volume")}
    if not isinstance(stamps, list) or any(not isinstance(v, list) for v in columns.values()):
        raise ProviderReadError(
            f"dhan {resp.endpoint}: expected parallel arrays, got "
            f"{ {k: type(v).__name__ for k, v in ({'timestamp': stamps} | columns).items()} }")
    lengths = {len(stamps)} | {len(v) for v in columns.values()}
    if len(lengths) != 1:
        raise ProviderReadError(
            f"dhan {resp.endpoint}: ragged candle columns {sorted(lengths)} — refusing rather "
            f"than zipping to the shortest, which fabricates candles from mixed rows")

    out: list[Candle] = []
    for i, raw_ts in enumerate(stamps):
        try:
            out.append(candle_from_columns_row(raw_ts, columns, i))
        except ProviderReadError:
            raise
        except Exception as e:                     # noqa: BLE001
            raise ProviderReadError(
                f"dhan {resp.endpoint}: uninterpretable candle at index {i}") from e
    out.sort(key=lambda b: b.ts)
    return out
