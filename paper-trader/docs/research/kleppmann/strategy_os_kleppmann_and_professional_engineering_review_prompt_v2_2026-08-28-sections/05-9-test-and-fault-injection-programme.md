Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

## 9. Test and fault-injection programme

Create or extend tests according to risk-weighted verification.

### Critical paths

Use:

- explicit invariants;
- RED → GREEN tests;
- concurrency tests with synchronization barriers;
- database integration tests against the actual engine;
- process crash/restart tests;
- duplicate/reordered event tests;
- fault injection and timeout ambiguity;
- state-machine/property-based tests;
- deterministic replay;
- independent review of the final invariant.

### Important paths

Use focused unit/integration/regression tests and representative failure cases.

### Routine paths

Use affected tests, type checks, build, and smoke validation. Do not create ceremonial tests solely to inflate coverage.

Useful tools may include existing project tooling or carefully justified additions such as:

- Testcontainers;
- Toxiproxy;
- Hypothesis/property testing;
- k6 or an existing load framework;
- database isolation harnesses;
- deterministic fake clocks;
- broker/provider simulators;
- process kill/restart harnesses.

Do not add a tool before proving it fills a real gap and checking license/maintenance cost.

---

## 10. Implementation gate

Do not begin broad refactoring after the reading phase.

For each proposed change, require:

1. exact failure hypothesis;
2. current-code evidence;
3. source evidence;
4. project invariant;
5. smallest correct design;
6. alternatives considered;
7. performance and operational impact;
8. schema/API compatibility;
9. migration and rollback;
10. test plan;
11. release classification.

### 10.1 Implement now only when

- it fixes a confirmed current V0 correctness/security/research-validity defect;
- it closes a foundational money-path invariant already reachable or required by the active phase;
- it is an additive seam that prevents a known destructive rewrite and is cheap/safe now;
- or it adds a test/observability mechanism needed to prove safety.

### 10.2 Do not implement now merely because

- a source discusses Kafka, CRDTs, consensus, local-first, event sourcing, microservices, distributed transactions, Redis, or formal verification;
- the design is theoretically elegant;
- a future version might scale;
- it would look “enterprise-grade”;
- another company uses it.

### 10.3 Explicit anti-cargo-cult rules

- Do not replace PostgreSQL transactions with a distributed lock.
- Do not use Redis as authoritative financial truth.
- Do not adopt Kafka/CDC without a proven dual-write, replay, or throughput need and an operations plan.
- Do not split the codebase into microservices without measured deployment/team/scale need.
- Do not adopt eventual consistency in a money invariant that requires serialization.
- Do not demand linearizability everywhere when a weaker, explicit contract is sufficient.
- Do not claim CAP as a complete architecture analysis.
- Do not use wall-clock time as a fencing token.
- Do not use a non-cryptographic or runtime-dependent hash as durable identity.
- Do not silently downgrade provider/order/protection semantics.
- Do not implement CRDT collaboration in V0; preserve a future seam only if the present model would otherwise block it.
- Do not use formal proof as an excuse to avoid testing the real database, broker adapter, or recovery path.

---

## 11. Commit and migration discipline

Use small, reviewable commits. Suggested sequence:

```text
1. corpus manifest and source notes
2. architecture/contingency gap documents
3. tests that expose confirmed failures
4. critical correctness fixes
5. migrations and compatibility handling
6. observability and UX-state fixes
7. ADRs and deferred roadmap
8. final verification and report
```

Every implementation commit must state:

- finding IDs;
- invariant protected;
- tests run;
- migration/rollback notes;
- source references.

Do not mix unrelated cleanup or aesthetic refactoring into this audit.

For database migrations:

- support deployment order explicitly;
- consider old app/new schema and new app/old schema overlap;
- use expand/migrate/contract where required;
- define rollback after writes in the new format;
- test from zero and from representative current state;
- avoid long blocking changes on active tables without a plan.

---

## 12. Required deliverables

Create the following, adapting paths only to existing repository conventions:

```text
docs/research/kleppmann/
├── 00-README.md
├── 01-CURRENT-AUTHORITY-MAP.md
├── corpus-manifest.jsonl
├── corpus-manifest.csv
├── crawl-log.md
├── inaccessible-sources.md
├── deferred-external-bibliography.md
├── 02-STRATEGY-OS-CONTINGENCY-CATALOGUE.md
├── 03-UX-AND-TRUST-EDGE-CASES.md
├── 04-ARCHITECTURE-GAP-MATRIX.md
├── architecture-gap-matrix.json
├── 05-PRIORITY-READING-MAP.md
├── 06-SOURCE-TO-STRATEGY-OS-SYNTHESIS.md
├── 07-IMPLEMENTATION-AND-MIGRATION-PLAN.md
├── 08-SCALE-RECOVERY-AND-DEGRADED-STATE-PLAN.md
├── 09-REJECTED-CARGO-CULT-CHANGES.md
├── 10-FINAL-VERIFICATION-REPORT.md
└── source-notes/
```

Create/update bounded ADRs as findings justify, especially for:

- transaction/isolation policy for capital and other critical predicates;
- idempotency and timeout-ambiguity contract;
- distributed lock/lease/fencing policy;
- event/outbox/CDC responsibility boundary;
- order lifecycle and reconciliation state machine;
- event envelope and schema evolution;
- time/event-time semantics;
- cache identity and rebuildability;
- job claim/retry/checkpoint semantics;
- authoritative database versus Redis/cache/queue state;
- websocket/realtime consistency contract;
- backup/restore/reconstruction;
- bounded formal model for a critical path.

---

## 13. Required final response

Return a decision-grade report, not a diary.

It must include:

### A. Repository context

- branch/worktree;
- starting and ending commit;
- dirty-state handling;
- technologies actually found.

### B. Corpus coverage

- exact counts by status and tier;
- all inaccessible sources;
- how PDFs, visuals, slides, and videos were handled;
- top 20 sources for Strategy OS and why;
- older sources rejected or treated cautiously.

### C. Highest-impact newly discovered contingencies

For each:

- scenario;
- consequence;
- current code evidence;
- source;
- severity;
- action taken or scheduled.

Highlight genuinely new failures not already represented in canonical Strategy OS documents.

### D. Confirmed bugs and gaps

Separate:

```text
CONFIRMED BUGS
MISSING TESTS
MISSING INVARIANTS
UX/TRUST GAPS
OBSERVABILITY GAPS
SCALE LIMITS
FUTURE SEAMS
FALSE ALARMS / ALREADY CORRECT
```

Give exact file/line references.

### E. Changes made

- commits;
- files;
- migrations;
- tests;
- behavior before/after;
- rollback.

### F. Changes deliberately not made

Explain why each major tempting architecture change was deferred or rejected.

### G. Verification

List exact commands and results for:

- targeted tests;
- database/integration tests;
- concurrency/fault tests;
- frontend type/build/tests;
- migrations from zero and current state;
- deterministic/replay tests;
- load tests where relevant;
- formal/model checking where used;
- restore/recovery exercise where feasible.

### H. Release map

Classify every unresolved item into:

```text
V0 BLOCKER
V0 NON-BLOCKING HARDENING
V1 EXECUTION
V1.1
V1.5
V2
V3 / DEMAND-LED
REJECTED
```

### I. Residual risk

State clearly what has not been proven, what environment limitations prevented verification, and what evidence is still needed.

---
