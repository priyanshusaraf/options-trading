"""The database-backed, owner-first research operation scheduler seam."""
from __future__ import annotations

import datetime as dt
import json
import uuid
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, case, func, or_, select, text, update
from sqlalchemy.orm import Session

from research.domain.models import ResearchOperation

_TRIGGERS = frozenset(("nightly", "manual", "generated"))
_STAGES = frozenset(("startup", "planning", "collection", "experiments", "reports", "generation", "completed"))
_ACTIVE = frozenset(("pending", "running"))
_MAX_PLAN_BYTES = 65536
_MAX_ERROR_BYTES = 4096
_MAX_PENDING_PER_OWNER = 16
_MAX_RUNNING_PER_OWNER = 4


def _instant(value: dt.datetime | None) -> dt.datetime:
    return value or dt.datetime.now(dt.UTC)


def _json(value: Any, *, limit: int) -> str:
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                            allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("operation payload is not strict JSON") from exc
    if len(result.encode()) > limit:
        raise ValueError("operation payload exceeds its bounded contract")
    return result


def _error_payload(value: dict[str, Any]) -> dict[str, str]:
    """Persist a closed, bounded error DTO rather than exception text/objects."""
    if not isinstance(value, dict) or not set(value) <= {"code", "message", "stage"}:
        raise ValueError("operation error payload is invalid")
    code = value.get("code")
    message = value.get("message", "research operation failed")
    stage = value.get("stage")
    if (not isinstance(code, str) or not code or len(code) > 120
            or not isinstance(message, str) or not message or len(message) > 2000
            or (stage is not None and (not isinstance(stage, str) or stage not in _STAGES))):
        raise ValueError("operation error payload is invalid")
    result = {"code": code, "message": message}
    if stage is not None:
        result["stage"] = stage
    return result


def _load(value: str | None, expected, default):
    try:
        decoded = json.loads(value or "null")
    except (TypeError, ValueError):
        return default
    return decoded if isinstance(decoded, expected) else default


@dataclass(frozen=True)
class OperationView:
    operation_id: str
    trigger: str
    plan: dict[str, Any]
    status: str
    stage: str
    error: dict[str, Any] | None
    build: str
    provider_mode: str
    completed_run_ids: list[int]
    created_at: dt.datetime
    queued_at: dt.datetime
    started_at: dt.datetime | None
    heartbeat_at: dt.datetime | None
    completed_at: dt.datetime | None
    cancel_requested_at: dt.datetime | None
    attempt_count: int
    claim_token: str | None = None


def _view(row: ResearchOperation, *, claim: bool = False) -> OperationView:
    return OperationView(row.operation_id, row.trigger, _load(row.plan_json, dict, {}),
        row.status, row.stage, _load(row.error_json, dict, None) if row.error_json else None,
        row.build, row.provider_mode, _load(row.completed_run_ids_json, list, []),
        row.created_at, row.queued_at, row.started_at, row.heartbeat_at, row.completed_at,
        row.cancel_requested_at, row.attempt_count, row.claim_token if claim else None)


