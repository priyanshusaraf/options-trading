Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

## 3. Build a machine-readable corpus manifest

Create:

```text
docs/research/kleppmann/
├── 00-README.md
├── corpus-manifest.jsonl
├── corpus-manifest.csv
├── crawl-log.md
├── inaccessible-sources.md
├── deferred-external-bibliography.md
└── source-notes/
```

Each manifest record must include at least:

```text
source_id
canonical_url
source_page_url
content_type
artifact_type
first_party_or_external
title
author(s)
published_date
accessed_date
page_or_slide_count
checksum
license
transcript_available
visuals_inspected
crawl_status
duplicate_of
relevance_tier
relevance_dimensions
strategy_os_domains
summary
key_claims
limitations_or_age_risk
code_actionability
notes_path
```

At the end, report exact counts:

- inventoried;
- successfully fetched;
- fully read;
- partially reviewed;
- deduplicated;
- inaccessible;
- irrelevant after screening;
- high-priority;
- medium-priority;
- low-priority.

A source is not “reviewed” merely because its title was indexed.

---

## 4. Relevance scoring and reading depth

Score each source from 0–5 on:

1. real-money or irreversible correctness impact;
2. research-validity impact;
3. current Strategy OS code-path relevance;
4. probability that the repository currently has the failure;
5. usefulness for scale/recovery;
6. usefulness for user-facing trust and failure UX;
7. evidence quality and technical rigor;
8. implementation actionability;
9. novelty relative to existing Strategy OS documents;
10. release urgency.

Classify:

```text
TIER 0 — mandatory full deep review
TIER 1 — substantial review of all relevant sections and visuals
TIER 2 — targeted review and explicit applicability decision
TIER 3 — inventory only, with reason for low relevance
```

The archive itself contains old writing and changing opinions. Treat age as a warning, not an automatic rejection. Separate durable principles from obsolete product/framework details.

### 4.1 Mandatory Tier 0 starting set

These are starting points, not the complete final list:

#### Foundations, partial failure, clocks, replication, consistency

- public Concurrent and Distributed Systems lecture notes/slides;
- `Please stop calling databases CP or AP`;
- `Sequential Consistency versus Linearizability`;
- `Transactions: myths, surprises and opportunities`;
- `Research for Practice: Convergence`;
- relevant sections of the long Hydra interview;
- `The probability of data loss in large clusters`.

#### Transactions, locking, and financial correctness

- `How to do distributed locking`;
- `Hermitage: Testing the “I” in ACID` plus the Hermitage artifact repository;
- `Accounting for Computer Scientists`;
- transaction/recovery material in talks, papers, and course notes.

#### Logs, CDC, events, derived state, and dual-write failures

- `Using logs to build a solid data infrastructure (or: why dual writes are a bad idea)`;
- `Change Data Capture: The Magic Wand We Forgot`;
- `Turning the database inside-out with Apache Samza`;
- `Making Sense of Stream Processing`;
- `Online Event Processing: Achieving consistency where distributed transactions have failed`;
- `Thinking in Events`;
- `Should you put several event types in the same Kafka topic?`;
- `Bottled Water: Real-time integration of PostgreSQL and Kafka`.

#### Schema, caching, deterministic identity, and compatibility

- `Schema evolution in Avro, Protocol Buffers and Thrift`;
- `Rethinking caching in web apps`;
- `Java’s hashCode is not safe for distributed systems`;
- any paper/talk sections on materialized views, replay, schema compatibility, and migration.

#### Verification and testability

- `Prediction: AI will make formal verification go mainstream`;
- `Verifying distributed systems with Isabelle/HOL`;
- `Assessing the understandability of a distributed algorithm by tweeting buggy pseudocode`;
- formal verification artifacts that are relevant to a bounded Strategy OS invariant.

#### Scale, operations, and product trust

- `Six things I wish we had known about scaling`;
- `Having a launched product is hard`;
- `System operations over seven centuries`;
- relevant product, support, and customer-learning posts.

#### UX and failure communication

- `The complexity of user experience`;
- `Hey, what happened just then?`;
- `Yes/No/Cancel causes Aspirin sales to soar`;
- train-ticket-machine/interface-design posts;
- mobile-web failure and latency posts where the lesson remains applicable;
- customer-learning and ignored-customer retrospectives.

#### Future collaboration/offline seams—not current V0 mandates

- `Local-first software: You own your data, in spite of the cloud`;
- CRDT/convergence talks and papers;
- undo/redo and replicated-editing material;
- Automerge/local-first talks.

Review these for future strategy-editor durability, conflict handling, offline work, and collaboration seams, but do not implement CRDTs in V0 without a proven need.

---

## 5. Core research questions

For every high-priority source, answer:

1. What exact system model and failure assumptions does the source use?
2. What is the durable principle, and what is implementation-specific or dated?
3. Which Strategy OS invariant does it support, contradict, or expose as missing?
4. What realistic user-visible or financial failure could occur if we ignore it?
5. Which repository files, schemas, APIs, workers, queues, caches, or UI states are implicated?
6. Does the current code already solve it? Prove this with file/line/test/runtime evidence.
7. Is the issue:

```text
CURRENT BUG
LATENT BUG
MISSING INVARIANT
MISSING TEST
OBSERVABILITY GAP
UX/TRUST GAP
SCALE LIMIT
FUTURE SEAM
NOT APPLICABLE
OUTDATED/REJECTED
```

8. What is the narrowest correct change?
9. What test or formal model would prove the change?
10. What migration, rollout, rollback, compatibility, and operational consequences exist?
11. Which release owns it?
12. What tempting but incorrect cargo-cult response should be rejected?

---
