"""
Sweep orchestrator — runs the strategy backtest across the universe × intervals.

Runs in a background thread (Kite calls are blocking + throttled). Each
(instrument, interval) result is cached in BacktestResult so reruns are instant
and the UI can filter/sort without recomputation.

Computation returns serialized values; it never writes. Results and the run's
progress are persisted together in transactions of at most `BATCH_SIZE` cells,
and progress is DERIVED from the durable result count rather than incremented —
so a result can never be counted before its row exists. That same split is what
lets the cell arithmetic run in worker processes (`workers`), which have no
database session, with output gated bit-identical against the serial path.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from dataclasses import dataclass
from functools import cached_property

from app.backtest.engine import (backtest_charge_segment, compute_signals,
                                 prepare_signal_frame, simulate)
from app.backtest.metrics import BTMetrics
from app.backtest import dataset_store
from app.backtest.identity import (INSTRUMENT_IDENTITY_FIELDS,
                                   PROVIDER_IDENTITY_FIELDS,
                                   execution_result_address,
                                   ordered_dataset_address, source_identity)
from app.backtest.premium import NO_OPTIONS_PREMIUM_ERROR, simulate_premium
from app.core.config import get_settings
from app.backtest.universe import full_universe, liquid_universe
from app.core.logging import log
from app.core.market_hours import ist_epoch
from app.backtest import repository
from app.db.session import SessionLocal
from app.providers.factory import get_provider

# Results and progress are persisted together, in transactions of at most this
# many cells. Two things depend on the number being small and fixed: a crash can
# lose at most this much completed work, and the single SQLite writer is held for
# at most this many inserts while the next cell simulates.
BATCH_SIZE = 10

# Kite's documented max lookback per interval (days). We pull as much as allowed.
# This is the hard ceiling: a requested range is silently CLAMPED to it (and the
# UI discloses the clamp), because Kite sells no history older than this.
MAX_DAYS = {
    "minute": 60, "3minute": 90, "5minute": 100, "10minute": 100,
    "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000,
}
DEFAULT_INTERVALS = ["minute", "5minute", "15minute", "30minute", "60minute", "day"]
MIN_BARS = 60

# Preset lookback windows (days) the UI offers; None = "entire available history".
PRESET_DAYS = {"1w": 7, "2w": 14, "1m": 30, "3m": 90, "6m": 180,
               "1y": 365, "3y": 1095, "7y": 2555, "10y": 3650, "max": None}
_DAYS_TO_LABEL = {v: k for k, v in PRESET_DAYS.items() if v}


def window_label(lookback_days: int | None, start_date: str | None,
                 end_date: str | None) -> str:
    """Human label for a sweep's date window (stored on the run, shown in the UI)."""
    if start_date or end_date:
        return f"{start_date or '…'}→{end_date or 'now'}"
    if lookback_days and lookback_days > 0:
        return _DAYS_TO_LABEL.get(lookback_days, f"{lookback_days}d")
    return "max"


def _fetch_days(interval: str, lookback_days: int | None, start_date: str | None,
                end_date: str | None = None) -> int:
    """How many days to pull for this interval, clamped to Kite's per-interval max.

    For a custom [start,end] window we must fetch enough days to cover the whole
    span back from TODAY (the provider only sells trailing history): the deepest
    candle we need is `start_date`, so we ask for (today - start) days + buffer,
    still clamped to the per-interval ceiling. `_clip_to_window` then trims to the
    requested [start,end]; a window older than the ceiling clips to nothing (see
    `_window_out_of_range`)."""
    cap = MAX_DAYS.get(interval, 200)
    if start_date:
        sd = dt.date.fromisoformat(start_date)
        return max(1, min(cap, (dt.date.today() - sd).days + 2))
    if lookback_days and lookback_days > 0:
        return min(cap, lookback_days)
    return cap


def _is_clamped(interval: str, lookback_days: int | None, start_date: str | None) -> bool:
    """True when the requested span exceeds Kite's per-interval ceiling and was
    therefore silently capped (so the UI can badge the row)."""
    cap = MAX_DAYS.get(interval, 200)
    if start_date:
        sd = dt.date.fromisoformat(start_date)
        return (dt.date.today() - sd).days + 2 > cap
    if lookback_days and lookback_days > 0:
        return lookback_days > cap
    return False   # "max" history asks for the cap itself — not a user clamp


def _window_out_of_range(interval: str, start_date: str | None,
                         end_date: str | None) -> bool:
    """True when a custom window ends BEFORE the earliest candle Kite can serve
    for this interval — i.e. the whole [start,end] is older than the per-interval
    ceiling, so no candle inside it is ever fetchable (a 2018 window on any TF)."""
    if not (start_date or end_date):
        return False
    cap = MAX_DAYS.get(interval, 200)
    earliest_available = dt.date.today() - dt.timedelta(days=cap)
    ed = dt.date.fromisoformat(end_date) if end_date else dt.date.today()
    return ed < earliest_available


def _clip_to_window(candles, start_date: str | None, end_date: str | None):
    """Keep only candles whose date falls inside an explicit custom window."""
    if not (start_date or end_date):
        return candles
    sd = dt.date.fromisoformat(start_date) if start_date else dt.date.min
    ed = dt.date.fromisoformat(end_date) if end_date else dt.date.max
    return [c for c in candles if sd <= c.ts.date() <= ed]

def _requested_window(interval: str, win) -> dict:
    """The request half of a dataset address: what the caller ASKED for.

    Kept in one place because it is computed twice — once when fetching, and once
    when checking that a pinned dataset was fetched for this same request.

    `fetch_days` is deliberately NOT here. It is a fact about *how* we reached the
    data, not about what was requested: for a custom window it is
    `(today - start).days + 2`, because the provider only sells trailing history.
    Including it made an unchanged request resolve to a different address tomorrow
    — an unpinned rerun silently produced different numbers (indistinguishable
    from strategy drift) and a pin from yesterday failed closed, turning a
    "pinned rerun" into a run of all-error cells. `interval` stays out for the
    same reason it always was: the address hashes it separately.

    What actually came back is recorded exactly, and separately, in the effective
    window — which is where a genuinely larger trailing window correctly appears
    as a new dataset. Pinned by tests/test_backtest_request_identity_is_dateless.py.
    """
    return {
        "lookback_days": win.get("lookback_days"),
        "start": win.get("start"),
        "end": win.get("end"),
    }


