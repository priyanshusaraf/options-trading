Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

## 17. Professional engineering source registry

The following sources complement Kleppmann. They are not all equal authorities, and no source may override repository evidence, official provider specifications, or Strategy OS owner decisions.

### 17.1 Tier A — continuous core authorities

#### A1. Martin Kleppmann, Cambridge course material, and DDIA 2e

Use for:

- data models and evolution;
- transactions and consistency;
- clocks, causality, and partial failure;
- event logs and derived state;
- local-first and convergence;
- data governance;
- formal reasoning and distributed-systems security.

Primary roots:

```text
https://martin.kleppmann.com/
https://martin.kleppmann.com/archive.html
https://martin.kleppmann.com/talks.html
https://dataintensive.net/
```

#### A2. AWS Builders' Library

Use for:

- idempotent APIs;
- timeout selection;
- retries, exponential backoff, and jitter;
- overload, backpressure, and load shedding;
- shuffle sharding and tenant blast-radius control;
- queue backlogs;
- leader election;
- correlated failures;
- operational visibility;
- risky fallback paths.

Root:

```text
https://aws.amazon.com/builders-library/
```

Prioritize the first-party articles on idempotent APIs, retries/timeouts, overload, load shedding, shuffle sharding, leader election, queue backlogs, and avoiding fallback.

#### A3. Google Site Reliability Engineering books and workbook

Use for:

- SLOs and error budgets;
- monitoring and alerting;
- incident response;
- blameless postmortems;
- overload and cascading failures;
- capacity planning;
- emergency response;
- reliable data pipelines;
- operational simplicity.

Root:

```text
https://sre.google/books/
```

#### A4. Jepsen and official PostgreSQL concurrency documentation

Use together for:

- consistency-model precision;
- testing database claims rather than trusting labels;
- transactional anomalies;
- network partitions, process pauses, and failover;
- PostgreSQL isolation, predicate locks, row locks, advisory locks, and application-level consistency.

Roots:

```text
https://jepsen.io/
https://jepsen.io/consistency
https://www.postgresql.org/docs/current/mvcc.html
https://www.postgresql.org/docs/current/transaction-iso.html
https://www.postgresql.org/docs/current/explicit-locking.html
```

#### A5. Stripe Engineering, Modern Treasury, and TigerBeetle

Use for future execution/money paths and any V0 financial accounting that already exists:

- immutable ledgers;
- double-entry models;
- pending, posted, and available balances;
- idempotency;
- concurrency controls;
- reconciliation of expected versus actual movement;
- data-quality monitoring;
- zero-downtime migrations;
- strict serializability and state-machine replication patterns.

Roots:

```text
https://stripe.com/blog/engineering
https://stripe.com/blog/ledger-stripe-system-for-tracking-and-validating-money-movement
https://stripe.com/blog/idempotency
https://www.moderntreasury.com/journal
https://docs.tigerbeetle.com/
```

Treat vendor material as an implementation case study, not a product recommendation. Cross-check invariants against accounting principles, database behavior, and Strategy OS requirements.

#### A6. FoundationDB deterministic simulation and testing material

Use for:

- deterministic simulation;
- seeded replay;
- process/network/disk fault injection;
- reproducible concurrency failures;
- code probes and shadow validation;
- recovery testing.

Root:

```text
https://apple.github.io/foundationdb/testing.html
```

Do not attempt to recreate FoundationDB's entire simulator. Extract the seams and determinism practices useful for Strategy OS.

#### A7. OWASP, CISA, NIST SSDF, and SLSA

Use for:

- application-security verification;
- secure product design;
- authentication, session, secrets, file upload, API, logging, and tenancy controls;
- secure development lifecycle;
- customer-security outcomes;
- software supply-chain provenance.

Roots:

```text
https://owasp.org/www-project-application-security-verification-standard/
https://cheatsheetseries.owasp.org/
https://www.cisa.gov/securebydesign
https://csrc.nist.gov/projects/ssdf
https://slsa.dev/spec/
```

#### A8. OpenTelemetry specifications

