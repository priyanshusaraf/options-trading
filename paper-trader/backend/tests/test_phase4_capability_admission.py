"""Phase 4 wrapper, conditional receipt, and generic persistence tests."""
from __future__ import annotations

from dataclasses import replace
import datetime as dt
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.strategy_admissions import AdmissionPersistenceError, put, require_current
from app.db.models import Base, Organization
from app.ir.hashing import canonical_json, content_address
from app.ir.v2_graph_versions import (
    PersistedPhase4Artifact,
    V2GraphVerificationError,
)
from app.strategy.admission import reconstruct_phase4_artifact
from research.domain.base import ResearchBase
from research.domain.admissions import (
    AdmissionPersistenceError as ResearchAdmissionPersistenceError,
    require_admission,
    store_admission,
)
from app.strategy.admission import (
    AdmissionRefused,
    Phase4V2AdmittedStrategyArtifact,
    V2AdmissionEvidence,
    admit_phase4_v2_strategy,
    admit_v2_strategy,
)
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_v2_implementation
from app.ir.resolve import resolve_v2
from app.market_data.capability import (
    CapabilityAssessment,
    CapabilityProfile,
    CapabilityRefusal,
    assess_capability,
)
from app.market_data.authority import persist_capability_assessment
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.identity import canonical_fact_address
from research.domain.strategy_admissions import persist_verified_dataset_authority
from tests.test_phase4_dataset_assessment_authority import (
    T0,
    _authority,
    _engines,
    _seed_execution,
    address,
)
from tests.test_phase4_data_capability import (
    _profile as _capability_profile,
    _profile_authorities,
)

ADDRESS = "sha256:" + "a" * 64
def _implementation(parameters, inputs): return {}


def _plan():
    component = {"component_id": "leaf.close", "component_version": 1, "domain_family": "transform", "structural_role": "transform", "ports": [], "parameters": {}}
    declaration = {"schema": "data-requirement-declaration/1", "classification": "REQUIRES_DATA", "requirements": [{"requirement_id": "primary_close", "instrument": {"literal": {"role": "primary", "type": "PHYSICAL"}}, "field": {"literal": "CLOSE"}, "timeframe": {"literal": 60}, "history": {"literal": {"minimum_bars": 1, "warmup_bars": 20}}, "freshness": {"literal": {"maximum_age_seconds": 60}}, "depth": {"literal": {"kind": "NONE", "levels": None}}, "session": {"literal": "INSTRUMENT_CALENDAR"}, "alignment": {"literal": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}}, "derived_local": {"literal": False}}]}
    registration = registered_v2_implementation(component=("leaf.close", 1), implementation=_implementation, dependency_boundary=DependencyBoundary("defining_module"))
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): component}, v2_implementations={("leaf.close", 1): registration}, data_requirement_declarations={("leaf.close", 1): declaration})
    document = {"format_version": 2, "strategy_id": "phase4", "strategy_version": 1, "metadata": {"metadata_version": 1, "name": "P4", "description": None, "tags": []}, "graph_inputs": [], "graph_outputs": [], "nodes": [{"node_id": "close", "component": {"component_id": "leaf.close", "component_version": 1}, "parameters": {}}], "edges": []}
    return registry, document, compile_data_requirement_plan(resolve_v2(document, registry))


def _assessment():
    _, _, plan = _plan()
    profile = _capability_profile()
    conformance, contract = _profile_authorities(profile.owner_id, profile.mode, profile.offers)
    return assess_capability(plan=plan, profile=profile, owner_id="owner-a",
        mode="RESEARCH", dataset_manifest_address="sha256:" + "b" * 64,
        market_truth_snapshot_address="sha256:" + "c" * 64,
        evaluation_policy_address="sha256:" + "d" * 64,
        assessment_evidence_address="sha256:" + "e" * 64,
        at_time=int((T0 + dt.timedelta(seconds=50)).timestamp()),
        conformance=conformance, provider_contract=contract)


def _evidence(): return V2AdmissionEvidence(*(ADDRESS[:7] + value + ADDRESS[8:] for value in "1234567"))


