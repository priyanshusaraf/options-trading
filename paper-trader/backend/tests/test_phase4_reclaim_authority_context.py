"""Focused regression seams for Phase 4's owner-local reclaim authority."""
from __future__ import annotations

import datetime as dt
from dataclasses import replace
import inspect
import os
import subprocess
import sys
import threading
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import event, update
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.backtest import repository, sweep
from app.backtest.reclaim_authority import ReclaimAuthorityContext
from app.db.models import BacktestRun
from app.db.session import SessionLocal, init_db
from app.ir.library import REGISTRY


def _persist_real_phase4_reclaim(tmp_path, monkeypatch):
    """Persist the real two-plane authority chain used by public reclaim."""
    from app.core.strategy_admissions import put
    from app.db.models import Base, Organization
    from app.market_data.authority import persist_capability_assessment
    from app.market_data.capability import assess_capability
    from app.strategy.admission import admit_phase4_v2_strategy
    from research.domain.admissions import store_admission
    from research.domain.strategy_admissions import persist_verified_dataset_authority
    from tests.test_phase4_capability_admission import _evidence, _plan
    from tests.test_phase4_dataset_assessment_authority import T0, _authority, _engines, _seed_execution, address

    execution, research = _engines(tmp_path)
    Base.metadata.create_all(execution)
    registry, document, plan = _plan()
    at_time = T0 + dt.timedelta(hours=3)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        persist_verified_dataset_authority(
            research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=at_time)
        assessment = assess_capability(
            plan=plan, profile=values["profile"], owner_id="owner-a", mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address("evaluation-policy"),
            assessment_evidence_address=address("assessment-evidence"),
            at_time=int(at_time.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"])
        persist_capability_assessment(execution_session, assessment, plan=plan, at_time=at_time)
        wrapper = admit_phase4_v2_strategy(
            owner_id="owner-a", mode="RESEARCH", document=document, registry=registry,
            evidence=_evidence(), plan=plan, assessment_address=assessment.authority_address,
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=assessment.evaluation_policy_address,
            research_session=research_session, execution_session=execution_session, at_time=at_time)
        put(execution_session, wrapper)
        store_admission(research_session, wrapper)
        execution_session.add(BacktestRun(
            owner_id="owner-a", scope="liquid", intervals="day", capital=1.0,
            total=1, status="pending", admission_address=wrapper.admission_address,
            request_json='{"intervals":["day"],"strategies":[{"key":"x","version":1}]}'))
        execution_session.commit()
        research_session.commit()
    execution_maker = sessionmaker(bind=execution)
    research_maker = sessionmaker(bind=research)
    monkeypatch.setattr(sweep, "SessionLocal", execution_maker)
    return execution, research, registry, execution_maker, research_maker


def test_real_persisted_two_plane_public_reclaim_refuses_before_claim(tmp_path, monkeypatch):
    """Actual classifier, verifier and loader reach the v2 runtime boundary."""
    execution, research, registry, execution_maker, research_maker = _persist_real_phase4_reclaim(
        tmp_path, monkeypatch)
    try:
        cutoff = dt.datetime(2026, 8, 1, 3, tzinfo=dt.timezone.utc)

        class FixedDateTime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return cutoff if tz else cutoff.replace(tzinfo=None)

        monkeypatch.setattr(sweep, "dt", SimpleNamespace(
            datetime=FixedDateTime, timezone=dt.timezone))
        monkeypatch.setattr(sweep, "_launch_reclaimed_claim",
                            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("post-claim launch")))
        real_loader = repository.load_verified_admission
        terminal_codes = []

        def observing_real_loader(*args, **kwargs):
            try:
                return real_loader(*args, **kwargs)
            except repository.AdmissionRequired as exc:
                terminal_codes.append(exc.code)
                raise

        # This is an observing wrapper, not a substitute verifier: the real
        # persisted loader remains the only code that evaluates authority.
        monkeypatch.setattr(repository, "load_verified_admission", observing_real_loader)
        lifecycle = []

        class TrackingResearchSession(Session):
            def close(self):
                lifecycle.append("closed")
                super().close()

        def tracking_research_maker():
            lifecycle.append("opened")
            return TrackingResearchSession(research)

        context = ReclaimAuthorityContext(registry=registry,
                                          research_sessionmaker=tracking_research_maker)
        assert sweep.dispatch_reclaimable(owner_id="owner-a", maximum=1,
                                          authority_context=context) == []
        assert terminal_codes == ["V2_RUNTIME_UNAVAILABLE"]
        assert lifecycle == ["opened", "closed"]
        with execution_maker() as session:
            row = session.query(BacktestRun).one()
            assert row.status == "pending" and row.claim_token is None
    finally:
        execution.dispose()
        research.dispose()


def test_fresh_interpreter_reconstructs_context_for_real_public_v2_refusal(tmp_path, monkeypatch):
    """A new process rebuilds its context and reaches the public refusal seam."""
    execution, research, _registry, _execution_maker, _research_maker = _persist_real_phase4_reclaim(
        tmp_path, monkeypatch)
    try:
        script = '''
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.backtest import sweep
from app.backtest.reclaim_authority import ReclaimAuthorityContext
from app.db.models import BacktestRun
from tests.test_phase4_capability_admission import _plan
import datetime as dt
import os
from types import SimpleNamespace

execution = create_engine(os.environ["EXECUTION_URL"])
research = create_engine(os.environ["RESEARCH_URL"])
registry, _document, _plan_value = _plan()
sweep.SessionLocal = sessionmaker(bind=execution)
context = ReclaimAuthorityContext(
    registry=registry, research_sessionmaker=sessionmaker(bind=research))
cutoff = dt.datetime(2026, 8, 1, 3, tzinfo=dt.timezone.utc)
class FixedDateTime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cutoff if tz else cutoff.replace(tzinfo=None)
sweep.dt = SimpleNamespace(datetime=FixedDateTime, timezone=dt.timezone)
assert sweep.dispatch_reclaimable(owner_id="owner-a", maximum=1, authority_context=context) == []
with sweep.SessionLocal() as session:
    run = session.scalar(select(BacktestRun))
    assert run.status == "pending" and run.claim_token is None
'''
        result = subprocess.run(
            [sys.executable, "-c", script], check=False, text=True,
            capture_output=True,
            env={**os.environ, "PYTHONPATH": os.getcwd(),
                 "EXECUTION_URL": str(execution.url), "RESEARCH_URL": str(research.url)},
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        execution.dispose()
        research.dispose()


def test_unexpected_v2_loader_success_still_refuses_before_mutation(monkeypatch):
    """Removing the terminal throw cannot accidentally enable v2 reclaim."""
    init_db(reset=True)
    run_id = _run(admission_address="sha256:" + "d" * 64)
    monkeypatch.setattr(repository, "reclaim_admission_format", lambda *_a, **_k: 2)
    monkeypatch.setattr(repository, "load_verified_admission",
                        lambda *_a, **_k: SimpleNamespace(strategy=object(), phase4_binding=None))
    context = ReclaimAuthorityContext(registry=REGISTRY,
                                      research_sessionmaker=lambda: Session(create_engine("sqlite:///:memory:")))
    result = sweep.dispatch_reclaimable(owner_id="owner", maximum=1,
                                        authority_context=context)
    with SessionLocal() as session:
        row = session.get(BacktestRun, run_id)
        assert row.status == "pending" and row.claim_token is None
    assert result == []


def test_public_v2_exception_closes_its_one_lazy_research_session(monkeypatch):
    init_db(reset=True)
    _run(admission_address="sha256:" + "c" * 64)
    engine = create_engine("sqlite:///:memory:")
    lifecycle = []

    class TrackingResearchSession(Session):
        def close(self):
            lifecycle.append("closed")
            super().close()

    monkeypatch.setattr(repository, "reclaim_admission_format", lambda *_a, **_k: 2)
    monkeypatch.setattr(repository, "load_verified_admission",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("loader boom")))
    context = ReclaimAuthorityContext(
        registry=REGISTRY,
        research_sessionmaker=lambda: (lifecycle.append("opened") or TrackingResearchSession(engine)))
    with pytest.raises(RuntimeError, match="loader boom"):
        sweep.dispatch_reclaimable(owner_id="owner", maximum=1, authority_context=context)
    assert lifecycle == ["opened", "closed"]


def test_postgres_closed_snapshot_locks_rows_and_excludes_late_insert(monkeypatch):
    """PG16 uses exact `FOR UPDATE`; a post-enumeration insert is outside A's set."""
    postgres_url = os.environ.get("PT_TEST_POSTGRES_URL")
    if not postgres_url:
        pytest.skip("requires disposable PostgreSQL 16")
    from app.db.models import Base, Organization

    engine = create_engine(postgres_url, future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    statements = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_args: statements.append(_args[2]))
    with maker() as session:
        session.add(Organization(organization_id="pg-owner", name="PG owner"))
        session.flush()
        session.add(BacktestRun(owner_id="pg-owner", scope="liquid", intervals="day",
                                capital=1.0, total=1, status="pending"))
        session.commit()

    locked, release, second_started, second_done = (threading.Event() for _ in range(4))
    observed = {}

    def first_snapshot():
        with maker() as session:
            observed["first"] = repository.snapshot_claimable_runs(
                session, owner_id="pg-owner")
            locked.set()
            assert release.wait(5)
            session.commit()

    def second_snapshot():
        assert locked.wait(5)
        with maker() as session:
            second_started.set()
            observed["second"] = repository.snapshot_claimable_runs(
                session, owner_id="pg-owner")
            session.commit()
        second_done.set()

    first = threading.Thread(target=first_snapshot)
    second = threading.Thread(target=second_snapshot)
    first.start(); assert locked.wait(5)
    second.start(); assert second_started.wait(5)
    with maker() as session:
        session.add(BacktestRun(owner_id="pg-owner", scope="liquid", intervals="day",
                                capital=1.0, total=1, status="pending"))
        session.commit()
    assert not second_done.wait(0.1)
    release.set(); first.join(5); second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert len(observed["first"]) == 1
    # B began its locked enumeration before the insert and therefore sees the
    # same closed statement snapshot, even though it waited on A's exact row.
    assert len(observed["second"]) == 1
    with maker() as session:
        assert len(repository.snapshot_claimable_runs(session, owner_id="pg-owner")) == 2
    assert any("FOR UPDATE" in statement.upper() for statement in statements)
    engine.dispose()


def test_postgres_frozen_claim_predicates_refuse_post_snapshot_transition():
    """The PostgreSQL conditional claim binds every scalar frozen fact."""
    postgres_url = os.environ.get("PT_TEST_POSTGRES_URL")
    if not postgres_url:
        pytest.skip("requires disposable PostgreSQL 16")
    from app.db.models import Base, Organization

    engine = create_engine(postgres_url, future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    owner_id = f"pg-predicate-{uuid.uuid4().hex}"
    other_owner = f"pg-other-{uuid.uuid4().hex}"
    mutations = (
        {"owner_id": other_owner}, {"status": "running"},
        {"admission_address": "sha256:" + "7" * 64},
        {"cancel_requested_at": dt.datetime(2026, 8, 18)},
        {"claim_token": "other-token"},
        {"claim_expires_at": dt.datetime(2026, 8, 18)},
    )
    try:
        with maker() as session:
            session.add_all((Organization(organization_id=owner_id, name=owner_id),
                             Organization(organization_id=other_owner, name=other_owner)))
            session.commit()
        for values in mutations:
            with maker() as session:
                row = BacktestRun(owner_id=owner_id, scope="liquid", intervals="day",
                                  capital=1.0, total=1, status="pending")
                session.add(row); session.commit()
                frozen = repository.snapshot_claimable_runs(session, owner_id=owner_id)[-1]
                session.execute(update(BacktestRun).where(BacktestRun.id == row.id).values(
                    **values).execution_options(synchronize_session=False))
                assert repository.claim_frozen_run(session, frozen=frozen,
                                                   claimed_by="test") is None
                session.rollback()
    finally:
        engine.dispose()


def test_sqlite_reservation_snapshot_excludes_late_insert(tmp_path):
    """SQLite's admission-scoped immediate reservation keeps a closed set."""
    from app.db.concurrency import begin_reservation
    from app.db.models import Base, Organization

    engine = create_engine(f"sqlite:///{tmp_path / 'reclaim-race.db'}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    with maker() as session:
        session.add(Organization(organization_id="sqlite-owner", name="SQLite owner"))
        session.flush()
        session.add(BacktestRun(owner_id="sqlite-owner", scope="liquid", intervals="day",
                                capital=1.0, total=1, status="pending"))
        session.commit()

    enumerated, release, inserted = threading.Event(), threading.Event(), threading.Event()
    observed = {}

    def snapshot_owner_set():
        with maker() as session:
            begin_reservation(session, scope="backtest:admission")
            observed["snapshot"] = repository.snapshot_claimable_runs(
                session, owner_id="sqlite-owner")
            enumerated.set()
            assert release.wait(5)
            session.commit()

    def insert_after_enumeration():
        assert enumerated.wait(5)
        with maker() as session:
            session.add(BacktestRun(owner_id="sqlite-owner", scope="liquid", intervals="day",
                                    capital=1.0, total=1, status="pending"))
            session.commit()
        inserted.set()

    first = threading.Thread(target=snapshot_owner_set)
    second = threading.Thread(target=insert_after_enumeration)
    first.start(); assert enumerated.wait(5)
    second.start(); assert not inserted.wait(0.1)
    release.set(); first.join(5); second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert len(observed["snapshot"]) == 1
    with maker() as session:
        assert len(repository.snapshot_claimable_runs(session, owner_id="sqlite-owner")) == 2
    engine.dispose()


def _run(*, owner_id="owner", status="pending", admission_address=None,
         claim_token=None, claim_expires_at=None, cancelled=False):
    with SessionLocal() as session:
        row = BacktestRun(owner_id=owner_id, scope="liquid", intervals="day",
                          capital=1.0, total=1, status=status,
                          admission_address=admission_address,
                          request_json='{"intervals":["day"],"strategies":[{"key":"x","version":1}]}',
                          claim_token=claim_token, claim_expires_at=claim_expires_at,
                          cancel_requested_at=(dt.datetime.now(dt.timezone.utc) if cancelled else None))
        session.add(row); session.commit()
        return row.id


def test_v2_head_of_line_refusal_keeps_every_frozen_legacy_row_unmodified(monkeypatch):
    """A later v2 row refuses the owner before an earlier legacy row is claimed."""
    init_db(reset=True)
    legacy_id = _run()
    v2_address = "sha256:" + "2" * 64
    v2_id = _run(admission_address=v2_address)
    maker_calls, loader_calls = [], []

    class ResearchSession(Session):
        def close(self):
            maker_calls.append("closed")
            super().close()

    def unavailable(session, **kwargs):
        loader_calls.append(kwargs)
        raise repository.AdmissionRequired("V2_RUNTIME_UNAVAILABLE")

    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda _session, **kwargs: 2 if kwargs["admission_address"] == v2_address else 1)
    monkeypatch.setattr(repository, "load_verified_admission", unavailable)
    research_engine = create_engine("sqlite:///:memory:")
    context = ReclaimAuthorityContext(
        registry=REGISTRY,
        research_sessionmaker=lambda: (maker_calls.append("opened") or ResearchSession(research_engine)))
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=2,
                                      authority_context=context) == []
    assert maker_calls == ["opened", "closed"]
    assert len(loader_calls) == 1
    assert loader_calls[0]["authority_context"] is context
    assert loader_calls[0]["research_session"] is not None
    assert loader_calls[0]["at_time"].tzinfo is not None
    with SessionLocal() as session:
        assert session.get(BacktestRun, legacy_id).claim_token is None
        assert session.get(BacktestRun, v2_id).claim_token is None


def test_snapshot_and_frozen_reconciliation_include_cancelled_legacy_rows():
    """Cancellation cannot make an expired/claimless legacy mutation invisible."""
    init_db(reset=True)
    now = dt.datetime(2026, 8, 18, 12, tzinfo=dt.timezone.utc)
    expired = _run(status="running", claim_token="expired",
                   claim_expires_at=now - dt.timedelta(seconds=1), cancelled=True)
    claimless = _run(status="running", cancelled=True)
    with SessionLocal() as session:
        snapshot = repository.snapshot_claimable_runs(session, owner_id="owner", now=now)
        assert {row.id for row in snapshot} == {expired, claimless}
        for row in snapshot:
            reconciled, replacement = repository.reconcile_frozen_run(session, frozen=row, now=now)
            assert reconciled and replacement is None
        session.commit()
    with SessionLocal() as session:
        assert session.get(BacktestRun, expired).status == "cancelled"
        assert session.get(BacktestRun, claimless).status == "error"


def test_non_cancelled_expired_reconciliation_preserves_completion_and_returns_scalar_successor():
    """An expired claim becomes pending without reselecting mutable row state."""
    init_db(reset=True)
    now = dt.datetime(2026, 8, 18, 12, tzinfo=dt.timezone.utc)
    completed_at = now - dt.timedelta(days=2)
    run_id = _run(status="running", claim_token="expired",
                  claim_expires_at=now - dt.timedelta(seconds=1))
    with SessionLocal() as session:
        session.execute(update(BacktestRun).where(BacktestRun.id == run_id).values(
            completed_at=completed_at))
        frozen = repository.snapshot_claimable_runs(session, owner_id="owner", now=now)[0]
        reconciled, successor = repository.reconcile_frozen_run(
            session, frozen=frozen, now=now)
        assert reconciled
        assert successor == replace(frozen, status="pending", claim_token=None,
                                    claim_expires_at=None)
        assert repository.claim_frozen_run(session, frozen=successor,
                                           claimed_by="test", now=now) is not None
        session.commit()
    with SessionLocal() as session:
        row = session.get(BacktestRun, run_id)
        assert row.completed_at == completed_at.replace(tzinfo=None)
        assert row.status == "running"


def test_frozen_claim_refuses_a_transition_without_a_broad_owner_update():
    """A changed frozen predicate produces no replacement claim."""
    init_db(reset=True)
    run_id = _run()
    with SessionLocal() as session:
        frozen = repository.snapshot_claimable_runs(session, owner_id="owner")[0]
        session.execute(update(BacktestRun).where(BacktestRun.id == run_id).values(
            cancel_requested_at=dt.datetime.now(dt.timezone.utc)).execution_options(
                synchronize_session=False))
        assert repository.claim_frozen_run(session, frozen=frozen, claimed_by="test") is None
        session.rollback()
    with SessionLocal() as session:
        assert session.get(BacktestRun, run_id).claim_token is None


def test_frozen_claim_binds_every_scalar_predicate_after_actual_transition():
    """Each persisted frozen fact independently prevents a later claim."""
    mutations = (
        {"owner_id": "other"}, {"status": "running"},
        {"admission_address": "sha256:" + "4" * 64},
        {"cancel_requested_at": dt.datetime(2026, 8, 18)},
        {"claim_token": "other-token"},
        {"claim_expires_at": dt.datetime(2026, 8, 18)},
    )
    for values in mutations:
        init_db(reset=True)
        run_id = _run()
        with SessionLocal() as session:
            frozen = repository.snapshot_claimable_runs(session, owner_id="owner")[0]
            if "owner_id" in values:
                from app.db.models import Organization
                session.add(Organization(organization_id="other", name="Other"))
                session.flush()
            session.execute(update(BacktestRun).where(BacktestRun.id == run_id).values(
                **values).execution_options(synchronize_session=False))
            assert repository.claim_frozen_run(session, frozen=frozen,
                                               claimed_by="test") is None
            session.expire_all()
            current = session.get(BacktestRun, run_id)
            assert current.owner_id == values.get("owner_id", "owner"), values
            assert current.status == values.get("status", "pending"), values
            assert current.admission_address == values.get("admission_address"), values
            assert current.cancel_requested_at == values.get("cancel_requested_at"), values
            assert current.claim_token == values.get("claim_token"), values
            assert current.claim_expires_at == values.get("claim_expires_at"), values
            assert current.claimed_by is None
            session.rollback()
        with SessionLocal() as session:
            assert session.get(BacktestRun, run_id).claim_token is None


def test_unknown_frozen_receipt_refuses_before_the_first_legacy_claim(monkeypatch):
    init_db(reset=True)
    legacy_id = _run()
    unknown_id = _run(admission_address="sha256:" + "3" * 64)
    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda _session, **_kwargs: None)
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=2) == []
    with SessionLocal() as session:
        assert session.get(BacktestRun, legacy_id).claim_token is None
        assert session.get(BacktestRun, unknown_id).claim_token is None


