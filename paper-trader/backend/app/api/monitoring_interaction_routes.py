"""Factory-built, unregistered monitoring attention and review mutation API."""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, owner_id_for
from app.monitoring.contracts import AlertAttentionProjection, AttentionAction
from app.monitoring.interaction_service import (
    AttentionCommandResult,
    MonitoringInteractionConflict,
    MonitoringInteractionNotFound,
    MonitoringInteractionRefusal,
    ReviewCommandResult,
    apply_attention_command,
    submit_signal_review_command,
)
from app.monitoring.repository import MonitoringNotFound, MonitoringRepository


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MAX_SEQUENCE = 2**31 - 1
_MAX_NOTE_BYTES = 4096
_MAX_BODY_BYTES = 16384


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MonitoringAttentionMutationRead(_ClosedModel):
    schema_version: Literal["monitoring-attention-mutation-read/1"] = Field(
        default="monitoring-attention-mutation-read/1", alias="schema",
    )
    attention_event_address: str
    request_id: str
    assignment_id: str
    alert_address: str
    sequence: int
    action: Literal["READ", "ACKNOWLEDGE", "DISMISS"]
    occurred_at: dt.datetime
    replayed: bool
    last_sequence: int
    is_unread: bool
    read_at: dt.datetime | None
    acknowledged_at: dt.datetime | None
    dismissed_at: dt.datetime | None


class MonitoringReviewMutationRead(_ClosedModel):
    schema_version: Literal["monitoring-review-mutation-read/1"] = Field(
        default="monitoring-review-mutation-read/1", alias="schema",
    )
    review_address: str
    assignment_id: str
    monitoring_event_address: str
    disposition: Literal["CONFIRMED", "REJECTED"]
    reason_code: str
    note: str
    created_at: dt.datetime
    replayed: bool


def _principal_context(principal: Principal) -> tuple[str, str]:
    if type(principal) is not Principal or principal.kind != "user" \
            or not principal.authenticated or not principal.user_id \
            or not principal.organization_id or not principal.session_id:
        raise HTTPException(status_code=401, detail="unauthorized")
    return owner_id_for(principal), principal.user_id


def _identifier(value: str, label: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    return value


def _address(value: str) -> str:
    if type(value) is not str or not _ADDRESS.fullmatch(value):
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    return value


def _clock(value: Callable[[], dt.datetime]) -> dt.datetime:
    try:
        current = value()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="monitoring command unavailable") from exc
    if type(current) is not dt.datetime or current.tzinfo is not dt.timezone.utc:
        raise HTTPException(status_code=503, detail="monitoring command unavailable")
    return current


def _mapping(value: Any, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


async def _json_body(request: Request) -> Any:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=400, detail="invalid monitoring command")
    if not body:
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    try:
        return json.loads(
            body.decode("utf-8"), object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail="invalid monitoring command",
        ) from exc


def _attention_body(value: Any) -> tuple[int, AttentionAction]:
    payload = _mapping(value, {"expected_sequence", "action"})
    sequence = payload["expected_sequence"]
    action = payload["action"]
    if type(sequence) is not int or sequence < 0 or sequence > _MAX_SEQUENCE \
            or type(action) is not str or action not in AttentionAction._value2member_map_:
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    return sequence, AttentionAction(action)