def _phase4_fixture(
    *, admission_plan=None, admission_mode: str = "RESEARCH", name: str = "P4",
    owner_id: str = "owner-a",
):
    """Build one receipt through the current database-backed admission seam."""
    registry, document, plan = _plan()
    if name != "P4":
        document = {
            **document,
            "metadata": {**document["metadata"], "name": name},
        }
        plan = compile_data_requirement_plan(resolve_v2(document, registry))
    at_time = T0 + dt.timedelta(hours=3)
    with tempfile.TemporaryDirectory() as directory:
        execution, research = _engines(Path(directory))
        with Session(execution) as execution_session, Session(research) as research_session:
            values = _seed_execution(execution_session, owner_id=owner_id)
            manifest, segments = _authority(values, owner_id=owner_id)
            persist_verified_dataset_authority(
                research_session, manifest=manifest, segments=segments,
                execution_session=execution_session, at_time=at_time,
            )
            assessment = assess_capability(
                plan=plan, profile=values["profile"], owner_id=owner_id,
                mode="RESEARCH", dataset_manifest_address=manifest.manifest_address,
                market_truth_snapshot_address=values["truth"].address,
                evaluation_policy_address=address("evaluation-policy"),
                assessment_evidence_address=address("assessment-evidence"),
                at_time=int(at_time.timestamp()), conformance=values["conformance"],
                provider_contract=values["contract"],
            )
            persist_capability_assessment(
                execution_session, assessment, plan=plan, at_time=at_time
            )
            wrapper = admit_phase4_v2_strategy(
                owner_id=owner_id, mode=admission_mode, document=document,
                registry=registry, evidence=_evidence(),
                plan=plan if admission_plan is None else admission_plan,
                assessment_address=assessment.authority_address,
                dataset_manifest_address=manifest.manifest_address,
                market_truth_snapshot_address=values["truth"].address,
                evaluation_policy_address=assessment.evaluation_policy_address,
                research_session=research_session,
                execution_session=execution_session, at_time=at_time,
            )
        execution.dispose()
        research.dispose()
    return registry, document, plan, assessment, wrapper


def _json_receipt(wrapper):
    """Cross a process boundary: only canonical JSON-compatible values remain."""
    return json.loads(canonical_json(wrapper.to_dict()))


def _reject_reconstruction(payload, registry):
    with pytest.raises(V2GraphVerificationError):
        reconstruct_phase4_artifact(payload, owner_id="owner-a", registry=registry)


def test_legacy_non_opted_receipt_bytes_are_unchanged():
    registry, document, _ = _plan()
    component = registry.v2_components[("leaf.close", 1)]
    registration = registered_v2_implementation(component=("leaf.close", 1), implementation=_implementation, dependency_boundary=DependencyBoundary("defining_module"))
    plain = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): component}, v2_implementations={("leaf.close", 1): registration})
    receipt = admit_v2_strategy(owner_id="owner-a", document=document, registry=plain, evidence=_evidence())
    assert receipt.registry_snapshot["address"] != plain.registry_snapshot_address
    assert set(receipt.registry_snapshot["snapshot"]) == {"components", "implementation_identities", "types"}


def test_unrelated_phase4_declaration_does_not_change_non_opted_v2_receipt():
    registry, document, _ = _plan()
    declared = registry.v2_components[("leaf.close", 1)]
    plain_component = {**declared, "component_id": "leaf.plain"}
    registration = registered_v2_implementation(component=("leaf.plain", 1), implementation=_implementation, dependency_boundary=DependencyBoundary("defining_module"))
    declared_registration = registered_v2_implementation(component=("leaf.close", 1), implementation=_implementation, dependency_boundary=DependencyBoundary("defining_module"))
    mixed = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): declared, ("leaf.plain", 1): plain_component}, v2_implementations={("leaf.close", 1): declared_registration, ("leaf.plain", 1): registration}, data_requirement_declarations={("leaf.close", 1): registry.data_requirement_declarations[("leaf.close", 1)]})
    plain = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): declared, ("leaf.plain", 1): plain_component}, v2_implementations={("leaf.close", 1): declared_registration, ("leaf.plain", 1): registration})
    document = {**document, "nodes": [{"node_id": "plain", "component": {"component_id": "leaf.plain", "component_version": 1}, "parameters": {}}]}
    assert admit_v2_strategy(owner_id="owner-a", document=document, registry=mixed, evidence=_evidence()).to_dict() == admit_v2_strategy(owner_id="owner-a", document=document, registry=plain, evidence=_evidence()).to_dict()


