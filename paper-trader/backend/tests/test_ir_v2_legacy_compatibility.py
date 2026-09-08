"""IR v2 persistence compatibility cases for admitted v1 receipts."""
from __future__ import annotations

import dataclasses
import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.strategy_admissions import AdmissionPersistenceError, get, put, require_current
from app.db.models import Base, Deployment, ExecutionIntent, Position, StrategyAdmission, Trade
from app.ir.hashing import canonical_json
from app.strategy.admission import (
    AdmittedKernelIdentity,
    AdmittedStrategyArtifact,
    InputProvenance,
    ParityEvidence,
    ResolvedComponentIdentity,
    SourceEvidence,
    StructuralAdmission,
    admitted_artifact,
)


def _legacy_artifact(owner_id: str = "owner-a") -> AdmittedStrategyArtifact:
    structural = StructuralAdmission(
        owner_id=owner_id,
        source="ir_graph",
        source_evidence=SourceEvidence("ir_graph", "legacy.graph", "1", None, None),
        graph_identifier="legacy.graph",
        graph_version=1,
        graph_address="sha256:" + "1" * 64,
        resolved_components=(ResolvedComponentIdentity(
            "n", "indicator.test", 1, "sha256:" + "2" * 64, {"length": 2}),),
        input_provenance=(InputProvenance(
            "n", "source", ("close",), (("$input.close", "n.source"),)),),
        bound_parameters={"length": 2},
        kernels=(AdmittedKernelIdentity(
            "sha256:" + "2" * 64, "sha256:" + "3" * 64,
            {"history": {"mode": "bounded", "constant": 2, "terms": []}}, 2),),
        canonical_mapping={"longEntry": "signal"},
        declared_warmup=2,
        risk_model=None,
    )
    return admitted_artifact(
        structural,
        ParityEvidence("sha256:" + "4" * 64, "sha256:" + "5" * 64,
                       "sha256:" + "5" * 64),
    )


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'admissions.db'}", future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_legacy_receipt_bytes_and_semantic_v2_fields_survive_restart(sqlite_engine, tmp_path):
    artifact = _legacy_artifact()
    expected_bytes = canonical_json(artifact.to_dict())
    with Session(sqlite_engine) as session:
        put(session, artifact)
        session.commit()

    sqlite_engine.dispose()
    restarted = create_engine(f"sqlite:///{tmp_path / 'admissions.db'}", future=True)
    try:
        with Session(restarted) as session:
            row = get(session, owner_id=artifact.owner_id,
                      admission_address=artifact.admission_address)
            assert row is not None
            assert row.artifact_json == expected_bytes
            assert row.format_version is None
            assert row.content_address is None
            assert require_current(session, artifact).artifact_json == expected_bytes
    finally:
        restarted.dispose()


def test_legacy_receipts_are_owner_isolated(sqlite_engine):
    artifact = _legacy_artifact("owner-a")
    with Session(sqlite_engine) as session:
        put(session, artifact)
        session.commit()
        assert get(session, owner_id="owner-b",
                   admission_address=artifact.admission_address) is None
        with pytest.raises(AdmissionPersistenceError, match="absent for this owner"):
            require_current(session, dataclasses.replace(artifact, owner_id="owner-b"))


def test_concurrent_exact_retries_converge_to_one_immutable_receipt(sqlite_engine):
    artifact = _legacy_artifact()
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def insert_once() -> None:
        try:
            with Session(sqlite_engine) as session:
                barrier.wait()
                put(session, artifact)
                session.commit()
        except BaseException as exc:  # assertion below reports every race outcome
            errors.append(exc)

    threads = [threading.Thread(target=insert_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with Session(sqlite_engine) as session:
        rows = session.scalars(select(StrategyAdmission)).all()
        assert len(rows) == 1
        assert rows[0].format_version is None
        assert rows[0].content_address is None


def test_same_address_conflict_refuses_without_rewriting_legacy_bytes(sqlite_engine):
    artifact = _legacy_artifact()
    with Session(sqlite_engine) as session:
        corrupted = artifact.to_dict()
        corrupted["risk_model"] = {"tampered": True}
        session.execute(StrategyAdmission.__table__.insert().values(
            owner_id=artifact.owner_id,
            admission_address=artifact.admission_address,
            graph_identifier=artifact.graph_identifier,
            graph_version=artifact.graph_version,
            graph_address=artifact.graph_address,
            artifact_json=canonical_json(corrupted),
            scheme=artifact.scheme,
            contract_suite=artifact.contract_suite,
            parity_suite=artifact.parity_suite,
        ))
        session.commit()
        original = session.get(StrategyAdmission,
                               (artifact.owner_id, artifact.admission_address)).artifact_json
        with pytest.raises(AdmissionPersistenceError, match="conflicting.*immutable"):
            put(session, artifact)
        assert session.get(StrategyAdmission,
                           (artifact.owner_id, artifact.admission_address)).artifact_json == original


def test_downstream_money_records_distinguish_admission_authority_and_graph_provenance():
    for model in (Deployment, ExecutionIntent, Position, Trade):
        assert "admission_address" in model.__table__.c
        assert "graph_address" in model.__table__.c
        assert "content_address" not in model.__table__.c
