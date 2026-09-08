"""Critical owner-scoped persistence checks for research admission receipts."""
from __future__ import annotations

import dataclasses
import importlib
import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

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
from research.domain.base import (ResearchBase, init_research_db, make_engine,
                                  make_sessionmaker)
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Hypothesis,
    PromotionCandidate,
    ResearchProgram,
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
    ResearchBase.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
        value.rollback()
    engine.dispose()


def _run(session: Session, *, owner_id: str, admission_address: str | None) -> ExperimentRun:
    program = ResearchProgram(owner_id=owner_id, name=f"program-{owner_id}", thesis="test")
    session.add(program)
    session.flush()
    hypothesis = Hypothesis(owner_id=owner_id, program_id=program.id, statement="test")
    session.add(hypothesis)
    session.flush()
    spec = ExperimentSpec(owner_id=owner_id, id=f"spec-{owner_id}", hypothesis_id=hypothesis.id)
    session.add(spec)
    session.flush()
    run = ExperimentRun(owner_id=owner_id, spec_id=spec.id, admission_address=admission_address)
    session.add(run)
    session.flush()
    return run


def test_research_receipt_is_owner_scoped_and_exact_retries_converge(session):
    """Another owner cannot discover a private receipt, while exact retries are safe."""
    from research.domain.admissions import load_admission, require_admission, store_admission

    artifact = _artifact()
    first = store_admission(session, artifact)
    session.commit()

    assert load_admission(session, owner_id=artifact.owner_id,
                          admission_address=artifact.admission_address) is first
    assert load_admission(session, owner_id="owner-b",
                          admission_address=artifact.admission_address) is None
    assert require_admission(session, artifact) is first
    assert store_admission(session, artifact) is first


def test_research_receipt_refuses_conflicting_bytes_at_one_owner_key(session):
    """An address collision cannot replace a receipt through a raw concurrent insert."""
    from research.domain.admissions import AdmissionPersistenceError, require_admission, store_admission

    artifact = _artifact()
    corrupted = artifact.to_dict()
    corrupted["risk_model"] = {"tampered": True}
    session.execute(text("""
        INSERT INTO research_strategy_admission
            (owner_id, admission_address, graph_identifier, graph_version, graph_address,
             artifact_json, scheme, contract_suite, parity_suite, created_at)
        VALUES (:owner, :address, :graph_identifier, :graph_version, :graph_address,
                :artifact_json, :scheme, :contract_suite, :parity_suite, CURRENT_TIMESTAMP)
    """), {
        "owner": artifact.owner_id,
        "address": artifact.admission_address,
        "graph_identifier": artifact.graph_identifier,
        "graph_version": artifact.graph_version,
        "graph_address": artifact.graph_address,
        "artifact_json": canonical_json(corrupted),
        "scheme": artifact.scheme,
        "contract_suite": artifact.contract_suite,
        "parity_suite": artifact.parity_suite,
    })
    session.commit()

    with pytest.raises(AdmissionPersistenceError, match="conflicting.*immutable"):
        store_admission(session, artifact)
    with pytest.raises(AdmissionPersistenceError, match="conflicting.*immutable"):
        require_admission(session, artifact)


def test_research_receipt_refuses_forged_address(session):
    """Valid-looking receipt fields cannot make an invented address persist."""
    from research.domain.admissions import AdmissionPersistenceError, store_admission

    artifact = _artifact()

    @dataclasses.dataclass(frozen=True)
    class ForgedArtifact:
        value: AdmittedStrategyArtifact
        admission_address: str = "sha256:" + "f" * 64

        def to_dict(self):
            return self.value.to_dict()

    with pytest.raises(AdmissionPersistenceError, match="address"):
        store_admission(session, ForgedArtifact(artifact))


