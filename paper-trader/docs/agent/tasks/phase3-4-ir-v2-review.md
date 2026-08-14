---
{
  "id": "phase3-4-ir-v2-review",
  "phase": "component-ir-v2-interphase",
  "status": "blocked",
  "goal": "Independently accept or reject the reconciled Component IR v2 contract before Phase 4 and record the programme transition.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after separate SPEC and QUALITY verdicts. Dual PASS makes phase4-architecture ready; any other result records a bounded correction state and leaves Phase 4 blocked."
  },
  "risk_tags": [
    "critical",
    "read-only-product-review",
    "architecture",
    "ir-contract"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Global constraints",
        "Phase 3: Causal strategy admission",
        "Phase 4: Market truth, numeric validity, and data capability"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
      "sections": [
        "2. Hidden platform layers",
        "3. Strategy definition is not deployment",
        "4. Named secondary instrument roles",
        "5. Dynamic derivative identity",
        "6. Options lifecycle model",
        "7. Position and strategy state",
        "9. V1 acceptance scenarios",
        "10. Non-negotiable product rules"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
      "sections": [
        "1. Node contract required for every first-party node",
        "3. Type 3 derivative/microstructure library",
        "4. Type 1 execution starter pack",
        "5. Type 5 logic, temporal and state pack",
        "6. Custom-node hierarchy",
        "7. Numerical validity",
        "8. Node versioning"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "1. Risk-weighted verification",
        "2. Test rule",
        "6. Implementation sequencing",
        "7. Canonical acceptance scenarios",
        "8. Guard against scope drift"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase3-4-ir-v2-acceptance.md",
      "sections": [
        "acceptance",
        "test_plan",
        "nonclaims",
        "owner_gates"
      ]
    }
  ],
  "preserved_inputs": [
    "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
    "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md"
  ],
  "allowed_paths": [
    ".agent/runs/phase3-4-ir-v2-review",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md"
  ],
  "nonclaims": [
    "This architecture gate does not implement or enable Component IR v2.",
    "IR v2 acceptance does not prove Phase 4 market truth, provider capability, deployment readiness, or live authority."
  ],
  "owner_gates": [
    "Stop before product implementation or any live, deployment, VPS, credential, production-data, destructive, or frontend action."
  ],
  "stop_conditions": [
    "The review package or source-coverage evidence is absent, stale, or incomplete.",
    "Either preserved IR document remains ambiguous or conflicts with accepted Phase 3 or an owner steer."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Product code remains read-only.",
    "The review verifies all mapped IR v2 source coverage and accepted dependency boundaries.",
    "Separate SPEC and QUALITY verdicts are explicit.",
    "Phase 4 advances only on dual PASS."
  ],
  "test_plan": [
    "Verify package fingerprint and evidence hashes.",
    "Inspect both preserved IR documents and their coverage matrix.",
    "Return separate SPEC and QUALITY verdicts."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase3_4_ir_v2_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-acceptance.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase3-4-ir-v2-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Component IR v2 Sol-high review goal

This capsule remains blocked until its declared dependency has dual passing verdicts.
