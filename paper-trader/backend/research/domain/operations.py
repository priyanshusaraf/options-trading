"""The database-backed, owner-first research operation scheduler seam."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import uuid
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, case, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.concurrency import (append_unique_json_integer,
                                begin_after_clean_reads, locked_rows)
from app.ir.hashing import canonical_json, content_address
from research.domain.models import (ExperimentRun, ResearchOperation,
                                    ResearchOperationEvent, ResearchOperationItem)

_TRIGGERS = frozenset(("nightly", "manual", "generated", "v2_graph"))
_STAGES = frozenset(("startup", "planning", "collection", "experiments", "reports", "generation", "completed"))
_ACTIVE = frozenset(("pending", "running"))
_MAX_PLAN_BYTES = 65536
_MAX_ERROR_BYTES = 4096
_MAX_PENDING_PER_OWNER = 16
_MAX_RUNNING_PER_OWNER = 4
_MAX_PENDING_HOST = 256
_MAX_RUNNING_HOST = 32
_MAX_PENDING_ITEMS_PER_OWNER = 128
_MAX_RUNNING_ITEMS_PER_OWNER = 32
_MAX_PENDING_ITEMS_HOST = 512
_MAX_RUNNING_ITEMS_HOST = 128
_MAX_DAYS = 10_000
_MAX_SEED = 2_147_483_647
_MAX_MIN_TRADES = 100_000
_MAX_FOLDS = 32
_MAX_CAPITAL = 1_000_000_000.0
_MAX_OPERATION_EVENTS = 128
_admission_rejections: dict[str, int] = {}
_admission_rejections_lock = threading.Lock()


def _instant(value: dt.datetime | None) -> dt.datetime:
    instant = value or dt.datetime.now(dt.UTC)
    # SQLite stores DateTime without an offset.  Bind the same naïve UTC shape
    # on every conditional lease predicate; comparing an aware ISO value to a
    # stored naïve value is a lexical false-negative at exact boundaries.
    if instant.tzinfo is not None:
        instant = instant.astimezone(dt.UTC).replace(tzinfo=None)
    return instant


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


def _plan_text(value: Any, limit: int) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= limit


def _plan_integer(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _plan_number(value: Any, minimum: float, maximum: float, *, positive: bool = False) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    number = float(value)
    return math.isfinite(number) and (number > minimum if positive else number >= minimum) and number <= maximum


def _plan_instruments(value: Any, minimum: int) -> bool:
    return isinstance(value, list) and minimum <= len(value) <= 64 and all(_plan_text(key, 48) for key in value)


def _plan_parameters(value: Any) -> bool:
    if not isinstance(value, dict) or len(value) > 64:
        return False
    return all(isinstance(key, str) and len(key) <= 64
               and isinstance(option, (str, int, float, bool, type(None)))
               for key, option in value.items())


def _legacy_plan_shape(value: dict[str, Any]) -> None:
    expected = {"content_address", "experiment_count", "items"}
    if set(value) not in (expected, expected | {"generated"}) or not isinstance(value["content_address"], str):
        raise ValueError("operation plan payload is invalid")
    if not _plan_integer(value["experiment_count"], 0, 64):
        raise ValueError("operation plan payload is invalid")
    if not isinstance(value["items"], list) or not isinstance(value.get("generated", []), list):
        raise ValueError("operation plan payload is invalid")
    if len(value["items"]) + len(value.get("generated", [])) != value["experiment_count"]:
        raise ValueError("operation plan payload is invalid")


def _experiment_limits(item: dict[str, Any]) -> bool:
    return (_plan_integer(item["min_trades"], 1, _MAX_MIN_TRADES)
            and _plan_integer(item["n_folds"], 2, _MAX_FOLDS)
            and _plan_number(item["min_positive_fold_frac"], 0.0, 1.0))


def _handwritten_item(item: Any) -> None:
    fields = {"program", "hypothesis", "strategy_key", "instrument_keys", "interval", "days",
              "optimize_search", "params", "seed", "min_trades", "n_folds", "min_positive_fold_frac", "capital"}
    if not isinstance(item, dict) or set(item) != fields:
        raise ValueError("operation plan payload is invalid")
    labels = (("program", 80), ("hypothesis", 4000), ("strategy_key", 80), ("interval", 24))
    if not all(_plan_text(item[name], limit) for name, limit in labels):
        raise ValueError("operation plan payload is invalid")
    _handwritten_bounds(item)


def _handwritten_bounds(item: dict[str, Any]) -> None:
    if not (_plan_instruments(item["instrument_keys"], 0)
            and _plan_integer(item["days"], 0, _MAX_DAYS)
            and isinstance(item["optimize_search"], bool)
            and _plan_parameters(item["params"])
            and _plan_integer(item["seed"], 0, _MAX_SEED)
            and _experiment_limits(item)
            and _plan_number(item["capital"], 0.0, _MAX_CAPITAL, positive=True)):
        raise ValueError("operation plan payload is invalid")


def _generated_item(descriptor: Any) -> None:
    fields = {"admission_address", "build", "composition", "composition_identity", "graph",
              "graph_content_address", "interval", "limit", "min_positive_fold_frac", "min_trades",
              "n_folds", "owner_universe", "program", "provider_mode", "seed"}
    if not isinstance(descriptor, dict) or set(descriptor) != fields:
        raise ValueError("operation generated descriptor is invalid")
    labels = (("build", 40), ("provider_mode", 80), ("program", 80), ("interval", 24))
    if not all(_plan_text(descriptor[name], limit) for name, limit in labels):
        raise ValueError("operation generated descriptor is invalid")
    _generated_bounds(descriptor)
    _generated_identity(descriptor)
    _generated_grammar(descriptor)


def _generated_bounds(descriptor: dict[str, Any]) -> None:
    if not (_plan_integer(descriptor["limit"], 1, 64)
            and _plan_instruments(descriptor["owner_universe"], 1)
            and (descriptor["seed"] is None or _plan_integer(descriptor["seed"], 0, _MAX_SEED))
            and _experiment_limits(descriptor)):
        raise ValueError("operation generated descriptor is invalid")


def _generated_identity(descriptor: dict[str, Any]) -> None:
    for name, address_key in (("composition", "composition_identity"), ("graph", "graph_content_address")):
        if not isinstance(descriptor[name], dict) or descriptor[address_key] != content_address(descriptor[name]):
            raise ValueError("operation generated descriptor is invalid")
    address = descriptor["admission_address"]
    if not isinstance(address, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", address) is None:
        raise ValueError("operation generated descriptor is invalid")


def _generated_grammar(descriptor: dict[str, Any]) -> None:
    # Validate mechanical graph derivation before any provider can be opened.
    try:
        from research.strategy.builder.composition_ir import composition_to_ir
        from research.strategy.builder.grammar import Composition
        composition = Composition.from_dict(descriptor["composition"])
        if composition.to_dict() != descriptor["composition"]:
            raise ValueError("non-canonical generated composition")
        if canonical_json(composition_to_ir(composition, identifier=f"generated.{composition.key}")) != canonical_json(descriptor["graph"]):
            raise ValueError("non-mechanical generated graph")
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("operation generated descriptor is invalid") from exc


def _legacy_plan_address(value: dict[str, Any]) -> None:
    payload = {"experiment_count": value["experiment_count"], "items": value["items"]}
    if "generated" in value:
        payload["generated"] = value["generated"]
    if value["content_address"] != content_address(payload):
        raise ValueError("operation plan content address is invalid")


def _plan_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Validate each supported workload before admitting provider or data work."""
    if not isinstance(value, dict):
        raise ValueError("operation plan payload is invalid")
    if value.get("schema") in {"v2-graph-research-operation/2", "v2-graph-research-operation/3", "v2-graph-research-operation/4"}:
        from research.orchestrator.v2_preparation import parse_public_preparation_plan
        return parse_public_preparation_plan(value)
    if value.get("schema") == "v2-graph-research-operation/1":
        from research.orchestrator.v2_operation import parse_v2_operation_plan
        return parse_v2_operation_plan(value)
    if value in ({}, {"items": []}):
        return value
    _legacy_plan_shape(value)
    for item in value["items"]:
        _handwritten_item(item)
    for descriptor in value.get("generated", []):
        _generated_item(descriptor)
    _legacy_plan_address(value)
    return value


