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
from sqlalchemy import func, select, text
import json
import threading
import time
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
from app.db.models import BacktestRun
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
MAX_REPLAY_DESCRIPTOR_BYTES = 256 * 1024
MAX_REPLAY_ARTIFACT_BYTES = 128 * 1024

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


# Local threads are observability/cleanup only.  Durable run claims are the
# write/admission authority, so another process may safely run unrelated work.
_state_lock = threading.Lock()
_LeaseThread = threading.Thread  # tests may replace launch threads; lease safety must remain real.
_workers: dict[int, threading.Thread] = {}
_running = False  # legacy observability only; never use for admission.
_measure_lock = threading.Lock()
_measurements: dict[str, int | float] = {
    "provider_reads": 0, "dataset_store_reads": 0, "batch_persists": 0,
    "claim_takeovers": 0, "rejections": 0, "inflight_datasets": 0,
    "active_process_pools": 0, "db_lock_wait_seconds": 0.0,
    "claim_latency_seconds": 0.0, "takeover_age_seconds": 0.0,
    # Origin is deliberately a bounded category, never an owner or cache key.
    "cache_owner_local": 0, "cache_public_shared": 0, "cache_cold": 0,
    "cache_public_integrity_failures": 0, "cache_public_write_failures": 0,
    "dataset_store_write_failures": 0,
}
_owner_measurements: dict[tuple[str, str], int | float] = {}
_measurement_gauges: dict[tuple[str, str | None, int | None], int | float] = {}
_REJECTION_REASONS = frozenset({"host_active_jobs", "owner_active_jobs",
                                "owner_queued_jobs", "host_requested_cells",
                                "host_worker_slots", "claim_conflict"})


def _measure(name: str, value: int | float = 1, *, owner_id: str | None = None,
             run_id: int | None = None) -> None:
    with _measure_lock:
        _measurements[name] = _measurements.get(name, 0) + value
        if owner_id is not None:
            key = (owner_id, name)
            _owner_measurements[key] = _owner_measurements.get(key, 0) + value


def _measure_set(name: str, value: int | float, *, owner_id: str | None = None,
                 run_id: int | None = None) -> None:
    with _measure_lock:
        _measurement_gauges[(name, owner_id, run_id)] = value


def _measure_rejection(reason: str, *, owner_id: str | None = None) -> None:
    """Track a bounded reason label set so hostile input cannot grow metrics."""
    bounded = reason if reason in _REJECTION_REASONS else "other"
    _measure("rejections", owner_id=owner_id)
    _measure(f"rejections_{bounded}", owner_id=owner_id)


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
    dataset_classification: str = dataset_store.MARKET_PUBLIC
    # True only after this process recomputed the ordered address from candles
    # or the public storage adapter decoded and verified its blob.
    dataset_verified: bool = False

    @cached_property
    def frame(self):
        # Lazily prepared: a refresh-warm cache hit validates candle bytes but
        # performs no DataFrame conversion or signal work.
        return prepare_signal_frame(self.candles)


def is_running() -> bool:
    # Compatibility/diagnostic helper: reports a local thread, never an
    # admission decision and never a remote worker's durable lease.
    with _state_lock:
        return any(thread.is_alive() for thread in _workers.values())


def _join() -> None:
    """Test helper: block until the running sweep thread completes."""
    with _state_lock:
        threads = list(_workers.values())
    for thread in threads:
        thread.join()


