Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

Prove that lower-priority work cannot starve:

```text
P0 — existing-position protection, kill switch, reconciliation
P1 — execution-critical data and evaluation
```

Measure before proposing infrastructure. Look for:

- unbounded queues;
- retry storms;
- reconnect thundering herds;
- fan-out explosions;
- N+1 queries;
- per-event full-graph recomputation;
- repeated parsing/loading;
- missing admission control;
- lack of per-tenant ceilings;
- UI update rate coupled to engine update rate;
- memory growth without ownership/eviction rules.

### 6.16 Backup, restore, correlated failure, and disaster recovery

Do not accept “we take backups” as evidence.

Prove:

- what is backed up;
- RPO/RTO targets;
- encryption and key recovery;
- restore into a clean environment;
- consistency between database and object artifacts;
- recovery of orders/positions/evidence;
- behavior if Redis/cache/queue state disappears;
- region/provider/account credential loss;
- correlated failure assumptions;
- disk-full and storage-quota behavior;
- migration rollback and forward-fix strategy.

Run at least one realistic restore/reconstruction exercise if the environment allows it.

### 6.17 UX edge cases and operational communication

Review the older UX/product posts for durable lessons, not styling.

Audit whether Strategy OS:

- uses ambiguous Yes/No/Cancel-like decisions;
- hides irreversible consequences;
- offers cancel without defining whether cancellation is guaranteed;
- reports generic “Something went wrong” for actionable failures;
- conflates empty, missing, stale, invalid, unavailable, and not-yet-loaded;
- loses user work after disconnect/session expiry;
- makes a long job appear frozen;
- allows duplicate actions under slow responses;
- explains blocked deployment/preflight reasons;
- provides undo/recovery where safe;
- preserves context after failure;
- tells users whether data is authoritative or delayed;
- communicates partial success honestly;
- provides support receipts without exposing strategy IP;
- designs for the post-launch support burden.

Create explicit UX requirements for each serious backend uncertainty state.

### 6.18 Formal methods—bounded, risk-weighted use

Do not attempt to formally verify the entire application.

Select one or more critical state machines where bugs could lose money or invalidate evidence, preferably:

- capital reservation/admission;
- order lifecycle and idempotency;
- open-position version ownership;
- research-job claim/retry/commit;
- deployment activation/kill-switch precedence.

Write a compact executable/formal model using the smallest suitable tool already available or reasonably adoptable, such as TLA+/PlusCal, Alloy, state-machine property tests, or another checked specification. State:

- variables;
- actions;
- safety invariants;
- liveness expectations;
- fairness assumptions;
- fault model;
- counterexamples found;
- correspondence to implementation tests.

Formal work must complement, not replace, integration and recovery tests.

---

## 7. Required contingency catalogue

Create `02-STRATEGY-OS-CONTINGENCY-CATALOGUE.md` with at least these fields:

```text
ID
Domain
Scenario
Trigger
Hidden assumption violated
User-visible symptom
Financial/research/security consequence
Current prevention
Current detection
Current recovery
Evidence in code/tests
Source(s)
Severity
Likelihood
Release owner
Required invariant
Proposed test
Proposed change
Migration/rollback
Status
```

Include, at minimum, scenarios for:

- duplicate order after timeout;
- accepted order with lost response;
- postback duplication/reordering;
- simultaneous capital requests;
- stale margin/position snapshot;
- expired lease and resumed old worker;
- kill switch racing entry;
- partial fill/cancel race;
- current selector changing while held instrument must not;
- provider semantic capability change;
- data-provider failover producing different bars;
- cross-instrument stale alignment;
- late/revised market data;
- wall-clock jump;
- cache key collision or omitted semantic version;
- dual-write succeeds on one side only;
- websocket missed event;
- worker crash around transaction boundary;
- duplicate optimisation trial;
- locked OOS contamination;
- schema rollback after new data was written;
- Redis/cache loss;
- database failover/retry;
- disk full;
- backup that cannot restore;
- tenant leak through cache/socket/job/log;
- support diagnosing an issue without strategy-source access;
- thundering-herd reconnect;
- low-priority research starving protection;
- user repeats a slow action;
- ambiguous cancel;
- UI shows “healthy” from stale state;
- old client reading new event schema;
- migration during active jobs/deployments;
- external provider rate-limit escalation;
- provider auth expiry during a live session;
- process pause/GC/host suspension;
- partial region/provider outage;
- corrupted or revised dataset invalidating evidence.

Do not stop at this list. The purpose of the corpus review is to discover failures we have not already named.

---

## 8. Source-to-code traceability

Create `04-ARCHITECTURE-GAP-MATRIX.md` and a machine-readable companion JSON file.

Every finding must contain:

```text
finding_id
source_id(s)
exact page/section/timestamp
principle
Strategy OS invariant
repository file(s) and line(s)
observed current behavior
reproduction/failure hypothesis
severity
confidence
current release impact
recommended disposition
change set
tests
migration
rollback
non-goals
```

Allowed dispositions:

```text
MUST FIX BEFORE V0
MUST SPECIFY/TEST BEFORE V0
V1 EXECUTION HARDENING
V1.1
V1.5
V2
V3 / DEMAND-LED
OBSERVABILITY ONLY
DOCUMENT / ADR
NO CHANGE — ALREADY CORRECT
REJECT — NOT APPLICABLE
REJECT — CARGO CULT
REQUIRES LEGAL/COMMERCIAL DECISION
```

A blog principle without a code path is not a finding. A code smell without a realistic failure hypothesis is not automatically a priority.

---
