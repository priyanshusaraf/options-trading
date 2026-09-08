"""Phase 4 admission binds current analytical contracts to exact dataset inputs."""
from __future__ import annotations

from copy import deepcopy
import dataclasses
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.strategy_admissions import (
    AdmissionPersistenceError as ExecutionAdmissionPersistenceError,
    put,
)
from app.db.models import Base, StrategyAdmission
from app.ir.first_party.analytical_v2.contracts import (
    ContractInputBindings,
    canonical_input_bindings,
)
from app.ir.hashing import canonical_json, content_address
from app.ir.library import REGISTRY
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.v2_graph_versions import V2GraphVerificationError
from app.market_data.authority import (
    load_capability_profile,
    load_provider_conformance,
    persist_capability_assessment,
    persist_capability_profile,
    persist_provider_conformance,
)
from app.market_data.capability import assess_capability
from app.market_data.requirements import (
    DataRequirementRefusal,
    compile_data_requirement_plan,
)
from app.market_truth.identity import canonical_fact_address, load_provider_identity
from app.strategy.admission import (
    AdmissionRefused,
    admit_phase4_v2_strategy,
    admit_v2_strategy,
    is_closed_phase4_registry_snapshot,
    reconstruct_phase4_artifact,
)
from research.data.canonical_dataset import (
    load_canonical_datasets,
    project_verified_research_inputs,
)
from research.domain.admissions import (
    AdmissionPersistenceError as ResearchAdmissionPersistenceError,
    store_admission,
)
from research.domain.base import ResearchBase, init_research_db
from research.domain.models import ResearchStrategyAdmission
from research_tests.test_canonical_dataset import AS_OF, seed_canonical
from tests.test_phase4_capability_admission import _evidence, _phase4_fixture, _plan


OWNER = "owner-a"


def _plain(value):
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _analytical_graph():
    descriptor = _plain(REGISTRY.v2_components[("analytical.rising", 2)])
    frame = next(port for port in descriptor["ports"] if port["direction"] == "input")
    return {
        "format_version": 2,
        "strategy_id": "phase4.dynamic.binding",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": "Phase 4 dynamic binding",
            "description": None,
            "tags": [],
        },
        "graph_inputs": [frame],
        "graph_outputs": [],
        "nodes": [{
            "node_id": "rising",
            "component": {
                "component_id": "analytical.rising",
                "component_version": 2,
            },
            "parameters": {"window": 2},
        }],
        "edges": [{
            "edge_id": "frame-rising",
            "source": {"scope": "graph_input", "port_id": "frame"},
            "target": {"scope": "node", "node_id": "rising", "port_id": "frame"},
            "binding": {"kind": "single"},
        }],
    }


@dataclass
class DynamicAuthority:
    execution: Session
    research: Session
    graph: dict
    bindings: ContractInputBindings
    plan: object
    assessment: object
    manifest: object

    def admit(self, *, bindings=None, registry=REGISTRY, plan=None):
        return admit_phase4_v2_strategy(
            owner_id=OWNER,
            mode="RESEARCH",
            document=self.graph,
            registry=registry,
            evidence=_evidence(),
            plan=self.plan if plan is None else plan,
            input_bindings=self.bindings if bindings is None else bindings,
            assessment_address=self.assessment.authority_address,
            dataset_manifest_address=self.manifest.manifest_address,
            market_truth_snapshot_address=self.manifest.truth_snapshot_addresses[0],
            evaluation_policy_address=self.assessment.evaluation_policy_address,
            research_session=self.research,
            execution_session=self.execution,
            at_time=AS_OF,
        )


class ReceiptProxy:
    """Hostile persisted-byte candidate with independently recomputed outer identity."""

    def __init__(self, document, *, claimed_address=None):
        self.document = deepcopy(document)
        for name in (
            "owner_id", "graph_identifier", "graph_version", "graph_address",
            "scheme", "contract_suite", "parity_suite", "format_version",
            "content_address",
        ):
            setattr(self, name, self.document[name])
        self.admission_address = claimed_address or content_address(self.document)

    def to_dict(self):
        return deepcopy(self.document)


