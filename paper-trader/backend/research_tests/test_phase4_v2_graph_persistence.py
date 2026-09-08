"""Direct research-plane regressions for immutable Phase 4 IR v2 graph facts."""
from __future__ import annotations

import json
import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.ir.hashing import canonical_json
from app.ir.v2_graph_versions import facts_from_row
from app.strategy.admission import derive_v2_graph_facts
from research.domain.admissions import (
    AdmissionPersistenceError,
    require_admission,
    store_admission,
)
from research.domain.base import ResearchBase
from research.domain.models import ResearchIrV2GraphVersion, ResearchStrategyAdmission

from tests.test_phase4_v2_graph_persistence import _phase4_fixture


def _engine():
    engine = sa.create_engine(os.environ.get("PT_TEST_POSTGRES_URL", "sqlite:///:memory:"), future=True)
    ResearchBase.metadata.create_all(engine)
    return engine


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(ResearchIrV2GraphVersion)),
        session.scalar(select(func.count()).select_from(ResearchStrategyAdmission)),
    )


def test_research_phase4_write_is_atomic_and_receipt_contains_capability_assessment():
    _registry, wrapper = _phase4_fixture()
    engine = _engine()
    with Session(engine) as session:
        original = store_admission(session, wrapper)
        session.commit()
        row = session.get(ResearchIrV2GraphVersion, ("owner-a", "phase4", 1))
        assert row is not None
        assert original.artifact_json == canonical_json(wrapper.to_dict())
        assert "capability_assessment" in json.loads(original.artifact_json)
        assert facts_from_row(row) == derive_v2_graph_facts(wrapper)
        assert require_admission(session, wrapper).artifact_json == original.artifact_json


def test_research_exact_retries_owner_isolation_and_identity_collision_refuse():
    _registry, wrapper = _phase4_fixture()
    _other_registry, other_owner = _phase4_fixture(owner_id="owner-b")
    _variant_registry, variant = _phase4_fixture(name="different-bytes")
    assert other_owner.owner_id == "owner-b"
    engine = _engine()
    with Session(engine) as session:
        first = store_admission(session, wrapper)
        retry = store_admission(session, wrapper)
        assert retry.artifact_json == first.artifact_json
        store_admission(session, other_owner)
        session.commit()
        assert _counts(session) == (2, 2)
        assert session.get(ResearchIrV2GraphVersion, ("owner-b", "phase4", 1)) is not None
        assert session.get(
            ResearchStrategyAdmission, ("owner-b", other_owner.admission_address)
        ) is not None
        with pytest.raises(AdmissionPersistenceError, match="v2 graph version"):
            store_admission(session, variant)
        session.rollback()
        assert _counts(session) == (2, 2)


def test_research_graph_and_receipt_have_no_partial_write_on_receipt_failure():
    _registry, wrapper = _phase4_fixture(owner_id="owner-flush-research")

    def fail_receipt(_mapper, _connection, _target):
        raise RuntimeError("injected receipt failure")

    engine = _engine()
    event.listen(ResearchStrategyAdmission, "before_insert", fail_receipt)
    try:
        with Session(engine) as session:
            with pytest.raises(RuntimeError, match="injected receipt failure"):
                store_admission(session, wrapper)
            session.rollback()
        with Session(engine) as observer:
            assert observer.scalar(select(func.count()).select_from(ResearchIrV2GraphVersion).where(
                ResearchIrV2GraphVersion.owner_id == wrapper.owner_id)) == 0
            assert observer.scalar(select(func.count()).select_from(ResearchStrategyAdmission).where(
                ResearchStrategyAdmission.owner_id == wrapper.owner_id)) == 0
    finally:
        event.remove(ResearchStrategyAdmission, "before_insert", fail_receipt)


@pytest.mark.parametrize("caller_state", ["clean", "prior-read", "prior-write", "explicit"])
def test_research_real_writer_preserves_the_callers_lifecycle(caller_state: str):
    """Exercise ``store_admission`` itself under caller-owned states."""
    owner = f"owner-lifecycle-research-{uuid.uuid4().hex}"
    _registry, wrapper = _phase4_fixture(owner_id=owner)
    engine = _engine()
    try:
        if caller_state == "explicit":
            with Session(engine) as session:
                with session.begin():
                    store_admission(session, wrapper)
        else:
            with Session(engine) as session:
                if caller_state == "prior-read":
                    session.execute(sa.text("SELECT 1"))
                elif caller_state == "prior-write":
                    _unused, caller_work = _phase4_fixture(
                        owner_id=f"caller-work-research-{uuid.uuid4().hex}")
                    store_admission(session, caller_work)
                store_admission(session, wrapper)
                session.commit()
        with Session(engine) as observer:
            assert observer.scalar(select(func.count()).select_from(ResearchIrV2GraphVersion).where(
                ResearchIrV2GraphVersion.owner_id == owner)) == 1
            assert observer.scalar(select(func.count()).select_from(ResearchStrategyAdmission).where(
                ResearchStrategyAdmission.owner_id == owner)) == 1
    finally:
        engine.dispose()


