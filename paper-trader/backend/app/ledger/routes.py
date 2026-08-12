"""HTTP surface for THE LEDGER.

Auth: none per-route. The global auth_gate middleware in app/main.py already
requires Bearer PT_API_TOKEN on every /api/* path except health/login/session.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.ledger import service
from app.ledger.db import get_sessionmaker
from app.api.execution_access import local_execution_cell
from app.api.principal import Principal, get_principal
from app.core.trade_claims import scoped_trade_exists

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

# A screenshot larger than this is a mistake, not a screenshot. Bounding it keeps
# one bad upload from wedging a 1GB VPS that has already OOM'd twice.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


class PutSnapshotRequest(BaseModel):
    base_version: int | None = None
    payload: Any = None


def _scope(request: Request, principal: Principal, *, mutation: bool = False) -> tuple[str, str]:
    runner = local_execution_cell(request, principal, mutation=mutation)
    return runner.owner_id, runner.broker_account_id


@router.get("/snapshot")
def get_snapshot(request: Request, principal: Principal = Depends(get_principal)):
    owner_id, broker_account_id = _scope(request, principal)
    got = service.read_snapshot(get_sessionmaker(), owner_id=owner_id,
                                broker_account_id=broker_account_id)
    if got is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    version, payload = got
    return {"version": version, "payload": json.loads(payload)}


@router.put("/snapshot")
def put_snapshot(req: PutSnapshotRequest, request: Request,
                 principal: Principal = Depends(get_principal)):
    owner_id, broker_account_id = _scope(request, principal, mutation=True)
    try:
        version = service.write_snapshot(
            get_sessionmaker(),
            json.dumps(req.payload, separators=(",", ":")),
            req.base_version,
            owner_id=owner_id, broker_account_id=broker_account_id,
        )
    except service.VersionConflict as exc:
        # Flat body, not FastAPI's nested {"detail": {...}} — the client reads
        # `current` off the top level to adopt the server's version.
        return JSONResponse(
            status_code=409,
            content={"detail": "version conflict", "current": exc.current},
        )
    return {"version": version}


@router.post("/artifacts")
async def post_artifact(request: Request, artifact_id: str = Form(...), file: UploadFile = File(...),
                        principal: Principal = Depends(get_principal)):
    data = await file.read()
    if len(data) > MAX_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail="artifact too large")
    owner_id, broker_account_id = _scope(request, principal, mutation=True)
    service.put_artifact(get_sessionmaker(), artifact_id,
                         file.content_type or "application/octet-stream", data,
                         owner_id=owner_id, broker_account_id=broker_account_id)
    return {"id": artifact_id}


@router.get("/artifacts/{artifact_id}")
def fetch_artifact(artifact_id: str, request: Request,
                   principal: Principal = Depends(get_principal)):
    owner_id, broker_account_id = _scope(request, principal)
    got = service.get_artifact(get_sessionmaker(), artifact_id, owner_id=owner_id,
                               broker_account_id=broker_account_id)
    if got is None:
        raise HTTPException(status_code=404, detail="no such artifact")
    mime, data = got
    # Artifact bytes are immutable for a given id, so this can cache hard.
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.delete("/artifacts/{artifact_id}")
def remove_artifact(artifact_id: str, request: Request,
                    principal: Principal = Depends(get_principal)):
    owner_id, broker_account_id = _scope(request, principal, mutation=True)
    if not service.delete_artifact(get_sessionmaker(), artifact_id, owner_id=owner_id,
                                   broker_account_id=broker_account_id):
        raise HTTPException(status_code=404, detail="no such artifact")
    return {"ok": True}


# ── Manual fills ──────────────────────────────────────────────────────────
# Kite orders attributed to the owner rather than the bot, awaiting reasoning.


class ClaimRequest(BaseModel):
    trade_id: str


@router.get("/manual-fills")
def get_manual_fills(request: Request, unclaimed: bool = True,
                     principal: Principal = Depends(get_principal)):
    owner_id, broker_account_id = _scope(request, principal)
    return {"fills": service.list_manual_fills(get_sessionmaker(), unclaimed,
                                                 owner_id=owner_id,
                                                 broker_account_id=broker_account_id)}


@router.post("/manual-fills/{order_id}/claim")
def claim_manual_fill(order_id: str, req: ClaimRequest, request: Request,
                      principal: Principal = Depends(get_principal)):
    owner_id, broker_account_id = _scope(request, principal, mutation=True)

    try:
        found = service.claim_manual_fill(get_sessionmaker(), order_id, req.trade_id,
                                          owner_id=owner_id,
                                          broker_account_id=broker_account_id,
                                          trade_exists=scoped_trade_exists)
    except service.AlreadyClaimed as exc:
        return JSONResponse(
            status_code=409,
            content={"detail": "already claimed", "trade_id": exc.trade_id},
        )
    if not found:
        raise HTTPException(status_code=404, detail="no such fill")
    return {"ok": True, "order_id": order_id, "trade_id": req.trade_id}
