"""Journal configuration — deliberately independent of app.core.config so the
journal never implicitly binds the execution DB engine. Mirrors
research/config.py's isolation pattern.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_JOURNAL_DB = "journal.db"


def journal_db_path(env: Mapping | None = None) -> str:
    """Path to journal.db (``PT_JOURNAL_DB_PATH``; default ``journal.db``)."""
    e = os.environ if env is None else env
    return e.get("PT_JOURNAL_DB_PATH", DEFAULT_JOURNAL_DB)
