Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

## 6. Mandatory Strategy OS audit domains

Map the corpus against actual code in all of the following areas.

### 6.1 Database transactions and isolation

Determine:

- actual production database and isolation level;
- ORM/driver transaction defaults;
- where read-modify-write races exist;
- whether critical predicates are protected, not merely individual rows;
- whether write skew, lost update, stale read, phantom, duplicate insert, or non-repeatable read can violate an invariant;
- whether retries are safe after serialization/deadlock/connection errors;
- whether unique constraints, exclusion constraints, compare-and-swap, row locks, advisory locks, or serializable transactions are used appropriately;
- whether migrations preserve invariants under mixed-version deployment.

Create Hermitage-style, repository-specific anomaly tests for critical flows rather than relying on the database marketing label.

### 6.2 Capital admission and double-spend prevention

Use this canonical scenario:

```text
10:00:00 — Deployment A requests a ₹5,000 buy
10:00:00 — Deployment B requests a ₹5,000 buy
Available admissible capital: ₹8,000
```

Prove:

- both requests use one coherent account snapshot or a versioned equivalent;
- the admission policy has a stable deterministic tie-breaker;
- reservation is transactional and recovery-safe;
- accepted + pending + filled exposure cannot exceed the allowed amount;
- duplicate retries cannot reserve twice;
- cancellation, rejection, partial fill, and timeout release or retain capital correctly;
- restart/replay reconstructs the same answer;
- every decision has a durable receipt.

Do not use a Redis/distributed lock as the only correctness mechanism for capital.

### 6.3 Distributed locks, leases, and fencing

Find every lock, lease, leader-election, singleton-worker, scheduler, job-claim, Redis lock, advisory lock, and “only one worker” assumption.

For each, classify whether the lock is for:

```text
EFFICIENCY ONLY
CORRECTNESS
```

For correctness locks, test the paused-worker failure:

```text
Worker A acquires lease
→ A pauses longer than lease
→ B acquires lease and performs work
→ A resumes and still believes it owns the work
```

Require fencing/version tokens or authoritative transactional state where necessary. A lease expiry is not proof that the old worker is dead.

### 6.4 Idempotency, retries, and timeout ambiguity

Audit all boundaries where a timeout does not reveal whether the action happened:

- broker order submission;
- broker modify/cancel;
- webhooks/postbacks;
- email/notification delivery;
- billing/payment operations if present;
- research-job creation;
- dataset import/admission;
- deployment activation;
- websocket commands;
- background task dispatch;
- object-store writes.

For each operation, define:

- operation ID/idempotency key;
- deduplication scope;
- replay semantics;
- response to duplicate, late, and conflicting requests;
- authoritative status lookup;
- retention period;
- safe retry policy;
- user-facing “unknown/pending/reconciling” state.

Never claim “exactly once” without defining the boundary and proof. Prefer at-least-once delivery plus idempotent effects and reconciliation.

### 6.5 Orders, fills, positions, and reconciliation

Attack:

- accepted order but lost HTTP response;
- duplicate postback;
- postback before synchronous response;
- out-of-order order events;
- partial fill racing cancel/modify;
- cancel rejected because already filled;
- stale position API;
- broker netting versus Strategy OS virtual ownership;
- restart during an open order;
- strategy version update while old-version position remains open;
- dynamic selector moving while held contract identity must remain fixed;
- kill switch racing new-entry admission;
- provider disconnection during protection handling.

Require an explicit order/position state machine, monotonic transition rules, durable event/receipt identity, and reconciliation that is safe to run repeatedly.

### 6.6 Event logs, CDC, dual writes, and materialized views

Inventory every dual-write pattern, including:

```text
DB + websocket
DB + queue
DB + cache
DB + object store
DB + search index
DB + analytics event
DB + broker side effect
DB + email/notification
```

Determine whether failures can leave derived systems inconsistent. Evaluate, but do not automatically adopt:

- transactional outbox;
- inbox/deduplication table;
- CDC;
- append-only domain event log;
- rebuildable materialized views;
- reconciliation jobs;
- compensating workflows.

For each derived view, state:

- source of truth;
- rebuild procedure;
- ordering scope;
- idempotency rule;
- lag/staleness contract;
- schema version;
- replay safety;
- monitoring and repair.

Do not introduce Kafka just to “be event-driven.” First prove the failure and the throughput/operational need.

### 6.7 Time, clocks, causality, and market event semantics

Audit every use of wall-clock time, database time, broker time, exchange time, provider timestamps, monotonic timers, UUID timestamps, and scheduled jobs.

Test:

- clock skew;
- NTP correction;
- process pause;
- leap/ambiguous time handling where relevant;
- timezone/DST mistakes in international or imported data;
- event time versus processing/ingestion time;
- duplicate timestamps;
- late and out-of-order events;
- same-timestamp deterministic ordering;
- higher-timeframe completed versus forming bars;
- cross-instrument maximum skew and maximum age;
- stale-but-present data;
- provider timestamps with different meanings.

