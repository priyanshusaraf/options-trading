# ROADMAP

**The agenda across workstreams. Detail lives in the workstream documents, not here.**

This file used to be 1,279 lines and every session parsed all of it to find one item. It is now
an index and a sequencing decision. If you are implementing, go straight to your workstream
document — see [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

**Current checkpoint: 2026-08-09** · local branch `codex/execution-foundation`, source revision
`1e96b52` before this documentation update · not pushed · not deployed. The branch-wide gate
collected **3,712 backend/research tests: 3,706 passed + 6 expected skips, exit 0**. The frontend
passed **223/223 tests**, TypeScript checking, and the production build. `dryrun.py 700` ended
`LEDGER OK`; `backtest_smoke.py` completed 16/16 cells with `SWEEP OK`; migration head remains
`0014`. These results verify the configurable live-entry order slice within its stated scope.
They are not deployment authorisation and do not prove paper/backtest LIMIT-fill parity.

The older workstream programme and implementation history remain in
[`engineering/EXECUTION_PLAN.md`](engineering/EXECUTION_PLAN.md). The current sequence is the
execution-first order and evidence matrix below.

---

## 1. Order of work

The owner's 2026-08-09 direction supersedes the 2026-08-01 research/UI/futures sequence and
the older B → E → C → D → A sequence. The current order is:

1. execution safety and truthful fill behaviour;
2. causal strategy admission;
3. content-addressed backtest correctness, then 100 × 5 performance;
4. explicit data/execution/account role bindings;
5. account-isolated deployment design and load/failure proof;
6. novice research UX on the existing frontend;
7. additional brokers;
8. customer authentication, tenancy, and commercial administration.

Broker breadth and commercial tenancy remain deliberately deferred. Internal deployment,
account, and connection identities still belong in money-state paths before customer login does.

### Phase truth

The decision rule is strict: implementation without its gate is `PARTIAL`; an old statement that
the present code cannot support is `CLAIM REJECTED`.

| Phase | Current status | Evidence and remaining gate |
|---|---|---|
| 1. Durable entry intent and immutable lifecycle | **COMPLETE** | Migration `0014`, append-only intent/events, pure reduction, and pre-submit commit are verified at `9827e23`. |
| 2. Live entry integration, recovery, protection, telemetry | **COMPLETE within the live-entry scope** | Durable recovery, cumulative fill deltas, protection-before-booking, latency, slippage, and `AUTO`/`MARKET`/`LIMIT` live-entry routing passed the branch-wide gate. Live options and equity entries persist and submit the effective MARKET or LIMIT request. **Paper and backtest LIMIT fill parity remains open. Exits remain on the legacy journal and market-order path.** |
| 3. Causal strategy contract | **PARTIAL** | IR prefix causality and handwritten-strategy mutation tests exist. Closed per-block causal declarations, admission enforcement, and streaming-versus-vectorised parity are not complete. |
| 4. Content-addressed backtest cache | **CLAIM REJECTED** | The current cache uses the final candle timestamp rather than a full ordered OHLCV address, omits executable/cost identity, and drops `bh_curve_json` on cache copy. |
| 5. Fast 100 × 5 sweep | **UNSTARTED as a gate** | A 16-cell smoke exists. Provider-read/DataFrame budgets, zero-read warm reuse, batched progress, frozen-output parity, and p50/p95/p99 measurement do not. |
| 6. Data/execution/account role bindings | **PARTIAL** | Capability gates admit a second-broker-shaped test double, but `make_broker(provider)` still derives execution from one provider. No account actor owns one account yet. |
| 7. Deployable 100-user topology | **UNSTARTED** | The current single-owner VPS deploy path is real and guarded; it is not a multi-account worker topology and has no soak, lease, fencing, failover, RPO, or RTO proof. |
| 8. Novice research experience | **PARTIAL** | The React/Vite graph, research, backtest, engine, portfolio, and ledger surfaces exist. The guided idea-to-paper journey and novice usability gate do not. |
| 9. Additional brokers | **DEFERRED / UNSTARTED** | Capability and resolver seams exist; no Upstox or second execution adapter is shipped. |
| 10. Commercial access | **DEFERRED / PARTIAL SEAM** | A single-owner bearer-token principal seam exists. Customer identity, ownership, encrypted credentials, and cross-account isolation do not. |

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

For roughly 100 users, the target is one shared control plane plus account-isolated execution
workers, initially capped at five active accounts per worker and spread across at least two
hosts. The gate is a 50-account soak plus crash-after-submit, token-expiry, throttling, restore,
failover, and duplicate-worker fencing drills.

At roughly 1,000 users, bounded execution cells add versioned placement, resource limits,
primary/standby assignment, shared PostgreSQL authority, leases, and fencing. Per-user VPSs stay
an optional premium isolation mode, not the default. These are architectural targets only. The
current application is one process, one SQLite authority, and one single-owner VPS; it is not
ready for either target.

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
