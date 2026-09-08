---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-browser-auth-rfc4122-identity-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_principal_identity_replan",
  "goal": "Resolve V0-ACSA-IDENTITY-001 by binding invited browser enrollment to the already accepted canonical RFC4122 user and tenant identity contract without lossy normalization, aliasing, or weakening policy identifiers.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision freezes the canonical issuance, prelaunch compatibility, exact correction paths, RED/GREEN/session/tenant/restart evidence and shared-assembly resume gate."},
  "risk_tags": ["critical", "auth", "identity", "tenancy", "entitlements", "compatibility", "privacy"],
  "depends_on": ["strategy-os-v0-account-lifecycle-contract-foundation", "strategy-os-v0-account-commerce-shared-assembly"],
  "dependency_gate": {"finding": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly/invited-identity-contract-blocker.json", "finding_sha256": "41d8ada8fcc2a32f20a545e46745d668603b04c6791da742b25958e80a880e39", "shared_package_sha256": "bd3df978f32fb1ffca2daca4a16756c78cc9db7ce0d2a78ca5255aef4ce11155", "policy": "Do not lowercase, rewrite, alias, or broaden identities inside account commerce. Resolve issuance against the accepted account-lifecycle authority and keep shared product bytes frozen."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly/invited-identity-contract-blocker.json", "sections": ["failure_hypothesis", "required_invariant", "correction_evidence_required", "browser_red"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-account-lifecycle-contract-foundation.md", "sections": ["scope", "acceptance", "Account lifecycle contract foundation"]},
    {"path": "paper-trader/backend/app/accounts/lifecycle_contracts.py", "sections": ["_opaque_uuid", "AuthenticatedAccountContext", "CurrentAccountAuthority"]},
    {"path": "paper-trader/backend/app/accounts/browser_auth.py", "sections": ["enroll", "login", "change_password", "switch_workspace"]},
    {"path": "paper-trader/backend/app/billing/policy_contracts.py", "sections": ["_identifier", "ProfileEvidence", "TrialEligibilityEvidence", "CouponProof"]},
    {"path": "paper-trader/backend/tests/test_v0_account_lifecycle_contracts.py", "sections": ["test_user_and_tenant_ids_are_opaque_canonical_rfc4122_values", "restart round trip"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["Backend execution rules"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-replan.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-replan.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Prove the controlling identity authority: accepted account lifecycle requires exact canonical non-nil RFC4122 user and tenant strings, while browser enrollment currently issues token-url-safe values and billing principal fields accept only the lowercase contract alphabet.",
    "Choose exact future issuance and collision behavior without client-authored IDs, lowercasing, truncation, aliasing, policy-identifier broadening, or a second principal authority.",
    "Classify every existing identity population: accepted RFC4122 rows, fixed legacy fixtures, prelaunch token-url-safe browser rows, sessions, memberships and account-commerce references. Freeze a compatibility/reset/migration decision from direct deployment-state evidence rather than assuming production data exists.",
    "Define the smallest correction paths and tests for invitation enrollment, login, bootstrap, password replacement, workspace switch, session revocation, owner isolation, restart and account profile/beta/coupon composition.",
    "Preserve email normalization separately from opaque identity; no raw password, invitation, coupon, strategy, broker credential or customer research fact enters evidence.",
    "Freeze the shared assembly hashes and exact resume gate after one independent Critical correction review."
  ],
  "acceptance": [
    "Decision names one canonical principal identity format and proves it matches lifecycle, database width/index/FK, session, commerce, entitlement and operator seams without changing policy identifier semantics.",
    "Existing-state disposition is evidence-backed and cannot silently relabel an owner, merge two principals, orphan a session/membership, or rewrite accepted evidence.",
    "Successor owns the smallest exact source/test paths, supported-database evidence, reversible mutations, protected hashes and one Critical SPEC/QUALITY review.",
    "Shared assembly remains frozen until the correction is accepted and the full real generated-identity E2E is rerun."
  ],
  "test_plan": ["Read-only identity producer/consumer/schema/test inventory, exact fresh-browser RED confirmation, current deployment-state audit, collision/compatibility matrix and successor capsule seal. Product implementation belongs only to the successor."],
  "risk_classification": {"tier": "Critical", "reason": "Changing principal identity issuance or compatibility can cross tenants, orphan account authority, invalidate entitlements, or alias owners."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_browser_auth_rfc4122_identity_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-auth-identity-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-replan.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan"], "output": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_browser_auth_rfc4122_identity_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical replan; the implementation successor receives independent Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-replan.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan/decision.json", "verdicts": ["IDENTITY", "COMPATIBILITY", "TENANCY", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/schema/migration/frontend edit, identity rewrite, account-commerce workaround, provider/money, production data, commit, deployment or V0 claim."],
  "stop_conditions": ["Evidence shows released production browser identities require an owner-approved migration or destructive rewrite.", "Canonical RFC4122 issuance cannot compose with an accepted persisted authority without a schema or identity-version change.", "Shared auth or account-commerce source receives concurrent ownership."],
  "deployment_impact": {"classification": "none for read-only replan; successor auth-critical", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "result": {"decision": "KEEP + HARDEN", "issuance": "server-side str(uuid.uuid4()) for user_id and organization_id", "compatibility": "forward-only; preserve canonical RFC4122 and explicit legacy bytes; no migration/reset/alias because browser auth is uncommitted and undeployed; stop if a durable noncanonical browser row is evidenced", "decision_sha256": "9469d4a52960e1a70fa6848a9bcb90b12a03194885bcbafba8496292e5afab94", "successor_capsule_sha256": "e840a6308b0771179b469bf18ae5b601af5663ade6a11e0168814786ceeaaa34", "shared_resume_hashes_sha256": "492f45709bcf9b65318f3594a3a7edc22bc723fe42043114ef2952426a388963", "evidence_index_sha256": "2f16f267abd7638b99b0b6d07b3c00bba10467394dadf058c53765ecb9a25491", "compatibility_probe": "PASS", "frozen_hashes_checked": 31, "architecture": "488 files / 0 failures", "product_writes": 0, "deployment": false, "blocker": null},
  "nonclaims": ["No auth fix, identity migration/reset, shared publication, provider, deployment, release readiness or V0 completion."]
}
---

# Browser-auth RFC4122 identity replan

Bind future invited-user issuance to the accepted principal identity authority.
Do not repair the symptom by normalizing identities inside account commerce.
