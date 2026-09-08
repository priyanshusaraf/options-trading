---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-founder-admin-numeric-projection-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_fresh_numeric_admin_projection_contract",
  "goal": "Replace mutable admin dimension strings/enums with exact built-in integer codes from a fixed five-family table while preserving threshold, context, privacy and non-publication semantics.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Canonical values contain only exact family-valid int codes; all hostile strings, enum mutation, type/range/cross-family/copy vectors refuse; original positives/resource/mutations and one fresh Critical review pass with effects closed."},
  "risk_tags": ["critical", "admin", "privacy", "numeric-code", "fresh-successor"],
  "depends_on": ["strategy-os-v0-founder-admin-numeric-code-replan"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan/decision.json", "policy": "Only fixed exact integer codes may proceed; failed enum lineage remains rejected."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan/decision.json", "sections": ["immutable_failed_lineage", "rejected_design", "fixed_numeric_table", "numeric_contract", "required_regressions", "retained_gates"]},
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review/recheck-verdict.json", "sections": ["risk_boundaries", "SPEC", "QUALITY", "evidence_gaps", "recheck_accounting"]},
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/decision.json", "sections": ["safe_pure_contract", "structural_exclusions", "owner_security_privacy_gates"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-projection-correction.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-projection-correction.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction"],
  "protected_paths": ["paper-trader/backend/app/admin/__init__.py", "paper-trader/backend/app/accounts", "paper-trader/backend/app/billing", "paper-trader/backend/app/support", "paper-trader/backend/app/product_analytics", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/api", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review"],
  "scope": ["Remove AdminDimensionCode and every dimension string/enum from canonical policy/input/projection values.", "Use exact built-in int codes 1..10 with immutable module family table: account 1-2, entitlement 3-4, support 5-6, usage 7-8, health 9-10.", "Policy chooses sorted nonempty subsets within each exact family; cannot add codes. Input/projection dimensions are exact int tuples only.", "Every factory/derivation/decode revalidates type(value) is int, range, family subset, exact policy/proof/source/time/threshold and false flags.", "Human labels are absent; all prior privacy exclusions and effect gates remain.", "No operator auth, individual access, persistence/API/frontend/publication/deployment."],
  "acceptance": ["Five families pass with exact valid ints and threshold context.", "All 22 hostile strings, mutated old enum name/value, bool/float/string/IntEnum/subclass/zero/negative/11/large/cross-family codes refuse across direct/policy/input/projection/codec.", "Direct/copy/deepcopy/replace/object mutation and fresh restart revalidate current codes and exact context.", "Canonical JSON contains dimension integers only and no human/private label.", "Original threshold/privacy/false-flag/mutation/resource gates plus at least three fresh numeric decoder/use-site mutations pass.", "Critical SPEC/QUALITY review passes; production/effect gates remain closed."],
  "test_plan": ["Real RED for enum-mutation and numeric-only contract.", "Full hostile type/range/family/value matrix plus original 22 sentinels.", "Copy/restart/strict codec/privacy/threshold controls.", "Fresh policy/input/decode numeric guard mutations restored.", "100000/resource/architecture/protected and fresh review."],
  "risk_classification": {"tier": "Critical", "reason": "Canonical admin data must be structurally unable to carry mutable or arbitrary private labels."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_founder_admin_numeric_projection_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-projection-correction.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction"], "output": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_founder_admin_numeric_projection_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Fresh review after exhausted privacy lineage.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/review-package.json", "review_paths": ["paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-projection-correction.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction"], "exclude_paths": ["paper-trader/backend/app/admin/__init__.py", "paper-trader/backend/app/accounts", "paper-trader/backend/app/billing", "paper-trader/backend/app/support", "paper-trader/backend/app/product_analytics", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/api", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["Production code subset/threshold, operator auth, individual/PII, persistence/API/frontend/publication/deployment remain closed."],
  "stop_conditions": ["Any canonical label/string/enum remains or validation skips exact int type/family.", "Any effect or production policy is added."],
  "deployment_impact": {"classification": "compatible pure contract correction", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "implementation_evidence": {
    "assignment": "v0_founder_admin_numeric_projection_owner",
    "status": "implementation_complete_pending_critical_review",
    "dimension_code_type": "exact built-in int",
    "fixed_family_table": {"ACCOUNT_STATE_AGGREGATE": [1, 2], "ENTITLEMENT_AGGREGATE": [3, 4], "SUPPORT_AGGREGATE": [5, 6], "PRODUCT_USAGE_AGGREGATE": [7, 8], "OPERATIONS_HEALTH_AGGREGATE": [9, 10]},
    "focused_cases": 70,
    "hostile_string_sentinels": 22,
    "numeric_type_range_family_vectors": 10,
    "fresh_numeric_policy_input_decode_mutations": 6,
    "positive_family_controls": 5,
    "resource_decisions": 100000,
    "product_sha256": "eb378d05cb6fc8930fdd1b48a1d8e268faa14cf1c70fff19230217c148e33ece",
    "tests_sha256": "3a016f81c7cb56dd529d6f1e0120ebe73817d589e53be1977ea48d03fbb3cfcc",
    "red_sha256": "a16cf337a3e105eead417d768d1a51bfd88693b9b48bc7c9b3ff2e6cd49d9fa9",
    "focused_green_sha256": "075ca72bd3c733566e8b37c84bfcdb26ebaad93cb7e0a15d42d96d3ed9f0e0b4",
    "exact_int_mutation_sha256": "92793a00c0f4a8d0719cead354b417e27e3584f85ff878019a33538d5705d2c9",
    "architecture": {"checked_files": 463, "sha256": "b9cf0cfeae7502bffd071ff9c7b5a3cf4ac5053f35fb6df5a2aa2776a8b7a766"},
    "protected_before": {"entries": 31833, "sha256": "365a30cc21848f8c5c01d02762a85b86770eba2bbb8934a5f0d142d972d044d8"},
    "protected_after": {"entries": 31833, "sha256": "365a30cc21848f8c5c01d02762a85b86770eba2bbb8934a5f0d142d972d044d8"},
    "protected_comparison_sha256": "042d9d4ce34ff77868942c508b5daa979ce90e2ea28a0b97274b8789cd8202b8",
    "protected_claim": "Byte-identical continuity only; inherited bytes are not attributed to this assignment.",
    "report": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/report.md",
    "review_package": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/review-package.json"
  },
  "first_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "verdict_sha256": "a34df2d7a42edcb1041e765187c393fdcaa6df8c6513f8e6faaf5af4d6b7a009", "findings": ["V0-FANP-CR-001", "V0-FANP-CR-002"], "evidence_gaps": ["V0-FANP-EG-001", "V0-FANP-EG-002"], "rechecks_used": 0, "rechecks_remaining": 1, "correction_scope": "Replace mutable family and band labels with exact integer codes; test actual production enum removal/cached identity and exhaustive family JSON-number semantics.", "deployment": false},
  "correction_evidence": {
    "status": "correction_complete_pending_focused_recheck",
    "closes": ["V0-FANP-CR-001", "V0-FANP-CR-002", "V0-FANP-EG-001", "V0-FANP-EG-002"],
    "family_code_table": [101, 102, 103, 104, 105],
    "band_code_table": [201, 202, 203],
    "dimension_code_table": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "focused_cases": 131,
    "exhaustive_cross_family_json_cases": 40,
    "hostile_string_sentinels": 22,
    "family_type_table_vectors": 9,
    "band_type_table_vectors": 9,
    "fresh_family_band_object_decode_mutations": 9,
    "resource_decisions": 100000,
    "product_sha256": "ee058fe39c05a771c79543ff8b862b6d11c35ce92dcca3e0ab0567b18bf0f291",
    "tests_sha256": "737e81254316fdad287c875dbe94746d50430644cfcb5b9ef1f1c2c0a83db6e8",
    "review_verdict_sha256": "a34df2d7a42edcb1041e765187c393fdcaa6df8c6513f8e6faaf5af4d6b7a009",
    "reviewer_exact_red_sha256": "dbcea8c27a8795ff316ef8ebfe9df30628b784f67088f6cc9c538d78f0c2dbb8",
    "focused_green_sha256": "7fcc46904bad8c16f525a40bf2feeb1b75612b3bbe19f6add6251b9e461211ab",
    "family_band_mutation_sha256": "690f730f2cb642b382fe835e59b625a657539465892c90936c8c99b4fc72057e",
    "architecture": {"checked_files": 463, "sha256": "b9cf0cfeae7502bffd071ff9c7b5a3cf4ac5053f35fb6df5a2aa2776a8b7a766"},
    "protected_baseline": {"entries": 31833, "sha256": "365a30cc21848f8c5c01d02762a85b86770eba2bbb8934a5f0d142d972d044d8"},
    "protected_after": {"entries": 31833, "sha256": "365a30cc21848f8c5c01d02762a85b86770eba2bbb8934a5f0d142d972d044d8"},
    "protected_comparison_sha256": "f5b6cc9ae3d76c9192f79f15470064b1e23eb421235caa3be05fc8b568dd678c",
    "codec_boundary": "Python direct values reject IntEnum and int subclasses before serialization; decoded JSON number text has only built-in int provenance and is checked by numeric table and family membership.",
    "report": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/correction-report.md",
    "review_package": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/corrected-review-package.json"
  },
  "final_review": {"verdict": "SPEC PASS / QUALITY PASS / final PASS", "first_verdict_sha256": "a34df2d7a42edcb1041e765187c393fdcaa6df8c6513f8e6faaf5af4d6b7a009", "corrected_package_sha256": "b911b57e3e091622d0db602aaaceca8ff595fee0eda0a01411e56e65286d1cfe", "recheck_verdict_sha256": "7753e62e1d61b85bd5c70beb70c88ff0c6d1b08896718bbdf5569e6972a79775", "closed_findings": ["V0-FANP-CR-001", "V0-FANP-CR-002", "V0-FANP-EG-001", "V0-FANP-EG-002"], "rechecks_used": 1, "rechecks_remaining": 0, "publication": false, "deployment": false},
  "nonclaims": ["No acceptance of failed lineage, operator auth, individual access, publication, API/frontend, deployment or V0 completion."
  ]
}
---

# Founder/admin numeric projection correction

Canonical admin dimension values are exact built-in integers only.

## Implementation receipt

- Status: `implementation_complete_pending_critical_review`.
- The failed enum lineage remains rejected. `AdminDimensionCode` and all dimension
  strings/enums are absent from policy, input and projection canonical values.
- The immutable module table is account `1-2`, entitlement `3-4`, support `5-6`,
  product usage `7-8` and operations health `9-10`. Injected policy selects sorted
  nonempty family-valid subsets without a production default.
- Exact built-in `int` validation rejects bool, float, string, `IntEnum`, int
  subclasses, zero, negative, 11, huge and cross-family values at direct,
  serialization, factory, derive, validation and decode use sites.
- Real RED reproduces mutable enum `_value_` entry and nonnumeric canonical output.
  The restored numeric contract passes 70 focused cases, five family positives,
  the original 22 hostile strings, legacy enum mutation, six fresh numeric
  policy/input/decode mutations, restart/copy/context/threshold/privacy/false-flag
  controls and the 100,000-decision resource bound.
- A reversible `isinstance` mutation reopens bool, `IntEnum` and int subclasses;
  the exact-type matrix kills it.
- Two 31,833-entry protected manifests are byte-identical with SHA-256
  `365a30cc21848f8c5c01d02762a85b86770eba2bbb8934a5f0d142d972d044d8`.
  This claims continuity only, not authorship.
- Production code subset and threshold, operator authority, PII/individual access,
  persistence, API/frontend, publication and deployment remain closed.

## Focused family and band correction receipt

- Immutable verdict: `a34df2d7a42edcb1041e765187c393fdcaa6df8c6513f8e6faaf5af4d6b7a009`.
- Status: `correction_complete_pending_focused_recheck`.
- `ProjectionFamily` is absent. Canonical family codes are exact built-in integers
  `101..105`; dimensions remain exact integers `1..10`; operational band codes are
  exact built-in integers `201..203`. No family or band name/value/label object is
  serialized.
- Reviewer-exact RED restores the reviewed source hash, caches identities, mutates
  only the actual `ProjectionFamily._value_`, emits tenant-private text in policy,
  input and projection JSON, and confirms final validation accepted it. GREEN proves
  that type is absent and mutation of a legacy enum cannot affect cached output.
- All 40 family-versus-other-family JSON-number combinations refuse across direct
  values and policy/input/projection decode. Python `IntEnum` and int subclasses
  refuse before serialization; JSON number text has no subclass provenance and is
  validated as a built-in decoded integer against the fixed tables.
- The original 22 private strings also refuse as band codes through direct,
  self-attested policy, projection and codec paths. Nine fresh family/band object
  and decode mutations refuse.
- All 131 focused cases and the 100,000-decision resource bound pass. A reversible
  `isinstance` mutation reopens family and band `IntEnum`/subclass inputs and four
  controls turn RED.
- Protected continuity remains 31,833 byte-identical entries at SHA-256
  `365a30cc21848f8c5c01d02762a85b86770eba2bbb8934a5f0d142d972d044d8`.
- Production subsets/threshold and every authority, individual, persistence,
  publication, frontend and deployment gate remain closed.