class WorkloadAdmissionError(RuntimeError):
    """Explicit, non-topology-leaking refusal before provider/worker resources."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"backtest workload rejected: {reason}")


class ClaimLost(RuntimeError):
    """The durable token was cancelled, replaced, or allowed to expire."""


def _terminalize_requested_cancel(*, owner_id: str, run_id: int,
                                  claim_token: str) -> bool:
    """Finish a cancellation safely when no worker exists yet."""
    with SessionLocal() as session:
        if not repository.is_cancel_requested(
                session, owner_id=owner_id, run_id=run_id,
                claim_token=claim_token):
            return False
        completed = repository.complete_claim(
            session, owner_id=owner_id, run_id=run_id,
            claim_token=claim_token, status="cancelled")
        if completed:
            session.commit()
        else:
            session.rollback()
        return completed


class ReplayUnavailable(RuntimeError):
    """A durable descriptor cannot be reconstructed without changing its meaning.

    This is deliberately distinct from a malformed request.  A missing immutable
    artifact is a recoverable availability state: the dispatcher returns the claim
    to the queue instead of writing an "error" result for a strategy it did not run.
    """


class _ClaimGuard:
    """Own lease liveness without ever sharing a SQLAlchemy Session across threads."""
    def __init__(self, *, owner_id: str, run_id: int, claim_token: str):
        self.owner_id, self.run_id, self.claim_token = owner_id, run_id, claim_token
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def ensure_active(self) -> None:
        if self._lost.is_set():
            raise ClaimLost("backtest claim is no longer active")

    def _beat(self) -> bool:
        # One short-lived session per beat is deliberate: SQLAlchemy sessions are
        # thread-confined, and provider/simulation may be blocked for seconds.
        with SessionLocal() as session:
            alive = repository.heartbeat_claim(
                session, owner_id=self.owner_id, run_id=self.run_id,
                claim_token=self.claim_token,
                lease_seconds=get_settings().backtest_claim_lease_seconds)
            if alive:
                session.commit()
            else:
                session.rollback()
            return alive

    def start(self) -> None:
        lease = max(1, int(get_settings().backtest_claim_lease_seconds))
        interval = max(0.05, min(float(lease) / 3.0, 5.0))
        def loop() -> None:
            while not self._stop.wait(interval):
                try:
                    if not self._beat():
                        self._lost.set()
                        return
                except Exception:
                    # An unavailable database cannot prove this worker still has
                    # authority. Stop scheduling rather than risking a stale write.
                    self._lost.set()
                    return
        self._thread = _LeaseThread(target=loop, name=f"backtest-lease-{self.run_id}", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, float(get_settings().backtest_claim_lease_seconds)))


def _admit_workload(*, owner_id: str, total: int, workers: int, session=None,
                    excluding_run_id: int | None = None) -> None:
    """Check host and tenant pressure from durable rows before any data read.

    Limits are deployment configuration, not customer count. SQLite gets simple
    aggregate reads; Phase 2 can retain this interface while using PostgreSQL
    locks/metrics without rewriting callers.
    """
    settings = get_settings()
    owns_session = session is None
    if owns_session:
        session = SessionLocal()
    try:
        scope = [] if excluding_run_id is None else [BacktestRun.id != excluding_run_id]
        active = int(session.scalar(select(func.count()).select_from(BacktestRun).where(
            *scope, BacktestRun.status == "running")) or 0)
        owner_active = int(session.scalar(select(func.count()).select_from(BacktestRun).where(
            *scope, BacktestRun.owner_id == owner_id, BacktestRun.status == "running")) or 0)
        owner_queued = int(session.scalar(select(func.count()).select_from(BacktestRun).where(
            *scope, BacktestRun.owner_id == owner_id, BacktestRun.status == "pending")) or 0)
        reserved_cells = int(session.scalar(select(func.coalesce(func.sum(BacktestRun.total), 0)).where(
            *scope, BacktestRun.status.in_(("pending", "running")))) or 0)
        reserved_workers = int(session.scalar(select(func.coalesce(func.sum(
            BacktestRun.requested_workers), 0)).where(
            *scope, BacktestRun.status.in_(("pending", "running")))) or 0)
    finally:
        if owns_session:
            session.close()
    if active >= max(0, settings.backtest_host_active_jobs):
        _measure_rejection("host_active_jobs", owner_id=owner_id)
        raise WorkloadAdmissionError("host_active_jobs")
    if owner_active >= max(0, settings.backtest_owner_active_jobs):
        _measure_rejection("owner_active_jobs", owner_id=owner_id)
        raise WorkloadAdmissionError("owner_active_jobs")
    if owner_queued >= max(0, settings.backtest_owner_queued_jobs):
        _measure_rejection("owner_queued_jobs", owner_id=owner_id)
        raise WorkloadAdmissionError("owner_queued_jobs")
    if reserved_cells + total > max(0, settings.backtest_host_requested_cells):
        _measure_rejection("host_requested_cells", owner_id=owner_id)
        raise WorkloadAdmissionError("host_requested_cells")
    if reserved_workers + workers > max(0, settings.backtest_host_worker_slots):
        _measure_rejection("host_worker_slots", owner_id=owner_id)
        raise WorkloadAdmissionError("host_worker_slots")


def measurement_snapshot(*, owner_id: str | None = None, session=None) -> dict[str, int | float]:
    """Measured scheduler state, deliberately without an invented performance SLO."""
    owns_session = session is None
    if owns_session:
        session = SessionLocal()
    try:
        statuses = [BacktestRun.status.in_(("pending", "running"))]
        if owner_id is not None:
            statuses.append(BacktestRun.owner_id == owner_id)
        queued = int(session.scalar(select(func.count()).select_from(BacktestRun).where(
            *statuses, BacktestRun.status == "pending")) or 0)
        active = int(session.scalar(select(func.count()).select_from(BacktestRun).where(
            *statuses, BacktestRun.status == "running")) or 0)
        cells = int(session.scalar(select(func.coalesce(func.sum(BacktestRun.total), 0)).where(
            *statuses)) or 0)
        workers = int(session.scalar(select(func.coalesce(func.sum(BacktestRun.requested_workers), 0)).where(
            *statuses)) or 0)
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        oldest = session.scalar(select(func.min(BacktestRun.queued_at)).where(
            *statuses, BacktestRun.status == "pending"))
        heartbeat = session.scalar(select(func.max(BacktestRun.heartbeat_at)).where(
            *statuses, BacktestRun.status == "running"))
        with _measure_lock:
            counters = (dict(_measurements) if owner_id is None else {
                name: 0 for name in _measurements
            })
            if owner_id is not None:
                counters.update({name: value for (owner, name), value in _owner_measurements.items()
                                 if owner == owner_id})
            gauges: dict[str, int | float] = {}
            for (name, owner, _run), value in _measurement_gauges.items():
                if owner_id is None or owner == owner_id:
                    gauges[name] = gauges.get(name, 0) + value
        with _state_lock:
            local_threads = sum(thread.is_alive() for thread in _workers.values())
        return {"queued_jobs": queued, "active_jobs": active, "reserved_cells": cells,
                "reserved_worker_slots": workers,
                "queue_age_seconds": max(0.0, (now - oldest).total_seconds()) if oldest else 0.0,
                "heartbeat_age_seconds": max(0.0, (now - heartbeat).total_seconds()) if heartbeat else 0.0,
                "local_worker_threads": local_threads, **counters, **gauges}
    finally:
        if owns_session:
            session.close()


def _conservative_cell_estimate(*, scope: str, instruments: list[str] | None,
                                intervals: list[str], strategies: int) -> int:
    """Bound admission without reading a provider/universe or launching work."""
    if instruments:
        universe = len({key.strip() for key in instruments if key.strip()})
    else:
        settings = get_settings()
        universe = (settings.backtest_full_universe_upper_bound if scope == "full"
                    else settings.backtest_liquid_universe_upper_bound)
    return max(0, universe) * len(intervals) * max(1, strategies)


def _strategy_descriptor(strategy, *, owner_id: str | None = None) -> dict[str, str]:
    """Persist the execution identity, never just a mutable registry key."""
    descriptor = {"key": strategy.key, "version": strategy.version}
    # Generated keys are mutable database names. Persist the reviewed composition
    # itself with the run so a later republish cannot make recovery execute newer
    # bytes under the previous run's identity.  The payload is validated again at
    # dispatch; it contains neither credentials nor a provider object.
    if owner_id is not None:
        from app.strategy.registry import is_generated_key
        if is_generated_key(strategy.key):
            from app.core.generated_strategies import list_generated
            with SessionLocal() as session:
                rows = {row.key: row for row in list_generated(session, owner_id=owner_id)}
            row = rows.get(strategy.key)
            if row is None or row.version != strategy.version:
                raise ReplayUnavailable(
                    f"generated strategy artifact disappeared during admission: {strategy.key}")
            descriptor["composition_json"] = row.composition_json
    return descriptor


def _resolve_descriptor_strategies(*, owner_id: str, descriptor: dict):
    """Resolve only strategies whose immutable identity still matches the run.

    A key may be republished between an interrupted run and its replacement.  A
    replacement worker must fail closed rather than generate results under the old
    label from the new bytes.  Generated artifacts are hydrated by the caller before
    this check; future historical artifact storage can extend the descriptor with an
    explicit immutable payload without weakening this invariant.
    """
    from app.strategy.registry import StrategyNotFound, resolve_strategy
    requested = descriptor.get("strategies", [])
    if not isinstance(requested, list) or not requested:
        raise ValueError("descriptor lacks strategy artifacts")
    resolved = []
    for artifact in requested:
        if not isinstance(artifact, dict):
            raise ReplayUnavailable("unversioned legacy strategy descriptor")
        key, version = artifact.get("key"), artifact.get("version")
        if not isinstance(key, str) or not key or not isinstance(version, str) or not version:
            raise ValueError("descriptor strategy artifact lacks key or version")
        composition_json = artifact.get("composition_json")
        if composition_json is not None:
            if not isinstance(composition_json, str) or len(composition_json.encode()) > MAX_REPLAY_ARTIFACT_BYTES:
                raise ValueError("descriptor generated artifact is not text")
            try:
                from app.core.generated_strategies import generated_version
                from research.strategy.builder.grammar import Composition
                from research.strategy.builder.load import build_strategy
                composition = Composition.from_dict(json.loads(composition_json))
                strategy = build_strategy(composition)
                strategy.pin_version(generated_version(
                    composition, default_params=getattr(strategy, "default_params", None),
                    risk_model=getattr(strategy, "risk_model", None)))
            except Exception as exc:
                raise ReplayUnavailable(f"strategy artifact unavailable: {key}") from exc
            if strategy.key != key:
                raise ReplayUnavailable(f"strategy artifact key changed: {key}")
        else:
            try:
                strategy = resolve_strategy(key, owner_id=owner_id)
            except StrategyNotFound as exc:
                raise ReplayUnavailable(f"strategy artifact unavailable: {key}") from exc
        if strategy.version != version:
            raise ReplayUnavailable(
                f"strategy artifact version unavailable: {key} requested {version}, "
                f"available {strategy.version}")
        resolved.append(strategy)
    return resolved


def start_sweep(*, owner_id: str, scope: str = "liquid", intervals: list[str] | None = None,
                capital: float = 50_000.0, provider=None,
                instruments: list[str] | None = None,
                lookback_days: int | None = None,
                start_date: str | None = None, end_date: str | None = None,
                strategies: list[str] | None = None,
                pinned_datasets=None, workers: int | None = None) -> int:
    """Create a run row, resolve the universe, launch its background thread.
    Returns the new durable run id. Independent sweeps may run concurrently,
    subject to the configured host and owner workload limits.

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
    pinned = normalize_pinned_datasets(pinned_datasets) if pinned_datasets else None
    worker_count = _worker_count(workers)
    # A caller for any tenant, not only the boot owner, gives expired work a
    # production reclaim path before admitting another request.
    if reconcile_stale_runs(owner_id=owner_id):
        dispatch_reclaimable(owner_id=owner_id)
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
        # A historical generated composition is reconstructed in this process for
        # an exact replay.  Do not hand it to spawned workers through their mutable
        # owner registry; serial replay is slower but preserves the recorded bytes.
        from app.strategy.registry import is_generated_key
        if any(is_generated_key(strategy.key) for strategy in strat_objs):
            worker_count = 1
        win = {"lookback_days": lookback_days, "start": start_date, "end": end_date,
               "label": window_label(lookback_days, start_date, end_date)}
        # Must happen before provider/universe I/O or thread/pool creation.  The
        # durable reservation uses a conservative configured upper bound; after
        # resolution we replace it with the exact manifest total.
        total = _conservative_cell_estimate(
            scope=scope, instruments=instruments, intervals=intervals,
            strategies=len(strat_objs))
        # SQLite's single-writer reservation makes the aggregate budget check
        # and pending-row creation one admission decision.  A concurrent caller
        # observes this row before it can pass the same host budget.
        strat_label = "×".join(st.key for st in strat_objs)
        with SessionLocal() as s:
            lock_started = time.monotonic()
            s.execute(text("BEGIN IMMEDIATE"))
            _measure("db_lock_wait_seconds", time.monotonic() - lock_started, owner_id=owner_id)
            _admit_workload(owner_id=owner_id, total=total, workers=worker_count, session=s)
            run = repository.enqueue_run(
                s, owner_id=owner_id, scope=scope,
                intervals=",".join(intervals), capital=capital, total=total, done=0,
                requested_workers=worker_count,
                window=win["label"],
                instruments=",".join(sorted({i.strip() for i in (instruments or []) if i.strip()})),
                strategies=",".join(st.key for st in strat_objs),
                request_json=json.dumps({
                    "scope": scope, "intervals": intervals, "capital": capital,
                    "instruments": sorted({i.strip() for i in (instruments or []) if i.strip()}),
                    "lookback_days": lookback_days, "start_date": start_date,
                    "end_date": end_date,
                    "strategies": [_strategy_descriptor(st, owner_id=owner_id) for st in strat_objs],
                    # A pin is a content address, not provider state or a credential.
                    "pinned_datasets": pinned or {}, "workers": worker_count,
                }, sort_keys=True, separators=(",", ":")),
                note=f"reserved ≤{total} cells × {len(intervals)} intervals "
                     f"× {len(strat_objs)} strategies · {win['label']}"
                     + (" · pinned" if pinned else "")
                     + (f" · {worker_count} workers" if worker_count > 1 else ""))
            claim = repository.claim_run(
                s, owner_id=owner_id, run_id=run.id,
                claimed_by=f"local:{threading.get_ident()}",
                lease_seconds=get_settings().backtest_claim_lease_seconds)
            if claim is None:
                raise WorkloadAdmissionError("claim_conflict")
            s.commit()
            run_id = run.id
        resolving_guard = _ClaimGuard(owner_id=owner_id, run_id=run_id,
                                      claim_token=claim.claim_token)
        resolving_guard.start()
        try:
            resolving_guard.ensure_active()
            provider = provider or get_provider()
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=run_id,
                                              claim_token=claim.claim_token):
                resolving_guard.close()
                return run_id
            specs = full_universe(provider) if scope == "full" else liquid_universe(provider)
            if instruments:
                want = {k.strip() for k in instruments if k.strip()}
                specs = [i for i in specs if i.key in want]
                if not specs:
                    raise RuntimeError(f"none of the requested instruments exist: {sorted(want)}")
            exact_total = len(specs) * len(intervals) * len(strat_objs)
            with SessionLocal() as resolved:
                # Resolution can expand beyond the conservative configured bound.
                # Re-check the exact reservation inside the same writer decision
                # that publishes it, excluding this run's old reservation.
                lock_started = time.monotonic()
                resolved.execute(text("BEGIN IMMEDIATE"))
                _measure("db_lock_wait_seconds", time.monotonic() - lock_started, owner_id=owner_id)
                active = repository.get_run(resolved, owner_id=owner_id, run_id=run_id)
                if (active is None or active.claim_token != claim.claim_token
                        or active.status != "running"):
                    raise ClaimLost("admitted run lost its claim during resolution")
                _admit_workload(owner_id=owner_id, total=exact_total,
                                workers=worker_count, session=resolved,
                                excluding_run_id=run_id)
                active.total = exact_total
                active.instruments = ",".join(i.key for i in specs) if instruments else ""
                active.note = (f"{len(specs)} instruments × {len(intervals)} intervals "
                               f"× {len(strat_objs)} strategies · {win['label']}"
                               + (" · pinned" if pinned else "")
                               + (f" · {worker_count} workers" if worker_count > 1 else ""))
                resolved.commit()
            resolving_guard.ensure_active()
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=run_id,
                                              claim_token=claim.claim_token):
                resolving_guard.close()
                return run_id
            total = exact_total
        except Exception as exc:
            resolving_guard.close()
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=run_id,
                                              claim_token=claim.claim_token):
                return run_id
            with SessionLocal() as failed:
                repository.complete_claim(failed, owner_id=owner_id, run_id=run_id,
                                          claim_token=claim.claim_token, status="error",
                                          note=f"universe resolution failed: {exc}")
                failed.commit()
            raise
        log.info(f"backtest sweep #{run_id} started — {total} cells, "
                 f"window={win['label']}, strategies={strat_label}"
                 + (f", PINNED to {len(pinned)} stored datasets" if pinned else "")
                 + (f", {worker_count} worker processes" if worker_count > 1 else ""))
        t = threading.Thread(target=_run,
                             args=(run_id, provider, specs, intervals, capital, win,
                                   strat_objs, pinned, worker_count),
                             kwargs={"owner_id": owner_id, "claim_token": claim.claim_token,
                                     "guard": resolving_guard},
                             daemon=True)
        with _state_lock:
            _workers[run_id] = t
        try:
            t.start()
            # Ownership of the already-running lease loop moves to `_run`; it
            # closes it exactly once on every terminal path.
            resolving_guard = None
        except Exception as exc:
            # The durable claim was reserved before launch. If launch itself
            # fails, close *that exact token* so capacity is released without
            # ever touching a worker that subsequently reclaimed the run.
            with _state_lock:
                _workers.pop(run_id, None)
            resolving_guard.close()
            with SessionLocal() as failed:
                repository.complete_claim(
                    failed, owner_id=owner_id, run_id=run_id,
                    claim_token=claim.claim_token, status="error",
                    note=f"worker launch failed: {exc}")
                failed.commit()
            raise
        return run_id
    except Exception:
        raise


