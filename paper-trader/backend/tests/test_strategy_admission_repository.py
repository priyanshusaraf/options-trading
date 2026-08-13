"""Owner-scoped immutable persistence for causal admission receipts."""
from __future__ import annotations

import dataclasses
import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import Base
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


def _artifact(owner_id: str = "owner-a") -> AdmittedStrategyArtifact:
    structural = StructuralAdmission(
        owner_id=owner_id,
        source="ir_graph",
        source_evidence=SourceEvidence("ir_graph", "graph.test", "1", None, None),
        graph_identifier="graph.test",
        graph_version=1,
        graph_address="sha256:" + "1" * 64,
        resolved_components=(ResolvedComponentIdentity(
            "n", "indicator.test", 1, "sha256:" + "2" * 64, {"length": 2}),),
        input_provenance=(InputProvenance(
            "n", "source", ("close",), (("$input.close", "n.source"),)),),
        bound_parameters={"length": 2},
        kernels=(AdmittedKernelIdentity(
            "sha256:" + "2" * 64,
            "sha256:" + "3" * 64,
            {"history": {"mode": "bounded", "constant": 2, "terms": []}},
            2,
        ),),
        canonical_mapping={"longEntry": "signal"},
        declared_warmup=2,
        risk_model=None,
    )
    return admitted_artifact(
        structural,
        ParityEvidence("sha256:" + "4" * 64,
                       "sha256:" + "5" * 64, "sha256:" + "5" * 64),
    )


@pytest.fixture
def session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
        value.rollback()
    engine.dispose()


def test_owner_scope_and_exact_duplicate_are_safe(session):
    """A receipt cannot be discovered across owners, and retrying exact bytes converges."""
    from app.core.strategy_admissions import get, put, require_current

    artifact = _artifact()
    first = put(session, artifact)
    session.commit()

    assert get(session, owner_id=artifact.owner_id,
               admission_address=artifact.admission_address) is first
    assert get(session, owner_id="owner-b", admission_address=artifact.admission_address) is None
    assert require_current(session, artifact) is first
    assert put(session, artifact) is first


def test_same_owner_address_with_different_bytes_refuses(session):
    """A damaged or raced insert cannot silently substitute receipt bytes at one key."""
    from app.core.strategy_admissions import AdmissionPersistenceError, put, require_current

    artifact = _artifact()
    corrupted = artifact.to_dict()
    # This field has no scalar mirror.  It keeps every database CHECK valid while
    # changing the immutable receipt bytes under the same forged primary key.
    corrupted["risk_model"] = {"tampered": True}
    row = {
        "owner": artifact.owner_id,
        "address": artifact.admission_address,
        "graph_identifier": artifact.graph_identifier,
        "graph_version": artifact.graph_version,
        "graph_address": artifact.graph_address,
        "artifact_json": canonical_json(corrupted),
        "scheme": artifact.scheme,
        "contract_suite": artifact.contract_suite,
        "parity_suite": artifact.parity_suite,
    }
    session.execute(text("""
        INSERT INTO strategy_admissions
            (owner_id, admission_address, graph_identifier, graph_version, graph_address,
             artifact_json, scheme, contract_suite, parity_suite, created_at)
        VALUES (:owner, :address, :graph_identifier, :graph_version, :graph_address,
                :artifact_json, :scheme, :contract_suite, :parity_suite, CURRENT_TIMESTAMP)
    """), row)
    session.commit()

    with pytest.raises(AdmissionPersistenceError, match="conflicting.*immutable"):
        put(session, artifact)
    with pytest.raises(AdmissionPersistenceError, match="conflicting.*immutable"):
        require_current(session, artifact)


def test_put_refuses_an_artifact_with_a_forged_address(session):
    """Changing the address while retaining valid-looking receipt fields is not persistence."""
    from app.core.strategy_admissions import AdmissionPersistenceError, put

    artifact = _artifact()

    @dataclasses.dataclass(frozen=True)
    class ForgedArtifact:
        value: AdmittedStrategyArtifact
        admission_address: str = "sha256:" + "f" * 64

        def to_dict(self):
            return self.value.to_dict()

    with pytest.raises(AdmissionPersistenceError, match="address"):
        put(session, ForgedArtifact(artifact))


def test_direct_sql_update_and_delete_are_refused_and_retain_bytes(session):
    """ORM guards are insufficient: raw SQL must not mutate an admitted receipt."""
    from app.core.strategy_admissions import put

    artifact = _artifact()
    put(session, artifact)
    session.commit()
    key = {"owner": artifact.owner_id, "address": artifact.admission_address}
    original = session.execute(text("""
        SELECT artifact_json FROM strategy_admissions
        WHERE owner_id=:owner AND admission_address=:address
    """), key).scalar_one()

    with pytest.raises(DBAPIError, match="immutable"):
        session.execute(text("""
            UPDATE strategy_admissions SET artifact_json='{}'
            WHERE owner_id=:owner AND admission_address=:address
        """), key)
    session.rollback()
    assert session.execute(text("""
        SELECT artifact_json FROM strategy_admissions
        WHERE owner_id=:owner AND admission_address=:address
    """), key).scalar_one() == original

    with pytest.raises(DBAPIError, match="immutable"):
        session.execute(text("""
            DELETE FROM strategy_admissions
            WHERE owner_id=:owner AND admission_address=:address
        """), key)
    session.rollback()
    assert session.execute(text("""
        SELECT artifact_json FROM strategy_admissions
        WHERE owner_id=:owner AND admission_address=:address
    """), key).scalar_one() == original


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_postgresql_raw_receipt_mutation_is_sqlstate_55000_and_retains_bytes():
    """The PostgreSQL trigger, not an ORM event, keeps a receipt append-only."""
    from app.core.strategy_admissions import put
    from app.db import migrate

    base_url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"admission_{uuid.uuid4().hex}"
    admin = create_engine(base_url, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = str(sa.engine.make_url(base_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}))
    engine = create_engine(url, future=True)
    artifact = _artifact()
    key = {"owner": artifact.owner_id, "address": artifact.admission_address}
    try:
        Base.metadata.create_all(engine)
        migrate._validate_postgresql_immutable_triggers(engine)
        with Session(engine) as session:
            put(session, artifact)
            session.commit()
        with engine.connect() as connection:
            original = connection.execute(text("""
                SELECT artifact_json FROM strategy_admissions
                WHERE owner_id=:owner AND admission_address=:address
            """), key).scalar_one()
            for statement in (
                "UPDATE strategy_admissions SET artifact_json='{}' "
                "WHERE owner_id=:owner AND admission_address=:address",
                "DELETE FROM strategy_admissions "
                "WHERE owner_id=:owner AND admission_address=:address",
            ):
                with pytest.raises(DBAPIError) as raised:
                    connection.execute(text(statement), key)
                assert getattr(raised.value.orig, "sqlstate", None) == "55000"
                connection.rollback()
                assert connection.execute(text("""
                    SELECT artifact_json FROM strategy_admissions
                    WHERE owner_id=:owner AND admission_address=:address
                """), key).scalar_one() == original
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
