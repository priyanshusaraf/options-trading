"""Measured multiprocess fan-out (Task 6), and the one thing that gates it.

The owner's §5 requirement is not "faster". It is **identical**: every iteration
must produce the same numbers when no parameter changed, because that is what
makes the product's claims checkable at all. "Faster but subtly different
numbers" is the single outcome that is unacceptable, and it is the outcome that
fails silently — an equity curve that moved by a mantissa byte looks like a
strategy, not like a bug.

So the gate here is bit-identity of every stored column against the serial
reference, **including the serialized artifacts** (`curve_json`, `trades_json`,
`bh_curve_json`, `premium_trades_json`), because float formatting drift shows up
in those strings before it shows up in a rounded metric.

The rest of the file guards the things that would make identity untrue later:
isolation between workers, a bounded worker count, streaming (memory that does
not grow with cell count), and a serial path that stays reachable.
"""
from __future__ import annotations

import os
import tracemalloc

import pytest
from sqlalchemy import select

from app.backtest import dataset_store, repository, sweep
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.providers.base import Candle
from app.providers.mock import MockProvider

INTERVALS = ["15minute", "30minute", "60minute"]
# One current receipt authorizes one executable graph.  Multiprocess identity is
# therefore measured across instruments and intervals for that admitted graph;
# multi-strategy refusal has its own causal-boundary regression.
STRATEGIES = ["ir.test.strategy.expanding_z_impulse"]
# Keep six independently addressed cells using verified-charge instruments.
# MCX/BFO futures remain refused by the production charge profile; their refusal
# is tested in test_charge_schedule_correction, not bypassed for worker parity.
INSTRUMENTS = ["NIFTY", "BANKNIFTY"]

# Every column a result actually asserts. Run-local identity is excluded because
# it is *supposed* to differ: row id, run id, and the wall-clock stamp of when
# the arithmetic happened. `from_cache` is excluded for the same reason — it
# records where a row came from, not what it says.
RUN_LOCAL = {"id", "run_id", "computed_at", "from_cache"}
ARTIFACT_COLUMNS = ("curve_json", "bh_curve_json", "trades_json",
                    "premium_trades_json")


class CountingMockProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.candle_reads = []

    def get_candles(self, inst, interval, days, end=None):
        self.candle_reads.append((inst.key, interval, days, end))
        return super().get_candles(inst, interval, days, end=end)


class FullPrecisionMockProvider(CountingMockProvider):
    """The mock rounds every OHLC value to two decimals, which makes it the wrong
    witness for a bit-identity claim: a worker that "normalised" prices with
    `round(x, 2)` would produce identical numbers on this data and the gate would
    pass while being blind to exactly the class of drift it exists to catch
    (verified — that suppression did not redden until this provider existed).

    So perturb every price into the full mantissa. The values remain a valid
    ordered OHLC series; they simply stop being representable in two decimals.
    """

    def get_candles(self, inst, interval, days, end=None):
        import math
        out = []
        for i, c in enumerate(super().get_candles(inst, interval, days, end=end)):
            k = 1.0 + math.pi * 1e-9 * ((i % 7) + 1)
            out.append(Candle(ts=c.ts, open=c.open * k, high=c.high * k,
                              low=c.low * k, close=c.close * k, volume=c.volume))
        return out


@pytest.fixture()
def store_root(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()
    yield tmp_path / "datasets"
    dataset_store.reset_default_store()


def _artifacts(run_id) -> dict:
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == run_id)))
        return {
            (row.instrument_key, row.interval, row.strategy_key): {
                column.name: getattr(row, column.name)
                for column in BacktestResult.__table__.columns
                if column.name not in RUN_LOCAL
            }
            for row in rows
        }


def _sweep(provider, *, workers, instruments=INSTRUMENTS, intervals=INTERVALS,
           admitted_backtest_receipt):
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=intervals, capital=50_000,
        instruments=instruments, provider=provider,
        workers=workers, **admitted_backtest_receipt())
    sweep._join()
    return run_id


# ── the gate: bit-identical output ───────────────────────────────────────────

@pytest.mark.parametrize("workers", [2, 4])
@pytest.mark.parametrize("provider_cls",
                         [FullPrecisionMockProvider, CountingMockProvider])
