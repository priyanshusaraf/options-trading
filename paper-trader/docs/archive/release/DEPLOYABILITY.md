# Strategy OS deployability ledger

Updated: 2026-08-18. This is a cross-phase gate, not a claim that production is ready or deployed. Every architecture, implementation, correction, phase review, and release review must update affected rows or cite unchanged evidence.

The session-data accuracy capsule is active after independent nine-component/19-output assurance PASS. It is a compatible, unpublished research-only analytical contributor with no SQL migration, service, dependency, provider, execution, live, order, money or deployment change. The Q01 additive 0043 auth migration remains under its own union correction and same-reviewer recheck; Q03 remains under one critical review. Local numerical evidence cannot establish release deployability.

The IR v2 implementation-closure correction affects local Application, CPU, Memory, Research runtime, and Admission identity only. It introduces no migration, schema, provider, broker, deployment, credential, or live-authority change. Focused local evidence is `.agent/runs/phase3-4-ir-v2-implementation-closure-correction/owner_integration/focused-final.log`; it does not alter any rejected release or production verdict below.

The accepted Phase 4 architecture artifacts change documentation and programme routing only. They do not change runtime, schema, configuration, dependencies, services, providers, infrastructure, or deployment state. The implementation capsules below own each prospective deployment consequence; architecture validation cannot prove any implementation or release claim.

The accepted `phase4-research-receipt-authority-architecture-correction` is documentation-only. Its planned implementation is `schema-free-phase4-research-receipt-authority-hardening`: the existing execution loader chain must invoke the existing research receipt-and-graph verifier before dataset/assessment verification and the unchanged terminal refusal. It changes no schema, migration head, dependency, configuration, service, provider, frontend, infrastructure, deployment artifact, runtime availability, production state, live authority, or money authority. SQLite and disposable PostgreSQL 16 evidence can restore only the named local verifier-composition and consumer-containment claims.

The accepted `phase4-authority-transaction-architecture-correction` is
`documentation-only-phase4-authority-transaction-architecture`. Its planned
implementation is `schema-free-phase4-authority-transaction-hardening`: one
shared caller-owned savepoint boundary in existing application code and direct
adoption at seven existing persistence seams. It changes no schema, migration
head, dependency, configuration, service, provider, frontend, infrastructure,
deployment artifact, production state, live authority, money authority, or
ledger business rule. SQLite compatibility and disposable PostgreSQL 16
transaction evidence can restore only the named local atomicity contracts.

The bounded `phase4-review-correction` is classified `compatible-application-and-research-identity-hardening-no-schema-or-service-change`. It hardens application validation and immutable market-truth facts, and carries a freshly verified Phase 4 receipt binding through the existing backtest request, reclaim, worker, result-address, and owner-local cache seams. It adds no schema, migration, service, dependency, configuration, provider, broker, credential, infrastructure, frontend, production, deployment, or live-authority change. Focused local evidence cannot change the rejected release or production verdict below.

The active `phase4-loader-authority-recovery-correction` is classified `schema-free-phase4-loader-authority-enforcement`. It adds no schema, migration, dependency, configuration, service, provider, frontend, runtime enablement, deployment, credential, production, live, or money change. Its only runtime-boundary correction requires explicit research-session, plan, and aware cutoff context at the existing execution loader, which then invokes the existing complete verifier before its unchanged `V2_RUNTIME_UNAVAILABLE` terminal refusal. Contextless consumers remain fail closed. Current SQLite and the existing isolated PostgreSQL two-plane lifecycle are local verification only; release deployability, production rehearsal, and deployment remain rejected or unauthorized.

The correction's current-byte closure uses explicit authority context only in focused tests and the existing two-plane integration lifecycle. Production deployment, runner, broker, enqueue, retry, reclaim, pinned-worker, cache, and job callers do not infer or open that context; they refuse before provider, cache, job, evaluation, activation, order, or money side effects. Separate consumer regressions, restored mutation evidence, and exact source/test hashes revalidate this local containment boundary. They do not make Phase 4 operational or change the verdicts below. No deploy command ran.

The `phase4-v2-durable-graph-integration` correction is classified `additive-execution-and-research-schema-with-fail-closed-v2-runtime`. It advances local execution and research heads to `0037` and `0008`, adds immutable owner-scoped v2 graph-version records, persists complete receipt and assessment authority atomically, and makes verified v2 loads stop at stable `V2_RUNTIME_UNAVAILABLE`. It adds no service, dependency, configuration, provider, broker, credential, infrastructure, frontend, production, deployment, or live-money authority. SQLite and disposable PostgreSQL 16 evidence can prove only the named local gates.

The `phase4-capability-assessment-receipt-correction` is classified
`schema-free-application-receipt-identity-hardening`. It makes receipt creation,
both persistence writers, and reconstruction use one exact closed
`capability-assessment/2` authority envelope from canonical bytes. It adds no
schema, migration, dependency, configuration, service, provider, broker,
credential, infrastructure, frontend, runtime enablement, deployment,
production, live, or money-authority change. Old or incomplete local receipts
refuse closed and require explicit recreation; there is no migration or legacy
identity fallback. Local SQLite and fresh-interpreter evidence cannot change
the rejected release or unproved production verdict below.

The `phase4-authority-timestamp-normalization-correction` is classified
`schema-free-cross-database-authority-timestamp-hardening`. It gives all named
Phase 4 copied timestamp columns and alias interval predicates one explicit
UTC-naive SQL representation while leaving canonical aware UTC documents and
content addresses unchanged. Focused SQLite and disposable PostgreSQL 16
evidence under `Asia/Kolkata` proves only this local compatibility contract. It
adds no schema, migration, dependency, configuration, service, provider,
broker, credential, infrastructure, frontend, runtime enablement, deployment,
production, live, or money-authority change and does not accept Phase 4 or the
full integration gate.

The `phase4-research-json-shape-parity-correction` is classified
`additive-research-schema-json-shape-parity-repair`. It advances only the
research head from accepted immutable `0009` to forward-only `0010`, replacing
an ambiguous cross-dialect helper with explicit object and array constraints at
all eight use sites. Focused SQLite and disposable PostgreSQL 16 evidence proves
the named fresh-install, exact-upgrade, interruption/restart, byte/row/contract
preservation, typed-manifest lifecycle, and drift-refusal gates locally. It is
not a production rehearsal, does not authorize deployment, and changes no
execution schema, service, dependency, configuration, provider, credential,
frontend, runtime, live, or money authority.

## Current verdict

- `locally_runnable`: **PROVEN** for the named local PostgreSQL 16-backed execution, research, concurrency, schema, outbox, admission, and restore contracts through the disposable harness.
- `release_deployable`: **REJECTED / OPEN**.
- `production_rehearsed`: **UNPROVEN**.
- `deployed`: **NOT AUTHORIZED** for the current dirty tree.

The current `deploy.sh` correctly rejects a dirty tree. Nothing in this ledger grants VPS, credential, production-data, live-provider, destructive, or deployment authority.

## Proven foundations

- PostgreSQL 16, psycopg 3, three explicit execution/research/ledger authorities, production refusal of SQLite, schema-head validation, immutable constraints, concurrency leases, and a live logical dump/clean-restore test exist.
- `backend/scripts/run_disposable_postgres.py` provisions a unique loopback-only PostgreSQL 16 cluster, passes an explicit Psycopg 3 URL only to its child, rejects inherited PostgreSQL connection state, preserves the child exit code, and tears the cluster down on success, failure, interruption, and startup failure. Evidence is recorded in `.agent/runs/post-phase3-postgresql-harness/`.
- CI runs PostgreSQL 16 contracts, backend and research suites, deterministic smoke work, frontend tests, type checking, and a production frontend build.
- The sanctioned deploy script guards market hours, a clean exact-head tree, test count, ledger reconciliation, frontend artifacts, remote `.env`, dependency importability, service restart, readiness, frontend response, and running build identity.
- Cutover and backup/restore runbooks require frozen sources, fresh targets, content-addressed reports, signed manifests, schema/table/digest/sequence checks, quarantine on partial failure, and explicit rollback.

## Open obligations

### Research receipt authority correction

`phase4-research-receipt-authority-correction` is
`schema-free-phase4-research-receipt-authority-hardening`. It changes only the
existing Phase 4 loader's required research-plane admission invocation and
current-byte tests. It adds no schema, migration, dependency, configuration,
service, provider, broker, deployment, runtime enablement, frontend, credential,
production, live, or money behavior. Execution migration head remains `0039`;
research migration provenance is unchanged and is not advanced by this slice.
SQLite and disposable PostgreSQL 16 are evidence environments only. No deploy,
release claim, production rehearsal, or runtime authorization follows from this
correction. The deployment, frontend, live, and money gates remain blocked for
final-review-5.

### Foundation migration and numeric direct closure

Owner direction SHA-256
`eb66946c5f7a8807ab116883b9847e337122dd3ebf6e118de2bf7d45d3322d01`
removes the recursive evidence-engine route from the active gate. Its files and
historical verdicts remain immutable and unaccepted. The current executable
capsule is `phase1-4-foundation-direct-closure`.

The deployment impact is `migration-required`. Research head advances from
`0010` to `0011`. SQLite supports clean installation, the exact frozen `0010`
catalog including its enumerated guard-only restart states, and exact `0011`.
PostgreSQL 16 supports clean installation, exact frozen `0010`, and exact
`0011`. Unversioned populated, `0001` through `0009`, unknown, future,
downgraded, corrupted, partial, drifted, and hybrid states refuse before
durable writes. The operator preserves a verified backup and uses a read-only
diagnostic/export or a clean rebuild. Marker rewrites, automatic arbitrary
repair, and downgrade support remain forbidden.

Direct SQLite and disposable PostgreSQL 16 evidence exercises two materially
different populated corpora per dialect, all 24 durable tables, rows, keys,
owners, sequence state, textual JSON, Unicode, binary values, canonical stored
bytes, every required SQL guard, interruption rollback, deterministic restart,
and exact-current idempotence. SQLite deliberately uses
`(version, schema_cookie)`; PostgreSQL deliberately uses a transactionally
validated version-only marker.

The numeric correction is schema-free and otherwise deployment-compatible.
One shared pre-coercion rule rejects Python and installed NumPy boolean scalars
before assigned OHLCV values can create dataset, cache, signal, sizing, or
executable-price authority. Valid finite behavior, encoded bytes, addresses,
and causal next-bar behavior must remain unchanged.

The first independent review package, SHA-256
`bb003c995679941e0d6202f9a0d120d9a5879a715c7fb3b2659477b81678dbb3`,
returned `SPEC FAIL` and `QUALITY FAIL`. It found one missed research dataset
numeric ingress and one partial PostgreSQL catalog inventory, plus fixture-label
and evidence-currentness gaps. One bounded correction closed those findings.
The same reviewer then returned `SPEC PASS` and `QUALITY PASS` against refreshed
package SHA-256
`0e67dfcebb0b85161efa34501a8a3a6a953c4bed5a9e66bc93b2ffe481a56cfc`.
Recheck verdict SHA-256 is
`d43994cc2d4d1d6e9b827a0f6169a1a75128b24d862e3ac3461ded7fca153069`.
The finite local foundation gate is accepted and Phase 5 architecture may
start; the release and production gates below remain unchanged.

