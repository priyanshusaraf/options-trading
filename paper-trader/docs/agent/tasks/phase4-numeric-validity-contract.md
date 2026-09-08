---
{
  "id": "phase4-numeric-validity-contract",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Implement one closed numeric validity contract inside accepted Component IR v2 and prove deterministic scalar, series, boolean, fallback, and entry-gate behavior.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after every unknown, non-finite, and ambiguous case fails closed, v1/v2 behavior stays compatible, named mutations die, and phase4-market-truth-domain is eligible."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "numeric-validity",
    "ir-runtime"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "3. One accepted executable architecture",
        "4. Closed numeric validity contract",
        "11. Deployment contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-architecture",
  "allowed_paths": [
    "paper-trader/backend/app/ir/validity.py",
    "paper-trader/backend/app/ir/schema.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/validate.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/tests/test_ir_numeric_validity.py",
    "paper-trader/docs/agent/tasks/phase4-numeric-validity-contract.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-numeric-validity-contract"
  ],
  "nonclaims": [
    "No market truth, provider capability, persistence, dataset, frontend, deployment, provider, or live authority is implemented.",
    "A valid local value does not prove data sufficiency, causality, capability, admission, or execution safety."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would duplicate accepted IR, validator, resolver, hash, registry, research lineage, execution binding, owner boundary, or authority."
  ],
  "stop_conditions": [
    "A change creates a second evaluator, registry, validator, resolver, or hash.",
    "An invalid value can authorize entry, NaN/infinity can be valid, or fallback is implicit.",
    "V1/v2 IR goldens or prefix behavior regress."
  ],
  "deployment_impact": {
    "classification": "application-contract-additive",
    "affected_dimensions": [
      "Application",
      "Registry",
      "Serialization"
    ],
    "required_evidence": "Focused compatibility, deterministic serialization, refusal, regression, and killed-mutation evidence; no schema, service, deployment, or readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The ten-state vocabulary is closed; VALID carries a finite typed value and all other states carry no executable value.",
    "Unary, multi-input, comparison, boolean, warmup, and explicit fallback behavior is deterministic and registry-declared.",
    "Only VALID(true) authorizes entry; invalid entry inputs do not disable risk-reducing exits.",
    "V1/v2 validation, identity, runtime, and prefix goldens pass."
  ],
  "test_plan": [
    "Run backend/.venv/bin/python -m pytest -q backend/tests/test_ir_numeric_validity.py backend/tests/test_ir_v2_ports_types.py backend/tests/test_ir_v2_vector_runtime.py backend/tests/test_ir_v2_prefix_parity.py.",
    "Kill mutations for invalid-to-false, non-finite VALID, argument-order cause selection, and implicit fallback.",
    "Run protected hashes and git diff --check."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_numeric_validity_contract_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/validity.py",
      "paper-trader/backend/app/ir/schema.py",
      "paper-trader/backend/app/ir/registry.py",
      "paper-trader/backend/app/ir/validate.py",
      "paper-trader/backend/app/ir/runtime.py",
      "paper-trader/backend/tests/test_ir_numeric_validity.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-numeric-validity-contract/owner_integration/report.md",
    "verdicts": [
      "INTEGRATION"
    ],
    "max_rechecks": 0
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 numeric validity contract

This is one durable implementation goal. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py`.
