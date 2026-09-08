# Phase 4 Strategy OS implementation plan

## 1. Scope and stopping rule

Implement the reviewed Phase 4 design through seven serial durable implementation goals and one serial Sol-high review. The documentation-only registry architecture correction is a prerequisite correction stage, not one of the seven implementation goals. The non-executable `phase4-implementation` compatibility gate is neither a capsule nor a durable goal. Shared IR, domain, persistence, assessment, and runtime boundaries are serialized. No capsule implements frontend, provider adapters, live authority, money authority, deployment, credentials, production data, or destructive work.

Each implementation owner uses Terra medium. A capsule may dispatch only its declared disjoint Luna-medium children after freezing shared interfaces. The capsules below declare no children by default; the owner must not invent them.

## 2. Dependency order

1. `phase4-numeric-validity-contract`
2. `phase4-market-truth-domain`
3. `phase4-market-truth-persistence`
4. `phase4-data-requirement-registry-correction`
5. `phase4-data-contract-capability`
6. `phase4-dataset-causality`
7. `phase4-integration-gate`
8. non-executable programme compatibility gate `phase4-implementation`
9. `phase4-review`

The first three capsules are already accepted. The documentation-only `phase4-data-requirement-registry-architecture-correction` must be accepted before the new Terra registry correction becomes ready. The root coordinator must add that executable stage to the programme, change `phase4-data-contract-capability.depends_on` to the registry correction, and add the registry correction to `phase4-implementation.expanded_by` in the same atomic transition; until then every downstream stage remains blocked. Every later executable capsule depends on the prior one. `phase4-implementation` is not a capsule or work goal and opens only after the integration gate. This serial order isolates the accepted registry/resolver repair from capability assessment and avoids overlapping authority.

## 3. Exclusive path ownership

| Capsule | Exclusive product paths | Evidence/test ownership |
| --- | --- | --- |
| Numeric validity | `backend/app/ir/validity.py`, `backend/app/ir/schema.py`, `backend/app/ir/registry.py`, `backend/app/ir/validate.py`, `backend/app/ir/runtime.py` | `backend/tests/test_ir_numeric_validity.py` |
| Market-truth domain | `backend/app/market_truth/__init__.py`, `backend/app/market_truth/identity.py`, `backend/app/market_truth/rulebook.py` | `backend/tests/test_market_truth_domain.py` |
| Persistence | `backend/app/db/models.py`, `backend/migrations/versions/20260817_0036_phase4_market_truth.py`, `backend/research/domain/models.py`, `backend/research/domain/migrate.py`, `backend/research/domain/migrations/0007_phase4_dataset_provenance.py` | `backend/tests/test_phase4_market_truth_persistence.py`, `backend/tests/test_phase4_market_truth_postgresql.py`, `backend/tests/test_schema_migrations.py` |
| Data-requirement registry correction | `backend/app/ir/registry.py`, `backend/app/ir/resolve.py`, `backend/app/market_data/requirements.py` | `backend/tests/test_phase4_data_requirement_registry.py` |
| Data capability | `backend/app/market_data/capability.py`, `backend/app/strategy/admission.py`, `backend/app/core/strategy_admissions.py`, `backend/research/domain/admissions.py` | `backend/tests/test_phase4_data_capability.py`, `backend/tests/test_phase4_capability_admission.py` |
| Dataset and causality | `backend/app/market_data/observations.py`, `backend/app/market_data/candles.py`, `backend/app/backtest/dataset_store.py`, `backend/app/backtest/identity.py`, `backend/app/backtest/cache.py`, `backend/app/backtest/repository.py` | `backend/tests/test_phase4_dataset_manifest.py`, `backend/tests/test_phase4_alignment_causality.py`, `backend/tests/test_phase4_cache_identity.py` |
| Integration gate | no product implementation path | `backend/tests/test_phase4_acceptance_scenarios.py`, `docs/reports/phase4-implementation.md`, `.agent/review-package.json` |

No two open implementation capsules own the same file. The accepted numeric-validity capsule's earlier ownership of `registry.py` is closed; the new correction may edit only the accepted inherited version and must retain its regressions. If implementation discovers that another path must be edited, stop and amend the architecture instead of widening ownership. The registry correction runs the accepted `test_ir_v2_registry_compounds.py`, `test_ir_v2_compound_resolution.py`, `test_ir_v2_identity.py`, `test_ir_v2_legacy_compatibility.py`, and `test_ir_numeric_validity.py` as read-only regressions; it does not own or amend them.

