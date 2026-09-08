"""Public server-owned release-profile/capability read model."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.release_profile import manifest


router = APIRouter(prefix="/api")


@router.get("/release-profile")
def get_release_profile():
    settings = get_settings()
    return manifest(
        settings.release_profile,
        research_enabled=settings.research_enabled,
        service_role=settings.release_service_role,
    )
