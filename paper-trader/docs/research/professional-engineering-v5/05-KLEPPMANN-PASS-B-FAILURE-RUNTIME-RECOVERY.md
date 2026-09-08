# Kleppmann Pass K-B: failure, runtime, and recovery

Status: **complete for the bounded Chat 1 audit**. Production code was not changed. Live broker, provider, PostgreSQL, Docker, restore, and deployment operations were not invoked.

Baseline: `de6faae3e97cf5537338bee2143350e53f70da1c` plus inherited dirty bytes. The V0 release profile denies execution authority, so the live paths below are future or legacy safety seams, not current V0 capabilities.

## Source claims kept separate from repository inference

| Source-supported claim | Exact reviewed location | Source assumptions | Bounded Strategy OS inference |
|---|---|---|---|
| Messages may be lost, duplicated, delayed, or reordered; a received message need only have been sent earlier. | `KLEPPMANN_ISABELLE_2022_V5`, **Modelling a distributed system in Isabelle/HOL**, message-set model | Asynchronous processes and an unreliable network | Broker/provider events need durable identity, monotone fact reduction, and an explicit conflict policy. The source does not prescribe Kafka, consensus, or formal verification here. |
| Crash recovery requires a deliberate distinction between durable and volatile state. | `KLEPPMANN_ISABELLE_2022_V5`, **Modelling...**, process state and valid event sequences | A process can stop and later continue from retained state | In-memory pending maps and WebSocket queues cannot authorize money or completed work; durable intent, claims, events, checkpoints, and cursors must do so. |
| Timestamps do not prove that all earlier related events have arrived; events whose order defines one entity should share one ordering domain. | `KLEPPMANN_EVENT_ORDER_2018_V5`, **Ordering problems** and **Combining event types** | A state is reconstructed from an ordered event history | Execution-intent and job state need entity-scoped sequence/conflict rules. This does not imply adopting Kafka. |
| One authoritative log/change stream can rebuild derived views; dual writes admit races and partial failure. | `KLEPPMANN_LOGS_2015_V5`, edited transcript sections **The problem with dual writes**, **Logs**, and **Change data capture**; figures `logs-10`, `logs-13`, `logs-34`, `logs-35` | Multiple representations derive from one fact history | Transaction-bound outboxes and reload-from-durable-state are the right local pattern; the existing database outbox is sufficient at current scale. |
| Consistency must be stated per operation instead of applying a broad CP/AP label. | `KLEPPMANN_CP_AP_2015_V5`, full article, especially CAP definitions and false dichotomy | Different operations can require different guarantees | Capital reservation needs serialized predicate protection; UI broadcast can be bounded and eventually refreshed. They do not need the same coordination mechanism. |
| Online event processing needs explicit input position, state, replay, and output semantics. | `KLEPPMANN_OLEP_2019`, pp. 1-16 and figures inspected in the fresh corpus review | Durable ordered inputs and replayable processing | Research restart identities and future live state snapshots must bind exact graph/data/policy/plan inputs. It does not establish current live-runtime readiness. |

## Current runtime topology

- The FastAPI process assembles three database planes and transaction-bound outbox delivery in `backend/app/main.py:71-194`. It has no Redis, Celery, Kafka, or external workflow engine.
- Backtest claims use database state and conditional claim tokens in `backend/app/backtest/repository.py:332-570,692-900`.
- Research operations use owner-scoped quotas, advisory/transaction locks, claim tokens, heartbeat, cancellation, item binding, and terminal evidence in `backend/research/domain/operations.py:283-989`.
- Execution persists an immutable intent before submit and appends broker observations in `backend/app/engine/live_broker.py:193-325`; reduction and scoped restart discovery live in `backend/app/engine/execution_lifecycle.py:180-514`.
- The WebSocket hub coalesces snapshots, bounds non-coalescing messages to 200 per client, and evicts a blocked sender after ten seconds in `backend/app/ws/manager.py:69-168`.
- The outbox uses bounded claim batches and durable cursors; PostgreSQL notification is only a wake-up hint and polling remains authoritative in `backend/app/events/delivery.py:193-288`.

## Finding ledger

### KPV5-B-001: canonical graph research bypasses ResourcePlan

Classification: **confirms existing F03; V0 BLOCKER; MISSING INVARIANT**.