# ── pinned runs ──────────────────────────────────────────────────────────────
# A pinned run evaluates against dataset addresses the CALLER named. It makes
# zero provider reads, and that claim is truthful only because the caller chose
# the exact bytes. Nothing below is ever reached from an ordinary sweep: a
# refresh must still pay one read per dataset (design: "Truthful warm modes"),
# because no provider API exposes a revision token that could prove historical
# bytes unchanged. Pinning is opt-in at the call site and nowhere else.

def pin_key(instrument_key: str, interval: str) -> str:
    """The address-map key for one (instrument, interval) cell."""
    return f"{instrument_key}|{interval}"


def _is_address(value: str) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value.lower()))


def normalize_pinned_datasets(pinned_datasets) -> dict[str, str]:
    """Validate a caller's pin map, or raise. Malformed input must not reach a
    run row: a half-valid pin map would silently fail closed cell by cell and
    look like missing data rather than a caller mistake."""
    normalized: dict[str, str] = {}
    for key, address in dict(pinned_datasets).items():
        if not isinstance(key, str) or "|" not in key:
            raise RuntimeError(
                f"pinned dataset key must be 'INSTRUMENT|interval', got {key!r}")
        if not _is_address(address):
            raise RuntimeError(
                f"not a dataset address for {key}: {address!r}")
        normalized[key] = address.lower()
    return normalized


def resolve_pinned_datasets(provider, instruments, intervals, *,
                            lookback_days: int | None = None,
                            start_date: str | None = None,
                            end_date: str | None = None,
                            store=None) -> dict[str, str]:
    """Look up the stored dataset address for each requested cell.

    This is the *source-run* half of the pinned API: it turns "the datasets a
    previous sweep of this window fetched" into explicit addresses the caller
    then passes to `start_sweep(pinned_datasets=...)`. It is deliberately a
    separate call — `start_sweep` never invokes it — so that pinning cannot
    happen by omission. Cells with nothing stored are simply absent from the
    result and will fail closed if pinned anyway.
    """
    store = store or dataset_store.get_store()
    win = {"lookback_days": lookback_days, "start": start_date, "end": end_date}
    resolved: dict[str, str] = {}
    for inst in instruments:
        for interval in intervals:
            entry = store.lookup(
                provider=provider, instrument=inst, interval=interval,
                requested_window=_requested_window(interval, win))
            if entry is not None:
                resolved[pin_key(inst.key, interval)] = entry.address
    return resolved


_state_lock = threading.Lock()
_running = False
_worker: "threading.Thread | None" = None


@dataclass(frozen=True)
class _FrozenCandle:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class _PreparedDataset:
    candles: tuple[_FrozenCandle, ...] = ()
    bars: int = 0
    first_ts: int = 0
    last_ts: int = 0
    effective_days: int = 0
    clamped: bool = False
    dataset_address: str = ""
    error: str = ""

    @cached_property
    def frame(self):
        # Lazily prepared: a refresh-warm cache hit validates candle bytes but
        # performs no DataFrame conversion or signal work.
        return prepare_signal_frame(self.candles)


def is_running() -> bool:
    return _running


def _join() -> None:
    """Test helper: block until the running sweep thread completes."""
    t = _worker
    if t is not None:
        t.join()