def test_opted_in_wrapper_binds_full_registry_and_persists_exact_bytes():
    registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    assert wrapper.base_v2_admission.registry_snapshot["address"] == registry.registry_snapshot_address
    assert "data_requirement_declarations" in wrapper.base_v2_admission.registry_snapshot["snapshot"]
    assert wrapper.admission_address != wrapper.base_v2_admission.admission_address
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        assert put(session, wrapper).artifact_json
        with pytest.raises(ValueError):
            replace(wrapper, phase4_data_binding={**wrapper.phase4_data_binding, "mode": "PAPER"})


def test_wrapper_refuses_cross_owner_mode_and_embedded_base_mismatch():
    with pytest.raises(AdmissionRefused):
        _phase4_fixture(admission_mode="PAPER")
    _registry, _document, _plan, assessment, wrapper = _phase4_fixture()
    from app.strategy.admission import Phase4V2AdmittedStrategyArtifact
    with pytest.raises(ValueError, match="admission seam"):
        Phase4V2AdmittedStrategyArtifact(
            wrapper.base_v2_admission, wrapper.phase4_data_binding, assessment
        )


def test_replace_cannot_replay_private_construction_token():
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    with pytest.raises(ValueError, match="admission seam"):
        replace(wrapper, phase4_data_binding=wrapper.phase4_data_binding)


def test_embedded_base_receipt_mismatch_is_refused_after_seam_token_check():
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    from app.strategy.admission import Phase4V2AdmittedStrategyArtifact, _PHASE4_CONSTRUCTION_TOKEN
    with pytest.raises(ValueError, match="base receipt"):
        Phase4V2AdmittedStrategyArtifact(replace(wrapper.base_v2_admission, owner_id="owner-b"), wrapper.phase4_data_binding, wrapper.assessment, _PHASE4_CONSTRUCTION_TOKEN)


@pytest.mark.parametrize("change", [
    {"plan_address": "sha256:" + "f" * 64},
    {"registry_snapshot_address": "sha256:" + "f" * 64},
    {"resolved_graph_address": "sha256:" + "f" * 64},
    {"implementation_closure_address": "sha256:" + "f" * 64},
    {"declaration_addresses": ("sha256:" + "f" * 64,)},
])
def test_admission_recompiles_and_refuses_forged_plan_identity(change):
    _registry, _document, plan = _plan()
    with pytest.raises(AdmissionRefused):
        _phase4_fixture(admission_plan=replace(plan, **change))


def test_admission_refuses_empty_or_subset_assessment_coverage():
    registry, document, plan = _plan(); assessment = _assessment()
    with pytest.raises(CapabilityRefusal):
        replace(assessment, requirement_results=())

    two_leaf_document = {**document, "nodes": [*document["nodes"], {"node_id": "close-2", "component": {"component_id": "leaf.close", "component_version": 1}, "parameters": {}}]}
    two_leaf_plan = compile_data_requirement_plan(resolve_v2(two_leaf_document, registry))
    profile = _capability_profile()
    conformance, contract = _profile_authorities(profile.owner_id, profile.mode, profile.offers)
    two_leaf_assessment = assess_capability(plan=two_leaf_plan, profile=profile,
        owner_id="owner-a", mode="RESEARCH",
        dataset_manifest_address=assessment.dataset_manifest_address,
        market_truth_snapshot_address=assessment.market_truth_snapshot_address,
        evaluation_policy_address=assessment.evaluation_policy_address,
        assessment_evidence_address=assessment.assessment_evidence_address,
        at_time=int((T0 + dt.timedelta(seconds=50)).timestamp()),
        conformance=conformance, provider_contract=contract)
    with pytest.raises(CapabilityRefusal):
        replace(two_leaf_assessment,
                requirement_results=two_leaf_assessment.requirement_results[:1])


