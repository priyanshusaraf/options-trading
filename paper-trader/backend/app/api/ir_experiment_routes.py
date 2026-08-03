"""Closed S4.1 bridge from immutable graph versions to research experiments."""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings
from app.core import research_read
from app.core.instruments import get_instrument
from app.core.version import get_build_sha
from app.editor import graph_artifacts as store
from research.compare import compare_experiment_evidence
from research.config import research_db_path
from research.data.store import materialize
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import ExperimentSpec
from research.orchestrator.graph_experiment import (
    GraphBindingRejected,
    run_published_graph_experiment,
)


def _research_gate() -> None:
    if not get_settings().research_enabled:
        raise HTTPException(
            status_code=403,
            detail="research plane disabled (set PT_RESEARCH_ENABLED=1)",
        )


router = APIRouter(prefix="/api/ir", dependencies=[Depends(_research_gate)])


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class DatasetSelection(_ClosedModel):
    instrument_key: str = Field(min_length=1, max_length=48)
    interval: Literal["day", "15minute", "30minute", "60minute"]
    days: int = Field(ge=1, le=5000)


class GateSettings(_ClosedModel):
    min_oos_trades: int = Field(ge=1, le=1_000_000)
    n_folds: int = Field(ge=2, le=20)
    min_positive_fold_fraction: float = Field(ge=0.0, le=1.0)
    optimize_search: bool
    pbo_threshold: float = Field(ge=0.0, le=1.0)
    sibling_trials: int = Field(ge=1, le=100_000)


class CostAssumptions(_ClosedModel):
    capital: float = Field(gt=0.0, le=1_000_000_000.0)
    slippage_bps: float = Field(ge=0.0, le=10_000.0)
    slippage_multiplier: float = Field(ge=0.0, le=100.0)
    charge_model: Literal["zerodha_charges_v1"]
    sizing_model: Literal["one_lot_or_cash_budget_v1"]


class GraphExperimentRequest(_ClosedModel):
    program_name: str = Field(min_length=1, max_length=80)
    hypothesis_statement: str = Field(min_length=1, max_length=4000)
    datasets: list[DatasetSelection] = Field(min_length=1, max_length=32)
    seed: int = Field(ge=0, le=2_147_483_647)
    gates: GateSettings
    cost_assumptions: CostAssumptions

    @model_validator(mode="after")
    def _coherent_datasets(self):
        keys = [dataset.instrument_key for dataset in self.datasets]
        if len(keys) != len(set(keys)):
            raise ValueError("dataset instrument keys must be unique")
        intervals = {dataset.interval for dataset in self.datasets}
        if len(intervals) != 1:
            raise ValueError("all datasets in one experiment must use one interval")
        return self


class GraphExperimentResponse(_ClosedModel):
    spec_id: str
    run_id: int
    decision: Literal["propose", "archive"]
    binding: dict


EvidenceState = Literal[
    "verified", "legacy_unbound", "corrupt", "pending", "running"
]


class GraphRunCandidate(_ClosedModel):
    candidate_id: int
    status: Literal["shadow", "pending", "approved", "rejected"]
    decision: dict | None


class GraphRunSummary(_ClosedModel):
    run_id: int
    spec_id: str
    status: str
    decision: str | None
    evidence_state: EvidenceState
    graph: dict
    candidate: GraphRunCandidate | None


class GraphRunListResponse(_ClosedModel):
    runs: list[GraphRunSummary]


class GraphRunDetail(GraphRunSummary):
    evidence: dict | None


class GraphComparisonRequest(_ClosedModel):
    left_run_id: int = Field(ge=1)
    right_run_id: int = Field(ge=1)


class GraphComparisonDifference(_ClosedModel):
    dimension: str
    path: list[str | int]
    left: Any
    right: Any


class GraphComparisonResponse(_ClosedModel):
    equivalent: bool
    incomparable: list[str]
    differences: list[GraphComparisonDifference]


class CandidateDecisionRequest(_ClosedModel):
    expected_status: Literal["pending"]
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def _meaningful_reason(self):
        if not self.reason.strip():
            raise ValueError("decision reason must not be blank")
        return self


class CandidateDecisionResponse(_ClosedModel):
    candidate_id: int
    status: Literal["approved", "rejected"]
    decision: dict