def start_sweep(*, owner_id: str, scope: str = "liquid", intervals: list[str] | None = None,
                capital: float = 50_000.0, provider=None,
                instruments: list[str] | None = None,
                lookback_days: int | None = None,
                start_date: str | None = None, end_date: str | None = None,
                strategies: list[str] | None = None,
                pinned_datasets=None, workers: int | None = None) -> int:
    """Create a run row, resolve the universe, launch the background thread.
    Returns the new run id. Raises if a sweep is already in flight.

    `instruments`  — restrict the sweep to these instrument keys (e.g. just
                     GOLD/SILVER/COPPER); None/empty = the whole scope.
    `lookback_days`— preset window in days (None = max available history).
    `start_date`/`end_date` — ISO custom window (overrides lookback_days).
    `strategies`   — registry strategy keys to run EACH instrument×interval across;
                     None/empty = just the default strategy (single-strategy sweep).
    `pinned_datasets` — OPT-IN pinned run: `{"NIFTY|15minute": <dataset address>}`,
                     normally built by `resolve_pinned_datasets`. Every cell is
                     served from the local dataset store and the run makes ZERO
                     provider reads; a cell whose pin is missing, corrupt, or
                     describes another series fails closed with an explanatory
                     error rather than falling back to a fetch. Omit it and the
                     sweep behaves exactly as before, provider reads included.
    `workers`      — cell fan-out across processes. None = `backtest_sweep_workers`
                     (default 1 = the serial reference path). Bounded by
                     `MAX_SWEEP_WORKERS` and the CPU count. Output is gated
                     bit-identical against serial."""
    from app.strategy.registry import DEFAULT_STRATEGY_KEY, resolve_strategy
    global _running, _worker
    pinned = normalize_pinned_datasets(pinned_datasets) if pinned_datasets else None
    worker_count = _worker_count(workers)
    # A run left `running` by a dead process is a phantom nothing is driving.
    # Repair it before adding another, so the status endpoint never shows two.
    # Deliberately BEFORE `_running` is set: the guard inside protects a live
    # sweep's own row, and this must not be skipped by the flag we are about to
    # raise ourselves.
    reconcile_stale_runs(owner_id=owner_id)
    with _state_lock:
        if _running:
            raise RuntimeError("a sweep is already running")
        _running = True
    try:
        intervals = [i for i in (intervals or DEFAULT_INTERVALS) if i in MAX_DAYS]
        # resolve + de-dupe strategy keys (preserve request order); default = v3
        req_keys = [k for k in (strategies or [DEFAULT_STRATEGY_KEY]) if k]
        seen: set[str] = set()
        strat_objs = []
        for k in req_keys:
            strat = resolve_strategy(k, owner_id=owner_id)
            if strat.key not in seen:
                seen.add(strat.key)
                strat_objs.append(strat)
        if not strat_objs:
            strat_objs = [resolve_strategy(DEFAULT_STRATEGY_KEY, owner_id=owner_id)]
        provider = provider or get_provider()
        specs = full_universe(provider) if scope == "full" else liquid_universe(provider)
        if instruments:
            want = {k.strip() for k in instruments if k.strip()}
            specs = [i for i in specs if i.key in want]
            if not specs:
                raise RuntimeError(f"none of the requested instruments exist: {sorted(want)}")
        win = {"lookback_days": lookback_days, "start": start_date, "end": end_date,
               "label": window_label(lookback_days, start_date, end_date)}
        total = len(specs) * len(intervals) * len(strat_objs)
        strat_label = "×".join(st.key for st in strat_objs)
        with SessionLocal() as s:
            run = repository.create_run(
                s, owner_id=owner_id, status="running", scope=scope,
                intervals=",".join(intervals), capital=capital, total=total, done=0,
                window=win["label"],
                instruments=",".join(i.key for i in specs) if instruments else "",
                strategies=",".join(st.key for st in strat_objs),
                note=f"{len(specs)} instruments × {len(intervals)} intervals "
                     f"× {len(strat_objs)} strategies · {win['label']}"
                     + (" · pinned" if pinned else "")
                     + (f" · {worker_count} workers" if worker_count > 1 else ""))
            s.commit()
            run_id = run.id
        log.info(f"backtest sweep #{run_id} started — {total} cells, "
                 f"window={win['label']}, strategies={strat_label}"
                 + (f", PINNED to {len(pinned)} stored datasets" if pinned else "")
                 + (f", {worker_count} worker processes" if worker_count > 1 else ""))
        t = threading.Thread(target=_run,
                             args=(run_id, provider, specs, intervals, capital, win,
                                   strat_objs, pinned, worker_count),
                             kwargs={"owner_id": owner_id},
                             daemon=True)
        _worker = t
        t.start()
        return run_id
    except Exception:
        _running = False
        raise


def _run(run_id, provider, specs, intervals, capital, win=None, strategies=None,
         pinned=None, workers=None, *, owner_id: str) -> None:
    global _running
    win = win or {"lookback_days": None, "start": None, "end": None, "label": "max"}
    if not strategies:
        from app.strategy.registry import DEFAULT_STRATEGY_KEY, resolve_strategy
        strategies = [resolve_strategy(DEFAULT_STRATEGY_KEY, owner_id=owner_id)]
    batch: list[dict] = []
    try:
        for values in _cell_values(provider, specs, intervals, capital,
                                   win, strategies, pinned, workers, owner_id=owner_id):
            batch.append(values)
            if len(batch) >= BATCH_SIZE:
                _commit_batch(run_id, batch, owner_id=owner_id)
                batch = []
        # The terminal status rides the final batch: results, progress and the
        # run's completion are one transaction, so a run can never be `done`
        # while its last ten rows are missing.
        _commit_batch(run_id, batch, owner_id=owner_id, status="done")
        log.info(f"backtest sweep #{run_id} complete")
    except Exception as e:  # never let the thread die silently
        # `batch` is deliberately dropped: those cells were never durable, and
        # progress is derived from what IS durable, so nothing over-reports.
        _commit_batch(run_id, [], owner_id=owner_id, status="error", note=str(e))
        log.error(f"backtest sweep #{run_id} failed: {e}")
    finally:
        _running = False


def _cell_values(provider, specs, intervals, capital, win, strategies,
                 pinned, workers, *, owner_id: str):
    """Yield one serialized result payload per cell, in request order.

    Serial by default and by reference: `workers <= 1` walks the cells in this
    process, which is the implementation every parallel result is compared
    against (`tests/test_backtest_parallel.py`).
    """
    count = _worker_count(workers)
    if count > 1:
        yield from _parallel_cell_values(
            provider, specs, intervals, capital, win, strategies, pinned, count,
            owner_id=owner_id)
        return
    for inst in specs:
        for interval in intervals:
            prepared = _prepare_dataset(provider, inst, interval, win,
                                        pinned=pinned)
            for strat in strategies:
                yield _one(provider, inst, interval, capital, win, strat,
                           prepared=prepared, owner_id=owner_id)


# ── multiprocess fan-out (Task 6) ────────────────────────────────────────────
# Justified by measurement: a cell is 84.7 ms and the owner's full-universe warm
# pass is 16,000 cells, so serial is 22 minutes against a 1.4-minute target.
#
# What crosses a process boundary is a dict of plain values in and a dict of
# already-serialized column values out. Nothing shared, nothing mutable, no
# database session, no provider handle.
#
# On a REFRESH the parent must fetch, so candles cross the boundary. On a PINNED
# run only the dataset ADDRESS crosses and the worker reads the store itself:
# that read — decompress, re-address, check the manifest — was 37.9 ms of the
# parent's 52 ms per cell and capped fan-out at 2.08x (hardening record §12).
#
# The parent still keeps the throttled provider read, the store WRITE and the
# reusable-result lookup. The last of those is deliberate: moving it into workers
# would make their visibility of already-written rows depend on batch timing,
# which is exactly the class of difference the bit-identity gate exists to forbid.

MAX_SWEEP_WORKERS = 32