## 4. Capsule outcomes and failure hypotheses

### 4.1 Numeric validity

Add one closed validity envelope to the accepted IR/runtime. Prove invalid comparison is not false, different invalid causes do not collapse silently, domain errors are explicit, fallback is typed and identity-bearing, and only finite valid values serialize. Kill the entry-invalidity guard and a future contributor's NaN coercion guard. Preserve v1 and v2 golden behavior outside opted-in Phase 4 declarations.

Deployment impact: compatible application-contract change; no schema or service change.

### 4.2 Market-truth domain

Add immutable canonical physical instruments, economic selectors, provider mapping intervals, point-in-time records, snapshot identity, reconstruction quality, and data-requirement value objects. Prove token reuse, interval overlap, current-rule substitution, invented strikes/contracts, ambiguous decimal identity, and selector mutation of held identity fail.

Deployment impact: architecture-changing domain contract; persistence remains closed until the next capsule.

### 4.3 Persistence

Persist canonical market truth and owner-scoped dataset provenance through additive execution and research migrations. Prove empty install, supported upgrade, restart, exact heads, digest and interval constraints, owner isolation, secret exclusion, deterministic fixture import, and local backup/clean restore. Do not backfill production or historical attribution.

Deployment impact: migration-required. This capsule owns the complete Phase 4 migration evidence and must stop on an unrehearsed affected path.

### 4.4 Data-requirement registry correction

Harden the accepted `PlatformRegistry` with the one immutable `data_requirement_declarations` closure, deterministic registry snapshot, leaf-bound resolution facts, and canonical plan compiler frozen in design §7. Preserve authored IR identity, implementation identity, v1 behavior, and non-opted v2 behavior. Reject unknown or compound keys, malformed or mutable declarations, forged addresses, missing Phase 4 classifications, unbound parameters, stale snapshots, duplicate requirement ids, and declaration/leaf mismatches.

The focused test owns deterministic input permutations, caller-container mutation after construction, leaf and `NO_DATA` behavior, compound lowering with parent-to-child parameter provenance, missing/unbound/stale/mismatched refusal, v1 golden compatibility, and v2 nonclaim. It must kill and restore at least four critical mutations: omit declarations from the registry snapshot; treat missing declarations as `NO_DATA` or infer from a component name/port; bind a default instead of the lowered child parameter or discard `target_paths`; and omit declaration or registry identity from the resolved graph/plan address.

Deployment impact: architecture-changing application contract; no schema, dependency, configuration, service, provider connection, credential, or runtime process. Evidence can establish only focused locally runnable behavior.

### 4.5 Data contract and capability

Consume only the accepted immutable `DataRequirementPlan`; do not read component descriptors, rebind parameters, infer requirements, or re-resolve the graph. Assess research, paper, and live data capability independently. Extend the sole producer in `backend/app/strategy/admission.py` with the exact Phase 4 wrapper frozen in design §9: the accepted v2 receipt remains the embedded compatibility receipt, while the wrapper binds exact assessment and market/data addresses and receives a distinct complete-receipt address. The two generic persistence seams persist and verify those bytes but never construct or repair the binding. Prove unknown capability, insufficient range/resolution/freshness, historical/live mismatch, owner or mode mismatch, plan/registry mismatch, missing entitlement evidence, provider claim without evidence, base-receipt mismatch, and partial wrapper fail. Kill and restore mutations that omit the plan or registry snapshot from assessment/admission identity, bypass the sole wrapper constructor, or allow a mismatched or stale assessment.

Deployment impact: compatible application/admission change; no provider connection or new service.

### 4.6 Dataset identity and causality

Extend the canonical candle, alignment, research manifest, and existing cache seams. Prove future observations, forming higher-timeframe bars, stale/misaligned legs, silent forward fill, provider/rulebook corrections, adjustment changes, and incomplete cache identities cannot produce an accepted or stale cached answer. Preserve next-bar execution and prefix parity.

Deployment impact: compatible runtime/storage-consumer change; no new service. Storage/capacity claims remain open.

### 4.7 Integration gate

Run the three architecture scenarios and the named refusals against SQLite compatibility and disposable PostgreSQL 16. Verify exact migration heads, clean restart/restore where affected, protected hashes, package/import direction, no frontend or provider implementation, and killed critical mutations. Produce the integrated report and gate JSON. This capsule may fix only its owned gate/test/report files; product defects return to the owning capsule through a correction goal.