This evidence establishes only `locally_runnable` migration behavior and local
numeric compatibility. It does not establish release deployability, a
production rehearsal, production-data upgrade safety, backup retention,
restore, cutover, rollback, topology, roles, health, capacity, security,
observability, deployment, provider, frontend, live, order, or money readiness.
Those obligations retain their exact Phase 6 and V1 release owners.

### Foundation blockers

1. The tracked VPS plan and service topology still describe the older single-process SQLite system. They do not define the current three-plane PostgreSQL runtime or its API, worker, scheduler, research, and ledger responsibilities.
2. `deploy.sh` does not preflight `PT_PRODUCTION=1`, all three PostgreSQL URLs, PostgreSQL major/driver, all three schema heads, backup freshness, restore readiness, database roles/TLS, or an accepted cutover report before restart.
3. Public readiness probes only the execution database. Execution schema drift is descriptive rather than fatal, and research/ledger reachability and heads are absent from the verdict.
4. The production systemd unit and database backup schedule are remote-only artifacts. The tracked deployment plan still installs an SQLite backup job.
5. PostgreSQL logical backup code exists, but scheduled encrypted/off-host retention, restore rehearsal, alerting on backup age, managed PITR, and measured RPO/RTO remain unproven.

### Reproducibility and operations blockers

6. Python dependencies are lower-bounded rather than locked; the remote deploy performs a mutable `pip install -r requirements.txt`.
7. Compose is a development substrate: one credential, no TLS/role matrix, no production network policy, no resource limits, and no production service topology.
8. CI does not run `scripts/test_deploy_guards.sh` or a complete production-shaped clean install, upgrade, restart, rollback, and three-plane health rehearsal.
9. Database capacity, connection budgets, WAL/disk growth, queue/lease saturation, log retention, metrics, alerts, and failure drills are not yet accepted for the final topology.
10. Final independent architecture checking finds four unresolved Phase 4 authority collapses: DatasetManifest is not canonically loaded/proved at admission; canonical instruments and economic underliers remain labels or opaque JSON; provider observations and normalized observations lack separate durable identity; and market-truth/capability rows preserve hashes without typed reconstruction or copied-field reconciliation. These Critical findings block Phase 4 integration and final-review readiness.
11. The checker also finds that resolved-graph identity omits execution-relevant topology, a High IR architecture gate before Phase 5 execution or cache authority. A separate High schema finding routes 71-character canonical content addresses into 64-character strategy-version fields; PostgreSQL graph-to-paper execution and deployment remain blocked until that version/address contract is separated and migrated.
12. CUR-H2, CUR-C2/C3/H1, CUR-C4, and CUR-C1 have bounded local acceptance. Execution head `0039` and research head `0009` now carry the nine role-specific dataset-dependency authorities and typed segments/manifests at SQLite compatibility and separate disposable PostgreSQL 16 evidence scope. The accepted construction graph is manifest first without an assessment address, assessment second with the final manifest address, then admission/cache with both; cyclic, incomplete, generic-dispatch, and optional-resolver variants refuse. The stopped authority-integration receipt counterexample is corrected locally with one exact typed assessment envelope, but the evidence-only `phase4-authority-integration-gate` still must be reactivated and rerun before an official review package can be built.
13. CUR-H3 forbids graph-to-paper execution, v2 claim/reclaim, graph-address cache authority, deployment binding, and money records until `phase5-graph-paper-attribution-schema` separates full graph addresses from strategy versions. That schema is necessary but non-enabling. Phase 5 architecture must also generate one exclusive `P5-ADV-006-RUNTIME` capsule, dependent on accepted schema, and that capsule must prove claim, ownership loss, public-seam reclaim after process death, exact current-authority reload, stale-claimant fencing, and current-claimant-only exactly-once finalization on direct SQLite and disposable PostgreSQL 16 before any v2 claim/reclaim or downstream worker/result/cache/broker/order/money consumer becomes reachable. CUR-H4 forbids generated-strategy replay, promotion, current-slot replacement as evidence, paper/live assignment, activation, deployment, and release evidence until `phase6-generated-strategy-version-lineage` proves immutable versions.
14. ADV-003 proved that SQLAlchemy logical transaction state did not guarantee a DBAPI outer transaction on SQLite before a first savepoint. Execution/research admission, research dataset authority, fenced backtest batch, terminal run/outbox, public computation cache, and ledger snapshot/outbox atomicity evidence is stale until the schema-free transaction correction proves all seven seams on current SQLite and disposable PostgreSQL 16 bytes. The full 27-row matrix and official review package must then be regenerated; no local correction changes release deployability.
15. `phase4-final-review-4` is an immutable SPEC/QUALITY FAIL. The actual execution loader reached `V2_RUNTIME_UNAVAILABLE` without requiring the research receipt or immutable research graph, and the decisive integration checked both only after loader return. Loader, consumer, integration, adversarial, package, and review-readiness evidence that depended on complete loader enforcement is stale until the schema-free correction proves the sole verifier chain and rebuilds the official package. No local correction changes release deployability.
16. Foundation direct closure is accepted at its reviewed local boundary after the bounded correction closed research-dataset boolean authority and complete PostgreSQL current-schema validation. This PASS does not establish production-shaped backup, restore, topology, roles, cutover, rollback, health, exact-build smoke, release deployability, production rehearsal, or deployment.
17. SQLite history recovery resolves the architecture only by refusing
unversioned and `0001` through `0009` before writes and supporting empty, exact
or enumerated-five-guard `0010`, and exact `0011`. Downstream implementation
remains blocked until root accepts the exact recovery package. The bounded
repository audit found no affirmative released, deployed, production,
supported-database, customer, or external-promise SQLite state; it establishes
no fact outside the checkout. Contrary affirmative evidence activates a root
and user gate before support narrows. Release, deployment, and production
claims remain closed.

## Phase 4 ownership

Phase 4 uses exact serial ownership:

- Historical PostgreSQL/SQLite recovery, native-state, obligation, evidence-language, and transitive-review capsules remain immutable, unaccepted inputs outside the active critical path. They grant no migration or deployment credit.
- `phase1-4-foundation-direct-closure` owns the finite migration/numeric product boundary, direct current-byte tests, mutations, restoration, integrated evidence, one bounded correction, and one same-reviewer recheck. It cannot grant release, deployment, production, provider, frontend, live, order, or money authority.

- `phase4-research-receipt-authority-architecture-correction` owns only the schema-free KEEP + HARDEN architecture, DP-008 search, transitive evidence invalidation, deployability classification, and serial route after immutable final-review-4 FAIL.
- `phase4-research-receipt-authority-correction` owns the two existing application seams, exact affected tests, SQLite and disposable PostgreSQL 16 verifier-order evidence, killed/restored guards, transitive consumer reruns, and official package rebuild after byte freeze. It owns no schema, migration, provider, frontend, service, deployment, runtime enablement, live, or money behavior.
- `phase4-final-review-5` is a fresh read-only independent review blocked on root-accepted correction and exact package. It has zero repair authority and is the only stage that may assess the corrected review boundary.

- `phase4-numeric-validity-contract` owns application, registry, and serialization compatibility for the closed validity contract. It owns no schema or service claim.
- `phase4-market-truth-domain` owns canonicalization, temporal-rule, deterministic-digest, and refusal evidence. Persistence remains closed during that capsule.
- `phase4-market-truth-persistence` owns both additive migration planes, empty install, supported upgrade, exact heads, restart, local backup/clean restore, rollback-path, integrity, deterministic fixture import, owner isolation, and secret-exclusion evidence on SQLite compatibility and disposable PostgreSQL 16.
- `phase4-data-requirement-registry-correction` owns the architecture-changing but schema-free immutable registry closure, registry snapshot, leaf/compound binding, deterministic plan, v1/v2 compatibility, closed refusals, and four critical mutations. It adds no dependency, configuration, service, provider connection, credential, schema, or process; its highest possible claim is focused `locally_runnable` behavior.
- `phase4-data-contract-capability` consumes the accepted plan and owns mode separation, ownership, stale/change-level refusal, registry/plan/assessment admission attribution, compatibility, and bounded-query evidence. It extends the existing sole artifact authority in `backend/app/strategy/admission.py` with the closed Phase 4 wrapper; the execution and research persistence seams store and verify the same complete bytes and do not construct a second authority. It owns no requirement inference, provider connection, schema, or service.
- `phase4-dataset-causality` owns manifest/cache identity, correction invalidation, prefix parity, next-bar compatibility, owner isolation, secret exclusion, and bounded storage-consumer evidence. Capacity remains with Phase 7.
- `phase4-integration-gate` owns the consolidated local deployment-impact matrix and must retain exact Phase 6, 7, 8, 9, and V1 release assignments for every open production obligation.
- `phase4-review` independently rejects any unsupported implementation, deployability, readiness, provider, capacity, or live-authority claim.
- `phase4-review-correction` owns only the eight immutable first-review findings. Its highest possible claim is package-ready focused correction evidence for the separate recheck. It introduced no migration; subsequent durable-graph work advances execution and research heads to `0037` and `0008`. Deployment, production rehearsal, provider behavior, capacity, frontend, entry/exit runtime authority, money, and live authority remain outside this correction.
- `phase4-v2-durable-graph-integration` owns the additive graph-version migrations, atomic graph/receipt writes, persisted assessment reconstruction, exact loader dispatch, legacy-v1 preservation, and post-verification v2 refusal. It does not own the four authority-chain corrections, the resolved-topology identity correction, a v2 runtime, or a review/package transition.
- `phase4-resolved-topology-identity-correction` must close CUR-H2 before any other authority correction. It owns the complete topology address and fresh-process stale-receipt refusal without schema changes.
- `phase4-canonical-market-identity-correction` must close CUR-C2, CUR-C3, and CUR-H1. It owns exact underlier identity, separate provider entity/product/contract facts, raw versus normalized observation provenance, and additive execution migration `0038` on SQLite and PostgreSQL.
- `phase4-typed-market-authority-correction` must close CUR-C4 against `0038`. It owns typed truth, conformance, profile, and assessment reconstruction and copied-column reconciliation; it owns no schema path.
- `phase4-dataset-assessment-authority-correction` is accepted only for CUR-C1. Its 2026-08-18 bounded owner-gate amendment owns nine separate typed dataset-dependency facts and mandatory role-specific loaders, additive execution migration `0039`, research migration `0009`, exact bytes/segments/coverage, admission loading, and result/cache invalidation on SQLite and separate disposable PostgreSQL 16 planes. It adds no generic fact table or dispatcher, marks no legacy row verified, and grants no deployment or production-readiness claim.
- `phase4-capability-assessment-receipt-correction` owns only the stopped receipt-identity counterexample. It freezes the exact typed assessment envelope across receipt creation, both writers, and reconstruction without schema change, migration, fallback identity, runtime enablement, or deployment claim.
- `phase4-authority-timestamp-normalization-correction` owns only the database-neutral UTC-naive representation for the named copied authority timestamps, their loader comparisons, and alias overlap predicates. It preserves canonical bytes and addresses, changes no schema or migration, and leaves the full integration rerun and review verdict to their existing owners.
- `phase4-research-json-shape-parity-correction` owns only the eight explicit research JSON object/array constraints and forward research migration `0010`. Its local SQLite and disposable PostgreSQL 16 evidence cannot satisfy the production-shaped clean install/upgrade/rollback, backup/restore, three-plane health, or exact-head deployment gates retained by Phase 6 and V1 release review.
- `phase4-authority-integration-gate` must be reactivated and must recheck the full invalidation map through real two-plane process death. It cannot patch product or claim review readiness. A later independent critical review owns that verdict.
- `phase4-reclaim-authority-context-architecture-correction` freezes a schema-free local application hardening boundary. Its implementation moves reclaim reconciliation behind one closed candidate-set authority preflight: SQLite uses the existing admission-scoped `BEGIN IMMEDIATE`; PostgreSQL locks the exact candidate rows `FOR UPDATE`; and reconciliation and claim conditionally mutate only explicit classified legacy ids with all predicates preserved, never a broad owner update. It carries the current registry and existing lifespan-owned synchronous research `sessionmaker` explicitly, derives the sole plan inside receipt reconstruction, and keeps complete-current v2 dispatch terminal at `V2_RUNTIME_UNAVAILABLE` before mutation. It adds no dependency, configuration key, service, engine, database, migration, provider, broker, deployment artifact, or release claim. Disabled research opens no hidden session; mixed v1/v2 owner sets refuse without row mutation; pure-v1 direct and startup behavior remain byte/row equivalent. The fresh matrix rerun and final review retain their existing serial ownership.
- `phase4-authority-transaction-architecture-correction` owns the accepted seven-seam classification and one caller-owned SQLite/PostgreSQL savepoint contract. `phase4-authority-transaction-correction` owns the shared helper, direct adoption at every impacted seam, exact real-seam tests and mutations, and transitive current-byte revalidation. The ledger adoption hardens snapshot/outbox atomicity only; it grants or changes no money authority. Both stages are schema-free and cannot claim deployment, production rehearsal, runtime enablement, or release readiness.

