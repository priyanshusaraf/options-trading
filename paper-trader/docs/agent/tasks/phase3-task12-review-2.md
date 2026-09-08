---
{
  "id": "phase3-task12-review-2",
  "phase": "phase3-causal-strategy-admission",
  "status": "ready",
  "goal": "Independently accept or reject corrected Phase 3 Task 12 using the final integrated diff and current evidence, then record the next programme state.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after separate final SPEC and QUALITY verdicts are written. On dual PASS, mark this stage accepted and make phase3-4-ir-v2-acceptance ready; on any FAIL or UNVERIFIABLE, record a bounded Terra correction stage without advancing."
  },
  "risk_tags": [
    "critical",
    "read-only-product-review",
    "money-path",
    "research-integrity",
    "migrations"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Proven foundations",
        "Open obligations",
        "V1 release gate"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase3-task12-correction-1.md",
      "sections": [
        "acceptance",
        "test_plan",
        "nonclaims",
        "owner_gates"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
      "sections": [
        "8. Trust is a product requirement",
        "10. Non-negotiable product rules"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
      "sections": [
        "3. Position sizing hierarchy",
        "4. Multi-strategy position ownership",
        "5. Open-position version ownership",
        "6. Protection semantics",
        "7. Order semantics"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "1. Risk-weighted verification",
        "2. Test rule",
        "3. Test cadence"
      ]
    }
  ],
  "allowed_paths": [
    ".agent/runs/phase3-task12-review-2",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md"
  ],
  "nonclaims": [
    "A passing Phase 3 review does not prove Component IR v2, market truth, numeric validity, provider capability, resource fit, Strategy Preflight, or production readiness.",
    "This review grants no live, deployment, VPS, credential, production-data, or frontend authority."
  ],
  "owner_gates": [
    "Stop before any product implementation.",
    "Stop before live authority, live credentials, VPS, production data, deployment, destructive operations, or frontend work."
  ],
  "stop_conditions": [
    "The review package is absent, stale, incomplete, or does not bind the exact integrated dirty tree and named evidence.",
    "Any required evidence is failed, timed out, skipped, empty, stale, or unverifiable.",
    "The requested decision would require reading excluded Component IR v2 files."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The review records Phase 3's deployment-impact level, rejects any production-readiness overclaim, and leaves each remaining deployment obligation with an exact phase or release owner.",
    "The review package fingerprint matches the current complete dirty tree and its evidence hashes verify.",
    "Every correction acceptance claim has direct current evidence.",
    "Separate SPEC and QUALITY verdicts are explicit and supported by findings.",
    "Product code remains read-only during this goal.",
    "The programme advances only on dual PASS; otherwise it records correction state."
  ],
  "test_plan": [
    "Verify review-package fingerprint and evidence hashes.",
    "Inspect the complete integrated diff against the capsule and mapped owner-steer sections.",
    "Confirm required focused, mutation, PostgreSQL, broad, integrity, and protected-file evidence.",
    "Return separate SPEC and QUALITY verdicts."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase3_task12_review_2",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader"
    ],
    "exclude_paths": [
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md"
    ],
    "output": ".agent/runs/phase3-task12-review-2/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Phase 3 Task 12 Sol-high review goal

This goal is read-only for product code. Writing the verdict and the minimal programme transition is allowed. Do not repair findings in this task.