Deployment impact: none. It proves bounded local behavior only.

### Durable v2 graph integration correction

Add immutable execution and research v2 graph-version records at migration heads `0037` and `0008`. Persist the complete canonical Phase 4 receipt and capability assessment with each graph version, make graph-plus-receipt writes atomic, reject address collisions with different bytes, and reconstruct the exact persisted assessment authority before use. Dispatch persisted loads by actual format version: keep legacy v1 unchanged, and after full v2 verification return the stable `V2_RUNTIME_UNAVAILABLE` refusal until Phase 5 owns the catalogue, output mapping, Strategy adapter, and worker execution.

The correction evidence must cover SQLite compatibility, isolated disposable PostgreSQL 16 execution and research upgrades/restarts, interrupted research-migration recovery, arbitrary trigger-drift refusal, v1 compatibility, pre-claim/pre-reclaim v2 refusal, and reversible critical mutations. This is additive schema and fail-closed application behavior only. It authorizes no frontend, provider, deployment, production, credential, live, or money work.

Four independent Critical authority findings remain outside this correction: unproved DatasetManifest authority; canonical instrument/economic-underlier identity represented by labels or opaque JSON; collapsed provider/normalized-observation identity; and market-truth/capability rows that do not reconstruct typed authority or reconcile copied fields. They block integration and final-review readiness even when this durable-graph selector passes. The separate High finding that resolved-graph identity omits executable topology is an IR architecture gate before Phase 5 execution or cache authority.

## 5. Verification cadence

- Slice: focused contract tests, realistic negative cases, relevant existing regressions, and a killed mutation for each critical guard changed.
- Migration slice: SQLite compatibility plus disposable PostgreSQL 16 empty install, supported upgrade, restart, restore, exact heads, and integrity.
- Integration: affected Phase 4/backend/research suites once, three scenarios, registry/declaration/plan identity and refusal checks, exact base-v2-to-Phase-4-wrapper construction and two-plane persistence checks, import/package checks, protected hashes, capsule/coverage validation, and `git diff --check`.
- Research JSON parity correction: compile and execute all three object and five array constraints on SQLite and isolated PostgreSQL 16; prove fresh and exact `0009 -> 0010` lifecycles, resumable structural prefixes, exact row/byte/key/foreign-key/index/trigger preservation, typed-manifest process-death reload, arbitrary-drift and downgrade refusal, and killed/restored shape and migration-validation mutations.
- Durable graph correction: exact heads `0037`/`0008`, two isolated PostgreSQL planes, supported restart recovery and drift refusal, atomic graph/receipt persistence, persisted assessment reconstruction, pre-side-effect loader refusal, legacy v1 compatibility, protected hashes, and byte-restored mutations.
- Authority transaction correction: retain the failing ADV-003 counterexample; prove `caller_owned_savepoint` on SQLite compatibility and disposable PostgreSQL 16 with no prior SQL, a clean SELECT, prior caller writes, explicit and externally owned roots, proved recursive nesting, unproved external-SQLite-savepoint refusal, unrelated pending work, flush failure, DBAPI commit refusal plus rollback, rollback failure, exact retry and collision, process restart, and all seven real seams. Kill and byte-restore physical-root establishment, marker cleanup, nesting refusal, the no-commit/rollback/close rule, and one adoption guard per seam before rerunning transitive selectors.
- Research-receipt authority correction: call the existing research receipt-and-graph verifier from the actual complete-current loader chain before dataset/assessment verification; prove missing, tampered, wrong-owner, and cross-plane substitutions through the loader on SQLite and disposable PostgreSQL 16; run the loader before diagnostics; kill and byte-restore invocation and order guards; then rerun every affected consumer and package claim.
- Review: one independent Sol-high goal returns separate `SPEC` and `QUALITY` verdicts. It may use one focused recheck; a second rejection stops for replanning.

Full command output belongs under each capsule's ignored `.agent/runs/<capsule>/` directory through `.codex/scripts/run_logged.py`.

## 6. Deployment evidence ownership

