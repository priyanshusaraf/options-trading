---
{
  "id": "phase4-dataset-assessment-authority-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Close CUR-C1 with typed dataset bytes, segments, manifest, nine role-specific dependency authorities, coverage, two-plane persistence, admission, result, and cache authority.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The accepted Phase 4 authority-foundation architecture correction authorizes this serial CUR-C1 correction only after its dependency gate. On 2026-08-18 the root owner accepted the capsule's named-gate proposal and expanded authority only to the listed role-specific dataset-dependency, execution 0039, research 0009, admission/cache, test, and evidence paths. The root owner also resolved the discovered content-address cycle by freezing the causal direction dataset-manifest/2 -> capability-assessment/2: the manifest binds the profile and dataset dependencies but never an assessment address; the assessment binds the final manifest; admission/cache bind and verify both. The prior owners are frozen and these shared files are reopened serially, never concurrently. Provider adapters, runtime enablement, frontend, deployment, production, live, and money boundaries remain closed.",
    "stopping_condition": "Complete only after DatasetManifest is the sole immutable dataset authority across research, admission, cache, and assessment planes; raw schema, normalization transform, alignment, missing-data, adjustment, roll, correction, creation-evidence, and deterministic-algorithm roles each reconstruct through their closed loader with no optional resolver or generic address dispatcher; every decision verifies the exact canonical address and complete dependency chain after process death; execution 0038->0039 and research 0008->0009 pass SQLite and disposable PostgreSQL fresh install, supported upgrade, restart, atomicity, model-DDL, and refusal parity; affected accepted Phase 4 seams are revalidated; and every assigned adversarial row has direct refusal or identity-change evidence. Stop with the goal active at any named owner gate or unresolved acceptance failure."
  },
  "risk_tags": ["critical", "research-integrity", "dataset-authority", "migration"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["8. Dataset provenance and cache identity", "9. Ownership, authority, and persistence", "13. Authority-foundation correction contract"]}, {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["8. Authority-correction serial route"]}, {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Open obligations", "Phase 4 ownership"]}],
  "dependency_gate": "phase4-typed-market-authority-correction",
  "allowed_paths": [
    "paper-trader/backend/app/backtest/dataset_store.py",
    "paper-trader/backend/app/backtest/cache.py",
    "paper-trader/backend/app/market_data/dataset_authority.py",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations/versions/20260818_0039_phase4_dataset_dependency_authority.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0009_phase4_dataset_authority.py",
    "paper-trader/backend/research/domain/strategy_admissions.py",
    "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py",
    "paper-trader/backend/tests/test_phase4_dataset_dependency_authority.py",
    "paper-trader/backend/tests/test_phase4_authority_execution_migration.py",
    "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
    ".agent/runs/phase4-dataset-assessment-authority-correction"
  ],
  "nonclaims": ["No provider acquisition, object-store capacity, production data, runtime, frontend, deployment, live, or money authority.", "Local fixture bytes prove only the declared local boundary.", "No generic fact table, public load-any-address dispatcher, optional dependency resolver, or synthetic VERIFIED_V2 backfill is authorized."],
  "owner_gates": ["Stop if a minimal research manifest, caller-supplied address, copied coverage, execution projection, optional resolver, generic row, or wrong-schema fact can replace dataset-manifest/2, its bytes, or any role-specific dependency authority.", "Stop if any implementation reintroduces a content-address cycle between dataset-manifest/2 and capability-assessment/2, omits the final manifest address from the assessment, or permits admission/cache to use either fact without proving their exact relationship."],
  "stop_conditions": ["Admission/cache accepts missing or changed bytes, incomplete coverage, wrong owner/product/contract, altered corrections/policies, generic rows, unresolved role dependencies, or same-process authority; either SQLite or disposable PostgreSQL migration/lifecycle evidence is absent; affected earlier Phase 4 authority seams are not revalidated."],
  "deployment_impact": {"classification": "additive-execution-and-research-dataset-dependency-authority-schema", "required_evidence": "Execution 0038->0039 and research 0008->0009 empty install, supported upgrade, restart, model-DDL parity, exact heads, typed dependency/segment integrity, transaction and outbox atomicity, legacy-unverified and destructive-downgrade refusal on SQLite and separate disposable PostgreSQL 16 planes. No deployment action or production-readiness claim follows."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default"},
  "parallel_budget": 0,
  "assignments": [],
  "adversarial_rows": ["ADV-001", "ADV-002", "ADV-003", "ADV-004", "ADV-005", "ADV-006", "ADV-007", "ADV-008", "ADV-009", "ADV-010", "ADV-011", "ADV-012", "ADV-013", "ADV-014", "ADV-015", "ADV-016", "ADV-018", "ADV-019", "ADV-020", "ADV-021", "ADV-022", "ADV-023", "ADV-024", "ADV-025", "ADV-026", "ADV-027"],
  "acceptance": [
    "dataset-segment/1 binds immutable byte digest/length/range/schema/instruments/fields/provider-contract/correction facts and reload streams the bytes",
    "dataset-manifest/2 binds exact owner, segments, aggregate bytes, coverage/gaps/corrections, provider/raw schema, transforms, truth, capability profile, policies, and algorithms, and its closed schema rejects a capability-assessment address",
    "raw-schema/1, normalization-transform/1, alignment-policy/1, missing-data-policy/1, adjustment-policy/1, roll-policy/1, dataset-correction/1, dataset-creation-evidence/1, and deterministic-algorithm/1 each have a separate immutable execution representation and a closed role-specific loader",
    "dataset-segment/1 and dataset-manifest/2 use explicit typed role references; the mandatory dataset loader receives the execution session and selects loaders by field role, never by caller-supplied type or callback",
    "capability-assessment/2 binds the final dataset-manifest/2 address; assessment, admission, and cache load and recompute the complete authoritative chain in both planes before use, and admission/cache separately bind both addresses",
    "result/cache identity changes transitively for byte, coverage, gap, correction, truth, transform, alignment, missing-data, adjustment, roll, algorithm, owner, product, or contract changes",
    "execution 0039 and research 0009 preserve unverifiable legacy rows for audit but block them from authority",
    "fresh-process real admission and cold-cache paths refuse arbitrary addresses, incomplete bytes/coverage, cross-owner rows, and partial writes"
  ],
  "test_plan": ["Produce one real-path ledger entry for every adversarial_rows ID, including seam, database/process boundary, expected refusal/identity change, observed result, and artifact address; exercise every one of the nine role-specific schemas with wrong-role, wrong-owner, wrong-product/contract, missing dependency, payload/column mismatch, changed algorithm/policy/correction and partial-chain cases; prove the manifest rejects capability_assessment_address, the assessment requires the exact final manifest address, and admission/cache refuse either-address substitution or a missing half of the pair; byte and coverage mutations; cold/warm cache; admission/result lineage; real process death; execution and research SQLite/PostgreSQL migration parity; partial-write/outbox recovery; affected prior-slice regressions; protected hashes and scoped diff."],
  "review": {"required": false, "assignment_id": "phase4_dataset_authority_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/backtest/dataset_store.py","paper-trader/backend/app/backtest/cache.py","paper-trader/backend/app/market_data/dataset_authority.py","paper-trader/backend/app/market_data/observations.py","paper-trader/backend/app/strategy/admission.py","paper-trader/backend/app/core/strategy_admissions.py","paper-trader/backend/app/db/models.py","paper-trader/backend/migrations/versions/20260818_0039_phase4_dataset_dependency_authority.py","paper-trader/backend/research/domain/models.py","paper-trader/backend/research/domain/migrate.py","paper-trader/backend/research/domain/migrations/0009_phase4_dataset_authority.py","paper-trader/backend/research/domain/strategy_admissions.py","paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py","paper-trader/backend/tests/test_phase4_dataset_dependency_authority.py","paper-trader/backend/tests/test_phase4_authority_execution_migration.py","paper-trader/backend/tests/test_phase4_authority_research_migration.py"], "exclude_paths": [], "output": ".agent/runs/phase4-dataset-assessment-authority-correction/owner/report.md", "verdicts": ["IMPLEMENTATION"]}
}
---

# Phase 4 dataset and assessment authority correction

Replace the generic research manifest authority with the exact documents in design §13.1. Verify bytes before coverage and coverage before assessment/admission. Keep execution and research representations byte-identical and owner-scoped. Design §13.3 row IDs in `adversarial_rows` are mandatory individual evidence cases.

The 2026-08-18 owner-gate amendment closes the discovered dependency escape in this same serial capsule. It authorizes nine closed role-specific dependency facts, additive execution migration `0039`, and the amended unaccepted research migration `0009`. A manifest field selects one fixed loader; callers cannot supply a resolver or generic fact kind. Previously accepted market-identity and typed-market paths are reopened only for this bounded serial integration and must retain their focused regressions.

The content-address dependency order is also frozen: source facts and dataset dependencies produce `dataset-manifest/2`; the final manifest address produces `capability-assessment/2`; admission and cache then bind both. `dataset-manifest/2` must not contain `capability_assessment_address`. This is the only authorized causal break and does not weaken the assessment-to-manifest, admission, or cache equality checks.
