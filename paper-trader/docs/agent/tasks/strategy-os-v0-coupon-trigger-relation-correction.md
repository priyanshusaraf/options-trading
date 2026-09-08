---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-coupon-trigger-relation-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_current_head_trigger_relation_readiness_correction",
  "goal": "Bind every required 0049 coupon trigger to its exact protected relation, schema, function and enabled state in SQLite and PostgreSQL startup validation.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "SQLite 8-trigger and PostgreSQL 5-trigger relation-aware tamper matrices, unchanged-state proof, preserved 444/444 evidence and one fresh Critical review close V0-CDV-CR-001-R1."},
  "risk_tags": ["critical", "migration", "readiness", "sqlite", "postgresql", "trigger", "privacy", "source-attribution"],
  "depends_on": ["strategy-os-v0-coupon-trigger-relation-recovery-replan"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan/decision.json", "decision_sha256": "13d515078cd17b15ef38c7bc3605b4096fbbf32b2a4fe09dbf2cd67f3d7f8520", "open_finding": "V0-CDV-CR-001-R1", "policy": "Only migrate.py and exact account-commerce migration tests may change. 0049 schema/service/copy/restore semantics remain frozen."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan/decision.json", "sections": ["sqlite_inventory", "postgresql_inventory", "validation_design", "tamper_matrix", "successor", "preserved_evidence"]},
    {"path": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-correction/review/recheck-verdict.json", "sections": ["findings", "closed_findings", "nonclaims"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/db/migrate.py", "paper-trader/backend/tests/test_v0_account_commerce_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-correction.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-correction.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction"],
  "protected_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations/versions/20260902_0049_coupon_dynamic_entitlement_validity.py", "paper-trader/backend/app/account_commerce/service.py", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/account_commerce/publication.py", "paper-trader/backend/app/main.py", "paper-trader/backend/app/api/principal.py", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": ["SQLite current-head validation selects name,tbl_name,sql from persistent sqlite_master and compares the exact sorted multiset of eight name/relation/normalized-body records; no name-keyed collapse or temp trigger substitution.", "PostgreSQL validation joins pg_trigger, relation/function namespaces, pg_class, pg_proc and pg_language and compares the exact five-row multiset including relation/schema, tgtype, enabled O, internal false, no WHEN, function/schema/body/language/security-definer.", "Reject wrong relation/schema, duplicate/multiplicity, disabled/internal, missing, wrong timing/operation/WHEN/function/body/language/security mode with unchanged 0049 head and row digests.", "Preserve exact current control and accepted service/migration/copy/restore/PG16 evidence; do not modify revision/model/service/semantics."],
  "acceptance": ["All 8 SQLite and 5 PostgreSQL trigger records match exact protected relations and catalog semantics; exact control returns 0049 without writes.", "Every wrong-relation/schema/duplicate/disabled/internal/missing/function/body tamper refuses with unchanged head/rows on SQLite and real PG16.", "Existing current-head shape/source/privacy/capacity tamper gates, real PG16 444/444 and frozen shared hashes remain bound and green.", "Focused/full migration tests, architecture/protected hashes and one fresh critical-reviewer SPEC/QUALITY PASS close the finding."],
  "test_plan": ["Focused SQLite and disposable PG16 relation/name/body/schema/state tamper matrix with unchanged digests.", "Proportional account-commerce migration regression plus preserved evidence/hash verification and architecture."],
  "risk_classification": {"tier": "Critical", "reason": "False readiness could run writers while capacity/privacy/source guards protect the wrong relation."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_coupon_trigger_relation_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-readiness-validation-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/db/migrate.py", "paper-trader/backend/tests/test_v0_account_commerce_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-correction.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction"], "output": ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_coupon_trigger_relation_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Fresh Critical review required after exhausted predecessor and readiness P0.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction/review-package.json", "review_paths": ["paper-trader/backend/app/db/migrate.py", "paper-trader/backend/tests/test_v0_account_commerce_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-correction.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction"], "exclude_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations", "paper-trader/backend/app/account_commerce", "paper-trader/backend/app/platform_operations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "correction": {"first_verdict": ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction/review/verdict.json", "first_verdict_sha256": "3f7005c56e476ef2cea6ff63c5073e402b462489357c51bd3c824a22b7d8567b", "corrected_package_sha256": "eb2a31bd7947d26dfbc7a973395f0579cc0edb38afd74adeb93b5b2d99c28c7d", "recheck_verdict": ".agent/runs/strategy-os-v0-coupon-trigger-relation-correction/review/recheck-verdict.json", "recheck_verdict_sha256": "3f74a9bf094769bebd355b7e93de02abe3a5e51b6e69140cc41a3d3645b35d98", "closed_findings": ["V0-CDV-CR-001-R1", "V0-CTR-CR-001", "V0-CTR-EG-001"], "open_findings": [], "SPEC": "PASS", "QUALITY": "PASS", "rechecks_used": 1, "rechecks_remaining": 0},
  "owner_gates": ["No revision/model/service/copy/restore/shared edit, provider/money, commit, deployment or V0 claim. Dynamic activation remains frozen."],
  "stop_conditions": ["Relation-aware catalog validation requires a path outside migrate.py/tests.", "Real PG16 tamper cannot run.", "Protected coupon/shared hash changes."],
  "deployment_impact": {"classification": "readiness-critical application validation change; no schema revision", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No schema/service change, shared publication, deployment, release readiness or V0 completion."]
}
---

