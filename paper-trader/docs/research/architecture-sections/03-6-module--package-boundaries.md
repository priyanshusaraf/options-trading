Reference: [section index](../ARCHITECTURE.md). Read with its scope; this is not a new assignment.

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
- **M2 — Optimization. 🟢 CORE LANDED.** Constrained, bounded param search *inside* WF folds
  (`pipeline/optimize.py`), nested so OOS is never selection-contaminated; immutable
  `OptimizationTrial` ledger; DSR deflated by `n_trials`; wired into the orchestrator behind
  `optimize_search`. *Remaining:* multi-fidelity halving + sequential abort, parquet firehose
  shards, budget accounting in bar-count/CPU-seconds.
- **M3 — Knowledge & scheduling.** Findings (incl. negative) + `retest_priority` backlog scheduler;
  cross-experiment eval dedup; slippage-stress + regime + book-correlation + capacity gates.
- **M4 — Read-only research dashboard.** A polled `/api/research/*` read surface + one desktop-only
  tab. No dynamic forms, no approve-button.
- **M5 — Strategy Builder (last).** The primitive→implementation executable slots + the
  slot→canonical-column **combination grammar** (designed here, not before), constrained generation,
  seeded by Findings. Index-options synthetic-premium path revived if/when relevant.

---
