"""Bind simulated monitoring to retained research evidence and its exact rules.

The original admission is reconstructed against its original historical inputs.
Fresh monitoring inputs are a separate authority check owned by the worker.
This context grants no provider access, broker permission or money authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import sys

from sqlalchemy import select

from app.core import strategy_admissions
from app.db.models import GraphArtifact, IrV2GraphVersion
from app.ir.hashing import canonical_json
from app.ir.resource_plan import _canonical, _freeze
from app.ir.v2_graph_versions import PHASE4_BOUND_SCHEME, facts_from_row
from app.monitoring.state_contracts import _address, _identifier
from research.domain.operations import ResearchOperationRepository
from research.orchestrator import v2_operation, v2_preparation


SCHEMA = "monitoring-research-consumer/1"


class ResearchMonitoringRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise ResearchMonitoringRefused(code)


@dataclass(frozen=True)
class ResearchMonitoringContext:
    consumer: object
    graph: object
    original_projection: object
    original_admission: object
    graph_document: object


def _operation(research_session, owner_id, operation_id):
    repository = ResearchOperationRepository(research_session)
    operation = repository.get(operation_id, owner_id=owner_id)
    _require(operation is not None and operation.status == "completed"
        and operation.trigger == "v2_graph" and operation.provider_mode == v2_operation.V2_PROVIDER_MODE
        and operation.cancel_requested_at is None, "MONITORING_RESEARCH_NOT_COMPLETED")
    descriptor = v2_preparation.parse_public_preparation_plan(operation.plan)["v2_graphs"][0]
    _require(descriptor["owner_id"] == owner_id and operation.operation_id
        == v2_operation.operation_id_for_request(owner_id=owner_id, request_id=descriptor["request_id"]),
        "MONITORING_RESEARCH_SCOPE_MISMATCH")
    evidence = repository.preparation_evidence(operation_id, owner_id=owner_id)
    _require(evidence is not None, "MONITORING_RESEARCH_EVIDENCE_MISSING")
    return descriptor, evidence


def _saved_graph(execution_session, owner_id, project_id, graph_id, graph_version, descriptor):
    row = execution_session.scalar(select(IrV2GraphVersion).join(GraphArtifact,
        (IrV2GraphVersion.owner_id == GraphArtifact.owner_id)
        & (IrV2GraphVersion.graph_identifier == GraphArtifact.identifier)).where(
            IrV2GraphVersion.owner_id == owner_id, GraphArtifact.project_id == project_id,
            IrV2GraphVersion.graph_identifier == graph_id, IrV2GraphVersion.graph_version == graph_version))
    _require(row is not None, "MONITORING_RESEARCH_GRAPH_MISSING")
    facts = facts_from_row(row)
    actual = (project_id, graph_id, graph_version, facts.content_address,
        facts.graph_address, facts.registry_snapshot_address)
    expected = tuple(descriptor[key] for key in ("project_id", "graph_identifier", "graph_version",
        "content_address", "graph_address", "registry_snapshot_address"))
    _require(actual == expected, "MONITORING_RESEARCH_GRAPH_MISMATCH")
    return {"document": json.loads(facts.artifact_json), "content_address": facts.content_address,
        "graph_address": facts.graph_address, "registry_snapshot_address": facts.registry_snapshot_address}


def _original_authority(execution_session, research_session, owner_id, admission_address,
                        descriptor, evidence, version):
    from app.ir.library import REGISTRY
    original = strategy_admissions.load_phase4_descriptor(execution_session,
        owner_id=owner_id, admission_address=admission_address)
    _, projection = v2_preparation._dataset(descriptor, version, research_session, execution_session)
    admitted = {**descriptor, "admission_address": admission_address,
        "phase4_binding": original["phase4_data_binding"]}
    artifact = v2_operation._load_admitted_artifact(admitted, original, projection,
        execution_session, research_session)
    graph, plan = v2_operation._resolve_admitted_plan(version["document"], projection,
        artifact.phase4_data_binding)
    _require(canonical_json(artifact.base_v2_admission.evidence.to_dict())
        == canonical_json(evidence["addresses"]), "MONITORING_RESEARCH_EVIDENCE_MISMATCH")
    if artifact.scheme != PHASE4_BOUND_SCHEME:
        strategy_admissions.require_phase4_current(execution_session, artifact,
            research_session=research_session, plan=plan,
            at_time=dt.datetime.fromisoformat(descriptor["dataset_as_of"]))
    _require(graph.registry_snapshot_address == REGISTRY.registry_snapshot_address,
        "MONITORING_RESEARCH_LIBRARY_CHANGED")
    return artifact, graph, projection


def _replay_policy(descriptor):
    from research.strategy.v2_runtime_strategy import DIRECTIONAL_ADAPTER_POLICY_ADDRESS
    policy = descriptor["execution_policy"]
    _require(policy["adapter_policy_address"] == DIRECTIONAL_ADAPTER_POLICY_ADDRESS,
        "MONITORING_RESEARCH_ADAPTER_UNSUPPORTED")
    slippage = v2_operation._pinned_replay_slippage(descriptor)
    _require(slippage is not None, "MONITORING_RESEARCH_FILL_SPREAD_UNBOUND")
    return {"execution_policy": policy, "slippage_pct": slippage,
        "initial_state": "FLAT_AT_ACTIVATION", "history": "WARMUP_WITHOUT_RETROSPECTIVE_FILLS",
        "fill": "NEXT_OBSERVED_BAR_OPEN_SIMULATED_ONLY", "authority": "NONE"}


def research_consumer_implementation_address():
    """Bind the downstream consumer separately from the graph implementation."""
    from app.backtest import engine, identity, metrics, ratchet
    from app.core import market_hours
    from app.engine import charges, decision_kernel, equity_entry, event_risk
    from app.ir import hashing, resource_plan
    from app.monitoring import (
        contracts, evaluation, evaluation_policy, input_producer, repository, research_evaluation,
        research_event_contracts, research_prefix, research_protection, research_replay,
        research_replay_state, research_runtime, research_schedule, research_state_contracts, research_worker,
        runtime, state_contracts, watchlist_config, watchlist_store,
    )
    from app.strategy import ir_adapter, replay_decisions
    from research.data import canonical_dataset, historical_capture
    from research.evaluation import phase5_runtime
    from research.strategy import v2_runtime_strategy
    modules = (sys.modules[__name__], engine, identity, metrics, ratchet, market_hours,
        charges, decision_kernel, equity_entry, event_risk, hashing, resource_plan,
        contracts, evaluation, evaluation_policy, input_producer, repository, research_evaluation,
        research_event_contracts, research_prefix, research_protection, research_replay,
        research_replay_state, research_runtime, research_schedule, research_state_contracts, research_worker,
        runtime, state_contracts, watchlist_config, watchlist_store, ir_adapter,
        replay_decisions, canonical_dataset, historical_capture, phase5_runtime, v2_preparation, v2_operation, v2_runtime_strategy)
    digest = identity.transitive_module_source_digest(modules=modules)
    _require(digest is not None, "MONITORING_RESEARCH_IMPLEMENTATION_UNAVAILABLE")
    return "sha256:" + digest


def load_research_monitoring_context(execution_session, research_session, *, owner_id,
        project_id, graph_id, graph_version, admission_address, operation_id, assignment_id):
    """Reload original evidence for an owner-local saved graph; never infer a risk overlay."""
    try:
        for value in (owner_id, project_id, graph_id, assignment_id):
            _identifier(value, "monitoring research identity")
        _address(admission_address, "original admission")
        _require(type(graph_version) is int and graph_version > 0, "MONITORING_RESEARCH_GRAPH_MISMATCH")
        descriptor, evidence = _operation(research_session, owner_id, operation_id)
        version = _saved_graph(execution_session, owner_id, project_id, graph_id, graph_version, descriptor)
        artifact, graph, projection = _original_authority(execution_session, research_session,
            owner_id, admission_address, descriptor, evidence, version)
        from research.strategy.v2_runtime_strategy import _role_mapping
        roles = _role_mapping(version["document"])
        consumer = _canonical(SCHEMA, {"owner_id": owner_id, "project_id": project_id,
            "assignment_id": assignment_id, "graph_identifier": graph_id, "graph_version": graph_version,
            "graph_version_address": graph.authored_ir_address,
            "resolved_graph_address": graph.resolved_graph_address,
            "graph_implementation_address": graph.implementation_closure_address,
            "original_admission_address": artifact.admission_address,
            "original_operation_id": operation_id, "original_preparation_address": evidence["evidence_address"],
            "original_risk_address": evidence["addresses"]["risk_address"],
            "original_dataset_address": evidence["addresses"]["dataset_address"],
            "consumer_implementation_address": research_consumer_implementation_address(),
            "roles": roles, **_replay_policy(descriptor)})
        return ResearchMonitoringContext(consumer, graph, projection, artifact, _freeze(version['document']))
    except ResearchMonitoringRefused:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, LookupError):
        raise ResearchMonitoringRefused("MONITORING_RESEARCH_AUTHORITY_INVALID") from None