# Coupon trigger relation correction

Validate each required 0049 trigger against its exact table and catalog identity.
Preserve the accepted coupon migration and service semantics unchanged.

## Accepted receipt

The sole Critical recheck returned SPEC PASS / QUALITY PASS on SQLite and real
PostgreSQL 16. Head 0049, dynamic coupon semantics and shared frozen bytes are
released to the Account assembly resume gate.

## Owner implementation receipt

- Implemented exact sorted SQLite 8-row and PostgreSQL 5-row trigger catalog multiset validation without collapsing observed rows by trigger name.
- Added exact controls and relation, schema, multiplicity, enabled/internal, timing/operation/WHEN, function, body, language, security, missing-object, check, column, and persisted-row tamper cases with unchanged 0049 head and exact coupon row state.
- Passed the 59-test account-commerce migration file on a fresh isolated PostgreSQL 16.15 cluster with zero skips. Preserved the accepted 444/444 evidence and all nine frozen shared hashes.
- Architecture validation passed 487 files with zero failures. The migration revision, model, service, publication, copy, restore, frontend, CURRENT, PROGRAMME, and deploy script remain unchanged.
- Deployment impact is compatible startup-validation hardening only. Release deployability, production rehearsal, deployment, shared resume, provider opening, V0 completion, commit, and push remain unclaimed.
- The fresh Critical review package is sealed at `.agent/runs/strategy-os-v0-coupon-trigger-relation-correction/review-package.json`; no reviewer was dispatched by this assignment.

## Sole Critical correction receipt

- Bound to first verdict SHA-256 `3f7005c56e476ef2cea6ff63c5073e402b462489357c51bd3c824a22b7d8567b` and closed only implementation finding `V0-CTR-CR-001` for recheck.
- Replaced whole-string lowercasing with token-aware normalization that preserves exact quoted literal, E-string, quoted identifier, and dollar-quoted bytes while normalizing only unquoted SQL case and whitespace.
- Captured RED on SQLite and real PostgreSQL 16 when only `'ACCEPTED'` became `'accepted'`; both now refuse with exact 0049 head and rows unchanged, while exact controls still return 0049 without writes.
- Passed all 62 account-commerce migration tests on a fresh isolated PostgreSQL 16.15 cluster with zero skips, architecture 487/0, 11 correction-baseline protected hashes, and nine frozen shared hashes.
- Resealed the package once for the sole Critical recheck. No reviewer dispatch, shared resume, commit, push, deployment, or V0 completion claim was made.
