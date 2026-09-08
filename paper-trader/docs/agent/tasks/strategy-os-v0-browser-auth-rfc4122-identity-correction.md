---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-browser-auth-rfc4122-identity-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_browser_principal_identity_correction",
  "goal": "Issue invited browser user and organization identities as server-generated canonical non-nil RFC4122 UUIDv4 text and prove exact session, tenant and account-commerce composition without normalization, aliasing, migration or policy-identifier changes.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The source-only correction passes SQLite and PostgreSQL 16 generated-principal, collision, session, tenant, restart, commerce, privacy and mutation evidence; protected hashes pass; one independent Critical reviewer returns SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "auth", "identity", "tenancy", "entitlements", "compatibility", "privacy", "restart"],
  "depends_on": ["strategy-os-v0-browser-auth-rfc4122-identity-replan"],
  "dependency_gate": {"decision_sha256": "9469d4a52960e1a70fa6848a9bcb90b12a03194885bcbafba8496292e5afab94", "successor_sha256": "e840a6308b0771179b469bf18ae5b601af5663ade6a11e0168814786ceeaaa34", "shared_resume_sha256": "492f45709bcf9b65318f3594a3a7edc22bc723fe42043114ef2952426a388963", "policy": "One serialized source/test owner; account-commerce, billing, schema, migrations and shared frontend remain frozen until Critical acceptance."},
  "session_handle_gate": {"runtime_recovery_package_sha256": "a833323703c3357825b05a80ee9fc927ca6e0800d0c88945fb6bce976e3a2e4d", "runtime_recovery_verdict_sha256": "9d6d559123321e0399935dc4267b7791d6d1029adad3916389f60d62e4570f48", "SPEC": "PASS", "QUALITY": "PASS", "closed_findings": ["V0-SRH-CR-001", "V0-SRH-CR-002", "V0-SRH-CR-003"], "resume_policy": "Rebind accepted principal/test hashes, rerun full UUID integration on SQLite/PostgreSQL 16, reseal, then dispatch the declared Critical review."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan/decision.json", "sections": ["canonical_identity", "collision_policy", "population_disposition", "invariant_matrix", "shared_resume"]},
    {"path": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan/successor-capsule.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-replan/shared-resume-hashes.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly/invited-identity-contract-blocker.json", "sections": ["browser_red", "required_invariant", "correction_evidence_required"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/backend/tests/test_browser_auth_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-correction.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction"],
  "new_paths": ["paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-correction.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction"],
  "protected_paths": ["paper-trader/backend/app/accounts/lifecycle_contracts.py", "paper-trader/backend/app/account_commerce", "paper-trader/backend/app/billing", "paper-trader/backend/app/api", "paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations", "paper-trader/backend/tests/test_browser_auth.py", "paper-trader/backend/tests/test_v0_account_commerce_routes.py", "paper-trader/backend/tests/test_v0_account_commerce_service.py", "paper-trader/backend/tests/test_v0_account_commerce_migration.py", "paper-trader/backend/tests/test_v0_account_lifecycle_contracts.py", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Import uuid4 from uuid and replace only the two secrets.token_urlsafe(18) enrollment principal producers with str(uuid4()). Keep invitation, browser/session bearer, CSRF and counter token generation unchanged.",
    "Keep invitation consume, user, organization, membership, credential and session writes in the existing transaction. Inject user and organization primary-key collisions and prove generic 503, full rollback, unchanged existing owner, unconsumed invitation and later successful reuse. Do not alias, normalize, suffix or internally retry.",
    "Prove fresh generated user and organization IDs are distinct, lowercase canonical non-nil RFC4122 version 4 and propagate byte-for-byte through bootstrap, login, password replacement, workspace switch, membership/session restart and two-owner isolation.",
    "Prove real generated IDs compose with protected lifecycle, profile, beta and coupon contracts without editing account-commerce or billing policy bytes. Uppercase, underscore and nil samples remain refused.",
    "Run the exact matrix on isolated SQLite and PostgreSQL 16, with exact head 0049 and no migration delta; stop and remove all owned clusters/databases/processes.",
    "Correct only the historical browser-auth migration test fixture exposed by the affected rerun: reflect the actual tables present at a historical revision instead of querying them through the current 0049 ORM shape, and create the invitation CLI fixture at the tool-required current head. Do not change migration or CLI behavior.",
    "Keep passwords, invitations, coupons, session bearers, strategies, broker credentials and customer research out of responses/logs/evidence. Seal reversible issuance/collision/propagation mutations and protected/shared hashes."
  ],
  "acceptance": [
    "Fresh invited enrollment issues two distinct canonical non-nil RFC4122 UUIDv4 strings and exact persisted/session/account-commerce references match on SQLite and PostgreSQL 16.",
    "Login, bootstrap, cookie rotation, password replacement, workspace switch, membership refusal, restart and two-owner isolation preserve exact principal attribution.",
    "User and organization collision probes refuse generically, roll back every new fact, preserve existing ownership and invitation reuse, then pass after source restoration.",
    "No lifecycle, billing, account-commerce, schema, migration or frontend change exists; head remains 0049; privacy and protected/shared hashes pass.",
    "The historical 0042-to-0043 migration assertions remain meaningful against reflected historical schemas, and the current invitation CLI passes only against exact head 0049.",
    "One independent critical-reviewer returns SPEC PASS and QUALITY PASS before shared assembly resumes."
  ],
  "test_plan": ["Focused generated-principal RED/GREEN, collision/atomicity, session/password/workspace/restart/two-owner, commerce composition and privacy tests on SQLite and isolated PostgreSQL 16.", "Affected browser-auth/lifecycle/account-commerce/migration tests, reversible issuance/collision/propagation mutations, architecture and protected/shared hash manifests."],
  "risk_classification": {"tier": "Critical", "reason": "Principal issuance affects tenant ownership, sessions and entitlement attribution; a wrong correction could alias owners or orphan authority."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_browser_auth_rfc4122_identity_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-auth-source-test-evidence-package", "depends_on": [], "write_paths": ["paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/backend/tests/test_browser_auth_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-correction.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction"], "output": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_browser_auth_rfc4122_identity_correction_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Principal issuance and collision atomicity cross authentication, tenancy, sessions and entitlement attribution.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/review-package.json", "review_paths": ["paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/backend/tests/test_browser_auth_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-rfc4122-identity-correction.md", ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction"], "exclude_paths": ["paper-trader/backend/app/accounts/lifecycle_contracts.py", "paper-trader/backend/app/account_commerce", "paper-trader/backend/app/billing", "paper-trader/backend/app/api", "paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 0},
  "review_result": {"package_sha256": "dd7831c4d967e3bac0660df12845d9d2ec6540868f15b41cd6e4106d3b4d4b3f", "seal_sha256": "6a60681c398b8cef12c8cf04f30ca3e7546dc3a860709ed890dea97be7ac4b3b", "verdict_sha256": "0b49f946b13e552501d8b255bfa39e56012e6982aad8c310e6f3428d9a3e6c1e", "SPEC": "PASS", "QUALITY": "PASS", "open_findings": [], "superseded_blocked_package_sha256": "0fe301be147dd88206840b4b006c248b725d7f80f3eded10fa07103880d69425", "shared_assembly_released": true},
  "owner_gates": ["No identity migration/reset/alias, account-commerce/billing/schema/migration/frontend edit, provider/money, production data, shared resume, commit, deployment or V0 claim."],
  "stop_conditions": ["Any durable or released noncanonical browser identity is evidenced.", "Any accepted seam cannot represent canonical RFC4122 text without schema or contract-version change.", "Any protected path requires editing or shared source receives concurrent ownership."],
  "deployment_impact": {"classification": "compatible source-only correction within an unpublished subsystem", "schema_or_migration": false, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No migration, reset, alias, legacy rewrite, account-commerce/billing/frontend/provider/money change, deployment, release readiness or V0 completion."]
}
---

# Browser-auth RFC4122 identity correction

Correct only invited-principal issuance and prove its full authority propagation.
Shared account publication stays frozen until independent Critical acceptance.
