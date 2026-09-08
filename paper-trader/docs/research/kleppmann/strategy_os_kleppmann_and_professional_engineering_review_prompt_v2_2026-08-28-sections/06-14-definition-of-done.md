Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

## 14. Definition of done

This task is complete only when:

1. every first-party website item in the defined roots is inventoried;
2. every direct PDF/slide/transcript/publication artifact is accounted for;
3. high-priority PDFs and visuals are genuinely inspected;
4. all high-priority claims are traceable to exact source locations;
5. findings are mapped to actual Strategy OS code and tests;
6. realistic contingencies include both backend failures and user-visible consequences;
7. confirmed critical failures have RED → GREEN evidence or an explicit blocker report;
8. no speculative distributed technology was adopted without measured need;
9. current V0 scope remains shippable;
10. future V1/V1.1/V1.5/V2/V3 seams are preserved without implementing future products prematurely;
11. the final report tells the owner exactly what changed, what was discovered, what remains unsafe, and what should happen next.

Begin now. First print repository context, locate the authority documents and active capsule, and create the corpus manifest before making any code changes.


---

# ADDENDUM V2 — Missing Kleppmann Themes and the Strategy OS Professional Engineering Reference Programme

**Date:** 28 August 2026\
**Status:** Mandatory extension to the Kleppmann review mandate\
**Precedence:** This addendum supplements the prompt above. Where it adds a stricter research, traceability, or verification requirement, follow this addendum. It does not authorize speculative scope expansion or premature infrastructure.

## 15. Why this addendum exists

The first mandate covers the major distributed-systems failure families well: partial failure, clocks, transactions, isolation, leases, idempotency, event logs, schema evolution, caches, jobs, websockets, tenancy, provider degradation, backpressure, disaster recovery, UX uncertainty states, and bounded formal methods.

A second pass over Martin Kleppmann's full publication catalogue, current talks, the 2026 second edition of *Designing Data-Intensive Applications*, and adjacent professional engineering sources reveals several important themes that were either absent, underweighted, or too implicit:

1. exact numeric and unit semantics;
2. an explicit coordination-versus-convergence decision map;
3. the 2026 DDIA second-edition delta;
4. data governance and full information lifecycle;
5. provider portability and clean exit/restore paths;
6. tamper-evident evidence and independently verifiable receipts;
7. credential, device, session, and cryptographic-key lifecycle;
8. semantic conflict handling for future collaborative strategy graphs;
9. internationalisation, time, currency, and locale-safe input/output;
10. algorithmic feedback loops, recommendation governance, and conflicts of interest;
11. software-supply-chain integrity;
12. a durable external reference programme so architecture guidance continues beyond this one review.

These areas must now be included.

---

## 16. Mandatory new Kleppmann/DDIA audit domains

### 16.1 Exact numeric representation, dimensions, and rounding

Treat numeric representation as a domain contract, not a language implementation detail.

Audit all code and schemas representing:

- money and account balances;
- prices and premiums;
- quantities, lots, multipliers, and contract sizes;
- percentages, rates, basis points, Greeks, and ratios;
- fees, taxes, brokerage, exchange charges, slippage, and P&L;
- backtest metrics and optimisation objective values;
- timestamps, durations, and sequence numbers;
- tick-size and lot-size rounding.

Required questions:

1. Where are binary floats used?
2. Which uses are acceptable analytical approximations, and which are unacceptable financial or identity values?
3. Are `float`, `Decimal`, integer minor units, strings, database numeric types, JavaScript numbers, and provider payloads mixed implicitly?
4. Where and how does rounding occur?
5. Is the rounding mode explicit and versioned where it affects evidence or execution?
6. Can non-finite values enter persistence, JSON, caches, rankings, risk decisions, or frontend displays?
7. Are units encoded in types or merely implied by variable names?
8. Can rupees, paise, percentages, decimal fractions, basis points, shares, lots, and contracts be confused?

Produce a numeric-domain ADR defining at least:

```text
Money
Currency
Price
Quantity
Lots
ContractMultiplier
Rate
Percent
BasisPoints
Timestamp
Duration
```

The ADR must define:

- canonical storage representation;
- API representation;
- arithmetic rules;
- conversion rules;
- rounding boundaries and modes;
- overflow/underflow behavior;
- serialization and hashing rules;
- invalid/non-finite policy;
- research versus financial precision requirements.

Minimum tests:

- round-trip serialization across backend, database, API, and frontend;
- deterministic fee/P&L calculation;
- tick and lot rounding at boundaries;
- conservation and double-entry properties where a ledger exists;
- no `NaN`, infinity, or negative zero in durable evidence;
- property-based tests over large/small/negative values;
- parity between research and future execution arithmetic where semantics should match.

Do not mechanically replace every analytical float with decimal arithmetic. Make a documented domain decision.

### 16.2 Coordination budget and convergence map

Create:

```text
docs/research/kleppmann/11-COORDINATION-AND-CONSISTENCY-MAP.md
```

For every important Strategy OS object and transition, classify the weakest safe model:

```text
SERIALIZABLE / LINEARIZABLE COORDINATION REQUIRED
SINGLE-WRITER OR PARTITION-ORDERED
ATOMIC DATABASE TRANSACTION
IDEMPOTENT APPEND-ONLY EVENT
EVENTUALLY CONSISTENT / CONVERGENT DERIVED STATE
EPHEMERAL BEST-EFFORT FAN-OUT
```

