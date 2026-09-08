"""Durable account leases, fencing tokens, controls, and broker mutation gateway.

Database fencing closes durable writes. It cannot recall an HTTP request released while a
token was current. An uncertain response is therefore journalled ``sent_unknown`` and recovery,
not blind retry, is the only permitted next step.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from sqlalchemy import event, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.concurrency import begin_after_clean_reads, has_pending_writes, locked_rows
from app.db.models import (
    AccountExecutionCommand,
    AccountExecutionLease,
    AccountExecutionLeaseHistory,
    BrokerAccount,
    CandidateIntentRecord,
    CapitalReservationEventRecord,
    CapitalReservationRecord,
    Deployment,
)


class LeaseUnavailable(RuntimeError):
    pass


class StaleLease(RuntimeError):
    pass


class RecoveryRequired(RuntimeError):
    pass


class AmbiguousBrokerOutcome(RuntimeError):
    pass


@dataclass(frozen=True)
class LeaseToken:
    owner_id: str
    broker_account_id: str
    fence_epoch: int
    cell_id: str
    worker_id: str


def _db_now(session: Session) -> dt.datetime:
    value = session.scalar(select(func.current_timestamp()))
    if value is None:
        raise RuntimeError("database clock unavailable")
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


def _scope(owner_id: str, account_id: str) -> str:
    return f"execution-lease:{owner_id}:{account_id}"


def _history(session: Session, lease: AccountExecutionLease, transition: str,
             now: dt.datetime, reason: str = "") -> None:
    session.add(AccountExecutionLeaseHistory(
        owner_id=lease.owner_id,
        broker_account_id=lease.broker_account_id,
        fence_epoch=lease.fence_epoch,
        cell_id=lease.cell_id or "",
        worker_id=lease.worker_id or "",
        transition=transition,
        reason=reason[:200],
        occurred_at=now,
    ))


def _token(lease: AccountExecutionLease) -> LeaseToken:
    return LeaseToken(lease.owner_id, lease.broker_account_id, lease.fence_epoch,
                      lease.cell_id or "", lease.worker_id or "")


def _append_execution_change(session: Session, *, owner_id: str, broker_account_id: str,
                             aggregate_type: str, aggregate_id: str, event_type: str,
                             producer_key: str, payload: dict[str, Any]) -> None:
    from app.events.planes import execution_outbox

    outbox = execution_outbox()
    with outbox.writer(session):
        outbox.append(
            session, classification="private", owner_id=owner_id,
            broker_account_id=broker_account_id, aggregate_type=aggregate_type,
            aggregate_id=aggregate_id, event_type=event_type, schema_version=1,
            payload=payload, producer_key=producer_key)


class LeaseRepository:
    def __init__(self, sessions: sessionmaker):
        self.sessions = sessions

    @staticmethod
    def bind_money_session(session: Session, token: LeaseToken) -> None:
        """Require this exact token at every subsequent ORM money/evidence flush."""
        session.info["execution_lease_token"] = token

    @staticmethod
    def database_time(session: Session) -> dt.datetime:
        """Expose the same database-clock contract used by lease expiry checks."""
        return _db_now(session)

    def claim(self, *, owner_id: str, broker_account_id: str, cell_id: str,
              worker_id: str, ttl_seconds: int = 30, host_diagnostic: str = "") -> LeaseToken:
        if ttl_seconds < 2 or ttl_seconds > 300:
            raise ValueError("lease TTL must be between 2 and 300 seconds")
        if not cell_id or not worker_id or len(cell_id) > 96 or len(worker_id) > 96:
            raise ValueError("bounded cell and boot-unique worker identities are required")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(owner_id, broker_account_id))
            account = session.scalar(select(BrokerAccount).where(
                BrokerAccount.owner_id == owner_id,
                BrokerAccount.broker_account_id == broker_account_id,
                BrokerAccount.status == "active",
            ))
            if account is None:
                raise LeaseUnavailable("broker account unavailable")
            stmt = select(AccountExecutionLease).where(
                AccountExecutionLease.owner_id == owner_id,
                AccountExecutionLease.broker_account_id == broker_account_id,
            )
            lease = session.scalar(locked_rows(stmt, session))
            now = _db_now(session)
            if lease is None:
                lease = AccountExecutionLease(
                    owner_id=owner_id, broker_account_id=broker_account_id,
                    fence_epoch=1, state="recovering", cell_id=cell_id,
                    worker_id=worker_id, host_diagnostic=host_diagnostic[:160],
                    claimed_at=now, heartbeat_at=now,
                    expires_at=now + dt.timedelta(seconds=ttl_seconds),
                    recovery_started_at=now, desired_state="disabled", updated_at=now)
                session.add(lease)
                session.flush()
                transition = "claim"
            elif (lease.cell_id == cell_id and lease.worker_id == worker_id
                  and lease.state in {"recovering", "active"}
                  and lease.expires_at is not None and lease.expires_at > now):
                return _token(lease)
            elif lease.state != "idle" and lease.expires_at is not None and lease.expires_at > now:
                raise LeaseUnavailable("account lease is held")
            else:
                if lease.fence_epoch >= 2_147_483_647:
                    raise LeaseUnavailable("execution fence epoch is exhausted")
                lease.fence_epoch += 1
                lease.state = "recovering"
                lease.cell_id = cell_id
                lease.worker_id = worker_id
                lease.host_diagnostic = host_diagnostic[:160]
                lease.claimed_at = now
                lease.heartbeat_at = now
                lease.expires_at = now + dt.timedelta(seconds=ttl_seconds)
                lease.recovery_started_at = now
                lease.reconciled_at = None
                lease.blocked_at = None
                lease.block_reason = ""
                lease.desired_state = lease.effective_state = "disabled"
                lease.updated_at = now
                transition = "takeover"
                # Pending operator intent survives worker loss. Re-fence it to the new holder;
                # expected-epoch callers were already validated when the command was accepted.
                session.execute(update(AccountExecutionCommand).where(
                    AccountExecutionCommand.owner_id == owner_id,
                    AccountExecutionCommand.broker_account_id == broker_account_id,
                    AccountExecutionCommand.kind.like("control_%"),
                    AccountExecutionCommand.state.in_(("prepared", "processing")),
                ).values(state="prepared", fence_epoch=lease.fence_epoch, cell_id=cell_id,
                         worker_id=worker_id, updated_at=now))
            _history(session, lease, transition, now)
            _append_execution_change(
                session, owner_id=owner_id, broker_account_id=broker_account_id,
                aggregate_type="execution_lease", aggregate_id=broker_account_id,
                event_type="execution.lease.changed",
                producer_key=f"lease:{owner_id}:{broker_account_id}:{lease.fence_epoch}:{transition}",
                payload={"projection": "execution_status", "state": lease.state,
                         "fence_epoch": lease.fence_epoch})
            session.commit()
            return _token(lease)

    def claim_after_restore(self, *, owner_id: str, broker_account_id: str,
                            cell_id: str, worker_id: str, restore_evidence: str,
                            ttl_seconds: int = 30) -> LeaseToken:
        """Fence historical restored authority through the existing lease row.

        The caller proves infrastructure isolation and verifier approval before
        entering here.  This transaction takes the same row lock as normal claim,
        increments the same epoch and never grants active broker authority.
        """
        if ttl_seconds < 2 or ttl_seconds > 300:
            raise ValueError("lease TTL must be between 2 and 300 seconds")
        if not cell_id or not worker_id or len(cell_id) > 96 or len(worker_id) > 96:
            raise ValueError("bounded cell and boot-unique worker identities are required")
        if not restore_evidence.startswith("sha256:") or len(restore_evidence) != 71:
            raise ValueError("restore verification evidence is required")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(owner_id, broker_account_id))
            account = session.scalar(select(BrokerAccount).where(
                BrokerAccount.owner_id == owner_id,
                BrokerAccount.broker_account_id == broker_account_id,
                BrokerAccount.status == "active"))
            if account is None:
                raise LeaseUnavailable("broker account unavailable")
            lease = session.scalar(locked_rows(select(AccountExecutionLease).where(
                AccountExecutionLease.owner_id == owner_id,
                AccountExecutionLease.broker_account_id == broker_account_id), session))
            now = _db_now(session)
            if lease is None:
                raise LeaseUnavailable("restored execution lease evidence is absent")
            if lease.fence_epoch >= 2_147_483_647:
                raise LeaseUnavailable("execution fence epoch is exhausted")
            lease.fence_epoch += 1
            lease.state = "recovering"
            lease.cell_id = cell_id
            lease.worker_id = worker_id
            lease.host_diagnostic = "restored-generation"
            lease.claimed_at = now
            lease.heartbeat_at = now
            lease.expires_at = now + dt.timedelta(seconds=ttl_seconds)
            lease.recovery_started_at = now
            lease.reconciled_at = None
            lease.blocked_at = None
            lease.block_reason = ""
            lease.desired_state = lease.effective_state = "disabled"
            lease.updated_at = now
            session.execute(update(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == owner_id,
                AccountExecutionCommand.broker_account_id == broker_account_id,
                AccountExecutionCommand.kind.like("control_%"),
                AccountExecutionCommand.state.in_(("prepared", "processing")),
            ).values(state="prepared", fence_epoch=lease.fence_epoch,
                     cell_id=cell_id, worker_id=worker_id, updated_at=now))
            _history(session, lease, "takeover", now,
                     f"restore:{restore_evidence}"[:200])
            _append_execution_change(
                session, owner_id=owner_id, broker_account_id=broker_account_id,
                aggregate_type="execution_lease", aggregate_id=broker_account_id,
                event_type="execution.lease.changed",
                producer_key=f"lease:{owner_id}:{broker_account_id}:{lease.fence_epoch}:restore",
                payload={"projection": "execution_status", "state": "recovering",
                         "fence_epoch": lease.fence_epoch})
            session.commit()
            return _token(lease)

    def _current(self, session: Session, token: LeaseToken, *, allow_blocked: bool = False,
                 require_unexpired: bool = True,
                 lock: bool = False) -> tuple[AccountExecutionLease, dt.datetime]:
        now = _db_now(session)
        states = {"recovering", "active"} | ({"blocked"} if allow_blocked else set())
        statement = select(AccountExecutionLease).where(
            AccountExecutionLease.owner_id == token.owner_id,
            AccountExecutionLease.broker_account_id == token.broker_account_id,
            AccountExecutionLease.fence_epoch == token.fence_epoch,
            AccountExecutionLease.cell_id == token.cell_id,
            AccountExecutionLease.worker_id == token.worker_id,
            AccountExecutionLease.state.in_(states),
        )
        lease = session.scalar(locked_rows(statement, session) if lock else statement)
        if lease is None or (require_unexpired and (lease.expires_at is None or lease.expires_at <= now)):
            raise StaleLease("execution lease token is stale or expired")
        return lease, now

    def require_current_in_session(
            self, session: Session, token: LeaseToken, *, active: bool = False,
            lock: bool = False) -> AccountExecutionLease:
        """Verify one caller-owned transaction against the exact durable fence."""
        lease, _ = self._current(session, token, lock=lock)
        if active and lease.state != "active":
            raise RecoveryRequired("execution lease has not completed recovery")
        return lease

    def assert_current(self, token: LeaseToken, *, active: bool = False) -> None:
        with self.sessions() as session:
            lease, _ = self._current(session, token)
            if active and lease.state != "active":
                raise RecoveryRequired("execution lease has not completed recovery")

    def heartbeat(self, token: LeaseToken, *, ttl_seconds: int = 30) -> dt.datetime:
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token)
            expires = now + dt.timedelta(seconds=ttl_seconds)
            result = session.execute(update(AccountExecutionLease).where(
                AccountExecutionLease.owner_id == token.owner_id,
                AccountExecutionLease.broker_account_id == token.broker_account_id,
                AccountExecutionLease.fence_epoch == token.fence_epoch,
                AccountExecutionLease.cell_id == token.cell_id,
                AccountExecutionLease.worker_id == token.worker_id,
                AccountExecutionLease.state.in_(("recovering", "active")),
                AccountExecutionLease.expires_at > now,
            ).values(heartbeat_at=now, expires_at=expires, updated_at=now))
            if result.rowcount != 1:
                session.rollback()
                raise StaleLease("heartbeat lost lease authority")
            session.commit()
            return expires

    def activate(self, token: LeaseToken, *, reconciliation_evidence: str) -> None:
        if not reconciliation_evidence or len(reconciliation_evidence) > 200:
            raise ValueError("bounded reconciliation evidence is required")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token)
            if lease.state != "recovering":
                raise RecoveryRequired("only a recovering lease may activate")
            unresolved = session.scalar(select(func.count()).select_from(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.state.in_(("prepared", "sent_unknown", "acknowledged")),
                ~AccountExecutionCommand.kind.like("control_%"),
            ))
            if unresolved:
                raise RecoveryRequired("unresolved broker commands block activation")
            lease.state = "active"
            lease.reconciled_at = now
            lease.block_reason = ""
            lease.updated_at = now
            _history(session, lease, "activate", now, reconciliation_evidence)
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_lease", aggregate_id=token.broker_account_id,
                event_type="execution.lease.changed",
                producer_key=f"lease:{token.owner_id}:{token.broker_account_id}:{token.fence_epoch}:activate",
                payload={"projection": "execution_status", "state": "active",
                         "fence_epoch": token.fence_epoch})
            session.commit()

    def block(self, token: LeaseToken, reason: str) -> None:
        if not reason:
            raise ValueError("block reason is required")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token, allow_blocked=True)
            lease.state = "blocked"
            lease.blocked_at = now
            lease.block_reason = reason[:200]
            lease.desired_state = lease.effective_state = "disabled"
            lease.updated_at = now
            _history(session, lease, "block", now, reason)
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_lease", aggregate_id=token.broker_account_id,
                event_type="execution.lease.changed",
                producer_key=f"lease:{token.owner_id}:{token.broker_account_id}:{token.fence_epoch}:block",
                payload={"projection": "execution_status", "state": "blocked",
                         "fence_epoch": token.fence_epoch})
            session.commit()

    def release(self, token: LeaseToken, reason: str = "normal shutdown") -> None:
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token, allow_blocked=True,
                                       require_unexpired=False)
            lease.state = "idle"
            lease.cell_id = None
            lease.worker_id = None
            lease.heartbeat_at = None
            lease.expires_at = None
            lease.desired_state = lease.effective_state = "disabled"
            lease.updated_at = now
            _history(session, lease, "release", now, reason)
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_lease", aggregate_id=token.broker_account_id,
                event_type="execution.lease.changed",
                producer_key=f"lease:{token.owner_id}:{token.broker_account_id}:{token.fence_epoch}:release",
                payload={"projection": "execution_status", "state": "idle",
                         "fence_epoch": token.fence_epoch})
            session.commit()

    def status(self, *, owner_id: str, broker_account_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(AccountExecutionLease, (owner_id, broker_account_id))
            if row is None:
                return None
            now = _db_now(session)
            return {
                "broker_account_id": row.broker_account_id,
                "state": row.state,
                "fence_epoch": row.fence_epoch,
                "desired_state": row.desired_state,
                "effective_state": row.effective_state,
                "control_revision": row.control_revision,
                "lease_age_seconds": max(0.0, (now - row.heartbeat_at).total_seconds())
                if row.heartbeat_at else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "blocked": row.state == "blocked",
                "block_reason": row.block_reason,
            }

    def metrics(self) -> dict[str, Any]:
        """Bounded host aggregates. No tenant, account, worker, command, or order labels."""
        with self.sessions() as session:
            now = _db_now(session)
            transitions = dict(session.execute(select(
                AccountExecutionLeaseHistory.transition, func.count()).group_by(
                    AccountExecutionLeaseHistory.transition)).all())
            states = dict(session.execute(select(
                AccountExecutionLease.state, func.count()).group_by(
                    AccountExecutionLease.state)).all())
            oldest_unknown = session.scalar(select(func.min(AccountExecutionCommand.updated_at)).where(
                AccountExecutionCommand.state == "sent_unknown"))
            oldest_control = session.scalar(select(func.min(AccountExecutionCommand.updated_at)).where(
                AccountExecutionCommand.kind.like("control_%"),
                AccountExecutionCommand.state.in_(("prepared", "processing"))))
            recovering_since = session.scalar(select(func.min(
                AccountExecutionLease.recovery_started_at)).where(
                    AccountExecutionLease.state == "recovering"))
            return {
                "transitions": {key: int(transitions.get(key, 0)) for key in
                                ("claim", "takeover", "activate", "block", "fence_rejection")},
                "states": {key: int(states.get(key, 0)) for key in
                           ("active", "recovering", "blocked", "idle")},
                "sent_unknown_age_seconds": max(0.0, (now - oldest_unknown).total_seconds())
                if oldest_unknown else None,
                "control_age_seconds": max(0.0, (now - oldest_control).total_seconds())
                if oldest_control else None,
                "recovery_age_seconds": max(0.0, (now - recovering_since).total_seconds())
                if recovering_since else None,
                "reconciliation_discrepancy_count": int(session.scalar(select(func.count()).where(
                    AccountExecutionLease.state == "blocked")) or 0),
            }

    def request_control(self, *, owner_id: str, broker_account_id: str, kind: str,
                        idempotency_key: str, actor_user_id: str,
                        expected_revision: int | None = None,
                        expected_epoch: int | None = None) -> dict[str, Any]:
        if kind not in {"arm", "disarm", "kill"}:
            raise ValueError("unsupported execution control")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(owner_id, broker_account_id))
            lease = session.scalar(locked_rows(select(AccountExecutionLease).where(
                AccountExecutionLease.owner_id == owner_id,
                AccountExecutionLease.broker_account_id == broker_account_id), session))
            if lease is None:
                raise LeaseUnavailable("execution account has no durable cell")
            existing = session.scalar(select(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == owner_id,
                AccountExecutionCommand.broker_account_id == broker_account_id,
                AccountExecutionCommand.idempotency_key == idempotency_key,
            ))
            if existing is not None:
                expected_kind = f"control_{kind}"
                expected_digest = hashlib.sha256(
                    f"{owner_id}:{broker_account_id}:{kind}:{existing.expected_revision}".encode()
                ).hexdigest()
                if (existing.kind != expected_kind or existing.actor_user_id != actor_user_id
                        or existing.request_digest != expected_digest
                        or (expected_revision is not None
                            and existing.expected_revision != expected_revision + 1)
                        or (expected_epoch is not None and existing.fence_epoch != expected_epoch)):
                    raise ValueError("control idempotency identity collision")
                return {"request_id": existing.command_id, "status": existing.state,
                        "revision": existing.expected_revision,
                        "desired_state": lease.desired_state,
                        "effective_state": lease.effective_state}
            if expected_revision is not None and lease.control_revision != expected_revision:
                raise StaleLease("control revision changed")
            if expected_epoch is not None and lease.fence_epoch != expected_epoch:
                raise StaleLease("execution fence epoch changed")
            if kind == "arm" and lease.state != "active":
                raise RecoveryRequired("arm requires a recovered active lease")
            now = _db_now(session)
            lease.control_revision += 1
            lease.desired_state = "armed" if kind == "arm" else "disabled"
            lease.updated_at = now
            digest = hashlib.sha256(
                f"{owner_id}:{broker_account_id}:{kind}:{lease.control_revision}".encode()).hexdigest()
            command = AccountExecutionCommand(
                command_id=uuid.uuid4().hex, idempotency_key=idempotency_key[:96],
                owner_id=owner_id, broker_account_id=broker_account_id,
                fence_epoch=lease.fence_epoch, cell_id=lease.cell_id or "unassigned",
                worker_id=lease.worker_id or "unassigned", kind=f"control_{kind}", target_id="account",
                request_digest=digest, state="prepared", actor_user_id=actor_user_id[:64],
                expected_revision=lease.control_revision, created_at=now, updated_at=now)
            session.add(command)
            _append_execution_change(
                session, owner_id=owner_id, broker_account_id=broker_account_id,
                aggregate_type="execution_control", aggregate_id=command.command_id,
                event_type="execution.control.changed",
                producer_key=f"control:{command.command_id}:accepted",
                payload={"projection": "execution_status", "state": "accepted",
                         "revision": lease.control_revision})
            session.commit()
            return {"request_id": command.command_id, "status": "accepted",
                    "revision": lease.control_revision, "desired_state": lease.desired_state,
                    "effective_state": lease.effective_state}

    def claim_controls(self, token: LeaseToken, *, limit: int = 16) -> list[AccountExecutionCommand]:
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, _ = self._current(session, token)
            stmt = (select(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch == token.fence_epoch,
                AccountExecutionCommand.kind.like("control_%"),
                AccountExecutionCommand.state == "prepared",
            ).order_by(AccountExecutionCommand.expected_revision,
                       AccountExecutionCommand.command_id)
                    .limit(max(1, min(limit, 100))))
            candidates = list(session.scalars(locked_rows(stmt, session, skip_locked=True)))
            if any((candidate.expected_revision or 0) > lease.control_revision
                   for candidate in candidates):
                raise RecoveryRequired("control revision gap requires reconciliation")
            current = [candidate for candidate in candidates
                       if candidate.expected_revision == lease.control_revision]
            if len(current) > 1:
                raise RecoveryRequired("duplicate current control revision requires reconciliation")
            expected_state = "armed" if (current and current[0].kind == "control_arm") else "disabled"
            if current and lease.desired_state != expected_state:
                raise RecoveryRequired("current control does not match durable desired state")
            won: list[AccountExecutionCommand] = []
            for candidate in candidates:
                if candidate.expected_revision != lease.control_revision:
                    session.execute(update(AccountExecutionCommand).where(
                        AccountExecutionCommand.command_id == candidate.command_id,
                        AccountExecutionCommand.state == "prepared",
                        AccountExecutionCommand.fence_epoch == token.fence_epoch,
                    ).values(state="cancelled", resolved_at=_db_now(session),
                             updated_at=_db_now(session)))
                    continue
                result = session.execute(update(AccountExecutionCommand).where(
                    AccountExecutionCommand.command_id == candidate.command_id,
                    AccountExecutionCommand.state == "prepared",
                    AccountExecutionCommand.fence_epoch == token.fence_epoch,
                    AccountExecutionCommand.cell_id == token.cell_id,
                    AccountExecutionCommand.worker_id == token.worker_id,
                ).values(state="processing", updated_at=_db_now(session)))
                if result.rowcount == 1:
                    candidate.state = "processing"
                    won.append(candidate)
                    break
            session.commit()
            return won

    def complete_control(self, token: LeaseToken, command_id: str, *, success: bool) -> None:
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token)
            command = session.scalar(locked_rows(select(AccountExecutionCommand).where(
                AccountExecutionCommand.command_id == command_id,
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch == token.fence_epoch,
                AccountExecutionCommand.state == "processing"), session))
            if command is None:
                raise StaleLease("control completion lost exact token")
            expected_desired = "armed" if command.kind == "control_arm" else "disabled"
            if (command.expected_revision != lease.control_revision
                    or lease.desired_state != expected_desired):
                command.state = "cancelled"
                command.resolved_at = now
                command.updated_at = now
                session.commit()
                raise StaleLease("control completion was superseded by durable desired state")
            command.state = "resolved" if success else "failed"
            command.resolved_at = now
            command.updated_at = now
            if success:
                lease.effective_state = "armed" if command.kind == "control_arm" else "disabled"
            elif command.kind == "control_arm":
                lease.desired_state = lease.effective_state = "disabled"
            lease.updated_at = now
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_control", aggregate_id=command.command_id,
                event_type="execution.control.changed",
                producer_key=f"control:{command.command_id}:complete",
                payload={"projection": "execution_status", "state": command.state,
                         "revision": lease.control_revision})
            session.commit()

    def complete_control_with_projection(self, token: LeaseToken, command_id: str, *,
                                         deployment_id: int, armed: bool,
                                         success: bool = True) -> None:
        """Atomically commit the durable deployment projection and control outcome."""
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token)
            command = session.scalar(locked_rows(select(AccountExecutionCommand).where(
                AccountExecutionCommand.command_id == command_id,
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch == token.fence_epoch,
                AccountExecutionCommand.state == "processing"), session))
            expected_desired = "armed" if armed else "disabled"
            if (command is None or command.expected_revision != lease.control_revision
                    or lease.desired_state != expected_desired):
                raise StaleLease("control projection was superseded")
            deployment = session.scalar(locked_rows(select(Deployment).where(
                Deployment.id == deployment_id,
                Deployment.owner_id == token.owner_id,
                Deployment.broker_account_id == token.broker_account_id), session))
            if deployment is None:
                raise StaleLease("control deployment projection is unavailable")
            deployment.armed = armed
            command.state = "resolved" if success else "failed"
            command.resolved_at = command.updated_at = now
            lease.effective_state = expected_desired
            lease.updated_at = now
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_control", aggregate_id=command.command_id,
                event_type="execution.control.changed",
                producer_key=f"control:{command.command_id}:projection",
                payload={"projection": "execution_status", "state": command.state,
                         "revision": lease.control_revision, "armed": armed})
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="deployment", aggregate_id=str(deployment_id),
                event_type="execution.deployment.changed",
                producer_key=f"control:{command.command_id}:deployment",
                payload={"projection": "deployments",
                         "state": "armed" if armed else "disabled", "armed": armed})
            session.commit()

    def prepare_command(self, token: LeaseToken, *, kind: str, target_id: str,
                        idempotency_key: str, request_digest: str,
                        actor_user_id: str = "", broker_tag: str = "",
                        requested_qty: int | None = None, requested_side: str = "",
                        requested_trigger: float | None = None,
                        capital_reservation_id: str | None = None) -> AccountExecutionCommand:
        if not kind or len(kind) > 32 or not target_id or len(target_id) > 96:
            raise ValueError("bounded command kind and target are required")
        if not idempotency_key or len(idempotency_key) > 96:
            raise ValueError("bounded idempotency identity is required")
        if (len(request_digest) != 64 or request_digest != request_digest.lower()
                or any(ch not in "0123456789abcdef" for ch in request_digest)):
            raise ValueError("request digest must be 64 lowercase hexadecimal characters")
        if len(actor_user_id) > 64:
            raise ValueError("actor identity is too long")
        if len(broker_tag) > 32:
            raise ValueError("broker tag is too long")
        if capital_reservation_id is not None and (
                not capital_reservation_id or len(capital_reservation_id) > 64):
            raise ValueError("bounded capital reservation identity is required")
        if capital_reservation_id is not None and kind != "place_order":
            raise ValueError("capital reservations bind only new order preparation")
        if capital_reservation_id is not None and (
                type(requested_qty) is not int or requested_qty <= 0):
            raise RecoveryRequired(
                "command quantity does not match capital reservation")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token, lock=capital_reservation_id is not None)
            if lease.state != "active" and not kind.startswith("recovery_"):
                raise RecoveryRequired("new broker mutation denied during recovery")
            existing = session.scalar(select(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.idempotency_key == idempotency_key,
            ))
            if existing is not None:
                if existing.request_digest != request_digest or existing.kind != kind:
                    raise ValueError("idempotency identity reused with different command")
                if existing.state == "sent_unknown":
                    raise AmbiguousBrokerOutcome("ambiguous command requires reconciliation")
                raise LeaseUnavailable("command identity was already submitted")
            reservation = None
            if capital_reservation_id is not None:
                reservation = session.scalar(locked_rows(select(CapitalReservationRecord).where(
                    CapitalReservationRecord.reservation_id == capital_reservation_id,
                    CapitalReservationRecord.owner_id == token.owner_id,
                    CapitalReservationRecord.broker_account_id == token.broker_account_id,
                    CapitalReservationRecord.fence_epoch == token.fence_epoch,
                    CapitalReservationRecord.state == "held",
                    CapitalReservationRecord.command_id.is_(None),
                ), session))
                if reservation is None or reservation.expires_at <= now:
                    raise RecoveryRequired(
                        "exact active capital reservation is unavailable for command preparation")
                candidate = session.get(
                    CandidateIntentRecord, reservation.candidate_intent_id)
                if candidate is None or (
                        candidate.owner_id, candidate.broker_account_id,
                        candidate.book, candidate.fence_epoch) != (
                        token.owner_id, token.broker_account_id,
                        reservation.book, reservation.fence_epoch) \
                        or target_id != candidate.target_position_request_id:
                    raise RecoveryRequired("command target does not match capital reservation")
                if requested_qty is None or requested_qty != abs(
                        reservation.admitted_quantity):
                    raise RecoveryRequired("command quantity does not match capital reservation")
                expected_side = "BUY" if candidate.requested_quantity > 0 else "SELL"
                expected_direction = "LONG" if expected_side == "BUY" else "SHORT"
                if candidate.direction != expected_direction \
                        or requested_side != expected_side:
                    raise RecoveryRequired("command side does not match capital reservation")
            command = AccountExecutionCommand(
                command_id=uuid.uuid4().hex,
                idempotency_key=idempotency_key, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id, fence_epoch=token.fence_epoch,
                cell_id=token.cell_id, worker_id=token.worker_id, kind=kind,
                target_id=target_id, request_digest=request_digest,
                broker_tag=broker_tag,
                requested_qty=requested_qty, requested_side=requested_side,
                requested_trigger=requested_trigger,
                state="prepared", actor_user_id=actor_user_id,
                created_at=now, updated_at=now)
            session.add(command)
            if reservation is not None:
                from app.ir.hashing import content_address

                previous_state = reservation.state
                reservation.state = "submission_pending"
                reservation.command_id = command.command_id
                reservation.revision += 1
                event_id = hashlib.sha256(
                    (f"reservation-event\0{reservation.reservation_id}\0"
                     f"{reservation.revision}").encode("utf-8")).hexdigest()
                evidence_address = f"sha256:{request_digest}"
                event_document = {
                    "schema": "strategy-os.capital-reservation-event/v1",
                    "event_id": event_id,
                    "reservation_address": reservation.reservation_address,
                    "revision": reservation.revision,
                    "from_state": previous_state,
                    "to_state": reservation.state,
                    "consumed_minor": reservation.consumed_minor,
                    "consumed_quantity": reservation.consumed_quantity,
                    "fence_epoch": token.fence_epoch,
                    "evidence_address": evidence_address,
                    "reason_code": "COMMAND_PREPARED",
                    "occurred_at": now.isoformat(timespec="microseconds"),
                }
                session.add(CapitalReservationEventRecord(
                    event_id=event_id,
                    event_address=content_address(event_document),
                    reservation_id=reservation.reservation_id,
                    revision=reservation.revision,
                    from_state=previous_state,
                    to_state=reservation.state,
                    consumed_minor=reservation.consumed_minor,
                    consumed_quantity=reservation.consumed_quantity,
                    fence_epoch=token.fence_epoch,
                    evidence_address=evidence_address,
                    reason_code="COMMAND_PREPARED",
                    occurred_at=now,
                ))
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_command", aggregate_id=command.command_id,
                event_type="execution.lifecycle.changed",
                producer_key=f"command:{command.command_id}:prepared",
                payload={"projection": "execution_status", "state": "prepared",
                         "fence_epoch": token.fence_epoch})
            if reservation is not None:
                _append_execution_change(
                    session, owner_id=token.owner_id,
                    broker_account_id=token.broker_account_id,
                    aggregate_type="capital_reservation",
                    aggregate_id=reservation.reservation_id,
                    event_type="execution.money.changed",
                    producer_key=(f"capital-reservation:{reservation.reservation_id}:"
                                  f"{reservation.revision}"),
                    payload={
                        "projection": "capital_reservation",
                        "state": reservation.state,
                        "revision": reservation.revision,
                        "fence_epoch": token.fence_epoch,
                        "command_id": command.command_id,
                    },
                )
            session.commit()
            return command

    def transition_command(self, token: LeaseToken, command_id: str, *, from_state: str,
                           to_state: str, broker_order_id: str = "",
                           protective_id: str = "", error_code: str = "") -> None:
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            _, now = self._current(session, token)
            values: dict[str, Any] = {"state": to_state, "updated_at": now,
                                      "error_code": error_code[:64]}
            if to_state == "sent_unknown":
                values["sent_at"] = now
            if to_state == "acknowledged":
                values.update(sent_at=now, acknowledged_at=now,
                              broker_order_id=broker_order_id[:64],
                              protective_id=protective_id[:64])
            if to_state in {"resolved", "cancelled", "failed"}:
                values["resolved_at"] = now
            result = session.execute(update(AccountExecutionCommand).where(
                AccountExecutionCommand.command_id == command_id,
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch == token.fence_epoch,
                AccountExecutionCommand.cell_id == token.cell_id,
                AccountExecutionCommand.worker_id == token.worker_id,
                AccountExecutionCommand.state == from_state,
            ).values(**values))
            if result.rowcount != 1:
                session.rollback()
                raise StaleLease("command transition lost its exact fence predicate")
            if to_state in {"sent_unknown", "resolved", "failed", "blocked"}:
                _append_execution_change(
                    session, owner_id=token.owner_id,
                    broker_account_id=token.broker_account_id,
                    aggregate_type="execution_command", aggregate_id=command_id,
                    event_type="execution.lifecycle.changed",
                    producer_key=f"command:{command_id}:{to_state}",
                    payload={"projection": "execution_status", "state": to_state,
                             "fence_epoch": token.fence_epoch})
            session.commit()

    def resolve_acknowledged_evidence(self, token: LeaseToken, broker_identity: str,
                                      evidence_digest: str) -> None:
        """Resolve only the command whose exact broker identity now has durable evidence."""
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            self._current(session, token)
            command = session.scalar(locked_rows(select(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch == token.fence_epoch,
                AccountExecutionCommand.state == "acknowledged",
                AccountExecutionCommand.broker_order_id == str(broker_identity)), session))
            if command is None:
                raise StaleLease("no acknowledged command matches durable broker evidence")
            now = _db_now(session)
            command.state = "resolved"
            command.resolved_at = now
            command.resolved_by_epoch = token.fence_epoch
            command.resolution_digest = evidence_digest
            command.updated_at = now
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_command", aggregate_id=command.command_id,
                event_type="execution.lifecycle.changed",
                producer_key=f"command:{command.command_id}:evidence-resolved",
                payload={"projection": "execution_status", "state": "resolved",
                         "fence_epoch": token.fence_epoch})
            session.commit()

    def mark_ambiguous(self, token: LeaseToken, command_id: str, error_code: str) -> None:
        """Atomically journal uncertainty and strip all mutation authority."""
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token)
            command = session.scalar(locked_rows(select(AccountExecutionCommand).where(
                AccountExecutionCommand.command_id == command_id,
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch == token.fence_epoch,
                AccountExecutionCommand.state == "prepared"), session))
            if command is None:
                raise StaleLease("ambiguous command lost exact prepared identity")
            command.state = "sent_unknown"
            command.sent_at = now
            command.updated_at = now
            command.error_code = error_code[:64]
            lease.state = "blocked"
            lease.desired_state = lease.effective_state = "disabled"
            lease.blocked_at = now
            lease.block_reason = "ambiguous broker outcome"
            lease.updated_at = now
            _history(session, lease, "block", now, "ambiguous broker outcome")
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_command", aggregate_id=command.command_id,
                event_type="execution.lifecycle.changed",
                producer_key=f"command:{command.command_id}:sent-unknown",
                payload={"projection": "execution_status", "state": "sent_unknown",
                         "fence_epoch": token.fence_epoch})
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_lease", aggregate_id=token.broker_account_id,
                event_type="execution.lease.changed",
                producer_key=f"lease:{token.owner_id}:{token.broker_account_id}:{token.fence_epoch}:ambiguous-block",
                payload={"projection": "execution_status", "state": "blocked",
                         "fence_epoch": token.fence_epoch})
            session.commit()

    def reconcile_prior_command(self, token: LeaseToken, command_id: str, *,
                                expected_state: str, outcome: str,
                                evidence_digest: str) -> None:
        if outcome not in {"resolved", "blocked"} or len(evidence_digest) != 64:
            raise ValueError("bounded reconciliation outcome and digest required")
        with self.sessions() as session:
            begin_after_clean_reads(session, scope=_scope(token.owner_id, token.broker_account_id))
            lease, now = self._current(session, token)
            if lease.state != "recovering":
                raise RecoveryRequired("prior commands reconcile only during recovery")
            command = session.scalar(locked_rows(select(AccountExecutionCommand).where(
                AccountExecutionCommand.command_id == command_id,
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id), session))
            if command is None or command.fence_epoch >= token.fence_epoch:
                raise StaleLease("command is not prior-epoch evidence")
            if command.state != expected_state:
                raise StaleLease("prior command state changed")
            command.state = outcome
            command.resolved_at = now
            command.resolved_by_epoch = token.fence_epoch
            command.resolution_digest = evidence_digest
            command.updated_at = now
            if outcome == "blocked":
                lease.state = "blocked"
                lease.desired_state = lease.effective_state = "disabled"
                lease.block_reason = "reconciliation discrepancy"
                lease.blocked_at = now
                _history(session, lease, "block", now, "reconciliation discrepancy")
            _append_execution_change(
                session, owner_id=token.owner_id,
                broker_account_id=token.broker_account_id,
                aggregate_type="execution_command", aggregate_id=command.command_id,
                event_type="execution.lifecycle.changed",
                producer_key=f"command:{command.command_id}:reconcile:{token.fence_epoch}",
                payload={"projection": "execution_status", "state": outcome,
                         "fence_epoch": token.fence_epoch})
            session.commit()

    def reconcile_prior_commands_from_snapshot(self, token: LeaseToken, *,
                                               orders: list[Mapping[str, Any]],
                                               protection: list[Mapping[str, Any]]) -> None:
        """Consume prior-epoch command blockers from one strict broker snapshot.

        An exact id/tag match proves a visible effect.  A cancel whose exact target is
        absent proves the requested end state.  Everything else is discrepant and blocks;
        it is never converted into permission to retry.
        """
        with self.sessions() as session:
            lease, _ = self._current(session, token)
            if lease.state != "recovering":
                raise RecoveryRequired("snapshot command reconciliation requires recovery")
            commands = list(session.scalars(select(AccountExecutionCommand).where(
                AccountExecutionCommand.owner_id == token.owner_id,
                AccountExecutionCommand.broker_account_id == token.broker_account_id,
                AccountExecutionCommand.fence_epoch < token.fence_epoch,
                AccountExecutionCommand.state.in_(("prepared", "sent_unknown", "acknowledged")),
                ~AccountExecutionCommand.kind.like("control_%"),
            ).order_by(AccountExecutionCommand.fence_epoch,
                       AccountExecutionCommand.created_at,
                       AccountExecutionCommand.command_id)))
        evidence = [*orders, *protection]
        for command in commands:
            pool = protection if "protective" in command.kind else orders
            def row_id(row):
                return str(row.get("id") or row.get("order_id") or row.get("trigger_id") or "")
            correlated_ids = {str(value) for value in
                              (command.broker_order_id, command.protective_id, command.target_id)
                              if value}
            matches = [row for row in pool if row_id(row) in correlated_ids
                       or (command.broker_tag and str(row.get("tag") or "") == command.broker_tag)]
            status = str(matches[0].get("status") or "").lower() if len(matches) == 1 else ""
            dead = status in {"dead", "cancelled", "canceled", "complete", "completed",
                              "rejected", "expired"}
            fields_match = len(matches) == 1
            if fields_match and command.requested_qty is not None:
                fields_match = int(matches[0].get("qty", matches[0].get("quantity", -1)) or -1) == command.requested_qty
            if fields_match and command.requested_side:
                fields_match = str(matches[0].get("side") or matches[0].get(
                    "transaction_type") or "").upper() == command.requested_side
            if fields_match and command.requested_trigger is not None:
                try:
                    fields_match = Decimal(str(matches[0].get("trigger_price"))) == Decimal(
                        str(command.requested_trigger))
                except InvalidOperation:
                    fields_match = False
            if command.kind in {"place_protective", "modify_protective"}:
                exact = fields_match and not dead
            elif command.kind in {"cancel_order", "cancel_protective"}:
                exact = (not matches and bool(command.target_id)) or (fields_match and dead)
            else:
                exact = fields_match
            outcome = "resolved" if exact else "blocked"
            digest = hashlib.sha256(json.dumps({
                "command_id": command.command_id,
                "outcome": outcome,
                "matched_ids": sorted(row_id(row) for row in matches),
                "match_count": len(matches),
            }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.reconcile_prior_command(
                token, command.command_id, expected_state=command.state,
                outcome=outcome, evidence_digest=digest)
            if outcome == "blocked":
                raise RecoveryRequired("prior broker command disagrees with strict snapshot")


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {
            str(k): ("[redacted]" if any(part in str(k).lower()
                                         for part in ("token", "secret", "credential", "password"))
                     else _safe_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_safe_value(item) for item in value]
    if hasattr(value, "value") and isinstance(value.value, (bool, int, float, str)):
        return value.value
    if hasattr(value, "__dict__"):
        return {k: _safe_value(v) for k, v in vars(value).items()
                if not k.lower().endswith(("token", "secret", "credential"))}
    return type(value).__name__


def command_digest(kind: str, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> str:
    raw = json.dumps({"kind": kind, "args": _safe_value(args), "kwargs": _safe_value(kwargs)},
                     sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


class FencedBrokerGateway:
    """The sole point at which a current epoch releases a broker mutation."""
    def __init__(self, repository: LeaseRepository, token: LeaseToken,
                 on_acknowledged: Callable[[str], None] | None = None):
        self.repository = repository
        self.token = token
        self.on_acknowledged = on_acknowledged

    def call(self, *, kind: str, target_id: str, operation: Callable[..., Any],
             args: tuple[Any, ...] = (), kwargs: Mapping[str, Any] | None = None,
             idempotency_key: str | None = None,
             broker_tag: str | None = None) -> Any:
        call_kwargs = dict(kwargs or {})
        digest = command_digest(kind, args, call_kwargs)
        # A command identity names one release to the wire, not the semantic request.
        # Callers that need retry identity must supply it explicitly; otherwise two
        # legitimate later operations with equal parameters must remain distinct.
        identity = idempotency_key or uuid.uuid4().hex
        command = self.repository.prepare_command(
            self.token, kind=kind, target_id=target_id,
            idempotency_key=identity, request_digest=digest,
            broker_tag=str(broker_tag if broker_tag is not None else
                           (call_kwargs.get("tag") or
                            (getattr(args[0], "tag", "") if args else ""))),
            requested_qty=(call_kwargs.get("qty", call_kwargs.get("quantity"))
                           or (getattr(args[0], "qty", None) if args else None)),
            requested_side=str(call_kwargs.get("side")
                               or (getattr(args[0], "side", "") if args else "")).upper(),
            requested_trigger=call_kwargs.get("trigger_price"))
        # Exact-token recheck occurs after prepare and immediately before network I/O.
        self.repository.assert_current(self.token, active=not kind.startswith("recovery_"))
        try:
            result = operation(*args, **call_kwargs)
        except Exception as exc:
            try:
                self.repository.mark_ambiguous(
                    self.token, command.command_id, type(exc).__name__)
            except Exception:
                # The prepared row remains recovery-blocking. Never expose this as a normal
                # stale/DB failure because the request may already be at the venue.
                pass
            raise AmbiguousBrokerOutcome(
                "broker acknowledgement is unknown; command requires reconciliation") from exc
        broker_id = "" if result is None else str(getattr(result, "order_id", result))
        try:
            self.repository.transition_command(
                self.token, command.command_id, from_state="prepared", to_state="acknowledged",
                broker_order_id=broker_id)
        except Exception as exc:
            try:
                self.repository.mark_ambiguous(
                    self.token, command.command_id, type(exc).__name__)
            except Exception:
                pass
            # The request may have reached the venue. The still-prepared row deliberately
            # remains recovery-blocking; reporting ordinary failure could invite a duplicate.
            raise AmbiguousBrokerOutcome(
                "broker call returned but durable acknowledgement was not recorded") from exc
        return result


class FencedTransportProxy:
    """Wrap one transport and close only its declared mutation methods."""
    def __init__(self, transport: Any, gateway: FencedBrokerGateway,
                 mutation_methods: Mapping[str, str]):
        self._transport = transport
        self._gateway = gateway
        self._mutations = dict(mutation_methods)

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._transport, name)
        if name not in self._mutations:
            return value

        def fenced(*args, **kwargs):
            target = kwargs.get("order_id") or kwargs.get("protective_id")
            if not target and args:
                if name == "cancel":
                    target = args[0]
                elif "protective" in name and len(args) > 1:
                    target = args[1]
                else:
                    target = getattr(args[0], "tag", "")
            wire_tag = str(kwargs.get("tag") or (getattr(args[0], "tag", "") if args else ""))
            if not target and name == "place_protective_stop":
                target = f"{wire_tag}:{kwargs.get('tradingsymbol', '')}".strip(":")
            target = str(target or wire_tag or "account")
            return self._gateway.call(kind=self._mutations[name], target_id=target,
                                      operation=value, args=args, kwargs=kwargs,
                                      broker_tag=wire_tag)
        return fenced


BROKER_CLIENT_MUTATIONS = {"place": "place_order", "cancel": "cancel_order"}
VENUE_MUTATIONS = {
    "place_protective_stop": "place_protective",
    "cancel_protective_stop": "cancel_protective",
    "modify_protective_stop": "modify_protective",
}


def validate_recovery_snapshot(durable_positions, account_positions, protection_by_kind,
                               kind_for_position, protective_id_for_position) -> None:
    if account_positions is None or protection_by_kind is None:
        raise RecoveryRequired("broker recovery snapshot is unreadable")
    for position in durable_positions:
        matches = [row for row in account_positions
                   if str(row.get("tradingsymbol") or row.get("symbol") or "")
                   == position.tradingsymbol]
        if len(matches) != 1:
            raise RecoveryRequired("broker position identity is missing or ambiguous")
        try:
            actual_quantity = Decimal(str(matches[0].get(
                "quantity", matches[0].get("qty"))))
            durable_quantity = Decimal(str(position.qty))
        except (InvalidOperation, TypeError, ValueError):
            raise RecoveryRequired("broker position quantity is unreadable") from None
        if actual_quantity != actual_quantity.to_integral_value() or durable_quantity <= 0:
            raise RecoveryRequired("broker position quantity is ambiguous")
        expected_quantity = (-durable_quantity if
                             getattr(position, "segment", "") in {"equity_intraday", "index_futures"}
                             and position.direction == "SHORT" else durable_quantity)
        if actual_quantity != expected_quantity:
            raise RecoveryRequired("broker position quantity mismatch")
        expected_id = protective_id_for_position(position)
        if not expected_id:
            raise RecoveryRequired("durable protective identity is missing")
        kind = kind_for_position(position)
        rows = protection_by_kind.get(kind)
        if rows is None:
            raise RecoveryRequired("protective inventory is unreadable")
        stop = [row for row in rows if str(row.get("id") or row.get("order_id")
                                           or row.get("trigger_id") or "") == str(expected_id)]
        if len(stop) != 1:
            raise RecoveryRequired("protective inventory identity is missing or ambiguous")
        try:
            protective_quantity = Decimal(str(stop[0].get("qty", stop[0].get("quantity"))))
            actual_trigger = Decimal(str(stop[0].get("trigger_price")))
            expected_trigger = Decimal(str(position.stop_price))
        except (InvalidOperation, TypeError, ValueError):
            raise RecoveryRequired("protective inventory values are unreadable") from None
        if (protective_quantity != durable_quantity
                or protective_quantity != protective_quantity.to_integral_value()):
            raise RecoveryRequired("protective inventory quantity mismatch")
        if actual_trigger != expected_trigger:
            raise RecoveryRequired("protective inventory trigger mismatch")
        if str(stop[0].get("status") or "").lower() in {
                "dead", "cancelled", "canceled", "complete", "completed", "rejected", "expired"}:
            raise RecoveryRequired("durable protection is no longer live")
        expected_side = "SELL" if position.direction == "LONG" else "BUY"
        actual_side = str(stop[0].get("side") or stop[0].get("transaction_type") or "").upper()
        if actual_side != expected_side:
            raise RecoveryRequired("protective inventory side mismatch")


def _assert_bound_write_fence(session: Session, *, force: bool = False) -> None:
    token = session.info.get("execution_lease_token")
    if token is None or (not force and not has_pending_writes(session)):
        return
    lock_suffix = " FOR UPDATE" if session.get_bind().dialect.name == "postgresql" else ""
    row = session.connection().execute(text("""
        SELECT state
        FROM account_execution_leases
        WHERE owner_id = :owner_id AND broker_account_id = :account_id
          AND fence_epoch = :epoch AND cell_id = :cell_id AND worker_id = :worker_id
          AND state IN ('recovering', 'active')
          AND expires_at > CURRENT_TIMESTAMP
    """ + lock_suffix), {
        "owner_id": token.owner_id, "account_id": token.broker_account_id,
        "epoch": token.fence_epoch, "cell_id": token.cell_id, "worker_id": token.worker_id,
    }).first()
    if row is None:
        raise StaleLease("durable money/evidence write rejected by execution fence")
    session.info["execution_fence_locked"] = True


@event.listens_for(Session, "do_orm_execute")
def _lock_bound_core_dml(execute_state) -> None:
    if (bool(getattr(execute_state.statement, "is_dml", False))
            and execute_state.session.info.get("execution_lease_token") is not None
            and not execute_state.session.info.get("execution_fence_locked")):
        _assert_bound_write_fence(execute_state.session, force=True)


@event.listens_for(Session, "after_transaction_end")
def _clear_bound_fence_lock(session: Session, transaction) -> None:
    if transaction.parent is None:
        session.info.pop("execution_fence_locked", None)


@event.listens_for(Session, "before_flush")
def _fence_bound_money_flush(session: Session, _flush_context, _instances) -> None:
    _assert_bound_write_fence(session)


@event.listens_for(Session, "before_commit")
def _fence_bound_money_commit(session: Session) -> None:
    _assert_bound_write_fence(session)
