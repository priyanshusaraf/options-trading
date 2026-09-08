# Kleppmann re-audit handoff for Chat 2

## 1. Baseline and posture

- Repository/worktree: `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation`
- Branch: `codex/execution-foundation`
- HEAD at audit start: `de6faae3e97cf5537338bee2143350e53f70da1c`
- Worktree at audit start: 244 tracked changed entries and 583 untracked entries. All inherited work was preserved.
- Production posture: read-only. Writes are limited to this V5 research directory, the two engineering registries, and ignored `.agent/runs/kleppmann-reaudit-v5/` evidence.
- V0 negative authority: execution worker, live provider/connection/account assignments, and execution WebSockets are denied. No live broker/provider, credentials, VPS, deployment, migration, backup, restore or external infrastructure was used.

## 2. Prior-research verdict

The old review is a useful bounded intake, not a complete corpus audit.

- Prior manifest: 373 items; 7 recorded fully read; 366 not read; 349 unscreened; no video/transcript reviewed.
- Four PDFs were inspected page-by-page and remain valuable.
- Metadata was weak: 22 missing titles, 235 missing authors, 115 missing dates, 344 missing page counts, 109 unverified licences, and transcript status unknown for all 373.
- Of 29 prior claims, three authority claims had no citation; 13 lacked system assumptions and repository failure hypotheses; none had an explicit inference field.
- Deterministic 20-claim sample: 8 retained, 3 misapplied, 4 source-does-not-say-this, 2 require fresh tests, and 3 are stale because the repository changed.
- Core defect: source claim, Codex inference and Strategy OS recommendation were often merged. Detailed DDIA second-edition claims exceeded the public publisher contents; the book text was unavailable.

Retain the four inspected PDFs, bounded first-party inventory, and exact useful source captures. Discard unsupported recommendation force and all “full corpus” implications.

## 3. Fresh corpus coverage

The fresh responsible crawl started from first-party website/navigation/archive/talk/course roots and direct high-value artifacts.

- 2,848 discovered URLs: 373 first-party content pages, 2,016 external links, 459 assets.
- 368 first-party URLs fetched, 4 archive downloads deferred, 1 honest 404, 0 pending.
- Fresh URL set, status, final URL and content hashes exactly matched the prior crawl. `/sitemap.xml` returned 404; navigation/archive pages supplied the inventory.
- V5 manifest: 375 unique rows = 373 first-party pages plus the Cambridge PDF and official O’Reilly contents page.
- Review status: 25 reviewed beyond inventory, 350 `INVENTORIED_ONLY`.
- Reviewed set: 5 full text, 4 selected pages/figures, 3 root inventories, 3 full text with figures pending, and 10 other explicit reviewed variants recorded in the manifest.
- Availability: 367 fetched/public-fetched, 4 deferred archives, 1 fetch error/404, 1 video page with video unreviewed, 1 author page with book text unavailable, 1 official contents page with book gated.
- Four central PDFs matched earlier hashes: Cambridge notes, *Making Sense of Stream Processing*, *Online Event Processing*, and *Local-First Software*.
- Four HTML diagrams were directly inspected: dual-write reordering, partial failure, ordered log consumers, and CDC topology.

Coverage is broad inventory plus risk-driven Tier A review, not full-text review of all 375 items. Videos, most talks, archives, DDIA book chapters, and 350 inventory-only items remain unreviewed.

## 4. Top 20 sources for Strategy OS

