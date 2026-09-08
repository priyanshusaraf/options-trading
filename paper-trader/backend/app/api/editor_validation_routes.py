"""Rollback-only canonical graph edit validation."""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api import ir_edit_routes
from app.api.principal import Principal, get_principal, owner_id_for
from app.db.models import GraphVersion
from app.db.session import SessionLocal
from app.editor import graph_artifacts as store
from app.editor import layouts
from app.ir.hashing import content_address


router = APIRouter(prefix="/api/ir")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ValidationViolation(_Closed):
    operation_index: int | None
    clause: str | None
    path: list[str | int]
    message: str


class EditorValidationResponse(_Closed):
    schema_version: Literal["strategy-os-editor-validation/1"] = Field(
        default="strategy-os-editor-validation/1", alias="schema")
    valid: bool
    base_revision: int
    base_version: int
    predicted_content_address: str | None
    violations: list[ValidationViolation]
    nonauthority: Literal["VALIDATION_DOES_NOT_PUBLISH_OR_GRANT_AUTHORITY"] = (
        "VALIDATION_DOES_NOT_PUBLISH_OR_GRANT_AUTHORITY"
    )


def _invalid(body, base_version: int, violations: list[ValidationViolation]) -> EditorValidationResponse:
    return EditorValidationResponse(
        valid=False,
        base_revision=body.base_revision,
        base_version=base_version,
        predicted_content_address=None,
        violations=violations[:128],
    )


@router.post(
    "/projects/{project_id}/graphs/{identifier}/edits/validate",
    response_model=EditorValidationResponse,
)
def validate_graph_edits(
    project_id: str,
    identifier: str,
    body: ir_edit_routes.GraphEditRequest,
    principal: Principal = Depends(get_principal),
) -> EditorValidationResponse:
    owner_id = owner_id_for(principal)
    session = SessionLocal()
    try:
        store._active_project(session, project_id, owner_id)
        artifact = store._owned_artifact(session, project_id, identifier, owner_id)
        if artifact.draft_revision != body.base_revision:
            raise store.GraphConflict(artifact.draft_revision)
        if artifact.current_version is None:
            raise store.InvalidTransition("graph has no published version")
        if artifact.published_revision != artifact.draft_revision:
            raise store.InvalidTransition("graph has unpublished draft changes")
        published = session.get(GraphVersion, (owner_id, identifier, artifact.current_version))
        if published is None:
            raise store.GraphNotFound()
        original = json.loads(artifact.draft_json)
        try:
            edit_result = ir_edit_routes._apply_all(original, body.edits)
        except ir_edit_routes.BatchEditRejected as exc:
            return _invalid(body, artifact.current_version, [ValidationViolation(
                operation_index=exc.operation_index,
                clause=violation.clause,
                path=ir_edit_routes._structured_path(violation.path),
                message=violation.message,
            ) for violation in exc.violations])

        document, _encoded = store._normalise_graph(
            identifier, edit_result.graph, current_version=artifact.current_version)
        try:
            store._require_resolvable(document)
            store._admit_for_publication(session, owner_id=owner_id, document=document)
            layouts.apply_presentation_batch_in_session(
                session,
                identifier,
                artifact.current_version,
                base_revision=body.base_presentation_revision,
                operations=tuple(edit.model_dump(mode="python") for edit in body.presentation_edits),
                valid_instance_ids=store._authored_ids(document),
                owner_id=owner_id,
            )
            session.flush()
        except layouts.LayoutConflict:
            raise
        except layouts.LayoutRejected as exc:
            return _invalid(body, artifact.current_version, [ValidationViolation(
                operation_index=exc.operation_index,
                clause=None,
                path=list(exc.path),
                message=str(exc),
            )])
        except store.GraphAdmissionRefused as exc:
            return _invalid(body, artifact.current_version, [ValidationViolation(
                operation_index=None,
                clause=exc.code.value,
                path=[],
                message="Causal admission refused",
            )])
        except store.GraphRejected as exc:
            return _invalid(body, artifact.current_version, [ValidationViolation(
                operation_index=None,
                clause=None,
                path=[],
                message=str(exc),
            )])
        return EditorValidationResponse(
            valid=True,
            base_revision=body.base_revision,
            base_version=artifact.current_version,
            predicted_content_address=content_address(document),
            violations=[],
        )
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise HTTPException(status_code=404, detail="graph artefact not found") from exc
    except store.GraphConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "DRAFT_REVISION_CONFLICT",
            "current_revision": exc.current_revision,
        }) from exc
    except layouts.LayoutConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "PRESENTATION_REVISION_CONFLICT",
            "current_presentation_revision": exc.current_revision,
        }) from exc
    except store.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail={
            "code": ir_edit_routes._transition_code(exc),
            "message": str(exc),
        }) from exc
    finally:
        # This endpoint may exercise the real admission and layout writers, but it
        # never commits them.  Rollback is unconditional, including success.
        session.rollback()
        session.close()


__all__ = ["router", "validate_graph_edits"]
