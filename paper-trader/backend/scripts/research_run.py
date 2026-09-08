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
import sys
import datetime as dt

from app.ir.hashing import content_address

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
    # API admission and the worker must name the same running build. A checkout
    # HEAD can differ from a deployed VERSION or be absent from release artifacts.
    from app.core.version import get_build_sha
    return get_build_sha()


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

    from research.config import database_authority_label, research_database_url
    from research.guards import enforce
    from app.core.config import get_settings
    from app.db.engine import database_url
    from app.ledger.config import ledger_database_url

    research_db = research_database_url()
    exec_db = database_url(get_settings())
    print(f"research.db = {database_authority_label(research_db)}\n"
          f"exec.db     = {database_authority_label(exec_db)}  "
          "(read-only V2 authority facts; never execution writes)\n")

    # (1) fail closed BEFORE any work
    enforce(research_db=research_db, exec_db=exec_db,
            ledger_db=ledger_database_url(),
            loaded_modules=sys.modules, env=os.environ)
    print("guardrails: PASS (distinct DBs · no order/broker/runner imports · not live)\n")
    return research_db


def _research_enabled() -> bool:
    from app.core.config import get_settings

    return get_settings().research_enabled


def _operation_failure(error):
    from research.orchestrator.generate import ResearchAdmissionRefused
    from research.orchestrator.v2_operation import V2OperationRefusal
    if isinstance(error, V2OperationRefusal):
        return {"code": error.code, "message": str(error)[:500]}
    if isinstance(error, ResearchAdmissionRefused):
        return {"code": error.code.value, "message": "research operation refused"}
    return {"code": "RESEARCH_OPERATION_FAILED", "message": "research operation refused"}


def _operation_heartbeat(research_db, operation_id, scoped_owner, token):
    from research.domain.base import make_engine, make_sessionmaker
    from research.domain.operations import ResearchOperationRepository
    engine = make_engine(research_db)
    try:
        with make_sessionmaker(engine)() as session:
            return ResearchOperationRepository(session).heartbeat(operation_id, owner_id=scoped_owner, token=token)
    finally:
        engine.dispose()


def _verified_claim(repository, recorder, owner_id):
    from app.core.config import get_settings
    from research.orchestrator.v2_operation import V2_PROVIDER_MODE
    claimed = repository.get(recorder.operation_id, owner_id=owner_id)
    if claimed is None:
        raise RuntimeError("claimed research operation disappeared")
    if claimed.build != _git_commit():
        _replay_refused(recorder, "research operation replay requires its admitted build and provider mode")
    expected_provider = V2_PROVIDER_MODE if claimed.trigger == "v2_graph" else get_settings().provider
    if claimed.provider_mode != expected_provider:
        message = ("research operation replay requires persisted-dataset mode" if claimed.trigger == "v2_graph"
                   else "research operation replay requires its admitted build and provider mode")
        _replay_refused(recorder, message)
    return claimed


def _replay_refused(recorder, message):
    recorder.fail({"code": "RESEARCH_OPERATION_PROVENANCE_MISMATCH", "message": message})
    raise RuntimeError("research operation replay provenance mismatch")


def _run_claimed_v2(claimed, recorder, repository, session, research_db):
    from functools import partial
    # Cold component-library imports can outlast a claim lease. Protect the
    # claimed job before loading that library, not only during its evaluation.
    recorder.start_watchdog(partial(_operation_heartbeat, research_db))
    from app.db.session import SessionLocal
    from research.orchestrator.graph_experiment import run_saved_v2_graph_experiment
    from research.orchestrator.v2_operation import V2_PROVIDER_MODE
    recorder.transition("planning")
    with SessionLocal() as execution_session:
        report = run_saved_v2_graph_experiment(operation=claimed, recorder=recorder,
            repository=repository, execution_session=execution_session, research_session=session)
    # The caller-owned run transaction already committed terminal operation facts.
    recorder.close_watchdog()
    return [report], V2_PROVIDER_MODE


def _fresh_manual_operation(session, repository, owner_id):
    from app.core.config import get_settings
    from app.core.instruments import get_instrument
    from research.domain.operations import DurableOperationRecorder
    from research.operations import safe_plan_summary
    from research.orchestrator.generate import generated_descriptors
    from research.universe import ALWAYS_ALLOWED
    plan = _plan(get_instrument)
    summary = safe_plan_summary(plan)
    sandbox = [get_instrument(key) for key in UNIVERSE if key in ALWAYS_ALLOWED]
    descriptors = []
    if sandbox:
        for interval in INTERVALS:
            descriptors.extend(generated_descriptors(session, sandbox, interval, owner_id=owner_id,
                limit=8, seed=None, git_commit=_git_commit(), provider_mode=get_settings().provider,
                min_trades=30, n_folds=4, min_positive_fold_frac=0.5))
    payload = {"experiment_count": summary["experiment_count"] + len(descriptors),
               "items": summary["items"], "generated": descriptors}
    summary = {"content_address": content_address(payload), **payload}
    recorder = DurableOperationRecorder.start(repository, owner_id=owner_id, trigger="manual",
        build=_git_commit(), provider_mode=get_settings().provider,
        worker_id=f"manual:{os.getpid()}", plan=summary)
    return recorder, plan, summary


