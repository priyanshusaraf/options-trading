# Kleppmann artifacts and DDIA 2e source packet

Date: 29 August 2026. Capsule: `kleppmann-corpus-artifacts-and-ddia2e`.

This packet continues the existing 373-record corpus. It did not run the HTML
crawler. The [one-hop triage](../one-hop-triage.jsonl) classifies all 2,016
recorded links. Triage admitted 117 bounded candidates and deferred 1,899 records.
Admission means eligible for later review. It does not mean fetched, read,
licensed for reuse or applicable.

## Exact artifacts and reading depth

| Source | Exact identity | Review | Licence evidence and limit |
| --- | --- | --- | --- |
| Cambridge *Distributed Systems* notes | 91 pages; SHA-256 `4a754e36358948d4f98cb26fb8ecd44d868024d3bb0f26db30851158ddea3064` | Every page read and every page render inspected. Relevant diagrams cover RPC failures, clocks, broadcast order, quorums, Raft, two-phase commit, linearizability and collaboration conflicts. | Page 1 states CC BY-SA. The author course page links CC BY-SA 4.0. |
| *Making Sense of Stream Processing* | 183 pages; SHA-256 `13793a2c25d6f707e91dfc17884eebc8cc9fc69473156c3ab851ca73117572b2` | Every page read and every page render inspected. | Copyright 2016 O'Reilly Media, all rights reserved. Analysis and citation only. |
| *Online Event Processing* | 21 pages; SHA-256 `f4b10a04ab4408e99d317ec2ee1d44efa991af1396856f12c8b188c8393fde79` | Every page read. The database/search-log and payment-pipeline diagrams were inspected. | Copyright 2019 held by the authors; publication rights licensed to ACM. No broad reuse licence was identified. |
| *Local-First Software* | 25 pages; SHA-256 `60c6e47c3b648fbe73c1613f28251bd5c3f4c3ecd534127653684ee3194c9aa2` | Every page read. Conflict screenshots, the seven-ideal table, CRDT examples and prototype figures were inspected. | ACM personal/classroom copying notice on page 1. Other reuse requires permission. |
| Hermitage | commit `f029bec8e32af6a9506508638fdf74ef61286225` | README caveats, anomaly table, PostgreSQL histories and licence reviewed. No artifact code was executed or copied. | CC BY 4.0 in README. |
| Redlock counteranalysis and current Redis lock page | captured SHA-256 `32fe7cc1e6e757b45af5991fb0cb2ea4bba6c548a0525da3297d07f6af553b86` and `66446de34d311ca74c9ac901319088ff01baa49bd85b3bbda4e405e2db61d848` | Counteranalysis and current safety, liveness, clock and fencing sections read. | No reuse licence was inferred. The sources are argument and current product guidance, not a reason to add Redis. |

The page-level hashes, extracted text, contact sheets and direct-inspection state
are under `.agent/runs/kleppmann-corpus-artifacts-and-ddia2e/root/pdf-review/`.
The tracked [PDF ledger](../pdf-review-ledger.json) records the four reviewed PDFs.

## KCA-001: elapsed-time metrics need a monotonic clock

- **Source and exact location:** Cambridge notes, pages 25 and 30-31. Quartz
  clocks drift; NTP can step a time-of-day clock forwards or backwards; a
  monotonic clock is suitable for elapsed durations on one node.
- **Assumptions:** The value measures elapsed duration within one process. It
  is not a market event timestamp, durable business time or cross-node order.
- **Strategy OS failure hypothesis:** An NTP step during a dataset read can make
  `read_seconds` negative or inflated, which corrupts an operational metric and
  can mislead a capacity or latency decision.
- **Repository evidence:**
  `paper-trader/backend/app/backtest/dataset_store.py:853-897` subtracts two
  `datetime.now().timestamp()` readings on every exit path. In contrast,
  `paper-trader/backend/app/engine/runner.py:231-240` deliberately uses
  `time.monotonic()` for readiness and explains the NTP failure.
- **Classification:** Confirmed observability gap. No dataset bytes, result
  identity, trading decision or money fact depends on this measurement.
- **Smallest safe response:** Under the research-spine owner, replace only the
  elapsed-read timer with `time.monotonic()`. Keep durable `fetched_at` and
  market timestamps on their declared time domains.
- **Verification:** Inject a wall-clock backward step and a monotonic advance.
  Assert a non-negative accumulated duration on success and every refusal path.
  Run affected dataset-store tests. This capsule did not run or edit them.
