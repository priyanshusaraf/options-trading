# Strategy OS — Clean-Room Scale and Systems-Design Review Brief

**Date:** 29 August 2026\
**Scope:** Approximately 50 → 500 → 2,000 → 5,000 → 10,000 users\
**Status:** Review mandate, not an implementation authorization\
**Purpose:** Determine how Strategy OS should grow in reliability, capacity, cost, team, and architecture without prematurely replacing a simple system with distributed infrastructure.

---

## 0. Review objective

Perform a zero-assumption systems-design review of the **actual repository and deployment**, while preserving validated technical invariants and existing user work.

“From scratch” means:

```text
question every assumption
measure current behavior
reconstruct the real system model
compare alternatives
```

It does not mean:

```text
delete accepted architecture
rewrite the application
install fashionable infrastructure
```

The review must answer:

1. What can the current topology safely support?
2. Which bottlenecks appear at each realistic workload stage?
3. Which changes are configuration, code, data-model, deployment, or organizational changes?
4. What should remain unchanged?
5. What are the per-user and per-workload cost drivers?
6. What hiring/funding becomes necessary and when?
7. Which product features should be gated by scale, operational maturity, data rights, or regulation?
8. Which later architecture changes have measurable adoption triggers?

---

# 1. User count is not a workload model

Do not equate registered users with system pressure.

For every stage, estimate or measure:

```text
registered users
daily active users
weekly retained users
peak concurrent sessions
concurrent graph editors
normal backtests per minute/hour
heavy optimizations per day
Monte Carlo/walk-forward jobs per day
average and p95 dataset size
artifact/storage growth
signal monitors active during market hours
alerts generated per second/minute/day
websocket connections
provider/API requests
market-data subscriptions
instruments observed per user
Dynamic Watchlist candidates later
paper/live deployments later
orders, modifications, fills, and reconciliation events later
admin/support load
billing/webhook events
```

Create at least three workload profiles:

1. **Research-heavy:** few simultaneous users, expensive jobs and datasets.
2. **Signal-monitoring-heavy:** many market-hour monitors and alerts.
3. **Execution-heavy future:** fewer users but strict latency, reconciliation, and availability requirements.

Ten thousand passive registered users may be easier than five hundred concurrent live derivatives users.

---

# 2. Reconstruct the actual current topology

Before recommendations, record:

- repository root, worktree, branch, commit, dirty state;
- frontend framework and deployment;
- backend processes and language/runtime;
- authoritative database(s);
- migrations;
- background-job system;
- caches and in-process state;
- websocket/realtime path;
- object/file storage;
- market-data providers and broker adapters;
- authentication/session provider;
- payment provider;
- observability/logging;
- CI/CD and deployment mechanism;
- secrets/configuration handling;
- backups and restore;
- current cloud/vendor pricing assumptions;
- current test and staging environments.

Draw:

```text
current request path
current research-job path
current signal/alert path
current payment/webhook path
future execution-critical path
```

State every source of truth and every rebuildable projection.

---

# 3. Preserve a simple default architecture

The default target until evidence disproves it is:

```text
one coherent application / modular monolith
+
one authoritative transactional database
+
durable artifact/object storage where needed
+
bounded background workers
+
reconstructible caches
+
clear resource limits
+
strong observability, backup, and recovery
```

Do not recommend or install microservices, Kafka, Kubernetes, a workflow platform, Redis Cluster, event sourcing, a second database, or multi-region active-active merely because the user count reaches a round number.

A new component requires:

1. a measured current or imminent bottleneck/correctness problem;
2. proof existing topology cannot satisfy the invariant economically;
3. migration and rollback;
4. operational ownership;
5. cost and failure-mode comparison;
6. explicit owner approval.

---

# 4. Stage model

The exact stage boundaries should be calibrated from real usage. Use the following as planning envelopes.

## Stage A — approximately 0–50 serious users

### Product character

- founder-assisted alpha;
- low total concurrency;
- highly variable and potentially heavy research jobs;
- V0 research and alerts;
- frequent product change.

### Priorities

- correctness and tenant isolation;
- fast feedback and observability;
- reproducible research;
- simple deployment;
- backups and restore;
- rate/resource limits;
- payment/auth/admin correctness;
- alert durability;
- support receipts;
- no public execution authority.

