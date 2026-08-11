# Strategy OS V1 Verified Gap Map

**Verified at:** `0b795a6` on `codex/execution-foundation`

**Governing product direction:** the 12 August 2026 canonical V1 continuation directive

**Frontend boundary:** major frontend implementation begins only after the backend and research
contracts below pass their acceptance gates.

## PROVEN

- Tenancy roots exist for organizations, users, memberships and broker accounts.
- MONEY-plane identities and repository reads require owner/account scope. The Phase 1 Task 2
  adversarial review and complete backend/research acceptance gates pass.
- SQLite tenancy migrations preserve payloads and recover from the tested interrupted rebuild
  states without losing historical indexes, partial uniqueness, foreign keys or event guards.
- The visual strategy foundation has typed/versioned Component IR, immutable graph versions and
  content addressing. Owner provenance does not need to alter canonical graph bytes.
- Zerodha data and execution foundations are substantial. Provider capability vocabulary and
  separate data-provider/execution-venue roles exist. Upstox data support is partially proven.
- Paper/live separation, execution lifecycle attribution, MARKET and LIMIT order paths, charge
  modelling, slippage inputs and reconciliation foundations exist.
- Backtest result identity already binds the dataset, strategy parameters, capital, slippage and
  implementation/engine identity in tested paths.

## IN PROGRESS

- Phase 1 Task 3: owner-scoping projects, graphs, immutable versions, layouts, watchlists,
  strategies, research specifications and review artifacts.
- Private-IP boundaries for immutable strategy versions: private by default, tenant-local
  identity/lookups, no cross-tenant hash/existence signals, and a future
  `PRIVATE | SHARED | PUBLISHED` seam without marketplace mechanics.
- Phase 1 Tasks 4-7: owned backtests/jobs/results, private cache visibility, authenticated
  principals, WebSocket/export/cache partitioning and one adversarial two-tenant gate.

## MISSING FOR V1

- USER/RESEARCH ownership for private CSVs/features, strategy Python source, evidence, optimiser
  trials, candidate decisions, OOS/walk-forward/Monte-Carlo artifacts, findings and reviews.
- A private BYOD admission path with immutable dataset versions, typed columns, timestamp/timezone
  mapping, quality rules and canonical series identity.
- Causal multi-series execution with observed instruments separate from the execution target and
  hard anti-look-ahead alignment tests.
- A Python authoring/import contract that lowers into the same canonical strategy semantics as
  visual graphs; no second backtest or execution engine.
- Durable owned heavy jobs with progress, restart/failure state and resource budgets; normal-run
  profiling and a reachable fast/content-addressed path.
- The bounded optimisation workflow, complete trial population, neighbourhood analysis, locked
  OOS/reveal history, walk-forward, basic Monte Carlo and execution-stress evidence. DSR remains
  hidden unless its trial population is statistically valid.
- First-class `RESEARCH ONLY`, durable attributable `SIGNAL ONLY`, `PAPER` and
  `AUTHORISED LIVE` outcomes.
- Honest capability implementations and conformance tests for all V1 targets: Zerodha, Dhan,
  Upstox and Angel One. Data and execution capabilities must remain separable.
- A provider-neutral canonical instrument model throughout the research/execution boundary.
- PostgreSQL-compatible tenancy/evidence/money persistence, backup/PITR/restore drills and a
  workload-based deployment topology. SQLite remains useful for local/test/single-node modes.
- Private-content encryption, plaintext-log controls, audited privileged access and explicit
  analytics/training opt-in enforcement.

## DEFERRED

- Marketplace mechanics, strategy sales, DRM and social/copy trading.
- AI strategy invention or an autonomous research agent.
- Full L2/TBT order flow, institutional FIX/CTCL/DMA/SOR and co-location.
- Brokers beyond the four V1 targets.
- PBO unless it becomes straightforward after the V1 validation population is correct.
- Complete derivatives warehousing, advanced roll engines, multi-leg orchestration and broad
  multi-timeframe/stateful-language expansion beyond the required V1 seam.
- Kafka, Kubernetes or speculative service decomposition without measured workload evidence.

## CONTRADICTS THIS DIRECTION

- Classifying durable backtest evidence as MARKET. Reusable raw computation may be MARKET, but
  owned runs, results and validation evidence are USER/RESEARCH.
- Treating every `signal_event` as MONEY. Signal-only research evidence needs an owned
  USER/RESEARCH identity; only execution-authority/order lifecycle belongs in MONEY.
- Treating Python authoring, cross-instrument semantics, Monte Carlo or the four provider targets
  as post-V1 work.
- Using a headline user count as the capacity gate. Capacity must be measured by instruments,
  rows, graph complexity, optimiser throughput, concurrent jobs, live evaluations, latency and
  database/WebSocket/cache contention.
- Building major frontend surfaces against unfinished backend contracts.
- Global deduplication or hash lookup of private content that can reveal another tenant's
  strategy, dataset or artifact existence.

## Dependency order from here

1. Finish USER/research ownership and private strategy provenance (Phase 1 Task 3).
2. Own backtests, research jobs, evidence and private cache visibility (Task 4).
3. Resolve real user principals and enforce scoped HTTP/export access (Task 5).
4. Partition WebSockets, exports and answer-changing in-memory caches (Task 6).
5. Pass the Phase 1 adversarial two-tenant gate (Task 7).
6. Establish the PostgreSQL/storage seam and private-data controls.
7. Build BYOD and causal multi-series semantics.
8. Complete common visual/Python authoring semantics.
9. Profile and harden interactive backtests and durable heavy jobs.
10. Build bounded optimisation, validation and explicit outcomes.
11. Complete four-provider capability tracks and deployment/recovery/load gates.
12. Stop for the owner review immediately before major frontend implementation.
