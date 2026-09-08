"""Direct execution-plane regressions for immutable Phase 4 IR v2 graph facts."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.strategy_admissions import AdmissionPersistenceError, put, require_current
from app.db.models import Base, IrV2GraphVersion, Organization, StrategyAdmission
from app.ir.hashing import canonical_json
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_v2_implementation
from app.ir.resolve import resolve_v2
from app.strategy.admission import derive_v2_graph_facts
from app.ir.v2_graph_versions import (
    V2GraphVerificationError,
    facts_from_row,
    require_row_matches,
)
from app.strategy.admission import V2AdmissionEvidence
from research.domain.admissions import store_admission
from research.domain.base import ResearchBase
from research_tests.test_canonical_dataset import authority_sessions
from tests.test_v0_graph_data_eligibility import bound_csv_case


ADDRESS = "sha256:" + "a" * 64


@pytest.fixture
def bound_admission_case(bound_csv_case, authority_sessions):
    from research.data.canonical_dataset import project_verified_research_input_set
    from app.strategy.admission import admit_phase4_bound_v2_strategy
    case, loaded = bound_csv_case
    projection = project_verified_research_input_set(loaded, owner_id="owner-a", primary_input="frame",
        graph_input_fields={name: tuple(entry["binding"]["fields"])
            for name, entry in case["input_bindings"].document["inputs"].items()})
    es, rs = authority_sessions
    arguments = dict(owner_id="owner-a", document=json.loads(case["graph"].artifact_json), registry=case["registry"],
        evidence=V2AdmissionEvidence(projection.input_digest, projection.dataset_selection_address,
                                    ADDRESS, ADDRESS, ADDRESS, ADDRESS, ADDRESS),
        plan=case["plan"], projection=projection, evaluation_policy_address=case["evaluation_policy_address"],
        research_session=rs, execution_session=es, at_time=case["request"].as_of)
    return admit_phase4_bound_v2_strategy(**arguments), arguments


def test_bound_phase4_both_planes_round_trip_and_fresh_source_reload(bound_admission_case):
    from app.core.strategy_admissions import load_current_phase4_bound_artifact, load_phase4_descriptor
    from research.domain.admissions import require_admission
    wrapper, args = bound_admission_case
    es, rs = args["execution_session"], args["research_session"]
    first = put(es, wrapper); store_admission(rs, wrapper)
    es.commit(); rs.commit()
    assert first.scheme == "strategy-admission/phase4-data/2"
    assert first.artifact_json == canonical_json(wrapper.to_dict())
    assert wrapper.phase4_data_binding["dataset_set_address"] != wrapper.phase4_data_binding["dataset_manifest_address"]
    assert put(es, wrapper).admission_address == wrapper.admission_address
    assert require_admission(rs, wrapper).artifact_json == first.artifact_json
    descriptor = load_phase4_descriptor(es, owner_id="owner-a", admission_address=wrapper.admission_address)
    assert descriptor == wrapper.to_dict()
    restored = load_current_phase4_bound_artifact(es, owner_id="owner-a", admission_address=wrapper.admission_address,
        registry=args["registry"], research_session=rs, projection=args["projection"], at_time=args["at_time"])
    assert restored.to_dict() == wrapper.to_dict()
    assert restored.admission_address == wrapper.admission_address
    with pytest.raises(AdmissionPersistenceError):
        put(es, restored)
    with pytest.raises(AdmissionPersistenceError):
        load_current_phase4_bound_artifact(es, owner_id="owner-b", admission_address=wrapper.admission_address,
            registry=args["registry"], research_session=rs, projection=args["projection"], at_time=args["at_time"])


def test_bound_phase4_constructor_does_not_trust_supplied_source_projection(bound_admission_case):
    from app.strategy.admission import admit_phase4_bound_v2_strategy, Phase4BoundV2AdmittedStrategyArtifact
    wrapper, args = bound_admission_case
    with pytest.raises(ValueError, match="admission seam"):
        Phase4BoundV2AdmittedStrategyArtifact()
    with pytest.raises(ValueError):
        admit_phase4_bound_v2_strategy(**{**args, "owner_id": "owner-b"})
    forged = replace(args["evidence"], input_address=ADDRESS)
    with pytest.raises(ValueError, match="evidence differs"):
        admit_phase4_bound_v2_strategy(**{**args, "evidence": forged})
    assert wrapper.phase4_data_binding["mode"] == "RESEARCH"


@pytest.mark.parametrize("field", ["capability_assessment", "dataset_selection", "phase4_data_binding"])
def test_bound_phase4_open_receipts_are_refused(bound_admission_case, field):
    from app.strategy.admission import reconstruct_phase4_bound_artifact
    wrapper, args = bound_admission_case
    document = wrapper.to_dict(); document[field]["unexpected"] = True
    with pytest.raises(ValueError):
        reconstruct_phase4_bound_artifact(document, owner_id="owner-a", registry=args["registry"],
            input_bindings=args["projection"].input_bindings)


def test_bound_phase4_source_assignment_swap_is_not_valid_reconstruction(bound_admission_case):
    from app.strategy.admission import reconstruct_phase4_bound_artifact
    from app.market_data.capability import require_bound_capability_assessment_envelope
    wrapper, args = bound_admission_case
    document = wrapper.to_dict()
    assignments = document["capability_assessment"]["fact"]["requirement_sources"]
    for row in assignments:
        row["graph_input_id"] = "benchmark" if row["graph_input_id"] == "frame" else "frame"
    _, address = require_bound_capability_assessment_envelope(document["capability_assessment"])
    document["phase4_data_binding"]["capability_assessment_address"] = address
    with pytest.raises(ValueError, match="requirement source differs"):
        reconstruct_phase4_bound_artifact(document, owner_id="owner-a", registry=args["registry"],
            input_bindings=args["projection"].input_bindings)


def _implementation(parameters, inputs):
    return {}


def _phase4_fixture(*, name: str = "P4", owner_id: str = "owner-a"):
    from tests.test_phase4_capability_admission import _phase4_fixture as current_fixture

    registry, _document, _plan, _assessment, wrapper = current_fixture(
        name=name, owner_id=owner_id
    )
    return registry, wrapper


def _engine():
    engine = sa.create_engine(os.environ.get("PT_TEST_POSTGRES_URL", "sqlite:///:memory:"), future=True)
    Base.metadata.create_all(engine)
    return engine


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(IrV2GraphVersion)),
        session.scalar(select(func.count()).select_from(StrategyAdmission)),
    )


def test_execution_phase4_write_is_atomic_and_receipt_contains_capability_assessment():
    from app.core.strategy_admissions import load_phase4_descriptor
    _registry, wrapper = _phase4_fixture()
    engine = _engine()
    with Session(engine) as session:
        original = put(session, wrapper)
        session.commit()
        row = session.get(IrV2GraphVersion, ("owner-a", "phase4", 1))
        assert row is not None
        assert original.artifact_json == canonical_json(wrapper.to_dict())
        assert "capability_assessment" in json.loads(original.artifact_json)
        assert facts_from_row(row) == derive_v2_graph_facts(wrapper)
        assert require_current(session, wrapper).artifact_json == original.artifact_json
        assert load_phase4_descriptor(session, owner_id=wrapper.owner_id,
            admission_address=wrapper.admission_address) == wrapper.to_dict()


def test_execution_exact_retries_and_identity_collision_refuse():
    _registry, wrapper = _phase4_fixture()
    _variant_registry, variant = _phase4_fixture(name="different-bytes")
    engine = _engine()
    with Session(engine) as session:
        first = put(session, wrapper)
        retry = put(session, wrapper)
        assert retry.artifact_json == first.artifact_json
        session.commit()
        assert _counts(session) == (1, 1)
        with pytest.raises(AdmissionPersistenceError, match="v2 graph version"):
            put(session, variant)
        session.rollback()
        assert _counts(session) == (1, 1)


def test_execution_graph_and_receipt_have_no_partial_write_on_receipt_failure():
    _registry, wrapper = _phase4_fixture(owner_id="owner-flush-execution")

    def fail_receipt(_mapper, _connection, _target):
        raise RuntimeError("injected receipt failure")

    engine = _engine()
    event.listen(StrategyAdmission, "before_insert", fail_receipt)
    try:
        with Session(engine) as session:
            with pytest.raises(RuntimeError, match="injected receipt failure"):
                put(session, wrapper)
            session.rollback()
        with Session(engine) as observer:
            assert observer.scalar(select(func.count()).select_from(IrV2GraphVersion).where(
                IrV2GraphVersion.owner_id == wrapper.owner_id)) == 0
            assert observer.scalar(select(func.count()).select_from(StrategyAdmission).where(
                StrategyAdmission.owner_id == wrapper.owner_id)) == 0
    finally:
        event.remove(StrategyAdmission, "before_insert", fail_receipt)


@pytest.mark.parametrize("caller_state", ["clean", "prior-read", "prior-write", "explicit"])
def test_execution_real_writer_preserves_the_callers_lifecycle(caller_state: str):
    """Exercise ``put`` itself; no generic savepoint substitute is involved."""
    owner = f"owner-lifecycle-execution-{uuid.uuid4().hex}"
    _registry, wrapper = _phase4_fixture(owner_id=owner)
    engine = _engine()
    try:
        if caller_state == "explicit":
            with Session(engine) as session:
                with session.begin():
                    put(session, wrapper)
        else:
            with Session(engine) as session:
                if caller_state == "prior-read":
                    session.execute(sa.text("SELECT 1"))
                elif caller_state == "prior-write":
                    _unused, caller_work = _phase4_fixture(
                        owner_id=f"caller-work-execution-{uuid.uuid4().hex}")
                    put(session, caller_work)
                put(session, wrapper)
                session.commit()
        with Session(engine) as observer:
            assert observer.scalar(select(func.count()).select_from(IrV2GraphVersion).where(
                IrV2GraphVersion.owner_id == owner)) == 1
            assert observer.scalar(select(func.count()).select_from(StrategyAdmission).where(
                StrategyAdmission.owner_id == owner)) == 1
    finally:
        engine.dispose()


def test_execution_real_writer_caller_rollback_and_commit_refusal_leave_no_rows():
    owner = f"owner-refusal-execution-{uuid.uuid4().hex}"
    _registry, wrapper = _phase4_fixture(owner_id=owner)
    engine = _engine()

    def refuse_commit(connection):
        if connection.engine is engine:
            raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)

    event.listen(engine, "commit", refuse_commit)
    try:
        with Session(engine) as session:
            put(session, wrapper)
            with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                session.commit()
            session.rollback()
        with Session(engine) as observer:
            assert observer.scalar(select(func.count()).select_from(IrV2GraphVersion).where(
                IrV2GraphVersion.owner_id == owner)) == 0
            assert observer.scalar(select(func.count()).select_from(StrategyAdmission).where(
                StrategyAdmission.owner_id == owner)) == 0
    finally:
        event.remove(engine, "commit", refuse_commit)
        engine.dispose()


def test_execution_writer_preflushes_valid_caller_work_and_refuses_invalid_work_distinctly():
    """A pre-savepoint caller flush is never mistaken for an admission collision."""
    owner = f"owner-preflush-execution-{uuid.uuid4().hex}"
    _registry, wrapper = _phase4_fixture(owner_id=owner)
    engine = _engine()
    try:
        with Session(engine) as session:
            session.add(Organization(organization_id=f"caller-{uuid.uuid4().hex}", name="caller"))
            def fail_receipt(*_args):
                raise RuntimeError("receipt failure")
            event.listen(StrategyAdmission, "before_insert", fail_receipt)
            try:
                with pytest.raises(RuntimeError, match="receipt failure"):
                    put(session, wrapper)
                session.commit()
            finally:
                event.remove(StrategyAdmission, "before_insert", fail_receipt)
        with Session(engine) as observer:
            assert observer.get(StrategyAdmission, (owner, wrapper.admission_address)) is None
        with Session(engine) as session:
            session.add(Organization(organization_id=None, name="invalid"))
            with pytest.raises(RuntimeError, match="pre-savepoint caller flush failure"):
                put(session, wrapper)
            session.rollback()
        with Session(engine) as observer:
            assert observer.get(StrategyAdmission, (owner, wrapper.admission_address)) is None
    finally:
        engine.dispose()


def test_execution_graph_is_immutable_through_orm_and_sqlite_trigger():
    _registry, wrapper = _phase4_fixture()
    engine = _engine()
    with Session(engine) as session:
        put(session, wrapper)
        session.commit()
        row = session.get(IrV2GraphVersion, ("owner-a", "phase4", 1))
        row.artifact_json = "{}"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()
        session.rollback()
        with pytest.raises(sa.exc.DBAPIError):
            session.execute(sa.text(
                "UPDATE ir_v2_graph_versions SET artifact_json='{}' "
                "WHERE owner_id='owner-a' AND graph_identifier='phase4' AND graph_version=1"
            ))
        session.rollback()
        assert session.get(IrV2GraphVersion, ("owner-a", "phase4", 1)).artifact_json == (
            derive_v2_graph_facts(wrapper).artifact_json
        )


def test_execution_fact_verifier_rejects_tampered_canonical_identity():
    _registry, wrapper = _phase4_fixture()
    engine = _engine()
    with Session(engine) as session:
        put(session, wrapper)
        session.commit()
        row = session.get(IrV2GraphVersion, ("owner-a", "phase4", 1))
        expected = derive_v2_graph_facts(wrapper)
        with pytest.raises(V2GraphVerificationError):
            require_row_matches(row, replace(expected, content_address="sha256:" + "f" * 64))


def test_phase4_receipt_survives_process_death_and_fresh_registry_reconstruction(tmp_path):
    """A new interpreter verifies both durable planes before refusing v2 runtime."""
    _registry, wrapper = _phase4_fixture()
    execution_path = tmp_path / "execution.db"
    research_path = tmp_path / "research.db"
    execution = sa.create_engine(f"sqlite:///{execution_path}", future=True)
    research = sa.create_engine(f"sqlite:///{research_path}", future=True)
    Base.metadata.create_all(execution)
    ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        put(session, wrapper)
        session.commit()
    with Session(research) as session:
        store_admission(session, wrapper)
        session.commit()
    execution.dispose()
    research.dispose()

    backend_dir = Path(__file__).resolve().parents[1]
    script = r'''import importlib
import json
import sys
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

fixture = importlib.import_module(sys.argv[3])
from app.backtest.repository import AdmissionRequired, load_verified_admission
from app.strategy.admission import reconstruct_phase4_artifact
from app.db.models import StrategyAdmission
from research.domain.admissions import require_admission
from research.domain.models import ResearchStrategyAdmission

execution = sa.create_engine("sqlite:///" + sys.argv[1], future=True)
research = sa.create_engine("sqlite:///" + sys.argv[2], future=True)
registry, _unused_constructor_artifact = fixture._phase4_fixture()
with Session(research) as session:
    receipt = session.scalar(select(ResearchStrategyAdmission).where(
        ResearchStrategyAdmission.owner_id == "owner-a"
    ))
    assert receipt is not None
    artifact = reconstruct_phase4_artifact(
        json.loads(receipt.artifact_json), owner_id="owner-a", registry=registry
    )
    require_admission(session, artifact)
with Session(execution) as session:
    receipt = session.scalar(select(StrategyAdmission).where(
        StrategyAdmission.owner_id == "owner-a"
    ))
    assert receipt is not None
    try:
        load_verified_admission(
            session,
            owner_id="owner-a",
            admission_address=receipt.admission_address,
            registry=registry,
        )
    except AdmissionRequired as exc:
        assert exc.code == "PHASE4_CONTEXT_REQUIRED"
    else:
        raise AssertionError("verified v2 receipt reached a runtime consumer")
print("fresh-process contextless loader refused PHASE4_CONTEXT_REQUIRED")
'''
    environment = os.environ.copy()
    python_path = [str(backend_dir), str(backend_dir / "tests")]
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    completed = subprocess.run(
        [sys.executable, "-c", script, str(execution_path), str(research_path),
         _implementation.__module__],
        cwd=backend_dir.parent,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        "fresh-process contextless loader refused PHASE4_CONTEXT_REQUIRED"
    )


def test_phase4_current_loader_rejects_missing_authority_context_before_lookup():
    from app.core.strategy_admissions import load_current_phase4_artifact
    with pytest.raises(AdmissionPersistenceError, match="authority context"):
        load_current_phase4_artifact(None, owner_id="owner-a", admission_address=ADDRESS,
                                    registry=None, research_session=None)


def test_bound_phase4_reloads_secondary_source_bytes_on_admission_and_restart(bound_admission_case):
    """Storage blocks writes; a simulated corrupt read must also fail closed."""
    from app.core.strategy_admissions import load_current_phase4_bound_artifact
    from app.strategy.admission import admit_phase4_bound_v2_strategy
    from research.domain.models import ResearchDatasetManifestV2
    from sqlalchemy.orm.attributes import set_committed_value
    wrapper, args = bound_admission_case
    es, rs = args["execution_session"], args["research_session"]
    put(es, wrapper); store_admission(rs, wrapper); es.commit(); rs.commit()
    source_address = args["projection"].input_sources["benchmark"].manifest.manifest_address
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        rs.execute(sa.update(ResearchDatasetManifestV2).where(
            ResearchDatasetManifestV2.owner_id == "owner-a", ResearchDatasetManifestV2.manifest_address == source_address
        ).values(canonical_bytes=b"{}"))
    rs.rollback()
    row = rs.get(ResearchDatasetManifestV2, ("owner-a", source_address))
    # Inject a private identity-map read fault without a write or dirty flush.
    set_committed_value(row, "canonical_bytes", b"{}")
    assert row not in rs.dirty
    with pytest.raises(ValueError):
        admit_phase4_bound_v2_strategy(**args)
    with pytest.raises(AdmissionPersistenceError):
        load_current_phase4_bound_artifact(es, owner_id="owner-a", admission_address=wrapper.admission_address,
            registry=args["registry"], research_session=rs, projection=args["projection"], at_time=args["at_time"])


def _readdress_bound_selection(document):
    from app.ir.hashing import content_address
    from app.market_data.capability import require_bound_capability_assessment_envelope
    address = content_address(document["dataset_selection"])
    document["phase4_data_binding"]["dataset_set_address"] = address
    document["capability_assessment"]["fact"]["dataset_set_address"] = address
    _, assessment_address = require_bound_capability_assessment_envelope(document["capability_assessment"])
    document["phase4_data_binding"]["capability_assessment_address"] = assessment_address
    document["base_v2_admission"]["evidence"]["dataset_address"] = address
    document["base_v2_admission_address"] = content_address(document["base_v2_admission"])


def test_bound_phase4_readdressed_selection_cannot_reuse_old_context(bound_admission_case):
    from app.strategy.admission import reconstruct_phase4_bound_artifact
    wrapper, args = bound_admission_case
    document = wrapper.to_dict()
    document["dataset_selection"]["inputs"]["benchmark"]["source_codec"] = "changed-source-codec"
    _readdress_bound_selection(document)
    with pytest.raises(ValueError, match="selection context differs"):
        reconstruct_phase4_bound_artifact(document, owner_id="owner-a", registry=args["registry"],
            input_bindings=args["projection"].input_bindings)


@pytest.mark.parametrize("cutoff", ["2026-04-01T00:00:01.100000+00:00", "2026-04-01T01:00:01+01:00", "2026-04-01T00:00:01Z"])
def test_bound_phase4_receipt_requires_canonical_whole_utc_cutoff(bound_admission_case, cutoff):
    from app.ir.v2_graph_versions import require_bound_phase4_receipt
    wrapper, _ = bound_admission_case
    document = wrapper.to_dict(); document["dataset_selection"]["as_of"] = cutoff
    _readdress_bound_selection(document)
    with pytest.raises(ValueError, match="cutoff differs"):
        require_bound_phase4_receipt(document)
