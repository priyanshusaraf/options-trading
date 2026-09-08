"""Publish owner-scoped alert history and review; this creates no monitoring assignment."""
from __future__ import annotations

import datetime as dt
import hashlib

from fastapi import APIRouter

from app.api.monitoring_interaction_routes import build_monitoring_interaction_router
from app.api.monitoring_read_routes import build_monitoring_read_router
from app.core.config import get_settings
from app.db.session import SessionLocal


def build_published_monitoring_router() -> APIRouter:
    settings = get_settings()
    secret = settings.event_cursor_secret
    if len(secret.strip()) < 32 and settings.service_role not in {"development", "test"}:
        raise ValueError("Configure a stable event cursor secret before publishing alerts.")
    key = hashlib.sha256(b"monitoring-alert-inbox/1:" +
        (secret or "strategy-os-development-resume-cursor").encode()).digest()
    router = APIRouter()
    router.include_router(build_monitoring_read_router(sessionmaker=SessionLocal, cursor_secret=key, attributed=True))
    router.include_router(build_monitoring_interaction_router(sessionmaker=SessionLocal, clock=lambda: dt.datetime.now(dt.UTC)))
    return router