Use for a vendor-neutral telemetry contract:

- traces;
- metrics;
- logs;
- correlation identifiers;
- semantic conventions;
- redaction and export boundaries;
- collector architecture.

Root:

```text
https://opentelemetry.io/docs/
```

### 17.2 Tier B — targeted architecture and verification authorities

#### B1. Temporal, DBOS, and Restate official documentation

Use only when evaluating durable jobs/workflows:

- retries and resumability;
- workflow determinism;
- versioning and replay;
- cancellation;
- timers;
- exactly-once effects and their limits;
- virtual objects/single-key coordination.

Roots:

```text
https://docs.temporal.io/
https://docs.dbos.dev/
https://docs.restate.dev/
```

Required output is a capability comparison against Strategy OS's existing job system. Do not adopt any engine merely because its documentation is compelling.

#### B2. TLA+, Hillel Wayne, and Hypothesis

Use for:

- precise state-machine models;
- bounded formal verification;
- property-based tests;
- rule-based stateful tests;
- testing optimized/vector and streaming implementations for equivalence.

Roots:

```text
https://lamport.azurewebsites.net/tla/tla.html
https://www.hillelwayne.com/
https://hypothesis.works/articles/
```

#### B3. Martin Fowler's distributed-systems patterns and evolutionary migration material

Use for:

- named patterns;
- incremental replacement;
- strangler migrations;
- avoiding microservice cargo cults;
- evolutionary architecture.

Root:

```text
https://martinfowler.com/articles/patterns-of-distributed-systems/
```

#### B4. Cloudflare, GitHub, Shopify, and other transparent engineering postmortems

Use as a failure corpus, especially for:

- hidden dependencies;
- configuration propagation;
- credential rotation;
- overload and retry storms;
- bad rollback assumptions;
- control-plane/data-plane separation;
- online migrations;
- multi-tenant isolation;
- job-history retention.

Roots:

```text
https://blog.cloudflare.com/tag/post-mortem/
https://github.blog/engineering/
https://shopify.engineering/
```

Every incident note must distinguish the initiating event, enabling conditions, detection gaps, mitigation, and transferable lesson. Do not generalize from one company's architecture without proof.

### 17.3 Tier C — trading-runtime and research-validity authorities

#### C1. NautilusTrader

Use for:

- deterministic event-driven trading architecture;
- research/live core parity;
- event sourcing and replay;
- execution reconciliation;
- provider/venue adapters;
- deterministic simulation testing.

Root:

```text
https://nautilustrader.io/docs/latest/
```

Review exact commits and license before code reuse.

#### C2. QuantConnect LEAN

Use for:

- event-driven algorithm semantics;
- data/broker separation;
- warm-up;
- corporate actions and survivorship concerns;
- configurable fee, fill, slippage, and margin models;
- live/backtest divergence and reconciliation.

Root:

```text
https://www.quantconnect.com/docs/v2/
```

#### C3. Freqtrade

Use for concrete tests that detect:

- look-ahead bias;
- recursive-indicator startup drift;
- backtest/live data-window differences;
- exchange-adapter churn.

Root:

```text
https://docs.freqtrade.io/
```

#### C4. hftbacktest

Use later for:

- feed and order latency models;
- queue-position assumptions;
- replay-based order-book simulation;
- conservative versus probabilistic fills.

Root:

```text
https://hftbacktest.readthedocs.io/
```

This is not a V0 requirement and must not create a false impression that Strategy OS is an HFT system.

#### C5. Jane Street engineering, Mechanical Sympathy, and Aeron

Use selectively for:

- type-driven domain modeling;
- battle-tested testing culture;
- predictable performance;
- bounded queues and backpressure;
- message sequencing, archive, and replay;
- low-latency designs when measured need exists.

Roots:

```text
https://blog.janestreet.com/
https://mechanical-sympathy.blogspot.com/
https://aeron.io/docs/
```

Do not adopt OCaml, Aeron, lock-free structures, custom allocators, or ultra-low-latency architecture without profiling and an actual product requirement.

---
