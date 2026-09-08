---
{
  "id": "phase3-4-ir-v2-review",
  "phase": "component-ir-v2-interphase",
  "status": "ready",
  "goal": "Independently accept or reject the reconciled Component IR v2 contract before Phase 4 and record the programme transition.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after separate SPEC and QUALITY verdicts. Dual PASS makes phase3-4-ir-v2-dispatch-compatibility ready; any other result records a bounded correction state and leaves all IR v2 implementation and Phase 4 blocked."
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
  "bounded_correction": {
    "maximum_iterations": 1,
    "iteration_used": 1,
    "owner": "phase3-4-ir-v2-acceptance architecture owner",
    "reviewer_remains_read_only": true,
    "findings_addressed": [
      "IRV2-REVIEW-001",
      "IRV2-REVIEW-002",
      "IRV2-REVIEW-003"
    ],
    "correction_paths": [
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-acceptance.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-schema-topology.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-resolution-runtime.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-admission-persistence.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-api-contract.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-integration-gate.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-review.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md"
    ],
    "first_verdict": ".agent/runs/phase3-4-ir-v2-review/verdict.json",
    "focused_recheck_output": ".agent/runs/phase3-4-ir-v2-review/recheck-verdict.json"
  },
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
    "The first IR v2 implementation capsule advances only on dual PASS; Phase 4 remains blocked until the later implementation review."
  ],
  "test_plan": [
    "Verify package fingerprint and evidence hashes.",
    "Inspect both preserved IR documents and their coverage matrix.",
    "Verify the one bounded correction closes exact compound parameter binding and canonical complete-document identity without weakening v1, admission, or Phase 4 boundaries.",
    "Verify the snapshot comparison and explicit owner disposition preserve the unresolved 16-path attribution limit rather than converting it into product-code evidence.",
    "Return separate SPEC and QUALITY verdicts; the focused recheck writes a separate output and does not erase the first verdict."
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
    "focused_recheck_output": ".agent/runs/phase3-4-ir-v2-review/recheck-verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Component IR v2 Sol-high review goal

Iteration 1 returned `SPEC: FAIL` and `QUALITY: FAIL`. The architecture owner used the single permitted bounded correction to close the two contract ambiguities and record the unresolved dirty-tree attribution limit. The same reviewer now performs one focused recheck against a regenerated package and writes `recheck-verdict.json` without replacing the first verdict.

The reviewer stays read-only over product and architecture files. Dual PASS unlocks only the first IR v2 implementation capsule, not Phase 4.