- **Migration and rollback:** No schema or data migration. Rollback restores the
  timer call only. Existing metrics are ephemeral and should not be rewritten.
- **Release owner:** `strategy-os-v0-canonical-research-spine`, before capacity
  evidence consumes this metric.
- **Disposition:** Record a finding. Do not implement it in this corpus capsule.

## KCA-002: durable facts and delivery are separate boundaries

- **Source and exact location:** *Making Sense of Stream Processing*, pages
  56-64, 82-87 and 152-164; *Online Event Processing*, pages 6-10 and 14-18.
  The sources show non-atomic and reordered dual writes, then derive separate
  views from an ordered log. OLEP also states that subscriber lag is unbounded
  and that cross-store reads do not gain snapshot isolation automatically.
- **Assumptions:** One authoritative transaction owns the domain fact. Delivery
  is at least once, effects are idempotent, and a consumer may lag or restart.
- **Strategy OS failure hypothesis:** A domain mutation can commit while a
  websocket, cache or notification write is lost, or a restarted dispatcher can
  repeat an effect. Treating the notification as authority can show false state.
- **Repository evidence:** `paper-trader/backend/app/events/outbox.py:1-5`
  declares a transaction-bound durable outbox. Lines 370-423 serialize an
  aggregate, deduplicate producer identity, append a content-addressed event and
  make PostgreSQL notification transactional. The notification is a wake-up,
  not authority. `paper-trader/backend/tests/test_outbox_delivery.py:55-81`
  exercises polling after a lost notification and at-least-once replay after a
  crash.
- **Classification:** Already correct for the inspected outbox contract. The
  source does not prove every producer or future alert consumer uses it.
- **Smallest safe response:** Keep the plane-local outbox and polling source of
  truth. Extend future monitoring persistence through its assigned capsule. Do
  not add Kafka, CDC, a workflow engine or universal event sourcing.
- **Verification:** Future monitoring persistence must prove event and alert
  atomicity, lost-wakeup polling, duplicate delivery idempotence, restart and
  owner-scoped replay on the real supported database path. Existing tests were
  inspected, not rerun by this read-only packet.
- **Migration and rollback:** No migration for this finding. Any monitoring
  tables remain owned by the separately planned expand-contract migration. A
  rollback must retain durable source facts and use forward repair for produced
  rows rather than delete evidence.
- **Release owner:** `strategy-os-v0-monitoring-persistence` and the later
  `strategy-os-v0-security-operations-deployability` gate.
- **Disposition:** Keep and verify. No infrastructure adoption.

## KCA-003: monitoring alerts must not reuse execution signal facts

- **Source and exact location:** *Online Event Processing*, pages 7-10 and
  14-18; *Making Sense of Stream Processing*, pages 177-178. Ordered source
  facts can feed several projections, but failed delivery and stale subscribers
  do not change the source fact.
- **Assumptions:** Monitoring has no V0 execution authority. Signal validity,
  delivery outcome and user attention are distinct facts.
- **Strategy OS failure hypothesis:** Reusing an execution-bound signal row for
  an alert can invent broker/deployment meaning, while allowing delivery or read
  state to mutate the signal can erase evidence or make retries ambiguous.
- **Repository evidence:** The legacy `SignalEvent` in
  `paper-trader/backend/app/db/models.py:2234-2258` requires a broker account and
  deployment. The additive contract in
  `paper-trader/backend/app/monitoring/contracts.py:313-344` defines a separate
  content-addressed `MonitoringSignalEvent`; lines 711-750 derive or refuse an
  alert from exact validity, freshness, state and protection facts.
  `paper-trader/backend/tests/test_v0_signal_alert_attention_contract.py:422-451`
  asserts that delivery failure does not mutate the alert and conflicting reuse
  of an attempt identity refuses.
- **Classification:** Contract seam present and aligned with the later owner
  direction. Persistence, runtime, API and UI acceptance remain separate.
- **Smallest safe response:** Preserve the distinct contract and consume it in
  the already assigned monitoring queue. Do not alias `SignalEvent`, and do not
  make an in-app delivery receipt the alert source of truth.
- **Verification:** The persistence owner must prove one idempotent alert per
  monitoring event, immutable alert bytes across delivery failures, append-only
  attention events, deterministic projection rebuild and owner isolation.
- **Migration and rollback:** The planned monitoring migration must be additive,
  retain legacy `signal_events`, support mixed-version readers, and specify
  downgrade or forward repair after new facts exist. This capsule makes no
  migration claim.
