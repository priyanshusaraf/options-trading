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


def content_hash(candles) -> str:
    """Stable 128-bit content address over the candle series (ts,o,h,l,c)."""
    h = hashlib.sha256()
    for c in candles:
        h.update(f"{int(c.ts.timestamp())}|{c.open}|{c.high}|{c.low}|{c.close}|".encode())
    return h.hexdigest()[:32]


@dataclasses.dataclass
class Dataset:
    instrument_key: str
    interval: str
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
        bar_count=len(candles),
        start_ts=int(candles[0].ts.timestamp()) if candles else 0,
        end_ts=int(candles[-1].ts.timestamp()) if candles else 0,
        content_hash=content_hash(candles),
        candles=candles,
    )