def test_research_real_writer_caller_rollback_and_commit_refusal_leave_no_rows():
    owner = f"owner-refusal-research-{uuid.uuid4().hex}"
    _registry, wrapper = _phase4_fixture(owner_id=owner)
    engine = _engine()

    def refuse_commit(connection):
        if connection.engine is engine:
            raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)

    event.listen(engine, "commit", refuse_commit)
    try:
        with Session(engine) as session:
            store_admission(session, wrapper)
            with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                session.commit()
            session.rollback()
        with Session(engine) as observer:
            assert observer.scalar(select(func.count()).select_from(ResearchIrV2GraphVersion).where(
                ResearchIrV2GraphVersion.owner_id == owner)) == 0
            assert observer.scalar(select(func.count()).select_from(ResearchStrategyAdmission).where(
                ResearchStrategyAdmission.owner_id == owner)) == 0
    finally:
        event.remove(engine, "commit", refuse_commit)
        engine.dispose()


def test_research_writer_refuses_invalid_preexisting_orm_work_distinctly():
    owner = f"owner-preflush-research-{uuid.uuid4().hex}"
    _registry, wrapper = _phase4_fixture(owner_id=owner)
    engine = _engine()
    try:
        with Session(engine) as session:
            # A malformed unrelated receipt must fail before the seam savepoint,
            # rather than be handled as the seam's exact-retry collision.
            session.add(ResearchIrV2GraphVersion())
            with pytest.raises(RuntimeError, match="pre-savepoint caller flush failure"):
                store_admission(session, wrapper)
            session.rollback()
        with Session(engine) as observer:
            assert observer.get(ResearchStrategyAdmission, (owner, wrapper.admission_address)) is None
    finally:
        engine.dispose()


def test_research_graph_is_immutable_through_orm_and_sqlite_trigger():
    _registry, wrapper = _phase4_fixture()
    engine = _engine()
    with Session(engine) as session:
        store_admission(session, wrapper)
        session.commit()
        row = session.get(ResearchIrV2GraphVersion, ("owner-a", "phase4", 1))
        row.artifact_json = "{}"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()
        session.rollback()
        with pytest.raises(sa.exc.DBAPIError):
            session.execute(sa.text(
                "UPDATE research_ir_v2_graph_versions SET artifact_json='{}' "
                "WHERE owner_id='owner-a' AND graph_identifier='phase4' AND graph_version=1"
            ))
        session.rollback()
        assert session.get(
            ResearchIrV2GraphVersion, ("owner-a", "phase4", 1)
        ).artifact_json == derive_v2_graph_facts(wrapper).artifact_json


def test_execution_and_research_graph_fact_bytes_are_identical():
    """The two stores carry the same graph evidence, not two encodings of it."""
    from app.core.strategy_admissions import put
    from app.db.models import Base, IrV2GraphVersion, StrategyAdmission

    _registry, wrapper = _phase4_fixture()
    execution = sa.create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(execution)
    research = _engine()
    with Session(execution) as execution_session, Session(research) as research_session:
        execution_receipt = put(execution_session, wrapper)
        research_receipt = store_admission(research_session, wrapper)
        execution_session.commit()
        research_session.commit()
        execution_graph = execution_session.get(IrV2GraphVersion, ("owner-a", "phase4", 1))
        research_graph = research_session.get(ResearchIrV2GraphVersion, ("owner-a", "phase4", 1))
        assert execution_receipt.artifact_json == research_receipt.artifact_json
        assert execution_graph.artifact_json == research_graph.artifact_json
        assert (
            execution_graph.owner_id,
            execution_graph.graph_identifier,
            execution_graph.graph_version,
            execution_graph.format_version,
            execution_graph.content_address,
            execution_graph.graph_address,
            execution_graph.registry_snapshot_address,
        ) == (
            research_graph.owner_id,
            research_graph.graph_identifier,
            research_graph.graph_version,
            research_graph.format_version,
            research_graph.content_address,
            research_graph.graph_address,
            research_graph.registry_snapshot_address,
        )
        assert execution_receipt.artifact_json == canonical_json(wrapper.to_dict())
        assert execution_graph.artifact_json == derive_v2_graph_facts(wrapper).artifact_json