No Phase 4 capsule may present local database or scenario evidence as deployment, production rehearsal, release deployability, or live authority.

## Phase 5 ownership

Own reproducible research-worker packaging, dependency locking, queue/cache/artifact storage, bounded concurrency, and production-shaped research runtime evidence. It also owns the v2 component catalogue, output mapping, Strategy adapter, and worker execution required before `V2_RUNTIME_UNAVAILABLE` may be replaced.

Before any runtime-enablement capsule, `phase5-graph-paper-attribution-schema` must close its CUR-H3 schema obligation on SQLite and disposable PostgreSQL 16. Acceptance grants no consumer reachability. Phase 5 architecture must generate one exclusive runtime capsule for `P5-ADV-006-RUNTIME` after the schema and before any v2 claim/reclaim consumer or downstream worker/result/cache/broker/order/money path can become reachable. `phase5-provider-evidence-compatibility` may test fixture mapping into accepted Phase 4 facts after authority integration, but Phase 9 retains credentials, network adapters, real-provider conformance, fallback, and commercial gates.

### P5.1 graph/paper attribution migration

Deployment impact is `migration-required`. Execution head advances from `0039` to
`0040`. The migration adds independent 71-character `graph_address` and explicit
`attribution_state` columns to deployments, execution intents, positions, trades,
and backtest results. It preserves every prior `strategy_version` byte, assigns
`LEGACY_UNVERIFIED` without inference, refuses destructive downgrade, and uses a
verified pre-0040 backup restore or forward repair for rollback.

Correction evidence closes the first implementation review's four local findings.
Fenced result persistence reconstructs one expected artifact per non-empty batch and
matches every distinct submitted source/state tuple, including `NON_GRAPH`; a forged
native-graph downgrade leaves zero result and progress effects. SQLite evidence uses a
five-table, owner/account-scoped, money-bearing 0039 corpus and compares complete rows,
keys, original strategy-version bytes, and next-id state after clean backup restore.
PostgreSQL 16.14 constructs the accepted pre-authority catalogue without 0040 objects,
runs repository migrations 0038 and 0039, seeds the same corpus, interrupts 0040 inside
its DDL transaction, proves exact 0039 rollback, restarts to 0040, then uses PostgreSQL
16.14 `pg_dump` and clean-target `pg_restore` to compare complete rows, sequences, head,
columns, functions, triggers, and constraints. Nineteen killed/restored mutations cover
the required carrier/writer omissions, legacy-entry acceptance, terminal v2 refusal,
source-state downgrade, 64-character guard, and result identity with exact restoration
hashes. The refreshed 71-path phase tier collects 1,022 tests and passes 1,020 with two
ordinary-process PostgreSQL skips; the separate PostgreSQL test passes.

Current evidence is under
`.agent/runs/phase5-graph-paper-attribution-schema/correction-1/`, including
`direct-sqlite-final-pass.log`, `postgres16-final-pass.log`,
`mutations-19-frozen-pass.log`, `backtest-budget-50000-final-pass.log`,
`deployment-consumers-final-pass.log`, `phase-tier-71-path-inventory-pass.log`, and
`phase-tier-1022-final-pass.log`. Failed and stopped iterations remain retained with
their named passing successors.

The highest claim remains `locally_runnable`. This evidence does not establish a
release-deployable artifact, production-data upgrade, retained/encrypted backup,
production restore, maintenance window, cutover, rollback timing, topology, roles,
TLS, health, capacity, deployment, live behavior, order safety, or money readiness.
It enables no v2 claim, reclaim, provider, cache, worker, result, broker, order, or
money consumer. Those gates retain their named later owners.

### P5.2 exclusive v2 lifecycle

Deployment impact is `architecture-changing`; the highest possible capsule claim
is `locally_runnable`.

The existing execution database, five-state `BacktestRun`, claim token, lease,
frozen reclaim predicates, result cell identity, terminal outbox writer, and public
`dispatch_reclaimable` seam remain the sole authorities. No schema, migration,
dependency, configuration, provider, broker, order, money, frontend, or service
definition changes. The generic production and boot call shape has no v2 executor
and retains `V2_RUNTIME_UNAVAILABLE` before the first claim or mutation.

Direct SQLite and disposable PostgreSQL 16 evidence use separate execution and
research databases with a genuine complete Phase 4 authority chain. One real child
process claims and exits through `os._exit`; a second process reclaims after the
actual one-second lease, receives a different token, reconstructs authority through
fresh execution and research Sessions immediately before write, persists one exact
attributed result, and terminalizes once. Fresh processes prove same-token retry is
idempotent and stale/competing tokens refuse without new result or terminal event.
Provider, cache, legacy worker, broker, order, and money paths have direct or static
tripwires.

The first independent review is preserved at
`.agent/runs/phase5-adv-006-runtime/review/verdict.json` and correctly failed the
initial package. The bounded correction enforces the exact unique result count
against `BacktestRun.total`, compares complete durable retry payloads while
excluding only run-local fields, samples a fresh aware cutoff at final authority
reload, and runs stale and competing heartbeat, append, release, completion,
cancellation-completion, and finalization probes in fresh child processes while a
replacement token is still active.

Corrected frozen evidence is under
`.agent/runs/phase5-adv-006-runtime/root-recheck-correction/`. The 60-file dynamic
tier in `phase-tier-correction-final.log` collects 1,225 tests, passes 1,157, and
skips 68. The separate `public-computation-correction.log` passes 19 tests. The
fresh loopback-only PostgreSQL 16 suite in `postgres16-review-findings-1.log`
passes three cases corresponding to three of the dynamic tier's ordinary-process
PostgreSQL skips: the real death/reclaim/finalization trace, the operation-by-
operation stale/competing fence matrix, and result-universe/retry equality. The
other 65 dynamic-tier skips remain skips and receive no passing credit.
`direct-lifecycle-correction-1.log`, `mutations-correction-1.log`,
`pinned-worker-correction.log`, `phase4-transaction-correction.log`, and
`phase4-reclaim-correction.log` retain the focused, nine killed-guard, and
compatibility evidence. Failed and skipped predecessor attempts remain preserved
under their original names and do not receive passing credit.

Affected deployment dimensions:

- **Services:** the executor is an explicitly supplied test-process callable only.
  No production worker role or process topology is accepted.
- **Restart/shutdown:** local abrupt process death and reclaim are proved. Graceful
  production worker shutdown and restart policy remain open.
- **Health/observability:** existing status, attempt, heartbeat, expiry, progress,
  claim latency and takeover measurements are observed locally. Production
  readiness, alerts, retention and queue visibility remain open.
- **Capacity:** existing host/owner job, cell and worker-slot admission limits remain
  unchanged. No production capacity result follows.
- **Rollout/rollback:** there is no data migration. Code rollback restores the exact
  preclaim v2 terminal. No deployment or production rollback is rehearsed.

`phase5-research-runtime-packaging` in the later Phase 5 implementation sequence
owns production worker packaging, dependency locking, explicit service role,
queue/artifact visibility, graceful shutdown, health/metrics/alerts, capacity and
rollout evidence. Phase 6 and the V1 release gate retain production topology,
configuration, security, deployment and rollback authority.

### P5.3 research runtime packaging

Deployment impact is `architecture-changing`; the highest claim is
`locally_runnable`. The exact Python 3.13/macOS arm64 lock contains 59 existing
distributions with immutable versions. Build identity binds the lock, worker,
accepted artifact store, entrypoint, Python implementation/version, operating
system and machine architecture.

The production-shaped local evidence uses separate API and research-worker
processes, separate disposable execution and research SQLite databases, and the
accepted bounded cache/artifact adapter. The API role admits one canonical pending
`BacktestRun` under the existing workload reservation. The worker role consumes
only `dispatch_all_reclaimable`, so the existing row, claim, lease, fence, pinned
worker and terminal publication remain the sole durable job authority. The local
in-memory queue remains a lifecycle evidence adapter and is not a second service or
durable production queue.

The initial correction established separate roles, exact concurrency, real schema
heads, attempt exhaustion and the 59-entry lock. Its exhausted recheck closed
`P5-RRP-003/004/005` but rejected artifact/cache participation, durable queue and
memory authority, PostgreSQL pool evidence and direct worker process lifecycle.
That lineage remains failed and immutable.

