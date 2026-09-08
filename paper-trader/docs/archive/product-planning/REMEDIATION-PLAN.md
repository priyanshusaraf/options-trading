# Dependency-ordered remediation plan

> **Programme superseded on 24 August 2026.** The slice proposals remain useful architecture evidence, but this file no longer controls sequence or version timing. Use [REVISED-V1-PROGRESS-MAPPER-2026-08-24.md](REVISED-V1-PROGRESS-MAPPER-2026-08-24.md).

Status: proposed programme input only

The active programme remains blocked in phase1-4-foundation-critical-closure. These proposed capsule names are exact homes for later work. This directory does not add them to PROGRAMME.json or make them ready.

## Gate 0: finish the current foundation closure

No recommendation below may bypass the active migration and numeric evidence work.

Stopping evidence:

- current foundation review PASS;
- exact protected hashes;
- current migration authority;
- current deployability ledger;
- no invalidated Phase 1 to 4 evidence.

## Slice 1: immutable static Universe binding

Proposed capsule: v1-static-universe-version-binding

Outcome:

- separate editable watchlist alias from immutable UniverseVersion and UniverseSnapshot;
- mint one exact static snapshot for new deployment bindings;
- preserve every legacy deployment without backfill;
- refuse a snapshot whose members lack canonical instrument authority.

Allowed conceptual paths:

- deployment and watchlist models and services;
- one additive migration;
- focused repository and route tests;
- deployability ledger.

Required tests:

- editing a watchlist cannot change an existing deployment snapshot;
- identical members and policy produce identical address;
- ordering differences do not change a set snapshot;
- canonical-instrument substitution changes identity;
- open positions remain resolvable after a member leaves the editable alias;
- SQLite and PostgreSQL empty install, current upgrade, restart, and rollback or restore.

Deployment impact: migration-required.

Owner gate: schema and deployment binding. No live behavior change without later activation.

## Slice 2: durable candidate-instance lineage

Proposed capsule: v1-dynamic-candidate-lineage

Depends on: Slice 1.

Outcome:

- define CandidateInstanceAddress from exact Universe evaluation, member, rank, Strategy version, research policy, and workflow context;
- attach lineage to deployment, signal, execution intent, and evidence without making it execution authority;
- keep legacy manual and static deployments valid with explicit null lineage.

Required tests:

- duplicate discovery produces one candidate identity;
- material input change produces a new identity;
- same instrument from two workflows remains distinct;
- owner substitution refuses;
- signal-to-fill attribution retains the candidate address.

Deployment impact: migration-required.

## Slice 3: portfolio admission and reservation architecture

Proposed capsule: v1-portfolio-admission-reservation

Depends on: Slice 2 and current execution-lease authority.

Outcome:

- persist DecisionBatch, CandidateIntent, AdmissionDecision, and CapitalReservation;
- retain the account execution lease as the single writer;
- make priority-subset the default;
- keep atomic baskets whole;
- reject silent resizing;
- produce why-trade and why-not-trade receipts;
- release or consume reservations idempotently under broker outcomes.

Required evidence:

- schema and state-machine architecture acceptance;
- PostgreSQL transaction and account-lock proof;
- deliberate two-actor contention;
- crash and broker-uncertainty tests;
- independent critical review after implementation.

Deployment impact: architecture-changing and migration-required.

Owner gate: money, live sizing, risk, routing, and execution semantics.

## Slice 4: Workflow-safe command boundary

Proposed capsule: v1-workflow-invocation-boundary

Depends on: Slices 1 to 3.

Outcome:

- expose idempotent application commands for research start, evidence gate, approval, portfolio admission, deployment create, pause, retire, and review;
- require exact immutable references at every command;
- keep existing admission, preflight, ARM, lease, and money boundaries authoritative;
- prohibit Workflow code from direct table writes.

Required tests:

- duplicate command delivery;
- stale approval;
- changed candidate after approval;
- process death before and after each durable effect;
- user cancel racing completion;
- Workflow retry cannot duplicate a deployment or order;
- risk-reducing exit remains available.

Deployment impact: compatible application boundary if schema-free; migration-required if command receipts persist in a new table.

## Slice 5: operational canonical-instrument binding

Proposed capsule: v1-canonical-instrument-operational-binding

Depends on: accepted Phase 4 market authority and current foundation closure.

Outcome:

- replace provider-era shared fields with canonical physical addresses plus adapter mappings on new paths;
- retain legacy Instrument as an adapter until exact parity passes;
- bind held positions to exact filled contract identity;
- keep observation and execution targets distinct.

Required tests:

- Kite parity before and after mapping;
- two providers map one physical instrument differently;
- token reuse intervals refuse ambiguity;
- symbol rename does not change canonical identity;
- dynamic selector change cannot rewrite a held position.

Deployment impact: architecture-changing and migration-required.

## Slice 6: five-broker V1 capability closure

Proposed capsules:

- v1-upstox-execution-conformance
- v1-groww-provider-and-execution-conformance
- v1-angelone-provider-and-execution-conformance

Depends on: Slice 5.

