"""Headless end-to-end run of the autonomous research pipeline over a SMALL live
universe — the human-triggered sibling of `research.nightly` (which ships with an
empty plan until the M3 scheduler lands).

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

    PT_PROVIDER=kite PT_RESEARCH_DB_PATH=/tmp/research.db \
    PT_RESEARCH_REPORT_DIR=/tmp/reports .venv/bin/python scripts/research_run.py
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys

# make `app` and `research` importable when this file is run directly as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The strategy is valid only on 15m/30m candles (see CLAUDE.md), so we test on its
# native timeframe. Kite caps 30minute history at 200 days/request (sweep.MAX_DAYS).
# Sweep the full liquid seed universe with BOTH strategies and let a real survivor
# surface if one exists — gates are never loosened to manufacture one.
UNIVERSE = ["NIFTY", "BANKNIFTY", "SENSEX", "GOLDM", "SILVERM",
            "CRUDEOIL", "NATURALGAS", "COPPERM"]
INTERVAL = "30minute"
DAYS = 180


def _plan(get_instrument):
    insts = [get_instrument(k) for k in UNIVERSE]
    common = dict(instruments=insts, interval=INTERVAL, days=DAYS,
                  min_trades=30, n_folds=4, min_positive_fold_frac=0.5,
                  optimize_search=True)
    return [
        {"program": "Trend-Impulse (liquid universe)",
         "hypothesis": "Displacement-confirmed EMA50 trend persists on liquid underlyings (30m)",
         "strategy_key": "trend_impulse_v3", **common},
        {"program": "Expanding-Z Reversion (liquid universe)",
         "hypothesis": "Expanding-window z-score reversion adds edge on liquid underlyings (30m)",
         "strategy_key": "expanding_z_v4", **common},
    ]


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()[:40] or "unknown"
    except Exception:
        return "unknown"


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

    print(f"\nPromotionCandidate ({q(PromotionCandidate).count()}) — human-gated, NOT auto-deployed")
    for c in q(PromotionCandidate).all():
        print(f"  #{c.id} run={c.run_id} status={c.status} "
              f"param_hash={c.parameterization_hash[:12]}… universe={c.qualifying_universe_json}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S")

    # research plane must NEVER run in a live-execution environment
    os.environ.pop("PT_EXECUTION", None)
    os.environ.setdefault("PT_PROVIDER", "kite")

    from research.config import research_db_path
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.guards import enforce

    from app.core.config import get_settings
    from app.core.instruments import get_instrument
    from app.providers.factory import get_provider
    from research.data.store import KiteDataSource
    from research.orchestrator.run import run_nightly

    research_db = research_db_path()
    exec_db = get_settings().db_path
    print(f"research.db = {research_db}\nexec.db     = {exec_db}  (never opened)\n")

    # (1) fail closed BEFORE any work
    enforce(research_db=research_db, exec_db=exec_db,
            loaded_modules=sys.modules, env=os.environ)
    print("guardrails: PASS (distinct DBs · no order/broker/runner imports · not live)\n")

    # (2) schema
    engine = make_engine(research_db)
    init_research_db(engine)
    Session = make_sessionmaker(engine)

    # (3) live data source (SafePaperKite — data only, orders hard-disabled)
    source = KiteDataSource(provider=get_provider())
    report_dir = os.environ.get("PT_RESEARCH_REPORT_DIR", ".")
    os.makedirs(report_dir, exist_ok=True)

    # (4) run the plan through the full pipeline
    with Session() as session:
        reports = run_nightly(session, source, _plan(get_instrument),
                              git_commit=_git_commit(), report_dir=report_dir)
        _dump_db(session)

    # (5) show every generated report
    for rep in reports:
        print("\n" + "=" * 78)
        print(f"REPORT: {rep['report_path']}")
        print("=" * 78)
        with open(rep["report_path"]) as fh:
            print(fh.read())
    print(f"\ndone — {len(reports)} experiment(s) run against live {get_provider().name} data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