def test_capability_assessment_direct_construction_cannot_forge_satisfied_rows():
    """Copied SATISFIED rows are not an admission authority."""
    assessment = _assessment()
    with pytest.raises(CapabilityRefusal, match="constructed by assess_capability"):
        CapabilityAssessment(
            owner_id=assessment.owner_id,
            mode=assessment.mode,
            plan_address=assessment.plan_address,
            registry_snapshot_address=assessment.registry_snapshot_address,
            capability_profile_address=assessment.capability_profile_address,
            dataset_manifest_address=assessment.dataset_manifest_address,
            market_truth_snapshot_address=assessment.market_truth_snapshot_address,
            evaluation_policy_address=assessment.evaluation_policy_address,
            assessment_evidence_address=assessment.assessment_evidence_address,
            requirement_results=assessment.requirement_results,
            assessed_at=assessment.assessed_at,
        )


@pytest.mark.parametrize("change", [
    {"owner_id": "owner-b"},
    {"capability_profile_address": "sha256:" + "f" * 64},
    {"assessment_evidence_address": "sha256:" + "f" * 64},
    {"requirement_results": ()},
])
def test_dataclasses_replace_cannot_forge_canonical_assessment(change):
    """``replace`` cannot mint the private construction authority."""
    with pytest.raises(CapabilityRefusal, match="constructed by assess_capability"):
        replace(_assessment(), **change)


def test_phase4_direct_wrapper_constructor_is_closed_and_json_reconstruction_is_process_safe():
    """Raw persisted JSON reconstructs facts without replaying write authority."""
    registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()

    with pytest.raises(ValueError, match="admission seam"):
        Phase4V2AdmittedStrategyArtifact(
            wrapper.base_v2_admission,
            wrapper.phase4_data_binding,
            wrapper.assessment,
        )

    persisted_json = _json_receipt(wrapper)
    assert canonical_json(persisted_json["capability_assessment"]).encode() == (
        _assessment_value.canonical_bytes
    )
    assert canonical_fact_address(
        persisted_json["capability_assessment"]["schema"],
        persisted_json["capability_assessment"]["fact"],
    ) == persisted_json["phase4_data_binding"]["capability_assessment_address"]
    assert _assessment_value.capability_assessment_address == (
        _assessment_value.authority_address
    ) == persisted_json["phase4_data_binding"]["capability_assessment_address"]
    reconstructed = reconstruct_phase4_artifact(
        persisted_json, owner_id="owner-a", registry=registry
    )
    assert type(reconstructed) is PersistedPhase4Artifact
    assert reconstructed.to_dict() == persisted_json
    assert reconstructed.assessment == persisted_json["capability_assessment"]
    assert reconstructed.admission_address == content_address(persisted_json)
    # The reconstructed assessment is a frozen evidence mapping, not the
    # constructor-authorized CapabilityAssessment token.
    with pytest.raises(CapabilityRefusal, match="constructed by assess_capability"):
        CapabilityAssessment(**reconstructed.assessment)

    execution = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(execution)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A"))
        session.commit()
        with pytest.raises(AdmissionPersistenceError, match="constructor-authorized"):
            put(session, reconstructed)


@pytest.mark.parametrize(
    "label, mutate",
        [
            (
                "schema",
                lambda receipt: receipt["capability_assessment"].update(
                    schema="capability-assessment/1"
                ),
            ),
            (
                "algorithm",
                lambda receipt: receipt["capability_assessment"]["fact"].update(
                    assessment_algorithm="legacy-evaluation"
                ),
            ),
            (
                "algorithm version",
                lambda receipt: receipt["capability_assessment"]["fact"].update(
                    assessment_algorithm_version="1"
                ),
            ),
        (
            "assessment address",
            lambda receipt: receipt["phase4_data_binding"].update(
                capability_assessment_address="sha256:" + "f" * 64
            ),
        ),
        (
            "owner",
            lambda receipt: receipt["capability_assessment"]["fact"].update(owner_id="owner-b"),
        ),
        (
            "mode",
            lambda receipt: receipt["capability_assessment"]["fact"].update(mode="PAPER"),
        ),
        (
            "plan",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                plan_address="sha256:" + "f" * 64
            ),
        ),
        (
            "registry",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                registry_snapshot_address="sha256:" + "f" * 64
            ),
        ),
        (
            "dataset",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                dataset_manifest_address="sha256:" + "f" * 64
            ),
        ),
        (
            "market truth",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                market_truth_snapshot_address="sha256:" + "f" * 64
            ),
        ),
        (
            "policy",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                evaluation_policy_address="sha256:" + "f" * 64
            ),
        ),
        (
            "profile",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                capability_profile_address="sha256:" + "f" * 64
            ),
        ),
        (
            "evidence",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                assessment_evidence_address="sha256:" + "f" * 64
            ),
        ),
        (
            "time",
            lambda receipt: receipt["capability_assessment"]["fact"].update(assessed_at=51),
        ),
        (
            "requirement row selector",
            lambda receipt: receipt["capability_assessment"]["fact"]["requirement_results"][0].update(
                selector="sha256:" + "f" * 64
            ),
        ),
    ],
)
def test_process_style_reconstruction_refuses_assessment_tampering(label, mutate):
    """Every repeated assessment fact is checked after the original token is gone."""
    del label  # The parameter name keeps failure output explicit and readable.
    registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    payload = _json_receipt(wrapper)
    mutate(payload)
    _reject_reconstruction(payload, registry)


