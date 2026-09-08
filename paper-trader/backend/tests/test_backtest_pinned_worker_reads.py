"""A pinned parallel run reads the dataset store IN THE WORKERS.

Measured cause (hardening record §12): with candles decoded in the parent,
`_prepare_dataset` was 37.9 ms of 52 ms of parent wall time per cell and fan-out
plateaued at 2.08x on four workers, then regressed at eight. The parent was the
serial ceiling, and past four workers it was also pickling candles it had just
decoded.

So on a pinned run the parent sends the worker the dataset *address* and the
worker reads and verifies the bytes itself. The whole risk of that move is the
fail-closed refusals: `_pinned_dataset` refuses five ways, every refusal must
still produce one explanatory result row for its cell with the SAME text, the
run must continue, and there must be no path from a worker back to
`provider.get_candles`. This file is that contract.
"""
from __future__ import annotations

import json
import pickle
import zlib

import pytest
from sqlalchemy import select

from app.backtest import dataset_store, sweep
from app.backtest import repository
from app.backtest.universe import liquid_universe
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from tests.test_backtest_parallel import (CountingMockProvider,
                                          FullPrecisionMockProvider)

INTERVALS = ["15minute", "30minute"]
STRATEGIES = ["ir.test.strategy.expanding_z_impulse"]
WORKERS = 2


@pytest.fixture()
def store_root(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()
    yield tmp_path / "datasets"
    dataset_store.reset_default_store()


def _nifty(provider):
    return [i for i in liquid_universe(provider) if i.key == "NIFTY"][0]


def _cold(provider, admitted_backtest_receipt, intervals=INTERVALS, **kwargs):
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=intervals, capital=50_000,
        instruments=["NIFTY"], provider=provider,
        **kwargs, **admitted_backtest_receipt())
    sweep._join()
    return run_id


def _pinned(provider, pins, *, workers=WORKERS, intervals=INTERVALS,
            admitted_backtest_receipt, **kwargs):
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=intervals, capital=50_000,
        instruments=["NIFTY"], provider=provider,
        pinned_datasets=pins, workers=workers, **kwargs,
        **admitted_backtest_receipt())
    sweep._join()
    return run_id


def _rows(run_id):
    with SessionLocal() as session:
        return list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == run_id)))


def _artifacts(run_id) -> dict:
    excluded = {"id", "run_id", "from_cache", "computed_at"}
    with SessionLocal() as session:
        return {
            (row.instrument_key, row.interval, row.strategy_key): {
                column.name: getattr(row, column.name)
                for column in BacktestResult.__table__.columns
                if column.name not in excluded}
            for row in session.scalars(
                select(BacktestResult).where(BacktestResult.run_id == run_id))}


def _pins_for(provider, intervals=INTERVALS):
    return sweep.resolve_pinned_datasets(provider, [_nifty(provider)], intervals)


