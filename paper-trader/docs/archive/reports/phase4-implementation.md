# Phase 4 implementation correction report

## Disposition

The immutable first review remains a failed verdict. Its SHA-256 is
`ce6ed8c4d8a0a0fd0c93984c1c195d70704ce5ac7cc109fedd06df466ba61a7a`.
This bounded correction adds direct regressions for P4-SPEC-001 through
P4-SPEC-007 and P4-QUALITY-001. It does not accept Phase 4. Only the separate
`phase4-review-recheck` may decide whether the findings are closed.

The corrected local interfaces now:

- normalize supported array/series VALID numeric payloads into recursively
  immutable finite scalars and tuples;
- enforce one closed uppercase physical-instrument matrix and one exact
  `nearest_eligible_weekly_call` selector schema;
- defensively own snapshot records and apply the snapshot's recorded-at cutoff
  when selecting a historical rule or correction;
- accept a capability assessment only when the canonical assessment seam minted
  its private authority receipt, including the exact assessment time;
- reconstruct the persisted Phase 4 wrapper through the existing admission
  authority, derive one internal result binding, and carry it through the
  existing request JSON, reclaim, worker, dataset, result-address, and
  owner-local cache seams; and
- exercise three different composed local scenarios instead of relabelling one
  generic fixture.

Legacy v1 and non-opted-v2 admission and result identity retain their existing
path. A Phase 4 run refuses a missing, malformed, stale, caller-forged, or
owner-mismatched binding before provider construction or cache access.

## Focused corrected evidence

- `.agent/runs/phase4-review-correction/owner_integration/immutable-first-verdict-counterexamples.log`
  hash-checks the immutable failed verdict and all eight retained counterexamples.
- `.agent/runs/phase4-review-correction/phase4_numeric_truth_regressions/report.md`
  records 46 passing numeric and market-truth regressions.
- `.agent/runs/phase4-review-correction/phase4_capability_cache_regressions/report.md`
  records 66 passing capability, admission, reclaim, real sweep, and cache-path
  regressions, including cold/warm reuse and owner isolation.
- `.agent/runs/phase4-review-correction/phase4_acceptance_scenario_regressions/report.md`
  records four passing tests: three substantive scenarios and the existing
  refusal chain.
- `.agent/runs/phase4-review-correction/owner_integration/phase4-data-capability-compat-restored.log`
  records 23 passing compatibility tests after preserving established malformed
  assessment refusal order.
- `.agent/runs/phase4-review-correction/owner_integration/focused-affected-final.log`
  records the combined 139-test focused affected selector. No broad backend or
  research suite was rerun for confidence.
- `.agent/runs/phase4-review-correction/phase4_correction_mutation_evidence/report.md`
  records ten counted critical-guard mutations. Every counted mutation failed
  its exact selector, was byte-restored, passed after restoration, and matched
  the captured baseline SHA-256. One exploratory multiplier-only probe did not
  kill its selector and is explicitly excluded from the count.
- `.agent/runs/phase4-review-correction/owner_integration/migration-heads.log`
  records unchanged execution and research heads `0036` and `0007`.

The correction adds no schema, migration, service, dependency, configuration,
provider, broker, credential, infrastructure, frontend, production, deployment,
money, or live-authority change. Its deployability classification is
`compatible-application-and-research-identity-hardening-no-schema-or-service-change`.

## Scenario boundary

The equity scenario composes distinct NSE and NASDAQ physical identities,
sessions, completed observations, manifests, Phase 4 bindings, cache identities,
and persisted receipt bytes while reusing one authored graph. The weekly-option
scenario uses observed historical listed contracts with exact expiry, strike,
right, and multiplier, preserves the held physical identity after selector
intent changes, and refuses unavailable open interest and insufficient depth.
The cross-market scenario composes two providers, markets, timezones, and
sessions and checks completed observations, age, skew, forming/future bars,
closed-session, stale, unavailable, and missing states.

These are local contract fixtures. They do not implement or claim selector
resolution, a real provider feed, order placement, entry/exit runtime policy,
production migrations, a release rehearsal, capacity, deployment readiness, or
production readiness.

## Remaining authority and nonclaims

The first failed verdict remains immutable. Root still owns exact package
regeneration and the one focused recheck. This correction grants no frontend,
provider, credential, VPS, production-data/use, deployment, Phase 5, release,
paper/live money, sizing, routing, risk, execution, or live-authority action.

## Durable v2 graph integration

