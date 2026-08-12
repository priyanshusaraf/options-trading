"""The local content-addressed dataset store.

Five contracts, one test each:

1. a stored dataset is served with no provider call and round-trips exactly;
2. a blob whose recomputed address disagrees with its filename is refused;
3. a normal refresh sweep still costs its provider reads — the store must never
   silently become a pin (design: "Truthful warm modes");
4. revised history under the same final timestamp becomes a NEW address;
5. an interrupted write leaves nothing readable.
"""
from __future__ import annotations

import datetime as dt
import os
import zlib

import pytest
from sqlalchemy import select

from app.backtest import dataset_store, sweep
from app.backtest.identity import ordered_dataset_address
from app.backtest.universe import liquid_universe
from app.db.models import BacktestResult
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider


class CountingMockProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.candle_reads = []

    def get_candles(self, inst, interval, days, end=None):
        self.candle_reads.append((inst.key, interval, days, end))
        return super().get_candles(inst, interval, days, end=end)


def _nifty(provider):
    return [i for i in liquid_universe(provider) if i.key == "NIFTY"][0]


def _candles(n: int = 120, *, last_close: float | None = None):
    base = dt.datetime(2026, 8, 3, 9, 15)
    rows = []
    for i in range(n):
        close = 100.0 + i * 0.25
        if last_close is not None and i == n - 1:
            close = last_close
        rows.append(dataset_store.StoredCandle(
            ts=base + dt.timedelta(minutes=15 * i),
            open=100.0 + i * 0.25, high=101.0 + i * 0.25,
            low=99.5 + i * 0.25, close=close, volume=1000.0 + i))
    return tuple(rows)


REQUESTED = {"lookback_days": 30, "start": None, "end": None, "fetch_days": 30}


def _effective(candles):
    return {"first_ts": 1, "last_ts": 2, "bars": len(candles), "clamped": False}


def _put(store, provider, instrument, candles):
    return store.put(candles, provider=provider, instrument=instrument,
                     interval="15minute", requested_window=REQUESTED,
                     effective_window=_effective(candles))


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()
    yield dataset_store.get_store()
    dataset_store.reset_default_store()


# ── 1. served from disk, exact round-trip ────────────────────────────────────

def test_stored_dataset_is_served_without_a_provider_call(store):
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    candles = _candles()
    address = _put(store, provider, instrument, candles)
    reads_after_put = len(provider.candle_reads)

    loaded = store.get(address)

    assert loaded is not None
    assert len(provider.candle_reads) == reads_after_put   # zero reads to serve
    assert tuple((c.ts, c.open, c.high, c.low, c.close, c.volume)
                 for c in loaded.candles) == tuple(
        (c.ts, c.open, c.high, c.low, c.close, c.volume) for c in candles)
    assert ordered_dataset_address(
        loaded.candles, provider=loaded.provider, instrument=loaded.instrument,
        interval=loaded.interval, requested_window=loaded.requested_window,
        effective_window=loaded.effective_window) == address
    assert loaded.bars == len(candles)
    assert loaded.address == address


def test_request_index_maps_the_request_to_its_latest_address(store):
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    address = _put(store, provider, instrument, _candles())
    entry = store.lookup(provider=provider, instrument=instrument,
                         interval="15minute", requested_window=REQUESTED)
    assert entry is not None and entry.address == address
    assert entry.fetched_at


# ── 2. corruption containment ────────────────────────────────────────────────

def test_blob_whose_address_no_longer_matches_is_refused(store):
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    address = _put(store, provider, instrument, _candles())
    path = store.blob_path(address)

    # a valid, readable blob whose CONTENT was revised: only the address check
    # can catch this.
    payload = bytearray(zlib.decompress(path.read_bytes()))
    payload[-1] ^= 0x01           # last byte of the final volume field
    path.write_bytes(zlib.compress(bytes(payload), 6))

    assert store.get(address) is None


def test_unreadable_blob_is_refused(store):
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    address = _put(store, provider, instrument, _candles())
    store.blob_path(address).write_bytes(b"not a blob")
    assert store.get(address) is None


# ── 3. a normal refresh still costs its reads ────────────────────────────────

def test_populated_store_does_not_make_a_refresh_sweep_free(tmp_path, monkeypatch):
    """The single most important test in this task.

    A store that silently served a refresh would reintroduce the stale-history
    defect fixed by cache schema v8. A refresh must still read every dataset.
    """
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()
    try:
        init_db(reset=True)
        cold = CountingMockProvider()
        rid = sweep.start_sweep(owner_id="owner",
            scope="liquid", intervals=["15minute", "30minute"], capital=50_000,
            instruments=["NIFTY"], provider=cold)
        sweep._join()
        cold_reads = list(cold.candle_reads)
        assert len(cold_reads) == 2

        # the store really is populated — otherwise the assertion below is vacuous
        stored = dataset_store.get_store().stored_addresses()
        assert len(stored) == 2, stored

        warm = CountingMockProvider()
        rid2 = sweep.start_sweep(owner_id="owner",
            scope="liquid", intervals=["15minute", "30minute"], capital=50_000,
            instruments=["NIFTY"], provider=warm)
        sweep._join()

        assert [r[:2] for r in warm.candle_reads] == [r[:2] for r in cold_reads]
        with SessionLocal() as session:
            assert len(list(session.scalars(select(BacktestResult).where(
                BacktestResult.run_id == rid2)))) == len(list(session.scalars(
                    select(BacktestResult).where(BacktestResult.run_id == rid))))
    finally:
        dataset_store.reset_default_store()


