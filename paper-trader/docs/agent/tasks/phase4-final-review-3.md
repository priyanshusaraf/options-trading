---
{
  "id": "phase4-final-review-3",
  "phase": "phase4",
  "status": "active",
  "review_iteration": 4,
  "goal": "Independently accept or reject the complete Phase 4 implementation after the durable v2 graph integration, testing the whole Phase 4 contract and the corrected non-executable v2 runtime boundary against the exact final tree.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "On 2026-08-17 the owner authorized all bounded correction and independent-review work needed to finish Phase 4, an implementation-owner-independent Sol-high defect-pattern check, and a separate post-Phase-4 Sol-high foundation audit at the repository maximum. This fresh phase-wide review replaces the superseded phase4-final-review-2 stage and retains every downstream safety block.",
    "stopping_condition": "Complete only after one fresh read-only critical reviewer verifies the exact official package and complete Phase 4 lineage, independently attacks every original and later finding, directly verifies the complete typed authority chain and all forward migrations through execution 0039 and research 0010, proves legitimate restart reconstruction and forged-fact rejection, proves the stable v2 runtime refusal occurs only after full verification and before every provider/cache/worker/money surface, and writes separate SPEC and QUALITY verdicts. Only dual PASS accepts Phase 4; any other verdict keeps Phase 4 and every downstream boundary blocked."
  },
  "risk_tags": [
    "critical",
    "phase-wide-review",
    "schema",
    "migration",
    "ir-v2-identity",
    "research-integrity",
    "market-truth",
    "causality",
    "admission-authority",
    "runtime-refusal",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "2. Existing architecture verdicts",
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
        "1. Scope and stopping rule",
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
        "Phase 5 ownership",
        "V1 release gate"
      ]
    }
  ],
  "input_evidence": [
    ".agent/runs/phase4-review/verdict.json",
    ".agent/runs/phase4-review/recheck-verdict.json",
    ".agent/runs/phase4-review-correction",
    ".agent/runs/phase4-review-recovery",
    ".agent/runs/phase4-v2-durable-graph-integration",
    ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/report.md",
    ".agent/runs/phase4-authority-foundation-architecture-correction",
    ".agent/runs/phase4-resolved-topology-identity-correction",
    ".agent/runs/phase4-canonical-market-identity-correction",
    ".agent/runs/phase4-typed-market-authority-correction",
    ".agent/runs/phase4-dataset-assessment-authority-correction",
    ".agent/runs/phase4-capability-assessment-receipt-correction",
    ".agent/runs/phase4-authority-timestamp-normalization-correction",
    ".agent/runs/phase4-research-json-shape-parity-correction",
    ".agent/runs/phase4-authority-integration-gate",
    "paper-trader/docs/reports/phase4-implementation.md",
    ".agent/review-package.json"
  ],
  "dependency_gate": "phase4-authority-integration-gate",
  "allowed_paths": [
    ".agent/runs/phase4-final-review-3/verdict.json"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "Dual PASS accepts only the exact reviewed local Phase 4 contracts and their explicit non-executable v2 runtime boundary. It does not accept Phase 5 implementation, frontend, providers, deployment, credentials, production data/use, capacity, money authority, authoritative live IR, or release deployability.",
    "The reviewer writes only its verdict and never repairs product, tests, migrations, reports, packages, capsules, programme state, or retained evidence. All earlier failed verdicts and stopped-recovery evidence remain immutable.",
    "Local SQLite/PostgreSQL migration, persistence, restart, and scenario evidence does not prove a production migration, feed, execution behavior, service topology, capacity, release rehearsal, or production readiness."
  ],
  "owner_gates": [
    "Stop before any edit outside the sole verdict path and before deployment, credentials, production data/use, destructive work, Phase 5 implementation, frontend, provider, live, or money action."
  ],
  "stop_conditions": [
    "The official package, exact HEAD/base, complete dirty fingerprint, scoped hashes, evidence hashes, historical verdict/recovery hashes, migration heads, protected hashes, frontend exclusion, programme state, or diff check is stale or inconsistent.",
    "Any original review counterexample, forged receipt/assessment/graph case, collision, owner-isolation case, legitimate restart reconstruction, migration gate, v1 compatibility case, or provider/cache/worker non-reachability test contradicts the implementation or report.",
    "A v2 graph is stored in or read through legacy GraphVersion, a Phase 4 graph executes through IRGraphStrategy, the global registry gains fixture/placeholder v2 components, or V2_RUNTIME_UNAVAILABLE occurs before complete durable verification.",
    "A correction is required. Record FAIL and stop; reviewers never repair the reviewed tree."
  ],
  "deployment_impact": {
    "classification": "read-only-phase-wide-review-of-additive-v2-graph-persistence-and-fail-closed-runtime",
    "required_evidence": "Verify execution head 0039 and research head 0010; fresh/upgrade/restart integrity on the declared dialects; unchanged v1 schema/bytes/readers; exact local graph/receipt/assessment/market/dataset authority behavior; protected boundaries; frontend exclusion; deployability ledger; and explicit production/release nonclaims. Do not infer deployment readiness."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Package lineage, exact HEAD/base, complete dirty-tree fingerprint, scoped hashes, evidence hashes, all immutable failed-verdict and stopped-recovery hashes, integration manifest, protected hashes, frontend exclusion, programme state, and diff check verify before substantive review.",
    "The reviewer independently replays the critical Phase 4 domain surface: immutable finite numeric validity; complete physical/selector identity; immutable knowledge-cutoff market truth; canonical capability assessment; complete dataset/result/cache identity; and substantive equity, weekly-options/order-flow, cross-market, and refusal scenarios.",
    "Execution and research v2 graph records are separate from receipts and legacy GraphVersion, immutable, canonical, owner-scoped, collision-safe, address-complete, and atomically persisted with exact Phase 4 receipts. Direct database and application counterexamples cannot produce a partial or cross-bound row set through supported seams.",
    "A legitimate constructor-produced receipt and complete assessment survive canonical JSON, both plane-local stores, session/process restart, registry and plan reconstruction, and actual loader verification without the original in-memory authority token or a monkeypatched loader.",
    "A forged lookalike, changed assessment/address, changed graph document/content/projection/registry address, wrong owner, same-version collision, malformed JSON, and non-canonical bytes fail closed in both relevant planes before any authority is consumed.",
    "The actual execution loader verifies the full Phase 4 chain and then raises exactly V2_RUNTIME_UNAVAILABLE. Enqueue, retry, reclaim, pinned worker, broker/deployment, and cache paths prove no provider construction, cache access, job creation/claim, evaluation, order, money, or live side effect.",
    "Legacy v1 graph publication, GraphVersion rows, admission receipts, load_verified_admission behavior, worker serialization, and result/cache bytes remain unchanged. Non-opted v2 retains its prior fail-closed boundary. No placeholder v2 catalogue, output mapping, or Strategy adapter exists in Phase 4.",
    "Execution migrations through 0039 and research migrations through 0010 pass exact fresh, supported-upgrade, restart, model/metadata parity, constraint/index, immutability, collision, and disposable PostgreSQL 16 evidence. The ledger assigns production migration/rehearsal work precisely and makes no release claim.",
    "The reviewer validates every changed killed/restored mutation, focused final-tree selector, command cwd/exit attribution, report claim, migration head, protected hash, and package evidence hash without running a broad suite merely for confidence.",
    "The independent Sol-high pattern-check report is bound to its intake and final reviewed fingerprints, reconstructs the original contradiction without relying on the implementation owner, explains the prior review miss, and supplies exact defect assets plus a transitive evidence-invalidation map. Every Critical finding is closed with direct real-path evidence before this review; every invalidated dependent contract, test, report, and verdict is revalidated or remains explicitly STALE/REQUIRES RECHECK.",
    "Separate SPEC and QUALITY verdicts are explicit. Only dual PASS accepts Phase 4 and allows the root coordinator to mark phase1-4-foundation-audit ready but unstarted. Phase 5 remains blocked until the later read-only Sol-high foundation audit completes and every Critical architecture/invariant finding is closed or the no-Critical closure is recorded; every implementation/live/deployment boundary remains blocked."
  ],
  "test_plan": [
    "Verify the official package, immutable historical verdicts, stopped-recovery evidence, integration manifest, and exact migration heads before relying on any implementation claim.",
    "Write reviewer-owned read-only counterexamples for original Phase 4 domains, two-plane graph/receipt/assessment persistence, restart reconstruction, collisions/tampering/owner isolation, actual loader dispatch, and provider/cache/worker non-reachability; then run only the focused selectors needed to assess the integrated contract.",
    "Inspect migration implementation and targeted SQLite/PostgreSQL evidence, mutation command/exit/restoration records, unchanged v1 bytes and readers, global registry contents, Phase 5 obligation assignment, report/nonclaims, and every command's declared cwd.",
    "Write only the final verdict JSON with separate SPEC and QUALITY results, exact evidence references, residual risks, and the precise downstream recommendation."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase4_final_review_3",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/validity.py",
      "paper-trader/backend/app/ir/v2_graph_versions.py",
      "paper-trader/backend/app/market_truth/identity.py",
      "paper-trader/backend/app/market_truth/rulebook.py",
      "paper-trader/backend/app/market_truth/authority.py",
      "paper-trader/backend/app/market_truth/temporal.py",
      "paper-trader/backend/app/market_data/requirements.py",
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/market_data/authority.py",
      "paper-trader/backend/app/market_data/dataset_authority.py",
      "paper-trader/backend/app/market_data/observations.py",
      "paper-trader/backend/app/market_data/candles.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/backtest/dataset_store.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/migrations/versions/20260817_0037_ir_v2_graph_versions.py",
      "paper-trader/backend/migrations/versions/20260817_0038_phase4_authority_facts.py",
      "paper-trader/backend/migrations/versions/20260818_0039_phase4_dataset_dependency_authority.py",
      "paper-trader/backend/research/domain/models.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/research/domain/migrate.py",
      "paper-trader/backend/research/domain/migrations/0008_ir_v2_graph_versions.py",
      "paper-trader/backend/research/domain/migrations/0009_phase4_dataset_authority.py",
      "paper-trader/backend/research/domain/migrations/0010_research_json_shape_parity.py",
      "paper-trader/backend/tests/test_ir_numeric_validity.py",
      "paper-trader/backend/tests/test_market_truth_domain.py",
      "paper-trader/backend/tests/test_phase4_data_requirement_registry.py",
      "paper-trader/backend/tests/test_phase4_data_capability.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py",
      "paper-trader/backend/tests/test_phase4_dataset_manifest.py",
      "paper-trader/backend/tests/test_phase4_alignment_causality.py",
      "paper-trader/backend/tests/test_phase4_cache_identity.py",
      "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
      "paper-trader/backend/tests/test_backtest_job_claims.py",
      "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
      "paper-trader/backend/tests/test_schema_migrations.py",
      "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
      "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
      "paper-trader/backend/tests/test_phase4_canonical_market_identity.py",
      "paper-trader/backend/tests/test_phase4_typed_market_authority.py",
      "paper-trader/backend/tests/test_phase4_dataset_dependency_authority.py",
      "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py",
      "paper-trader/backend/tests/test_phase4_authority_execution_migration.py",
      "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
      "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py",
      "paper-trader/backend/tests/test_phase4_authority_integration.py",
      "paper-trader/backend/tests/test_phase4_acceptance_scenarios.py",
      "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/research_tests/test_phase4_v2_receipt_authority.py",
      "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
      "paper-trader/backend/research_tests/test_phase4_research_json_shape_parity.py",
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/tasks/phase4-review.md",
      "paper-trader/docs/agent/tasks/phase4-review-correction.md",
      "paper-trader/docs/agent/tasks/phase4-review-recheck.md",
      "paper-trader/docs/agent/tasks/phase4-review-recovery.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-2.md",
      "paper-trader/docs/agent/tasks/phase4-v2-durable-graph-integration.md",
      "paper-trader/docs/agent/tasks/phase4-authority-foundation-architecture-correction.md",
      "paper-trader/docs/agent/tasks/phase4-resolved-topology-identity-correction.md",
      "paper-trader/docs/agent/tasks/phase4-canonical-market-identity-correction.md",
      "paper-trader/docs/agent/tasks/phase4-typed-market-authority-correction.md",
      "paper-trader/docs/agent/tasks/phase4-dataset-assessment-authority-correction.md",
      "paper-trader/docs/agent/tasks/phase4-capability-assessment-receipt-correction.md",
      "paper-trader/docs/agent/tasks/phase4-authority-timestamp-normalization-correction.md",
      "paper-trader/docs/agent/tasks/phase4-research-json-shape-parity-correction.md",
      "paper-trader/docs/agent/tasks/phase4-authority-integration-gate.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-3.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-audit.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
      "paper-trader/docs/agent/tasks/phase5-architecture.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      "AGENTS.md",
      ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/report.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "first_output": ".agent/runs/phase4-review/verdict.json",
    "failed_recheck_output": ".agent/runs/phase4-review/recheck-verdict.json",
    "stopped_recovery_output": ".agent/runs/phase4-review-recovery/owner_integration/report.md",
    "output": ".agent/runs/phase4-final-review-3/verdict.json",
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

# Phase 4 independent final review 3

This is a fresh phase-wide review after the owner-authorized durable v2 graph and authority-foundation corrections. One read-only Sol-high critical reviewer verifies the exact package, attacks every Phase 4 domain and persistence boundary, and writes only the verdict. Phase 4's accepted runtime result for Component IR v2 is an explicit verified refusal until Phase 5 supplies the reviewed catalogue and adapter. Dual PASS accepts Phase 4 and opens only the separate read-only Phase 1-4 foundation audit. Phase 5 remains blocked until that audit's Critical findings are closed; no implementation or live/deployment surface opens here.
