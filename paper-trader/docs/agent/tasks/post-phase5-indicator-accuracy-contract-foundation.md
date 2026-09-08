---
{
  "id": "post-phase5-indicator-accuracy-contract-foundation",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Implement the smallest canonical versioned contract/binding extension and immutable legacy-address baseline, without registering corrected numeric components or enabling a product surface.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Implement the smallest canonical versioned contract/binding extension and immutable legacy-address baseline, without registering corrected numeric components or enabling a product surface. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
  "dependency_gate": "post-phase5-indicator-accuracy-correction-replan",
  "allowed_paths": [
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/implementation_identity.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/common.py",
    "paper-trader/backend/tests/test_indicator_accuracy_contract_foundation.py",
    ".agent/runs/post-phase5-indicator-accuracy-contract-foundation",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-contract-foundation.md",
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
    "paper-trader/scripts/deploy.sh",
    "paper-trader/backend/app/ir/node_contracts.py"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Start only after explicit authorization AUTHORIZE INDICATOR ACCURACY CONTRACT FOUNDATION.",
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
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [],
  "acceptance": [
    "Canonical /1 contracts and all 125 v1 implementation/descriptor/declaration addresses remain exact in the pinned environment.",
    "A versioned /2 contract/binding record carries exact parameter-dependent warmup, selected fields, timeframe and canonical role/session context through the one resolver and data compiler.",
    "No user expression language or second registry/compiler; all binding rules have transitive implementation identities.",
    "Unknown, forged, missing, reordered or stale binding facts refuse before resource planning/job execution.",
    "Common numeric validity/state helpers are frozen before numerical waves; no invented resource constants or dependency adoption."
  ],
  "test_plan": [
    "All 22 contract obligations plus successor binding fields; v1 round trip/address parity; missing/stale/rule/parameter/role/timeframe/warmup mutation matrix.",
    "Wrong source, forged lower history and provider/owner swaps refuse at the canonical boundary.",
    "No new numeric contributor in app.ir.library and no runtime capability change."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_contract_foundation_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-contract-foundation/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/node_contracts.py",
      "paper-trader/backend/app/ir/registry.py",
      "paper-trader/backend/app/ir/resolve.py",
      "paper-trader/backend/app/ir/implementation_identity.py",
      "paper-trader/backend/app/market_data/requirements.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/common.py",
      "paper-trader/backend/tests/test_indicator_accuracy_contract_foundation.py",
      ".agent/runs/post-phase5-indicator-accuracy-contract-foundation"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-contract-foundation/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "owner_authorization_required": "AUTHORIZE INDICATOR ACCURACY CONTRACT FOUNDATION",
  "owner_authorization": "AUTHORIZE INDICATOR ACCURACY CONTRACT FOUNDATION",
  "implementation_decision": "Preserve resolve(document, registry) purity; carry an immutable binding recipe there and materialize/replay resolved-node-contract receipts in the same DataRequirementPlan compiler using explicit pinned canonical input facts. Source /2 contracts double as their dynamic declaration; no new declaration language. Details in the foundation orientation receipt. Full-registry identity verification found that legacy logic/state/execution/derivative components hash node_contracts.py. That file is now protected and restored byte-exact. Registry-owned schema dispatch delegates /1 to the frozen helper and /2 to private analytical_v2 helpers; no monkey-patching or second registry.",
  "completion": {
    "verdict": "IMPLEMENTATION PASS",
    "report": ".agent/runs/post-phase5-indicator-accuracy-contract-foundation/report.md",
    "report_sha256": "297b763c104809ecd2536feda3a2b774ea45a40aea0b1b946f0b0ef14165d1e2",
    "tests_passed": 321,
    "v1_records_unchanged": 125,
    "default_registry_unchanged": true,
    "independent_contract_assurance": "pending separate owner",
    "numerical_accuracy_claim": false,
    "deployment_authority": false
  }
}

---

# Contract foundation

Implemented under the exact owner authorization. Source and behavioral evidence are sealed under `.agent/runs/post-phase5-indicator-accuracy-contract-foundation`.

This accepts only the foundation implementation. Independent contract assurance is the next capsule and must use a different owner before numerical correction begins. No publication or deployment is authorized.