@pytest.mark.parametrize(
    "field, value",
    [
        ("schema", "capability-assessment/1"),
        ("assessment_algorithm", "legacy-evaluation"),
        ("assessment_algorithm_version", "1"),
        ("dataset_manifest_address", "sha256:" + "f" * 64),
    ],
)
def test_reconstruction_refuses_self_consistent_noncanonical_assessment(field, value):
    """A recomputed address cannot authorize a stale schema or dependency."""
    registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    payload = _json_receipt(wrapper)
    envelope = payload["capability_assessment"]
    if field == "schema":
        envelope["schema"] = value
    else:
        envelope["fact"][field] = value
    payload["phase4_data_binding"]["capability_assessment_address"] = (
        canonical_fact_address(envelope["schema"], envelope["fact"])
    )
    _reject_reconstruction(payload, registry)


@pytest.mark.parametrize(
    "label, mutate",
    [
        (
            "non-SATISFIED result",
            lambda receipt: receipt["capability_assessment"]["fact"]["requirement_results"][0].update(
                result="UNKNOWN", reason="complete capability is unknown"
            ),
        ),
        (
            "non-SATISFIED reason",
            lambda receipt: receipt["capability_assessment"]["fact"]["requirement_results"][0].update(
                reason="complete capability is unknown"
            ),
        ),
        (
            "missing coverage",
            lambda receipt: receipt["capability_assessment"]["fact"].update(
                requirement_results=[]
            ),
        ),
        (
            "duplicate coverage",
            lambda receipt: receipt["capability_assessment"]["fact"]["requirement_results"].append(
                dict(receipt["capability_assessment"]["fact"]["requirement_results"][0])
            ),
        ),
    ],
)
def test_process_style_reconstruction_refuses_non_satisfied_or_inexact_coverage(
    label, mutate
):
    del label
    registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    payload = _json_receipt(wrapper)
    mutate(payload)
    _reject_reconstruction(payload, registry)


def test_execution_and_research_persist_identical_complete_wrapper_json():
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    expected = canonical_json(wrapper.to_dict())
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        assert put(session, wrapper).artifact_json == expected
    with Session(research) as session:
        assert store_admission(session, wrapper).artifact_json == expected


