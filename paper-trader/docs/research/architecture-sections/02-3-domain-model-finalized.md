Reference: [section index](../ARCHITECTURE.md). Read with its scope; this is not a new assignment.

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
