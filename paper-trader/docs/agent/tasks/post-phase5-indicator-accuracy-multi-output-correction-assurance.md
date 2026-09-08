---
{
  "id": "post-phase5-indicator-accuracy-multi-output-correction-assurance",
  "phase": "post-phase5",
  "status": "active",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently accept or reject corrected mathematical MACD source and STOCH_RSI mathematics plus the full9component/19output wave.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently accept or reject corrected mathematical MACD source and STOCH_RSI mathematics plus the full9component/19output wave. Named complete-array/source/identity/state/resource evidence, genuine guard mutations and a sealed report are required. No publication or deployment."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "semantic-versioning"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/architecture-decision.md",
      "sections": [
        "Immutable version 1",
        "Parameter-dependent contracts: bounded extension, no expression language",
        "Validity, sessions and outputs",
        "Source and oracle independence",
        "Sequencing and stopping rule"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/legacy-cache-result-policy.md",
      "sections": [
        "Version and graph identity",
        "Cache and result disposition",
        "Authority and compatibility"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/semantic-contracts.md",
      "sections": [
        "BOLLINGER_BANDS",
        "BOLLINGER_BANDWIDTH",
        "BOLLINGER_PERCENT_B",
        "DONCHIAN_CHANNELS",
        "KELTNER_CHANNELS",
        "MACD",
        "PPO",
        "STOCHASTIC",
        "STOCH_RSI"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/source-authority.json",
      "sections": [
        "records"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/binding-contract-spec.json",
      "sections": [
        "source_contract",
        "binding_registration",
        "bound_contract",
        "validation_rules",
        "legacy"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/source-access-policy.md",
      "sections": [
        "Inspected sources",
        "Reference environment gate",
        "Deferred numerical conventions"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/verification-contract.md",
      "sections": [
        "Thresholds",
        "Complete-array comparators",
        "Adversarial fixtures",
        "Operational evidence"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-multi-output-source-replan/decision.json",
      "sections": [
        "controlling_reference",
        "corrected_target_delta",
        "source_provenance_update",
        "F02",
        "F03",
        "retained_invariants",
        "required_proof",
        "versioning"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-multi-output-assurance/report.md",
      "sections": [
        "Verdict: ASSURANCE REJECT",
        "Findings",
        "Independence and preserved failures",
        "Direct verification"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-multi-output-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_multi_output_correction_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_correction_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-multi-output-correction-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-multi-output-correction-assurance.md"
  ],
  "protected_paths": [
    ".agent/runs/post-phase5-indicator-accuracy-correction-replan",
    ".agent/runs/post-phase5-indicator-accuracy-multi-output",
    ".agent/runs/post-phase5-indicator-accuracy-multi-output-assurance",
    ".agent/runs/post-phase5-indicator-accuracy-multi-output-correction",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/common.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/resource_plan.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_oracle.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_recursive_sar_source_oracle.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_recursive_state_oracle.py",
    "paper-trader/backend/tests/test_indicator_accuracy_multi_output.py",
    "paper-trader/backend/tests/test_indicator_accuracy_multi_output_assurance.py",
    "paper-trader/backend/tests/test_indicator_accuracy_multi_output_correction.py",
    "paper-trader/backend/tests/test_indicator_accuracy_recursive_sar_source_assurance.py",
    "paper-trader/backend/tests/test_indicator_accuracy_recursive_sar_source_contract.py",
    "paper-trader/backend/tests/test_indicator_accuracy_recursive_state.py",
    "paper-trader/backend/tests/test_indicator_accuracy_recursive_state_assurance.py",
    "paper-trader/frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "component_scope": [
    "BOLLINGER_BANDS",
    "BOLLINGER_BANDWIDTH",
    "BOLLINGER_PERCENT_B",
    "DONCHIAN_CHANNELS",
    "KELTNER_CHANNELS",
    "MACD",
    "PPO",
    "STOCHASTIC",
    "STOCH_RSI"
  ],
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "v0_auth_session_transport",
      "kind": "bounded_parallel_implementation",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-transport.md",
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
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "owner_task": "01a04a82-f51b-7c01-bb03-8f7421108b99",
      "primary_programme_owner": false,
      "status": "assigned_waiting_sealed_START"
    },
    {
      "id": "v0_canonical_dataset_bridge",
      "kind": "bounded_parallel_implementation",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-dataset-research-bridge.md",
      "allowed_paths": [
        "paper-trader/backend/app/api/ir_experiment_routes.py",
        "paper-trader/backend/research/orchestrator/graph_experiment.py",
        "paper-trader/backend/tests/test_ir_experiment_routes.py",
        "paper-trader/backend/research_tests/test_graph_experiment.py",
        "paper-trader/backend/research/data/canonical_dataset.py",
        "paper-trader/backend/research_tests/test_canonical_dataset.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-dataset-research-bridge.md",
        ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge"
      ],
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "owner_task": "01a04a83-352a-7e72-be8d-f368a590275a",
      "primary_programme_owner": false,
      "status": "assigned_waiting_sealed_START"
    }
  ],
  "numerical_parallel_budget": 0,
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "source_decision": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-multi-output-source-replan/decision.json",
    "sha256": "f954430f5b7981078faf609fba47a0754187f3923f2ae2dc596368a18c3e271a"
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
  "reference_environment": {
    "receipt": ".agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment/environment-receipt.json",
    "receipt_sha256": "4009d26ff3949641700d59b33ec8a55d284eaa86ae759bc25a694a8e9396153a",
    "approved": true,
    "reference_only": true,
    "executable": "/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation/.agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment/venv/bin/python",
    "settings": "DEFAULT compatibility, unstable periods zero; no provisioning or product adoption"
  },
  "scope": [
    "Fresh different owner, zero numerical agents/no history fork. Independently author/seal new expectations before corrected product helpers, correction-owner tests/producers or prior expected-value code inspection. Old independent baseline is read-only after authorship.",
    "Verify exact MACD source decision under its new identity, unchanged other8sources, corrected STOCH_RSI impulse/flat and nonzero-movement semantics, all9components/19ports, bounds/defaults/fields/roles/timeframes/masks/seeds/causal prefixes/stream/restart/resources and real consumers.",
    "Preserve old REJECT/native tests, original Decimal90 oracle and exact-rational supplement. Native comparisons still use unchanged strict thresholds and retain every FAIL. F03 actual graph-input planner failures remain separately owned integration debt, not a numerical PASS or hidden skip.",
    "Use genuine isolated omission/output/source/state/numerical mutations with intended test failures0errors/skips and exact restoration. No product/control edits; return reproduced findings for bounded correction."
  ],
  "acceptance": [
    "Exact declared component/output and source/parameter scope; no invented formulas or hidden fallbacks.",
    "Evidence explicitly separates current mathematical/source acceptance, historical native RED, local resource measurements and integration/deployment claims.",
    "Every identity and output/mask/state guard is checked through actual declared consumers; no self-derived expected values."
  ],
  "test_plan": [
    "Complete per-port arrays and masks, source/parameter closure and first-valid seeds; no overlap-only comparator.",
    "Adversarial exact constant/cancellation and small-nonzero cases; prefix, stream, serialized restart, min/default/max measured state/history/memory/event time.",
    "Real resolver/compiler/runtime old/current identity consumers and genuine isolated mutation failures followed by exact restoration."
  ],
  "owner_gates": [
    "Standing development authority applies; no routine user token. No agents unless separately declared; no live/provider/credential/VPS/money/deployment or dependency changes.",
    "Do not edit outside exact ownership, change legacy identity, publish candidates, rewrite old evidence or waive numerical/source gates."
  ],
  "stop_conditions": [
    "Unexplained source/protected drift or required shared-code change.",
    "Unsupported mathematical/source claim or self-derived expected values."
  ],
  "nonclaims": [
    "No publication, native universal parity, frontend/catalogue exposure, deployment or V0 completion.",
    "F03 resource planner remains blocked until exact registry-lineage integration proof."
  ],
  "deployment_impact": {
    "classification": "evidence-only",
    "required_evidence": "Local source/state/resource proof; registry-lineage integration owns whole-job/cache/resource-plan composition, strategy-os-v0-security-operations-deployability owns release assembly."
  },
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_multi_output_correction_assurance_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "package": ".agent/runs/post-phase5-indicator-accuracy-multi-output-correction-assurance/review-package.json",
    "output": ".agent/runs/post-phase5-indicator-accuracy-multi-output-correction-assurance/report.md",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_multi_output_correction_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_correction_oracle.py"
    ],
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0,
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "exclude_paths": []
  },
  "independence": "Fresh different owner with no history and zero numerical agents. Author and seal independent expectations BEFORE corrected formula helpers, implementation-owner tests/producers or previous expected-value code. Reuse immutable independent baselines read-only after authorship; never edit original evidence or product.",
  "owner_task": "01a04a71-4d34-73b2-ab4a-d464ab057177",
  "coordinator": "01a04a8c-db7c-72e0-a864-80a08ec2a596",
  "predecessor_acceptance": {
    "verdict": "IMPLEMENTATION_EVIDENCE_COMPLETE_PENDING_INDEPENDENT_ASSURANCE",
    "seal": ".agent/runs/post-phase5-indicator-accuracy-multi-output-correction/closure-seal.json",
    "seal_sha256": "1150612a38f001b6340c46fe23a7289174cb87f5c188fb7a69cf3c8e49d35327",
    "source_hashes": {
      "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py": "376fa6c30bab8656751272532496b28fb3e331f80485d15797338cc1e70d1457",
      "paper-trader/backend/tests/test_indicator_accuracy_multi_output_correction.py": "596fc5eee059a2bb17686444de1fff4e8a4beb57b952775b1dd0882e03ece0d2"
    },
    "source_decision_sha256": "f954430f5b7981078faf609fba47a0754187f3923f2ae2dc596368a18c3e271a",
    "before_seal_sha256": "566b73b8d5109953e8cea587a19350e81fbc9152648f841bec19196eeabef913",
    "report_sha256": "4839b06eeb96af77a550938a6a39be42f195a2f50ea40f91273f8b8476ffe5f7",
    "review_package_sha256": "c08428a90ae50f379c12a981898ae76baf4b19823576441c30c7641fdd90b08f",
    "independent_acceptance": false,
    "native_failures_retained": 20,
    "F03_failures_retained": 9,
    "publication": false,
    "deployment": false
  },
  "routing_state": "assigned_waiting_sealed_START",
  "routing_seal": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/numerical-assurance-routing/closure-seal.json",
  "coordination_scope": {
    "id": "strategy-os-v0-q03-schema-role-clarification",
    "kind": "bounded_coordinator_contract_correction",
    "owner_task": "01a04a8c-db7c-72e0-a864-80a08ec2a596",
    "goal": "Clarify Q03 provider raw-schema provenance versus index codec encoding from direct evidence; keep same owner and six product paths, no shared product change.",
    "allowed_paths": [
      ".agent/runs/strategy-os-v0-q03-schema-role-clarification",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-multi-output-correction-assurance.md",
      "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-dataset-research-bridge.md",
      ".codex/tests/test_programme_orchestration.py",
      ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/control-transition-index.json"
    ],
    "protected": [
      "all product/test/frontend files outside .codex orchestration test",
      "all previous sealed runs/contracts/decisions including original Q01/Q03 contract and decision"
    ],
    "parallel_budget": 0,
    "authority": "standing allV0 + parallel mandate; explicit handed-off coordinator authority and reproduced Q03-F01",
    "stopping_condition": "Fresh preservation audit, exact source/real persisted reproduction, additive contract/metadata successor with actual negative checks, sealed attribution and same Q03 owner resumed. No feature/numerical/source or V0 acceptance."
  },
  "parallel_auth_dataset_authority": {
    "path": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/leaf-decision.json",
    "sha256": "ffbb88cf2c2fa4c016d1e1368ba3d5a23c5e5f60947f10e0f46b737281d20e3e"
  },
  "concurrent_peer_rule": "Only exact sealed Q01/Q03 ownership is attributed; numerical owner never edits peers. Auth is sole local schema/main/principal/frontend writer; Q03 no shared schema. No dependency/lock change. Coordinator supplies every bounded transition hash.",
  "parallel_auth_dataset_schema_addendum": {
    "path": ".agent/runs/strategy-os-v0-q03-schema-role-clarification/decision.json",
    "sha256": "2ae577e076fd2080642ceebbeb69f45775f8f31fe1ca1570eb5a1f9962e9e41c"
  }
}
---

# Independently accept or reject corrected mathematical MACD source and STOCH_RSI mathematics plus the full9component/19output wave.

Await sealed predecessor acceptance and exact owner START.