def test_research_receipt_refuses_direct_sql_mutation_and_retains_bytes(session):
    """Database triggers, not ORM discipline, preserve the stored receipt bytes."""
    from research.domain.admissions import store_admission

    artifact = _artifact()
    store_admission(session, artifact)
    session.commit()
    key = {"owner": artifact.owner_id, "address": artifact.admission_address}
    original = session.execute(text("""
        SELECT artifact_json FROM research_strategy_admission
        WHERE owner_id=:owner AND admission_address=:address
    """), key).scalar_one()

    for statement in (
        "UPDATE research_strategy_admission SET artifact_json='{}' "
        "WHERE owner_id=:owner AND admission_address=:address",
        "DELETE FROM research_strategy_admission "
        "WHERE owner_id=:owner AND admission_address=:address",
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(text(statement), key)
        session.rollback()
        assert session.execute(text("""
            SELECT artifact_json FROM research_strategy_admission
            WHERE owner_id=:owner AND admission_address=:address
        """), key).scalar_one() == original


def test_candidate_must_bind_to_its_own_run_and_receipt(session):
    """A candidate cannot cite another receipt or be required by a different owner."""
    from research.domain.admissions import AdmissionBindingError, require_candidate_admission, store_admission

    artifact = _artifact()
    store_admission(session, artifact)
    run = _run(session, owner_id=artifact.owner_id,
               admission_address=artifact.admission_address)
    candidate = PromotionCandidate(
        owner_id=artifact.owner_id,
        run_id=run.id,
        parameterization_hash="parameterization",
        admission_address=artifact.admission_address,
    )
    session.add(candidate)
    session.commit()

    assert (require_candidate_admission(session, candidate, owner_id=artifact.owner_id)
            .admission_address == artifact.admission_address)
    candidate.admission_address = "sha256:" + "f" * 64
    with pytest.raises(AdmissionBindingError, match="run"):
        require_candidate_admission(session, candidate, owner_id=artifact.owner_id)
    candidate.admission_address = artifact.admission_address
    with pytest.raises(AdmissionBindingError, match="owner"):
        require_candidate_admission(session, candidate, owner_id="owner-b")


def connection_marker(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(text(
            "SELECT version FROM research_schema_version")).scalar_one()


def test_fresh_research_schema_stamps_0005_and_keeps_new_rows_explicitly_unadmitted(tmp_path):
    """Migration 0005 leaves the nullable legacy state intact rather than inventing proof."""
    from research.domain import migrate

    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    try:
        inspector = sa.inspect(engine)
        # A-04 refresh: pinned the constant when 0005 was head.  The intent —
        # a fresh install stamps the CURRENT head and keeps new receipt rows
        # explicitly unadmitted — is checked against the live marker.
        assert connection_marker(engine) == migrate.HEAD_VERSION
        assert "research_strategy_admission" in inspector.get_table_names()
        for table in ("research_experiment_run", "research_promotion_candidate"):
            columns = {column["name"]: column for column in inspector.get_columns(table)}
            assert columns["admission_address"]["nullable"] is True
        with make_sessionmaker(engine)() as session:
            run = _run(session, owner_id="legacy-owner", admission_address=None)
            candidate = PromotionCandidate(
                owner_id=run.owner_id, run_id=run.id,
                parameterization_hash="legacy-parameterization", admission_address=None,
            )
            session.add(candidate)
            session.commit()
            run_id, candidate_id = run.id, candidate.id
        with engine.begin() as connection:
            assert connection.execute(text(
                "SELECT admission_address FROM research_experiment_run WHERE id=:id"),
                {"id": run_id}).scalar_one() is None
            assert connection.execute(text(
                "SELECT admission_address FROM research_promotion_candidate WHERE id=:id"),
                {"id": candidate_id}).scalar_one() is None
            for table, row_id in (("research_experiment_run", run_id),
                                  ("research_promotion_candidate", candidate_id)):
                with pytest.raises(DBAPIError, match="admission_address"):
                    connection.execute(text(
                        f"UPDATE {table} SET admission_address='not-an-address' WHERE id=:id"),
                        {"id": row_id})
    finally:
        engine.dispose()


def test_0005_upgrade_keeps_existing_run_and_candidate_addresses_null():
    """The additive migration must not manufacture proof for a 0004 receipt chain."""
    engine = create_engine("sqlite://", future=True)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TABLE research_experiment_run (
                    id INTEGER PRIMARY KEY, owner_id VARCHAR(64) NOT NULL,
                    spec_id VARCHAR(64) NOT NULL
                )
            """)
            connection.exec_driver_sql("""
                CREATE TABLE research_promotion_candidate (
                    id INTEGER PRIMARY KEY, owner_id VARCHAR(64) NOT NULL,
                    run_id INTEGER NOT NULL, parameterization_hash VARCHAR(64) NOT NULL
                )
            """)
            connection.exec_driver_sql(
                "INSERT INTO research_experiment_run (id, owner_id, spec_id) VALUES (1, 'owner-a', 'spec')")
            connection.exec_driver_sql("""
                INSERT INTO research_promotion_candidate
                    (id, owner_id, run_id, parameterization_hash)
                VALUES (2, 'owner-a', 1, 'parameters')
            """)
            migration = importlib.import_module(
                "research.domain.migrations.0005_strategy_admissions")
            migration.upgrade(
                connection,
                ResearchBase.metadata.tables["research_strategy_admission"],
                (ResearchBase.metadata.tables["research_experiment_run"],
                 ResearchBase.metadata.tables["research_promotion_candidate"]),
            )
            assert connection.execute(text(
                "SELECT admission_address FROM research_experiment_run WHERE id=1")).scalar_one() is None
            assert connection.execute(text(
                "SELECT admission_address FROM research_promotion_candidate WHERE id=2")).scalar_one() is None
    finally:
        engine.dispose()


def test_real_0004_schema_refuses_without_rewriting_legacy_rows():
    """The active finite runner preserves and refuses a genuine 0004 input."""
    from research.domain import migrate
    from research_tests.test_ir_v2_research_migration import (
        _REFUSAL_PATTERN,
        _sqlite_logical_digest,
    )

    engine = create_engine("sqlite://", future=True)
    try:
        with engine.begin() as connection:
            previous = migrate._pre_0005_tables()
            for table in previous:
                connection.execute(CreateTable(table))
            migrate._create_indexes_and_triggers(connection, tables=previous)
            migrate._create_current_marker(connection)
            connection.exec_driver_sql(
                "INSERT INTO research_schema_version (version, schema_cookie) VALUES ('0004', ?)",
                (migrate._schema_cookie(connection),),
            )
            connection.execute(text("""
                INSERT INTO research_program
                    (owner_id, name, thesis, status, created_at)
                VALUES ('owner-a', 'program', 'test', 'active', CURRENT_TIMESTAMP)
            """))
            program_id = connection.execute(text(
                "SELECT id FROM research_program WHERE owner_id='owner-a'")).scalar_one()
            connection.execute(text("""
                INSERT INTO research_hypothesis
                    (owner_id, program_id, statement, status, retest_priority, created_at)
                VALUES ('owner-a', :program_id, 'hypothesis', 'open', 1.0, CURRENT_TIMESTAMP)
            """), {"program_id": program_id})
            hypothesis_id = connection.execute(text(
                "SELECT id FROM research_hypothesis WHERE owner_id='owner-a'")).scalar_one()
            connection.execute(text("""
                INSERT INTO research_experiment_spec
                    (owner_id, id, hypothesis_id, recipe_json, git_commit,
                     qualifier_version, optimizer_version, validator_version,
                     scoring_version, rng_seed, created_at)
                VALUES ('owner-a', 'spec', :hypothesis_id, '{}', '', '', '', '', '', 0,
                        CURRENT_TIMESTAMP)
            """), {"hypothesis_id": hypothesis_id})
            connection.execute(text("""
                INSERT INTO research_experiment_run
                    (owner_id, spec_id, status, spent_bar_seconds, error, created_at)
                VALUES ('owner-a', 'spec', 'pending', 0.0, '', CURRENT_TIMESTAMP)
            """))
            run_id = connection.execute(text(
                "SELECT id FROM research_experiment_run WHERE owner_id='owner-a'")).scalar_one()
            connection.execute(text("""
                INSERT INTO research_promotion_candidate
                    (owner_id, run_id, parameterization_hash, qualifying_universe_json,
                     scorecard_json, status, created_at)
                VALUES ('owner-a', :run_id, 'parameters', '[]', '{}', 'pending', CURRENT_TIMESTAMP)
            """), {"run_id": run_id})
            candidate_id = connection.execute(text(
                "SELECT id FROM research_promotion_candidate WHERE owner_id='owner-a'")).scalar_one()

        before = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            migrate.migrate_research_db(engine)
        assert _sqlite_logical_digest(engine) == before
        with engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version FROM research_schema_version")).scalar_one() == "0004"
            assert connection.execute(text(
                "SELECT id FROM research_experiment_run WHERE id=:id"),
                {"id": run_id}).scalar_one() == run_id
            assert connection.execute(text(
                "SELECT id FROM research_promotion_candidate WHERE id=:id"),
                {"id": candidate_id}).scalar_one() == candidate_id
    finally:
        engine.dispose()


@pytest.mark.parametrize("tamper", ("disabled", "wrong_events", "when", "mislinked", "wrong_sqlstate"))
def test_postgresql_receipt_trigger_catalog_rejects_inert_same_name(monkeypatch, tamper):
    """Current-schema startup must reject a same-name receipt trigger that cannot protect rows."""
    from app.db import plane_schema
    from research.domain import migrate

    monkeypatch.setattr(plane_schema, "validate_postgresql_plane", lambda *_args, **_kwargs: None)
    immutable = ("research_experiment_spec", "research_optimization_trial",
                 "research_strategy_admission")
    actual = {
        f"{table}_refuse_mutation": (
            table, "O", 27, f"{table}_refuse_mutation",
            migrate._normalise_function_body(
                "BEGIN RAISE EXCEPTION 'research_strategy_admission is immutable' "
                "USING ERRCODE = '55000'; END;"
                if table == "research_strategy_admission"
                else f"BEGIN RAISE EXCEPTION '{table} is immutable'; END;"
            ),
            None,
        )
        for table in immutable
    }
    key = "research_strategy_admission_refuse_mutation"
    row = list(actual[key])
    if tamper == "disabled":
        row[1] = "D"
    elif tamper == "wrong_events":
        row[2] = 19
    elif tamper == "when":
        row[5] = "false"
    elif tamper == "mislinked":
        row[3] = "research_strategy_admission_passthrough"
    else:
        row[4] = migrate._normalise_function_body(
            "BEGIN RAISE EXCEPTION 'research_strategy_admission is immutable' "
            "USING ERRCODE = 'P0001'; END;"
        )
    actual[key] = tuple(row)
    monkeypatch.setattr(migrate, "_postgresql_trigger_contracts", lambda _connection: actual)

    with pytest.raises(migrate.ResearchMigrationError, match="immutable-trigger"):
        migrate._validate_postgresql(object())


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_postgresql_research_receipt_trigger_has_sqlstate_55000_and_current_contract():
    """A live PostgreSQL schema rejects raw mutations and validates its complete trigger contract."""
    from research.domain import migrate
    from research.domain.admissions import store_admission

    base_url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"research_admission_{uuid.uuid4().hex}"
    admin = create_engine(base_url, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = str(sa.engine.make_url(base_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}))
    engine = make_engine(url)
    artifact = _artifact()
    key = {"owner": artifact.owner_id, "address": artifact.admission_address}
    try:
        init_research_db(engine)
        with engine.connect() as connection:
            migrate._validate_postgresql(connection)
        with Session(engine) as session:
            store_admission(session, artifact)
            session.commit()
        with engine.connect() as connection:
            original = connection.execute(text("""
                SELECT artifact_json FROM research_strategy_admission
                WHERE owner_id=:owner AND admission_address=:address
            """), key).scalar_one()
            for statement in (
                "UPDATE research_strategy_admission SET artifact_json='{}' "
                "WHERE owner_id=:owner AND admission_address=:address",
                "DELETE FROM research_strategy_admission "
                "WHERE owner_id=:owner AND admission_address=:address",
            ):
                with pytest.raises(DBAPIError) as raised:
                    connection.execute(text(statement), key)
                assert getattr(raised.value.orig, "sqlstate", None) == "55000"
                connection.rollback()
                assert connection.execute(text("""
                    SELECT artifact_json FROM research_strategy_admission
                    WHERE owner_id=:owner AND admission_address=:address
                """), key).scalar_one() == original
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