def test_reclaim_receipt_classifier_rejects_malformed_and_noncanonical_legacy_bytes(monkeypatch):
    """Only an exact v1 receipt is eligible for a legacy mutation."""
    class ScalarSession:
        def __init__(self, value): self.value = value
        def scalar(self, _statement): return self.value

    assert repository.reclaim_admission_format(
        ScalarSession("{not-json"), owner_id="owner", admission_address="sha256:" + "7" * 64) is None
    from app.strategy.admission import AdmissionRefusalCode, AdmissionRefused
    monkeypatch.setattr(
        "app.strategy.admission.artifact_from_dict",
        lambda _document: (_ for _ in ()).throw(AdmissionRefused(
            AdmissionRefusalCode.RECEIPT_STALE, "not canonical")))
    assert repository.reclaim_admission_format(
        ScalarSession('{"scheme":"legacy"}'), owner_id="owner",
        admission_address="sha256:" + "8" * 64) is None


def test_loader_refuses_a_persisted_non_object_receipt_with_stable_code(monkeypatch):
    """A JSON scalar/list is a receipt refusal, never an attribute error."""
    monkeypatch.setattr(
        "app.core.strategy_admissions.get",
        lambda *_args, **_kwargs: SimpleNamespace(artifact_json="[]"))
    with SessionLocal() as session:
        try:
            repository.load_verified_admission(
                session, owner_id="owner", admission_address="sha256:" + "9" * 64)
        except repository.AdmissionRequired as exc:
            assert exc.code == "RECEIPT_STALE"
        else:
            raise AssertionError("non-object receipt was accepted")