def _worker_count(workers=None) -> int:
    """Resolve and BOUND the worker count. 1 means the serial reference path."""
    import os
    if workers is None:
        workers = get_settings().backtest_sweep_workers
    try:
        n = int(workers)
    except (TypeError, ValueError):
        n = 1
    if n <= 1:
        return 1
    return max(1, min(n, MAX_SWEEP_WORKERS, os.cpu_count() or 1))


def _worker_task(payload: dict) -> list[dict]:
    """Compute every un-cached strategy for ONE dataset. Runs in a worker process.

    The dataset is the unit of work, not the cell, so the canonical frame is still
    built exactly once per dataset (the Task-2 invariant) and the candles cross
    the boundary once rather than once per strategy.

    Strategy resolution is FAIL-CLOSED here and the version is checked against the
    parent's. `get_strategy` would silently substitute the default strategy in a
    worker whose registry differs from the parent's — a runtime-registered
    generated strategy does not exist in a spawned process — and the run would
    finish green with a different strategy's numbers under the requested key.
    """
    from app.strategy.registry import StrategyNotFound, resolve_strategy
    candles = payload["candles"]
    inst, interval = payload["inst"], payload["interval"]
    meta = dict(bars=payload["bars"], first_ts=payload["first_ts"],
                last_ts=payload["last_ts"],
                effective_days=payload["effective_days"],
                clamped=payload["clamped"])
    frame = None
    out: list[dict] = []
    for cell in payload["cells"]:
        try:
            owner_id = payload["owner_id"]
            try:
                strat = resolve_strategy(cell["strategy_key"], owner_id=owner_id)
            except StrategyNotFound:
                if not cell["strategy_key"].startswith("gen_"):
                    raise
                from app.core.generated_strategies import register_all
                from app.db.session import SessionLocal
                with SessionLocal() as session:
                    register_all(session, owner_id=owner_id)
                strat = resolve_strategy(cell["strategy_key"], owner_id=owner_id)
            if strat.version != cell["strategy_version"]:
                raise RuntimeError(
                    f"strategy {cell['strategy_key']!r} is version "
                    f"{strat.version[:12]}… in this worker but "
                    f"{cell['strategy_version'][:12]}… in the sweep")
        except Exception as exc:
            out.append(_result_values(
                inst, interval, None, [], meta["bars"],
                clamped=meta["clamped"], strategy_key=cell["strategy_key"],
                error=f"parallel worker: {exc}"))
            continue
        if frame is None:
            frame = prepare_signal_frame(candles)
        out.append(_compute_values(
            candles, inst, interval, payload["capital"], strat, cell["params"],
            payload["slippage_pct"], cell["phash"], frame=frame, **meta))
    return out


_WORKER_STORES: dict[str, dataset_store.DatasetStore] = {}


def _worker_store(root: str) -> dataset_store.DatasetStore:
    """One store handle per (process, root). The root is carried in the payload
    rather than resolved from settings, so a worker reads the same directory the
    parent pinned against and cannot silently address a different corpus."""
    store = _WORKER_STORES.get(root)
    if store is None:
        store = _WORKER_STORES[root] = dataset_store.DatasetStore(root)
    return store


def _pinned_worker_task(payload: dict) -> dict:
    """Read, VERIFY and simulate one pinned dataset. Runs in a worker process.

    This is the lever measured in hardening record §12: with the candles decoded
    in the parent, `_prepare_dataset` was 37.9 ms of the parent's 52 ms per cell
    and fan-out plateaued at 2.08x. Only the address crosses the boundary now, so
    the decompress + re-address + manifest check happen once per dataset in the
    process that is about to use them.

    Every refusal of `_pinned_dataset` is reproduced here, in the same order and
    with the same text, by calling the same function. A refusal is returned as a
    DATASET-level verdict rather than a per-cell one, because it must also
    override a result-cache hit the parent took from the unverified manifest:
    serially that cell is an explanatory error row, so it is one here too.

    There is no provider in this payload and no way to reach one.
    """
    inst, interval = payload["inst"], payload["interval"]
    prepared = _pinned_dataset_from_store(
        lambda address: _worker_store(payload["store_root"]).get(address),
        address=payload["address"],
        key=pin_key(getattr(inst, "key", ""), interval),
        provider_identity=payload["provider_identity"],
        instrument_identity=source_identity(
            inst, fields=INSTRUMENT_IDENTITY_FIELDS),
        interval=interval, requested_window=payload["requested_window"],
        clamped=payload["clamped"])
    if prepared.error:
        return {"refused": True, "rows": [
            _result_values(inst, interval, None, [], prepared.bars,
                           clamped=prepared.clamped, strategy_key=key,
                           error=prepared.error)
            for key in payload["strategy_keys"]]}
    return {"refused": False, "rows": _worker_task(dict(
        payload, candles=prepared.candles, bars=prepared.bars,
        first_ts=prepared.first_ts, last_ts=prepared.last_ts,
        effective_days=prepared.effective_days, clamped=prepared.clamped))}