def _run(run_id, provider, specs, intervals, capital, win=None, strategies=None,
         pinned=None, workers=None, *, owner_id: str, claim_token: str,
         guard: _ClaimGuard | None = None) -> None:
    if not isinstance(claim_token, str) or not claim_token:
        raise ValueError("backtest worker requires a durable claim token")
    win = win or {"lookback_days": None, "start": None, "end": None, "label": "max"}
    if not strategies:
        from app.strategy.registry import DEFAULT_STRATEGY_KEY, resolve_strategy
        strategies = [resolve_strategy(DEFAULT_STRATEGY_KEY, owner_id=owner_id)]
    batch: list[dict] = []
    # A dispatcher may already be beating this claim while it resolves the
    # descriptor/provider. Transfer that exact guard to the worker: never leave
    # a resolution-to-worker gap and never run two heartbeat loops for one token.
    if guard is None:
        guard = _ClaimGuard(owner_id=owner_id, run_id=run_id, claim_token=claim_token)
        guard.start()
    else:
        if (guard.owner_id, guard.run_id, guard.claim_token) != (owner_id, run_id, claim_token):
            raise ValueError("claim guard does not match worker token")
        guard.ensure_active()
    try:
        for values in _cell_values(provider, specs, intervals, capital,
                                   win, strategies, pinned, workers, owner_id=owner_id,
                                   run_id=run_id, guard=guard):
            guard.ensure_active()
            batch.append(values)
            if len(batch) >= BATCH_SIZE:
                if not _commit_claimed_batch(run_id, batch, owner_id=owner_id,
                                             claim_token=claim_token):
                    raise ClaimLost("claimed batch was rejected")
                batch = []
        # The terminal status rides the final batch: results, progress and the
        # run's completion are one transaction, so a run can never be `done`
        # while its last ten rows are missing.
        if not _commit_claimed_batch(run_id, batch, owner_id=owner_id,
                                     claim_token=claim_token, status="done"):
            raise ClaimLost("claimed terminal write was rejected")
        if not guard._lost.is_set():
            log.info(f"backtest sweep #{run_id} complete")
    except ClaimLost:
        # A requested cancellation owns its terminal transition. A replaced
        # worker owns nothing further: it cannot overwrite the replacement.
        _commit_claimed_batch(run_id, [], owner_id=owner_id,
                              claim_token=claim_token, status="cancelled")
    except Exception as e:  # never let the thread die silently
        # `batch` is deliberately dropped: those cells were never durable, and
        # progress is derived from what IS durable, so nothing over-reports.
        _commit_claimed_batch(run_id, [], owner_id=owner_id,
                              claim_token=claim_token, status="error", note=str(e))
        log.error(f"backtest sweep #{run_id} failed: {e}")
    finally:
        guard.close()
        with _state_lock:
            _workers.pop(run_id, None)


