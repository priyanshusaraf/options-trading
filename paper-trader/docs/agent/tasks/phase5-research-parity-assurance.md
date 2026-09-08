---
{
  "id": "phase5-research-parity-assurance",
  "phase": "phase5",
  "status": "accepted",
  "kind": "independent_assurance",
  "goal": "Independently verify the complete registered research universe, cache/provenance dimensions, vector/incremental causality, state restart/reset, invalidity, and guard restoration from frozen bytes.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after independent references and source-derived universes reproduce every claimed parity/provenance boundary without changing product or tests."},
  "risk_tags": ["critical", "read-only", "research-assurance", "causality"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-research-execution.md", "sections": ["Phase 5 research execution"]}],
  "dependency_gate": "phase5-research-execution",
  "allowed_paths": [".agent/runs/phase5-research-parity-assurance", "paper-trader/docs/agent/tasks/phase5-research-parity-assurance.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No product repair, performance, deployment, provider, live, order, or money claim."],
  "owner_gates": ["Stop and reject on any frozen-byte or complete-universe mismatch."],
  "stop_conditions": ["Reference results come from the implementation under review; only sampled nodes/cache fields/reset modes are checked; product/test bytes change."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Independent registry and provenance universes match product bytes.", "Independent mathematical references and causal prefixes match vector/incremental results.", "All state/reset/validity/cache dimensions and mutations pass with exact restoration.", "No product/test changes."],
  "test_plan": ["Freeze hashes; derive complete sets; independent golden recomputation; prefix and snapshot replay; cache-key mutation; restoration audit."],
  "review": {"required": false, "assignment_id": "phase5_research_parity_assurance_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": [".agent/runs/phase5-research-parity-assurance"], "exclude_paths": [], "output": ".agent/runs/phase5-research-parity-assurance/report.md", "verdicts": ["ASSURANCE"]},
  "assurance_result": {"verdict": "FAIL", "report_sha256": "0283012d0343be3b682b2bfbeacfe833ffa9cd2322106be57f79da9f31d8cad3", "deployability_sha256": "0c2271a2e5be0ee920ad66a5f400cbfd6fad6021652a61cb8b3edd4eae7f0bbd", "evidence_sha256": "46e4d24971036e58b48b839b19f196e5759d0f1ab45cc4989f3a9190b9459b6d", "product_test_changes": 0, "findings": ["P5-RPA-001", "P5-RPA-002"], "type3_failed": 63, "recursive_type5_failed": 18},
  "recovery_result": {"verdict": "PASS", "report": ".agent/runs/phase5-research-parity-assurance/recovery-report.md", "report_sha256": "5e0061947fba32880dab8313c92080309879e0d9fca0771b4797536e65ab440a", "evidence_sha256": "477b8fe24aeb86bde256545c037baee8816b98a821964fe0ab1fce15b2a9a636", "semantic_baseline_verdict_sha256": "938e98066f386077bb577968b5b9a37bcbe6da4c59b6b0c00c8a1a2161b77b75", "registered_components": 309, "independent_analytical": 125, "type3_completed": 63, "type5_completed": 60, "mutations": 10, "open_findings": [], "successor": "phase5-bounded-sweeps-cache-artifacts"}
}
---

# Phase 5 research parity assurance

This evidence-only capsule independently checks the accepted research execution package.