The bounded durable-graph correction adds immutable execution and research graph-version records and advances their migration heads to `0037` and `0008`. The record binds exact owner, authored document, resolved graph, implementation closure, registry snapshot, complete canonical Phase 4 receipt, and persisted capability assessment. Graph-version and receipt persistence is atomic, and an existing address is reusable only for byte-identical canonical facts.

The persisted loader now dispatches by actual format version. Legacy v1 retains its established path. The Phase 4 branch requires an explicit research session, plan, and aware cutoff, then invokes the existing complete `require_phase4_current` verifier before returning the stable `V2_RUNTIME_UNAVAILABLE` refusal. It neither opens a research session nor infers plan or time. Contextless deployment, runner, broker, enqueue, retry, reclaim, pinned-worker, cache, and job callers remain fail closed before side effects. No catalogue, output mapping, Strategy adapter, or v2 worker runtime is implemented; those remain Phase 5 work.

The restart claim is exercised across a real process boundary: one process writes the complete receipt and graph records to separate durable execution and research databases and exits; a fresh interpreter independently reconstructs the registry, reloads and verifies both planes, and reaches `V2_RUNTIME_UNAVAILABLE` through the real execution loader. Same-interpreter JSON round trips and monkeypatched consumers are not used as substitutes for that lifecycle evidence.

Migration evidence covers local SQLite compatibility and isolated disposable PostgreSQL 16 execution and research planes. Research `0008` supports exact interrupted-upgrade restart recovery and refuses missing or altered triggers and other arbitrary partial-schema drift. Destructive downgrade is refused. This work is classified `additive-execution-and-research-schema-with-fail-closed-v2-runtime`; it is not deployment, production rehearsal, release deployability, or production readiness.

Final independent checking accepts the historical content-address/graph-address repair only for the bounded durable graph, receipt, fresh-process verification, and refusal path. It identifies four unresolved Critical authority-chain defects outside this correction: DatasetManifest is accepted by address without canonical owner/content/coverage/provenance proof; canonical instrument and economic-underlier authority remains label/opaque-JSON shaped; provider and normalized observations lack separate durable identity; and market-truth/capability rows do not reconstruct typed authority or reconcile copied fields. It also identifies a High resolved-graph identity defect because the address omits execution-relevant topology. The Criticals block Phase 4 integration and final-review readiness, and the topology defect blocks Phase 5 execution or cache authority. Durable persistence does not close or weaken those findings and grants no frontend, provider, credential, deployment, live, or money authority.

## Authority-foundation architecture correction

The architecture verdict is `KEEP + HARDEN`. The correction retains one Component IR v2, resolver, registry, canonical hash, admission path, research lineage, and cache identity. It freezes closed versioned facts and verified loaders for canonical physical instruments and exact underliers, provider entities/products/owner contracts, provider aliases, raw provider observations, normalized observations, market truth, conformance, capability profiles and assessments, dataset bytes/segments/manifests, and topology-complete resolved graphs.

The serial corrections now have bounded local acceptance: CUR-H2, CUR-C2/C3/H1, CUR-C4, and CUR-C1. The accepted migration heads are execution `0039` and research `0009`. Dataset construction is acyclic: the manifest closes over typed dependencies without an assessment address, the assessment binds the final manifest, and admission/cache reload and compare both. The no-product-patch authority integration gate is active; Phase 4 and review readiness remain open until that gate, root audit, a fresh package, and independent dual PASS complete.

Every earlier PASS that depends on typed dataset authority, exact underliers, raw/normalized provenance, truth/capability reconstruction, or topology-complete identity remains `STALE/REQUIRES RECHECK` until the active integration gate provides direct transitive evidence. CUR-H3 blocks graph-to-paper/runtime/cache/deployment/money consumers until `phase5-graph-paper-attribution-schema`. CUR-H4 blocks generated replay/promotion/assignment/activation/deployment/release consumers until `phase6-generated-strategy-version-lineage`. This documentation does not change runtime, provider, frontend, deployment, live, or money behavior and does not make Phase 4 review ready.

The corrected adversarial contract has 27 separate classified cases, `ADV-001` through `ADV-027`, rather than grouped examples. Every case names exact Phase 4 primary owner capsules and a required real-path refusal, identity change, or recovery observation. Each mandatory serial capsule carries its exact row subset in frontmatter, and the integration gate carries all 27. No case is deferred to a later phase. This is an architecture allocation only; the cases remain unproved until the named capsules produce row-addressed evidence.

## Capability-assessment receipt identity correction

