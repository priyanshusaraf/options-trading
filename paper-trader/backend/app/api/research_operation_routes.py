"""Read-only status for bounded research operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from research.config import operation_receipt_path
from research.operations import OperationStateCorrupt, ResearchOperationRecorder


def _research_gate() -> None:
    if not get_settings().research_enabled:
        raise HTTPException(
            status_code=403,
            detail="research plane disabled (set PT_RESEARCH_ENABLED=1)",
        )


router = APIRouter(dependencies=[Depends(_research_gate)])


@router.get("/api/research/operations/status")
def get_research_operation_status():
    """Return the persisted current/last receipt without executing research."""
    try:
        state = ResearchOperationRecorder.load(operation_receipt_path())
    except OperationStateCorrupt:
        return JSONResponse(
            status_code=409,
            content={
                "code": "RESEARCH_OPERATION_STATE_CORRUPT",
                "message": (
                    "research operation status is unavailable because its receipt is invalid"
                ),
            },
        )
    return {
        "state": "never_run" if state == {"active": None, "last": None} else "available",
        **state,
    }