def _plan_dataset(provider, inst, interval, capital, win, strategies, prepared,
                  *, pinned_address: str = "", owner_id: str):
    """Split one dataset's cells into values this process already has and cells a
    worker must compute — keeping the ORDER the serial path would produce.

    `pinned_address` switches the payload from candles to an address. A pinned
    dataset is submitted even when every cell was served from the result cache:
    the parent planned it from an UNVERIFIED manifest, so something must still
    prove the bytes, and a worker's refusal replaces those cached values.
    """
    slots: list[tuple[str, dict | None]] = []
    cells: list[dict] = []
    slippage_pct = float(get_settings().backtest_slippage_pct)
    for strat in strategies:
        if prepared.error:
            slots.append(("ready", _result_values(
                inst, interval, None, [], prepared.bars,
                clamped=prepared.clamped, strategy_key=strat.key,
                error=prepared.error)))
            continue
        phash = _execution_address(prepared, inst, interval, capital, win, strat,
                                   slippage_pct)
        cached = _reusable_values(inst, interval, phash, prepared.last_ts, owner_id=owner_id)
        if cached is not None:
            slots.append(("ready", cached))
            continue
        slots.append(("worker", None))
        cells.append({"strategy_key": strat.key,
                      "strategy_version": strat.version,
                      "params": dict(strat.default_params),
                      "phash": phash})
    payload = None
    if pinned_address:
        payload = {"pinned": True, "address": pinned_address,
                   "owner_id": owner_id,
                   "store_root": str(dataset_store.get_store().root),
                   "provider_identity": source_identity(
                       provider, fields=PROVIDER_IDENTITY_FIELDS),
                   "requested_window": _requested_window(interval, win),
                   "clamped": _is_clamped(interval, win.get("lookback_days"),
                                          win.get("start")),
                   "strategy_keys": [st.key for st in strategies],
                   "inst": inst, "interval": interval, "capital": capital,
                   "slippage_pct": slippage_pct, "cells": cells}
    elif cells:
        payload = {"candles": prepared.candles, "inst": inst,
                   "owner_id": owner_id,
                   "interval": interval, "capital": capital,
                   "slippage_pct": slippage_pct, "bars": prepared.bars,
                   "first_ts": prepared.first_ts, "last_ts": prepared.last_ts,
                   "effective_days": prepared.effective_days,
                   "clamped": prepared.clamped, "cells": cells}
    return slots, payload


def _merge(slots, computed) -> list[dict]:
    it = iter(computed)
    return [value if kind == "ready" else next(it) for kind, value in slots]


def _drain(slots, future) -> list[dict]:
    """One dataset's results, in slot order, from whichever task computed it."""
    if future is None:
        return _merge(slots, ())
    result = future.result()
    if isinstance(result, dict):          # a pinned dataset's verdict
        if result["refused"]:
            # The dataset itself is unservable: every cell of it is that
            # refusal, including cells the parent had planned from the cache.
            return result["rows"]
        return _merge(slots, result["rows"])
    return _merge(slots, result)


def _parallel_cell_values(provider, specs, intervals, capital, win, strategies,
                          pinned, workers, *, owner_id: str):
    """Yield the same values as the serial path, in the same order, computed in
    `workers` processes.

    Datasets are STREAMED: at most `workers * 2` are in flight at once, so peak
    memory is bounded by the worker count and not by the cell count. At the
    measured 2.10 MB/dataset, holding all 50,000 would be ~105 GB.
    """
    import multiprocessing
    from collections import deque
    from concurrent.futures import ProcessPoolExecutor

    max_inflight = max(2, workers * 2)
    pending: deque = deque()
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        for inst in specs:
            for interval in intervals:
                if pinned is not None:
                    # Pinned: the parent reads the manifest, never the bars. The
                    # store read — and every refusal it can raise — belongs to
                    # the worker (`_pinned_worker_task`).
                    prepared = _pinned_header(
                        provider, inst, interval, win, pinned,
                        clamped=_is_clamped(interval, win.get("lookback_days"),
                                            win.get("start")))
                    task, address = _pinned_worker_task, prepared.dataset_address
                else:
                    prepared = _prepare_dataset(provider, inst, interval, win)
                    task, address = _worker_task, ""
                slots, payload = _plan_dataset(
                    provider, inst, interval, capital, win, strategies, prepared,
                    pinned_address=address, owner_id=owner_id)
                future = pool.submit(task, payload) if payload else None
                pending.append((future, slots))
                # `prepared` (and its lazily-built frame) is dropped here: the
                # parent never holds a dataset past its submission.
                del prepared, payload
                while len(pending) >= max_inflight:
                    future, slots = pending.popleft()
                    yield from _drain(slots, future)
        while pending:
            future, slots = pending.popleft()
            yield from _drain(slots, future)


def _prepare_dataset(provider, inst, interval, win, *,
                     pinned=None) -> _PreparedDataset:
    start, end = win.get("start"), win.get("end")
    clamped = _is_clamped(interval, win.get("lookback_days"), start)
    if pinned is not None:
        # Explicitly pinned: the store is the only source, and a pin that cannot
        # be honoured is an error, never a fetch. Falling back here would turn a
        # pinned run into a refresh wearing a pin's name.
        return _pinned_dataset(provider, inst, interval, win, pinned,
                               clamped=clamped)
    # A custom window entirely older than Kite's per-interval ceiling can never be
    # fetched — surface a DISTINCT, explanatory status rather than the generic,
    # silently-dropped 'insufficient history' (DV-3).
    if _window_out_of_range(interval, start, end):
        cap = MAX_DAYS.get(interval, 200)
        return _PreparedDataset(
            clamped=clamped,
            error=f"window older than Kite max for this interval "
                  f"(≈{cap}d on {interval})")
    requested_window = _requested_window(interval, win)
    days = _fetch_days(interval, win.get("lookback_days"), start, end)
    try:
        candles = provider.get_candles(inst, interval, days, end=end) \
            if _supports_end(provider) else provider.get_candles(inst, interval, days)
    except Exception as e:
        # Preserve the existing provider-failure artifact: clamp metadata was not
        # asserted when no dataset was obtained.
        return _PreparedDataset(error=f"candles: {e}")
    candles = tuple(
        _FrozenCandle(c.ts, float(c.open), float(c.high), float(c.low),
                      float(c.close), float(c.volume))
        for c in _clip_to_window(candles, start, end)
    )
    if len(candles) < MIN_BARS:
        # distinguish "the window is reachable but thin" from "older than ceiling"
        if (start or end):
            return _PreparedDataset(
                candles=candles, bars=len(candles), clamped=clamped,
                error="window older than Kite max for this interval"
                if len(candles) == 0 else "insufficient history in window")
        return _PreparedDataset(
            candles=candles, bars=len(candles), clamped=clamped,
            error="insufficient history")
    first_ts = ist_epoch(candles[0].ts)
    last_ts = ist_epoch(candles[-1].ts)   # IST-correct cache discriminator (DV-5)
    effective_days = max(0, round((last_ts - first_ts) / 86400))
    effective_window = {
        "first_ts": first_ts,
        "last_ts": last_ts,
        "bars": len(candles),
        "clamped": clamped,
    }
    try:
        dataset_address = ordered_dataset_address(
            candles,
            provider=provider,
            instrument=inst,
            interval=interval,
            requested_window=requested_window,
            effective_window=effective_window,
        )
    except Exception as exc:
        # A dataset can still be simulated when it cannot be addressed. It is
        # deliberately non-reusable for this run.
        log.warn(f"backtest cache disabled for {inst.key}/{interval}: {exc}")
        dataset_address = ""
    if dataset_address:
        # Keep the bytes we just paid a throttled provider read for. This is a
        # WRITE only: the sweep never reads the store back, so a refresh still
        # costs its reads. Serving from the store is an explicit pinned run.
        # Storage failure is not a sweep failure, exactly as above.
        try:
            dataset_store.get_store().put(
                candles, provider=provider, instrument=inst, interval=interval,
                requested_window=requested_window,
                effective_window=effective_window, address=dataset_address)
        except Exception as exc:
            log.warn(f"backtest dataset not stored for "
                     f"{inst.key}/{interval}: {exc}")
    return _PreparedDataset(
        candles=candles, bars=len(candles), first_ts=first_ts, last_ts=last_ts,
        effective_days=effective_days, clamped=clamped,
        dataset_address=dataset_address)


