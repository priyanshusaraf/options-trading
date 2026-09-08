"""HistoricalDataStore — the reproducibility anchor.

A `DataSource` is a pluggable candle provider (Kite now; option/IV, fundamentals
later). `materialize` fetches once and freezes the result into a content-hashed
`Dataset` that an experiment binds to — so re-running a spec against the same data
is a cache hit, and a Kite backfill/correction (same last timestamp, different bytes)
produces a *different* hash rather than a silent stale reuse. The inner pipeline
reads only Datasets; only the orchestrator's collection phase calls a DataSource.
"""
from __future__ import annotations

import dataclasses
import hashlib
from typing import Protocol

from app.market_data.numeric import market_float


_MARKET_FIELDS = ("open", "high", "low", "close", "volume")


def _identity_rows(candles) -> tuple[tuple[object, dict[str, object]], ...]:
    """Validate OHLCV and return the exact current identity representations.

    Every supplied market field crosses the one numeric ingress once.  Only a
    zero uses the normalized return value, so signed and differently typed zero
    share the current identity while every nonzero accepted representation keeps
    its historical string form.  The source candles themselves remain untouched.
    """
    rows = []
    for index, candle in enumerate(candles):
        identity = {}
        for field in _MARKET_FIELDS:
            if field == "volume" and not hasattr(candle, field):
                # Historical research fixtures predate volume. Absence remains
                # the existing "no volume information" case; any supplied raw
                # volume still crosses the same authoritative numeric rule.
                continue
            raw = getattr(candle, field, None)
            normalized = market_float(
                raw, field=f"research candle {index} {field}")
            identity[field] = 0.0 if normalized == 0.0 else raw
        rows.append((candle, identity))
    return tuple(rows)


def content_hash(candles) -> str:
    """Stable 128-bit content address over the candle series (ts,o,h,l,c)."""
    rows = _identity_rows(candles)
    h = hashlib.sha256()
    for candle, identity in rows:
        h.update(
            f"{int(candle.ts.timestamp())}|{identity['open']}|{identity['high']}|"
            f"{identity['low']}|{identity['close']}|".encode()
        )
    return h.hexdigest()[:32]


@dataclasses.dataclass
class Dataset:
    instrument_key: str
    interval: str
    requested_days: int
    bar_count: int
    start_ts: int
    end_ts: int
    content_hash: str
    candles: list


class DataSource(Protocol):
    def get_candles(self, inst, interval, days): ...


@dataclasses.dataclass
class StaticDataSource:
    """Offline source backed by an in-memory {(instrument_key, interval): candles}
    map — the deterministic source for tests and dry-runs (no network, no DB)."""
    data: dict

    def get_candles(self, inst, interval, days=0):
        key = getattr(inst, "key", inst)
        return self.data.get((key, interval), [])


@dataclasses.dataclass
class KiteDataSource:
    """Thin adapter over the shared MarketDataProvider. Only the orchestrator's
    collection phase uses this; workers read frozen Datasets, never Kite."""
    provider: object

    def get_candles(self, inst, interval, days):
        return self.provider.get_candles(inst, interval, days)


def materialize(source, inst, interval, days: int = 2000) -> Dataset:
    """Fetch candles from `source` and freeze them into a content-hashed Dataset."""
    candles = source.get_candles(inst, interval, days)
    return Dataset(
        instrument_key=getattr(inst, "key", ""),
        interval=interval,
        requested_days=days,
        bar_count=len(candles),
        start_ts=int(candles[0].ts.timestamp()) if candles else 0,
        end_ts=int(candles[-1].ts.timestamp()) if candles else 0,
        content_hash=content_hash(candles),
        candles=candles,
    )
