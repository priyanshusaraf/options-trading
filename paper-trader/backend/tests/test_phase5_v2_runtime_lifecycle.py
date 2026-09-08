"""Direct P5-ADV-006-RUNTIME lifecycle and real-process evidence."""
from __future__ import annotations

import datetime as dt
import ast
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.backtest import repository, sweep, v2_lifecycle
from app.backtest.reclaim_authority import ReclaimAuthorityContext
from app.db.models import BacktestResult, BacktestRun, Base, Organization
from app.events.planes import execution_outbox


OWNER = "owner-a"
AUTHORITY_TIME = dt.datetime(2026, 8, 1, 3, tzinfo=dt.timezone.utc)
BACKEND = Path(__file__).resolve().parents[1]


def _persist_current_authority(execution, research, *, total: int = 1):
    """Persist one genuine complete Phase 4 two-plane chain and pending v2 run."""
    from app.core.strategy_admissions import put
    from app.market_data.authority import persist_capability_assessment
    from app.market_data.capability import assess_capability
    from app.strategy.admission import admit_phase4_v2_strategy
    from research.domain.admissions import store_admission
    from research.domain.migrate import migrate_research_db
    from research.domain.strategy_admissions import persist_verified_dataset_authority
    from tests.test_phase4_capability_admission import _evidence, _plan
    from tests.test_phase4_dataset_assessment_authority import (
        _authority, _seed_execution, address,
    )

    Base.metadata.create_all(execution)
    migrate_research_db(research)
    registry, document, plan = _plan()
    with Session(execution) as execution_session, Session(research) as research_session:
        execution_session.add(Organization(
            organization_id=OWNER, name="P5 v2 lifecycle owner"))
        execution_session.flush()
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        persist_verified_dataset_authority(
            research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=AUTHORITY_TIME)
        assessment = assess_capability(
            plan=plan, profile=values["profile"], owner_id=OWNER, mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address("evaluation-policy"),
            assessment_evidence_address=address("assessment-evidence"),
            at_time=int(AUTHORITY_TIME.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"])
        persist_capability_assessment(
            execution_session, assessment, plan=plan, at_time=AUTHORITY_TIME)
        wrapper = admit_phase4_v2_strategy(
            owner_id=OWNER, mode="RESEARCH", document=document, registry=registry,
            evidence=_evidence(), plan=plan,
            assessment_address=assessment.authority_address,
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=assessment.evaluation_policy_address,
            research_session=research_session,
            execution_session=execution_session, at_time=AUTHORITY_TIME)
        put(execution_session, wrapper)
        store_admission(research_session, wrapper)
        identity = {
            "strategy_key": f"ir.{wrapper.graph_identifier}",
            "strategy_version": str(wrapper.graph_version),
            "graph_address": wrapper.graph_address,
            "admission_address": wrapper.admission_address,
            "attribution_state": "VERIFIED_GRAPH",
        }
        descriptor = {
            "scope": "liquid",
            "intervals": ["day"],
            "capital": 1.0,
            "strategies": [{
                "key": identity["strategy_key"],
                "version": identity["strategy_version"],
            }],
            "admission_address": wrapper.admission_address,
            "attribution": identity,
            "_phase4_binding": wrapper.to_dict()["phase4_data_binding"],
        }
        descriptor["_phase4_binding"]["declaration_addresses"] = list(
            descriptor["_phase4_binding"]["declaration_addresses"])
        row = BacktestRun(
            owner_id=OWNER, scope="liquid", intervals="day", capital=1.0,
            total=total, status="pending", queued_at=dt.datetime.now(),
            admission_address=wrapper.admission_address,
            request_json=json.dumps(
                descriptor, sort_keys=True, separators=(",", ":")))
        execution_session.add(row)
        execution_session.commit()
        research_session.commit()
        return registry, wrapper, row.id


def _fixture_result(_admission=None, _descriptor=None):
    return [{
        "instrument_key": "NIFTY", "name": "NIFTY", "segment": "nse_delivery",
        "interval": "day", "bars": 1, "params_hash": "p5-v2-fixture-v1",
        "error": "",
    }]


def _fixture_cell(instrument: str, *, net_pnl: float = 0.0):
    return {
        **_fixture_result()[0],
        "instrument_key": instrument,
        "name": instrument,
        "net_pnl": net_pnl,
    }


def _die_executor(_admission, _descriptor):
    os._exit(23)


def _child_context(execution_url: str, research_url: str):
    from tests.test_phase4_capability_admission import _plan

    execution = sa.create_engine(execution_url, future=True)
    research = sa.create_engine(research_url, future=True)
    maker = sessionmaker(bind=execution)
    registry, _document, _plan_value = _plan()
    context = ReclaimAuthorityContext(
        registry=registry, research_sessionmaker=lambda: Session(research))
    sweep.SessionLocal = maker
    return execution, research, maker, context


def _load_current(maker, context, research, admission_address):
    with maker() as execution_session, Session(research) as research_session:
        return repository.load_verified_v2_lifecycle_admission(
            execution_session, owner_id=OWNER,
            admission_address=admission_address,
            authority_context=context, research_session=research_session,
            at_time=AUTHORITY_TIME)


def _child_entry(execution_url: str, research_url: str, mode: str,
                 supplied_token: str = "") -> None:
    execution, research, maker, context = _child_context(execution_url, research_url)
    try:
        if mode in {"die", "success"}:
            executor = _die_executor if mode == "die" else _fixture_result
            launched = sweep.dispatch_reclaimable(
                owner_id=OWNER, maximum=1, authority_context=context,
                _v2_lifecycle_executor=executor,
                _authority_at_time=AUTHORITY_TIME,
                _authority_clock=lambda: AUTHORITY_TIME)
            print(json.dumps({"launched": launched}))
            return
        with maker() as session:
            run = session.query(BacktestRun).one()
            token = supplied_token or run.claim_token or ""
            admission_address = run.admission_address
        operation_modes = {
            "heartbeat", "append", "release", "cancel", "complete", "finalize",
        }
        admission = (
            _load_current(maker, context, research, admission_address)
            if mode in operation_modes | {"retry", "mismatch", "refuse"}
            else None)
        if mode in operation_modes - {"finalize"}:
            with maker() as session:
                if mode == "heartbeat":
                    accepted = repository.heartbeat_claim(
                        session, owner_id=OWNER, run_id=run.id,
                        claim_token=token, lease_seconds=60)
                elif mode == "append":
                    accepted = repository.append_claimed_result_batch(
                        session, owner_id=OWNER, run_id=run.id,
                        claim_token=token,
                        values=[{
                            **_fixture_result()[0],
                            **v2_lifecycle.attribution(admission),
                        }],
                        lease_seconds=60,
                        verified_v2_admission=admission)
                elif mode == "release":
                    accepted = repository.release_claim(
                        session, owner_id=OWNER, run_id=run.id,
                        claim_token=token, note="fresh-process fence probe")
                else:
                    accepted = repository.complete_claim(
                        session, owner_id=OWNER, run_id=run.id,
                        claim_token=token,
                        status="cancelled" if mode == "cancel" else "done")
                session.commit()
            print(json.dumps({"operation": mode, "accepted": accepted}))
            return
        values = _fixture_result()
        if mode == "mismatch":
            values[0]["instrument_key"] = "BANKNIFTY"
        try:
            with maker() as session:
                outcome = v2_lifecycle.finalize_claimed_results(
                    session, owner_id=OWNER, run_id=run.id,
                    claim_token=token, admission=admission,
                    values=values, lease_seconds=1)
                session.commit()
            print(json.dumps({"state": outcome.state,
                              "durable_results": outcome.durable_results}))
        except v2_lifecycle.V2LifecycleRefused as exc:
            print(json.dumps({"refused": exc.code}))
    finally:
        execution.dispose()
        research.dispose()


def _run_child(execution_url: str, research_url: str, mode: str,
               token: str = "", *, lease_seconds: int = 1) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PT_BACKTEST_CLAIM_LEASE_SECONDS"] = str(lease_seconds)
    script = (
        "import sys; from tests.test_phase5_v2_runtime_lifecycle import _child_entry; "
        "_child_entry(*sys.argv[1:])")
    return subprocess.run(
        [sys.executable, "-c", script, execution_url, research_url, mode, token],
        cwd=BACKEND, env=environment, text=True, capture_output=True, check=False)


def _terminal_event_count(session, run_id: int) -> int:
    Event = execution_outbox().models.Event
    return int(session.scalar(sa.select(sa.func.count()).select_from(Event).where(
        Event.producer_key == f"backtest:{OWNER}:{run_id}:terminal:done")) or 0)


def _durable_snapshot(session, run_id: int):
    Event = execution_outbox().models.Event
    run = session.get(BacktestRun, run_id)
    results = list(session.scalars(sa.select(BacktestResult).where(
        BacktestResult.owner_id == OWNER,
        BacktestResult.run_id == run_id)))
    events = list(session.scalars(sa.select(Event)))

    def values(row):
        return tuple(
            (column.name, repr(getattr(row, column.name)))
            for column in row.__table__.columns)

    return {
        "run": values(run),
        "results": sorted(values(row) for row in results),
        "events": sorted(values(row) for row in events),
    }


def _assert_real_process_trace(execution, research, run_id: int) -> None:
    execution_url, research_url = str(execution.url), str(research.url)
    dead = _run_child(execution_url, research_url, "die")
    assert dead.returncode == 23, dead.stdout + dead.stderr
    maker = sessionmaker(bind=execution)
    with maker() as session:
        row = session.get(BacktestRun, run_id)
        first_token = row.claim_token
        assert row.status == "running" and first_token and row.attempt_count == 1
        assert repository.durable_result_count(session, owner_id=OWNER, run_id=run_id) == 0
        assert _terminal_event_count(session, run_id) == 0

    time.sleep(1.2)
    replacement = _run_child(execution_url, research_url, "success")
    assert replacement.returncode == 0, replacement.stdout + replacement.stderr
    assert json.loads(replacement.stdout)["launched"] == [run_id]
    with maker() as session:
        row = session.get(BacktestRun, run_id)
        winning_token = row.claim_token
        result = session.scalar(sa.select(BacktestResult).where(
            BacktestResult.owner_id == OWNER, BacktestResult.run_id == run_id))
        assert row.status == "done" and row.done == 1 and row.attempt_count == 2
        assert winning_token and winning_token != first_token
        assert result is not None
        assert (result.strategy_key, result.strategy_version,
                result.graph_address, result.admission_address,
                result.attribution_state) == (
                    "ir.phase4", "1", result.graph_address,
                    row.admission_address, "VERIFIED_GRAPH")
        assert result.graph_address.startswith("sha256:")
        assert _terminal_event_count(session, run_id) == 1

    retry = _run_child(execution_url, research_url, "retry", winning_token)
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert json.loads(retry.stdout) == {
        "state": v2_lifecycle.ALREADY_FINALIZED, "durable_results": 1}
    mismatch = _run_child(execution_url, research_url, "mismatch", winning_token)
    assert mismatch.returncode == 0, mismatch.stdout + mismatch.stderr
    assert json.loads(mismatch.stdout)["refused"] == "FINALIZATION_MISMATCH"
    for token in (first_token, uuid.uuid4().hex):
        refused = _run_child(execution_url, research_url, "refuse", token)
        assert refused.returncode == 0, refused.stdout + refused.stderr
        assert json.loads(refused.stdout)["refused"] == "CLAIM_LOST"
    with maker() as session:
        assert repository.durable_result_count(session, owner_id=OWNER, run_id=run_id) == 1
        assert _terminal_event_count(session, run_id) == 1


def _assert_fresh_process_fence_matrix(execution, research, run_id: int) -> None:
    execution_url, research_url = str(execution.url), str(research.url)
    first = _run_child(execution_url, research_url, "die", lease_seconds=1)
    assert first.returncode == 23, first.stdout + first.stderr
    maker = sessionmaker(bind=execution)
    with maker() as session:
        first_token = session.get(BacktestRun, run_id).claim_token
        assert first_token

    time.sleep(1.2)
    second = _run_child(execution_url, research_url, "die", lease_seconds=60)
    assert second.returncode == 23, second.stdout + second.stderr
    with maker() as session:
        row = session.get(BacktestRun, run_id)
        second_token = row.claim_token
        assert (row.status == "running" and row.attempt_count == 2
                and second_token and second_token != first_token)

    stale_tokens = (first_token, uuid.uuid4().hex)
    for token in stale_tokens:
        for operation in ("heartbeat", "append", "release", "complete", "finalize"):
            with maker() as session:
                before = _durable_snapshot(session, run_id)
            refused = _run_child(
                execution_url, research_url, operation, token,
                lease_seconds=60)
            assert refused.returncode == 0, refused.stdout + refused.stderr
            response = json.loads(refused.stdout)
            if operation == "finalize":
                assert response == {"refused": "CLAIM_LOST"}
            else:
                assert response == {"operation": operation, "accepted": False}
            with maker() as session:
                assert _durable_snapshot(session, run_id) == before

    with maker() as session:
        assert repository.request_cancel(
            session, owner_id=OWNER, run_id=run_id)
        session.commit()
        cancellation_baseline = _durable_snapshot(session, run_id)
    for token in stale_tokens:
        refused = _run_child(
            execution_url, research_url, "cancel", token,
            lease_seconds=60)
        assert refused.returncode == 0, refused.stdout + refused.stderr
        assert json.loads(refused.stdout) == {
            "operation": "cancel", "accepted": False}
        with maker() as session:
            assert _durable_snapshot(session, run_id) == cancellation_baseline


def test_sqlite_real_process_death_reclaim_and_exactly_once_finalize(tmp_path):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        _registry, _wrapper, run_id = _persist_current_authority(execution, research)
        execution.dispose(); research.dispose()
        execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
        research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
        _assert_real_process_trace(execution, research, run_id)
    finally:
        execution.dispose()
        research.dispose()


def test_postgresql16_real_process_death_reclaim_and_exactly_once_finalize(pg_sandbox):
    execution = pg_sandbox.engine("p5_v2_execution")
    research = pg_sandbox.engine("p5_v2_research")
    _registry, _wrapper, run_id = _persist_current_authority(execution, research)
    _assert_real_process_trace(execution, research, run_id)


def test_sqlite_fresh_process_stale_and_competing_operation_matrix(tmp_path):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        _registry, _wrapper, run_id = _persist_current_authority(execution, research)
        execution.dispose(); research.dispose()
        execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
        research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
        _assert_fresh_process_fence_matrix(execution, research, run_id)
    finally:
        execution.dispose()
        research.dispose()


def test_postgresql16_fresh_process_stale_and_competing_operation_matrix(pg_sandbox):
    execution = pg_sandbox.engine("p5_v2_fence_execution")
    research = pg_sandbox.engine("p5_v2_fence_research")
    _registry, _wrapper, run_id = _persist_current_authority(execution, research)
    _assert_fresh_process_fence_matrix(execution, research, run_id)


def test_production_public_seam_retains_terminal_before_claim_provider_cache_or_worker(
        tmp_path, monkeypatch):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        registry, _wrapper, run_id = _persist_current_authority(execution, research)
        maker = sessionmaker(bind=execution)
        monkeypatch.setattr(sweep, "SessionLocal", maker)
        for name in ("get_provider", "_run", "_reusable_values",
                     "_public_reusable_values", "_publish_public_computation"):
            monkeypatch.setattr(
                sweep, name,
                lambda *_args, _name=name, **_kwargs:
                (_ for _ in ()).throw(AssertionError(_name)))
        context = ReclaimAuthorityContext(
            registry=registry, research_sessionmaker=lambda: Session(research))
        assert sweep.dispatch_reclaimable(
            owner_id=OWNER, maximum=1, authority_context=context,
            _authority_at_time=AUTHORITY_TIME,
            _authority_clock=lambda: AUTHORITY_TIME) == []
        with maker() as session:
            row = session.get(BacktestRun, run_id)
            assert row.status == "pending" and row.claim_token is None
            assert repository.durable_result_count(
                session, owner_id=OWNER, run_id=run_id) == 0
    finally:
        execution.dispose()
        research.dispose()


def test_success_reloads_fresh_authority_before_write_and_skips_legacy_consumers(
        tmp_path, monkeypatch):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        registry, _wrapper, run_id = _persist_current_authority(execution, research)
        maker = sessionmaker(bind=execution)
        monkeypatch.setattr(sweep, "SessionLocal", maker)
        for name in ("get_provider", "_run", "_reusable_values",
                     "_public_reusable_values", "_publish_public_computation"):
            monkeypatch.setattr(
                sweep, name,
                lambda *_args, _name=name, **_kwargs:
                (_ for _ in ()).throw(AssertionError(_name)))
        context = ReclaimAuthorityContext(
            registry=registry, research_sessionmaker=lambda: Session(research))
        real_loader = repository.load_verified_v2_lifecycle_admission
        calls = []

        def observing_loader(execution_session, **kwargs):
            calls.append((id(execution_session), id(kwargs["research_session"])))
            return real_loader(execution_session, **kwargs)

        monkeypatch.setattr(
            repository, "load_verified_v2_lifecycle_admission", observing_loader)
        assert sweep.dispatch_reclaimable(
            owner_id=OWNER, maximum=1, authority_context=context,
            _v2_lifecycle_executor=_fixture_result,
            _authority_at_time=AUTHORITY_TIME,
            _authority_clock=lambda: AUTHORITY_TIME) == [run_id]
        assert len(calls) == 3
        assert calls[0][1] == calls[1][1]
        assert calls[2][0] != calls[1][0] and calls[2][1] != calls[1][1]
        with maker() as session:
            assert session.get(BacktestRun, run_id).status == "done"
            assert repository.durable_result_count(
                session, owner_id=OWNER, run_id=run_id) == 1
    finally:
        execution.dispose()
        research.dispose()


def test_authority_withdrawn_by_executor_refuses_result_before_terminal_error(
        tmp_path, monkeypatch):
    from research.domain.models import ResearchStrategyAdmission

    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        registry, _wrapper, run_id = _persist_current_authority(execution, research)
        maker = sessionmaker(bind=execution)
        monkeypatch.setattr(sweep, "SessionLocal", maker)
        context = ReclaimAuthorityContext(
            registry=registry, research_sessionmaker=lambda: Session(research))

        def withdraw_then_return(admission, descriptor):
            with Session(research) as session:
                session.query(ResearchStrategyAdmission).filter_by(
                    owner_id=OWNER,
                    admission_address=admission.admission_address).delete()
                session.commit()
            return _fixture_result(admission, descriptor)

        assert sweep.dispatch_reclaimable(
            owner_id=OWNER, maximum=1, authority_context=context,
            _v2_lifecycle_executor=withdraw_then_return,
            _authority_at_time=AUTHORITY_TIME,
            _authority_clock=lambda: AUTHORITY_TIME) == []
        with maker() as session:
            row = session.get(BacktestRun, run_id)
            assert row.status == "error" and row.done == 0
            assert repository.durable_result_count(
                session, owner_id=OWNER, run_id=run_id) == 0
    finally:
        execution.dispose()
        research.dispose()


def test_write_time_authority_expiry_refuses_after_executor_before_result(
        tmp_path, monkeypatch):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        registry, _wrapper, run_id = _persist_current_authority(execution, research)
        maker = sessionmaker(bind=execution)
        monkeypatch_context = ReclaimAuthorityContext(
            registry=registry, research_sessionmaker=lambda: Session(research))
        monkeypatch.setattr(sweep, "SessionLocal", maker)
        sampled = []

        def write_clock():
            value = AUTHORITY_TIME + dt.timedelta(hours=13)
            sampled.append(value)
            return value

        assert sweep.dispatch_reclaimable(
            owner_id=OWNER, maximum=1, authority_context=monkeypatch_context,
            _v2_lifecycle_executor=_fixture_result,
            _authority_at_time=AUTHORITY_TIME,
            _authority_clock=write_clock) == []
        assert sampled == [AUTHORITY_TIME + dt.timedelta(hours=13)]
        with maker() as session:
            row = session.get(BacktestRun, run_id)
            assert row.status == "error" and row.done == 0
            assert repository.durable_result_count(
                session, owner_id=OWNER, run_id=run_id) == 0
    finally:
        execution.dispose()
        research.dispose()


def test_requested_cancellation_terminalizes_before_executor_or_fresh_reload(tmp_path):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        registry, _wrapper, run_id = _persist_current_authority(execution, research)
        maker = sessionmaker(bind=execution)
        context = ReclaimAuthorityContext(
            registry=registry, research_sessionmaker=lambda: Session(research))
        with maker() as session:
            claim = repository.claim_run(
                session, owner_id=OWNER, run_id=run_id,
                claimed_by="cancel-before-executor", lease_seconds=60)
            session.commit()
            assert claim is not None
            token = claim.claim_token
            descriptor_json = claim.request_json
            admission_address = claim.admission_address
        initial = _load_current(maker, context, research, admission_address)
        with maker() as session:
            assert repository.request_cancel(
                session, owner_id=OWNER, run_id=run_id)
            session.commit()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("cancelled lifecycle reached executor or authority reload")

        outcome = v2_lifecycle.run_claimed_lifecycle(
            sessionmaker=maker, owner_id=OWNER, run_id=run_id,
            claim_token=token, descriptor_json=descriptor_json,
            initial_admission=initial, authority_loader=forbidden,
            executor=forbidden, lease_seconds=60)
        assert outcome == v2_lifecycle.V2LifecycleOutcome(
            run_id, v2_lifecycle.CANCELLED, 0)
        with maker() as session:
            row = session.get(BacktestRun, run_id)
            assert row.status == "cancelled" and row.done == 0
            assert repository.durable_result_count(
                session, owner_id=OWNER, run_id=run_id) == 0
    finally:
        execution.dispose()
        research.dispose()


def test_v2_lifecycle_module_has_no_cache_provider_broker_order_or_money_import():
    tree = ast.parse(Path(v2_lifecycle.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(module.startswith((
        "app.backtest.cache", "app.providers", "app.engine", "app.ledger"))
        for module in imported)


def test_sole_authority_loader_and_executor_seams_have_no_undeclared_app_consumer():
    app_root = BACKEND / "app"
    loader_consumers = {
        path.relative_to(BACKEND).as_posix()
        for path in app_root.rglob("*.py")
        if "load_verified_v2_lifecycle_admission(" in path.read_text(encoding="utf-8")
    }
    executor_consumers = {
        path.relative_to(BACKEND).as_posix()
        for path in app_root.rglob("*.py")
        if "_v2_lifecycle_executor" in path.read_text(encoding="utf-8")
    }
    assert loader_consumers == {
        "app/backtest/repository.py", "app/backtest/sweep.py"}
    assert executor_consumers == {"app/backtest/sweep.py"}


def _assert_result_universe_and_retry_payloads(execution, research):
    registry, _wrapper, run_id = _persist_current_authority(
        execution, research, total=2)
    maker = sessionmaker(bind=execution)
    context = ReclaimAuthorityContext(
        registry=registry, research_sessionmaker=lambda: Session(research))
    with maker() as session:
        claim = repository.claim_run(
            session, owner_id=OWNER, run_id=run_id,
            claimed_by="result-universe", lease_seconds=60)
        session.commit()
        assert claim is not None
        token = claim.claim_token
        admission_address = claim.admission_address
    admission = _load_current(maker, context, research, admission_address)
    first = _fixture_cell("NIFTY", net_pnl=1.25)
    second = _fixture_cell("BANKNIFTY", net_pnl=2.5)
    third = _fixture_cell("FINNIFTY", net_pnl=3.75)

    with maker() as session:
        untouched = _durable_snapshot(session, run_id)
    for values in ([first], [first, first], [first, second, third]):
        with maker() as session:
            with pytest.raises(
                    v2_lifecycle.V2LifecycleRefused,
                    match="RESULT_UNIVERSE_MISMATCH"):
                v2_lifecycle.finalize_claimed_results(
                    session, owner_id=OWNER, run_id=run_id,
                    claim_token=token, admission=admission,
                    values=values, lease_seconds=60)
            # The lifecycle savepoint owns atomic refusal even if a caller catches
            # the error and commits its surrounding transaction.
            session.commit()
        with maker() as session:
            assert _durable_snapshot(session, run_id) == untouched

    with maker() as session:
        finalized = v2_lifecycle.finalize_claimed_results(
            session, owner_id=OWNER, run_id=run_id,
            claim_token=token, admission=admission,
            values=[first, second], lease_seconds=60)
        session.commit()
    assert finalized == v2_lifecycle.V2LifecycleOutcome(
        run_id, v2_lifecycle.FINALIZED, 2)

    with maker() as session:
        reordered = v2_lifecycle.finalize_claimed_results(
            session, owner_id=OWNER, run_id=run_id,
            claim_token=token, admission=admission,
            values=[second, first], lease_seconds=60)
        session.commit()
    assert reordered == v2_lifecycle.V2LifecycleOutcome(
        run_id, v2_lifecycle.ALREADY_FINALIZED, 2)

    with maker() as session:
        terminal = _durable_snapshot(session, run_id)
    for values in (
        [{**first, "net_pnl": 999.0}, second],
        [first],
        [first, second, third],
    ):
        with maker() as session:
            with pytest.raises(
                    v2_lifecycle.V2LifecycleRefused,
                    match="FINALIZATION_MISMATCH"):
                v2_lifecycle.finalize_claimed_results(
                    session, owner_id=OWNER, run_id=run_id,
                    claim_token=token, admission=admission,
                    values=values, lease_seconds=60)
            session.commit()
        with maker() as session:
            assert _durable_snapshot(session, run_id) == terminal


def test_sqlite_result_universe_and_complete_retry_payload_equality(tmp_path):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        _assert_result_universe_and_retry_payloads(execution, research)
    finally:
        execution.dispose()
        research.dispose()


def test_postgresql16_result_universe_and_complete_retry_payload_equality(pg_sandbox):
    execution = pg_sandbox.engine("p5_v2_universe_execution")
    research = pg_sandbox.engine("p5_v2_universe_research")
    _assert_result_universe_and_retry_payloads(execution, research)


def test_v2_result_batch_bounds_and_conflicting_attribution_refuse_before_write(
        tmp_path):
    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        registry, _wrapper, run_id = _persist_current_authority(execution, research)
        maker = sessionmaker(bind=execution)
        context = ReclaimAuthorityContext(
            registry=registry, research_sessionmaker=lambda: Session(research))
        with maker() as session:
            claim = repository.claim_run(
                session, owner_id=OWNER, run_id=run_id, claimed_by="bounds",
                lease_seconds=60)
            session.commit()
            assert claim is not None
            token = claim.claim_token
            admission_address = claim.admission_address
        admission = _load_current(maker, context, research, admission_address)
        for values, code in (
            ([], "RESULT_REQUIRED"),
            (_fixture_result() * 11, "RESULT_BATCH_TOO_LARGE"),
            ([{**_fixture_result()[0], "graph_address": "sha256:" + "f" * 64}],
             "GRAPH_ATTRIBUTION_MISMATCH"),
        ):
            with maker() as session:
                with pytest.raises(v2_lifecycle.V2LifecycleRefused, match=code):
                    v2_lifecycle.finalize_claimed_results(
                        session, owner_id=OWNER, run_id=run_id,
                        claim_token=token, admission=admission, values=values)
                session.rollback()
        with maker() as session:
            row = session.get(BacktestRun, run_id)
            assert row.status == "running" and row.done == 0
            assert repository.durable_result_count(
                session, owner_id=OWNER, run_id=run_id) == 0
    finally:
        execution.dispose()
        research.dispose()


def test_five_state_repository_matrix_and_stale_fences(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'states.db'}", future=True)
    research = sa.create_engine(f"sqlite:///{tmp_path / 'research.db'}", future=True)
    try:
        _registry, _wrapper, run_id = _persist_current_authority(engine, research)
        maker = sessionmaker(bind=engine)
        now = dt.datetime.now()
        with maker() as session:
            claim = repository.claim_run(
                session, owner_id=OWNER, run_id=run_id, claimed_by="matrix",
                now=now, lease_seconds=30)
            session.commit()
            assert claim is not None and claim.status == "running"
            token = claim.claim_token
        assert token
        with maker() as session:
            assert repository.heartbeat_claim(
                session, owner_id=OWNER, run_id=run_id, claim_token=token,
                now=now + dt.timedelta(seconds=1), lease_seconds=30)
            assert repository.release_claim(
                session, owner_id=OWNER, run_id=run_id, claim_token=token,
                note="matrix release", now=now + dt.timedelta(seconds=2))
            session.commit()
        with maker() as session:
            replacement = repository.claim_run(
                session, owner_id=OWNER, run_id=run_id, claimed_by="replacement",
                now=now + dt.timedelta(seconds=3), lease_seconds=30)
            session.commit()
            assert replacement is not None and replacement.claim_token != token
        with maker() as session:
            assert not repository.heartbeat_claim(
                session, owner_id=OWNER, run_id=run_id, claim_token=token,
                now=now + dt.timedelta(seconds=4))
            assert not repository.complete_claim(
                session, owner_id=OWNER, run_id=run_id, claim_token=token,
                status="done", now=now + dt.timedelta(seconds=4))
            assert repository.request_cancel(
                session, owner_id=OWNER, run_id=run_id,
                now=now + dt.timedelta(seconds=4))
            assert repository.complete_claim(
                session, owner_id=OWNER, run_id=run_id,
                claim_token=replacement.claim_token, status="cancelled",
                now=now + dt.timedelta(seconds=5))
            session.commit()
        with maker() as session:
            assert session.get(BacktestRun, run_id).status == "cancelled"
            assert repository.claim_run(
                session, owner_id=OWNER, run_id=run_id, claimed_by="terminal") is None
    finally:
        engine.dispose()
        research.dispose()