The fresh `phase5-research-runtime-packaging-recovery-correction` keeps
`BacktestRun`, claim/lease/fence, pinned execution and claimed result publication as
the sole durable authority. Every launched terminal run now reconstructs one
canonical research cache identity from its persisted descriptor, reads the complete
owner-scoped result universe in stable order, and passes those exact bytes through
the accepted `BoundedResearchArtifactStore`. Cold publication, warm reuse, changed-
byte refusal, corruption, artifact/cache first-over and visible health degradation
are therefore on the durable worker path.

API queue depth is counted and admitted inside the existing SQLite immediate or
PostgreSQL advisory-lock transaction before the new row is written. A minimal
parent supervisor starts before application import, measures aggregate RSS for the
worker and every descendant process, and kills the process group on first-over;
health proves the live parent/child relationship and exact bound. SQLite and
loopback-only disposable PostgreSQL 16 use separate execution/research databases,
actual heads, exact pool size and zero overflow; direct saturation degrades health.
An OS-level SIGKILL after a database-visible active claim is reclaimed once by a
fresh child after the real lease, while SIGTERM stops new dispatch and permits the
active fenced claim and artifact publication to finish safely.

Fresh recovery evidence is under
`.agent/runs/phase5-research-runtime-packaging-recovery-correction/owner/`. It
includes the exact 59-distribution clean install, 28 focused cases, 50 canonical
claim/pinned/interrupted-publication cases, two passing disposable PostgreSQL 16
cases and five killed/restored mutations for artifact-path, durable-queue,
aggregate-memory, PostgreSQL-pool and warm-byte guards. A fresh critical review,
not another exhausted-lineage recheck, owns acceptance.

That fresh review mechanically accepted the recovery boundaries but failed one new
credential-isolation finding, `P5-RRP-R004`: known credential variables were blank,
but `.env` loading was not disabled before application import. The focused
correction now sets `PT_DISABLE_DOTENV=1` in the parent before the supervised child
exists. Health directly requires `Settings.env_file is None`, mock/paper mode,
non-production and empty credential environment/settings. Removing the detachment
kills the named entrypoint test. The restored 28 focused cases, two disposable
PostgreSQL cases and clean 59-distribution install pass. The single focused recheck
returned SPEC PASS and QUALITY PASS with no findings. The recovery package is
accepted at `locally_runnable`; no broader configuration or production authority
follows.

This does not define or start a production service, external queue or object store,
managed PostgreSQL, TLS, credentials, provider networking, broker, order, live or
money behavior. It does not prove production backup/restore, alerts, measured
capacity, rollout, rollback, release deployability, production rehearsal or
deployment. Phase 6, Phase 7 and the V1 release gate retain those exact obligations.

### P5.4 capital-admission architecture

Decision is `KEEP + HARDEN`. The existing execution binding, account lease/fence,
`CapitalState`, execution intent/event lifecycle, command recovery, operational
`Position`, `Trade` and in-process allocator remain singular. Architecture adds
separate product-policy, sizing, target request, closed batch, decision,
reservation and campaign/tranche contracts. It creates no product/schema/runtime
fact in this capsule and authorizes no sizing, order or money behavior switch.

The generated implementation sequence is exact and serial:

1. pure product/sizing/target contracts (`compatible`);
2. additive execution migration `0041` (`migration-required`);
3. unwired fenced PostgreSQL admission transaction (`architecture-changing`);
4. explicit paper/mock shadow, recovery and lineage evidence;
5. read-only money-critical assurance and one Sol-high critical review;
6. Phase 5 evidence integration and sole final phase review.

Migration implementation must prove empty and exact-0040 SQLite/PostgreSQL 16
upgrade, interruption/restart, constraints/triggers/model parity, complete restore
and destructive-downgrade refusal. Broker-touched reservations are retained for
forward reconciliation; rollback never deletes them. The account reservation head
is a lock/revision cursor, not cash authority. Expiry and broker uncertainty never
prove release. Risk-reducing exits remain independent of entry admission.

Phase 5 evidence remains `locally_runnable` and paper-shadow only. Production
service topology, configuration, secrets, TLS, least-privilege roles, health,
alerts, retention, backup policy, capacity, cutover, rollout and deployment remain
assigned to Phase 6, Phase 7, V1 release and the explicit owner gate. No obligation
is deferred to an unnamed future phase.

#### Pure product/sizing/target contract slice

`phase5-sizing-target-position-contracts` is `compatible` and locally runnable.
It adds four pure unwired modules and two direct test files. There is no database,
migration, dependency, configuration, service, provider, runner, broker, order,
money or frontend change. Existing allocator, equity and futures sizing, execution
binding and money-isolation suites remain the compatibility evidence.

The contract uses integer minor units, integer quantities and bounded fixed-point
rates; non-finite/boolean/stale/missing numerics refuse. Product facts consume an
already-resolved binding and cannot select a strategy or query a provider. Target
delta names held and pending evidence; broker uncertainty blocks additions while
risk-reducing reductions remain independent. No product result has a production
caller. Migration and runtime obligations remain owned by the exact subsequent
capital schema, transaction, shadow/recovery and assurance capsules.

#### Capital-admission schema 0041

`phase5-capital-admission-schema` is `migration-required` and locally runnable.
Execution head advances from `0040` to `0041`; research remains `0011`. The
migration adds twelve independent sizing/target/batch/decision/reservation/
campaign/tranche relations. Existing parent tables and historical rows are byte-
preserved; lineage is not inferred and no schema consumer exists.

Money uses `BIGINT` minor units and integer quantities, never new Float columns.
Content addresses, digests, JSON shape, primary sizing mode, owner/account/book/
currency scope, graph attribution, reservation states and unique identities are
database-guarded on SQLite and PostgreSQL. Immutable facts reject update/delete;
mutable reservation/campaign/tranche rows reject identity changes.

Evidence under `.agent/runs/phase5-capital-admission-schema/owner/` includes:

- nine SQLite passes and one declared PostgreSQL skip in
  `direct-sqlite-final-3.log`;
- exact PostgreSQL 16 0040→0041 upgrade, injected transactional interruption,
  restart, model parity and clean dump/restore in `postgres16-final-3.log`;
- prior 0040 attribution and three-plane restore replay in
  `postgres16-transitive-3.log`;
- 275 historical migration passes in `schema-migrations-full-final.log`;
- 31 attribution/PostgreSQL compatibility passes and two declared skips;
- nine killed/restored schema guards in `mutations-2.log`.

Destructive downgrade refuses. Code rollback disables future writers while
retaining immutable facts; broker-touched reservations require forward
reconciliation. Production upgrade, retained/encrypted backup, cutover, RPO/RTO,
service topology, health, capacity, rollout and deployment remain Phase 6/V1 and
owner-gated obligations.

#### Unwired capital-admission transaction

`phase5-capital-admission-transaction` is `architecture-changing` and locally
runnable. It adds one unwired closed-batch service under the existing exact
`AccountExecutionLease` fence and the owner/account/book/currency reservation-head
row lock. One caller-owned transaction re-reads capital, margin evidence, active
reservations, unresolved commands and the held/pending digest; persists the full
candidate set, batch, one decision per candidate, reservations, append-only events,
the head revision and one execution money outbox fact; and leaves commit ownership
with the caller. Exact replay converges only on the same batch address. Conflicting
identity, stale fence/head/capital/pending evidence, incomplete replay and broker
uncertainty have zero effects.

The compatibility policy remains `FUND_ALL_ELSE_PRIORITY_GREEDY_NO_RESIZE`.
Independent and atomic groups use a complete stable rank; unsupported resizing is
recorded as rejection rather than inferred. Risk-reducing requests remain available
without entry capital and create no reservation. Reservation-bound `place_order`
preparation requires the exact held, unexpired, same-fence reservation, target and
quantity, then moves it to `submission_pending` in the same command transaction.
Existing v1 command callers remain unchanged and do not acquire capital-admission
behavior.

SQLite proves local parity and caller-owned rollback. Disposable PostgreSQL 16 is
the concurrency authority: two sessions cannot double-reserve one head, the exact
head `SELECT FOR UPDATE` is observed and blocks a competing admission, and two
sessions cannot prepare one reservation twice. Seven killed source guards cover
lease/flush fencing, exact replay, held/pending evidence, capital bounds, savepoint
rollback, the PostgreSQL head lock and reservation-command predicates with exact
source restoration.

No migration, dependency, configuration key, service role, runner/provider/broker
network call, order submission, behavior switch, credential, frontend, deployment
or production claim is added. The code is not wired into a runtime. Shadow/recovery
and critical assurance remain the exact following capsules. Production service
topology, lease/reservation recovery operations, monitoring, retention, backup,
capacity, cutover, rollout and deployment remain Phase 6/7/V1 and owner-gated.

#### Paper shadow, conservative recovery and position lineage

`phase5-capital-admission-shadow-recovery` is `architecture-changing` and locally
runnable. It adds three unwired application modules plus one offline fixture
comparison script. The read-only shadow receipt runs the current allocator for an
observation, reconstructs the immutable admission batch and exposes canonical
parity, why/why-not facts and replay addresses. A mismatch is evidence only and
cannot change either decision.

Reservation recovery is paper-only, caller-transaction-owned and fenced by the
current account lease plus the exact reservation head. Send-unknown, late
acknowledgement, partial fill, expiry, cancel/fill crossing, external order and
takeover evidence retain capital or consume it monotonically. Rejection,
cancellation or unused resolution releases only with zero-fill evidence and the
matching durable command state where a command exists. Evidence timestamps cannot
move backwards. Two PostgreSQL 16 sessions cannot apply one head revision twice.

Campaign, tranche and fill-allocation facts are additive and paper-only. Exact fill
shares must equal the immutable cumulative-fill delta, cannot over-allocate a
tranche or outrun reconciled reservation consumption, and converge only on exact
replay. Campaign quantity reconstructs in causal allocation order. A campaign
cannot close while either lineage or the operational `Position` is non-flat.
Legacy positions remain explicitly `legacy_unattributed`; no label, quantity or
timestamp inference creates lineage. The lineage service never writes `Position`.

Eleven killed source mutations cover false release, missing zero-fill/command/time
proof, duplicate recovery, fill-delta and tranche bounds, non-flat close, legacy
inference, replay and forbidden runtime imports. Existing money-repository and
paper/live book-isolation suites remain green.

No migration, dependency, configuration key, service role, scheduled process,
runner/provider/broker import, broker network call, order control, current allocator
or `Position` behavior switch, credential, frontend, deployment or production claim
is added. The script reads one supplied JSON fixture and writes one comparison to
stdout. Critical capital assurance remains the exact next capsule. Production
recovery operations, health, alerts, retention, capacity, cutover, rollout and
deployment remain Phase 6/7/V1 and owner-gated.

#### Capital critical-review correction

The first independent `phase5-capital-admission-assurance` review is preserved as
`SPEC FAIL / QUALITY FAIL`. `phase5-capital-admission-critical-correction` changes
only the nine finding-owned boundaries and invalidates the predecessor capital
packages until the sole focused recheck.