The stopped authority integration counterexample was real: the receipt bound the
tagged `capability-assessment/2` authority address while embedding the legacy
`assessment.to_dict()` projection, and reconstruction hashed that incomplete
projection. The correction freezes one exact typed authority envelope from the
assessment's canonical bytes. Receipt construction, the execution writer, the
research writer, and fresh-process reconstruction now verify that same closed
envelope and its tagged address. There is no legacy-hash fallback, equivalence
escape, generic dispatcher, second identity, or migration.

Focused current-interface evidence is under
`.agent/runs/phase4-capability-assessment-receipt-correction/owner/`. It covers
direct canonical-byte equality, both persistence planes, process death and a
fresh interpreter, exact post-verification `V2_RUNTIME_UNAVAILABLE`, malformed
and incomplete envelopes, wrong schema, algorithm, version, address, owner,
mode, dependency, result, and coverage cases, and counted mutation kills with
byte restoration. The integration-owned test remained unchanged. Old or
incomplete local receipt forms refuse closed and must be recreated explicitly;
the correction does not silently bless or migrate them.

This work is classified
`schema-free-application-receipt-identity-hardening`. It changes no schema,
migration head, dependency, configuration, service, provider, broker,
credential, infrastructure, frontend, deployment, production, live, or money
authority. Its local SQLite and fresh-interpreter evidence does not accept Phase
4, make an official review package, authorize runtime enablement, prove release
deployability, rehearse production, or authorize deployment.

## Authority timestamp normalization correction

The PostgreSQL 16 counterexample was caused by aware canonical instants crossing
timezone-naive SQL columns through driver-dependent conversion. One shared
temporal contract now converts canonical values to UTC before removing timezone
information, validates loaded SQL values as already naive, and never treats a
loaded wall time as local time. Provider contract and alias intervals, alias
overlap, truth, conformance, profile, assessment, provider and normalized
observations, and all nine dataset-dependency `recorded_at` columns use that
contract. Canonical serialization and content-address semantics are unchanged.

Focused evidence is under
`.agent/runs/phase4-authority-timestamp-normalization-correction/phase4_authority_timestamp_owner/`.
The SQLite and disposable PostgreSQL 16 selectors use positive and negative
source offsets, explicitly assert PostgreSQL `Asia/Kolkata`, persist all named
facts, terminate the writer context, reload them in a fresh interpreter, and
produce identical canonical bytes and addresses. The same selector records
one-hour copied-column and canonical-document refusal for each named family and
each of the nine tables, malformed aware-row refusal, and alias-overlap refusal.
Three reversible mutations show that UTC conversion, loaded-row validation, and
copied-time comparison are causally required; restored hashes match the captured
baseline exactly.

## Research JSON-shape parity correction

The research constraint vocabulary now separates exact JSON objects from exact
JSON arrays across SQLite and PostgreSQL. The three graph, admission, and legacy
manifest document columns require objects; the five typed `dataset-manifest/2`
collection columns require arrays. Forward migration `0010` leaves accepted
`0009` unchanged, validates exact old/new or resumable-prefix state, preserves
canonical bytes and relational contracts, and refuses arbitrary drift and
destructive downgrade.

Focused evidence under
`.agent/runs/phase4-research-json-shape-parity-correction/phase4_research_json_shape_owner/`
covers the eight-site compiled and real-row matrix, SQLite and disposable
PostgreSQL 16 fresh/upgrade/interruption lifecycles, exact byte and row hashes,
keys, foreign keys, indexes, immutable triggers, typed-manifest process-death
reload, the original two-plane selector, and reversible killed mutations with
exact restoration. The bounded result is `CORRECTED` for DP-007 only. It does
not accept Phase 4, complete the integration gate, establish production
deployability, or authorize runtime, provider, credential, frontend,
deployment, live, or money work.

The preserved pre-edit integration log fails while the raw segment reloads its
provider contract. With this correction that path passes and the same selector
continues to a later inherited research-manifest JSON constraint failure outside
this capsule's allowed paths. That later failure is not corrected or accepted
here. The deployment classification is
`schema-free-cross-database-authority-timestamp-hardening`: no schema, migration
head, dependency, configuration, service, provider, broker, credential,
infrastructure, frontend, runtime, deployment, production, live, or money
authority changes. This evidence does not accept Phase 4, complete the authority
integration gate, refresh the review package, or establish release deployability
or production readiness.

## Loader authority recovery correction