def _run_generated_interval(session, source, entries, interval, owner_id, recorder):
    from app.core.instruments import get_instrument
    from research.orchestrator.generate import run_generated
    descriptors, keys = zip(*entries)
    sandbox = [get_instrument(key) for key in descriptors[0]["owner_universe"]]
    reports = run_generated(session, source, sandbox, interval, owner_id=owner_id,
        limit=len(descriptors), git_commit=_git_commit(), min_trades=30, n_folds=4,
        min_positive_fold_frac=0.5, claim_guard=getattr(recorder, "assert_claim", None),
        durable_descriptors=list(descriptors), durable_item_keys=list(keys),
        completed_item_run=recorder.completed_item_run, bound_item_run=recorder.bound_item_run,
        reclaim_bound_item=recorder.reclaim_bound_item, bind_item_run=recorder.bind_item_run_in_transaction,
        finalize_item=recorder.finalize_item_in_transaction)
    for report in reports:
        if isinstance(report.get("run_id"), int):
            recorder.add_completed_run(report["run_id"])
    return reports


def _run_generated_items(session, source, descriptors, keys, owner_id, recorder):
    by_interval = {}
    for descriptor, item_key in zip(descriptors, keys):
        by_interval.setdefault(descriptor["interval"], []).append((descriptor, item_key))
    reports = []
    if by_interval:
        print("\n── code-gen: composing strategies on the sandbox from admitted durable descriptors ──")
        for interval, entries in by_interval.items():
            reports += _run_generated_interval(session, source, entries, interval, owner_id, recorder)
    return reports


def _run_manual_items(session, recorder, plan, summary, owner_id, research_db):
    from functools import partial
    from research.domain.operations import operation_item_keys
    from research.orchestrator.run import run_nightly
    recorder.start_watchdog(partial(_operation_heartbeat, research_db))
    recorder.transition("planning")
    # Provider construction stays after durable workload admission and planning.
    from app.providers.factory import get_provider
    from research.data.store import KiteDataSource
    provider = get_provider()
    source = KiteDataSource(provider=provider)
    report_dir = os.environ.get("PT_RESEARCH_REPORT_DIR", ".")
    os.makedirs(report_dir, exist_ok=True)
    keys = operation_item_keys(summary, trigger="manual")
    reports = run_nightly(session, source, plan, owner_id=owner_id, git_commit=_git_commit(),
        report_dir=report_dir, progress=recorder.add_completed_run, stage=recorder.transition,
        item_keys=keys[:len(plan)], completed_item_run=getattr(recorder, "completed_item_run", None),
        bound_item_run=getattr(recorder, "bound_item_run", None),
        bind_item_run=getattr(recorder, "bind_item_run_in_transaction", None),
        finalize_item=getattr(recorder, "finalize_item_in_transaction", None))
    recorder.transition("generation")
    reports += _run_generated_items(session, source, summary.get("generated", []), keys[len(plan):], owner_id, recorder)
    _dump_db(session)
    return reports, provider.name


def _run_enabled_operation(research_db: str) -> tuple[list, str]:
    from app.core.instruments import get_instrument
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.domain.operations import DurableOperationRecorder, ResearchOperationRepository, reconstruct_plan
    owner_id = os.environ.get("PT_RESEARCH_OWNER_ID")
    if not owner_id:
        raise RuntimeError("PT_RESEARCH_OWNER_ID is required for manual research")
    engine = None
    try:
        engine = make_engine(research_db)
        init_research_db(engine)
        with make_sessionmaker(engine)() as session:
            repository = ResearchOperationRepository(session)
            repository.reconcile_expired(owner_id=owner_id)
            recorder = DurableOperationRecorder.claim_next(repository, owner_id=owner_id,
                worker_id=f"manual:{os.getpid()}", triggers=("v2_graph", "manual"))
            if recorder is not None:
                claimed = _verified_claim(repository, recorder, owner_id)
                if claimed.trigger == "v2_graph":
                    return _run_claimed_v2(claimed, recorder, repository, session, research_db)
                summary = claimed.plan
                plan = reconstruct_plan(summary, instrument_for_key=get_instrument)
            else:
                recorder, plan, summary = _fresh_manual_operation(session, repository, owner_id)
            reports = _run_manual_items(session, recorder, plan, summary, owner_id, research_db)
        recorder.complete()
        return reports
    except Exception as exc:
        try:
            recorder.close_watchdog()
            recorder.fail(_operation_failure(exc))
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
        if "report_path" in rep:
            print(f"REPORT: {rep['report_path']}")
            print("=" * 78)
            with open(rep["report_path"]) as fh:
                print(fh.read())
        else:
            print("SAVED V2 RESEARCH RECEIPT")
            print("=" * 78)
            print(json.dumps({key: rep[key] for key in (
                "spec_id", "run_id", "decision", "total_bars"
            ) if key in rep}, sort_keys=True))
    source_label = ("persisted canonical data" if provider_name == "persisted-dataset"
                    else f"live {provider_name} data")
    print(f"\ndone — {len(reports)} experiment(s) run against {source_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