@pytest.mark.parametrize(
    "damage",
    [
        "partial", "legacy", "wrong-schema", "forged-address",
        "wrong-algorithm", "wrong-version", "stale-dependency",
        "malformed-result", "cross-owner", "cross-mode",
    ],
)
def test_both_writers_refuse_invalid_typed_assessment_envelopes(damage):
    """Both canonicalizers recompute typed identity before any receipt write."""
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    bad = _json_receipt(wrapper)
    envelope = bad["capability_assessment"]
    fact = envelope["fact"]
    binding = bad["phase4_data_binding"]
    if damage == "partial":
        fact.pop("assessment_evidence_address")
    elif damage == "legacy":
        fact.pop("assessment_algorithm")
        fact.pop("assessment_algorithm_version")
        bad["capability_assessment"] = fact
    elif damage == "wrong-schema":
        envelope["schema"] = "capability-assessment/1"
    elif damage == "forged-address":
        binding["capability_assessment_address"] = "sha256:" + "f" * 64
    elif damage == "wrong-algorithm":
        fact["assessment_algorithm"] = "legacy-evaluation"
    elif damage == "wrong-version":
        fact["assessment_algorithm_version"] = "1"
    elif damage == "stale-dependency":
        fact["dataset_manifest_address"] = "sha256:" + "f" * 64
        binding["capability_assessment_address"] = canonical_fact_address(
            envelope["schema"], fact
        )
    elif damage == "malformed-result":
        fact["requirement_results"][0]["reason"] = "copied metadata"
    elif damage == "cross-owner":
        fact["owner_id"] = "owner-b"
        binding["capability_assessment_address"] = canonical_fact_address(
            envelope["schema"], fact
        )
    elif damage == "cross-mode":
        fact["mode"] = "PAPER"
        binding["capability_assessment_address"] = canonical_fact_address(
            envelope["schema"], fact
        )
    lookalike = SimpleNamespace(
        **{name: getattr(wrapper, name) for name in (
            "owner_id", "graph_identifier", "graph_version", "graph_address",
            "scheme", "contract_suite", "parity_suite", "format_version",
            "content_address",
        )},
        admission_address=content_address(bad),
        to_dict=lambda: bad,
    )
    execution = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:")
    ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A"))
        session.commit()
        with pytest.raises(AdmissionPersistenceError, match="Phase 4"):
            put(session, lookalike)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="Phase 4"):
            store_admission(session, lookalike)


def test_constructor_authorized_phase4_writes_and_retries_work_in_both_planes():
    """Only the exact admission-seam artifact may be inserted or retried."""
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()

    assert type(wrapper) is Phase4V2AdmittedStrategyArtifact
    expected = canonical_json(wrapper.to_dict())
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        first = put(session, wrapper)
        retry = put(session, wrapper)
        assert retry is first
        assert first.artifact_json == expected
        session.commit()
    with Session(execution) as session:
        retry = put(session, wrapper)
        assert retry.artifact_json == expected
        assert require_current(session, wrapper).artifact_json == expected
    with Session(research) as session:
        first = store_admission(session, wrapper)
        retry = store_admission(session, wrapper)
        assert retry is first
        assert first.artifact_json == expected
        session.commit()
    with Session(research) as session:
        retry = store_admission(session, wrapper)
        assert retry.artifact_json == expected
        assert require_admission(session, wrapper).artifact_json == expected


def test_both_persistence_seams_refuse_self_consistent_phase4_lookalike_with_forged_assessment_address():
    """Recomputing wrapper bytes does not grant Phase 4 write authority."""
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    forged = wrapper.to_dict()
    binding = dict(forged["phase4_data_binding"])
    forged_assessment_address = "sha256:" + "9" * 64
    assert forged_assessment_address != binding["capability_assessment_address"]
    binding["capability_assessment_address"] = forged_assessment_address
    forged["phase4_data_binding"] = binding
    forged_address = content_address(forged)
    lookalike = SimpleNamespace(
        **{name: getattr(wrapper, name) for name in (
            "owner_id", "graph_identifier", "graph_version", "graph_address",
            "scheme", "contract_suite", "parity_suite", "format_version",
            "content_address")},
        admission_address=forged_address,
        to_dict=lambda: forged,
    )
    assert lookalike.admission_address == content_address(lookalike.to_dict())
    assert lookalike.admission_address != wrapper.admission_address

    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        with pytest.raises(AdmissionPersistenceError, match="binding is stale"):
            put(session, lookalike)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="binding is stale"):
            store_admission(session, lookalike)