The sole `load_verified_admission` Phase 4 branch now requires an explicit research session, execution plan, and timezone-aware cutoff. It reconstructs the persisted receipt and calls the existing `require_phase4_current` verifier itself. The loader reaches `V2_RUNTIME_UNAVAILABLE` only after the persisted dataset, capability assessment, graph, receipt, owner, plan, registry, and cutoff bindings verify. Missing context returns `PHASE4_CONTEXT_REQUIRED`; missing or stale authority returns its authority refusal before the terminal runtime boundary. The legacy v1 call shape, verified return, persistence, worker serialization, result, and cache contracts remain unchanged.

Current-byte regressions dynamically cover the contextless production deployment, runner, broker, enqueue, retry, reclaim, pinned-worker, cache, and job consumers. Each refuses before its relevant provider, cache, job, worker, evaluator, activation, signal, order, or money side effect. Static call-site mapping supports those dynamic tests but does not substitute for them.

ADV-001 through ADV-027 were rerun as separate verbose selectors with machine-readable command, canonical cwd, timestamp, selected and collected node IDs, exit status, observation, and source mapping. The semantic audit against design section 13.3 classifies only ADV-001 as `FULL`; ADV-002 through ADV-027 are `RESIDUAL-GAP`. Those 26 open normative gaps block Phase 4 and final-review readiness even though this bounded loader-evidence capsule can stop. ADV-019 is corrected through the retained fresh-process integration test: the real loader receives persisted research authority, the registry, an aware cutoff, and an explicitly tampered plan; it refuses that stale binding with `RECEIPT_STALE` before the current-plan companion completes authority verification and reaches `V2_RUNTIME_UNAVAILABLE`. The older contextless topology observation remains only missing-context guard evidence and is not used as stale-receipt proof.

Six controlled mutations killed the missing-context guard, the `require_phase4_current` invocation, dataset verification, assessment verification, terminal-refusal ordering, and an enqueue no-side-effect guard. Every product and test byte was restored to the frozen hash map before the final focused selector. The immutable `phase4-final-review-3` verdict remains the historical SPEC/QUALITY FAIL at SHA-256 `845a0675a2245838f9ddf2a9280bcb82981e60a1db5dbcd3f2ba5cf5220e584c`; this correction supplies new evidence and does not rewrite or relabel that verdict.

Transitive invalidation removes the earlier invocation-only loader result, helper-adjacent integration claim, aggregate ADV evidence, inferred H3/H4 containment, and dependent completion claims. Revalidation now runs from frozen current bytes through the actual loader authority chain, contextless consumer containment, v1 compatibility, separate ADV records, restored mutations, and scoped/protected hashes. Only a root audit, regenerated official package, and `phase4-final-review-4` can change review readiness.

Deployment impact remains `schema-free-phase4-loader-authority-enforcement`. This correction changes no schema, migration, dependency, service, configuration, provider, frontend, deployment, credential, production, live, or money behavior. It neither deploys nor claims release deployability, production rehearsal, Phase 4 acceptance, or Phase 4 runtime capability.

## Research receipt authority correction

The sole Phase 4 loader chain now invokes the existing research-plane
`research.domain.admissions.require_admission` after reconstruction and
execution-plane currentness, and before dataset or assessment loading. The core
boundary normalizes that module's `AdmissionPersistenceError` to its existing
error so the public loader always refuses stale research authority as
`AdmissionRequired("RECEIPT_STALE")`. It adds no verifier, hash, dispatcher,
schema, migration, or compatibility route.

The decisive fresh-process two-plane test calls the actual loader without
caller-side research verification. It proves missing research receipt, missing
graph, receipt-byte and copied-column tampering, graph-byte and copied-column
tampering, wrong-owner and cross-plane substitution all refuse before the
dataset tripwire; the complete current companion reaches exactly
`V2_RUNTIME_UNAVAILABLE`. It passes on SQLite and disposable PostgreSQL 16.
Current consumer tests retain no-side-effect containment for deployment, runner,
broker, enqueue, retry, reclaim, pinned-worker, cache, and job consumers; the
v1 golden dispatch contract remains passing. Invocation, verifier ordering,
terminal ordering, and enqueue-consumer mutations each kill their direct test
and the owned product/test bytes restore exactly to the frozen hash map.

Evidence is under
`.agent/runs/phase4-research-receipt-authority-correction/phase4_research_receipt_authority_owner/`.
This is `schema-free-phase4-research-receipt-authority-hardening`: it does not
enable v2 runtime, deployment, production, live, provider, broker, frontend,
credential, or money behavior. The immutable final-review-4 counterexample and
its historical FAIL remain unchanged; only final-review-5 may assess this new
package.
