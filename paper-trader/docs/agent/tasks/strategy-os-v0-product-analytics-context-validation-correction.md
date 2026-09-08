---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-product-analytics-context-validation-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_fresh_context_complete_value_validation",
  "goal": "Replace copyable product-analytics trust state with complete context validation of untrusted canonical values at every event factory, aggregate derivation and decode boundary.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The stored marker is absent; all current event fields and exact injected catalogue/authority/source context are revalidated at every use; direct/copy/deepcopy/replace/object mutations and original reviewer vectors refuse; positive restart/resource/mutations and one fresh Critical review pass."},
  "risk_tags": ["critical", "analytics", "privacy", "copy-semantics", "authority", "fresh-successor"],
  "depends_on": ["strategy-os-v0-product-analytics-copy-safe-validation-replan"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan/decision.json", "policy": "The exhausted marker lineage remains rejected; only context-complete validation may proceed."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan/decision.json", "sections": ["immutable_failed_lineage", "rejected_design", "fresh_architecture", "required_regressions", "retained_owner_gate"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/review/recheck-verdict.json", "sections": ["fresh_recheck_evidence", "risk_boundaries", "SPEC", "QUALITY", "evidence_gaps", "recheck_accounting"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "sections": ["safe_pure_contract", "prohibited", "owner_privacy_security_gates"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-context-validation-correction.md", ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-context-validation-correction.md", ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction"],
  "protected_paths": ["paper-trader/backend/app/product_analytics/__init__.py", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/accounts", "paper-trader/backend/app/admin", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/events", "paper-trader/backend/app/engine", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/review"],
  "scope": [
    "Remove every stored derivation marker, token and object-identity trust check from event and aggregate values.",
    "Treat EventCandidate and AggregateDimensionsCandidate as untrusted canonical value carriers. No caller consumes them as authoritative without the validation seam.",
    "One complete seam revalidates exact built-in types, RFC4122 nonzero subject/tenant/session/source UUIDs, canonical UTC received time, source fact version/context, catalogue/source provenance, authority catalogue/source/provenance/allow fact, event content IDs, finite fields and typed dimensions from current fields.",
    "Event factory validates before return; aggregate derivation validates current event; event decode reconstructs through factory; aggregate decode re-derives expected aggregate from exact injected event.",
    "Aggregate value alone has no authority; every consumer/decode requires exact event and re-derivation. publishable remains false.",
    "Unchanged copies may validate because facts are unchanged. Shallow/deep/replace/object-mutated fields receive no inherited trust and are fully revalidated.",
    "Content-ID cache remains bounded identity-only and never caches validation/trust.",
    "No production catalogue, collection, persistence, preference, admin/API/frontend, processor, analytics emission or deployment."
  ],
  "acceptance": [
    "Original foreign identifier, forged authority/source, direct aggregate and foreign decode vectors reject without a marker.",
    "copy.copy, copy.deepcopy, dataclasses.replace and object-level mutation of time, UUID, source, content identity, finite field, dimension and publishable invariants are either unchanged-and-valid or changed-and-refused by complete validation.",
    "One legitimate factory, aggregate and fresh-process decode control passes; strict codecs and privacy allowlists remain unchanged.",
    "At least three isolated mutations remove validation from factory, derivation and decode and are killed/restored; prior ten regression mutations remain green.",
    "100000 decisions stay within 30 seconds/2 MiB; architecture/protected attribution and one new Critical SPEC/QUALITY review pass.",
    "V0-PAC-EG-003 remains open and collection/publication/effects remain false."
  ],
  "test_plan": ["RED exact shallow-copy invalid-time and marker-removal regressions.", "Full constructor/copy/deepcopy/replace/object-mutation matrix for every current invariant.", "Original reviewer probes and fresh restart.", "Isolated factory/derivation/decode validation-seam mutations with restoration.", "Full 100000/resource/AST/import/architecture gates."],
  "risk_classification": {"tier": "Critical", "reason": "Every future analytics consumer depends on validation being a function of current facts, not copied runtime identity."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_product_analytics_context_validation_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-context-validation-correction.md", ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction"], "output": ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_product_analytics_context_validation_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Fresh review after exhausted lineage; copy semantics and complete validation are a Critical privacy/authority boundary.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction/review-package.json", "review_paths": ["paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-context-validation-correction.md", ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction"], "exclude_paths": ["paper-trader/backend/app/product_analytics/__init__.py", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/events", "paper-trader/backend/app/engine", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-product-analytics-context-validation-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["V0-PAC-EG-003 and all production catalogue/preference/lifecycle/persistence/admin/API/frontend/processor/deployment decisions remain closed."],
  "stop_conditions": ["Any design still stores trust on a copyable object or skips complete use-time validation.", "Any product effect or production semantic policy is required."],
  "implementation_evidence": {
    "status": "implementation_complete_pending_critical_review",
    "review_package_sha256": "7068c43ff69875a47af4e985fa724a1a92c70d8f8626194b9444e268273d64aa",
    "source_sha256": "e4a5f7a8b4d5ba172ed9d976a344df0b23751062067d68e2e07dfd0f031b7da8",
    "test_sha256": "c81f12a7b40436f8c6bab79a701b131bd1c38b9a890094313f406bde31e35f46",
    "report_sha256": "a89c993b624a5293c737df3e0e8a7dfff76a67d77cdef51f29e81a42042f4386",
    "fingerprint_sha256": "a34d820585a091f8f2e0f19c99beb653b04810ff48dd6bad060e5aee167c27be",
    "evidence_sha256": "604cdc4860cb1110ae0c707fc6fed9780912ee7ba9a2756a66efe2bbfd3d83b5",
    "tests": 33,
    "new_use_site_mutations_exposed_and_restored": 3,
    "prior_ten_regression_checks_green": true,
    "resource": {"decisions": 100000, "elapsed_seconds": 24.817261, "peak_bytes": 614506},
    "architecture": {"result": "PASS", "log_sha256": "a2da2e59f4ab9309cbaa4321afe53a074929acff1913ec092976d33d6f82fdc8"},
    "stored_trust_absent": true,
    "validation_cache_absent": true,
    "old_review_directory_sha256": "138def9ae21b93aa189c3ea4b5867c4473584999ab35fb0fc6e3ed2d4a7bc58a",
    "owner_gate_remaining": "V0-PAC-EG-003: production catalogue/provenance and forbidden semantic namespaces require owner/privacy approval; no keyword filter added.",
    "effect_flags": {"collection": false, "persistence": false, "retry": false, "export": false, "external_processor": false, "admin_access": false, "publication": false, "api": false, "frontend": false, "deployment": false}
  },
  "first_review": {"verdict": "SPEC PASS / QUALITY FAIL / final FAIL", "verdict_sha256": "4ef7ed53e44dd7a7244aa9d5d2b856defee8826ff4a78d9f1d2aa5fb7612dbd0", "findings": ["V0-PAC-CV-QR-001", "V0-PAC-CV-QR-002", "V0-PAC-CV-QR-003"], "evidence_gaps": ["V0-PAC-CV-EG-001", "V0-PAC-CV-EG-002", "V0-PAC-CV-EG-003", "V0-PAC-EG-003"], "rechecks_used": 0, "rechecks_remaining": 1, "correction_scope": "Honest protected continuity wording; aggregate-decode/aggregate-value evidence; identity-only performance margin and profile/equivalence evidence. Validation architecture and effects remain unchanged.", "deployment": false},
  "correction_evidence": {
    "status": "correction_complete_pending_focused_recheck",
    "corrected_package_sha256": "1d082a441f3562afd32b8d87183ed23d91a0669c23ddaf74e98608ad68994310",
    "source_sha256": "1a3850f0722886a1f9395629304037802d25ae7e18945f0121bd39af84ece185",
    "test_sha256": "8a4e03c18e9a01b0fa3455b5fe3ce2e161582a3809e9ad65f75b7e539cf7837d",
    "report_sha256": "8fd15a075fcf1177a6a79a9fd0642406b871603317d2302a0bd0f619e2de558c",
    "fingerprint_sha256": "6cc1d79b70d601fc1666f7a8a14a336af84b13e67cf0db9cc516f50be98a8bcf",
    "evidence_sha256": "badc2c0edea26f8220071abf6831cc1411214944ee24254ca06d451b5da01338",
    "tests": 37,
    "aggregate_decode_mutation_exposed_and_restored": true,
    "aggregate_replace_and_object_matrix": true,
    "prior_mutations_green": true,
    "resource": {"decisions": 100000, "elapsed_seconds": 15.897644, "peak_bytes": 315376, "timing_margin_percent": 47.01},
    "profile": {"dominant_cost": "recursive canonical identity-key construction", "dominant_cumulative_seconds": 18.946, "before_seconds": 19.311742583988234, "after_seconds": [13.077109167003073, 12.403991124941967], "output_identity_equal": true},
    "identity_cache": {"identity_only": true, "validation_or_trust_cached": false, "maxsize": 256, "field_and_nested_mutation_change_identity": true, "complete_validation_runs_every_use": true},
    "architecture": {"result": "PASS", "log_sha256": "a2da2e59f4ab9309cbaa4321afe53a074929acff1913ec092976d33d6f82fdc8"},
    "protected_continuity": "Hash equality establishes byte continuity only. Assignment-level authorship is not independently reconstructible in the shared dirty worktree.",
    "assignment_authorship_claim": null,
    "addressed_pending_recheck": ["V0-PAC-CV-QR-001", "V0-PAC-CV-QR-002", "V0-PAC-CV-QR-003", "V0-PAC-CV-EG-001", "V0-PAC-CV-EG-002", "V0-PAC-CV-EG-003"],
    "owner_gate_remaining": "V0-PAC-EG-003",
    "effect_flags": {"collection": false, "persistence": false, "retry": false, "export": false, "external_processor": false, "admin_access": false, "publication": false, "api": false, "frontend": false, "deployment": false}
  },
  "final_review": {"verdict": "SPEC PASS / QUALITY PASS / final PASS", "first_verdict_sha256": "4ef7ed53e44dd7a7244aa9d5d2b856defee8826ff4a78d9f1d2aa5fb7612dbd0", "corrected_package_sha256": "1d082a441f3562afd32b8d87183ed23d91a0669c23ddaf74e98608ad68994310", "recheck_verdict_sha256": "58e5cf8dade9a36f33e675db6796cf093c384dd54981526d54a95478814ebd6f", "closed_findings": ["V0-PAC-CV-QR-001", "V0-PAC-CV-QR-002", "V0-PAC-CV-QR-003", "V0-PAC-CV-EG-001", "V0-PAC-CV-EG-002", "V0-PAC-CV-EG-003"], "owner_gate_remaining": "V0-PAC-EG-003", "rechecks_used": 1, "rechecks_remaining": 0, "collection": false, "deployment": false},
  "deployment_impact": {"classification": "compatible pure contract correction", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No acceptance of failed lineage, production catalogue, collection, persistence, admin/API/frontend, processor, deployment or V0 completion."]
}
---

# Product analytics context validation correction

Trust is recomputed from current values and exact context at every use boundary.

QUALITY correction is complete pending the one allowed focused recheck. The
corrected package is
`.agent/runs/strategy-os-v0-product-analytics-context-validation-correction/corrected-review-package.json`.
Protected hashes establish byte continuity only; assignment authorship is not
independently reconstructible in the shared dirty worktree. V0-PAC-EG-003 stays
open, and no production effect is authorized.
