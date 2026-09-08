---
{
  "id": "phase5-bounded-sweeps-cache-artifacts",
  "phase": "phase5",
  "status": "accepted",
  "kind": "research_scale",
  "goal": "Harden bounded parallel sweeps, provenance-complete cache reuse, artifact/result lineage, tenant-safe sharing, storage budgets and research cost accounting around the existing authorities.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after bounded sweeps cannot exceed ResourcePlan/tier/tenant/provider limits, every cache/artifact/result identity is complete, corruption and stampedes fail closed, cancellation/retry/restart preserve lifecycle authority, and storage/cost bounds are observable."},
  "risk_tags": ["important", "cache", "artifacts", "concurrency", "tenancy"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Research execution and cache boundary", "Canonical ResourcePlan schema", "Deployment impact and nonclaims"]}],
  "dependency_gate": "phase5-research-parity-assurance",
  "allowed_paths": ["paper-trader/backend/app/backtest/sweep.py", "paper-trader/backend/app/backtest/cache.py", "paper-trader/backend/app/backtest/dataset_store.py", "paper-trader/backend/app/backtest/artifacts.py", "paper-trader/backend/tests/test_phase5_bounded_sweeps_cache_artifacts.py", ".agent/runs/phase5-bounded-sweeps-cache-artifacts", "paper-trader/docs/agent/tasks/phase5-bounded-sweeps-cache-artifacts.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No cross-tenant/licence feed sharing, production object store, deployment, provider, live, order, or money authority.", "Measured local cost is not commercial pricing or production capacity."],
  "owner_gates": ["Stop before licence-sensitive sharing, object-store dependency adoption, production retention/destruction, commercial pricing, or deployment."],
  "stop_conditions": ["Any cache key omits semantic/data/truth/policy/implementation identity; tenant or licence scope is crossed; queues/storage are unbounded; corruption or cancellation can mint reusable authority."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Local artifact adapter, bounded storage/concurrency and restart evidence; production object store, retention, backup and capacity remain C9/V1 gates."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Sweep concurrency, queue depth, cache bytes, artifact bytes and dynamic windows never exceed the lowest applicable bound.", "Cache/result/artifact identities include every semantic, implementation, dataset, truth, policy, ResourcePlan and owner dimension.", "Identical work shares only inside accepted owner/data/licence scope; cross-tenant reuse refuses.", "Cold starts, stampedes, corrupt/missing artifacts, cancellation, retry, restart and eviction preserve exact lifecycle and authority.", "Structured local cost metrics have bounded cardinality and exact attribution."],
  "test_plan": ["At-limit/first-over concurrency/storage/cache/window matrix.", "Complete cache/provenance dimension mutations.", "Cross-tenant/licence refusal and stampede/cold-start concurrency.", "Corruption, cancellation, retry, restart, eviction and exact restoration.", "Research cost attribution and affected backtest subsystem."],
  "review": {"required": false, "assignment_id": "phase5_sweeps_cache_artifacts_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/backtest", "paper-trader/backend/tests/test_phase5_bounded_sweeps_cache_artifacts.py"], "exclude_paths": [], "output": ".agent/runs/phase5-bounded-sweeps-cache-artifacts/owner/report.md", "verdicts": ["SCALE", "IDENTITY"]},
  "implementation": {"status": "accepted", "report_sha256": "3cf17bae91eebe1986c788e82045efa0008d1bf3558a421f6017d43013ff1787", "deployability_sha256": "f54448a0c177fd43ff512ad96add95e3be75c14b02d71bfc4a1d0bc95ff0bc94", "evidence_sha256": "3714c3b2ee4088fb7d8123d5253c063582bdee9cea736f37a9e0436893e9ff2f", "focused_passed": 54, "affected_passed": 148, "identity_fields": 25, "mutations": 4}
}
---

# Phase 5 bounded sweeps, cache and artifacts

This capsule scales research within explicit local bounds and preserves existing dataset, cache and lifecycle authority.
