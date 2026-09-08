---
{
  "id": "phase5-scenario-assurance",
  "phase": "phase5",
  "status": "accepted",
  "kind": "independent_assurance",
  "goal": "Independently replay every canonical scenario, tier boundary, role/binding seed, provider refusal and persisted lineage from frozen integrated bytes.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after independent scenario inputs and expected facts cover the complete declared universe, real persistence/reload paths pass, mutations fail, and no product/test repair occurs."},
  "risk_tags": ["critical", "read-only", "scenario-assurance"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-canonical-scenario-gate.md", "sections": ["Phase 5 canonical scenario gate"]}],
  "dependency_gate": "phase5-canonical-scenario-gate",
  "allowed_paths": [".agent/runs/phase5-scenario-assurance", "paper-trader/docs/agent/tasks/phase5-scenario-assurance.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No product repair, deployment, provider, live, order, money, tier entitlement, or production claim."],
  "owner_gates": ["Stop and reject on missing frozen inputs, mocked critical seam, or any owner gate approach."],
  "stop_conditions": ["Expected results come from the implementation owner, a scenario is sampled, persistence/reload is mocked, or product/test bytes change."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All three canonical scenarios and three carry-through seed cases replay independently.", "Every role, provider requirement, ResourcePlan and tier dimension is complete.", "SQLite/PostgreSQL persisted reload and refusal mutations pass.", "No product/test changes."],
  "test_plan": ["Freeze hashes; independent fixture and universe derivation; direct scenario replay; omission/wrong-binding/tier/provider mutations; restoration and nonclaim audit."],
  "review": {"required": false, "assignment_id": "phase5_scenario_assurance_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": [".agent/runs/phase5-scenario-assurance"], "exclude_paths": [], "output": ".agent/runs/phase5-scenario-assurance/report.md", "verdicts": ["ASSURANCE"]},
  "implementation": {"status": "accepted", "report_sha256": "e79096dfce0d9e6c0fa429e7d469442d81dcbef057c8ff4a2d4f45194057fe2a", "evidence_sha256": "b8c814b5318d3dd953ce78619ef2bc3841dfe0a7257b47edb94f60777b28ddb8", "freeze_sha256": "d6e0bea188d2697d5d5134d1afb672f057210ca91424d2b0866b24e9b8d344c9", "oracle_sha256": "1b210d84d3dfc578c27f8edb30d616e9084d2ff0015c2ee191971c95dbdd44ce", "frozen_passed": 44, "frozen_skipped": 1, "postgresql16_passed": 1, "mutations": 3, "verdict": "ASSURANCE PASS"}
}
---

# Phase 5 scenario assurance

This evidence-only capsule independently checks the canonical scenario package.
