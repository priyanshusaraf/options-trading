---
{
  "id": "phase4-review",
  "phase": "phase4",
  "status": "blocked",
  "review_iteration": 1,
  "goal": "Independently accept or reject the complete Phase 4 implementation with separate SPEC and QUALITY verdicts against the frozen architecture, source coverage, capsule evidence, protected boundaries, and deployment nonclaims.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after one fresh Sol-high critical reviewer inspects the exact integrated package and returns separate SPEC and QUALITY verdicts. Dual PASS accepts only bounded Phase 4 implementation; any other result permits at most one focused recheck after a separately authorized bounded correction and leaves Phase 5 blocked."
  },
  "risk_tags": [
    "critical",
    "phase-review",
    "research-integrity",
    "market-truth",
    "causality",
    "tenancy",
    "migration",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "3. One accepted executable architecture",
        "4. Closed numeric validity contract",
        "5. Canonical instrument and market-truth model",
        "6. Data observations, alignment, and causality",
        "7. Data requirement and provider capability contracts",
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract",
        "12. Deferred homes and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "4. Capsule outcomes and failure hypotheses",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership",
        "V1 release gate"
      ]
    }
  ],
  "input_evidence": [
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/reports/phase4-implementation.md",
    ".agent/review-package.json",
    ".agent/runs/phase4-numeric-validity-contract",
    ".agent/runs/phase4-market-truth-domain",
    ".agent/runs/phase4-market-truth-persistence",
    ".agent/runs/phase4-data-requirement-registry-correction",
    ".agent/runs/phase4-data-contract-capability",
    ".agent/runs/phase4-dataset-causality",
    ".agent/runs/phase4-integration-gate"
  ],
  "first_output": ".agent/runs/phase4-review/verdict.json",
  "first_output_sha256": "ce6ed8c4d8a0a0fd0c93984c1c195d70704ce5ac7cc109fedd06df466ba61a7a",
  "first_verdict": {
    "SPEC": "FAIL",
    "QUALITY": "FAIL",
    "overall": "FAIL",
    "rechecks_remaining": 0,
    "correction_stage": "phase4-review-correction",
    "recheck_stage": "phase4-review-recheck"
  },
  "dependency_gate": "phase4-implementation",
  "allowed_paths": [
    ".agent/runs/phase4-review",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "Dual PASS accepts only the reviewed Phase 4 implementation. It does not accept Phase 5, provider breadth, frontend, capacity, production readiness, production rehearsal, deployment, credentials, live authority, or release deployability.",
    "The reviewer performs no product, test, migration, package, or retained-evidence correction."
  ],
  "owner_gates": [
    "Stop before any product, test, migration, frontend, provider, package, or retained-evidence edit and before deployment, credentials, production data/use, destructive work, or Phase 5 action."
  ],
  "stop_conditions": [
    "The review package, source coverage, integrated report, evidence hashes, dirty fingerprint, protected hashes, exact HEAD, or capsule lineage is stale or inconsistent.",
    "Any realistic validity, point-in-time truth, causality, capability, cache, tenancy, migration, or authority counterexample succeeds.",
    "A fix is required; record FAIL and stop because review is read-only."
  ],
  "deployment_impact": {
    "classification": "read-only-review-of-phase4",
    "affected_dimensions": [
      "Review evidence",
      "Deployability ledger"
    ],
    "required_evidence": "Reject deployment claims unless every affected local dimension has direct evidence and every open production dimension names its exact later capsule. No deployment or readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The exact review package matches HEAD, reviewed paths, evidence hashes, dirty snapshot, and protected hashes.",
    "Every source-map entry and frozen design invariant has implementation or explicit nonclaim evidence.",
    "Critical scenarios, registry closure and identity chain, leaf/compound provenance, exact base-v2-to-Phase-4 admission wrapping, single artifact authority, two-plane identical-byte persistence, compatibility, refusals, two-plane migrations, prefix parity, cache correction, owner isolation, secret exclusion, and killed mutations have reproducible evidence.",
    "SPEC and QUALITY are assessed separately; dual PASS accepts only Phase 4."
  ],
  "test_plan": [
    "Reproduce the package's focused Phase 4, affected regression, migration, structured, protected-hash, import, and diff checks.",
    "Probe realistic counterexamples at numeric validity, registry/declaration/plan identity, compound binding, base-receipt/wrapper admission identity, constructor authority, execution/research persistence equivalence, historical identity, alignment, capability, cache, tenancy, migration, and authority boundaries.",
    "Verify deployment claims against DEPLOYABILITY.md and exact future capsule ownership."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase4_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/app/market_truth",
      "paper-trader/backend/app/market_data",
      "paper-trader/backend/app/backtest",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/migrations/versions/20260817_0036_phase4_market_truth.py",
      "paper-trader/backend/tests/test_phase4_acceptance_scenarios.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/reports/phase4-source-coverage.json"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 independent review

The immutable first independent review returned SPEC FAIL and QUALITY FAIL. Its verdict remains at `.agent/runs/phase4-review/verdict.json`. The bounded correction passed root audit at correction-evidence scope only, but the sole focused recheck also returned SPEC FAIL and QUALITY FAIL at `.agent/runs/phase4-review/recheck-verdict.json` (SHA-256 `904138b12d46f9d2d484661ea0b4307eef46bf6eef7ae293c6531aa8a26d969d`). The permitted route is exhausted; Phase 4 remains blocked pending a new owner-authorized recovery capsule and independent final-review stage.
