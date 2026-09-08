# Executive synthesis

## Superseded timing notice

The architecture inspection below was completed on 22 August 2026. Its repository findings remain evidence, but its V1.1/V2 timing and proposed sequence are superseded by the owner-directed hybrid addendum and [revised V1 progress mapper](REVISED-V1-PROGRESS-MAPPER-2026-08-24.md). Dynamic Watchlists, bounded point-in-time reference/events, bounded forward chart semantics, Operator Thesis and proposal approval are V1. Broad certified options execution remains V1.5; general Workflows remain V2. Do not use this older synthesis to select implementation work.

## Executive judgment

The V1 foundation should remain. The current repository already contains the difficult core contracts needed for additive V2 work:

- one Component IR facade with immutable graph identities;
- one validator, resolver, hash discipline, and platform registry;
- deterministic lowering with authored-to-resolved attribution;
- causal completed-bar checks and an independent prefix evaluator;
- owner-scoped graph and admission facts;
- content-addressed market truth, observations, dataset dependencies, and cache bindings;
- durable research-operation claims and checkpoints;
- account-scoped execution leases with fencing;
- immutable execution lifecycle events;
- separate data-provider and execution-broker roles;
- an explicit broker registry with honest supported and planned states;
- logical and physical database-plane boundaries;
- bounded WebSocket fan-out with tenant channels and slow-client eviction.

The 24 August memo does not justify a rewrite. It does expose four V1 boundary defects that should close before later releases depend on them:

1. A deployment can still point at a mutable watchlist instead of an immutable Universe snapshot.
2. Portfolio admission and capital allocation remain in-memory decisions with no durable batch or reservation fact.
3. A dynamically created candidate has no durable lifecycle identity that joins discovery, research, admission, deployment, signal, intent, and fill.
4. The operational instrument path still carries provider-era fields even though the new canonical market-truth authority models the correct identity.

These are bounded refactors. They do not require building Dynamic Universes, general Workflows, non-OHLCV data, chart automation, or multi-rate execution in V1.

## Strongest areas

| Area | Judgment | Evidence-backed state |
| --- | --- | --- |
| Component IR identity and topology | KEEP | Implemented across v1; v2 contract and authority paths exist |
| Research causality | KEEP + HARDEN | Strong contracts and tests exist; the active foundation gate still blocks broad acceptance |
| Data provenance and cache identity | KEEP + HARDEN | Phase 4 contracts are deep; production-shaped deployment remains open |
| Research job durability | KEEP + HARDEN | Durable operation, item, lease, takeover, and event models exist |
| Account execution ownership | KEEP | Account lease and epoch fencing form the right single-writer base |
| Provider role separation | KEEP + HARDEN | Data and execution are distinct; five-broker V1 implementation is incomplete |
| Three-plane direction | KEEP + HARDEN | Current runbooks and schema boundaries are strong; release deployability remains rejected |

## Dangerously weak areas

| Area | Failure if left unchanged |
| --- | --- |
| Mutable watchlist binding | Historical and running deployments cannot prove the exact eligible instrument set |
| In-memory capital admission | Concurrent or recovered work cannot reconstruct why a candidate won, lost, or consumed capital |
| No reservation ledger | Broker uncertainty, process death, and external orders can invalidate the margin snapshot after admission |
| Single-instrument ENTRY intent | Dynamic batches, atomic baskets, explicit resizing, and grouped why-not receipts have no durable parent |
| Legacy operational instrument model | A second provider can still encounter Kite-shaped symbol fields above the new canonical authority |
| Candle-only replay payload | Universe changes, provider corrections, event availability, and future external artifacts cannot replay through one event record |

## Unproven areas

- The active programme is blocked on the Phase 1 to 4 foundation critical closure.
- Release deployability is rejected and open.
- Production rehearsal is unproven.
- The current dirty tree cannot be deployed through the sanctioned script.
- Component IR v2 has no production component catalogue and reaches an intentional runtime refusal on the complete authority path.
- Groww and Angel One are planned, and Upstox remains data-only.
- Full independent reconstruction of signals, orders, fills, fees, positions, and final P&L does not exist as a packaged export.
- The current production frontend has not been behaviorally benchmarked during this static inspection.

## Product timing decisions

| Capability | Disposition | Timing |
| --- | --- | --- |
| Immutable V1 static-Universe snapshot at deployment | REFACTOR | must change in V1 |
| Durable candidate-instance identity | REFACTOR | must change in V1 |
| Portfolio admission batch and capital reservation | REFACTOR | must change in V1 |
| Operational canonical-instrument binding | KEEP + HARDEN | must change in V1 |
| Five-broker architecture and conformance | KEEP + HARDEN | must change in V1 |
| Workflow-safe deployment command boundary | KEEP + HARDEN | must change in V1 |
| Reconstruction receipt and first-divergence contract | KEEP + HARDEN | must change in V1 architecture |
| Cross-sectional set, map, rank, and top-K types | KEEP + HARDEN | safe extension seam exists |
| Dependency-driven and multi-rate runtime | KEEP + HARDEN | safe extension seam exists; implementation can wait for V2 |
| Dynamic subscription planner | DEFER | V1.1 Dynamic Watchlist work |
| Dynamic Universe product and UI | DEFER | V1.1 |
| General Workflow product and UI | DEFER | V2 |
| Bounded India VIX data and derived nodes | KEEP + HARDEN | V1 |
| Certified liquid index-options execution | DEFER | V1.5 |
| Broader fundamental, event, and derivative-intelligence products | DEFER | V2 |
| Strategy Diagnostics and Counterfactual Lab | DEFER | V2 |
| Semantic chart artifacts | DEFER | V2 |
| Event and point-in-time external-data replay | DEFER | V2 |
| MT5, Bloomberg, international markets, meta-strategies | DEFER | V3 or demand dependent |

## Core architecture decision

Keep one Component IR, registry, validator, resolver, hash, and authored-to-resolved lineage.

Strategy, Universe, Workflow, and Deployment remain distinct product facts:

- Strategy owns per-context trading logic.
- Universe owns eligible instruments and rank at a point in time.
- Workflow owns long-running research, gate, approval, deployment, monitoring, and retirement steps.
- Deployment owns the exact operational binding and authority.

Universe logic may use the existing Component IR and type registry. A screener must not become a second language.

Workflow orchestration must invoke existing Strategy OS command boundaries. It must not write deployment, admission, or money tables directly. It may share content addressing and typed conditions, but its durable lifecycle state stays outside the low-latency strategy runtime.

## Smallest safe next slices

The dependency order is:

1. Close the active foundation critical gate.
2. Freeze a versioned static Universe snapshot and bind new deployments to it.
3. Define a durable candidate-instance identity.
4. Define portfolio admission batches and account capital reservations.
5. Route all deployment creation through one idempotent command boundary.
6. Complete canonical-instrument use on operational data and execution paths.
7. Close five-broker V1 capability and conformance gaps.
8. Package the reconstruction receipt and first-divergence test contract.
9. Only then schedule V1.1 Dynamic Watchlist work and later V2 Workflow implementation through their own capsules.

The detailed capsule proposals and deployment impacts are in [REMEDIATION-PLAN.md](REMEDIATION-PLAN.md).

## Nonclaims

This synthesis does not authorize:

- a schema or migration change;
- a V2 runtime;
- a new broker;
- a provider connection;
- a frontend implementation;
- live IR authority;
- capital policy changes;
- deployment;
- production access;
- licence-sensitive code adoption.