def _pinned_address(inst, interval, pinned) -> str:
    """The address the caller pinned for this cell, or "". No I/O."""
    return (pinned.get(pin_key(getattr(inst, "key", ""), interval))
            or "").strip().lower()


def _pinned_dataset(provider, inst, interval, win, pinned, *,
                    clamped: bool) -> _PreparedDataset:
    """Serve one cell from a caller-named dataset address, or refuse.

    The serial path. It reads and verifies in this process; the parallel path
    sends the address to a worker, which calls the same function underneath
    (`_pinned_dataset_from_store`) so there is one set of refusals, not two.
    """
    key = pin_key(getattr(inst, "key", ""), interval)
    address = _pinned_address(inst, interval, pinned)
    if not address:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: no dataset address pinned for {key}")
    return _pinned_dataset_from_store(
        lambda a: dataset_store.get_store().get(a),
        address=address, key=key,
        provider_identity=source_identity(provider,
                                          fields=PROVIDER_IDENTITY_FIELDS),
        instrument_identity=source_identity(inst,
                                            fields=INSTRUMENT_IDENTITY_FIELDS),
        interval=interval, requested_window=_requested_window(interval, win),
        clamped=clamped)


def _pinned_header(provider, inst, interval, win, pinned, *,
                   clamped: bool) -> _PreparedDataset:
    """What the PARENT needs to plan a pinned dataset, without decoding it.

    Deliberately candle-less and deliberately proof-less. It resolves the pinned
    address (no I/O) and reads the manifest sidecar for the one planning value
    the parent cannot obtain otherwise: the effective window's last timestamp,
    which discriminates the result cache. It performs no refusal check beyond
    "nothing was pinned for this cell", which is a property of the caller's pin
    map rather than of any stored bytes — so the ORDER in which the remaining
    refusals fire is unchanged, and every one of them still fires, in the worker.

    A manifest that is missing, unreadable or untruthful costs a cache miss and
    nothing else: an execution address binds the dataset address, and a stored
    row's `last_candle_ts` came from real decoded bars, so no wrong row can be
    matched. The bytes are then proven, or refused, by the worker.
    """
    key = pin_key(getattr(inst, "key", ""), interval)
    address = _pinned_address(inst, interval, pinned)
    if not address:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: no dataset address pinned for {key}")
    try:
        manifest = dataset_store.get_store().manifest(address)
    except Exception:
        manifest = None
    effective = (manifest or {}).get("effective_window")
    effective = effective if isinstance(effective, dict) else {}
    try:
        last_ts = int(effective.get("last_ts") or 0)
    except (TypeError, ValueError):
        last_ts = 0
    return _PreparedDataset(clamped=clamped, dataset_address=address,
                            last_ts=last_ts)


def _pinned_dataset_from_store(read, *, address: str, key: str,
                               provider_identity, instrument_identity,
                               interval: str, requested_window,
                               clamped: bool) -> _PreparedDataset:
    """Verify one pinned dataset and decode it, or refuse — the whole fail-closed
    set, in one place, callable from the parent or from a worker.

    Every refusal below is a *closed* failure: one explanatory result row for the
    cell, the rest of the run untouched, and not one provider read. `read` takes
    an address and returns a proven `StoredDataset` or None; there is
    deliberately no path from here back to `provider.get_candles`.
    """
    try:
        stored = read(address)
    except Exception as exc:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: dataset store unreadable for {key}: {exc}")
    if stored is None:
        # Missing, unreadable, or its bytes no longer recompute to this address.
        # The store refuses all three the same way and so do we.
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: dataset {address[:12]}… for {key} is missing or "
                  f"its content no longer matches its address")
    mismatch = _pin_mismatch(stored, provider_identity=provider_identity,
                             instrument_identity=instrument_identity,
                             interval=interval,
                             requested_window=requested_window)
    if mismatch:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: dataset {address[:12]}… does not describe "
                  f"{key} — {mismatch}")

    candles = tuple(
        _FrozenCandle(c.ts, float(c.open), float(c.high), float(c.low),
                      float(c.close), float(c.volume))
        for c in stored.candles)
    if len(candles) < MIN_BARS:
        return _PreparedDataset(
            candles=candles, bars=len(candles), clamped=clamped,
            error="insufficient history")
    first_ts = ist_epoch(candles[0].ts)
    last_ts = ist_epoch(candles[-1].ts)
    effective = stored.effective_window if isinstance(
        stored.effective_window, dict) else {}
    return _PreparedDataset(
        candles=candles, bars=len(candles), first_ts=first_ts, last_ts=last_ts,
        effective_days=max(0, round((last_ts - first_ts) / 86400)),
        clamped=bool(effective.get("clamped", clamped)),
        dataset_address=stored.address)