The persistence capsule owns Phase 4 schema, migration, deterministic import, local restore, and integrity evidence. The registry correction owns declaration closure, registry snapshot, binding, deterministic plan, v1/v2 compatibility, and closed-refusal evidence. The capability capsule owns the sole Phase 4 wrapper construction in the existing strategy-admission authority plus generic two-plane persistence, and the capability and dataset capsules own bounded query, ownership, secret-exclusion, assessment/admission, cache, and refusal evidence. The integration gate owns the consolidated deployability matrix and exact unresolved assignments:

- Phase 6: configuration validation, services, readiness, activation preflight, rollback authority;
- Phase 7: subscription/storage/compute ceilings and degradation;
- Phase 8: truthful readiness UI;
- Phase 9: credentials, adapter conformance, fallback, rate/network behavior;
- V1 release: locked build, production-shaped three-plane install/upgrade, backup/restore, TLS/roles, security, observability, capacity, rollback, and smoke.

No capsule may translate local PostgreSQL evidence into release-deployable or production-rehearsed status.

The durable graph correction is classified `additive-execution-and-research-schema-with-fail-closed-v2-runtime`. Its strongest bounded claim is the named locally runnable gates. The authority-chain correction and a new accepted review package remain prerequisites to Phase 4 integration readiness.

The research JSON parity correction is classified `additive-research-schema-json-shape-parity-repair`. It advances the research head `0009 -> 0010` without changing accepted `0009`, execution schema, or runtime authority. Production-shaped upgrade, rollback, backup/restore, readiness, and deployment remain owned by Phase 6 and V1 release review.

The research-receipt authority correction is classified `schema-free-phase4-research-receipt-authority-hardening`. It changes verifier composition only. Migration heads, dependencies, services, configuration, providers, frontend, infrastructure, runtime availability, and deployment artifacts remain unchanged.

## 7. Owner gates and nonclaims

Stop for owner direction before frontend implementation, provider implementation, authoritative live IR, material live sizing/routing/risk/execution changes, credentials, VPS, production data/use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.

Phase 4 acceptance will not claim complete provider breadth, real-provider conformance, resource capacity, production readiness, production rehearsal, deployment, or live authority.

## 8. Authority-correction serial route

The independent check supersedes the earlier completion route for CUR-C1 through CUR-C4 and CUR-H2. Run these capsules one at a time. A later capsule cannot start until its dependency has direct evidence and no open Critical finding in its boundary. Owners are fresh Sol-medium tasks. No capsule has a child assignment; a future owner may add one Luna-max mechanical child only by first updating its capsule with an exact non-overlapping assignment.

| Order | Capsule | Findings and outcome | Exclusive product and test ownership |
| --- | --- | --- | --- |
| 1 | `phase4-resolved-topology-identity-correction` | Close CUR-H2. Address every lowered node, edge, bundle, boundary, graph input/output/default, binding, member type, and provenance. Prove fresh-process receipt refusal for topology-only mutations. | `backend/app/ir/resolve.py`; `backend/app/ir/v2_graph_versions.py`; `backend/tests/test_phase4_resolved_topology_identity.py`. |
| 2 | `phase4-canonical-market-identity-correction` | Close CUR-C2, CUR-C3, and CUR-H1. Add exact underlier identity, separate entity/product/contract, typed raw and normalized observations, canonical bytes, execution persistence, and migration `0038`. It installs the complete execution storage shape the next loader consumes; it grants no C4 authority. | `backend/app/market_truth/identity.py`; `backend/app/market_data/observations.py`; `backend/app/db/models.py`; `backend/migrations/versions/20260817_0038_phase4_authority_facts.py`; `backend/tests/test_phase4_canonical_market_identity.py`; `backend/tests/test_phase4_authority_execution_migration.py`. |
| 3 | `phase4-typed-market-authority-correction` | Close CUR-C4 against the installed schema. Reconstruct typed truth, conformance, profile, and assessment facts; recompute results; reconcile copied columns; refuse tokens and generic rows. | `backend/app/market_truth/rulebook.py`; `backend/app/market_truth/authority.py`; `backend/app/market_data/capability.py`; `backend/app/market_data/authority.py`; `backend/tests/test_phase4_typed_market_authority.py`. |
| 4 | `phase4-dataset-assessment-authority-correction` | Close CUR-C1. Add typed segments and `dataset-manifest/2`; nine closed role-specific dependency authorities with mandatory loader dispatch; byte/coverage proof; execution migration `0039`; amended research migration `0009`; authoritative assessment/admission loading; and transitive result/cache invalidation. Preserve the acyclic construction order: dataset manifest first without an assessment address, assessment second with the exact manifest address, then admission/cache with both. | `backend/app/backtest/dataset_store.py`; `backend/app/backtest/cache.py`; `backend/app/market_data/dataset_authority.py`; `backend/app/market_data/observations.py`; `backend/app/strategy/admission.py`; `backend/app/core/strategy_admissions.py`; `backend/app/db/models.py`; `backend/migrations/versions/20260818_0039_phase4_dataset_dependency_authority.py`; `backend/research/domain/models.py`; `backend/research/domain/migrate.py`; `backend/research/domain/migrations/0009_phase4_dataset_authority.py`; `backend/research/domain/strategy_admissions.py`; `backend/tests/test_phase4_dataset_assessment_authority.py`; `backend/tests/test_phase4_dataset_dependency_authority.py`; `backend/tests/test_phase4_authority_execution_migration.py`; `backend/tests/test_phase4_authority_research_migration.py`. |
| 5 | `phase4-authority-integration-gate` | Recheck the full invalidation map through real two-plane process death, SQLite and disposable PostgreSQL parity, canonical scenarios, cache/result changes, partial writes, and stable pre-runtime refusal. It patches no product. | `backend/tests/test_phase4_authority_integration.py` and its own evidence directory only. |