`run_published_graph_experiment` verifies admission and graph/data provenance, then calls `run_experiment` without accepting, reconstructing, or recording a ResourcePlan (`backend/research/orchestrator/graph_experiment.py:193-222`). The canonical ResourcePlan and its reconstruction checks exist (`backend/app/ir/resource_plan.py:64-471`; `backend/app/ir/incremental_runtime.py:98-147,555-639`) but are not on this route. The programme already assigns F03 to `post-phase5-indicator-accuracy-registry-lineage-integration`; this audit does not create a competing owner.

Failure scenario: an admitted graph reaches research execution without its declared memory, storage, artifact, provider, or concurrency bounds. User consequence: workload cost and refusal evidence do not match the accepted graph contract. The smallest response is the existing F03 repair, not a scheduler or new queue. RED structural characterization: `characterization/test_graph_resource_plan_boundary.py`.

### KPV5-B-002: terminal observation conflicts can yield an internally inconsistent state

Classification: **CONFIRMED DEFECT; V1 FOUNDATION / EXECUTION**. V0 reachability: denied.

The reducer processes facts in insertion order, updates cumulative fills before terminal conflict handling, but refuses to change the first terminal status (`backend/app/engine/execution_lifecycle.py:180-302`). A `CANCELLED, filled=0` observation followed by `COMPLETE, filled=requested` produces `status=CANCELLED` with a full fill and an anomaly. It remains reconciliation-required until booking/protection, which limits money risk, but status and evidence are inconsistent. RED characterization: `characterization/test_execution_terminal_observation_conflict.py`.

Smallest response: specify a broker-status partial order and a terminal-conflict state such as `RECONCILIATION_REQUIRED`; never choose by arrival time alone. Test complete/cancel race, delayed lower cumulative observations, duplicate IDs, restart, and broker corrections. Do not infer that every terminal conflict may be auto-resolved.

### Retained control: unknown submit outcomes fail closed, with bounded residual uncertainty

Classification: **ALREADY CORRECT for the inspected seam; V1 FOUNDATION / EXECUTION**.

`execute_order` sends once, never retries the side effect, returns reconciliation-required on submit/poll/ack persistence uncertainty, and never assumes a timeout fill (`backend/app/engine/order_executor.py:67-141`). Live entry persistence precedes submission; an acknowledged order is persisted before further processing (`backend/app/engine/live_broker.py:193-325`). Restart matches a missing acknowledgement only when exactly one broker order has the durable tag; zero or multiple matches remain blocked (`backend/app/engine/live_broker.py:807-875`).

Limit: the broker tag is `pti-` plus 16 UUID hex characters (`backend/app/engine/execution_lifecycle.py:31-38`). Local uniqueness retries protect the current database, and multiple remote matches fail closed, but a complete provider/account/day tag namespace and retention analysis was not available. No tag-length change is recommended from this audit alone.

### KPV5-B-003: claim fencing is substantial; the current claim-race gate does not complete

Classification: **MISSING TEST / DEPLOYABILITY EVIDENCE**, not a confirmed current defect.

Backtest and research repositories bind all writes to owner/run/claim token, heartbeat and terminal predicates. A read-only shadow run reported positive SQLite evidence before later concurrent backend edits. Against final audited bytes, the combined suite remained blocked for more than ten minutes, and an isolated 45-second run timed out in the first case, `test_claim_race_allows_exactly_one_token_and_never_blocks_another_owner`. Evidence: `.agent/runs/kleppmann-reaudit-v5/pass-b-runtime/backtest-job-claims-timeboxed.log`. `backend/app/db/concurrency.py:1-104` uses `BEGIN IMMEDIATE` for SQLite and PostgreSQL transaction-scoped advisory locks plus row locks for PostgreSQL. This proves a current validation gate failure, not which lock/thread owns the defect. PostgreSQL/Docker were unavailable, so process-kill, network-partition, lock-timeout, and takeover behavior was also not re-proved.

### KPV5-B-004: no explicit P0/P1 QoS exists, but V0 has no live protection workload

Classification: **V1 FOUNDATION / EXECUTION; RECOVERY/CAPACITY GAP; not a V0 scheduler requirement**.

