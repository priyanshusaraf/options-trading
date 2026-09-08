"""Unpublished transaction-bound monitoring attention and review commands."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import re

from app.db.concurrency import (
    TransactionBoundaryError,
    begin_after_clean_reads,
    caller_owned_savepoint,
)
from app.monitoring.contracts import (
    AlertAttentionEvent,
    AlertAttentionProjection,
    AttentionAction,
    MonitoringContractError,
)
from app.monitoring.repository import (
    MonitoringConflict,
    MonitoringNotFound,
    MonitoringRefused,
    MonitoringRepository,
    SignalReview,
)


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")


class MonitoringInteractionError(ValueError):
    """Base error for the unpublished command boundary."""


class MonitoringInteractionRefusal(MonitoringInteractionError):
    pass


class MonitoringInteractionConflict(MonitoringInteractionError):
    pass


class MonitoringInteractionNotFound(MonitoringInteractionError):
    pass


@dataclass(frozen=True, slots=True)
class AttentionCommandResult:
    event: AlertAttentionEvent
    projection: AlertAttentionProjection
    replayed: bool


@dataclass(frozen=True, slots=True)
class ReviewCommandResult:
    review: SignalReview
    replayed: bool


def _repository(value: object) -> MonitoringRepository:
    if type(value) is not MonitoringRepository:
        raise MonitoringInteractionRefusal(
            "exact owner-scoped monitoring repository required"
        )
    return value


def _utc(value: object, label: str) -> dt.datetime:
    if type(value) is not dt.datetime or value.tzinfo is not dt.timezone.utc:
        raise MonitoringInteractionRefusal(f"{label} must use exact UTC")
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise MonitoringInteractionRefusal(f"{label} identifier required")
    return value


def _address(value: object, label: str) -> str:
    if type(value) is not str or not _ADDRESS.fullmatch(value):
        raise MonitoringInteractionRefusal(f"{label} content address required")
    return value


def _attention_replay(
    repository: MonitoringRepository, *, assignment_id: str,
    alert_address: str, candidate: AlertAttentionEvent,
) -> AttentionCommandResult:
    try:
        existing = repository.get_attention_event(
            assignment_id, alert_address, candidate.request_id,
        )
        projection = repository.get_attention_state(assignment_id, alert_address)
    except MonitoringNotFound as exc:
        raise MonitoringInteractionConflict(
            "attention sequence is stale or conflicting"
        ) from exc
    if (
        existing.sequence != candidate.sequence
        or existing.action is not candidate.action
        or existing.owner_id != repository.owner_id
    ):
        raise MonitoringInteractionConflict("attention request identity conflicts")
    return AttentionCommandResult(existing, projection, True)


def apply_attention_command(
    repository: MonitoringRepository,
    *,
    assignment_id: str,
    alert_address: str,
    expected_sequence: int,
    action: AttentionAction,
    occurred_at: dt.datetime,
) -> AttentionCommandResult:
    """Append one optimistic attention action or replay its exact prior effect."""
    repository = _repository(repository)
    if type(expected_sequence) is not int or expected_sequence < 0:
        raise MonitoringInteractionRefusal("nonnegative expected sequence required")
    if type(action) is not AttentionAction:
        raise MonitoringInteractionRefusal("closed attention action required")
    occurred = _utc(occurred_at, "attention occurrence")
    assignment_id = _identifier(assignment_id, "assignment")
    alert_address = _address(alert_address, "alert")
    scope = (
        f"monitoring-attention:{repository.owner_id}:"
        f"{assignment_id}:{alert_address}"
    )
    try:
        begin_after_clean_reads(repository.session, scope=scope)
        alert = repository.get_alert(assignment_id, alert_address)
        projection = repository.get_attention_state(assignment_id, alert_address)
        candidate = AlertAttentionEvent.create(
            alert=alert,
            sequence=expected_sequence + 1,
            action=action,
            occurred_at=occurred,
        )
        if projection.last_sequence > expected_sequence:
            return _attention_replay(
                repository,
                assignment_id=assignment_id,
                alert_address=alert_address,
                candidate=candidate,
            )
        if projection.last_sequence < expected_sequence:
            raise MonitoringInteractionConflict("attention sequence has a gap")
        try:
            with caller_owned_savepoint(repository.session, scope=scope):
                event = repository.append_attention_event(
                    candidate, created_at=occurred,
                )
                updated = repository.get_attention_state(
                    assignment_id, alert_address,
                )
                if (
                    event != candidate
                    or updated.last_sequence != candidate.sequence
                    or updated.owner_id != repository.owner_id
                    or updated.assignment_id != assignment_id
                    or updated.alert_address != alert_address
                ):
                    raise MonitoringInteractionConflict(
                        "attention result differs from command"
                    )
        except (MonitoringConflict, MonitoringContractError):
            return _attention_replay(
                repository,
                assignment_id=assignment_id,
                alert_address=alert_address,
                candidate=candidate,
            )
    except MonitoringNotFound as exc:
        raise MonitoringInteractionNotFound("monitoring object not found") from exc
    except MonitoringInteractionError:
        raise
    except (
        MonitoringRefused,
        MonitoringContractError,
        TransactionBoundaryError,
        RuntimeError,
    ) as exc:
        raise MonitoringInteractionRefusal("attention command refused") from exc
    return AttentionCommandResult(event, updated, False)


def _same_review(
    value: SignalReview, *, disposition: str, reason_code: str, note: str,
) -> bool:
    return (
        value.disposition == disposition
        and value.reason_code == reason_code
        and value.note == note
    )


def submit_signal_review_command(
    repository: MonitoringRepository,
    *,
    assignment_id: str,
    monitoring_event_address: str,
    server_reviewer_user_id: str,
    disposition: str,
    reason_code: str,
    note: str,
    created_at: dt.datetime,
) -> ReviewCommandResult:
    """Create one immutable reviewer/event decision or replay the same decision."""
    repository = _repository(repository)
    created = _utc(created_at, "review creation")
    assignment_id = _identifier(assignment_id, "assignment")
    monitoring_event_address = _address(
        monitoring_event_address, "monitoring event",
    )
    server_reviewer_user_id = _identifier(
        server_reviewer_user_id, "server reviewer",
    )
    scope = (
        f"monitoring-review:{repository.owner_id}:{assignment_id}:"
        f"{monitoring_event_address}:{server_reviewer_user_id}"
    )
    try:
        begin_after_clean_reads(repository.session, scope=scope)
        try:
            existing = repository.get_review(
                assignment_id, monitoring_event_address, server_reviewer_user_id,
            )
        except MonitoringNotFound:
            existing = None
        if existing is not None:
            if not _same_review(
                existing, disposition=disposition,
                reason_code=reason_code, note=note,
            ):
                raise MonitoringInteractionConflict("signal review is immutable")
            return ReviewCommandResult(existing, True)
        candidate = SignalReview(
            owner_id=repository.owner_id,
            assignment_id=assignment_id,
            monitoring_event_address=monitoring_event_address,
            reviewer_user_id=server_reviewer_user_id,
            disposition=disposition,
            reason_code=reason_code,
            note=note,
            created_at=created,
        )
        try:
            with caller_owned_savepoint(repository.session, scope=scope):
                review = repository.append_review(candidate)
                if review != candidate:
                    raise MonitoringInteractionConflict(
                        "signal review result differs from command"
                    )
        except MonitoringConflict:
            existing = repository.get_review(
                assignment_id, monitoring_event_address, server_reviewer_user_id,
            )
            if not _same_review(
                existing, disposition=disposition,
                reason_code=reason_code, note=note,
            ):
                raise MonitoringInteractionConflict("signal review is immutable")
            return ReviewCommandResult(existing, True)
    except MonitoringNotFound as exc:
        raise MonitoringInteractionNotFound("monitoring object not found") from exc
    except MonitoringInteractionError:
        raise
    except (MonitoringRefused, TransactionBoundaryError, RuntimeError) as exc:
        raise MonitoringInteractionRefusal("signal review command refused") from exc
    return ReviewCommandResult(review, False)


__all__ = [
    "AttentionCommandResult",
    "MonitoringInteractionConflict",
    "MonitoringInteractionError",
    "MonitoringInteractionNotFound",
    "MonitoringInteractionRefusal",
    "ReviewCommandResult",
    "apply_attention_command",
    "submit_signal_review_command",
]