Path ownership is serially exclusive: no two capsules edit a shared path at once. The 2026-08-18 root-approved CUR-C1 owner-gate amendment reopens only `app/market_data/observations.py`, `app/db/models.py`, and `tests/test_phase4_authority_execution_migration.py` after their prior owners froze and were accepted; the CUR-C1 owner must rerun their affected contracts, and the integration gate must revalidate dependent evidence. Shared-source defects otherwise return to the owning earlier capsule; the integration gate does not patch them. Migration order is execution `0037 -> 0038 -> 0039` and research `0008 -> 0009 -> 0010`; `0010` is the forward JSON-shape repair and accepted `0009` remains immutable.

Every capsule runs focused tests, architecture/source-map checks, protected hashes, scoped diff, and its design §13.3 mutations. Migration owners also run model-DDL parity, empty install, supported upgrade, interrupted-upgrade restart, exact-head and destructive-downgrade refusal on SQLite and isolated PostgreSQL 16. Each capsule writes full output under `.agent/runs/<capsule>/owner/` and records deployment impact. The gate runs no provider, frontend, deployment, production, credential, live, or money action.

After immutable `phase4-final-review-4` returned SPEC FAIL and QUALITY FAIL, the next route is strictly `phase4-research-receipt-authority-architecture-correction` -> `phase4-research-receipt-authority-correction` -> `phase4-final-review-5`. The implementation owns the bounded affected integration selector and official package rebuild after product/test freeze, so no separate integration capsule is required. If that ownership proves insufficient, implementation stops for a new architecture decision. Final review 5 stays blocked until root accepts the correction and exact package. Phase 4, the foundation audit, Phase 5, deployment, live authority, and money authority remain blocked.

Design §13.3 defines 27 individually classified rows, `ADV-001` through `ADV-027`. Each implementation capsule's `adversarial_rows` field is its exact inherited subset; the integration gate inherits the complete set. Evidence is row-addressed and must name the real seam, database/process boundary, expected refusal or identity change, observed result, and artifact address. A grouped test or generic mutation-matrix PASS cannot satisfy multiple rows without separate observations. Architecture validation must fail on a missing ID, duplicate matrix ID, out-of-range ID, empty primary ownership, capsule row outside its design ownership, missing integration row, or design row absent from every correction capsule.

Phase 4 `ADV-006` is fail-closed public-seam containment only. With explicit current authority context, the real v2 reclaim-dispatch seam must verify the complete current chain and reach exact `V2_RUNTIME_UNAVAILABLE` before claim, reclaim, provider, cache, worker, claim-token, result, broker, order, or money side effects; stale or missing authority must refuse earlier. This row remains one of exactly 27 and may be `FULL` only for that containment. It does not prove successful v2 reclaim.

The serial correction route inserts
`phase4-reclaim-authority-context-architecture-correction` and then
`phase4-reclaim-authority-context-correction` before the fresh matrix rerun.
The implementation owns only the exact candidate selector and explicit-id
conditional reconcile/claim seams, the typed `ReclaimAuthorityContext`,
lifespan wiring, the two existing loader call sites, and the existing
receipt-reconstruction/loader return path. Startup
passes the current registry and existing synchronous research `sessionmaker`;
one owner dispatch owns one lazy synchronous `Session` and one aware cutoff shared by both
loader sites. The exact persisted receipt plus that registry internally yields
the only canonical plan. A caller cannot pass a plan.

