---
{
  "id": "strategy-os-v0-browser-auth-current-head-test-correction",
  "lineage_id": "strategy-os-v0-browser-auth-rfc4122-identity-correction",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "accepted",
  "kind": "routine_stale_migration_head_test_correction",
  "goal": "Restore the accepted browser-auth identity suite after later accepted migrations advanced the repository head from 0049 to 0051.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Only the three stale expected-head literals change to 0051; the exact SQLite identity suite and architecture pass; reverting the literals reproduces the setup failure and exact restoration returns GREEN."},
  "authorization_resolution": {"status": "ROOT_ROUTED_RELEASE_SUITE_CORRECTION", "evidence": "The V0 Zerodha data-account affected run found eight setup errors solely because the historical accepted identity test expects 0049 while migrate.head_revision() and the repository migration chain are 0051."},
  "risk_tags": ["routine", "test-only", "auth", "migration-head", "release-suite"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-chart-context-and-annotations-foundation"],
  "required_docs": [
    {"path": "paper-trader/backend/app/db/migrate.py", "sections": ["head_revision", "managed upgrade 0051"]},
    {"path": "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "sections": ["identity_store", "restart"]},
    {"path": ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction/owner/affected-provider-auth-tenancy.log", "sections": ["eight stale 0049 setup errors"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-current-head-test-correction.md",
    ".agent/runs/strategy-os-v0-browser-auth-current-head-test-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-current-head-test-correction.md",
    ".agent/runs/strategy-os-v0-browser-auth-current-head-test-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/migrations",
    "paper-trader/backend/tests/test_browser_auth.py",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/scripts/deploy.sh",
    "/Users/priyanshusaraf/dev/strategy-os-frontend"
  ],
  "scope": ["Update only the three fixture/restart expected current-head values from 0049 to 0051. Do not alter identity, migration, auth, provider, schema or product behavior."],
  "acceptance": ["The exact SQLite browser-auth RFC4122 suite reaches and tests identity behavior at head 0051.", "ABL-HEAD-EXPECTATION restores 0049 and reproduces the exact setup error; restoring 0051 returns GREEN.", "Architecture validation passes and all protected bytes remain unchanged."],
  "test_plan": ["Run the exact file on SQLite with PostgreSQL cases skipped only when its disposable harness is unavailable; run the affected provider/auth selector and architecture."],
  "risk_classification": {"tier": "Routine", "reason": "Only stale test expectations change to the already authoritative migration head; product and migration bytes are protected."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_browser_auth_current_head_test_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-browser-auth-current-head-test-correction/review-package.json", "review_paths": ["paper-trader/backend/tests/test_browser_auth_rfc4122_identity.py", "paper-trader/docs/agent/tasks/strategy-os-v0-browser-auth-current-head-test-correction.md", ".agent/runs/strategy-os-v0-browser-auth-current-head-test-correction"], "exclude_paths": ["paper-trader/backend/app", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-browser-auth-current-head-test-correction/report.md", "verdicts": ["TEST_FIXTURE"], "max_rechecks": 0},
  "owner_gates": ["No product, migration, schema, auth, provider, money or deployment edit."],
  "stop_conditions": ["Any failure remains after changing the three stale current-head expectations, or a product/migration edit is required."],
  "deployment_impact": {"classification": "test-only maintenance", "schema_change": false, "dependency_change": false, "runtime_wiring": false, "release_deployable": false, "deployed": false},
  "nonclaims": ["No auth, migration, provider, deployment or V0 completion claim follows from this test-only correction."]
}
---

# V0 browser-auth current-head test correction

Keep the accepted identity proof aligned with the repository's later accepted
migration head. No product or migration behavior changes.
