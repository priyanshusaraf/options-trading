"""Research-plane configuration — deliberately independent of app.core.config so
the research process never imports (and never binds) the execution DB engine.

Only what the research plane needs lives here; it reads its own ``PT_RESEARCH_*``
environment, never the execution ``.env`` implicitly.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_RESEARCH_DB = "research.db"


def research_db_path(env: Mapping | None = None) -> str:
    """Path to research.db (``PT_RESEARCH_DB_PATH``; default ``research.db``)."""
    e = os.environ if env is None else env
    return e.get("PT_RESEARCH_DB_PATH", DEFAULT_RESEARCH_DB)
