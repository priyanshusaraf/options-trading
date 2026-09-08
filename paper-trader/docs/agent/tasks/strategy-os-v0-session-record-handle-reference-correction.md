---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-session-record-handle-reference-correction",
  "phase": "v0",
  "status": "correction_package_ready",
  "kind": "critical_session_record_handle_reference_correction",
  "goal": "Issue every new UserSession record handle as canonical lowercase UUIDv4 text, retire caller-selected handles, and prove exact bearer separation, session lifecycle, persistence, tenant and account-commerce composition without rewriting existing authority or weakening consumers.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The principal source/test correction passes SQLite and PostgreSQL 16 grammar, collision, lifecycle, restart, tenant, commerce, privacy and mutation matrices; protected hashes pass; one independent Critical reviewer returns SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "auth", "session", "identity", "tenancy", "entitlements", "privacy", "restart", "collision"],
  "depends_on": ["strategy-os-v0-session-record-handle-reference-replan"],
  "dependency_gate": {"decision_sha256": "864dfac21d1be8458ef4ec5ab5338cb6881db28c83c66b768179dfaf0c437534", "successor_sha256": "91db1d31935d41f91060ba997df732ba73101672cecbc4ccd38ea0d1edf33a8a", "shared_resume_sha256": "eafac9dc767e6db764bd2f83e9a773af342a457afdda3cf210ca42d8667e8ec5", "policy": "One serialized principal/test owner; UUID correction, account-commerce, platform operations, schema, migrations and shared frontend remain frozen until Critical acceptance."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-replan/decision.json", "sections": ["canonical_contract", "producer_and_caller_policy", "collision_and_transaction_policy", "existing_state_disposition", "resume_gates"]},
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-replan/successor-capsule.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-replan/shared-resume-hashes.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/session-handle-blocker.json", "sections": ["all"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/api/principal.py", "paper-trader/backend/tests/test_user_sessions.py", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-correction.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-correction"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-correction.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-correction"],
  "protected_paths": ["paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/app/account_commerce", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/session.py", "paper-trader/backend/app/api/connection_routes.py", "paper-trader/backend/migrations", "paper-trader/backend/tests/test_browser_auth.py", "paper-trader/backend/tests/test_browser_auth_migration.py", "paper-trader/backend/tests/test_v0_account_commerce_service.py", "paper-trader/backend/tests/test_v0_account_commerce_routes.py", "paper-trader/backend/tests/test_v0_account_commerce_publication.py", "paper-trader/backend/tests/test_connection_routes.py", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Import uuid4 in principal.py and use str(uuid4()) at issue_user_session and only the absent-digest branch of bootstrap_legacy_session. Remove the unused optional session_id keyword and caller override. Do not change any bearer-token or digest call.",
    "Require generated handles to be exact 36-character lowercase canonical UUIDv4 text while keeping the persisted/consumer maximum at 64 and preserving every existing handle and digest byte-for-byte.",
    "Keep caller-owned transaction and database PK/token-digest uniqueness as collision authority. Inject handle and digest collisions; prove generic refusal, rollback, no response token/cookie or partial BrowserSession/OAuth state, unchanged existing owner and successful whole-operation retry after restoration. No internal retry, alias, suffix, normalization or rebind.",
    "Prove exact issued/persisted/Principal/BrowserSession/AccountAuthority session-reference equality across enrollment, login, password change, workspace switch, logout/revocation, expiry, restart, concurrent issuance/revocation and two-owner commerce.",
    "Prove leading dash/underscore and prefixed-base64url forbidden-substring REDs; prove the UUID alphabet cannot form any protected operations privacy term without changing platform/account consumers.",
    "Run affected user-session/browser-auth/UUID-identity/migration/account-commerce/session-bound connection tests on SQLite and isolated PostgreSQL 16, seal reversible mutations, cleanup and protected/shared hashes."
  ],
  "acceptance": [
    "Both forward UserSession producers issue canonical UUIDv4 handles; no repository caller can supply session_id; bearer generation remains token_urlsafe(32) and plaintext never persists or appears in logs/repr/DTO/commerce evidence.",
    "Generated handles compose unchanged through session, browser, OAuth and account-commerce consumers; existing rows remain byte-stable and no schema/migration/consumer edit exists.",
    "Handle/digest collision, concurrent lifecycle, restart, expiry, membership and cross-owner cases pass on SQLite and PostgreSQL 16 with full rollback and cleanup.",
    "UUID correction frozen hashes, protected/shared manifests, head 0049, architecture and reversible mutations pass.",
    "One independent critical-reviewer returns SPEC PASS and QUALITY PASS with zero open findings before UUID/shared assembly resume."
  ],
  "test_plan": ["Focused handle grammar/caller retirement/bearer separation/collision RED-GREEN in user-session and generated-identity tests.", "Affected session/browser/migration/commerce/session-bound connection matrices on SQLite and owned PostgreSQL 16; reversible producer/caller/tenant/privacy mutations; architecture/protected/shared hashes."],
  "risk_classification": {"tier": "Critical", "reason": "Session record identity binds bearer authority to exact user and tenant; a wrong change can deny access, alias sessions or cross entitlement attribution."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_session_record_handle_reference_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-session-source-test-evidence-package", "depends_on": [], "write_paths": ["paper-trader/backend/app/api/principal.py", "paper-trader/backend/tests/test_user_sessions.py", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-correction.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-correction"], "output": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_session_record_handle_reference_correction_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Session identity/bearer separation/collision recovery cross authentication, tenancy, OAuth and entitlement authority.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/review-package-correction.json", "review_paths": ["paper-trader/backend/app/api/principal.py", "paper-trader/backend/tests/test_user_sessions.py", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-correction.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-correction"], "exclude_paths": ["paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/backend/app/account_commerce", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/session.py", "paper-trader/backend/app/api/connection_routes.py", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/review/recheck-verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "correction": {
    "first_package_sha256": "364d4ee6814a53c1f286b5cbc29a3effc2fa91bbb5094fb13765fcba88370162",
    "first_verdict_sha256": "b1f12b9f8cab1387db0fbb65ae011277640e191a45bf2ab6bc024b592e043090",
    "first_open_findings": ["V0-SRH-CR-001", "V0-SRH-CR-002", "V0-SRH-CR-003"],
    "closed_in_correction_package": ["V0-SRH-CR-001", "V0-SRH-CR-002", "V0-SRH-CR-003"],
    "open_findings": [],
    "rechecks_remaining": 1,
    "recheck_ready": true,
    "policy": "Add evidence/tests only inside existing owned test paths; source and protected consumers remain frozen."
  },
  "owner_gates": ["Stop on any durable invalid non-legacy session row; no expiry/reauthentication/migration/reset without owner approval. No consumer broadening, schema/migration/frontend/provider/money/production/deployment change or UUID/shared resume before Critical acceptance."],
  "stop_conditions": ["A protected consumer/schema/migration path requires editing.", "Generated UUID handles cannot preserve a current accepted caller or authority seam.", "Protected shared source receives concurrent ownership."],
  "deployment_impact": {"classification": "auth-critical compatible forward source change", "schema_or_migration": false, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "result": {
    "implementation": "GREEN_REVIEW_REQUIRED",
    "forward_handle": "str(uuid4()) at both principal.py producers; canonical lowercase 36-character UUIDv4; maximum remains 64",
    "caller_override": "retired; repository scan finds no supplied session_id keyword",
    "bearer": "unchanged secrets.token_urlsafe(32) with SHA-256-only persistence",
    "collision": "UserSession PK and token_digest collisions fail the whole transaction; exact existing digest authority survives; public route returns generic 503/no cookie; retry succeeds",
    "sqlite_postgresql16": "declared affected matrix PASS on SQLite and owned PostgreSQL 16.15; server stopped and cluster/databases removed",
    "migration_head": "0049 before and after",
    "mutations": "ordinary producer, legacy producer and caller override each produce expected RED; restored suite GREEN",
    "architecture": "491 files / 0 failures",
    "protected_shared_hashes": "14/14 PASS",
    "source_sha256": "03022ac9ecb0a325e7b93800c5956b0e3dbae1e503c319668c1ed77cf4472092",
    "user_session_tests_sha256": "848a8a962467ef19de6bd9966d9aa62fcca51bd4b354a47b24484c918880aa41",
    "first_identity_tests_sha256": "34f6562d6c57210b87b82a1264485773da5f9891291399c1147591e2163c24ac",
    "identity_tests_sha256": "8b75f46472c953a298a95c8d30c19ca942fcc677a4bcff6e404334c7fde05264",
    "verification_sha256": "f459345014ebc404057bbf652b5dd6dd2392ef3d3cf411e33ff64f5a39a460e0",
    "architecture_matrix_sha256": "cb243604a6ecdcb2ddf1a43ba3b8b63b526b233865ca77e79d18ad90260c0e7e",
    "tenant_matrix_sha256": "2463ba69efa667105fb227b1fcce3416a16dd3b7eb29865b200d27cd4be1bf39",
    "protected_hashes_sha256": "121d42a398692c3456ea5111ea69009659f5cb5d242d854e22a76f2b6f9ca542",
    "report_sha256": "35cf67355818e013041911c237f1417ddd672558814b2199fc3dbd257241d91d",
    "review": "first Critical verdict FAIL; same-lineage correction package ready for the one allowed focused recheck, not dispatched",
    "uuid_correction_frozen": true,
    "shared_assembly_frozen": true,
    "deployment": false
  },
  "correction_result": {
    "status": "GREEN_RECHECK_REQUIRED",
    "V0-SRH-CR-001": "generated UUID handle persists through OAuthCallbackState exact session/user/organization, privacy and restart on SQLite/PostgreSQL 16",
    "V0-SRH-CR-002": "owned PostgreSQL 16 concurrent issue/revoke, expiry and logout exact session/tenant behavior PASS",
    "V0-SRH-CR-003": "absent-digest legacy UUID collision caller transaction rollback, existing authority preservation and restart/retry PASS on SQLite/PostgreSQL 16",
    "principal_frozen_sha256": "03022ac9ecb0a325e7b93800c5956b0e3dbae1e503c319668c1ed77cf4472092",
    "test_user_sessions_frozen_sha256": "848a8a962467ef19de6bd9966d9aa62fcca51bd4b354a47b24484c918880aa41",
    "corrected_identity_tests_sha256": "8b75f46472c953a298a95c8d30c19ca942fcc677a4bcff6e404334c7fde05264",
    "findings_closure_sha256": "f28f29a1b19b8c381a83af280f1a800846f402a24c9dc9f415455a467c583882",
    "verification_sha256": "288eeb8b0bb10aafceff8eb9983e648bd93f6773b251682174b11889132301ff",
    "architecture_tenant_sha256": "bca0f8e89d880e6d4448735b86501e84211c5943fc00c4d6937a02ffd9ceb48a",
    "protected_hashes_sha256": "ef3a0b51c9488d6af673161b8e21a2336d8a972d3192935c4b4bab6fe31cf578",
    "report_sha256": "63e184e19ca63285af5ccfe431a07cac37cc6bf0fca0587169c3426f32f4017e",
    "affected_sqlite_postgresql16": "PASS",
    "migration_head": "0049",
    "architecture": "491 files / 0 failures",
    "protected_shared_hashes": "14/14 plus controls exact",
    "cleanup": "all correction-owned PostgreSQL clusters removed and processes stopped",
    "reviewer_dispatched": false,
    "uuid_correction_frozen": true,
    "shared_assembly_frozen": true,
    "deployment": false
  },
  "nonclaims": ["No existing session rewrite/expiry/reset, UUID correction acceptance, shared publication, provider, money, deployment, release readiness or V0 completion."]
}
---

# Session record-handle reference correction

Use one canonical non-secret UUID record handle while preserving the full bearer.
Keep every downstream authority and existing persisted session byte unchanged.
