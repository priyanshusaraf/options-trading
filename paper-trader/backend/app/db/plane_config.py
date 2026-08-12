"""Configuration source shared by standalone research and ledger processes."""
from __future__ import annotations

import os
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_file() -> str | None:
    if os.environ.get("PT_DISABLE_DOTENV") == "1" or "pytest" in sys.modules:
        return None
    return ".env"


class PlaneSettings(BaseSettings):
    """Load private-plane authorities without importing execution settings/engine."""

    model_config = SettingsConfigDict(
        env_prefix="PT_", env_file=_env_file(), env_file_encoding="utf-8", extra="ignore",
    )

    production: bool = False
    research_database_url: str = ""
    ledger_database_url: str = ""
    research_db_path: str = ""
    ledger_db_path: str = ""
    research_operation_receipt: str = ""
    research_operation_lock: str = ""
