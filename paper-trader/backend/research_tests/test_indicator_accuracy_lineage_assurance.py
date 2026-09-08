"""Independent assurance of real research/cache/public/reclaim consumers."""
from __future__ import annotations

from copy import deepcopy
import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.backtest import repository
from app.backtest.artifacts import (
    BoundedResearchArtifactStore,
    ResearchArtifactRefusal,
    research_cache_identity,
    research_cache_identity_document,
)
from app.backtest.public_computation import is_eligible
from app.db.models import BacktestRun, Base, Organization
from app.ir.hashing import content_address
from app.ir.library import REGISTRY


ROOT = Path(__file__).resolve().parents[3]
IMPACT_CONSUMERS = {
    "registry_composition": {
        "paper-trader/backend/app/ir/library.py": ("ANALYTICAL_V2_DISPOSITIONS", "compose_v2")},
    "contract_binding_identity": {
        "paper-trader/backend/app/ir/registry.py": ("contract_bindings", "registry_snapshot_address"),
        "paper-trader/backend/app/market_data/requirements.py": ("parameter_binding_provenance",),
    },
    "numeric_execution": {
        "paper-trader/backend/app/ir/runtime.py": ("evaluate_v2", "evaluation_context_resolver"),
        "paper-trader/backend/app/ir/streaming_reference.py": ("evaluate_v2_prefix_stream",)},
    "state_resource_execution": {
        "paper-trader/backend/app/ir/incremental_runtime.py": (
            "registry_snapshot_address", "resource_plan_address", "run_authority_address")},
    "artifact_serialization": {
        "paper-trader/backend/app/backtest/artifacts.py": (
            "implementation_closure_address", "registry_snapshot_address", "resolved_graph_address")},
    "cache_identity": {
        "paper-trader/backend/app/backtest/cache.py": (
            "implementation_closure_address", "registry_snapshot_address", "plan_address")},
    "public_materialization": {
        "paper-trader/backend/app/backtest/public_computation.py": (
            "is_eligible", "put_immutable", "maybe_materialize")},
    "claim_reclaim_result": {
        "paper-trader/backend/app/backtest/repository.py": (
            "load_verified_v2_lifecycle_admission", "claim_frozen_run", "append_claimed_result_batch")},
    "admission_research_context": {
        "paper-trader/backend/app/core/strategy_admissions.py": (
            "registry_snapshot_address", "implementation_closure_address")},
    "research_consumer": {
        "paper-trader/backend/research/orchestrator/graph_experiment.py": (
            "REGISTRY", "require_graph_admission", "run_published_graph_experiment")},
    "persisted_model_constraints": {
        "paper-trader/backend/research/domain/models.py": (
            "ResearchIrV2GraphVersion", "ResearchStrategyAdmission", "immutable")},
}


def _address(label: str) -> str:
    return content_address({"complete-universe-assurance": label})


def _identity_values(*, suffix="a", owner_id="assurance-owner"):
    return {
        "owner_id": owner_id,
        "licence_scope": "OWNER_PRIVATE",
        "semantic_nodes": [{"component_id": "analytical.sma", "component_version": 2}],
        "parameters_address": _address(f"parameters-{suffix}"),
        "instrument_addresses": [_address(f"instrument-{suffix}")],
        "registry_snapshot_address": REGISTRY.registry_snapshot_address,
        "dataset_manifest_address": _address(f"dataset-{suffix}"),
        "provider_evidence_addresses": [_address(f"provider-{suffix}")],
        "event_start": "2026-01-01T00:00:00+00:00",
        "event_end": "2026-01-02T00:00:00+00:00",
        "segment_addresses": [_address(f"segment-{suffix}")],
        "adjustment_policy_address": _address(f"adjustment-{suffix}"),
        "session_policy_address": _address(f"session-{suffix}"),
        "resampling_policy_address": _address(f"resampling-{suffix}"),
        "missing_data_policy_address": _address(f"missing-{suffix}"),
        "alignment_policy_address": _address(f"alignment-{suffix}"),
        "implementation_closure_address": _address(f"implementation-{suffix}"),
        "resolved_graph_address": _address(f"graph-{suffix}"),
        "resource_plan_address": _address(f"resource-{suffix}"),
        "evaluation_policy_address": _address(f"evaluation-{suffix}"),
        "node_context_resolver_address": _address(f"resolver-{suffix}"),
        "run_authority_address": _address(f"run-{suffix}"),
    }


def _identity(**overrides):
    values = _identity_values()
    values.update(overrides)
    return research_cache_identity(research_cache_identity_document(**values))


def _store():
    return BoundedResearchArtifactStore(
        owner_id="assurance-owner", licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=4096, artifact_bytes_upper_bound=1024,
        entry_upper_bound=8, concurrency_upper_bound=1, queue_depth_upper_bound=2,
    )


def test_every_actual_impact_matrix_consumer_is_explicit_and_identity_aware():
    assert set(IMPACT_CONSUMERS) == {
        "registry_composition", "contract_binding_identity", "numeric_execution",
        "state_resource_execution", "artifact_serialization", "cache_identity",
        "public_materialization", "claim_reclaim_result", "admission_research_context",
        "research_consumer", "persisted_model_constraints"}
    for consumer, files in IMPACT_CONSUMERS.items():
        assert files, consumer
        for relative, required_tokens in files.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            for token in required_tokens:
                assert token in source, (consumer, relative, token)