def _pin_mismatch(stored, *, provider_identity, instrument_identity, interval,
                  requested_window) -> str:
    """Why this stored dataset is not an answer to this cell's request, or "".

    The store's own address check proves the bytes are the bytes that address
    names. It cannot prove they are the SERIES this cell asked for: a 30-minute
    GOLD dataset recomputes to its own address perfectly. Serving it to a
    15-minute NIFTY cell would be a silently wrong backtest, which is worse than
    any refusal, so the manifest is compared against the request as well.

    Identities rather than a provider handle, because this now also runs in a
    worker process — which has no provider and must never acquire one.
    """
    if stored.interval != interval:
        return f"its interval is {stored.interval!r}, not {interval!r}"
    if stored.instrument != instrument_identity:
        return f"its instrument is {stored.instrument!r}"
    if stored.provider != provider_identity:
        return f"its provider is {stored.provider!r}"
    if stored.requested_window != requested_window:
        return (f"it was fetched for window {stored.requested_window!r}, "
                f"not {requested_window!r}")
    return ""


def _one(provider, inst, interval, capital, win, strat=None, *, owner_id: str,
         prepared: _PreparedDataset | None = None) -> dict:
    """Resolve one cell to a serialized result payload. Writes nothing.

    Returning values instead of writing them is what makes both Task 5 and Task 6
    possible: persistence moves into a batched transaction the caller owns, and
    the arithmetic below can run in a process that has no database session at all.
    Everything that needs the database — the reusable-result lookup — stays here,
    in the parent.
    """
    if strat is None:
        from app.strategy.registry import get_strategy
        strat = get_strategy(None)
    prepared = prepared or _prepare_dataset(provider, inst, interval, win)
    if prepared.error:
        return _result_values(
            inst, interval, None, [], prepared.bars,
            clamped=prepared.clamped, strategy_key=strat.key,
            error=prepared.error)
    slippage_pct = float(get_settings().backtest_slippage_pct)
    phash = _execution_address(prepared, inst, interval, capital, win, strat,
                               slippage_pct)
    cached = _reusable_values(inst, interval, phash, prepared.last_ts, owner_id=owner_id)
    if cached is not None:
        return cached
    return _compute_values(
        prepared.candles, inst, interval, capital, strat,
        dict(strat.default_params), slippage_pct, phash,
        bars=prepared.bars, first_ts=prepared.first_ts, last_ts=prepared.last_ts,
        effective_days=prepared.effective_days, clamped=prepared.clamped,
        frame=prepared.frame)


def _execution_address(prepared, inst, interval, capital, win, strat,
                       slippage_pct) -> str:
    if not prepared.dataset_address:
        return ""
    try:
        return execution_result_address(
            dataset_address=prepared.dataset_address,
            instrument=inst,
            strategy=strat,
            parameters=dict(strat.default_params),
            capital=capital,
            window=win,
            slippage_pct=slippage_pct,
            implementation_maps=(),
        ) or ""
    except Exception as exc:
        # Identity failure disables reuse for this cell; it never disables the run.
        log.warn(f"backtest cache disabled for {inst.key}/{interval}: {exc}")
        return ""


def _reusable_values(inst, interval, phash: str, last_ts: int, *, owner_id: str) -> dict | None:
    """The refresh-warm hit: an identical execution address already has a row.

    This is the ONLY database read in the per-cell path, and it stays in the
    parent process deliberately — a worker with its own session would be a second
    reader of the result table whose visibility depends on batch timing.
    """
    if not phash:
        return None
    from app.backtest import cache
    expected_premium_error = ("" if getattr(inst, "has_options", True)
                              else NO_OPTIONS_PREMIUM_ERROR)
    with SessionLocal() as s:
        hit = cache.find_reusable(
            s, inst.key, interval, phash, last_ts, owner_id=owner_id,
            expected_premium_error=expected_premium_error)
        if hit is None:
            return None
        from app.backtest.cache import cached_result_values
        return dict(cached_result_values(hit), from_cache=True)


def _compute_values(candles, inst, interval, capital, strat, params,
                    slippage_pct, phash, *, bars, first_ts, last_ts,
                    effective_days, clamped, frame=None) -> dict:
    """The pure cell: candles in, serialized result values out.

    No database, no provider, no module-level mutable state — which is exactly
    what lets a worker process run it (Task 6). Every input that could differ
    between two processes is passed in explicitly rather than resolved from
    settings here; `slippage_pct` and `params` in particular.
    """
    signals = compute_signals(candles, strat, params, frame=frame)
    trades, m = simulate(
        candles, inst, interval, capital=capital, strategy=strat, params=params,
        slippage_pct=slippage_pct, signals=signals)
    # synthetic-premium backtest (audit C6) — runs alongside the spot cell above.
    # A premium-side bug must NEVER kill the spot result: any exception here is
    # caught and surfaced as premium_error instead of aborting the sweep.
    if not getattr(inst, "has_options", True):
        p_trades, p_metrics, premium_error = [], BTMetrics(), \
            NO_OPTIONS_PREMIUM_ERROR
    else:
        try:
            p_trades, p_metrics = simulate_premium(
                candles, inst, interval, strategy=strat,
                params=params, capital=capital, signals=signals)
            premium_error = ""
        except Exception as e:
            p_trades, p_metrics, premium_error = [], BTMetrics(), str(e)
    return _result_values(
        inst, interval, m, trades, bars, strategy_key=strat.key,
        params_hash=phash, last_candle_ts=last_ts,
        first_ts=first_ts, last_ts_span=last_ts, effective_days=effective_days,
        clamped=clamped, premium_trades=p_trades, premium_metrics=p_metrics,
        premium_error=premium_error)