The correction includes unresolved intent/event/command facts in the canonical
pending snapshot and blocks unmatched pending entry authority; applies known pending
before uncertain risk-reduction classification; refuses non-integer rank/money facts
before hashing or allocation; binds reserved commands to exact positive quantity and
canonical side; prevents submitted `RESOLVED_UNUSED` release; converges exact batch
replay after TTL; requires exact intent/event/campaign/fence attribution for new fill
lineage; sums reservation consumption across every linked tranche; and protects every
addressed campaign/tranche identity plus durable lineage deletion.

Migration `0041` remains additive and the execution head remains `0041`, but its
trigger bytes are corrected. Fresh and exact-`0040` SQLite/PostgreSQL 16 upgrade,
interruption/restart, fresh-model parity, direct trigger refusal and clean
dump/restore are rerun from the corrected bytes. Code rollback still disables new
writers and retains immutable facts; destructive downgrade still refuses.

The identical broad execution/money compatibility selection is green after binding
the `0037` test to its historical fixture universe and replacing the obsolete `0039`
current-head assertion with the exact `0040→0039` lineage assertion. Fourteen
finding-owned mutations fail and restore exact bytes.

No dependency, configuration, service, runtime caller, provider/broker network,
order submission, allocator/`Position` behavior switch, live authority, credential,
frontend, deployment or production claim is added. The blocked assurance capsule
owns one focused recheck only. Production topology, backup policy, monitoring,
capacity, cutover, rollout, rollback rehearsal and deployment remain Phase 6/7/V1
and owner-gated.

#### Fresh capital assurance and Phase 5 integration gate

The owner-authorized capital replan, exact-int recovery correction and test-only
provider-leak correction culminated in a fresh independent SPEC PASS / QUALITY PASS
with zero findings. The accepted capital claim remains locally runnable, unwired and
paper/mock only. The first FAIL, exhausted recheck FAIL and blocked recovery attempt
remain immutable history.

The historical `phase5-implementation` evidence-integration attempt remains preserved
as `EVIDENCE_CURRENT FAIL` with 169 failures. Its owner-authorized recovery chain is
now complete: all twelve capital tables belong to the existing MONEY plane with zero
new FK crossings; cache schema version 9 and its consumers agree; four stale
compatibility fixtures use current contracts; pytest restores the complete accepted
process-state vector; and the position-lineage admission fixture reads the test
database clock per affected test without changing product time or the 3,600-second
reservation TTL.

The frozen 35-file order passes with 444 passed and one skip. The Settings predecessor
plus all 28 formerly red files passes with 337 passed and one skip. A fresh canonical
`.venv/bin/python -m pytest -q tests research_tests` process ran 4,974.36 seconds and
returned 6,385 passed, 163 skipped and zero failed. Product/runtime SHA-256 remains
`ae9cef587e1b4585fedecd98c8eb2f5ac96be43d5a6d0c53a200a0f51936a2a4`;
every non-target Python test path remains
`3768ff907c3485dc702c688c2fe858dbe13c34eb1b2ebc848404cf0ba9b222b4`.
The exact correction report is
`.agent/runs/phase5-position-lineage-time-fixture-correction/report.md`.

Deployment impact remains `migration-required` for the integrated Phase 5 capital
subsystem because migration `0041` is part of the accepted implementation. The
recovery corrections add no schema, migration, dependency, configuration, service,
provider, infrastructure or production behavior. Phase 5 remains locally runnable,
unwired and paper/mock only. Release-deployable build/configuration/service/health/
rollback evidence, production rehearsal, deployment and live authority remain false
and are owned by Phase 6, Phase 7, the V1 release gate and their explicit owner gates.

#### Type 3 authority and canonical snapshot correction

The owner-authorized `KEEP + HARDEN` correction is architecture-changing but pure
in-process. It adds transient keyword-only evaluator contexts and strengthens existing
catalogue/snapshot validation without changing schema, migration, configuration,
database state, dependencies, services, provider adapters, network behavior, brokers,
credentials, infrastructure, or deployment artifacts. Its fresh local gate passes 643
checks and three direct guard mutations. Highest claim remains `locally_runnable`;
release deployability, production rehearsal, deployment, provider networking, live
authority, and customer-money behavior remain false. Evidence:
`.agent/runs/phase5-state-authority-snapshot-correction/owner-correction/deployability.md`.

#### Custom-node contracts

The four-level custom-node admission slice is architecture-changing and pure
in-process. Levels 1/2 are bounded contract evaluators; Levels 3/4 have no eligible
mode, no batch/stream support, and return a typed unavailable decision. No sandbox
process, external ingress, schema, migration, database, configuration, dependency,
service, provider, broker, credential, infrastructure, or deployment artifact exists.
Highest claim remains `locally_runnable`; sandbox security, authenticated external
signals, release deployability, production rehearsal, deployment, live authority, and
money behavior remain false. Evidence:
`.agent/runs/phase5-custom-node-contracts/owner/deployability.md`.

#### Research execution

The Phase 5 research runtime is architecture-changing and local-only. It reuses the
accepted PlatformRegistry, vector/prefix evaluators, DatasetManifest authority,
ResourcePlan, numeric validity, and state-snapshot schema. It adds no schema,
migration, database state, cache authority, queue, worker service, configuration,
provider, network, broker, credential, infrastructure, or deployment artifact.
Highest claim remains `locally_runnable`; service packaging, capacity, release
deployability, production rehearsal, deployment, live authority, and money behavior
remain false. The accepted snapshot-authority recovery adds no operational dimension;
its fresh independent review closed P5-REX-R001 with SPEC PASS and QUALITY PASS while
keeping complete registered-component parity assigned to the immediate read-only
assurance capsule. Evidence:
`.agent/runs/phase5-research-snapshot-authority-recovery/recovery_owner/deployability.md`
and `.agent/runs/phase5-research-snapshot-authority-recovery/review/verdict.json`.

Read-only complete-universe assurance then found that all 63 Type 3 nodes lacked their
accepted evaluation context at the research orchestration boundary and all 18
recursive Type 5 nodes lacked closed nested-event/result semantics. At that review
point the recovery remained architecture-changing, in-process only and unaccepted.
It added no deployment dimension and made no claim beyond `locally_runnable`. The
fresh semantic-baseline recovery and complete-universe parity assurance recorded
below close that historical finding. Evidence:
`.agent/runs/phase5-research-parity-assurance/report.md` and
`.agent/runs/phase5-research-complete-boundary-replan/deployability.md`.

Exact unresolved ownership is now fixed: `phase5-bounded-sweeps-cache-artifacts`
owns queue/cache/artifact bounds and degradation;
`phase5-research-runtime-packaging` owns locked packaging, service roles, restart,
health, observability and production-shaped local capacity bounds;
`phase6-architecture` owns deployment foundation, topology, preflight, cutover and
rollback choreography; `phase6-strategy-preflight` owns strategy-version preflight;
`phase7-architecture` owns production capacity/economics; the V1 release gate below
owns clean exact-head production rehearsal and release acceptance. Actual deployment
still requires separate explicit owner authorization and `paper-trader/scripts/deploy.sh`.
Evidence: `.agent/runs/phase5-research-context-state-evidence-recovery/ownership.md`.

Post-review complete-universe parity assurance is accepted at SHA-256
`5e0061947fba32880dab8313c92080309879e0d9fca0771b4797536e65ab440a`:
309 registered components, complete independent analytical semantics, Type 3 context,
recursive nested-event parity, provenance identity and restoration all pass. The
accepted claim remains local and in-process; cache reuse, sweeps, artifacts and worker
packaging remain their immediate exact Phase 5 capsules.

Bounded sweeps/cache/artifacts are now accepted locally: complete 25-field identity,
owner/licence isolation, lowest-limit sweep admission, single-flight concurrency,
corruption/restart/eviction and byte/cost bounds pass. The adapter is in-memory and
does not establish a production object store or worker service. Evidence:
`.agent/runs/phase5-bounded-sweeps-cache-artifacts/owner/deployability.md`.

### P5.5 canonical scenario gate

Deployment impact is `architecture-changing`; the highest claim is
`locally_runnable`. The gate adds only two test files and local evidence. Product,
schema, migration, dependency, configuration, service, provider, broker, order,
live and money paths are unchanged.

Three immutable scenario envelopes pass through the accepted registry, resolver,
data-requirement compiler, provider-evidence mapper, ResourcePlan, research
batch/incremental execution and bounded cache/artifact seams. Scenario A retains one
graph across three primary binding requirements and names actual EMA/RSI/ATR,
sizing-risk, stop and addition intents. Scenario B retains a 21-member weekly option
selector, point-in-time OI/depth facts, weekday/session scheduling and pure exit/
protection intents without order authority. Scenario C retains one execution target
and three observation/reference roles with distinct MCX/NYMEX/NSE sessions,
freshness and alignment facts. GOLD/CRUDE simultaneous and one-strategy/three-
instrument cases reuse one graph and preserve every role, binding-input, provider
and resource address.

The complete claimed universe is 18 real first-party components and outputs plus a
20-field scenario envelope. Every omitted envelope field refuses. Standard, Pro and
Desk pass at simultaneous conjunctive maxima and refuse every first-over dimension.
SQLite and loopback-only disposable PostgreSQL 16 persist immutable ExperimentSpecs;
a fresh process reloads and recomputes all graph, implementation, dataset, truth,
policy, ResourcePlan, result, owner, job, cache and artifact lineage addresses.
Tampered lineage, stale provider capability, overwide selector, wrong alignment/
truth/binding, and cache-path bypass refuse.

Evidence under `.agent/runs/phase5-canonical-scenario-gate/owner/` includes 44
ordinary-process passes with one PostgreSQL skip, the separately passing PostgreSQL
case, 232 affected-seam passes and five killed/restored mutations. Scenario evidence
does not create a binding, account, capital, lease, reservation, provider route,
broker protection, order or money record. Production capacity, commercial tiers,
release deployability, rehearsal and deployment remain false and retain their
Phase 6/7/9/V1 owners.

### P5.6 final implementation integration

All 31 executable Phase 5 architecture, implementation, correction and assurance
predecessors are accepted in serial order. The recovered runtime-packaging lineage
ends in fresh independent SPEC PASS / QUALITY PASS evidence. Its local worker pack
proves mandatory durable cache/artifact materialization, a serialized durable queue
bound, aggregate resident-memory supervision, exact SQLite/PostgreSQL pool limits,
process-death reclaim, graceful termination and credential-environment detachment.
These are local packaging and failure-semantics claims, not production service or
deployment claims.

The fresh canonical Phase 5 process ran
`.venv/bin/python -m pytest -q tests research_tests` from one process and returned
7,290 passed, 166 skipped and zero failures. The exact log SHA-256 is
`f4b538f57e3954191ee689f8ecd3622d56dae16d0e640fc7651c48d6b74a4afa`.
The programme/repository contract gate returned 27 passed plus 35 subtests, and the
agent-architecture validator checked 265 files with zero findings. These results
establish local integration and evidence currentness only.

Deployment obligations remain explicit:

