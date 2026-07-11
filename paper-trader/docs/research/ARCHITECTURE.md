# Autonomous Quantitative Research Layer — Architecture

**Status:** finalized design, review-hardened. Foundations in progress on `feat/research-plane`.
**Scope:** a research *plane* that coexists beside the existing execution engine and is
physically incapable of moving capital. This document is the source of truth for the design;
it supersedes the conversational proposal and folds in nine independent adversarial reviews
(architecture, backend integration, registry/metadata, backtest reuse, persistence, frontend,
statistics, compute/orchestration, git-merge).

---

## 0. First principles (non-negotiable)

1. **Two planes, separate processes.** The *execution plane* (the existing FastAPI engine on
   `paper_trader.db`) is untouched except through clean, test-protected abstractions. The
   *research plane* is a separate process with its own `research.db`.
2. **Research is autonomous; capital allocation is not.** The research plane cannot open a
   position, cannot import the broker/runner, and cannot write execution state. The only bridge
   to production is a **human-reviewed git commit + a controlled restart + a human cockpit
   assignment + a human re-arm.**
3. **Reuse the simulation math; never duplicate it.** The pure kernels (`backtest.engine`
   internals, `backtest.metrics`, `backtest.ratchet`, `engine.charges`, `options.pricing`,
   `strategy.registry`) are imported as a library. The DB-bound orchestration (`sweep.py`,
   `cache.py`) is **not** reusable and is re-implemented against `research.db`.
4. **Evidence over optimization.** Hard validation gates *before* ranking. Optimization only
   *after* qualification. Aggressively kill weak candidates before expensive search.
5. **Immutable experiments, revisable knowledge, first-class negative evidence.**
6. **Maximize reliable knowledge per unit of compute**, not the number of strategies. Compute is
   scarce; budget, cache, resume, and early-stop accordingly.

---

## 1. Understanding of the vision

A research plane that, after market close, begins from an **explicit hypothesis**, qualifies
candidate strategies on the universe/regimes where they *naturally* work, optimizes only the
survivors, validates them through hard statistical gates, ranks what remains, and accumulates
durable **knowledge** (including failures) that steers tomorrow's effort — all without ever
touching the live book. The execution plane remains the sole executor of *approved* strategies.

Per the 2026-07 product pivot, the research target is **equity + index on the underlying**, not
stock-specific options. This is a material simplification: the mature *spot* backtester now
tests the actual traded instrument for equities, so the historic "backtests spot but trades
options" validation gap does not apply to the equity/index universe. Options research is
deferred and index-only (the synthetic-premium path stays dormant for that later milestone).

---

## 2. Weaknesses in the original idea (surfaced by review) and resolutions