Research operations and sweeps have quotas and bounded batches, while WebSocket delivery and outbox polling are bounded. There is no common priority scheduler that proves protection/reconciliation cannot be starved by research/UI work. V0 denies the execution worker in `backend/app/core/release_profile.py:213-246` and `backend/app/main.py:256-277`, so this is not current V0 money reachability. Before V1 execution, measure contention and enforce reserved P0/P1 capacity at existing process/database boundaries. Do not add Kafka, Redis, or a workflow engine without a failing capacity test.

### KPV5-B-005: WebSocket state is bounded and derived; connected-session revocation is unspecified

Classification: **V1 FOUNDATION / EXECUTION; MISSING INVARIANT**, V0 denied.

Private channels are server-derived owner/account pairs, resume cursors are scope-bound, projection events reload durable state, and client queues are bounded (`backend/app/api/routes.py:1173-1263`; `backend/app/events/delivery.py:143-190`; `backend/app/ws/manager.py:77-168`). Authentication is checked before channel registration (`backend/app/api/principal.py:477-497`), but the receive loop does not revalidate expiry, revocation, or membership. V0 refuses both WebSocket routes before authentication. Chat 2 should first decide the required connected-session revocation latency, then add a deterministic revoke/expiry test rather than assume permanent sockets.

### KPV5-B-006: deterministic capital admission is transactionally shaped but intentionally unwired

Classification: **ALREADY CORRECT foundation / V1 FOUNDATION / EXECUTION**, not live authority.

The admission transaction fences the lease, locks an owner/account/book/currency head, checks exact snapshots and unresolved work, ranks deterministically, reserves whole atomic groups, and writes decisions/reservations/events in one caller-owned transaction (`backend/app/execution/capital_admission.py:530-822`). Risk reductions bypass capital consumption. The module explicitly says it is unwired, and current application search finds no production caller of `admit_closed_batch`. Recovery currently covers paper reservations in `backend/app/execution/capital_recovery.py:121-291`; live recovery needs its own later authority. No current V0 capital-contention claim follows.

### KPV5-B-007: restore and rebuild claims remain plane-specific

Classification: **RECOVERY GAP / DEPLOYABILITY EVIDENCE**.

Outbox state can replay from durable offsets, research jobs can be reclaimed, execution startup replays the journal, and derived WebSocket state reloads from durable projections. This audit did not execute a three-plane backup/restore, PostgreSQL point-in-time restore, corrupted checkpoint, or schema downgrade. “Rebuildable” therefore means only the rows and focused code paths named in `07-RECOVERY-AND-REBUILDABILITY-MATRIX.md`.

## Required adversarial answers, Pass B subset

| Question | Current answer |
|---|---|
| Broker accepts then local timeout/crash | One send; durable intent exists first; unknown result remains blocked for exact-tag/order reconciliation. Focused synthetic coverage only. |
| Duplicate or out-of-order order/fill events | Duplicate source IDs are idempotent; cumulative fill regressions and terminal reopening produce anomalies. Terminal-to-terminal conflict policy is defective as KPV5-B-002. |
| Two workers claim one job | Static token/predicate design is strong, but the current isolated SQLite claim-race test times out. PostgreSQL failover is also unproved. |
| Restart identity | Backtest/research claims bind durable run/item facts. Canonical graph research still omits ResourcePlan at KPV5-B-001. |
| Backpressure | WebSocket queues and outbox batches are bounded. A system-wide provider/research/execution admission and QoS proof does not exist. |
| Whole-graph live recomputation | Incremental research runtime exists; no accepted live execution authority exists. V1 measurement remains future. |
| Runtime recovery while warming | Research snapshots verify exact retained graph/registry/data/policy/plan inputs. No current live warming policy can be claimed. |
| WebSocket/cache authority | Both are derived. Outbox projection delivery reloads durable state. |
| Tenant ownership in workers | Inspected job, lifecycle, outbox, and money predicates carry owner/account scope. A repository-wide proof is not claimed. |

## Rejected implementation leaps

- No Kafka, Redis, Celery, distributed consensus service, or workflow engine is justified by this pass.
- No formal-verification programme is justified; two focused state-machine properties and database contention tests are cheaper and directly relevant.
- No live execution, credentials, provider connection, deployment, or infrastructure mutation was authorized.