### Preferred topology

Keep the smallest understandable topology. Separate app and worker processes only if necessary for heavy jobs or fault isolation, not as independent services with duplicated domain logic.

### Exit triggers

- users can self-onboard;
- core research/alert journey works without founder guidance;
- p95 latency and job queue are understood;
- restore drill passes;
- payment/entitlement reconciliation passes;
- meaningful weekly retention and willingness to pay.

## Stage B — approximately 50–500 users

### Product character

- early self-serve product;
- more simultaneous research;
- regular market-hour monitoring;
- support and billing volume becomes real;
- first production incidents likely.

### Likely needs, only if measured

- dedicated bounded worker pools;
- job priorities and per-tenant quotas;
- database connection pooling;
- object storage for large artifacts;
- query/index tuning;
- explicit websocket reconnection and catch-up;
- stronger staging and migration process;
- automated backups plus recurring restore tests;
- alert and payment operational dashboards;
- cost attribution by workload;
- clear SLOs and incident ownership.

### Exit triggers

- onboarding and support are repeatable;
- no tenant/resource monopolizes the system;
- p95/p99 job and API behavior is stable;
- there is a reliable deployment rollback;
- unit economics can be estimated;
- founders are no longer the only operators who can diagnose incidents.

## Stage C — approximately 500–2,000 users

### Product character

- repeatable commercial product;
- meaningful background-job backlog;
- many simultaneous monitors during Indian market hours;
- growing historical data and artifacts;
- first controlled execution cohort may exist separately.

### Possible needs, contingent on measurements

- stronger isolation among interactive research, heavy jobs, and live/signal workloads;
- autoscaling stateless app instances;
- separate worker classes without separate business authorities;
- durable job leasing/claims and checkpointing;
- cache/state abstraction if shared hot state is justified;
- managed database HA and connection discipline;
- artifact lifecycle/retention controls;
- load/fault tests from real workload traces;
- security review and dependency/supply-chain controls;
- on-call rotation and operational runbooks;
- provider quota planning and cost controls.

### Exit triggers

- measured load demonstrates where scaling occurs;
- execution-critical work, if any, cannot be starved by research;
- tenant cost and abuse controls work;
- database growth and maintenance are predictable;
- incident metrics and SLOs are stable;
- controlled execution safety gates are independently reviewed.

## Stage D — approximately 2,000–5,000 users

### Product character

- substantial market-hour fan-out;
- professional customers and possibly private institutional pilots;
- Dynamic Watchlists and richer data may be active;
- stronger availability expectations;
- higher support and compliance burden.

### Possible needs, only under proven pressure

- horizontally scaled runtime workers;
- workload partitioning by tenant/deployment/universe;
- explicit subscription sharing within licensing boundaries;
- hot-state coordination layer where rehydration is proven;
- websocket fan-out layer if direct app fan-out is a measured bottleneck;
- database read scaling or partitioning only where queries prove it;
- dedicated security/reliability ownership;
- provider redundancy for approved semantic equivalents;
- formal capacity planning and quarterly recovery exercises;
- private networking and environment separation appropriate to institutional contracts.

### Exit triggers

- defined and met service objectives;
- no single provider or database failure creates an unrecoverable state;
- marketplace/managed products are considered only if supply/demand/legal gates exist;
- institutional support and governance are staffed.

## Stage E — approximately 5,000–10,000 users

### Product character

- platform operation rather than founder-led SaaS;
- materially different workloads coexist;
- broader providers/data and possibly international use;
- stronger regulatory, security, and enterprise demands;
- more serious incident impact.

### Possible needs, evidence-led

- explicit control-plane/data-plane separation where it removes a proven failure coupling;
- stronger database HA/DR, tested RPO/RTO, and archival strategy;
- dedicated research, signal, and execution worker pools with shared semantics;
- sharding/partitioning only when a specific limit is reached;
- regional deployment only when latency, data residency, or customer demand requires it;
- formal platform capacity management;
- 24×7 or market-hours operations depending product authority;
- security, SRE, data, and support teams;
- audited controls for institutional/managed-money products.

Do not interpret this stage as an automatic microservice or Kubernetes trigger.