The implementation must remove the current
`dispatch_all_reclaimable -> reconcile_stale_runs` mutation-before-authority
order. `dispatch_reclaimable` closes every pending, expired-running, or
claimless-running candidate in one transaction. SQLite takes the existing
admission-scoped `BEGIN IMMEDIATE` reservation before enumeration; PostgreSQL
selects the exact candidate rows `FOR UPDATE`. A locked snapshot records every
mutation predicate and preflights all v2 rows. Startup reconciliation and claim
conditionally mutate only explicit classified legacy ids with every predicate
preserved; no broad owner update or fresh selector is allowed. A concurrent
insert stays outside the closed ids, while a state, owner, admission,
cancellation, token, or expiry transition yields zero affected rows, rollback,
and refusal. Direct dispatch retains its legacy no-pre-reconcile policy; startup
supplies the internal explicit-id policy. Race regressions cover
insert-after-enumeration and each transition class, and killed mutations restore
a broad update, remove the lock, or drop a predicate. Any v2 row in the
deterministic snapshot causes owner-level head-of-line refusal and zero mutation
for every row; only a locked all-v1 set may enter the byte/row-compatible legacy
path. Missing or
disabled research refuses before session creation and every
named side effect. Complete current authority reaches exact
`V2_RUNTIME_UNAVAILABLE` before claim. The implementation remains schema-free,
adds no provider or service, and cannot enable `P5-ADV-006-RUNTIME`.

ADV-003 inserts two more strict serial stages after the reclaim correction and
before the fresh matrix: `phase4-authority-transaction-architecture-correction`
then `phase4-authority-transaction-correction`. The architecture freezes one
`caller_owned_savepoint(session, *, scope)` API in `app/db/concurrency.py` and
classifies all seven current savepoint seams. The implementation has exclusive
ownership of that helper and the execution admission, research admission,
research dataset authority, two backtest repository, public computation, and
ledger snapshot call sites, plus exact focused tests. It changes no schema,
migration, package, configuration, dependency, service, provider, frontend,
deployment, production, live, money authority, or ledger business rule.

The implementation must establish and verify a physical outer transaction on
the same connection before every nested savepoint, bind the proof to the live
root transaction, clear it only when that root ends, and refuse unproved
external SQLite nesting. The helper owns only its savepoint and never commits,
rolls back, closes, invalidates, retries, or replaces caller resources. The
`outbox.writer` wrapper remains the ledger unit-of-work owner, while
`write_snapshot` obtains direct physical-boundary proof before its nested
snapshot/event write. Root acceptance of the implementation unblocks only one
fresh full matrix rerun; no historical matrix result receives completion
credit.

The successful lifecycle remains the mandatory `P5-ADV-006-RUNTIME` obligation: claim, lose ownership, reclaim through the public seam after process death, reload the exact current authority chain, fence the stale claimant, and let only the current claimant finalize exactly once. Phase 5 architecture must generate one exclusive capsule for that identifier. It must depend on accepted `phase5-graph-paper-attribution-schema`, prove direct SQLite and disposable PostgreSQL 16 process-restart and adversarial behavior, and close before any v2 claim, reclaim, worker, result, cache, broker, order, or money consumer is reachable. The schema is necessary and non-enabling; a generic dynamic implementation placeholder does not satisfy the named-capsule requirement.

CUR-H3 has a hard pre-use dependency on `phase5-graph-paper-attribution-schema`, owned by a fresh Sol-medium task. Until it closes, graph-to-paper execution, v2 job claim/reclaim, graph-address cache authority, deployment binding, and every money record are forbidden. Schema acceptance alone does not open those uses; `P5-ADV-006-RUNTIME` must also close before the named runtime consumers become reachable. CUR-H4 has a hard pre-use dependency on `phase6-generated-strategy-version-lineage`, also owned by a fresh Sol-medium task. Until it closes, generated-strategy replay, promotion, current-slot replacement, paper/live assignment, activation, deployment, and release evidence are forbidden. It must close before the first Phase 6 activation or deployment-binding capsule.

## 9. Foundation migration and numeric correction route

