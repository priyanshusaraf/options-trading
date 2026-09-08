---
{
  "id": "post-phase5-indicator-accuracy-session-data",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Implement only the 31 declared session-data component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Implement only the 31 declared session-data component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "semantic-versioning",
    "complete-universe"
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
        "ANCHORED_VWAP",
        "ASK",
        "BARS_SINCE_SESSION_OPEN",
        "BID",
        "BOOK_DEPTH",
        "CLOSE",
        "DISTANCE_FROM_SESSION_HIGH_LOW",
        "DTE",
        "EXPIRY_CALENDAR",
        "HIGH",
        "INSTRUMENT_METADATA",
        "LOW",
        "LTP",
        "MARKET_CLOCK",
        "MID",
        "OHLCV",
        "OPEN",
        "OPENING_RANGE",
        "OPEN_INTEREST",
        "PREVIOUS_SESSION_FIELDS",
        "PREVIOUS_SESSION_OHLC",
        "RESAMPLING",
        "SESSION_CALENDAR",
        "SESSION_HIGH",
        "SESSION_LOW",
        "SESSION_OPEN",
        "SESSION_OPEN_HIGH_LOW",
        "SPREAD",
        "TIMEFRAME",
        "TIME_TO_SESSION_CLOSE",
        "VWAP"
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
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-data",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Start only after the predecessor is accepted and this exact bounded assignment is authorized by the programme/owner.",
    "Stop before an in-place v1 semantic/address change, an undeclared schema/dependency/provider/execution change, or a cross-wave shared-file edit."
  ],
  "stop_conditions": [
    "Any claimed component/output/contract field is missing or a test expected value is self-derived from product math.",
    "A v1 source, descriptor, contract, declaration or implementation address changes.",
    "An unaccepted v2 implementation becomes product-eligible, or registry/cache/result identity is silently rewritten.",
    "A writer reaches a path owned by another wave without serial integration ownership."
  ],
  "deployment_impact": {
    "classification": "compatible versioned analytical/runtime change; no SQL migration authorized",
    "required_evidence": "Name exact artifacts, locked runtime, resource bounds, semantic/cache identity and refusal evidence; unresolved release assembly belongs to strategy-os-v0-security-operations-deployability before its acceptance."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 4,
  "assignments": [
    {
      "id": "v0_launch_convergence_replan",
      "kind": "bounded_read_only_scope_architecture_replan",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-launch-convergence-replan.md",
      "allowed_paths": [
        "paper-trader/docs/agent/tasks/strategy-os-v0-launch-convergence-replan.md",
        ".agent/runs/strategy-os-v0-launch-convergence"
      ],
      "model": "root user-selected model",
      "child_model": "gpt-5.6-sol",
      "child_reasoning_effort": "medium",
      "fork_turns": "none",
      "owner_task": "01a04c7c-257a-7210-9dd3-f639c661db00",
      "primary_programme_owner": false,
      "status": "accepted",
      "product_writes": 0,
      "verdict": "ARCHITECTURE_REPLAN PASS",
      "decision": ".agent/runs/strategy-os-v0-launch-convergence/decision.json",
      "decision_sha256": "eccd558c991ec43d1b794680f9a9a7908f8ef1b947e7a0d943b99f929a9c32b5"
    },
    {
      "id": "v0_data_only_connection",
      "kind": "bounded_parallel_implementation",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md",
      "allowed_paths": [
        "paper-trader/backend/app/api/connection_routes.py",
        "paper-trader/backend/app/providers/connection_store.py",
        "paper-trader/backend/tests/test_connection_routes.py",
        "paper-trader/backend/tests/test_connection_store.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md",
        ".agent/runs/strategy-os-v0-data-only-connection-contract"
      ],
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "owner_task": "/root/v0_data_only_connection",
      "primary_programme_owner": false,
      "status": "active",
      "stable_rebind": ".agent/runs/strategy-os-v0-data-only-connection-materialization/stable-input-rebind.json"
    },
    {
      "id": "v0_local_release_operations",
      "kind": "bounded_parallel_implementation",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md",
      "allowed_paths": [
        "paper-trader/backend/scripts/v0_local_release_evidence.py",
        "paper-trader/backend/tests/test_v0_local_release_operations.py",
        "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md",
        ".agent/runs/strategy-os-v0-local-release-operations"
      ],
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "owner_task": "/root/v0_local_release_operations",
      "primary_programme_owner": false,
      "status": "active",
      "stable_rebind": ".agent/runs/strategy-os-v0-local-release-operations-materialization/stable-input-rebind.json"
    },
    {
      "id": "v0_frontend_production_convergence_foundation",
      "kind": "critical_cross_repository_frontend_foundation",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-production-convergence-foundation.md",
      "allowed_paths": [
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/main.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product",
        "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-production-convergence-foundation.md",
        ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation"
      ],
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "owner_task": "/root/v0_frontend_production_convergence",
      "primary_programme_owner": false,
      "status": "active"
    }
  ],
  "component_scope": [
    "ANCHORED_VWAP",
    "ASK",
    "BARS_SINCE_SESSION_OPEN",
    "BID",
    "BOOK_DEPTH",
    "CLOSE",
    "DISTANCE_FROM_SESSION_HIGH_LOW",
    "DTE",
    "EXPIRY_CALENDAR",
    "HIGH",
    "INSTRUMENT_METADATA",
    "LOW",
    "LTP",
    "MARKET_CLOCK",
    "MID",
    "OHLCV",
    "OPEN",
    "OPENING_RANGE",
    "OPEN_INTEREST",
    "PREVIOUS_SESSION_FIELDS",
    "PREVIOUS_SESSION_OHLC",
    "RESAMPLING",
    "SESSION_CALENDAR",
    "SESSION_HIGH",
    "SESSION_LOW",
    "SESSION_OPEN",
    "SESSION_OPEN_HIGH_LOW",
    "SPREAD",
    "TIMEFRAME",
    "TIME_TO_SESSION_CLOSE",
    "VWAP"
  ],
  "acceptance": [
    "Exactly component_scope is accounted for; no omitted outputs, parameters, input roles or validity masks.",
    "Every KEEP/REPLACE candidate has immutable semantic v2 definitions; REFUSE records have stable negative evidence and no executable placeholder version.",
    "All mathematical variants, bounds, first-valid indices, seeds, zero cases and resets match the matrix and pinned sources.",
    "Batch, streaming and serialized restart agree; state/compute/history bounds are measured over the declared parameter domain.",
    "Existing pandas/numpy lock is unchanged; TA-Lib is reference-only unless a separate oracle-environment owner gate is satisfied.",
    "The module can be inspected/tested as a contributor but is not registered or made product-eligible here."
  ],
  "test_plan": [
    "Defaults, nondefault parameters, minimum, maximum and first-above-bound values; missing field, wrong role, NaN/infinity, flat/zero, impulse, reversal and gap cases.",
    "Every named output and every validity bit compared, not only overlap or a final value.",
    "Complete-prefix tests plus batch/stream/state snapshot/restart at warmup, gaps, reversal and session boundaries.",
    "Source-specific default parity and independent extended-parameter vectors; no self-derived expected values."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_session_data_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-data/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
      "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
      ".agent/runs/post-phase5-indicator-accuracy-session-data"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/ir/first_party/analytical.py",
      "paper-trader/frontend",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/migrations",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-data/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "owner_task": "01a04ac0-ee97-7230-9ffb-1f4e6cdbf1d6",
  "coordinator": "01a04ac0-ee97-7230-9ffb-1f4e6cdbf1d6",
  "predecessor_acceptance": {
    "seal": ".agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance/closure-seal.json",
    "seal_sha256": "4f936a7df88c636953cabb9057d7ad65afbaef7586b3289fea95de4c3c711a32",
    "verdict": "ASSURANCE PASS",
    "publication": false
  },
  "parallel_carry_in": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-session-data/coordinator/decision.json",
    "sha256": "bfd15300a9691fbce64348338ba2e79cf28355622e93bdd488f0edf089d90392"
  },
  "numerical_parallel_budget": 0,
  "parallel_q03_review_addendum": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-session-data/coordinator/q03-review-addendum.json",
    "sha256": "b6f637d626bbe0ef5d3b7268b1a1f83a7625dbd74e9a88e7ab64e5b487752bf7"
  },
  "serial_context_binding_correction": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/routing/decision.json",
    "sha256": "432a852ebe62d604837e41618ff7b8b24c08d12bcacaf8be06b2f62a942dafbe",
    "owner_task": "01a04b00-dbce-7d40-a15d-2234b756bce2",
    "capsule": "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-context-binding-correction.md",
    "session_product_frozen": false,
    "assurance": {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/routing/decision.json",
      "sha256": "dbc582c4f3acaf79e5bbeac60cd6558c4d15965294047b15dcfb0e779c6c36f2",
      "owner_task": "01a04b27-a6e3-7940-b1ea-1b56afd593f5",
      "status": "accepted",
      "seal": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/closure-seal.json",
      "seal_sha256": "4c04161d7d390914981f8f8fe56eee549faf0cca854267d4fbcb61e21e2b91ef"
    }
  },
  "parallel_q01_evidence_recovery": {
    "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/routing/decision.json",
    "sha256": "0ec242dfe91a931354d80b1819f6b6923d20192adfc611a06020b9b5a4f963b1"
  },
  "parallel_q03_loader_amendment": {
    "path": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/review-correction/loader-amendment/decision.json",
    "sha256": "10f0ca0bb91d7572714cfb5ff9e808b98320bc1d7c9ceec31aa05e44889ff2f4"
  },
  "parallel_q01_acceptance": {
    "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/coordinator-acceptance/decision.json",
    "sha256": "f42e233119bba92852501cfdbf0b996c1b6349298f875582ebee42235c142dd5"
  },
  "parallel_q03_acceptance": {
    "path": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/coordinator-acceptance/decision.json",
    "sha256": "bae5b19a9cde57ca6695a219a6b5ae79c2329f48a6692ed3ba8a9c5ec91247ec"
  }
}
---

# Session data

Implement only the 31 declared session-data component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits.

This capsule is a future bounded assignment. The architecture replan does not start it.