def dispatch_reclaimable(*, owner_id: str, maximum: int | None = None) -> list[int]:
    """Claim and launch owner-local pending/expired durable work after restart.

    The descriptor is validated data from `start_sweep`; it deliberately names
    only request values and content addresses.  The provider is rebuilt by the
    configured factory at dispatch time, so no provider object or credentials can
    enter the database.  Invalid/stale descriptors are terminalized under the
    fresh token rather than silently retried forever.
    """
    from app.providers.factory import get_provider
    from app.strategy.registry import resolve_strategy
    limit = maximum if maximum is not None else max(0, int(get_settings().backtest_host_active_jobs))
    launched: list[int] = []
    for _ in range(limit):
        with SessionLocal() as session:
            lock_started = time.monotonic()
            session.execute(text("BEGIN IMMEDIATE"))
            _measure("db_lock_wait_seconds", time.monotonic() - lock_started, owner_id=owner_id)
            claim_started = time.monotonic()
            claim = repository.claim_next_run(
                session, owner_id=owner_id,
                claimed_by=f"dispatcher:{threading.get_ident()}",
                lease_seconds=get_settings().backtest_claim_lease_seconds)
            if claim is None:
                break
            # Replacement consumes the same budget as a fresh run.  This must be
            # decided before provider reconstruction, pool creation, or any I/O.
            try:
                _admit_workload(owner_id=owner_id, total=claim.total,
                                workers=claim.requested_workers, session=session,
                                excluding_run_id=claim.id)
            except WorkloadAdmissionError as exc:
                repository.release_claim(session, owner_id=owner_id, run_id=claim.id,
                                         claim_token=claim.claim_token,
                                         note=f"waiting for scheduler capacity: {exc.reason}")
                session.commit()
                break
            session.commit()
        _measure("claim_latency_seconds", time.monotonic() - claim_started, owner_id=owner_id)
        if claim.attempt_count > 1:
            _measure("claim_takeovers", owner_id=owner_id)
            if claim.queued_at:
                _measure("takeover_age_seconds", max(0.0, (
                    dt.datetime.now() - claim.queued_at).total_seconds()), owner_id=owner_id)
        # Begin liveness immediately after the atomic claim commits, before any
        # descriptor, registry, provider, universe or process-pool resolution.
        resolving_guard = _ClaimGuard(owner_id=owner_id, run_id=claim.id,
                                      claim_token=claim.claim_token)
        resolving_guard.start()
        try:
            resolving_guard.ensure_active()
            if len((claim.request_json or "").encode()) > MAX_REPLAY_DESCRIPTOR_BYTES:
                raise ValueError("descriptor exceeds durable replay size limit")
            descriptor = json.loads(claim.request_json or "")
            if not isinstance(descriptor, dict):
                raise ValueError("descriptor is not an object")
            intervals = [value for value in descriptor.get("intervals", []) if value in MAX_DAYS]
            if not intervals or not descriptor.get("strategies"):
                raise ValueError("descriptor lacks intervals or strategies")
            # Do this before provider I/O. A generated owner partition is rebuilt
            # from execution-plane rows; no research DB is consulted at replay.
            from app.core.generated_strategies import register_all
            with SessionLocal() as hydrate:
                register_all(hydrate, owner_id=owner_id)
            strategies = _resolve_descriptor_strategies(owner_id=owner_id,
                                                        descriptor=descriptor)
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=claim.id,
                                              claim_token=claim.claim_token):
                resolving_guard.close()
                continue
            provider = get_provider()
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=claim.id,
                                              claim_token=claim.claim_token):
                resolving_guard.close()
                continue
            scope = descriptor.get("scope", "liquid")
            specs = full_universe(provider) if scope == "full" else liquid_universe(provider)
            requested = set(descriptor.get("instruments") or ())
            if requested:
                specs = [instrument for instrument in specs if instrument.key in requested]
            if not specs:
                raise ValueError("descriptor resolves no instruments")
            win = {"lookback_days": descriptor.get("lookback_days"),
                   "start": descriptor.get("start_date"), "end": descriptor.get("end_date"),
                   "label": window_label(descriptor.get("lookback_days"),
                                         descriptor.get("start_date"), descriptor.get("end_date"))}
            pinned = normalize_pinned_datasets(descriptor.get("pinned_datasets") or {}) or None
            workers = _worker_count(descriptor.get("workers"))
            if any(isinstance(item, dict) and item.get("composition_json") is not None
                   for item in descriptor["strategies"]):
                workers = 1
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=claim.id,
                                              claim_token=claim.claim_token):
                resolving_guard.close()
                continue
            thread = threading.Thread(
                target=_run,
                args=(claim.id, provider, specs, intervals, float(descriptor.get("capital", claim.capital)),
                      win, strategies, pinned, workers),
                kwargs={"owner_id": owner_id, "claim_token": claim.claim_token,
                        "guard": resolving_guard}, daemon=True)
            with _state_lock:
                _workers[claim.id] = thread
            thread.start()
            # The worker owns and closes the same guard; no second heartbeat
            # thread is created after descriptor resolution.
            resolving_guard = None
            launched.append(claim.id)
        except ReplayUnavailable as exc:
            if resolving_guard is not None:
                resolving_guard.close()
            with _state_lock:
                _workers.pop(claim.id, None)
            with SessionLocal() as session:
                repository.release_claim(session, owner_id=owner_id, run_id=claim.id,
                                         claim_token=claim.claim_token,
                                         note=f"waiting for pinned strategy artifact: {exc}")
                session.commit()
            # The next queued job may still be runnable; do not let one unavailable
            # artifact monopolize this bounded dispatch pass.
            continue
        except Exception as exc:
            if resolving_guard is not None:
                resolving_guard.close()
            with _state_lock:
                _workers.pop(claim.id, None)
            if _terminalize_requested_cancel(owner_id=owner_id, run_id=claim.id,
                                              claim_token=claim.claim_token):
                continue
            with SessionLocal() as session:
                repository.complete_claim(session, owner_id=owner_id, run_id=claim.id,
                                          claim_token=claim.claim_token, status="error",
                                          note=f"restart dispatch failed: {exc}")
                session.commit()
    return launched