Do not use wall-clock time to prove lock ownership or event causality. Preserve separate timestamps such as:

```text
observed_at
effective_at
published_at
ingested_at
processed_at
decision_at
submitted_at
acknowledged_at
filled_at
```

only where the domain requires them.

### 6.8 Market truth, research validity, and replay

Cross-check the current point-in-time market and data contracts against the corpus’s lessons on causality, versioning, and reproducibility.

Attack:

- present-day market rules projected into history;
- current contract master used for historical options/futures;
- adjusted/unadjusted price mismatch;
- data-provider correction changing old evidence;
- silent missing-data forward fill;
- lookahead from resampling or cross-series joins;
- cache keys missing dataset/node/session/adjustment identity;
- random seeds or parallel execution changing results;
- failed/partial optimisation trials omitted from evidence;
- job restart producing duplicate or divergent trials;
- old evidence silently reading a new dataset version;
- strategy semantic version drifting under the same ID.

Prove that evidence can identify the exact strategy, node versions, data, mappings, rules, costs, validation policy, engine version, and search history.

### 6.9 Schema evolution and rolling deployment

Inventory:

- database schemas and migrations;
- event payloads;
- websocket messages;
- REST/GraphQL contracts;
- broker/provider adapter contracts;
- stored strategy IR;
- node metadata;
- object-store artifacts;
- optimisation/validation result formats;
- cache values and job payloads.

For each, define backward/forward compatibility and mixed-version behavior.

Test:

- old writer/new reader;
- new writer/old reader;
- additive field;
- removed/renamed field;
- enum expansion;
- semantic meaning change under the same field;
- replay of old persisted messages;
- rollback after a new producer has emitted data;
- unknown event/node version;
- migration interruption.

Never reuse a stable field/tag/semantic ID for a different meaning.

### 6.10 Caches and deterministic identity

Find all caches and memoization, including in-process, Redis, database, HTTP, browser, CDN, research-kernel, and derived-feature caches.

For each cache, document:

- authoritative source;
- full key identity;
- tenant boundary;
- expiry policy;
- invalidation trigger;
- behavior after schema/code/data version change;
- stale-data tolerance;
- rebuild and cache-loss behavior;
- collision/hash assumptions;
- observability.

Test wrong-result hazards, not only hit rate. Include canonical instrument, timeframe, session policy, adjustment policy, missing-data policy, provider/dataset version, node semantic version, parameters, and range/segment identity where relevant.

### 6.11 Background jobs, optimisation, and queue semantics

Audit:

- persisted job state machine;
- claim/lease semantics;
- retries and backoff;
- duplicate workers;
- cancellation;
- restart/resume;
- checkpoint identity;
- partial results;
- resource accounting;
- fairness and starvation;
- per-tenant quotas;
- P0/P1 live protection priority over research;
- websocket/UI progress consistency;
- dead-letter/recovery path;
- deterministic candidate/trial identity.

Inject:

- worker crash before/after commit;
- queue redelivery;
- database disconnect;
- object-store failure;
- cancellation racing completion;
- stale lease;
- duplicate completion message;
- job owner deletion/tenant disable;
- process restart mid-trial;
- lower-priority load saturation.

### 6.12 Websockets, realtime UI, and user trust

Audit connection and UI semantics under:

- dropped/reconnected socket;
- duplicate event;
- missed event;
- out-of-order event;
- server failover;
- stale tab;
- old client schema;
- optimistic update rejection;
- slow command leading to repeat click;
- partial page state from different snapshots;
- tenant/channel authorization change while connected.

The UI must distinguish:

```text
CONFIRMED
PENDING
RECONCILING
STALE
DEGRADED
UNKNOWN
FAILED
BLOCKED
```

where appropriate. Never display an action as completed solely because the button click succeeded locally.

### 6.13 Tenant isolation, confidentiality, and support tooling

Attack cross-tenant leakage through:

- missing query filters;
- cache keys;
- websocket channels;
- background jobs;
- object-store paths/signed URLs;
- logs/traces/errors;
- support/admin tooling;
- broker-secret lookup;
- analytics/telemetry;
- reused idempotency keys;
- migration/backfill jobs.

Verify that support can diagnose through receipts and metadata without casually viewing customer strategy graphs/source. Record every privileged/break-glass path.

### 6.14 Provider partial failure and degraded operation

Model providers independently:

- live data provider;
- historical data provider;
- execution broker;
- account/portfolio provider;
- notification/email provider;
- object storage;
- database;
- cache/state store;
- job system.

Test partial failures and semantic capability changes. Do not silently switch market-data providers or order semantics. Define which operations continue, block, suspend, reconcile, or degrade.

### 6.15 Backpressure, load shedding, and scale economics

Map queueing and resource pressure across:

- market-data ingress;
- incremental graph evaluation;
- option-window updates;
- websocket fan-out;
- research requests;
- optimisation/Monte Carlo;
- imports;
- provider rate limits;
- database pools;
- external API retries.