def operation_item_keys(plan: dict[str, Any], *, trigger: str) -> list[str]:
    """Stable item identifiers for exactly-once *checkpoint* delivery.

    The item itself may be interrupted while talking to a provider.  We make no
    claim to resume inside that call; the durable boundary is before the next
    item.  The ordinal distinguishes intentionally identical experiments.
    """
    safe = _plan_payload(plan)
    if safe in ({}, {"items": []}):
        return []
    if safe.get("schema") in {"v2-graph-research-operation/1", "v2-graph-research-operation/2", "v2-graph-research-operation/3", "v2-graph-research-operation/4"}:
        if trigger != "v2_graph":
            raise ValueError("V2 graph plans require the v2_graph trigger")
        descriptor = safe["v2_graphs"][0]
        return [f"v2_graph:000:{descriptor['descriptor_address'].split(':', 1)[1][:32]}"]
    handwritten = [
        f"{trigger}:{ordinal:03d}:{hashlib.sha256(_json(item, limit=_MAX_PLAN_BYTES).encode()).hexdigest()[:32]}"
        for ordinal, item in enumerate(safe["items"])
    ]
    generated = [
        f"{trigger}:generated:{ordinal:03d}:{descriptor['composition_identity'].split(':')[-1][:32]}"
        for ordinal, descriptor in enumerate(safe.get("generated", []))
    ]
    return handwritten + generated


def reconstruct_plan(plan: dict[str, Any], *, instrument_for_key) -> list[dict[str, Any]]:
    """Rebuild executable bounded work from the persisted public descriptor.

    The caller supplies the in-process instrument registry; no execution-plane
    database is opened.  Descriptor fields are copied rather than regenerated so
    a reclaimed job executes the plan it was admitted with, not today's plan.
    """
    safe = _plan_payload(plan)
    if safe in ({}, {"items": []}):
        return []
    return [{
        "program": item["program"], "hypothesis": item["hypothesis"],
        "strategy_key": item["strategy_key"],
        "instruments": [instrument_for_key(key) for key in item["instrument_keys"]],
        "interval": item["interval"], "days": item["days"],
        "optimize_search": item["optimize_search"], "params": item["params"],
        "seed": item["seed"], "min_trades": item["min_trades"],
        "n_folds": item["n_folds"],
        "min_positive_fold_frac": item["min_positive_fold_frac"],
        "capital": item["capital"],
    } for item in safe["items"]]


def _load(value: str | None, expected, default):
    try:
        decoded = json.loads(value or "null")
    except (TypeError, ValueError):
        return default
    return decoded if isinstance(decoded, expected) else default


def _enqueue_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError(f"{label} is invalid")
    return value


def _enqueue_provenance(plan, *, owner_id, trigger, operation_id, build, provider_mode):
    if trigger == "v2_graph":
        from research.orchestrator.v2_operation import V2_PROVIDER_MODE, operation_id_for_request
        descriptor = plan["v2_graphs"][0]
        expected_id = operation_id_for_request(owner_id=owner_id, request_id=descriptor["request_id"])
        declared_owner = descriptor.get("owner_id", descriptor.get("phase4_binding", {}).get("owner_id"))
        if operation_id != expected_id or provider_mode != V2_PROVIDER_MODE or declared_owner != owner_id:
            raise ValueError("V2 graph operation identity or mode is invalid")
    if any(item["build"] != build or item["provider_mode"] != provider_mode for item in plan.get("generated", [])):
        raise ValueError("generated descriptor provenance does not match operation")


def _queued_operation(*, owner_id, trigger, plan, build, provider_mode, operation_id, now):
    owner_id = _enqueue_identifier(owner_id, "owner_id")
    if trigger not in _TRIGGERS:
        raise ValueError("operation trigger is invalid")
    identifier = _enqueue_identifier(operation_id or uuid.uuid4().hex, "operation_id")
    plan = _plan_payload(plan)
    build = str(build)[:40] or "unknown"
    provider_mode = str(provider_mode)[:80] or "unknown"
    _enqueue_provenance(plan, owner_id=owner_id, trigger=trigger, operation_id=identifier,
                        build=build, provider_mode=provider_mode)
    instant = _instant(now)
    return ResearchOperation(owner_id=owner_id, operation_id=identifier, trigger=trigger,
        plan_json=_json(plan, limit=_MAX_PLAN_BYTES), build=build, provider_mode=provider_mode,
        created_at=instant, queued_at=instant), plan


def _same_queued_operation(existing, candidate) -> bool:
    return existing is not None and all(getattr(existing, name) == getattr(candidate, name)
        for name in ("trigger", "plan_json", "build", "provider_mode"))


