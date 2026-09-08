"""Closed S4.1 bridge from immutable graph versions to research experiments."""
from __future__ import annotations

import json
import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings
from app.core import research_read
from app.core.instruments import get_instrument
from app.core.version import get_build_sha
from app.core.release_profile import is_v0_profile
from app.db.session import SessionLocal
from app.api.principal import Principal, get_principal, owner_id_for
from app.api.execution_access import local_execution_cell
from app.editor import graph_artifacts as store
from app.editor import v2_editor_store
from app.editor.comparison import GraphComparisonRejected, compare_graph_versions
from app.ir.hashing import canonical_json
from app.ir.v2_graph_versions import V2GraphVerificationError
from research.compare import compare_experiment_evidence
from research.config import research_database_url
from research.data.store import materialize
from research.data.canonical_dataset import CanonicalDatasetRefused, load_canonical_datasets
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import ExperimentSpec
from research.domain.operations import ResearchOperationRepository
from research.orchestrator.v2_operation import (
    V2_PROVIDER_MODE,
    V2OperationRefusal,
    build_v2_operation_plan,
    operation_id_for_request,
)
from research.orchestrator.graph_experiment import (
    GraphAdmissionRejected,
    GraphBindingRejected,
    enqueue_graph_admission,
    build_graph_provenance,
    require_graph_admission,
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


class CanonicalDatasetSelection(_ClosedModel):
    kind: Literal["canonical_manifest_v2"]
    manifest_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    as_of: AwareDatetime

    @model_validator(mode="after")
    def _utc_whole_seconds(self):
        if self.as_of.utcoffset() != dt.timedelta(0) or self.as_of.microsecond:
            raise ValueError("canonical as_of must be whole UTC seconds")
        return self


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


class StationaryBootstrapSettings(_ClosedModel):
    enabled: bool
    iterations: int = Field(ge=100, le=5_000)
    restart_probability_ppm: int = Field(ge=1, le=1_000_000)


class ParameterNeighborhoodAxisSettings(_ClosedModel):
    node_id: str = Field(min_length=1, max_length=128)
    parameter_id: str = Field(min_length=1, max_length=128)
    step: str = Field(min_length=1, max_length=128)
    minimum: str = Field(min_length=1, max_length=128)
    maximum: str = Field(min_length=1, max_length=128)


class ParameterNeighborhoodSettings(_ClosedModel):
    enabled: bool
    axes: list[ParameterNeighborhoodAxisSettings] = Field(max_length=4)
    maximum_score_drop_paise: int = Field(ge=0, le=2**63 - 1)
    minimum_stable_fraction_ppm: int = Field(ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _closed_work(self):
        if self.enabled:
            if not 1 <= len(self.axes) <= 4:
                raise ValueError("enabled parameter neighborhood requires one to four axes")
            keys = [(axis.node_id, axis.parameter_id) for axis in self.axes]
            if keys != sorted(set(keys)):
                raise ValueError("parameter neighborhood axes must be sorted and unique")
        elif self.axes or self.maximum_score_drop_paise or self.minimum_stable_fraction_ppm:
            raise ValueError("disabled parameter neighborhood cannot carry work")
        return self


class RobustnessSettings(_ClosedModel):
    stationary_bootstrap: StationaryBootstrapSettings | None = None
    parameter_neighborhood: ParameterNeighborhoodSettings | None = None

    @model_validator(mode="after")
    def _not_empty(self):
        if self.stationary_bootstrap is None and self.parameter_neighborhood is None:
            raise ValueError("robustness request is empty")
        return self


class V2RobustnessSettings(_ClosedModel):
    parameter_neighborhood: ParameterNeighborhoodSettings


class GraphExperimentRequest(_ClosedModel):
    program_name: str = Field(min_length=1, max_length=80)
    hypothesis_statement: str = Field(min_length=1, max_length=4000)
    datasets: list[CanonicalDatasetSelection | DatasetSelection] = Field(min_length=1, max_length=32)
    seed: int = Field(ge=0, le=2_147_483_647)
    gates: GateSettings
    cost_assumptions: CostAssumptions
    robustness: RobustnessSettings | None = None

    @model_validator(mode="after")
    def _coherent_datasets(self):
        canonical = [isinstance(dataset, CanonicalDatasetSelection) for dataset in self.datasets]
        if any(canonical):
            if not all(canonical) or len(self.datasets) > 8:
                raise ValueError("canonical selections cannot be mixed and are limited to eight")
            if len({dataset.as_of for dataset in self.datasets}) != 1:
                raise ValueError("canonical selections require one as_of")
            if len({dataset.manifest_address for dataset in self.datasets}) != len(self.datasets):
                raise ValueError("canonical manifests must be unique")
            return self
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


class V2GraphResearchOperationRequest(_ClosedModel):
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    admission_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dataset_manifest_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dataset_as_of: AwareDatetime
    hypothesis: str = Field(min_length=1, max_length=4000)
    research_capital: float = Field(gt=0.0, le=1_000_000_000.0)
    seed: int = Field(ge=0, le=2_147_483_647)
    min_trades: int = Field(ge=1, le=100_000)
    n_folds: int = Field(ge=2, le=32)
    min_positive_fold_frac: float = Field(ge=0.0, le=1.0)
    robustness: V2RobustnessSettings | None = None

    @model_validator(mode="after")
    def _canonical_request(self):
        if self.dataset_as_of.utcoffset() != dt.timedelta(0) \
                or self.dataset_as_of.microsecond:
            raise ValueError("dataset_as_of must be a whole UTC second")
        if not self.hypothesis.strip():
            raise ValueError("hypothesis must not be blank")
        return self


class V2GraphResearchPreparationRequest(_ClosedModel):
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    dataset_manifest_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dataset_as_of: AwareDatetime
    hypothesis: str = Field(min_length=1, max_length=4000)
    research_capital: float = Field(gt=0.0, le=1_000_000_000.0)
    seed: int = Field(ge=0, le=2_147_483_647)
    min_trades: int = Field(ge=1, le=100_000)
    n_folds: int = Field(ge=2, le=32)
    min_positive_fold_frac: float = Field(ge=0.0, le=1.0)
    risk_policy: Literal["none", "pine-v4-ratchet/1"] = "none"

    @model_validator(mode="after")
    def _canonical_request(self):
        if self.dataset_as_of.utcoffset() != dt.timedelta(0) \
                or self.dataset_as_of.microsecond:
            raise ValueError("dataset_as_of must be a whole UTC second")
        if not self.hypothesis.strip():
            raise ValueError("hypothesis must not be blank")
        return self


class V2GraphResearchOperationReceipt(_ClosedModel):
    request_id: str
    operation_id: str
    status: str
    status_url: str
    cancel_url: str


EvidenceState = Literal[
    "verified", "legacy_unbound", "corrupt", "pending", "running"
]


class V2SettingsResearchPreparationRequest(_ClosedModel):
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    dataset_manifest_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dataset_as_of: AwareDatetime
    hypothesis: str = Field(min_length=1, max_length=4000)
    expected_workspace_revision: int = Field(strict=True, ge=0, le=2_147_483_646)
    expected_strategy_revision: int = Field(strict=True, ge=0, le=2_147_483_646)
    run_overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _canonical_request(self):
        return V2GraphResearchPreparationRequest._canonical_request(self)


class V2InputDatasetSelection(_ClosedModel):
    graph_input_id: str = Field(min_length=1, max_length=128)
    dataset_manifest_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class V2InputSetResearchPreparationRequest(_ClosedModel):
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    input_datasets: list[V2InputDatasetSelection] = Field(min_length=2, max_length=8)
    primary_input: str = Field(min_length=1, max_length=128)
    dataset_as_of: AwareDatetime
    hypothesis: str = Field(min_length=1, max_length=4000)
    expected_workspace_revision: int = Field(strict=True, ge=0, le=2_147_483_646)
    expected_strategy_revision: int = Field(strict=True, ge=0, le=2_147_483_646)
    run_overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _canonical_request(self):
        V2GraphResearchPreparationRequest._canonical_request(self)
        inputs = {item.graph_input_id for item in self.input_datasets}
        manifests = {item.dataset_manifest_address for item in self.input_datasets}
        if len(inputs) != len(self.input_datasets) or len(manifests) != len(inputs):
            raise ValueError("Choose one distinct dataset for every strategy input.")
        if self.primary_input not in inputs:
            raise ValueError("Choose the strategy input used for simulated fills.")
        return self


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


class VersionComparisonSelection(_ClosedModel):
    format_version: Literal[1, 2] = 1
    graph_identifier: str = Field(min_length=1, max_length=128)
    graph_version: int = Field(ge=1)
    run_id: int | None = Field(default=None, ge=1)


class VersionComparisonRequest(_ClosedModel):
    left: VersionComparisonSelection
    right: VersionComparisonSelection

    @model_validator(mode="after")
    def _paired_run_selection(self):
        if (self.left.run_id is None) != (self.right.run_id is None):
            raise ValueError("comparison run ids must be selected as a pair")
        return self


class VerifiedComparisonSelection(_ClosedModel):
    project_id: str
    graph_identifier: str
    graph_version: int
    content_address: str
    run_id: int | None


class VersionComparisonResponse(GraphComparisonResponse):
    left: VerifiedComparisonSelection
    right: VerifiedComparisonSelection


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


class FindingRequest(_ClosedModel):
    statement: str = Field(min_length=1, max_length=4000)
    polarity: Literal["positive", "negative"]

    @model_validator(mode="after")
    def _meaningful_statement(self):
        if not self.statement.strip():
            raise ValueError("finding statement must not be blank")
        return self


class FindingRevisionRequest(FindingRequest):
    expected_superseded_by: Literal[None]


class FindingResponse(_ClosedModel):
    finding_id: int
    statement: str
    polarity: Literal["positive", "negative"]
    confidence: float
    evidence_run_id: int
    superseded_by: int | None
    status: Literal["active", "superseded"]
    created_at: str | None
    binding: dict


class FindingListResponse(_ClosedModel):
    findings: list[FindingResponse]


class FindingRevisionResponse(_ClosedModel):
    superseded: FindingResponse
    successor: FindingResponse


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
    "/projects/{project_id}/graphs/{identifier}/versions/{version}/research-operations",
    response_model=V2GraphResearchOperationReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_v2_graph_research_operation(
    project_id: str, identifier: str, version: int,
    body: V2GraphResearchOperationRequest,
    principal: Principal = Depends(get_principal),
) -> V2GraphResearchOperationReceipt:
    """Persist one exact saved-V2 operation before canonical object-byte load."""
    from app.core import strategy_admissions

    owner_id = owner_id_for(principal)
    if version < 1:
        raise _error(422, "V2_OPERATION_INVALID", "graph version is invalid")
    try:
        saved = v2_editor_store.read_version(
            project_id, identifier, version, owner_id=owner_id,
        )
    except v2_editor_store.EditorNotFound as exc:
        raise _error(404, "V2_GRAPH_NOT_FOUND", "saved V2 graph not found") from exc
    except V2GraphVerificationError as exc:
        raise _error(409, "V2_GRAPH_CORRUPT", "saved V2 graph is corrupt") from exc

    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        ResearchSession = make_sessionmaker(engine)
        with SessionLocal() as execution_session, ResearchSession() as research_session:
            try:
                admission = strategy_admissions.load_phase4_descriptor(
                    execution_session, owner_id=owner_id,
                    admission_address=body.admission_address,
                )
                phase4 = admission["phase4_data_binding"]
                base = admission["base_v2_admission"]
                if not all((
                    phase4["mode"] == "RESEARCH",
                    phase4["owner_id"] == owner_id,
                    phase4["dataset_manifest_address"] == body.dataset_manifest_address,
                    saved["format_version"] == 2,
                    saved["graph_identifier"] == admission["graph_identifier"] == identifier,
                    saved["graph_version"] == admission["graph_version"] == version,
                    saved["content_address"] == admission["content_address"],
                    saved["graph_address"] == admission["graph_address"],
                    saved["registry_snapshot_address"] == phase4["registry_snapshot_address"],
                    canonical_json(saved["document"]) == canonical_json(
                        base["document"]),
                )):
                    raise V2OperationRefusal(
                        "V2_AUTHORITY_MISMATCH", "saved V2 authority differs",
                    )
                item = {
                    "request_id": body.request_id, "project_id": project_id,
                    "graph_identifier": identifier, "graph_version": version,
                    "content_address": saved["content_address"],
                    "graph_address": saved["graph_address"],
                    "admission_address": body.admission_address,
                    "dataset_manifest_address": body.dataset_manifest_address,
                    "dataset_as_of": body.dataset_as_of.isoformat(),
                    "phase4_binding": phase4,
                    "experiment": {
                        "hypothesis": body.hypothesis,
                        "research_capital": body.research_capital,
                        "seed": body.seed, "min_trades": body.min_trades,
                        "n_folds": body.n_folds,
                        "min_positive_fold_frac": body.min_positive_fold_frac,
                    },
                }
                if body.robustness is not None:
                    item["robustness"] = body.robustness.model_dump()
                plan = build_v2_operation_plan(item)
                operation_id = operation_id_for_request(
                    owner_id=owner_id, request_id=body.request_id,
                )
                operation = ResearchOperationRepository(research_session).enqueue(
                    owner_id=owner_id, trigger="v2_graph", plan=plan,
                    build=get_build_sha(), provider_mode=V2_PROVIDER_MODE,
                    operation_id=operation_id,
                )
            except strategy_admissions.AdmissionPersistenceError as exc:
                raise _error(404, "V2_GRAPH_NOT_FOUND", "saved V2 graph not found") from exc
            except V2OperationRefusal as exc:
                raise _error(
                    409 if exc.code in {"REQUEST_ID_REUSED", "STRATEGY_LIBRARY_CHANGED"} else 422,
                    exc.code, str(exc),
                ) from exc
            except ValueError as exc:
                raise _error(422, "V2_OPERATION_INVALID", "V2 operation refused") from exc
    finally:
        engine.dispose()
    status_url = f"/api/research/operations/{operation.operation_id}"
    return V2GraphResearchOperationReceipt(
        request_id=body.request_id, operation_id=operation.operation_id,
        status=operation.status, status_url=status_url,
        cancel_url=status_url + "/cancel",
    )


def _preflight_preparation_library(saved, body, owner_id):
    from research.orchestrator.v2_preparation import require_current_strategy_library
    try:
        require_current_strategy_library(saved)
    except V2OperationRefusal:
        # An existing request keeps its immutable plan and ordinary exact-retry check.
        if _existing_preparation(owner_id, body.request_id) is None:
            raise


def _preparation_plan(saved, body, *, owner_id, project_id, identifier, version):
    from research.orchestrator.v2_preparation import build_preparation_plan, execution_policy
    experiment = body.model_dump(exclude={"request_id", "dataset_manifest_address", "dataset_as_of", "risk_policy"})
    return build_preparation_plan({
        "owner_id": owner_id, "project_id": project_id, "graph_identifier": identifier,
        "graph_version": version, "content_address": saved["content_address"],
        "graph_address": saved["graph_address"], "registry_snapshot_address": saved["registry_snapshot_address"],
        "dataset_manifest_address": body.dataset_manifest_address,
        "dataset_as_of": body.dataset_as_of.isoformat(), "request_id": body.request_id,
        "experiment": experiment, "execution_policy": execution_policy(body.research_capital, body.risk_policy),
    })


def _enqueue_preparation(plan, body, owner_id):
    from research.domain.models import ResearchDatasetManifestV2
    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        with make_sessionmaker(engine)() as session:
            for address in _preparation_manifest_addresses(body):
                row = session.get(ResearchDatasetManifestV2, (owner_id, address))
                if row is None or row.authority_state != "VERIFIED_V2":
                    raise _error(404, "V2_DATASET_NOT_FOUND", "Choose a verified dataset owned by this workspace for every input.")
            return ResearchOperationRepository(session).enqueue(owner_id=owner_id, trigger="v2_graph", plan=plan,
                build=get_build_sha(), provider_mode=V2_PROVIDER_MODE,
                operation_id=operation_id_for_request(owner_id=owner_id, request_id=body.request_id))
    finally:
        engine.dispose()


def _preparation_manifest_addresses(body):
    if isinstance(body, V2InputSetResearchPreparationRequest):
        return [item.dataset_manifest_address for item in body.input_datasets]
    return [body.dataset_manifest_address]


@router.post(
    "/projects/{project_id}/graphs/{identifier}/versions/{version}/research-preparations",
    response_model=V2GraphResearchOperationReceipt, status_code=status.HTTP_202_ACCEPTED,
)
def post_v2_graph_research_preparation(
    project_id: str, identifier: str, version: int, body: V2GraphResearchPreparationRequest,
    principal: Principal = Depends(get_principal),
) -> V2GraphResearchOperationReceipt:
    """Queue real evidence production; no client-supplied admission is accepted."""
    owner_id = owner_id_for(principal)
    try:
        saved = v2_editor_store.read_version(project_id, identifier, version, owner_id=owner_id)
        _preflight_preparation_library(saved, body, owner_id)
        plan = _preparation_plan(saved, body, owner_id=owner_id, project_id=project_id,
                                 identifier=identifier, version=version)
        operation = _enqueue_preparation(plan, body, owner_id)
    except v2_editor_store.EditorNotFound as exc:
        raise _error(404, "V2_GRAPH_NOT_FOUND", "Choose a saved strategy owned by this workspace.") from exc
    except V2GraphVerificationError as exc:
        raise _error(409, "V2_GRAPH_CORRUPT", "The saved strategy could not be verified. Save a new version.") from exc
    except V2OperationRefusal as exc:
        raise _error(409 if exc.code in {"REQUEST_ID_REUSED", "STRATEGY_LIBRARY_CHANGED"} else 422, exc.code, str(exc)) from exc
    status_url = f"/api/research/operations/{operation.operation_id}"
    return V2GraphResearchOperationReceipt(request_id=body.request_id, operation_id=operation.operation_id,
        status=operation.status, status_url=status_url, cancel_url=status_url + "/cancel")


def _existing_preparation(owner_id, request_id):
    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        with make_sessionmaker(engine)() as session:
            return ResearchOperationRepository(session).get(
                operation_id_for_request(owner_id=owner_id, request_id=request_id), owner_id=owner_id)
    finally:
        engine.dispose()


def _check_canonical_search(saved, request):
    if request is None or not request["enabled"]:
        return
    from app.ir.library import REGISTRY
    from research.pipeline.v2_parameter_search import prepare_canonical_search
    try:
        prepare_canonical_search(request, document=saved["document"], registry=REGISTRY)
    except ValueError as exc:
        raise V2OperationRefusal("V2_PARAMETER_SEARCH_INVALID", str(exc)) from exc


def _pinned_preparation_fields(saved, body, snapshot, *, owner_id, project_id, identifier, version):
    from research.orchestrator.v2_preparation import execution_policy
    values = dict(snapshot["values"])
    values.pop("optimization", None)
    risk = values.pop("risk_policy")
    bands = {key: values.pop(key, 0.0) for key in ("stop_loss_pct", "take_profit_pct")}
    return {
        "owner_id": owner_id, "project_id": project_id, "graph_identifier": identifier,
        "graph_version": version, "content_address": saved["content_address"],
        "graph_address": saved["graph_address"], "registry_snapshot_address": saved["registry_snapshot_address"],
        "dataset_as_of": body.dataset_as_of.isoformat(), "request_id": body.request_id,
        "experiment": {**values, "hypothesis": body.hypothesis}, "settings_snapshot": snapshot,
        "execution_policy": execution_policy(values["research_capital"], risk, **bands),
    }


def _settings_preparation_plan(saved, body, snapshot, *, owner_id, project_id, identifier, version):
    from research.orchestrator.v2_preparation import build_settings_preparation_plan
    return build_settings_preparation_plan({
        **_pinned_preparation_fields(saved, body, snapshot, owner_id=owner_id,
                                    project_id=project_id, identifier=identifier, version=version),
        "dataset_manifest_address": body.dataset_manifest_address,
    })


def _input_set_preparation_plan(saved, body, snapshot, *, owner_id, project_id, identifier, version):
    from research.orchestrator.v2_preparation import build_input_set_preparation_plan
    inputs = {port["port_id"] for port in saved["document"]["graph_inputs"]}
    if inputs != {item.graph_input_id for item in body.input_datasets}:
        raise V2OperationRefusal("V2_PREPARATION_INVALID",
                                 "Choose one dataset for every input in this saved strategy.")
    return build_input_set_preparation_plan({
        **_pinned_preparation_fields(saved, body, snapshot, owner_id=owner_id,
                                    project_id=project_id, identifier=identifier, version=version),
        "input_datasets": [item.model_dump() for item in sorted(body.input_datasets, key=lambda item: item.graph_input_id)],
        "primary_input": body.primary_input,
    })


def _preparation_settings_snapshot(repository, existing, body, owner_id, identifier):
    from research.domain.settings import validate_snapshot, validate_values
    if existing is None:
        return repository.snapshot(owner_id=owner_id, graph_identifier=identifier,
            workspace_revision=body.expected_workspace_revision, strategy_revision=body.expected_strategy_revision,
            run_overrides=body.run_overrides)
    from research.orchestrator.v2_preparation import parse_public_preparation_plan
    item = parse_public_preparation_plan(existing.plan)["v2_graphs"][0]
    snapshot = validate_snapshot(item.get("settings_snapshot"), owner_id=owner_id, graph_identifier=identifier)
    intent = validate_values(body.run_overrides, sparse=True, schema=snapshot["schema"])
    expected = (body.expected_workspace_revision, body.expected_strategy_revision, intent)
    pinned = (snapshot["workspace"]["revision"], snapshot["strategy"]["revision"], snapshot["run_overrides"])
    if expected != pinned:
        raise V2OperationRefusal("REQUEST_ID_REUSED", "This request ID was already used with different settings.")
    return snapshot


def _queue_settings_preparation(saved, body, *, owner_id, project_id, identifier, version):
    from research.domain.settings import ResearchSettingsRepository
    with SessionLocal() as session:
        repository = ResearchSettingsRepository(session)
        repository.lock_owner(owner_id)
        existing = _existing_preparation(owner_id, body.request_id)
        if existing is None:
            from research.orchestrator.v2_preparation import require_current_strategy_library
            require_current_strategy_library(saved)
        snapshot = _preparation_settings_snapshot(repository, existing, body, owner_id, identifier)
        if existing is None:
            _check_canonical_search(saved, snapshot["values"].get("optimization"))
        builder = (_input_set_preparation_plan if isinstance(body, V2InputSetResearchPreparationRequest)
                   else _settings_preparation_plan)
        plan = builder(saved, body, snapshot, owner_id=owner_id,
                       project_id=project_id, identifier=identifier, version=version)
        return _enqueue_preparation(plan, body, owner_id)


@router.post(
    "/projects/{project_id}/graphs/{identifier}/versions/{version}/research-preparations/from-settings",
    response_model=V2GraphResearchOperationReceipt, status_code=status.HTTP_202_ACCEPTED,
)
def post_v2_settings_research_preparation(
    project_id: str, identifier: str, version: int, body: V2SettingsResearchPreparationRequest,
    principal: Principal = Depends(get_principal),
) -> V2GraphResearchOperationReceipt:
    from research.domain.settings import SettingsConflict
    owner_id = owner_id_for(principal)
    try:
        saved = v2_editor_store.read_version(project_id, identifier, version, owner_id=owner_id)
        operation = _queue_settings_preparation(saved, body, owner_id=owner_id,
                                                project_id=project_id, identifier=identifier, version=version)
    except v2_editor_store.EditorNotFound as exc:
        raise _error(404, "V2_GRAPH_NOT_FOUND", "Choose a saved strategy owned by this workspace.") from exc
    except SettingsConflict as exc:
        raise _error(409, "RESEARCH_SETTINGS_CONFLICT", str(exc)) from exc
    except V2GraphVerificationError as exc:
        raise _error(409, "V2_GRAPH_CORRUPT", "The saved strategy could not be verified. Save a new version.") from exc
    except V2OperationRefusal as exc:
        raise _error(409 if exc.code in {"REQUEST_ID_REUSED", "STRATEGY_LIBRARY_CHANGED"} else 422, exc.code, str(exc)) from exc
    except ValueError as exc:
        raise _error(422, "RESEARCH_SETTINGS_INVALID", "Use supported research settings within their bounds.") from exc
    status_url = f"/api/research/operations/{operation.operation_id}"
    return V2GraphResearchOperationReceipt(request_id=body.request_id, operation_id=operation.operation_id,
        status=operation.status, status_url=status_url, cancel_url=status_url + "/cancel")


@router.post(
    "/projects/{project_id}/graphs/{identifier}/versions/{version}/research-preparations/from-inputs",
    response_model=V2GraphResearchOperationReceipt, status_code=status.HTTP_202_ACCEPTED,
)
def post_v2_input_set_research_preparation(
    project_id: str, identifier: str, version: int, body: V2InputSetResearchPreparationRequest,
    principal: Principal = Depends(get_principal),
) -> V2GraphResearchOperationReceipt:
    return post_v2_settings_research_preparation(project_id, identifier, version, body, principal)


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
    principal: Principal = Depends(get_principal),
) -> GraphExperimentResponse:
    canonical = isinstance(body.datasets[0], CanonicalDatasetSelection)
    if not canonical and is_v0_profile(get_settings().release_profile):
        raise _error(422, "EXPERIMENT_CANONICAL_DATASET_REQUIRED",
                     "V0 research requires a persisted canonical manifest selection")
    if version < 1:
        raise _error(
            422,
            "EXPERIMENT_VERSION_INVALID",
            "graph version must be greater than zero",
        )
    try:
        published = store.load_owned_version_for_experiment(
            project_id, identifier, version, owner_id=owner_id_for(principal)
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

    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            try:
                enqueue_graph_admission(
                    session, owner_id=owner_id_for(principal), graph=published.graph,
                    graph_content_address=published.content_address,
                    admission_address=published.admission_address,
                    persist=not canonical,
                )
            except GraphAdmissionRejected as exc:
                session.rollback()
                raise _error(422, exc.code, "causal admission refused") from exc
            datasets = []
            if canonical:
                try:
                    with SessionLocal() as execution_session:
                        datasets = load_canonical_datasets(
                            session, execution_session=execution_session,
                            owner_id=owner_id_for(principal), selections=body.datasets,
                        )
                except CanonicalDatasetRefused as exc:
                    session.rollback()
                    raise _error(422, exc.code, str(exc)) from exc
                # Resolve and bind the supported graph/data subset without writes.
                # Only after every check passes may the existing mirror be copied.
                try:
                    build_graph_provenance(project_id=project_id, graph=published.graph,
                        declared_content_address=published.content_address, datasets=datasets)
                    enqueue_graph_admission(session, owner_id=owner_id_for(principal),
                        graph=published.graph, graph_content_address=published.content_address,
                        admission_address=published.admission_address)
                except (GraphBindingRejected, GraphAdmissionRejected) as exc:
                    session.rollback()
                    raise _error(422, getattr(exc, "code", "EXPERIMENT_GRAPH_BINDING_INVALID"), str(exc)) from exc
            for selection in (() if canonical else body.datasets):
                try:
                    instrument = get_instrument(selection.instrument_key)
                except KeyError as exc:
                    raise _error(
                        422, "EXPERIMENT_DATASET_INVALID",
                        f"unknown instrument {selection.instrument_key!r}",
                    ) from exc
                dataset = materialize(
                    local_execution_cell(request, principal).provider,
                    instrument, selection.interval, selection.days,
                )
                if dataset.bar_count == 0:
                    raise _error(
                        422, "EXPERIMENT_DATASET_EMPTY",
                        f"dataset {selection.instrument_key!r} contains no bars",
                    )
                datasets.append((instrument, dataset))
            try:
                report = run_published_graph_experiment(
                    session,
                    owner_id=owner_id_for(principal),
                    project_id=project_id,
                    graph=published.graph,
                    declared_content_address=published.content_address,
                    admission_address=published.admission_address,
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
                    robustness=(
                        body.robustness.stationary_bootstrap.model_dump()
                        if body.robustness is not None
                        and body.robustness.stationary_bootstrap is not None else None
                    ),
                    parameter_neighborhood=(
                        body.robustness.parameter_neighborhood.model_dump()
                        if body.robustness is not None
                        and body.robustness.parameter_neighborhood is not None else None
                    ),
                )
            except (GraphBindingRejected, GraphAdmissionRejected) as exc:
                session.rollback()
                raise _error(
                    422, getattr(exc, "code", "EXPERIMENT_GRAPH_BINDING_INVALID"), str(exc)
                ) from exc
            spec = session.get(ExperimentSpec, (owner_id_for(principal), report["spec_id"]))
            recipe = json.loads(spec.recipe_json)
            provenance = recipe["graph_provenance"]
            binding = {
                **provenance,
                "datasets": recipe["datasets"],
                "cost_assumptions": recipe["cost_assumptions"],
                "gates": recipe["gates"],
            }
            if "robustness" in recipe:
                binding["robustness"] = recipe["robustness"]
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
def get_graph_experiments(
    project_id: str, principal: Principal = Depends(get_principal)
) -> GraphRunListResponse:
    return GraphRunListResponse(runs=research_read.list_graph_runs(
        project_id, owner_id=owner_id_for(principal)))


@router.post(
    "/projects/{project_id}/experiments/comparisons",
    response_model=GraphComparisonResponse,
)
def post_graph_experiment_comparison(
    project_id: str, body: GraphComparisonRequest,
    principal: Principal = Depends(get_principal),
) -> GraphComparisonResponse:
    try:
        owner_id = owner_id_for(principal)
        left = research_read.get_graph_run(project_id, body.left_run_id, owner_id=owner_id)
        right = research_read.get_graph_run(project_id, body.right_run_id, owner_id=owner_id)
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


@dataclass(frozen=True)
class _LoadedComparisonGraph:
    format_version: int
    identifier: str
    version: int
    content_address: str
    graph: dict[str, Any]


def _load_comparison_graph(
    project_id: str, selection: VersionComparisonSelection, *, owner_id: str
) -> _LoadedComparisonGraph:
    if selection.format_version == 2:
        try:
            row = v2_editor_store.read_version(
                project_id, selection.graph_identifier, selection.graph_version,
                owner_id=owner_id,
            )
        except v2_editor_store.EditorNotFound as exc:
            raise _error(
                404, "EXPERIMENT_GRAPH_VERSION_NOT_FOUND", "graph version not found",
            ) from exc
        except V2GraphVerificationError as exc:
            raise _error(
                409, "GRAPH_VERSION_CORRUPT",
                "persisted graph version failed integrity verification",
            ) from exc
        return _LoadedComparisonGraph(
            format_version=2,
            identifier=row["graph_identifier"],
            version=row["graph_version"],
            content_address=row["content_address"],
            graph=row["document"],
        )
    try:
        row = store.load_version(
            project_id, selection.graph_identifier, selection.graph_version, owner_id=owner_id
        )
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _error(
            404, "EXPERIMENT_GRAPH_VERSION_NOT_FOUND", "graph version not found",
        ) from exc
    except store.GraphVersionCorrupt as exc:
        raise _error(
            409, "GRAPH_VERSION_CORRUPT",
            "persisted graph version failed integrity verification",
        ) from exc
    return _LoadedComparisonGraph(
        format_version=1, identifier=row.identifier, version=row.version,
        content_address=row.content_address, graph=row.graph,
    )


def _compare_loaded_graphs(
    left: _LoadedComparisonGraph, right: _LoadedComparisonGraph,
) -> dict[str, Any]:
    if left.format_version == right.format_version == 1:
        return compare_graph_versions(
            {"graph": left.graph, "content_address": left.content_address},
            {"graph": right.graph, "content_address": right.content_address},
        )
    if left.format_version != right.format_version:
        return {
            "equivalent": False,
            "incomparable": ["GRAPH_FORMAT_CHANGED"],
            "differences": [{
                "dimension": "identity", "path": ["format_version"],
                "left": left.format_version, "right": right.format_version,
            }],
        }
    equivalent = (
        left.content_address == right.content_address
        and canonical_json(left.graph) == canonical_json(right.graph)
    )
    return {
        "equivalent": equivalent,
        "incomparable": ([] if equivalent else ["GRAPH_IDENTITY_CHANGED"]),
        "differences": ([] if equivalent else [{
            "dimension": "identity", "path": ["content_address"],
            "left": left.content_address, "right": right.content_address,
        }]),
    }


def _comparison_run(
    project_id: str,
    selection: VersionComparisonSelection,
    published,
    *,
    owner_id: str,
):
    if selection.run_id is None:
        return None
    try:
        run = research_read.get_graph_run(project_id, selection.run_id, owner_id=owner_id)
    except research_read.StoredEvidenceCorrupt as exc:
        raise _error(
            409,
            "EXPERIMENT_EVIDENCE_CORRUPT",
            "persisted experiment evidence failed integrity verification",
        ) from exc
    if run is None:
        raise _error(404, "EXPERIMENT_RUN_NOT_FOUND", "experiment run not found")
    if run["evidence_state"] != "verified" or run["evidence"] is None:
        raise _error(
            409,
            "EXPERIMENT_EVIDENCE_UNAVAILABLE",
            "verified terminal evidence is unavailable for comparison",
        )
    expected = {
        "project_id": project_id,
        "identifier": published.identifier,
        "version": published.version,
        "content_address": published.content_address,
    }
    evidence_provenance = run["evidence"].get("provenance")
    evidence_graph = (
        evidence_provenance.get("graph_provenance", {}).get("graph")
        if isinstance(evidence_provenance, dict) else None
    )
    if run["graph"] != expected or evidence_graph != expected:
        raise _error(
            409,
            "EXPERIMENT_GRAPH_BINDING_MISMATCH",
            "experiment run is not bound to the selected graph version",
        )
    return run


@router.post(
    "/projects/{project_id}/version-comparisons",
    response_model=VersionComparisonResponse,
)
def post_version_comparison(
    project_id: str,
    body: VersionComparisonRequest,
    principal: Principal = Depends(get_principal),
) -> VersionComparisonResponse:
    owner_id = owner_id_for(principal)
    left_graph = _load_comparison_graph(project_id, body.left, owner_id=owner_id)
    right_graph = _load_comparison_graph(project_id, body.right, owner_id=owner_id)
    try:
        graph_result = _compare_loaded_graphs(left_graph, right_graph)
    except GraphComparisonRejected as exc:
        raise _error(409, "GRAPH_VERSION_CORRUPT", str(exc)) from exc

    left_run = _comparison_run(project_id, body.left, left_graph, owner_id=owner_id)
    right_run = _comparison_run(project_id, body.right, right_graph, owner_id=owner_id)
    differences = list(graph_result["differences"])
    incomparable = list(graph_result["incomparable"])
    if left_run is not None and right_run is not None:
        evidence_result = compare_experiment_evidence(
            left_run["evidence"], right_run["evidence"]
        )
        differences.extend(evidence_result["differences"])
        incomparable.extend(evidence_result["incomparable"])
    differences.sort(key=lambda item: (item["dimension"], repr(item["path"])))
    incomparable = list(dict.fromkeys(incomparable))

    def verified(selection, published):
        return VerifiedComparisonSelection(
            project_id=project_id,
            graph_identifier=published.identifier,
            graph_version=published.version,
            content_address=published.content_address,
            run_id=selection.run_id,
        )

    return VersionComparisonResponse(
        left=verified(body.left, left_graph),
        right=verified(body.right, right_graph),
        equivalent=not differences,
        incomparable=incomparable,
        differences=differences,
    )


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}/decisions",
    response_model=CandidateDecisionResponse,
)
def post_candidate_decision(
    project_id: str, candidate_id: int, body: CandidateDecisionRequest,
    principal: Principal = Depends(get_principal),
) -> CandidateDecisionResponse:
    try:
        result = research_read.decide_project_candidate(
            project_id,
            candidate_id,
            owner_id=owner_id_for(principal),
            expected_status=body.expected_status,
            decision=body.decision,
            reason=body.reason.strip(),
            actor_id=(principal.user_id if principal.kind == "user" else "owner"),
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


def _finding_failure(exc: Exception) -> None:
    if isinstance(exc, research_read.StoredEvidenceCorrupt):
        raise _error(
            409,
            "FINDING_EVIDENCE_CORRUPT",
            "persisted finding evidence failed integrity verification",
        ) from exc
    if isinstance(exc, research_read.FindingEvidenceUnavailable):
        raise _error(
            409,
            "FINDING_EVIDENCE_UNAVAILABLE",
            "finding requires a completed run with verified terminal evidence",
        ) from exc
    raise exc


@router.get(
    "/projects/{project_id}/findings",
    response_model=FindingListResponse,
)
def get_findings(project_id: str, principal: Principal = Depends(get_principal)) -> FindingListResponse:
    try:
        findings = research_read.list_project_findings(project_id, owner_id=owner_id_for(principal))
    except (research_read.StoredEvidenceCorrupt,
            research_read.FindingEvidenceUnavailable) as exc:
        _finding_failure(exc)
    return FindingListResponse(findings=findings)


@router.get(
    "/projects/{project_id}/findings/{finding_id}",
    response_model=FindingResponse,
)
def get_finding(project_id: str, finding_id: int, principal: Principal = Depends(get_principal)) -> FindingResponse:
    try:
        finding = research_read.get_project_finding(project_id, finding_id, owner_id=owner_id_for(principal))
    except (research_read.StoredEvidenceCorrupt,
            research_read.FindingEvidenceUnavailable) as exc:
        _finding_failure(exc)
    if finding is None:
        raise _error(404, "FINDING_NOT_FOUND", "finding not found")
    return FindingResponse(**finding)


@router.post(
    "/projects/{project_id}/experiments/{run_id}/findings",
    response_model=FindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_finding(
    project_id: str, run_id: int, body: FindingRequest,
    principal: Principal = Depends(get_principal),
) -> FindingResponse:
    try:
        finding = research_read.create_project_finding(
            project_id,
            run_id,
            owner_id=owner_id_for(principal),
            statement=body.statement.strip(),
            polarity=body.polarity,
        )
    except (research_read.StoredEvidenceCorrupt,
            research_read.FindingEvidenceUnavailable) as exc:
        _finding_failure(exc)
    if finding is None:
        raise _error(404, "FINDING_RUN_NOT_FOUND", "experiment run not found")
    return FindingResponse(**finding)


@router.post(
    "/projects/{project_id}/findings/{finding_id}/revisions",
    response_model=FindingRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_finding_revision(
    project_id: str, finding_id: int, body: FindingRevisionRequest,
    principal: Principal = Depends(get_principal),
) -> FindingRevisionResponse:
    try:
        revision = research_read.revise_project_finding(
            project_id,
            finding_id,
            owner_id=owner_id_for(principal),
            statement=body.statement.strip(),
            polarity=body.polarity,
        )
    except research_read.FindingRevisionConflict as exc:
        raise _error(
            409,
            "FINDING_REVISION_CONFLICT",
            "finding was already superseded",
        ) from exc
    except (research_read.StoredEvidenceCorrupt,
            research_read.FindingEvidenceUnavailable) as exc:
        _finding_failure(exc)
    if revision is None:
        raise _error(404, "FINDING_NOT_FOUND", "finding not found")
    return FindingRevisionResponse(**revision)


@router.get(
    "/projects/{project_id}/experiments/{run_id}",
    response_model=GraphRunDetail,
)
def get_graph_experiment(
    project_id: str, run_id: int, principal: Principal = Depends(get_principal)
) -> GraphRunDetail:
    try:
        run = research_read.get_graph_run(project_id, run_id, owner_id=owner_id_for(principal))
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