def request_validation_envelope(errors: list[dict]) -> dict:
    return {
        "code": "EXPERIMENT_REQUEST_INVALID",
        "message": "Experiment request validation failed",
        "errors": [
            {
                "path": list(error.get("loc", ())[1:]),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in errors
        ],
    }


class GraphExperimentFailure(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error(status_code: int, code: str, message: str) -> GraphExperimentFailure:
    return GraphExperimentFailure(status_code, code, message)


@router.post(
    "/projects/{project_id}/graphs/{identifier}/versions/{version}/experiments",
    response_model=GraphExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_graph_experiment(
    request: Request,
    project_id: str,
    identifier: str,
    version: int,
    body: GraphExperimentRequest,
) -> GraphExperimentResponse:
    if version < 1:
        raise _error(
            422,
            "EXPERIMENT_VERSION_INVALID",
            "graph version must be greater than zero",
        )
    try:
        published = store.load_owned_version_for_experiment(
            project_id, identifier, version
        )
    except store.ProjectNotFound as exc:
        raise _error(404, "EXPERIMENT_PROJECT_NOT_FOUND", "project not found") from exc
    except store.GraphNotFound as exc:
        raise _error(404, "EXPERIMENT_GRAPH_NOT_FOUND", "graph artefact not found") from exc
    except store.GraphVersionNotFound as exc:
        raise _error(
            404,
            "EXPERIMENT_GRAPH_VERSION_NOT_FOUND",
            "immutable graph version not found",
        ) from exc
    except store.InvalidTransition as exc:
        message = str(exc)
        if "archived" in message:
            raise _error(
                409, "EXPERIMENT_PROJECT_ARCHIVED", "project is archived"
            ) from exc
        if "unpublished draft" in message:
            raise _error(
                409,
                "EXPERIMENT_GRAPH_DRAFT",
                "graph has unpublished draft changes",
            ) from exc
        raise _error(
            409, "EXPERIMENT_GRAPH_UNPUBLISHED", "graph has no published version"
        ) from exc

    datasets = []
    for selection in body.datasets:
        try:
            instrument = get_instrument(selection.instrument_key)
        except KeyError as exc:
            raise _error(
                422,
                "EXPERIMENT_DATASET_INVALID",
                f"unknown instrument {selection.instrument_key!r}",
            ) from exc
        dataset = materialize(
            request.app.state.runner.provider,
            instrument,
            selection.interval,
            selection.days,
        )
        if dataset.bar_count == 0:
            raise _error(
                422,
                "EXPERIMENT_DATASET_EMPTY",
                f"dataset {selection.instrument_key!r} contains no bars",
            )
        datasets.append((instrument, dataset))

    engine = make_engine(research_db_path())
    try:
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            try:
                report = run_published_graph_experiment(
                    session,
                    project_id=project_id,
                    graph=published.graph,
                    declared_content_address=published.content_address,
                    datasets=datasets,
                    program_name=body.program_name,
                    hypothesis_statement=body.hypothesis_statement,
                    git_commit=get_build_sha(),
                    seed=body.seed,
                    min_trades=body.gates.min_oos_trades,
                    n_folds=body.gates.n_folds,
                    min_positive_fold_frac=body.gates.min_positive_fold_fraction,
                    optimize_search=body.gates.optimize_search,
                    pbo_threshold=body.gates.pbo_threshold,
                    sibling_trials=body.gates.sibling_trials,
                    capital=body.cost_assumptions.capital,
                    slippage_bps=body.cost_assumptions.slippage_bps,
                    slippage_multiplier=body.cost_assumptions.slippage_multiplier,
                )
            except GraphBindingRejected as exc:
                session.rollback()
                raise _error(
                    422, "EXPERIMENT_GRAPH_BINDING_INVALID", str(exc)
                ) from exc
            spec = session.get(ExperimentSpec, report["spec_id"])
            recipe = json.loads(spec.recipe_json)
            provenance = recipe["graph_provenance"]
            binding = {
                **provenance,
                "datasets": recipe["datasets"],
                "cost_assumptions": recipe["cost_assumptions"],
                "gates": recipe["gates"],
            }
            return GraphExperimentResponse(
                spec_id=report["spec_id"],
                run_id=report["run_id"],
                decision=report["decision"],
                binding=binding,
            )
    finally:
        engine.dispose()


@router.get(
    "/projects/{project_id}/experiments",
    response_model=GraphRunListResponse,
)
def get_graph_experiments(project_id: str) -> GraphRunListResponse:
    return GraphRunListResponse(runs=research_read.list_graph_runs(project_id))


@router.post(
    "/projects/{project_id}/experiments/comparisons",
    response_model=GraphComparisonResponse,
)
def post_graph_experiment_comparison(
    project_id: str, body: GraphComparisonRequest
) -> GraphComparisonResponse:
    try:
        left = research_read.get_graph_run(project_id, body.left_run_id)
        right = research_read.get_graph_run(project_id, body.right_run_id)
    except research_read.StoredEvidenceCorrupt as exc:
        raise _error(
            409,
            "EXPERIMENT_EVIDENCE_CORRUPT",
            "persisted experiment evidence failed integrity verification",
        ) from exc
    if left is None or right is None:
        raise _error(404, "EXPERIMENT_RUN_NOT_FOUND", "experiment run not found")
    if (
        left["evidence_state"] != "verified"
        or right["evidence_state"] != "verified"
        or left["evidence"] is None
        or right["evidence"] is None
    ):
        raise _error(
            409,
            "EXPERIMENT_EVIDENCE_UNAVAILABLE",
            "verified terminal evidence is unavailable for comparison",
        )
    return GraphComparisonResponse(
        **compare_experiment_evidence(left["evidence"], right["evidence"])
    )


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}/decisions",
    response_model=CandidateDecisionResponse,
)
def post_candidate_decision(
    project_id: str, candidate_id: int, body: CandidateDecisionRequest
) -> CandidateDecisionResponse:
    try:
        result = research_read.decide_project_candidate(
            project_id,
            candidate_id,
            expected_status=body.expected_status,
            decision=body.decision,
            reason=body.reason.strip(),
        )
    except research_read.CandidateDecisionConflict as exc:
        raise _error(
            409,
            "CANDIDATE_STATUS_CONFLICT",
            "candidate is not pending at the expected status",
        ) from exc
    if result is None:
        raise _error(404, "CANDIDATE_NOT_FOUND", "candidate not found")
    return CandidateDecisionResponse(**result)


@router.get(
    "/projects/{project_id}/experiments/{run_id}",
    response_model=GraphRunDetail,
)
def get_graph_experiment(project_id: str, run_id: int) -> GraphRunDetail:
    try:
        run = research_read.get_graph_run(project_id, run_id)
    except research_read.StoredEvidenceCorrupt as exc:
        raise _error(
            409,
            "EXPERIMENT_EVIDENCE_CORRUPT",
            "persisted experiment evidence failed integrity verification",
        ) from exc
    if run is None:
        raise _error(404, "EXPERIMENT_RUN_NOT_FOUND", "experiment run not found")
    return GraphRunDetail(**run)


__all__ = ["GraphExperimentFailure", "request_validation_envelope", "router"]