def _request_id_reused():
    from research.orchestrator.v2_operation import V2OperationRefusal
    raise V2OperationRefusal("REQUEST_ID_REUSED", "request_id was reused with changed operation content")


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

    def _append_event(self, operation_id: str, *, owner_id: str, event_type: str,
                      stage: str | None, now: dt.datetime,
                      payload: dict[str, str] | None = None) -> None:
        """Append only closed, secret-free scheduler evidence with fixed retention."""
        if event_type not in {"claimed", "heartbeat", "stage", "item_completed",
                              "takeover", "completed", "failed", "cancelled"}:
            raise ValueError("operation event type is invalid")
        if stage is not None and stage not in _STAGES:
            raise ValueError("operation event stage is invalid")
        count = self.session.scalar(select(func.count()).select_from(ResearchOperationEvent).where(
            ResearchOperationEvent.owner_id == owner_id,
            ResearchOperationEvent.operation_id == operation_id,
        )) or 0
        if count >= _MAX_OPERATION_EVENTS:
            cutoff = self.session.scalar(select(ResearchOperationEvent.sequence).where(
                ResearchOperationEvent.owner_id == owner_id,
                ResearchOperationEvent.operation_id == operation_id,
            ).order_by(ResearchOperationEvent.sequence).limit(count - _MAX_OPERATION_EVENTS + 1))
            if cutoff is not None:
                self.session.execute(delete(ResearchOperationEvent).where(
                    ResearchOperationEvent.owner_id == owner_id,
                    ResearchOperationEvent.operation_id == operation_id,
                    ResearchOperationEvent.sequence <= cutoff,
                ))
        latest = self.session.scalar(select(func.max(ResearchOperationEvent.sequence)).where(
            ResearchOperationEvent.owner_id == owner_id,
            ResearchOperationEvent.operation_id == operation_id,
        ))
        sequence = int(latest or 0) + 1
        safe_payload = _error_payload(payload) if payload is not None else {}
        self.session.add(ResearchOperationEvent(
            owner_id=owner_id, operation_id=operation_id,
            sequence=sequence, event_type=event_type, stage=stage,
            payload_json=_json(safe_payload, limit=_MAX_ERROR_BYTES), created_at=now,
        ))
        from app.events.planes import research_outbox
        outbox = research_outbox()
        with outbox.writer(self.session):
            outbox.append(
                self.session, classification="private", owner_id=owner_id,
                broker_account_id=None, aggregate_type="research_operation",
                aggregate_id=operation_id, event_type="research.operation.changed",
                schema_version=1,
                payload={"projection": "research_operation", "state": event_type,
                         "stage": stage or "", "audit_sequence": sequence,
                         **({"code": safe_payload["code"]} if "code" in safe_payload else {})},
                producer_key=f"operation:{owner_id}:{operation_id}:{sequence}")

    def _queued_retry(self, row):
        existing = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == row.owner_id,
            ResearchOperation.operation_id == row.operation_id))
        if existing is None:
            return None
        same = _same_queued_operation(existing, row)
        self.session.commit()
        if same and row.trigger == "v2_graph":
            return _view(existing)
        if row.trigger == "v2_graph":
            _request_id_reused()
        raise ValueError("operation_id already exists")

    def _pending_capacity_counts(self, owner_id):
        pending = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id, ResearchOperation.status == "pending")) or 0
        host_pending = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(
            ResearchOperation.status == "pending")) or 0
        owner_items = self.session.scalar(select(func.count()).select_from(ResearchOperationItem).join(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id, ResearchOperation.status == "pending")) or 0
        host_items = self.session.scalar(select(func.count()).select_from(ResearchOperationItem).join(ResearchOperation).where(
            ResearchOperation.status == "pending")) or 0
        return pending, host_pending, owner_items, host_items

    def _require_pending_capacity(self, owner_id, item_count):
        pending, host_pending, owner_items, host_items = self._pending_capacity_counts(owner_id)
        if (pending >= _MAX_PENDING_PER_OWNER or host_pending >= _MAX_PENDING_HOST
                or owner_items + item_count > _MAX_PENDING_ITEMS_PER_OWNER
                or host_items + item_count > _MAX_PENDING_ITEMS_HOST):
            with _admission_rejections_lock:
                _admission_rejections[owner_id] = _admission_rejections.get(owner_id, 0) + 1
            raise RuntimeError("research operation admission capacity is exhausted")

    def _insert_queued_operation(self, row, item_keys):
        self.session.add(row)
        self.session.flush()
        for ordinal, item_key in enumerate(item_keys):
            self.session.add(ResearchOperationItem(owner_id=row.owner_id, operation_id=row.operation_id,
                item_key=item_key, ordinal=ordinal, status="pending"))
        from app.events.planes import research_outbox
        outbox = research_outbox()
        with outbox.writer(self.session):
            outbox.append(self.session, classification="private", owner_id=row.owner_id,
                broker_account_id=None, aggregate_type="research_operation", aggregate_id=row.operation_id,
                event_type="research.operation.changed", schema_version=1,
                payload={"projection": "research_operation", "state": "queued", "stage": "startup", "audit_sequence": 0},
                producer_key=f"operation:{row.owner_id}:{row.operation_id}:queued")
        self.session.commit()

    def _raced_v2_enqueue(self, row):
        existing = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == row.owner_id,
            ResearchOperation.operation_id == row.operation_id))
        if _same_queued_operation(existing, row):
            return _view(existing)
        _request_id_reused()

    def enqueue(self, *, owner_id: str, trigger: str, plan: dict[str, Any], build: str,
                provider_mode: str, operation_id: str | None = None,
                now: dt.datetime | None = None) -> OperationView:
        row, plan = _queued_operation(owner_id=owner_id, trigger=trigger, plan=plan, build=build,
            provider_mode=provider_mode, operation_id=operation_id, now=now)
        try:
            # Reserve owner and host capacity in the same transaction as items and outbox.
            begin_after_clean_reads(self.session, scope="research:admission")
            existing = self._queued_retry(row)
            if existing is not None:
                return existing
            item_keys = operation_item_keys(plan, trigger=trigger)
            self._require_pending_capacity(owner_id, len(item_keys))
            self._insert_queued_operation(row, item_keys)
        except IntegrityError:
            self.session.rollback()
            if trigger != "v2_graph":
                raise
            return self._raced_v2_enqueue(row)
        except Exception:
            self.session.rollback()
            raise
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

    def events(self, operation_id: str, *, owner_id: str, limit: int = 64) -> list[dict[str, Any]]:
        """Return bounded, owner-scoped, secret-free operation evidence."""
        if not isinstance(limit, int) or not 1 <= limit <= _MAX_OPERATION_EVENTS:
            raise ValueError("operation event history limit is invalid")
        rows = self.session.scalars(select(ResearchOperationEvent).where(
            ResearchOperationEvent.owner_id == owner_id,
            ResearchOperationEvent.operation_id == operation_id,
        ).order_by(ResearchOperationEvent.sequence.desc()).limit(limit)).all()
        return [{"sequence": row.sequence, "type": row.event_type, "stage": row.stage,
                 "created_at": row.created_at, "payload": _load(row.payload_json, dict, {})}
                for row in reversed(rows)]

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

    def active_for_recovery(self, *, owner_id: str) -> tuple[list[OperationView], bool]:
        """Return the bounded active set; overflow never proves job absence."""
        capacity = _MAX_PENDING_PER_OWNER + _MAX_RUNNING_PER_OWNER
        rows = self.session.scalars(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.status.in_(tuple(_ACTIVE)),
        ).order_by(ResearchOperation.queued_at.desc(),
                   ResearchOperation.operation_id.desc()).limit(capacity + 1)).all()
        return [_view(row) for row in rows], len(rows) <= capacity

    def latest_terminal(self, *, owner_id: str) -> OperationView | None:
        row = self.session.scalar(select(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.status.in_(("completed", "failed", "cancelled")),
        ).order_by(ResearchOperation.completed_at.desc(),
                   ResearchOperation.operation_id.desc()).limit(1))
        return _view(row) if row else None

    def running_v2_count(self, *, owner_id: str) -> int:
        """Actual owner-local active predicate used by V2 resource admission."""
        # Findings stay pending while evaluation runs; flushing would block the watchdog.
        with self.session.no_autoflush:
            return int(self.session.scalar(select(func.count()).select_from(
                ResearchOperation).where(
                    ResearchOperation.owner_id == owner_id,
                    ResearchOperation.trigger == "v2_graph",
                    ResearchOperation.status == "running",
                )) or 0)

    def claim_next(self, *, owner_id: str, worker_id: str, triggers: tuple[str, ...] | None = None,
                   now: dt.datetime | None = None, lease_seconds: int = 60) -> OperationView | None:
        if not isinstance(worker_id, str) or not worker_id or lease_seconds < 1:
            raise ValueError("claim arguments are invalid")
        if triggers is not None and (not triggers or not set(triggers) <= _TRIGGERS):
            raise ValueError("claim triggers are invalid")
        instant = _instant(now)
        return self._claim(None, owner_id=owner_id, worker_id=worker_id,
                           now=instant, lease_seconds=lease_seconds,
                           triggers=triggers)

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
        return self._claim(operation_id, owner_id=owner_id, worker_id=worker_id,
                           now=_instant(now), lease_seconds=lease_seconds)

    def _claim(self, operation_id: str | None, *, owner_id: str, worker_id: str,
               now: dt.datetime, lease_seconds: int,
               triggers: tuple[str, ...] | None = None) -> OperationView | None:
        """Atomically reserve active operation and item capacity before a claim.

        Queue capacity is intentionally separate from active capacity.  The
        immediate write transaction turns the count-and-transition into one
        critical section for every dispatcher lane, including trigger-filtered
        restart workers.
        """
        try:
            begin_after_clean_reads(self.session, scope="research:active-admission")
            targeted = operation_id is not None
            filters = [
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.cancel_requested_at.is_(None),
                or_(ResearchOperation.status == "pending", and_(
                    ResearchOperation.status == "running",
                    ResearchOperation.claim_expires_at < now)),
            ]
            if operation_id is not None:
                filters.append(ResearchOperation.operation_id == operation_id)
            if triggers is not None:
                filters.append(ResearchOperation.trigger.in_(triggers))
            candidate = select(ResearchOperation).where(*filters).order_by(
                ResearchOperation.queued_at, ResearchOperation.operation_id).limit(1)
            row = self.session.scalar(locked_rows(candidate, self.session, skip_locked=True))
            if row is None:
                self.session.rollback()
                return None
            if row.trigger == "v2_graph":
                owner_v2_active = self.session.scalar(
                    select(func.count()).select_from(ResearchOperation).where(
                        ResearchOperation.owner_id == owner_id,
                        ResearchOperation.trigger == "v2_graph",
                        ResearchOperation.status == "running",
                        ResearchOperation.operation_id != row.operation_id,
                    )
                ) or 0
                if owner_v2_active >= 1:
                    if targeted:
                        self.session.rollback()
                        return None
                    alternate = select(ResearchOperation).where(
                        *filters, ResearchOperation.trigger != "v2_graph",
                    ).order_by(
                        ResearchOperation.queued_at,
                        ResearchOperation.operation_id,
                    ).limit(1)
                    row = self.session.scalar(locked_rows(
                        alternate, self.session, skip_locked=True,
                    ))
                    if row is None:
                        self.session.rollback()
                        return None
            operation_id = row.operation_id
            owner_active = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.status == "running",
                ResearchOperation.operation_id != operation_id,
            )) or 0
            host_active = self.session.scalar(select(func.count()).select_from(ResearchOperation).where(
                ResearchOperation.status == "running",
                or_(ResearchOperation.owner_id != owner_id,
                    ResearchOperation.operation_id != operation_id),
            )) or 0
            item_count = self.session.scalar(select(func.count()).select_from(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
            )) or 0
            owner_active_items = self.session.scalar(select(func.count()).select_from(
                ResearchOperationItem).join(ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.status == "running",
                ResearchOperation.operation_id != operation_id,
            )) or 0
            host_active_items = self.session.scalar(select(func.count()).select_from(
                ResearchOperationItem).join(ResearchOperation).where(
                ResearchOperation.status == "running",
                or_(ResearchOperation.owner_id != owner_id,
                    ResearchOperation.operation_id != operation_id),
            )) or 0
            if (owner_active >= _MAX_RUNNING_PER_OWNER or host_active >= _MAX_RUNNING_HOST
                    or owner_active_items + item_count > _MAX_RUNNING_ITEMS_PER_OWNER
                    or host_active_items + item_count > _MAX_RUNNING_ITEMS_HOST):
                self.session.rollback()
                return None
            token = uuid.uuid4().hex
            changed = self.session.execute(update(ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.operation_id == operation_id,
                ResearchOperation.cancel_requested_at.is_(None),
                or_(ResearchOperation.status == "pending", and_(
                    ResearchOperation.status == "running",
                    ResearchOperation.claim_expires_at < now)),
            ).values(status="running", started_at=func.coalesce(ResearchOperation.started_at, now),
                     heartbeat_at=now, claim_token=token, claimed_by=worker_id[:128],
                     claim_expires_at=now + dt.timedelta(seconds=lease_seconds),
                     attempt_count=ResearchOperation.attempt_count + 1).execution_options(
                         synchronize_session=False))
            if changed.rowcount != 1:
                self.session.rollback()
                return None
            self._append_event(operation_id, owner_id=owner_id,
                               event_type="takeover" if row.status == "running" else "claimed",
                               stage=row.stage, now=now)
            self.session.commit()
            # Conditional bulk update deliberately avoids SQLAlchemy's Python
            # evaluator (aware-vs-naïve lease timestamps). Refresh the identity
            # map before exposing the freshly issued token.
            self.session.expire_all()
            row = self.session.scalar(select(ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.operation_id == operation_id))
            return _view(row, claim=True)
        except Exception:
            self.session.rollback()
            raise

    def _write(self, operation_id: str, *, owner_id: str, token: str, now: dt.datetime | None,
               values: dict[str, Any], event_type: str | None, event_stage: str | None = None,
               event_payload: dict[str, str] | None = None) -> bool:
        instant = _instant(now)
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id, ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running", ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        ).values(**values))
        if changed.rowcount == 1 and event_type is not None:
            self._append_event(operation_id, owner_id=owner_id, event_type=event_type,
                               stage=event_stage, now=instant, payload=event_payload)
        self.session.commit(); return changed.rowcount == 1

    def heartbeat(self, operation_id: str, *, owner_id: str, token: str, now: dt.datetime | None = None, lease_seconds: int = 60) -> bool:
        instant = _instant(now)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant,
            values={"heartbeat_at": instant, "claim_expires_at": instant + dt.timedelta(seconds=lease_seconds)},
            # Heartbeats are already represented exactly by the current row's
            # timestamp.  Persisting each one would let routine liveness churn
            # evict the last stage/authority evidence from bounded history.
            event_type=None)

    def claim_active(self, operation_id: str, *, owner_id: str, token: str,
                     now: dt.datetime | None = None) -> bool:
        """Read the current durable fence without extending its lease."""
        instant = _instant(now)
        return bool(self.session.scalar(select(func.count()).select_from(
            ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.operation_id == operation_id,
                ResearchOperation.status == "running",
                ResearchOperation.claim_token == token,
                ResearchOperation.claim_expires_at >= instant,
                ResearchOperation.cancel_requested_at.is_(None),
            )))

    def fail_bound_v2_replay(self, operation_id: str, *, owner_id: str,
                             token: str, item_key: str,
                             now: dt.datetime | None = None) -> int | None:
        """Terminalize an abandoned bound V2 run and its operation atomically."""
        instant = _instant(now)
        try:
            operation = self.session.scalar(locked_rows(select(ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.operation_id == operation_id,
                ResearchOperation.trigger == "v2_graph",
                ResearchOperation.status == "running",
                ResearchOperation.claim_token == token,
                ResearchOperation.claim_expires_at >= instant,
                ResearchOperation.cancel_requested_at.is_(None),
            ), self.session))
            if operation is None:
                self.session.rollback()
                return None
            item = self.session.scalar(locked_rows(select(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.item_key == item_key,
                ResearchOperationItem.status == "running",
                ResearchOperationItem.run_id.is_not(None),
            ), self.session))
            if item is None:
                self.session.rollback()
                return None
            run_id = int(item.run_id)
            changed = self.session.execute(update(ExperimentRun).where(
                ExperimentRun.owner_id == owner_id,
                ExperimentRun.id == run_id,
                ExperimentRun.status.in_(("pending", "running")),
            ).values(status="failed", decision="needs_review", completed_at=instant,
                     error="V2_BOUND_RUN_REPLAY_REFUSED"))
            if changed.rowcount != 1:
                self.session.rollback()
                return None
            error = {"code": "V2_BOUND_RUN_REPLAY_REFUSED",
                     "message": "bound V2 research run cannot be replayed",
                     "stage": "experiments"}
            operation.status = "failed"
            operation.completed_at = instant
            operation.heartbeat_at = instant
            operation.error_json = _json(error, limit=_MAX_ERROR_BYTES)
            operation.claim_token = None
            operation.claimed_by = None
            operation.claim_expires_at = None
            self._append_event(operation_id, owner_id=owner_id, event_type="failed",
                               stage="experiments", now=instant, payload=error)
            self.session.commit()
            return run_id
        except Exception:
            self.session.rollback()
            raise

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
        active_rows = self.session.execute(select(
            ResearchOperation.operation_id, ResearchOperation.queued_at, ResearchOperation.started_at,
            ResearchOperation.heartbeat_at,
        ).where(ResearchOperation.owner_id == owner_id,
                ResearchOperation.status == "running")).all()
        def _age(value):
            return max(0, int((instant - _instant(value)).total_seconds())) if value else 0
        # Metric names intentionally omit owner, strategy, instrument, and any
        # descriptor field.  Callers attach deployment-safe aggregate labels.
        stage_ages = []
        for row in active_rows:
            stage_at = self.session.scalar(select(ResearchOperationEvent.created_at).where(
                ResearchOperationEvent.owner_id == owner_id,
                ResearchOperationEvent.operation_id == row.operation_id,
                ResearchOperationEvent.event_type.in_(("claimed", "takeover", "stage")),
            ).order_by(ResearchOperationEvent.sequence.desc()).limit(1))
            stage_ages.append(_age(stage_at or row.started_at))
        takeovers = self.session.scalar(select(func.count()).select_from(ResearchOperationEvent).where(
            ResearchOperationEvent.owner_id == owner_id,
            ResearchOperationEvent.event_type == "takeover",
        )) or 0
        return {"queued": int(queued), "active": int(active), "expired_claims": int(expired),
                "completed": int(terminals.get("completed", 0)),
                "failed": int(terminals.get("failed", 0)),
                "cancelled": int(terminals.get("cancelled", 0)),
                "stage_age_seconds": max(stage_ages, default=0),
                "claim_latency_seconds": max((_age(row.queued_at) - _age(row.started_at)
                                                for row in active_rows), default=0),
                "heartbeat_age_seconds": max((_age(row.heartbeat_at) for row in active_rows), default=0),
                "takeovers": int(takeovers),
                # Rejected admissions are exposed by the caller's counter; no
                # rejected row is persisted, because that would itself become
                # unbounded tenant history.
                "admission_rejections": _admission_rejections.get(owner_id, 0),
        }

    def lock_preparation(self, operation_id: str, *, owner_id: str, token: str) -> None:
        """Hold the current operation fence in the caller's research transaction."""
        instant = _instant(None)
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.trigger == "v2_graph",
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        ).values(heartbeat_at=instant)).rowcount
        if changed != 1:
            raise RuntimeError("research operation claim was lost")

    def preparation_evidence(self, operation_id: str, *, owner_id: str):
        from research.orchestrator.v2_preparation import decode_preparation_evidence
        row = self.session.get(ResearchOperation, (owner_id, operation_id), populate_existing=True)
        if row is None:
            raise ValueError("research operation is unavailable")
        if row.preparation_evidence_json is None:
            return None
        descriptor = _plan_payload(json.loads(row.plan_json))["v2_graphs"][0]
        return decode_preparation_evidence(row.preparation_evidence_json, descriptor)

    def store_preparation_evidence(self, operation_id: str, *, owner_id: str,
                                  token: str, evidence: dict[str, Any]) -> None:
        from research.orchestrator.v2_preparation import validate_preparation_evidence
        self.lock_preparation(operation_id, owner_id=owner_id, token=token)
        row = self.session.get(ResearchOperation, (owner_id, operation_id), populate_existing=True)
        descriptor = _plan_payload(json.loads(row.plan_json))["v2_graphs"][0]
        encoded = canonical_json(validate_preparation_evidence(evidence, descriptor))
        if row.preparation_evidence_json not in (None, encoded):
            raise ValueError("preparation evidence conflicts with the recorded computation")
        row.preparation_evidence_json = encoded
        self.session.commit()

    def transition(self, operation_id: str, *, owner_id: str, token: str, stage: str, now: dt.datetime | None = None) -> bool:
        if stage not in _STAGES - {"completed"}: raise ValueError("operation stage is invalid")
        instant = _instant(now)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant,
                           values={"stage": stage, "heartbeat_at": instant},
                           event_type="stage", event_stage=stage)

    def complete(self, operation_id: str, *, owner_id: str, token: str, now: dt.datetime | None = None) -> bool:
        instant = _instant(now)
        # Completion certifies the exact workload admitted at enqueue time.  The
        # absence check lives in the same UPDATE predicate as the lease fence so
        # a caller cannot observe an incomplete item set and publish success in
        # a later transaction.
        unfinished = select(ResearchOperationItem.item_key).where(
            ResearchOperationItem.owner_id == owner_id,
            ResearchOperationItem.operation_id == operation_id,
            ResearchOperationItem.status != "completed",
        ).exists()
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
            ~unfinished,
        ).values(status="completed", stage="completed", completed_at=instant,
                 heartbeat_at=instant, claim_token=None, claimed_by=None,
                 claim_expires_at=None))
        if changed.rowcount == 1:
            self._append_event(operation_id, owner_id=owner_id, event_type="completed",
                               stage="completed", now=instant)
        self.session.commit()
        return changed.rowcount == 1

    def add_completed_run(self, operation_id: str, *, owner_id: str, token: str, run_id: int,
                          now: dt.datetime | None = None) -> bool:
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
            raise ValueError("completed run id is invalid")
        instant = _instant(now)
        # One conditional write carries the same cancellation/fence predicate as
        # every other worker mutation. The centralized dialect expression makes
        # repeat delivery idempotent on both SQLite and PostgreSQL.
        changed = self.session.execute(update(ResearchOperation).where(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        ).values(
            completed_run_ids_json=append_unique_json_integer(
                ResearchOperation.completed_run_ids_json, run_id, self.session),
            heartbeat_at=instant,
        ))
        if changed.rowcount == 1:
            self._append_event(operation_id, owner_id=owner_id, event_type="item_completed",
                               stage=None, now=instant)
        self.session.commit()
        return changed.rowcount == 1

    def completed_item_run(self, operation_id: str, *, owner_id: str,
                           item_key: str) -> int | None:
        """Return only a previously fenced completion for this owner/item."""
        row = self.session.scalar(select(ResearchOperationItem.run_id).where(
            ResearchOperationItem.owner_id == owner_id,
            ResearchOperationItem.operation_id == operation_id,
            ResearchOperationItem.item_key == item_key,
            ResearchOperationItem.status == "completed",
        ))
        return int(row) if row is not None else None

    def bound_item_run(self, operation_id: str, *, owner_id: str, item_key: str) -> int | None:
        """Return a nonterminal durable binding for safe replay refusal."""
        row = self.session.scalar(select(ResearchOperationItem.run_id).where(
            ResearchOperationItem.owner_id == owner_id,
            ResearchOperationItem.operation_id == operation_id,
            ResearchOperationItem.item_key == item_key,
            ResearchOperationItem.status == "running",
        ))
        return int(row) if row is not None else None

    def reclaim_bound_item(self, operation_id: str, *, owner_id: str, token: str,
                           item_key: str, now: dt.datetime | None = None) -> int | None:
        """Turn a takeover's abandoned run into auditable failure, then retry item.

        A worker may die after publishing the run binding but before it can write
        terminal evidence.  The replacement owns a new claim token, so it may
        make the old run terminal and reset *that exact item* in one short
        transaction.  Completed rows never pass this method.
        """
        instant = _instant(now)
        predicate = and_(ResearchOperation.owner_id == owner_id,
                         ResearchOperation.operation_id == operation_id,
                         ResearchOperation.status == "running",
                         ResearchOperation.claim_token == token,
                         ResearchOperation.claim_expires_at >= instant,
                         ResearchOperation.cancel_requested_at.is_(None))
        try:
            if self.session.execute(update(ResearchOperation).where(predicate).values(
                    heartbeat_at=instant)).rowcount != 1:
                self.session.rollback(); return None
            item = self.session.scalar(select(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.item_key == item_key,
                ResearchOperationItem.status == "running",
            ))
            if item is None or item.run_id is None:
                self.session.rollback(); return None
            run_id = int(item.run_id)
            changed = self.session.execute(update(ExperimentRun).where(
                ExperimentRun.owner_id == owner_id, ExperimentRun.id == run_id,
                ExperimentRun.status.in_(("pending", "running")),
            ).values(status="failed", decision="needs_review", completed_at=instant,
                     error="RESEARCH_OPERATION_TAKEOVER_RETRY"))
            if changed.rowcount != 1:
                self.session.rollback(); return None
            reset = self.session.execute(update(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.item_key == item_key,
                ResearchOperationItem.status == "running",
                ResearchOperationItem.run_id == run_id,
            ).values(status="pending", run_id=None, completed_at=None))
            if reset.rowcount != 1:
                self.session.rollback(); return None
            self._append_event(operation_id, owner_id=owner_id, event_type="takeover",
                               stage="experiments", now=instant)
            self.session.commit()
            return run_id
        except Exception:
            self.session.rollback()
            raise

    def bind_item_run(self, operation_id: str, *, owner_id: str, token: str,
                      item_key: str, run_id: int,
                      now: dt.datetime | None = None) -> bool:
        """Bind a just-opened run to its item before provider work begins.

        This short transaction is deliberately distinct from the long-running
        experiment.  On restart, a bound-but-nonterminal run is never executed
        a second time: callers must resume it or fail the operation safely.
        """
        if (not isinstance(item_key, str) or not item_key or len(item_key) > 128
                or not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1):
            raise ValueError("operation item binding is invalid")
        instant = _instant(now)
        predicate = and_(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        )
        try:
            bound = self._bind_item_run_in_transaction(
                operation_id, owner_id=owner_id, token=token, item_key=item_key,
                run_id=run_id, now=instant)
            if not bound:
                self.session.rollback()
                return False
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def _bind_item_run_in_transaction(self, operation_id: str, *, owner_id: str,
                                      token: str, item_key: str, run_id: int,
                                      now: dt.datetime) -> bool:
        """Bind without committing; used with the ExperimentRun open transaction."""
        predicate = and_(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= now,
            ResearchOperation.cancel_requested_at.is_(None),
        )
        if self.session.execute(update(ResearchOperation).where(predicate).values(
            heartbeat_at=now)).rowcount != 1:
            return False
        changed = self.session.execute(update(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.item_key == item_key,
                ResearchOperationItem.status == "pending",
                ResearchOperationItem.run_id.is_(None),
            ).values(status="running", run_id=run_id)).rowcount
        return changed == 1

    def complete_item(self, operation_id: str, *, owner_id: str, token: str,
                      item_key: str, run_id: int,
                      now: dt.datetime | None = None) -> bool:
        """Fence a durable item-to-run receipt and advance its item checkpoint."""
        if (not isinstance(item_key, str) or not item_key or len(item_key) > 128
                or not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1):
            raise ValueError("operation item checkpoint is invalid")
        instant = _instant(now)
        predicate = and_(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        )
        try:
            # Keep the lease validation and receipt in one DB transaction.  A
            # cancelled/reclaimed worker never gets a new completed checkpoint.
            touched = self.session.execute(update(ResearchOperation).where(predicate).values(
                heartbeat_at=instant)).rowcount
            if touched != 1:
                self.session.rollback()
                return False
            item = self.session.execute(update(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.item_key == item_key,
                ResearchOperationItem.status == "running",
                ResearchOperationItem.run_id == run_id,
            ).values(status="completed", run_id=run_id, completed_at=instant)).rowcount
            if item == 1:
                self._append_event(operation_id, owner_id=owner_id, event_type="item_completed",
                                   stage=None, now=instant)
                self.session.commit()
                return True
            existing = self.session.scalar(select(ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.item_key == item_key,
                ResearchOperationItem.status == "completed",
            ))
            if existing is not None and existing.run_id == run_id:
                self.session.commit()
                return True
            self.session.rollback()
            return False
        except Exception:
            self.session.rollback()
            raise

    def finalize_item_in_transaction(self, operation_id: str, *, owner_id: str,
                                     token: str, item_key: str, run_id: int,
                                     now: dt.datetime | None = None) -> bool:
        """Append the receipt in the caller's terminal ExperimentRun transaction.

        No commit happens here.  ``run_experiment`` has already assembled
        terminal evidence on the same Session, then this method transitions the
        bound item and mirrors its run id under the same fence.  A crash before
        the single outer commit rolls all terminal evidence/receipt mutations
        back together.
        """
        instant = _instant(now)
        predicate = and_(ResearchOperation.owner_id == owner_id,
                         ResearchOperation.operation_id == operation_id,
                         ResearchOperation.status == "running",
                         ResearchOperation.claim_token == token,
                         ResearchOperation.claim_expires_at >= instant,
                         ResearchOperation.cancel_requested_at.is_(None))
        if self.session.execute(update(ResearchOperation).where(predicate).values(
            heartbeat_at=instant,
            completed_run_ids_json=append_unique_json_integer(
                ResearchOperation.completed_run_ids_json, run_id,
                self.session))).rowcount != 1:
            return False
        completed = self.session.execute(update(ResearchOperationItem).where(
            ResearchOperationItem.owner_id == owner_id,
            ResearchOperationItem.operation_id == operation_id,
            ResearchOperationItem.item_key == item_key,
            ResearchOperationItem.status == "running",
            ResearchOperationItem.run_id == run_id,
        ).values(status="completed", completed_at=instant)).rowcount == 1
        if completed:
            self._append_event(operation_id, owner_id=owner_id, event_type="item_completed",
                               stage=None, now=instant)
        return completed

    def finalize_v2_operation_in_transaction(
        self, operation_id: str, *, owner_id: str, token: str,
        item_key: str, run_id: int, now: dt.datetime | None = None,
    ) -> bool:
        """Terminalize the one-item V2 run, item, operation, and events atomically.

        The caller owns the transaction that already contains the completed
        ``ExperimentRun`` and its terminal evidence.  This method never commits or
        rolls back.  Its first conditional operation update both verifies and locks
        the owner/token/lease/cancel fence, so cancellation either wins before any
        terminal item fact or waits until the completed operation is visible.
        """
        if (not isinstance(item_key, str) or not item_key or len(item_key) > 128
                or not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1):
            raise ValueError("V2 operation terminal binding is invalid")
        instant = _instant(now)
        predicate = and_(
            ResearchOperation.owner_id == owner_id,
            ResearchOperation.operation_id == operation_id,
            ResearchOperation.trigger == "v2_graph",
            ResearchOperation.status == "running",
            ResearchOperation.claim_token == token,
            ResearchOperation.claim_expires_at >= instant,
            ResearchOperation.cancel_requested_at.is_(None),
        )
        # This conditional write acquires the operation row under the same fence
        # used by the final transition.  No item or event mutation precedes it.
        with self.session.no_autoflush:
            fenced = self.session.execute(update(ResearchOperation).where(
                predicate).values(heartbeat_at=instant)).rowcount
        if fenced != 1:
            return False
        item_count = self.session.scalar(select(func.count()).select_from(
            ResearchOperationItem).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
            )) or 0
        if item_count != 1:
            return False
        completed_item = self.session.execute(update(ResearchOperationItem).where(
            ResearchOperationItem.owner_id == owner_id,
            ResearchOperationItem.operation_id == operation_id,
            ResearchOperationItem.item_key == item_key,
            ResearchOperationItem.status == "running",
            ResearchOperationItem.run_id == run_id,
        ).values(status="completed", completed_at=instant)).rowcount == 1
        if not completed_item:
            return False
        run = self.session.get(ExperimentRun, run_id)
        if (run is None or run.owner_id != owner_id or run.status != "completed"
                or run.completed_at is None):
            return False
        completed_operation = self.session.execute(update(ResearchOperation).where(
            predicate,
        ).values(
            status="completed", stage="completed", completed_at=instant,
            heartbeat_at=instant,
            completed_run_ids_json=append_unique_json_integer(
                ResearchOperation.completed_run_ids_json, run_id, self.session),
            claim_token=None, claimed_by=None, claim_expires_at=None,
        )).rowcount == 1
        if not completed_operation:
            return False
        self._append_event(
            operation_id, owner_id=owner_id, event_type="item_completed",
            stage=None, now=instant,
        )
        self._append_event(
            operation_id, owner_id=owner_id, event_type="completed",
            stage="completed", now=instant,
        )
        return True

    def fail(self, operation_id: str, *, owner_id: str, token: str, error: dict[str, Any],
             now: dt.datetime | None = None) -> bool:
        instant = _instant(now)
        safe_error = _error_payload(error)
        return self._write(operation_id, owner_id=owner_id, token=token, now=instant,
            values={"status": "failed", "completed_at": instant, "heartbeat_at": instant,
                    "error_json": _json(safe_error, limit=_MAX_ERROR_BYTES), "claim_token": None,
                    "claimed_by": None, "claim_expires_at": None}, event_type="failed",
            event_stage=safe_error.get("stage"), event_payload=safe_error)

    def request_cancel(self, operation_id: str, *, owner_id: str, now: dt.datetime | None = None) -> bool:
        instant = _instant(now)
        # Cancellation is a terminal authority decision, not a request that
        # consumes capacity until an arbitrary lease expires.  Clearing the
        # fence in this atomic operation update blocks every stale writer; only
        # then do we terminalize any already-bound ExperimentRun in the same
        # transaction for an auditable, non-replayable cleanup.
        try:
            changed = self.session.execute(update(ResearchOperation).where(
                ResearchOperation.owner_id == owner_id,
                ResearchOperation.operation_id == operation_id,
                ResearchOperation.status.in_(_ACTIVE),
                ResearchOperation.cancel_requested_at.is_(None),
            ).values(cancel_requested_at=instant, status="cancelled", completed_at=instant,
                     heartbeat_at=instant, claim_token=None, claimed_by=None,
                     claim_expires_at=None))
            if changed.rowcount != 1:
                self.session.rollback()
                return False
            bound_run_ids = self.session.scalars(select(ResearchOperationItem.run_id).where(
                ResearchOperationItem.owner_id == owner_id,
                ResearchOperationItem.operation_id == operation_id,
                ResearchOperationItem.status == "running",
                ResearchOperationItem.run_id.is_not(None),
            )).all()
            if bound_run_ids:
                self.session.execute(update(ExperimentRun).where(
                    ExperimentRun.owner_id == owner_id,
                    ExperimentRun.id.in_(bound_run_ids),
                    ExperimentRun.status.in_(("pending", "running")),
                ).values(status="failed", decision="needs_review", completed_at=instant,
                         error="RESEARCH_OPERATION_CANCELLED"))
            self._append_event(operation_id, owner_id=owner_id, event_type="cancelled",
                               stage=None, now=instant)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def reconcile_expired(self, *, owner_id: str, now: dt.datetime | None = None) -> int:
        instant = _instant(now)
        candidates = list(self.session.scalars(select(ResearchOperation.operation_id).where(
            ResearchOperation.owner_id == owner_id,
            or_(
                and_(ResearchOperation.status == "pending",
                     ResearchOperation.cancel_requested_at.is_not(None)),
                and_(ResearchOperation.status == "running",
                     ResearchOperation.cancel_requested_at.is_not(None),
                     ResearchOperation.claim_expires_at < instant),
            ))))
        pending = self.session.execute(update(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "pending", ResearchOperation.cancel_requested_at.is_not(None)).values(status="cancelled", completed_at=instant))
        active = self.session.execute(update(ResearchOperation).where(ResearchOperation.owner_id == owner_id, ResearchOperation.status == "running", ResearchOperation.cancel_requested_at.is_not(None), ResearchOperation.claim_expires_at < instant).values(status="cancelled", completed_at=instant, claim_token=None, claimed_by=None, claim_expires_at=None))
        for operation_id in candidates:
            self._append_event(operation_id, owner_id=owner_id, event_type="cancelled",
                               stage=None, now=instant)
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

    @classmethod
    def claim_next(cls, repository: ResearchOperationRepository, *, owner_id: str,
                   worker_id: str, triggers: tuple[str, ...] | None = None) -> "DurableOperationRecorder | None":
        """Claim one pending or expired job for a bounded restart dispatcher.

        The persisted plan resumes only at durable item boundaries; provider and
        experiment calls are not falsely presented as preemptible.
        """
        claimed = repository.claim_next(owner_id=owner_id, worker_id=worker_id, triggers=triggers)
        if claimed is None:
            return None
        if claimed.claim_token is None:
            raise RuntimeError("research operation claim was lost")
        return cls(repository, owner_id=owner_id, operation_id=claimed.operation_id,
                   token=claimed.claim_token)

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

    def assert_claim(self) -> None:
        """Public guard for stages that perform their own bounded item loop."""
        self._assert_claim()

    def assert_durable_claim(self) -> None:
        """Check both watchdog state and the current database fence."""
        self._assert_claim()
        if not self.repository.claim_active(
                self.operation_id, owner_id=self.owner_id, token=self.token):
            self._claim_lost.set()
            raise RuntimeError("research operation claim was lost")

    def start_watchdog(self, heartbeat, *, interval_seconds: float = 15.0) -> None:
        """Heartbeat through an independent DB session while a provider blocks."""
        if self._watchdog is not None:
            raise RuntimeError("research operation watchdog already started")
        def _run() -> None:
            while not self._watchdog_stop.wait(interval_seconds):
                try:
                    alive = heartbeat(self.operation_id, self.owner_id, self.token)
                except Exception:
                    # No watchdog result is no proof of lease ownership.
                    self._claim_lost.set()
                    return
                if not alive:
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

    def completed_item_run(self, item_key: str) -> int | None:
        self._assert_claim()
        return self.repository.completed_item_run(self.operation_id,
                                                  owner_id=self.owner_id,
                                                  item_key=item_key)

    def bound_item_run(self, item_key: str) -> int | None:
        self._assert_claim()
        return self.repository.bound_item_run(self.operation_id, owner_id=self.owner_id,
                                              item_key=item_key)

    def complete_item(self, item_key: str, run_id: int) -> None:
        self._assert_claim()
        if not self.repository.complete_item(self.operation_id, owner_id=self.owner_id,
                                             token=self.token, item_key=item_key,
                                             run_id=run_id):
            self._claim_lost.set()
            raise RuntimeError("research operation claim was lost")

    def reclaim_bound_item(self, item_key: str) -> int | None:
        self._assert_claim()
        return self.repository.reclaim_bound_item(
            self.operation_id, owner_id=self.owner_id, token=self.token,
            item_key=item_key)

    def bind_item_run(self, item_key: str, run_id: int) -> None:
        self._assert_claim()
        if not self.repository.bind_item_run(self.operation_id, owner_id=self.owner_id,
                                             token=self.token, item_key=item_key,
                                             run_id=run_id):
            self._claim_lost.set()
            raise RuntimeError("research operation item is already bound or claim was lost")

    def bind_item_run_in_transaction(self, item_key: str, run_id: int) -> bool:
        self._assert_claim()
        return self.repository._bind_item_run_in_transaction(
            self.operation_id, owner_id=self.owner_id, token=self.token,
            item_key=item_key, run_id=run_id, now=_instant(None))

    def finalize_item_in_transaction(self, item_key: str, run_id: int) -> bool:
        self._assert_claim()
        return self.repository.finalize_item_in_transaction(
            self.operation_id, owner_id=self.owner_id, token=self.token,
            item_key=item_key, run_id=run_id)

    def finalize_v2_operation_in_transaction(self, item_key: str, run_id: int) -> bool:
        self._assert_claim()
        return self.repository.finalize_v2_operation_in_transaction(
            self.operation_id, owner_id=self.owner_id, token=self.token,
            item_key=item_key, run_id=run_id,
        )

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
