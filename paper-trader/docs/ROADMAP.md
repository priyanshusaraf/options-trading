# ROADMAP

**The agenda across workstreams. Detail lives in the workstream documents, not here.**

This file used to be 1,279 lines and every session parsed all of it to find one item. It is now
an index and a sequencing decision. If you are implementing, go straight to your workstream
document — see [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

**Current checkpoint: 2026-08-13** · local branch `codex/execution-foundation` · not pushed · not
deployed. Phase 1 is closed. Phase 2 implementation now covers PostgreSQL profiles for all three
private planes, verified copy, fenced account execution, scoped durable replica events, local
restore proof, and bounded workload rehearsals. Exact retained gates live in the Phase 2 task
reports. These results are local engineering evidence, not deployment authorisation, managed
PITR evidence, production capacity, or a cost certificate.

The older workstream programme and implementation history remain in
[`engineering/EXECUTION_PLAN.md`](engineering/EXECUTION_PLAN.md). The current sequence is the
execution-first order and evidence matrix below.

---

## 1. Order of work

The owner's 2026-08-09 direction supersedes the 2026-08-01 research/UI/futures sequence and
the older B → E → C → D → A sequence. The current order is:

1. execution safety and truthful fill behaviour;
2. causal strategy admission;
3. content-addressed backtest correctness, then scalable sweep performance (100 × 5 baseline,
   followed by 1,000 × 5 and **10,000 × 5** tiers — see the scale corrections below);
4. explicit data/execution/account role bindings;
5. account-isolated deployment design and load/failure proof;
6. novice research UX on the existing frontend;
7. additional brokers;
8. commercial administration after the closed authentication and tenancy foundation.

Broker breadth remains deliberately deferred. Phase 1 closed ownership, authentication, jobs,
APIs, exports, WebSockets, and cache boundaries. Commercial administration remains later work.
Deployment, account, and connection identities now sit in the money-state paths; production
rollout still requires Phase 2 closure acceptance and deployment-specific evidence.

### Current product framing (2026-08-13)

Strategy OS is being built as a broker-agnostic, multi-user research → backtest → deploy
platform. The older single-user Indian-options engine remains useful execution history, not the
current product definition. Its trend-and-displacement strategy is one strategy implementation,
not the platform's boundary.

Phase 1 is closed on owner-scoped data, sessions, jobs, APIs, exports, WebSockets, caches,
execution lifecycle boundaries, and adversarial isolation. Phase 2 implements PostgreSQL plane
profiles, account execution leases and fences, replicated API ownership, scoped shared event
delivery, copy/restore tools, and bounded failure/workload proofs. Production deployment remains
unproven. `500 users` is one launch-validation workload and cost tier, never a product cap.

### Phase truth

The decision rule is strict: implementation without its gate is `PARTIAL`; an old statement that
the present code cannot support is `CLAIM REJECTED`.

| Phase | Current status | Evidence and remaining gate |
|---|---|---|
| 1. Durable entry intent and immutable lifecycle | **COMPLETE** | Migration `0014`, append-only intent/events, pure reduction, and pre-submit commit are verified at `9827e23`. |
| 2. Live entry integration, recovery, protection, telemetry | **COMPLETE within the live-entry scope** | Durable recovery, cumulative fill deltas, protection-before-booking, latency, slippage, and `AUTO`/`MARKET`/`LIMIT` live-entry routing passed the branch-wide gate. Live options and equity entries persist and submit the effective MARKET or LIMIT request. **Paper and backtest LIMIT fill parity remains open. Exits remain on the legacy journal and market-order path.** |
| 3. Causal strategy contract | **PARTIAL** | IR prefix causality and handwritten-strategy mutation tests exist. Closed per-block causal declarations, admission enforcement, and streaming-versus-vectorised parity are not complete. |
| 4. Content-addressed backtest cache | **COMPLETE on this branch** | Schema v8 binds exact ordered OHLCV bytes and source context to a closed execution manifest: strategy and transitive source, bound parameters, instrument economics, slippage, charges, event/exit policy, and premium assumptions. Historical revisions with the same final timestamp are cold; transient premium failures are not reusable; warm rows preserve every result column except row/run identity. |
| 5. Scalable sweep: 100 × 5, then 1,000 × 5 / **10,000 × 5 in minutes** | **IN PROGRESS, now measured** | Shared dataset acquisition (`439d45d`), shared frame/signal preparation (`a291722`) and the options-pricing fix (`5ba1233`) are done. Per-stage cost is measured on realistic 5,000-bar datasets and recorded in the hardening record §10: a cell is **84.7 ms**, down from 185.7 ms, after removing a `scipy.stats.norm.cdf` wrapper that was 74% of the premium replay. **Two floors remain and both are named:** the live-fetch I/O floor is 5 h 33 m for 50,000 datasets (Kite's rate limit — not optimisable in our process, so the local dataset store is the only path and is promoted ahead of batching), and serial compute is still 4,236 s, ~20× over target, which is what justifies measured multiprocess fan-out. The store, batching, fan-out and tiered p50/p95/p99 do not exist yet. |
| 6. Data/execution/account role bindings | **PARTIAL** | Owner and broker-account identities, broker connections, scoped execution state, and fenced account ownership exist. A second production broker adapter and complete provider-role portability remain unproven. |
| 7. Deployable **500-user** topology at a bounded cost | **PARTIAL — local foundation implemented** | PostgreSQL plane profiles, fenced account leases, replicated API ownership, scoped event delivery, local restore proof, and bounded workload rehearsals exist. A managed multi-host deployment, sustained soak, managed PITR/failover, measured capacity, and monthly cost remain open. The five-accounts-per-worker figure remains withdrawn until measured. |
| 8. Novice research experience | **PARTIAL** | The React/Vite graph, research, backtest, engine, portfolio, and ledger surfaces exist. The guided idea-to-paper journey and novice usability gate do not. |
| 9. Additional brokers | **DEFERRED / UNSTARTED** | Capability and resolver seams exist; no Upstox or second execution adapter is shipped. |
| 10. Commercial access | **PARTIAL FOUNDATION** | Multi-user identity, membership, ownership, encrypted broker credentials, sessions, and adversarial cross-tenant isolation exist. Billing, entitlements, customer administration, and production identity operations remain deferred. |

The governing design and detailed gates are in
[`superpowers/specs/2026-08-09-execution-first-product-roadmap-design.md`](superpowers/specs/2026-08-09-execution-first-product-roadmap-design.md).

## 2. Waiting on the owner

Nothing below can be resolved by implementation. Everything else can proceed today.

1. **Authorise any live deployment.** The `codex/execution-foundation` branch is local and not
   deployed. Its verification gate does not replace the live-money deployment review, release
   provenance, or owner approval. → WS-02, WS-06
2. **Adopt the IR runtime in a live path.** RFC 0001 Appendix C(d). The parity evidence now
   exists: `expanding_z_v4` expressed in the IR produces identical signals bar for bar. → WS-01,
   WS-02
3. **VPS OS reboot** (5 ESM security updates) and **droplet resize 1 GB → 2 GB**. → WS-06

### Deployment direction, not deployment truth

**Owner correction 2026-08-12: 500 users is a launch-validation tier, not a product ceiling, and
hosting cost is a first-class constraint.** The full analysis is
[`superpowers/specs/2026-08-09-scale-and-cost-corrections-design.md`](superpowers/specs/2026-08-09-scale-and-cost-corrections-design.md).
Its load-bearing conclusion: market data must be fanned in **once per distinct instrument set**
and broadcast, never once per user — per-account credentials are needed for orders, not for
prices. That single decision is what keeps 500 users affordable, and the standing "data provider
≠ execution broker" invariant is what makes it legal. WebSockets stay; **HTTP polling is not the
answer and is not proposed.** 500 concurrent sockets cost ~25 MB, which is nothing; the real
line item is sustained payload volume (~2.6 TB/month at 2 KB/s/user), so fan-out must push
deltas rather than full state. The 2026-07-23 outage is the precedent — a fanout bug, not a
bandwidth bill.

For the 500-user launch tier, the target is one shared control plane plus account-isolated execution
workers spread across at least two hosts. The per-worker account cap is a **measurement, not a
guess**. The gate is a 50-account soak plus crash-after-submit, token-expiry, throttling,
restore, failover, and duplicate-worker fencing drills — and a stated monthly cost.

Bounded execution cells add versioned placement, resource limits, primary/standby assignment,
shared PostgreSQL authority, leases, and fencing when measured workload demands them; they are not
deferred until a particular user count. Per-user VPSs stay an optional premium isolation mode, not
the default. Capacity should grow by adding stateless control-plane replicas, research workers,
market-data fan-out capacity, and bounded execution cells. Shared PostgreSQL authorities, scoped
durable event delivery, independently deployable API/worker roles, and fenced per-account execution
ownership are implemented and locally proven. Replicated APIs, distributed execution ownership,
shared event delivery, and production capacity remain deployment gates until production-like
rehearsals prove them; those gates may still require schema or data-placement changes.

## 3. Parked deliberately

Do not spend sessions here.

- UI→deployed-Python codegen bridge — owner 2026-07-20: hand-coding approved strategies is
  fine, and the approve→deploy bridge that exists is enough.
- Stock-specific options work — equity/index first; options are index-only and later.
- Product avenues from the 2026-07-18 review — revisit after the research plane ships.

## 4. Session protocol

1. Read [`PROGRESS.md`](PROGRESS.md) for state, then your workstream document. You should not
   need to read this file to implement anything.
2. TDD. Both backend suites plus `dryrun.py 700` green before any "done" claim, and the
   workstream's own §6 acceptance criteria on top.
3. A checked box means verified evidence, ticked in the same commit as the work.
4. Prove new guards can go red. A green test can be vacuous — five shapes have been caught here
   by suppressing the implementation and checking the guard's own test fails.
5. Deploys go through `scripts/deploy.sh` and nothing else. It refuses during market hours and
   on a dirty tree, and builds the SPA locally. Never bare-rsync — that has taken the VPS down
   twice. Full mechanics in [`operations.md`](operations.md).
6. Model split (owner): Fable advises and reviews, Sonnet builds, Opus judges optimisation.

## 5. Where the implementation history went

Nothing was deleted. Every completed item, with its date, commit and acceptance evidence, moved
into the §4 Completed section of the workstream that owns it:

| Was | Now |
|---|---|
| Strategy OS — Component IR | WS-01 §4 |
| Workstream A — Research plane, Phases 0–5 · Research Plane Gen 2 | WS-03 §4 |
| Workstream B — Safety backlog · C — Exit tuning · E — P&L, profit-lock, futures, MTF | WS-02 §4 |
| Workstream D — UI | WS-08 §4 |
| Workstream F — Infrastructure, persistence & deploy safety | WS-07 §4 and WS-06 §4 |

Architectural rationale that belongs to no workstream is in
[`ARCHITECTURE.md`](ARCHITECTURE.md) and
[`rfcs/0001-component-ir.md`](rfcs/0001-component-ir.md).