def test_store_failure_never_breaks_a_sweep(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()

    def boom(*_a, **_k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(dataset_store.DatasetStore, "put", boom)
    try:
        init_db(reset=True)
        provider = CountingMockProvider()
        rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"],
                                capital=50_000, instruments=["NIFTY"],
                                provider=provider)
        sweep._join()
        with SessionLocal() as session:
            rows = list(session.scalars(select(BacktestResult).where(
                BacktestResult.run_id == rid)))
        assert len(rows) == 1
        assert rows[0].error == ""
        assert rows[0].bars > 0
    finally:
        dataset_store.reset_default_store()


def test_unaddressable_dataset_degrades_instead_of_killing_the_sweep(
        tmp_path, monkeypatch):
    """The degradation path this task was told to mirror. `LogBus` has `warn`,
    not `warning`, so the existing handler raised AttributeError and took the
    whole sweep down instead of disabling reuse for one cell."""
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()

    def unaddressable(*_a, **_k):
        raise ValueError("candle 3 close must be finite")

    monkeypatch.setattr(sweep, "ordered_dataset_address", unaddressable)
    try:
        init_db(reset=True)
        provider = CountingMockProvider()
        rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"],
                                capital=50_000, instruments=["NIFTY"],
                                provider=provider)
        sweep._join()
        with SessionLocal() as session:
            rows = list(session.scalars(select(BacktestResult).where(
                BacktestResult.run_id == rid)))
        assert len(rows) == 1
        assert rows[0].error == ""
        assert rows[0].params_hash == ""      # reuse disabled for this cell only
    finally:
        dataset_store.reset_default_store()


# ── 4. revised history is a new address, not an overwrite ────────────────────

def test_revised_history_with_the_same_last_timestamp_is_a_new_address(store):
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    original = _candles()
    revised = _candles(last_close=original[-1].close + 1.0)
    assert original[-1].ts == revised[-1].ts

    first = _put(store, provider, instrument, original)
    second = _put(store, provider, instrument, revised)

    assert first != second
    assert store.get(first).candles[-1].close == original[-1].close
    assert store.get(second).candles[-1].close == revised[-1].close
    entry = store.lookup(provider=provider, instrument=instrument,
                         interval="15minute", requested_window=REQUESTED)
    assert entry.address == second        # index points at the newest
    assert len(store.stored_addresses()) == 2


# ── 5. interrupted writes leave nothing readable ─────────────────────────────

def test_interrupted_write_leaves_no_readable_blob(store, monkeypatch):
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    candles = _candles()
    address = ordered_dataset_address(
        candles, provider=provider, instrument=instrument, interval="15minute",
        requested_window=REQUESTED, effective_window=_effective(candles))

    real_replace = os.replace

    def fail_replace(src, dst):
        raise OSError("interrupted")

    monkeypatch.setattr(dataset_store.os, "replace", fail_replace)
    with pytest.raises(OSError):
        _put(store, provider, instrument, candles)
    monkeypatch.setattr(dataset_store.os, "replace", real_replace)

    assert store.get(address) is None
    assert not store.blob_path(address).exists()
    assert store.stored_addresses() == []


def test_a_half_written_temp_file_is_neither_served_nor_counted(store):
    """A concurrent writer's temp file sits in the same shard directory. It must
    not be readable as a dataset and must not shadow the real one."""
    provider = CountingMockProvider()
    instrument = _nifty(provider)
    candles = _candles()
    address = _put(store, provider, instrument, candles)
    path = store.blob_path(address)
    (path.parent / f"{path.name}.tmp-halfwritten").write_bytes(b"\x00\x01")
    (path.parent / f"{store.manifest_path(address).name}.tmp-x").write_bytes(b"{")

    assert store.get(address) is not None            # the real one still serves
    assert store.stored_addresses() == [address]     # the temp is not a dataset


def test_put_recomputes_supplied_address_before_any_filesystem_write(store, monkeypatch):
    provider, instrument, candles = CountingMockProvider(), None, _candles()
    instrument = _nifty(provider)
    writes = []
    monkeypatch.setattr(store, "_atomic_write", lambda *args: writes.append(args))
    with pytest.raises(dataset_store.DatasetStoreError, match="supplied address"):
        _put(store, provider, instrument, candles) if False else store.put(
            candles, provider=provider, instrument=instrument, interval="15minute",
            requested_window=REQUESTED, effective_window=_effective(candles), address="0" * 64)
    assert writes == []


def test_failed_idempotent_retry_never_deletes_prior_valid_artifact(store, monkeypatch):
    provider, instrument, candles = CountingMockProvider(), None, _candles()
    instrument = _nifty(provider)
    address = _put(store, provider, instrument, candles)
    original_blob = store.blob_path(address).read_bytes()
    original_manifest = store.manifest_path(address).read_bytes()
    monkeypatch.setattr(store, "_atomic_write", lambda *_args: (_ for _ in ()).throw(OSError("disk")))
    # A same-content retry returns the already verified immutable artifact, and
    # cannot overwrite or remove either half if the filesystem is failing.
    assert _put(store, provider, instrument, candles) == address
    assert store.blob_path(address).read_bytes() == original_blob
    assert store.manifest_path(address).read_bytes() == original_manifest


def test_legacy_manifest_without_explicit_public_classification_is_refused(store):
    provider, instrument = CountingMockProvider(), None
    instrument = _nifty(provider)
    address = _put(store, provider, instrument, _candles())
    manifest = __import__("json").loads(store.manifest_path(address).read_text())
    manifest.pop("classification")
    store.manifest_path(address).write_text(__import__("json").dumps(manifest))
    assert store.get(address) is None