| # | Weakness (as originally proposed) | Resolution |
|---|---|---|
| W1 | **Immutable `Experiment` also carried `status`/`checkpoint`/`decision`** — a contradiction. | Split into **`ExperimentSpec`** (immutable, content-hashed) + **`ExperimentRun`** (mutable). A re-run under new code is a *new Run against the same Spec*; content-addressed evals mean only changed cells recompute. |
| W2 | **Knowledge "decay" on `Finding.confidence`** would forget well-powered negatives. | `confidence` is **monotone in evidence**, revised only by a superseding Finding. Decay lives on a derived **`Hypothesis.retest_priority`** (floor > 0 ⇒ no permanent bans; cap ⇒ no thrash), triggered primarily by *data accumulation / structural break*, not a hand-set half-life. |
| W3 | **4-layer primitive/slot ontology** is unsound for v1: v3/v4 aren't slot-decomposable and the slot→canonical-column *combination grammar* (the builder's hard 80%) is unwritten. | Collapse to **`Definition = (strategy key + version + param_space)`** + **`Parameterization`**. Keep primitives as a **lightweight declarative taxonomy tag** (satisfies "semantic", seeds the builder). Build executable swappable slots **with** the builder milestone, gated on designing the grammar first. |
| W4 | **`sweep.py`/`cache.py` claimed as reusable** — both bind the *execution* DB at import (`app.db.session` builds the engine at import time). | Reuse **only the pure kernels**. Research owns its own fan-out, persistence, cache, and a new content-address (see §7). |
| W5 | **"Coupling = one git commit, no restart"** is false: the registry caches discovery once per process; `instrument_state` is un-versioned DB state invisible to the running engine. | Promotion = **commit file → human review → controlled restart → human cockpit `set_strategy` → human re-arm.** Research never writes `instrument_state`. |
| W6 | **Fixed 1-lot / additive / no-leverage sizing** understates index-futures return-on-margin ~7–10× and can't model MIS leverage/concurrency — the pivot's headline instruments. | Research owns a **capital-aware `SizingModel` + per-segment return numeraire** (reusing `charges`/`pricing`/`ratchet`, not `compute_metrics`' base logic verbatim). |
| W7 | **"Breadth = validation"** double-counts correlated names: **N_eff ≈ 2–4, not 200.** | Cluster the universe (correlation/sector); count evidence in **independent clusters**; report N_eff on every scorecard; pool trades across clusters to reach usable N. |
| W8 | **No multiple-comparisons control** across the cell × grid × fold garden of forking paths. | **PBO (CSCV)** and **Deflated Sharpe** over the persisted trial ledger as hard gates; **FDR** across final candidates. |
| W9 | **Data can't support the corrected evidence bar for intraday.** | **Intraday = hypothesis-generating only; daily/swing = the one confirmatory regime** (disclosed survivorship bias). Min-evidence = a *corrected pooled t-stat*, not raw trade count. |
| W10 | **`oos_pass` is inert (never called), PF≥1 is break-even, `pf=None` passes, single 70/30 split ≠ walk-forward.** | Replace with a bootstrap lower-confidence-bound gate; kill `pf=None→pass`; **walk-forward is the OUTER loop** (optimize only inside each in-sample fold). |
| W11 | **No slippage/impact model** (fills at candle close). | Slippage-stress robustness: re-run at 0/1/2× per-segment slippage; **gate on survival at 2×**. |
| W12 | **Over-engineered resource plane** (per-experiment `max_parallel_workers`/`max_evaluations`, `Checkpoint` entity, ML early-stopping). | **Global** process pool (`cores-1`); budget in **bar-count/CPU-seconds**; resume via status columns + idempotent cache; early-stop = **multi-fidelity universe/window halving + sequential abort**. |
| W13 | **`HistoricalDataStore` 3-tier versioned store** is aspirational for one provider. | Ship the `DataSource` seam + a **real candle content-hash** + parquet-per-series. Defer versioned dataset-views until a 2nd source exists. |

---

## 3. Domain model (finalized)

```
ResearchProgram ("Trend Following")          ── long-lived initiative; global budget share
  └─ Hypothesis ("EMA-trend persists in large-cap intraday")   ← re-test priority lives here
        └─ ExperimentSpec ★ (IMMUTABLE, content-hashed)
              recipe: definitions[] · datasets[] · qualifier/optimizer/validator/scoring versions
              provenance: git_commit · rng_seed · parent_spec_id (lineage)
              │ 1..*
              └─ ExperimentRun (MUTABLE): status · checkpoint ptr · spent(bar-s) · decision · error
                    ├─ QualificationResult   (candidate × cluster × interval × regime → pass/fail + gate values)
                    ├─ OptimizationTrial      (one param point + objective; every trial persisted → DSR/PBO ledger)
                    ├─ ValidationResult       (walk-forward folds · OOS · stability · slippage-stress · robustness)
                    ├─ Scorecard              (gate stack → DSR-primary rank + Pareto front; every component logged)
                    └─ PromotionCandidate     (status: pending|approved|rejected + git SHA of the committed file)

StrategyDefinition = strategy key + version + param_space   (+ primitive taxonomy TAGS)
      param_space[param] = {type, hard-validity bounds, default}   ← intrinsic validity only
      Experiment recipe declares the search subrange + which params are optimizable   ← context, not intrinsic
  └─ Parameterization (candidate) = definition@version + concrete params  → content-hashed

Finding (Knowledge)  = distilled, evidence-linked, confidence(monotone), supersedable
      attaches to a Hypothesis; rolls up to a Program; append-only + superseded_by pointer

Content-addressed shared stores (OUTSIDE the Experiment aggregate; referenced, not owned):
  Parameterization · Dataset (candle content-hash) · EvaluationResult (candidate_hash, dataset_hash, sim_version)
```

**Aggregate boundary:** an `ExperimentRun` *owns* its private run-log
{Qualification/Trial/Validation/Scorecard/Promotion}; it *references* the shared content-addressed
stores {Parameterization, Dataset, EvaluationResult, Finding}. The Experiment is a thin
audit/coordination envelope — the domain weight is the evaluation cache.

**Cut from v1 (reintroduced with the builder milestone):** `ResearchPrimitive` /
`PrimitiveImplementation` as executable swappable units; `ApprovedProductionStrategy` as a
research entity (it is `PromotionCandidate.status=approved` + a git SHA in the *other* plane);
`Checkpoint` as an entity (→ status columns).

---

## 4. Subsystem architecture

```
┌──────────────── RESEARCH PLANE — separate process · research.db · cron@~19:00 IST ────────────────┐
│  research/nightly.py (cron one-shot, own lockfile)                                                 │
│     └─ Orchestrator: worklist · global process pool (cores-1) · bar-count budget · report gen      │
│          stages (versioned): Hypothesis ▸ Qualify ▸ Optimize ▸ [Validate = OUTER walk-forward] ▸    │
│                              Score ▸ Decide/Promotion-proposal ▸ Report                              │
│          │ imports (pure kernels only)          │ read/write                                        │
│   ┌──────▼───────────────┐          ┌───────────▼──────────────┐                                   │
│   │ Evaluation Core       │          │  research.db (own Base)   │                                   │
│   │  registry (defs+tags) │          │  Programs·Hypotheses·     │                                   │
│   │  compute_signals()    │          │  ExperimentSpec/Run·      │  + append-only eval/trial shards  │
│   │  run_trades()  [NEW]  │          │  Qual·Trial·Val·Scorecard·│    (parquet; SQLite = index)      │
│   │  SizingModel  [NEW]   │          │  Findings·Promotions·     │                                   │
│   │  metrics·ratchet·     │          │  Datasets(idx)            │                                   │
│   │  charges·pricing      │          └──────────────────────────┘                                   │
│   └──────┬────────────────┘                                                                          │
│          │ reads only local store                                                                    │
│   ┌──────▼──────────── HistoricalDataStore ────────────────────┐   ┌── Guardrails (fail-closed) ──┐ │
│   │ DataSource: kite_candles (future: option/IV, fundamentals) │   │ assert research_db≠exec_db    │ │
│   │ candle content-hash · parquet-per-(instrument,interval)    │   │ ban import of broker/runner   │ │
│   └──────┬─────────────────────────────────────────────────────┘   │ own env; never PT_EXECUTION   │ │
└──────────┼──────────────────────────────────────────────────────────┴───────────────────────────────┘
           │ cross-process Kite token bucket (shared api_key)      ▲ git commit (approved param file)
           ▼                                                       │  → human restart + cockpit assign + re-arm
   MarketDataProvider (shared pure lib) ── Kite / mock             │
                                                                   │
┌──────────────── EXECUTION PLANE — existing backend · paper_trader.db — UNTOUCHED ───────────────────┐
│  EngineRunner (signal + risk loops) · broker/safety · registry auto-discovery (startup)              │
│  ONE sanctioned edit: extract run_trades() from backtest/engine.py (behavior-preserving, golden-test │
│  protected) so walk-forward is O(N) and EMA/ATR-seed-consistent. simulate() external behavior frozen. │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Data flow (nightly autonomous; morning human)

**Nightly (~19:00 IST, same-day Kite token still valid; hard-capped to finish well before ~06:00):**
1. `DataStore.refresh()` — orchestrator (only) fetches new candles, content-hashes, writes parquet.
   Workers **never** call a DataSource.
2. Open `ExperimentRun`s from the top of each Program's hypothesis backlog by `retest_priority`.
3. **Qualify** candidate × cluster × interval × regime; sequential abort once hopeless; record *why*.
4. **Validate = OUTER walk-forward loop**; inside each in-sample fold, **Optimize** only on that
   fold; evaluate on its untouched OOS; multi-fidelity universe halving prunes; every trial persisted.
5. **Score** survivors: hard gates (PBO, corrected pooled t-stat, cost-stress @2×, cross-cluster
   breadth, stability) → **DSR-primary rank + Pareto front**; log every component.
6. **Decide**: top candidate(s) → `PromotionCandidate` (queued); deposit Findings (positive *and*
   negative); update `Hypothesis.retest_priority`.
7. **Report**: per-Program morning artifact (HTML/MD/JSON on disk) — ran/qualified/rejected+why,
   ranked candidates, new findings, budget spent. Resume = re-run; cache hits skip completed cells.

**Morning (human — the only capital path):**
Read report → approve → **git commit** the frozen parameterization file → **controlled restart** of
the execution process → set the assignment from the cockpit (`set_strategy`) → **ARM**.

---

## 6. Module / package boundaries

New top-level package `backend/research/` (the engine never imports it; structurally
conflict-free). Reuse line is explicit:

- **Imported as pure library (never modified except W-refactor):** `app.backtest.engine`
  (`simulate`, and the new `run_trades`/`compute_signals` split), `app.backtest.metrics`,
  `app.backtest.ratchet`, `app.engine.charges`, `app.options.pricing`, `app.strategy.registry`,
  `app.providers`.
- **Re-implemented in `research/` (do NOT reuse):** fan-out orchestration, persistence, cache,
  content-addressing, scheduler.
- **`research/` internal layout:**
  `domain/` (ResearchBase models), `data/` (DataSource + store + content-hash),
  `evaluation/` (sizing, numeraire, windowed-eval wrappers over the kernels),
  `pipeline/` (qualify, optimize, validate, score, decide — each versioned),
  `stats/` (clustering/N_eff, PBO, DSR, bootstrap gates),
  `orchestrator/` (worklist, budget, pool, report), `nightly.py` (cron entry), `guards.py`.

---

## 7. Persistence

- **Own `ResearchBase`**, engine, sessionmaker, and its own PRAGMA listener (WAL/busy_timeout/
  synchronous). New `research_db_path` in `Settings`. Never the execution `Base`.
- **Metadata plane → SQLite** (Programs, Hypotheses, Spec/Run, Scorecards, Findings, Promotions).
- **Eval/trial firehose → append-only parquet shards (one per worker), SQLite holds the index.**
  (Foundations: SQLite is fine; the harness milestone has fixed params / low volume. Build shards
  when the optimizer arrives.)
- **Content address:** reuse `params_signature` for the candidate component; **add a real
  `dataset_hash`** (sha256 over canonical `(ts,o,h,l,c,v)`, cached per fetch — *not* the
  `last_candle_ts` label, which misses Kite backfills); derive **`sim_version` from the git commit /
  source hash** (not a hand-bumped int); fold in `charges_version`. UNIQUE constraint on the address.
- **Immutability enforced by SQLite triggers** (`BEFORE UPDATE/DELETE … RAISE(ABORT)`) on Spec/
  Trial/Eval/Validation — holds even against a stray CLI, unlike ORM events. Findings are append-only
  + `superseded_by`.
- **Alembic for the research plane only** (greenfield, isolated; the execution DB keeps its
  hand-migrations). Every immutable row records its `schema_version`.
- **Backups:** nightly `VACUUM INTO` / file copy — research.db is expensive-to-recompute knowledge.
- **Any read of the live execution DB is strictly read-only** (`?mode=ro`) so it can never take the
  write lock and stall the ~1s risk loop.

---

## 8. Repository structure (target)

```
backend/
  app/                      # EXECUTION PLANE — untouched (except the one run_trades refactor)
  research/                 # RESEARCH PLANE — new top-level package (engine never imports it)
    domain/  data/  evaluation/  pipeline/  stats/  orchestrator/  nightly.py  guards.py
  tests/                    # existing suite stays green
  research_tests/           # research-plane tests (own dir, own conftest → research.db in tmp)
frontend/                   # unchanged in foundations; a read-only research tab is a later milestone
docs/research/              # this doc + methodology notes + roadmap
requirements-research.txt   # research-only deps (pyarrow, alembic, optuna…) — keeps app deps clean
```

---

## 9. Merge strategy (long-lived branch)

- **Branch `feat/research-plane`, based on `main`** (not on the in-flight `feat/vps-deploy`).
- **Conflicts are structurally minimized** by keeping virtually all code in the new `research/`
  package the engine never imports. The engine's own files change only for the single
  `run_trades` extraction (guarded by the golden + dry-run tests).
- **Rebase forward on `main` regularly** (weekly, or when a shared file — `main.py`, `config.py`,
  `App.tsx` — moves). Prefer rebase over merge to keep a linear, reviewable branch.
- **Proof that execution is untouched:** the existing `tests/` suite and `scripts/dryrun.py`
  ledger-reconciliation must stay green on every research commit; the diff to `app/` stays empty
  save the one refactor.
- **Merge-back when mature:** research ships as an additive package + one refactor + a new
  `research_db_path` setting; the merge is near-conflict-free by construction.

---

## 10. Implementation roadmap (milestones)

- **M0 — Foundations. ✅ DONE.** Repo skeleton, `ResearchBase` + `research.db`, the corrected
  domain spine, fail-closed **guardrails**, the pure-kernel evaluation wrapper, the
  `run_trades`/`compute_signals` split (test-protected). (Alembic deferred to first schema change.)
- **M1 — Harness over existing strategies. 🟢 IMPLEMENTED (fixed params).** Content-hashed
  DataStore + `DataSource` seam; walk-forward (WF-outer); Qualify → Validate (hard gate battery:
  min-OOS-trades, temporal stability, confident bootstrap edge, 2× slippage-stress) → DSR score +
  Pareto front; Findings (±) + PromotionCandidate + markdown report; nightly cron loop.
  *Remaining M1:* wire `N_eff` clustering into scoring, capital-aware `SizingModel`/segment
  numeraire, real Kite universe plan + parquet persistence for the eval store.
- **M2 — Optimization.** Constrained param search *inside* WF folds; trial ledger + firehose shards;
  multi-fidelity halving + sequential abort; budget accounting in bar-count/CPU-seconds.
- **M3 — Knowledge & scheduling.** Findings (incl. negative) + `retest_priority` backlog scheduler;
  cross-experiment eval dedup; slippage-stress + regime + book-correlation + capacity gates.
- **M4 — Read-only research dashboard.** A polled `/api/research/*` read surface + one desktop-only
  tab. No dynamic forms, no approve-button.
- **M5 — Strategy Builder (last).** The primitive→implementation executable slots + the
  slot→canonical-column **combination grammar** (designed here, not before), constrained generation,
  seeded by Findings. Index-options synthetic-premium path revived if/when relevant.

---

## 11. Risk register

**Technical:** import-time DB-engine binding in `app.db.session` (mitigate: research never imports
it; guardrail asserts DB paths differ); SQLite single-writer under a process pool (mitigate: shards
+ single-writer funnel); `fork` inheriting the SQLite fd (mitigate: worker-initializer disposes
engine, pass keys/hashes not objects); cross-process Kite 429/quota (mitigate: token bucket + strict
post-close window); promotion silently falling back to default strategy (mitigate: verify importable
in the running process + alert on fallback).

**Statistical:** N_eff ≈ 2–4 makes breadth weak evidence; multiple-comparisons overfitting;
intraday sample too thin to be confirmatory; survivorship + look-ahead in a *today's-dump* universe;
unmodeled slippage flattering high-turnover edges. Mitigations are the §5 gate stack — and honest
labeling of intraday as hypothesis-generating and daily as survivorship-biased.

**Architectural:** the semantic-primitive layer deferred to M5 means the builder's hardest problem
(the combination grammar) is validated by nothing built earlier — accepted deliberately, designed
when its consumer exists; long-lived-branch drift (mitigate: rebase cadence + structural isolation);
scope creep toward a general research platform (mitigate: "knowledge per unit compute", ruthless YAGNI).

---

*This document will evolve on `feat/research-plane`. Changes to the reuse line (§6) or the capital
guardrails (§0.2) require re-review — they are the load-bearing safety boundaries.*