def test_persistence_refuses_forged_address_without_repairing_receipt():
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    forged = SimpleNamespace(**{name: getattr(wrapper, name) for name in ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme", "contract_suite", "parity_suite", "format_version", "content_address")}, admission_address="sha256:" + "f" * 64, to_dict=lambda: wrapper.to_dict())
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        with pytest.raises(AdmissionPersistenceError, match="address"):
            put(session, forged)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="address"):
            store_admission(session, forged)


def test_both_persistence_seams_refuse_partial_phase4_wrapper():
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    partial_document = wrapper.to_dict(); partial_document.pop("phase4_data_binding")
    partial = SimpleNamespace(**{name: getattr(wrapper, name) for name in ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme", "contract_suite", "parity_suite", "format_version", "content_address")}, admission_address=content_address(partial_document), to_dict=lambda: partial_document)
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        with pytest.raises(AdmissionPersistenceError, match="partial"):
            put(session, partial)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="partial"):
            store_admission(session, partial)


@pytest.mark.parametrize("damage", ["legacy_base", "incomplete_full_snapshot"])
def test_both_persistence_seams_refuse_self_consistent_incomplete_opted_base(damage):
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    bad = wrapper.to_dict(); base = dict(bad["base_v2_admission"])
    if damage == "legacy_base":
        base.pop("resolved_topology")
    else:
        envelope = dict(base["registry_snapshot"]); snapshot = dict(envelope["snapshot"])
        snapshot.pop("v1_components"); envelope["snapshot"] = snapshot
        envelope["address"] = content_address(snapshot); base["registry_snapshot"] = envelope
        binding = dict(bad["phase4_data_binding"]); binding["registry_snapshot_address"] = envelope["address"]; bad["phase4_data_binding"] = binding
    bad["base_v2_admission"] = base; bad["base_v2_admission_address"] = content_address(base)
    fake = SimpleNamespace(**{name: getattr(wrapper, name) for name in ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme", "contract_suite", "parity_suite", "format_version", "content_address")}, admission_address=content_address(bad), to_dict=lambda: bad)
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        with pytest.raises(AdmissionPersistenceError, match="Phase 4"):
            put(session, fake)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="Phase 4"):
            store_admission(session, fake)


def test_both_persistence_seams_refuse_self_consistent_forged_base_document_identity():
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    bad = wrapper.to_dict(); base = dict(bad["base_v2_admission"]); base_document = dict(base["document"])
    base_document["strategy_id"] = "forged-strategy"; base["document"] = base_document
    base["content_address"] = content_address(base_document)
    base["graph_address"] = content_address({"identity_scheme_version": 1, "graph": {key: base_document[key] for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}})
    # Keep the outer bytes self-consistent while retaining a deliberately stale
    # base graph identity; generic persistence must refuse instead of repairing it.
    bad.update({"content_address": base["content_address"], "graph_address": base["graph_address"]})
    binding = dict(bad["phase4_data_binding"]); binding["authored_ir_address"] = base["content_address"]; bad["phase4_data_binding"] = binding
    bad["base_v2_admission"] = base; bad["base_v2_admission_address"] = content_address(base)
    fake = SimpleNamespace(owner_id=bad["owner_id"], graph_identifier=bad["graph_identifier"], graph_version=bad["graph_version"], graph_address=bad["graph_address"], scheme=bad["scheme"], contract_suite=bad["contract_suite"], parity_suite=bad["parity_suite"], format_version=bad["format_version"], content_address=bad["content_address"], admission_address=content_address(bad), to_dict=lambda: bad)
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        with pytest.raises(AdmissionPersistenceError, match="Phase 4"):
            put(session, fake)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="Phase 4"):
            store_admission(session, fake)


@pytest.mark.parametrize("change", [
    ("missing", None), ("mode", "INVALID"), ("owner_id", "owner-b"),
    ("declaration_addresses", ["sha256:" + "f" * 64, "sha256:" + "a" * 64]),
    ("registry_snapshot_address", "sha256:" + "f" * 64),
])
def test_both_persistence_seams_refuse_self_consistent_invalid_inner_binding(change):
    _registry, _document, _plan_value, _assessment_value, wrapper = _phase4_fixture()
    bad = wrapper.to_dict(); binding = dict(bad["phase4_data_binding"])
    if change[0] == "missing": binding.pop("plan_address")
    else: binding[change[0]] = change[1]
    bad["phase4_data_binding"] = binding
    fake = SimpleNamespace(**{name: getattr(wrapper, name) for name in ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme", "contract_suite", "parity_suite", "format_version", "content_address")}, admission_address=content_address(bad), to_dict=lambda: bad)
    execution = create_engine("sqlite:///:memory:"); Base.metadata.create_all(execution)
    research = create_engine("sqlite:///:memory:"); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A")); session.commit()
        with pytest.raises(AdmissionPersistenceError, match="Phase 4"):
            put(session, fake)
    with Session(research) as session:
        with pytest.raises(ResearchAdmissionPersistenceError, match="Phase 4"):
            store_admission(session, fake)