def test_parallel_output_is_bit_identical_to_serial(provider_cls, workers,
                                                    store_root, admitted_backtest_receipt):
    """The §5 gate. Same frozen datasets, same everything except the process the
    arithmetic ran in."""
    init_db(reset=True)
    serial_id = _sweep(provider_cls(), workers=1,
                       admitted_backtest_receipt=admitted_backtest_receipt)
    serial = _artifacts(serial_id)
    assert len(serial) == len(INSTRUMENTS) * len(INTERVALS) * len(STRATEGIES)
    assert all(a["error"] == "" for a in serial.values()), \
        "every cell must have computed, or this comparison is vacuous"
    assert any(a["trades"] for a in serial.values()), \
        "no cell booked a trade — the comparison would not exercise the maths"

    # A fresh database so the RESULT cache cannot serve the parallel run: what
    # follows is real recomputation in worker processes, not a row copy.
    init_db(reset=True)
    parallel_id = _sweep(provider_cls(), workers=workers,
                         admitted_backtest_receipt=admitted_backtest_receipt)
    parallel = _artifacts(parallel_id)

    assert set(parallel) == set(serial)
    for key in sorted(serial):
        for column in ARTIFACT_COLUMNS:
            assert parallel[key][column] == serial[key][column], (
                f"{key} {column} differs between serial and {workers} workers")
        assert parallel[key] == serial[key], f"{key} differs"
    with SessionLocal() as session:
        run = session.get(BacktestRun, parallel_id)
    assert run.status == "done" and run.done == run.total == len(serial)


def test_parallel_rows_land_in_the_same_order_as_serial(store_root, admitted_backtest_receipt):
    """Completion order is not result order. Workers finish out of order — the
    parent must re-sequence them, or the row ids (which the browser paginates on)
    would depend on which core happened to be free."""
    init_db(reset=True)
    serial_id = _sweep(CountingMockProvider(), workers=1,
                       admitted_backtest_receipt=admitted_backtest_receipt)
    with SessionLocal() as s:
        serial_order = [
            (r.instrument_key, r.interval, r.strategy_key)
            for r in s.scalars(select(BacktestResult)
                               .where(BacktestResult.run_id == serial_id)
                               .order_by(BacktestResult.id))]
    init_db(reset=True)
    parallel_id = _sweep(CountingMockProvider(), workers=4,
                         admitted_backtest_receipt=admitted_backtest_receipt)
    with SessionLocal() as s:
        parallel_order = [
            (r.instrument_key, r.interval, r.strategy_key)
            for r in s.scalars(select(BacktestResult)
                               .where(BacktestResult.run_id == parallel_id)
                               .order_by(BacktestResult.id))]
    assert parallel_order == serial_order


def test_a_pinned_parallel_run_makes_no_provider_call_and_matches_serial(
        store_root, admitted_backtest_receipt):
    """The owner's actual target workload: a warm iteration on stored bytes,
    fanned out. Zero provider reads AND identical numbers, or it is not the same
    run twice."""
    init_db(reset=True)
    cold = CountingMockProvider()
    from app.backtest.universe import liquid_universe
    instruments = [i for i in liquid_universe(cold) if i.key in INSTRUMENTS]
    serial_id = _sweep(cold, workers=1, admitted_backtest_receipt=admitted_backtest_receipt)
    serial = _artifacts(serial_id)
    pins = sweep.resolve_pinned_datasets(cold, instruments, INTERVALS)
    assert len(pins) == len(INSTRUMENTS) * len(INTERVALS)

    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=INTERVALS, capital=50_000,
        instruments=INSTRUMENTS, provider=pinned_provider,
        pinned_datasets=pins, workers=4, **admitted_backtest_receipt())
    sweep._join()

    assert pinned_provider.candle_reads == []
    assert _artifacts(run_id) == serial


# ── isolation: no worker sees another's frame or mutates shared state ────────

def test_no_worker_observes_another_workers_frame(store_root, admitted_backtest_receipt):
    """Every worker builds its own canonical frame from its own candles.

    Proven by construction and then observed: what crosses the boundary is a
    tuple of frozen candles, never a DataFrame, so a worker cannot be handed one
    at all — and the parent never builds one in the parallel path either.
    """
    init_db(reset=True)
    from app.backtest import engine

    built = []
    original = engine._candles_to_df
    parent_pid = os.getpid()

    def spy(candles):
        built.append(os.getpid())
        return original(candles)

    engine._candles_to_df = spy
    try:
        _sweep(CountingMockProvider(), workers=2, instruments=["NIFTY"],
               intervals=["15minute"],
               admitted_backtest_receipt=admitted_backtest_receipt)
    finally:
        engine._candles_to_df = original

    assert built == [], (
        f"the parent process built {len(built)} frame(s) during a parallel "
        f"sweep (pid {parent_pid}); frames belong to workers")


