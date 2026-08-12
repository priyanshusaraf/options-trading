"""Durable, tenant-scoped ownership of asynchronous backtest work.

These tests name the persistence decisions that make a local worker replaceable:
the run row, not a Python global, grants permission to write; its claim token
fences every mutating operation.
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from sqlalchemy import select
from fastapi.testclient import TestClient

from app.backtest import repository
from app.backtest import sweep
from app.db.models import BacktestResult, BacktestRun, Organization
from app.db.session import SessionLocal, init_db


def _run(owner_id: str, *, total: int = 2) -> int:
    with SessionLocal() as session:
        run = repository.enqueue_run(
            session, owner_id=owner_id, scope="liquid", intervals="day",
            capital=1.0, total=total)
        session.commit()
        return run.id


def _value(key: str) -> dict:
    return {"instrument_key": key, "name": key, "segment": "nse_delivery",
            "strategy_key": "trend_impulse_v3", "interval": "day", "bars": 1,
            "strategy_version": "strategy-version-v1", "params_hash": "strategy-version-and-params-v1", "error": ""}


def test_claim_race_allows_exactly_one_token_and_never_blocks_another_owner():
    """Removing the conditional status/expiry predicate would make both win."""
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="a", name="A"),
                         Organization(organization_id="b", name="B")])
        session.commit()
    a, b = _run("a"), _run("b")
    now = dt.datetime(2026, 8, 12, 10, tzinfo=dt.timezone.utc)
    with SessionLocal() as first, SessionLocal() as second:
        a_claim = repository.claim_next_run(first, owner_id="a", claimed_by="worker-a",
                                            now=now, lease_seconds=30)
        first.commit()
        b_claim = repository.claim_next_run(second, owner_id="b", claimed_by="worker-b",
                                            now=now, lease_seconds=30)
        second.commit()
    with SessionLocal() as session:
        repeat = repository.claim_run(session, owner_id="a", run_id=a,
                                      claimed_by="worker-2", now=now, lease_seconds=30)
    assert a_claim is not None and b_claim is not None
    assert a_claim.claim_token != b_claim.claim_token
    assert repeat is None


def test_replaced_or_cancelled_claim_cannot_append_or_finish_a_run():
    """Dropping owner, token, expiry or cancellation fences must fail this test."""
    init_db(reset=True)
    with SessionLocal() as session:
        session.add(Organization(organization_id="a", name="A")); session.commit()
    run_id = _run("a")
    started = dt.datetime(2026, 8, 12, 10, tzinfo=dt.timezone.utc)
    with SessionLocal() as session:
        old = repository.claim_run(session, owner_id="a", run_id=run_id,
                                   claimed_by="old", now=started, lease_seconds=1)
        session.commit()
    with SessionLocal() as session:
        new = repository.claim_run(session, owner_id="a", run_id=run_id,
                                   claimed_by="new", now=started + dt.timedelta(seconds=2),
                                   lease_seconds=30)
        session.commit()
    assert old is not None and new is not None and old.claim_token != new.claim_token
    with SessionLocal() as session:
        assert not repository.append_claimed_result_batch(
            session, owner_id="a", run_id=run_id, claim_token=old.claim_token,
            values=[_value("OLD")], now=started + dt.timedelta(seconds=2))
        assert not repository.complete_claim(session, owner_id="a", run_id=run_id,
                                             claim_token=old.claim_token,
                                             status="done", now=started + dt.timedelta(seconds=2))
        assert repository.request_cancel(session, owner_id="a", run_id=run_id,
                                         now=started + dt.timedelta(seconds=3))
        session.commit()
    with SessionLocal() as session:
        assert not repository.append_claimed_result_batch(
            session, owner_id="a", run_id=run_id, claim_token=new.claim_token,
            values=[_value("NEW")], now=started + dt.timedelta(seconds=4))
        assert repository.complete_claim(session, owner_id="a", run_id=run_id,
                                         claim_token=new.claim_token, status="cancelled",
                                         now=started + dt.timedelta(seconds=4))
        session.commit()
        run = repository.get_run(session, owner_id="a", run_id=run_id)
        assert run.status == "cancelled" and run.done == 0
        assert session.scalars(select(BacktestResult).where(BacktestResult.run_id == run_id)).all() == []


def test_replacement_resumes_only_cells_not_already_durable():
    """A new claimant must not duplicate a cell completed by the old claimant."""
    init_db(reset=True)
    run_id = _run("owner", total=2)
    started = dt.datetime(2026, 8, 12, 10, tzinfo=dt.timezone.utc)
    with SessionLocal() as session:
        first = repository.claim_run(session, owner_id="owner", run_id=run_id,
                                     claimed_by="first", now=started, lease_seconds=1)
        session.commit()
    assert first is not None
    with SessionLocal() as session:
        assert repository.append_claimed_result_batch(
            session, owner_id="owner", run_id=run_id, claim_token=first.claim_token,
            values=[_value("NIFTY")], now=started + dt.timedelta(milliseconds=100),
            lease_seconds=1)
        session.commit()
    with SessionLocal() as session:
        second = repository.claim_run(session, owner_id="owner", run_id=run_id,
                                      claimed_by="second", now=started + dt.timedelta(seconds=2),
                                      lease_seconds=30)
        session.commit()
    assert second is not None
    with SessionLocal() as session:
        assert repository.append_claimed_result_batch(
            session, owner_id="owner", run_id=run_id, claim_token=second.claim_token,
            values=[_value("NIFTY"), _value("BANKNIFTY")],
            now=started + dt.timedelta(seconds=3))
        session.commit()
    with SessionLocal() as session:
        rows = list(session.scalars(select(BacktestResult).where(
            BacktestResult.run_id == run_id).order_by(BacktestResult.instrument_key)))
        run = repository.get_run(session, owner_id="owner", run_id=run_id)
    assert [row.instrument_key for row in rows] == ["BANKNIFTY", "NIFTY"]
    assert run.done == run.total == 2


def test_cancelling_pending_run_is_terminal_and_releases_admission_capacity():
    """A job with no claimant cannot wait forever for a worker to cancel it."""
    init_db(reset=True)
    run_id = _run("owner")
    with SessionLocal() as session:
        assert repository.request_cancel(session, owner_id="owner", run_id=run_id)
        session.commit()
    with SessionLocal() as session:
        run = repository.get_run(session, owner_id="owner", run_id=run_id)
    assert run.status == "cancelled"
    assert run.completed_at is not None
    assert run.claim_token is None


def test_slow_provider_is_heartbeated_then_cancellation_stops_next_cell(monkeypatch):
    """Lease liveness must not depend on reaching a persistence batch boundary."""
    init_db(reset=True)
    run_id = _run("owner", total=2)
    with SessionLocal() as session:
        claim = repository.claim_run(session, owner_id="owner", run_id=run_id,
                                     claimed_by="worker", lease_seconds=1)
        session.commit()
    assert claim is not None
    settings = sweep.get_settings().model_copy(update={"backtest_claim_lease_seconds": 1})
    monkeypatch.setattr(sweep, "get_settings", lambda: settings)
    entered = threading.Event()
    calls = {"datasets": 0}
    def slow_dataset(*_args, **_kwargs):
        calls["datasets"] += 1
        entered.set()
        time.sleep(0.55)
        return sweep._PreparedDataset(error="stub")
    monkeypatch.setattr(sweep, "_prepare_dataset", slow_dataset)
    thread = threading.Thread(target=sweep._run, args=(
        run_id, object(), [object(), object()], ["day"], 1.0,
        {"lookback_days": None, "start": None, "end": None, "label": "max"}, []),
        kwargs={"owner_id": "owner", "claim_token": claim.claim_token})
    thread.start()
    assert entered.wait(timeout=1)
    with SessionLocal() as session:
        assert repository.request_cancel(session, owner_id="owner", run_id=run_id)
        session.commit()
    thread.join(timeout=3)
    assert not thread.is_alive()
    with SessionLocal() as session:
        run = repository.get_run(session, owner_id="owner", run_id=run_id)
    assert calls["datasets"] == 1
    assert run.status == "cancelled" and run.done == 0


def test_restart_dispatch_claims_pending_descriptor_without_provider_object(monkeypatch):
    """Recovery must launch durable request data, never a pickled provider/session."""
    init_db(reset=True)
    descriptor = {
        "scope": "liquid", "intervals": ["day"], "capital": 1.0,
        "instruments": ["NIFTY"], "lookback_days": None,
        "start_date": None, "end_date": None,
        "strategies": ["trend_impulse_v3"], "pinned_datasets": {}, "workers": 1,
    }
    with SessionLocal() as session:
        run = repository.enqueue_run(session, owner_id="owner", scope="liquid",
                                     intervals="day", capital=1.0, total=1,
                                     request_json=__import__("json").dumps(descriptor))
        session.commit()
    class _Thread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def is_alive(self): return False
    monkeypatch.setattr(sweep.threading, "Thread", _Thread)
    launched = sweep.dispatch_reclaimable(owner_id="owner", maximum=1)
    assert launched == [run.id]
    with SessionLocal() as session:
        claimed = repository.get_run(session, owner_id="owner", run_id=run.id)
    assert claimed.status == "running" and claimed.claim_token is not None


def test_global_restart_dispatch_reclaims_nonlegacy_owner(monkeypatch):
    """A startup dispatcher restricted to the legacy owner strands tenant work."""
    init_db(reset=True)
    with SessionLocal() as session:
        session.add(Organization(organization_id="tenant", name="Tenant")); session.flush()
        run = repository.enqueue_run(session, owner_id="tenant", scope="liquid",
                                     intervals="day", capital=1.0, total=1,
                                     request_json=__import__("json").dumps({
                                         "scope": "liquid", "intervals": ["day"], "capital": 1.0,
                                         "instruments": ["NIFTY"], "strategies": ["trend_impulse_v3"],
                                         "pinned_datasets": {}, "workers": 1}))
        session.commit()
    class _Thread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def is_alive(self): return False
    monkeypatch.setattr(sweep.threading, "Thread", _Thread)
    assert sweep.dispatch_all_reclaimable() == [run.id]
    with SessionLocal() as session:
        assert repository.get_run(session, owner_id="tenant", run_id=run.id).status == "running"


def test_measurement_snapshot_reports_state_without_product_user_limit():
    init_db(reset=True)
    run_id = _run("owner", total=37)
    with SessionLocal() as session:
        snapshot = sweep.measurement_snapshot(owner_id="owner", session=session)
    assert snapshot["queued_jobs"] == 1
    assert snapshot["reserved_cells"] == 37
    assert snapshot["active_jobs"] == 0


def test_batch_progress_and_heartbeat_roll_back_together_on_error(monkeypatch):
    """Removing the one-transaction update would leave a durable partial batch."""
    init_db(reset=True)
    run_id = _run("owner")
    now = dt.datetime(2026, 8, 12, 10, tzinfo=dt.timezone.utc)
    with SessionLocal() as session:
        claim = repository.claim_run(session, owner_id="owner", run_id=run_id,
                                     claimed_by="w", now=now, lease_seconds=30)
        session.commit()
    real = repository.durable_result_count
    def fail_count(*args, **kwargs):
        raise RuntimeError("count failed")
    monkeypatch.setattr(repository, "durable_result_count", fail_count)
    with SessionLocal() as session:
        try:
            repository.append_claimed_result_batch(
                session, owner_id="owner", run_id=run_id, claim_token=claim.claim_token,
                values=[_value("ONE")], now=now + dt.timedelta(seconds=1))
            session.commit()
        except RuntimeError:
            session.rollback()
    monkeypatch.setattr(repository, "durable_result_count", real)
    with SessionLocal() as session:
        run = repository.get_run(session, owner_id="owner", run_id=run_id)
        assert run.done == 0 and run.heartbeat_at == now.replace(tzinfo=None)
        assert session.scalars(select(BacktestResult).where(BacktestResult.run_id == run_id)).all() == []


def test_reconciliation_only_requeues_expired_claims():
    """Replacing all running rows on restart would make the live lease disappear."""
    init_db(reset=True)
    expired_id, live_id = _run("owner"), _run("owner")
    now = dt.datetime(2026, 8, 12, 10, tzinfo=dt.timezone.utc)
    with SessionLocal() as session:
        repository.claim_run(session, owner_id="owner", run_id=expired_id,
                             claimed_by="expired", now=now, lease_seconds=1)
        repository.claim_run(session, owner_id="owner", run_id=live_id,
                             claimed_by="live", now=now, lease_seconds=60)
        session.commit()
    with SessionLocal() as session:
        assert repository.reconcile_expired_claims(
            session, owner_id="owner", now=now + dt.timedelta(seconds=2)) == 1
        session.commit()
        expired = repository.get_run(session, owner_id="owner", run_id=expired_id)
        live = repository.get_run(session, owner_id="owner", run_id=live_id)
        assert expired.status == "pending" and expired.claim_token is None
        assert live.status == "running" and live.claimed_by == "live"


def test_admission_is_per_workload_not_a_process_global(monkeypatch):
    """The previous `_running` guard rejected this before either run had work."""
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="a", name="A"),
                         Organization(organization_id="b", name="B")])
        session.commit()
    monkeypatch.setattr(sweep, "reconcile_stale_runs", lambda **_kw: 0)
    # The guard is intentionally set without a live worker. Durable admission,
    # not that unrelated process state, decides whether this new workload may run.
    monkeypatch.setattr(sweep, "_running", True)
    class _Thread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def join(self): pass
    monkeypatch.setattr(sweep.threading, "Thread", _Thread)
    run_id = sweep.start_sweep(owner_id="a", intervals=["day"], instruments=["NIFTY"])
    assert run_id > 0


def test_zero_host_budget_rejects_before_provider_or_worker_creation(monkeypatch):
    """Deleting the host budget predicate would start work despite explicit overload."""
    init_db(reset=True)
    settings = type("Settings", (), {
        "backtest_host_active_jobs": 0, "backtest_owner_active_jobs": 1,
        "backtest_owner_queued_jobs": 1, "backtest_host_requested_cells": 10,
        "backtest_host_worker_slots": 1, "backtest_claim_lease_seconds": 30,
        "backtest_sweep_workers": 1, "backtest_slippage_pct": 0.0})()
    monkeypatch.setattr(sweep, "get_settings", lambda: settings)
    reads = {"count": 0}
    class _Provider:
        def get_candles(self, *args, **kwargs):
            reads["count"] += 1
    monkeypatch.setattr(sweep, "get_provider", lambda: _Provider())
    try:
        sweep.start_sweep(owner_id="owner", intervals=["day"], instruments=["NIFTY"])
    except sweep.WorkloadAdmissionError as exc:
        assert exc.reason == "host_active_jobs"
    else:
        raise AssertionError("zero configured host capacity must reject")
    assert reads["count"] == 0


def test_concurrent_admission_reserves_exact_host_capacity_once(monkeypatch):
    """Removing SQLite's reservation transaction can admit two one-slot jobs."""
    import threading
    real_thread = threading.Thread
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="a", name="A"),
                         Organization(organization_id="b", name="B")]); session.commit()
    settings = type("Settings", (), {
        "backtest_host_active_jobs": 1, "backtest_owner_active_jobs": 1,
        "backtest_owner_queued_jobs": 2, "backtest_host_requested_cells": 2,
        "backtest_host_worker_slots": 1, "backtest_claim_lease_seconds": 30,
        "backtest_sweep_workers": 1, "backtest_slippage_pct": 0.0})()
    monkeypatch.setattr(sweep, "get_settings", lambda: settings)
    class _Thread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def join(self): pass
        def is_alive(self): return False
    monkeypatch.setattr(sweep.threading, "Thread", _Thread)
    gate = threading.Barrier(2)
    outcomes = []
    def submit(owner):
        gate.wait()
        try:
            outcomes.append((owner, "ok", sweep.start_sweep(
                owner_id=owner, intervals=["day"], instruments=["NIFTY"])))
        except sweep.WorkloadAdmissionError as exc:
            outcomes.append((owner, "rejected", exc.reason))
    threads = [real_thread(target=submit, args=(owner,)) for owner in ("a", "b")]
    [thread.start() for thread in threads]; [thread.join() for thread in threads]
    assert sorted(kind for _, kind, _ in outcomes) == ["ok", "rejected"]
    assert [reason for _, kind, reason in outcomes if kind == "rejected"] in (
        ["host_active_jobs"], ["host_worker_slots"])