---

# 5. QoS and workload isolation

Preserve priority classes:

```text
P0 — position protection, kill switch, reconciliation
P1 — live execution-critical evaluation and order state
P2 — paper/shadow and signal monitoring
P3 — interactive research
P4 — optimization, walk-forward, Monte Carlo
P5 — nonessential analytics/UI refresh
```

For V0, P0/P1 may be mostly inaccessible publicly, but the architecture should not let future money paths share an unbounded queue with batch research.

Review:

- queue depth and wait time by class;
- per-tenant concurrency;
- cancellation and timeout;
- memory/CPU ceilings;
- backpressure;
- admission control;
- priority inversion;
- starvation;
- recovery after worker death;
- idempotent restart;
- cost per job/monitor.

---

# 6. Capacity and performance experiments

Build representative, reproducible tests rather than arbitrary synthetic benchmarks.

At minimum:

## API/session

- login/session refresh;
- strategy list/open/save;
- alert inbox filters and catch-up;
- billing status;
- websocket reconnect.

## Research

- cold and warm backtest;
- small and large datasets;
- parallel backtests;
- heavy optimization queue;
- worker death/reclaim;
- artifact write/read;
- cancellation and retry.

## Signal/alerts

- many monitors at market open;
- burst of signals;
- duplicate events;
- UI disconnected then reconnects;
- alert history pagination;
- delayed/stale event.

## Future execution

- broker timeout ambiguity;
- duplicate acknowledgements;
- partial fills;
- reconciliation after restart;
- simultaneous capital admission;
- degraded data/provider state.

For every test report:

- workload assumptions;
- hardware/cloud shape;
- dataset;
- concurrency;
- throughput;
- p50/p95/p99;
- errors;
- CPU/memory/database/IO;
- cost estimate;
- bottleneck;
- whether a change is justified.

---

# 7. Database and data-lifecycle review

Audit:

- authoritative financial/research/identity tables;
- transaction boundaries;
- indexes and query plans;
- large artifacts stored in database versus object store;
- migration duration and rollback;
- connection limits;
- backup and restore;
- retention/deletion/export;
- tenant-scoped access;
- hot versus archival data;
- immutable evidence and mutable projections;
- point-in-time market data growth;
- alert/event growth;
- billing/webhook audit growth.

Use the current database well before adding a second database.

Define measurable triggers for:

- larger instance;
- connection pooler;
- read replica;
- partitioning;
- archival/object store;
- analytical store;
- database split.

A round user count is not a trigger.

---

# 8. Provider and market-data capacity

Compute may not be the dominant cost. Review:

- subscription limits;
- websocket connection limits;
- historical request limits;
- instrument fan-out;
- quote/depth fields;
- data redistribution rights;
- per-user versus shared licensed feeds;
- provider rate-limit/reconnect behavior;
- contract-master and historical derivatives coverage;
- cost per monitored instrument and user;
- fallback semantic compatibility;
- data recording/retention rights.

Create a provider-capability and economics matrix for every release stage.

---

# 9. Cost model

Do not provide a single “server cost.” Break costs into drivers.

```text
application compute
background research compute
market-hour signal/runtime compute
database
object storage and egress
logs/metrics/traces
email/notifications
payment fees
identity/auth provider
market data and exchange/vendor licensing
broker/API costs
security tooling
backup/DR
support/on-call
compliance/legal/audit
engineering salaries
```

Calculate:

- fixed monthly base;
- cost per DAU;
- cost per retained paid user;
- cost per normal backtest;
- cost per heavy research job;
- cost per active signal monitor;
- cost per live deployment later;
- storage growth per user/month;
- gross margin by plan;
- provider/license step changes;
- worst-case abuse/noisy-neighbor cost.

Use current official vendor pricing at the time of review and record date/currency/tax assumptions.

---

# 10. Team and funding triggers

Do not translate every stage directly into a fundraising round. Produce capability needs and trigger conditions.

Possible ownership areas:

- product/frontend;
- backend/domain architecture;
- quantitative research/data;
- security;
- reliability/platform;
- customer success/support;
- compliance/legal/finance;
- institutional integrations.

For each stage, answer:

- minimum team to operate safely;
- which roles can be shared;
- what work cannot remain founder-only;
- expected monthly burn range under explicit assumptions;
- runway needed before the next commercial milestone;
- whether revenue can fund the stage;
- what external review/contract/data license requires capital;
- what evidence would justify fundraising.

Potential funding triggers include:

- paid retention proves the V0 wedge;
- market-data/license contract creates a step cost;
- public execution requires independent security and operations;
- institutional pilots require integrations/SLA staff;
- marketplace/managed money requires legal and operational design;
- enterprise treasury requires domain experts and long sales cycles.

Do not present invented precision. Show assumptions and ranges.

---

# 11. Security and trust progression

At every stage:

- auth/session security;
- tenant isolation;
- encryption and secret handling;
- strategy-IP confidentiality;
- dependency/supply-chain baseline;
- privileged-access audit;
- backup/restore;
- incident response;
- secure deletion/export.

Before public execution:

- independent security review;
- broker adapter conformance;
- capital/order/reconciliation testing;
- kill switch and degraded-state drills;
- production access controls;
- on-call readiness.

Before marketplace/managed capital:

- rights and provenance;
- fraud/misrepresentation controls;
- ranking conflicts;
- investor/creator support;
- regulated partner/structure;
- audit and reporting.

Before enterprise treasury:

- enterprise IAM/SSO and segregation of duties;
- maker-checker;
- model governance;
- audit controls;
- data residency;
- accounting/OTC/counterparty controls.

---

# 12. Architecture-change trigger registry

Create a registry such as:

```text
Concern
Current capacity/limit
Metric
Threshold
Observation window
Candidate change
Cheaper alternatives considered
Migration/rollback
Owner
Status
```

Examples:

- app CPU saturation;
- worker queue p95 wait;
- database connections;
- slow query rate;
- websocket fan-out;
- cache hit/miss;
- artifact storage;
- provider quotas;
- market-open alert burst;
- restore duration;
- deployment frequency/rollback;
- on-call incident load.

Every future infrastructure idea should have a measurable revisit trigger.

---

# 13. Required outputs

Create:

```text
docs/systems-design/scale-50-10000/
├── 00-README.md
├── 01-CURRENT-TOPOLOGY-AND-SOURCES-OF-TRUTH.md
├── 02-WORKLOAD-MODEL.md
├── 03-CAPACITY-BENCHMARK-PLAN.md
├── 04-STAGE-A-0-50.md
├── 05-STAGE-B-50-500.md
├── 06-STAGE-C-500-2000.md
├── 07-STAGE-D-2000-5000.md
├── 08-STAGE-E-5000-10000.md
├── 09-DATABASE-AND-DATA-LIFECYCLE.md
├── 10-PROVIDER-CAPACITY-AND-DATA-RIGHTS.md
├── 11-COST-AND-UNIT-ECONOMICS-MODEL.md
├── 12-TEAM-FUNDING-AND-OPERATIONS-TRIGGERS.md
├── 13-SECURITY-RELIABILITY-MATURITY-MATRIX.md
├── 14-ARCHITECTURE-CHANGE-TRIGGER-REGISTRY.md
├── 15-CHANGES-NOT-REQUIRED.md
└── 16-FINAL-DECISION-REPORT.md
```

Also provide a machine-readable assumptions file and cost model where useful.

---

# 14. Required final decision format

For every recommendation:

```text
Finding
Current evidence
Affected workload/stage
User consequence
Capacity/cost/security consequence
Smallest safe change
Alternatives rejected
Adoption trigger
Migration/rollback
Owner/team requirement
Release impact
Confidence
```

End with:

```text
SYSTEM SIMPLICITY OUTCOME

Deployables before / proposed after:
Stateful dependencies before / proposed after:
Databases before / proposed after:
Queues before / proposed after:
Network hops before / proposed after:
Current confirmed bottlenecks:
Hypothetical concerns deferred:
Cost drivers:
Funding/team triggers:
Next benchmark:
Owner decisions required:
```

The preferred result at early stages is usually:

```text
same topology
+
better measurements
+
stronger boundaries
+
bounded workers
+
correct indexes/transactions
+
reliable recovery
```

not an infrastructure rewrite.
