"""Conservative, fenced recovery transitions for capital reservations.

Expiry and uncertainty are evidence of ambiguity, never evidence of release.
The caller owns the outer transaction and commit.  No broker call occurs here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.concurrency import begin_after_clean_reads, caller_owned_savepoint, locked_rows
from app.db.models import (
    AccountExecutionCommand,
    CapitalReservationEventRecord,
    CapitalReservationHead,
    CapitalReservationRecord,
)
from app.execution.leases import LeaseRepository, LeaseToken, _append_execution_change
from app.ir.hashing import content_address


UNCERTAIN_OUTCOMES = frozenset({
    "SEND_UNKNOWN", "LATE_ACK", "CANCEL_FILL_CROSS", "EXTERNAL_ORDER",
    "TAKEOVER", "EXPIRED",
})
RELEASE_OUTCOMES = frozenset({
    "REJECTED_CONFIRMED", "CANCELLED_CONFIRMED", "RESOLVED_UNUSED",
})
ALL_OUTCOMES = UNCERTAIN_OUTCOMES | RELEASE_OUTCOMES | {"PARTIAL_FILL", "FILLED"}
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_INT32_MAX = (1 << 31) - 1
_INT64_MAX = (1 << 63) - 1


class RecoveryRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RecoveryEvidence:
    recovery_id: str
    reservation_id: str
    outcome: str
    expected_head_revision: int
    cumulative_filled_quantity: int
    consumed_minor: int
    broker_evidence_address: str
    occurred_at: dt.datetime
    command_id: str | None = None
    broker_identity: str = ""

    @property
    def address(self) -> str:
        return content_address({
            "schema": "strategy-os.capital-recovery-evidence/v1",
            "recovery_id": self.recovery_id,
            "reservation_id": self.reservation_id,
            "outcome": self.outcome,
            "expected_head_revision": self.expected_head_revision,
            "cumulative_filled_quantity": self.cumulative_filled_quantity,
            "consumed_minor": self.consumed_minor,
            "broker_evidence_address": self.broker_evidence_address,
            "occurred_at": self.occurred_at.isoformat(timespec="microseconds"),
            "command_id": self.command_id,
            "broker_identity": self.broker_identity,
        })


@dataclass(frozen=True)
class RecoveryResult:
    reservation_id: str
    state: str
    consumed_quantity: int
    consumed_minor: int
    revision: int
    head_revision: int
    duplicate: bool = False


def _event_id(evidence: RecoveryEvidence) -> str:
    return hashlib.sha256(
        (f"reservation-recovery\0{evidence.reservation_id}\0"
         f"{evidence.recovery_id}").encode("utf-8")).hexdigest()


def _bounded_exact_int(value: object, *, maximum: int) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _validate(evidence: RecoveryEvidence) -> None:
    if not evidence.recovery_id or len(evidence.recovery_id) > 64 \
            or not evidence.reservation_id or len(evidence.reservation_id) > 64:
        raise RecoveryRefused("INVALID_RECOVERY_IDENTITY")
    if evidence.outcome not in ALL_OUTCOMES:
        raise RecoveryRefused("INVALID_RECOVERY_OUTCOME")
    if not _bounded_exact_int(
            evidence.expected_head_revision, maximum=_INT32_MAX) \
            or not _bounded_exact_int(
                evidence.cumulative_filled_quantity, maximum=_INT32_MAX) \
            or not _bounded_exact_int(
                evidence.consumed_minor, maximum=_INT64_MAX):
        raise RecoveryRefused("INVALID_RECOVERY_NUMERIC")
    if not _ADDRESS.fullmatch(evidence.broker_evidence_address):
        raise RecoveryRefused("INVALID_BROKER_EVIDENCE")
    if evidence.occurred_at.tzinfo is not None:
        raise RecoveryRefused("INVALID_RECOVERY_TIMESTAMP")
    if evidence.command_id is not None and len(evidence.command_id) > 64:
        raise RecoveryRefused("INVALID_COMMAND_IDENTITY")
    if len(evidence.broker_identity) > 96:
        raise RecoveryRefused("INVALID_BROKER_IDENTITY")


def _result(
        reservation: CapitalReservationRecord, head: CapitalReservationHead,
        *, duplicate: bool = False) -> RecoveryResult:
    return RecoveryResult(
        reservation.reservation_id, reservation.state,
        reservation.consumed_quantity, reservation.consumed_minor,
        reservation.revision, head.revision, duplicate,
    )


def recover_reservation(
        session: Session, leases: LeaseRepository, token: LeaseToken,
        evidence: RecoveryEvidence) -> RecoveryResult:
    """Apply one exact recovery fact under the current lease and head lock."""
    _validate(evidence)
    leases.bind_money_session(session, token)
    scope = f"capital-recovery:{token.owner_id}:{token.broker_account_id}"
    begin_after_clean_reads(session, scope=scope)
    with caller_owned_savepoint(session, scope=scope):
        leases.require_current_in_session(session, token, active=False, lock=True)
        reservation = session.scalar(locked_rows(select(CapitalReservationRecord).where(
            CapitalReservationRecord.reservation_id == evidence.reservation_id,
            CapitalReservationRecord.owner_id == token.owner_id,
            CapitalReservationRecord.broker_account_id == token.broker_account_id,
            CapitalReservationRecord.book == "paper",
        ), session))
        if reservation is None:
            raise RecoveryRefused("PAPER_RESERVATION_MISSING")
        head = session.scalar(locked_rows(select(CapitalReservationHead).where(
            CapitalReservationHead.owner_id == reservation.owner_id,
            CapitalReservationHead.broker_account_id == reservation.broker_account_id,
            CapitalReservationHead.book == reservation.book,
            CapitalReservationHead.currency == reservation.currency,
        ), session))
        if head is None:
            raise RecoveryRefused("RESERVATION_HEAD_MISSING")

        event_id = _event_id(evidence)
        prior = session.get(CapitalReservationEventRecord, event_id)
        if prior is not None:
            if prior.evidence_address != evidence.address \
                    or prior.reason_code != evidence.outcome:
                raise RecoveryRefused("CONFLICTING_RECOVERY_DUPLICATE")
            return _result(reservation, head, duplicate=True)
        if head.revision != evidence.expected_head_revision:
            raise RecoveryRefused("STALE_HEAD_REVISION")
        if reservation.state in {"consumed", "released"}:
            raise RecoveryRefused("RESERVATION_TERMINAL")
        if evidence.occurred_at < reservation.created_at or (
                reservation.last_reconciled_at is not None
                and evidence.occurred_at < reservation.last_reconciled_at):
            raise RecoveryRefused("STALE_RECOVERY_EVIDENCE")
        if token.fence_epoch < reservation.fence_epoch:
            raise RecoveryRefused("STALE_RESERVATION_FENCE")
        if evidence.outcome == "TAKEOVER" and token.fence_epoch <= reservation.fence_epoch:
            raise RecoveryRefused("TAKEOVER_REQUIRES_NEW_FENCE")
        command = (session.get(AccountExecutionCommand, reservation.command_id)
                   if reservation.command_id is not None else None)
        if reservation.command_id is not None and command is None:
            raise RecoveryRefused("COMMAND_EVIDENCE_MISSING")
        if reservation.command_id is not None \
                and evidence.outcome != "EXTERNAL_ORDER" \
                and evidence.command_id != reservation.command_id:
            raise RecoveryRefused("COMMAND_EVIDENCE_MISMATCH")
        if reservation.command_id is None and evidence.command_id is not None:
            raise RecoveryRefused("COMMAND_EVIDENCE_MISMATCH")
        if evidence.outcome == "SEND_UNKNOWN" \
                and (command is None or command.state != "sent_unknown"):
            raise RecoveryRefused("SEND_UNKNOWN_COMMAND_MISMATCH")
        if evidence.outcome == "LATE_ACK" \
                and (command is None or command.state not in {"acknowledged", "resolved"}):
            raise RecoveryRefused("LATE_ACK_COMMAND_MISMATCH")
        if evidence.outcome == "REJECTED_CONFIRMED" \
                and (command is None or command.state != "failed"):
            raise RecoveryRefused("REJECTION_COMMAND_MISMATCH")
        if evidence.outcome == "CANCELLED_CONFIRMED" \
                and (command is None or command.state != "cancelled"):
            raise RecoveryRefused("CANCELLATION_COMMAND_MISMATCH")
        if evidence.outcome == "RESOLVED_UNUSED" and command is not None:
            raise RecoveryRefused("RESOLVED_UNUSED_COMMAND_MISMATCH")
        admitted = abs(reservation.admitted_quantity)
        if evidence.cumulative_filled_quantity < reservation.consumed_quantity \
                or evidence.cumulative_filled_quantity > admitted \
                or evidence.consumed_minor < reservation.consumed_minor \
                or evidence.consumed_minor > reservation.estimated_minor:
            raise RecoveryRefused("NON_MONOTONIC_CONSUMPTION")

        if evidence.outcome in RELEASE_OUTCOMES:
            if evidence.cumulative_filled_quantity != 0 or evidence.consumed_minor != 0:
                raise RecoveryRefused("RELEASE_REQUIRES_ZERO_FILL_PROOF")
            to_state = "released"
        elif evidence.outcome == "PARTIAL_FILL":
            if not 0 < evidence.cumulative_filled_quantity < admitted:
                raise RecoveryRefused("PARTIAL_FILL_SHAPE_MISMATCH")
            to_state = "partially_consumed"
        elif evidence.outcome == "FILLED":
            if evidence.cumulative_filled_quantity != admitted:
                raise RecoveryRefused("FILLED_QUANTITY_MISMATCH")
            to_state = "consumed"
        else:
            to_state = "reconciliation_required"

        from_state = reservation.state
        reservation.state = to_state
        reservation.consumed_quantity = evidence.cumulative_filled_quantity
        reservation.consumed_minor = evidence.consumed_minor
        reservation.last_reconciled_at = evidence.occurred_at
        reservation.revision += 1
        head.revision += 1
        head.updated_at = evidence.occurred_at
        event_document = {
            "schema": "strategy-os.capital-reservation-event/v1",
            "event_id": event_id,
            "reservation_address": reservation.reservation_address,
            "revision": reservation.revision,
            "from_state": from_state,
            "to_state": to_state,
            "consumed_minor": reservation.consumed_minor,
            "consumed_quantity": reservation.consumed_quantity,
            "fence_epoch": token.fence_epoch,
            "evidence_address": evidence.address,
            "reason_code": evidence.outcome,
            "occurred_at": evidence.occurred_at.isoformat(timespec="microseconds"),
        }
        session.add(CapitalReservationEventRecord(
            event_id=event_id, event_address=content_address(event_document),
            reservation_id=reservation.reservation_id,
            revision=reservation.revision,
            from_state=from_state, to_state=to_state,
            consumed_minor=reservation.consumed_minor,
            consumed_quantity=reservation.consumed_quantity,
            fence_epoch=token.fence_epoch,
            evidence_address=evidence.address,
            reason_code=evidence.outcome,
            occurred_at=evidence.occurred_at,
        ))
        _append_execution_change(
            session, owner_id=token.owner_id,
            broker_account_id=token.broker_account_id,
            aggregate_type="capital_reservation",
            aggregate_id=reservation.reservation_id,
            event_type="execution.money.changed",
            producer_key=f"capital-recovery:{event_id}",
            payload={
                "projection": "capital_reservation",
                "state": to_state,
                "revision": reservation.revision,
                "head_revision": head.revision,
                "fence_epoch": token.fence_epoch,
            },
        )
        session.flush()
        leases.require_current_in_session(session, token, active=False, lock=True)
        return _result(reservation, head)


def expired_paper_reservations(
        session: Session, *, owner_id: str, broker_account_id: str,
        observed_at: dt.datetime) -> tuple[str, ...]:
    """Return expiry candidates without releasing or mutating any reservation."""
    if observed_at.tzinfo is not None:
        raise RecoveryRefused("INVALID_RECOVERY_TIMESTAMP")
    return tuple(session.scalars(select(CapitalReservationRecord.reservation_id).where(
        CapitalReservationRecord.owner_id == owner_id,
        CapitalReservationRecord.broker_account_id == broker_account_id,
        CapitalReservationRecord.book == "paper",
        CapitalReservationRecord.state.in_((
            "held", "submission_pending", "partially_consumed",
            "reconciliation_required",
        )),
        CapitalReservationRecord.expires_at <= observed_at,
    ).order_by(CapitalReservationRecord.reservation_id)))


__all__ = [
    "ALL_OUTCOMES", "RecoveryEvidence", "RecoveryRefused", "RecoveryResult",
    "UNCERTAIN_OUTCOMES", "expired_paper_reservations", "recover_reservation",
]