def _review_body(value: Any) -> tuple[str, str, str]:
    payload = _mapping(value, {"disposition", "reason_code", "note"})
    disposition, reason, note = (
        payload["disposition"], payload["reason_code"], payload["note"],
    )
    if type(disposition) is not str or disposition not in {"CONFIRMED", "REJECTED"} \
            or type(reason) is not str or not _REASON.fullmatch(reason) \
            or type(note) is not str or note != note.strip() \
            or any(ord(character) < 32 or ord(character) == 127 for character in note):
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    try:
        note_bytes = len(note.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise HTTPException(
            status_code=400, detail="invalid monitoring command",
        ) from exc
    if note_bytes > _MAX_NOTE_BYTES:
        raise HTTPException(status_code=400, detail="invalid monitoring command")
    return disposition, reason, note


def _attention_read(
    result: AttentionCommandResult,
) -> MonitoringAttentionMutationRead:
    event = result.event
    projection: AlertAttentionProjection = result.projection
    return MonitoringAttentionMutationRead(
        attention_event_address=event.address,
        request_id=event.request_id,
        assignment_id=event.assignment_id,
        alert_address=event.alert_address,
        sequence=event.sequence,
        action=event.action.value,
        occurred_at=event.occurred_at,
        replayed=result.replayed,
        last_sequence=projection.last_sequence,
        is_unread=projection.is_unread,
        read_at=projection.read_at,
        acknowledged_at=projection.acknowledged_at,
        dismissed_at=projection.dismissed_at,
    )


def _review_read(result: ReviewCommandResult) -> MonitoringReviewMutationRead:
    review = result.review
    return MonitoringReviewMutationRead(
        review_address=review.address,
        assignment_id=review.assignment_id,
        monitoring_event_address=review.monitoring_event_address,
        disposition=review.disposition,
        reason_code=review.reason_code,
        note=review.note,
        created_at=review.created_at,
        replayed=result.replayed,
    )


def _raise_command_error(exc: Exception) -> None:
    if isinstance(exc, (MonitoringInteractionNotFound, MonitoringNotFound)):
        raise HTTPException(status_code=404, detail="monitoring object not found") from exc
    if isinstance(exc, MonitoringInteractionConflict):
        raise HTTPException(status_code=409, detail="monitoring command conflict") from exc
    if isinstance(exc, MonitoringInteractionRefusal):
        raise HTTPException(status_code=400, detail="invalid monitoring command") from exc
    raise exc


def build_monitoring_interaction_router(
    *, sessionmaker: Callable, clock: Callable[[], dt.datetime],
) -> APIRouter:
    """Build dedicated mutation routes without shared registration or defaults."""
    if not callable(sessionmaker) or not callable(clock):
        raise TypeError("monitoring sessionmaker and UTC clock must be callable")
    router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring-interactions"])

    @router.post(
        "/assignments/{assignment_id}/alerts/{alert_address}/attention",
        response_model=MonitoringAttentionMutationRead,
    )
    async def post_attention(
        assignment_id: str,
        alert_address: str,
        request: Request,
        principal: Principal = Depends(get_principal),
    ) -> MonitoringAttentionMutationRead:
        owner_id, _reviewer = _principal_context(principal)
        assignment = _identifier(assignment_id, "assignment")
        alert = _address(alert_address)
        payload = await _json_body(request)
        sequence, action = _attention_body(payload)
        now = _clock(clock)
        try:
            with sessionmaker() as session:
                result = apply_attention_command(
                    MonitoringRepository(session, owner_id=owner_id),
                    assignment_id=assignment,
                    alert_address=alert,
                    expected_sequence=sequence,
                    action=action,
                    occurred_at=now,
                )
                response = _attention_read(result)
                session.commit()
                return response
        except Exception as exc:
            _raise_command_error(exc)

    @router.post(
        "/assignments/{assignment_id}/alerts/{alert_address}/review",
        response_model=MonitoringReviewMutationRead,
    )
    async def post_review(
        assignment_id: str,
        alert_address: str,
        request: Request,
        principal: Principal = Depends(get_principal),
    ) -> MonitoringReviewMutationRead:
        owner_id, reviewer_user_id = _principal_context(principal)
        assignment = _identifier(assignment_id, "assignment")
        alert_address = _address(alert_address)
        payload = await _json_body(request)
        disposition, reason, note = _review_body(payload)
        now = _clock(clock)
        try:
            with sessionmaker() as session:
                repository = MonitoringRepository(session, owner_id=owner_id)
                alert = repository.get_alert(assignment, alert_address)
                result = submit_signal_review_command(
                    repository,
                    assignment_id=assignment,
                    monitoring_event_address=alert.monitoring_event_address,
                    server_reviewer_user_id=reviewer_user_id,
                    disposition=disposition,
                    reason_code=reason,
                    note=note,
                    created_at=now,
                )
                response = _review_read(result)
                session.commit()
                return response
        except Exception as exc:
            _raise_command_error(exc)

    return router


__all__ = [
    "MonitoringAttentionMutationRead",
    "MonitoringReviewMutationRead",
    "build_monitoring_interaction_router",
]