def test_v2_loader_requires_the_typed_context_and_callable_factory(monkeypatch):
    """Lookalike context objects cannot introduce hidden authority state."""
    from app.ir.v2_graph_versions import PHASE4_SCHEME
    monkeypatch.setattr(
        "app.core.strategy_admissions.get",
        lambda *_args, **_kwargs: SimpleNamespace(
            artifact_json='{"scheme":"' + PHASE4_SCHEME + '"}'))
    with SessionLocal() as session:
        for context in (None, SimpleNamespace(registry=object(), research_sessionmaker=lambda: None),
                        ReclaimAuthorityContext(registry=object(), research_sessionmaker=object())):
            try:
                repository.load_verified_admission(
                    session, owner_id="owner", admission_address="sha256:" + "a" * 64,
                    authority_context=context, research_session=object(),
                    at_time=dt.datetime.now(dt.timezone.utc))
            except repository.AdmissionRequired as exc:
                assert exc.code == "PHASE4_CONTEXT_REQUIRED"
            else:
                raise AssertionError("untyped or non-callable authority context was accepted")


def test_public_v2_dispatch_refuses_bad_context_factories_before_hidden_session(monkeypatch):
    """The public preflight validates context/factory failures before any loader."""
    init_db(reset=True)
    address = "sha256:" + "b" * 64
    _run(admission_address=address)
    calls = []
    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(repository, "load_verified_admission",
                        lambda *_args, **_kwargs: calls.append("loader"))

    for context in (
        SimpleNamespace(registry=object(), research_sessionmaker=lambda: calls.append("lookalike")),
        ReclaimAuthorityContext(registry=object(), research_sessionmaker=object()),
        ReclaimAuthorityContext(registry=object(), research_sessionmaker=lambda: calls.append("invalid-registry")),
        ReclaimAuthorityContext(registry=object(), research_sessionmaker=lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
        ReclaimAuthorityContext(registry=object(), research_sessionmaker=lambda: object()),
    ):
        assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1,
                                          authority_context=context) == []
    assert calls == []


