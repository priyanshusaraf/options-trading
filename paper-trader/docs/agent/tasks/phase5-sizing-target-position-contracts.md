---
{
  "id": "phase5-sizing-target-position-contracts",
  "phase": "phase5",
  "status": "accepted",
  "kind": "implementation_sequence",
  "goal": "Implement pure Execution Product Policy, sizing and pending-order-aware target-position contracts while preserving current allocator and product behavior.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after every sizing mode, numeric refusal, rounding/cap/fee rule, product compatibility path and held/pending target delta passes direct tests and guard mutations without database, broker or runner wiring."},
  "risk_tags": ["critical", "sizing", "target-position", "product-policy", "compatibility"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "sections": ["Execution Product Policy", "SizingPolicy and SizingDecision", "TargetPositionRequest", "Invariants"]}, {"path": "paper-trader/docs/engineering/decisions/0016-execution-product-policy.md", "sections": ["Decision", "Contract", "Authority and dependency direction"]}, {"path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "sections": ["Sizing hierarchy", "Target position and pending orders"]}],
  "dependency_gate": "phase5-capital-admission-architecture",
  "allowed_paths": ["paper-trader/backend/app/execution/product_policy.py", "paper-trader/backend/app/execution/sizing.py", "paper-trader/backend/app/execution/target_position.py", "paper-trader/backend/app/execution/capital_compatibility.py", "paper-trader/backend/tests/test_execution_product_policy.py", "paper-trader/backend/tests/test_sizing_target_position.py", "paper-trader/backend/tests/test_allocator.py", "paper-trader/docs/agent/DEPLOYABILITY.md", "paper-trader/docs/agent/tasks/phase5-sizing-target-position-contracts.md", ".agent/runs/phase5-sizing-target-position-contracts"],
  "nonclaims": ["No database, migration, runner, broker, order, live, money, provider or frontend behavior change."],
  "owner_gates": ["Stop before wiring a caller or changing current product/quantity behavior."],
  "stop_conditions": ["A strategy selects provider/broker authority; numeric invalidity defaults to zero; current allocator behavior drifts; target delta ignores unresolved orders."],
  "deployment_impact": {"classification": "compatible", "highest_claim": "locally_runnable", "future_owner": "Schema and runtime obligations remain in the exact following capital capsules."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Pure content-addressed policies and decisions use fixed-point/minor-unit arithmetic.", "Current options/equity/futures behavior is exact under compatibility adapters.", "Held plus pending quantity derives one deterministic target delta.", "No-resize, pending-order and numeric guards redden under mutation."],
  "test_plan": ["All sizing modes and invalid numerics; product parity/refusals; rounding/fees/caps; pending-order target deltas; exact attribution; exit independence; killed/restored guards."],
  "review": {"required": false, "assignment_id": "phase5_sizing_contracts_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/execution/product_policy.py", "paper-trader/backend/app/execution/sizing.py", "paper-trader/backend/app/execution/target_position.py"], "exclude_paths": ["paper-trader/backend/app/engine", "paper-trader/backend/app/providers", "paper-trader/frontend"], "output": ".agent/runs/phase5-sizing-target-position-contracts/report.md", "verdicts": ["CONTRACT"]},
  "result": {"verdict": "CONTRACT", "status": "PASS", "report": ".agent/runs/phase5-sizing-target-position-contracts/report.md", "report_sha256": "ce0a7bb56654b6c45d5c9ef7c01273a2ac8ae997761f2b275f3908eb0df3f7c4", "direct_tests": 51, "compatibility_tests": 89, "mutations": 6, "runtime_consumers": 0, "execution_head": "0040", "research_head": "0011"}
}
---

# Phase 5 sizing and target-position contracts

This slice is pure and unwired. It preserves the current allocator and order path.
