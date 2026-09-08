---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-account-lifecycle-contract-foundation",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_pure_unpublished_account_lifecycle_authority_contracts",
  "goal": "Implement immutable pure contracts for post-auth account context, lifecycle requests, retained-exception candidates and separate founder operator-binding candidates without email, secrets, persistence, access activation or deletion effects.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Closed deterministic policy/context/request/founder-binding identities cover legitimate synthetic local-auth flows, reject cross-user/tenant/session/policy/proof substitutions, preserve fact separation/restart/resource/mutations and pass one Critical review; all external, durable and effecting gates remain closed."},
  "risk_tags": ["critical", "account", "auth", "privacy", "tenant-isolation", "founder-bootstrap", "no-external-effect"],
  "depends_on": ["strategy-os-v0-account-lifecycle-local-authority-policy-replan", "strategy-os-v0-auth-session-transport", "strategy-os-v0-platform-operations-persistence", "strategy-os-v0-entitlement-policy-contract-foundation"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-account-lifecycle-local-authority-policy-replan/decision.json", "policy": "Only pure opaque non-effecting contracts may proceed; Google, PII, retention, deletion, operator session and persistence remain blocked."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-lifecycle-local-authority-policy-replan/decision.json", "sections": ["accepted_authority", "safe_pure_contract", "fact_separation", "prohibited", "injected_configuration_without_default", "unresolved_owner_external_legal", "later_owners"]},
    {"path": ".agent/runs/strategy-os-v0-account-lifecycle-local-authority-policy-replan/policy-matrix.md", "sections": ["V0 account lifecycle local-authority matrix"]},
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Founder operator and complimentary entitlement"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/accounts/lifecycle_contracts.py", "paper-trader/backend/tests/test_v0_account_lifecycle_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-lifecycle-contract-foundation.md", ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation"],
  "new_paths": ["paper-trader/backend/app/accounts/lifecycle_contracts.py", "paper-trader/backend/tests/test_v0_account_lifecycle_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-lifecycle-contract-foundation.md", ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation"],
  "protected_paths": ["paper-trader/backend/app/accounts/__init__.py", "paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/app/api", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/billing", "paper-trader/backend/app/product_analytics", "paper-trader/backend/app/support", "paper-trader/backend/app/admin", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/providers", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Create frozen canonical values and pure factories only; no DB, clock lookup, HTTP, environment, network, filesystem or external dependency.",
    "Injected finite policy defines issuer classes, account states, onboarding steps, lifecycle request types and retained-exception codes with no production default.",
    "AuthenticatedAccountContext binds opaque RFC4122 user/tenant IDs, exact session authority content address, issuer class, policy identity and injected UTC authenticated time; no email or secret.",
    "LifecycleRequestCandidate binds exact context, reauth proof address, request type/time and effected=false. RetainedExceptionCandidate uses only policy-approved codes and creates no retention promise.",
    "FounderMatchProofReference contains only server proof/policy content addresses. OperatorBindingCandidate binds singleton FOUNDER slot, opaque user, permission/bootstrap addresses and activated=false; no operator session.",
    "Optional complimentary candidate address is a reference to a separate entitlement-policy candidate and cannot activate access or create payment/coupon facts.",
    "Every factory/derivation/decode completely revalidates current values and exact injected policy/context/proof; raw values are untrusted.",
    "No Google token/link, email/password/session secret, contact PII, actual export/deletion, retention duration, membership/entitlement mutation, operator step-up/admin, API/frontend or deployment."
  ],
  "acceptance": [
    "Canonical identities change for every answer-changing policy/user/tenant/session/issuer/time/request/reauth/proof/permission/exception/reference field; exact codecs refuse open/extra values.",
    "One legitimate synthetic local-auth account context, export/deletion request and founder binding candidate pass so universal denial cannot pass.",
    "Cross-user/tenant/session/policy/reauth/founder-proof/permission/bootstrap/complimentary substitutions refuse; direct/copy/deepcopy/replace/object-mutated values are revalidated at use.",
    "AST/signature guards prove email/password/token/cookie/free-text/private product/money/provider/payment fields and forbidden imports/effects are absent.",
    "Strict duplicate/noncanonical/Unicode/size/depth/recursion/UUID/time/exact-int-version/count tests, fresh restart, at least eight isolated mutations and 100000 decisions under 30 seconds/2 MiB pass.",
    "One Critical SPEC/QUALITY review passes; all external/durable/effect gates remain explicit."
  ],
  "test_plan": ["RED/GREEN policy/context/request/exception/founder/operator codecs and positive controls.", "Cross-binding, current-value copy/mutation, strict hostile input and restart matrix.", "Fact-separation/signature/AST/import/effect guards.", "At least eight factory/derivation/decode/fact-separation mutations with restoration.", "100000 pure decisions and architecture/protected attribution."],
  "risk_classification": {"tier": "Critical", "reason": "These candidates sit directly before account deletion and singleton platform authority and must fail closed without conflating membership or entitlement."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_account_lifecycle_contract_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/accounts/lifecycle_contracts.py", "paper-trader/backend/tests/test_v0_account_lifecycle_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-lifecycle-contract-foundation.md", ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation"], "output": ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_account_lifecycle_contract_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Pure values are the future account deletion and singleton operator authority boundary.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation/review-package.json", "review_paths": ["paper-trader/backend/app/accounts/lifecycle_contracts.py", "paper-trader/backend/tests/test_v0_account_lifecycle_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-lifecycle-contract-foundation.md", ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation"], "exclude_paths": ["paper-trader/backend/app/accounts/__init__.py", "paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/app/api", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/billing", "paper-trader/backend/app/product_analytics", "paper-trader/backend/app/support", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No Google/linking, contact PII, founder recovery/rebind, operator step-up/MFA, retention/export/delete/holds, email, persistence/API/frontend or deployment action."],
  "stop_conditions": ["A safe contract requires email matching, secrets, client authority, actual deletion/access or coupling membership/operator/entitlement/payment facts.", "Existing lifecycle_contracts path ownership appears."],
  "deployment_impact": {"classification": "compatible pure unpublished contracts", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "implementation_evidence": {
    "pre_metadata_review_package_sha256": "b8a26e3a993d179a8c70430654a260f8424a1c1ae66c7bcfc17b369996845061",
    "source_sha256": "4d245f774805caa5b98e4cca991be5e9da2cbd83365783877f178fadac47d154",
    "tests_sha256": "223784dbbfb598c184f4f097b8eefe2b661323dbf7e9f396f6dc2d82c6e26e86",
    "report_sha256": "5d8d5e03aadd15dab3778e1c610378782aae7a44a52feadbc4ff0144e4b5309e",
    "focused_tests": 41,
    "isolated_mutations": 9,
    "resource": {"decisions": 100000, "elapsed_seconds": 9.599, "sampled_peak_bytes": 587580},
    "architecture": {"checked_files": 459, "failures": 0},
    "protected_continuity": "Normalized protected manifests matched before and after sealing; generated bytecode and dependency trees were excluded.",
    "effects": {"account": false, "export_delete": false, "retention": false, "operator_activation": false, "entitlement": false, "payment": false, "persistence": false, "api": false, "frontend": false, "deployment": false}
  },
  "first_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "verdict_sha256": "014b69d86b34e0b2c099b53812efd09bf1b3f4b50cb0b16189c8fdde17ab50d6", "findings": ["V0-ALC-CR-001", "V0-ALC-CR-002", "V0-ALC-CR-003"], "evidence_gaps": ["V0-ALC-EG-001", "V0-ALC-EG-002", "V0-ALC-EG-003"], "rechecks_used": 0, "rechecks_remaining": 1, "correction_scope": "Bind downstream factories/decoders to independently expected account/session authority; bind request time at every consumer; fully revalidate request sources before retained derivation/decode.", "deployment": false},
  "correction_evidence": {"status": "correction_complete_pending_focused_recheck", "source_sha256": "6d34034d9397a40756492f63ba509540d6fc4b31b7cf1f181b0a457ee428e6e0", "tests_sha256": "c456f1e6b05505c44f679e6dc8dd41e30e8b5fcb21aed56c44a2e1f782aeef4f", "report_sha256": "2a04d7c9c0e45f156ba20d1e7d8831d64d8cb22263b928fe8af3e5df2a091757", "reviewer_counterexamples": 12, "focused_tests": 53, "isolated_mutations": 12, "resource": {"decisions": 100000, "elapsed_seconds": 13.475, "sampled_peak_bytes": 589730}, "architecture": {"checked_files": 459, "failures": 0}, "closed_findings": ["V0-ALC-CR-001", "V0-ALC-CR-002", "V0-ALC-CR-003"], "closed_evidence_gaps": ["V0-ALC-EG-001", "V0-ALC-EG-002", "V0-ALC-EG-003"], "effects": {"account": false, "export_delete": false, "retention": false, "operator_activation": false, "entitlement": false, "payment": false, "persistence": false, "api": false, "frontend": false, "deployment": false}},
  "final_review": {"verdict": "SPEC PASS / QUALITY PASS / final PASS", "first_verdict_sha256": "014b69d86b34e0b2c099b53812efd09bf1b3f4b50cb0b16189c8fdde17ab50d6", "corrected_package_sha256": "330bf3e8385d45921b4c3cfdc5da61a4102425a6290430064eee236cf70292c0", "recheck_verdict_sha256": "6b63d069c025f545f85900da7b036d37be25eae06298ce393098ea5e70a3aac8", "closed_findings": ["V0-ALC-CR-001", "V0-ALC-CR-002", "V0-ALC-CR-003", "V0-ALC-EG-001", "V0-ALC-EG-002", "V0-ALC-EG-003"], "rechecks_used": 1, "rechecks_remaining": 0, "account_mutation": false, "operator_activation": false, "deployment": false},
  "nonclaims": ["No account mutation, Google, founder binding, complimentary access, export/deletion, retention/email, operator session/admin, API/frontend, deployment or V0 completion."
  ]
}
---

# Account lifecycle contract foundation

Pure opaque, non-effecting account lifecycle and founder-binding candidates only.

## Implementation handoff

- Review state: `correction_complete_pending_focused_recheck` after the bounded
  correction to first-review findings `V0-ALC-CR-001` through `003`.
- Product surface: one unpublished pure module and one focused test module; no
  package export, persistence, schema, configuration, runtime, API or frontend
  integration changed.
- Corrected focused verification: 53 tests pass, including a legitimate local-auth
  context, export and deletion requests, a retained-exception candidate, a
  non-activating singleton founder candidate, strict restart/codec/AST checks,
  twelve isolated permissive mutations with source restoration, and 100000 pure
  request decisions under the declared time and memory bounds.
- Evidence report:
  `.agent/runs/strategy-os-v0-account-lifecycle-contract-foundation/report.md`.
- One authorized focused recheck remains. CURRENT/PROGRAMME remain unchanged.
