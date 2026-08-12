"""Nightly research entry point — the cron one-shot (`python -m research.nightly`).

It (1) enforces the fail-closed capital guardrails, (2) ensures research.db exists,
then (3) builds the bounded server-owned plan and runs it through the orchestrator
(qualify -> validate -> score -> knowledge -> promotion -> report). An empty plan is
a safe no-op that still proves the guardrails and schema.

Run by cron at ~19:00 IST (well after the 15:30 close, well before the ~06:00 token
rollover), under its own lockfile so a slow run never overlaps the next.
"""
from __future__ import annotations

import os
import subprocess
import sys
import datetime as dt

from research.config import (nightly_generate_limit, nightly_interval,
                             nightly_search_seed, nightly_strategy_key,
                             research_db_path, watchlist_snapshot_path)
from research.plan import build_plan
from research.universe import eligible_for_research, read_watchlist_snapshot
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.guards import enforce
from research.orchestrator.report import write_report
from research.orchestrator.run import run_nightly
from research.operations import safe_plan_summary


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


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def _load_plan(session, *, owner_id: str) -> list:
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
    plan = build_plan(session, owner_id=owner_id, eligible=eligible, strategy_key=nightly_strategy_key(),
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


def _run_generation(session, source, plan, report_dir) -> list:
    """Explore generated COMPOSITIONS, not just the handwritten strategy.

    This is what makes the loop actually search rather than re-measure one idea
    every night. It reuses the plan's instrument set so generation and the
    handwritten baseline are evaluated on exactly the same universe — otherwise a
    difference in results could just be a difference in what they were run on.

    Note this is genuinely expensive: each composition is a full
    qualify -> optimize -> validate -> score pass over every instrument, and since
    2026-08-01 the composition count also inflates the DSR deflation via
    `sibling_trials`, so a wider search raises the bar it has to clear. That is the
    intended trade and the reason the limit is bounded and configurable.
    """
    limit = nightly_generate_limit()
    if not limit or not plan:
        return []
    from research.orchestrator.generate import run_generated

    instruments = plan[0]["instruments"]
    interval = plan[0]["interval"]
    print(f"generation: exploring up to {limit} composition(s) on "
          f"{len(instruments)} instrument(s) @ {interval}"
          f"{f' (sampled, seed={nightly_search_seed()})' if nightly_search_seed() is not None else ' (fixed grid)'}")
    seed = nightly_search_seed()
    owner_id = os.environ["PT_RESEARCH_OWNER_ID"]
    reports = run_generated(session, source, instruments, interval, owner_id=owner_id, limit=limit,
                            git_commit=_git_commit(), seed=seed)
    for i, report in enumerate(reports, 1):
        path = os.path.join(report_dir, f"report_generated_{report.get('run_id', i)}.md")
        write_report(report, path)
        report["report_path"] = path
    return reports


def _run_enabled_operation(research_db: str) -> list:
    from app.core.config import get_settings

    owner_id = os.environ.get("PT_RESEARCH_OWNER_ID")
    if not owner_id:
        raise RuntimeError("PT_RESEARCH_OWNER_ID is required for nightly research")
    engine = None
    try:
        engine = make_engine(research_db)
        init_research_db(engine)
        Session = make_sessionmaker(engine)
        with Session() as session:
            from research.domain.operations import DurableOperationRecorder, ResearchOperationRepository
            plan = _load_plan(session, owner_id=owner_id)
            # Admission (including the bounded, secret-free durable manifest)
            # comes before the provider is even constructed.  An invalid plan
            # must not consume an API call or create a live-data object.
            recorder = DurableOperationRecorder.start(
                ResearchOperationRepository(session), owner_id=owner_id, trigger="nightly",
                build=_git_commit(), provider_mode=get_settings().provider,
                worker_id=f"nightly:{os.getpid()}", plan=safe_plan_summary(plan),
            )
            def _heartbeat(operation_id: str, scoped_owner: str, token: str) -> bool:
                watchdog_engine = make_engine(research_db)
                try:
                    with make_sessionmaker(watchdog_engine)() as watchdog_session:
                        return ResearchOperationRepository(watchdog_session).heartbeat(
                            operation_id, owner_id=scoped_owner, token=token)
                finally:
                    watchdog_engine.dispose()
            recorder.start_watchdog(_heartbeat)
            recorder.transition("planning")
            src = _make_source()
            report_dir = os.environ.get("PT_RESEARCH_REPORT_DIR", ".")
            reports = run_nightly(session, source=src, plan=plan, owner_id=owner_id,
                git_commit=_git_commit(), report_dir=report_dir,
                progress=recorder.add_completed_run, stage=recorder.transition)
            recorder.transition("generation")
            generated = _run_generation(session, src, plan, report_dir)
            for report in generated:
                if isinstance(report.get("run_id"), int):
                    recorder.add_completed_run(report["run_id"])
            reports += generated
            recorder.complete()
            return reports
    except Exception:
        try:
            recorder.fail({"code": "RESEARCH_OPERATION_FAILED", "message": "research operation failed"})
        except (UnboundLocalError, RuntimeError):
            pass
        raise
    finally:
        if engine is not None:
            engine.dispose()


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
    reports = _run_enabled_operation(research_db)
    print(f"research.db ready at {research_db}; ran {len(reports)} experiment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
