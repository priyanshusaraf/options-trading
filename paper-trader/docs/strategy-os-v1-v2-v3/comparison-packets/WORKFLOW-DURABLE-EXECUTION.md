# Workflow and durable-execution comparison packet

## Concrete scenario

    launch optimisation
    → persist trials
    → worker crashes
    → resume
    → select candidate
    → request locked OOS reveal
    → obtain human approval
    → run deployment preflight
    → create deployment

## Current Strategy OS position

Strategy OS already has durable research operations:

- owner and operation identity;
- pending, running, completed, failed, and cancelled outcomes;
- claim token, holder, expiry, heartbeat, and takeover;
- bounded item checkpoints;
- exact run binding;
- progress events;
- build and provider-mode checks.

It also has separate deployment and authority services. The gap is an end-to-end Workflow definition and instance that invokes those services without writing their tables directly.

## Comparison

| System | Best fit | Cost or risk | Verdict |
| --- | --- | --- | --- |
| Current Strategy OS operations | Research jobs, claims, checkpoints, domain evidence | Not a general Workflow product | KEEP + HARDEN |
| DBOS Python | Database-backed Python workflows and queues without a separate server | Schema dependency, replay discipline, and current async/cancel issue reports | BOUNDED SPIKE |
| DBOS TypeScript | Cross-language confirmation of workflow, step, queue, and batch-ingestion patterns | Wrong backend language for current research plane | REFERENCE ONLY |
| Temporal Python | Mature durable server, signals, queries, timers, child workflows, deterministic replay | New service, operational load, SDK sandbox limitations, versioning burden | BOUNDED SPIKE only after need |
| Restate Python | Durable async service and object model | New runtime and smaller Python ecosystem | BOUNDED SPIKE alternative |
| Airflow | Execution history tied to graph versions | Batch scheduler weight and definition by Python execution | REFERENCE ONLY |
| Dagster | Compile and validate a graph before execution | Data-asset bias and service surface | REFERENCE ONLY |
| Prefect | Declarative cache policy and workflow ergonomics | Non-transitive identity and definition by execution | REFERENCE ONLY |
| Kestra | Definition, plan, execution, and pinned nested calls | Large service and dynamic interpolation | REFERENCE ONLY |
| XState | Pure transition plus explicit effects | Not a durable dataflow or job engine | Local state-machine reference |

## Current issue evidence

Two 2026 DBOS Python issue reports matter to the adoption decision:

- [completed async invocation can rerun wrapper code](https://github.com/dbos-inc/dbos-transact-py/issues/762);
- [cancellation can race completion without a clear caller outcome](https://github.com/dbos-inc/dbos-transact-py/issues/767).

These are issue reports, not broad judgments about DBOS. They confirm that Strategy OS must test wrapper side effects, replay, cancellation, and terminal races in a bounded spike.

## Durable-work ADR

Decision: keep Strategy OS domain jobs authoritative. Do not adopt a general workflow dependency now.

A future backend may execute a Strategy OS Workflow instance only behind this port:

| Operation | Domain authority |
| --- | --- |
| start research | research operation repository |
| checkpoint item | research operation item |
| reveal OOS | exact evidence gate |
| request approval | approval fact tied to exact inputs |
| portfolio admit | portfolio admission service |
| reserve capital | account reservation ledger |
| create deployment | deployment command service |
| submit order | execution command and lease authority |

The workflow backend owns scheduling and replay. It never owns Strategy, evidence, approval, deployment, reservation, order, fill, or money identity.

## Research job state model

Keep the current durable state model and make its command outcomes explicit:

    PENDING
      → CLAIMED
      → RUNNING
      → COMPLETED
      → FAILED
      → CANCELLED

Valid recovery edges:

    CLAIMED or RUNNING with expired lease
      → TAKEOVER
      → RUNNING

Every item moves:

    PENDING
      → RUNNING with exact run identity
      → COMPLETED with immutable receipt

Cancellation is a request fact. The terminal result must say whether cancellation won or arrived too late.

## Retry and idempotency policy

- Every Workflow instance has a caller-chosen durable ID.
- Every step command has an idempotency key derived from Workflow instance, step, attempt-independent semantic input, and exact target.
- Replaying completed work returns the stored receipt.
- A stale worker cannot complete an item after lease loss.
- External side effects require a Strategy OS command ID and reconciliation.
- Broker orders remain at-least-once uncertain until broker evidence resolves them.
- Human approval never retries as a generic boolean. It binds exact reviewed facts.
- Compensation is a new domain command, not history deletion.

## Human approval persistence

Approval should bind:

- owner and actor;
- Workflow definition and instance;
- candidate identity;
- Strategy version;
- Universe evaluation and snapshot;
- research evidence;
- proposed deployment binding;
- portfolio policy;
- expiry and stale-on-change rules.

Any material change makes the approval stale. A later Workflow may ask again; it may not reinterpret the old approval.

## Bounded adoption spike

Proposed capsule: v2-durable-work-backend-spike

Run the same non-money research workflow through:

1. current Strategy OS operations;
2. DBOS Python;
3. one of Temporal or Restate if current operations show an actual ceiling.

Measure:

- process death at each stage;
- duplicate start;
- wrapper side effects;
- cancellation race;
- child failure;
- database outage;
- deploy and migration burden;
- operator diagnostics;
- exact provenance;
- recovery time.

Accept a dependency only if it reduces code and operational risk for the measured workload.

## Rejections

- no batch orchestrator in the live order path;
- no workflow UUID as Strategy or deployment identity;
- no generic attributes as canonical domain facts;
- no partial replay of real-money effects without reconciliation;
- no visual Workflow builder before deterministic templates prove demand.

## Verdict

KEEP + HARDEN current durable research operations. DEFER a general Workflow engine to V2. Require a bounded spike before any dependency adoption.
