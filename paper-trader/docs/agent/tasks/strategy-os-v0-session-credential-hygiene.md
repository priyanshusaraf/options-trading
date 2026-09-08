---
{
  "id": "strategy-os-v0-session-credential-hygiene",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "complete",
  "goal": "Keep issued session credentials out of routine representations",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Routine issuance-object representations no longer expose bearer credentials; onboarding remains unimplemented. Required local checks and independent SPEC/QUALITY review must pass; protected drift attributed; no release claim."
  },
  "risk_tags": [
    "critical",
    "v0",
    "parallel-owned"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md",
      "sections": [
        "V0 test matrix",
        "Security findings",
        "Data and licensing gates",
        "V0 deployment topology to prove",
        "Deployability gates"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-precision-slate-shell-foundation",
  "programme_assignment": {
    "assignment_id": "v0_session_credential_hygiene",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output",
    "primary_programme_owner": false,
    "coordinator": "01a04997-52e4-79c3-ad87-9c896b560920",
    "prerequisite": "Coordinator materializes exact assignment and seals narrow successor orchestration test before START; no repeated user permission."
  },
  "allowed_paths": [
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/tests/test_user_sessions.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-session-credential-hygiene.md",
    ".agent/runs/strategy-os-v0-session-credential-hygiene"
  ],
  "new_paths": [],
  "protected_paths": [
    "AGENTS.md",
    ".codex",
    ".agents",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/strategy",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/research",
    "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27",
    ".agent/runs/post-phase5-indicator-accuracy-*",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/tests/test_health_endpoint.py",
    "paper-trader/backend/tests/test_v0_release_profile.py",
    "paper-trader/backend/tests/test_v0_private_diagnostics.py",
    "paper-trader/backend/app/core/static_scopes.py",
    "paper-trader/backend/app/api/static_scope_routes.py",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/db/planes.py",
    "paper-trader/backend/app/db/copy_contract.py",
    "paper-trader/backend/migrations/versions/20260828_0042_static_instrument_scopes.py",
    "paper-trader/backend/tests/test_static_scopes.py",
    "paper-trader/backend/tests/test_static_scope_routes.py",
    "paper-trader/backend/tests/test_static_scope_migration.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_db_planes.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/api/auth.py",
    "paper-trader/backend/tests/test_api_auth.py"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/app/db/models.py",
      "sha256": "8687bdcac880b326e6dfb6391d40257e0c36fc17430ee467548928798204582d"
    },
    {
      "path": "paper-trader/backend/app/api/auth.py",
      "sha256": "914f54fe71eca4916d04f56688b43c0cd050352a90cd60585b64f0693e0e5724"
    },
    {
      "path": "paper-trader/backend/tests/test_api_auth.py",
      "sha256": "fe8b31a9219747d69b7fc3300dad3c6fbfd6ab0f8198bd4cbc1410e8612f80ad"
    }
  ],
  "scope": [
    "Suppress bearer values from routine repr/str of IssuedBearerCredential using the existing dataclass mechanism. Keep explicit one-time .token delivery, field names, return type, frozen behavior and token entropy unchanged. Do not invent encryption or a new secret framework.",
    "Extend the existing user-session tests to cover object repr, str, container repr and ordinary logging interpolation with synthetic credentials; demonstrate actual issuance still authenticates and revoke/expiry behavior stays unchanged.",
    "Do not change issuance lifetime policy, revoke ownership signature, roles/actions, transport, cookies, token hashing, persistence, auth_enabled, legacy bootstrap or session semantics. Explicit access to .token/dataclasses.asdict is not claimed redacted; call-site audit must reject claims broader than routine representation."
  ],
  "source_failure_hypothesis": "IssuedBearerCredential is a frozen dataclass with an ordinary token field at principal.py:283-289. Generated repr/str therefore includes the bearer even though persistence and Principal.to_dict omit it. Existing plaintext tests cover SQL logs and principal DTO, not issuance-object repr.",
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "fork_turns": "none",
  "owner_gates": [
    "Standing V0 development and parallel-work authority applies; do not ask for a routine token.",
    "No live credentials/providers/orders, VPS, hosting/remote/CI changes, licence-sensitive adoption, production data or deployment.",
    "You are not alone in the codebase. Do not revert others; no stash/reset/clean/rebase/stage/commit. Only named paths; no hidden helper edits.",
    "A critical reviewer may start only after integrated evidence, by the sole coordinator; zero implementation subagents."
  ],
  "test_plan": [
    "Use existing _seed/_issue fixture to produce the failing repr/logging test first. Assert no synthetic bearer in repr/str/list repr/captured normal logging and unchanged explicit delivery/digest resolution.",
    "From backend: .venv/bin/python -m pytest -q tests/test_user_sessions.py tests/test_api_auth.py. Run with safe test settings and synthetic temporary databases.",
    "In a leaf-owned isolated copy, remove the repr suppression and show the exact regression fails, restore and rerun. No working-tree mutation of other assignments."
  ],
  "review": {
    "required": true,
    "assignment_id": "v0_session_credential_hygiene_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "One independent integrated critical review after evidence: credential exposure boundary. Sol high reason: authentication secret handling despite small diff.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-session-credential-hygiene/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api/principal.py",
      "paper-trader/backend/tests/test_user_sessions.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-session-credential-hygiene/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "deployment_impact": {
    "classification": "compatible",
    "prove_now": [
      "Use existing _seed/_issue fixture to produce the failing repr/logging test first. Assert no synthetic bearer in repr/str/list repr/captured normal logging and unchanged explicit delivery/digest resolution.",
      "From backend: .venv/bin/python -m pytest -q tests/test_user_sessions.py tests/test_api_auth.py. Run with safe test settings and synthetic temporary databases.",
      "In a leaf-owned isolated copy, remove the repr suppression and show the exact regression fails, restore and rerun. No working-tree mutation of other assignments."
    ],
    "integration_owner": "strategy-os-v0-security-operations-deployability",
    "release_assembly_owner": "strategy-os-v0-security-operations-deployability",
    "rollback": "No deployment. Compatible changes revert only own code after owner decision; static-scope migration requires writer quiescence and retained readable facts/forward repair, never destructive schema downgrade."
  },
  "stop_conditions": [
    "Unattributed protected drift; shared-contract change outside paths; missing required proof; first compaction handoff before a second.",
    "Any numerical catalogue publication, new authority or external action required to finish must be returned to coordinator, not guessed."
  ],
  "nonclaims": [
    "No implementation acceptance from source reading or draft status.",
    "No indicator, dataset, provider, beta, live or deployment acceptance. No fixture-backed fake product."
  ],
  "acceptance": [
    "Suppress bearer values from routine repr/str of IssuedBearerCredential using the existing dataclass mechanism. Keep explicit one-time .token delivery, field names, return type, frozen behavior and token entropy unchanged. Do not invent encryption or a new secret framework.",
    "Extend the existing user-session tests to cover object repr, str, container repr and ordinary logging interpolation with synthetic credentials; demonstrate actual issuance still authenticates and revoke/expiry behavior stays unchanged.",
    "Do not change issuance lifetime policy, revoke ownership signature, roles/actions, transport, cookies, token hashing, persistence, auth_enabled, legacy bootstrap or session semantics. Explicit access to .token/dataclasses.asdict is not claimed redacted; call-site audit must reject claims broader than routine representation.",
    "Routine issuance-object representations no longer expose bearer credentials; onboarding remains unimplemented."
  ],
  "owner_task": "01a049a6-e83c-7791-8af2-79f80e35cc64",
  "accepted_replan": {
    "schema": "v0-parallel-leaf-authority/1",
    "replan_seal": ".agent/runs/strategy-os-v0-parallel-workstream-replan/closure-seal.json",
    "replan_seal_sha256": "37fe5c736a1ae169e08be985ec27fcf615b377419977e577da4445ff1da334ec",
    "ownership": ".agent/runs/strategy-os-v0-parallel-workstream-replan/leaf-ownership.json",
    "ownership_sha256": "91a4265c258a515075ed3c2c6d0dbdf86587ecfd8901e7cf7a688d390ad6dfa6",
    "coordinator": "01a04997-52e4-79c3-ad87-9c896b560920",
    "permitted_assignment_ids": [
      "v0_shell_access_revalidation",
      "v0_session_credential_hygiene",
      "v0_private_diagnostics",
      "v0_static_scope_foundation"
    ],
    "maximum_active_owners": 4,
    "primary_stage": "post-phase5-indicator-accuracy-multi-output",
    "numerical_parallel_budget": 0,
    "stage_acceptance": "unchanged serial main programme",
    "public_capability_opening": false,
    "publication": false,
    "deployment": false
  },
  "v0_standing_development_authorization": {
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
  "parallel_development_authorization": {
    "date": "2026-08-28",
    "source_task": "01a04977-e974-7d41-b09d-393159514bc8",
    "owner_instruction": "can we have a parallel workflow running for parts of the application which are unrelated to this indicator verification? i think that overall v0 isn't just gated by indicators there are a lot of steps which can progress without just the nodes as well right lets go ahead with all of them on the side",
    "scope": "Identify and execute accepted V0 work that is independent of indicator correctness, under exact disjoint assignments. Keep numerical evidence, shared identity, frontend truth, independent assurance, convergence and external-action gates. No routine authorization pause.",
    "immediate_assignment": "One read-only architecture owner identifies executable independent leaves and exact shared-contract freezes. Numerical implementation parallelism remains zero.",
    "stage_acceptance": "Main programme acceptance remains serial. Parallel leaves do not advance a dependent stage or consume unpublished indicators. Existing declared-assignment support is used; no second programme controller or scheduler is created."
  },
  "concurrent_ownership": {
    "main_numerical_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
      "paper-trader/backend/tests/test_indicator_accuracy_multi_output.py"
    ],
    "peer_paths": {
      "v0_shell_access_revalidation": [
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
        "paper-trader/docs/agent/tasks/strategy-os-v0-shell-access-revalidation.md",
        ".agent/runs/strategy-os-v0-shell-access-revalidation"
      ],
      "v0_private_diagnostics": [
        "paper-trader/backend/app/main.py",
        "paper-trader/backend/tests/test_health_endpoint.py",
        "paper-trader/backend/tests/test_v0_release_profile.py",
        "paper-trader/backend/tests/test_v0_private_diagnostics.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-private-diagnostics.md",
        ".agent/runs/strategy-os-v0-private-diagnostics"
      ],
      "v0_static_scope_foundation": [
        "paper-trader/backend/app/core/static_scopes.py",
        "paper-trader/backend/app/api/static_scope_routes.py",
        "paper-trader/backend/app/api/product_object_routes.py",
        "paper-trader/backend/app/db/models.py",
        "paper-trader/backend/app/db/planes.py",
        "paper-trader/backend/app/db/copy_contract.py",
        "paper-trader/backend/migrations/versions/20260828_0042_static_instrument_scopes.py",
        "paper-trader/backend/tests/test_static_scopes.py",
        "paper-trader/backend/tests/test_static_scope_routes.py",
        "paper-trader/backend/tests/test_static_scope_migration.py",
        "paper-trader/backend/tests/test_schema_migrations.py",
        "paper-trader/backend/tests/test_db_planes.py",
        "paper-trader/backend/tests/test_postgresql_restore_contract.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-static-scope-foundation.md",
        ".agent/runs/strategy-os-v0-static-scope-foundation"
      ]
    },
    "rule": "Protected means do not write. Peers may change exactly their named paths; record hashes and attribution, preserve interface freezes, and reconcile unexplained drift. Never restore another owner."
  },
  "routing_seal": ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/parallel-routing-seal.json",
  "local_evidence": {
    "status": "local_pass_pending_independent_spec_quality",
    "owner_task": "01a049a6-e83c-7791-8af2-79f80e35cc64",
    "focused_tests_passed": 35,
    "regression_red_cases": 5,
    "isolated_mutation_red_cases": 5,
    "isolated_restored_passed": 5,
    "source_sha256": {
      "paper-trader/backend/app/api/principal.py": "2ac5312fa2795d10f7f6b5a4d54c42761287c54ef1f4e21a74d698e95f65be15",
      "paper-trader/backend/tests/test_user_sessions.py": "5d6aacced3a9201bed586f27a4ad4b6f369d19a10880ca81569684f00c1161c5"
    },
    "review_package": ".agent/runs/strategy-os-v0-session-credential-hygiene/review-package.json",
    "seal": ".agent/runs/strategy-os-v0-session-credential-hygiene/local-evidence-seal.json",
    "independent_acceptance": false,
    "publication": false,
    "deployment": false,
    "v0_complete": false
  },
  "acceptance_result": {
    "SPEC": "PASS",
    "QUALITY": "PASS",
    "independent_acceptance": true,
    "review_assignment": "v0_session_credential_hygiene_review",
    "review_report": ".agent/runs/strategy-os-v0-session-credential-hygiene/review.md",
    "review_verdict": ".agent/runs/strategy-os-v0-session-credential-hygiene/review/verdict.json",
    "review_verdict_sha256": "8840c824581865b7972cf60e5372d3661f6162eb095b76ef169cfdceda169c9b",
    "source_sha256": {
      "paper-trader/backend/app/api/principal.py": "2ac5312fa2795d10f7f6b5a4d54c42761287c54ef1f4e21a74d698e95f65be15",
      "paper-trader/backend/tests/test_user_sessions.py": "5d6aacced3a9201bed586f27a4ad4b6f369d19a10880ca81569684f00c1161c5"
    },
    "closure_seal": ".agent/runs/strategy-os-v0-session-credential-hygiene/closure-seal.json",
    "publication": false,
    "deployment": false,
    "v0_complete": false
  }
}
---

# Keep issued session credentials out of routine representations

Materialized from the sealed independent V0 dependency replan under standing authority. Await the exact owner assignment and START. Development is parallel; feature opening and final acceptance remain separate.
