Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-003 — Mocked seam presented as lifecycle evidence

- Severity: High, elevated to Critical when the seam carries authority, tenancy, money, persistence, or research integrity
- Status: OPEN
- Incident: Phase 4 correction selectors mocked `load_verified_admission`, so 139 passing tests did not exercise canonical persisted reconstruction and missed a legitimate receipt failing after reload.
- Root cause: local behavior evidence was reported as end-to-end evidence without a map of which boundary was replaced.
- Prevention invariant: each acceptance claim names the furthest real boundary exercised. A mocked critical seam is valid unit evidence only and cannot satisfy cross-layer acceptance.
- Required search surfaces: persistence/reload, migrations, cache warm/cold paths, worker enqueue/reclaim, provider construction, authority resolution, research promotion, and v1/v2 dispatch.
- Permanent regression: for every critical cross-layer invariant, add one unmocked create/admit → persist → process death → reload → verify → consume path, plus a test/evidence assertion that fails if the critical seam is monkeypatched.
- Transitive evidence map: real-path coverage semantics → every prior review relying on mocked persistence or consumers → named tests/reports/reviews → Sol-high checker classification and Ultra foundation-audit evidence invalidation map.
- Owner: root review system; first broad disposition by `phase1-4-foundation-audit`.
- Evidence: `.agent/runs/phase4-review/recheck-verdict.json`.

## DP-004 — Immutable envelope over mutable or time-incoherent facts

- Severity: Critical when the digest controls admission, cache reuse, research provenance, or execution
- Status: CONTAINED for known Phase 4 numeric and market-truth instances; broader search pending
- Incident: VALID numeric payloads and market-truth snapshot records could mutate after validation, and a snapshot could include facts recorded after its knowledge cutoff while retaining an apparently valid identity.
- Root cause: digest or frozen-envelope construction did not recursively close payload mutability and temporal eligibility.
- Prevention invariant: an immutable identity recursively closes every semantic payload and enforces both effective-time and knowledge-time rules before hashing. Reloaded facts must revalidate the same closure.
- Required search surfaces: IR parameters, observations, datasets, rulebooks, registry snapshots, capability evidence, results, cache payloads, serialized JSON/arrays, and ORM JSON columns.
- Permanent regression: mutate nested data after construction and inject future-recorded facts into past snapshots; identity, reload, and consumption must refuse or remain byte-stable as specified.
- Transitive evidence map: immutable/temporal identity → Phase 3 causal and Phase 4 numeric/market-truth/dataset/cache contracts → named mutation tests and fresh foundation revalidation.
- Owner: Phase 4 known-instance tests; `phase1-4-foundation-audit` for foundation-wide disposition.
- Evidence: `.agent/runs/phase4-review/verdict.json`, `.agent/runs/phase4-review-correction`.

## DP-005 — Address-bearing metadata mistaken for a typed authoritative fact

