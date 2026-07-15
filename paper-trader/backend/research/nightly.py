"""Nightly research entry point — the cron one-shot (`python -m research.nightly`).

It (1) enforces the fail-closed capital guardrails, (2) ensures research.db exists,
then (3) runs the configured research plan through the orchestrator (qualify ->
validate -> score -> knowledge -> promotion -> report). The plan is empty until the
scheduler/config lands (M3), so an unconfigured run is a safe no-op that still proves
the guardrails and schema.

Run by cron at ~19:00 IST (well after the 15:30 close, well before the ~06:00 token
rollover), under its own lockfile so a slow run never overlaps the next.
"""
from __future__ import annotations

import os
import subprocess
import sys

from research.config import research_db_path
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.guards import enforce
from research.orchestrator.run import run_nightly


def _execution_db_path() -> str:
    """The execution DB path, read-only. Importing app.core.config binds no DB
    engine (unlike app.db.session), so this cannot open the money ledger."""
    from app.core.config import get_settings

    return get_settings().db_path


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL).strip()[:40] or "unknown"
    except Exception:
        return "unknown"


def _load_plan() -> list:
    """The research plan (which programs/hypotheses/instruments to run tonight).
    Empty until the M3 scheduler + config supplies one; a configured autonomous run
    would resolve the qualifying universe by Hypothesis.retest_priority."""
    return []


def main() -> int:
    research_db = research_db_path()
    # Fail closed BEFORE any research work: distinct DB, no capital-moving imports,
    # not live. Any violation raises ResearchIsolationError and aborts the run.
    enforce(research_db=research_db, exec_db=_execution_db_path(),
            loaded_modules=sys.modules, env=os.environ)
    # Freeze gate (checked AFTER the guardrails so an isolation violation still
    # fails loudly even while frozen): with the research plane disabled the cron
    # one-shot is a no-op — no research.db is created or touched.
    from app.core.config import get_settings
    if not get_settings().research_enabled:
        print("research plane disabled (PT_RESEARCH_ENABLED=0) — nightly run skipped")
        return 0
    engine = make_engine(research_db)
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as session:
        reports = run_nightly(session, source=None, plan=_load_plan(),
                              git_commit=_git_commit(),
                              report_dir=os.environ.get("PT_RESEARCH_REPORT_DIR", "."))
    print(f"research.db ready at {research_db}; ran {len(reports)} experiment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
