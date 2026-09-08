---
{
  "id": "phase5-research-runtime-packaging-recovery-replan",
  "phase": "phase5",
  "status": "accepted",
  "kind": "architecture_replan",
  "goal": "Freeze the exhausted packaging review lineage and assign a smallest fresh correction for durable artifact participation, resource limits, PostgreSQL connections and worker process lifecycle.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after the exhausted review lineage is frozen, each open finding has one exact correction owner, product and test paths remain unchanged, deployability nonclaims remain explicit, and the fresh correction capsule is executable."},
  "risk_tags": ["critical", "architecture-replan", "research-packaging", "deployability"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-research-runtime-packaging.md", "sections": ["Phase 5 research runtime packaging"]}, {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Phase 5 ownership", "Phase 6 ownership", "Phase 7 ownership", "V1 release gate"]}],
  "dependency_gate": "phase5-research-runtime-packaging",
  "allowed_paths": ["paper-trader/docs/agent/DEPLOYABILITY.md", ".agent/runs/phase5-research-runtime-packaging/recovery-replan", "paper-trader/docs/agent/tasks/phase5-research-runtime-packaging-recovery-replan.md", "paper-trader/docs/agent/tasks/phase5-research-runtime-packaging-recovery-correction.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"],
  "nonclaims": ["No product/runtime patch, schema, migration, dependency, production service, external queue/object store, provider, broker, order, live, money, deployment or Phase 6 work."],
  "owner_gates": ["Stop before changing any product/test path or rerouting another review inside the exhausted capsule lineage."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["The original FAIL and exhausted recheck remain immutable and hash-addressed.", "P5-RRP-R001 through P5-RRP-R003 map to the fresh recovery-correction capsule without overlapping ownership.", "Product, test, schema, migration, dependency and configuration bytes remain unchanged.", "The deployment boundary remains local-only and names the exact Phase 6, Phase 7 and V1 release owners."],
  "test_plan": ["Verify original and recheck verdict hashes.", "Verify the recovery report and deployability hashes.", "Validate the successor capsule and serial programme dependency.", "Compare protected product and test hashes before and after the replan."],
  "stop_conditions": ["Any exhausted-review evidence hash changes; product or test bytes drift; a finding lacks one correction owner; the successor overlaps another active writer; deployment or production authority is implied."],
  "review": {"required": false, "assignment_id": "phase5_research_runtime_packaging_recovery_replan_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/phase5-research-runtime-packaging/recovery-replan/review-package.json", "review_paths": [".agent/runs/phase5-research-runtime-packaging/recovery-replan", "paper-trader/docs/agent/tasks/phase5-research-runtime-packaging-recovery-replan.md", "paper-trader/docs/agent/tasks/phase5-research-runtime-packaging-recovery-correction.md", "paper-trader/docs/agent/DEPLOYABILITY.md"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"], "output": ".agent/runs/phase5-research-runtime-packaging/recovery-replan/report.md", "verdicts": ["ARCHITECTURE_REPLAN_COMPLETE"]},
  "implementation": {"status": "accepted", "decision": "KEEP + HARDEN", "initial_verdict_sha256": "64df021079e8f698a3d08c240ee60c8beb8088ee5550bae86b798c8d33cf705d", "recheck_verdict_sha256": "777ec2144f776a8facf7bf84129862ce3687714c7c7b80cd45c5e05443dd8552", "report_sha256": "eb9509d3899312d2f67ade39eabb2adf604ac10f48f7c068573d109268273a03", "deployability_sha256": "87b3a97a8b863176e457f36121b3a6b7d57235bff34bffcb42aa156caf50e3a2", "open_findings": ["P5-RRP-R001", "P5-RRP-R002", "P5-RRP-R003"], "successor": "phase5-research-runtime-packaging-recovery-correction"}
}
---

# Phase 5 research runtime packaging recovery replan

The exhausted review lineage is immutable. The accepted report under
`.agent/runs/phase5-research-runtime-packaging/recovery-replan/` is the sole
architecture authority for the fresh correction and review.