- Severity: Critical when the address controls research admission, cache reuse, market truth, capability, or execution identity
- Status: OPEN; architecture frozen, implementation and transitive revalidation pending
- Incident: Phase 4 persisted generic JSON and repeated well-formed addresses for dataset manifests, instruments, observations, truth snapshots, capability profiles, and assessments. Consumers could verify outer digest syntax while never reconstructing the named typed fact, its owner/product/contract equality, exact bytes, coverage, or dependency authority.
- Root cause: the design treated address-bearing metadata as proof that an authoritative object existed. Several layers shared labels such as provider and instrument while meaning different entity, product, contract, alias, physical instrument, or economic underlier facts. Persistence preserved claims but did not preserve a closed reconstruction proof.
- Prevention invariant: every authority-bearing address names one closed versioned document with canonical bytes, a sole constructor, immutable dependencies, exact owner/provider/product/contract/quality equality, a durable representation, and a fresh-process loader that reconstructs the typed fact and recomputes its address. Generic JSON, minimal rows, constructor tokens, copied digests/statuses, and address syntax grant no authority.
- Required search surfaces: canonical instrument/underlier and alias mapping; raw and normalized observations; truth and reconstruction; provider entity/product/contract and conformance/entitlement; capability profile/assessment; dataset segments/bytes/coverage; admission, result, cache, graph receipt, deployment attribution, generated lineage, and cross-plane copies.
- Permanent regressions: substitute an arbitrary valid address, a minimal row, wrong owner/product/contract/underlier/quality, same address with different cross-plane bytes, missing segment or field/range, changed raw byte/transform/rule/gap/correction/policy, copied-column disagreement, partial write, and process restart. Each real loader must refuse or change identity before admission, result/cache reuse, claim/reclaim, or execution.
- Transitive evidence map: typed-fact authority -> Phase 4 instrument, observation, truth, capability, dataset, assessment, admission, result, cache, graph and scenario contracts -> correction capsules and exact migrations `0038`/`0009` -> full authority integration -> later independent critical review. Every prior dependent PASS is `STALE/REQUIRES RECHECK` until its owning capsule supplies direct evidence.
- Owner: the serial route `phase4-resolved-topology-identity-correction` -> `phase4-canonical-market-identity-correction` -> `phase4-typed-market-authority-correction` -> `phase4-dataset-assessment-authority-correction` -> `phase4-authority-integration-gate`.
- Evidence: `.agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/` and `.agent/runs/phase4-authority-foundation-architecture-correction/owner/`.

## DP-006 — Database session timezone changed copied authority instants

- Severity: Critical because the affected copies gate reconstruction of provider, market-data, capability, and dataset authority.
- Status: CLOSED for the named Phase 4 typed-authority surfaces; the stopped full integration remains stale and requires its owning capsule to rerun.
- Incident: PostgreSQL 16 configured to `Asia/Kolkata` converted aware values written to timezone-naive columns into server-local wall time. Loaders then removed timezone information from canonical UTC instants or compared against a different representation. SQLite masked the mismatch, and the earliest real failure appeared while a raw segment reloaded its provider contract.
- Root cause: copied SQL timestamps had no single database-neutral representation. Writers relied on driver conversion, loaders used local private rules, and the alias overlap query did not share a common conversion contract.
- Prevention invariant: canonical fact bytes retain aware UTC instants. Every copied timezone-naive SQL value is explicitly converted to UTC and then made naive before a write or predicate. Every loaded value must already be a timezone-naive `datetime`; loaders reject aware, absent, or malformed values without reinterpreting local wall time, and compare them with the same shared conversion.
- Searched surfaces: provider contract and alias intervals, including alias overlap predicates; truth snapshot knowledge/effective times; conformance observation interval; profile observation/expiry; assessment time; provider and normalized observation event/availability times; and `recorded_at` in deterministic algorithm, raw schema, normalization transform, alignment policy, missing-data policy, adjustment policy, roll policy, dataset-creation evidence, and dataset correction. Duplicate private conversion rules were removed from these allowed modules.
- Permanent regression: `tests/test_phase4_authority_timestamp_normalization.py` exercises non-zero `+05:30` and `-04:00` source offsets, SQLite and disposable PostgreSQL 16 with explicit `SHOW TIMEZONE = Asia/Kolkata`, process death and a fresh interpreter, byte/address parity, alias overlap, malformed aware-row refusal, and one-hour copied-column plus canonical-document substitution for all eight authority families and all nine dataset tables.
- Transitive evidence map: copied timestamp representation → all Phase 4 typed-authority persistence and dependency reloads → the stopped authority-integration run and any review or package derived from it. The correction supersedes the original timestamp counterexample only. The later research-manifest constraint failure and the full integration/review verdict remain owned by their existing capsules; no historical PASS is promoted.
- Owner: `phase4-authority-timestamp-normalization-correction` for the closed instance; `phase4-authority-integration-gate` for fresh transitive revalidation.
- Evidence: `.agent/runs/phase4-authority-integration-gate/owner_2/lifecycle-postgresql16-separated-planes.log` and `.agent/runs/phase4-authority-timestamp-normalization-correction/phase4_authority_timestamp_owner/`.
