"""Unpublished transaction-bound deterministic in-app alert delivery."""
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
    AlertDeliveryAttempt,
    DeliveryChannel,
    DeliveryOutcome,
    MonitoringContractError,
)
from app.monitoring.repository import (
    MonitoringConflict,
    MonitoringNotFound,
    MonitoringRefused,
    MonitoringRepository,
)


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_FAILURE_CODES = frozenset({"IN_APP_STORE_UNAVAILABLE"})


class MonitoringDeliveryError(ValueError):
    """Base error for the unpublished delivery boundary."""


class MonitoringDeliveryRefusal(MonitoringDeliveryError):
    pass


class MonitoringDeliveryConflict(MonitoringDeliveryError):
    pass


class MonitoringDeliveryNotFound(MonitoringDeliveryError):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryAttemptResult:
    attempt: AlertDeliveryAttempt
    replayed: bool


def _repository(value: object) -> MonitoringRepository:
    if type(value) is not MonitoringRepository:
        raise MonitoringDeliveryRefusal(
            "exact owner-scoped monitoring repository required"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise MonitoringDeliveryRefusal(f"{label} identifier required")
    return value


def _address(value: object, label: str) -> str:
    if type(value) is not str or not _ADDRESS.fullmatch(value):
        raise MonitoringDeliveryRefusal(f"{label} content address required")
    return value


def _utc(value: object) -> dt.datetime:
    if type(value) is not dt.datetime or value.tzinfo is not dt.timezone.utc:
        raise MonitoringDeliveryRefusal("delivery occurrence must use exact UTC")
    return value


def _failure_code(outcome: DeliveryOutcome, value: object) -> str | None:
    if outcome is DeliveryOutcome.FAILED:
        if type(value) is not str or value not in _FAILURE_CODES:
            raise MonitoringDeliveryRefusal("closed delivery failure code required")
        return value
    if value is not None:
        raise MonitoringDeliveryRefusal("delivered attempt cannot have a failure code")
    return None


def _same_semantic_request(
    attempt: AlertDeliveryAttempt, *, outcome: DeliveryOutcome,
    failure_code: str | None,
) -> bool:
    return (
        attempt.channel is DeliveryChannel.IN_APP
        and attempt.outcome is outcome
        and attempt.failure_code == failure_code
    )


def record_in_app_delivery(
    repository: MonitoringRepository,
    *,
    assignment_id: str,
    alert_address: str,
    expected_sequence: int,
    outcome: DeliveryOutcome,
    occurred_at: dt.datetime,
    failure_code: str | None = None,
) -> DeliveryAttemptResult:
    """Append or replay one deterministic IN_APP attempt without committing."""
    repository = _repository(repository)
    assignment_id = _identifier(assignment_id, "assignment")
    alert_address = _address(alert_address, "alert")
    if type(expected_sequence) is not int or expected_sequence < 0:
        raise MonitoringDeliveryRefusal("nonnegative expected sequence required")
    if type(outcome) is not DeliveryOutcome:
        raise MonitoringDeliveryRefusal("closed delivery outcome required")
    occurred_at = _utc(occurred_at)
    failure_code = _failure_code(outcome, failure_code)
    sequence = expected_sequence + 1
    scope = (
        f"monitoring-delivery:{repository.owner_id}:"
        f"{assignment_id}:{alert_address}"
    )

    try:
        begin_after_clean_reads(repository.session, scope=scope)
        with caller_owned_savepoint(repository.session, scope=scope):
            alert = repository.get_alert(assignment_id, alert_address)
            try:
                existing = repository.get_delivery_attempt(
                    assignment_id, alert_address, sequence,
                )
            except MonitoringNotFound:
                existing = None
            if existing is not None:
                if not _same_semantic_request(
                    existing, outcome=outcome, failure_code=failure_code,
                ):
                    raise MonitoringDeliveryConflict(
                        "delivery request outcome or failure conflicts"
                    )
                return DeliveryAttemptResult(existing, True)

            candidate = AlertDeliveryAttempt.create(
                alert=alert,
                sequence=sequence,
                outcome=outcome,
                occurred_at=occurred_at,
                failure_code=failure_code,
            )
            persisted = repository.append_delivery_attempt(
                candidate, created_at=occurred_at,
            )
            if persisted != candidate:
                raise MonitoringDeliveryConflict(
                    "delivery result differs from command"
                )
            verified = repository.get_delivery_attempt(
                assignment_id, alert_address, sequence,
            )
            if verified != candidate:
                raise MonitoringDeliveryConflict(
                    "delivery postcondition differs from command"
                )
    except MonitoringNotFound as exc:
        raise MonitoringDeliveryNotFound("monitoring object not found") from exc
    except MonitoringDeliveryError:
        raise
    except (MonitoringConflict, MonitoringContractError) as exc:
        raise MonitoringDeliveryConflict("delivery sequence conflicts") from exc
    except (
        MonitoringRefused,
        TransactionBoundaryError,
        RuntimeError,
    ) as exc:
        raise MonitoringDeliveryRefusal("in-app delivery refused") from exc
    return DeliveryAttemptResult(verified, False)


__all__ = [
    "DeliveryAttemptResult",
    "MonitoringDeliveryConflict",
    "MonitoringDeliveryError",
    "MonitoringDeliveryNotFound",
    "MonitoringDeliveryRefusal",
    "record_in_app_delivery",
]
