"""HTTP surface for THE LEDGER.

Auth: none per-route. The global auth_gate middleware in app/main.py already
requires Bearer PT_API_TOKEN on every /api/* path except health/login/session.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.ledger import service
from app.ledger.db import get_sessionmaker

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

# A screenshot larger than this is a mistake, not a screenshot. Bounding it keeps
# one bad upload from wedging a 1GB VPS that has already OOM'd twice.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


class PutSnapshotRequest(BaseModel):
    base_version: int | None = None
    payload: Any = None


@router.get("/snapshot")
def get_snapshot():
    got = service.read_snapshot(get_sessionmaker())
    if got is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    version, payload = got
    return {"version": version, "payload": json.loads(payload)}


@router.put("/snapshot")
def put_snapshot(req: PutSnapshotRequest):
    try:
        version = service.write_snapshot(
            get_sessionmaker(),
            json.dumps(req.payload, separators=(",", ":")),
            req.base_version,
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
async def post_artifact(artifact_id: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail="artifact too large")
    service.put_artifact(get_sessionmaker(), artifact_id,
                         file.content_type or "application/octet-stream", data)
    return {"id": artifact_id}


@router.get("/artifacts/{artifact_id}")
def fetch_artifact(artifact_id: str):
    got = service.get_artifact(get_sessionmaker(), artifact_id)
    if got is None:
        raise HTTPException(status_code=404, detail="no such artifact")
    mime, data = got
    # Artifact bytes are immutable for a given id, so this can cache hard.
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.delete("/artifacts/{artifact_id}")
def remove_artifact(artifact_id: str):
    if not service.delete_artifact(get_sessionmaker(), artifact_id):
        raise HTTPException(status_code=404, detail="no such artifact")
    return {"ok": True}


# ── Manual fills ──────────────────────────────────────────────────────────
# Kite orders attributed to the owner rather than the bot, awaiting reasoning.


class ClaimRequest(BaseModel):
    trade_id: str


@router.get("/manual-fills")
def get_manual_fills(unclaimed: bool = True):
    return {"fills": service.list_manual_fills(get_sessionmaker(), unclaimed)}


@router.post("/manual-fills/{order_id}/claim")
def claim_manual_fill(order_id: str, req: ClaimRequest):
    try:
        found = service.claim_manual_fill(get_sessionmaker(), order_id, req.trade_id)
    except service.AlreadyClaimed as exc:
        return JSONResponse(
            status_code=409,
            content={"detail": "already claimed", "trade_id": exc.trade_id},
        )
    if not found:
        raise HTTPException(status_code=404, detail="no such fill")
    return {"ok": True, "order_id": order_id, "trade_id": req.trade_id}