- **Release owner:** `strategy-os-v0-monitoring-persistence`, followed by its
  runtime, API, frontend and release-review owners.
- **Disposition:** Keep the existing plan. Findings do not advance its stage.

## KCA-004: executable graph conflicts need semantic refusal

- **Source and exact location:** *Local-First Software*, pages 4-5, 9, 14-15
  and 22. The figures show manual conflict copies and text-oriented merge tools;
  the paper says some concurrent values still need application/user handling.
- **Assumptions:** A Strategy OS graph can change executable identity. Layout
  state and executable nodes, edges and parameters have different semantics.
- **Strategy OS failure hypothesis:** Silent last-write-wins can discard a user
  edit or publish an executable strategy that neither editor reviewed. Structural
  convergence alone cannot prove trading semantics.
- **Repository evidence:** `paper-trader/backend/app/editor/graph_artifacts.py:
  405-440` requires the caller's `base_revision` and repeats the predicate in an
  atomic update, raising `GraphConflict` for a stale draft. Published versions
  are immutable and content addressed. `paper-trader/backend/tests/test_ir_edit.py:
  147-164` proves presentation layout does not enter graph or cache identity.
- **Classification:** Already correct V0 seam, with a V2 future-collaboration
  question. No current need for CRDT collaboration was established.
- **Smallest safe response:** Keep optimistic concurrency, immutable versions
  and separate presentation state. If collaboration is later authorized, define
  graph-specific conflict rules and revalidate any executable merge.
- **Verification:** Retain stale-revision refusal, concurrent two-session edit
  tests, immutable publication and presentation/executable identity tests. A
  future collaboration model must produce counterexamples before dependency
  adoption.
- **Migration and rollback:** None for V0. A future collaboration migration must
  be additive and preserve every immutable graph/version and conflict receipt.
- **Release owner:** V0 graph/research owner for current refusal; V2 workflow and
  collaboration owner for any multi-user merge.
- **Disposition:** Preserve the seam. Reject CRDT adoption in V0.

## KCA-009: Redlock does not change the local database fence decision

- **Source and exact location:** Kleppmann's 2016 locking article, the linked
  counteranalysis at `antirez.com/news/101`, and current Redis distributed-lock
  documentation sections “Safety and Liveness Guarantees,” “The Redlock
  Algorithm” and “Analysis of Redlock.” Current Redis guidance calls out fencing
  tokens and wall-clock shifts for correctness-sensitive use.
- **Assumptions:** The reviewed Strategy OS claimant writes back to the same
  authoritative database row using exact owner, run and random token equality.
  It is not trying to fence an independent object store or broker.
- **Strategy OS failure hypothesis:** A stale claimant may resume after takeover.
  If the protected database update omits the current token predicate, it can
  overwrite later state.
- **Repository evidence:** The prior [job-claim packet](job-claim-fencing.md)
  maps `_active_claim`, batch and terminal writers and records a killed token
  mutation. The exact-token database predicate protects this boundary without a
  Redis lease service.
- **Classification:** Already correct for the inspected sink. The sources
  disagree about Redlock's broader guarantees but share the need to state the
  failure model and protect correctness at the effect boundary.
- **Smallest safe response:** Keep the database predicate. Require a separate
  design for any future external side effect that cannot check the token.
- **Verification:** Preserve the stale-claim mutation and exact-engine contention
  tests. Add broker/object-store tests only if such effects enter this claimant's
  scope.
- **Migration and rollback:** None. No Redis, lock service or token-sequence
  migration is justified.
- **Release owner:** `strategy-os-v0-canonical-research-spine` for the job sink;
  the exact future side-effect owner for any new boundary.
- **Disposition:** Keep. Reject Redlock adoption and universal monotonic-token
  requirements for a sink that already performs exact conditional equality.

## Unavailable and deferred evidence

The V3 Kleppmann prompt and standalone simplicity directive remain unavailable
and were not read. The owner explicitly accepted the V2 prompt, V4 brief,
Professional Engineering Reference Programme and V0-V6 reconciliation as the
controlling composite for this run.

The official O'Reilly second-edition page was visible through indexed publisher
content but returned HTTP 403 to the shell capture. No full book copy was supplied
or searched outside the project workspace. The book text is not claimed read.
The exact public companion references are reviewed separately in the
[DDIA 2e delta](../12-DDIA-2E-DELTA-FOR-STRATEGY-OS.md).
