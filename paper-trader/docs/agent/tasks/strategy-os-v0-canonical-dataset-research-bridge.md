---
{
  "id": "strategy-os-v0-canonical-dataset-research-bridge",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "accepted",
  "goal": "Execute existing graph research from verified persisted canonical datasets without an execution provider",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete exact contract, integrated source/preservation/runtime/mutation evidence and one actual independent SPEC PASS/QUALITY PASS; owner closure verified. No public capability, numerical, deployment or whole-V0 acceptance."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
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
      "path": ".agent/runs/strategy-os-v0-q03-cold-admission-clarification/dataset-contract.md",
      "sections": [
        "Scope and authority",
        "Selection and persisted trust",
        "Executable segment interpretation",
        "Instrument projection and recipe identity",
        "Real consumers and evidence",
        "Deployment and remaining gates"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md",
      "sections": [
        "Backtest and robustness",
        "Data and instruments"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": [
        "1. Point-in-time market rulebook",
        "4. Contract identity",
        "7. Data sufficiency",
        "9. Missing-data semantics",
        "10. Cross-instrument alignment",
        "11. Cross-timeframe causality",
        "13. Dataset provenance"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "programme_assignment": {
    "assignment_id": "v0_canonical_dataset_bridge",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output-correction-assurance",
    "primary_programme_owner": false,
    "coordinator": "01a04a5b-40f5-73a0-a443-7fa8ea67a348",
    "prerequisite": "Read-only orientation until exact owner/routing seal and ACTUAL START; no user token."
  },
  "allowed_paths": [
    "paper-trader/backend/app/api/ir_experiment_routes.py",
    "paper-trader/backend/research/orchestrator/graph_experiment.py",
    "paper-trader/backend/tests/test_ir_experiment_routes.py",
    "paper-trader/backend/research_tests/test_graph_experiment.py",
    "paper-trader/backend/research/data/canonical_dataset.py",
    "paper-trader/backend/research_tests/test_canonical_dataset.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-dataset-research-bridge.md",
    ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/research/domain/strategy_admissions.py"
  ],
  "new_paths": [
    "paper-trader/backend/research/data/canonical_dataset.py",
    "paper-trader/backend/research_tests/test_canonical_dataset.py"
  ],
  "protected_paths": [
    ".agents",
    ".codex",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "AGENTS.md",
    "paper-trader/backend/app/accounts/__init__.py",
    "paper-trader/backend/app/accounts/browser_auth.py",
    "paper-trader/backend/app/api/auth_session_routes.py",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/app/core/config.py",
    "paper-trader/backend/app/db/copy_contract.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/db/planes.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/market_data",
    "paper-trader/backend/app/market_truth",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
    "paper-trader/backend/requirements.lock",
    "paper-trader/backend/research/domain/migrations",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/orchestrator/run.py",
    "paper-trader/backend/research_tests/conftest.py",
    "paper-trader/backend/scripts/create_enrollment_invite.py",
    "paper-trader/backend/tests/conftest.py",
    "paper-trader/backend/tests/test_api_auth.py",
    "paper-trader/backend/tests/test_browser_auth.py",
    "paper-trader/backend/tests/test_browser_auth_migration.py",
    "paper-trader/backend/tests/test_db_planes.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_user_sessions.py",
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
      "path": "paper-trader/backend/app/backtest/dataset_store.py",
      "sha256": "85c9111e6f20080c6a9b5451c77f3e5ae6c34e789c777f5afa9cab2029c08442"
    },
    {
      "path": "paper-trader/backend/research/domain/strategy_admissions.py",
      "sha256": "558857af6ab5f31cd523d147c11a56ded88db9dfcf100965c9a9e2625ba5efed"
    },
    {
      "path": "paper-trader/backend/research/orchestrator/run.py",
      "sha256": "73c6e8c70dd896b68493b38ffbe7347637a087f90aaad6969f46942b897a38c5"
    },
    {
      "path": "paper-trader/backend/research/domain/models.py",
      "sha256": "54a438809170ede0a085b0ff846bb189a46446d6cb7a2cf94ae6971335decb07"
    },
    {
      "path": "paper-trader/backend/app/market_truth/identity.py",
      "sha256": "c990e27bcb314f9b9a11d47144374edda2199fae244868184c43602b2f1867b7"
    },
    {
      "path": "paper-trader/backend/app/market_data/candles.py",
      "sha256": "81347698c248c117633915d2b5ce7b50f37777632e4cf417d0bd8c20a53c4017"
    },
    {
      "path": "paper-trader/backend/app/strategy/ir_adapter.py",
      "sha256": "9d403570acd7a2b91464543e608cb1fb1bc6bf92e93b1a71fe08016ce0b6b226"
    }
  ],
  "scope": [
    "Implement only the complete frozen dataset-contract.md contract; no duplicate authority or hidden fallback.",
    "Preserve inherited and peer edits; you are not alone in the checkout. Only exact paths belong to this owner. Shared changes outside ownership require a bounded serial correction before mutation.",
    "One durable goal before product work; zero agents. Request the single coordinator-routed critical reviewer only after integrated local evidence; do not self-certify or launch a reviewer."
  ],
  "acceptance": [
    "Every requirement of .agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/dataset-contract.md is evidenced; preserve every explicit refusal/remaining gate.",
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
  "owner_task": "01a04a83-352a-7e72-be8d-f368a590275a",
  "contract": {
    "path": ".agent/runs/strategy-os-v0-q03-cold-admission-clarification/dataset-contract.md",
    "sha256": "20c7808685eb4e76ace6e6b62960a1ff37382a94b20e0a554f6b58b9a05de168"
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
    "assignment_id": "v0_canonical_dataset_bridge_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "One independent evidence-backed integrated critical review of research validity, causal data and tenant lineage.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api/ir_experiment_routes.py",
      "paper-trader/backend/research/orchestrator/graph_experiment.py",
      "paper-trader/backend/tests/test_ir_experiment_routes.py",
      "paper-trader/backend/research_tests/test_graph_experiment.py",
      "paper-trader/backend/research/data/canonical_dataset.py",
      "paper-trader/backend/research_tests/test_canonical_dataset.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-dataset-research-bridge.md",
      ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "deployment_impact": {
    "classification": "compatible persisted-data consumer; no schema/dependency change",
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
  "schema_changes": false,
  "required_skills": [
    "anti-lookahead-and-market-truth",
    "research-validity-audit",
    "tenant-isolation-audit"
  ],
  "routing_seal": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/closure-seal.json",
  "contract_clarification": {
    "path": ".agent/runs/strategy-os-v0-q03-schema-role-clarification/decision.json",
    "sha256": "2ae577e076fd2080642ceebbeb69f45775f8f31fe1ca1570eb5a1f9962e9e41c"
  },
  "admission_order_clarification": {
    "path": ".agent/runs/strategy-os-v0-q03-cold-admission-clarification/decision.json",
    "sha256": "8ecdc007a7351785fa39676eaca6b7d0a4ac45383f4050db0cae716e0e5601b8"
  },
  "performance_loader_amendment": {
    "path": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/review-correction/loader-amendment/decision.json",
    "sha256": "10f0ca0bb91d7572714cfb5ff9e808b98320bc1d7c9ceec31aa05e44889ff2f4"
  },
  "acceptance_result": {
    "status": "accepted",
    "SPEC": "PASS",
    "QUALITY": "PASS",
    "review_sha256": "7c6814d83af65edb93b210c0d7bf27ca7e9973890015be2285002d7465197221",
    "verdict_sha256": "43fc8fb0ff35e694d8c9e58fb7d43a7fda8a2e58e8f895276c112ce116ab2e02",
    "recheck_seal_sha256": "6a9ef774e8c5ccfc8320c342cb3364ba9385290a0e2b07fa5d15d5f2ca17177b",
    "closure": {
      "path": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/coordinator-acceptance/decision.json",
      "sha256": "bae5b19a9cde57ca6695a219a6b5ae79c2329f48a6692ed3ba8a9c5ec91247ec"
    },
    "capacity_claim": false,
    "publication": false,
    "deployment": false,
    "v0_complete": false
  }
}
---

# Execute existing graph research from verified persisted canonical datasets without an execution provider

Do not start product work before the coordinator sends ACTUAL START with its exact routing seal.
