---
{
  "id": "phase4-final-review-2",
  "phase": "phase4",
  "status": "blocked",
  "superseded_by": "phase4-final-review-3",
  "review_iteration": 3,
  "goal": "Independently accept or reject the complete Phase 4 implementation after the owner-authorized recovery, with particular emphasis on sole admission authority, durable reconstruction, causality, immutable market truth, cache identity, and exact evidence quality.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "On 2026-08-17 the owner explicitly authorized one new recovery capsule and this new independent final-review stage so Phase 4 can be completed without opening Phase 5 or any live boundary.",
    "stopping_condition": "Complete only after one fresh read-only critical reviewer verifies the exact official package and whole Phase 4 lineage, independently challenges every first-review and recheck finding including the real loader and both persistence planes, and writes separate SPEC and QUALITY verdicts. Only dual PASS accepts Phase 4; any other verdict keeps Phase 4 and every downstream boundary blocked and requires a new bounded replan."
  },
  "risk_tags": [
    "critical",
    "phase-wide-review",
    "research-integrity",
    "market-truth",
    "causality",
    "admission-authority",
    "durable-reconstruction",
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
    ".agent/runs/phase4-review/recheck-verdict.json",
    ".agent/runs/phase4-review-correction",
    ".agent/runs/phase4-review-recovery",
    "paper-trader/docs/reports/phase4-implementation.md",
    ".agent/review-package.json"
  ],
  "dependency_gate": "phase4-review-recovery",
  "allowed_paths": [
    ".agent/runs/phase4-final-review-2/verdict.json"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "Dual PASS accepts only the exact reviewed local Phase 4 implementation and locally runnable evidence. It does not accept Phase 5, frontend, provider breadth/acquisition, deployment, credentials, production data/use, capacity, money authority, authoritative live IR, or release deployability.",
    "The reviewer performs no product, test, migration, report, package, capsule, programme, or retained-evidence correction and does not overwrite either failed verdict.",
    "Local scenarios, PostgreSQL harnesses, and persistence roundtrips do not prove real feeds, execution behavior, production migrations, service topology, provider conformance, or production rehearsal."
  ],
  "owner_gates": [
    "Stop before any edit outside the sole verdict path and before deployment, credentials, production data/use, destructive work, Phase 5, frontend, provider, live, or money action."
  ],
  "stop_conditions": [
    "The official package, exact HEAD/base, complete dirty fingerprint, scoped hashes, evidence hashes, failed-verdict hashes, recovery lineage, protected hashes, frontend exclusion, programme state, or diff check is stale or inconsistent.",
    "Any first-review or failed-recheck counterexample succeeds; a legitimate persisted receipt cannot traverse the actual loader; a forged lookalike writes to either plane; any changed guard lacks a killed/restored mutation; or the report overclaims coverage.",
    "A correction is required. Record FAIL and stop; reviewers never repair the reviewed tree."
  ],
  "deployment_impact": {
    "classification": "read-only-phase-wide-review-of-compatible-phase4-runtime-and-persistence-hardening",
    "required_evidence": "Verify exact local behavior, unchanged schema/service/config/dependency and migration heads, protected boundaries, frontend exclusion, deployability ledger, and explicit production/release nonclaims. Do not infer deployment readiness."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Package lineage, exact HEAD/base, complete dirty-tree fingerprint, all scoped hashes, all evidence hashes, both immutable failed-verdict hashes, recovery manifests, protected hashes, frontend exclusion, programme state, and diff check verify before substantive review.",
    "The reviewer independently replays the critical Phase 4 refusal surface: numeric immutability; complete physical/selector identity; immutable knowledge-cutoff market truth; canonical capability assessment; complete dataset/result/cache identity; real durable wrapper reconstruction; and sole constructor-authorized writes in both persistence planes.",
    "A legitimate constructor-produced receipt is serialized to canonical JSON, stored, loaded in a fresh reconstruction path, verified against the current registry and graph version, and consumed through load_verified_admission without monkeypatching that loader.",
    "A structurally self-consistent lookalike with only capability_assessment_address replaced and the outer address recomputed is rejected by execution put and research store_admission. Exact legitimate writes/retries and durable read verification remain valid.",
    "The reviewer verifies the recovery regressions, the retained 139-test correction selector, all changed killed/restored mutations, focused Phase 4 compatibility, migration heads 0036/0007, protected hashes, frontend no-diff, report accuracy, and deployability boundary without running a broad suite merely for confidence.",
    "The three architecture scenarios and refusal chain remain substantively distinct and make no provider, selector-resolution, execution, production, or release claim they do not exercise.",
    "Separate SPEC and QUALITY verdicts are explicit. Only dual PASS accepts Phase 4 and allows the root coordinator to make Phase 5 architecture ready but unstarted."
  ],
  "test_plan": [
    "Verify the official package and immutable first/recheck verdicts before relying on any correction claim.",
    "Run reviewer-authored counterexamples for the two recovered defects and representative counterexamples for every original critical domain, then run the exact focused Phase 4 selectors needed to test the integrated product. Do not run a broad confidence suite.",
    "Inspect mutation commands and byte restoration, actual non-mocked loader coverage, both write seams, migration heads, protected hashes, frontend exclusion, report/nonclaims, and every command's declared cwd.",
    "Write only the final verdict JSON with separate SPEC and QUALITY results, exact evidence references, residual risks, and the precise downstream recommendation."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase4_final_review_2",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/validity.py",
      "paper-trader/backend/app/market_truth/identity.py",
      "paper-trader/backend/app/market_truth/rulebook.py",
      "paper-trader/backend/app/market_data/requirements.py",
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/market_data/observations.py",
      "paper-trader/backend/app/market_data/candles.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/app/backtest/dataset_store.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/tests/test_ir_numeric_validity.py",
      "paper-trader/backend/tests/test_market_truth_domain.py",
      "paper-trader/backend/tests/test_phase4_data_requirement_registry.py",
      "paper-trader/backend/tests/test_phase4_data_capability.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py",
      "paper-trader/backend/tests/test_phase4_dataset_manifest.py",
      "paper-trader/backend/tests/test_phase4_alignment_causality.py",
      "paper-trader/backend/tests/test_phase4_cache_identity.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_phase4_acceptance_scenarios.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/tasks/phase4-review.md",
      "paper-trader/docs/agent/tasks/phase4-review-correction.md",
      "paper-trader/docs/agent/tasks/phase4-review-recheck.md",
      "paper-trader/docs/agent/tasks/phase4-review-recovery.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-2.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      "AGENTS.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "first_output": ".agent/runs/phase4-review/verdict.json",
    "failed_recheck_output": ".agent/runs/phase4-review/recheck-verdict.json",
    "output": ".agent/runs/phase4-final-review-2/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
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

# Phase 4 independent final review

This is a fresh phase-wide review after the owner-authorized recovery, not another recheck in the exhausted first-review lineage. One read-only Sol-high critical reviewer verifies the exact package, directly attacks every material Phase 4 boundary, and writes only the verdict. Dual PASS accepts the local Phase 4 implementation; every later and live boundary remains separately gated.

This review never became ready because `phase4-review-recovery` stopped at its declared architecture boundary. It is superseded by `phase4-final-review-3`, which reviews the additive v2 graph persistence and explicit non-executable runtime boundary. No verdict exists for this capsule.