Run the native-oracle correction as three fresh serial implementation capsules,
then a separate mutation capsule. Never reactivate the exhausted monolithic
implementation or combined projection capsules:

1. `phase1-4-foundation-research-migration-native-state-contract-core` owns only
   the immutable scalar, declaration, expected-state, receipt, rejection,
   process, owner, catalog, sequence, and attestation contracts. Root must
   accept its exact hashes before observer work starts.
2. `phase1-4-foundation-research-migration-native-state-observer` consumes the
   accepted core read-only and owns only the SQLite and PostgreSQL builders,
   distinct-process observers, comparators, and focused observer tests. Root
   must accept its exact hashes before obligation work starts.
3. `phase1-4-foundation-research-migration-native-state-obligation-evidence`
   consumes the first two nodes read-only and owns the sealed 24-DATA and 39-CAT
   registry, four complete baseline envelopes, 174 typed receipt slots, and all
   omission, dead-binding, and wrong-binding rejection families. Root must
   accept its exact hashes before mutation work starts.
4. `phase1-4-foundation-research-migration-native-mutation-attestation`
   consumes those accepted state bytes read-only, executes 24 DATA obligations
   across both corpora and dialects for 96 receipts plus 16 SQLite and 23
   PostgreSQL CAT obligations across both corpora for 78 receipts, proves exact
   reopen rejection and restoration, and seals `ClaimAttestation`. Root must
   accept all 174 receipt slots before runtime work starts.
5. Continue serially through runtime correction, evidence integration, numeric
   ingress correction, transitive revalidation, and one independent critical
   review. No successor patches an accepted dependency.

All four implementation nodes have parallel budget zero, use fresh
Terra-medium owners, and allow one initial patch plus one evidence-backed
repair. A second failure of one material defect stops the node for fresh
recovery; no prior owner resumes and no third patch begins. All full command
output goes to ignored evidence through `run_logged.py`. The narrow SQLite and
disposable PostgreSQL 16 selector already ran and passed; that pass proves
harness availability only.

Foundation audit A-01 through A-05 invalidate only the dependent migration and
raw OHLCV claims named by the audit map. The immutable audit binds this route by
report SHA-256
`cec0bdc931632b9297d733fa58f6057a60b32820882af5e90b3184fd88d54d6d`
and manifest SHA-256
`4933505aa93b9a9fc03a08617b933944c28a409269602f53d9060d563f2143c5`.

Run these stages serially:

The SQLite history-authority recovery returns
`RECOVERY_ARCHITECTURE_ACCEPTABLE` for a narrow matrix, but the route remains
inactive. Root must accept its report, manifest, 13-row ledger, transitive
source-closure map, support matrix, final capsule bytes, audit freeze, and
protected hashes. No implementation owner may widen that compatibility
decision.

1. root-owner acceptance of `phase1-4-foundation-sqlite-history-authority-recovery`
2. root confirmation that it supersedes the blocked SQLite portion of `phase1-4-foundation-research-migration-state-contract-recovery`
3. root-owner acceptance of `phase1-4-foundation-research-migration-projection-repeated-failure-recovery`
4. `phase1-4-foundation-research-migration-projection-correction`, fresh assignment `foundation_research_migration_native_round_trip_owner`
5. `phase1-4-foundation-research-migration-runtime-correction`, fresh assignment `foundation_research_migration_runtime_owner_2`
6. `phase1-4-foundation-research-migration-evidence-integration`, fresh assignment `foundation_research_migration_evidence_attestation_owner`
7. `phase1-4-foundation-numeric-ingress-correction`
8. `phase1-4-foundation-transitive-revalidation`, fresh assignment `foundation_transitive_revalidation_owner_2`
9. one `phase1-4-foundation-critical-review`

