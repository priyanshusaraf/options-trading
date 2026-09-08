Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-007 — One JSON helper encoded different shapes by database dialect

- Severity: Critical because the affected research constraints protect canonical graph, admission, legacy-manifest, and typed dataset-manifest authority.
- Status: CLOSED for the eight named research JSON columns by forward migration `0010`; the full Phase 4 integration and review claims remain stale and require their existing owners.
- Incident: `_JsonIsValid` meant syntax-valid JSON on SQLite but JSON object on PostgreSQL. Three object-valued columns therefore lacked an explicit object contract on SQLite, while five legitimate array-valued `dataset-manifest/2` columns were rejected on PostgreSQL.
- Root cause: one constraint abstraction combined syntax validation with an undeclared top-level shape. Dialect compilers silently gave that abstraction different meanings, and same-dialect fixtures did not exercise a real typed array through both databases.
- Prevention invariant: every JSON-bearing authority column declares its exact object or array shape. SQLite checks `json_valid` before guarded `json_type`; PostgreSQL checks exact `jsonb_typeof`. A migration validates exact old, exact new, or an explicitly resumable prefix before mutation and refuses marker-only claims, arbitrary hybrids, unrelated drift, malformed JSON, null, scalars, strings, and the opposite top-level shape.
- Searched surfaces: every research JSON constraint helper and use site; object-valued graph-version, strategy-admission, and legacy dataset-manifest artifacts; all five typed-manifest segment, instrument, field, gap, and dependency arrays; exact schema markers, constraints, keys, foreign keys, indexes, immutability triggers, upgrade boundaries, typed persistence/reload, and the original integration seam.
- Permanent regression: `research_tests/test_phase4_research_json_shape_parity.py` compiles and executes the complete eight-site matrix on SQLite and isolated PostgreSQL 16. `tests/test_phase4_authority_research_migration.py` proves exact `0009 -> 0010`, interrupted restart, row/canonical-byte preservation, exact-new idempotence, arbitrary-hybrid and unrelated-drift refusal, trigger/index/foreign-key parity, and downgrade refusal. The original two-plane selector exercises real typed-manifest persistence, process death, and reload.
- Transitive evidence map: research JSON constraint vocabulary → graph/admission/legacy-manifest and typed-manifest persistence → dataset assessment, admission, result/cache, two-plane lifecycle, integration, and review. This correction supersedes only the JSON-shape counterexample; it does not promote earlier stopped integration or review evidence.
- Owner: `phase4-research-json-shape-parity-correction` for this closed instance; `phase4-authority-integration-gate` for fresh transitive revalidation.
- Evidence: `.agent/runs/phase4-research-json-shape-parity-correction/phase4_research_json_shape_owner/`.

## DP-008 — Manual prerequisite verification substituted for the consuming seam

- Severity: Critical when the consuming seam can issue a terminal authority or runtime decision.
- Status: REOPENED by immutable `phase4-final-review-4` SPEC/QUALITY FAIL. The earlier loader and matrix evidence closed dataset/assessment and reclaim-context instances but did not prove research receipt-and-graph enforcement at the actual terminal loader. Architecture is accepted for `phase4-research-receipt-authority-correction`; implementation, transitive revalidation, package rebuild, and fresh final review remain open.
- Incident: The Phase 4 integration path called `load_verified_admission`, which reconstructed the artifact and checked execution receipt/graph plus dataset/assessment authority, then reached `V2_RUNTIME_UNAVAILABLE` while `ResearchStrategyAdmission` and `ResearchIrV2GraphVersion` were absent. The test manually queried and verified those research records only after the loader returned.
- Root cause: successful prerequisites were treated as transitive enforcement even though the authority-consuming seam could bypass them.
- Prevention invariant: an authority-consuming seam receives every required authority input explicitly and invokes the sole complete chain itself: `load_verified_admission` -> `reconstruct_phase4_artifact` -> `require_phase4_current` -> existing `research.domain.admissions.require_admission` -> dataset/assessment verification -> terminal refusal. It refuses missing context or authority before reconciliation, claim, provider, cache, job, worker, deployment, broker, order, or money effects. A second verifier/hash/dispatcher, caller preverification, diagnostic after loader return, broad owner update, fresh post-classification selector, or first-row-only check is invalid.
- Required search surfaces: execution admission dispatch, enqueue/retry/reclaim, cache and pinned-worker reads, deployment and runner entry points, broker evaluation, and every production `load_verified_admission` caller.
- Permanent regression: retain the missing-context and reclaim guards, then add actual-loader refusals for missing research receipt, missing research graph, tampered receipt, tampered graph, tampered copied columns, wrong owner, and cross-plane substitution. Prove a fresh-process two-plane reconstruction and exact complete-current `V2_RUNTIME_UNAVAILABLE` only after research receipt/graph and dataset/assessment verification. Run on SQLite and disposable PostgreSQL 16. Kill and byte-restore research-verifier invocation, verifier order, terminal order, and consumer no-side-effect guards; helper-only or caller-manual verification is invalid.
- Transitive invalidation map: final-review-3 and final-review-4 remain immutable historical FAILs. The new counterexample invalidates every claim that the actual loader proves the complete two-plane chain, including the decisive integration lifecycle, contextless deployment/runner/broker/enqueue/retry/reclaim/pinned/cache/job containment where complete verification was assumed, affected ADV rows, the official review package, and review readiness. Earlier transaction, reclaim-locking, and v1 evidence remains historical evidence for its exact unaffected contract only.
- Transitive revalidation map: frozen current product/test hashes -> actual-loader research receipt/graph invocation and order -> missing/tampered/wrong-owner/cross-plane refusals -> complete-current terminal refusal -> fresh-process SQLite and PostgreSQL 16 reconstruction -> dynamic deployment/runner/broker/enqueue/retry/reclaim/pinned/cache/job no-side-effect checks -> affected ADV rows -> killed/restored guards -> package rebuild -> fresh independent final review 5.
- Owner: `phase4-research-receipt-authority-correction`; only `phase4-final-review-5` may assess the rebuilt review boundary.
- Evidence: `.agent/runs/phase4-final-review-4/verdict.json` and `.agent/runs/phase4-research-receipt-authority-architecture-correction/`.

### DP-008 correction evidence

The accepted schema-free correction is implemented and revalidated from frozen
current bytes. `load_verified_admission` now follows the required single chain:
reconstruction, `require_phase4_current`, the existing research admission
requirement, dataset/assessment verification, then the exact terminal
`V2_RUNTIME_UNAVAILABLE`. Research-plane persistence errors normalize at the
core boundary to the existing public `RECEIPT_STALE` refusal. SQLite and
disposable PostgreSQL 16 direct-loader cases prove all named absent, tampered,
copied-column, wrong-owner, and cross-plane research authority substitutions
fail before dataset loading; the complete-current companion reaches the terminal
refusal. Killed invocation, order, terminal, and consumer guard mutations each
fail and restore exactly. This does not alter the immutable final-review-4 FAIL
or accept Phase 4: final-review-5 remains the sole review authority.