def test_phase4_worker_refuses_before_provider_pinned_store_cache_or_strategy(
        monkeypatch):
    """The worker cannot turn a verified-but-unrunnable v2 receipt into work."""
    from tests.test_backtest_admission import _persist_phase4_fixture

    init_db(reset=True)
    registry, wrapper = _persist_phase4_fixture()
    with SessionLocal() as session:
        run = BacktestRun(
            owner_id="owner-a", scope="liquid", intervals="15minute",
            capital=50_000.0, total=1, status="pending",
            admission_address=wrapper.admission_address,
            request_json=json.dumps({
                "scope": "liquid", "intervals": ["15minute"],
                "admission_address": wrapper.admission_address,
            }),
        )
        session.add(run)
        session.flush()
        claim = repository.claim_run(
            session, owner_id="owner-a", run_id=run.id,
            claimed_by="phase4-refusal-test", lease_seconds=60)
        session.commit()
        run_id = run.id
    assert claim is not None

    real_loader = repository.load_verified_admission

    def injected_loader(session, **kwargs):
        return real_loader(session, registry=registry, **kwargs)

    monkeypatch.setattr(repository, "load_verified_admission", injected_loader)
    calls = {name: 0 for name in (
        "provider", "pinned_store", "cache", "worker", "strategy")}

    class ProviderTripwire:
        def get_candles(self, *_args, **_kwargs):
            calls["provider"] += 1
            raise AssertionError("Phase 4 refusal reached provider")

    def forbidden(name):
        def tripwire(*_args, **_kwargs):
            calls[name] += 1
            raise AssertionError(f"Phase 4 refusal reached {name}")
        return tripwire

    monkeypatch.setattr(sweep, "_pinned_worker_task", forbidden("worker"))
    monkeypatch.setattr(sweep, "_worker_task", forbidden("worker"))
    monkeypatch.setattr(sweep, "_pinned_dataset_from_store",
                        forbidden("pinned_store"))
    monkeypatch.setattr(sweep, "_execution_address", forbidden("cache"))
    monkeypatch.setattr(sweep, "_reusable_values", forbidden("cache"))
    monkeypatch.setattr(sweep, "_public_reusable_values", forbidden("cache"))
    monkeypatch.setattr(
        "app.strategy.ir_adapter.IRGraphStrategy", forbidden("strategy"))

    sweep._run(
        run_id, ProviderTripwire(), [], ["15minute"], 50_000.0,
        {"lookback_days": None, "start": None, "end": None, "label": "max"},
        [], None, 1, wrapper.admission_address,
        owner_id="owner-a", claim_token=claim.claim_token,
    )

    assert calls == {name: 0 for name in calls}
    with SessionLocal() as session:
        persisted = session.get(BacktestRun, run_id)
        assert persisted is not None
        assert persisted.status == "error"
        assert persisted.note == "PHASE4_CONTEXT_REQUIRED"
        assert session.scalars(select(BacktestResult).where(
            BacktestResult.run_id == run_id)).all() == []


# ── the seam: an address crosses the boundary, candles do not ────────────────

def test_the_pinned_payload_carries_an_address_and_no_candles(store_root, admitted_backtest_receipt):
    """The whole point of the change, asserted at the seam.

    5,000-bar datasets are ~2 MB each once decoded; pickling them per dataset is
    the cost being removed. An address is 64 bytes.
    """
    init_db(reset=True)
    provider = CountingMockProvider()
    receipt = admitted_backtest_receipt()
    sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"],
                      capital=50_000, instruments=["NIFTY"], provider=provider,
                      **receipt)
    sweep._join()
    pins = _pins_for(provider, ["15minute"])
    dataset_address = pins[sweep.pin_key("NIFTY", "15minute")]

    win = {"lookback_days": None, "start": None, "end": None, "label": "max"}
    inst = _nifty(provider)
    header = sweep._pinned_header(provider, inst, "15minute", win, pins,
                                  clamped=False)
    assert header.error == "" and header.dataset_address == dataset_address
    assert header.candles == (), "the parent decoded the dataset it was told not to"

    with SessionLocal() as session:
        admitted = repository.load_verified_admission(
            session, owner_id="owner",
            admission_address=receipt["admission_address"])
    slots, payload = sweep._plan_dataset(
        provider, inst, "15minute", 50_000.0, win,
        [admitted.strategy], header,
        pinned_address=header.dataset_address, owner_id="owner",
        admission_address=receipt["admission_address"])

    assert payload is not None and payload["address"] == dataset_address
    assert payload["admission_address"] == receipt["admission_address"]
    assert "candles" not in payload and "provider" not in payload
    assert payload["strategy_keys"] == [admitted.strategy.key]
    blob = pickle.dumps(payload)
    assert b"DataFrame" not in blob and b"Session" not in blob
    assert len(blob) < 4096, (
        f"the pinned payload is {len(blob)} bytes — it is carrying data, "
        f"not an address")


