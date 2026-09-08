---
{
  "id": "phase5-language-resource-assurance",
  "phase": "phase5",
  "status": "accepted",
  "kind": "independent_assurance",
  "goal": "Independently enumerate and mutate every language, lowering, ResourcePlan, role, state, validity, tier, and identity dimension from frozen contract bytes.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after an independently derived universe matches every closed product field and all omission, extra, hidden-demand, boundary, and identity mutations produce the required refusal before downstream work starts."},
  "risk_tags": ["critical", "read-only", "complete-universe", "identity"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-language-resource-contracts.md", "sections": ["Phase 5 language and ResourcePlan contracts"]}],
  "dependency_gate": "phase5-language-resource-contracts",
  "allowed_paths": [".agent/runs/phase5-language-resource-assurance", "paper-trader/docs/agent/tasks/phase5-language-resource-assurance.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No product/test repair, catalogue, runtime, provider, deployment, live, order, or money authority."],
  "owner_gates": ["Stop and reject on any universe mismatch or mutable input."],
  "stop_conditions": ["Expected sets come from implementation-owner manifests or counts alone; a mutation does not reach the normal validator; product/test bytes change."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 1,
  "assignments": [{"id": "phase5_language_resource_assurance_owner", "depends_on": [], "write_paths": [".agent/runs/phase5-language-resource-assurance"], "model": "gpt-5.6-sol", "reasoning_effort": "medium", "authority": "evidence-only; product and tests read-only"}],
  "first_result": {"verdict": "ASSURANCE FAIL", "report": ".agent/runs/phase5-language-resource-assurance/report.md", "report_sha256": "27c8fb3d9465c52bfb6188df269182b6e7ba1ab85c20d463d6bea7b482cdad13", "passed": 102, "failed": 4, "findings": ["P5-LRA-001", "P5-LRA-002", "P5-LRA-003", "P5-LRA-004"], "recheck_remaining": 0, "correction_report_sha256": "8e52995ba21acfc264d864f105afa7e2446dd7e9caf9862c6d432f27b2644473"},
  "result": {"verdict": "ASSURANCE PASS", "report": ".agent/runs/phase5-language-resource-assurance/recheck-report.md", "report_sha256": "1bd0dd8d61aa6c4160be380339acf18efc328a272db26f44c701d6bae33b1ec2", "passed": 106, "failed": 0, "closed_findings": ["P5-LRA-001", "P5-LRA-002", "P5-LRA-003", "P5-LRA-004"], "protected_restoration": "exact"},
  "acceptance": ["Independent sets match every closed contract universe.", "At-limit and first-over cases cover every tier dimension.", "Hidden leaves/demand and semantic/plan/policy identity collapse mutations fail.", "Exact restoration and protected hashes pass."],
  "test_plan": ["Freeze hashes; independently derive source sets; replay normal validators; run one-at-a-time omission/extra/reorder/wrong-binding mutations; verify restoration."],
  "review": {"required": false, "assignment_id": "phase5_language_resource_assurance_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": [".agent/runs/phase5-language-resource-assurance"], "exclude_paths": [], "output": ".agent/runs/phase5-language-resource-assurance/report.md", "verdicts": ["ASSURANCE"]}
}
---

# Phase 5 language/resource assurance

This evidence-only capsule independently checks the contract universe and cannot repair it.