class ResearchOperationRepository:
    """All lookups begin with owner scope and all worker writes are fenced."""
    def __init__(self, session: Session):
        self.session = session

    def enqueue(self, *, owner_id: str, trigger: str, plan: dict[str, Any], build: str,
                provider_mode: str, operation_id: str | None = None,
                now: dt.datetime | None = None) -> OperationView:
        if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 64:
            raise ValueError("owner_id is invalid")
        if trigger not in _TRIGGERS:
            raise ValueError("operation trigger is invalid")
        value = operation_id or uuid.uuid4().hex
        if not isinstance(value, str) or not value or len(value) > 64:
            raise ValueError("operation_id is invalid")
        instant = _instant(now)
        pending = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.status == "pending",
        )) or 0
        running = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.status == "running",
        )) or 0
        if pending >= _MAX_PENDING_PER_OWNER or running >= _MAX_RUNNING_PER_OWNER:
            raise RuntimeError("research operation admission capacity is exhausted")
        row = ResearchOperation(owner_id=owner_id, operation_id=value, trigger=trigger,
            plan_json=_json(plan, limit=_MAX_PLAN_BYTES), build=str(build)[:40] or "unknown",
            provider_mode=str(provider_mode)[:80] or "unknown", created_at=instant, queued_at=instant)
        self.session.add(row); self.session.commit()
        return _view(row)

    def get(self, operation_id: str, *, owner_id: str) -> OperationView | None:
        row = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id, ResearchOperation.operation_id == operation_id))
        return _view(row) if row else None

    def list(self, *, owner_id: str, limit: int = 32) -> list[OperationView]:
        if not isinstance(limit, int) or not 1 <= limit <= 128:
            raise ValueError("operation history limit is invalid")
        rows = self.session.scalars(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id).order_by(
            ResearchOperation.created_at.desc(), ResearchOperation.operation_id.desc()).limit(limit)).all()
        return [_view(row) for row in rows]

    def latest(self, *, owner_id: str) -> OperationView | None:
        rows = self.list(owner_id=owner_id, limit=1)
        return rows[0] if rows else None

    def latest_active(self, *, owner_id: str) -> OperationView | None:
        row = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.status.in_(tuple(_ACTIVE)),
        ).order_by(ResearchOperation.queued_at.desc(),
                   ResearchOperation.operation_id.desc()).limit(1))
        return _view(row) if row else None

    def latest_terminal(self, *, owner_id: str) -> OperationView | None:
        row = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.status.in_(("completed", "failed", "cancelled")),
        ).order_by(ResearchOperation.completed_at.desc(),
                   ResearchOperation.operation_id.desc()).limit(1))
        return _view(row) if row else None

    def claim_next(self, *, owner_id: str, worker_id: str, now: dt.datetime | None = None,
                   lease_seconds: int = 60) -> OperationView | None:
        if not isinstance(worker_id, str) or not worker_id or lease_seconds < 1:
            raise ValueError("claim arguments are invalid")
        instant = _instant(now)
        candidate = self.session.scalar(select(ResearchOperation.operation_id).where(
            ResearchOperation.owner_id == owner_id,
            or_(ResearchOperation.status == "pending", and_(ResearchOperation.status == "running", ResearchOperation.claim_expires_at < instant)),
        ).order_by(ResearchOperation.queued_at, ResearchOperation.operation_id).limit(1))
        if candidate is None:
            return None
        token = uuid.uuid4().hex
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id, ResearchOperation.operation_id == candidate,
            or_(ResearchOperation.status == "pending", and_(ResearchOperation.status == "running", ResearchOperation.claim_expires_at < instant)),
        ).values(status="running", started_at=func.coalesce(ResearchOperation.started_at, instant),
                 heartbeat_at=instant, claim_token=token, claimed_by=worker_id[:128],
                 claim_expires_at=instant + dt.timedelta(seconds=lease_seconds),
                 attempt_count=ResearchOperation.attempt_count + 1))
        self.session.commit()
        if changed.rowcount != 1:
            return None
        row = self.session.scalar(select(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.operation_id == candidate))
        return _view(row, claim=True)

    def claim_operation(self, operation_id: str, *, owner_id: str, worker_id: str,
                        now: dt.datetime | None = None,
                        lease_seconds: int = 60) -> OperationView | None:
        """Claim this exact durable operation, never whichever job sorts first.

        Enqueue-and-start callers must not accidentally receive a fencing token for
        an older pending operation.  Restart dispatchers deliberately use
        :meth:`claim_next`; new entry points use this target-bound variant.
        """
        if (not isinstance(operation_id, str) or not operation_id or len(operation_id) > 64
                or not isinstance(worker_id, str) or not worker_id or lease_seconds < 1):
            raise ValueError("claim arguments are invalid")
        instant = _instant(now)
        token = uuid.uuid4().hex
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.cancel_requested_at.is_(None),
            or_(ResearchOperation.status == "pending", and_(
                ResearchOperation.status == "running",
                ResearchOperation.claim_expires_at < instant)),
        ).values(status="running", started_at=func.coalesce(ResearchOperation.started_at, instant),
                 heartbeat_at=instant, claim_token=token, claimed_by=worker_id[:128],
                 claim_expires_at=instant + dt.timedelta(seconds=lease_seconds),
                 attempt_count=ResearchOperation.attempt_count + 1))
        self.session.commit()
        if changed.rowcount != 1:
            return None
        row = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id))
        return _view(row, claim=True)

    def _write(self, operation_id: str, *, owner_id: str, token: str, now: dt.datetime | None,
               values: dict[str, Any]) -> bool:
        instant = _instant(now)
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id, ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running", ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        ).values(**values))
        self.session.commit(); return changed.rowcount == 1

    def heartbeat(self, operation_id: str, *, owner_id: str, token: str, now: dt.datetime | None = None, lease_seconds: int = 60) -> bool:
        instant = _instant(now)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant,
            values={"heartbeat_at": instant, "claim_expires_at": instant + dt.timedelta(seconds=lease_seconds)})

    def metrics(self, *, owner_id: str, now: dt.datetime | None = None) -> dict[str, int]:
        """Owner-local bounded operational counters; never label with tenant id."""
        instant = _instant(now)
        # Compact count queries keep this bounded even if history grows.
        queued = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "pending")) or 0
        active = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "running")) or 0
        expired = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "running", ResearchOperation.claim_expires_at < instant)) or 0
        terminals = dict(self.session.execute(
            select(ResearchOperation.status, func.count()).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.status.in_(("completed", "failed", "cancelled")),
            ).group_by(ResearchOperation.status)
        ).all())
        return {"queued": int(queued), "active": int(active), "expired_claims": int(expired),
                "completed": int(terminals.get("completed", 0)),
                "failed": int(terminals.get("failed", 0)),
                "cancelled": int(terminals.get("cancelled", 0))}

    def transition(self, operation_id: str, *, owner_id: str, token: str, stage: str, now: dt.datetime | None = None) -> bool:
        if stage not in _STAGES - {"completed"}: raise ValueError("operation stage is invalid")
        instant = _instant(now)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant, values={"stage": stage, "heartbeat_at": instant})

    def complete(self, operation_id: str, *, owner_id: str, token: str, now: dt.datetime | None = None) -> bool:
        instant = _instant(now)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant, values={"status": "completed", "stage": "completed", "completed_at": instant, "heartbeat_at": instant, "claim_token": None, "claimed_by": None, "claim_expires_at": None})

    def add_completed_run(self, operation_id: str, *, owner_id: str, token: str, run_id: int,
                          now: dt.datetime | None = None) -> bool:
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
            raise ValueError("completed run id is invalid")
        instant = _instant(now)
        # One conditional write carries the same cancellation/fence predicate as
        # every other worker mutation.  JSON1 is part of SQLite's supported
        # runtime here; `json_each` makes repeat delivery idempotent.
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        ).values(
            completed_run_ids_json=case(
                (text("EXISTS (SELECT 1 FROM json_each(research_operation.completed_run_ids_json) WHERE value = :completed_run_id)"),
                 ResearchOperation.completed_run_ids_json),
                else_=func.json_insert(ResearchOperation.completed_run_ids_json, "$[#]", run_id),
            ),
            heartbeat_at=instant,
        ), {"completed_run_id": run_id})
        self.session.commit()
        return changed.rowcount == 1

    def fail(self, operation_id: str, *, owner_id: str, token: str, error: dict[str, Any],
             now: dt.datetime | None = None) -> bool:
        instant = _instant(now)
        safe_error = _error_payload(error)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant,
            values={"status": "failed", "completed_at": instant, "heartbeat_at": instant,
                    "error_json": _json(safe_error, limit=_MAX_ERROR_BYTES), "claim_token": None,
                    "claimed_by": None, "claim_expires_at": None})

    def request_cancel(self, operation_id: str, *, owner_id: str, now: dt.datetime | None = None) -> bool:
        changed = self.session.execute(update(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.operation_id == operation_id, ResearchOperation.status.in_(_ACTIVE)).values(cancel_requested_at=_instant(now)))
        self.session.commit(); return changed.rowcount == 1

    def reconcile_expired(self, *, owner_id: str, now: dt.datetime | None = None) -> int:
        instant = _instant(now)
        pending = self.session.execute(update(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "pending", ResearchOperation.cancel_requested_at.is_not(None)).values(status="cancelled", completed_at=instant))
        active = self.session.execute(update(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "running", ResearchOperation.cancel_requested_at.is_not(None), ResearchOperation.claim_expires_at < instant).values(status="cancelled", completed_at=instant, claim_token=None, claimed_by=None, claim_expires_at=None))
        self.session.commit(); return (pending.rowcount or 0) + (active.rowcount or 0)


