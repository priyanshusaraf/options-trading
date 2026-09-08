Reference: [section index](../architecture-extension-review-2026-08-07.md). Read with its scope; this is not a new assignment.

## F. Scaling assessment — roughly 100 serious users

The workload: research experiments, backtests, paper strategies, eventually a few live strategies,
market-data consumption, stored evidence.

**Verdict: a modular monolith is the right shape and should stay. Three things need a boundary; none
needs a service.**

| Concern | Today | At ~100 users | Action |
|---|---|---|---|
| **Backtests** | `sweep.py` — one global worker, `raise RuntimeError("a sweep is already running")` | **Hard failure.** The second user is refused | The one real bottleneck. A `jobs` table + claiming worker, in-process. **G-3** |
| **Concurrent runtimes** | One `EngineRunner`, two async lanes (~2.5 s signal, ~1 s risk), one deployment | Per-deployment loops or a scheduler | Deferrable — `Deployment` already exists as the execution root and `deployment_id` is already on `positions`/`trades` |
| **Market-data fan-out** | `get_provider()` — a process-wide singleton, one Kite token | One token per user; fan-out per instrument, not per user | Deferrable. The `MarketDataProvider` seam is the right boundary and already exists |
| **Broker rate limits** | Per-process, implicit | Per-account budgeting | Deferrable; belongs with the second broker account |
| **Job isolation** | None — a sweep shares the process with the risk lane | A failing job must not touch the risk lane | Same fix as G-3. Note hard invariant 2: nothing may block an exit |
| **Large artifacts** | `graph_versions.artifact_json`, `backtest_results` in SQLite | Fine at this scale | Watch, don't act. The 2026-07-23 outage was full-table ORM scans, already fixed with SQL aggregates |
| **Restart / recovery** | Strong. Disarm on start, journal recovery, orphan reconciliation, book-scoped ledgers, `foreign_book_positions` reported at startup and on `/api/health` | Unchanged | None |
| **User isolation** | None. `Principal` exists but every table is global | Owner scoping | **G-5.** Namespace identifiers now (free), schema later |
| **DB contention** | One SQLite file, WAL, `busy_timeout=10000`, `pool_timeout=10`, `pool_pre_ping` | SQLite is plausible at 100 users with WAL if writes stay short; the *write* path is the engine, not the users | Do not migrate speculatively. The trigger is a measured lock-wait, not a headcount |

**Explicitly not recommended:** microservices, event sourcing, a second execution engine, a message
broker, or a Postgres migration. None has a demonstrated need, and the 2026-07-23 outage post-mortem
shows this system's real scaling failures have been *query shape* (full-table ORM scans) and
*memory*, not architecture.

**Boundaries worth having clean now, in one repository and one deployment:** the job/worker boundary
(G-3), the platform component library (G-1), and the signal→intent→order boundary (G-2).

---

## G. Recommended sequence

**Outcome 2 — make one small bounded architectural correction first, then proceed to L1.4.**

Not outcome 3. No foundational contradiction was found. The two capabilities that looked most likely
to produce one — cross-instrument typing and reusable subgraph components — were both tested by
execution and both came back better than expected: the domain axis already makes a cross-instrument
edge a *type error*, and `publish()` already reproduces the shipped ATR body address exactly.

Not outcome 1 only because G-1 is five import lines today and will be more after the next queued
WS-01 slice, and because G-2 costs nothing but must land before L1.4 writes order-lifecycle code
across an unnamed boundary.

**Sequence:**

1. **G-1 — platform component library** (bounded, mechanical). A module owning the platform
   `(Library, implementations)` pair; the five imports repointed at it; the strategy's components
   stay where they are. Acceptance: reference artefact content address and all 18 node cache ids
   byte-identical, `test_ir_strategy_parity.py` green, and a new import guard proven able to go red.
2. **G-2 — name the signal → intent → order boundary** in `WS-02-execution.md`. Documentation only.
3. **Then L1.4, unchanged in scope.**

### Closure — 2026-08-07

Both corrections are **done**, and this section is the record rather than the plan.

- **G-1 shipped.** `app/ir/library.py` composes the platform `(Library, IMPLEMENTATIONS)` pair from
  an explicit `CONTRIBUTORS` tuple and refuses contributor disagreement. All six production call
  sites — the five above plus `research/orchestrator/graph_experiment.py` — take their library from
  it. Identity is byte-identical across the correction, measured by fingerprint over the graph's
  canonical JSON, content address, every component body ref, and every resolved node id, cache id,
  body ref and warmup: `1077ee8cdb53641e9451956994b6800a5c48a8bce6c2625ba3ea44f07c853590` before
  and after. `tests/test_ir_platform_library.py` pins it, and its seam guard was proven able to go
  red by restoring the old import.
- **G-2 shipped as a contract**, at `WS-02-execution.md` §3, "The execution lifecycle boundary".
  No code was required: L1.4 was inspected against its four forbidden assumptions first and deepens
  none of them.
- **G-3 deliberately untouched**, per the amended entry above.

Deferred with a named home, not forgotten: multi-instrument runtime and multi-timeframe resolution
(WS-01 §5); typed data sources, dataset identity, futures continuity and temporal semantics (L3);
component packaging, permissions and marketplace (L4); auth and tenancy (L5 / G-5); the job queue
(G-3, before the second concurrent user, not before).

**Unchanged by this review:** `(ir_graph, live, authoritative)` remains **NOT APPROVED** and is not
designed here. Nothing in this document proposes a change to sizing, routing, risk, live-order
authority, broker behaviour or any real-money path.

---