def dispatch_all_reclaimable() -> list[int]:
    """Boot-time bounded dispatcher for every tenant with pending/expired work."""
    with SessionLocal() as session:
        owners = list(session.scalars(select(BacktestRun.owner_id).where(
            BacktestRun.status.in_(("pending", "running"))).distinct()))
    launched: list[int] = []
    for owner_id in owners:
        reconcile_stale_runs(owner_id=owner_id)
        remaining = max(0, int(get_settings().backtest_host_active_jobs) - len(launched))
        if not remaining:
            break
        launched.extend(dispatch_reclaimable(owner_id=owner_id, maximum=remaining))
    return launched


def _cell_values(provider, specs, intervals, capital, win, strategies,
                 pinned, workers, *, owner_id: str, run_id: int | None = None,
                 guard: _ClaimGuard | None = None):
    """Yield one serialized result payload per cell, in request order.

    Serial by default and by reference: `workers <= 1` walks the cells in this
    process, which is the implementation every parallel result is compared
    against (`tests/test_backtest_parallel.py`).
    """
    count = _worker_count(workers)
    if count > 1:
        yield from _parallel_cell_values(
            provider, specs, intervals, capital, win, strategies, pinned, count,
            owner_id=owner_id, run_id=run_id, guard=guard)
        return
    for inst in specs:
        if guard is not None:
            guard.ensure_active()
        for interval in intervals:
            if guard is not None:
                guard.ensure_active()
            prepared = _prepare_dataset(provider, inst, interval, win,
                                        pinned=pinned)
            for strat in strategies:
                if guard is not None:
                    guard.ensure_active()
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
                strategy_version=cell["strategy_version"],
                error=f"parallel worker: {exc}"))
            continue
        if frame is None:
            frame = prepare_signal_frame(candles)
        out.append(_compute_values(
            candles, inst, interval, payload["capital"], strat, cell["params"],
            payload["slippage_pct"], cell["phash"], frame=frame, **meta))
    return out