def test_mixed_v2_and_unknown_refuse_before_v2_loader_or_mutation(monkeypatch):
    """Closed-set classification cannot let v2 terminal refusal mask unknown."""
    init_db(reset=True)
    legacy_id = _run()
    v2_address = "sha256:" + "5" * 64
    unknown_address = "sha256:" + "6" * 64
    v2_id = _run(admission_address=v2_address)
    unknown_id = _run(admission_address=unknown_address)
    loader_calls = []
    monkeypatch.setattr(
        repository, "reclaim_admission_format",
        lambda _session, **kwargs: 2 if kwargs["admission_address"] == v2_address
        else None if kwargs["admission_address"] == unknown_address else 1)
    monkeypatch.setattr(repository, "load_verified_admission",
                        lambda *_args, **_kwargs: loader_calls.append("called"))
    context = ReclaimAuthorityContext(registry=object(),
                                      research_sessionmaker=lambda: AssertionError("must not open"))
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=3,
                                      authority_context=context) == []
    assert loader_calls == []
    with SessionLocal() as session:
        for run_id in (legacy_id, v2_id, unknown_id):
            assert session.get(BacktestRun, run_id).claim_token is None


def test_direct_dispatch_retains_legacy_no_pre_reconcile_policy(monkeypatch):
    """Only startup dispatch may reconcile a frozen claimless legacy row."""
    init_db(reset=True)
    _run(status="running")
    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(repository, "reconcile_frozen_run",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(
                            AssertionError("direct dispatch must not reconcile")))
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1) == []