class DurableOperationRecorder:
    """Adapter used by runtime flows; optional receipt mirroring stays elsewhere."""
    def __init__(self, repository: ResearchOperationRepository, *, owner_id: str,
                 operation_id: str, token: str):
        self.repository, self.owner_id, self.operation_id, self.token = repository, owner_id, operation_id, token
        self._watchdog_stop = threading.Event()
        self._claim_lost = threading.Event()
        self._watchdog: threading.Thread | None = None

    @classmethod
    def start(cls, repository: ResearchOperationRepository, *, owner_id: str, trigger: str,
              build: str, provider_mode: str, worker_id: str, plan: dict[str, Any],
              operation_id: str | None = None) -> "DurableOperationRecorder":
        queued = repository.enqueue(owner_id=owner_id, trigger=trigger, build=build,
                                  provider_mode=provider_mode, plan=plan, operation_id=operation_id)
        claimed = repository.claim_operation(queued.operation_id, owner_id=owner_id,
                                             worker_id=worker_id)
        if claimed is None or claimed.operation_id != queued.operation_id or claimed.claim_token is None:
            raise RuntimeError("research operation claim was lost")
        return cls(repository, owner_id=owner_id, operation_id=queued.operation_id, token=claimed.claim_token)

    def transition(self, stage: str) -> None:
        self._assert_claim()
        if not self.repository.transition(self.operation_id, owner_id=self.owner_id, token=self.token, stage=stage):
            raise RuntimeError("research operation claim was lost")

    def heartbeat(self) -> None:
        self._assert_claim()
        if not self.repository.heartbeat(self.operation_id, owner_id=self.owner_id, token=self.token):
            self._claim_lost.set()
            raise RuntimeError("research operation claim was lost")

    def _assert_claim(self) -> None:
        if self._claim_lost.is_set():
            raise RuntimeError("research operation claim was lost")

    def start_watchdog(self, heartbeat, *, interval_seconds: float = 15.0) -> None:
        """Heartbeat through an independent DB session while a provider blocks."""
        if self._watchdog is not None:
            raise RuntimeError("research operation watchdog already started")
        def _run() -> None:
            while not self._watchdog_stop.wait(interval_seconds):
                if not heartbeat(self.operation_id, self.owner_id, self.token):
                    self._claim_lost.set()
                    return
        self._watchdog = threading.Thread(target=_run, daemon=True, name="research-operation-heartbeat")
        self._watchdog.start()

    def close_watchdog(self) -> None:
        self._watchdog_stop.set()
        if self._watchdog is not None:
            self._watchdog.join(timeout=2)

    def add_completed_run(self, run_id: int) -> None:
        self._assert_claim()
        if not self.repository.add_completed_run(self.operation_id, owner_id=self.owner_id, token=self.token, run_id=run_id):
            raise RuntimeError("research operation claim was lost")

    def complete(self) -> None:
        self._assert_claim()
        if not self.repository.complete(self.operation_id, owner_id=self.owner_id, token=self.token):
            raise RuntimeError("research operation claim was lost")
        self.close_watchdog()

    def fail(self, error: dict[str, Any]) -> None:
        try:
            if not self.repository.fail(self.operation_id, owner_id=self.owner_id, token=self.token, error=error):
                raise RuntimeError("research operation claim was lost")
        finally:
            self.close_watchdog()


__all__ = ["DurableOperationRecorder", "OperationView", "ResearchOperationRepository"]