1. `phase6-architecture` owns PostgreSQL service topology, configuration binding,
   database heads, preflight, health, restart, cutover and rollback choreography.
2. `phase6-strategy-preflight` owns exact immutable strategy-version deployment
   preflight.
3. `phase7-architecture` and
   `phase7-incremental-runtime-resource-economics` own production-shaped CPU,
   memory, queue, disk, database-connection, latency, degradation and cost evidence.
4. `phase9-architecture` and its provider capsules own credentials, network calls,
   rate limits, fallback and real-provider conformance.
5. The V1 release gate owns clean exact-head build/install, backup/restore,
   observability, capacity, rollback rehearsal and release acceptance.
6. Actual deployment remains a separate owner gate and may use only
   `paper-trader/scripts/deploy.sh` after its exact-head evidence exists.

Phase 5 final review can grant Phase 6 architecture readiness only. It cannot grant
release deployability, production rehearsal, deployed state, provider authority,
live authority, order authority or customer-money authority.

The sole final review first returned SPEC FAIL / QUALITY FAIL on evidence-lineage
findings P5-FINAL-001 and P5-FINAL-002. The bounded evidence-only correction changed
no product or product-test bytes. Its single focused recheck returned SPEC PASS /
QUALITY PASS with zero findings against package SHA-256
`eb87bdf31dc074f2588cab6c3aba4b47ed0183f16f27eb0f1240dc15ce6d12f9`;
the verdict SHA-256 is
`283233e7d145fa06239a86d2008a13bd9ac4af301e4477e8f52f7c55c20afdc3`.
Phase 5 is accepted. This grants Phase 6 architecture readiness only and does not
change any deployment or authority claim above.

### Post-Phase-5 indicator accuracy audit

The owner-authorized read-only audit rejects the numerical-accuracy claim for the
125-component Type 2/4 catalogue: 25 components have strict independent matches,
60 have known mismatches or incomplete contracts and 40 remain unverified. All
2,500 hostile prefix-causality checks pass, so this is an accuracy/semantic finding,
not a look-ahead finding. Product and product-test changes are zero.

The audit is `read-only assurance`; it adds no deployment dimension. Any correction
will be architecture-changing and must use new semantic versions or typed refusal,
not silently reinterpret accepted version 1. Phase 6 remains blocked behind the
owner-gated `post-phase5-indicator-accuracy-correction-replan`. TradingView private
library access and licence review remain a separate owner/legal gate; no unofficial
API or credential was used.

### Strategy OS V0 release audit and accelerated plan

The owner-directed V0 package is a read-only architecture/release replan. It changes
no application, product test, schema, migration, dependency, configuration, service,
provider or infrastructure bytes. It retains one Strategy OS architecture and places
ten accelerated V0 stages before the old Phase 6 continuation.

The planned V0 is architecture-changing and configuration/service/frontend/provider
affecting. Its first required slice creates a server-enforced research/signal profile
that cannot host an execution worker, execution lease, broker/order client or
execution mutation route. Later stages own indicator accuracy, canonical research,
Zerodha/data, charts/annotations/replay, robustness, monitoring/signals/review,
frontend convergence, security/operations/analytics/deployability and A/B/D/E/F
release evidence.

Current evidence remains `locally_runnable` only. The full requested V0 is not
demo-certified, beta-ready, paid-beta-ready, release-deployable,
production-rehearsed, deployed or legally/data-rights cleared. Phase 6 remains
blocked until V0 review and the owner-selected continuation.

### V0-A release-profile foundation

The V0 release profile is architecture-, configuration-, service- and
frontend-affecting and remains `locally_runnable`. It adds no schema, migration,
dependency, provider network, credential, infrastructure, broker, order or money
change. `PT_RELEASE_PROFILE=v0_research_signal` refuses boot unless research is
enabled, execution is paper, the execution-worker role is API-only, the live
acknowledgement and execution provider/connection are empty, and no execution
owner/account/cell is assigned.

The bounded first-review correction adds a typed current
`PT_RELEASE_SERVICE_ROLE` in `{api,research_worker,monitor,scheduler}`. The
manifest reports that current role and its required planes; API readiness proves
execution, ledger and research authorities, while the other roles prove execution
and research. A failed research probe returns 503 and names the research plane.
Non-API V0 roles do not serve product API routes, and research reclaim/dispatch is
restricted to research-worker and scheduler roles.

The immutable server manifest names 35 current execution-shaped mutations, ten
private execution reads and two private execution WebSockets as unavailable. Both
HTTP prefixes return one typed V0 refusal, both WebSockets close before private
state resolution, and a second construction boundary prevents runner or account
lease creation. A local isolated mock/paper V0 process reported research readiness,
`engine.present=false`, `execution_authority=false` and zero account execution
leases. Desktop and 390px browser network evidence contained only the release
manifest and canonical IR/research reads. Mixed-role broker-connection creation,
credentials, revocation, login materialization, OAuth initiation and callback are
blocked until V0-D proves data-only separation. The ordinary profile passed 140
existing boot, auth, versioning, connection, health, execution-isolation,
tenant-channel, WebSocket and portfolio tests after the final correction.

The browser capture is denial evidence, not visual product acceptance. The owner
reaffirmed Precision Slate Direction 7 in the standalone
`/Users/priyanshusaraf/dev/strategy-os-frontend` prototype as the V0 design
authority. That prototype remains fixture-only and has no backend. The accelerated
V0 sequence must establish a real-API Precision Slate shell before later feature UI
is accepted, while retaining a later convergence gate for completed surfaces and
removing fixture claims rather than treating them as product truth.

The trading bot is not the V0 application or deployment target. Its standard
profile was started once locally with mock data, paper execution, empty live
acknowledgement and temporary databases solely to prove compatibility; it remained
disarmed. The trading-bot VPS was not accessed and remains untouched. Strategy OS
is a separate application and separate future deployment target. Shared backend
infrastructure may be used by its separately configured process, but no bot or
Strategy OS deployment is authorized here.

Evidence: `.agent/runs/strategy-os-v0-release-profile-foundation/report.md`,
`browser-evidence.md`, `runtime-evidence.json`, the pre/post protected-path freezes
and the killed/restored central-barrier mutation. Correction evidence is in
`correction-report.md`, `correction-browser-evidence.md`,
`verification-commands.json`, the correction post-edit freeze and the independent
connection-inventory mutation. No deployment was attempted or authorized. V0 demo,
beta, release, production, capacity, rollback, provider/data rights, legal and
Phase 6 readiness remain false.

### V0 separate Precision Slate application replan

The owner-authorized replan changes architecture/programme evidence only and has
current deployment impact `none`. Product, prototype source, dependencies, schemas,
configuration, services, providers, credentials and infrastructure remain
byte-protected. The future application is architecture-changing.

Precision Slate Direction 7 in the standalone `strategy-os-frontend` repository is
the frontend source/design authority after a separately authorized promotion slice.
The canonical backend/IR/research system remains in options-trading and will run
later as a separately configured V0 API/service deployment. The frontend is not
merged into the bot cockpit, no second backend/IR/research ledger is created, and the
bot VPS, deployed build, databases, credentials and deploy script remain excluded.

The plan inserts an early shell foundation before indicator/node and feature work,
then makes research, data/static-watchlist, chart, robustness and monitoring stages
own their real Precision Slate surfaces. A later integration closure owns
fixture-elimination, accessibility, desktop/390px behavior and performance. Public
V0 omits Deploy, execution Live, money/position Portfolio and custom Workspace;
monitoring-only Signals replaces Live after V0-G. Static research watchlists are new
owner-scoped instrument scopes and never reuse the execution Watchlist assignment.

No separate deployment path exists today. The repository currently authorizes only
the bot-oriented `paper-trader/scripts/deploy.sh`, which the owner has excluded.
`strategy-os-v0-security-operations-deployability` must obtain an explicit
repository-contract amendment before creating a separate Strategy OS deploy and
rollback entrypoint. It also owns remote/CI/hosting, two-repo artifact identity,
PostgreSQL roles/heads/TLS, secrets/auth, health, observability, capacity,
backup/restore and rollout evidence. Until those gates pass, the highest claim
remains `locally_runnable`; release-deployable, production-rehearsed, deployed and
bot/VPS-changed are false.

Evidence: `.agent/runs/strategy-os-v0-frontend-convergence/architecture-decision.md`,
`surface-api-matrix.json`, `implementation-capsules.json`,
`implementation-sequence.md`, `findings.json` and `deployability.md`.

## Phase 6 ownership

Own the deployment-foundation blockers: current PostgreSQL service topology, configuration binding, preflight, three-plane health, tracked systemd/runbook artifacts, deploy-script database gates, authority separation, and cutover/rollback choreography.

Before activation or deployment-binding work, `phase6-generated-strategy-version-lineage` must close CUR-H4 with immutable generated versions, append-only lineage, and exact-version fresh-process replay. Mutable current-slot rows remain non-authoritative.

## Phase 7 ownership

Own CPU, memory, disk, database connections, WAL, subscriptions, cache, queues, latency, degradation behavior, and cost telemetry under production-shaped load.

## Phase 8 ownership

Own truthful operator-facing preflight, readiness, degraded/recovery states, deployment progress, rollback/error guidance, and no-false-green UX.

## Phase 9 ownership

Own provider/broker credential injection and rotation, network/rate-limit behavior, capability drift, fallback, degraded provider health, and deployment compatibility.

## Phase 10 ownership

Own tenant administration, retention, audit, support diagnostics, operational access, incident/runbook completeness, backup monitoring, and production customer operations. It may not absorb unowned debt from earlier phases.

## V1 release gate

Require a clean exact-head production-shaped rehearsal covering build/install, locked dependencies, secrets/configuration, PostgreSQL roles and three-plane heads, supported upgrade, backup/clean restore, service restart, health, rollback, observability, capacity, and post-deploy smoke. Require zero unowned obligations. Actual deployment remains a separate owner-gated action.

### V0 Precision Slate shell foundation — 2026-08-28

Owner authorization: `AUTHORIZE V0 PRECISION SLATE SHELL FOUNDATION`.
The separate frontend now has a manifest-first Precision Slate shell and a bounded
owner-scoped graph-index read seam over existing canonical records. This is an
architecture-changing frontend build and compatible read API. No migration,
dependency, lock, provider, runtime authority, bot/VPS or deployment change.

Local evidence: external frontend lint/typecheck/68 tests and deterministic artifact,
8 graph-index/tenant tests plus 65 V0-A/standard compatibility tests, manifest-barrier
mutation killed/restored, 11 desktop/390px browser cases, no application WebSocket,
no runner/lease, distinct temporary databases and completed runtime cleanup.
Product/protected-byte and independent review receipts live under
`.agent/runs/strategy-os-v0-precision-slate-shell-foundation/`.

