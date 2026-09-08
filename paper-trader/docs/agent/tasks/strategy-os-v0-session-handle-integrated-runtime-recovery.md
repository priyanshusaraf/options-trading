---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-session-handle-integrated-runtime-recovery",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_evidence_only_runtime_integration_correction",
  "goal": "Close V0-SRH-CR-001 and V0-SRH-CR-003 with one dedicated integration test that drives the accepted UUID session through the actual OAuth and init_db runtime entry points on SQLite and owned PostgreSQL 16 without changing protected source.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Dedicated real-entry-point tests and mutation evidence pass on SQLite and owned PostgreSQL 16; V0-SRH-CR-002 remains hash-bound and closed; protected hashes and cleanup pass; one fresh Critical review returns SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "auth", "session", "oauth", "bootstrap", "transaction", "identity", "tenancy", "privacy", "restart"],
  "depends_on": ["strategy-os-v0-session-handle-integrated-runtime-recovery-replan"],
  "dependency_gate": {"decision_sha256": "0b8d3fcbd7788d1c4ae3f7186cdf66cb76c75f35f6ec86d82067ee23bbb2d4bd", "successor_sha256": "6bc35eaaaea1b6710d16c707fe3c149b9784999e248bd93343cebbda8a420a81", "entrypoint_evidence_sha256": "27ea66fefd50b68e7f968cfc07cde55380a41f2da13065d67cfa3ee330cddea3", "policy": "Evidence-only successor. The exhausted predecessor stays immutable; no direct OAuth-state insertion, direct bootstrap helper call or manually substituted transaction."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/decision.json", "sections": ["runtime_seams", "shortcut_rejections", "database_matrix", "transaction_assertion", "mutation_gate", "review_gate"]},
    {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/entrypoint-evidence.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/successor-correction-capsule.md", "sections": ["scope", "forbidden_shortcuts", "exact_test_nodes", "mutation_plan", "acceptance"]},
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/review/recheck-verdict.json", "sections": ["closed_findings", "open_findings", "verdict"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery.md", "paper-trader/backend/tests/test_session_handle_integrated_runtime_recovery.py", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery.md", "paper-trader/backend/tests/test_session_handle_integrated_runtime_recovery.py", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery"],
  "protected_paths": ["paper-trader/backend/app", "paper-trader/backend/migrations", "paper-trader/backend/research", "paper-trader/backend/research_tests", "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/backend/tests/test_connection_routes.py", "paper-trader/backend/conftest.py", "paper-trader/backend/tests/conftest.py", "paper-trader/backend/tests/postgres_sandbox.py", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Add one new integration test module only; do not edit accepted UUID producer, OAuth consumer, init_db caller, schema, migration or existing tests.",
    "Parameterize over a unique temporary SQLite database and tests.postgres_sandbox.PostgresSandbox; prove PostgreSQL major 16 and redact its URL.",
    "Create the session only through browser_auth.create_invite/enroll, then create prerequisites through actual connection routes, call actual _start_oauth, inspect state by digest without constructing it, restart, call actual oauth_callback with local fake authenticator/vault, prove single consumption/encrypted update and actual revoke_connection.",
    "Prove logout, expiry, replacement and cross-owner/mismatched authority fail through actual OAuth predicates with zero exchange, credential or event side effects.",
    "For init_db collision, use a second real browser enrollment as the pre-existing foreign UUID row, inject its UUID into principal.uuid4 and call actual app.db.session.init_db. Never call bootstrap_legacy_session or root helpers directly and never substitute test-owned commit/rollback.",
    "After failure prove foreign session/digest/owner/enrollment unchanged and all legacy roots, deployment/outbox, catalogue, capital, universe/preference/instrument seeds absent. Restore/restart, call whole init_db, prove complete seeds, restart again and prove idempotency.",
    "Install in-process authenticator/vault and socket tripwire; no raw bearer, OAuth state, request token, vault key or credential plaintext in evidence. Run five reversible test-time mutations and exact protected/cleanup/head gates."
  ],
  "acceptance": [
    "Seven exact test nodes pass on SQLite and PostgreSQL 16 without skips; actual OAuth call trace carries the same generated UUID through initiation, state, callback, restart and revocation.",
    "Negative OAuth trace proves logout, expiry, replacement and cross-owner refusal with zero exchange and secret/event writes.",
    "Actual init_db collision trace rolls back the complete first transaction, preserves the enrolled foreign authority, then whole-call retry and second restart create complete idempotent seeds on both databases.",
    "AST/trace guards reject direct OAuthCallbackState construction, direct bootstrap/root calls and test-owned rollback; all reversible mutations RED then restore GREEN.",
    "V0-SRH-CR-002 remains closed at recheck SHA aa25218246325b436594b25c6ad070905d6261bbfea64fbb504f9b66d4d56d54; protected hashes/head 0049/cleanup pass.",
    "One fresh critical-reviewer returns SPEC PASS and QUALITY PASS with zero open V0-SRH-CR-001/003 findings before UUID/shared resume."
  ],
  "test_plan": ["Run the exact new module on unique SQLite and owned PostgreSQL 16 with full logs; run five named mutation nodes separately with restoration.", "Run affected OAuth/browser integration nodes and architecture once; query head 0049; record no-process/no-network/privacy/protected/allowed diff gates."],
  "risk_classification": {"tier": "Critical", "reason": "Direct OAuth capability and init_db transaction evidence cross session identity, credential binding, durable bootstrap authority and rollback."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_session_handle_integrated_runtime_recovery_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "evidence-only-runtime-integration", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery.md", "paper-trader/backend/tests/test_session_handle_integrated_runtime_recovery.py", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery"], "output": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_session_handle_integrated_runtime_recovery_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Fresh review after exhausted predecessor must verify actual runtime entry points and shortcut exclusion.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/review-package.json", "review_paths": ["paper-trader/backend/app/api/principal.py", "paper-trader/backend/tests/test_session_handle_integrated_runtime_recovery.py", "paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery.md", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery"], "exclude_paths": ["paper-trader/backend/app/account_commerce", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/api/connection_routes.py", "paper-trader/backend/app/db/session.py", "paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "review_result": {"package_sha256": "a833323703c3357825b05a80ee9fc927ca6e0800d0c88945fb6bce976e3a2e4d", "verdict_sha256": "9d6d559123321e0399935dc4267b7791d6d1029adad3916389f60d62e4570f48", "SPEC": "PASS", "QUALITY": "PASS", "closed_findings": ["V0-SRH-CR-001", "V0-SRH-CR-003"], "preserved_finding": "V0-SRH-CR-002", "open_findings": [], "independent_nodes": "7 passed on SQLite and PostgreSQL 16.15", "remaining_sandboxes": 0},
  "owner_gates": ["No product source, existing test, schema, migration, frontend, control, provider network/credential, live/money, production, commit or deploy write. No UUID/shared resume before fresh Critical acceptance."],
  "stop_conditions": ["Actual entrypoint evidence requires protected source change, provider network, real credentials, production access or destructive non-temporary state.", "A protected semantic defect appears instead of the documented evidence gap.", "The test cannot rebind safe factories without altering production code or a protected hash moves."],
  "deployment_impact": {"classification": "compatible test/evidence-only correction", "schema_or_migration": false, "runtime_change": false, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "delivery_status": "accepted",
  "implementation_result": {
    "exact_nodes": "7 passed, 0 skipped on SQLite and owned PostgreSQL 16.15",
    "mutations": "5/5 expected RED; baseline restored GREEN",
    "affected": "4 passed, 1 expected PostgreSQL skip in the separate no-harness predecessor-focused run",
    "migration_head": "0049",
    "architecture": "493 checked, 0 failures",
    "protected_hashes": "PASS",
    "cleanup": "PASS",
    "privacy": "PASS",
    "provider_network": false,
    "protected_semantic_defect": false
  },
  "output_artifacts": {
    "test": {"path": "paper-trader/backend/tests/test_session_handle_integrated_runtime_recovery.py", "sha256": "afd4d43728d62062103086be86bb9a7c1ae4600bc9aa6fe26fb5e7e8ad8cf769"},
    "report": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/report.md", "sha256": "991a8740cc8d5cc8c95918e1e71394d525113d21e6b6e47197b9b8c8c8bf23d8"},
    "runtime_matrix": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/runtime-matrix.json", "sha256": "8d0ffcde27d4b38e94287172b9ffcb97ac38dc1525d5ef51369f098f0188009c"},
    "mutation_matrix": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/mutation-matrix.json", "sha256": "232634070a89015039e14ad8494669049e8737bceb6a8f312d967e31019914dc"},
    "protected_hashes": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/protected-hashes.json", "sha256": "e42e8492ef6300313fca7a06419402fcb38ee6a9e49423960e9d243947b58f90"},
    "review_package": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery/review-package.json", "status": "to be sealed after this capsule receipt"}
  },
  "nonclaims": ["No source/runtime change, UUID/shared resume, provider capability, deployment, release readiness or V0 completion until fresh Critical review passes."]
}
---

# Session-handle integrated runtime recovery

Prove the accepted UUID handle through real protected runtime entry points.
This capsule adds tests and evidence only.

## Critical review handoff

The dedicated module passed all seven exact nodes on unique SQLite databases
and task-owned PostgreSQL 16.15 databases without skips. The generated UUID
travels through actual enrollment, connection creation and credential storage,
`_start_oauth`, digest-only state lookup, restart, `oauth_callback`, and
`revoke_connection`. Logout, UTC expiry, replacement and mismatched-session
ownership all refuse before exchange or credential/event side effects.

The collision test creates its foreign row through real enrollment, injects the
UUID, and calls whole `init_db`. It does not call the bootstrap or tenancy-root
helpers and does not own rollback. Every companion seed is absent after the
collision; whole-call retry and a second restart are complete and idempotent.

Five process-local mutations turned their named guards RED, after which the
exact matrix returned GREEN. Protected hashes, privacy, PostgreSQL cleanup,
migration head `0049`, and architecture validation passed. V0-SRH-CR-002 stays
closed at its accepted predecessor hash. V0-SRH-CR-001 and V0-SRH-CR-003 remain
pending one fresh independent Critical verdict; review is not dispatched here.