def test_the_parent_never_decodes_a_pinned_dataset(store_root, monkeypatch, admitted_backtest_receipt):
    """The measured bottleneck, asserted as an absence.

    `decode_candles` is the decompress, and `DatasetStore.get` is the
    decompress + re-address + manifest check that cost 37.9 ms/cell in the
    parent. Neither may happen in this process during a pinned parallel run.
    """
    init_db(reset=True)
    provider = CountingMockProvider()
    _cold(provider, admitted_backtest_receipt)
    pins = _pins_for(provider)

    decodes, gets = [], []
    real_decode = dataset_store.decode_candles
    real_get = dataset_store.DatasetStore.get
    monkeypatch.setattr(dataset_store, "decode_candles",
                        lambda blob: decodes.append(1) or real_decode(blob))
    monkeypatch.setattr(dataset_store.DatasetStore, "get",
                        lambda self, a: gets.append(a) or real_get(self, a))

    init_db(reset=True)
    warm = CountingMockProvider()
    run_id = _pinned(warm, pins, admitted_backtest_receipt=admitted_backtest_receipt)

    assert warm.candle_reads == []
    assert all(row.error == "" for row in _rows(run_id)), \
        "cells failed, so this measurement would be of nothing"
    assert decodes == [], (
        f"the parent decoded {len(decodes)} dataset(s); that work belongs in "
        f"the workers")
    assert gets == [], f"the parent read the store {len(gets)} time(s)"


# ── every fail-closed refusal survives, worker-side ──────────────────────────

