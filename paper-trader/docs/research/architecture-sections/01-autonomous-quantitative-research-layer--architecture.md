Reference: [section index](../ARCHITECTURE.md). Read with its scope; this is not a new assignment.

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
