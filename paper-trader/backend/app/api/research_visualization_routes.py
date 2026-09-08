"""Closed read API for persisted terminal research visualization evidence."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.principal import Principal, get_principal, owner_id_for
from app.core import research_read
from app.core.research_visualization_read import VisualizationRejected, page_projection
from app.ir.hashing import content_address
from research.robustness.integration import (
    NOT_REQUESTED,
    PROJECTION_SCHEMA,
    RobustnessEvidenceRejected,
    reconstruct_robustness_projection,
    stationary_bootstrap_request_enabled,
)
from research.robustness.parameter_integration import (
    PROJECTION_SCHEMA as PARAMETER_PROJECTION_SCHEMA,
    ParameterNeighborhoodIntegrationRejected,
    parameter_neighborhood_binding_from_provenance,
    reconstruct_parameter_neighborhood_projection,
)


router = APIRouter(prefix="/api/ir")


@router.get("/projects/{project_id}/experiments/{run_id}/visualization")
def get_research_visualization(
    project_id: str,
    run_id: int,
    trade_after: int = Query(default=0, ge=0),
    trade_limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_principal),
) -> dict:
    try:
        run = research_read.get_graph_run(
            project_id, run_id, owner_id=owner_id_for(principal))
    except research_read.StoredEvidenceCorrupt as exc:
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_EVIDENCE_CORRUPT",
            "message": "Persisted experiment evidence failed integrity verification",
        }) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="experiment run not found")
    if run["evidence_state"] in {"pending", "running"}:
        return {
            "schema": "strategy-os-backtest-visualization/1",
            "state": "PENDING",
            "run_id": run_id,
            "spec_id": run["spec_id"],
            "status": run["status"],
        }
    if run["evidence_state"] != "verified" or run.get("evidence") is None:
        return {
            "schema": "strategy-os-backtest-visualization/1",
            "state": "UNAVAILABLE",
            "run_id": run_id,
            "spec_id": run["spec_id"],
            "reason_code": "LEGACY_TERMINAL_EVIDENCE_UNAVAILABLE",
        }
    evidence = run["evidence"]
    projection = evidence.get("results", {}).get("visualization")
    if projection is None:
        return {
            "schema": "strategy-os-backtest-visualization/1",
            "state": "UNAVAILABLE",
            "run_id": run_id,
            "spec_id": run["spec_id"],
            "reason_code": "LEGACY_VISUALIZATION_UNAVAILABLE",
        }
    try:
        result = page_projection(
            projection,
            trade_after=trade_after,
            trade_limit=trade_limit,
            terminal_evidence_address=content_address(evidence),
        )
    except (VisualizationRejected, TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_VISUALIZATION_CORRUPT",
            "message": "Persisted visualization failed integrity verification",
        }) from exc
    result.setdefault("run_id", run_id)
    result.setdefault("spec_id", run["spec_id"])
    return result


@router.get("/projects/{project_id}/experiments/{run_id}/robustness")
def get_research_robustness(
    project_id: str,
    run_id: int,
    response: Response,
    principal: Principal = Depends(get_principal),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    try:
        run = research_read.get_graph_run(
            project_id, run_id, owner_id=owner_id_for(principal))
    except research_read.StoredEvidenceCorrupt as exc:
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_EVIDENCE_CORRUPT",
            "message": "Persisted experiment evidence failed integrity verification",
        }, headers={"Cache-Control": "no-store"}) from exc
    if run is None:
        raise HTTPException(
            status_code=404, detail="experiment run not found",
            headers={"Cache-Control": "no-store"},
        )
    if run["evidence_state"] in {"pending", "running"}:
        return {
            "schema": PROJECTION_SCHEMA,
            "state": "UNAVAILABLE",
            "reason_code": "RUN_NOT_TERMINAL",
        }
    if run["evidence_state"] != "verified" or run.get("evidence") is None:
        return {
            "schema": PROJECTION_SCHEMA,
            "state": "UNAVAILABLE",
            "reason_code": "LEGACY_TERMINAL_EVIDENCE_UNAVAILABLE",
        }
    stored = run["evidence"].get("results", {}).get("robustness")
    if stored is None:
        recipe_binding = run["evidence"].get("provenance", {}).get("robustness")
        try:
            requested = stationary_bootstrap_request_enabled(recipe_binding)
        except RobustnessEvidenceRejected as exc:
            raise HTTPException(status_code=409, detail={
                "code": "EXPERIMENT_ROBUSTNESS_CORRUPT",
                "message": "Persisted robustness evidence failed semantic reconstruction",
            }, headers={"Cache-Control": "no-store"}) from exc
        if not requested:
            return {"schema": PROJECTION_SCHEMA, "state": NOT_REQUESTED}
        if run["status"] == "failed":
            return {
                "schema": PROJECTION_SCHEMA,
                "state": "UNAVAILABLE",
                "reason_code": "RUN_FAILED_BEFORE_ROBUSTNESS_EVIDENCE",
            }
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_ROBUSTNESS_CORRUPT",
            "message": "Persisted robustness evidence failed semantic reconstruction",
        }, headers={"Cache-Control": "no-store"})
    try:
        return reconstruct_robustness_projection(stored)
    except RobustnessEvidenceRejected as exc:
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_ROBUSTNESS_CORRUPT",
            "message": "Persisted robustness evidence failed semantic reconstruction",
        }, headers={"Cache-Control": "no-store"}) from exc


@router.get(
    "/projects/{project_id}/experiments/{run_id}/robustness/parameter-neighborhood"
)
def get_parameter_neighborhood(
    project_id: str,
    run_id: int,
    response: Response,
    principal: Principal = Depends(get_principal),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    no_store = {"Cache-Control": "no-store"}
    try:
        run = research_read.get_graph_run(
            project_id, run_id, owner_id=owner_id_for(principal),
        )
    except research_read.StoredEvidenceCorrupt as exc:
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_EVIDENCE_CORRUPT",
            "message": "Persisted experiment evidence failed integrity verification",
        }, headers=no_store) from exc
    if run is None:
        raise HTTPException(
            status_code=404, detail="experiment run not found", headers=no_store,
        )
    if run["evidence_state"] in {"pending", "running"}:
        return {
            "schema": PARAMETER_PROJECTION_SCHEMA,
            "state": "UNAVAILABLE", "reason_code": "RUN_NOT_TERMINAL",
        }
    if run["evidence_state"] != "verified" or run.get("evidence") is None:
        return {
            "schema": PARAMETER_PROJECTION_SCHEMA,
            "state": "UNAVAILABLE",
            "reason_code": "LEGACY_TERMINAL_EVIDENCE_UNAVAILABLE",
        }
    evidence = run["evidence"]
    stored = evidence.get("results", {}).get("parameter_neighborhood")
    try:
        provenance = evidence.get("provenance")
        if not isinstance(provenance, dict):
            raise ParameterNeighborhoodIntegrationRejected(
                "persisted parent ExperimentSpec recipe is malformed"
            )
        recipe_binding = parameter_neighborhood_binding_from_provenance(
            provenance.get("robustness")
        )
        if stored is None:
            if recipe_binding is None:
                stored = {"schema": PARAMETER_PROJECTION_SCHEMA, "state": "NOT_REQUESTED"}
            elif not recipe_binding["parameter_neighborhood"]["enabled"]:
                stored = {"schema": PARAMETER_PROJECTION_SCHEMA, "state": "DISABLED"}
            elif run["status"] == "failed":
                return {
                    "schema": PARAMETER_PROJECTION_SCHEMA,
                    "state": "UNAVAILABLE",
                    "reason_code": "RUN_FAILED_BEFORE_PARAMETER_NEIGHBORHOOD_EVIDENCE",
                }
            else:
                raise ParameterNeighborhoodIntegrationRejected(
                    "requested parameter-neighbourhood terminal evidence is absent"
                )
        return reconstruct_parameter_neighborhood_projection(
            stored, recipe_binding=recipe_binding,
            parent_spec_id=evidence.get("spec_id"), parent_recipe=provenance,
        )
    except ParameterNeighborhoodIntegrationRejected as exc:
        raise HTTPException(status_code=409, detail={
            "code": "EXPERIMENT_PARAMETER_NEIGHBORHOOD_CORRUPT",
            "message": "Persisted parameter-neighborhood evidence failed semantic reconstruction",
        }, headers=no_store) from exc


__all__ = [
    "get_parameter_neighborhood", "get_research_robustness",
    "get_research_visualization", "router",
]