def test_the_payload_that_crosses_the_boundary_carries_no_frame_and_no_session(
        store_root, admitted_backtest_receipt):
    """The seam, asserted directly: candles and plain values only.

    A `_PreparedDataset` caches its frame lazily, so pickling one would ship a
    DataFrame per cell — the accumulation the 2.10 MB/dataset measurement warns
    about. A provider handle or a Session would be worse: unpicklable at best,
    a second writer at worst.
    """
    init_db(reset=True)
    import pickle

    provider = CountingMockProvider()
    from app.backtest.universe import liquid_universe
    inst = [i for i in liquid_universe(provider) if i.key == "NIFTY"][0]
    win = {"lookback_days": None, "start": None, "end": None, "label": "max"}
    prepared = sweep._prepare_dataset(provider, inst, "15minute", win)
    receipt = admitted_backtest_receipt()
    with SessionLocal() as session:
        admitted = repository.load_verified_admission(
            session, owner_id="owner",
            admission_address=receipt["admission_address"])
    slots, payload = sweep._plan_dataset(
        provider, inst, "15minute", 50_000.0, win, [admitted.strategy], prepared,
        owner_id="owner", admission_address=receipt["admission_address"],
        attribution=sweep._admission_attribution(admitted))

    assert payload is not None and len(payload["cells"]) == 1
    assert payload["admission_address"] == receipt["admission_address"]
    assert "frame" not in payload and "provider" not in payload
    assert all(isinstance(c, sweep._FrozenCandle) for c in payload["candles"])
    blob = pickle.dumps(payload)
    assert b"DataFrame" not in blob and b"Session" not in blob
    # Cells carry the parent's resolved params and strategy version, so a worker
    # cannot resolve a different strategy under the same key and stay silent.
    for cell in payload["cells"]:
        assert cell["strategy_version"] and isinstance(cell["params"], dict)


def test_a_worker_whose_strategy_version_disagrees_fails_closed(store_root):
    """The silent-substitution hazard, made loud.

    A spawned worker re-imports the registry, so a strategy `register()`ed at
    runtime — a deployed generated strategy — does not exist there. `get_strategy`
    would hand back the DEFAULT strategy and the run would finish green with the
    wrong logic's numbers filed under the requested key. The worker resolves
    fail-closed and checks the version instead.
    """
    payload = {
        "candles": (), "inst": _stub_instrument(), "interval": "15minute",
        "capital": 50_000.0, "slippage_pct": 0.0005, "bars": 0, "first_ts": 0,
        "last_ts": 0, "effective_days": 0, "clamped": False,
        "owner_id": "owner",
        "admission_address": "sha256:" + "a" * 64,
        "cells": [{"runtime_key": "trend_impulse_v3",
                   "runtime_content_version": "f" * 64,
                   "strategy_key": "trend_impulse_v3",
                   "strategy_version": "f" * 64,
                   "graph_address": None,
                   "attribution_state": "NON_GRAPH",
                   "params": {}, "phash": ""}],
    }
    (row,) = sweep._worker_task(payload)
    assert "parallel worker" in row["error"] and "version" in row["error"]
    assert row["strategy_key"] == "trend_impulse_v3"
    assert "curve_json" not in row      # an error row, not a computed one

    payload["cells"][0]["runtime_key"] = "no_such_strategy"
    payload["cells"][0]["strategy_key"] = "no_such_strategy"
    (row,) = sweep._worker_task(payload)
    assert "parallel worker" in row["error"]
    assert "refusing to substitute" in row["error"]


def _stub_instrument():
    from app.core.instruments import Instrument
    return Instrument("STUB", "STUB", "NSE", "NSE", "STUB", "STUB",
                      lot_size=1, strike_step=1, priority=1,
                      mock_spot=100.0, mock_vol=0.2)


# ── bounded worker count, and the serial path stays reachable ────────────────

def test_worker_count_is_bounded_and_defaults_to_the_serial_path():
    assert sweep._worker_count(None) == 1        # settings default
    assert sweep._worker_count(0) == 1
    assert sweep._worker_count(-4) == 1
    assert sweep._worker_count("nonsense") == 1
    assert sweep._worker_count(10_000) <= sweep.MAX_SWEEP_WORKERS
    assert sweep._worker_count(10_000) <= (os.cpu_count() or 1)
    assert sweep._worker_count(2) == min(2, os.cpu_count() or 1)


def test_worker_count_of_one_takes_the_serial_path_in_this_process(store_root,
                                                                   monkeypatch,
                                                                   admitted_backtest_receipt):
    """Serial is the reference implementation, so it must stay REACHABLE and not
    merely be a pool of size one wearing its name."""
    init_db(reset=True)
    calls = []
    monkeypatch.setattr(
        sweep, "_parallel_cell_values",
        lambda *a, **k: calls.append(a) or iter(()))
    _sweep(CountingMockProvider(), workers=1, instruments=["NIFTY"],
           intervals=["15minute"],
           admitted_backtest_receipt=admitted_backtest_receipt)
    assert calls == []
    with SessionLocal() as s:
        assert s.scalar(select(BacktestResult.bars)
                        .order_by(BacktestResult.id.desc())) > 0


