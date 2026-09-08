"""Explicit, lifespan-owned authority inputs for durable reclaim."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.ir.registry import PlatformRegistry


@dataclass(frozen=True)
class ReclaimAuthorityContext:
    """The only non-persisted inputs allowed to verify a v2 reclaim receipt."""

    registry: PlatformRegistry
    research_sessionmaker: Callable[[], Session]
