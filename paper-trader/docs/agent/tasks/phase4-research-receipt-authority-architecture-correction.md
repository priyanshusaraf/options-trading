---
{
  "id": "phase4-research-receipt-authority-architecture-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Freeze the schema-free KEEP + HARDEN correction that makes the actual execution loader require the exact research admission receipt and immutable research graph before dataset/assessment verification and terminal V2_RUNTIME_UNAVAILABLE.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work needed to finish Phase 4 after immutable phase4-final-review-4 failed. One fresh Sol-medium architecture owner may edit only the declared architecture documents, capsules, programme, CURRENT, and ignored evidence. Product, tests, schemas, migrations, review package, verdicts, frontend, providers, deployment, live, and money paths are read-only.",
    "stopping_condition": "Complete only when one schema-free authority chain, the DP-008 search across every current Phase 1-4 consumer, transitive evidence invalidation, implementation evidence, deployability impact, package rebuild, and fresh final-review-5 route are exact. Stop if closure needs a second verifier/hash/dispatcher, caller manual verification, schema work, runtime enablement, or another product boundary."
  },
  "risk_tags": ["critical", "architecture-correction", "research-authority", "consumer-enforcement", "evidence-invalidation"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["9. Ownership, authority, and persistence", "10. Acceptance scenarios and refusals", "11. Deployment contract", "13. Authority-foundation correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["5. Verification cadence", "8. Authority-correction serial route"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-001 — Distinct facts collapsed into one representation", "DP-002 — Syntactic self-consistency mistaken for authority", "DP-003 — Mocked seam presented as lifecycle evidence", "DP-004 — Immutable envelope over mutable or time-incoherent facts", "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact", "DP-006 — Database session timezone changed copied authority instants", "DP-007 — One JSON helper encoded different shapes by database dialect", "DP-008 — Manual prerequisite verification substituted for the consuming seam"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "Phase 4 ownership"]}
  ],
  "dependency_gate": "phase4-final-review-4",
  "input_evidence": [".agent/runs/phase4-final-review-4/verdict.json"],
  "accepted_decision": {
    "disposition": "KEEP + HARDEN",
    "classification": "schema-free-phase4-research-receipt-authority-hardening",
    "sole_chain": "load_verified_admission -> reconstruct_phase4_artifact -> require_phase4_current -> research.domain.admissions.require_admission -> dataset/assessment verification -> V2_RUNTIME_UNAVAILABLE",
    "research_authority": "The existing research.domain.admissions.require_admission is the sole verifier of exact ResearchStrategyAdmission and ResearchIrV2GraphVersion against the reconstructed artifact.",
    "order": "Research receipt and graph verification precedes dataset and assessment verification; complete current companion records alone reach the unchanged terminal refusal.",
    "forbidden": ["second verifier", "second hash", "generic dispatcher", "caller manual preverification", "post-return diagnostic as enforcement", "runtime enablement"]
  },
  "consumer_search": [
    {"path": "paper-trader/backend/app/backtest/repository.py", "scope": "loader, enqueue, retry, reclaim, job and cache-facing admission reads"},
    {"path": "paper-trader/backend/app/backtest/sweep.py", "scope": "retry, reclaim, pinned-worker, cache and job consumers"},
    {"path": "paper-trader/backend/app/core/deployments.py", "scope": "deployment create and activation consumers"},
    {"path": "paper-trader/backend/app/engine/runner.py", "scope": "runner entry consumer"},
    {"path": "paper-trader/backend/app/engine/broker.py", "scope": "broker evaluation consumer"}
  ],
  "transitive_invalidation": ["complete-loader authority evidence", "two-plane fresh-process integration", "deployment/runner/broker/enqueue/retry/reclaim/pinned/cache/job no-side-effect evidence", "affected adversarial rows", "official review package", "review-readiness claims"],
  "route_decision": "Implementation owns the bounded integrated selector, affected consumer reruns, adversarial reruns, and official package rebuild after product/test byte freeze. No separate integration capsule is needed; discovery of a larger boundary stops for architecture amendment. Fresh phase4-final-review-5 follows serially.",
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase4-research-receipt-authority-architecture-correction.md",
    "paper-trader/docs/agent/tasks/phase4-research-receipt-authority-correction.md",
    "paper-trader/docs/agent/tasks/phase4-final-review-5.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-research-receipt-authority-architecture-correction"
  ],
  "product_paths_read_only": ["paper-trader/backend", "paper-trader/frontend", ".agent/review-package.json", ".agent/runs/phase4-final-review-4/verdict.json"],
  "nonclaims": ["Architecture acceptance changes no product or test behavior and does not claim Phase 4 closure, review readiness, deployability, runtime enablement, production readiness, live authority, or money authority.", "Final-review-4 remains an immutable historical FAIL.", "No separate integration capsule is authorized because the bounded integration and package evidence can live honestly in implementation."],
  "owner_gates": ["Stop before product, test, schema, migration, package, verdict, frontend, provider, deployment, credential, production, live, money, destructive, legal, or commercial change.", "Stop if the correction cannot use the existing verifier and loader chain without a new abstraction or expanded boundary."],
  "stop_conditions": ["Any research receipt or graph can be absent, stale, tampered, wrong-owner, or cross-plane substituted while the actual loader reaches V2_RUNTIME_UNAVAILABLE.", "A caller-side check or second verifier substitutes for the actual loader chain.", "Consumer invalidation, dialect evidence, mutation evidence, package rebuild, or serial final review is implicit."],
  "deployment_impact": {"classification": "documentation-only-phase4-research-receipt-authority-architecture", "required_evidence": "Record the planned schema-free verifier composition, unchanged heads/dependencies/services/configuration/providers/frontend/runtime terminal, SQLite and PostgreSQL 16 local evidence, package rebuild, and all release/deployment nonclaims."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["The sole loader chain and exact verifier order are frozen without a second authority mechanism.", "Every current production loader consumer is mapped and its dependent complete-authority/no-side-effect evidence is invalidated.", "Implementation owns exact missing/tampered/wrong-owner/cross-plane/fresh-process/current-terminal evidence on SQLite and disposable PostgreSQL 16 plus killed/restored invocation and order guards.", "The correction is schema-free and non-enabling, with unchanged terminal refusal and exact deployment nonclaims.", "Final-review-4 stays immutable; implementation plus integrated package rebuild and fresh independent final-review-5 are serially routed."],
  "test_plan": ["Inspect the actual loader, complete-current verifier, existing research verifier, decisive integration, and every production loader caller.", "Validate capsule architecture, JSON/TOML, source coverage, programme seriality, protected hashes, scoped diff, and evidence hashes.", "Write the architecture decision and acceptance evidence under the ignored assignment directory."],
  "review": {"required": false, "assignment_id": "phase4_research_receipt_authority_architect", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "paper-trader/docs/reports/phase4-source-coverage.json", "paper-trader/docs/agent/DEPLOYABILITY.md", "paper-trader/docs/agent/DEFECT_PATTERNS.md", "paper-trader/docs/agent/tasks/phase4-research-receipt-authority-architecture-correction.md", "paper-trader/docs/agent/tasks/phase4-research-receipt-authority-correction.md", "paper-trader/docs/agent/tasks/phase4-final-review-5.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", ".agent/review-package.json"], "output": ".agent/runs/phase4-research-receipt-authority-architecture-correction/owner/report.md", "verdicts": ["ACCEPTED", "BLOCKED"]},
  "protected_files": {"paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240", "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae", "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38", "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"}
}
---

# Phase 4 research receipt authority architecture correction

This accepted architecture keeps the existing authority objects and hardens only their composition at the actual execution loader. It authorizes no product changes itself.
