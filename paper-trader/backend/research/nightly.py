"""Nightly research entry point — the cron one-shot (`python -m research.nightly`).

Foundations stub: it does the two things every research run must do first —
(1) enforce the fail-closed capital guardrails, (2) ensure research.db exists —
and nothing else yet. The pipeline stages (qualify -> optimize -> validate ->
score -> decide -> report) land in M1 and hang off here.

Run by cron at ~19:00 IST (well after the 15:30 close, well before the ~06:00
token rollover), under its own lockfile so a slow run never overlaps the next.
"""
from __future__ import annotations

import os
import sys

from research.config import research_db_path
from research.domain.base import init_research_db, make_engine
from research.guards import enforce


def _execution_db_path() -> str:
    """The execution DB path, read-only. Importing app.core.config binds no DB
    engine (unlike app.db.session), so this cannot open the money ledger."""
    from app.core.config import get_settings

    return get_settings().db_path


def main() -> int:
    research_db = research_db_path()
    # Fail closed BEFORE any research work: distinct DB, no capital-moving imports,
    # not live. Any violation raises ResearchIsolationError and aborts the run.
    enforce(research_db=research_db, exec_db=_execution_db_path(),
            loaded_modules=sys.modules, env=os.environ)
    init_research_db(make_engine(research_db))
    print(f"research.db ready at {research_db}; pipeline stages arrive in M1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
