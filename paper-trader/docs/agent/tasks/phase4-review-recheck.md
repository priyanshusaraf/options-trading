---
{
  "id": "phase4-review-recheck",
  "phase": "phase4",
  "status": "blocked",
  "review_iteration": 2,
  "goal": "Independently accept or reject the corrected Phase 4 implementation in the single permitted focused recheck, preserving the immutable first FAIL and opening no Phase 5, frontend, provider, deployment, credential, production, capacity, money, or live-authority boundary.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner's active durable Phase 4 goal and the first review authorize exactly one bounded correction followed by this one focused recheck.",
    "stopping_condition": "Complete only after one fresh read-only Sol-high critical reviewer verifies the regenerated exact package, directly challenges all eight first-review findings, and writes separate SPEC and QUALITY verdicts to the recheck output. Dual PASS accepts only bounded Phase 4 implementation; any other result exhausts the route and leaves Phase 4 and every later boundary blocked."
  },
  "risk_tags": [
    "critical",
    "focused-recheck",
    "research-integrity",
    "market-truth",
    "causality",
    "capability-authority",
    "cache-identity",
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
    ".agent/runs/phase4-review/verdict.json",
    ".agent/runs/phase4-review-correction",
    "paper-trader/docs/reports/phase4-implementation.md",
    ".agent/review-package.json"
  ],
  "output": ".agent/runs/phase4-review/recheck-verdict.json",
  "output_sha256": "904138b12d46f9d2d484661ea0b4307eef46bf6eef7ae293c6531aa8a26d969d",
  "final_verdict": {
    "SPEC": "FAIL",
    "QUALITY": "FAIL",
    "overall": "FAIL",
    "rechecks_remaining": 0
  },
  "dependency_gate": "phase4-review-correction",
  "allowed_paths": [
    ".agent/runs/phase4-review/recheck-verdict.json",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "Dual PASS accepts only the exact reviewed Phase 4 local implementation. It does not accept Phase 5, frontend, provider breadth or acquisition, deployment, credentials, production data/use, capacity, money authority, live IR, or release deployability.",
    "The reviewer performs no product, test, migration, package, report, programme, or retained-evidence correction and never overwrites the immutable first verdict.",
    "Composed scenario tests prove only their exact local contracts; they do not prove real feeds, execution, entry/exit authority, production migrations, or release rehearsal."
  ],
  "owner_gates": [
    "Stop before any product, test, migration, package, report, frontend, provider, programme, or retained-evidence edit and before deployment, credentials, production data/use, destructive work, Phase 5, or live/money action."
  ],
  "stop_conditions": [
    "The official package, exact HEAD/base, complete dirty fingerprint, scoped hashes, evidence hashes, first-verdict hash, correction lineage, protected hashes, frontend exclusion, programme, or capsule state is stale or inconsistent.",
    "Any of the eight first-review counterexamples still succeeds, any required mutation survives, the real Phase 4 sweep/cache path can omit binding or reuse legacy identity, or the three scenarios remain nominal.",
    "A fix is required; record FAIL and stop because this is the final permitted review iteration."
  ],
  "deployment_impact": {
    "classification": "read-only-focused-review-of-compatible-phase4-hardening",
    "required_evidence": "Verify the no-schema/no-service correction classification, runtime/cache replay compatibility, exact locally runnable evidence, protected boundaries, and explicit production/release nonclaims without inferring deployability."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Package lineage, exact HEAD/base, complete dirty-tree fingerprint, every scoped-file hash, every retained-evidence hash, first failed-verdict hash, correction manifest, protected hash, frontend exclusion, programme state, and diff check verify before substantive review.",
    "P4-SPEC-001 through P4-SPEC-005 are independently challenged with caller mutation, incomplete/invented derivative identity, provider-selector aliases, snapshot mutation, and future-recorded correction cases; every case fails closed while valid compatibility remains.",
    "P4-SPEC-006 is independently challenged through direct construction, dataclasses.replace, arbitrary copied SATISFIED rows, mismatched profile/evidence/plan/owner/mode/time facts, and persisted-wrapper reconstruction; only canonical assessed evidence is admitted.",
    "P4-SPEC-007 is independently exercised through the actual enqueue/reclaim/worker/sweep/result/cache path: the binding comes only from a freshly verified Phase 4 receipt, survives restart, is mandatory before provider/cache access, changes identity for every answer-changing address, preserves owner isolation, and cannot reuse incomplete legacy rows. V1 and non-opted-v2 compatibility remains intact.",
    "P4-QUALITY-001 is closed by three substantively distinct composed fixtures with the exact claimed equity, weekly-option, and cross-market facts/refusals; every unimplemented provider, selector-resolution, entry/exit, production, and release behavior remains an explicit nonclaim.",
    "The reviewer verifies every named correction regression and killed/restored mutation, focused affected tests, unchanged migration heads 0036/0007, protected hashes, frontend no-diff, report accuracy, and deployability boundary.",
    "Separate SPEC and QUALITY verdicts are explicit. Only dual PASS closes Phase 4; any other result exhausts the route."
  ],
  "test_plan": [
    "Verify the official package and immutable first verdict before reading correction claims.",
    "Run only the eight bounded counterexamples, high-value real-path cache selectors, substantive scenario selectors, and focused affected compatibility needed to challenge the correction. Do not run a broad confidence suite.",
    "Inspect mutation commands and restoration hashes, migration heads, protected hashes, frontend exclusion, report/nonclaims, and exact per-command cwd attribution.",
    "Write only the focused recheck verdict JSON with separate SPEC and QUALITY results and exact evidence references."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase4_review_recheck",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/validity.py",
      "paper-trader/backend/app/market_truth/identity.py",
      "paper-trader/backend/app/market_truth/rulebook.py",
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/tests/test_ir_numeric_validity.py",
      "paper-trader/backend/tests/test_market_truth_domain.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py",
      "paper-trader/backend/tests/test_phase4_cache_identity.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_phase4_acceptance_scenarios.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/tasks/phase4-review.md",
      "paper-trader/docs/agent/tasks/phase4-review-correction.md",
      "paper-trader/docs/agent/tasks/phase4-review-recheck.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      "AGENTS.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "first_output": ".agent/runs/phase4-review/verdict.json",
    "output": ".agent/runs/phase4-review/recheck-verdict.json",
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

# Phase 4 focused final recheck

The sole focused read-only Sol-high recheck completed with SPEC FAIL and QUALITY FAIL at `.agent/runs/phase4-review/recheck-verdict.json` (SHA-256 `904138b12d46f9d2d484661ea0b4307eef46bf6eef7ae293c6531aa8a26d969d`). Package preconditions passed, but canonical durable reconstruction and capability-assessment authority remain broken. No further correction or recheck is authorized in this lineage, so Phase 4 and all downstream gates remain blocked.
