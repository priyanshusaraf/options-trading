---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-session-record-handle-reference-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_session_handle_replan",
  "goal": "Resolve V0-BARIC-SESSION-001 by defining one non-secret durable UserSession record-handle contract that every current producer and account-commerce/operations consumer can represent without changing bearer secrecy or tenant attribution.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision freezes generated and caller-supplied handle semantics, prelaunch compatibility, exact correction paths/tests/review and UUID/shared-assembly resume gates."},
  "risk_tags": ["critical", "auth", "session", "identity", "tenancy", "entitlements", "compatibility", "privacy"],
  "depends_on": ["strategy-os-v0-browser-auth-rfc4122-identity-correction"],
  "dependency_gate": {"finding": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/session-handle-blocker.json", "finding_sha256": "0272611ca079712124ed78dbb23b26fc8a501acabbc9048011d3f02cefd17b79", "blocked_package_sha256": "0fe301be147dd88206840b4b006c248b725d7f80f3eded10fa07103880d69425", "policy": "Do not weaken account-commerce/platform reference validation or conflate the non-secret session record handle with the bearer credential. Keep accepted UUID and shared assembly bytes frozen."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/session-handle-blocker.json", "sections": ["producer", "consumer", "red", "identity_correction_disposition", "forbidden_actions"]},
    {"path": ".agent/runs/strategy-os-v0-browser-auth-rfc4122-identity-correction/review-package.json", "sections": ["all"]},
    {"path": "paper-trader/backend/app/api/principal.py", "sections": ["IssuedBearerCredential", "issue_user_session", "bootstrap_legacy_session", "resolve_principal"]},
    {"path": "paper-trader/backend/app/account_commerce/repository.py", "sections": ["AccountCommerceRepository.resolve_authority"]},
    {"path": "paper-trader/backend/app/platform_operations/contracts.py", "sections": ["_REFERENCE", "reference"]},
    {"path": "paper-trader/backend/tests/test_user_sessions.py", "sections": ["issuance", "concurrency", "legacy bootstrap", "restart"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["Backend execution rules"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-replan.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-replan.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Inventory every UserSession.session_id producer, optional caller path, persistence width/key/FK, browser-session copy, principal projection and consumer grammar. Keep the bearer token and its digest as separate secret authority.",
    "Choose one exact forward-generated non-secret handle format whose first byte and full alphabet/length compose with the existing account-commerce/platform reference boundary. Compare prefixed base64url and canonical UUID forms from direct constraints; reject downstream normalization and validator broadening.",
    "Decide whether optional caller-supplied session_id remains, is validated, or is retired. No unchecked internal caller may create a handle that current consumers cannot represent.",
    "Classify legacy bootstrap, current accepted/manual session rows and unreleased generated rows. Preserve exact existing authority; use direct deployment-state evidence for any expiry, reauthentication, migration or stop policy.",
    "Freeze collision/transaction/retry semantics and tests for issue, browser copy, login/password/workspace rotation, revocation, restart, two-owner account commerce and legacy bootstrap on SQLite/PostgreSQL 16.",
    "Freeze the smallest correction capsule, reversible mutations, privacy/protected evidence, one Critical review, UUID correction resume and shared assembly resume gates."
  ],
  "acceptance": [
    "Decision separates the non-secret record handle from the 256-bit bearer and names one producer/consumer-compatible format and maximum length.",
    "Every producer and optional caller path has exact validation/collision/compatibility semantics; no normalization, alias, suffix, consumer broadening or tenant rewrite is allowed.",
    "Existing-state disposition is evidence-backed and cannot silently orphan/reassign a session; successor paths and SQLite/PostgreSQL/session/restart/tenant/privacy tests are exact.",
    "UUID correction and shared assembly remain frozen until one Critical session-handle correction review passes and integrated matrices rerun."
  ],
  "test_plan": ["Read-only producer/consumer/schema/caller/test/deployment inventory; reproduce the exact leading-hyphen/underscore RED deterministically; compare candidate formats; seal exact successor and resume hashes. Product implementation belongs only to the successor."],
  "risk_classification": {"tier": "Critical", "reason": "A session record handle binds bearer authority to user and tenant; malformed or aliased handling can deny access, cross attribution, or break entitlement composition."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_session_record_handle_reference_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-session-handle-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-replan.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-replan"], "output": ".agent/runs/strategy-os-v0-session-record-handle-reference-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_session_record_handle_reference_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical replan; implementation successor receives independent Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-session-record-handle-reference-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-record-handle-reference-replan.md", ".agent/runs/strategy-os-v0-session-record-handle-reference-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-session-record-handle-reference-replan/decision.json", "verdicts": ["SESSION_IDENTITY", "AUTHORITY", "COMPATIBILITY", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/schema/migration/frontend edit, bearer change, session rewrite, consumer-validation workaround, provider/money, production data, commit, deployment or V0 claim."],
  "stop_conditions": ["Evidence shows released invalid generated handles require owner-approved expiry/migration/destructive action.", "A current authority consumer cannot accept any safe forward format without schema or contract-version change.", "Protected shared source receives concurrent ownership."],
  "deployment_impact": {"classification": "none for read-only replan; successor auth-critical", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "result": {
    "decision": "KEEP + HARDEN",
    "forward_handle": "server-side str(uuid.uuid4()); 36-character lowercase canonical UUIDv4; consumer and persistence maximum remains 64",
    "bearer": "unchanged secrets.token_urlsafe(32) 256-bit bearer with SHA-256-only persistence",
    "optional_caller": "retire unused issue_user_session session_id keyword",
    "legacy": "preserve existing digest-bound row exactly; use UUIDv4 only for an absent legacy digest; never reassign a foreign binding",
    "compatibility": "forward-only; preserve compatible existing handles; no migration/reset/alias; stop for owner direction if a durable invalid non-legacy row is evidenced",
    "decision_sha256": "864dfac21d1be8458ef4ec5ab5338cb6881db28c83c66b768179dfaf0c437534",
    "successor_capsule_sha256": "91db1d31935d41f91060ba997df732ba73101672cecbc4ccd38ea0d1edf33a8a",
    "shared_resume_hashes_sha256": "eafac9dc767e6db764bd2f83e9a773af342a457afdda3cf210ca42d8667e8ec5",
    "evidence_index_sha256": "5ad14abe8213cad6756d39935fe06ad9e704693a26a7773c726cf7702e746f81",
    "compatibility_probe": "PASS: leading '-' and '_' refused; prefixed base64url privacy counterexample refused; 4096 UUIDv4 samples and alphabet proof pass",
    "frozen_hashes_checked": 17,
    "reviewer": "one independent Critical reviewer belongs to the implementation successor",
    "uuid_correction_frozen": true,
    "shared_assembly_frozen": true,
    "product_tests_run": 0,
    "product_writes": 0,
    "deployment": false,
    "blocker": null
  },
  "nonclaims": ["No session fix, UUID correction acceptance, migration/reset, shared publication, provider, deployment, release readiness or V0 completion."]
}
---

# Session record-handle reference replan

Correct the durable non-secret session record identifier at its producer.
Do not change bearer-token generation or weaken downstream authority contracts.
