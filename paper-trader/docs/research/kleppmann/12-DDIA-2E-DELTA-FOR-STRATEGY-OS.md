# DDIA second-edition delta for Strategy OS

Date: 29 August 2026. Status: bounded public delta review. The second-edition
book text was not available to this capsule and is not claimed read.

## Sources and method

The review compared the official O'Reilly contents for the
[2017 first edition](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/)
and [2026 second edition](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/).
The [author page](https://martin.kleppmann.com/2026/03/24/designing-data-intensive-applications-2e.html)
confirms Martin Kleppmann and Chris Riccomini, March 2026 and ISBNs
9781098119065/9781098119027. The exact companion bibliography is commit
`1752cbd0cfbab5515f1606b48123b7c0d6103c51` of
[`ept/ddia2-references`](https://github.com/ept/ddia2-references), licensed
CC BY-NC 4.0.

The shell retrieval of the O'Reilly second-edition page returned HTTP 403. The
official indexed contents were available for inspection. No access control was
bypassed. The author page reports 670 pages, while O'Reilly's indexed product
page reports 672. This bibliographic difference does not support a technical
claim. No owner-provided lawful book file was identified in the project workspace.

## Publicly evidenced delta

This table records section-title evidence only. It does not infer arguments from
unavailable chapter text.

| Second-edition area | Public section-title delta | Strategy OS handling |
| --- | --- | --- |
| Architecture trade-offs | Chapter 1 now names cloud/self-hosting, distributed/single-node, microservices, serverless and law/society. | Use explicit trade-offs and adoption triggers. No new infrastructure. |
| Nonfunctional requirements | Chapter 2 separates latency distributions and percentiles, reliability, human error, load, scalability, operability, simplicity and evolvability. | KCA-005 below. V0 hardening, not a production-capacity claim. |
| Data models | Chapter 3 adds GraphQL, event sourcing and CQRS beside relational/document/graph models. | No universal event sourcing. Use existing immutable facts and outbox only where repository failures justify them. |
| Durable execution and events | Chapter 5 names durable execution/workflows and event-driven architectures. | KCA-006 below. Compare against the current job system before any dependency decision. |
| Sync and local-first | Chapter 6 names sync engines and local-first software. | Preserve V2 collaboration semantics. KCA-004 rejects V0 CRDT adoption. |
| Multitenancy | Chapter 7 names sharding for multitenancy. | KCA-007 below. Tenant isolation and sharding remain different questions. |
| Message processing | Chapter 8 names exactly-once message processing “revisited.” | Continue to state the boundary: at-least-once delivery plus idempotent effects and reconciliation unless direct evidence proves more. |
| Formal and randomized testing | Chapter 9 names formal methods and randomized testing beside partial failure, clocks and process pauses. | Apply only to critical state machines and direct failure hypotheses. No routine formalisation mandate. |
| Logical identity | Chapter 10 names ID generators and logical clocks. | Keep content identity, business time and ordering facts separate. Do not use wall time as a causal or fencing token. |
| Batch infrastructure | Chapter 11 names object stores and distributed job orchestration. | Preserve exact artifacts and durable job evidence. Do not infer a workflow engine or distributed object store need. |
| Streaming correctness | Chapters 12 and 13 retain time, fault tolerance, integrity, verification and derived state as explicit concerns. | Keep transaction-bound source facts, polling authority, idempotence and honest lag states. |
| Privacy and feedback loops | Chapter 14 expands predictive analytics into bias, accountability, feedback loops, surveillance, consent, data power and regulation. | KCA-008 below. Future recommendations require provenance, consent and conflict governance. |

## KCA-005: define NFRs before adopting scale infrastructure

- **Source and exact location:** DDIA 2e official contents, chapters 1 and 2;
  companion references `chapter-01-refs.md` and `chapter-02-refs.md` at commit
  `1752cbd0cfbab5515f1606b48123b7c0d6103c51`.
- **Assumptions:** Strategy OS is in the accepted Stage A planning envelope of
  roughly 0-50 serious users. No production load baseline or bottleneck has been
  established.
- **Strategy OS failure hypothesis:** Choosing a queue, sharding scheme or new
  deployable without workload, percentile, durability and recovery targets can
  add failure modes while solving no observed constraint.
- **Repository evidence:** The accepted reconciliation at
  `paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md:242-267`
  preserves one corpus and states that Stage A is a planning envelope only. It
  permits measurement, quotas, recovery and deployability evidence, and it
  records no capacity or bottleneck claim.
- **Classification:** V0 hardening and adoption gate. No current infrastructure
  defect is asserted.
- **Smallest safe response:** At the deployability gate, define workload names,
  latency percentiles, job-durability objectives, stale-data bounds, restore
  objectives and per-tenant ceilings from measured local/rehearsal evidence.
- **Verification:** Use repeatable workload fixtures and report distributions,
  queue depth, pool pressure, recovery time and resource ownership. An adoption
  proposal must reproduce the limiting failure and compare the current design.
- **Migration and rollback:** None for measurement. A later dependency requires
  its own expand-contract, data exit, rollback and operations owner.
- **Release owner:** `strategy-os-v0-security-operations-deployability`.
- **Disposition:** V0 HARDENING. Reject microservices, Kafka, Kubernetes,
  sharding or a workflow platform without measured pressure.

## KCA-006: durable workflows are a comparison, not an adoption mandate

- **Source and exact location:** DDIA 2e official contents, chapter 5 sections
  “Durable Execution and Workflows” and “Event-Driven Architectures”; companion
  `chapter-05-refs.md`, including the recorded Temporal workflow reference.
- **Assumptions:** The current research job system persists run state, claims,
  tokens and results in the database. Its supported workload has not been shown
  to require a separate workflow platform.
- **Strategy OS failure hypothesis:** A crash between a job effect and durable
  checkpoint can duplicate work or lose lineage. Replacing the job system before
  reproducing that failure can create a second scheduler and split authority.
- **Repository evidence:** `paper-trader/backend/app/backtest/repository.py`
  owns claim, heartbeat, batch and terminal predicates. The prior
  [job-claim packet](source-notes/job-claim-fencing.md) records current token
  fencing and remaining process-kill/PostgreSQL recovery limits. The repository
  has no accepted Temporal, DBOS or Restate runtime dependency.
- **Classification:** V0 verification obligation. No workflow dependency need is
  established.
- **Smallest safe response:** Continue exact crash/restart, claim/reclaim,
  checkpoint, cancellation and result-identity tests on the current system. Use
  the workflow vendors only as a capability comparison if a direct gap survives.
- **Verification:** Kill a worker before and after effect/checkpoint boundaries;
  restart on the supported database; prove no semantic switch, missing result or
  duplicate durable trial. Record operations and resource cost.
- **Migration and rollback:** None now. A later workflow adoption must migrate
  in-flight histories without replaying effects, retain an exit/export path and
  support rollback to the database-owned state machine.
- **Release owner:** `strategy-os-v0-canonical-research-spine` and
  `strategy-os-v0-robustness-lab` before the deployability gate.
- **Disposition:** V0 HARDENING. Reject Temporal, DBOS and Restate adoption now.

## KCA-007: multitenancy does not establish a sharding need

- **Source and exact location:** DDIA 2e official contents, chapter 7 section
  “Sharding for Multitenancy”; companion `chapter-07-refs.md` at the exact
  reference commit.
- **Assumptions:** Tenant ownership is a security and correctness invariant.
  Physical sharding is an operational topology chosen for measured isolation or
  capacity needs.
- **Strategy OS failure hypothesis:** Treating `owner_id` filters as a capacity
  plan can hide noisy-neighbour pressure; treating multitenancy as proof that
  sharding is required can add routing, migration and cross-shard failure modes
  before they are needed.
- **Repository evidence:** Owner scope appears in durable job, graph, outbox and
  monitoring identities, with dedicated cross-tenant tests such as
  `paper-trader/backend/tests/test_backtest_tenant_isolation.py` and
  `paper-trader/backend/tests/test_user_plane_tenant_isolation.py`. The accepted
  reconciliation records no capacity claim and no sharding authority.
- **Classification:** Already scoped for correctness; capacity evidence remains
  open. No current sharding finding.
- **Smallest safe response:** Keep owner-scoped predicates and measure per-tenant
  queue, database, cache and websocket load. Add quotas before topology changes.
- **Verification:** Run cross-tenant denial tests and workload fixtures that
  isolate one tenant's saturation. Record the threshold at which current
  admission or storage topology misses an accepted SLO.
- **Migration and rollback:** None now. Any future shard key needs online
  backfill, dual-read verification, ownership checks, reshard/restore evidence
  and a tested return path.
- **Release owner:** `strategy-os-v0-security-operations-deployability`; later
  scale-stage owner only after measured triggers.
- **Disposition:** PRESERVE SEAM NOW. Reject pre-emptive sharding.

## KCA-008: recommendation feedback needs provenance and consent

- **Source and exact location:** DDIA 2e official contents, chapter 14 sections
  on bias, responsibility, accountability, feedback loops, privacy, surveillance,
  consent, data power and regulation; companion `chapter-14-refs.md`.
- **Assumptions:** Strategy OS V0 has no accepted recommendation, marketplace or
  managed-allocation authority. Research outputs and user hypotheses already
  have exact lineage that future proposals can reference.
- **Strategy OS failure hypothesis:** A future ranking or recommendation can
  appear as source fact, favor platform-owned content, train on private strategy
  data without consent, or create self-reinforcing crowding.
- **Repository evidence:** The accepted V0-V6 reconciliation assigns active
  portfolio/hedge proposals to V2 and separates V3 strategy assets from managed
  allocation. It preserves source, rights, ownership, custody, execution
  authority and investor exposure as distinct facts. Current V0 capsules grant no
  recommendation or marketplace behavior.
- **Classification:** V2/V3 future governance seam and owner/legal decision.
- **Smallest safe response:** Preserve source/hypothesis/proposal attribution,
  graph diffs, experiment lineage and explicit consent boundaries. Before any
  recommendation product, define ranking ownership, conflict disclosure,
  decline behavior, telemetry eligibility and fresh validation.
- **Verification:** Use synthetic policy fixtures to distinguish source facts
  from proposals, reject missing consent/provenance, reproduce ranking versions
  and detect platform-owned preference. Research validity and privacy reviews
  remain mandatory.
- **Migration and rollback:** None in V0. A future migration must version policy,
  consent and model/artifact identity and support disabling recommendations
  without deleting research evidence.
- **Release owner:** V2 Portfolio/recommendation owner, V3 marketplace governance
  owner, and explicit legal/commercial/privacy owners.
- **Disposition:** V2/V3 / DEMAND-LED. No V0 implementation.

## Rejected interpretations

- A table-of-contents entry is not the same as reading a chapter.
- A reference in `ddia2-references` is not an admitted claim from that source.
- “Durable workflows” does not require a workflow platform.
- “Sharding for multitenancy” does not require sharding at Stage A.
- Event sourcing and CQRS are options, not a universal product model.
- Local-first and sync engines remain future seams, not V0 CRDT authority.
- Privacy and feedback-loop topics create governance questions, not legal claims.

No product, schema, dependency, frontend, provider, credential, deployment, live,
order or money change follows from this delta.