def _supports_end(provider) -> bool:
    """True if this provider's get_candles accepts an `end` kwarg (backtest-only
    date-range anchoring). The live engine never passes `end`, so its frozen call
    path is untouched."""
    import inspect
    try:
        return "end" in inspect.signature(provider.get_candles).parameters
    except (TypeError, ValueError):
        return False


def _result_values(inst, interval, m, trades, bars, error="",
                   params_hash="", last_candle_ts=0, first_ts=0, last_ts_span=0,
                   effective_days=0, clamped=False, strategy_key="trend_impulse_v3",
                   premium_trades=None, premium_metrics=None,
                   premium_error="") -> dict:
    """Every stored column for one cell, already serialized. Writes nothing.

    JSON encoding happens HERE rather than at the transaction, so a batch commit
    is pure I/O and — for a worker — so the value that crosses the process
    boundary is the exact string that will be stored. Float formatting drift
    between processes would show up in these strings first, which is why the
    bit-identity gate compares them.
    """
    import datetime as dt
    from app.backtest import cache
    seg = backtest_charge_segment(inst)
    # `run_id` is deliberately absent: it is run-local identity, applied by
    # `_commit_batch` at insert time. A payload that carried it could not be
    # computed in a worker before the run existed, nor compared across runs.
    common = dict(instrument_key=inst.key, name=inst.name,
                  segment=seg, strategy_key=strategy_key, interval=interval, bars=bars,
                  params_hash=params_hash, last_candle_ts=last_candle_ts,
                  first_ts=first_ts, last_ts=last_ts_span,
                  effective_days=effective_days, clamped=clamped,
                  schema_version=cache.SCHEMA_VERSION, from_cache=False,
                  computed_at=dt.datetime.now())
    pm = premium_metrics if premium_metrics is not None else BTMetrics()
    ptrades = premium_trades or []
    # Serialization of premium trades must obey the same rule as the premium
    # simulation itself: a premium-side failure NEVER kills the spot result
    # (2026-07-23: an np.bool in a trade dict aborted whole sweeps here).
    try:
        ptrades_json = json.dumps([t.to_dict() for t in ptrades])
    except Exception as e:
        pm, ptrades_json = BTMetrics(), "[]"
        premium_error = premium_error or f"premium trades not serializable: {e}"
    premium_common = dict(
        premium_trades=pm.trades, premium_win_rate=pm.win_rate,
        premium_net_pnl=pm.net_pnl, premium_return_pct=pm.return_pct,
        premium_profit_factor=pm.profit_factor,
        premium_max_drawdown_pct=pm.max_drawdown_pct,
        premium_expectancy=pm.expectancy, premium_charges=pm.charges,
        premium_trades_json=ptrades_json,
        premium_error=premium_error)
    if m is None:
        return dict(error=error, **premium_common, **common)
    return dict(trades=m.trades, wins=m.wins, win_rate=m.win_rate,
                profit_factor=m.profit_factor, max_drawdown_pct=m.max_drawdown_pct,
                return_pct=m.return_pct, net_pnl=m.net_pnl, gross_pnl=m.gross_pnl,
                charges=m.charges, expectancy=m.expectancy, cagr=m.cagr,
                calmar=m.calmar, consistency=m.consistency, sharpe=m.sharpe,
                max_consec_losses=m.max_consec_losses, time_underwater_pct=m.time_underwater_pct,
                notional=m.notional, lots=m.lots, affordable=m.affordable,
                option_cost=m.option_cost,
                open_at_end=m.open_at_end, win_rate_realised=m.win_rate_realised,
                return_pct_realised=m.return_pct_realised,
                bh_return_pct=m.bh_return_pct, worst_trade_pnl=m.worst_trade_pnl,
                worst_mae_pct=m.worst_mae_pct,
                curve_json=json.dumps(m.equity_curve),
                trades_json=json.dumps([t.to_dict() for t in trades]),
                bh_curve_json=json.dumps(m.bh_curve), **premium_common, **common)


# ── persistence ──────────────────────────────────────────────────────────────

def _durable_result_count(session, run_id, *, owner_id: str) -> int:
    """How many result rows this run has, counted inside the caller's transaction.

    This — not a counter — is progress. An incrementing counter is written by a
    different transaction than the one that made the row durable, so a crash
    between the two leaves a run reporting work it cannot show.
    """
    return repository.durable_result_count(session, owner_id=owner_id, run_id=run_id)


def _commit_batch(run_id, values: list[dict], *, owner_id: str, status: str = "",
                  note: str = "") -> None:
    """Persist up to `BATCH_SIZE` results, their progress, and any terminal
    status as ONE transaction. It changes all of them or none of them."""
    if len(values) > BATCH_SIZE:
        raise RuntimeError(
            f"batch of {len(values)} exceeds BATCH_SIZE={BATCH_SIZE}")
    with SessionLocal() as s:
        repository.append_result_batch(s, owner_id=owner_id, run_id=run_id, values=values)
        s.flush()          # rows are visible to the count below, still uncommitted
        repository.update_run(s, owner_id=owner_id, run_id=run_id,
                              status=status, note=note)
        s.commit()


def reconcile_stale_runs(*, owner_id: str) -> int:
    """Repair runs left `running` by a process that died mid-sweep.

    Nothing in-process is driving them: `_running` is a module global and does not
    survive a restart, so the row is a phantom the status endpoint reports forever
    and `start_sweep` would contradict. `done` is reset from the durable row count
    rather than trusted, because a run written by the pre-batch incrementing
    counter can be arbitrarily ahead of its rows. Returns how many were repaired.
    """
    if _running:            # a live sweep owns its own row; never touch it
        return 0
    repaired = 0
    with SessionLocal() as s:
        repaired = repository.reconcile_stale_runs(
            s, owner_id=owner_id,
            note="interrupted: the process ended before this sweep finished; "
                 "progress reset to its durable results")
        if repaired:
            s.commit()
    return repaired
