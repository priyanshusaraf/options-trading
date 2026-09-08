---
{
  "id": "phase5-catalogue-wave-2-scope",
  "phase": "phase5",
  "status": "deferred",
  "kind": "exact_deferral",
  "goal": "Own the exact WAVE_2_DEFERRED catalogue entries without allowing them into the Phase 5 V1 claim unless explicitly promoted and fully conformed before review.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only when each deferred entry is either retained outside V1 with rationale or promoted through the same node/resource/reference/conformance gates before phase5-review."},
  "risk_tags": ["deferred", "catalogue"],
  "required_docs": [{"path": "paper-trader/docs/reports/phase5-v1-catalogue.json", "sections": []}],
  "dependency_gate": "phase5-first-party-analytical-catalogue",
  "deadline": "Before phase5-review if any deferred entry is promoted into the V1 claim.",
  "allowed_paths": ["paper-trader/docs/reports/phase5-v1-catalogue.json", "paper-trader/docs/agent/tasks/phase5-catalogue-wave-2-scope.md", ".agent/runs/phase5-catalogue-wave-2-scope"],
  "nonclaims": ["Deferred entries are not part of V1 catalogue acceptance and have no runtime/provider/live authority."],
  "owner_gates": ["Stop before licence-sensitive adoption or expanding V1 scope without accepted evidence."],
  "stop_conditions": ["A deferred entry is registered or claimed without full contract/conformance evidence."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Every deferred entry remains explicitly outside V1 or passes the full promotion gate."],
  "test_plan": ["Inventory diff; production registry search; conformance evidence check for any promotion."],
  "review": {"required": false, "assignment_id": "phase5_wave2_scope_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/docs/reports/phase5-v1-catalogue.json"], "exclude_paths": [], "output": ".agent/runs/phase5-catalogue-wave-2-scope/report.md", "verdicts": ["SCOPE"]}
}
---

# Phase 5 catalogue wave-2 scope

This exact deferral prevents obscure entries from silently entering the V1 claim.
