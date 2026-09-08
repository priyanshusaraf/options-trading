---
{
  "id": "phase4-integration-gate",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Reject or accept the bounded Phase 4 implementation through three canonical scenarios, named refusals, two-plane migration evidence, protected boundaries, and a review-ready package without patching product defects.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after every evidence contract, scenario, refusal, migration gate, protected hash, package check, structured check, and critical mutation passes and phase4-review is eligible."
  },
  "risk_tags": [
    "critical",
    "integration",
    "research-integrity",
    "deployability",
    "review-gate"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
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
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-dataset-causality",
  "allowed_paths": [
    "paper-trader/backend/tests/test_phase4_acceptance_scenarios.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    ".agent/review-package.json",
    "paper-trader/docs/agent/tasks/phase4-integration-gate.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-integration-gate"
  ],
  "nonclaims": [
    "The gate patches no product defect, implements no frontend/provider, deploys nothing, accesses no credential or production data, grants no live authority, and claims no production readiness.",
    "Local scenarios and disposable databases do not prove provider breadth, capacity, production rehearsal, rollback, security, observability, or release deployability."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would duplicate accepted IR, validator, resolver, hash, registry, research lineage, execution binding, owner boundary, or authority."
  ],
  "stop_conditions": [
    "A product defect needs a product edit; return it to its exclusive owner through a correction goal.",
    "Evidence is missing, stale, unattributed, irreproducible, or fails a negative case or mutation.",
    "A protected file changed, forbidden implementation entered scope, or package paths/HEAD differ."
  ],
  "deployment_impact": {
    "classification": "integration-evidence-only",
    "affected_dimensions": [
      "Verification",
      "Release evidence"
    ],
    "required_evidence": "Consolidated local matrix for schema/migrations, configuration contract, dependencies, service nonclaims, persistence, startup/restart, local restore, compatibility, ownership, secret exclusion, and bounded queries, with exact later ownership for open production dimensions."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "All three scenarios pass with exact validity, truth, capability, provenance, cache, and causal attribution.",
    "Registry snapshot, declaration, leaf/compound binding, plan, assessment, result/cache, accepted base-v2 receipt, and Phase 4 wrapper admission addresses form one exact chain while authored IR identity remains separate.",
    "All current-rule, invented-contract, invalid, missing/fill, stale/skew, future/forming, capability, owner, correction/cache, and authority refusals pass.",
    "SQLite compatibility and disposable PostgreSQL 16 reach exact heads and prove restart plus local restore.",
    "Protected hashes, source coverage, capsule DAG/paths/routes, imports, regressions, Phase 4 suite, killed mutations, and diff check pass.",
    "Report, gate JSON, and exact review package name every nonclaim and later deployment obligation."
  ],
  "test_plan": [
    "Run all Phase 4 tests and named IR/backtest/admission regressions with backend/.venv/bin/python through run_logged.py.",
    "Reproduce the registry-correction compatibility and four killed-and-restored mutations, then prove missing, unbound, stale, mismatched, and compound-owned declarations fail closed through integration.",
    "Prove admit_phase4_v2_strategy is the sole Phase 4 artifact constructor, the accepted v2 receipt is embedded unchanged, the complete wrapper has its own address, and execution/research stores persist identical canonical wrapper bytes without constructing a second admission fact.",
    "Run disposable PostgreSQL 16 for both migration planes, exact heads, restart, and local backup/restore.",
    "Run structured, coverage, DAG/path/route, protected-hash, import/package, architecture-validator, and git diff checks.",
    "Rerun retained mutation commands and prove failure under mutation and pass after exact restoration."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_integration_gate_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_phase4_acceptance_scenarios.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-integration-gate/owner_integration/report.md",
    "verdicts": [
      "INTEGRATION"
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

# Phase 4 integration gate

This is one durable implementation goal. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py`.
