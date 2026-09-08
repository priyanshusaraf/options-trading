Reference: [section index](../13-BROADER-SOURCE-CATALOG.md). Read with its scope; this is not a new assignment.

# Broader source catalog

Date: 2026-08-31
Repository baseline: `de6faae3e97cf5537338bee2143350e53f70da1c` plus inherited dirty bytes
Chat 1 handoff: `12-KLEPPMANN-REAUDIT-HANDOFF-FOR-CHAT-2.md`

## Method and status vocabulary

This catalog contains sources actually opened during Chat 2. Search results that
were not opened remain leads and are not counted below. `FULL TEXT` means the
relevant HTML document was read through its extracted text. `SELECTED SECTIONS`
means exact sections or PDF pages were inspected. `ABSTRACT/METADATA` supports only
the stated abstract or bibliographic fact. A source never authorizes implementation.

Every application decision still requires:

```text
source claim and assumptions
→ current Strategy OS failure hypothesis
→ repository evidence or direct probe
→ smallest current-stack response
→ migration, rollback, observability and release owner
```

## A. Database, temporal data and transaction correctness

| ID | Source and reviewed location | Review | Transferable claim | Strategy OS decision |
| --- | --- | --- | --- | --- |
| DB-01 | [PostgreSQL 16 transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html), §§13.2.1–13.2.3 | FULL TEXT | Read Committed uses statement snapshots; Repeatable Read still permits serialization anomalies; Serializable requires whole-transaction retry. | Specify isolation per predicate and prove exact concurrent histories. Do not label the whole database “serializable.” |
| DB-02 | [PostgreSQL 16 explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html), row/advisory locks and deadlocks | FULL TEXT | Locks can block indefinitely, deadlocks need ordered acquisition/retry, and advisory locks are voluntary and bounded shared-memory resources. | Prefer row predicates/constraints for owned records. Use transaction advisory locks only for a named invariant and bounded cardinality. |
| DB-03 | [PostgreSQL queue-like `SKIP LOCKED` semantics](https://www.postgresql.org/docs/17/sql-select.html) | SELECTED SECTION | `SKIP LOCKED` intentionally returns an inconsistent view and is suitable only for queue-like consumers. | It may distribute claims but cannot prove aggregate completeness or fencing. |
| DB-04 | [Jepsen consistency models](https://jepsen.io/consistency/models) | FULL TEXT | Consistency models are sets of histories; stronger names do not substitute for operation-specific anomalies. | Name the capital, claim, ledger and artifact predicate, then test its history. |
| DB-05 | [FoundationDB simulation and testing](https://apple.github.io/foundationdb/testing.html) | FULL TEXT | Deterministic simulation combines seeded replay with live performance and hardware-failure testing. | Reuse seeded failure schedules and invariant oracles; do not build a FoundationDB-style simulator. |
| DB-06 | Jensen and Snodgrass, [Temporal Database](https://www2.cs.arizona.edu/~rts/pubs/TRmerged.pdf) | ABSTRACT/DEFINITION | Valid time describes modeled reality; transaction time describes when the database recorded a fact; both produce bitemporal data. | Map these concepts to explicit market/effective and recorded/known times without introducing a generic temporal platform. |
| DB-07 | Kulkarni and Michels, [Temporal features in SQL:2011](https://sigmod.org/publications/sigmodRecord/1209/entire-issue.pdf), PDF pp. 33–41 | SELECTED PAGES | Application and system time are orthogonal; periods use explicit start/end columns, closed-open semantics, and start-before-end constraints. | Existing explicit fields and immutable snapshots are sufficient if constraints and cutoff queries are precise. No temporal-table dependency is required. |
| DB-08 | Bailis et al., [Coordination Avoidance in Database Systems](https://www.vldb.org/pvldb/vol8/p185-bailis.pdf) | ABSTRACT/SELECTED SECTIONS | Coordination is required where concurrent operations can violate a named invariant, not everywhere. | Keep money, unique identity and ownership predicates coordinated; leave read projections and UI delivery weaker/rebuildable. |
| DB-09 | Gray, [A Transaction Model](https://infolab.usc.edu/csci599/Fall2008/papers/b-1.pdf) | ABSTRACT/CONTENTS | Atomicity, durability, restart, serial histories, predicate locking and deadlock are separate proof obligations. | A successful local transaction does not prove external broker effect or restart reconciliation. |
| DB-10 | Lamport, [Time, Clocks, and the Ordering of Events](https://www.microsoft.com/en-us/research/publication/time-clocks-ordering-events-distributed-system/) | METADATA/ABSTRACT | Physical timestamps do not establish causal order across independently delivered events. | Order broker observations and revisions with source sequence/identity and reconciliation policy, not timestamps alone. |

## B. Reliability and asynchronous failure

| ID | Source and reviewed location | Review | Transferable claim | Strategy OS decision |
| --- | --- | --- | --- | --- |
| REL-01 | Featonby, [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | FULL TEXT | Caller intent must scope the token; the first parameters must be stored; same token plus different intent must refuse. | Compare canonical intent bytes on every duplicate order/job request. A unique key alone is insufficient. |
| REL-02 | Brooker, [Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) | SELECTED ARTICLE | Timeouts, bounded retries, exponential backoff and jitter reduce amplification only when the operation is safe to retry. | Unknown broker submit remains reconciliation state; never turn timeout into rejection or blind resend. |
| REL-03 | Google SRE, [Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/) | FULL TEXT | Overload expands queues and retry traffic; fail early, bound queues, shed lower-priority work and test degraded modes. | Research/optimization must shed before future protection/reconciliation. V0 has no execution worker, so this is a measured V1 gate. |
| REL-04 | Akidau et al., [The Dataflow Model](https://research.google/pubs/the-dataflow-model-a-practical-approach-to-balancing-correctness-latency-and-cost-in-massive-scale-unbounded-out-of-order-data-processing/) | ABSTRACT | Event time, processing progress, late data and retractions require explicit correctness/latency/cost choices. | Preserve completion, availability and correction semantics. Do not import Beam/watermark machinery into bounded historical datasets. |
| REL-05 | OpenTelemetry, [trace semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/trace/) and [database conventions](https://opentelemetry.io/docs/specs/semconv/db/) | SELECTED SECTIONS | Producer/consumer and database operations need stable, versioned telemetry schemas. | Instrument existing boundaries with release/resource/tenant-safe IDs; do not make telemetry a source of truth. |
| REL-06 | Google SRE, [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) | FULL TEXT | Monitoring and paging should remain simple, actionable and low-noise. | Add semantic-correctness metrics and direct receipts before dashboards; no new telemetry platform is implied. |
