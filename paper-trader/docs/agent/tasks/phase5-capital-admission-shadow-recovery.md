---
{
  "id": "phase5-capital-admission-shadow-recovery",
  "phase": "phase5",
  "status": "accepted",
  "kind": "implementation_sequence",
  "goal": "Produce explicit paper/mock shadow admission receipts and prove reservation recovery plus campaign/tranche lineage without allowing the new decision to control an order.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after current allocator decisions and new receipts compare byte-for-byte across the complete matrix; every broker-uncertainty and lineage transition replays from durable facts; provider/live/order paths are tripwired; and entry blocks never disable risk-reducing exits."},
  "risk_tags": ["critical", "paper-shadow", "recovery", "broker-uncertainty", "position-lineage"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "sections": ["Pending-order and broker-uncertainty behavior", "Campaign, tranche and fill allocation", "Why-trade and why-not-trade receipt"]}, {"path": "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md", "sections": ["Decision", "Invariants", "Legacy rows and migration"]}],
  "dependency_gate": "phase5-capital-admission-transaction",
  "allowed_paths": ["paper-trader/backend/app/execution/capital_shadow.py", "paper-trader/backend/app/execution/capital_recovery.py", "paper-trader/backend/app/execution/position_lineage.py", "paper-trader/backend/scripts/capital_admission_shadow.py", "paper-trader/backend/tests/test_capital_admission_shadow.py", "paper-trader/backend/tests/test_capital_admission_recovery.py", "paper-trader/backend/tests/test_position_campaign_lineage.py", "paper-trader/backend/tests/test_capital_admission_schema.py", "paper-trader/backend/tests/test_money_repository_isolation.py", "paper-trader/backend/tests/test_book_isolation.py", "paper-trader/docs/agent/DEPLOYABILITY.md", "paper-trader/docs/agent/tasks/phase5-capital-admission-shadow-recovery.md", ".agent/runs/phase5-capital-admission-shadow-recovery"],
  "nonclaims": ["No runner/live-broker wiring, order control, authoritative sizing, provider network, frontend, deployment, production, live or customer-money claim."],
  "owner_gates": ["Stop before the new result influences current allocator, broker, order or position behavior."],
  "stop_conditions": ["Shadow controls an order; uncertain reservation releases; lineage replaces Position; legacy facts are inferred; entry blockage disables exits."],
  "deployment_impact": {"classification": "architecture-changing", "highest_claim": "locally_runnable", "future_owner": "Critical assurance follows; production service/health/rollout remain Phase 6/V1 and named packaging owners."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Explicit paper/mock shadow receipt matches the current allocator without controlling it.", "Every uncertain broker state retains conservative capital until evidence resolves.", "Campaign/tranche/fill allocations reconstruct exact held inventory without replacing Position.", "Risk-reducing exits remain reachable under all entry blocks."],
  "test_plan": ["Allocator shadow parity; crash/send/ack/reject/partial/late/expiry/cancel-fill/external-order/takeover; add/reduce/close/opposing campaigns; legacy visibility; provider/order tripwires; conservative-release and exit mutations."],
  "review": {"required": false, "assignment_id": "phase5_capital_shadow_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/execution/capital_shadow.py", "paper-trader/backend/app/execution/capital_recovery.py", "paper-trader/backend/app/execution/position_lineage.py"], "exclude_paths": ["paper-trader/backend/app/providers", "paper-trader/backend/app/engine/runner.py", "paper-trader/backend/app/engine/live_broker.py", "paper-trader/frontend"], "output": ".agent/runs/phase5-capital-admission-shadow-recovery/report.md", "verdicts": ["SHADOW_RECOVERY"]},
  "acceptance_record": {"decision": "ACCEPTED", "report": ".agent/runs/phase5-capital-admission-shadow-recovery/report.md", "report_sha256": "b3f836544586a4259534eb06d8ddedf5a8a7b80f83570fc24f30cedbf3dc28fb", "scope_correction": ".agent/runs/phase5-capital-admission-shadow-recovery/scope-correction.md", "scope_correction_sha256": "cc6b835576fe78e3d59ca67ed39ffc6b64df5dd6ecc78716cb490eacdc95f48d", "verdict": "SHADOW_RECOVERY PASS"}
}
---

# Phase 5 capital shadow and recovery

This slice records comparison evidence only and cannot control an order.

The accepted schema-consumer AST gate is a required transitive regression path.
This capsule may update it only to enumerate the three new unwired modules and
must continue to reject every runner, provider, broker and frontend consumer.