def test_pending_only_boot_policy_launches_but_start_policy_does_not(monkeypatch):
    """Boot retains reconcile-then-dispatch; a new start needs a repair first."""
    init_db(reset=True)
    run_id = _run()
    launched = []
    monkeypatch.setattr(repository, "reclaim_admission_format", lambda *_a, **_k: 1)
    monkeypatch.setattr(sweep, "_launch_reclaimed_claim",
                        lambda **kwargs: launched.append(kwargs["claim"].id) or kwargs["claim"].id)
    assert sweep.dispatch_reclaimable(
        owner_id="owner", maximum=1,
        _reclaim_policy=sweep._ReclaimPolicy.START_IF_CHANGED) == []
    assert launched == []
    with SessionLocal() as session:
        assert session.get(BacktestRun, run_id).claim_token is None
    assert sweep.dispatch_reclaimable(
        owner_id="owner", maximum=1,
        _reclaim_policy=sweep._ReclaimPolicy.BOOT) == [run_id]
    assert launched == [run_id]


def test_all_v1_context_keeps_post_claim_loader_on_legacy_call_shape(monkeypatch):
    """Supplying Phase 4 context cannot open research state for a v1 restart."""
    init_db(reset=True)
    run_id = _run()
    loader_calls, research_calls = [], []
    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda *_args, **_kwargs: 1)

    def legacy_loader(_session, **kwargs):
        loader_calls.append(kwargs)
        raise repository.AdmissionRequired("RECEIPT_STALE")

    monkeypatch.setattr(repository, "load_verified_admission", legacy_loader)
    context = ReclaimAuthorityContext(
        registry=object(),
        research_sessionmaker=lambda: research_calls.append("opened"))
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1,
                                      authority_context=context) == []
    assert research_calls == []
    assert loader_calls == [{"owner_id": "owner", "admission_address": None}]
    with SessionLocal() as session:
        assert session.get(BacktestRun, run_id).status == "error"