def test_missing_dataset_fails_closed_in_a_worker(store_root, admitted_backtest_receipt):
    init_db(reset=True)
    provider = CountingMockProvider()
    run_id = _pinned(provider, {sweep.pin_key("NIFTY", "15minute"): "a" * 64},
                     intervals=["15minute"],
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert provider.candle_reads == []
    (row,) = _rows(run_id)
    assert row.bars == 0 and row.trades == 0
    assert "pinned" in row.error and "missing" in row.error


def test_revised_content_fails_closed_in_a_worker(store_root, admitted_backtest_receipt):
    """Only the address recomputation catches this — and it now runs in a worker."""
    init_db(reset=True)
    provider = CountingMockProvider()
    _cold(provider, admitted_backtest_receipt, intervals=["15minute"])
    pins = _pins_for(provider, ["15minute"])
    path = dataset_store.get_store().blob_path(
        pins[sweep.pin_key("NIFTY", "15minute")])
    payload = bytearray(zlib.decompress(path.read_bytes()))
    payload[-1] ^= 0x01
    path.write_bytes(zlib.compress(bytes(payload), 6))

    init_db(reset=True)
    warm = CountingMockProvider()
    run_id = _pinned(warm, pins, intervals=["15minute"],
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert warm.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "missing" in row.error


def test_a_dataset_describing_another_series_fails_closed_in_a_worker(store_root, admitted_backtest_receipt):
    """A 30-minute dataset recomputes to its own address perfectly, so only the
    manifest comparison refuses it. That comparison must have moved too."""
    init_db(reset=True)
    provider = CountingMockProvider()
    _cold(provider, admitted_backtest_receipt)
    pins = _pins_for(provider)
    swapped = {sweep.pin_key("NIFTY", "15minute"):
               pins[sweep.pin_key("NIFTY", "30minute")]}

    init_db(reset=True)
    warm = CountingMockProvider()
    run_id = _pinned(warm, swapped, intervals=["15minute"],
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert warm.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "interval" in row.error


def test_a_dataset_from_another_window_fails_closed_in_a_worker(store_root, admitted_backtest_receipt):
    init_db(reset=True)
    provider = CountingMockProvider()
    _cold(provider, admitted_backtest_receipt, intervals=["15minute"])
    pins = _pins_for(provider, ["15minute"])

    init_db(reset=True)
    warm = CountingMockProvider()
    run_id = _pinned(warm, pins, intervals=["15minute"],
                     lookback_days=30,
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert warm.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "window" in row.error


def test_an_unpinned_cell_fails_closed_and_the_run_continues(store_root, admitted_backtest_receipt):
    init_db(reset=True)
    provider = CountingMockProvider()
    _cold(provider, admitted_backtest_receipt)
    pins = _pins_for(provider)
    pins.pop(sweep.pin_key("NIFTY", "30minute"))

    init_db(reset=True)
    warm = CountingMockProvider()
    run_id = _pinned(warm, pins,
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert warm.candle_reads == []
    rows = {row.interval: row for row in _rows(run_id)}
    assert rows["15minute"].error == "" and rows["15minute"].bars > 0
    assert "pinned" in rows["30minute"].error
    assert "no dataset address" in rows["30minute"].error


def test_a_thin_pinned_dataset_fails_closed_in_a_worker(store_root, admitted_backtest_receipt):
    """`MIN_BARS` is a dataset-level refusal too, and it is decided from the
    DECODED bar count — which now only exists in the worker."""
    init_db(reset=True)
    provider = CountingMockProvider()
    inst = _nifty(provider)
    candles = provider.get_candles(inst, "15minute", 5)[:10]
    window = {"lookback_days": None, "start": None, "end": None}
    address = dataset_store.get_store().put(
        candles, provider=provider, instrument=inst, interval="15minute",
        requested_window=window,
        effective_window={"first_ts": 0, "last_ts": 0, "bars": len(candles),
                          "clamped": False})

    init_db(reset=True)
    warm = CountingMockProvider()
    run_id = _pinned(warm, {sweep.pin_key("NIFTY", "15minute"): address},
                     intervals=["15minute"],
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert warm.candle_reads == []
    (row,) = _rows(run_id)
    assert row.error == "insufficient history" and row.bars == 10


def test_a_refused_dataset_beats_a_reusable_result_row(store_root, admitted_backtest_receipt):
    """The one case the address-in-the-payload design could have lost.

    The parent plans a pinned dataset from its manifest, which is cheap and
    unverified, so a cell whose execution address already has a result row could
    be served from the result cache while the BYTES are unservable. Serially
    that cell is a refusal, so it must be a refusal here too — the worker's
    verdict overrides the parent's cache hit.
    """
    init_db(reset=True)
    provider = CountingMockProvider()
    _cold(provider, admitted_backtest_receipt, intervals=["15minute"])
    pins = _pins_for(provider, ["15minute"])
    address = pins[sweep.pin_key("NIFTY", "15minute")]

    # A pinned rerun on the SAME database: the cold run's row is reusable.
    warm = CountingMockProvider()
    reuse_id = _pinned(warm, pins, intervals=["15minute"],
                       admitted_backtest_receipt=admitted_backtest_receipt)
    (reused,) = _rows(reuse_id)
    assert reused.from_cache and reused.error == "", \
        "the result cache did not serve this cell, so the test is vacuous"

    path = dataset_store.get_store().blob_path(address)
    payload = bytearray(zlib.decompress(path.read_bytes()))
    payload[-1] ^= 0x01
    path.write_bytes(zlib.compress(bytes(payload), 6))

    corrupt = CountingMockProvider()
    run_id = _pinned(corrupt, pins, intervals=["15minute"],
                     admitted_backtest_receipt=admitted_backtest_receipt)
    assert corrupt.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "missing" in row.error, (
        "a pinned cell whose bytes no longer verify was served from the result "
        "cache instead of failing closed")


# ── identity is still the gate ───────────────────────────────────────────────

@pytest.mark.parametrize("workers", [2, 4])
def test_pinned_parallel_output_is_bit_identical_to_pinned_serial(workers,
                                                                  store_root, admitted_backtest_receipt):
    """Full-precision candles, because the mock's two-decimal prices made this
    same gate vacuous once already (hardening record §12)."""
    init_db(reset=True)
    cold = FullPrecisionMockProvider()
    _cold(cold, admitted_backtest_receipt)
    pins = _pins_for(cold)
    assert len(pins) == len(INTERVALS)

    init_db(reset=True)
    serial = _artifacts(_pinned(FullPrecisionMockProvider(), pins, workers=1,
                                admitted_backtest_receipt=admitted_backtest_receipt))
    assert len(serial) == len(INTERVALS) * len(STRATEGIES)
    assert all(a["error"] == "" for a in serial.values())
    assert any(a["trades"] for a in serial.values())

    init_db(reset=True)
    parallel = _artifacts(_pinned(FullPrecisionMockProvider(), pins,
                                  workers=workers,
                                  admitted_backtest_receipt=admitted_backtest_receipt))
    assert set(parallel) == set(serial)
    for key in sorted(serial):
        for column in ("curve_json", "bh_curve_json", "trades_json",
                       "premium_trades_json"):
            assert parallel[key][column] == serial[key][column], \
                f"{key} {column} differs between pinned serial and {workers} workers"
        assert parallel[key] == serial[key], f"{key} differs"
