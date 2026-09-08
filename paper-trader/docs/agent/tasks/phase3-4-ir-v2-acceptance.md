---
{
  "id": "phase3-4-ir-v2-acceptance",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Reconcile the preserved Component IR v2 plan and design with accepted Phase 3 and all six owner steers, then produce an implementable accepted or rejected interphase contract before Phase 4.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the preserved IR v2 design and plan are audited, reconciled, validated, and packaged for a separate Sol-high review. Do not implement IR v2 product code or unlock Phase 4."
  },
  "risk_tags": [
    "critical",
    "architecture",
    "ir-contract",
    "interphase-gate"
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
    }
  ],
  "preserved_inputs": [
    "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
    "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md"
  ],
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
    "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
    "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-acceptance.md",
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-acceptance",
    ".agent/review-package.json"
  ],
  "nonclaims": [
    "This architecture gate does not implement or enable Component IR v2.",
    "IR v2 acceptance does not prove Phase 4 market truth, provider capability, deployment readiness, or live authority."
  ],
  "owner_gates": [
    "Stop before product implementation, live authority, deployment, VPS, credentials, production data, destructive work, or frontend implementation.",
    "Stop if the preserved inputs are missing or their provenance cannot be established."
  ],
  "stop_conditions": [
    "Phase 3 does not have dual passing SPEC and QUALITY verdicts.",
    "The proposed IR creates a second executable identity, strategy language, provider identity, deployment authority, or research ledger.",
    "A core conflict with an owner steer remains unresolved."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The two preserved documents are accounted for without loading them during Phase 3 correction.",
    "The contract preserves one typed immutable IR, canonical identity, exact ports/types/validity, and strategy/deployment separation.",
    "Every mapped owner-steer section has an explicit coverage row or conflict disposition.",
    "Implementation tasks are dependency-ordered, bounded, testable, and do not begin Phase 4 early.",
    "A current review package and separate phase3-4-ir-v2-review capsule are ready."
  ],
  "test_plan": [
    "Parse all structured examples and validate every referenced path.",
    "Check section-level coverage against SOURCE_MAP.json phase view ir_v2.",
    "Check for duplicate IR/identity/authority abstractions and future-phase leakage.",
    "Run architecture validator and git diff --check."
  ],
  "review": {
    "required": true,
    "separate_goal": "phase3-4-ir-v2-review",
    "assignment_id": "phase3_4_ir_v2_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-acceptance.md",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-acceptance.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-review.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-dispatch-compatibility.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-schema-topology.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-resolution-runtime.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-admission-persistence.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-api-contract.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-integration-gate.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-implementation-review.md",
      "paper-trader/docs/agent/tasks/phase4-architecture.md",
      "paper-trader/docs/agent/tasks/phase3-task12-correction-2.md",
      "paper-trader/docs/agent/tasks/post-phase3-postgresql-harness.md"
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

# Component IR v2 interphase architecture goal

The architecture owner completed this capsule without product implementation. Its evidence-backed package routes to the separate phase3-4-ir-v2-review goal; only that review's dual PASS can unlock the first implementation capsule.