def test_launch_site_requires_and_propagates_frozen_v2_format(monkeypatch):
    """The second loader site cannot silently fall back to the v1 branch."""
    init_db(reset=True)
    run_id = _run()
    with SessionLocal() as session:
        frozen = repository.snapshot_claimable_runs(session, owner_id="owner")[0]
        claim = repository.claim_frozen_run(session, frozen=frozen, claimed_by="test")
        assert claim is not None
        session.commit()

    class Guard:
        def __init__(self, **_kwargs): pass
        def start(self): pass
        def ensure_active(self): pass
        def close(self): pass

    calls = []
    monkeypatch.setattr(sweep, "_ClaimGuard", Guard)
    assert "admission_format" in inspect.signature(sweep._launch_reclaimed_claim).parameters
    assert sweep._launch_reclaimed_claim(
        owner_id="owner", claim=claim, admission_format=2,
        phase4_loader=lambda _session, **kwargs: (
            calls.append(kwargs), (_ for _ in ()).throw(
                repository.AdmissionRequired("V2_RUNTIME_UNAVAILABLE")))[1]) is None
    assert calls == [{"admission_address": None, "v2": True}]


def test_zero_limit_is_a_true_noop_before_context_or_reservation(monkeypatch):
    init_db(reset=True)
    calls = []
    monkeypatch.setattr(sweep, "begin_reservation",
                        lambda *_args, **_kwargs: calls.append("reservation"))
    context = ReclaimAuthorityContext(registry=object(),
                                      research_sessionmaker=lambda: calls.append("research"))
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=0,
                                      authority_context=context) == []
    assert calls == []


def test_positive_legacy_dispatch_takes_the_admission_reservation(monkeypatch):
    """The closed legacy path cannot silently lose its SQLite reservation."""
    init_db(reset=True)
    _run()
    calls = []
    real_reservation = sweep.begin_reservation
    monkeypatch.setattr(sweep, "begin_reservation",
                        lambda *args, **kwargs: calls.append(kwargs["scope"]) or real_reservation(*args, **kwargs))
    monkeypatch.setattr(repository, "reclaim_admission_format", lambda *_a, **_k: 1)
    monkeypatch.setattr(sweep, "_launch_reclaimed_claim",
                        lambda **kwargs: kwargs["claim"].id)
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1) == [1]
    assert calls == ["backtest:admission"]
