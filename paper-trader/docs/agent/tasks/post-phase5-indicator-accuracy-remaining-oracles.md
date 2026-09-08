---
{
  "id": "post-phase5-indicator-accuracy-remaining-oracles",
  "phase": "post-phase5",
  "status": "implementation_complete_pending_assurance",
  "kind": "critical_accuracy_correction",
  "goal": "Implement only the 10 declared remaining-oracles component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Implement only the 10 declared remaining-oracles component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
        "EWMA_VOLATILITY",
        "GARMAN_KLASS",
        "ICHIMOKU_COMPONENTS",
        "PARKINSON",
        "REALIZED_VOLATILITY",
        "ROGERS_SATCHELL",
        "SUPERTREND",
        "VOLATILITY_PERCENTILE",
        "VOLATILITY_RANK",
        "YANG_ZHANG"
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
  "dependency_gate": "post-phase5-indicator-accuracy-session-prefix-fresh-assurance",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/remaining_oracles.py",
    "paper-trader/backend/tests/test_indicator_accuracy_remaining_oracles.py",
    ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-remaining-oracles.md",
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
    {"id": "v0_data_only_connection", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md", "owner_task": "/root/v0_data_only_connection", "status": "recheck_active"},
    {"id": "v0_local_release_operations", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md", "owner_task": "/root/v0_local_release_operations", "status": "correction_active"},
    {"id": "v0_frontend_route_attribution_correction", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-route-attribution-correction.md", "owner_task": "/root/v0_frontend_production_convergence", "status": "active"},
    {"id": "v0_monitoring_intent_contract", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-intent-contract.md", "owner_task": "/root/v0_nodes_signals_inventory", "status": "active"}
  ],
  "owner_task": "01a04d37-8ad8-7052-8115-531ae52d4095",
  "component_scope": [
    "EWMA_VOLATILITY",
    "GARMAN_KLASS",
    "ICHIMOKU_COMPONENTS",
    "PARKINSON",
    "REALIZED_VOLATILITY",
    "ROGERS_SATCHELL",
    "SUPERTREND",
    "VOLATILITY_PERCENTILE",
    "VOLATILITY_RANK",
    "YANG_ZHANG"
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
    "assignment_id": "post_phase5_indicator_accuracy_remaining_oracles_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/remaining_oracles.py",
      "paper-trader/backend/tests/test_indicator_accuracy_remaining_oracles.py",
      ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "implementation_result": {
    "status": "implementation_complete_pending_assurance",
    "verdict": "IMPLEMENTATION PASS PENDING FRESH INDEPENDENT ASSURANCE",
    "report": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles/report.md",
    "report_sha256": "82385e9a622e82956e1d62ac690c3ab70d35f81c8e00f3b81ace26cc7eb3eac9",
    "closure_seal": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles/closure-seal.json",
    "closure_seal_sha256": "b9164d768ec23315d28c00644b204677ea6e8bb6889a07ebd1fa9d08e2e535ae",
    "source_sha256": "aa0beead42fa1ee0ffc69dddcfc7fa3d83d62ec5c431138950593115261a061c",
    "owner_test_sha256": "473d04ec8eb2c6d1da08b575afca3cf0553664d5d2e39159bae927d6370f323a",
    "candidates": 7,
    "typed_refusals": 3,
    "owner_checks": 65,
    "affected_subsystem_checks": 432,
    "mutations_detected": 3,
    "protected_shared_bytes_unchanged": true,
    "independent_assurance": false,
    "publication": false,
    "deployment": false
  }
}

---

# Remaining oracles

The 10 declared decisions have a sealed local implementation PASS. Seven semantic-v2 candidates remain unpublished, and Garman-Klass, Ichimoku and Supertrend remain typed refusals.

Fresh different-owner assurance remains required. This closure authorizes no registry publication, provider/frontend/schema/dependency/deployment/live/order/money or later-scope work.
