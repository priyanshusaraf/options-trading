"""Read-only status for bounded research operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.principal import Principal, get_principal, owner_id_for
from app.core.config import get_settings
from research.config import research_db_path
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


@router.get("/api/research/operations/status")
def get_research_operation_status(principal: Principal = Depends(get_principal)):
    """Owner-local durable status; a receipt file is never consulted here."""
    engine = make_engine(research_db_path())
    try:
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            repository = ResearchOperationRepository(session)
            owner_id = owner_id_for(principal)
            active = repository.latest_active(owner_id=owner_id)
            last = repository.latest_terminal(owner_id=owner_id)
    finally:
        engine.dispose()
    return {"state": "available" if active or last else "never_run", "active": _public(active) if active else None, "last": _public(last) if last else None}
