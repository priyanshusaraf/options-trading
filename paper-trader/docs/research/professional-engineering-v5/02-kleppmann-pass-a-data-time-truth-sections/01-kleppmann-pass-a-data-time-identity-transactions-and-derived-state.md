Reference: [section index](../02-KLEPPMANN-PASS-A-DATA-TIME-TRUTH.md). Read with its scope; this is not a new assignment.

# Kleppmann Pass A: data, time, identity, transactions, and derived state

Date: 2026-08-31\
Posture: production code read-only\
Baseline: `codex/execution-foundation` at `de6faae3e97cf5537338bee2143350e53f70da1c` plus inherited dirty bytes

## Decision

The current repository contains a strong point-in-time authority foundation and a narrow canonical-manifest research path. It does not yet justify a general claim of research validity or universal historical market truth.

Three current paths fail direct characterization:

1. an experiment-spec hash collision can silently bind a new run to a different stored recipe;
2. qualification reads the full history before the same history is labelled OOS by validation;
3. the V0 route policy permits the legacy sweep that resolves today's provider universe or a curated fallback.

The first is low-likelihood identity corruption but violates immutable evidence reconstruction. The second invalidates the word “untouched” for the legacy research pipeline. The third bypasses the canonical-manifest-only data path promised by the active V0 research surface.

The bounded Q03 canonical path itself passed static reconstruction: it verifies exact owner, manifest, typed dependency, physical instrument, bar, provider-source, correction-chain, truth-snapshot, time, availability, cost, and adapter identities before evaluation. It supports only one contiguous NSE/BSE INR equity-spot series at 15/30/60 minutes, with no corrections, gaps, delayed availability, adjustment, roll, multi-instrument, session-context, derivative, or forming-bar semantics.

## Transferable source principles

### Source of record and derived state

[Using logs to build a solid data infrastructure](https://martin.kleppmann.com/2015/05/27/logs-for-data-infrastructure.html) and [Online Event Processing](https://martin.kleppmann.com/papers/olep-acm-queue.pdf) show why direct writes to multiple stores can reorder or partially fail. The durable lesson is narrower than the machinery:

- one transaction owns the source fact;
- projections, caches, indexes, notifications, and UI views are derived;
- a derived consumer may lag, restart, or receive an effect twice;
- rebuildability and explicit lag are part of correctness.

The Kafka/Samza examples solve larger cross-store systems. They do not justify a new event platform here. Strategy OS already has database-owned immutable facts and a transaction-bound outbox for the inspected paths.

### Stable identity

[Java's `hashCode` is not safe for distributed systems](https://martin.kleppmann.com/2012/06/18/java-hashcode-unsafe-for-distributed-systems.html) supports one precise rule: cross-process identity must derive from stable canonical bytes, not a runtime's process-local hash contract.

[Schema evolution in Avro, Protocol Buffers and Thrift](https://martin.kleppmann.com/2012/12/05/schema-evolution-in-avro-protocol-buffers-thrift.html) separates writer and reader schema, immutable field/tag identity, compatibility order, and schema-version lookup. Strategy OS should transfer those invariants, not adopt those libraries by analogy.

### Explicit inputs and caches

[Rethinking caching in web apps](https://martin.kleppmann.com/2012/10/01/rethinking-caching-in-web-apps.html) argues that answer-changing data dependencies should be explicit and business logic should be deterministic over those inputs. It also treats cache staleness as an application policy. Its Hadoop, Storm, lambda-architecture, and Flowquery material is dated and solution-specific.

### Time domains

Cambridge *Distributed Systems*, pages 30-31, distinguishes time-of-day clocks from monotonic elapsed clocks. NTP may step a wall clock forwards or backwards. Only differences from one monotonic clock on one node are valid elapsed durations.

This does not make wall time invalid for event, publication, business, or audit timestamps. It requires each timestamp to state its domain.

### Transactions and named guarantees

[Hermitage](https://martin.kleppmann.com/2014/11/25/hermitage-testing-the-i-in-acid.html) supports testing concrete concurrent histories on the actual engine rather than accepting an isolation label. [Please stop calling databases CP or AP](https://martin.kleppmann.com/2015/05/11/please-stop-calling-databases-cp-or-ap.html) reinforces operation-specific safety and liveness statements.

Neither source supplies a Strategy OS transaction boundary. The repository and a direct concurrency history must do that.

### Formal verification

[Verifying distributed systems with Isabelle/HOL](https://martin.kleppmann.com/2022/10/12/verifying-distributed-systems-isabelle.html) gives a useful model for message loss, duplication, delay, timeout, crash, and stable versus volatile state. The later [formal-verification prediction](https://martin.kleppmann.com/2025/12/08/ai-formal-verification.html) is speculative and explicitly says the specification remains the hard part.

Use a bounded model only for a critical state machine with a reproduced failure. Do not formalize ordinary research CRUD or infer that AI-generated proof changes current proof cost.

## Actual evaluation timeline

The current authority model uses several distinct clocks:

| Fact | Time fields | Repository meaning | Audit status |
| --- | --- | --- | --- |
| Rulebook record | `effective_from`, `effective_to`, `recorded_at` | When the rule applies and when Strategy OS recorded the revision | CLEAN for the inspected contract |
| Market-truth snapshot v3 | `effective_from`, `effective_to`, `recorded_at`, `knowledge_cutoff` | Snapshot scope, original recording fact, and maximum included knowledge | CLEAN after accepted NMT-001 correction |
| Raw provider segment | `recorded_at` | When raw bytes entered evidence custody | CLEAN |
| Provider observation | `event_time`, `completed_at`, `available_at`, `recorded_at` | Market event, completed value, provider availability, local recording | AT RISK: construction still permits availability before completion |
| Normalized observation | same four fields plus correction lineage | Causal normalized value and revision provenance | AT RISK for the same ordering gap |
| Dataset segment/manifest | event and availability ranges, `created_at`, `recorded_at` | Closed coverage and evidence custody | CLEAN structurally; relation semantics are loader-specific |
| Canonical experiment selection | `as_of` | Server-checked replay cutoff for every dependency and row | CLEAN in the narrow Q03 path |
| Runtime evaluation index | aware input index | Recorded bar timestamps; no process clock supplies bar context | CLEAN |
| Job/run lifecycle | started/completed/checkpoint times | Operational processing facts, not market time | Separate from executable identity except where recipe records it |

There is no standalone `published_at` field. Provider `available_at` currently carries the earliest knowable instant. `recorded_at` represents Strategy OS custody. That vocabulary is adequate only if provider capture proves `available_at` from real source semantics and refuses backdating.