def test_actual_research_cache_binds_every_answer_changing_dimension_and_reconstructs_history():
    baseline_values = _identity_values()
    baseline = _identity()
    fields = sorted(set(baseline_values) - {"owner_id", "licence_scope"})
    assert len(fields) >= 20
    for field in fields:
        changed = deepcopy(baseline_values)
        if field == "semantic_nodes":
            changed[field][0]["component_version"] = 1
        elif field == "event_start":
            changed[field] = "2025-12-31T23:59:00+00:00"
        elif field == "event_end":
            changed[field] = "2026-01-02T00:01:00+00:00"
        elif isinstance(changed[field], list):
            changed[field] = [_address(f"changed-{field}")]
        else:
            changed[field] = _address(f"changed-{field}")
        candidate = research_cache_identity(research_cache_identity_document(**changed))
        assert candidate.identity_address != baseline.identity_address, field

    store = _store()
    old = store.get_or_compute(baseline, lambda: {"historical_result": [1.5, 2.5]})
    assert old.from_cache is False
    restarted = BoundedResearchArtifactStore.from_snapshot(
        store.snapshot(), cache_bytes_upper_bound=4096, artifact_bytes_upper_bound=1024,
        entry_upper_bound=8, concurrency_upper_bound=1, queue_depth_upper_bound=2,
    )
    restored = restarted.get_or_compute(baseline, lambda: {"historical_result": [99]})
    changed = _identity(implementation_closure_address=_address("changed-semantics"))
    fresh = restarted.get_or_compute(changed, lambda: {"new_result": [3.5]})
    assert restored.from_cache is True and restored.payload == {"historical_result": [1.5, 2.5]}
    assert restored.artifact_address == old.artifact_address
    assert fresh.from_cache is False and fresh.payload == {"new_result": [3.5]}


def test_missing_stale_duplicate_and_reordered_research_identity_refuse():
    baseline = _identity_values()
    for field in baseline:
        document = dict(research_cache_identity_document(**baseline))
        document.pop(field)
        with pytest.raises(ResearchArtifactRefusal):
            research_cache_identity(document)
    stale = dict(research_cache_identity_document(**baseline))
    stale["registry_snapshot_address"] = _address("stale-registry")
    with pytest.raises(ResearchArtifactRefusal, match="stale"):
        research_cache_identity(stale)
    duplicated = deepcopy(baseline)
    duplicated["semantic_nodes"] *= 2
    with pytest.raises(ResearchArtifactRefusal, match="noncanonical"):
        research_cache_identity(research_cache_identity_document(**duplicated))
    reordered = deepcopy(baseline)
    reordered["semantic_nodes"] = [
        {"component_id": "analytical.zscore", "component_version": 2},
        {"component_id": "analytical.sma", "component_version": 2},
    ]
    with pytest.raises(ResearchArtifactRefusal, match="noncanonical"):
        research_cache_identity(research_cache_identity_document(**reordered))


def test_failed_reclaim_cannot_claim_after_admission_semantics_change_and_preserves_row():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = dt.datetime(2026, 8, 29, 12, tzinfo=dt.timezone.utc)
    old_admission = _address("old-admission-semantics")
    new_admission = _address("new-admission-semantics")
    with Session(engine) as session:
        session.add(Organization(organization_id="assurance-owner", name="Assurance"))
        session.add(BacktestRun(
            owner_id="assurance-owner", scope="assurance", intervals="day", capital=1.0,
            total=1, status="running", admission_address=old_admission,
            claim_token="dead-worker", claimed_by="dead-worker",
            claim_expires_at=now - dt.timedelta(seconds=1),
        ))
        session.commit()
        frozen = repository.snapshot_claimable_runs(session, owner_id="assurance-owner", now=now)[0]
        reconciled, successor = repository.reconcile_frozen_run(session, frozen=frozen, now=now)
        assert reconciled and successor is not None and successor.status == "pending"
        row = session.get(BacktestRun, frozen.id)
        row.admission_address = new_admission
        session.flush()
        assert repository.claim_frozen_run(
            session, frozen=successor, claimed_by="replacement", now=now) is None
        session.expire_all()
        retained = session.get(BacktestRun, frozen.id)
        assert retained.admission_address == new_admission
        assert retained.status == "pending" and retained.claim_token is None
    engine.dispose()


def test_public_consumer_never_promotes_private_or_incomplete_v2_research():
    assert is_eligible(
        dataset_classification="MARKET_PUBLIC",
        strategy_key="ir.assurance-sma",
        strategy_module="app.ir.runtime",
        execution_manifest={"dataset_address": _address("dataset"), "dataset_verified": True},
    ) is False
    assert is_eligible(
        dataset_classification="OWNER_PRIVATE",
        strategy_key="ir.assurance-sma",
        strategy_module="app.ir.runtime",
        execution_manifest={
            "dataset_address": _address("dataset"), "dataset_verified": True,
            "registry_snapshot_address": REGISTRY.registry_snapshot_address,
        },
    ) is False


def test_cache_resource_bounds_pass_at_limit_and_refuse_first_over():
    identity = _identity()
    payload = {"value": "x" * 64}
    from app.backtest.artifacts import _canonical_payload
    size = len(_canonical_payload(payload))
    exact = BoundedResearchArtifactStore(
        owner_id="assurance-owner", licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=size, artifact_bytes_upper_bound=size,
        entry_upper_bound=1, concurrency_upper_bound=1, queue_depth_upper_bound=0,
    )
    assert exact.get_or_compute(identity, lambda: payload).payload == payload
    too_small = BoundedResearchArtifactStore(
        owner_id="assurance-owner", licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=size, artifact_bytes_upper_bound=size - 1,
        entry_upper_bound=1, concurrency_upper_bound=1, queue_depth_upper_bound=0,
    )
    with pytest.raises(ResearchArtifactRefusal, match="artifact exceeds"):
        too_small.get_or_compute(identity, lambda: payload)