def test_launch_failure_releases_its_own_claimed_capacity(monkeypatch):
    """A failure after enqueue must not leave an invisible forever-running lease."""
    init_db(reset=True)
    class _BrokenThread:
        def __init__(self, *args, **kwargs): pass
        def start(self): raise RuntimeError("thread start exploded")
        def is_alive(self): return False
    monkeypatch.setattr(sweep.threading, "Thread", _BrokenThread)
    try:
        sweep.start_sweep(owner_id="owner", intervals=["day"], instruments=["NIFTY"])
    except RuntimeError as exc:
        assert "thread start exploded" in str(exc)
    with SessionLocal() as session:
        run = repository.latest_run(session, owner_id="owner")
        assert run.status == "error" and run.claim_token is not None


def test_cancel_foreign_and_absent_runs_have_the_same_owner_local_response(monkeypatch):
    """A missing owner predicate would let a guessed id cancel another tenant's run."""
    from app.api.principal import Principal, get_principal
    from app.main import app
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="a", name="A"),
                         Organization(organization_id="b", name="B")]); session.commit()
    foreign = _run("a")
    from app.api import backtest_routes
    monkeypatch.setattr(backtest_routes, "owner_id_for", lambda principal: principal.id)
    app.dependency_overrides[get_principal] = lambda: Principal(
        id="b", kind="owner", scopes=frozenset({"*"}))
    try:
        client = TestClient(app)
        foreign_response = client.post(f"/api/backtest/runs/{foreign}/cancel")
        absent_response = client.post("/api/backtest/runs/999999/cancel")
    finally:
        app.dependency_overrides.clear()
    assert (foreign_response.status_code, foreign_response.content) == (
        absent_response.status_code, absent_response.content)
    with SessionLocal() as session:
        assert repository.get_run(session, owner_id="a", run_id=foreign).cancel_requested_at is None