@pytest.fixture(scope="module")
def dynamic_authority(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("phase4-dynamic-binding")
    execution_engine = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    research_engine = create_engine(f"sqlite:///{tmp_path / 'research.db'}")
    Base.metadata.create_all(execution_engine)
    init_research_db(research_engine)
    with Session(execution_engine) as execution, Session(research_engine) as research:
        manifest = seed_canonical(execution, research, owner=OWNER, count=8)
        dataset = load_canonical_datasets(
            research,
            execution_session=execution,
            owner_id=OWNER,
            selections=[type("Selection", (), {
                "manifest_address": manifest.manifest_address,
                "as_of": AS_OF,
            })()],
            now=AS_OF,
        )[0][1]
        projected = project_verified_research_inputs(
            dataset,
            owner_id=OWNER,
            graph_input_fields={"frame": ("CLOSE",)},
        )
        graph = _analytical_graph()
        resolved = resolve_v2(graph, REGISTRY)
        plan = compile_data_requirement_plan(
            resolved,
            registry=REGISTRY,
            input_bindings=projected.input_bindings,
        )
        profile = load_capability_profile(
            execution, manifest.capability_profile_address, at_time=AS_OF,
        )
        conformance = load_provider_conformance(
            execution, profile.conformance_evidence_address,
        )
        exact_coverage = tuple({
            **_plain(row),
            "maximum_freshness_seconds": 0,
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        } for row in conformance.coverage)
        conformance = dataclasses.replace(conformance, coverage=exact_coverage)
        exact_offers = tuple({
            **_plain(offer),
            "maximum_freshness_seconds": 0,
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        } for offer in profile.offers)
        profile = dataclasses.replace(
            profile,
            conformance_evidence_address=conformance.address,
            offers=exact_offers,
        )
        persist_provider_conformance(execution, conformance)
        persist_capability_profile(execution, profile)
        _entity, _product, contract = load_provider_identity(
            execution, profile.provider_contract_address,
        )
        assessment = assess_capability(
            plan=plan,
            profile=profile,
            owner_id=OWNER,
            mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=manifest.truth_snapshot_addresses[0],
            evaluation_policy_address=content_address({"policy": "phase4-dynamic-test"}),
            assessment_evidence_address=conformance.address,
            at_time=int(AS_OF.timestamp()),
            conformance=conformance,
            provider_contract=contract,
        )
        assert all(
            row["result"] == "SATISFIED" for row in assessment.requirement_results
        ), assessment.requirement_results
        persist_capability_assessment(
            execution, assessment, plan=plan, at_time=AS_OF,
        )
        execution.commit()
        research.commit()
        yield DynamicAuthority(
            execution, research, graph, projected.input_bindings,
            plan, assessment, manifest,
        )
    execution_engine.dispose()
    research_engine.dispose()


def _changed_bindings(bindings, change):
    document = _plain(bindings.document)
    entry = document["inputs"]["frame"]
    fact = entry["binding"]
    if change == "owner":
        document["owner_id"] = fact["owner_id"] = "owner-b"
    elif change == "dataset_context":
        changed = content_address({"changed": change})
        document["dataset_context_address"] = fact["dataset_context_address"] = changed
    elif change == "evaluation_context":
        changed = content_address({"changed": change})
        document["evaluation_context_address"] = fact["evaluation_context_address"] = changed
    elif change == "input_name":
        document["inputs"] = {"other": entry}
    elif change == "role":
        fact["instrument"]["role"] = "peer"
    elif change == "instrument":
        fact["canonical_instrument_address"] = content_address({"changed": change})
    elif change == "field":
        fact["fields"] = ["OPEN"]
    elif change == "timeframe":
        fact["timeframe"] = 1800
    elif change == "session":
        fact["session"] = "CONTINUOUS"
    elif change == "alignment":
        fact["alignment"] = {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 1}
    elif change == "product":
        fact["provider_product_address"] = content_address({"changed": change})
    elif change == "contract":
        fact["provider_contract_address"] = content_address({"changed": change})
    elif change == "source":
        fact["market_truth_address"] = content_address({"changed": change})
    else:
        raise AssertionError(change)
    facts = {name: value["binding"] for name, value in document["inputs"].items()}
    return canonical_input_bindings(
        owner_id=document["owner_id"],
        dataset_context_address=document["dataset_context_address"],
        evaluation_context_address=document["evaluation_context_address"],
        bindings=facts,
        expected_source_addresses={
            name: content_address(fact) for name, fact in facts.items()
        },
    )


def test_each_v2_admission_path_resolves_once_and_preserves_sealed_identities(
    dynamic_authority, monkeypatch,
):
    authority = dynamic_authority
    sealed = authority.admit()
    sealed_receipt = json.loads(canonical_json(sealed.to_dict()))
    sealed_topology = _plain(sealed.base_v2_admission.resolved_topology)
    sealed_registry = _plain(sealed.base_v2_admission.registry_snapshot)
    sealed_plan = authority.plan

    import app.strategy.admission as admission_module

    actual_resolve = admission_module.resolve_v2
    calls = []

    def counted_resolve(document, registry):
        calls.append((document, registry))
        return actual_resolve(document, registry)

    monkeypatch.setattr(admission_module, "resolve_v2", counted_resolve)

    public = admit_v2_strategy(
        owner_id=OWNER,
        document=authority.graph,
        registry=REGISTRY,
        evidence=_evidence(),
    )
    call_counts = {"public": len(calls)}
    assert public.to_dict() == sealed.base_v2_admission.to_dict()
    assert _plain(public.resolved_topology) == sealed_topology
    assert _plain(public.registry_snapshot) == sealed_registry

    calls.clear()
    minted = authority.admit()
    call_counts["mint"] = len(calls)
    assert minted.to_dict() == sealed_receipt
    assert minted.phase4_data_binding["declaration_addresses"] == (
        sealed.phase4_data_binding["declaration_addresses"]
    )
    assert minted.phase4_data_binding["plan_address"] == sealed_plan.plan_address

    calls.clear()
    reconstructed = reconstruct_phase4_artifact(
        sealed_receipt,
        owner_id=OWNER,
        registry=REGISTRY,
        input_bindings=authority.bindings,
    )
    call_counts["restart"] = len(calls)
    assert reconstructed.to_dict() == sealed_receipt
    assert reconstructed.plan == sealed_plan
    assert call_counts == {"public": 1, "mint": 1, "restart": 1}


def test_real_projection_mints_and_reconstructs_exact_identity(dynamic_authority):
    authority = dynamic_authority
    artifact = authority.admit()
    provenance = artifact.assessment.plan_address == authority.plan.plan_address
    node_binding = authority.plan.parameter_binding_provenance[0]["node_contract_binding"]
    input_binding = node_binding["input_binding"]
    source = authority.bindings.document["inputs"]["frame"]

    assert provenance
    assert artifact.phase4_data_binding["plan_address"] == authority.plan.plan_address
    assert input_binding["context_address"] == authority.bindings.context_address
    assert input_binding["ports"]["frame"]["binding_address"] == source["binding_address"]
    assert input_binding["ports"]["frame"]["binding"] == source["binding"]

    persisted = json.loads(canonical_json(artifact.to_dict()))
    reconstructed = reconstruct_phase4_artifact(
        persisted,
        owner_id=OWNER,
        registry=REGISTRY,
        input_bindings=authority.bindings,
    )
    assert reconstructed.to_dict() == persisted
    assert reconstructed.plan == authority.plan
    assert reconstructed.admission_address == artifact.admission_address


def test_dynamic_receipt_persists_identical_execution_and_research_bytes(
    dynamic_authority,
):
    authority = dynamic_authority
    artifact = authority.admit()
    execution_row = put(authority.execution, artifact)
    research_row = store_admission(authority.research, artifact)
    authority.execution.commit()
    authority.research.commit()
    assert execution_row.artifact_json == research_row.artifact_json == canonical_json(
        artifact.to_dict()
    )
    assert put(authority.execution, artifact).artifact_json == execution_row.artifact_json
    assert store_admission(authority.research, artifact).artifact_json == research_row.artifact_json


def test_shared_snapshot_shape_accepts_only_legacy_or_atomic_contract_form(
    dynamic_authority,
):
    current = _plain(
        dynamic_authority.admit().base_v2_admission.registry_snapshot
    )
    assert set(current["snapshot"]) == {
        "v1_components", "v1_bodies", "v1_implementations", "v2_types",
        "v2_components", "v2_implementations", "data_requirement_declarations",
        "node_contracts", "contract_bindings",
    }
    assert is_closed_phase4_registry_snapshot(
        current, expected_address=current["address"],
    )

    static_registry, _document, _plan_value, _assessment, static = _phase4_fixture()
    legacy = _plain(static.base_v2_admission.registry_snapshot)
    assert is_closed_phase4_registry_snapshot(
        legacy, expected_address=legacy["address"],
    )
    assert legacy["address"] == static_registry.registry_snapshot_address

    for label, mutate in (
        ("unknown", lambda value: value["snapshot"].update(unknown=[])),
        ("missing-node-contracts", lambda value: value["snapshot"].pop("node_contracts")),
        ("missing-contract-bindings", lambda value: value["snapshot"].pop("contract_bindings")),
        ("wrong-node-contract-shape", lambda value: value["snapshot"].update(node_contracts={})),
        ("wrong-binding-shape", lambda value: value["snapshot"].update(contract_bindings={})),
    ):
        changed = deepcopy(current)
        mutate(changed)
        changed["address"] = content_address(changed["snapshot"])
        assert not is_closed_phase4_registry_snapshot(
            changed, expected_address=changed["address"],
        ), label
    assert not is_closed_phase4_registry_snapshot(
        current, expected_address=content_address({"stale": True}),
    )


def _reseal_registry_snapshot(receipt):
    snapshot = receipt["base_v2_admission"]["registry_snapshot"]
    address = content_address(snapshot["snapshot"])
    snapshot["address"] = address
    receipt["phase4_data_binding"]["registry_snapshot_address"] = address
    envelope = receipt["capability_assessment"]
    envelope["fact"]["registry_snapshot_address"] = address
    receipt["phase4_data_binding"]["capability_assessment_address"] = (
        canonical_fact_address(envelope["schema"], envelope["fact"])
    )
    receipt["base_v2_admission_address"] = content_address(
        receipt["base_v2_admission"]
    )


def test_both_writers_refuse_closed_snapshot_mutations_before_new_rows(
    dynamic_authority,
):
    authority = dynamic_authority
    artifact = authority.admit()
    put(authority.execution, artifact)
    store_admission(authority.research, artifact)
    authority.execution.commit()
    authority.research.commit()
    execution_before = authority.execution.scalar(
        select(func.count()).select_from(StrategyAdmission)
    )
    research_before = authority.research.scalar(
        select(func.count()).select_from(ResearchStrategyAdmission)
    )
    mutations = (
        lambda payload: payload.update(unknown=[]),
        lambda payload: payload.pop("node_contracts"),
        lambda payload: payload.pop("contract_bindings"),
        lambda payload: payload.update(node_contracts={}),
        lambda payload: payload.update(contract_bindings={}),
    )
    for mutate in mutations:
        receipt = _plain(artifact.to_dict())
        mutate(receipt["base_v2_admission"]["registry_snapshot"]["snapshot"])
        _reseal_registry_snapshot(receipt)
        proxy = ReceiptProxy(receipt)
        with pytest.raises(ExecutionAdmissionPersistenceError):
            put(authority.execution, proxy)
        with pytest.raises(ResearchAdmissionPersistenceError):
            store_admission(authority.research, proxy)
    stale = _plain(artifact.to_dict())
    stale["base_v2_admission"]["registry_snapshot"]["snapshot"][
        "node_contracts"
    ].append({})
    stale["base_v2_admission_address"] = content_address(
        stale["base_v2_admission"]
    )
    stale_proxy = ReceiptProxy(stale)
    with pytest.raises(ExecutionAdmissionPersistenceError):
        put(authority.execution, stale_proxy)
    with pytest.raises(ResearchAdmissionPersistenceError):
        store_admission(authority.research, stale_proxy)
    drift = ReceiptProxy(
        artifact.to_dict(), claimed_address=content_address({"cross-plane": "drift"}),
    )
    with pytest.raises(ExecutionAdmissionPersistenceError):
        put(authority.execution, drift)
    with pytest.raises(ResearchAdmissionPersistenceError):
        store_admission(authority.research, drift)
    assert authority.execution.scalar(
        select(func.count()).select_from(StrategyAdmission)
    ) == execution_before
    assert authority.research.scalar(
        select(func.count()).select_from(ResearchStrategyAdmission)
    ) == research_before


def test_fresh_process_repeats_dynamic_receipt_and_plan_identity(dynamic_authority, tmp_path):
    artifact = dynamic_authority.admit()
    payload = tmp_path / "receipt.json"
    payload.write_text(canonical_json({
        "receipt": artifact.to_dict(),
        "bindings": _plain(dynamic_authority.bindings.document),
        "context_address": dynamic_authority.bindings.context_address,
    }), encoding="utf-8")
    script = """
import json, sys
from app.ir.first_party.analytical_v2.contracts import ContractInputBindings
from app.ir.library import REGISTRY
from app.strategy.admission import reconstruct_phase4_artifact
value=json.load(open(sys.argv[1], encoding='utf-8'))
bindings=ContractInputBindings(value['bindings'], value['context_address'])
artifact=reconstruct_phase4_artifact(value['receipt'], owner_id='owner-a', registry=REGISTRY, input_bindings=bindings)
print(json.dumps({'admission':artifact.admission_address,'plan':artifact.plan.plan_address}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(payload)],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )
    result = json.loads(completed.stdout)
    assert result == {
        "admission": artifact.admission_address,
        "plan": dynamic_authority.plan.plan_address,
    }


def test_dynamic_admission_and_restart_require_bindings(dynamic_authority):
    authority = dynamic_authority
    before = authority.execution.scalar(
        select(func.count()).select_from(StrategyAdmission)
    )
    with pytest.raises(AdmissionRefused):
        admit_phase4_v2_strategy(
            owner_id=OWNER, mode="RESEARCH", document=authority.graph,
            registry=REGISTRY, evidence=_evidence(), plan=authority.plan,
            assessment_address=authority.assessment.authority_address,
            dataset_manifest_address=authority.manifest.manifest_address,
            market_truth_snapshot_address=authority.manifest.truth_snapshot_addresses[0],
            evaluation_policy_address=authority.assessment.evaluation_policy_address,
            research_session=authority.research,
            execution_session=authority.execution, at_time=AS_OF,
        )
    assert authority.execution.scalar(
        select(func.count()).select_from(StrategyAdmission)
    ) == before
    artifact = authority.admit()
    with pytest.raises(V2GraphVerificationError):
        reconstruct_phase4_artifact(
            artifact.to_dict(), owner_id=OWNER, registry=REGISTRY,
        )


@pytest.mark.parametrize("change", [
    "owner", "dataset_context", "evaluation_context", "input_name", "role",
    "instrument", "field", "timeframe", "session", "alignment", "product",
    "contract", "source",
])
def test_one_field_binding_substitution_refuses_mint_and_existing_receipt(
    dynamic_authority, change,
):
    authority = dynamic_authority
    artifact = authority.admit()
    changed = _changed_bindings(authority.bindings, change)
    execution_before = authority.execution.scalar(
        select(func.count()).select_from(StrategyAdmission)
    )
    research_before = authority.research.scalar(
        select(func.count()).select_from(ResearchStrategyAdmission)
    )
    assert changed.context_address != authority.bindings.context_address
    with pytest.raises(AdmissionRefused):
        authority.admit(bindings=changed)
    assert authority.execution.scalar(
        select(func.count()).select_from(StrategyAdmission)
    ) == execution_before
    assert authority.research.scalar(
        select(func.count()).select_from(ResearchStrategyAdmission)
    ) == research_before
    with pytest.raises(V2GraphVerificationError):
        reconstruct_phase4_artifact(
            artifact.to_dict(), owner_id=OWNER, registry=REGISTRY,
            input_bindings=changed,
        )


def test_forged_missing_and_unused_bindings_refuse(dynamic_authority):
    authority = dynamic_authority
    forged = object.__new__(ContractInputBindings)
    object.__setattr__(forged, "document", authority.bindings.document)
    object.__setattr__(forged, "context_address", content_address({"forged": True}))
    with pytest.raises(AdmissionRefused):
        authority.admit(bindings=forged)

    document = _plain(authority.bindings.document)
    fact = document["inputs"]["frame"]["binding"]
    missing = canonical_input_bindings(
        owner_id=document["owner_id"],
        dataset_context_address=document["dataset_context_address"],
        evaluation_context_address=document["evaluation_context_address"],
        bindings={"missing": fact},
        expected_source_addresses={"missing": content_address(fact)},
    )
    with pytest.raises(AdmissionRefused):
        authority.admit(bindings=missing)

    static_registry, static_document, _static_plan = _plan()
    with pytest.raises(DataRequirementRefusal, match="unused"):
        compile_data_requirement_plan(
            resolve_v2(static_document, static_registry),
            registry=static_registry,
            input_bindings=authority.bindings,
        )


def test_foreign_registry_refuses_and_static_receipt_identity_remains_compatible(
    dynamic_authority,
):
    authority = dynamic_authority
    foreign = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types={}, v2_components={},
    )
    with pytest.raises(AdmissionRefused):
        authority.admit(registry=foreign)
    artifact = authority.admit()
    with pytest.raises(V2GraphVerificationError):
        reconstruct_phase4_artifact(
            artifact.to_dict(), owner_id=OWNER, registry=foreign,
            input_bindings=authority.bindings,
        )

    static_registry, _document, static_plan, _assessment, static = _phase4_fixture()
    reconstructed = reconstruct_phase4_artifact(
        json.loads(canonical_json(static.to_dict())),
        owner_id=OWNER,
        registry=static_registry,
    )
    assert reconstructed.admission_address == static.admission_address
    assert reconstructed.plan == static_plan
