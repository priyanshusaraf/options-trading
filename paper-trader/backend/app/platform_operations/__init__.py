"""Privacy-minimised platform operations persistence boundary."""

from app.platform_operations.contracts import (
    OperationsConflict,
    OperationsCorrupt,
    OperationsNotFound,
    OperationsRefused,
)
from app.platform_operations.repository import PlatformOperationsRepository

__all__ = [
    "OperationsConflict",
    "OperationsCorrupt",
    "OperationsNotFound",
    "OperationsRefused",
    "PlatformOperationsRepository",
]
