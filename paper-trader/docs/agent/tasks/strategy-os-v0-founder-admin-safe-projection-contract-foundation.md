---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-founder-admin-safe-projection-contract-foundation",
  "phase": "v0",
  "status": "rejected_after_exhausted_recheck",
  "kind": "critical_pure_unpublished_thresholded_admin_projection_contracts",
  "goal": "Implement pure thresholded aggregate projection contracts for founder/admin visibility without individual identities, PII, tenant private data, operator authentication, publication or mutation authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Closed policy/authority/input/projection identities cover legitimate thresholded aggregate families, refuse small cells/private/open/cross-policy facts, preserve copy/restart/resource/mutations and pass Critical review; all individual, privileged and effecting gates remain closed."},
  "risk_tags": ["critical", "admin", "privacy", "tenant-isolation", "small-cell", "no-external-effect"],
  "depends_on": ["strategy-os-v0-founder-admin-safe-projection-policy-replan"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/decision.json", "policy": "Only aggregate-only non-publishable pure projections may proceed; operator auth and individual access remain blocked."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/decision.json", "sections": ["observed_sources", "safe_pure_contract", "structural_exclusions", "fact_separation", "injected_without_default", "owner_security_privacy_gates"]},
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/policy-matrix.md", "sections": ["V0 founder/admin safe projection matrix"]},
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Founder operator and complimentary entitlement"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/admin/__init__.py", "paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-contract-foundation.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation"],
  "new_paths": ["paper-trader/backend/app/admin/__init__.py", "paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-contract-foundation.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation"],
  "protected_paths": ["paper-trader/backend/app/accounts", "paper-trader/backend/app/billing", "paper-trader/backend/app/support", "paper-trader/backend/app/product_analytics", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/api", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/providers", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Create frozen canonical values and pure factories only; no DB, clock lookup, HTTP, environment, network, filesystem or dependency.",
    "Injected finite policy defines projection families, allowed dimension codes, operational bands and minimum cohort threshold with no production default.",
    "OperatorProofReferences carries only binding, permission-policy and step-up-proof content addresses and authenticates nobody.",
    "SafeAggregateInput carries one family, sorted finite dimensions, bounded count, source receipt address and injected UTC time; no individual ID.",
    "AdminAggregateProjectionCandidate derives only after exact policy/authority/source validation and count >= threshold; it carries publishable=false, access_activated=false and no mutation authority.",
    "Every factory/derivation/decode revalidates current values and exact injected policy/proof/source. Raw/direct/copy values are untrusted.",
    "No account/user/tenant/session/support-case/subject/source-event identifier, PII, strategy/research/monitoring detail/money/provider/payment/credential/free-text/raw transport field.",
    "No operator session/impersonation, individual view, persistence/SQL/API/frontend, mutation/audit, publication or deployment."
  ],
  "acceptance": [
    "One legitimate aggregate for each five family types passes at/above threshold; below-threshold and zero/negative/bool/oversize counts refuse.",
    "Cross-policy/authority/source/family/dimension/threshold/time substitutions refuse; canonical identity covers all answer-changing fields.",
    "Projection fields exclude all individual/private/money/credential/raw/free-form facts and exact constructor/signature/AST/import guards pass.",
    "Direct/copy/deepcopy/replace/object-mutated inputs/projections receive complete use-time validation; publishable/access flags cannot flip.",
    "Strict duplicate/noncanonical/Unicode/size/depth/recursion/exact-version/count/time/restart tests, at least eight isolated mutations and 100000 decisions under 30 seconds/2 MiB pass.",
    "Critical SPEC/QUALITY review passes; all privileged/individual/effecting owner gates remain explicit."
  ],
  "test_plan": ["RED/GREEN five-family policy/authority/input/projection codecs and positive controls.", "Threshold, cross-binding, privacy surface and copy/mutation matrix.", "Strict hostile codec/restart/AST/import/effect guards.", "At least eight policy/authority/source/threshold/privacy/publishability use-site mutations restored.", "100000 decisions and architecture/protected attribution."],
  "risk_classification": {"tier": "Critical", "reason": "An aggregate projection can leak small cohorts or become an authority/impersonation surface before any admin UI exists."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_founder_admin_projection_contract_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/admin/__init__.py", "paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-contract-foundation.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation"], "output": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_founder_admin_projection_contract_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "This is the future cross-tenant operator visibility boundary.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review-package.json", "review_paths": ["paper-trader/backend/app/admin/__init__.py", "paper-trader/backend/app/admin/projection_contracts.py", "paper-trader/backend/tests/test_v0_admin_projection_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-contract-foundation.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation"], "exclude_paths": ["paper-trader/backend/app/accounts", "paper-trader/backend/app/billing", "paper-trader/backend/app/support", "paper-trader/backend/app/product_analytics", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/api", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No operator auth/session/permissions, production threshold/catalogue, PII/individual access, persistence/SQL/API/frontend, mutation/audit, incident access or deployment."],
  "stop_conditions": ["A safe projection requires individual IDs, PII, private/money facts, arbitrary properties, small-cell override, impersonation or effect.", "Existing admin path ownership appears."],
  "deployment_impact": {"classification": "compatible pure unpublished contracts", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "implementation_evidence": {
    "assignment": "v0_founder_admin_projection_contract_owner",
    "focused_cases": 33,
    "positive_family_controls": 5,
    "isolated_use_site_mutations": 12,
    "resource_decisions": 100000,
    "protected_hashes_compared": 9716,
    "architecture_checked_files": 461,
    "product_sha256": "03f3e2d09f8cbffad5912533212b038307c2340703ea7fe6e8180eebf3cf911f",
    "tests_sha256": "fced6c20ead75e716aac3e78a2079eaa85e51829b13573fef78fe18af92bec88",
    "focused_green_sha256": "cb27fd7f42b6d224dfa05db3fc71777af0a383bcb32d6cfe1be44ebfcab22739",
    "architecture_sha256": "4688ad66a2bf15313b13a9a3d44471a2b905d117ef6ba856ea2ef270d7a21dc5",
    "protected_compare_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "review_package": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review-package.json"
  },
  "first_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "verdict_sha256": "0557b83fe624ab419d4c98e127b96c4402a3197d87a8185a078399b009a5d0ed", "findings": ["V0-FAP-CR-001", "V0-FAP-CR-002"], "evidence_gaps": ["V0-FAP-EG-001"], "rechecks_used": 0, "rechecks_remaining": 1, "correction_scope": "Replace arbitrary dimension strings with one closed safe code type and add hostile value-level/mutation evidence; seal the actual protected snapshots.", "deployment": false},
  "correction_evidence": {
    "status": "correction_complete_pending_focused_recheck",
    "closes": ["V0-FAP-CR-001", "V0-FAP-CR-002", "V0-FAP-EG-001"],
    "admin_dimension_codes": 10,
    "hostile_dimension_sentinels": 22,
    "focused_cases": 56,
    "positive_family_controls": 5,
    "resource_decisions": 100000,
    "product_sha256": "18c5f571647834da354e43f26cf8f0de4159a2bc093ba8efed99f5353af1a967",
    "tests_sha256": "5b492e05fe38e387972492b910400985daac0aad8eca2362d765a86d906c516b",
    "focused_green_sha256": "a5bad37fc2190bed21c8f7befa636dc4fbe8b2f6206048cff2d3378a016c4864",
    "permissive_mutation_sha256": "5d73d95cebaaebfccc1e161fa616dfd6174c1c2591bfd2bc4b0a06329dabbd6c",
    "architecture_sha256": "4688ad66a2bf15313b13a9a3d44471a2b905d117ef6ba856ea2ef270d7a21dc5",
    "protected_before": {"entries": 9716, "sha256": "3933a9171e9e9f8c60e3a84cff82e847d13dacda10af8520bc487561763bbc8c"},
    "protected_after": {"entries": 9716, "sha256": "3933a9171e9e9f8c60e3a84cff82e847d13dacda10af8520bc487561763bbc8c"},
    "protected_comparison_sha256": "998668c27c4b8bd828ce90cdcc3495087487239bccafbb4ba4d8a9935c847390",
    "protected_claim": "Byte-identical continuity only; no assignment authorship claim.",
    "report": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/correction-report.md",
    "review_package": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/corrected-review-package.json"
  },
  "final_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "first_verdict_sha256": "0557b83fe624ab419d4c98e127b96c4402a3197d87a8185a078399b009a5d0ed", "corrected_package_sha256": "b01541e1af82f9c6b1ec36504d76b62c25feb01e5853ffd9cce9813beb4b9350", "recheck_verdict_sha256": "2dcab3344c15fff44f3fb478b6ca72548a7dd452b992f9f8118f4b2186a68ba2", "open_findings": ["V0-FAP-CR-001-R1", "V0-FAP-CR-002-R1"], "rechecks_used": 1, "rechecks_remaining": 0, "next_action": "REPLAN_REQUIRED", "successor_replan": "strategy-os-v0-founder-admin-numeric-code-replan", "publication": false, "deployment": false},
  "nonclaims": ["No operator authentication, individual admin view, production threshold, persistence, mutation, publication, API/frontend, deployment or V0 completion."
  ]
}
---

# Founder/admin safe projection contract foundation

Pure thresholded, aggregate-only, non-publishable projection candidates.

## Implementation receipt

- Assignment: `v0_founder_admin_projection_contract_owner`
- Status: `implementation_complete_pending_critical_review`
- Risk: Critical privacy, tenant-isolation and authority boundary.
- Outcome: five injected finite aggregate-family catalogues, injected contiguous
  operational bands and an injected minimum cohort threshold now control pure
  frozen projection candidates. There is no production threshold or catalogue
  default.
- Authority: operator binding, permission-policy and step-up proof values remain
  opaque content addresses. They authenticate nobody and activate no access.
- Safety: input and projection use sites revalidate exact policy, proof, source,
  family, time and threshold context. Counts below the threshold refuse;
  `publishable` and `access_activated` remain false.
- Exclusions: no individual, user, tenant, account, session, support-case,
  subject or source-event identity; no PII, tenant-private strategy/research/
  monitoring details, money, provider/payment/credential, free-text or raw
  transport facts; no persistence, SQL, API, frontend, audit, mutation,
  publication or deployment.
- Evidence: real RED, 33 focused cases, five positive family controls, strict
  codecs/restart/copy/AST/import guards, 12 isolated use-site mutations,
  reversible publication-guard mutation, 100,000 bounded decisions, architecture
  validation and 9,716 unchanged protected-file hashes are sealed under
  `.agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/`.
- Deployment impact: compatible pure unpublished contracts only; production
  readiness, rehearsal and deployment remain false.
- Owner gates: generic production dimension/band codes, production cohort
  threshold, operator auth/session/permissions, PII or individual access,
  persistence, API/frontend, audit/mutation, publication and deployment.

## Focused correction receipt

- Immutable first verdict: `0557b83fe624ab419d4c98e127b96c4402a3197d87a8185a078399b009a5d0ed`.
- Status: `correction_complete_pending_focused_recheck`.
- `AdminDimensionCode` is one fixed 10-member safe v1 enum. Family policy values
  are sorted subsets of that enum; raw caller strings never enter aggregate input
  or projection payloads, including strings equal to serialized safe codes.
- Twenty-two hostile sentinels spanning tenant/account identity, credentials,
  token/secret, PII/email, private product facts, symbol/signal, money/PnL,
  provider/broker/payment, raw transport and long token-like values refuse across
  direct, self-attested policy, factory and codec paths.
- An isolated permissive mutation re-enabled raw strings and all 22 hostile
  controls failed. The restored source passes all 56 focused cases, including the
  original five positives, exact context/copy/restart, false flags and 100,000
  decision resource bound.
- Two standalone normalized 9,716-entry protected manifests have identical
  SHA-256 `3933a9171e9e9f8c60e3a84cff82e847d13dacda10af8520bc487561763bbc8c`.
  This proves byte continuity only and does not claim assignment authorship.
- Production catalogue selection and threshold, operator authority, individual
  access, persistence, API/frontend, publication and deployment remain closed.
