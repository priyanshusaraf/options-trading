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

from research.config import (nightly_interval, nightly_strategy_key,
                             research_db_path, watchlist_snapshot_path)
from research.plan import build_plan
from research.universe import eligible_for_research, read_watchlist_snapshot
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


def _load_plan(session) -> list:
    """Tonight's plan: open hypotheses by retest_priority over the research-eligible
    universe. See research/plan.py for the two rules that govern it.

    Eligibility is resolved HERE rather than inside `build_plan` because it needs
    the execution side's instrument list and watchlist snapshot, and keeping that
    at the edge leaves `build_plan` pure over its inputs.
    """
    from app.core.instruments import all_instruments

    snapshot_path = watchlist_snapshot_path()
    committed = read_watchlist_snapshot(snapshot_path)
    if not committed:
        # Permissive fallback — say so. "Nothing is committed" and "I could not
        # read what is committed" look identical downstream, and only one of them
        # is safe to assume.
        print(f"WARNING: no watchlist snapshot at {snapshot_path!r} — treating every "
              f"instrument as research-eligible. If the execution side should have "
              f"exported one, this run may develop strategies on LIVE instruments.")
    by_key = {i.key: i for i in all_instruments()}
    eligible = eligible_for_research(set(by_key), committed)
    plan = build_plan(session, eligible=eligible, strategy_key=nightly_strategy_key(),
                      interval=nightly_interval())
    # `build_plan` deals in instrument KEYS so it stays pure over its inputs and
    # testable without the execution-side registry; `run_nightly` needs the
    # Instrument objects to fetch candles. Resolve at the edge, here.
    for item in plan:
        item["instruments"] = [by_key[k] for k in item["instruments"] if k in by_key]
    print(f"plan: {len(plan)} experiment(s) over {len(eligible)} eligible instrument(s)"
          f"{' (cold start)' if plan and not committed else ''}")
    return plan


def _make_source():
    """The candle source for tonight's collection phase.

    Built from the SAME provider seam the execution side uses, so research reads
    the same bars the engine would — with `PT_PROVIDER=mock` (the default) that is
    a deterministic offline series and no network is touched at all.

    Only the orchestrator's collection phase calls this; the pipeline itself reads
    frozen, content-hashed Datasets. Note the isolation guard has already run by
    this point: it is a BOOT-time assertion about what was imported before research
    started, not a continuous one.
    """
    from app.providers.factory import get_provider
    from research.data.store import KiteDataSource

    return KiteDataSource(get_provider())


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
        reports = run_nightly(session, source=_make_source(), plan=_load_plan(session),
                              git_commit=_git_commit(),
                              report_dir=os.environ.get("PT_RESEARCH_REPORT_DIR", "."))
    print(f"research.db ready at {research_db}; ran {len(reports)} experiment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