| Rank | Source | What it safely supports | Limit |
|---|---|---|---|
| 1 | `KLEPPMANN_LOGS_2015_V5` — *Using logs to build a solid data infrastructure* | Dual-write failure, ordered change, CDC, rebuildable consumers | Kafka/Samza prescriptions are dated and not adopted. |
| 2 | `CAMBRIDGE_DISTSYS_2022` — Cambridge Distributed Systems notes | Clocks, replication, transactions, consensus, stream processing and failure models | Course notes, not Strategy OS architecture authority. |
| 3 | `KLEPPMANN_STREAM_PROCESSING_2016` | Event time, windows, replay, state, exactly/at-least-once discussion | Selected system examples are dated. |
| 4 | `KLEPPMANN_OLEP_2019` | Online event processing, durable input/state/view distinctions | Does not prove current runtime readiness. |
| 5 | `KLEPPMANN_EVENT_ORDER_2018_V5` | Entity-scoped ordering, timestamp insufficiency, compound event provenance | Does not imply Kafka. |
| 6 | `KLEPPMANN_ISABELLE_2022_V5` | Loss/duplication/reordering/crash model and invariant thinking | Video unreviewed; no proof-assistant adoption. |
| 7 | `HERMITAGE_F029BEC8` / manifest Hermitage page | Concrete isolation anomalies and test vocabulary | Database/dialect-specific behaviors require direct tests. |
| 8 | manifest `KPV5-B7E13681B8FA502E` — *How to do distributed locking* plus `REDLOCK_COUNTERANALYSIS_2016_CURRENT` | Lease/clock/fencing cautions | No Redis adoption. |
| 9 | `KLEPPMANN_DB_INSIDE_OUT_2015_V5` | Immutable facts, indexes/materialized views, rebuild and subscriptions | Samza architecture is not copied. |
| 10 | `KLEPPMANN_CACHE_2012_V5` | Explicit data dependencies and rebuildable cache outputs | Hadoop/Storm examples rejected. |
| 11 | `KLEPPMANN_SCHEMA_EVOLUTION_2012_V5` | Writer/reader compatibility and stable field identity | Dated library specifics. |
| 12 | `KLEPPMANN_HASHCODE_2012_V5` | Stable cross-process serialization/hash requirement | Java detail is illustrative only. |
| 13 | `KLEPPMANN_CP_AP_2015_V5` | Operation-specific consistency guarantees | Avoids product-wide labels. |
| 14 | `KLEPPMANN_SCALING_2014_V5` | Stateful scaling and realistic operational/load evidence | Retrospective, not a capacity plan. |
| 15 | manifest `KPV5-63893DC6A408F088` — *Accounting for Computer Scientists* | Ledger/accounting mental model | Figures pending; financial-domain rules need separate sources. |
| 16 | `KLEPPMANN_LOCAL_FIRST_2019` | Ownership/availability/synchronization distinction | Local-first architecture is not applicable to server authority. |
| 17 | `DDIA2_OFFICIAL_TOC_2026` | Public topic delta for the second edition | Contents cannot support chapter-detail claims. |
| 18 | `DDIA2_REFERENCES_1752CBD0` | Literature inventory for broader follow-up | Inventory is not completed review. |
| 19 | manifest `KPV5-C1BC45C21A78F191` — Hermitage article/figure | Transaction isolation test method | No blanket serializable recommendation. |
| 20 | manifest `KPV5-5CB834EF4EC9795B` — AI/formal-verification prediction | A speculative research direction only | Not evidence for product adoption or schedule. |

## 5. Source-supported principles without implementation leap

1. Persist one authoritative fact/intent before deriving views or performing recoverable work.
2. Treat timeout as uncertainty after an external side effect, not proof of failure.
3. Name idempotency and ordering at the entity/operation boundary; timestamps alone do not establish completeness.
4. Separate durable source of truth from cache, runtime state and realtime presentation.
5. Bind exact answer-changing inputs before hashing, caching, restarting or claiming reproducibility.
6. Model event/completion/availability/recorded/correction times separately where the data source supports them.
7. Use database transactions/fencing for money and claim predicates; use weaker bounded delivery for UI projections.
8. Make state rebuildable from addressed durable inputs or block with explicit degraded state.
9. Add coordination only where a named invariant requires it.
10. Prefer direct failure tests over prestige-driven distributed infrastructure.

## 6. Top confirmed or likely backend failures

| Order | Finding | Release | Evidence |
|---|---|---|---|
| 1 | KPV5-A-002: full-history qualification contaminates later OOS | V0 blocker for locked/untouched OOS claims | Direct RED row-span probe |
| 2 | KPV5-A-003: legacy sweep route is reachable in V0 | V0 blocker | Direct RED release-policy probe |
| 3 | KPV5-B-001/F03: canonical graph experiment omits ResourcePlan | V0 blocker, existing named owner | Direct RED structural characterization |
| 4 | KPV5-A-004: completed observations accept `available_at < completed_at` | V0 provider-capture blocker; current Q03 contained | Constructor characterization/static reachability |
| 5 | KPV5-A-001: truncated experiment-spec ID reuses without byte comparison | V0 hardening | Forced collision RED |
| 6 | KPV5-B-002: cancel/complete sequence yields cancelled full fill | V1 execution | Direct reducer RED |
| 7 | KPV5-A-007: exact optimization/search-stat reconstruction under-proved | V0 evidence hardening | Persistence/code matrix |
| 8 | KPV5-A-005: IID bootstrap assumption unstated/untested | V0 evidence label | Static method audit; statistical source pending |
| 9 | KPV5-B-003: current SQLite claim-race validation times out; PostgreSQL also unproved | Release/deployability evidence | Isolated 45-second timeout |
| 10 | KPV5-B-005: connected WebSocket revocation unspecified | V1 execution/security | Static code; V0 route denied |

Two inherited current-tree gates require the active capsule: `tests/test_live_entry_durability.py::test_paper_entry_remains_unlinked` fails alone because dirty `app/engine/broker.py` now creates a paper intent, and the first backtest claim-race test times out after 45 seconds. These are current validation failures, not yet localized Kleppmann findings. Reconcile intent and concurrency changes before changing tests or claiming the suites pass.

