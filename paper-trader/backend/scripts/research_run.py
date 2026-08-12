"""Headless end-to-end run of the autonomous research pipeline over a SMALL live
universe — the human-triggered sibling of `research.nightly`.

It does exactly what the nightly cron will do, with a hand-written plan:
  1. enforce the fail-closed capital guardrails (distinct DB, no order/broker/runner
     imports, not a live-execution environment) — abort on any violation;
  2. init research.db;
  3. materialize a few index underlyings from the *live* provider into content-hashed
     Datasets (data collection is the ONLY place a provider is touched);
  4. run each experiment through qualify -> (optimize) -> validate -> score -> deposit
     Findings -> queue a PromotionCandidate -> update the hypothesis -> write a report;
  5. dump every research.db table and print each generated report.

Data source is whatever PT_PROVIDER selects (kite for live candles). No capital moves:
the provider is SafePaperKite (orders hard-disabled) and the research plane never
constructs a broker. Run from backend/:

    PT_RESEARCH_ENABLED=1 PT_PROVIDER=kite PT_RESEARCH_DB_PATH=/tmp/research.db \
    PT_RESEARCH_REPORT_DIR=/tmp/reports .venv/bin/python scripts/research_run.py
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import datetime as dt

# make `app` and `research` importable when this file is run directly as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The strategy is valid only on 15m/30m candles (see CLAUDE.md), so we test on BOTH
# of its native timeframes and compare — an edge that shows on one bar size but not
# the other is a useful signal in itself. Kite caps 15minute AND 30minute history at
# 200 days/request (sweep.MAX_DAYS), so DAYS=180 is safe for both. Sweep the full
# liquid seed universe with BOTH strategies × BOTH intervals and let a real survivor
# surface if one exists — gates are never loosened to manufacture one.
UNIVERSE = ["NIFTY", "BANKNIFTY", "SENSEX", "GOLDM", "SILVERM",
            "CRUDEOIL", "NATURALGAS", "COPPERM"]
INTERVALS = ["15minute", "30minute"]
DAYS = 180

# (strategy_key, program name, hypothesis stem) — the interval is appended per sweep.
_STRATEGIES = [
    ("trend_impulse_v3", "Trend-Impulse (liquid universe)",
     "Displacement-confirmed EMA50 trend persists on liquid underlyings"),
    ("expanding_z_v4", "Expanding-Z Reversion (liquid universe)",
     "Expanding-window z-score reversion adds edge on liquid underlyings"),
]


def _plan(get_instrument):
    # Dev-blacklist: never develop on an instrument committed to a live watchlist
    # (except the always-allowed sandbox). Membership comes from a read-only snapshot
    # the execution side exports — the research process never opens the trading DB.
    from research.universe import eligible_for_research, read_watchlist_snapshot
    committed = read_watchlist_snapshot(os.environ.get("PT_WATCHLIST_SNAPSHOT", ""))
    eligible = eligible_for_research(set(UNIVERSE), committed)
    universe = [k for k in UNIVERSE if k in eligible]
    excluded = [k for k in UNIVERSE if k not in eligible]
    if excluded:
        logging.getLogger("research").info(
            "dev-blacklist: skipping %s (committed to live watchlists)", excluded)
    insts = [get_instrument(k) for k in universe]
    plan = []
    for interval in INTERVALS:
        common = dict(instruments=insts, interval=interval, days=DAYS,
                      min_trades=30, n_folds=4, min_positive_fold_frac=0.5,
                      optimize_search=True)
        for key, program, hypothesis in _STRATEGIES:
            plan.append({"program": program,
                         "hypothesis": f"{hypothesis} ({interval})",
                         "strategy_key": key, **common})
    return plan


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()[:40] or "unknown"
    except Exception:
        return "unknown"


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def _dump_db(session) -> None:
    from research.domain.models import (
        ExperimentRun, ExperimentSpec, Finding, Hypothesis,
        OptimizationTrial, PromotionCandidate, ResearchProgram,
    )
    q = session.query
    print("\n" + "=" * 78)
    print("research.db — populated tables")
    print("=" * 78)

    print(f"\nResearchProgram ({q(ResearchProgram).count()})")
    for p in q(ResearchProgram).all():
        print(f"  #{p.id} {p.name!r}  status={p.status}")

    print(f"\nHypothesis ({q(Hypothesis).count()})")
    for h in q(Hypothesis).all():
        tested = (f"{h.last_tested_at:%Y-%m-%d %H:%M}" if h.last_tested_at else "untested")
        print(f"  #{h.id} status={h.status:9s} retest_priority={h.retest_priority:.3f}"
              f"  last_tested={tested}")
        print(f"       {h.statement!r}")

    print(f"\nExperimentSpec ({q(ExperimentSpec).count()}) — IMMUTABLE, content-addressed")
    for s in q(ExperimentSpec).all():
        print(f"  {s.id}  commit={s.git_commit}  seed={s.rng_seed}  "
              f"versions=[q:{s.qualifier_version} o:{s.optimizer_version} "
              f"v:{s.validator_version} s:{s.scoring_version}]")

    print(f"\nExperimentRun ({q(ExperimentRun).count()})")
    for r in q(ExperimentRun).all():
        print(f"  #{r.id} spec={r.spec_id[:12]}… status={r.status} decision={r.decision} "
              f"bars={r.spent_bar_seconds:.0f}")

    print(f"\nOptimizationTrial ({q(OptimizationTrial).count()}) — IMMUTABLE trial ledger")
    sel = q(OptimizationTrial).filter_by(selected=True).count()
    print(f"  {q(OptimizationTrial).count()} trials, {sel} selected (fold winners)")
    for t in q(OptimizationTrial).filter_by(selected=True).all():
        print(f"    [selected] {t.instrument_key} fold {t.fold_index}: {t.params_json} "
              f"is_obj={t.is_objective:.1f} is_trades={t.is_trades} oos_trades={t.oos_trades}")

    print(f"\nFinding ({q(Finding).count()}) — revisable knowledge, negative first-class")
    for f in q(Finding).all():
        print(f"  [{f.polarity:8s} conf={f.confidence:.2f}] {f.statement}")

    from research.domain.models import GeneratedStrategyRecord
    print(f"\nGeneratedStrategyRecord ({q(GeneratedStrategyRecord).count()}) — bot-composed, sandboxed Python")
    for g in q(GeneratedStrategyRecord).all():
        print(f"  {g.key}  ({len(g.source.splitlines())} lines of emitted compute)")

    print(f"\nPromotionCandidate ({q(PromotionCandidate).count()}) — human-gated, NOT auto-deployed")
    for c in q(PromotionCandidate).all():
        print(f"  #{c.id} run={c.run_id} status={c.status} "
              f"param_hash={c.parameterization_hash[:12]}… universe={c.qualifying_universe_json}")


def _enforce_isolation() -> str:
    # research plane must NEVER run in a live-execution environment
    os.environ.pop("PT_EXECUTION", None)
    os.environ.setdefault("PT_PROVIDER", "kite")

    from research.config import research_db_path
    from research.guards import enforce
    from app.core.config import get_settings

    research_db = research_db_path()
    exec_db = get_settings().db_path
    print(f"research.db = {research_db}\nexec.db     = {exec_db}  (never opened)\n")

    # (1) fail closed BEFORE any work
    enforce(research_db=research_db, exec_db=exec_db,
            loaded_modules=sys.modules, env=os.environ)
    print("guardrails: PASS (distinct DBs · no order/broker/runner imports · not live)\n")
    return research_db


def _research_enabled() -> bool:
    from app.core.config import get_settings

    return get_settings().research_enabled


def _run_enabled_operation(research_db: str) -> tuple[list, str]:
    from app.core.config import get_settings
    from app.core.instruments import get_instrument
    from app.providers.factory import get_provider
    from research.data.store import KiteDataSource
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.domain.operations import DurableOperationRecorder, ResearchOperationRepository
    from research.operations import safe_plan_summary
    from research.orchestrator.generate import run_generated
    from research.orchestrator.run import run_nightly
    from research.universe import ALWAYS_ALLOWED

    owner_id = os.environ.get("PT_RESEARCH_OWNER_ID")
    if not owner_id:
        raise RuntimeError("PT_RESEARCH_OWNER_ID is required for manual research")
    engine = None
    try:
            # (2) schema
            engine = make_engine(research_db)
            init_research_db(engine)
            Session = make_sessionmaker(engine)

            # (3) admit the bounded server-owned plan before constructing a
            # provider/source. Invalid work must fail without touching data I/O.
            with Session() as session:
                plan = _plan(get_instrument)
                recorder = DurableOperationRecorder.start(
                    ResearchOperationRepository(session), owner_id=owner_id, trigger="manual",
                    build=_git_commit(), provider_mode=get_settings().provider,
                    worker_id=f"manual:{os.getpid()}", plan=safe_plan_summary(plan),
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
                # (4) live data source (SafePaperKite — data only, orders
                # hard-disabled) is created only after durable admission.
                provider = get_provider()
                source = KiteDataSource(provider=provider)
                report_dir = os.environ.get("PT_RESEARCH_REPORT_DIR", ".")
                os.makedirs(report_dir, exist_ok=True)
                reports = run_nightly(
                    session,
                    source,
                    plan,
                    owner_id=owner_id,
                    git_commit=_git_commit(),
                    report_dir=report_dir,
                    progress=recorder.add_completed_run,
                    stage=recorder.transition,
                )
                recorder.transition("generation")
                sandbox = [get_instrument(k) for k in UNIVERSE if k in ALWAYS_ALLOWED]
                if sandbox:
                    print(f"\n── code-gen: composing strategies on the sandbox "
                          f"{[i.key for i in sandbox]} ──")
                    for interval in INTERVALS:
                        generated = run_generated(
                            session, source, sandbox, interval, owner_id=owner_id, limit=8,
                            git_commit=_git_commit(), min_trades=30, n_folds=4,
                            min_positive_fold_frac=0.5,
                        )
                        for report in generated:
                            if isinstance(report.get("run_id"), int):
                                recorder.add_completed_run(report["run_id"])
                _dump_db(session)
            recorder.complete()
            return reports, provider.name
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S")

    research_db = _enforce_isolation()
    if not _research_enabled():
        print("research plane disabled (PT_RESEARCH_ENABLED=0) — manual run skipped")
        return 0
    from research.operations import OperationAlreadyRunning

    try:
        reports, provider_name = _run_enabled_operation(research_db)
    except OperationAlreadyRunning:
        print("RESEARCH_OPERATION_ALREADY_RUNNING: another research operation owns the lock")
        return 2

    # (5) show every generated report
    for rep in reports:
        print("\n" + "=" * 78)
        print(f"REPORT: {rep['report_path']}")
        print("=" * 78)
        with open(rep["report_path"]) as fh:
            print(fh.read())
    print(f"\ndone — {len(reports)} experiment(s) run against live {provider_name} data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
