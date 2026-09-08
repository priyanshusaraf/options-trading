---
{
  "id": "post-phase5-indicator-accuracy-remaining-oracles-assurance",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently accept or reject the exact remaining-oracles component/parameter/output universe and its resource/state evidence before integration.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently accept or reject the exact remaining-oracles component/parameter/output universe and its resource/state evidence before integration. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
  "dependency_gate": "post-phase5-indicator-accuracy-remaining-oracles",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_remaining_oracles_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_remaining_oracles_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-remaining-oracles-assurance.md"
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
    "classification": "evidence-only",
    "required_evidence": "Name exact artifacts, locked runtime, resource bounds, semantic/cache identity and refusal evidence; unresolved release assembly belongs to strategy-os-v0-security-operations-deployability before its acceptance."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "owner_task": "01a04d51-4720-7980-be5d-83cb064aa0e3",
  "parallel_budget": 0,
  "assignments": [],
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
    "Different assurance owner; oracle imports no product math or its helper code.",
    "Every claimed component/output and valid/invalid/seed/session state is tested in the locked product environment.",
    "An omission, wrong output binding or real numerical/state guard mutation fails the relevant consumer and is restored.",
    "No approved expected fixture is overwritten from product results; failures preserve rejected evidence.",
    "Pass is evidence for this wave only, not registry/publication or deployment authority."
  ],
  "test_plan": [
    "Read exact source and version/licence receipts before using a reference.",
    "Compare complete arrays/masks and threshold classes; separately verify parameter/output closure.",
    "Audit parameter-derived resource/state upper bounds, including max-domain and first-above-domain cases."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_remaining_oracles_assurance_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_remaining_oracles_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_remaining_oracles_oracle.py",
      ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles-assurance"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "independence": "Must be a different owner from the corresponding implementation. Read product code, but author expected vectors independently; no product mutation. Product-changing findings return to an explicitly bounded correction.",
  "assurance_result": {
    "verdict": "ASSURANCE PASS",
    "owner_task": "01a04d51-4720-7980-be5d-83cb064aa0e3",
    "report": ".agent/runs/post-phase5-indicator-accuracy-remaining-oracles-assurance/report.md",
    "report_sha256": "a7c227b4d87d58943f2c3e15030f4e960e4472c8beceddadf63b1df5975f171f",
    "review_package_sha256": "6f055ac6a8f72a1ae89455823ede4229cfca8289f16bb72e6b00de06a084c76c",
    "closure_seal_sha256": "b7ce6f3559b4482f5ce5af23fe848131548d3634e27b8060f15c84e957a2683c",
    "checks_passed": 495,
    "mutations_detected_and_restored": 4,
    "publication": false,
    "deployment": false
  }
}

---

# Remaining oracles assurance

Independently accept or reject the exact remaining-oracles component/parameter/output universe and its resource/state evidence before integration.

This capsule is a future bounded assignment. The architecture replan does not start it.