## 7. First tests/probes for Chat 2

Run in this order:

1. OOS suffix mutation and sealed selection-boundary tests.
2. V0 legacy route refusal before provider/queue/repository dispatch.
3. Existing nine F03 consumers plus exact ResourcePlan bridge/result identity.
4. Isolated reconciliation of the inherited paper-entry lifecycle test against its active capsule.
5. Forced full-address/spec-byte collision test.
6. Same-build and post-restart optimization reconstruction.
7. PostgreSQL two-process claim/takeover/process-kill suite.
8. Execution reducer property/state-machine tests before any V1 broker work.

The complete ordered backlog is `11-CHARACTERIZATION-AND-RED-TEST-BACKLOG.md`.

## 8. Questions requiring broader sources

- Which dependence-aware resampling method and label fit Strategy OS trade sequences? Use primary statistical literature, not Kleppmann.
- What exact broker tag/order-history guarantees and retention does each execution provider expose? Use provider docs and conformance probes.
- Which isolation level and retry semantics does deployed PostgreSQL require for each money/claim predicate? Use PostgreSQL primary docs plus direct two-process tests.
- What WebSocket/session revocation bound does the product require? Owner/security decision plus ASVS guidance.
- What backup/PITR/RPO/RTO targets are required? Owner operations decision plus deployment evidence.
- What corporate-action, derivative-history, fundamental/event and data-rights contracts are licensed? Owner/provider/legal decision.
- What P0/P1 latency/capacity target is acceptable for future execution? Owner risk and resource plan, then measurement.

## 9. Implementation candidates ordered by evidence and reachability

1. **V0:** stop calling contaminated output locked/untouched OOS; seal boundaries or label exploratory.
2. **V0:** deny the legacy sweep under V0 before provider access.
3. **V0 existing F03:** bind the exact canonical ResourcePlan at published graph execution and evidence.
4. **V0 hardening:** collision-safe full experiment identity with stored canonical-byte comparison.
5. **V0 evidence:** prove exact optimization reconstruction and method identity before schema additions.
6. **Provider capture only:** enforce completed/availability ordering after producer inventory.
7. **V1 execution:** specify and implement terminal observation conflict semantics from raw immutable events.
8. **V1 release:** PostgreSQL contention/takeover, unknown-submit, capital recovery, session revocation and P0/P1 measurements.

These candidates are proposals for the relevant named capsules. Chat 1 did not authorize implementation.

## 10. Rejected or deferred patterns

- Kafka, Redis, Celery, a workflow engine, distributed consensus service, a second IR/resource plan, and a new cache abstraction are rejected now.
- Formal proof tooling, local-first architecture and event sourcing as a repository-wide rewrite are deferred/rejected as prescriptions.
- Dynamic Watchlists, Workflows, multi-leg economic positions, marketplace/managed strategies, live incremental execution and broader provider data are future seams, not V0 work.

## 11. Remaining limitations

- 350 corpus items remain inventory-only; most talks/videos/transcripts and four archive downloads are unreviewed.
- DDIA second-edition text is gated/unavailable; only author and official contents pages were reviewed.
- V3 prompt and the separately named simplicity directive were not found in the repository, canonical checkout or Downloads; their substance is present in the supplied V5 prompt but their exact bytes remain unavailable.
- PostgreSQL, Docker, provider networks, broker semantics, backup/restore, deployment, capacity and live behavior were unavailable.
- Worktree bytes are inherited and changing under other tasks; this handoff identifies the exact audit baseline and preserves later external changes.

## 12. Registries and evidence

- Source registry: 68 total entries. Twenty-nine pre-existing catalogue entries remain explicitly `registered_not_reviewed`; the V5 additions record seven full-text reviews, one full-text-plus-selected-figures review, one full-article/code-snippet review, and two direct audit evidence bundles. Other reviewed legacy references retain their own exact statuses.
- Claim registry: 43 total claims, including 14 V5 claims. Five V5 claims have direct expected-RED evidence; the remaining nine are explicitly characterized as contained, unverified, future-only, capacity/test gaps, or already-correct patterns.
- Corpus manifest: `01-KLEPPMANN-CORPUS-MANIFEST.csv`
- Review overlay: `01-KLEPPMANN-CORPUS-REVIEW-OVERRIDES.json`
- Source registry: `docs/engineering-references/source-registry.yaml`
- Claim registry: `docs/engineering-references/claim-registry.jsonl`
- Fresh crawl/cache/diff/PDF/figure evidence: `.agent/runs/kleppmann-reaudit-v5/fresh-corpus/`
- Pass A evidence: `.agent/runs/kleppmann-reaudit-v5/pass-a/`
- Pass B evidence: `.agent/runs/kleppmann-reaudit-v5/pass-b-runtime/`
- Independent read-only shadow receipts: `.agent/runs/ultra-backend-v5-chat1/`