Kite and Dhan remain current reference adapters. Each new capsule must read current official documentation and SDK licence terms at dispatch time.

Required tests per broker:

- authentication and rotation;
- canonical instrument mapping;
- exact supported market-data fields and ranges;
- order types and protection;
- correlation and idempotency;
- partial fills, cancel and replace;
- reconnect, postback, polling, and restart reconciliation;
- capability-lie mutations;
- provider and execution role split.

Deployment impact: architecture-changing provider and service behavior. Production and credentials remain owner-gated.

## Slice 7: reconstruction receipt and export

Proposed capsule: v1-reconstruction-receipt-export

Depends on: current dataset and admission authority, plus Slice 5.

Outcome:

- assemble one closed receipt from existing exact facts;
- produce a licence-aware export;
- add an independent reference runner and first-divergence report;
- cover the three canonical acceptance scenarios and simultaneous contention.

Deployment impact: compatible if export-only; storage and retention may make it migration-required.

## Slice 8: truthful realtime client state

Proposed capsule: v1-realtime-health-state-contract

Outcome:

- separate browser transport, authorization, subscription, snapshot, freshness, and provider health;
- display unknown and stale states explicitly;
- preserve one WebSocket and backend-owned truth;
- provide keyboard and single-pointer alternatives for graph movement.

Deployment impact: compatible API and frontend change.

Owner gate: frontend implementation.

## V1 migration, rollback, and continuation ledger

Effort is a relative architecture estimate for planning. A future capsule must replace it with an inspected file and test budget.

| Proposed capsule | Main risks | Migration posture | Rollback posture | Relative effort | Can current backend work continue? |
| --- | --- | --- | --- | --- | --- |
| v1-static-universe-version-binding | R-02, F-016 | additive nullable references and immutable snapshot tables; no inferred backfill | stop new snapshot-bound writes, keep legacy deployments on their original path, retain minted snapshots | M | Yes, except dependent Universe binding work |
| v1-dynamic-candidate-lineage | R-03, F-017 | additive nullable lineage on new facts; legacy and manual flows remain explicit | disable new lineage creation, preserve all lineage already written, continue legacy null path | M | Yes, except Workflow-driven candidate creation |
| v1-portfolio-admission-reservation | R-01, F-001 to F-011 | additive decision and reservation tables with exact account and fence identity | do not activate live authority until rollback proof; disable new admission command and retain immutable decisions for reconciliation | L | Yes, except broader live concurrency and dynamic admission |
| v1-workflow-invocation-boundary | R-07, F-023 to F-026 | compatible command layer if schema-free; otherwise additive receipt table | route callers back to existing services, retain any committed receipts, and refuse uncertain retries | M | Yes, except Workflow execution |
| v1-canonical-instrument-operational-binding | R-04, F-012, F-040, F-041 | additive canonical references, adapter mappings, and dual-read compatibility | disable new canonical-path writes, keep mappings and historical references, continue legacy adapter only where unambiguous | L | Yes; new broker completion depends on it |
| three broker-specific conformance capsules | R-05, F-042 to F-044 | adapter, configuration, credential, and possible additive connection changes per broker | mark the affected role unsupported, stop its service, preserve connection records, and keep other providers independent | L across three slices | Yes; do not claim five-broker completion |
| v1-reconstruction-receipt-export | R-11, F-070 | compatible when assembled on demand; additive retention schema only if receipts persist | disable export or new receipt persistence without changing source authority facts | M | Yes; reconstructibility claims remain rejected |
| v1-realtime-health-state-contract | R-10, F-045, F-046 | compatible API evolution with old fields retained during the client transition | restore the prior client projection while backend health facts remain authoritative | S to M | Yes; frontend implementation remains owner-gated |

## V2 sequence after V1 closure

1. v2-cross-sectional-type-pack
2. v2-dynamic-universe-engine
3. v2-universe-point-in-time-replay
4. v2-subscription-resource-planner
5. v2-durable-work-backend-spike
6. v2-workflow-templates
7. v2-multi-rate-runtime
8. v2-external-data-domains
9. v2-chart-thesis-artifacts
10. v2-external-signal-ingress
11. v2-general-event-replay

## Explicit deferrals

| Item | Home | Reason |
| --- | --- | --- |
| Non-OHLCV product support | v2-external-data-domains | Owner deferred it |
| Full Workflow builder | later V2 | Deterministic templates must prove need |
| Full Dynamic Universe UI | later V2 | Backend identity and replay come first |
| TradingView-scale chart clone | rejected | Specialist input, not Strategy OS core |
| Bloomberg | V3 owner gate | licence, entitlement, topology, and demand |
| MT5 | V3 owner gate | international demand and competition first |
| Meta-strategies | V3 | statistical and product complexity |
| Shadow version racing | V3 or unit-economics gate | duplicate compute and data cost |
| Kubernetes, Kafka, new time-series database | exact measured capacity finding | no current evidence |

## Release effect

Nothing here changes the current deployability verdict:

- locally runnable: proven only for named local contracts;
- release deployable: rejected and open;
- production rehearsed: unproven;
- deployed: not authorized.