At minimum classify:

- strategy revision publication;
- dataset admission/version registration;
- experiment creation and completion;
- optimisation trial claim, retry, and commit;
- OOS reveal;
- research approval/rejection;
- deployment activation and disarm;
- capital reservation and release;
- order intent, submission, acknowledgement, fill, cancel, and reconciliation;
- position ownership;
- notification delivery;
- websocket/UI projections;
- analytics/materialized views;
- telemetry;
- future Dynamic Watchlist membership;
- future collaborative graph edits.

Required rule:

> Never pay the availability and latency cost of global coordination where convergence is safe, and never use eventual consistency where an invariant, authority decision, money balance, exact ownership, or one-time reveal requires coordination.

For each choice record:

- invariant;
- consistency model;
- ordering scope;
- idempotency key;
- conflict rule;
- recovery source of truth;
- user-visible uncertainty state;
- test that proves the decision.

### 16.3 Mandatory DDIA second-edition delta review

The 2026 second edition of *Designing Data-Intensive Applications* is a Tier 0 source. Use a lawfully available copy if one exists in the owner's environment. Otherwise use first-party/public material, the official table of contents, public talks, and cited open papers without bypassing access controls.

The delta review must explicitly cover:

- cloud versus self-hosting and provider-exit trade-offs;
- distributed versus single-node systems;
- microservices and serverless as trade-offs rather than status symbols;
- defining nonfunctional requirements and percentiles;
- reliability, operability, simplicity, evolvability, and human error;
- event sourcing and CQRS;
- durable execution and workflows;
- event-driven architectures;
- sync engines and local-first software;
- sharding for multitenancy;
- exactly-once message processing revisited;
- formal methods and randomized testing;
- logical clocks and ID generators;
- object storage and distributed job orchestration;
- correctness in streaming systems;
- privacy, accountability, consent, and feedback loops.

Create:

```text
docs/research/kleppmann/12-DDIA-2E-DELTA-FOR-STRATEGY-OS.md
```

Every proposed implication must be classified as:

```text
V0 BLOCKER
V0 HARDENING
PRESERVE SEAM NOW
V1 EXECUTION
V1.1 DYNAMIC UNIVERSES
V1.5 OPTIONS CERTIFICATION
V2
V3 / DEMAND-LED
REJECT
```

### 16.4 Data governance and complete information lifecycle

The existing Strategy OS emphasis on provenance and immutable evidence is necessary but not sufficient. Audit the full lifecycle of:

- account/profile data;
- strategy source and graph contents;
- uploaded datasets;
- broker credentials and tokens;
- provider payloads;
- backtests, optimisation trials, and evidence artifacts;
- logs, traces, metrics, support receipts, and audit events;
- backups, replicas, caches, object storage, local files, and exports;
- deleted, expired, corrected, or superseded data.

For each data class record:

```text
owner / controller
purpose
legal or product necessity
sensitivity
source
jurisdiction / residency
who may access it
normal retention
backup retention
deletion mechanism
export mechanism
correction/versioning behavior
encryption and key owner
support visibility
telemetry eligibility
```

Resolve explicitly the tension between:

```text
immutable evidence and auditability
versus
user deletion, privacy, retention limits, and strategy-IP confidentiality
```

Possible patterns to evaluate include:

- immutable financial/authority receipts containing minimal non-secret facts;
- cryptographic hashes after user content is deleted;
- tombstones and revocation records;
- separate retention classes for raw strategy content and operational receipts;
- cryptographic erasure by destroying per-tenant keys;
- backup expiry and restore-time deletion replay.

Do not invent legal conclusions. Produce technical options and flag issues that require legal review.

Minimum V0 outputs:

- data inventory;
- retention matrix;
- deletion/export state machine;
- restore-after-deletion test;
- support-access boundary test;
- telemetry redaction policy.

### 16.5 Provider portability, sovereignty, and clean exit

Treat provider independence as an operational capability, not only an interface abstraction.

Audit whether Strategy OS can:

- export a strategy and its executable identity without provider-specific IDs;
- export dataset manifests and evidence bundles;
- reconstruct a research result in a clean environment;
- switch object storage, queue, cache, observability backend, or hosting provider without changing strategy semantics;
- migrate broker/data providers through an explicit compatibility receipt;
- operate in a degraded/read-only mode if a vendor account is suspended or unavailable;
- recover from loss of a SaaS dependency;
- document which dependencies are genuinely portable and which are not.

Create:

```text
docs/research/kleppmann/13-PORTABILITY-AND-PROVIDER-EXIT-PLAN.md
```

For V0, require at least one clean-environment restoration exercise for the research plane and one user-visible export format. Do not build full local-first sync or a desktop runtime solely for portability.

### 16.6 Tamper-evident evidence and independently verifiable receipts

Strategy OS already values exact strategy, data, engine, and experiment identity. Extend the audit to ask whether a later reader can detect tampering or accidental substitution.

Evaluate a bounded evidence-bundle manifest containing:

```text
strategy revision hash
dataset/version hashes
mapping and market-rulebook versions
engine/build identity
node-library versions
parameters and policies
trial/search manifest
result artifact hashes
approval/reveal/deployment receipts
creation time and signer identity
```