_WORKER_STORES: dict[str, dataset_store.PublicDatasetStorage] = {}


def _worker_store(descriptor: dict) -> dataset_store.PublicDatasetStorage:
    """One storage-port handle per worker descriptor, selected by the parent."""
    key = json.dumps(descriptor, sort_keys=True, separators=(",", ":"))
    store = _WORKER_STORES.get(key)
    if store is None:
        store = _WORKER_STORES[key] = dataset_store.open_worker_storage(descriptor)
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
        lambda address: _worker_store(payload["storage_descriptor"]).get(address),
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
                           strategy_version=next((cell["strategy_version"] for cell in payload["cells"]
                                                  if cell["strategy_key"] == key), "unknown"),
                           error=prepared.error)
            for key in payload["strategy_keys"]]}
    return {"refused": False, "rows": _worker_task(dict(
        payload, candles=prepared.candles, bars=prepared.bars,
        first_ts=prepared.first_ts, last_ts=prepared.last_ts,
        effective_days=prepared.effective_days, clamped=prepared.clamped)),
        "public_dataset": {"dataset_address": prepared.dataset_address,
                           "dataset_classification": prepared.dataset_classification,
                           "dataset_verified": prepared.dataset_verified}}


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
                strategy_version=strat.version,
                error=prepared.error)))
            continue
        phash = _execution_address(prepared, inst, interval, capital, win, strat,
                                   slippage_pct)
        cached = _reusable_values(inst, interval, phash, prepared.last_ts, owner_id=owner_id)
        if cached is not None:
            _measure("cache_owner_local", owner_id=owner_id)
            slots.append(("ready", cached))
            continue
        public = _public_reusable_values(prepared, strat, phash)
        if public is not None:
            _measure("cache_public_shared", owner_id=owner_id)
            slots.append(("ready", public))
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
                   "storage_descriptor": dataset_store.get_store().worker_descriptor(),
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


