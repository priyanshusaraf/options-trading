---
{
  "id": "phase5-adv-006-runtime-assurance",
  "phase": "phase5",
  "status": "accepted",
  "kind": "independent_assurance",
  "goal": "Independently recompute the complete v2 lifecycle and consumer universe from frozen runtime bytes and reject missing states, transitions, consumers, side effects, process boundaries, or restoration evidence.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after independent current-byte replay covers every declared lifecycle state, transition and consumer, reproduces process death and PostgreSQL contention, verifies guard mutations and restoration, and reports PASS without changing product or tests."},
  "risk_tags": ["critical", "read-only", "runtime-assurance"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-adv-006-runtime.md", "sections": ["Phase 5 exclusive v2 runtime lifecycle"]}],
  "dependency_gate": "phase5-adv-006-runtime",
  "allowed_paths": [".agent/runs/phase5-adv-006-runtime-assurance"],
  "nonclaims": ["No product/test repair, runtime authority, deployment, live, order, or money claim."],
  "owner_gates": ["Stop on any frozen-byte mismatch or missing product evidence; return the blocker to the implementation owner."],
  "stop_conditions": ["Assurance relies on owner counts, sampled consumers, in-process death, self-derived expected state, or mutable product/test bytes."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Independent inventories equal the complete product state/transition/consumer sets.", "Direct SQLite and PostgreSQL 16 traces replay from frozen bytes.", "Every required mutation fails and exact restoration passes.", "No product/test path changes."],
  "test_plan": ["Hash freeze; independent source inventory; exact command metadata; focused replay; mutation/restore audit; protected hashes."],
  "review": {"required": false, "assignment_id": "phase5_adv_006_runtime_assurance_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": [".agent/runs/phase5-adv-006-runtime-assurance"], "exclude_paths": [], "output": ".agent/runs/phase5-adv-006-runtime-assurance/report.md", "verdicts": ["ASSURANCE"]},
  "result": {"assurance": "PASS", "report": ".agent/runs/phase5-adv-006-runtime-assurance/report.md", "report_sha256": "0797fb394fa89ec8dfbf2981c2e9b377d5b08790335d108eedb0b4759dfaac46", "verdict": ".agent/runs/phase5-adv-006-runtime-assurance/verdict.json", "verdict_sha256": "ff0b2f59985a72be021b9f9ba509376dc449b97c838290a8cd28d2d9898a81e5", "product_test_manifest_sha256": "53f154edb2de082c5b34bc747e35e9a9cc4cb097c6454fd350b8fffd635d4622"}
}
---

# Phase 5 runtime lifecycle assurance

This capsule independently checks the accepted runtime package and cannot repair it.