Highest claim is locally runnable. Release-deployable, production-rehearsed and
deployed remain false. Exact remaining owner is
`strategy-os-v0-security-operations-deployability` (V0-I), before its acceptance:
production auth/origin/TLS, approved hosting/remote/CI and separate deployment
contract, release identity/HTML metadata, full clean-install/platform lock and
advisory/SBOM validation, notices, PostgreSQL/services, health/build stamping,
backup/restore, capacity, rollout and rollback. The installed CycloneDX SBOM is
current; lock-only SBOM generation reports missing optional WASM transitive entries.
No dependency remediation or external advisory network access was authorized.
See the slice `deployability.md` for the exact evidence and boundaries. No later
feature or deployment authorization follows from local checks or review PASS.

### Post-Phase-5 indicator accuracy correction replan — 2026-08-28

Owner authorized architecture-only planning. No product, dependency, database,
service, provider or deployment mutation. The 125-component plan preserves all v1
bytes/addresses and specifies 23 kept formulas under new contracts, 85 versioned
replacements, and 17 unavailable candidates. These are planned dispositions, not
new numerical PASS results.

Fifteen serial correction/independent-assurance/integration/review capsules are
scheduled before the V0 verified catalogue. Contract foundation owns the versioned
parameter-aware canonical binding extension; each numerical wave owns its measured
resource and state proof; registry-lineage integration owns real cache/result/job
consumers; complete-universe assurance and one final critical review gate publication.
Any needed SQL migration requires a new explicit owner gate before mutation.

Reference environments require exact core/wrapper/build/runtime evidence; no
TA-Lib adoption occurs here. The prior audit used pandas 2.3.2; the current lock
uses pandas 3.0.5. Old results are historical evidence, not current-runtime parity.
TradingView access is excluded. The deferred source gate for Supertrend, Ichimoku
and the intended Garman–Klass convention is not executable without new authorization.

Exact evidence and future ownership:
`.agent/runs/post-phase5-indicator-accuracy-correction-replan/deployability.md`.
V0-I (`strategy-os-v0-security-operations-deployability`) still owns separate
release/build/configuration/database/service/security/operations/rollback evidence
before a release-deployable claim. No Phase 6, frontend, live or deployment authority
is opened by the architecture replan.

### Post-Phase-5 indicator accuracy contract foundation — 2026-08-28

Compatible versioned in-memory contract/binding/state readers; no dependency, lock, SQL, service, provider, frontend or deployment change. The 321-check affected selector and isolated killed/restored binding mutation passed; all 125 v1 records and the full default registry identity are unchanged.

Highest claim: locally tested foundation, pending independent contract assurance. No numerical accuracy, publication, release-deployable, production-rehearsed or deployed claim. Verified producer/job/cache/result wiring belongs to `post-phase5-indicator-accuracy-registry-lineage-integration`; numerical waves own measured resource/state/causal evidence. `strategy-os-v0-security-operations-deployability` owns separate build/install/dependency/SBOM/advisory/auth/database/service/backup/capacity/rollout/rollback gates before release acceptance.

Exact boundary, offline runtime inventory and future owners: `.agent/runs/post-phase5-indicator-accuracy-contract-foundation/deployability.md`. Independent assurance and numerical work require their separate owner gates.


### Post-Phase-5 indicator accuracy core math — 2026-08-28

Compatible unpublished v2 candidate code only: 58 decisions, with 1,035 final local/compatibility checks and four killed/restored isolated mutations. All 125 legacy identities and the default registry snapshot remain unchanged. No dependency/lock, SQL, provider, execution, frontend, service or deployment change.

Acceptance remains incomplete: the exact reference-only TA-Lib 0.7.1 executor permission is missing for 26 native parity checks, and separate numerical assurance has not started. Standing owner continuation authority is recorded; no routine stage token is required. Local tests are not publication, release-deployable, production-rehearsed or deployed evidence.

Measured bounded streaming resources and remaining batch/job/consumer gates are recorded in `.agent/runs/post-phase5-indicator-accuracy-core-math/deployability.md`. `post-phase5-indicator-accuracy-registry-lineage-integration` owns actual runtime/state/mask/resource/cache/result/admission consumers and whole-job allocation evidence. `strategy-os-v0-security-operations-deployability` owns the named release assembly, topology, provenance, capacity and rollback gates before acceptance.


### Core-math reference environment and independent handoff — 2026-08-28

The expanded V0 instruction resolves the reference-environment permission gate. An isolated exact TA-Lib 0.7.1 native/wrapper build passes upstream regression and records compiler, settings, source and binary hashes. Product packages/locks and system libraries are unchanged; the upstream system-cleaning install target was not run.

All 26 default native comparisons pass. Five raw extended/adversarial failures remain visible and pass exact mathematical counterchecks; separate-owner assurance must independently confirm these reference limitations. Implementation acceptance does not imply universal parity, publication or release-deployability. Evidence: `.agent/runs/post-phase5-indicator-accuracy-core-math/v0-authorized-resume/` and its reference-environment receipt. Existing registry/lineage integration and V0 release-assembly/resource gates retain ownership.


### Core PERCENTILE canonical-parameter correction — 2026-08-28

F01 local correction passes 98 focused checks and a killed/restored coercion mutation. The replay guard and mathematical functions are unchanged; all 125 v1 identities/default registry remain preserved. All 58 unpublished candidate implementation/binding identities move with the defining module, without rewriting historical evidence. No dependency/lock, SQL, provider, execution, frontend or deployment change.

F02 remains open, with 12 reproduced failures. `post-phase5-indicator-accuracy-core-return-stability-correction` owns stable arithmetic and final corrected-wave resource/restart/compatibility proof; `post-phase5-indicator-accuracy-core-correction-assurance` owns independent acceptance. Evidence: `.agent/runs/post-phase5-indicator-accuracy-core-parameter-correction/`. No publication or release-deployability claim.

### Core return and near-flat stability correction — 2026-08-28

F02 and the explicitly amended F03 scope now pass local correction checks: 2,184
numerical/compatibility tests, 58 separately run resource checks, 36 complete-array
trace cases, and seven detected/exactly restored isolated numerical mutations.
This uses existing Python stdlib arithmetic only; no installed dependency/lock,
SQL, provider, execution, frontend, service or deployment change.

Measured resource coverage is 399 points across all 58 candidates and minimum,
default, intermediate and maximum windows; precision paths also include near-flat,
subnormal and large finite inputs. The observed maximum untraced event time is
187,539.166 microseconds. ALPHA/BETA compute declarations increase from 200,000 to
500,000 microseconds after an earlier traced event exceeded the old bound. Exact
rational level regression removes the intermediate Decimal workspace overrun;
final level-regression memory estimates are at most 2,411,208 bytes. Other resource
fields stay unchanged. These are local node measurements, not job/host capacity.

All 125 v1 identities and default registry must remain exact at the closing source
proof. All 58 unpublished candidate binding/implementation identities change; only
the ALPHA/BETA source-contract compute bounds change. No historical package is
rewritten. Original native/reference failures remain negative evidence: all 26
defaults pass, while the same five raw extended comparison failures remain.

Different-owner acceptance remains at
`post-phase5-indicator-accuracy-core-correction-assurance`, including a fresh
constant-ratio oracle extension. Actual composition, runtime/state/resource/cache/
result/admission consumers and whole-job resource accounting remain owned by
`post-phase5-indicator-accuracy-registry-lineage-integration`. Separate release,
installation, security, service, capacity and rollback evidence remains owned by
`strategy-os-v0-security-operations-deployability` before release acceptance.
Evidence: `.agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/`.
No numerical publication, release-deployable, production-rehearsed or deployed claim.

### F04 core level-moment correction — 2026-08-28

Compatible unpublished numerical correction for seven explicitly audited consumers.
Local evidence: 2,425 numerical/compatibility tests and 58 standalone resource checks
pass; 144 complete-array impact cases pass after 76 pre-correction failures; 40 new
permanent regressions pass; four numerical mutants are detected and all 265 isolated
copied files are restored. These remain implementation-owner checks.

All 525 measured resource points fit the existing declarations, including the newly
corrected paths at near-flat, subnormal and large finite scales. Maximum observed
untraced step is 110,604.541 microseconds; maximum retained-state plus measured
workspace estimate is 5,065,662 bytes. No resource ceiling is raised in F04. Source
contracts and float64 state/serialization semantics remain unchanged; defining-module
binding/implementation identities change and historical receipts are never rewritten.

No installed dependency/lock, SQL, service, provider, execution, frontend, live/VPS,
money or deployment change. Full protected/legacy identity proof belongs to this
capsule's closing source receipt. Independent acceptance remains at
`post-phase5-indicator-accuracy-core-level-moment-assurance`. Actual composition,
job/state/resource/cache/result consumers remain at
`post-phase5-indicator-accuracy-registry-lineage-integration`; release assembly and
operations remain at `strategy-os-v0-security-operations-deployability` before any
release-deployable claim. Raw native reference limitations remain explicit.
Evidence: `.agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/`.

### Independent core-wave acceptance and recursive-state transition — 2026-08-28

The separate fresh owner sealed ASSURANCE PASS for all 58 core components and 60
outputs after F01/F02/F03/F04. The coordinator reverified all 120 sealed artifacts,
current source snapshots, branches/HEADs/indexes and both test/oracle/source hashes.
The accepted packet has 2,698 distinct passing test identities, 222 resource points
and six killed/restored mutations; overlapping runs are not summed. Original test
adapter failures and native-reference limitations remain visible. The independent
capsule and package are preserved byte-for-byte at their sealed hashes.

Core numerical acceptance does not publish candidates or grant deployment authority.
The next bounded unit is the 17-component recursive-state capsule, under standing V0
authority. Core/shared source, v1, both frontends and dependencies/locks remain frozen.
No product/runtime/schema/provider/deployment change occurs in this control transition.
Evidence: `.agent/runs/post-phase5-indicator-accuracy-core-level-moment-assurance/`
and its coordinator acceptance/transition seal. Existing registry/lineage integration
and V0 release-assembly gates retain their exact ownership.


## 2026-08-28 recursive indicator candidates

Seventeen unpublished /2 recursive candidates are locally verified; independent assurance is pending. Existing interpreter/stdlib and locks are unchanged. No SQL, service, provider, frontend or deployment change. The 243 measured scalar resource points fit declarations; this does not establish whole-job capacity. Evidence: `.agent/runs/post-phase5-indicator-accuracy-recursive-state/report.md`, `source-proof.json`, `resources-final.json` and `deployability.md`. Canonical transport/composition and job/cache/result/admission adoption belong to `post-phase5-indicator-accuracy-registry-lineage-integration`; release assembly, whole-job operations/resources and deployment/rollback evidence belong to `strategy-os-v0-security-operations-deployability`. Publication, deployment and V0 completion remain false.


## 2026-08-28 SAR source-contract reconciliation

`post-phase5-indicator-accuracy-recursive-sar-source-replan` proves the two scalar reference promises cannot both meet the existing error bounds. An explicit additive mathematical source decision is accepted for the unpublished SAR candidate; the original native-parity promise remains REJECT. No product algorithm, precision, input domain, tolerance, mask, dependency, SQL, provider, frontend or deployment change occurs in this replan. The exact metadata correction must prove new source/binding/state identity and unchanged mathematical behavior; fresh independent assurance remains required. Integration and V0 security/operations/deployability retain their exact consumer and release gates. Evidence: `.agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-replan/report.md`, `decision.json` and `conflict-proof.json`.