def _drain_with_metadata(slots, future) -> tuple[list[dict], dict | None]:
    """One dataset's results, in slot order, from whichever task computed it."""
    if future is None:
        return _merge(slots, ()), None
    result = future.result()
    if isinstance(result, dict):          # a pinned dataset's verdict
        if result["refused"]:
            # The dataset itself is unservable: every cell of it is that
            # refusal, including cells the parent had planned from the cache.
            return result["rows"], None
        return _merge(slots, result["rows"]), result.get("public_dataset")
    return _merge(slots, result), None


def _drain(slots, future) -> list[dict]:
    """Compatibility result-only drain used by focused worker tests."""
    return _drain_with_metadata(slots, future)[0]


def _publish_parallel_rows(prepared, strategies, rows) -> None:
    """The parent owns shared DB publication after worker arithmetic completes."""
    by_identity = {(strategy.key, strategy.version): strategy for strategy in strategies}
    for row in rows:
        if row.get("from_cache") or row.get("error"):
            continue
        strategy = by_identity.get((row.get("strategy_key"), row.get("strategy_version")))
        if strategy is not None:
            _measure("cache_cold")
            _publish_public_computation(prepared, strategy, row.get("params_hash", ""), row)


def _parallel_cell_values(provider, specs, intervals, capital, win, strategies,
                          pinned, workers, *, owner_id: str,
                          run_id: int | None = None,
                          guard: _ClaimGuard | None = None):
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
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            _measure_set("active_process_pools", 1, owner_id=owner_id, run_id=run_id)
            for inst in specs:
                if guard is not None:
                    guard.ensure_active()
                for interval in intervals:
                    if guard is not None:
                        guard.ensure_active()
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
                    if guard is not None:
                        guard.ensure_active()
                    future = pool.submit(task, payload) if payload else None
                    public_prepared = _PreparedDataset(
                        dataset_address=prepared.dataset_address,
                        dataset_classification=prepared.dataset_classification,
                        dataset_verified=prepared.dataset_verified)
                    pending.append((future, slots, public_prepared))
                    _measure_set("inflight_datasets", len(pending), owner_id=owner_id, run_id=run_id)
                    # `prepared` (and its lazily-built frame) is dropped here: the
                    # parent never holds a dataset past its submission.
                    del prepared, payload
                    while len(pending) >= max_inflight:
                        if guard is not None:
                            guard.ensure_active()
                        future, slots, prepared = pending.popleft()
                        _measure_set("inflight_datasets", len(pending), owner_id=owner_id, run_id=run_id)
                        rows, verified = _drain_with_metadata(slots, future)
                        if verified is not None:
                            prepared = _PreparedDataset(
                                dataset_address=verified["dataset_address"],
                                dataset_classification=verified["dataset_classification"],
                                dataset_verified=verified["dataset_verified"])
                        _publish_parallel_rows(prepared, strategies, rows)
                        yield from rows
            while pending:
                if guard is not None:
                    guard.ensure_active()
                future, slots, prepared = pending.popleft()
                _measure_set("inflight_datasets", len(pending), owner_id=owner_id, run_id=run_id)
                rows, verified = _drain_with_metadata(slots, future)
                if verified is not None:
                    prepared = _PreparedDataset(
                        dataset_address=verified["dataset_address"],
                        dataset_classification=verified["dataset_classification"],
                        dataset_verified=verified["dataset_verified"])
                _publish_parallel_rows(prepared, strategies, rows)
                yield from rows
    finally:
        _measure_set("active_process_pools", 0, owner_id=owner_id, run_id=run_id)
        _measure_set("inflight_datasets", 0, owner_id=owner_id, run_id=run_id)


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
        _measure("provider_reads")
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
            _measure("dataset_store_write_failures")
            log.warn(f"backtest dataset not stored for "
                     f"{inst.key}/{interval}: {exc}")
    return _PreparedDataset(
        candles=candles, bars=len(candles), first_ts=first_ts, last_ts=last_ts,
        effective_days=effective_days, clamped=clamped,
        dataset_address=dataset_address, dataset_verified=bool(dataset_address))


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
    def read_store(address):
        _measure("dataset_store_reads")
        return dataset_store.get_store().get(address)
    return _pinned_dataset_from_store(
        read_store,
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
        dataset_address=stored.address, dataset_classification=stored.classification,
        dataset_verified=True)


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
            strategy_version=strat.version,
            error=prepared.error)
    slippage_pct = float(get_settings().backtest_slippage_pct)
    phash = _execution_address(prepared, inst, interval, capital, win, strat,
                               slippage_pct)
    cached = _reusable_values(inst, interval, phash, prepared.last_ts, owner_id=owner_id)
    if cached is not None:
        _measure("cache_owner_local", owner_id=owner_id)
        return cached
    public = _public_reusable_values(prepared, strat, phash)
    if public is not None:
        _measure("cache_public_shared", owner_id=owner_id)
        return public
    values = _compute_values(
        prepared.candles, inst, interval, capital, strat,
        dict(strat.default_params), slippage_pct, phash,
        bars=prepared.bars, first_ts=prepared.first_ts, last_ts=prepared.last_ts,
        effective_days=prepared.effective_days, clamped=prepared.clamped,
        frame=prepared.frame)
    _measure("cache_cold", owner_id=owner_id)
    _publish_public_computation(prepared, strat, phash, values)
    return values


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


