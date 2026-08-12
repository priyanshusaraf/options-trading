"""Path resolution for the ledger DB.

Deliberately does NOT import app.core.config, so importing the ledger never
implicitly binds the execution DB engine. Mirrors the isolation the deleted
journal package had, which was the one thing about it worth keeping."""
from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy.engine import make_url

# Absolute by construction. A bare relative default resolves against the process
# cwd, so a systemd restart with a different WorkingDirectory would silently
# create a second, empty journal. See the design spec §9.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LEDGER_DB = os.path.join(_BACKEND_DIR, "ledger.db")


def ledger_db_path(env: Mapping[str, str] | None = None) -> str:
    e = os.environ if env is None else env
    return e.get("PT_LEDGER_DB_PATH") or DEFAULT_LEDGER_DB


def _production_enabled(env: Mapping[str, str]) -> bool:
    return str(env.get("PT_PRODUCTION", "")).strip().lower() in {"1", "true", "yes", "on"}


def ledger_database_url(
    env: Mapping[str, str] | None = None, *, database_url: str | None = None,
    production: bool | None = None, db_path: str | None = None,
) -> str:
    """Return the ledger authority, retaining its local SQLite path fallback."""
    if env is not None:
        explicit = str(env.get("PT_LEDGER_DATABASE_URL", "")).strip()
        is_production = _production_enabled(env)
        fallback = ledger_db_path(env)
    elif database_url is not None or production is not None or db_path is not None:
        explicit = str(database_url or "").strip()
        is_production = bool(production)
        fallback = db_path or DEFAULT_LEDGER_DB
    else:
        from app.db.plane_config import PlaneSettings

        settings = PlaneSettings()
        explicit = settings.ledger_database_url.strip()
        is_production = settings.production
        fallback = settings.ledger_db_path or DEFAULT_LEDGER_DB
    if explicit:
        if is_production and make_url(explicit).get_backend_name() != "postgresql":
            raise RuntimeError("PT_PRODUCTION=1 requires a PostgreSQL PT_LEDGER_DATABASE_URL")
        return explicit
    if is_production:
        raise RuntimeError("PT_LEDGER_DATABASE_URL is required when PT_PRODUCTION=1")
    return f"sqlite:///{fallback}"
