---
{
  "id": "phase5-capital-admission-assurance",
  "phase": "phase5",
  "status": "paused_owner_gate",
  "kind": "independent_assurance",
  "goal": "Independently freeze, replay and critically review the complete capital contracts, migration, transaction, shadow/recovery and lineage boundary without changing product or tests.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after current-byte inventories, SQLite/PostgreSQL migrations and contention, every recovery/lineage case, mutation restoration, broad compatibility and one exact critical reviewer return SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "money", "read-only", "assurance", "postgresql", "migration"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "sections": ["Invariants", "Complete failure and test matrix", "Deployment impact", "Owner gates and nonclaims"]}, {"path": "paper-trader/docs/superpowers/plans/phase5-capital-admission.md", "sections": ["Dependency order", "Slice 5: capital assurance and critical review"]}],
  "dependency_gate": "phase5-capital-admission-shadow-recovery",
  "allowed_paths": [".agent/review-package.json", ".agent/runs/phase5-capital-admission-assurance", "paper-trader/docs/agent/tasks/phase5-capital-admission-assurance.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"],
  "nonclaims": ["No product/test repair, behavior switch, production runtime, deployment, live, broker, order or customer-money authority."],
  "owner_gates": ["Reviewer is read-only; stop before any product/test correction or owner-gated action."],
  "stop_conditions": ["Any product/test hash drifts; state/consumer/side-effect universe is sampled; PostgreSQL or restore evidence is missing; mutation is vacuous; reviewer changes reviewed bytes."],
  "deployment_impact": {"classification": "migration-required", "highest_claim": "locally_runnable", "future_owner": "Phase 6/V1 retain production-shaped install, topology, backup/restore, capacity, rollout and deployment."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "reviewer": "gpt-5.6-sol", "reviewer_reasoning_effort": "high", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Complete product/table/state/transition/consumer/side-effect inventories match the design.", "SQLite/PostgreSQL and restore/recovery evidence replays from frozen bytes.", "All mutations fail and restore exact hashes.", "One independent critical reviewer returns SPEC PASS and QUALITY PASS."],
  "test_plan": ["Hash freeze; independent inventories; exact migration/contention/recovery replay; mutation audit; compatibility phase tier; deployability matrix; package/reviewer/root gate."],
  "review": {"required": true, "assignment_id": "phase5_capital_critical_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/execution", "paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py", "paper-trader/docs/engineering/decisions/0016-execution-product-policy.md", "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md", "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", ".agent/runs/phase5-capital-admission-*"], "exclude_paths": ["paper-trader/frontend", "paper-trader/backend/app/providers"], "output": ".agent/runs/phase5-capital-admission-assurance/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "failed_review": {"package_sha256": "cb6a1a0c727318f13fa57e5609348abd030b624f257c7bd4aef6994b4b2a015a", "verdict": ".agent/runs/phase5-capital-admission-assurance/review/verdict.json", "verdict_sha256": "89d05b05650b9775966d4ae263d833794f56f8f17690e9a390502191db9512b8", "spec": "FAIL", "quality": "FAIL", "findings": 9, "focused_recheck_remaining": 1, "correction_capsule": "paper-trader/docs/agent/tasks/phase5-capital-admission-critical-correction.md"},
  "recheck_failure": {"package_sha256": "c18e21f50645efa9e34104007b432778597f6e556c843c4bbfcba4da290f7bd6", "verdict": ".agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json", "verdict_sha256": "78e81a79606b6e70c2ed4d152a5edfab54a56dde30eee03a325cc8bf7762f8a9", "spec": "FAIL", "quality": "FAIL", "open_original_findings": ["P5-CAP-004"], "new_findings": ["P5-CAP-R001"], "recheck_exhausted": true, "disposition": "STOP_FOR_OWNER_REPLAN"}
}
---

# Phase 5 capital-admission assurance

This is the one integrated money-critical review route before Phase 5 integration.
