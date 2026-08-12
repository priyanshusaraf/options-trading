"""Research-plane configuration — deliberately independent of app.core.config so
the research process never imports (and never binds) the execution DB engine.

Only what the research plane needs lives here; it reads its own ``PT_RESEARCH_*``
environment, never the execution ``.env`` implicitly.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy.engine import make_url

DEFAULT_RESEARCH_DB = "research.db"


def research_db_path(env: Mapping | None = None) -> str:
    """Path to research.db (``PT_RESEARCH_DB_PATH``; default ``research.db``)."""
    e = os.environ if env is None else env
    return e.get("PT_RESEARCH_DB_PATH", DEFAULT_RESEARCH_DB)


def _production_enabled(env: Mapping) -> bool:
    return str(env.get("PT_PRODUCTION", "")).strip().lower() in {"1", "true", "yes", "on"}


def research_database_url(
    env: Mapping | None = None, *, database_url: str | None = None,
    production: bool | None = None, db_path: str | None = None,
) -> str:
    """Return the research-plane authority, with a local SQLite path fallback."""
    if env is not None:
        explicit = str(env.get("PT_RESEARCH_DATABASE_URL", "")).strip()
        is_production = _production_enabled(env)
        fallback = research_db_path(env)
    elif database_url is not None or production is not None or db_path is not None:
        explicit = str(database_url or "").strip()
        is_production = bool(production)
        fallback = db_path or DEFAULT_RESEARCH_DB
    else:
        from app.db.plane_config import PlaneSettings

        settings = PlaneSettings()
        explicit = settings.research_database_url.strip()
        is_production = settings.production
        fallback = settings.research_db_path or DEFAULT_RESEARCH_DB
    if explicit:
        if is_production and make_url(explicit).get_backend_name() != "postgresql":
            raise RuntimeError(
                "PT_PRODUCTION=1 requires a PostgreSQL PT_RESEARCH_DATABASE_URL"
            )
        return explicit
    if is_production:
        raise RuntimeError("PT_RESEARCH_DATABASE_URL is required when PT_PRODUCTION=1")
    return f"sqlite:///{fallback}"


def database_authority_label(authority: str) -> str:
    """Return a diagnostic label with no credentials or URL query values."""
    parsed = make_url(authority if "://" in authority else f"sqlite:///{authority}")
    if parsed.get_backend_name() == "sqlite":
        return f"sqlite:///{parsed.database or ''}"
    host = parsed.host or "local"
    port = f":{parsed.port}" if parsed.port is not None else ""
    database = f"/{parsed.database}" if parsed.database else ""
    return f"{parsed.get_backend_name()}://{host}{port}{database}"


def operation_receipt_path(env: Mapping | None = None) -> str:
    """Canonical current/last operation receipt beside research.db by default."""
    if env is None:
        from app.db.plane_config import PlaneSettings

        settings = PlaneSettings()
        explicit = settings.research_operation_receipt
        database_url = settings.research_database_url
        path = settings.research_db_path or DEFAULT_RESEARCH_DB
    else:
        explicit = env.get("PT_RESEARCH_OPERATION_RECEIPT")
        database_url = str(env.get("PT_RESEARCH_DATABASE_URL", "")).strip()
        path = research_db_path(env)
    if explicit:
        return explicit
    if database_url:
        return "research.operations.json"
    return f"{path}.operations.json"


def operation_lock_path(env: Mapping | None = None) -> str:
    """Shared process lock used by every bounded research entry point."""
    if env is None:
        from app.db.plane_config import PlaneSettings

        explicit = PlaneSettings().research_operation_lock
    else:
        explicit = env.get("PT_RESEARCH_OPERATION_LOCK")
    return explicit or f"{operation_receipt_path(env)}.lock"


DEFAULT_WATCHLIST_SNAPSHOT = "research_watchlist_snapshot.json"


def watchlist_snapshot_path(env: Mapping | None = None) -> str:
    """Path to the read-only watchlist snapshot the execution side exports
    (``PT_RESEARCH_WATCHLIST_SNAPSHOT``).

    A JSON snapshot rather than a DB read on purpose: the research plane must
    never open the execution ledger to learn what is committed. A MISSING file
    means "nothing known to be committed", which keeps an unconfigured run safe
    — but note it is safe in the permissive direction, so the nightly logs
    loudly when it falls back.
    """
    e = os.environ if env is None else env
    return e.get("PT_RESEARCH_WATCHLIST_SNAPSHOT", DEFAULT_WATCHLIST_SNAPSHOT)


DEFAULT_STRATEGY_KEY = "trend_impulse_v3"


def nightly_strategy_key(env: Mapping | None = None) -> str:
    """Which registered strategy the nightly plan runs (``PT_RESEARCH_STRATEGY``)."""
    e = os.environ if env is None else env
    return e.get("PT_RESEARCH_STRATEGY", DEFAULT_STRATEGY_KEY)


# 15m, not daily. CLAUDE.md: the strategy is valid on 15m/30m only, and a daily
# plan produced 1-5 trades per instrument against a 20-trade floor — every
# instrument rejected for insufficient sample rather than for lack of edge, which
# tells you nothing.
DEFAULT_NIGHTLY_INTERVAL = "15minute"


def nightly_interval(env: Mapping | None = None) -> str:
    """Candle interval for the nightly plan (``PT_RESEARCH_INTERVAL``)."""
    e = os.environ if env is None else env
    return e.get("PT_RESEARCH_INTERVAL", DEFAULT_NIGHTLY_INTERVAL)


# How many generated compositions the nightly explores. Bounded because each one
# is a full qualify -> optimize -> validate -> score pass over every instrument in
# the plan, and because the composition count now inflates the DSR deflation
# (sibling_trials): a wider search genuinely raises the bar it must clear.
DEFAULT_GENERATE_LIMIT = 8
# Generated descriptors are admitted as durable operation items.  Keep the
# configuration boundary inside the descriptor grammar's hard maximum so an
# oversized environment value cannot make the search enumerate work that the
# scheduler must reject afterward.
MAX_GENERATED_OPERATION_ITEMS = 64


def nightly_generate_limit(env: Mapping | None = None) -> int:
    """Compositions to explore per night (``PT_RESEARCH_GENERATE_LIMIT``).
    0 disables generation — the nightly then only runs the handwritten strategy."""
    e = os.environ if env is None else env
    try:
        return min(MAX_GENERATED_OPERATION_ITEMS,
                   max(0, int(e.get("PT_RESEARCH_GENERATE_LIMIT", DEFAULT_GENERATE_LIMIT))))
    except (TypeError, ValueError):
        return DEFAULT_GENERATE_LIMIT


def nightly_search_seed(env: Mapping | None = None) -> int | None:
    """Seed for composition SAMPLING (``PT_RESEARCH_SEARCH_SEED``).

    Unset -> None -> the deterministic hand-picked grid (a stable control).
    Set -> draw from the block registry, which is the only way a newly
    registered block is ever reached. Deterministic per seed so any composition
    can be regenerated from the run that produced it.
    """
    e = os.environ if env is None else env
    raw = e.get("PT_RESEARCH_SEARCH_SEED")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