The projection owner alone creates the sole literal SQLite target authority at
`backend/research/domain/migrations/sqlite_catalog_contract.py` and the accepted PostgreSQL `0010` catalog at
`backend/research/domain/migrations/postgresql_0010_contract.py`; the sole
SQLite fixture consumer at `backend/tests/foundation_sqlite_catalog_builder.py`
and the
fixture builder at `backend/tests/foundation_postgresql_0010_builder.py`
import only their matching contract and accept arbitrary contract-valid user and
sequence state. At least two materially different deterministic synthetic
corpora run under each catalog, but their values define no schema, historical
fact, or user fact. Expected state is derived only from caller rows, requested
sequence state, and the frozen per-dialect ordered column/type declarations.
Observed rows and inventories cannot feed the expected function.
The projection-owned product contracts also declare the exact forward `0011 =
0010 + guard-only delta` targets. The runtime owner cannot change either
contract or builder. It owns only the runner, the `0011` migration
implementation, and a dedicated runtime test, removes current-metadata
historical derivation, and makes SQLite unversioned and `0001` through `0009`
and PostgreSQL `0003` through `0009` refuse before writes. SQLite supports only
empty direct construction, exact or enumerated-five-guard `0010`, and exact
`0011`. The migration consumes and must match the projection declaration; its
DDL is not a second authority. The integration owner changes only existing matrix fixtures and
evidence and proves the full supported matrix, refusal, restart, preservation,
and killed mutations. No owner may use current-model rewind, current
metadata, SQLite translation, a later-head dump, invented facts, user-data
rebuild, dependency or configuration changes, or execution-schema edits.

Projection, runtime, and integration tests apply dialect-exact predicates.
SQLite validates storage class and affinity and preserves textual JSON and BLOB
bytes. PostgreSQL preserves text/varchar JSON bytes; catalog-declared json or
jsonb uses its native database representation, not original input-text claims.
Sequence inspection never advances a sequence. Direct guard attempts run only
inside rollback-only savepoints or subtransactions, commit no test write, and
must leave the complete preflight digest byte-identical.

The next projection owner keeps both product declarations unaccepted, replaces
both builders and the projection test suite, and executes every one of the 24
named table mutations for each corpus and dialect. Each effective mutation must
commit, survive close/dispose/fresh-process reopen, change the expected-versus-
observed digest, produce its exact failure code, restore, and recover the exact
baseline digest. Immutable tables use valid extra-row INSERTs with guards
enabled; a refused statement receives no credit. The catalog matrix separately
covers table/column type-null-default, PK/FK/unique/check, index/predicate,
sequence state and serial binding, function body/identity/language, trigger
table/event/function, and extra/missing objects. A machine claim attestation
binds both corpora, both dialects, marker/version, exact sequence values,
24-table receipts, mutations, reopen receipts, commands, logs, and final hashes;
an independent validator derives the obligation set rather than trusting the
claim.

The retained `0007`/`0008` edits remain
`KEEP_UNACCEPTED_FOR_NEXT_CAPSULE` at the exact hashes in design §14.6. They are
read-only in all three stages and receive no credit until integration and
independent review. The broad
`phase1-4-foundation-research-migration-correction` capsule is superseded by
these three serial capsules.

Authority ledger SHA-256
`32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1`
returns `EXPLICIT_MATRIX_REVISION_REQUIRED`. The revision remains inactive
until root-owner architecture acceptance. No repository tag, accepted release
record, deployment record, production record, or external promise was found
for PostgreSQL `0003` through `0009`. The recovery capsule's conditional gate
requires root and user direction only if later evidence shows that the revision
could strand such a state. That evidence would stop the route immediately.
Without it, root acceptance is the exact architecture gate.

The numeric owner has exclusive product ownership of
`backend/app/market_data/candles.py`,
`backend/app/backtest/dataset_store.py`, and
`backend/app/backtest/sweep.py`, plus the named focused tests. It introduces one
source-type-before-coercion OHLCV rule, routes each assigned ingress through it,
and proves boolean refusal before dataset identity or execution-price effects.
It cannot change valid finite bytes, addresses, causal rules, strategy results,
sizing, routing, execution behavior, providers, or schema.

After all four serial correction owners freeze product and test bytes, the root-owned transitive stage
reruns the exact invalidation map, mutations, packages, and protected hashes.
It may edit only its evidence and `.agent/review-package.json`; a product or test
failure routes back to the owning correction. One independent critical reviewer
then reads the frozen package and returns migration and numeric verdicts without
patching anything. Historical PASS and FAIL records remain immutable.

This route has `migration-required` deployment impact because research head
advances to `0011` and both dialect matrices explicitly change after root
acceptance. Local SQLite and disposable PostgreSQL 16 passes prove only locally
runnable behavior.
Phase 6 and the V1 release gate retain production-shaped clean install and
upgrade, backup and clean restore, configuration, roles, health,
rollout/rollback, and exact-build smoke ownership. No stage here authorizes
deployment, production access, frontend, credentials, provider or broker work,
live authority, or money behavior.