def _public_manifest(prepared: _PreparedDataset) -> dict:
    """The public proof held by this caller before it can even query shared state."""
    return {"dataset_address": prepared.dataset_address,
            "dataset_verified": prepared.dataset_verified}


def _public_reusable_values(prepared: _PreparedDataset, strat, phash: str) -> dict | None:
    """Shared lookup after explicit eligibility; private inputs never probe it."""
    if not phash or not prepared.dataset_address:
        return None
    from app.backtest import public_computation
    manifest = _public_manifest(prepared)
    if not (public_computation.strategy_is_platform_public(strat)
            and public_computation.is_eligible(
                dataset_classification=prepared.dataset_classification,
                strategy_key=strat.key, strategy_module=type(strat).__module__,
                execution_manifest=manifest)):
        return None
    try:
        with SessionLocal() as session:
            return public_computation.maybe_materialize(
                session, execution_address=phash,
                dataset_classification=prepared.dataset_classification,
                strategy_key=strat.key, strategy_module=type(strat).__module__,
                strategy_version=strat.version, policy_address=phash,
                execution_manifest=manifest)
    # A global cache problem cannot turn a valid customer computation into a
    # failed run.  It is bounded telemetry, then a cold owner-local result.
    except public_computation.PublicComputationIntegrityError as exc:
        _measure("cache_public_integrity_failures")
        log.error(f"public backtest computation integrity refusal: {exc}")
        return None
    except Exception as exc:
        _measure("cache_public_write_failures")
        log.warn(f"public backtest computation lookup unavailable: {exc}")
        return None


def _publish_public_computation(prepared: _PreparedDataset, strat, phash: str,
                                values: dict) -> None:
    """Publish immutable pure bytes opportunistically after a cold public result."""
    if not phash or values.get("error"):
        return
    from app.backtest import public_computation
    manifest = _public_manifest(prepared)
    if not (public_computation.strategy_is_platform_public(strat)
            and public_computation.is_eligible(
                dataset_classification=prepared.dataset_classification,
                strategy_key=strat.key, strategy_module=type(strat).__module__,
                execution_manifest=manifest)):
        return
    try:
        with SessionLocal() as session:
            public_computation.put_immutable(
                session, execution_address=phash, dataset_address=prepared.dataset_address,
                strategy_key=strat.key, strategy_version=strat.version,
                # phash binds every public policy/input that can change this payload.
                policy_address=phash,
                payload=public_computation.public_result_payload(values))
            session.commit()
    except public_computation.PublicComputationIntegrityError as exc:
        # Never overwrite or read a competing result. The caller still has a
        # fresh owner-local cold result, which is safer than suppressing evidence.
        log.error(f"public backtest computation integrity refusal: {exc}")
        _measure("cache_public_integrity_failures")
    except Exception as exc:
        _measure("cache_public_write_failures")
        log.warn(f"public backtest computation publish unavailable: {exc}")


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
        strategy_version=strat.version,
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
                   strategy_version="",
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
                  segment=seg, strategy_key=strategy_key, strategy_version=strategy_version,
                  interval=interval, bars=bars,
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
    return dict(error="", trades=m.trades, wins=m.wins, win_rate=m.win_rate,
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
    """Compatibility refusal: every production write requires a lease token."""
    raise ValueError("backtest batch persistence requires a durable claim token")


def _commit_claimed_batch(run_id, values: list[dict], *, owner_id: str,
                          claim_token: str, status: str = "", note: str = "") -> bool:
    """Commit only while this worker owns the durable lease.

    Cancellation is observed before every batch; already-computed work is simply
    discarded after a cancellation request, never committed under an old token.
    """
    if len(values) > BATCH_SIZE:
        raise RuntimeError(f"batch of {len(values)} exceeds BATCH_SIZE={BATCH_SIZE}")
    started = time.monotonic()
    with SessionLocal() as session:
        if repository.is_cancel_requested(session, owner_id=owner_id, run_id=run_id,
                                          claim_token=claim_token):
            repository.complete_claim(session, owner_id=owner_id, run_id=run_id,
                                      claim_token=claim_token, status="cancelled")
            session.commit()
            return False
        if values and not repository.append_claimed_result_batch(
                session, owner_id=owner_id, run_id=run_id, claim_token=claim_token,
                values=values, lease_seconds=get_settings().backtest_claim_lease_seconds):
            session.rollback()
            return False
        if values:
            _measure("batch_persists", owner_id=owner_id, run_id=run_id)
        if status:
            if repository.is_cancel_requested(session, owner_id=owner_id, run_id=run_id,
                                              claim_token=claim_token):
                status = "cancelled"
            if not repository.complete_claim(session, owner_id=owner_id, run_id=run_id,
                                             claim_token=claim_token, status=status, note=note):
                session.rollback()
                return False
        session.commit()
        _measure("batch_persist_seconds", time.monotonic() - started,
                 owner_id=owner_id, run_id=run_id)
        return True


def reconcile_stale_runs(*, owner_id: str) -> int:
    """Requeue only expired durable leases and retire claimless legacy phantoms.

    A non-expired token can belong to another process, so restart never changes
    it. Progress remains derived from durable result rows for legacy records.
    """
    with SessionLocal() as s:
        repaired = repository.reconcile_expired_claims(s, owner_id=owner_id)
        if repaired:
            s.commit()
    return repaired