## 2026-08-28 corrected SAR source identity

The bounded metadata correction changes SAR provenance and all 17 defining-module binding/implementation identities, with no numerical/state function, domain, precision, mask or resource-profile changes. Real old plans/receipts/state refuse and new local canonical consumers pass; 243 current resource points fit declarations. Fresh independent assurance is pending. No dependency/lock, SQL, provider, frontend, service or deployment change. Integration owns source-version/archival-test accounting and actual job/cache/result/admission adoption; V0 security/operations/deployability owns release/whole-job/deployment proof. Evidence: `.agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-correction/report.md`, `source-proof.json`, `consumer-proof.json`, `resources-current.json`. Native-parity and V0 completion are not claimed.


## 2026-08-28 recursive-wave independent acceptance and parallel V0 planning

The corrected mathematical SAR source and complete 17-component recursive wave now have independent ASSURANCE PASS. The exact old 733 identities still produce 731 PASS plus two archived native-parity RED obligations; 14 raw native comparisons remain FAIL. No native-parity claim is added. The 400 current checks, 135 measured resource points, six intended-consumer mutation failures/restorations and all protected identities were verified by the coordinator against the sealed package. Evidence: `.agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-assurance/` and `coordinator/acceptance-verification.json`. This transition is evidence-only; publication/whole-job integration belongs to `post-phase5-indicator-accuracy-registry-lineage-integration`, and release/operations/rollback to `strategy-os-v0-security-operations-deployability`.

The next numerical capsule is multi-output. The owner separately requested parallel development of unrelated V0 work. The declared `strategy-os-v0-parallel-workstream-replan` is initially read-only and must identify exact independent leaves, file ownership, frozen contracts and convergence gates before their product work starts. It does not authorize deployment, live/provider credentials, external legal/commercial decisions or numerical publication.

The coordination test now distinguishes zero numerical children from the exact one read-only V0 replan assignment. The original failure is retained; all nine orchestration checks and four isolated metadata violations exercise the existing consumer. Dispatcher/validator runtime and all product bytes are unchanged. This is not a general parallel-write authorization; executable leaves still require exact accepted ownership.


## 2026-08-29 parallel V0 leaves

The independent dependency replan is accepted for four bounded leaves: existing-shell access revalidation, session credential representation, private failure diagnostics, and immutable static research-scope persistence. Their scopes and integration owners are in the exact materialized capsules. The first three have compatible local impact; static scope owns the sole additive 0042 migration slot after a safe actual 0041 head query, with PostgreSQL16/CAS/restore evidence required. No public capability, registry publication or deployment is opened. All four require their declared independent SPEC/QUALITY review before acceptance. Primary numerical work remains isolated. The replan seal is `37fe5c736a1ae169e08be985ec27fcf615b377419977e577da4445ff1da334ec`; exact routes and subsequent acceptance are recorded under the active multi-output coordinator run.


### 2026-08-29 session credential representation accepted

The bounded session credential representation leaf has independent SPEC PASS and QUALITY PASS, with its owner goal completed from the sealed verdict and current source hashes. Scope is routine repr/str/container/log interpolation only; explicit token access, asdict, onboarding and whole-application security remain excluded. Local, peer-convergence and independent suites each passed 35 checks; the original and isolated mutation each reproduced five intended failures. Closure: `.agent/runs/strategy-os-v0-session-credential-hygiene/closure-seal.json`. Compatible local change; release assembly remains owned by `strategy-os-v0-security-operations-deployability`. No deployment or V0 completion claim.


### 2026-08-29 shell/diagnostics acceptance and static authorization correction

Existing-shell access revalidation and bounded V0 private diagnostics have independent SPEC/QUALITY PASS and completed owner closures. These accept only their scoped behavior, not new capabilities, general privacy/accessibility conformance or deployment. The static-scope persistence checkpoint passes398 checks including PG16, but complete route/action mapping is RED for reserved Project/path values. A separate two-file principal action-classification correction is assigned; the static capability stays closed. Exact receipts and ownership are under the active multi-output coordinator/static-authorization run.

A pre-existing0041 broker SQLite CHECK/ORM mismatch independently reproduces strict copy refusal before static scope. `coordinator/inherited-copy-finding.json` records the evidence and exact `strategy-os-v0-security-operations-deployability` gate required before its acceptance. Current clean-install copy and historical mismatch refusal are separate claims; no copy guard is weakened and no legacy-copy deployability is claimed.


### Multi-output candidate implementation and independent assurance

The nine-component/nineteen-output implementation is sealed under
`.agent/runs/post-phase5-indicator-accuracy-multi-output/closure-seal.json`.
Classification: compatible unpublished analytical candidate, no numerical-owner
schema/dependency/provider/frontend changes. Local2087 tests,58 resource points and
seven genuine isolated mutations support implementation evidence only. Strict native
comparison remains33PASS/7FAIL out of40, plus5specification-only cases. There is no
independent numerical or native-parity acceptance. The exact-source question belongs
to `post-phase5-indicator-accuracy-multi-output-assurance` before publication.
`post-phase5-indicator-accuracy-registry-lineage-integration` owns whole-job resource,
cache/queue/result and registry composition; `strategy-os-v0-security-operations-deployability`
owns exact release assembly/capacity. Release/production/deployed verdicts are unchanged.
The two unfinished V0 assignments carry through the exact sealed one-stage decision;
no capability opens and reviewed static/authorization sources remain frozen.


### Static-scope authorization correction accepted

Exact three-source correction has independent SPEC PASS / QUALITY PASS and owner
closure under `.agent/runs/strategy-os-v0-static-scope-authorization-correction/closure-seal.json`.
The coordinator reverified historical42/integrated59 artifacts, reviewed source and
259 independent passing tests. Only actual-route action/path selection is accepted.
Private Starlette helper coupling retains its upgrade regression gate. Static-scope
foundation must finish its own HTTP/integration/review, and static capability stays
blocked. No migration/dependency/service/publication/deployment or V0-release claim.


### Multi-output source decision and completed bounded V0 leaves

MACD has an explicit additive mathematical source decision with477 exact disjoint
native/mathematical counterexample intervals. The old pinned-native promise remains
REJECT. Product correction and fresh9/19assurance are separate gates; STOCH_RSI's
mathematical definition/thresholds remain unchanged. No source or runtime product
edit occurs in this replan. F03 remains with registry-lineage integration.
Q04 geometry, Q06 existing recovery and static persistence/current BLOCKED/F1 scopes
have independent dual PASS and owner closures. They do not establish renderer,
dataset/service integration, real enum-enabled static opening or deployment. The
static enum mismatch is mandatory before zerodha-data-static-scope capability opening;
historical broker CHECK/fixed-head release qualifications remain. Release verdicts
are unchanged and the next independent queued scopes remain required.


### Corrected multi-output local evidence accepted for independent assurance

Local correction seal1150612a38f001b6340c46fe23a7289174cb87f5c188fb7a69cf3c8e49d35327
binds858artifacts and actual old/new consumer/state proof. MACD metadata follows the
explicit mathematical source decision; STOCH_RSI zero-delta ratio invariance is
locally corrected.149mathematical cases pass,4invalid combinations refuse; original
486identities reconcile457PASS/29FAIL, retaining20native and9F03 failures.31resource
points and9genuine mutants pass local evidence only. Fresh independent9/19assurance
is required. No public node composition, F03 repair, provider or deployment claim.


### Q01/Q03 bounded parallel development opening

Q01 alone owns additive local0043 USER auth schema, exact HTTP/session/cookie boundary and named Precision Slate files; real HTTPS/SQLite/PG16/restore/tenant proof and independent review precede acceptance. No public signup/email/recovery/MFA or dependency-security completion is claimed. Q03 alone owns the persisted canonical dataset adapter and existing experiment bridge; no schema, provider, shared IR or dependency changes. Both remain unaccepted, no capability opening or deployment. Exact contracts/limits: .agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/leaf-decision.json; later public account and broader capture/convergence gates are named in PROGRAMME.


### Q03 provider-schema/index-encoding clarification

Q03-F01 is a coordinator-contract ambiguity, not an established loader defect.
Real synthetic persistence reproduces both original schema-closure refusals and
successful reopen when segment.raw_schema_address retains provider provenance.
The additive Q03 contract validates index media/envelope separately; it preserves
all exact union/dependency guards and refuses unsupported multi-schema segments.
No shared code, schema, dependency, provider, capability or deployment change.
Full Q03 implementation/PG16/HTTP/causal/research proof and its one independent
critical review remain outstanding. Prior contracts and raw evidence remain exact.


### BOLLINGER_BANDS/PPO source decision and explicit parallel carry

Source reconciliation proves691disjoint required math/native intervals and selects
explicit mathematical variants under new unpublished source identities. The old
two native promises remain REJECT; no formula/seed/mask/domain/tolerance/precision
or resource change is allowed. Only named metadata/provenance correction and fresh
9/19assurance may follow.125legacy/58core/17recursive/defaultregistry remain exact.
Q01 and clarified Q03 keep their exact existing owners/paths; they are not accepted
by this transition. No schema/dependency/provider/capability/deployment is opened.
F03 and public-account/data-capture release gates remain in their exact stages.


### Q03 normal cold-admission ordering clarification

The normal first experiment cannot depend on manual research-receipt seeding.
Prepare the exact existing admission without writes, validate canonical data and
supported graph, then mirror with the existing helper/session and run the existing
orchestrator. Invalid preflight writes nothing; mirror failure rolls back; later
valid-run failures retain existing durable evidence. Same Q03 paths/owner; no new
authority/schema/provider or deployment. Full cold HTTP/PG16/negative proof and
the one independent Q03 critical review remain required before acceptance.


### BOLLINGER_BANDS/PPO source correction routed to fresh assurance

Local metadata/provenance correction keeps every function/class and all numerical
behavior exact;125legacy/58core/17recursive/defaultregistry remain unchanged and
unpublished. Historical20native+9F03 plus archived old-source tests remain explicit
RED obligations. Fresh independent full9/19assurance is mandatory. Q01/Q03 owners,
paths and both Q03 addenda carry unchanged. No public capability, dependency,
provider/live authority, deployment or V0 acceptance.

Q01 invited-user browser session transport is accepted at its fresh immutable evidence boundary. SPEC PASS and QUALITY PASS do not authorize public signup, recovery, MFA, production migration, release deployability, deployment, or V0 completion.

Q03 canonical persisted-dataset research bridge is accepted at SPEC PASS/QUALITY PASS for the bounded synchronous path. The 185,439,680-byte traced peak and 222,543,872-byte RSS high-water do not establish public concurrency/capacity, release deployability, deployment, or V0 completion.
