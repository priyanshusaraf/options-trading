"""Read-only status for bounded research operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.principal import Principal, get_principal, owner_id_for
from app.core.config import get_settings
from research.config import research_database_url
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.operations import OperationView, ResearchOperationRepository


def _research_gate() -> None:
    if not get_settings().research_enabled:
        raise HTTPException(
            status_code=403,
            detail="research plane disabled (set PT_RESEARCH_ENABLED=1)",
        )


router = APIRouter(dependencies=[Depends(_research_gate)])


def _public(operation: OperationView) -> dict:
    return {
        "operation_id": operation.operation_id, "trigger": operation.trigger,
        "plan": operation.plan, "status": operation.status, "stage": operation.stage,
        "error": operation.error, "build": operation.build, "provider_mode": operation.provider_mode,
        "completed_run_ids": operation.completed_run_ids,
        "created_at": operation.created_at.isoformat(), "queued_at": operation.queued_at.isoformat(),
        "started_at": operation.started_at.isoformat() if operation.started_at else None,
        "heartbeat_at": operation.heartbeat_at.isoformat() if operation.heartbeat_at else None,
        "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
        "cancel_requested_at": operation.cancel_requested_at.isoformat() if operation.cancel_requested_at else None,
        "attempt_count": operation.attempt_count,
    }


def _public_event(event: dict) -> dict:
    return {"sequence": event["sequence"], "type": event["type"],
            "stage": event["stage"], "created_at": event["created_at"].isoformat(),
            "payload": event["payload"]}


def _private_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="research operation not found")


def _owner_operation(operation_id: str, *, owner_id: str) -> dict:
    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            repository = ResearchOperationRepository(session)
            operation = repository.get(operation_id, owner_id=owner_id)
            if operation is None:
                raise _private_not_found()
            events = repository.events(operation_id, owner_id=owner_id)
            return {**_public(operation),
                    "events": [_public_event(event) for event in events]}
    finally:
        engine.dispose()


@router.get("/api/research/operations/status")
def get_research_operation_status(principal: Principal = Depends(get_principal)):
    """Owner-local durable status; a receipt file is never consulted here."""
    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            repository = ResearchOperationRepository(session)
            owner_id = owner_id_for(principal)
            active_operations, active_complete = repository.active_for_recovery(owner_id=owner_id)
            active = active_operations[0] if active_operations else None
            last = repository.latest_terminal(owner_id=owner_id)
            event_operation = active or last
            events = (repository.events(event_operation.operation_id, owner_id=owner_id)
                      if event_operation else [])
    finally:
        engine.dispose()
    return _recovery_payload(active, last, active_operations, active_complete, events)


def _recovery_payload(active, last, active_operations, active_complete, events):
    return {"state": "available" if active or last else "never_run",
            "active": _public(active) if active else None,
            "active_operations": [_public(operation) for operation in active_operations],
            "active_complete": active_complete,
            "last": _public(last) if last else None,
            "events": [_public_event(event) for event in events]}


@router.get("/api/research/operations/{operation_id}")
def get_research_operation(
    operation_id: str, principal: Principal = Depends(get_principal),
):
    return _owner_operation(operation_id, owner_id=owner_id_for(principal))


@router.post("/api/research/operations/{operation_id}/cancel")
def cancel_research_operation(
    operation_id: str, principal: Principal = Depends(get_principal),
):
    owner_id = owner_id_for(principal)
    engine = make_engine(research_database_url())
    try:
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            repository = ResearchOperationRepository(session)
            if repository.get(operation_id, owner_id=owner_id) is None:
                raise _private_not_found()
            repository.request_cancel(operation_id, owner_id=owner_id)
    finally:
        engine.dispose()
    return _owner_operation(operation_id, owner_id=owner_id)
