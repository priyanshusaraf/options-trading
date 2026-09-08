---
{
  "id": "strategy-os-v0-auth-session-transport",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "assigned_waiting_start",
  "goal": "Implement real invited-user enrollment and browser session lifecycle over existing UserSession",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete exact contract, integrated source/preservation/runtime/mutation evidence and one actual independent SPEC PASS/QUALITY PASS; owner closure verified. No public capability, numerical, deployment or whole-V0 acceptance."
  },
  "risk_tags": [
    "critical",
    "authority",
    "parallel-owned"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md",
      "sections": [
        "Public V0 scope",
        "Golden path"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "1. Risk-weighted verification",
        "2. Test rule",
        "3. Test cadence"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/auth-contract.md",
      "sections": [
        "Scope and authority",
        "Enrollment and credential boundary",
        "Browser transport and sole authority",
        "Persistence and browser experience",
        "Required proof and limits"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md",
      "sections": [
        "Security and tenancy",
        "Frontend and operations"
      ]
    },
    {
      "path": "paper-trader/docs/engineering-references/source-notes/2026-08-29-browser-session-reference-application.md",
      "sections": [
        "Decision and direct evidence",
        "Sources, alternatives and limits",
        "Repository hypothesis, verification and rollback"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "programme_assignment": {
    "assignment_id": "v0_auth_session_transport",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output-correction-assurance",
    "primary_programme_owner": false,
    "coordinator": "01a04a5b-40f5-73a0-a443-7fa8ea67a348",
    "prerequisite": "Read-only orientation until exact owner/routing seal and ACTUAL START; no user token."
  },
  "allowed_paths": [
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/app/core/config.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/db/planes.py",
    "paper-trader/backend/app/db/copy_contract.py",
    "paper-trader/backend/tests/test_api_auth.py",
    "paper-trader/backend/tests/test_user_sessions.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_db_planes.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/backend/app/accounts/__init__.py",
    "paper-trader/backend/app/accounts/browser_auth.py",
    "paper-trader/backend/app/api/auth_session_routes.py",
    "paper-trader/backend/scripts/create_enrollment_invite.py",
    "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
    "paper-trader/backend/tests/test_browser_auth.py",
    "paper-trader/backend/tests/test_browser_auth_migration.py",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx",
    "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-transport.md",
    ".agent/runs/strategy-os-v0-auth-session-transport"
  ],
  "new_paths": [
    "paper-trader/backend/app/accounts/__init__.py",
    "paper-trader/backend/app/accounts/browser_auth.py",
    "paper-trader/backend/app/api/auth_session_routes.py",
    "paper-trader/backend/scripts/create_enrollment_invite.py",
    "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
    "paper-trader/backend/tests/test_browser_auth.py",
    "paper-trader/backend/tests/test_browser_auth_migration.py",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx"
  ],
  "protected_paths": [
    ".agents",
    ".codex",
    "AGENTS.md",
    "paper-trader/backend/app/api/ir_experiment_routes.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/market_data",
    "paper-trader/backend/app/market_truth",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/requirements.lock",
    "paper-trader/backend/research/data/canonical_dataset.py",
    "paper-trader/backend/research/domain/migrations",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/orchestrator/graph_experiment.py",
    "paper-trader/backend/research/orchestrator/run.py",
    "paper-trader/backend/research_tests/conftest.py",
    "paper-trader/backend/research_tests/test_canonical_dataset.py",
    "paper-trader/backend/research_tests/test_graph_experiment.py",
    "paper-trader/backend/tests/conftest.py",
    "paper-trader/backend/tests/test_ir_experiment_routes.py",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/app/core/release_profile.py",
      "sha256": "bac0d0b76af0711e44d98af7e819cc42db0addce70b6658b251aaca23026b0a5"
    },
    {
      "path": "paper-trader/backend/app/ir/node_contracts.py",
      "sha256": "a1e16b735cd8decfcad4356aa82c10a20d65c5129f25d78ae7931ad9596af284"
    },
    {
      "path": "paper-trader/backend/requirements.lock",
      "sha256": "d71ab1dafcf51d26f77789d9a242ca2a3417b8231f09fad223979106ae274146"
    },
    {
      "path": "paper-trader/backend/app/db/concurrency.py",
      "sha256": "1e355d79f393db3b00433713d90244921a655525713d5e47f17ebdec99f45343"
    },
    {
      "path": "paper-trader/backend/app/api/versioning.py",
      "sha256": "116c5240cdb393b61e5b2fead686f9750ad169012ba1079ed3a9b7cded8bd263"
    },
    {
      "path": "paper-trader/backend/app/db/session.py",
      "sha256": "416445e1130433e91d2d01087acfdb7c5982a3b444ea0a1e012adfa770a758e3"
    },
    {
      "path": "paper-trader/backend/migrations/versions/20260828_0042_static_instrument_scopes.py",
      "sha256": "b86e09ede82204c3fa14b6fad9e4e1e6afbc2260ee4770bde19489295769bc8f"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/productionBoundary.test.ts",
      "sha256": "498df446acd4c11530a75500ea5f07e15d7d6a618bfbab86b021aa8d906ab406"
    }
  ],
  "scope": [
    "Implement only the complete frozen auth-contract.md contract; no duplicate authority or hidden fallback.",
    "Preserve inherited and peer edits; you are not alone in the checkout. Only exact paths belong to this owner. Shared changes outside ownership require a bounded serial correction before mutation.",
    "One durable goal before product work; zero agents. Request the single coordinator-routed critical reviewer only after integrated local evidence; do not self-certify or launch a reviewer."
  ],
  "acceptance": [
    "Every requirement of .agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/auth-contract.md is evidenced; preserve every explicit refusal/remaining gate.",
    "One independent critical SPEC PASS and QUALITY PASS with exact code/evidence binding, not local totals."
  ],
  "test_plan": [
    "Run focused RED/green regressions then affected existing subsystem, real SQLite and disposable PG16 where applicable. Exact logs, JUnit counts, source hashes, complete failure evidence and genuine isolated mutations must agree.",
    "Re-audit both repository heads/branches/indexes and all nonowned paths against routing snapshots; attribute declared peer/control changes, never reset them.",
    "Safe mock/paper/disabled dotenv/empty live ack/distinct temporary DBs. No HOME/CODEX_HOME overrides, live/network credentials, deployment, dependency or lock changes."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "owner_task": "01a04a82-f51b-7c01-bb03-8f7421108b99",
  "contract": {
    "path": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/auth-contract.md",
    "sha256": "a39d722d1b7eb5a8b7196e3c209c1294def72060a728c78e23a6e54cba4f9e77"
  },
  "owner_gates": [
    "Standing allV0 and parallel authority; no repeated routine token. External-action and exact ownership/evidence gates remain."
  ],
  "stop_conditions": [
    "Unexplained drift or indispensable change outside owned files; preserve evidence and ask coordinator for smallest serial correction.",
    "First automatic compaction is the handoff warning; fresh owner context before a second, preserving this goal/objective."
  ],
  "nonclaims": [
    "No public capability opening, numerical publication, live/provider/customer access, deployment or whole-V0 completion."
  ],
  "review": {
    "required": true,
    "assignment_id": "v0_auth_session_transport_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "One independent evidence-backed integrated critical review of authority/security/schema/browser boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-auth-session-transport/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/main.py",
      "paper-trader/backend/app/api/principal.py",
      "paper-trader/backend/app/core/config.py",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/db/planes.py",
      "paper-trader/backend/app/db/copy_contract.py",
      "paper-trader/backend/tests/test_api_auth.py",
      "paper-trader/backend/tests/test_user_sessions.py",
      "paper-trader/backend/tests/test_schema_migrations.py",
      "paper-trader/backend/tests/test_db_planes.py",
      "paper-trader/backend/tests/test_postgresql_restore_contract.py",
      "paper-trader/backend/app/accounts/__init__.py",
      "paper-trader/backend/app/accounts/browser_auth.py",
      "paper-trader/backend/app/api/auth_session_routes.py",
      "paper-trader/backend/scripts/create_enrollment_invite.py",
      "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
      "paper-trader/backend/tests/test_browser_auth.py",
      "paper-trader/backend/tests/test_browser_auth_migration.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-transport.md",
      ".agent/runs/strategy-os-v0-auth-session-transport"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-auth-session-transport/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1,
    "cross_repository_review": {
      "root": "/Users/priyanshusaraf/dev/strategy-os-frontend",
      "head": "f2ae5525ff3d0112e53babe936f32baa79a021d1",
      "paths": [
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx"
      ],
      "required": "Actual external incremental diff/source/build/browser evidence must be bound and inspected. Relative primary review paths do not omit frontend review."
    }
  },
  "deployment_impact": {
    "classification": "additive local USER schema + bounded auth/HTTPS browser configuration",
    "prove_now": "Exact scoped runtime/resource/identity/restore proof under contract. No production mutation.",
    "release_assembly_owner": "strategy-os-v0-security-operations-deployability",
    "rollback": "Preserve current data/readability, old identities and rejected evidence; no destructive downgrade, source reset or automatic deploy."
  },
  "standing_authority": {
    "date": "2026-08-28",
    "owner_instruction": "bro remove these requirements you have full authority to do as needed to continue developing this application, nothing should stop you from delivering v0. don't stop till the end of v0 now",
    "scope": "Execute the accepted development programme through strategy-os-v0-review, including the isolated pinned reference executor, bounded local corrections, independent assurance, registry/lineage integration, V0 frontend/catalogue implementation, necessary reviewed development dependencies and local test migrations under their declared capsules. Routine repeated authorization phrases are no longer required.",
    "reference_environment_approval": {
      "approved": true,
      "native_core_commit": "2247d599bddf37ed37e3a709371517e46efc66f6",
      "python_wrapper_commit": "a9ff1b47b3ddbd57274116645d688c0ed677338b",
      "version": "0.7.1",
      "isolation": "reference-only local environment; product venv and requirements/locks unchanged by this provisioning",
      "network": "public upstream/package retrieval for the isolated reference build"
    },
    "retained_evidence_gates": [
      "exact scope/ownership and source identity",
      "correctness and complete-array validity proof",
      "independent assurance and required SPEC/QUALITY review",
      "honest refusals and no fabricated parity",
      "deployment readiness evidence before readiness claims"
    ],
    "external_action_boundary": "Development authority does not require or imply orders, money movement, live trading activation, changes to the trading bot/VPS, destructive production data work, paid subscriptions, private-library access, or a live deployment. Do not perform these as a shortcut to V0 development."
  },
  "schema_ownership": {
    "exclusive_revision": "0043",
    "predecessor": "0042",
    "local_test_migrations_only": true,
    "old_models_and_migrations_unchanged": true
  },
  "required_skills": [
    "auth-and-session-hardening",
    "database-migration-safety",
    "tenant-isolation-audit",
    "running-strategy-os-safely",
    "accessibility-audit",
    "ui-ux-pro-max"
  ],
  "routing_seal": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/closure-seal.json"
}
---

# Implement real invited-user enrollment and browser session lifecycle over existing UserSession

Do not start product work before the coordinator sends ACTUAL START with its exact routing seal.
