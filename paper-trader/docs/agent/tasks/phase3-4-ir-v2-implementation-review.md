---
{
  "id": "phase3-4-ir-v2-implementation-review",
  "phase": "component-ir-v2-interphase",
  "status": "ready",
  "goal": "Independently accept or reject the complete bounded Component IR v2 implementation and determine whether Phase 4 architecture may begin.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after one read-only critical reviewer verifies package lineage and returns separate SPEC and QUALITY verdicts. Dual PASS makes phase4-architecture ready; any other result records one bounded correction route and leaves Phase 4 blocked."
  },
  "risk_tags": ["critical", "read-only-product-review", "identity", "research-integrity", "migrations", "authority"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["1. Decision", "4. One public architecture", "8. Edge and binding contract", "10. Compound components", "12. Evaluation", "13. Serialization and identity", "14. Admission and persistence", "20. Acceptance conditions"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["3. Accepted baseline", "5. Scope boundaries", "7. Migration and compatibility", "10.7 phase3-4-ir-v2-implementation-review", "11. Tests and evidence", "14. Stop and owner gates", "15. Required nonclaims", "16. Final gate"]
    }
  ],
  "input_evidence": [
    "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-implementation.md",
    ".agent/runs/phase3-4-ir-v2-integration-gate",
    ".agent/review-package.json"
  ],
  "allowed_paths": [
    ".agent/runs/phase3-4-ir-v2-implementation-review",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md"
  ],
  "product_paths_read_only": ["paper-trader/backend", "paper-trader/frontend"],
  "nonclaims": [
    "Dual PASS accepts only the reviewed Component IR v2 implementation and does not prove production readiness, frontend v2 authoring, Phase 4 implementation, provider capability, deployment, or live authority.",
    "The reviewer performs no product-code correction."
  ],
  "owner_gates": [
    "Stop before any product edit, frontend action, deployment, live authority, VPS, credential, production-data, or destructive action."
  ],
  "stop_conditions": [
    "The official package, fingerprint, scoped hashes, evidence hashes, or dirty-snapshot binding is stale, absent, or inconsistent.",
    "Required PostgreSQL, killed-mutation, v1 compatibility, or deployability-impact evidence is missing.",
    "A core contract conflict cannot be resolved by one bounded correction."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Package lineage and every evidence hash verify before substantive claims.",
    "The review challenges single-stack architecture, v1 compatibility, exact types and bindings, canonical identity, resolver/evaluator independence, compound closure, admission authority, migration safety, API atomicity, and frontend exclusion.",
    "Separate SPEC and QUALITY verdicts are explicit.",
    "Phase 4 architecture advances only on dual PASS."
  ],
  "test_plan": [
    "Verify the official package, fingerprint, scope, and evidence hashes.",
    "Inspect the integrated diff and replay only high-value named commands if needed.",
    "Return separate SPEC and QUALITY verdicts with exact evidence references."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase3_4_ir_v2_implementation_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/db",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/editor",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/tests",
      "paper-trader/backend/research_tests",
      "paper-trader/docs"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase3-4-ir-v2-implementation-review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  }
}
---

# IR v2 independent implementation review

This is one read-only Sol-high review after package creation. No reviewer swarm and no product edits.