def test_the_settings_knob_selects_the_worker_count(monkeypatch):
    """Two halves: the env var reaches the field, and the field reaches the sweep.

    Deliberately WITHOUT `get_settings.cache_clear()`. Several suites patch the
    cached Settings instance in place (`monkeypatch.setattr(get_settings(), …)`),
    so clearing the cache here discards their patch and reddens an unrelated test
    later in the run — observed, as `test_status_reports_research_flag`.
    """
    from app.core import config

    monkeypatch.setenv("PT_BACKTEST_SWEEP_WORKERS", "3")
    assert config.Settings().backtest_sweep_workers == 3

    monkeypatch.setattr(config.get_settings(), "backtest_sweep_workers", 3)
    assert sweep._worker_count(None) == min(3, os.cpu_count() or 1)
    monkeypatch.setattr(config.get_settings(), "backtest_sweep_workers", 1)
    assert sweep._worker_count(None) == 1


# ── streaming: memory does not grow with cell count ──────────────────────────

def test_peak_memory_does_not_grow_with_the_number_of_cells(store_root,
                                                             admitted_backtest_receipt):
    """50,000 datasets held at once would be ~105 GB at the measured 2.10 MB
    each, so the parent must stream them: bounded in-flight work, and no dataset
    retained after its submission.

    Compared at two cell counts rather than against an absolute number, because
    an absolute peak is a property of this machine and this pandas build."""
    init_db(reset=True)
    provider = CountingMockProvider()

    def peak_for(instruments, intervals):
        tracemalloc.start()
        tracemalloc.reset_peak()
        _sweep(provider, workers=2, instruments=instruments,
               intervals=intervals,
               admitted_backtest_receipt=admitted_backtest_receipt)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return peak

    small = peak_for(["NIFTY"], INTERVALS[:2])        # 2 datasets
    init_db(reset=True)
    large = peak_for(INSTRUMENTS, INTERVALS)          # 6 datasets, 3x the cells

    assert large < small * 2.0, (
        f"peak allocation scaled with cell count: {small/1e6:.1f} MB for 2 "
        f"datasets vs {large/1e6:.1f} MB for 6 — the parent is accumulating")


def test_in_flight_work_is_bounded_by_the_worker_count(store_root, monkeypatch,
                                                        admitted_backtest_receipt):
    init_db(reset=True)
    depths = []

    from concurrent.futures import ProcessPoolExecutor
    original = ProcessPoolExecutor.submit

    def counting_submit(self, fn, *a, **k):
        depths.append(len(self._pending_work_items))
        return original(self, fn, *a, **k)

    monkeypatch.setattr(ProcessPoolExecutor, "submit", counting_submit)
    _sweep(CountingMockProvider(), workers=2,
           admitted_backtest_receipt=admitted_backtest_receipt)
    assert depths, "nothing was submitted — this test would be vacuous"
    assert max(depths) <= 2 * 2, (
        f"up to {max(depths)} datasets were queued at once with 2 workers; "
        f"the parent is not applying back-pressure")


@pytest.mark.parametrize("failure", [RuntimeError("dataset failed"), sweep.ClaimLost("lost")])
def test_parallel_failure_clears_owner_run_process_gauges(store_root, monkeypatch, failure):
    """A failed parallel generator cannot leave capacity reported as consumed."""
    init_db(reset=True)
    run_id = 991

    class Pool:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    import concurrent.futures
    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", Pool)
    if isinstance(failure, sweep.ClaimLost):
        class Guard:
            def ensure_active(self): raise failure
        guard = Guard()
    else:
        guard = None
        def fail_prepare(*_args, **_kwargs): raise failure
        monkeypatch.setattr(sweep, "_prepare_dataset", fail_prepare)
    with pytest.raises(type(failure)):
        list(sweep._parallel_cell_values(object(), [object()], ["day"], 1.0,
                                             {}, [], None, 2, owner_id="owner",
                                             run_id=run_id, guard=guard,
                                             admission_address="test-receipt"))
    assert sweep._measurement_gauges[("active_process_pools", "owner", run_id)] == 0
    assert sweep._measurement_gauges[("inflight_datasets", "owner", run_id)] == 0


# ── the background-thread contract is untouched ──────────────────────────────

def test_a_parallel_sweep_still_reports_and_clears_is_running(store_root,
                                                               admitted_backtest_receipt):
    init_db(reset=True)
    assert not sweep.is_running()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=CountingMockProvider(),
        workers=2,
        **admitted_backtest_receipt())
    sweep._join()
    assert not sweep.is_running()
    with SessionLocal() as s:
        assert s.get(BacktestRun, run_id).status == "done"
    # a second sweep can start: the flag was released, not leaked
    sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=CountingMockProvider(),
        workers=2,
        **admitted_backtest_receipt())
    sweep._join()
    assert not sweep.is_running()
